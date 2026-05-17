"""
runtime_events — forward-only continuity trace ledger.

NOT observability pipeline.  NOT metrics aggregation.  NOT streaming UI.
NOT analytics dashboard.  NOT a counters service.

Pure append-only ledger that records salient transitions in cognitive
runtime substrate.  Used by Observatory + future post-hoc audits.

Discipline:
    • Append-only writes
    • Bounded retention (capped collection, oldest evicted)
    • Compact payloads — NO embedded runtime blobs
    • Forward-only — never backfilled, never reconstructed
    • Best-effort — emit failures must NEVER propagate

Event types (closed set):
    MODULE_DEGRADED          — a runtime layer transitioned to degraded
    MODULE_RECOVERED         — a runtime layer recovered from degraded
    ALIGNMENT_SHIFT          — cross-module coherence label changed
    OUTCOME_RESOLVED         — a pending outcome closed (resolved or expired)
    SHADOW_BLOCKED           — shadow verdict produced status=blocked
    PAPER_GATE_STATE_CHANGED — paper runtime gate open/closed flipped
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Optional

from pymongo import MongoClient, DESCENDING


COLLECTION = "runtime_events"
CAPPED_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB ring buffer
CAPPED_MAX_DOCS = 50_000

EVENT_TYPES = {
    "MODULE_DEGRADED",
    "MODULE_RECOVERED",
    "ALIGNMENT_SHIFT",
    "OUTCOME_RESOLVED",
    "SHADOW_BLOCKED",
    "PAPER_GATE_STATE_CHANGED",
}

_lock = threading.RLock()
_client: Optional[MongoClient] = None
_capped_ensured = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
    return _client[os.environ.get("DB_NAME", "test_database")]


def _ensure_capped() -> None:
    """Create the capped collection if it doesn't exist.
    No-op once ensured.  Never re-creates."""
    global _capped_ensured
    if _capped_ensured:
        return
    try:
        db = _db()
        names = set(db.list_collection_names())
        if COLLECTION not in names:
            db.create_collection(
                COLLECTION,
                capped=True,
                size=CAPPED_SIZE_BYTES,
                max=CAPPED_MAX_DOCS,
            )
        _capped_ensured = True
    except Exception:
        _capped_ensured = False


def emit(event_type: str, payload: Optional[dict] = None) -> None:
    """Append a continuity event.  Best-effort — never raises.

    Compact payloads enforced by convention; we do not deep-validate
    here to keep emit() in fastest possible path."""
    if event_type not in EVENT_TYPES:
        return
    try:
        _ensure_capped()
        doc = {
            "type": event_type,
            "payload": payload or {},
            "createdAt": _now_iso(),
        }
        _db()[COLLECTION].insert_one(doc)
    except Exception:
        # Continuity trace MUST NOT block the runtime path.
        pass


def recent(limit: int = 50, type_filter: Optional[str] = None) -> dict:
    """Pull recent events.  Operator-only consumption."""
    with _lock:
        _ensure_capped()
        try:
            q: dict = {}
            if type_filter and type_filter in EVENT_TYPES:
                q["type"] = type_filter
            rows = list(
                _db()[COLLECTION]
                .find(q, {"_id": 0})
                .sort("createdAt", DESCENDING)
                .limit(max(1, min(int(limit), 500)))
            )
            return {
                "ok": True,
                "count": len(rows),
                "items": rows,
                "asOf": _now_iso(),
            }
        except Exception as e:
            return {"ok": False, "reason": f"db_error: {e!r}", "count": 0, "items": []}


def health() -> dict:
    """Sanity probe — ledger existence, capped, doc count, latest timestamp."""
    with _lock:
        _ensure_capped()
        try:
            db = _db()
            coll = db[COLLECTION]
            total = coll.estimated_document_count()
            latest = coll.find_one({}, {"_id": 0, "createdAt": 1, "type": 1},
                                   sort=[("createdAt", DESCENDING)])
            return {
                "ok": True,
                "total": total,
                "capped": True,
                "capSizeBytes": CAPPED_SIZE_BYTES,
                "capMaxDocs": CAPPED_MAX_DOCS,
                "latest": latest or None,
                "asOf": _now_iso(),
            }
        except Exception as e:
            return {"ok": False, "reason": f"db_error: {e!r}"}
