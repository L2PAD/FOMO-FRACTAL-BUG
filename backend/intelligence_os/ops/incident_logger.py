"""
Incident Logger — Track all ingestion incidents
=================================================
Every DEGRADED or DEAD event is logged for audit trail.
"""
from datetime import datetime, timezone
from intelligence_os.core.logging_config import get_logger

log = get_logger("ops.incident")


class IncidentLogger:
    def __init__(self, db):
        self.db = db
        self.col = db["ingestion_incidents"]

    async def log_incident(self, kind: str, status: str, payload: dict, actions: list[str] = None):
        now = datetime.now(timezone.utc).isoformat()
        incident = {
            "kind": kind,
            "status": status,
            "payload": payload,
            "actions_taken": actions or [],
            "created_at": now,
        }
        await self.col.insert_one(incident)
        log.warning(f"[INCIDENT] {kind}/{status}: {actions}")

    async def get_recent(self, limit: int = 20) -> list[dict]:
        cursor = self.col.find(
            {}, {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_stats(self) -> dict:
        total = await self.col.estimated_document_count()
        dead_count = await self.col.count_documents({"status": "DEAD"})
        degraded_count = await self.col.count_documents({"status": "DEGRADED"})
        return {
            "total_incidents": total,
            "dead": dead_count,
            "degraded": degraded_count,
        }
