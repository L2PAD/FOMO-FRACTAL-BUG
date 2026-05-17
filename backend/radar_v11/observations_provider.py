"""
Observations Provider — reads rich 38-indicator layer from exchange_observations.

Used as PRIMARY source for spot/alpha radar.
Falls back to exchange_symbol_snapshots when observations unavailable.

4-layer Alpha Model:
  1. COMPRESSION: range_compression, atr_normalized, ema_distance, trend_slope
  2. PARTICIPATION: volume_index, relative_volume, participation_intensity, volume_price_response
  3. ORDER_FLOW: absorption_strength, book_imbalance, liquidity_vacuum, spread_pressure
  4. SMART_MONEY: funding_pressure, oi_delta, position_crowding, whale_side_bias
"""

from typing import Dict, Optional, List, Tuple
from pymongo import MongoClient, DESCENDING
import os

_client = None
_db = None

STALE_THRESHOLD_SEC = 900  # 15 minutes


def _get_db():
    global _client, _db
    if _db is None:
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        _client = MongoClient(mongo_url)
        _db = _client[db_name]
    return _db


def get_latest_observation(symbol: str) -> Optional[Dict]:
    """Get the latest observation for a symbol (with 38 indicators)."""
    db = _get_db()
    doc = db["exchange_observations"].find_one(
        {"symbol": symbol},
        {"_id": 0},
        sort=[("timestamp", DESCENDING)],
    )
    if not doc:
        return None
    return doc


def get_latest_observation_by_asset(asset: str) -> Optional[Dict]:
    """Block 7.2 — Get latest observation by asset name (BTC, ETH, SOL).
    Tries `asset` field first, falls back to symbol match."""
    db = _get_db()
    # Try new asset field first
    doc = db["exchange_observations"].find_one(
        {"asset": asset.upper()},
        {"_id": 0},
        sort=[("timestamp", DESCENDING)],
    )
    if doc:
        return doc
    # Fallback: symbol-based lookup
    symbol = f"{asset.upper()}USDT"
    return get_latest_observation(symbol)


def _ind(obs: Dict, name: str, field: str = "value") -> float:
    """Extract indicator value safely."""
    indicators = obs.get("indicators", {})
    ind = indicators.get(name, {})
    if isinstance(ind, dict):
        return float(ind.get(field, 0) or 0)
    return 0.0


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# ═══════════════════════════════════════════════════════════════
# 4-LAYER ALPHA MODEL
# ═══════════════════════════════════════════════════════════════

def compute_compression_layer(obs: Dict) -> float:
    """Layer 1: Structure compression → breakout probability."""
    range_comp = _ind(obs, "range_compression")         # 0..1, higher = more compressed
    atr_norm = _ind(obs, "atr_normalized")               # 0..1, lower = calmer
    trend_slope = abs(_ind(obs, "trend_slope"))           # 0..1, lower = flatter

    # EMA alignment: all EMAs close = compression
    ema_fast = abs(_ind(obs, "ema_distance_fast"))
    ema_mid = abs(_ind(obs, "ema_distance_mid"))
    ema_slow = abs(_ind(obs, "ema_distance_slow"))
    ema_cluster = _clamp(1.0 - (ema_fast + ema_mid + ema_slow) * 3)

    return _clamp(
        range_comp * 0.35
        + (1.0 - atr_norm) * 0.20
        + (1.0 - trend_slope) * 0.20
        + ema_cluster * 0.25
    )


def compute_participation_layer(obs: Dict) -> float:
    """Layer 2: Volume + participation build → accumulation signal."""
    vol_idx = _ind(obs, "volume_index")                   # 0..1
    rel_vol = _ind(obs, "relative_volume")                # 0..1+
    part_int = _ind(obs, "participation_intensity")       # 0..1
    vol_price = _ind(obs, "volume_price_response")        # -1..1

    # Direct volume from top-level
    vol_data = obs.get("volume", {})
    vol_ratio = float(vol_data.get("ratio", 0.5) or 0.5)  # buy/total ratio

    return _clamp(
        vol_idx * 0.25
        + _clamp(rel_vol) * 0.25
        + part_int * 0.25
        + abs(vol_price) * 0.15
        + abs(vol_ratio - 0.5) * 2 * 0.10  # deviation from 50/50
    )


def compute_orderflow_layer(obs: Dict) -> float:
    """Layer 3: Order flow + absorption → smart order detection."""
    absorption = _ind(obs, "absorption_strength")          # 0..1
    book_imb = abs(_ind(obs, "book_imbalance"))            # -1..1 → abs
    liq_vacuum = _ind(obs, "liquidity_vacuum")             # 0..1
    spread_press = _ind(obs, "spread_pressure")            # 0..1
    depth = _ind(obs, "depth_density")                     # 0..1
    liq_walls = _ind(obs, "liquidity_walls")               # 0..1

    # Top-level order flow
    of = obs.get("orderFlow", {})
    of_dominance = float(of.get("dominance", 0) or 0)     # 0..1
    of_imbalance = abs(float(of.get("imbalance", 0) or 0))  # 0..1

    return _clamp(
        absorption * 0.20
        + book_imb * 0.15
        + liq_vacuum * 0.10
        + spread_press * 0.10
        + of_dominance * 0.20
        + of_imbalance * 0.15
        + depth * 0.05
        + liq_walls * 0.05
    )


def compute_smartmoney_layer(obs: Dict) -> float:
    """Layer 4: Positioning + whales → smart money signal."""
    funding_press = abs(_ind(obs, "funding_pressure"))     # -1..1 → abs
    oi_delta = abs(_ind(obs, "oi_delta"))                  # -1..1 → abs
    oi_level = _ind(obs, "oi_level")                       # 0..1
    pos_crowd = _ind(obs, "position_crowding")             # 0..1
    whale_bias = abs(_ind(obs, "whale_side_bias"))         # -1..1 → abs
    contrarian = _ind(obs, "contrarian_pressure_index")    # 0..1
    large_pos = _ind(obs, "large_position_presence")       # 0..1
    stop_hunt = _ind(obs, "stop_hunt_probability")         # 0..1

    return _clamp(
        funding_press * 0.15
        + oi_delta * 0.15
        + oi_level * 0.10
        + pos_crowd * 0.10
        + whale_bias * 0.20
        + contrarian * 0.10
        + large_pos * 0.10
        + stop_hunt * 0.10
    )


# ═══════════════════════════════════════════════════════════════
# MULTI-HORIZON SIGNAL COMPUTATION
# ═══════════════════════════════════════════════════════════════

def compute_short_term_signal(obs: Dict) -> Tuple[str, float]:
    """
    Short-term (0-2d) signal from order flow, liquidations, OI delta,
    funding spikes, participation surges.
    """
    # Order flow
    of = obs.get("orderFlow", {})
    of_imbalance = float(of.get("imbalance", 0) or 0)
    aggressor = str(of.get("aggressorBias", "")).upper()

    # Liquidations
    liqs = obs.get("liquidations", {})
    cascade = bool(liqs.get("cascadeActive", False))
    cascade_dir = str(liqs.get("cascadeDirection", "")).upper()

    # OI delta (short-term positioning shift)
    oi_delta = _ind(obs, "oi_delta")

    # Funding (extreme = contrarian signal)
    funding = _ind(obs, "funding_pressure")

    # Participation (spike = attention)
    part_int = _ind(obs, "participation_intensity")
    rel_vol = _ind(obs, "relative_volume")

    # Absorption
    absorption = _ind(obs, "absorption_strength")

    # Score: -1 (short) to +1 (long)
    score = 0.0
    score += of_imbalance * 0.25
    score += (0.15 if aggressor == "BUY" else -0.15 if aggressor == "SELL" else 0)
    score += oi_delta * 0.15
    score += (-funding * 0.10)  # contrarian: heavy funding = squeeze risk
    score += absorption * 0.10 * (1 if of_imbalance > 0 else -1 if of_imbalance < 0 else 0)

    # Cascade: strong directional force
    if cascade:
        if cascade_dir == "LONG":
            score += 0.20
        elif cascade_dir == "SHORT":
            score -= 0.20

    # Participation amplifier
    activity = _clamp(part_int * 0.5 + rel_vol * 0.5)
    confidence = _clamp(abs(score) * (0.6 + activity * 0.4))

    if score > 0.05:
        return "long", confidence
    elif score < -0.05:
        return "short", confidence
    return "neutral", confidence * 0.5


def compute_mid_term_signal(obs: Dict) -> Tuple[str, float]:
    """
    Mid-term (3-7d) signal from momentum, structure, EMA alignment,
    trend slope, MACD, stochastic.
    """
    rsi = _ind(obs, "rsi_normalized")
    macd = _ind(obs, "macd_delta")
    stoch = _ind(obs, "stochastic")
    roc = _ind(obs, "roc")
    trend_slope = _ind(obs, "trend_slope")
    dir_mom = _ind(obs, "directional_momentum_balance")

    # EMA alignment (all EMAs pointing same way = strong trend)
    ema_fast = _ind(obs, "ema_distance_fast")
    ema_mid = _ind(obs, "ema_distance_mid")
    ema_slow = _ind(obs, "ema_distance_slow")

    # Score: -1 to +1
    score = 0.0
    score += (rsi - 0.5) * 2 * 0.15
    score += macd * 0.20
    score += (stoch - 0.5) * 2 * 0.10
    score += roc * 0.10
    score += trend_slope * 0.15
    score += dir_mom * 0.15

    # EMA alignment bonus
    ema_dirs = [ema_fast, ema_mid, ema_slow]
    if all(e > 0.01 for e in ema_dirs):
        score += 0.15
    elif all(e < -0.01 for e in ema_dirs):
        score -= 0.15

    confidence = _clamp(abs(score))

    if score > 0.08:
        return "long", confidence
    elif score < -0.08:
        return "short", confidence
    return "neutral", confidence * 0.5


def compute_swing_signal(obs: Dict) -> Tuple[str, float]:
    """
    Swing (1-4w) signal from regime, whale positioning, structural
    compression persistence, OI level.
    """
    # Regime (persistent macro trend)
    regime = obs.get("regime", {})
    regime_type = regime.get("type", "NEUTRAL") if isinstance(regime, dict) else "NEUTRAL"
    if isinstance(regime_type, dict):
        regime_type = regime_type.get("type", "NEUTRAL")
    regime_conf = float(regime.get("confidence", 0) or 0)

    # Whale positioning
    whale_bias = _ind(obs, "whale_side_bias")
    large_pos = _ind(obs, "large_position_presence")

    # Positioning
    pos_crowd = _ind(obs, "position_crowding")
    contrarian = _ind(obs, "contrarian_pressure_index")

    # Structure (long-term compression → breakout)
    oi_level = _ind(obs, "oi_level")

    # Score
    score = 0.0

    # Regime is the dominant signal for swing
    if regime_type == "BULLISH":
        score += 0.30 * _clamp(regime_conf)
    elif regime_type == "BEARISH":
        score -= 0.30 * _clamp(regime_conf)

    score += whale_bias * 0.25
    score += large_pos * 0.10 * (1 if whale_bias > 0 else -1 if whale_bias < 0 else 0)

    # Contrarian: extreme crowding = reversal risk
    if pos_crowd > 0.7:
        score -= contrarian * 0.15
    else:
        score += contrarian * 0.05

    # OI buildup = conviction
    score += oi_level * 0.10 * (1 if score > 0 else -1 if score < 0 else 0)

    confidence = _clamp(abs(score))

    if score > 0.06:
        return "long", confidence
    elif score < -0.06:
        return "short", confidence
    return "neutral", confidence * 0.5


# ═══════════════════════════════════════════════════════════════
# DIRECTION DETECTION (from observations)
# ═══════════════════════════════════════════════════════════════

def detect_direction(obs: Dict) -> Tuple[str, float]:
    """
    Returns (direction, confidence).
    direction: "long" | "short" | "neutral"
    confidence: 0..1
    """
    # Momentum indicators
    rsi = _ind(obs, "rsi_normalized")             # 0..1
    macd = _ind(obs, "macd_delta")                # -1..1
    roc = _ind(obs, "roc")                        # -1..1
    dir_mom_bal = _ind(obs, "directional_momentum_balance")  # -1..1
    stoch = _ind(obs, "stochastic")               # 0..1

    # Order flow
    of = obs.get("orderFlow", {})
    aggressor = str(of.get("aggressorBias", "")).upper()
    of_imbalance = float(of.get("imbalance", 0) or 0)  # -1..1

    # Regime
    regime = obs.get("regime", {})
    regime_type = regime.get("type", "NEUTRAL") if isinstance(regime, dict) else "NEUTRAL"
    if isinstance(regime_type, dict):
        regime_type = regime_type.get("type", "NEUTRAL")
    regime_conf = float(regime.get("confidence", 0) or 0)

    # Build directional score (-1 = short, +1 = long)
    score = 0.0
    score += (rsi - 0.5) * 2 * 0.15            # RSI contribution
    score += macd * 0.15                          # MACD
    score += roc * 0.10                           # Rate of change
    score += dir_mom_bal * 0.15                   # Directional momentum
    score += (stoch - 0.5) * 2 * 0.10           # Stochastic
    score += of_imbalance * 0.20                  # Order flow imbalance (strongest)

    # Regime bonus
    if regime_type == "BULLISH":
        score += 0.15 * regime_conf
    elif regime_type == "BEARISH":
        score -= 0.15 * regime_conf

    # Aggressor bonus
    if aggressor == "BUY":
        score += 0.10
    elif aggressor == "SELL":
        score -= 0.10

    confidence = _clamp(abs(score))

    if score > 0.08:
        return "long", confidence
    elif score < -0.08:
        return "short", confidence
    return "neutral", confidence


# ═══════════════════════════════════════════════════════════════
# RISK ASSESSMENT
# ═══════════════════════════════════════════════════════════════

def compute_risk(obs: Dict) -> Tuple[float, str]:
    """Returns (risk_score 0..1, risk_level)."""
    stop_hunt = _ind(obs, "stop_hunt_probability")
    liq_vacuum = _ind(obs, "liquidity_vacuum")
    pos_crowd = _ind(obs, "position_crowding")
    crowd_vs_whale = _ind(obs, "position_crowding_against_whales")
    spread_press = _ind(obs, "spread_pressure")

    # Liquidation cascade check
    liqs = obs.get("liquidations", {})
    cascade = bool(liqs.get("cascadeActive", False))

    risk = (
        stop_hunt * 0.20
        + liq_vacuum * 0.15
        + pos_crowd * 0.15
        + crowd_vs_whale * 0.15
        + spread_press * 0.15
        + (0.3 if cascade else 0) * 0.20
    )
    risk = _clamp(risk)

    if risk > 0.6:
        level = "high"
    elif risk > 0.35:
        level = "medium"
    else:
        level = "low"

    return risk, level


# ═══════════════════════════════════════════════════════════════
# FULL FEATURE PACK (for spot_engine integration)
# ═══════════════════════════════════════════════════════════════

def _build_features_from_obs(obs: Dict) -> Optional[Dict]:
    """Build feature pack from a single observation document."""
    if not obs:
        return None

    # Compute 4 layers
    compression = compute_compression_layer(obs)
    participation = compute_participation_layer(obs)
    orderflow = compute_orderflow_layer(obs)
    smartmoney = compute_smartmoney_layer(obs)

    # Direction
    direction, dir_confidence = detect_direction(obs)

    # Risk
    risk_score, risk_level = compute_risk(obs)

    # Multi-horizon signals
    short_dir, short_conf = compute_short_term_signal(obs)
    mid_dir, mid_conf = compute_mid_term_signal(obs)
    swing_dir, swing_conf = compute_swing_signal(obs)

    # Regime
    regime = obs.get("regime", {})
    regime_type = regime.get("type", "NEUTRAL") if isinstance(regime, dict) else "NEUTRAL"
    if isinstance(regime_type, dict):
        regime_type = regime_type.get("type", "NEUTRAL")

    return {
        "compressionScore": round(compression, 3),
        "volumeBuildScore": round(participation, 3),
        "trendAlignmentScore": round(_clamp(0.5 + (dir_confidence * (1 if direction == "long" else -1 if direction == "short" else 0))), 3),
        "liquidityScore": round(_clamp(1.0 - _ind(obs, "liquidity_vacuum")), 3),
        "riskScore": round(risk_score, 3),
        "_axes": {
            "momentum": _ind(obs, "directional_momentum_balance"),
            "structure": _ind(obs, "range_compression"),
            "participation": _ind(obs, "participation_intensity"),
            "orderbookPressure": _ind(obs, "book_imbalance"),
            "positioning": _ind(obs, "oi_delta"),
            "marketStress": _ind(obs, "stop_hunt_probability"),
        },
        "_regime": regime_type,
        "_verdict": "NEUTRAL",
        "_funding": None,
        "_updatedAt": str(obs.get("timestamp", "")),
        "_source": "observations",
        "_quality": 0.85,
        "_layers": {
            "compression": round(compression, 3),
            "participation": round(participation, 3),
            "orderflow": round(orderflow, 3),
            "smartmoney": round(smartmoney, 3),
        },
        "_direction": direction,
        "_dirConfidence": round(dir_confidence, 3),
        "_riskLevel": risk_level,
        "_obs_orderflow": obs.get("orderFlow", {}),
        "_obs_liquidations": obs.get("liquidations", {}),
        "_obs_regime": regime,
        "_obs_volume": obs.get("volume", {}),
        # Multi-horizon signals
        "_horizon_short": {"direction": short_dir, "conviction": round(short_conf, 3)},
        "_horizon_mid": {"direction": mid_dir, "conviction": round(mid_conf, 3)},
        "_horizon_swing": {"direction": swing_dir, "conviction": round(swing_conf, 3)},
    }


# Keep single-symbol API for backward compat
def build_rich_features(symbol: str) -> Optional[Dict]:
    """Build feature pack from exchange_observations for a single symbol."""
    obs = get_latest_observation(symbol)
    return _build_features_from_obs(obs)


# ═══════════════════════════════════════════════════════════════
# BATCH API (for optimized scan)
# ═══════════════════════════════════════════════════════════════

# Symbols that are test/backfill entries — skip them
_IGNORE_SYMBOLS = {"BACKFILL2", "BACKFILLMAX", "BACKFILLSRC", "BACKFILLTEST", "COVERAGETEST", "LEGACYTICK", "RATELIMITBYPASS"}


def build_rich_features_batch(symbols: List[str]) -> Dict[str, Dict]:
    """
    Batch load observations for multiple symbols.
    Returns {symbol: features_dict} for symbols that have observation data.
    Single aggregation query instead of N find_one calls.
    """
    db = _get_db()

    # Get latest observation per symbol via aggregation
    pipeline = [
        {"$match": {"symbol": {"$in": symbols, "$nin": list(_IGNORE_SYMBOLS)}}},
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$symbol", "doc": {"$first": "$$ROOT"}}},
    ]
    results = list(db["exchange_observations"].aggregate(pipeline))

    features_map = {}
    for r in results:
        sym = r["_id"]
        doc = r["doc"]
        doc.pop("_id", None)
        feat = _build_features_from_obs(doc)
        if feat:
            features_map[sym] = feat

    return features_map
