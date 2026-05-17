"""
Rule Repository — MongoDB storage for notification rules.
Collection: notification_rules
"""
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from notifications.rules.rule_types import default_user_rules, default_admin_rules

_db: Optional[AsyncIOMotorDatabase] = None
COLLECTION = "notification_rules"


def init_rule_repo(db: AsyncIOMotorDatabase):
    global _db
    _db = db


def _col():
    if _db is None:
        raise RuntimeError("Rule repo not initialized.")
    return _db[COLLECTION]


async def seed_default_rules():
    """Insert built-in rules if they don't exist, update channels if they do."""
    col = _col()
    for rule in default_user_rules() + default_admin_rules():
        existing = await col.find_one({"id": rule["id"]})
        if not existing:
            await col.insert_one(rule)
        else:
            # Update channels to include telegram if not present
            await col.update_one(
                {"id": rule["id"]},
                {"$set": {"channels": rule["channels"]}}
            )


async def get_matching_rules(event_type: str) -> list:
    """Get all enabled rules that match this event type."""
    col = _col()
    query = {
        "isEnabled": True,
        "$or": [
            {"eventTypes": event_type},
            {"eventTypes": {"$size": 0}},
            {"eventTypes": {"$exists": False}},
        ]
    }
    cursor = col.find(query, {"_id": 0})
    return await cursor.to_list(length=100)


async def get_all_rules() -> list:
    cursor = _col().find({}, {"_id": 0})
    return await cursor.to_list(length=200)


async def update_rule(rule_id: str, updates: dict) -> bool:
    updates.pop("id", None)
    updates.pop("_id", None)
    result = await _col().update_one({"id": rule_id}, {"$set": updates})
    return result.modified_count > 0


async def create_rule(rule: dict) -> dict:
    await _col().insert_one(rule)
    rule.pop("_id", None)
    return rule


async def delete_rule(rule_id: str) -> bool:
    result = await _col().delete_one({"id": rule_id, "isBuiltin": {"$ne": True}})
    return result.deleted_count > 0


async def ensure_indexes():
    col = _col()
    await col.create_index("id", unique=True)
    await col.create_index("eventTypes")
    await col.create_index("audience")
    await col.create_index("isEnabled")
