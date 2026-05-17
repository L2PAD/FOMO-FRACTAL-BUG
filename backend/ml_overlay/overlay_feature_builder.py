"""
ML Overlay Feature Builder
=============================
Block 5 — Task 5.3

Builds feature vectors from available data at forecast time.
Features must be strictly from BEFORE or AT the forecast timestamp (no leakage).

Feature sources:
  1. Forecast document itself (confidence, direction, move)
  2. exchange_observations near forecast time (market microstructure)
  3. exchange_funding_context (funding state)
  4. Tactical pipeline (derived signals)
"""

from tactical.tactical_signal_builder import build_tactical_signals
from tactical.tactical_fusion_engine import fuse_tactical_signals


_DIRECTION_MAP = {
    "LONG": 1, "UP": 1, "BULL": 1,
    "NEUTRAL": 0, "FLAT": 0,
    "SHORT": -1, "DOWN": -1, "BEAR": -1,
}

_AGGRESSOR_MAP = {"BUY": 1, "NEUTRAL": 0, "SELL": -1}
_ABSORPTION_MAP = {"ASK": 1, "": 0, "BID": -1, None: 0}
_REGIME_MAP = {"TREND": 2, "NEUTRAL": 1, "RANGE": 0}
_BIAS_MAP = {"bullish": 1, "neutral": 0, "bearish": -1}


def build_features_from_forecast_and_obs(
    forecast: dict,
    obs: dict | None,
    funding: dict | None,
) -> dict:
    """
    Build ML feature vector from a forecast + market observation.

    Args:
        forecast: exchange_forecasts document
        obs: nearest exchange_observation at forecast time (or None)
        funding: nearest exchange_funding_context (or None)

    Returns:
        Feature dictionary (all numeric, no missing values)
    """
    features = {}

    # ── 1. Forecast meta features ──
    features["horizon_days"] = forecast.get("horizonDays", 7)
    features["confidence"] = forecast.get("confidence", 0.5)
    features["confidence_raw"] = forecast.get("confidenceRaw") or forecast.get("confidence", 0.5)
    features["expected_move_pct"] = forecast.get("expectedMovePct", 0.0)
    features["direction_encoded"] = _DIRECTION_MAP.get(
        (forecast.get("direction") or "NEUTRAL").upper(), 0
    )

    # Derived: confidence gap (how much confidence was adjusted)
    features["confidence_gap"] = features["confidence"] - features["confidence_raw"]

    # ── 2. Market snapshot features ──
    of = (obs.get("orderFlow") or {}) if obs else {}
    liq = (obs.get("liquidations") or {}) if obs else {}
    vol = (obs.get("volume") or {}) if obs else {}
    oi = (obs.get("openInterest") or {}) if obs else {}
    market = (obs.get("market") or {}) if obs else {}
    regime = (obs.get("regime") or {}) if obs else {}

    features["orderflow_imbalance"] = of.get("imbalance", 0.0)
    features["orderflow_dominance"] = of.get("dominance", 0.5)
    features["aggressor_encoded"] = _AGGRESSOR_MAP.get(
        of.get("aggressorBias", "NEUTRAL"), 0
    )

    features["cascade_active"] = 1 if liq.get("cascadeActive") else 0
    lv = liq.get("longVolume", 0) or 0
    sv = liq.get("shortVolume", 0) or 0
    features["liq_long_volume"] = lv
    features["liq_short_volume"] = sv
    features["liq_ratio"] = lv / max(lv + sv, 1) if (lv + sv) > 0 else 0.5

    features["absorption_active"] = 1 if of.get("absorption") else 0
    features["absorption_side_encoded"] = _ABSORPTION_MAP.get(
        of.get("absorptionSide"), 0
    )

    # ── 3. Funding features ──
    fund = funding or {}
    features["funding_score"] = fund.get("fundingScore", 0.0)
    features["funding_trend"] = fund.get("fundingTrend", 0.0)

    # ── 4. Volatility / OI ──
    features["volume_delta"] = vol.get("delta", 0.0)
    features["oi_delta_pct"] = oi.get("deltaPct", 0.0)
    features["price_volatility"] = market.get("volatility", 0.0)

    # Price momentum
    pc5 = market.get("priceChange5m", 0.0)
    pc15 = market.get("priceChange15m", 0.0)
    features["price_change_5m"] = pc5
    features["price_change_15m"] = pc15

    # ── 5. Regime ──
    features["regime_encoded"] = _REGIME_MAP.get(
        regime.get("type", "NEUTRAL"), 1
    )
    features["regime_confidence"] = regime.get("confidence", 0.5)

    # ── 6. Tactical signals (derived from obs) ──
    if obs:
        snap = {
            "imbalance": of.get("imbalance", 0.0),
            "dominance": of.get("dominance", 0.5),
            "aggressor_bias": of.get("aggressorBias", "NEUTRAL"),
            "long_liq_volume": lv,
            "short_liq_volume": sv,
            "cascade_active": liq.get("cascadeActive", False),
            "cascade_direction": liq.get("cascadeDirection", ""),
            "cascade_phase": liq.get("cascadePhase") or "",
            "funding_score": fund.get("fundingScore", 0.0),
            "funding_trend": fund.get("fundingTrend", 0.0),
            "funding_label": fund.get("label", "NEUTRAL"),
            "absorption": of.get("absorption", False),
            "absorption_side": of.get("absorptionSide", ""),
            "volume_delta": vol.get("delta", 0),
            "oi_delta_pct": oi.get("deltaPct", 0),
        }
        signals = build_tactical_signals(snap)
        fusion = fuse_tactical_signals(signals)
        features["tactical_score"] = fusion["score"]
        features["tactical_bias_encoded"] = _BIAS_MAP.get(fusion["bias"], 0)
        features["tactical_signal_strength"] = fusion["signal_strength"]
        features["tactical_bearish_count"] = fusion["bearish_count"]
        features["tactical_bullish_count"] = fusion["bullish_count"]
    else:
        features["tactical_score"] = 0.0
        features["tactical_bias_encoded"] = 0
        features["tactical_signal_strength"] = 0.0
        features["tactical_bearish_count"] = 0
        features["tactical_bullish_count"] = 0

    # ── 7. Has-data flags ──
    features["has_obs"] = 1 if obs else 0
    features["has_funding"] = 1 if funding else 0

    return features


def get_feature_names() -> list[str]:
    """Return ordered list of feature names for model input."""
    return [
        # Forecast meta
        "horizon_days", "confidence", "confidence_raw", "expected_move_pct",
        "direction_encoded", "confidence_gap",
        # Market
        "orderflow_imbalance", "orderflow_dominance", "aggressor_encoded",
        "cascade_active", "liq_long_volume", "liq_short_volume", "liq_ratio",
        "absorption_active", "absorption_side_encoded",
        # Funding
        "funding_score", "funding_trend",
        # Vol/OI
        "volume_delta", "oi_delta_pct", "price_volatility",
        "price_change_5m", "price_change_15m",
        # Regime
        "regime_encoded", "regime_confidence",
        # Tactical
        "tactical_score", "tactical_bias_encoded", "tactical_signal_strength",
        "tactical_bearish_count", "tactical_bullish_count",
        # Data flags
        "has_obs", "has_funding",
    ]
