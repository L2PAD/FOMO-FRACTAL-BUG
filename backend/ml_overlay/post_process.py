"""
ML Risk Overlay: Post-Processing Hook
Runs after forecast generation, before insert.
Pipeline: base → interaction → ML overlay → preflight → final clamp.
"""
from ml_overlay.config import (
    ML_OVERLAY_ENABLED, ML_OVERLAY_KILL_SWITCH, ML_OVERLAY_RISK_THRESHOLD,
    ML_OVERLAY_CAP, ML_OVERLAY_MULT_HIGH, ML_OVERLAY_SALT, ML_OVERLAY_MODE,
    ML_OVERLAY_LIVE_PCT,
    PREFLIGHT_ENABLED, PREFLIGHT_MODE, PREFLIGHT_CONF_TARGET_THRESHOLD,
    PREFLIGHT_BASE_PENALTY, PREFLIGHT_CAP, PREFLIGHT_USE_ML, PREFLIGHT_ML_THRESHOLD,
    FINAL_CONFIDENCE_FLOOR,
    is_ml_live_eligible,
)
from ml_overlay.preflight_gate import compute_preflight_gate


def apply_ml_risk_layers(record_dict: dict) -> dict:
    """
    Apply ML overlay + preflight gate to a forecast record dict.
    Mutates audit and confidence. Returns the same dict.
    """
    audit = record_dict.setdefault("audit", {}) or {}
    record_dict["audit"] = audit
    forecast_id = record_dict.get("id", "")
    confidence = float(record_dict.get("confidence", 0))
    confidence_before_ml = confidence

    # ─── Step 1: ML Overlay ───
    ml_result = {"enabled": False, "mode": "disabled"}
    ml_live_applied = False
    ml_penalty = 0.0

    if ML_OVERLAY_ENABLED and not ML_OVERLAY_KILL_SWITCH:
        try:
            from ml_overlay.inference import infer_ml_overlay
            ml_data = infer_ml_overlay(record_dict)
            risk_score = ml_data["risk_score"]

            live_eligible = is_ml_live_eligible(forecast_id)

            # Live modulation: only for high-risk + eligible cohort
            if (live_eligible and
                risk_score >= ML_OVERLAY_RISK_THRESHOLD and
                ML_OVERLAY_MODE in ("shadow_plus_live", "live")):

                raw_penalty = confidence * ML_OVERLAY_MULT_HIGH
                ml_penalty = min(ML_OVERLAY_CAP, raw_penalty)
                confidence = max(0.0, confidence - ml_penalty)
                ml_live_applied = True

            ml_result = {
                "enabled": True,
                "mode": ML_OVERLAY_MODE,
                "risk_score": ml_data["risk_score"],
                "risk_bucket": ml_data["risk_bucket"],
                "would_reduce_confidence": ml_data["would_reduce_confidence"],
                "confidence_before_ml": round(confidence_before_ml, 4),
                "confidence_after_ml": round(confidence, 4),
                "live_eligible": live_eligible,
                "live_applied": ml_live_applied,
                "live_penalty": round(ml_penalty, 4),
                "threshold": ML_OVERLAY_RISK_THRESHOLD,
                "rollout_pct": ML_OVERLAY_LIVE_PCT,
            }
        except FileNotFoundError:
            ml_result = {"enabled": True, "mode": ML_OVERLAY_MODE, "error": "model_not_trained"}
        except Exception as e:
            ml_result = {"enabled": True, "mode": ML_OVERLAY_MODE, "error": str(e)[:100]}

    audit["ml"] = ml_result

    # ─── Step 2: Pre-Flight Gate ───
    confidence_before_preflight = confidence
    interaction = audit.get("interaction", {})

    preflight_config = {
        "PREFLIGHT_ENABLED": PREFLIGHT_ENABLED,
        "PREFLIGHT_MODE": PREFLIGHT_MODE,
        "PREFLIGHT_CONF_TARGET_THRESHOLD": PREFLIGHT_CONF_TARGET_THRESHOLD,
        "PREFLIGHT_BASE_PENALTY": PREFLIGHT_BASE_PENALTY,
        "PREFLIGHT_CAP": PREFLIGHT_CAP,
        "PREFLIGHT_USE_ML": PREFLIGHT_USE_ML,
        "PREFLIGHT_ML_THRESHOLD": PREFLIGHT_ML_THRESHOLD,
    }

    preflight = compute_preflight_gate(
        confidence_before=confidence_before_preflight,
        confidence_target=record_dict.get("confidenceTarget"),
        degraded=record_dict.get("degraded", False),
        interaction_state=interaction.get("state_group") or interaction.get("interaction_state"),
        ml_risk_score=ml_result.get("risk_score"),
        ml_live_applied=ml_live_applied,
        config=preflight_config,
    )

    if preflight.get("live_applied"):
        confidence = preflight["confidence_after"]

    audit["preflight"] = preflight

    # ─── Step 3: Global Confidence Floor ───
    confidence = max(FINAL_CONFIDENCE_FLOOR, confidence)
    confidence = round(confidence, 4)

    # Write back
    record_dict["confidence"] = confidence
    audit["confidence_pipeline"] = {
        "base": round(confidence_before_ml, 4),
        "after_ml": round(ml_result.get("confidence_after_ml", confidence_before_ml), 4),
        "after_preflight": round(preflight.get("confidence_after", confidence_before_ml), 4),
        "final": confidence,
        "floor_applied": confidence == FINAL_CONFIDENCE_FLOOR,
    }
    record_dict["audit"] = audit

    return record_dict
