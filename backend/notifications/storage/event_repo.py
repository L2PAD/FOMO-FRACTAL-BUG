"""
Event Repository — MongoDB storage for notification events.
Collection: notification_events
"""
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

_db: Optional[AsyncIOMotorDatabase] = None
COLLECTION = "notification_events"


def init_event_repo(db: AsyncIOMotorDatabase):
    global _db
    _db = db


def _col():
    if _db is None:
        raise RuntimeError("Event repo not initialized. Call init_event_repo(db) first.")
    return _db[COLLECTION]


async def save_event(event: dict) -> dict:
    """Insert event into notification_events. Returns the event with generated id."""
    event.setdefault("createdAt", datetime.now(timezone.utc).isoformat())
    await _col().insert_one(event)
    event.pop("_id", None)
    return event


async def get_event_by_id(event_id: str) -> Optional[dict]:
    doc = await _col().find_one({"id": event_id}, {"_id": 0})
    return doc


async def get_recent_events(limit: int = 50, source: Optional[str] = None,
                            event_type: Optional[str] = None) -> list:
    query = {}
    if source:
        query["source"] = source
    if event_type:
        query["type"] = event_type
    cursor = _col().find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def check_dedupe(dedupe_key: str, cooldown_minutes: int = 60) -> bool:
    """Returns True if a recent event with same dedupeKey exists (should skip)."""
    if not dedupe_key:
        return False
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)).isoformat()
    doc = await _col().find_one({
        "dedupeKey": dedupe_key,
        "timestamp": {"$gte": cutoff}
    })
    return doc is not None


async def get_event_stats() -> dict:
    """Get basic stats for dashboard."""
    total = await _col().count_documents({})
    pipeline = [
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    by_source = {}
    async for doc in _col().aggregate(pipeline):
        by_source[doc["_id"]] = doc["count"]

    pipeline_sev = [
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
    ]
    by_severity = {}
    async for doc in _col().aggregate(pipeline_sev):
        by_severity[doc["_id"]] = doc["count"]

    return {
        "total_events": total,
        "by_source": by_source,
        "by_severity": by_severity,
    }


async def ensure_indexes():
    col = _col()
    await col.create_index("id", unique=True)
    await col.create_index("type")
    await col.create_index("source")
    await col.create_index("timestamp")
    await col.create_index("dedupeKey")
    await col.create_index("asset")
