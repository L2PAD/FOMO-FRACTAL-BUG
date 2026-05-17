"""
Engine Memory Service — Market Memory Layer
=============================================
Tracks setup outcomes and calculates historical statistics.
Rule-based, no ML. Pure statistical aggregation.

Collections:
  - engine_setup_outcomes: individual setup detection + outcome records
"""

import os
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
        _db = _client[os.environ.get("DB_NAME", "test_database")]
    return _db


def record_setup_detection(engine_data: dict):
    """Record when a setup reaches 'confirmed' or 'active' status."""
    db = _get_db()
    setup = engine_data.get("setup_engine", {}).get("primary", {})
    setup_type = setup.get("type", "mixed")
    status = setup.get("status", "weak")

    if status not in ("confirmed", "active"):
        return  # Only track significant setups

    # Check if this exact setup+status combo is already being tracked
    existing = db["engine_setup_outcomes"].find_one(
        {"setup": setup_type, "status": status, "result": None},
        {"_id": 1},
    )
    if existing:
        return  # Already tracking this

    regime = engine_data.get("regime_engine", {}).get("primary", {})
    prob = engine_data.get("probability_layer", {})
    scores = engine_data.get("scores", {})

    doc = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "setup": setup_type,
        "status": status,
        "regime": regime.get("type", "neutral_chop"),
        "probability_at_detection": prob.get("continuation", 0),
        "confidence_at_detection": setup.get("confidence", 0),
        "composite_at_detection": scores.get("composite", 50),
        "result": None,  # To be filled when outcome is determined
        "result_timestamp": None,
        "duration_minutes": None,
    }

    db["engine_setup_outcomes"].insert_one(doc)


def record_setup_outcome(setup_type: str, result: str):
    """
    Record the outcome of a tracked setup.
    result: 'success' | 'failure' | 'expired'
    """
    db = _get_db()
    now = datetime.now(timezone.utc)

    # Find the most recent unresolved entry for this setup
    entry = db["engine_setup_outcomes"].find_one(
        {"setup": setup_type, "result": None},
        sort=[("timestamp", DESCENDING)],
    )

    if not entry:
        return

    detection_time = datetime.fromisoformat(entry["timestamp"])
    if detection_time.tzinfo is None:
        detection_time = detection_time.replace(tzinfo=timezone.utc)
    duration_min = round((now - detection_time).total_seconds() / 60)

    db["engine_setup_outcomes"].update_one(
        {"_id": entry["_id"]},
        {"$set": {
            "result": result,
            "result_timestamp": now.isoformat(),
            "duration_minutes": duration_min,
        }},
    )


def check_and_resolve_outcomes(engine_data: dict):
    """
    Check if tracked setups have resolved.
    Called during snapshot building.
    """
    db = _get_db()
    setup = engine_data.get("setup_engine", {}).get("primary", {})
    current_type = setup.get("type", "mixed")
    current_status = setup.get("status", "weak")

    # Find unresolved outcomes
    open_outcomes = list(db["engine_setup_outcomes"].find(
        {"result": None}, {"_id": 0, "setup": 1}
    ))

    for oo in open_outcomes:
        tracked_type = oo.get("setup")
        if tracked_type != current_type:
            # Setup changed — the old one either succeeded or failed
            # Check if the new setup is a natural successor or a failure
            if current_status in ("confirmed", "active"):
                record_setup_outcome(tracked_type, "expired")
            else:
                record_setup_outcome(tracked_type, "failure")


def calculate_setup_statistics(setup_type: str = None) -> dict:
    """
    Calculate historical statistics for a setup type.
    If setup_type is None, calculates for all types.
    """
    db = _get_db()

    query = {"result": {"$ne": None}}
    if setup_type:
        query["setup"] = setup_type

    outcomes = list(db["engine_setup_outcomes"].find(query, {"_id": 0}))

    if not outcomes:
        return {
            "setup": setup_type or "all",
            "sample_size": 0,
            "success_rate": 0,
            "avg_duration_minutes": 0,
            "by_regime": {},
        }

    total = len(outcomes)
    successes = sum(1 for o in outcomes if o.get("result") == "success")
    failures = sum(1 for o in outcomes if o.get("result") == "failure")
    durations = [o.get("duration_minutes", 0) for o in outcomes if o.get("duration_minutes")]

    success_rate = round(successes / total, 3) if total > 0 else 0
    avg_duration = round(sum(durations) / len(durations)) if durations else 0

    # Group by regime
    by_regime = {}
    for o in outcomes:
        r = o.get("regime", "unknown")
        if r not in by_regime:
            by_regime[r] = {"total": 0, "success": 0}
        by_regime[r]["total"] += 1
        if o.get("result") == "success":
            by_regime[r]["success"] += 1

    for r in by_regime:
        by_regime[r]["success_rate"] = round(
            by_regime[r]["success"] / by_regime[r]["total"], 3
        ) if by_regime[r]["total"] > 0 else 0

    return {
        "setup": setup_type or "all",
        "sample_size": total,
        "success_rate": success_rate,
        "failure_rate": round(failures / total, 3) if total > 0 else 0,
        "avg_duration_minutes": avg_duration,
        "by_regime": by_regime,
    }


def get_memory_for_engine(engine_data: dict) -> dict:
    """
    Get memory statistics relevant to the current engine state.
    Returns stats for the current setup type.
    """
    setup = engine_data.get("setup_engine", {}).get("primary", {})
    setup_type = setup.get("type", "mixed")

    stats = calculate_setup_statistics(setup_type)

    # Format for display
    avg_dur = stats.get("avg_duration_minutes", 0)
    if avg_dur > 0:
        if avg_dur < 60:
            duration_str = f"{avg_dur}m"
        else:
            duration_str = f"{round(avg_dur / 60, 1)}h"
    else:
        duration_str = "—"

    return {
        "setup": setup_type,
        "sample_size": stats.get("sample_size", 0),
        "success_rate": stats.get("success_rate", 0),
        "failure_rate": stats.get("failure_rate", 0),
        "avg_duration": duration_str,
        "by_regime": stats.get("by_regime", {}),
    }
