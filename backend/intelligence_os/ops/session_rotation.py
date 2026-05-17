"""
Session Rotation — Rotate Twitter sessions for longevity
==========================================================
Round-robin through available sessions.
Track usage, mark stale when failed.
"""
from datetime import datetime, timezone
from intelligence_os.core.logging_config import get_logger

log = get_logger("ops.session_rotation")


class SessionRotation:
    def __init__(self, db):
        self.db = db

    async def get_next_session(self) -> dict | None:
        """Get the least-recently-used active session."""
        session = await self.db["twitter_sessions"].find_one(
            {"status": {"$in": ["ACTIVE", "OK"]}},
            sort=[("lastUsedAt", 1)],
        )
        return session

    async def mark_used(self, session_id: str):
        """Mark a session as recently used."""
        now = datetime.now(timezone.utc)
        await self.db["twitter_sessions"].update_one(
            {"sessionId": session_id},
            {
                "$set": {"lastUsedAt": now, "updatedAt": now},
                "$inc": {"metrics.successfulRequests24h": 1},
            },
        )

    async def mark_failed(self, session_id: str, error: str):
        """Mark a session failure."""
        now = datetime.now(timezone.utc)
        await self.db["twitter_sessions"].update_one(
            {"sessionId": session_id},
            {
                "$set": {
                    "lastError": {"code": "FETCH_FAILED", "message": error[:200], "at": now},
                    "updatedAt": now,
                },
                "$inc": {"metrics.parserErrors24h": 1},
            },
        )

    async def mark_stale(self, session_id: str):
        """Mark a session as stale."""
        now = datetime.now(timezone.utc)
        await self.db["twitter_sessions"].update_one(
            {"sessionId": session_id},
            {"$set": {"status": "STALE", "lastStatusChangeAt": now, "updatedAt": now}},
        )
        log.warning(f"[SESSION] Marked {session_id} as STALE")

    async def validate_all(self) -> dict:
        """Validate all sessions and mark stale ones."""
        cursor = self.db["twitter_sessions"].find({"status": "ACTIVE"})
        validated, stale_count = 0, 0

        async for session in cursor:
            validated += 1
            # Check warmth failures
            warmth_fails = session.get("metrics", {}).get("warmthFailures24h", 0)
            if warmth_fails > 50:
                await self.mark_stale(session["sessionId"])
                stale_count += 1

        return {"validated": validated, "newly_stale": stale_count}

    async def get_session_status(self) -> dict:
        active = await self.db["twitter_sessions"].count_documents({"status": {"$in": ["ACTIVE", "OK"]}})
        stale = await self.db["twitter_sessions"].count_documents({"status": "STALE"})
        total = await self.db["twitter_sessions"].estimated_document_count()
        return {"active": active, "stale": stale, "total": total}
