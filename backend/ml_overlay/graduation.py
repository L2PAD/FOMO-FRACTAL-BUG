"""
Overlay Graduation System — managed ML influence stages.

Stages: SHADOW (0.0) -> LIVE_LITE (0.5) -> LIVE_MED (0.75) -> LIVE_FULL (1.0)
effectiveAlpha = mlAlpha * mlWeight (drift-based)

Auto-promote/demote based on shadow verdict, drift, calibration.
"""

import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

STAGES = [
    {"name": "SHADOW", "mlAlpha": 0.0},
    {"name": "LIVE_LITE", "mlAlpha": 0.5},
    {"name": "LIVE_MED", "mlAlpha": 0.75},
    {"name": "LIVE_FULL", "mlAlpha": 1.0},
]

STAGE_INDEX = {s["name"]: i for i, s in enumerate(STAGES)}

# Promote requires these thresholds
PROMOTE_CRITERIA = {
    "verdict_required": "SHADOW_OK",
    "consecutive_ok": 2,
    "drift_max": 0.55,
    "flip_delta_max": 3.0,
    "dir_hit_delta_min": -0.5,
    "mae_ratio_max": 0.97,
}

# Demote triggers
DEMOTE_TRIGGERS = {
    "verdict_fail": "SHADOW_FAIL",
    "drift_high": 0.70,
    "drift_critical": 0.85,
    "calibration_fail": "DRIFT",  # ECE status that triggers demotion
}

# Cooldown: minimum days between stage changes
PROMOTE_COOLDOWN_DAYS = 3


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _col():
    return _db()["ml_overlay_state"]


def _audit_col():
    return _db()["ml_overlay_audit"]


def get_current_stage(horizon: str = "7D", asset: str = "BTC") -> dict:
    """Get current graduation stage."""
    doc = _col().find_one(
        {"horizon": horizon, "asset": asset},
        {"_id": 0},
    )
    if not doc:
        return {
            "horizon": horizon,
            "asset": asset,
            "stage": "SHADOW",
            "mlAlpha": 0.0,
            "updatedAt": None,
            "reason": "initial",
            "lockedUntil": None,
        }
    return doc


def get_effective_alpha(horizon: str = "7D", asset: str = "BTC") -> dict:
    """
    Compute effectiveAlpha = mlAlpha * mlWeight.
    Returns full context for UI display.
    """
    state = get_current_stage(horizon, asset)
    ml_alpha = state["mlAlpha"]

    # Get drift weight
    ml_weight = 1.0
    try:
        from drift.service import get_current_ml_weight
        ml_weight = get_current_ml_weight(horizon=horizon, asset=asset)
    except Exception:
        pass

    effective = round(ml_alpha * ml_weight, 4)

    stage_idx = STAGE_INDEX.get(state["stage"], 0)

    return {
        "horizon": horizon,
        "asset": asset,
        "stage": state["stage"],
        "mlAlpha": ml_alpha,
        "mlWeight": round(ml_weight, 4),
        "effectiveAlpha": effective,
        "stageIndex": stage_idx,
        "maxStages": len(STAGES),
        "updatedAt": state.get("updatedAt"),
        "reason": state.get("reason", ""),
        "lockedUntil": state.get("lockedUntil"),
    }


def _log_audit(horizon, asset, action, from_stage, to_stage, reason, details=None):
    """Write audit log for stage transitions."""
    _audit_col().insert_one({
        "horizon": horizon,
        "asset": asset,
        "action": action,
        "fromStage": from_stage,
        "toStage": to_stage,
        "reason": reason,
        "details": details or {},
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
    })


def _set_stage(horizon, asset, new_stage, reason, cooldown_days=PROMOTE_COOLDOWN_DAYS):
    """Persist new stage to MongoDB."""
    now = datetime.now(timezone.utc)
    locked_until = int((now + timedelta(days=cooldown_days)).timestamp() * 1000)

    _col().update_one(
        {"horizon": horizon, "asset": asset},
        {"$set": {
            "horizon": horizon,
            "asset": asset,
            "stage": new_stage,
            "mlAlpha": STAGES[STAGE_INDEX[new_stage]]["mlAlpha"],
            "updatedAt": int(now.timestamp() * 1000),
            "reason": reason,
            "lockedUntil": locked_until,
        }},
        upsert=True,
    )


def evaluate_graduation(horizon: str = "7D", asset: str = "BTC") -> dict:
    """
    Evaluate whether to promote, demote, or hold current stage.
    Called daily from scheduler after SHADOW_EVAL.
    """
    state = get_current_stage(horizon, asset)
    current = state["stage"]
    current_idx = STAGE_INDEX.get(current, 0)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    # Check cooldown
    locked_until = state.get("lockedUntil")
    if locked_until and now_ms < locked_until:
        return {
            "action": "HOLD",
            "stage": current,
            "reason": "cooldown_active",
            "lockedUntil": locked_until,
        }

    # Gather signals
    db = _db()

    # 1. Shadow verdict
    verdict_doc = None
    try:
        from ml_overlay.eval_shadow import compute_rolling_verdict
        verdict_doc = compute_rolling_verdict(horizon, 30, asset)
    except Exception:
        pass

    verdict = verdict_doc.get("verdict", "INSUFFICIENT_DATA") if verdict_doc else "INSUFFICIENT_DATA"

    # 2. Drift score
    drift_score = 0.0
    drift_doc = db["drift_snapshots"].find_one(
        {"horizon": horizon, "asset": asset},
        {"_id": 0, "driftScore": 1, "calibration": 1},
        sort=[("ts", DESCENDING)],
    )
    if drift_doc:
        drift_score = drift_doc.get("driftScore", 0)

    # 2b. Calibration status from latest drift snapshot
    calib_status = "OK"
    calib_ece = 0.0
    if drift_doc and drift_doc.get("calibration"):
        calib = drift_doc["calibration"]
        calib_status = calib.get("status", "OK")
        calib_ece = calib.get("ece", 0)

    # 3. Check for CRITICAL -> force SHADOW
    if drift_score > DEMOTE_TRIGGERS["drift_critical"]:
        if current != "SHADOW":
            _set_stage(horizon, asset, "SHADOW", f"CRITICAL: drift={drift_score:.3f}", cooldown_days=1)
            _log_audit(horizon, asset, "FORCE_SHADOW", current, "SHADOW",
                       f"Critical drift {drift_score:.3f} > {DEMOTE_TRIGGERS['drift_critical']}")
            return {
                "action": "FORCE_SHADOW",
                "stage": "SHADOW",
                "reason": f"Critical drift {drift_score:.3f}",
                "fromStage": current,
            }

    # 4. Check for DEMOTE
    should_demote = False
    demote_reason = ""

    if verdict == DEMOTE_TRIGGERS["verdict_fail"]:
        should_demote = True
        demote_reason = f"verdict={verdict}"
    elif drift_score > DEMOTE_TRIGGERS["drift_high"]:
        should_demote = True
        demote_reason = f"drift={drift_score:.3f}"
    elif calib_status == DEMOTE_TRIGGERS["calibration_fail"]:
        should_demote = True
        demote_reason = f"calibration={calib_status} ECE={calib_ece:.4f}"

    if should_demote and current_idx > 0:
        new_idx = current_idx - 1
        new_stage = STAGES[new_idx]["name"]
        _set_stage(horizon, asset, new_stage, f"DEMOTE: {demote_reason}", cooldown_days=2)
        _log_audit(horizon, asset, "DEMOTE", current, new_stage, demote_reason)
        return {
            "action": "DEMOTE",
            "stage": new_stage,
            "reason": demote_reason,
            "fromStage": current,
        }

    # 5. Check for PROMOTE
    if current_idx < len(STAGES) - 1:
        can_promote = True
        promote_blockers = []

        if verdict != PROMOTE_CRITERIA["verdict_required"]:
            can_promote = False
            promote_blockers.append(f"verdict={verdict} (need {PROMOTE_CRITERIA['verdict_required']})")

        if drift_score > PROMOTE_CRITERIA["drift_max"]:
            can_promote = False
            promote_blockers.append(f"drift={drift_score:.3f} > {PROMOTE_CRITERIA['drift_max']}")

        if calib_status in ("DRIFT", "WATCH"):
            can_promote = False
            promote_blockers.append(f"calibration={calib_status} ECE={calib_ece:.4f}")

        # Check consecutive OK verdicts from audit log
        if can_promote:
            recent_audits = list(_audit_col().find(
                {"horizon": horizon, "asset": asset},
                {"_id": 0},
            ).sort("ts", DESCENDING).limit(5))

            # Count consecutive days with OK conditions (simplified: check if last decision was also a HOLD/PROMOTE with OK)
            consecutive_ok = 1  # current check passes
            for a in recent_audits:
                if a.get("action") in ("HOLD", "PROMOTE") and "verdict=SHADOW_OK" in a.get("reason", ""):
                    consecutive_ok += 1
                else:
                    break

            if consecutive_ok < PROMOTE_CRITERIA["consecutive_ok"]:
                can_promote = False
                promote_blockers.append(f"consecutive_ok={consecutive_ok} (need {PROMOTE_CRITERIA['consecutive_ok']})")

        if can_promote:
            new_idx = current_idx + 1
            new_stage = STAGES[new_idx]["name"]
            _set_stage(horizon, asset, new_stage, f"PROMOTE: verdict={verdict} drift={drift_score:.3f}")
            _log_audit(horizon, asset, "PROMOTE", current, new_stage,
                       f"verdict={verdict} drift={drift_score:.3f}")
            return {
                "action": "PROMOTE",
                "stage": new_stage,
                "reason": f"All criteria met (verdict={verdict}, drift={drift_score:.3f})",
                "fromStage": current,
            }
        else:
            # Log HOLD with context
            _log_audit(horizon, asset, "HOLD", current, current,
                       f"verdict={verdict} drift={drift_score:.3f} blockers={promote_blockers}")
            return {
                "action": "HOLD",
                "stage": current,
                "reason": f"Blockers: {'; '.join(promote_blockers)}" if promote_blockers else "stable",
                "canPromote": False,
                "blockers": promote_blockers,
            }

    # At max stage, just hold
    _log_audit(horizon, asset, "HOLD", current, current,
               f"MAX_STAGE verdict={verdict} drift={drift_score:.3f}")
    return {
        "action": "HOLD",
        "stage": current,
        "reason": "at_max_stage",
    }


def get_audit_history(horizon: str = "7D", asset: str = "BTC", limit: int = 20) -> list:
    """Get recent graduation audit log."""
    docs = list(_audit_col().find(
        {"horizon": horizon, "asset": asset},
        {"_id": 0},
    ).sort("ts", DESCENDING).limit(limit))
    return docs
