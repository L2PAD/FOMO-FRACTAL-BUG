"""
Decision Layer V1 — Scenario Proxy
=====================================
Derives scenario probabilities for 7D/24H horizons
where the full ScenarioEngine V2 does not run.

Uses available signals (structure, context, regime, direction)
to synthesize bullish/base/bearish probabilities.
"""


def derive_scenario_probs(
    forecast_direction: str,
    calibrated_confidence: float,
    regime_entropy: float,
    bullish_structure: float,
    bearish_structure: float,
    context_alignment: float,
    negative_context: float,
) -> dict:
    """
    Returns dict with keys: bullish_prob, base_prob, bearish_prob, dominant_scenario, dominant_scenario_prob.
    All probabilities sum to 1.0.
    """
    # Raw directional signals
    bull_signal = (
        0.30 * bullish_structure
        + 0.25 * context_alignment
        + 0.25 * calibrated_confidence
        + 0.20 * (1.0 - regime_entropy)
    )

    bear_signal = (
        0.30 * bearish_structure
        + 0.25 * negative_context
        + 0.25 * calibrated_confidence
        + 0.20 * (1.0 - regime_entropy)
    )

    # Direction prior boost (stronger than default)
    if forecast_direction == "bullish":
        bull_signal *= 1.25
    elif forecast_direction == "bearish":
        bear_signal *= 1.25

    # Base = uncertainty / range-bound (reduced from 0.40 entropy weight)
    base_signal = (
        0.30 * regime_entropy
        + 0.35 * (1.0 - abs(bullish_structure - bearish_structure))
        + 0.35 * (1.0 - calibrated_confidence)
    )

    # Normalize to probabilities via softmax-like division
    total = bull_signal + bear_signal + base_signal
    if total < 0.01:
        return {
            "bullish_prob": 0.33,
            "base_prob": 0.34,
            "bearish_prob": 0.33,
            "dominant_scenario": "base",
            "dominant_scenario_prob": 0.34,
        }

    bullish_prob = bull_signal / total
    bearish_prob = bear_signal / total
    base_prob = base_signal / total

    # Determine dominant
    probs = {"bullish": bullish_prob, "base": base_prob, "bearish": bearish_prob}
    dominant = max(probs, key=probs.get)

    return {
        "bullish_prob": round(bullish_prob, 4),
        "base_prob": round(base_prob, 4),
        "bearish_prob": round(bearish_prob, 4),
        "dominant_scenario": dominant,
        "dominant_scenario_prob": round(probs[dominant], 4),
    }
