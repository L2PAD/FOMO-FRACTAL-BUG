"""
Activities Intelligence
========================
Campaign/activity extraction, task timelines, participation detection.
"""
from datetime import datetime, timezone
from intelligence_os.core.logging_config import get_logger

log = get_logger("domain.activities")


class ActivitiesIntelligence:
    def __init__(self, db):
        self.db = db

    async def process_activities(self) -> dict:
        """Extract and classify activities from canonical events."""
        cursor = self.db["canonical_events"].find({"event_type": "activity"})
        processed, campaigns, tasks = 0, 0, 0
        now = datetime.now(timezone.utc).isoformat()

        async for event in cursor:
            processed += 1
            data = event.get("data", {})
            activity_type = (data.get("activity_type") or "unknown").lower()

            if activity_type in ("airdrop", "campaign", "quest"):
                campaigns += 1
                cat = "campaign"
            else:
                tasks += 1
                cat = "task"

            await self.db["intel_activity_campaigns"].update_one(
                {
                    "project_name": event.get("project_name"),
                    "activity_type": activity_type,
                },
                {
                    "$set": {
                        "category": cat,
                        "project_canonical_id": event.get("project_canonical_id"),
                        "status": data.get("status"),
                        "reward": data.get("reward"),
                        "description": data.get("description"),
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )

        log.info(f"[ACTIVITIES] Processed: {processed}, campaigns={campaigns}, tasks={tasks}")
        return {"processed": processed, "campaigns": campaigns, "tasks": tasks}

    async def get_graph_hooks(self) -> list[dict]:
        edges = []
        cursor = self.db["intel_activity_campaigns"].find(
            {"project_canonical_id": {"$exists": True}}, {"_id": 0}
        )
        async for act in cursor:
            if act.get("project_canonical_id"):
                edges.append({
                    "from_id": act["project_canonical_id"],
                    "to_id": f"activity:{act.get('project_name', '').lower().replace(' ', '-')}",
                    "edge_type": "has_activity",
                    "layer": "KNOWLEDGE",
                    "source": "activity_intelligence",
                })
        return edges
