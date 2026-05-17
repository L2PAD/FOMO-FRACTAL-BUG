"""
Regime Probability Engine
==========================
Computes 5-state regime probabilities using:
  1. Raw feature scores
  2. Context phase prior (maps calibrated phase → regime boost)
  3. Softmax normalization with tuned temperature

Regimes:
  trend       — sustained directional continuation
  range       — weak directionality, mixed structure
  pullback    — counter-trend local move within live major trend
  transition  — unstable, structure/context disagree, restructuring
  breakdown   — stress/damage, downside pressure dominates
"""
import math
from forecast.regime.regime_types import REGIME_NAMES

# Softmax temperature: lower = sharper, higher = flatter
# Calibrated: 0.25 gives dominant 57-79% for clear regimes,
# meaningful entropy range (0.50-0.97), ambiguity in mixed cases
_TEMPERATURE = 0.25

# Context phase → regime prior mapping
# The calibrated context phase gives strong directional hint.
# Priors scaled to overcome raw scoring biases observed in real BTC data:
#   range_score has structural advantage (~+0.30 centered) for moderate features,
#   so counter-range phases need stronger priors to activate correctly.
_PHASE_REGIME_PRIOR = {
    "continuation":         {"trend": 0.30, "range": -0.15, "pullback": -0.05, "transition": -0.12, "breakdown": -0.12},
    "late_trend":           {"trend": 0.15, "range": -0.05, "pullback": 0.03, "transition": 0.10, "breakdown": -0.05},
    "pullback":             {"trend": 0.03, "range": -0.12, "pullback": 0.30, "transition": -0.05, "breakdown": -0.08},
    "breakdown":            {"trend": -0.15, "range": -0.15, "pullback": -0.08, "transition": 0.03, "breakdown": 0.40},
    "recovery_attempt":     {"trend": -0.08, "range": 0.03, "pullback": 0.03, "transition": 0.05, "breakdown": 0.12},
    "unstable_transition":  {"trend": -0.15, "range": -0.12, "pullback": -0.03, "transition": 0.40, "breakdown": 0.03},
    "mixed_range":          {"trend": -0.06, "range": 0.18, "pullback": 0.00, "transition": 0.03, "breakdown": 0.00},
}


def _softmax(scores: list[float], temperature: float) -> list[float]:
    """Numerically stable softmax with temperature scaling."""
    scaled = [s / temperature for s in scores]
    max_s = max(scaled)
    exps = [math.exp(s - max_s) for s in scaled]
    total = sum(exps)
    return [e / total for e in exps]


def compute_regime_probabilities(features: dict, context_phase: str = "mixed_range") -> dict:
    """
    Compute 5-state regime probabilities from regime features + context phase prior.
    """
    ts = features["trend_strength"]
    tp = features["trend_persistence"]
    ex = features["exhaustion"]
    rr = features["reversal_risk"]
    dp = features["drawdown_pressure"]
    sa = features["structure_alignment"]
    ve = features["volatility_expansion"]

    # Raw scoring: each regime gets a weighted score
    trend_score = (
        0.35 * ts + 0.30 * tp + 0.15 * sa - 0.10 * rr - 0.10 * ex
    )
    range_score = (
        0.30 * (1.0 - ts) + 0.25 * (1.0 - tp) + 0.20 * (1.0 - sa)
        + 0.15 * (1.0 - ve) + 0.10 * (1.0 - dp)
    )
    pullback_score = (
        0.30 * ts + 0.20 * tp + 0.25 * rr + 0.15 * (1.0 - dp)
        + 0.10 * (1.0 - sa)
    )
    transition_score = (
        0.30 * rr + 0.25 * ex + 0.20 * (1.0 - sa) + 0.15 * ve
        + 0.10 * (1.0 - tp)
    )
    breakdown_score = (
        0.45 * dp + 0.20 * rr + 0.15 * ve + 0.10 * (1.0 - ts)
        + 0.10 * ex
    )

    raw = [trend_score, range_score, pullback_score, transition_score, breakdown_score]

    # Center raw scores to remove structural bias
    mean_score = sum(raw) / len(raw)
    centered = [s - mean_score for s in raw]

    # Apply context phase prior (the calibrated phase is a strong signal)
    prior = _PHASE_REGIME_PRIOR.get(context_phase, _PHASE_REGIME_PRIOR["mixed_range"])
    boosted = [
        centered[i] + prior.get(name, 0.0)
        for i, name in enumerate(REGIME_NAMES)
    ]

    probs = _softmax(boosted, _TEMPERATURE)

    return {
        name: round(p, 6)
        for name, p in zip(REGIME_NAMES, probs)
    }
