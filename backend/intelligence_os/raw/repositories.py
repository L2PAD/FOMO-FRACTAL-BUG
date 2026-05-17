"""
Raw Repositories — CRUD for raw collections
============================================
"""
from intelligence_os.raw.schemas import RAW_COLLECTIONS
from intelligence_os.core.logging_config import get_logger

log = get_logger("raw.repo")


class RawRepository:
    def __init__(self, db):
        self.db = db

    async def count_unprocessed(self, domain: str) -> int:
        col_name = RAW_COLLECTIONS.get(domain)
        if not col_name:
            return 0
        return await self.db[col_name].count_documents({"_canonicalized": {"$ne": True}})

    async def get_unprocessed(self, domain: str, limit: int = 500):
        col_name = RAW_COLLECTIONS.get(domain)
        if not col_name:
            return []
        cursor = self.db[col_name].find(
            {"_canonicalized": {"$ne": True}}, {"_id": 0}
        ).limit(limit)
        return await cursor.to_list(length=limit)

    async def mark_canonicalized(self, domain: str, doc_filter: dict):
        col_name = RAW_COLLECTIONS.get(domain)
        if col_name:
            await self.db[col_name].update_many(
                doc_filter,
                {"$set": {"_canonicalized": True}},
            )

    async def get_stats(self) -> dict:
        stats = {}
        for domain, col_name in RAW_COLLECTIONS.items():
            total = await self.db[col_name].estimated_document_count()
            unprocessed = await self.db[col_name].count_documents(
                {"_canonicalized": {"$ne": True}}
            )
            stats[domain] = {"total": total, "unprocessed": unprocessed}
        return stats
