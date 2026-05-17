"""
News Intelligence (Domain Module)
==================================
IMPORTANT: News goes ONLY to sentiment/events.
News does NOT influence graph base edges directly.

News → Sentiment pipeline
News → Event surface
News does NOT → Graph base edges
"""
from datetime import datetime, timezone
from intelligence_os.core.logging_config import get_logger

log = get_logger("domain.news")


class NewsIntelligence:
    def __init__(self, db):
        self.db = db

    async def process_news_events(self) -> dict:
        """Process news canonical events into intel clusters."""
        cursor = self.db["canonical_events"].find(
            {"event_type": "news_event", "_intel_processed": {"$ne": True}}
        )
        processed = 0
        now = datetime.now(timezone.utc).isoformat()

        async for event in cursor:
            processed += 1
            data = event.get("data", {})

            await self.db["intel_news_stories"].update_one(
                {"title": data.get("title"), "source": event.get("source")},
                {
                    "$set": {
                        "project_name": event.get("project_name"),
                        "project_canonical_id": event.get("project_canonical_id"),
                        "content_preview": (data.get("content") or "")[:500],
                        "categories": data.get("categories", []),
                        "published_at": data.get("published_at"),
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )

            await self.db["canonical_events"].update_one(
                {"_id": event["_id"]},
                {"$set": {"_intel_processed": True}},
            )

        log.info(f"[NEWS] Processed {processed} news events")
        return {"processed": processed}

    async def get_graph_hooks(self) -> list[dict]:
        """News generates ONLY co_mentioned_with edges, NOT base knowledge edges."""
        # News does NOT create base graph edges
        # Only co-mention / same-topic-cluster derived edges
        return []
