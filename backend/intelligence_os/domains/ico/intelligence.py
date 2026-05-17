"""
ICO Intelligence
================
Tracks ICO launches: upcoming, active, ended.
Builds intelligence on raise status, categories, trends.
"""
from datetime import datetime, timezone
from intelligence_os.core.logging_config import get_logger

log = get_logger("domain.ico")


class ICOIntelligence:
    def __init__(self, db):
        self.db = db

    async def classify_launches(self) -> dict:
        """Classify ICO events into upcoming/active/ended."""
        now = datetime.now(timezone.utc)
        cursor = self.db["canonical_events"].find({"event_type": "ico"})
        classified = {"upcoming": 0, "active": 0, "ended": 0, "unknown": 0}

        async for event in cursor:
            data = event.get("data", {})
            status = (data.get("status") or "unknown").lower()

            if status in ("upcoming", "presale"):
                classified["upcoming"] += 1
                launch_status = "upcoming"
            elif status in ("active", "live", "ongoing"):
                classified["active"] += 1
                launch_status = "active"
            elif status in ("ended", "completed", "closed"):
                classified["ended"] += 1
                launch_status = "ended"
            else:
                classified["unknown"] += 1
                launch_status = "unknown"

            await self.db["intel_ico_launches"].update_one(
                {"project_name": event.get("project_name"), "source": event.get("source")},
                {
                    "$set": {
                        "launch_status": launch_status,
                        "raise_target": data.get("raise_target"),
                        "category": data.get("category"),
                        "updated_at": now.isoformat(),
                    },
                    "$setOnInsert": {
                        "project_name": event.get("project_name"),
                        "project_canonical_id": event.get("project_canonical_id"),
                        "created_at": now.isoformat(),
                    },
                },
                upsert=True,
            )

        log.info(f"[ICO] Classified: {classified}")
        return classified

    async def get_graph_hooks(self) -> list[dict]:
        edges = []
        cursor = self.db["intel_ico_launches"].find({"project_canonical_id": {"$exists": True}})
        async for ico in cursor:
            if ico.get("project_canonical_id"):
                edges.append({
                    "from_id": ico["project_canonical_id"],
                    "to_id": f"ico:{ico.get('project_name', '').lower().replace(' ', '-')}",
                    "edge_type": "has_ico",
                    "layer": "KNOWLEDGE",
                    "source": "ico_intelligence",
                })
        return edges
