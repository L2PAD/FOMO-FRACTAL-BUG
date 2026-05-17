"""
Engine Snapshot Service — E7
==============================
Moves expensive engine calculations into background jobs.
API reads pre-computed snapshots from MongoDB instead of running live calculations.

Collections:
  - engine_context_snapshots: full engine output (TTL 48h)
  - engine_micro_snapshots: lightweight snapshots for timelines (no TTL)
  - engine_setup_history: event-driven setup change tracking (no TTL)

Background loops:
  - Full snapshot every 90 seconds
  - Micro snapshot every 3 minutes
  - Setup history: event-driven (on change)
"""

import os
import time
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

_client = None
_db = None


def _get_db():
    """Stage A-3: explicit DB resolution.

    Previously this used `_client.get_database()` without a name, which
    requires the database name to be encoded in the connection URI.  Our
    MONGO_URL is bare (`mongodb://localhost:27017`) so that call raised
    'No default database defined' on every snapshot tick — the recurring
    error that broke Snapshot DB Wiring.

    Now we resolve DB explicitly via DB_NAME env var with a safe fallback,
    matching the convention used everywhere else in this app.
    """
    global _client, _db
    if _db is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
        _db = _client[os.environ.get("DB_NAME", "test_database")]
    return _db


def ensure_indexes():
    """Create indexes and TTL on snapshot collections. Idempotent."""
    db = _get_db()

    # Full snapshots: timestamp desc + TTL 48h
    db["engine_context_snapshots"].create_index(
        [("timestamp", DESCENDING)],
        name="idx_timestamp_desc",
    )
    try:
        db["engine_context_snapshots"].create_index(
            "created_at",
            expireAfterSeconds=48 * 3600,
            name="ttl_48h",
        )
    except Exception:
        pass  # TTL index already exists

    # Micro snapshots: timestamp desc
    db["engine_micro_snapshots"].create_index(
        [("timestamp", DESCENDING)],
        name="idx_timestamp_desc",
    )

    # Setup history: timestamp desc
    db["engine_setup_history"].create_index(
        [("timestamp", DESCENDING)],
        name="idx_timestamp_desc",
    )

    print("[Snapshot] Indexes ensured")


# ══════════════════════════════════════════════════════════
#  FULL SNAPSHOT BUILDER
# ══════════════════════════════════════════════════════════


def build_engine_snapshot() -> dict:
    """
    Build a full engine snapshot by running the entire pipeline.
    Saves the complete result to engine_context_snapshots.
    Returns the snapshot.
    """
    db = _get_db()
    start = time.time()

    try:
        # Clear the in-memory cache to get fresh data
        from engine_integration.service import _cache
        _cache.clear()

        # Run the full engine pipeline
        from engine_integration.service import get_integrated_engine_context
        engine_data = get_integrated_engine_context(chain_id=1, window="30d")

        elapsed_ms = round((time.time() - start) * 1000)
        now = datetime.now(timezone.utc)

        # Build snapshot document (exact API response shape)
        snapshot = {
            **engine_data,
            "snapshot_meta": {
                "timestamp": now.isoformat(),
                "engine_version": "4.5",
                "build_latency_ms": elapsed_ms,
                "source": "background_worker",
            },
            "timestamp": now.isoformat(),
            "created_at": now,  # for TTL index
        }

        # Save to MongoDB
        db["engine_context_snapshots"].insert_one(snapshot)

        # Check setup change and record history
        _check_and_save_setup_history(db, engine_data)

        # Market Memory: track setup outcomes
        try:
            from engine_integration.engine_memory_service import (
                record_setup_detection, check_and_resolve_outcomes,
            )
            record_setup_detection(engine_data)
            check_and_resolve_outcomes(engine_data)
        except Exception as mem_err:
            print(f"[Snapshot] Memory tracking error (non-fatal): {mem_err}")

        # Regime Timeline: track regime changes
        try:
            _check_and_save_regime_history(db, engine_data)
        except Exception as reg_err:
            print(f"[Snapshot] Regime history error (non-fatal): {reg_err}")

        # Liquidity Evolution: track liquidity zone changes
        try:
            _track_liquidity_evolution(db, engine_data)
        except Exception as liq_err:
            print(f"[Snapshot] Liquidity evolution error (non-fatal): {liq_err}")

        print(f"[Snapshot] Full snapshot built in {elapsed_ms}ms")
        return snapshot

    except Exception as e:
        elapsed_ms = round((time.time() - start) * 1000)
        print(f"[Snapshot] Full snapshot FAILED in {elapsed_ms}ms: {e}")
        import traceback
        traceback.print_exc()
        return {}


# ══════════════════════════════════════════════════════════
#  MICRO SNAPSHOT BUILDER
# ══════════════════════════════════════════════════════════


def build_micro_snapshot() -> dict:
    """
    Build a lightweight snapshot for timeline visualizations.
    Reads from the latest full snapshot to avoid recalculation.
    """
    db = _get_db()

    # Read latest full snapshot
    latest = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0}, sort=[("timestamp", DESCENDING)]
    )

    if not latest:
        return {}

    now = datetime.now(timezone.utc)
    regime = latest.get("regime_engine", {}).get("primary", {})
    setup = latest.get("setup_engine", {}).get("primary", {})
    prob = latest.get("probability_layer", {})
    flow = latest.get("flow_engine", {})

    micro = {
        "timestamp": now.isoformat(),
        "decision": latest.get("decision", "NEUTRAL"),
        "confidence_score": latest.get("confidence", {}).get("score", 0),
        "composite": latest.get("scores", {}).get("composite", 50),
        "regime": regime.get("type", "neutral_chop"),
        "regime_status": regime.get("status", "weak"),
        "regime_confidence": regime.get("confidence", 0),
        "setup": setup.get("type", "mixed"),
        "setup_status": setup.get("status", "weak"),
        "setup_confidence": setup.get("confidence", 0),
        "probability_continuation": prob.get("continuation", 0),
        "probability_failure": prob.get("failure", 0),
        "probability_upgrade": prob.get("upgrade", 0),
        "flow_state": flow.get("state", "neutral"),
        "flow_strength": flow.get("strength", 0),
    }

    db["engine_micro_snapshots"].insert_one(micro)

    # Keep max 2000 micro snapshots (~4 days at 3min intervals)
    count = db["engine_micro_snapshots"].count_documents({})
    if count > 2000:
        oldest = db["engine_micro_snapshots"].find(
            {}, {"_id": 1}, sort=[("timestamp", 1)]
        ).limit(count - 2000)
        ids = [d["_id"] for d in oldest]
        if ids:
            db["engine_micro_snapshots"].delete_many({"_id": {"$in": ids}})

    print(f"[Snapshot] Micro snapshot saved")
    return micro


# ══════════════════════════════════════════════════════════
#  SETUP HISTORY (EVENT-DRIVEN)
# ══════════════════════════════════════════════════════════


def _check_and_save_setup_history(db, engine_data: dict):
    """Record setup change to engine_setup_history if setup or status changed."""
    setup = engine_data.get("setup_engine", {}).get("primary", {})
    regime = engine_data.get("regime_engine", {}).get("primary", {})
    prob = engine_data.get("probability_layer", {})

    current_type = setup.get("type", "mixed")
    current_status = setup.get("status", "weak")
    current_conf = setup.get("confidence", 0)

    # Get the most recent history entry
    last = db["engine_setup_history"].find_one(
        {}, {"_id": 0}, sort=[("timestamp", DESCENDING)]
    )

    # Check if setup or status changed
    if last:
        if last.get("setup") == current_type and last.get("status") == current_status:
            return  # No change — skip

    now = datetime.now(timezone.utc)
    entry = {
        "timestamp": now.isoformat(),
        "setup": current_type,
        "status": current_status,
        "confidence": round(current_conf, 3),
        "probability_at_event": round(prob.get("continuation", 0), 3),
        "regime_at_event": regime.get("type", "neutral_chop"),
        "previous_setup": last.get("setup") if last else None,
        "previous_status": last.get("status") if last else None,
    }

    db["engine_setup_history"].insert_one(entry)
    print(f"[Snapshot] Setup history: {last.get('setup', '?') if last else 'init'}/{last.get('status', '?') if last else '?'} → {current_type}/{current_status}")



def _check_and_save_regime_history(db, engine_data: dict):
    """Record regime change to engine_regime_history if regime changed."""
    regime = engine_data.get("regime_engine", {}).get("primary", {})
    setup = engine_data.get("setup_engine", {}).get("primary", {})

    current_regime = regime.get("type", "neutral_chop")
    current_conf = regime.get("confidence", 0)

    # Get the most recent regime entry
    last = db["engine_regime_history"].find_one(
        {}, {"_id": 0}, sort=[("timestamp", DESCENDING)]
    )

    # Only record if regime changed
    if last and last.get("regime") == current_regime:
        return  # No change

    now = datetime.now(timezone.utc)
    entry = {
        "timestamp": now.isoformat(),
        "regime": current_regime,
        "previous_regime": last.get("regime") if last else None,
        "confidence": round(current_conf, 3),
        "driver": setup.get("type", "mixed"),
        "driver_status": setup.get("status", "weak"),
    }

    db["engine_regime_history"].insert_one(entry)

    # Keep max 500 entries
    count = db["engine_regime_history"].count_documents({})
    if count > 500:
        oldest = db["engine_regime_history"].find(
            {}, {"_id": 1}, sort=[("timestamp", 1)]
        ).limit(count - 500)
        ids = [d["_id"] for d in oldest]
        if ids:
            db["engine_regime_history"].delete_many({"_id": {"$in": ids}})

    prev = last.get("regime", "init") if last else "init"
    print(f"[Snapshot] Regime history: {prev} → {current_regime}")


def _track_liquidity_evolution(db, engine_data: dict):
    """Record liquidity zone state for evolution tracking."""
    liq = engine_data.get("liquidity_map", {})
    targets = liq.get("target_zones", [])
    magnets = liq.get("magnet_zones", [])
    voids = liq.get("void_zones", [])

    if not targets and not magnets and not voids:
        return

    now = datetime.now(timezone.utc)

    # Build zones snapshot
    zones = []
    for t in targets[:3]:
        zones.append({"type": "target", "direction": t.get("direction", ""), "reason": t.get("reason", ""), "confidence": t.get("confidence", 0)})
    for m in magnets[:2]:
        zones.append({"type": "magnet", "direction": m.get("direction", ""), "reason": m.get("reason", ""), "confidence": m.get("confidence", 0)})
    for v in voids[:2]:
        zones.append({"type": "void", "direction": v.get("direction", ""), "reason": v.get("reason", ""), "confidence": v.get("confidence", 0)})

    # Get previous state
    prev = db["liquidity_level_history"].find_one(
        {}, {"_id": 0}, sort=[("timestamp", DESCENDING)]
    )
    prev_zones = prev.get("zones", []) if prev else []

    # Compute dynamics by comparing zone counts and confidence
    dynamics = []
    for z in zones:
        key = f"{z['type']}_{z['direction']}"
        prev_match = next((p for p in prev_zones if f"{p['type']}_{p['direction']}" == key), None)
        if prev_match:
            diff = z["confidence"] - prev_match["confidence"]
            if diff > 0.05:
                trend = "strengthening"
            elif diff < -0.05:
                trend = "weakening"
            else:
                trend = "stable"
        else:
            trend = "new"
        dynamics.append({**z, "trend": trend})

    entry = {
        "timestamp": now.isoformat(),
        "zones": zones,
        "dynamics": dynamics,
        "zone_count": len(zones),
    }
    db["liquidity_level_history"].insert_one(entry)

    # Keep max 500 entries
    count = db["liquidity_level_history"].count_documents({})
    if count > 500:
        oldest = db["liquidity_level_history"].find(
            {}, {"_id": 1}, sort=[("timestamp", 1)]
        ).limit(count - 500)
        ids = [d["_id"] for d in oldest]
        if ids:
            db["liquidity_level_history"].delete_many({"_id": {"$in": ids}})




# ══════════════════════════════════════════════════════════
#  SNAPSHOT READERS
# ══════════════════════════════════════════════════════════


def get_latest_snapshot() -> dict:
    """
    Get the most recent full snapshot.
    Returns None if no snapshot exists.
    """
    db = _get_db()
    doc = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0, "created_at": 0}, sort=[("timestamp", DESCENDING)]
    )
    return doc


def get_snapshot_age_seconds() -> float:
    """Get the age of the latest snapshot in seconds."""
    db = _get_db()
    doc = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0, "timestamp": 1}, sort=[("timestamp", DESCENDING)]
    )
    if not doc or not doc.get("timestamp"):
        return 999999
    try:
        ts = datetime.fromisoformat(doc["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return 999999


def get_setup_history(limit: int = 50) -> list:
    """Get setup history timeline."""
    db = _get_db()
    docs = list(
        db["engine_setup_history"].find(
            {}, {"_id": 0}
        ).sort("timestamp", DESCENDING).limit(limit)
    )
    return docs


def get_micro_snapshots(limit: int = 100) -> list:
    """Get micro snapshots for timeline visualization."""
    db = _get_db()
    docs = list(
        db["engine_micro_snapshots"].find(
            {}, {"_id": 0}
        ).sort("timestamp", DESCENDING).limit(limit)
    )
    return docs
