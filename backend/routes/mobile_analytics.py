"""
Mobile Analytics — Growth Layer G1
==================================
POST /api/mobile/analytics/track        — single event
POST /api/mobile/analytics/batch        — batch of events (array)
GET  /api/mobile/analytics/events       — (debug) recent events
GET  /api/mobile/analytics/summary      — aggregate counts by event (optional)

Collection: analytics_events
Schema: {
  event: str,
  userId: str | None,        # None for guests (pre-auth)
  sessionId: str | None,
  signalId: str | None,
  asset: str | None,
  source: str | None,
  priority: str | None,
  context: dict | None,      # { screen, from, ... }
  timestamp: datetime,
}

Indexes:
  (userId, event, timestamp desc)
  (event, timestamp desc)
  (timestamp desc)

Non-blocking / fire-and-forget: returns `{ok: true}` even if payload is weak.
Auth: optional — reads request.state.user if present (no 401).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

log = logging.getLogger("mobile.analytics")

router = APIRouter(prefix="/api/mobile/analytics", tags=["analytics"])

# ── Allowed events (whitelist) ────────────────────────────────────────
ALLOWED_EVENTS = {
    # Hero
    "signal_hero_view",
    "signal_hero_tap",
    # Edge
    "edge_open",
    "edge_paywall_view",
    "edge_paywall_click",
    # Missed retention loop
    "missed_seen",
    "missed_click",
    "return_after_missed",
    # Share growth loop
    "share_click",
    "share_complete",
}

# ── DB helper ─────────────────────────────────────────────────────────
_db = None


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient  # type: ignore
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        dbname = os.getenv("DB_NAME", "fomo")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        _db = client[dbname]
        # Best-effort indexes
        try:
            _db["analytics_events"].create_index(
                [("userId", 1), ("event", 1), ("timestamp", -1)]
            )
            _db["analytics_events"].create_index([("event", 1), ("timestamp", -1)])
            _db["analytics_events"].create_index([("timestamp", -1)])
        except Exception as e:  # pragma: no cover - index create is best-effort
            log.warning("analytics index create skipped: %s", e)
        return _db
    except Exception as e:
        log.error("analytics db init failed: %s", e)
        return None


# ── Models ────────────────────────────────────────────────────────────
class AnalyticsEvent(BaseModel):
    event: str
    signalId: Optional[str] = None
    asset: Optional[str] = None
    source: Optional[str] = None
    priority: Optional[str] = None
    sessionId: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    clientTs: Optional[int] = None  # client timestamp (ms) for latency debugging


class AnalyticsBatch(BaseModel):
    events: List[AnalyticsEvent] = Field(default_factory=list)
    sessionId: Optional[str] = None


# ── Core writer ───────────────────────────────────────────────────────
def _extract_user_id(request: Request) -> Optional[str]:
    """Read authenticated user id if middleware attached it. Otherwise None (guest)."""
    try:
        user = getattr(request.state, "user", None)
        if not user:
            return None
        return user.get("_id") or user.get("user_id") or user.get("id")
    except Exception:
        return None


def _normalize(ev: AnalyticsEvent, user_id: Optional[str], session_id: Optional[str]) -> Optional[Dict[str, Any]]:
    name = (ev.event or "").strip()
    if not name or name not in ALLOWED_EVENTS:
        return None
    return {
        "event": name,
        "userId": user_id,
        "sessionId": ev.sessionId or session_id,
        "signalId": ev.signalId,
        "asset": (ev.asset or "").upper() or None,
        "source": ev.source,
        "priority": ev.priority,
        "context": ev.context or {},
        "clientTs": ev.clientTs,
        "timestamp": datetime.utcnow(),
    }


@router.post("/track")
async def track_event(ev: AnalyticsEvent, request: Request):
    """Single event — fire-and-forget. Always returns ok=true for valid structure."""
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    doc = _normalize(ev, _extract_user_id(request), None)
    if not doc:
        # Unknown event name — do not error, just drop so clients do not retry forever
        return {"ok": True, "dropped": True, "reason": "unknown_event"}

    try:
        db["analytics_events"].insert_one(doc)
    except Exception as e:
        log.warning("analytics insert failed: %s", e)
        return {"ok": False, "error": "insert_failed"}

    return {"ok": True, "event": doc["event"]}


@router.post("/batch")
async def track_batch(batch: AnalyticsBatch, request: Request):
    """Batch of events — for offline flush / rapid-fire."""
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    user_id = _extract_user_id(request)
    docs = []
    dropped = 0
    for ev in batch.events[:50]:  # hard cap per batch
        doc = _normalize(ev, user_id, batch.sessionId)
        if doc:
            docs.append(doc)
        else:
            dropped += 1

    inserted = 0
    if docs:
        try:
            res = db["analytics_events"].insert_many(docs, ordered=False)
            inserted = len(res.inserted_ids)
        except Exception as e:
            log.warning("analytics batch insert failed: %s", e)
            return {"ok": False, "error": "insert_failed"}

    return {"ok": True, "inserted": inserted, "dropped": dropped}


@router.get("/events")
async def recent_events(limit: int = 50, event: Optional[str] = None):
    """Debug: recent events (admin-facing; no auth here for simplicity)."""
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}
    q: Dict[str, Any] = {}
    if event:
        q["event"] = event
    try:
        cur = db["analytics_events"].find(q, {"_id": 0}).sort("timestamp", -1).limit(max(1, min(limit, 200)))
        items = list(cur)
        for it in items:
            if isinstance(it.get("timestamp"), datetime):
                it["timestamp"] = it["timestamp"].isoformat()
        return {"ok": True, "count": len(items), "items": items}
    except Exception as e:
        log.warning("analytics fetch failed: %s", e)
        return {"ok": False, "error": "fetch_failed"}


@router.get("/summary")
async def event_summary(hours: int = 24):
    """Quick counts per event over last N hours."""
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(hours=max(1, min(hours, 24 * 30)))
    try:
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {"_id": "$event", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        agg = list(db["analytics_events"].aggregate(pipeline))
        counts = {row["_id"]: row["count"] for row in agg}
        return {"ok": True, "hours": hours, "counts": counts}
    except Exception as e:
        log.warning("analytics summary failed: %s", e)
        return {"ok": False, "error": "aggregate_failed"}


# ══════════════════════════════════════════════════════════════════════
# GROWTH METRICS (read-only, no side effects, no cache)
# ══════════════════════════════════════════════════════════════════════
# GET /api/mobile/analytics/growth-metrics?hours=48
#
# Strict semantics (per CEO spec — do not deviate):
#   share_rate         = share_complete / hero_tap
#                        (NOT hero_view, NOT edge_open)
#   ref_conversion     = users_with_ref_applied / share_complete
#                        users_with_ref_applied = users.referrals.referredBy set
#                        within the window (created or updated)
#   missed_return_rate = return_after_missed / missed_click
#
# Segments (per-userId aggregation — excludes anonymous events):
#   believers_no_share = users with hero_tap>=2 AND edge_open>=1 AND share=0
#   early_sharers      = users with share_complete>=2
#   missed_responders  = users with return_after_missed>=1
#
# Zero side effects: pure read; no writes; no cache.
# ══════════════════════════════════════════════════════════════════════
@router.get("/growth-metrics")
async def growth_metrics(hours: int = 48):
    """
    Returns top-line growth metrics over last N hours.
    Read-only. Safe to hit from anywhere. No auth required.
    """
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    from datetime import timedelta
    window_h = max(1, min(hours, 24 * 30))
    since = datetime.utcnow() - timedelta(hours=window_h)

    # Default zero-shape — always returned, even when empty.
    empty = {
        "share_rate": 0.0,
        "ref_conversion": 0.0,
        "missed_return_rate": 0.0,
        "funnel": {
            "hero_view": 0,
            "hero_tap": 0,
            "edge_open": 0,
            "share_complete": 0,
        },
        "segments": {
            "believers_no_share": 0,
            "early_sharers": 0,
            "missed_responders": 0,
        },
    }

    try:
        # ── 1. Global event counts (funnel) ────────────────────────────
        funnel_pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {"_id": "$event", "count": {"$sum": 1}}},
        ]
        funnel_rows = {r["_id"]: r["count"] for r in db["analytics_events"].aggregate(funnel_pipeline)}

        hero_view = int(funnel_rows.get("signal_hero_view", 0))
        hero_tap = int(funnel_rows.get("signal_hero_tap", 0))
        edge_open = int(funnel_rows.get("edge_open", 0))
        share_complete = int(funnel_rows.get("share_complete", 0))
        missed_click = int(funnel_rows.get("missed_click", 0))
        return_after_missed = int(funnel_rows.get("return_after_missed", 0))

        # ── 2. Rates (strict formulas from spec) ───────────────────────
        share_rate = round(share_complete / hero_tap, 4) if hero_tap > 0 else 0.0
        missed_return_rate = round(return_after_missed / missed_click, 4) if missed_click > 0 else 0.0

        # ── 3. ref_conversion ──────────────────────────────────────────
        # Count unique users who had a referral applied during the window.
        # Source of truth = users.referrals.referredBy (set by existing
        # /api/mobile/auth/referrals/apply endpoint — NOT a new collection).
        ref_applied_count = 0
        try:
            ref_applied_count = db["users"].count_documents({
                "referrals.referredBy": {"$exists": True, "$ne": None, "$ne": ""},
                # We count users whose record was updated in the window.
                # Use createdAt OR referrals.referredAt if present.
                "$or": [
                    {"referrals.referredAt": {"$gte": since}},
                    {"createdAt": {"$gte": since}},
                ],
            })
        except Exception:
            # If the users collection doesn't track updatedAt, count lifetime
            # applied (still useful, just less window-scoped).
            try:
                ref_applied_count = db["users"].count_documents({
                    "referrals.referredBy": {"$exists": True, "$ne": None, "$ne": ""}
                })
            except Exception:
                ref_applied_count = 0

        ref_conversion = round(ref_applied_count / share_complete, 4) if share_complete > 0 else 0.0

        # ── 4. Segments (per-userId) ───────────────────────────────────
        # Only consider events with non-null userId (logged-in sessions).
        # Anonymous events go into the funnel but cannot be segmented
        # without identity.
        segment_pipeline = [
            {"$match": {
                "timestamp": {"$gte": since},
                "userId": {"$ne": None},
                "event": {"$in": [
                    "signal_hero_tap", "edge_open", "share_complete", "return_after_missed",
                ]},
            }},
            {"$group": {
                "_id": "$userId",
                "hero_tap": {"$sum": {"$cond": [{"$eq": ["$event", "signal_hero_tap"]}, 1, 0]}},
                "edge_open": {"$sum": {"$cond": [{"$eq": ["$event", "edge_open"]}, 1, 0]}},
                "share_complete": {"$sum": {"$cond": [{"$eq": ["$event", "share_complete"]}, 1, 0]}},
                "return_after_missed": {"$sum": {"$cond": [{"$eq": ["$event", "return_after_missed"]}, 1, 0]}},
            }},
        ]
        believers_no_share = 0
        early_sharers = 0
        missed_responders = 0

        for u in db["analytics_events"].aggregate(segment_pipeline):
            ht = u.get("hero_tap", 0)
            eo = u.get("edge_open", 0)
            sc = u.get("share_complete", 0)
            rm = u.get("return_after_missed", 0)
            if ht >= 2 and eo >= 1 and sc == 0:
                believers_no_share += 1
            if sc >= 2:
                early_sharers += 1
            if rm >= 1:
                missed_responders += 1

        return {
            "ok": True,
            "hours": window_h,
            "since": since.isoformat() + "Z",
            "share_rate": share_rate,
            "ref_conversion": ref_conversion,
            "missed_return_rate": missed_return_rate,
            "funnel": {
                "hero_view": hero_view,
                "hero_tap": hero_tap,
                "edge_open": edge_open,
                "share_complete": share_complete,
            },
            "segments": {
                "believers_no_share": believers_no_share,
                "early_sharers": early_sharers,
                "missed_responders": missed_responders,
            },
            # Extra raw counts for debugging — not part of the core spec,
            # but useful when you (CEO) read the numbers.
            "_debug": {
                "missed_click": missed_click,
                "return_after_missed": return_after_missed,
                "ref_applied_users": ref_applied_count,
            },
        }

    except Exception as e:
        log.warning("growth_metrics failed: %s", e)
        # On any failure, return the zero-shape so dashboards don't break.
        result = dict(empty)
        result["ok"] = False
        result["hours"] = window_h
        result["error"] = "aggregate_failed"
        return result
