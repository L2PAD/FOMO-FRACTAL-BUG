"""
Notification Repository — MongoDB storage for notifications.
Collection: notifications
"""
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

_db: Optional[AsyncIOMotorDatabase] = None
COLLECTION = "notifications"


def init_notification_repo(db: AsyncIOMotorDatabase):
    global _db
    _db = db


def _col():
    if _db is None:
        raise RuntimeError("Notification repo not initialized.")
    return _db[COLLECTION]


async def save_notification(notification: dict) -> dict:
    notification.setdefault("createdAt", datetime.now(timezone.utc).isoformat())
    await _col().insert_one(notification)
    notification.pop("_id", None)
    return notification


async def check_notification_dedupe(dedupe_key: str, cooldown_minutes: int = 60) -> bool:
    """Returns True if should skip (recent duplicate exists)."""
    if not dedupe_key:
        return False
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)).isoformat()
    doc = await _col().find_one({
        "dedupeKey": dedupe_key,
        "createdAt": {"$gte": cutoff}
    })
    return doc is not None


async def get_notifications(audience: str = None, channel: str = None,
                            status: str = None, limit: int = 50) -> list:
    query = {}
    if audience:
        query["audience"] = audience
    if channel:
        query["channel"] = channel
    if status:
        query["status"] = status
    cursor = _col().find(query, {"_id": 0}).sort("createdAt", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_ui_notifications(audience: str = "user", limit: int = 20) -> list:
    """Get notifications for UI bell/feed."""
    query = {"channel": "ui", "audience": audience}
    cursor = _col().find(query, {"_id": 0}).sort("createdAt", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_unread_count(audience: str = "user") -> int:
    return await _col().count_documents({
        "channel": "ui",
        "audience": audience,
        "readAt": None
    })


async def mark_as_read(notification_id: str) -> bool:
    result = await _col().update_one(
        {"id": notification_id, "readAt": None},
        {"$set": {"readAt": datetime.now(timezone.utc).isoformat(), "status": "read"}}
    )
    return result.modified_count > 0


async def mark_all_read(audience: str = "user") -> int:
    now = datetime.now(timezone.utc).isoformat()
    result = await _col().update_many(
        {"audience": audience, "channel": "ui", "readAt": None},
        {"$set": {"readAt": now, "status": "read"}}
    )
    return result.modified_count


async def get_notification_stats() -> dict:
    total = await _col().count_documents({})
    unread_user = await get_unread_count("user")
    unread_admin = await get_unread_count("admin")
    pending = await _col().count_documents({"status": "pending"})
    sent = await _col().count_documents({"status": "sent"})
    return {
        "total": total,
        "unread_user": unread_user,
        "unread_admin": unread_admin,
        "pending": pending,
        "sent": sent,
    }


async def ensure_indexes():
    col = _col()
    await col.create_index("id", unique=True)
    await col.create_index("eventId")
    await col.create_index("audience")
    await col.create_index("channel")
    await col.create_index("status")
    await col.create_index("createdAt")
    await col.create_index("readAt")
    await col.create_index("dedupeKey")
