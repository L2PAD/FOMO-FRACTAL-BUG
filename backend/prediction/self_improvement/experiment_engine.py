"""
Experiment Engine — A/B testing for tuning proposals.

Implements 70% control / 30% treatment split.
State flow: APPROVED proposal → EXPERIMENT (running) → ACTIVE or REVERTED.
Tracks control vs treatment metrics over experiment duration.
"""
import logging
import uuid
import hashlib
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("self_improvement.experiment_engine")

CONTROL_RATIO = 0.70
TREATMENT_RATIO = 0.30
MIN_EXPERIMENT_DURATION_HOURS = 48
MIN_EXPERIMENT_SAMPLES = 20


def start_experiment(db, proposal: dict) -> dict:
    """Start an A/B experiment from an approved proposal."""
    if proposal.get("status") != "APPROVED":
        return {"ok": False, "error": "Proposal must be APPROVED to start experiment"}

    # Check no active experiment for same param
    existing = db.experiment_results.find_one({
        "param_key": proposal["param_key"],
        "status": "RUNNING"
    })
    if existing:
        return {"ok": False, "error": f"Active experiment already exists for {proposal['param_key']}"}

    now = datetime.now(timezone.utc).isoformat()
    experiment = {
        "experiment_id": f"exp_{uuid.uuid4().hex[:12]}",
        "proposal_id": proposal["proposal_id"],
        "param_key": proposal["param_key"],
        "control_value": proposal["current_value"],
        "treatment_value": proposal["proposed_value"],
        "split": {"control": CONTROL_RATIO, "treatment": TREATMENT_RATIO},
        "status": "RUNNING",
        "started_at": now,
        "ended_at": None,
        "min_end_at": (datetime.now(timezone.utc) + timedelta(hours=MIN_EXPERIMENT_DURATION_HOURS)).isoformat(),
        "control_metrics": {"accuracy": None, "brier": None, "sample_size": 0},
        "treatment_metrics": {"accuracy": None, "brier": None, "sample_size": 0},
        "winner": None,
    }

    db.experiment_results.insert_one(dict(experiment))

    # Update proposal status
    db.tuning_proposals.update_one(
        {"proposal_id": proposal["proposal_id"]},
        {"$set": {"status": "EXPERIMENT"}}
    )

    logger.info(f"[Experiment] Started {experiment['experiment_id']} for {proposal['param_key']}")
    return {"ok": True, "experiment": experiment}


def get_experiment_group(experiment_id: str, event_id: str) -> str:
    """Deterministic assignment: hash(experiment_id + event_id) → control/treatment."""
    h = hashlib.sha256(f"{experiment_id}:{event_id}".encode()).hexdigest()
    val = int(h[:8], 16) / 0xFFFFFFFF
    return "treatment" if val < TREATMENT_RATIO else "control"


def record_experiment_observation(db, experiment_id: str, event_id: str,
                                  binary_correct: bool, brier_score: float = None):
    """Record an observation for a running experiment."""
    experiment = db.experiment_results.find_one(
        {"experiment_id": experiment_id, "status": "RUNNING"}
    )
    if not experiment:
        return

    group = get_experiment_group(experiment_id, event_id)
    metrics_key = f"{group}_metrics"

    db.experiment_results.update_one(
        {"experiment_id": experiment_id},
        {
            "$inc": {f"{metrics_key}.sample_size": 1},
            "$push": {
                f"{metrics_key}.observations": {
                    "event_id": event_id,
                    "correct": binary_correct,
                    "brier": brier_score,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        }
    )


def evaluate_experiment(db, experiment_id: str) -> dict:
    """Evaluate an experiment's results and determine winner."""
    experiment = db.experiment_results.find_one(
        {"experiment_id": experiment_id},
        {"_id": 0}
    )
    if not experiment:
        return {"ok": False, "error": "Experiment not found"}

    if experiment["status"] != "RUNNING":
        return {"ok": False, "error": f"Experiment status is {experiment['status']}"}

    now = datetime.now(timezone.utc)
    min_end = datetime.fromisoformat(experiment["min_end_at"])
    if now < min_end:
        remaining = (min_end - now).total_seconds() / 3600
        return {"ok": False, "error": f"Min duration not reached. {remaining:.1f}h remaining"}

    control = experiment.get("control_metrics", {})
    treatment = experiment.get("treatment_metrics", {})

    c_samples = control.get("sample_size", 0)
    t_samples = treatment.get("sample_size", 0)

    if c_samples < MIN_EXPERIMENT_SAMPLES or t_samples < MIN_EXPERIMENT_SAMPLES:
        return {
            "ok": False,
            "error": f"Insufficient samples: control={c_samples}, treatment={t_samples}, min={MIN_EXPERIMENT_SAMPLES}"
        }

    # Compute accuracies from observations
    c_obs = control.get("observations", [])
    t_obs = treatment.get("observations", [])

    c_accuracy = sum(1 for o in c_obs if o.get("correct")) / len(c_obs) if c_obs else 0
    t_accuracy = sum(1 for o in t_obs if o.get("correct")) / len(t_obs) if t_obs else 0

    c_brier_vals = [o["brier"] for o in c_obs if o.get("brier") is not None]
    t_brier_vals = [o["brier"] for o in t_obs if o.get("brier") is not None]
    c_brier = sum(c_brier_vals) / len(c_brier_vals) if c_brier_vals else None
    t_brier = sum(t_brier_vals) / len(t_brier_vals) if t_brier_vals else None

    # Determine winner: treatment must be strictly better
    treatment_wins = t_accuracy > c_accuracy + 0.02  # Need 2% improvement to win

    winner = "TREATMENT" if treatment_wins else "CONTROL"

    now_iso = now.isoformat()
    db.experiment_results.update_one(
        {"experiment_id": experiment_id},
        {"$set": {
            "status": "COMPLETED",
            "ended_at": now_iso,
            "winner": winner,
            "control_metrics.accuracy": round(c_accuracy, 4),
            "control_metrics.brier": round(c_brier, 4) if c_brier else None,
            "treatment_metrics.accuracy": round(t_accuracy, 4),
            "treatment_metrics.brier": round(t_brier, 4) if t_brier else None,
        }}
    )

    # If treatment wins → promote to ACTIVE
    if winner == "TREATMENT":
        _promote_param(db, experiment)
    else:
        _revert_proposal(db, experiment)

    logger.info(f"[Experiment] {experiment_id} completed. Winner: {winner}")
    return {
        "ok": True,
        "experiment_id": experiment_id,
        "winner": winner,
        "control_accuracy": round(c_accuracy, 4),
        "treatment_accuracy": round(t_accuracy, 4),
    }


def _promote_param(db, experiment: dict):
    """Promote treatment value to active params."""
    now_iso = datetime.now(timezone.utc).isoformat()

    db.active_model_params.update_one(
        {"param_key": experiment["param_key"]},
        {"$set": {
            "param_key": experiment["param_key"],
            "value": experiment["treatment_value"],
            "source": "tuned",
            "updated_at": now_iso,
            "experiment_id": experiment["experiment_id"],
        }},
        upsert=True,
    )

    db.tuning_proposals.update_one(
        {"proposal_id": experiment["proposal_id"]},
        {"$set": {"status": "ACTIVE"}}
    )

    logger.info(f"[Experiment] Promoted {experiment['param_key']} = {experiment['treatment_value']}")


def _revert_proposal(db, experiment: dict):
    """Revert proposal: treatment didn't win."""
    db.tuning_proposals.update_one(
        {"proposal_id": experiment["proposal_id"]},
        {"$set": {"status": "REVERTED"}}
    )
    logger.info(f"[Experiment] Reverted proposal {experiment['proposal_id']} — control was better")


def get_experiments(db, status: str = None, limit: int = 50) -> list[dict]:
    """List experiments."""
    query = {}
    if status:
        query["status"] = status
    results = list(db.experiment_results.find(
        query, {"_id": 0, "control_metrics.observations": 0, "treatment_metrics.observations": 0}
    ).sort("started_at", -1).limit(limit))
    return results
