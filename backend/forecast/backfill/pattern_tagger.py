"""
Pattern Tagger
================
Tags replay cases with market pattern labels for diagnosis.
Deterministic rules based on structure features + outcome.
"""


def tag_patterns(case: dict, structure_features: dict, meta: dict) -> list[str]:
    """
    Tag a replay case with one or more pattern labels.
    Returns list of applicable pattern tags.
    """
    tags = []

    bias = structure_features.get("structure_bias_score", 0)
    momentum = structure_features.get("structure_momentum_score", 0)
    reversal_risk = structure_features.get("structure_reversal_risk", 0)
    exhaustion = structure_features.get("structure_exhaustion_score", 0)
    stability = structure_features.get("structure_stability_score", 0)
    compression = structure_features.get("structure_compression_score", 0)

    base_dir = case.get("base_direction", "NEUTRAL")
    struct_dir = case.get("structure_direction", "NEUTRAL")
    real_dir = case.get("real_direction", "FLAT")
    struct_correct = case.get("structure_correct", False)
    base_correct = case.get("base_correct", False)

    # ── trend_confirmation_helped ──
    # Structure bias aligned with base and both correct
    if struct_correct and base_correct and abs(bias) > 0.3:
        if _same_side(base_dir, struct_dir):
            tags.append("trend_confirmation_helped")

    # ── pullback_misread ──
    # Bias is bullish but short-term momentum bearish → structure went bearish → but market continued up
    if bias > 0.3 and momentum < -0.2 and real_dir == "BULL":
        if not struct_correct and struct_dir in ("MILD_BEAR", "STRONG_BEAR", "NEUTRAL"):
            tags.append("pullback_misread")

    if bias < -0.3 and momentum > 0.2 and real_dir == "BEAR":
        if not struct_correct and struct_dir in ("MILD_BULL", "STRONG_BULL", "NEUTRAL"):
            tags.append("pullback_misread")

    # ── fake_breakout ──
    # High reversal risk → structure adjusted → but market continued original direction
    if reversal_risk > 0.5 and not struct_correct and base_correct:
        tags.append("fake_breakout")

    # ── late_trend_exhaustion ──
    # Exhaustion was high → structure weakened the call → correctly
    if exhaustion > 0.4 and struct_correct and not base_correct:
        tags.append("late_trend_exhaustion")

    # ── range_chop_overreaction ──
    # Low stability + compression → structure moved signal → but was wrong
    if stability < 0.4 and compression > 0.3 and not struct_correct:
        tags.append("range_chop_overreaction")

    # If no specific pattern matched, classify by general type
    if not tags:
        if case.get("case_type") == "structure_improved":
            tags.append("generic_improved")
        elif case.get("case_type") == "structure_hurt":
            tags.append("generic_hurt")
        elif case.get("strength_only_change"):
            tags.append("strength_adjustment")
        else:
            tags.append("no_impact")

    return tags


def _same_side(d1: str, d2: str) -> bool:
    """Check if two directions are on the same side (bull/bear)."""
    bull = {"STRONG_BULL", "MILD_BULL"}
    bear = {"STRONG_BEAR", "MILD_BEAR"}
    return (d1 in bull and d2 in bull) or (d1 in bear and d2 in bear) or d1 == d2
