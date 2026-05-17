"""
Effective Confidence — computes trust-adjusted confidence.

effective = adjustedConfidence × familyTrust × sampleTrust × stabilityTrust
with hard floor of 0.25 (prevents everything from becoming AVOID).

Pipeline position: After calibration + analytics, before decision gate.
"""
import logging

logger = logging.getLogger("feed.effective_confidence")

HARD_FLOOR = 0.25


def compute_effective_confidence(
    confidence: float,
    adjusted_confidence: float | None = None,
    family_strength: str = "UNKNOWN",
    sample_size: int = 0,
    stability_state: str = "STABLE",
) -> dict:
    """Compute effective confidence with trust multipliers.

    Returns:
        base_confidence: original raw confidence
        adjusted_confidence: after calibration correction
        effective_confidence: final trust-adjusted value
        multipliers: {family, sample, stability}
    """
    base = adjusted_confidence if adjusted_confidence is not None else confidence

    family_mult = _family_trust(family_strength)
    sample_mult = _sample_trust(sample_size)
    stability_mult = _stability_trust(stability_state)

    raw_effective = base * family_mult * sample_mult * stability_mult
    effective = max(raw_effective, HARD_FLOOR)  # hard floor
    effective = min(effective, 1.0)

    return {
        "base_confidence": round(confidence, 4),
        "adjusted_confidence": round(base, 4),
        "effective_confidence": round(effective, 4),
        "multipliers": {
            "family": family_mult,
            "sample": sample_mult,
            "stability": stability_mult,
        },
    }


def _family_trust(strength: str) -> float:
    """Family trust multiplier based on historical performance.
    UNKNOWN = no data yet, default to neutral (1.0) to avoid cold-start penalty.
    """
    return {
        "STRONG": 1.0,
        "MEDIUM": 0.9,
        "WEAK": 0.72,
        "UNKNOWN": 1.0,  # neutral until proven otherwise
    }.get(strength, 1.0)


def _sample_trust(sample_size: int) -> float:
    """Sample trust multiplier — less data = less trust.
    Zero samples = no penalty (cold start).
    """
    if sample_size == 0:
        return 1.0  # no data = neutral
    if sample_size < 10:
        return 0.8
    if sample_size < 20:
        return 0.88
    if sample_size < 50:
        return 0.95
    return 1.0


def _stability_trust(state: str) -> float:
    """Stability multiplier — unstable decisions get penalized."""
    return {
        "STABLE": 1.0,
        "UNSTABLE": 0.8,
        "LOCKED": 0.7,
    }.get(state, 0.9)
