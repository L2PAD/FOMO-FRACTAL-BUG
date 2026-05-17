"""
Trust Service — Source trust scoring
=====================================
Computes and stores trust scores for each data source based on
success rate, data freshness, and consistency.
"""
from datetime import datetime, timezone
from intelligence_os.core.config import SOURCE_WEIGHTS
from intelligence_os.core.logging_config import get_logger

log = get_logger("trust")


class TrustService:
    def __init__(self, db):
        self.db = db
        self.col = db["ops_source_trust"]

    async def compute_trust(self, source: str) -> float:
        health = await self.db["ops_parser_health"].find_one(
            {"source": source}, {"_id": 0}
        )
        if not health:
            return SOURCE_WEIGHTS.get(source, 0.5)

        success = health.get("success_count", 0)
        failure = health.get("failure_count", 0)
        total = success + failure
        if total == 0:
            return SOURCE_WEIGHTS.get(source, 0.5)

        success_rate = success / total
        base_weight = SOURCE_WEIGHTS.get(source, 0.5)
        trust = round(base_weight * 0.6 + success_rate * 0.4, 4)
        return min(1.0, max(0.0, trust))

    async def update_trust(self, source: str):
        trust = await self.compute_trust(source)
        now = datetime.now(timezone.utc).isoformat()
        await self.col.update_one(
            {"source": source},
            {
                "$set": {"trust_score": trust, "updated_at": now},
                "$setOnInsert": {"source": source, "created_at": now},
            },
            upsert=True,
        )
        return trust

    async def get_all_trust(self) -> list[dict]:
        cursor = self.col.find({}, {"_id": 0}).sort("trust_score", -1)
        return await cursor.to_list(length=100)
