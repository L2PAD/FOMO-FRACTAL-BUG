"""
Scenario Weighting Engine
==========================
Assigns probabilities to bullish/base/bearish scenarios.

Key rules:
  - Probabilities ALWAYS sum to 1.0
  - Regime probs DO NOT map 1:1 to scenario probs
    (trend=0.7 does NOT mean bullish=0.7)
  - Base scenario is anchored and often dominant
  - Uncertainty → flattens distribution (more uniform)
  - Strong signals → concentrates on one tail

Inputs used:
  - momentum (directional signal strength)
  - structure_bias (structural lean)
  - regime_probs (5-regime distribution, optional)
  - dominant_regime
  - decision_uncertainty
  - context_phase (optional)
"""

from forecast.scenario.scenario_types import ScenarioInput


def _softmax3(scores: list[float], temperature: float = 1.0) -> list[float]:
    """Softmax over 3 values with temperature."""
    import math
    scaled = [s / max(temperature, 0.05) for s in scores]
    max_s = max(scaled)
    exps = [math.exp(s - max_s) for s in scaled]
    total = sum(exps)
    return [e / total for e in exps]


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_scenario_weights(inp: ScenarioInput) -> dict:
    """
    Compute scenario probabilities.

    Strategy:
      1. Start from base prior (base=0.45, tails=0.275 each)
      2. Directional tilt from momentum + structure
      3. Regime influence (indirect, NOT 1:1)
      4. Uncertainty flattening
      5. Normalize to sum=1.0

    Returns dict with {bullish, base, bearish} probabilities.
    """
    momentum = inp["momentum"]
    structure_bias = inp.get("structure_bias", 0.0)
    uncertainty = inp.get("decision_uncertainty", 0.5)
    dominant_regime = inp.get("dominant_regime", "range")
    regime_probs = inp.get("regime_probs")
    context_phase = inp.get("context_phase")
    regime_entropy = inp.get("regime_entropy", 0.5)

    # ── 1. Base prior: slightly front-loaded toward base ──
    bullish_score = 0.0
    base_score = 0.20  # base has a structural advantage
    bearish_score = 0.0

    # ── 2. Directional tilt ──
    # Momentum contribution: moderate influence
    # Positive momentum → tilt bullish, negative → bearish
    dir_signal = momentum * 0.4 + structure_bias * 0.2
    bullish_score += max(0, dir_signal) * 0.5
    bearish_score += max(0, -dir_signal) * 0.5

    # ── 3. Regime influence (indirect mapping) ──
    # NOT: trend=0.7 → bullish=0.7
    # INSTEAD: trend probability adds a gentle tilt
    if regime_probs:
        trend_p = regime_probs.get("trend", 0.2)
        range_p = regime_probs.get("range", 0.2)
        pullback_p = regime_probs.get("pullback", 0.2)
        breakdown_p = regime_probs.get("breakdown", 0.1)
        transition_p = regime_probs.get("transition", 0.1)

        # Trend → mild bullish tilt (if momentum aligns)
        if momentum > 0:
            bullish_score += trend_p * 0.20
        else:
            bearish_score += trend_p * 0.20

        # Range → boost base (no directional edge)
        base_score += range_p * 0.15

        # Pullback → counter-current bias (mean reversion)
        if momentum > 0:
            bearish_score += pullback_p * 0.10
        else:
            bullish_score += pullback_p * 0.10

        # Breakdown → bearish tilt
        bearish_score += breakdown_p * 0.25

        # Transition → base boost (low conviction everywhere)
        base_score += transition_p * 0.15
    else:
        # No regime probs available → use dominant regime as proxy
        if dominant_regime == "trend":
            tilt = 0.10 if momentum > 0 else -0.10
            bullish_score += max(0, tilt)
            bearish_score += max(0, -tilt)
        elif dominant_regime == "range":
            base_score += 0.10
        elif dominant_regime == "breakdown":
            bearish_score += 0.12
        elif dominant_regime == "transition":
            base_score += 0.08
        elif dominant_regime == "pullback":
            # Counter-momentum bias
            tilt = -0.08 if momentum > 0 else 0.08
            bullish_score += max(0, tilt)
            bearish_score += max(0, -tilt)

    # ── 4. Context phase influence (gentle) ──
    if context_phase:
        _PHASE_SCENARIO_TILT = {
            "continuation":        (0.08, -0.02, -0.04),   # (bull, base, bear)
            "late_trend":          (0.02, 0.02, 0.04),
            "pullback":            (-0.03, 0.05, 0.02),
            "breakdown":           (-0.06, -0.02, 0.10),
            "recovery_attempt":    (0.04, 0.03, -0.02),
            "unstable_transition": (-0.02, 0.06, 0.02),
            "mixed_range":         (0.00, 0.06, 0.00),
        }
        tilt = _PHASE_SCENARIO_TILT.get(context_phase, (0, 0, 0))
        bullish_score += tilt[0]
        base_score += tilt[1]
        bearish_score += tilt[2]

    # ── 5. Uncertainty flattening ──
    # High uncertainty → temperature rises → distribution flattens
    # Low uncertainty → temperature drops → more concentrated
    # Mapped: uncertainty 0→0.35, 0.5→1.18, 1.0→2.0
    temperature = 0.35 + uncertainty * 1.65

    # Convert scores to probabilities via softmax
    raw_scores = [bullish_score, base_score, bearish_score]
    probs = _softmax3(raw_scores, temperature)

    # ── 6. Stability guard ──
    # No scenario below 8% (always some probability for each)
    MIN_PROB = 0.08
    probs = [max(p, MIN_PROB) for p in probs]
    total = sum(probs)
    probs = [p / total for p in probs]

    result = {
        "bullish": round(probs[0], 4),
        "base": round(probs[1], 4),
        "bearish": round(probs[2], 4),
        "_debug": {
            "raw_scores": [round(s, 4) for s in raw_scores],
            "temperature": round(temperature, 4),
            "dir_signal": round(dir_signal, 4),
            "regime_source": "probs" if regime_probs else "dominant",
        },
    }

    # Ensure sum = 1.0 (fix rounding)
    diff = 1.0 - (result["bullish"] + result["base"] + result["bearish"])
    result["base"] = round(result["base"] + diff, 4)

    return result
