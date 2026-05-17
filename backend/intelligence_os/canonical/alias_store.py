"""
Alias Store — Entity alias management
=======================================
Stores and retrieves aliases for canonical entities.
Enables fuzzy resolution: "ETH" → "asset:ethereum", "Vitalik" → "person:vitalik-buterin"
"""
from datetime import datetime, timezone
from intelligence_os.core.logging_config import get_logger

log = get_logger("canonical.alias")


class AliasStore:
    def __init__(self, db):
        self.db = db
        self.col = db["entity_aliases"]

    async def add_alias(self, entity_type: str, canonical_id: str, alias: str, source: str):
        now = datetime.now(timezone.utc).isoformat()
        await self.col.update_one(
            {"entity_type": entity_type, "canonical_id": canonical_id},
            {
                "$addToSet": {
                    "aliases": {"value": alias.strip().lower(), "source": source, "added_at": now}
                },
                "$set": {"updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    async def find_by_alias(self, entity_type: str, alias: str) -> str | None:
        normalized = alias.strip().lower()
        doc = await self.col.find_one(
            {"entity_type": entity_type, "aliases.value": normalized},
            {"_id": 0, "canonical_id": 1},
        )
        return doc["canonical_id"] if doc else None

    async def get_aliases(self, canonical_id: str) -> list[str]:
        doc = await self.col.find_one(
            {"canonical_id": canonical_id}, {"_id": 0, "aliases": 1}
        )
        if not doc:
            return []
        return [a["value"] for a in doc.get("aliases", [])]
