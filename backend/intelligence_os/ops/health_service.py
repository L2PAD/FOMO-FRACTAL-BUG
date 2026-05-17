"""
Health Service — Centralized parser health tracking
=====================================================
Tracks success/failure/latency for every parser run.
Persists to MongoDB ops_parser_health collection.
"""
from datetime import datetime, timezone
from intelligence_os.core.logging_config import get_logger

log = get_logger("health")


class HealthService:
    def __init__(self, db):
        self.db = db
        self.col = db["ops_parser_health"]

    async def mark_success(self, source: str, saved: int, duration_sec: float = 0):
        now = datetime.now(timezone.utc).isoformat()
        await self.col.update_one(
            {"source": source},
            {
                "$set": {
                    "last_success": now,
                    "last_saved": saved,
                    "last_duration_sec": round(duration_sec, 2),
                    "status": "OK",
                    "updated_at": now,
                },
                "$inc": {"success_count": 1, "total_saved": saved},
                "$setOnInsert": {"source": source, "created_at": now},
            },
            upsert=True,
        )
        log.info(f"[HEALTH] {source}: OK, saved={saved}, duration={duration_sec:.1f}s")

    async def mark_failure(self, source: str, error: str, duration_sec: float = 0):
        now = datetime.now(timezone.utc).isoformat()
        await self.col.update_one(
            {"source": source},
            {
                "$set": {
                    "last_failure": now,
                    "last_error": error[:500],
                    "last_duration_sec": round(duration_sec, 2),
                    "status": "FAIL",
                    "updated_at": now,
                },
                "$inc": {"failure_count": 1},
                "$setOnInsert": {"source": source, "created_at": now},
            },
            upsert=True,
        )
        log.warning(f"[HEALTH] {source}: FAIL, error={error[:100]}")

    async def get_status(self, source: str) -> dict | None:
        return await self.col.find_one({"source": source}, {"_id": 0})

    async def get_all_statuses(self) -> list[dict]:
        cursor = self.col.find({}, {"_id": 0}).sort("source", 1)
        return await cursor.to_list(length=100)

    async def get_summary(self) -> dict:
        statuses = await self.get_all_statuses()
        ok = sum(1 for s in statuses if s.get("status") == "OK")
        fail = sum(1 for s in statuses if s.get("status") == "FAIL")
        return {
            "total_sources": len(statuses),
            "ok": ok,
            "fail": fail,
            "sources": statuses,
        }
