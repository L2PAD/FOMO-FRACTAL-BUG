"""
Market Stage Engine — lifecycle stage for each prediction case.

Stages: new, forming, triggered, repricing, crowded, exhausted, invalidated
"""


def compute_stage(repricing_state: str, edge: float, confidence: float,
                  recommendation_action: str, sizing_allowed: bool,
                  snap_count: int = 0) -> str:
    """
    Determine lifecycle stage from case analysis.

    Returns: stage string
    """
    # Invalidated: system says avoid
    if recommendation_action == "AVOID" or (edge < 0 and confidence < 0.3):
        return "invalidated"

    # Exhausted: market overheated or at fair value with no edge
    if repricing_state in ("overheated", "panic_move"):
        return "exhausted"

    if repricing_state == "fair_value" and abs(edge) < 0.03:
        return "exhausted"

    # Crowded: late repricing, edge thin
    if repricing_state == "late_repricing" and abs(edge) < 0.05:
        return "crowded"

    # Repricing: active movement
    if repricing_state in ("active_repricing", "late_repricing"):
        return "repricing"

    # Triggered: actionable entry
    if repricing_state in ("fresh_mispricing", "early_repricing") and sizing_allowed:
        return "triggered"

    # Forming: edge exists but conditions not ready
    if abs(edge) >= 0.05 and (not sizing_allowed or repricing_state == "stalled"):
        return "forming"

    # New: first seen, no snapshots, needs monitoring
    if snap_count < 3:
        return "new"

    return "forming"
