"""
System Aggregator V2 — Horizon-Aware Decision Brain
=====================================================
Combines all 4 modules into a single signal with horizon-specific weights.

FIX 1-8: Aggregator Optimization
  - Sentiment disabled for 7D/30D (time-dependent noise on long horizons)
  - Sentiment only for 24H with directional filter
  - Horizon-specific weight splits
  - Fractal weight reduced for 7D
  - Confidence excludes sentiment for non-24H
  - Hard guard: sentiment = 0 for all non-24H horizons
"""

from dataclasses import dataclass


# ── Feature flags ──
SYSTEM_AGGREGATOR_MODE = "controlled_live"  # "shadow" | "controlled_live" | "live"
SYSTEM_AGGREGATOR_PCT = 0.10                # % of traffic using aggregator output
SYSTEM_AGGREGATOR_SALT = "agg_v1_launch"


@dataclass
class AggregatorInputs:
    forecast_score: float
    exchange_bias: float
    sentiment_score: float
    sentiment_confidence: float
    fractal_signal: float
    fractal_confidence: float
    regime: str
    conflict_score: float
    horizon: str = "24H"


@dataclass
class AggregatorOutput:
    final_score: float
    direction: str
    confidence: float
    components: dict
    penalties: dict


# ── Horizon-specific weights (FIX 6) ──
HORIZON_WEIGHTS = {
    "24H": {"forecast": 0.35, "exchange": 0.30, "sentiment": 0.25, "fractal": 0.10},
    "7D":  {"forecast": 0.55, "exchange": 0.35, "sentiment": 0.00, "fractal": 0.10},
    "30D": {"forecast": 0.60, "exchange": 0.30, "sentiment": 0.00, "fractal": 0.10},
}
DEFAULT_WEIGHTS = {"forecast": 0.55, "exchange": 0.35, "sentiment": 0.00, "fractal": 0.10}

# Fractal horizon filter: fractal signal only meaningful for these horizons
# 7D is too short for fractal (365D/180D signals), 24H even shorter
FRACTAL_ALLOWED_HORIZONS = {"30D"}

ZERO_THRESHOLD = 0.001
SENTIMENT_MIN_STRENGTH = 0.2  # FIX 4: directional filter


def compute_aggregated_signal(inp: AggregatorInputs) -> AggregatorOutput:
    """
    Core aggregation with horizon-aware weight tuning.
    """
    penalties = {}
    horizon = inp.horizon or "24H"
    weights = HORIZON_WEIGHTS.get(horizon, DEFAULT_WEIGHTS)

    # ── FIX 1+2+8: Sentiment ONLY for 24H, HARD GUARD ──
    if horizon != "24H":
        sentiment_bias = 0.0
        penalties["sentiment_blocked"] = horizon
    else:
        sentiment_bias = inp.sentiment_score
        # FIX 4: directional filter
        if abs(sentiment_bias) < SENTIMENT_MIN_STRENGTH:
            sentiment_bias = 0.0
            penalties["sentiment_weak_filtered"] = True
        # Low confidence scaling
        elif inp.sentiment_confidence < 0.6:
            sentiment_bias *= 0.5
            penalties["sentiment_low_conf"] = True

    # Fractal scaling — signal * confidence
    # Only allow fractal for 30D+ horizons (shorter = noise from long-term signal)
    if horizon not in FRACTAL_ALLOWED_HORIZONS:
        fractal_bias = 0.0
        penalties["fractal_blocked"] = horizon
    else:
        fractal_bias = inp.fractal_signal * inp.fractal_confidence

    # Build components
    raw_components = {
        "forecast": inp.forecast_score,
        "exchange": inp.exchange_bias,
        "sentiment": sentiment_bias,
        "fractal": fractal_bias,
    }

    # Adaptive weight normalization for missing components
    active_weight = sum(
        weights[k] for k, v in raw_components.items() if abs(v) > ZERO_THRESHOLD
    )
    if active_weight > 0 and active_weight < 0.99:
        scale_factor = 1.0 / active_weight
        penalties["weight_normalized"] = round(scale_factor, 4)
    else:
        scale_factor = 1.0

    # Base aggregation
    final_score = 0.0
    for k, v in raw_components.items():
        if abs(v) > ZERO_THRESHOLD:
            final_score += weights[k] * scale_factor * v

    # Regime discipline
    if inp.regime == "TREND_DOWN" and final_score > 0:
        final_score *= 0.8
        penalties["regime_counter_trend"] = True
    elif inp.regime == "TREND_UP" and final_score < 0:
        final_score *= 0.8
        penalties["regime_counter_trend"] = True

    # Conflict penalty
    if inp.conflict_score > 0.6:
        final_score *= 0.7
        penalties["high_conflict"] = True

    # Clamp
    final_score = max(-1.0, min(1.0, final_score))

    # Direction
    if final_score > 0.1:
        direction = "LONG"
    elif final_score < -0.1:
        direction = "SHORT"
    else:
        direction = "NEUTRAL"

    # ── FIX 7: Confidence excludes sentiment for non-24H ──
    if horizon != "24H":
        # Only active components contribute to confidence (exclude sentiment)
        active_parts = []
        if abs(inp.forecast_score) > ZERO_THRESHOLD:
            active_parts.append(min(abs(inp.forecast_score), 1.0))
        if abs(inp.exchange_bias) > ZERO_THRESHOLD:
            active_parts.append(min(abs(inp.exchange_bias), 1.0))
        if abs(fractal_bias) > ZERO_THRESHOLD:
            active_parts.append(min(abs(fractal_bias), 1.0))
        confidence = sum(active_parts) / max(len(active_parts), 1) if active_parts else 0.0
    else:
        # All components contribute for 24H
        active_parts = []
        for k, v in raw_components.items():
            if abs(v) > ZERO_THRESHOLD:
                active_parts.append(min(abs(v), 1.0))
        confidence = sum(active_parts) / max(len(active_parts), 1) if active_parts else 0.0

    if inp.conflict_score > 0.6:
        confidence *= 0.7

    # Signal quality filter
    if confidence < 0.35:
        direction = "NEUTRAL"
        penalties["low_confidence_suppress"] = True

    confidence = max(0.2, min(0.9, confidence))

    return AggregatorOutput(
        final_score=round(final_score, 6),
        direction=direction,
        confidence=round(confidence, 4),
        components={
            "forecast": round(inp.forecast_score, 6),
            "exchange": round(inp.exchange_bias, 6),
            "sentiment": round(sentiment_bias, 6),
            "fractal": round(fractal_bias, 6),
        },
        penalties=penalties,
    )


def aggregator_to_audit(output: AggregatorOutput) -> dict:
    """Convert AggregatorOutput to audit-safe dict."""
    return {
        "mode": SYSTEM_AGGREGATOR_MODE,
        "pct": SYSTEM_AGGREGATOR_PCT,
        "final_score": output.final_score,
        "direction": output.direction,
        "confidence": output.confidence,
        "components": output.components,
        "penalties": output.penalties,
    }


def should_use_aggregator(forecast_id: str, exchange_bias: float, horizon: str) -> bool:
    """
    Controlled live routing:
    - Only when SYSTEM_AGGREGATOR_MODE != "shadow"
    - Only when exchange_bias is available (≠ 0)
    - Hash-based traffic split for controlled rollout
    """
    import hashlib

    if SYSTEM_AGGREGATOR_MODE == "shadow":
        return False

    # STEP 1: Exchange must be available
    if abs(exchange_bias) < 0.001:
        return False

    if SYSTEM_AGGREGATOR_MODE == "live":
        return True

    # controlled_live: hash-based split
    h = hashlib.md5(f"{forecast_id}{SYSTEM_AGGREGATOR_SALT}".encode()).hexdigest()
    bucket = int(h[:8], 16) / 0xFFFFFFFF
    return bucket < SYSTEM_AGGREGATOR_PCT


def apply_aggregator_to_forecast(
    forecast_id: str,
    current_direction: str,
    current_confidence: float,
    current_score: float,
    agg_output: "AggregatorOutput",
    exchange_bias: float,
    horizon: str,
) -> dict:
    """
    STEP 2-3: Apply aggregator in controlled live mode.
    Returns telemetry dict for audit["aggregator_live"].
    """
    use_agg = should_use_aggregator(forecast_id, exchange_bias, horizon)

    if use_agg:
        final_direction = agg_output.direction
        final_confidence = max(0.2, min(0.9, agg_output.confidence))
        final_score = agg_output.final_score
    else:
        final_direction = current_direction
        final_confidence = current_confidence
        final_score = current_score

    telemetry = {
        "used": use_agg,
        "exchange_available": abs(exchange_bias) >= 0.001,
        "horizon": horizon,
        "mode": SYSTEM_AGGREGATOR_MODE,
        "pct": SYSTEM_AGGREGATOR_PCT,
        "delta_direction": agg_output.direction != current_direction,
        "delta_confidence": round(agg_output.confidence - current_confidence, 4),
        "agg_direction": agg_output.direction,
        "agg_confidence": agg_output.confidence,
        "decision_direction": current_direction,
        "decision_confidence": round(current_confidence, 4),
    }

    return {
        "direction": final_direction,
        "confidence": final_confidence,
        "score": final_score,
        "telemetry": telemetry,
    }


def disable_aggregator():
    """STEP 5: Kill switch — disable aggregator immediately."""
    global SYSTEM_AGGREGATOR_MODE, SYSTEM_AGGREGATOR_PCT
    SYSTEM_AGGREGATOR_MODE = "shadow"
    SYSTEM_AGGREGATOR_PCT = 0.0
    return {"disabled": True, "mode": "shadow", "pct": 0.0}


def get_aggregator_status() -> dict:
    """Return current aggregator convergence status."""
    return {
        "mode": SYSTEM_AGGREGATOR_MODE,
        "pct": SYSTEM_AGGREGATOR_PCT,
        "salt": SYSTEM_AGGREGATOR_SALT,
    }

