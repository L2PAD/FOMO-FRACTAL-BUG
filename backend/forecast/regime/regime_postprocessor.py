"""
Regime Postprocessor
=====================
Derives dominant regime, confidence, entropy, and ambiguity flags
from raw probability distributions.
"""
import math
from forecast.regime.regime_types import REGIME_NAMES

# If top-2 regime probabilities are closer than this, mark ambiguous
_AMBIGUITY_GAP = 0.08
_AMBIGUITY_CONF_SCALE = 0.90


def postprocess_regime(probs: dict) -> dict:
    """
    Postprocess regime probabilities into actionable metadata.

    Returns:
      dominant_regime: str
      regime_confidence: float [0,1]
      regime_entropy: float [0,1]  (normalized)
      flags: list[str]
      probabilities: dict (passthrough)
    """
    sorted_regimes = sorted(REGIME_NAMES, key=lambda r: probs.get(r, 0), reverse=True)
    top1_name = sorted_regimes[0]
    top1_prob = probs[top1_name]
    top2_prob = probs[sorted_regimes[1]]

    # Regime confidence = max probability
    regime_confidence = top1_prob

    # Entropy: normalized Shannon entropy
    # max entropy for 5 states = log(5)
    max_entropy = math.log(5)
    entropy = 0.0
    for r in REGIME_NAMES:
        p = probs.get(r, 0.0)
        if p > 1e-10:
            entropy -= p * math.log(p)
    regime_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

    flags = []

    # Ambiguity detection
    gap = top1_prob - top2_prob
    if gap < _AMBIGUITY_GAP:
        flags.append("ambiguous_regime")
        regime_confidence *= _AMBIGUITY_CONF_SCALE

    # High entropy flag
    if regime_entropy > 0.85:
        flags.append("high_entropy")

    # Low entropy = strong conviction
    if regime_entropy < 0.50:
        flags.append("low_entropy_strong")

    return {
        "dominant_regime": top1_name,
        "regime_confidence": round(regime_confidence, 4),
        "regime_entropy": round(regime_entropy, 4),
        "flags": flags,
        "probabilities": probs,
    }
