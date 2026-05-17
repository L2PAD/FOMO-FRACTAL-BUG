"""
Pre-Flight Quality Gate V1
Soft gate that flags risky setups and applies mild confidence penalty.
Pipeline order: base → interaction → ML overlay → preflight → final clamp.
"""


def compute_preflight_gate(
    *,
    confidence_before: float,
    confidence_target: float | None,
    degraded: bool,
    interaction_state: str | None,
    ml_risk_score: float | None,
    ml_live_applied: bool,
    config: dict,
) -> dict:
    enabled = config.get("PREFLIGHT_ENABLED", False)
    mode = config.get("PREFLIGHT_MODE", "shadow")

    if not enabled:
        return {
            "enabled": False, "triggered": False, "flag": None,
            "penalty": 0.0, "confidence_after": confidence_before,
            "rationale": [], "mode": mode, "live_applied": False,
        }

    threshold = config.get("PREFLIGHT_CONF_TARGET_THRESHOLD", 0.65)
    triggered = False
    rationale = []

    # Core trigger: confidence_target high AND degraded
    if confidence_target is not None and confidence_target >= threshold:
        rationale.append("confidence_target_high")
        if degraded:
            rationale.append("degraded_state")
            triggered = True

    # Optional ML reinforcement
    use_ml = config.get("PREFLIGHT_USE_ML", False)
    ml_thr = config.get("PREFLIGHT_ML_THRESHOLD", 0.75)
    if triggered and use_ml and ml_risk_score is not None:
        if ml_risk_score >= ml_thr:
            rationale.append("ml_risk_high")
        else:
            triggered = False
            rationale.append("ml_risk_not_confirmed")

    # Calculate penalty
    base_penalty = config.get("PREFLIGHT_BASE_PENALTY", 0.05)
    max_cap = config.get("PREFLIGHT_CAP", 0.10)
    penalty = 0.0

    if triggered:
        penalty = base_penalty

        # ML boost
        if ml_risk_score is not None and ml_risk_score >= 0.85:
            penalty = max(penalty, 0.08)
            rationale.append("ml_boost")

        # Interaction conflict
        if interaction_state == "conflict":
            penalty += 0.02
            rationale.append("interaction_conflict")

        # ML overlap control: reduce penalty if ML already applied
        if ml_live_applied:
            penalty *= 0.5
            rationale.append("ml_overlap_reduced")

        penalty = min(penalty, max_cap)

    # Apply only in live mode
    live_applied = mode == "live" and triggered
    if live_applied:
        confidence_after = max(0.0, confidence_before - penalty)
    else:
        confidence_after = confidence_before

    return {
        "enabled": True,
        "mode": mode,
        "triggered": triggered,
        "flag": "HIGH_RISK_PRECHECK" if triggered else None,
        "penalty": round(penalty, 4),
        "confidence_before": round(confidence_before, 4),
        "confidence_after": round(confidence_after, 4),
        "live_applied": live_applied,
        "rationale": rationale,
    }
