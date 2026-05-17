"""
Self-Improvement Scheduler — background jobs with jitter.

Jobs:
  1. Pattern Scan    — every 2h  — detect patterns from forecast_results
  2. Drift Check     — every 1h  — compute drift states
  3. Proposal Gen    — every 4h  — generate tuning proposals from patterns+drift
  4. Experiment Eval — every 6h  — evaluate running experiments

All jobs have random jitter sleep(random.uniform(0, 120)) before execution.
"""
import asyncio
import logging
import random
from datetime import datetime, timezone

logger = logging.getLogger("self_improvement.scheduler")

PATTERN_SCAN_INTERVAL = 7200    # 2h
DRIFT_CHECK_INTERVAL = 3600     # 1h
PROPOSAL_GEN_INTERVAL = 14400   # 4h
EXPERIMENT_EVAL_INTERVAL = 21600  # 6h
STARTUP_DELAY = 120  # let other services warm up
MAX_JITTER = 120     # seconds


def _get_db():
    from prediction.prediction_lab.db_helper import get_sync_db
    return get_sync_db()


async def _jittered_run(job_name: str, fn, *args):
    """Run a sync function with random jitter and error handling."""
    jitter = random.uniform(0, MAX_JITTER)
    await asyncio.sleep(jitter)
    try:
        result = fn(*args)
        logger.info(f"[{job_name}] Completed (jitter={jitter:.0f}s): {_summarize(result)}")
        return result
    except Exception as e:
        logger.error(f"[{job_name}] Failed: {e}")
        return None


def _summarize(result) -> str:
    if isinstance(result, list):
        return f"{len(result)} items"
    if isinstance(result, dict):
        return str({k: v for k, v in result.items() if k != "observations"})[:200]
    return str(result)[:100]


async def pattern_scan_loop():
    """Detect patterns every 2h."""
    await asyncio.sleep(STARTUP_DELAY)
    logger.info("[PatternScan] Started (2h interval)")

    while True:
        db = _get_db()
        if db is not None:
            from prediction.self_improvement.pattern_learning import detect_patterns
            findings = await _jittered_run("PatternScan", detect_patterns, db)
            if findings:
                _persist_patterns(db, findings)

        await asyncio.sleep(PATTERN_SCAN_INTERVAL)


def _persist_patterns(db, findings: list):
    """Save pattern findings to DB, deactivating stale ones."""
    now = datetime.now(timezone.utc).isoformat()

    # Deactivate old active patterns
    db.pattern_findings.update_many(
        {"active": True},
        {"$set": {"active": False, "deactivated_at": now}}
    )

    # Insert new findings as active
    for f in findings:
        f["active"] = True
        f["persisted_at"] = now

    if findings:
        db.pattern_findings.insert_many([dict(f) for f in findings])
        logger.info(f"[PatternScan] Persisted {len(findings)} patterns")


async def drift_check_loop():
    """Check drift every 1h."""
    await asyncio.sleep(STARTUP_DELAY + 30)
    logger.info("[DriftCheck] Started (1h interval)")

    while True:
        db = _get_db()
        if db is not None:
            from prediction.self_improvement.drift_monitor import detect_drift
            drift_states = await _jittered_run("DriftCheck", detect_drift, db)
            if drift_states:
                _persist_drift(db, drift_states)

        await asyncio.sleep(DRIFT_CHECK_INTERVAL)


def _persist_drift(db, drift_states: list):
    """Upsert drift states by drift_key."""
    now = datetime.now(timezone.utc).isoformat()
    for d in drift_states:
        d["updated_at"] = now
        db.drift_states.update_one(
            {"drift_key": d["drift_key"]},
            {"$set": d},
            upsert=True,
        )
    logger.info(f"[DriftCheck] Upserted {len(drift_states)} drift states")


async def proposal_gen_loop():
    """Generate proposals every 4h."""
    await asyncio.sleep(STARTUP_DELAY + 60)
    logger.info("[ProposalGen] Started (4h interval)")

    while True:
        db = _get_db()
        if db is not None:
            from prediction.self_improvement.proposal_engine import generate_proposals
            await _jittered_run("ProposalGen", generate_proposals, db)

        await asyncio.sleep(PROPOSAL_GEN_INTERVAL)


async def experiment_eval_loop():
    """Evaluate running experiments every 6h."""
    await asyncio.sleep(STARTUP_DELAY + 90)
    logger.info("[ExperimentEval] Started (6h interval)")

    while True:
        db = _get_db()
        if db is not None:
            from prediction.self_improvement.experiment_engine import evaluate_experiment
            running = list(db.experiment_results.find(
                {"status": "RUNNING"}, {"_id": 0, "experiment_id": 1}
            ))
            for exp in running:
                await _jittered_run("ExperimentEval", evaluate_experiment, db, exp["experiment_id"])

        await asyncio.sleep(EXPERIMENT_EVAL_INTERVAL)


async def start_self_improvement_scheduler():
    """Start all self-improvement background tasks. Called from server.py startup."""
    logger.info("[SelfImprovement] Starting scheduler (4 background jobs)")
    asyncio.create_task(pattern_scan_loop())
    asyncio.create_task(drift_check_loop())
    asyncio.create_task(proposal_gen_loop())
    asyncio.create_task(experiment_eval_loop())
