"""
Dropstab Source Adapter
========================
Fetches activities and project data from Dropstab.
"""
import sys
from datetime import datetime, timezone
from intelligence_os.ingestion.base_parser import BaseParser
from intelligence_os.core.logging_config import get_logger

log = get_logger("source.dropstab")


class DropstabActivitiesParser(BaseParser):
    name = "dropstab"
    raw_collection = "raw_activities"

    async def fetch(self, query: dict | None = None) -> list[dict]:
        rows = []
        now = datetime.now(timezone.utc).isoformat()

        # Bridge to existing entity_activity collection
        cursor = self.db["entity_activity"].find(
            {"_raw_migrated": {"$ne": True}},
            {"_id": 0},
        ).sort("created_at", -1).limit(300)

        async for act in cursor:
            rows.append({
                "source": "dropstab",
                "domain": "ACTIVITIES",
                "project_name": act.get("entity") or act.get("project_name"),
                "activity_type": act.get("type", "unknown"),
                "description": act.get("description"),
                "status": act.get("status"),
                "fetched_at": now,
                "original_data": {k: v for k, v in act.items() if k != "_id"},
            })

        log.info(f"Fetched {len(rows)} activities from Dropstab bridge")
        return rows

    def validate(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if r.get("project_name")]

    async def save_raw(self, rows: list[dict]) -> int:
        count = await super().save_raw(rows)
        names = [r["project_name"] for r in rows if r.get("project_name")]
        if names:
            await self.db["entity_activity"].update_many(
                {"entity": {"$in": names}},
                {"$set": {"_raw_migrated": True}},
            )
        return count


class DropstabProjectsParser(BaseParser):
    name = "dropstab_projects"
    raw_collection = "raw_projects"

    async def fetch(self, query: dict | None = None) -> list[dict]:
        rows = []
        now = datetime.now(timezone.utc).isoformat()

        # Bridge to existing graph_nodes that are projects
        cursor = self.db["graph_nodes"].find(
            {"type": {"$in": ["project", "asset"]}, "_raw_migrated": {"$ne": True}},
            {"_id": 0},
        ).limit(500)

        async for node in cursor:
            rows.append({
                "source": "dropstab",
                "domain": "PROJECTS",
                "name": node.get("label") or node.get("name"),
                "symbol": node.get("symbol"),
                "entity_id": node.get("entity_id"),
                "category": node.get("category"),
                "fetched_at": now,
            })

        log.info(f"Fetched {len(rows)} projects from Dropstab bridge")
        return rows

    def validate(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if r.get("name")]
