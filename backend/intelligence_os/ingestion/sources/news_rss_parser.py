"""
News RSS Source Adapter
========================
Fetches news from RSS feeds and existing news pipeline.
"""
from datetime import datetime, timezone
from intelligence_os.ingestion.base_parser import BaseParser
from intelligence_os.core.logging_config import get_logger

log = get_logger("source.news_rss")


class NewsRSSParser(BaseParser):
    name = "news_rss"
    raw_collection = "raw_news"

    async def fetch(self, query: dict | None = None) -> list[dict]:
        rows = []
        now = datetime.now(timezone.utc).isoformat()

        # Bridge to existing news_articles collection
        cursor = self.db["news_articles"].find(
            {"_raw_migrated": {"$ne": True}},
            {"_id": 0},
        ).sort("published_at", -1).limit(200)

        async for article in cursor:
            rows.append({
                "source": article.get("source", "rss"),
                "domain": "NEWS",
                "title": article.get("title"),
                "content": (article.get("content") or article.get("summary", ""))[:2000],
                "url": article.get("url") or article.get("link"),
                "published_at": article.get("published_at"),
                "author": article.get("author"),
                "categories": article.get("categories", []),
                "fetched_at": now,
            })

        log.info(f"Fetched {len(rows)} news articles")
        return rows

    def validate(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if r.get("title")]

    async def save_raw(self, rows: list[dict]) -> int:
        count = await super().save_raw(rows)
        # Mark as migrated in source collection
        titles = [r["title"] for r in rows if r.get("title")]
        if titles:
            await self.db["news_articles"].update_many(
                {"title": {"$in": titles}},
                {"$set": {"_raw_migrated": True}},
            )
        return count
