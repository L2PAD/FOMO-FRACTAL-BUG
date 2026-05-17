"""
ALT RADAR V11 — Spot Radar Engine (v3 — batch optimized)
==============================================================
Key changes from v2:
- Batch loads ALL data from MongoDB upfront (5 queries instead of N*5)
- Source field populated in every row (observations/verdict/snapshot)
- Debug stats include source distribution
"""

from typing import List, Dict, Optional
from pymongo import MongoClient, DESCENDING
import os

from .types import (
    SpotRadarRow, SpotVenue, Direction, Verdict, RiskLevel,
    StructureType, MomentumBuild, ConvictionTier, SpotFeatures, SpotExplain,
    DataQualityInfo, HorizonSignal, HorizonsInfo, IntegrityInfo,
)
from .observations_provider import build_rich_features_batch
from .universe import get_spot_main_symbols, get_spot_alpha_symbols
from market_data.service import get_venue_info_batch

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        _client = MongoClient(mongo_url)
        _db = _client[db_name]
    return _db


# ═══════════════════════════════════════════════════════════════
# BATCH DATA LOADER
# ═══════════════════════════════════════════════════════════════

def _load_all_data(symbols: List[str]) -> Dict:
    """Load all required data from MongoDB in 5 batch queries."""
    db = _get_db()

    # 1. Observations (rich data, keyed by symbol)
    obs_map = build_rich_features_batch(symbols)

    # 2. Verdicts
    verdict_docs = list(db["exchange_verdicts"].find(
        {"symbol": {"$in": symbols}}, {"_id": 0}
    ))
    verdict_map = {d["symbol"]: d for d in verdict_docs}

    # 3. Snapshots (keyed by BASE+USDT)
    bases = [s.replace("USDT", "") for s in symbols]
    snapshot_docs = list(db["exchange_symbol_snapshots"].find(
        {"base": {"$in": bases}}, {"_id": 0}
    ))
    snapshot_map = {d["base"] + "USDT": d for d in snapshot_docs}

    # 4. Universe scores
    universe_docs = list(db["exchange_symbol_universe"].find(
        {"symbol": {"$in": symbols}}, {"_id": 0}
    ))
    universe_map = {d["symbol"]: d for d in universe_docs}

    # 5. Funding context (latest per symbol)
    funding_pipeline = [
        {"$match": {"symbol": {"$in": symbols}}},
        {"$sort": {"ts": -1}},
        {"$group": {"_id": "$symbol", "doc": {"$first": "$$ROOT"}}},
    ]
    funding_docs = list(db["exchange_funding_context"].aggregate(funding_pipeline))
    funding_map = {}
    for d in funding_docs:
        doc = d["doc"]
        doc.pop("_id", None)
        funding_map[d["_id"]] = doc

    # 6. Market context
    market_docs = list(db["exchange_market_context"].find(
        {"symbol": {"$in": symbols}}, {"_id": 0}
    ))
    market_map = {d["symbol"]: d for d in market_docs}

    return {
        "obs": obs_map,
        "verdicts": verdict_map,
        "snapshots": snapshot_map,
        "universe": universe_map,
        "funding": funding_map,
        "market": market_map,
    }


# ═══════════════════════════════════════════════════════════════
# SPOT FEATURE COMPUTATION (all 0-1)
# ═══════════════════════════════════════════════════════════════

def compute_spot_features_from_cache(symbol: str, data: Dict) -> Optional[Dict]:
    """Compute spot features using pre-loaded data cache."""

    # 1. TRY RICH OBSERVATIONS (38 indicators)
    rich = data["obs"].get(symbol)
    if rich:
        return rich

    # 2. TRY VERDICT-BASED (10 symbols with axis data)
    verdict_doc = data["verdicts"].get(symbol)
    universe_doc = data["universe"].get(symbol)
    funding_doc = data["funding"].get(symbol)
    market_ctx = data["market"].get(symbol)

    if verdict_doc:
        axes = verdict_doc.get("axisContrib", {})
        scores = (universe_doc or {}).get("scores", {})
        regime = (market_ctx or {}).get("regime") or {}
        regime_type_data = regime.get("type")
        regime_type = regime_type_data.get("type", "NEUTRAL") if isinstance(regime_type_data, dict) else "NEUTRAL"

        momentum = axes.get("momentum", 0)
        structure_val = axes.get("structure", 0)
        participation = axes.get("participation", 0)
        positioning = axes.get("positioning", 0)
        stress_val = axes.get("marketStress", 0.5)

        compression = max(0, min(1.0, 1.0 - abs(structure_val) - stress_val * 0.5))
        volume_build = max(0, min(1.0, max(0, participation) * 0.7 + max(0, 0.5 - abs(momentum)) * 0.6))

        mom_sign = 1 if momentum > 0 else -1
        pos_sign = 1 if positioning > 0 else -1
        if mom_sign == pos_sign:
            alignment = 0.5 + min(abs(momentum), 1.0) * 0.25 + min(abs(positioning), 1.0) * 0.25
        else:
            alignment = max(0, 0.5 - abs(momentum - positioning) * 0.25)
        alignment = max(0, min(1.0, alignment))

        liq_raw = scores.get("liquidityScore", 0.5)
        deriv_raw = scores.get("derivativesScore", 0.5)
        liquidity = max(0, min(1.0, liq_raw * 0.6 + deriv_raw * 0.4))

        whale_score = scores.get("whaleScore", 0.5)
        risk_val = max(0, min(1.0, stress_val * 0.4 + (1.0 - liquidity) * 0.3 + (1.0 - whale_score) * 0.3))

        return {
            "compressionScore": round(compression, 3),
            "volumeBuildScore": round(volume_build, 3),
            "trendAlignmentScore": round(alignment, 3),
            "liquidityScore": round(liquidity, 3),
            "riskScore": round(risk_val, 3),
            "_axes": axes,
            "_regime": regime_type,
            "_verdict": verdict_doc.get("verdict", "NEUTRAL"),
            "_funding": funding_doc,
            "_updatedAt": verdict_doc.get("updatedAt")
            or verdict_doc.get("contextRefs", {}).get("updatedAt", ""),
            "_source": "verdict",
        }

    # 3. FALLBACK: snapshot-based features
    snapshot = data["snapshots"].get(symbol)
    if not snapshot:
        return None

    f = snapshot.get("features", {})
    dq = snapshot.get("dataQuality", {})
    quality = dq.get("qualityScore", 0)

    ret_24h = f.get("ret_24h") or 0
    volume_log = f.get("volume_log") or 0
    oi_usd = f.get("oi_usd") or 0
    score_up = f.get("score_up") or 0.5
    score_down = f.get("score_down") or 0.5
    squeeze_score = f.get("squeeze_score") or 0
    range_24h = f.get("range_24h") or 0

    compression = max(0, min(1.0, 1.0 - range_24h * 5 - abs(ret_24h) * 3))
    vol_norm = max(0, min(1.0, (volume_log - 5) / 5)) if volume_log > 0 else 0.3
    volume_build = max(0, min(1.0, vol_norm * 0.6 + (1.0 - abs(ret_24h) * 5) * 0.4))

    bias = score_up - score_down
    alignment = max(0, min(1.0, 0.5 + abs(bias) * 2.5 + abs(ret_24h) * 2))

    liq_from_vol = max(0, min(1.0, (volume_log - 5) / 5)) if volume_log > 0 else 0.3
    liq_from_oi = max(0, min(1.0, oi_usd / 100_000_000)) if oi_usd > 0 else 0.3
    liquidity = max(0, min(1.0, liq_from_vol * 0.5 + liq_from_oi * 0.3 + quality * 0.2))

    funding_ann = f.get("funding_annualized") or 0
    funding_risk = min(1.0, abs(funding_ann) / 50) if funding_ann else 0.3
    risk_val = max(0, min(1.0, funding_risk * 0.3 + squeeze_score * 0.3 + (1.0 - quality) * 0.4))

    return {
        "compressionScore": round(compression, 3),
        "volumeBuildScore": round(volume_build, 3),
        "trendAlignmentScore": round(alignment, 3),
        "liquidityScore": round(liquidity, 3),
        "riskScore": round(risk_val, 3),
        "_axes": {},
        "_regime": "NEUTRAL",
        "_verdict": "NEUTRAL",
        "_funding": funding_doc,
        "_updatedAt": str(snapshot.get("ts", "")),
        "_source": "snapshot",
        "_quality": quality,
        "_ret24h": ret_24h,
        "_scoreUp": score_up,
        "_scoreDown": score_down,
    }


# ═══════════════════════════════════════════════════════════════
# STRUCTURE & MOMENTUM DETECTION
# ═══════════════════════════════════════════════════════════════

def _detect_structure(f: Dict) -> StructureType:
    comp = f["compressionScore"]
    vol = f["volumeBuildScore"]
    alignment = f["trendAlignmentScore"]
    structure_axis = f.get("_axes", {}).get("structure", 0)

    if comp > 0.6 and vol < 0.4:
        return StructureType.COMPRESSION
    if structure_axis < -0.5:
        return StructureType.BREAKDOWN
    if alignment > 0.7 and vol > 0.5:
        return StructureType.HIGHER_LOWS
    if vol > 0.6 and comp < 0.3:
        return StructureType.EXPANSION
    return StructureType.RANGE


def _detect_momentum(f: Dict) -> MomentumBuild:
    score = f["volumeBuildScore"] * 0.5 + f["trendAlignmentScore"] * 0.5
    if score > 0.65:
        return MomentumBuild.STRONG
    if score > 0.4:
        return MomentumBuild.BUILDING
    return MomentumBuild.WEAK


# ═══════════════════════════════════════════════════════════════
# UNIVERSE CONFIG — Alpha is more aggressive
# ═══════════════════════════════════════════════════════════════

SPOT_CONFIGS = {
    "main":  {"convBoost": 1.0,  "liqFloor": 0.30, "riskCap": 0.55},
    "alpha": {"convBoost": 1.10, "liqFloor": 0.20, "riskCap": 0.50},
}


# ═══════════════════════════════════════════════════════════════
# CONVICTION (risk as penalty, not feature)
# ═══════════════════════════════════════════════════════════════

def _compute_conviction(f: Dict, venue: str = "main") -> int:
    cfg = SPOT_CONFIGS.get(venue, SPOT_CONFIGS["main"])
    signal = (
        0.35 * f["trendAlignmentScore"] +
        0.25 * f["volumeBuildScore"] +
        0.20 * f["compressionScore"] +
        0.20 * f["liquidityScore"]
    )
    risk_penalty = f["riskScore"] * 0.6
    raw = signal * (1.0 - risk_penalty) * 100 * cfg["convBoost"]

    if f["liquidityScore"] < cfg["liqFloor"]:
        raw = min(raw, 40)

    return int(max(0, min(100, round(raw))))


# ═══════════════════════════════════════════════════════════════
# CONVICTION TIER (stratification)
# ═══════════════════════════════════════════════════════════════

def _conviction_tier(conviction: int) -> str:
    if conviction >= 75:
        return ConvictionTier.A_PLUS.value
    if conviction >= 65:
        return ConvictionTier.A.value
    if conviction >= 60:
        return ConvictionTier.B.value
    if conviction >= 50:
        return ConvictionTier.C.value
    return ConvictionTier.NOISE.value


# ═══════════════════════════════════════════════════════════════
# SNAPSHOT DAMPENING — snapshots are less reliable
# ═══════════════════════════════════════════════════════════════

def _apply_snapshot_dampening(conviction: int, source: str) -> int:
    if source == "snapshot":
        return int(conviction * 0.85)
    return conviction


# ═══════════════════════════════════════════════════════════════
# MULTI-HORIZON (3 layers)
# ═══════════════════════════════════════════════════════════════

def _compute_horizons(f: Dict, venue: str = "main") -> HorizonsInfo:
    """Build multi-horizon analysis from features."""
    cfg = SPOT_CONFIGS.get(venue, SPOT_CONFIGS["main"])

    if f.get("_source") == "observations":
        # Rich data — use precomputed horizon signals
        hs = f.get("_horizon_short", {})
        hm = f.get("_horizon_mid", {})
        hw = f.get("_horizon_swing", {})

        short_conv = int(min(100, max(0, hs.get("conviction", 0) * 100 * cfg["convBoost"])))
        mid_conv = int(min(100, max(0, hm.get("conviction", 0) * 100 * cfg["convBoost"])))
        swing_conv = int(min(100, max(0, hw.get("conviction", 0) * 100 * cfg["convBoost"])))

        short = HorizonSignal(
            direction=hs.get("direction", "neutral"),
            conviction=short_conv,
            label="0-2d",
        )
        mid = HorizonSignal(
            direction=hm.get("direction", "neutral"),
            conviction=mid_conv,
            label="3-7d",
        )
        swing = HorizonSignal(
            direction=hw.get("direction", "neutral"),
            conviction=swing_conv,
            label="1-4w",
        )
    elif f.get("_source") == "snapshot":
        # Snapshot: derive simplified horizons from available data
        ret = f.get("_ret24h", 0)
        bias = f.get("_scoreUp", 0.5) - f.get("_scoreDown", 0.5)
        vol = f["volumeBuildScore"]

        # Short-term: momentum + volume
        s_dir = "long" if ret > 0.01 else "short" if ret < -0.01 else "neutral"
        s_conv = int(min(100, max(0, (abs(ret) * 300 + vol * 30) * 0.85)))

        # Mid-term: model bias
        m_dir = "long" if bias > 0.005 else "short" if bias < -0.005 else "neutral"
        m_conv = int(min(100, max(0, abs(bias) * 1000 * 0.85)))

        # Swing: compression setup
        sw_dir = "neutral"
        sw_conv = int(min(100, max(0, f["compressionScore"] * 40 * 0.85)))

        short = HorizonSignal(direction=s_dir, conviction=s_conv, label="0-2d")
        mid = HorizonSignal(direction=m_dir, conviction=m_conv, label="3-7d")
        swing = HorizonSignal(direction=sw_dir, conviction=sw_conv, label="1-4w")
    else:
        # Verdict-based: use axes
        axes = f.get("_axes", {})
        mom = axes.get("momentum", 0)
        pos = axes.get("positioning", 0)

        s_dir = "long" if mom > 0.15 else "short" if mom < -0.15 else "neutral"
        s_conv = int(min(100, max(0, abs(mom) * 100)))

        m_dir = "long" if mom > 0.1 and pos > 0 else "short" if mom < -0.1 and pos < 0 else "neutral"
        m_conv = int(min(100, max(0, (abs(mom) * 50 + abs(pos) * 50))))

        sw_dir = "neutral"
        sw_conv = int(min(100, max(0, f["compressionScore"] * 40)))

        short = HorizonSignal(direction=s_dir, conviction=s_conv, label="0-2d")
        mid = HorizonSignal(direction=m_dir, conviction=m_conv, label="3-7d")
        swing = HorizonSignal(direction=sw_dir, conviction=sw_conv, label="1-4w")

    # Primary horizon selection
    if short.conviction >= 70:
        primary = "short"
    elif mid.conviction >= 65:
        primary = "mid"
    elif swing.conviction >= 60:
        primary = "swing"
    elif short.conviction >= mid.conviction and short.conviction >= swing.conviction:
        primary = "short"
    elif mid.conviction >= swing.conviction:
        primary = "mid"
    else:
        primary = "swing"

    return HorizonsInfo(short=short, mid=mid, swing=swing, primary=primary)


# ═══════════════════════════════════════════════════════════════
# SETUP GATING — BUY only with real setup signals
# ═══════════════════════════════════════════════════════════════

def _has_setup(f: Dict) -> bool:
    """
    Check if there's a real setup (not just 'price is going up').
    Requires at least 2 of: compression, participation build, orderflow shift.
    """
    signals = 0
    if f["compressionScore"] > 0.4:
        signals += 1
    if f["volumeBuildScore"] > 0.4:
        signals += 1
    if f.get("_layers", {}).get("orderflow", 0) > 0.4:
        signals += 1
    if f.get("_layers", {}).get("smartmoney", 0) > 0.4:
        signals += 1
    # For non-observation sources, use available features
    if f.get("_source") != "observations":
        if f["trendAlignmentScore"] > 0.6:
            signals += 1
    return signals >= 2


def _compute_setup_score(f: Dict) -> tuple:
    """
    SetupScore = #passedSetupSignals / #availableSetupSignals
    Returns (setupScore: float, passedCount: int, availableCount: int, passedSignals: list)
    """
    checks = {
        "compression": f["compressionScore"] > 0.4,
        "participation": f["volumeBuildScore"] > 0.4,
        "orderflow": f.get("_layers", {}).get("orderflow", 0) > 0.4,
        "smartmoney": f.get("_layers", {}).get("smartmoney", 0) > 0.4,
        "structure": f["trendAlignmentScore"] > 0.5,
    }
    passed = [k for k, v in checks.items() if v]
    available = len(checks)
    score = len(passed) / available if available > 0 else 0
    return round(score, 3), len(passed), available, passed


def _compute_coverage(f: Dict) -> tuple:
    """
    Coverage = #nonNullFeatures / #requiredFeatures
    Returns (coveragePct: int, missing: list)
    """
    required = [
        "compressionScore", "volumeBuildScore", "trendAlignmentScore",
        "liquidityScore", "riskScore",
    ]
    source = f.get("_source", "unknown")

    # Extra required for observations
    if source == "observations":
        required += ["_layers", "_obs_orderflow", "_obs_regime"]
    elif source == "verdict":
        required += ["_axes", "_regime"]
    elif source == "snapshot":
        required += ["_ret24h", "_scoreUp", "_scoreDown"]

    available = 0
    missing = []
    for key in required:
        val = f.get(key)
        if val is not None and val != {} and val != 0:
            available += 1
        else:
            missing.append(key)

    pct = int(available / len(required) * 100) if required else 0
    return pct, missing


def _compute_data_freshness(f: Dict) -> int | None:
    """Estimate data freshness in seconds."""
    import time
    from datetime import datetime
    updated = f.get("_updatedAt", "")
    if not updated:
        return None
    try:
        if isinstance(updated, (int, float)):
            return int(time.time() - updated)
        dt = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
        return int(time.time() - dt.timestamp())
    except Exception:
        return None


def _compute_integrity(f: Dict, conviction: int, verdict, setup_score: float,
                       passed_count: int, coverage_pct: int) -> IntegrityInfo:
    """
    Compute integrity status: OK / DEGRADED / INVALID
    Rules:
    - coverage < 50% → INVALID, force DATA_GAP
    - coverage 50-70% → DEGRADED (WATCH/NEUTRAL only)
    - snapshot source → DEGRADED
    - conviction high but setupScore low → DEGRADED
    - setupScore < 0.4 and verdict BUY/SELL → DEGRADED
    - dataFreshness > 900s → DEGRADED + conviction decay (P0.4)
    """
    reasons = []
    source = f.get("_source", "unknown")
    freshness = _compute_data_freshness(f)

    # INVALID checks
    if coverage_pct < 50:
        return IntegrityInfo(
            status="invalid",
            reasons=["LOW_COVERAGE"],
            coveragePct=coverage_pct,
            setupScore=setup_score,
            dataFreshnessSec=freshness,
        )

    # DEGRADED checks
    if coverage_pct < 70:
        reasons.append("PARTIAL_COVERAGE")
    if source == "snapshot":
        reasons.append("SNAPSHOT_SOURCE")
    if setup_score < 0.4 and conviction >= 60:
        reasons.append("HIGH_CONV_NO_SETUP")
    if passed_count < 2 and verdict in (Verdict.BUY, Verdict.SELL):
        reasons.append("WEAK_SETUP_SIGNALS")
    if f["riskScore"] > 0.55:
        reasons.append("HIGH_RISK")

    # P0.4: Freshness guard
    if freshness is not None and freshness > 900:
        reasons.append("STALE_DATA")

    status = "degraded" if reasons else "ok"
    return IntegrityInfo(
        status=status,
        reasons=reasons,
        coveragePct=coverage_pct,
        setupScore=setup_score,
        dataFreshnessSec=freshness,
    )


# ═══════════════════════════════════════════════════════════════
# VERDICT (clear thresholds)
# ═══════════════════════════════════════════════════════════════

def _compute_verdict_and_direction(f: Dict, conviction: int) -> tuple:
    alignment = f["trendAlignmentScore"]
    risk = f["riskScore"]
    axes = f.get("_axes", {})
    momentum = axes.get("momentum", 0)
    structure = axes.get("structure", 0)

    if f.get("_source") == "observations":
        obs_dir = f.get("_direction", "neutral")
        if obs_dir == "long":
            direction = Direction.LONG
        elif obs_dir == "short":
            direction = Direction.SHORT
        else:
            direction = Direction.NEUTRAL
    elif f.get("_source") == "snapshot":
        score_up = f.get("_scoreUp", 0.5)
        score_down = f.get("_scoreDown", 0.5)
        ret = f.get("_ret24h", 0)
        bias = score_up - score_down

        if bias > 0.01 or ret > 0.02:
            direction = Direction.LONG
            momentum = abs(bias) * 2 + abs(ret) * 3
        elif bias < -0.01 or ret < -0.02:
            direction = Direction.SHORT
            momentum = -(abs(bias) * 2 + abs(ret) * 3)
        else:
            direction = Direction.NEUTRAL
    else:
        if momentum > 0.15 and alignment >= 0.5:
            direction = Direction.LONG
        elif momentum < -0.15 and alignment < 0.5:
            direction = Direction.SHORT
        else:
            direction = Direction.NEUTRAL

    if conviction >= 60 and alignment >= 0.55 and risk <= 0.45:
        verdict = Verdict.BUY if direction == Direction.LONG else Verdict.SELL
    elif conviction >= 60 and alignment <= 0.35 and structure < -0.3:
        verdict = Verdict.SELL
        direction = Direction.SHORT
    elif conviction >= 45:
        verdict = Verdict.WATCH
    else:
        verdict = Verdict.NEUTRAL

    return verdict, direction


# ═══════════════════════════════════════════════════════════════
# REASONS (min 3, max 7)
# ═══════════════════════════════════════════════════════════════

def _generate_reasons(f: Dict) -> List[str]:
    reasons = []
    axes = f.get("_axes", {})
    funding = f.get("_funding")

    if f.get("_source") == "observations":
        layers = f.get("_layers", {})
        obs_of = f.get("_obs_orderflow", {})
        obs_liqs = f.get("_obs_liquidations", {})

        if layers.get("compression", 0) > 0.5:
            reasons.append("Volatility compression — breakout setup forming")
        if layers.get("participation", 0) > 0.5:
            reasons.append("Volume and participation building")
        elif layers.get("participation", 0) < 0.25:
            reasons.append("Low participation, thin activity")

        aggressor = str(obs_of.get("aggressorBias", "")).upper()
        if aggressor == "BUY":
            reasons.append("Buy aggressor dominant in order flow")
        elif aggressor == "SELL":
            reasons.append("Sell aggressor dominant in order flow")

        if obs_of.get("absorption"):
            side = obs_of.get("absorptionSide", "")
            reasons.append(f"Absorption detected on {side.lower()} side" if side else "Order absorption detected")

        if layers.get("smartmoney", 0) > 0.5:
            reasons.append("Smart money / whale positioning active")

        if obs_liqs.get("cascadeActive"):
            cascade_dir = obs_liqs.get("cascadeDirection", "?")
            reasons.append(f"Liquidation cascade active ({cascade_dir})")

        if f["riskScore"] > 0.5:
            reasons.append("Elevated risk — positioning crowded or stop-hunt zone")
        if f["liquidityScore"] < 0.3:
            reasons.append("Low liquidity depth — slippage risk")
        if f["liquidityScore"] > 0.7:
            reasons.append("Good orderbook depth")

        mom = axes.get("momentum", 0)
        if abs(mom) > 0.3:
            reasons.append(f"Momentum {'positive' if mom > 0 else 'negative'} and building")

    elif f.get("_source") == "snapshot":
        ret = f.get("_ret24h", 0)
        score_up = f.get("_scoreUp", 0.5)
        score_down = f.get("_scoreDown", 0.5)
        bias = score_up - score_down

        if ret > 0.03:
            reasons.append(f"Strong 24h return (+{ret*100:.1f}%)")
        elif ret > 0.01:
            reasons.append(f"Positive 24h return (+{ret*100:.1f}%)")
        elif ret < -0.03:
            reasons.append(f"Sharp 24h decline ({ret*100:.1f}%)")
        elif ret < -0.01:
            reasons.append(f"Negative 24h return ({ret*100:.1f}%)")
        else:
            reasons.append("Flat price action, consolidating")

        if bias > 0.005:
            reasons.append("Model bias tilted bullish")
        elif bias < -0.005:
            reasons.append("Model bias tilted bearish")
        else:
            reasons.append("Model signals balanced")

        if f["volumeBuildScore"] > 0.6:
            reasons.append("Volume above average")
        elif f["volumeBuildScore"] < 0.3:
            reasons.append("Low volume, thin activity")

        if f["compressionScore"] > 0.6:
            reasons.append("Volatility compression — potential breakout setup")

        if f["riskScore"] > 0.6:
            reasons.append("Elevated risk — funding extreme or low data quality")
        if f["liquidityScore"] < 0.3:
            reasons.append("Low liquidity — slippage risk")
        if f["liquidityScore"] > 0.7:
            reasons.append("Good liquidity depth")
    else:
        mom = axes.get("momentum", 0)
        if mom > 0.3:
            reasons.append("Momentum positive and building")
        elif mom > 0.1:
            reasons.append("Slight positive momentum")
        elif mom < -0.3:
            reasons.append("Momentum negative, selling pressure")
        elif mom < -0.1:
            reasons.append("Slight negative momentum")
        else:
            reasons.append("Momentum flat, no directional pressure")

        pos = axes.get("positioning", 0)
        if pos > 0.5:
            reasons.append("Strong long positioning by participants")
        elif pos > 0.2:
            reasons.append("Moderate long positioning")
        elif pos < -0.5:
            reasons.append("Short positioning dominant")
        elif pos < -0.2:
            reasons.append("Moderate short positioning")
        else:
            reasons.append("Positioning balanced, no clear bias")

        part = axes.get("participation", 0)
        if part > 0.5:
            reasons.append("High participation, volume building")
        elif part > 0.2:
            reasons.append("Moderate participation levels")
        else:
            reasons.append("Low participation, thin activity")

        if f["compressionScore"] > 0.6:
            reasons.append("Volatility compression — breakout setup forming")

        ob = axes.get("orderbookPressure", 0)
        if ob > 0.3:
            reasons.append("Orderbook skewed to buy side")
        elif ob < -0.3:
            reasons.append("Orderbook skewed to sell side")

        if funding:
            fl = funding.get("label", "NEUTRAL")
            fs = funding.get("fundingScore", 0)
            if fl == "BULLISH" or fs > 0.3:
                reasons.append("Funding bullish — market pays to short")
            elif fl == "BEARISH" or fs < -0.3:
                reasons.append("Funding bearish — market pays to long")

        if f["riskScore"] > 0.6:
            reasons.append("Elevated risk — stress or low liquidity")
        if f["liquidityScore"] < 0.3:
            reasons.append("Low liquidity — thin orderbook, slippage risk")

    return reasons[:7]


# ═══════════════════════════════════════════════════════════════
# EXPLAIN BLOCK
# ═══════════════════════════════════════════════════════════════

def _generate_explain(f: Dict, verdict: Verdict, direction: Direction) -> SpotExplain:
    axes = f.get("_axes", {})
    funding = f.get("_funding")

    if f.get("_source") == "observations":
        layers = f.get("_layers", {})
        obs_of = f.get("_obs_orderflow", {})
        obs_regime = f.get("_obs_regime", {})

        parts = []
        if layers.get("compression", 0) > 0.4:
            parts.append("compression building")
        if layers.get("participation", 0) > 0.4:
            parts.append("volume accumulation")
        if layers.get("orderflow", 0) > 0.4:
            parts.append(f"order flow {obs_of.get('aggressorBias', 'active').lower()}")
        if layers.get("smartmoney", 0) > 0.4:
            parts.append("smart money positioning")

        regime_type = obs_regime.get("type", "NEUTRAL") if isinstance(obs_regime, dict) else "NEUTRAL"
        if isinstance(regime_type, dict):
            regime_type = regime_type.get("type", "NEUTRAL")
        if regime_type != "NEUTRAL":
            parts.append(f"regime {regime_type.lower()}")

        why_now = f"Active setup: {', '.join(parts)}" if parts else "No active catalysts. Market balanced."

        if direction == Direction.LONG:
            invalidation = "Order flow reversal or absorption failure invalidates long bias"
        elif direction == Direction.SHORT:
            invalidation = "Bid absorption or volume reversal invalidates short bias"
        else:
            invalidation = "No active trade thesis to invalidate"

        if layers.get("compression", 0) > 0.6:
            time_horizon = "6-24h (compression breakout expected)"
        elif layers.get("orderflow", 0) > 0.6:
            time_horizon = "4-12h (strong order flow, near-term)"
        else:
            time_horizon = "24-72h (building setup, patience required)"

        return SpotExplain(whyNow=why_now, invalidation=invalidation, timeHorizon=time_horizon)

    elif f.get("_source") == "snapshot":
        ret = f.get("_ret24h", 0)
        bias = f.get("_scoreUp", 0.5) - f.get("_scoreDown", 0.5)

        parts = []
        if abs(ret) > 0.02:
            parts.append(f"{'positive' if ret > 0 else 'negative'} price momentum ({ret*100:.1f}%)")
        if abs(bias) > 0.005:
            parts.append(f"model bias {'bullish' if bias > 0 else 'bearish'}")
        if f["volumeBuildScore"] > 0.5:
            parts.append("volume building")
        if f["compressionScore"] > 0.5:
            parts.append("volatility compressing")

        why_now = f"Active setup: {', '.join(parts)}" if parts else "No active catalysts. Consolidation phase."

        if direction == Direction.LONG:
            invalidation = "Momentum reversal or sharp volume decline invalidates long bias"
        elif direction == Direction.SHORT:
            invalidation = "Price recovery above key levels invalidates short bias"
        else:
            invalidation = "No active trade thesis to invalidate"

        time_horizon = "24-72h (snapshot-based estimate)"
    else:
        mom = axes.get("momentum", 0)
        pos = axes.get("positioning", 0)
        structure = axes.get("structure", 0)

        parts = []
        if abs(mom) > 0.3:
            parts.append(f"momentum {'positive' if mom > 0 else 'negative'} ({abs(mom):.0%})")
        if abs(pos) > 0.3:
            parts.append(f"positioning {'long' if pos > 0 else 'short'} ({abs(pos):.0%})")
        if f["compressionScore"] > 0.5:
            parts.append("volatility compressing")
        if funding:
            fl = funding.get("label", "NEUTRAL")
            if fl != "NEUTRAL":
                parts.append(f"funding {fl.lower()}")

        why_now = f"Active setup: {', '.join(parts)}" if parts else "No active catalysts detected. Market in consolidation."

        if direction == Direction.LONG:
            if structure > 0:
                invalidation = "Structure break below recent support invalidates long thesis"
            else:
                invalidation = "Momentum reversal below zero or funding flip to extreme negative"
        elif direction == Direction.SHORT:
            invalidation = "Price reclaim above key resistance or funding flip to extreme positive"
        else:
            invalidation = "No active trade thesis to invalidate"

        mom_val = abs(mom) if mom else 0
        if f["compressionScore"] > 0.6:
            time_horizon = "6-24h (compression breakout expected)"
        elif mom_val > 0.5:
            time_horizon = "4-12h (strong momentum, near-term)"
        else:
            time_horizon = "24-72h (building setup, patience required)"

    return SpotExplain(whyNow=why_now, invalidation=invalidation, timeHorizon=time_horizon)


def _build_one_liner(direction, verdict, conviction, tier, horizons, risk, explain) -> str:
    """P0.3: Build execution-ready one-liner summary."""
    dir_str = direction.value.upper() if direction != Direction.NEUTRAL else "FLAT"

    h_label = ""
    if horizons and isinstance(horizons, dict) and horizons.get("primary"):
        labels = {"short": "Short 0-2d", "mid": "Mid 3-7d", "swing": "Swing 1-4w"}
        h_label = f" ({labels.get(horizons['primary'], '')})"

    tier_str = f" Tier {tier}" if tier else ""

    why = explain.whyNow.replace("Active setup: ", "").replace("No active catalysts. ", "").replace("No active catalysts detected. ", "")
    if len(why) > 60:
        why = why[:57] + "..."

    risk_str = risk.value.capitalize() if hasattr(risk, 'value') else str(risk).capitalize()

    if verdict.value == "data_gap":
        return "Insufficient data"
    if verdict.value == "neutral":
        return f"{dir_str}{h_label} | Conv {conviction}{tier_str} | {why} | Risk {risk_str}"

    return f"{verdict.value.upper()}{h_label} | Conv {conviction}{tier_str} | {why} | Risk {risk_str}"


# ═══════════════════════════════════════════════════════════════
# FULL SCAN
# ═══════════════════════════════════════════════════════════════

def compute_spot_verdict(features: Dict, venue: str = "main") -> Dict:
    cfg = SPOT_CONFIGS.get(venue, SPOT_CONFIGS["main"])
    conviction = _compute_conviction(features, venue)

    # Snapshot dampening
    conviction = _apply_snapshot_dampening(conviction, features.get("_source", ""))

    verdict, direction = _compute_verdict_and_direction(features, conviction)

    # Setup scoring
    setup_score, passed_count, _, _ = _compute_setup_score(features)
    coverage_pct, _ = _compute_coverage(features)

    # Setup gating: BUY/SELL only if real setup exists AND setupScore >= 0.4
    if verdict in (Verdict.BUY, Verdict.SELL):
        if not _has_setup(features) or setup_score < 0.4:
            verdict = Verdict.WATCH

    if features["riskScore"] > cfg["riskCap"] and verdict in (Verdict.BUY, Verdict.SELL):
        verdict = Verdict.WATCH

    # ── Integrity computation ──
    integrity = _compute_integrity(
        features, conviction, verdict, setup_score, passed_count, coverage_pct,
    )

    # ── Coverage-based verdict override ──
    if integrity.status == "invalid":
        verdict = Verdict.DATA_GAP
        direction = Direction.NEUTRAL

    if integrity.status == "degraded" and verdict in (Verdict.BUY, Verdict.SELL):
        verdict = Verdict.WATCH

    # ── Conviction Control (anti-extremes) ──
    source = features.get("_source", "")
    if integrity.status == "degraded":
        conviction = max(20, min(85, conviction))
    if source == "snapshot":
        conviction = max(20, min(70, conviction))
    if features["riskScore"] > 0.55:
        conviction = min(55, conviction)
        if verdict in (Verdict.BUY, Verdict.SELL):
            verdict = Verdict.WATCH

    # P0.4: Freshness-based confidence decay
    freshness = integrity.dataFreshnessSec
    if freshness is not None and freshness > 900:
        decay = 0.8
        conviction = int(conviction * decay)
        conviction = max(20, conviction)

    # P0.4: Flip cooldown — if setupScore too weak, prevent BUY/SELL
    if setup_score < 0.4 and verdict in (Verdict.BUY, Verdict.SELL):
        verdict = Verdict.WATCH

    breakout_prob = int(min(100, max(0, round(
        features["compressionScore"] * 40 +
        features["volumeBuildScore"] * 30 +
        features["trendAlignmentScore"] * 20 +
        (1 - features["riskScore"]) * 10
    ))))

    risk_val = features["riskScore"]
    liq = features["liquidityScore"]
    if risk_val > 0.65 or liq < 0.25:
        risk = RiskLevel.HIGH
    elif risk_val > 0.4 or liq < 0.5:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.LOW

    # Multi-horizon
    horizons = _compute_horizons(features, venue)

    # Conviction tier (after clamping)
    tier = _conviction_tier(conviction)

    explain = _generate_explain(features, verdict, direction)

    # P0.3: Execution-ready one-liner
    horizons_dict = None
    if horizons:
        horizons_dict = {"primary": horizons.primary} if hasattr(horizons, "primary") else horizons
    one_liner = _build_one_liner(direction, verdict, conviction, tier, horizons_dict, risk, explain)
    explain.oneLiner = one_liner

    return {
        "direction": direction,
        "verdict": verdict,
        "conviction": conviction,
        "convictionTier": tier,
        "breakoutProb": breakout_prob,
        "risk": risk,
        "structure": _detect_structure(features),
        "momentumBuild": _detect_momentum(features),
        "horizons": horizons,
        "integrity": integrity,
        "reasons": _generate_reasons(features),
        "explain": explain,
        "features": SpotFeatures(
            compression=features["compressionScore"],
            volumeBuild=features["volumeBuildScore"],
            trendAlignment=features["trendAlignmentScore"],
            liquidity=features["liquidityScore"],
            risk=features["riskScore"],
        ),
    }


def _build_data_gap_spot_row(symbol: str, venue: str, missing: list) -> SpotRadarRow:
    spot_venue = SpotVenue.ALPHA if venue == "alpha" else SpotVenue.MAIN
    return SpotRadarRow(
        symbol=symbol,
        venue=spot_venue,
        direction=Direction.NEUTRAL,
        verdict=Verdict.DATA_GAP,
        conviction=0,
        breakoutProb=0,
        structure=StructureType.RANGE,
        momentumBuild=MomentumBuild.WEAK,
        risk=RiskLevel.UNKNOWN,
        features=SpotFeatures(compression=0, volumeBuild=0, trendAlignment=0, liquidity=0, risk=0),
        reasons=["Insufficient market data to compute a reliable setup"],
        explain=SpotExplain(
            whyNow="No market data available for this asset",
            invalidation="N/A (data gap)",
            timeHorizon="N/A (data gap)",
        ),
        updatedAt="",
        dataQuality=DataQualityInfo(status="missing_core_fields", missing=missing),
        source="none",
    )



def _get_core_engine_execution() -> dict | None:
    """Fetch Core Engine global execution modifiers (cached internally by CE)."""
    try:
        from core_engine.service import get_core_global
        result = get_core_global()
        return result.get("execution") if result.get("ok") else None
    except Exception:
        return None



def scan_spot(venue: str = "main", limit: int = 500) -> List[SpotRadarRow]:
    if venue == "alpha":
        symbols = get_spot_alpha_symbols()
        spot_venue = SpotVenue.ALPHA
    else:
        symbols = get_spot_main_symbols()
        spot_venue = SpotVenue.MAIN

    # Batch load ALL data in ~5 queries
    data = _load_all_data(symbols)

    # P1.1: Fetch venue info (respects DUAL_VENUE_ENABLED flag)
    venue_info = get_venue_info_batch(symbols)

    # P1-CE: Fetch Core Engine execution modifiers (global)
    ce_execution = _get_core_engine_execution()

    rows = []
    for symbol in symbols:
        f = compute_spot_features_from_cache(symbol, data)
        if not f:
            rows.append(_build_data_gap_spot_row(symbol, venue, ["no_data_source"]))
            continue
        v = compute_spot_verdict(f, venue=venue)

        # P1-CE: Apply Core Engine signal amplification to conviction
        if ce_execution:
            amp = ce_execution.get("signalAmplification", 1.0)
            agg = ce_execution.get("aggressionMultiplier", 1.0)
            modifier = 0.7 + 0.3 * ((amp + agg) / 2)
            v["conviction"] = int(max(0, min(100, round(v["conviction"] * modifier))))
            v["convictionTier"] = _conviction_tier(v["conviction"])

        # P1.1: Attach venue metadata
        vi = venue_info.get(symbol)
        v_count = vi.venueCount if vi else 1
        v_list = vi.venues if vi else ["binance"]
        div_score = vi.divergenceScore if vi else 0.0
        div_label = vi.divergenceLabel if vi else "NONE"
        div_reasons = list(vi.divergenceReasons) if vi else []

        # P1.2: Divergence → short-horizon boost & integrity guard
        horizons_obj = v["horizons"]
        integrity_obj = v["integrity"]

        if div_score >= 0.25 and horizons_obj and integrity_obj:
            if div_score > 0.85:
                # Extreme divergence → force WATCH, flag integrity
                if "EXTREME_VENUE_CONFLICT" not in integrity_obj.reasons:
                    integrity_obj.reasons.append("EXTREME_VENUE_CONFLICT")
                if integrity_obj.status == "ok":
                    integrity_obj.status = "degraded"
                # Force verdict to WATCH if BUY/SELL
                verdict_val = v["verdict"]
                if verdict_val in (Verdict.BUY, Verdict.SELL):
                    v["verdict"] = Verdict.WATCH
            elif integrity_obj.status == "ok":
                # Moderate divergence → boost short conviction only
                boost = min(10, int(div_score * 12))
                new_short_conv = min(100, horizons_obj.short.conviction + boost)
                horizons_obj.short.conviction = new_short_conv
                # Add reason
                if "VENUE_DIVERGENCE" not in integrity_obj.reasons:
                    integrity_obj.reasons.append("VENUE_DIVERGENCE")

        rows.append(SpotRadarRow(
            symbol=symbol,
            venue=spot_venue,
            direction=v["direction"],
            verdict=v["verdict"],
            conviction=v["conviction"],
            convictionTier=v["convictionTier"],
            breakoutProb=v["breakoutProb"],
            structure=v["structure"],
            momentumBuild=v["momentumBuild"],
            risk=v["risk"],
            features=v["features"],
            horizons=horizons_obj,
            integrity=integrity_obj,
            reasons=v["reasons"],
            explain=v["explain"],
            updatedAt=str(f.get("_updatedAt", "")),
            source=f.get("_source", "unknown"),
            venueCount=v_count,
            venues=v_list,
            divergenceScore=div_score,
            divergenceLabel=div_label,
            divergenceReasons=div_reasons,
        ))

    rows.sort(key=lambda r: r.conviction, reverse=True)
    return rows
