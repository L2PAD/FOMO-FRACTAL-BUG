"""
Self-Improvement API Routes.

GET  /api/self-improvement/overview     — Full self-improvement dashboard
GET  /api/self-improvement/patterns     — Active pattern findings
GET  /api/self-improvement/drift        — Drift states
GET  /api/self-improvement/params       — Active model parameters
GET  /api/self-improvement/proposals    — Tuning proposals
GET  /api/self-improvement/experiments  — A/B experiments
POST /api/self-improvement/scan         — Trigger manual pattern scan + drift check
POST /api/self-improvement/propose      — Trigger manual proposal generation
POST /api/self-improvement/approve      — Approve a proposal → start experiment
POST /api/self-improvement/reject       — Reject a proposal
POST /api/self-improvement/evaluate     — Evaluate a running experiment
POST /api/self-improvement/seed-defaults — Seed default parameter values
"""
import logging
from fastapi import APIRouter, Query, Body

from prediction.self_improvement.parameter_registry import (
    get_all_params,
    TUNABLE_PARAMS,
)

logger = logging.getLogger("self_improvement.routes")

router = APIRouter(prefix="/api/self-improvement", tags=["self-improvement"])


def _get_db():
    from prediction.prediction_lab.db_helper import get_sync_db
    return get_sync_db()


@router.get("/overview")
def si_overview():
    """Full self-improvement dashboard data."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}

    patterns = list(db.pattern_findings.find({"active": True}, {"_id": 0}).limit(20))
    drift_states = list(db.drift_states.find({}, {"_id": 0}).sort("detected_at", -1).limit(30))
    active_params = list(db.active_model_params.find({}, {"_id": 0}))
    proposals = list(db.tuning_proposals.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(20))
    experiments = list(db.experiment_results.find(
        {}, {"_id": 0, "control_metrics.observations": 0, "treatment_metrics.observations": 0}
    ).sort("started_at", -1).limit(10))

    # Summary stats
    total_patterns = db.pattern_findings.count_documents({"active": True})
    degrading_count = db.drift_states.count_documents({"status": "DEGRADING"})
    pending_proposals = db.tuning_proposals.count_documents({"status": "SUGGESTED"})
    running_experiments = db.experiment_results.count_documents({"status": "RUNNING"})

    return {
        "ok": True,
        "summary": {
            "active_patterns": total_patterns,
            "degrading_metrics": degrading_count,
            "pending_proposals": pending_proposals,
            "running_experiments": running_experiments,
            "tunable_params_count": len(TUNABLE_PARAMS),
            "active_params_count": len(active_params),
        },
        "patterns": patterns,
        "drift_states": drift_states,
        "active_params": active_params,
        "proposals": proposals,
        "experiments": experiments,
    }


@router.get("/patterns")
def si_patterns():
    """Get active pattern findings."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    patterns = list(db.pattern_findings.find({"active": True}, {"_id": 0}).limit(20))
    history = list(db.pattern_findings.find(
        {"active": False}, {"_id": 0}
    ).sort("deactivated_at", -1).limit(30))
    return {"ok": True, "active": patterns, "history": history}


@router.get("/drift")
def si_drift():
    """Get drift states."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    states = list(db.drift_states.find({}, {"_id": 0}).sort("detected_at", -1))
    degrading = [s for s in states if s.get("status") == "DEGRADING"]
    return {"ok": True, "states": states, "degrading_count": len(degrading)}


@router.get("/params")
def si_params():
    """Get active model parameters and their specs."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    active = list(db.active_model_params.find({}, {"_id": 0}))
    specs = get_all_params()
    return {"ok": True, "active": active, "specs": specs}


@router.get("/proposals")
def si_proposals(status: str = Query(None)):
    """Get tuning proposals."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    from prediction.self_improvement.proposal_engine import get_proposals
    proposals = get_proposals(db, status=status)
    return {"ok": True, "proposals": proposals}


@router.get("/experiments")
def si_experiments(status: str = Query(None)):
    """Get A/B experiments."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    from prediction.self_improvement.experiment_engine import get_experiments
    experiments = get_experiments(db, status=status)
    return {"ok": True, "experiments": experiments}


@router.post("/scan")
def si_manual_scan():
    """Manually trigger pattern scan + drift check."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}

    from prediction.self_improvement.pattern_learning import detect_patterns
    from prediction.self_improvement.drift_monitor import detect_drift
    from datetime import datetime, timezone

    patterns = detect_patterns(db)
    drift_states = detect_drift(db)

    # Persist patterns
    now = datetime.now(timezone.utc).isoformat()
    if patterns:
        db.pattern_findings.update_many(
            {"active": True},
            {"$set": {"active": False, "deactivated_at": now}}
        )
        for p in patterns:
            p["active"] = True
            p["persisted_at"] = now
        db.pattern_findings.insert_many([dict(p) for p in patterns])

    # Persist drift states
    if drift_states:
        for d in drift_states:
            d["updated_at"] = now
            db.drift_states.update_one(
                {"drift_key": d["drift_key"]},
                {"$set": d},
                upsert=True,
            )

    return {
        "ok": True,
        "patterns_found": len(patterns),
        "drift_states_updated": len(drift_states),
    }


@router.post("/propose")
def si_manual_propose():
    """Manually trigger proposal generation."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}

    from prediction.self_improvement.proposal_engine import generate_proposals
    proposals = generate_proposals(db)
    suggested = [p for p in proposals if p.get("status") == "SUGGESTED"]
    rejected = [p for p in proposals if p.get("status") == "REJECTED_BY_GOVERNANCE"]
    return {
        "ok": True,
        "total_generated": len(proposals),
        "suggested": len(suggested),
        "rejected_by_governance": len(rejected),
        "proposals": proposals,
    }


@router.post("/approve")
def si_approve_proposal(proposal_id: str = Body(..., embed=True)):
    """Approve a proposal and start an experiment."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}

    proposal = db.tuning_proposals.find_one(
        {"proposal_id": proposal_id}, {"_id": 0}
    )
    if not proposal:
        return {"ok": False, "error": "Proposal not found"}
    if proposal.get("status") != "SUGGESTED":
        return {"ok": False, "error": f"Proposal status is {proposal['status']}, must be SUGGESTED"}

    # Update to APPROVED
    db.tuning_proposals.update_one(
        {"proposal_id": proposal_id},
        {"$set": {"status": "APPROVED"}}
    )
    proposal["status"] = "APPROVED"

    # Start experiment
    from prediction.self_improvement.experiment_engine import start_experiment
    result = start_experiment(db, proposal)

    # Record decision
    from datetime import datetime, timezone
    db.tuning_decisions.insert_one({
        "proposal_id": proposal_id,
        "action": "APPROVE",
        "reason": "Manual approval",
        "decided_at": datetime.now(timezone.utc).isoformat(),
    })

    return result


@router.post("/reject")
def si_reject_proposal(
    proposal_id: str = Body(...),
    reason: str = Body("Manual rejection"),
):
    """Reject a proposal."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}

    proposal = db.tuning_proposals.find_one(
        {"proposal_id": proposal_id}, {"_id": 0}
    )
    if not proposal:
        return {"ok": False, "error": "Proposal not found"}
    if proposal.get("status") != "SUGGESTED":
        return {"ok": False, "error": f"Proposal status is {proposal['status']}, must be SUGGESTED"}

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    db.tuning_proposals.update_one(
        {"proposal_id": proposal_id},
        {"$set": {"status": "REJECTED", "rejected_at": now, "rejection_reason": reason}}
    )

    db.tuning_decisions.insert_one({
        "proposal_id": proposal_id,
        "action": "REJECT",
        "reason": reason,
        "decided_at": now,
    })

    return {"ok": True, "proposal_id": proposal_id, "status": "REJECTED"}


@router.post("/evaluate")
def si_evaluate_experiment(experiment_id: str = Body(..., embed=True)):
    """Manually evaluate a running experiment."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}

    from prediction.self_improvement.experiment_engine import evaluate_experiment
    return evaluate_experiment(db, experiment_id)


@router.post("/seed-defaults")
def si_seed_defaults():
    """Seed default parameter values into active_model_params."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    defaults = {
        "fair_prob.time_decay_weight": 0.15,
        "fair_prob.liquidity_weight": 0.10,
        "fair_prob.structure_weight": 0.15,
        "fair_prob.volatility_weight": 0.10,
        "confidence.buy_now_threshold": 0.65,
        "confidence.buy_threshold": 0.55,
        "sizing.low_liquidity_cap": 0.50,
        "sizing.short_expiry_cap": 0.60,
        "sizing.high_volatility_cap": 0.50,
    }

    seeded = 0
    for key, value in defaults.items():
        existing = db.active_model_params.find_one({"param_key": key})
        if not existing:
            db.active_model_params.insert_one({
                "param_key": key,
                "value": value,
                "source": "default",
                "updated_at": now,
                "experiment_id": None,
            })
            seeded += 1

    return {"ok": True, "seeded": seeded, "total": len(defaults)}



@router.post("/simulate")
def si_simulate(scenarios: list[str] = Body(None)):
    """Run synthetic scenario simulation to test self-improvement cycle."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}

    from prediction.self_improvement.synthetic_scenarios import generate_scenarios
    result = generate_scenarios(db, scenarios=scenarios)
    return {"ok": True, **result}


@router.post("/simulate/clear")
def si_simulate_clear():
    """Clear all synthetic forecast_results."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}

    from prediction.self_improvement.synthetic_scenarios import clear_synthetic
    result = clear_synthetic(db)
    return {"ok": True, **result}


@router.post("/simulate/full-cycle")
def si_full_cycle():
    """Run full self-improvement cycle: simulate → scan → propose."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}

    # Step 1: Generate synthetic data
    from prediction.self_improvement.synthetic_scenarios import generate_scenarios
    sim_result = generate_scenarios(db)

    # Step 2: Seed defaults if needed
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    defaults_seeded = 0
    defaults = {
        "fair_prob.time_decay_weight": 0.15,
        "fair_prob.liquidity_weight": 0.10,
        "fair_prob.structure_weight": 0.15,
        "fair_prob.volatility_weight": 0.10,
        "confidence.buy_now_threshold": 0.65,
        "confidence.buy_threshold": 0.55,
        "sizing.low_liquidity_cap": 0.50,
        "sizing.short_expiry_cap": 0.60,
        "sizing.high_volatility_cap": 0.50,
    }
    for key, value in defaults.items():
        existing = db.active_model_params.find_one({"param_key": key})
        if not existing:
            db.active_model_params.insert_one({
                "param_key": key, "value": value, "source": "default",
                "updated_at": now, "experiment_id": None,
            })
            defaults_seeded += 1

    # Step 3: Run pattern scan + drift check
    from prediction.self_improvement.pattern_learning import detect_patterns
    from prediction.self_improvement.drift_monitor import detect_drift

    patterns = detect_patterns(db)
    drift_states = detect_drift(db)

    # Persist patterns
    if patterns:
        db.pattern_findings.update_many(
            {"active": True}, {"$set": {"active": False, "deactivated_at": now}}
        )
        for p in patterns:
            p["active"] = True
            p["persisted_at"] = now
        db.pattern_findings.insert_many([dict(p) for p in patterns])

    # Persist drift
    if drift_states:
        for d in drift_states:
            d["updated_at"] = now
            db.drift_states.update_one(
                {"drift_key": d["drift_key"]}, {"$set": d}, upsert=True,
            )

    # Step 4: Generate proposals
    from prediction.self_improvement.proposal_engine import generate_proposals
    proposals = generate_proposals(db)
    suggested = [p for p in proposals if p.get("status") == "SUGGESTED"]

    return {
        "ok": True,
        "cycle": {
            "synthetic_records": sim_result["total_generated"],
            "defaults_seeded": defaults_seeded,
            "patterns_found": len(patterns),
            "drift_states": len(drift_states),
            "proposals_generated": len(proposals),
            "proposals_suggested": len(suggested),
        },
        "patterns": patterns,
        "drift_states": drift_states,
        "proposals": proposals,
    }
