"""
Exchange Signal Adapter
========================
Converts raw exchange microstructure data into normalized signals
for the Forecast Decision Layer.

Inputs: exchange observations, funding context, whale events
Output: normalized signal dict for bias injection

IMPORTANT: This adapter only READS data, never modifies the exchange pipeline.
"""

from typing import Dict, Any


def clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def safe_norm(x: float, scale: float) -> float:
    if scale == 0:
        return 0.0
    return clamp(x / scale)


def build_exchange_signal(context: Dict[str, Any]) -> Dict[str, float]:
    """
    Build normalized exchange signal from raw microstructure data.

    Input keys (all optional, defaults to 0):
        funding_rate: float — current funding rate
        open_interest_change: float — OI delta
        liq_long: float — liquidation volume longs (USD)
        liq_short: float — liquidation volume shorts (USD)
        whale_volume: float — whale transaction volume (USD)
        pattern_score: float — bullish/bearish pattern score [0, 1]
        bullish_patterns: int — count of bullish patterns
        bearish_patterns: int — count of bearish patterns
        volume_change: float — volume change ratio

    Returns:
        Dict with normalized signals:
            funding_bias: [-1, 1] — negative funding = bullish squeeze
            orderflow_bias: [-1, 1] — liq imbalance direction
            whale_activity: [0, 1] — whale involvement level
            pattern_strength: [0, 1] — pattern detection strength
            micro_bias: [-1, 1] — combined microstructure bias
    """
    funding = context.get("funding_rate", 0.0) or 0.0
    funding_score = context.get("funding_score", 0.0) or 0.0
    oi_change = context.get("open_interest_change", 0.0) or 0.0
    liq_long = context.get("liq_long", 0.0) or 0.0
    liq_short = context.get("liq_short", 0.0) or 0.0
    whale_volume = context.get("whale_volume", 0.0) or 0.0
    bullish = context.get("bullish_patterns", 0) or 0
    bearish = context.get("bearish_patterns", 0) or 0
    volume_change = context.get("volume_change", 0.0) or 0.0
    orderflow_imb = context.get("orderflow_imbalance", 0.0) or 0.0

    # FUNDING BIAS: use funding_score if available, else raw funding_rate
    if abs(funding_score) > 0.01:
        funding_bias = clamp(funding_score * -2.0)  # score is 0-1, invert for bias
    else:
        funding_bias = clamp(funding * -10.0)

    # ORDERFLOW BIAS: use direct orderflow imbalance if available
    if abs(orderflow_imb) > 0.01:
        orderflow_bias = clamp(orderflow_imb)
    else:
        liq_delta = liq_long - liq_short
        orderflow_bias = safe_norm(liq_delta, 1e6)

    # WHALE ACTIVITY: normalized whale volume
    whale_activity = clamp(whale_volume / 1e7, 0.0, 1.0)

    # PATTERN STRENGTH: net bullish-bearish
    total_patterns = bullish + bearish
    if total_patterns > 0:
        pattern_score = (bullish - bearish) / total_patterns
        pattern_strength = clamp(abs(pattern_score), 0.0, 1.0)
        pattern_direction = 1.0 if pattern_score > 0 else -1.0
    else:
        pattern_strength = 0.0
        pattern_direction = 0.0

    # COMBINED MICROSTRUCTURE BIAS
    micro_bias = clamp(
        0.40 * funding_bias
        + 0.35 * orderflow_bias
        + 0.15 * (pattern_strength * pattern_direction)
        + 0.10 * safe_norm(oi_change, 1e8)
    )

    return {
        "funding_bias": round(funding_bias, 4),
        "orderflow_bias": round(orderflow_bias, 4),
        "whale_activity": round(whale_activity, 4),
        "pattern_strength": round(pattern_strength, 4),
        "pattern_direction": round(pattern_direction, 4),
        "micro_bias": round(micro_bias, 4),
    }


# ── Decision Layer Bias Application ─────────────────────

# Guardrails
MAX_EXCHANGE_CONF_DELTA = 0.10
MIN_CONFIDENCE_FLOOR = 0.20

# Mode: "shadow" = log only, "live" = apply bias
EXCHANGE_BIAS_MODE = "shadow"


def apply_exchange_bias(decision: dict, exchange_signal: dict) -> dict:
    """
    Apply exchange microstructure bias to a forecast decision.

    In shadow mode: only logs what WOULD happen.
    In live mode: actually modifies direction and confidence.
    """
    bias = exchange_signal.get("micro_bias", 0.0)
    whale = exchange_signal.get("whale_activity", 0.0)

    direction = decision.get("direction", "NEUTRAL")
    confidence = decision.get("confidence", 0.0)

    # Calculate what the bias WOULD do
    new_direction = direction
    confidence_delta = 0.0

    # Direction bias: only flip if strong signal
    if bias < -0.5 and direction in ("NEUTRAL", "MILD_BULL", "STRONG_BULL"):
        new_direction = "MILD_BEAR"
    elif bias > 0.5 and direction in ("NEUTRAL", "MILD_BEAR", "STRONG_BEAR"):
        new_direction = "MILD_BULL"

    # Confidence adjustment (capped)
    if abs(bias) > 0.4:
        confidence_delta += 0.05 * abs(bias)
    if whale > 0.7:
        confidence_delta += 0.03
    confidence_delta = min(confidence_delta, MAX_EXCHANGE_CONF_DELTA)

    new_confidence = min(1.0, max(MIN_CONFIDENCE_FLOOR, confidence + confidence_delta))

    # Build audit record
    bias_audit = {
        "mode": EXCHANGE_BIAS_MODE,
        "micro_bias": bias,
        "whale_activity": whale,
        "original_direction": direction,
        "proposed_direction": new_direction,
        "direction_changed": new_direction != direction,
        "confidence_delta": round(confidence_delta, 4),
        "original_confidence": round(confidence, 4),
        "proposed_confidence": round(new_confidence, 4),
    }

    if EXCHANGE_BIAS_MODE == "live":
        decision["direction"] = new_direction
        decision["confidence"] = new_confidence
        decision["exchange_bias_applied"] = True
    else:
        decision["exchange_bias_applied"] = False

    decision["exchange_bias_audit"] = bias_audit

    return decision
