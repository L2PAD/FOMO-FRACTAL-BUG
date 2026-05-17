"""
Projects Intelligence
======================
Project structure analysis, category classification.
"""
from datetime import datetime, timezone
from intelligence_os.core.logging_config import get_logger

log = get_logger("domain.projects")


class ProjectsIntelligence:
    def __init__(self, db):
        self.db = db

    async def enrich_projects(self) -> dict:
        """Enrich canonical projects with cross-source metadata."""
        cursor = self.db["canonical_projects"].find(
            {"_intel_enriched": {"$ne": True}}
        ).limit(500)
        enriched = 0
        now = datetime.now(timezone.utc).isoformat()

        async for project in cursor:
            pid = project.get("canonical_id")
            sources_count = len(project.get("sources", []))

            # Count related events
            funding_count = await self.db["canonical_events"].count_documents(
                {"project_canonical_id": pid, "event_type": "funding_round"}
            )
            activity_count = await self.db["canonical_events"].count_documents(
                {"project_canonical_id": pid, "event_type": "activity"}
            )
            news_count = await self.db["canonical_events"].count_documents(
                {"project_canonical_id": pid, "event_type": "news_event"}
            )

            await self.db["canonical_projects"].update_one(
                {"_id": project["_id"]},
                {
                    "$set": {
                        "_intel_enriched": True,
                        "intel": {
                            "sources_count": sources_count,
                            "funding_rounds": funding_count,
                            "activities": activity_count,
                            "news_mentions": news_count,
                            "enriched_at": now,
                        },
                    }
                },
            )
            enriched += 1

        log.info(f"[PROJECTS] Enriched: {enriched}")
        return {"enriched": enriched}
