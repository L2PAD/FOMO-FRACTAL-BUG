"""
Shadow Case Comparator
========================
Compares base vs structure forecast against actual outcome.
Produces case type + detailed comparison.
"""


def compare_case(
    base: dict,
    structure: dict,
    outcome: dict,
) -> dict:
    """
    Compare base and structure forecasts against the actual outcome.
    Returns case type and detailed comparison.
    """
    real_dir = outcome["real_direction"]

    base_correct = _direction_match(base["direction"], real_dir)
    struct_correct = _direction_match(structure["direction"], real_dir)

    # Classify case type
    if struct_correct and not base_correct:
        case_type = "structure_improved"
    elif not struct_correct and base_correct:
        case_type = "structure_hurt"
    elif struct_correct and base_correct:
        case_type = "both_correct"
    else:
        case_type = "both_wrong"

    # Detect strength-only changes
    base_sign = _direction_sign(base["direction"])
    struct_sign = _direction_sign(structure["direction"])
    sign_changed = base_sign != struct_sign
    strength_only = (not sign_changed) and (base["direction"] != structure["direction"])

    return {
        "case_type": case_type,
        "base_direction": base["direction"],
        "structure_direction": structure["direction"],
        "real_direction": real_dir,
        "base_correct": base_correct,
        "structure_correct": struct_correct,
        "direction_changed": base["direction"] != structure["direction"],
        "sign_changed": sign_changed,
        "strength_only_change": strength_only,
        "delta_score": round(structure["score"] - base["score"], 6),
        "real_move_pct": outcome["real_move_pct"],
    }


def _direction_match(predicted: str, actual: str) -> bool:
    """Check if predicted direction matches actual market move."""
    bullish = {"STRONG_BULL", "MILD_BULL"}
    bearish = {"STRONG_BEAR", "MILD_BEAR"}

    if actual == "BULL":
        return predicted in bullish
    elif actual == "BEAR":
        return predicted in bearish
    else:
        return predicted == "NEUTRAL"


def _direction_sign(direction: str) -> int:
    """Map direction to sign: +1, 0, -1."""
    if direction in ("STRONG_BULL", "MILD_BULL"):
        return 1
    elif direction in ("STRONG_BEAR", "MILD_BEAR"):
        return -1
    return 0
