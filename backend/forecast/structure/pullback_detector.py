"""
Pullback Detector
==================
Determines the relationship between major and minor structure:
  - aligned: both point same direction → strengthen
  - pullback: minor opposes major but major is healthy → don't flip
  - reversal_candidate: minor opposes AND major shows weakness → allow correction
  - mixed_range: both weak/unclear → minimize influence
"""


def detect_mode(major: dict, minor: dict) -> dict:
    """
    Detect structure mode from major/minor features.
    Returns mode, pullback_confidence, reversal_candidate flag, and diagnostic flags.
    """
    major_bias = major.get("structure_bias_score", 0.0)
    minor_bias = minor.get("structure_bias_score", 0.0)
    major_reversal = major.get("structure_reversal_risk", 0.0)
    minor_momentum = minor.get("structure_momentum_score", 0.0)
    major_trend = major.get("structure_trend_score", 0.0)
    major_stability = major.get("structure_stability_score", 0.0)

    major_directional = abs(major_bias) > 0.25
    minor_directional = abs(minor_bias) > 0.15
    same_sign = _same_sign(major_bias, minor_bias)
    opposite_sign = minor_directional and major_directional and not same_sign

    # Major dominance: strong and healthy major trend
    major_dominant = abs(major_bias) > 0.45 and major_reversal < 0.40

    # ── Reversal candidate (strictest check first) ──
    reversal_candidate = (
        major_reversal > 0.62
        and abs(minor_momentum) > 0.50
        and opposite_sign
    )

    if reversal_candidate:
        pullback_conf = 1.0 - min(1.0, major_reversal)
        return {
            "mode": "reversal_candidate",
            "pullback_confidence": round(pullback_conf, 4),
            "reversal_candidate": True,
            "major_dominant": major_dominant,
            "minor_counter_trend": True,
        }

    # ── Pullback: major directional, minor opposes, major healthy ──
    if major_directional and opposite_sign and major_reversal < 0.45:
        pullback_conf = min(1.0, major_trend * 0.5 + major_stability * 0.3 + (1.0 - major_reversal) * 0.2)
        return {
            "mode": "pullback",
            "pullback_confidence": round(pullback_conf, 4),
            "reversal_candidate": False,
            "major_dominant": major_dominant,
            "minor_counter_trend": True,
        }

    # ── Aligned: both same direction ──
    if major_directional and same_sign:
        return {
            "mode": "aligned",
            "pullback_confidence": 0.0,
            "reversal_candidate": False,
            "major_dominant": major_dominant,
            "minor_counter_trend": False,
        }

    # ── Mixed range: both weak or unclear ──
    return {
        "mode": "mixed_range",
        "pullback_confidence": 0.0,
        "reversal_candidate": False,
        "major_dominant": False,
        "minor_counter_trend": opposite_sign,
    }


def _same_sign(a: float, b: float) -> bool:
    """Check if two values have the same sign (both positive or both negative)."""
    if a == 0 or b == 0:
        return False
    return (a > 0) == (b > 0)
