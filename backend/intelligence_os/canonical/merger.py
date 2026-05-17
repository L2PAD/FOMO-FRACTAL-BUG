"""
Canonical Merger — Merge raw data into canonical entities
==========================================================
When resolver finds a match, merger updates the canonical entity
with new information from the raw source.
"""
from datetime import datetime, timezone
from intelligence_os.core.logging_config import get_logger

log = get_logger("canonical.merger")


class CanonicalMerger:
    def __init__(self, db, alias_store):
        self.db = db
        self.alias_store = alias_store

    async def merge_project(self, raw: dict, canonical: dict):
        raw_name = raw.get("name") or raw.get("project_name", "")
        source = raw.get("source", "unknown")
        canonical_id = canonical.get("canonical_id")
        now = datetime.now(timezone.utc).isoformat()

        # Add alias
        if raw_name:
            await self.alias_store.add_alias("project", canonical_id, raw_name, source)

        # Update canonical with latest data
        update = {
            "$set": {"last_seen": now, "updated_at": now},
            "$addToSet": {"sources": source},
        }

        # Merge non-null fields
        for field in ["category", "description", "website", "market_cap"]:
            if raw.get(field):
                update["$set"][f"metadata.{field}"] = raw[field]

        if raw.get("symbol") and not canonical.get("symbol"):
            update["$set"]["symbol"] = raw["symbol"].upper()

        await self.db["canonical_projects"].update_one(
            {"canonical_id": canonical_id}, update
        )
        log.info(f"Merged raw→canonical: '{raw_name}' → '{canonical.get('name')}'")

    async def merge_fund(self, raw: dict, canonical: dict):
        raw_name = raw.get("fund_name") or raw.get("investor_name") or raw.get("name", "")
        source = raw.get("source", "unknown")
        canonical_id = canonical.get("canonical_id")
        now = datetime.now(timezone.utc).isoformat()

        if raw_name:
            await self.alias_store.add_alias("fund", canonical_id, raw_name, source)

        await self.db["canonical_funds"].update_one(
            {"canonical_id": canonical_id},
            {
                "$set": {"last_seen": now, "updated_at": now},
                "$addToSet": {"sources": source},
            },
        )

    async def merge_token(self, raw: dict, canonical: dict):
        canonical_id = canonical.get("canonical_id")
        now = datetime.now(timezone.utc).isoformat()
        source = raw.get("source", "unknown")

        update_fields = {"last_seen": now, "updated_at": now}
        for field in ["price_usd", "market_cap", "volume_24h", "circulating_supply"]:
            if raw.get(field) is not None:
                update_fields[f"market.{field}"] = raw[field]

        await self.db["canonical_tokens"].update_one(
            {"canonical_id": canonical_id},
            {"$set": update_fields, "$addToSet": {"sources": source}},
        )
