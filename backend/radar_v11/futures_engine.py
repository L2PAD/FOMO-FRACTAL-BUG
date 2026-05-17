"""
ALT RADAR V11 — Futures Radar Engine (v2 — post quality review)
================================================================
Fixed: conviction formula (risk as penalty), verdict thresholds,
explain block, min 3 reasons, squeeze risk numeric, sanity checks.
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING
import os

from .types import (
    FuturesRadarRow, Direction, FuturesBias, Verdict, RiskLevel,
    SqueezeRisk, OIShift, FundingState, FuturesFeatures, FuturesExplain,
    DataQualityInfo,
)
from .universe import get_futures_symbols

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
        db_name = os.environ.get("DB_NAME", "intelligence_engine")
        _client = MongoClient(mongo_url)
        _db = _client[db_name]
    return _db


# ═══════════════════════════════════════════════════════════════
# FUTURES FEATURE COMPUTATION
# ═══════════════════════════════════════════════════════════════

def compute_futures_features(symbol: str) -> Optional[Dict]:
    db = _get_db()

    funding_doc = db["exchange_funding_context"].find_one(
        {"symbol": symbol}, {"_id": 0}, sort=[("ts", DESCENDING)]
    )
    base = symbol.replace("USDT", "").replace("USD", "")
    snapshot = db["exchange_symbol_snapshots"].find_one(
        {"base": base}, {"_id": 0}, sort=[("ts", DESCENDING)]
    )
    verdict_doc = db["exchange_verdicts"].find_one({"symbol": symbol}, {"_id": 0})

    features_raw = (snapshot or {}).get("features", {})
    data_quality = (snapshot or {}).get("dataQuality", {})
    quality_score = data_quality.get("qualityScore", 0)

    # ── Funding ──────────────────────────────────────────────
    funding_score = 0
    funding_trend = 0
    funding_label = "NEUTRAL"

    if funding_doc:
        funding_score = funding_doc.get("fundingScore", 0)
        funding_trend = funding_doc.get("fundingTrend", 0)
        funding_label = funding_doc.get("label", "NEUTRAL")
    elif features_raw.get("funding_rate") is not None:
        fr = features_raw.get("funding_rate", 0) or 0
        funding_score = max(-1, min(1, fr * 1000))
        funding_label = "BULLISH" if fr > 0.0001 else ("BEARISH" if fr < -0.0001 else "NEUTRAL")

    # Also use funding_annualized as a stronger signal when available
    funding_ann = features_raw.get("funding_annualized")
    if funding_ann is not None and abs(funding_ann) > 0:
        # Annualized rate: >10% is significant, >30% is extreme
        ann_signal = max(-1.0, min(1.0, funding_ann / 30.0))
        # Blend with funding_context score
        if abs(ann_signal) > abs(funding_score):
            funding_score = (funding_score + ann_signal) / 2

    # ── OI Shift Score (0-1) ─────────────────────────────────
    # Real field names: oi_chg_1h, oi_usd, oi_per_volume
    oi_change = features_raw.get("oi_chg_1h") or features_raw.get("oi_change_1h") or features_raw.get("oi_delta_pct")
    oi_usd = features_raw.get("oi_usd")
    oi_per_vol = features_raw.get("oi_per_volume")

    if oi_change is not None and oi_change != 0:
        oi_shift = min(1.0, max(0, abs(oi_change) * 10))
    elif oi_per_vol is not None and oi_per_vol > 0:
        # OI/Volume ratio: >1 = leveraged market, >2 = very leveraged
        oi_shift = min(1.0, max(0, oi_per_vol / 3.0))
    elif oi_usd is not None and oi_usd > 0:
        # Large OI itself indicates active derivatives market
        oi_shift = min(1.0, max(0.15, oi_usd / 5_000_000_000))
    else:
        oi_shift = 0

    # ── Funding Skew Score (-1 to 1) ─────────────────────────
    funding_skew = max(-1.0, min(1.0, funding_score))

    # ── Liquidation Density Score (0-1) ──────────────────────
    # Real field names: liq_1h, liq_to_oi_ratio
    liq_1h = features_raw.get("liq_1h") or features_raw.get("liq_buy_usd_1h")
    liq_to_oi = features_raw.get("liq_to_oi_ratio")

    if liq_1h is not None and liq_1h > 0:
        liq_density = min(1.0, liq_1h / 1_000_000)
    elif liq_to_oi is not None and liq_to_oi > 0:
        liq_density = min(1.0, liq_to_oi * 10)
    else:
        # Estimate from funding extremity + OI presence
        if oi_usd and oi_usd > 0 and abs(funding_skew) > 0.1:
            liq_density = min(0.6, abs(funding_skew) * 0.4 + 0.1)
        else:
            liq_density = 0.1

    # ── Volatility Regime Score (0-1) ────────────────────────
    # Real field names: volatility_24h, atr, range_24h, ret_24h
    volatility = features_raw.get("volatility_24h") or features_raw.get("atr") or features_raw.get("range_24h")
    ret_24h = features_raw.get("ret_24h")

    if volatility is not None and volatility != 0:
        vol_regime = min(1.0, max(0, abs(volatility) * 20 if abs(volatility) < 1 else abs(volatility) / 5))
    elif ret_24h is not None and ret_24h != 0:
        # Use absolute return as volatility proxy: 5% daily = moderate, 10%+ = high
        vol_regime = min(1.0, max(0, abs(ret_24h) / 0.10))
    else:
        vol_regime = 0.3

    # ── L/S Ratio & Crowdedness ──────────────────────────────
    # Real field names: ls_ratio, score_up/score_down
    ls_ratio = features_raw.get("ls_ratio")
    if ls_ratio is None or ls_ratio == 0:
        # Use model prediction scores as proxy for market positioning
        score_up = features_raw.get("score_up", 0.5) or 0.5
        score_down = features_raw.get("score_down", 0.5) or 0.5
        total = score_up + score_down
        ls_ratio = score_up / total if total > 0 else 0.5

    crowded = abs(ls_ratio - 0.5) * 2

    # ── Risk Score (0-1) ─────────────────────────────────────
    risk_val = max(0, min(1.0,
        crowded * 0.3 +
        liq_density * 0.3 +
        vol_regime * 0.2 +
        (1 - quality_score) * 0.2
    ))

    # ── Squeeze Risk Score (0-1) ─────────────────────────────
    squeeze_score = abs(funding_skew) * 0.4 + oi_shift * 0.3 + liq_density * 0.3
    squeeze_score = max(0, min(1.0, squeeze_score))

    # ── Timestamp ────────────────────────────────────────────
    updated_at = ""
    if funding_doc and funding_doc.get("ts"):
        ts = funding_doc["ts"]
        if isinstance(ts, (int, float)):
            updated_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
    elif snapshot and snapshot.get("ts"):
        updated_at = str(snapshot["ts"])

    return {
        "oiShiftScore": round(oi_shift, 3),
        "fundingSkewScore": round(funding_skew, 3),
        "liquidationDensityScore": round(liq_density, 3),
        "volatilityRegimeScore": round(vol_regime, 3),
        "riskScore": round(risk_val, 3),
        "squeezeRiskScore": round(squeeze_score, 3),
        "_fundingLabel": funding_label,
        "_fundingTrend": funding_trend,
        "_oiChange": oi_change,
        "_lsRatio": ls_ratio,
        "_axes": (verdict_doc or {}).get("axisContrib", {}),
        "_updatedAt": updated_at,
    }


# ═══════════════════════════════════════════════════════════════
# DETECTION HELPERS
# ═══════════════════════════════════════════════════════════════

def _detect_oi_shift(f: Dict) -> OIShift:
    oi = f["oiShiftScore"]
    if oi > 0.7:
        return OIShift.EXPLOSIVE
    if oi > 0.3:
        return OIShift.RISING
    return OIShift.FALLING


def _detect_funding_state(f: Dict) -> FundingState:
    skew = f["fundingSkewScore"]
    if skew > 0.25:
        return FundingState.POSITIVE_HEAVY
    if skew < -0.25:
        return FundingState.NEGATIVE_HEAVY
    return FundingState.NEUTRAL


def _detect_squeeze_risk(f: Dict) -> SqueezeRisk:
    score = f["squeezeRiskScore"]
    if score > 0.6:
        return SqueezeRisk.HIGH
    if score > 0.35:
        return SqueezeRisk.MEDIUM
    return SqueezeRisk.LOW


# ═══════════════════════════════════════════════════════════════
# CONVICTION (risk as penalty multiplier)
# ═══════════════════════════════════════════════════════════════

def _compute_futures_conviction(f: Dict) -> int:
    """
    signal = 0.30*oiShift + 0.25*(1-abs(fundingSkew)) + 0.25*liquidationDensity + 0.20*(1-volatilityRegime)
    conviction = signal * (1 - riskPenalty) * 100
    """
    signal = (
        0.30 * f["oiShiftScore"] +
        0.25 * (1.0 - abs(f["fundingSkewScore"])) +
        0.25 * f["liquidationDensityScore"] +
        0.20 * (1.0 - f["volatilityRegimeScore"])
    )
    risk_penalty = f["riskScore"] * 0.6
    raw = signal * (1.0 - risk_penalty) * 100

    return int(max(0, min(100, round(raw))))


# ═══════════════════════════════════════════════════════════════
# VERDICT (clear thresholds)
# ═══════════════════════════════════════════════════════════════

def _compute_futures_verdict(f: Dict, conviction: int) -> tuple:
    """
    Returns (verdict, direction, bias).
    BUY:  conv >= 60 and bias=long and squeezeRisk <= 0.65
    SELL: conv >= 60 and bias=short and squeezeRisk <= 0.65
    WATCH: 45..59 or squeeze high
    NEUTRAL: <45
    """
    skew = f["fundingSkewScore"]
    oi = f["oiShiftScore"]
    squeeze = f["squeezeRiskScore"]
    axes = f.get("_axes", {})
    momentum = axes.get("momentum", 0)

    # Bias
    if skew > 0.2 and (momentum > 0 or oi > 0.4):
        bias = FuturesBias.LONG_BUILD
    elif skew < -0.2 and (momentum < 0 or oi > 0.4):
        bias = FuturesBias.SHORT_BUILD
    else:
        bias = FuturesBias.NEUTRAL

    # Direction
    if bias == FuturesBias.LONG_BUILD:
        direction = Direction.LONG
    elif bias == FuturesBias.SHORT_BUILD:
        direction = Direction.SHORT
    else:
        direction = Direction.NEUTRAL

    # Verdict
    if conviction >= 60 and bias == FuturesBias.LONG_BUILD and squeeze <= 0.65:
        verdict = Verdict.BUY
    elif conviction >= 60 and bias == FuturesBias.SHORT_BUILD and squeeze <= 0.65:
        verdict = Verdict.SELL
    elif squeeze > 0.7:
        # High squeeze → forced WATCH with warning
        verdict = Verdict.WATCH
    elif conviction >= 45:
        verdict = Verdict.WATCH
    else:
        verdict = Verdict.NEUTRAL

    # Sanity: if funding extreme and no squeeze warning, cap verdict
    if abs(skew) > 0.7 and verdict in (Verdict.BUY, Verdict.SELL):
        verdict = Verdict.WATCH  # Funding crowded → can't be strong BUY/SELL

    return verdict, direction, bias


# ═══════════════════════════════════════════════════════════════
# REASONS (min 3, max 7)
# ═══════════════════════════════════════════════════════════════

def _generate_futures_reasons(f: Dict) -> List[str]:
    reasons = []
    skew = f["fundingSkewScore"]
    oi = f["oiShiftScore"]
    liq = f["liquidationDensityScore"]
    squeeze = f["squeezeRiskScore"]
    axes = f.get("_axes", {})

    # OI
    if oi > 0.5:
        reasons.append("OI expanding — new positions entering")
    elif oi > 0.2:
        reasons.append("OI slightly rising — moderate interest")
    else:
        reasons.append("OI declining — positions closing")

    # Funding
    if skew > 0.3:
        reasons.append("Funding heavily positive — longs paying shorts")
    elif skew > 0.1:
        reasons.append("Funding slightly positive")
    elif skew < -0.3:
        reasons.append("Funding heavily negative — shorts paying longs")
    elif skew < -0.1:
        reasons.append("Funding slightly negative")
    else:
        reasons.append("Funding neutral — balanced market")

    # Liquidation
    if liq > 0.6:
        reasons.append("High liquidation density — squeeze potential")
    elif liq > 0.3:
        reasons.append("Moderate liquidation activity")
    else:
        reasons.append("Low liquidation density — stable positioning")

    # Squeeze
    if squeeze > 0.6:
        reasons.append("Squeeze risk elevated — crowded positioning")

    # Positioning from axes
    ls = f.get("_lsRatio", 0.5)
    if ls > 0.65:
        reasons.append("Long-heavy positioning — short squeeze risk")
    elif ls < 0.35:
        reasons.append("Short-heavy positioning — long squeeze risk")

    # Momentum
    mom = axes.get("momentum", 0)
    if mom > 0.3:
        reasons.append("Positive momentum building")
    elif mom < -0.3:
        reasons.append("Negative momentum accelerating")

    # Volatility
    if f["volatilityRegimeScore"] > 0.7:
        reasons.append("High volatility regime — expansion mode")

    # Risk warnings
    if f["riskScore"] > 0.6:
        reasons.append("Elevated risk — crowded or thin conditions")

    return reasons[:7]


# ═══════════════════════════════════════════════════════════════
# EXPLAIN BLOCK
# ═══════════════════════════════════════════════════════════════

def _generate_futures_explain(f: Dict, verdict: Verdict, direction: Direction) -> FuturesExplain:
    skew = f["fundingSkewScore"]
    oi = f["oiShiftScore"]
    squeeze = f["squeezeRiskScore"]

    # whyNow
    parts = []
    if oi > 0.4:
        parts.append("OI expanding")
    if abs(skew) > 0.2:
        parts.append(f"funding {'long-heavy' if skew > 0 else 'short-heavy'}")
    if squeeze > 0.5:
        parts.append("squeeze risk building")
    if f["liquidationDensityScore"] > 0.4:
        parts.append("liquidation clusters forming")

    if parts:
        why_now = f"Derivatives setup: {', '.join(parts)}"
    else:
        why_now = "No active derivatives catalysts. Futures market in equilibrium."

    # invalidation
    if direction == Direction.LONG:
        invalidation = "Funding flip to extreme negative or OI collapse invalidates long bias"
    elif direction == Direction.SHORT:
        invalidation = "Funding flip to extreme positive or short squeeze event invalidates short bias"
    else:
        invalidation = "No active directional thesis to invalidate"

    # timeHorizon
    if squeeze > 0.6:
        time_horizon = "2-8h (squeeze imminent)"
    elif oi > 0.5:
        time_horizon = "4-24h (OI driven move expected)"
    else:
        time_horizon = "24-72h (waiting for imbalance to build)"

    return FuturesExplain(whyNow=why_now, invalidation=invalidation, timeHorizon=time_horizon)


# ═══════════════════════════════════════════════════════════════
# FULL VERDICT + SCAN
# ═══════════════════════════════════════════════════════════════

def compute_futures_verdict(features: Dict) -> Dict:
    conviction = _compute_futures_conviction(features)
    verdict, direction, bias = _compute_futures_verdict(features, conviction)

    breakout_prob = int(min(100, max(0, round(
        features["oiShiftScore"] * 35 +
        abs(features["fundingSkewScore"]) * 25 +
        features["liquidationDensityScore"] * 20 +
        features["volatilityRegimeScore"] * 20
    ))))

    risk_val = features["riskScore"]
    if risk_val > 0.65:
        risk = RiskLevel.HIGH
    elif risk_val > 0.4:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.LOW

    # Cap conviction for NEUTRAL/WATCH
    if verdict == Verdict.NEUTRAL:
        conviction = min(conviction, 44)
    elif verdict == Verdict.WATCH:
        conviction = min(conviction, 59)

    return {
        "direction": direction,
        "bias": bias,
        "verdict": verdict,
        "conviction": conviction,
        "breakoutProb": breakout_prob,
        "squeezeRisk": _detect_squeeze_risk(features),
        "squeezeRiskScore": features["squeezeRiskScore"],
        "oiShift": _detect_oi_shift(features),
        "fundingState": _detect_funding_state(features),
        "risk": risk,
        "reasons": _generate_futures_reasons(features),
        "explain": _generate_futures_explain(features, verdict, direction),
        "features": FuturesFeatures(
            oiShift=features["oiShiftScore"],
            fundingSkew=features["fundingSkewScore"],
            liquidationDensity=features["liquidationDensityScore"],
            volatilityRegime=features["volatilityRegimeScore"],
            risk=features["riskScore"],
        ),
    }


# Core fields required for meaningful futures analysis
FUTURES_CORE_FIELDS = ["oiShiftScore", "fundingSkewScore", "liquidationDensityScore", "volatilityRegimeScore"]


def _check_futures_data_quality(f: Dict) -> tuple:
    """Returns (is_data_gap: bool, missing: list)."""
    missing = []
    # Check if features are meaningful (not just defaults)
    if f["oiShiftScore"] == 0 and f["liquidationDensityScore"] <= 0.15 and f["volatilityRegimeScore"] <= 0.4:
        # All at default/floor values → likely no real data
        if not f.get("_axes"):
            missing.append("exchange_verdicts")
        if f.get("_fundingLabel") == "NEUTRAL" and abs(f["fundingSkewScore"]) < 0.01:
            missing.append("funding_context")
        if f.get("_oiChange") == 0 or f.get("_oiChange") is None:
            missing.append("oi_data")
        if f.get("_lsRatio") == 0.5 or f.get("_lsRatio") is None:
            missing.append("long_short_ratio")
    return len(missing) >= 2, missing


def _build_data_gap_futures_row(symbol: str, missing: list) -> FuturesRadarRow:
    """Build a DATA_GAP row for futures when data is insufficient."""
    return FuturesRadarRow(
        symbol=symbol,
        direction=Direction.NEUTRAL,
        bias=FuturesBias.NEUTRAL,
        verdict=Verdict.DATA_GAP,
        conviction=0,
        breakoutProb=0,
        squeezeRisk=SqueezeRisk.LOW,
        squeezeRiskScore=0,
        oiShift=OIShift.FALLING,
        fundingState=FundingState.NEUTRAL,
        risk=RiskLevel.UNKNOWN,
        features=FuturesFeatures(oiShift=0, fundingSkew=0, liquidationDensity=0, volatilityRegime=0, risk=0),
        reasons=["Insufficient derivatives data to compute a reliable setup"],
        explain=FuturesExplain(
            whyNow="No reliable derivatives data available",
            invalidation="N/A (data gap)",
            timeHorizon="N/A (data gap)",
        ),
        updatedAt="",
        dataQuality=DataQualityInfo(status="missing_core_fields", missing=missing),
    )


def scan_futures() -> List[FuturesRadarRow]:
    symbols = get_futures_symbols()
    rows = []

    for symbol in symbols:
        f = compute_futures_features(symbol)
        if not f:
            rows.append(_build_data_gap_futures_row(symbol, ["no_snapshot_data"]))
            continue

        # DATA QUALITY GATE: check if features are meaningful
        is_gap, gap_missing = _check_futures_data_quality(f)
        if is_gap:
            rows.append(_build_data_gap_futures_row(symbol, gap_missing))
            continue

        v = compute_futures_verdict(f)
        rows.append(FuturesRadarRow(
            symbol=symbol,
            direction=v["direction"],
            bias=v["bias"],
            verdict=v["verdict"],
            conviction=v["conviction"],
            breakoutProb=v["breakoutProb"],
            squeezeRisk=v["squeezeRisk"],
            squeezeRiskScore=v["squeezeRiskScore"],
            oiShift=v["oiShift"],
            fundingState=v["fundingState"],
            risk=v["risk"],
            features=v["features"],
            reasons=v["reasons"],
            explain=v["explain"],
            updatedAt=f.get("_updatedAt", ""),
        ))

    rows.sort(key=lambda r: r.conviction, reverse=True)
    return rows
