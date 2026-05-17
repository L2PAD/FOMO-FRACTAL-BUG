"""
Recovery Manager — Automatic recovery actions
===============================================
When watchdog detects DEGRADED or DEAD state,
recovery manager takes automatic corrective actions.
"""
from datetime import datetime, timezone
from intelligence_os.core.logging_config import get_logger

log = get_logger("ops.recovery")


class RecoveryManager:
    def __init__(self, db):
        self.db = db

    async def recover(self, watchdog_report: dict) -> list[str]:
        actions = []
        twitter = watchdog_report.get("twitter", {})
        now = datetime.now(timezone.utc).isoformat()

        if twitter.get("status") == "DEAD":
            # 1. Switch to playwright mode
            await self._set_flag("twitter_mode", "PLAYWRIGHT")
            actions.append("SWITCHED_TO_PLAYWRIGHT")

            # 2. Flag session refresh needed
            if twitter.get("active_sessions", 0) == 0:
                await self._set_flag("twitter_session_refresh_needed", True)
                actions.append("FLAGGED_SESSION_REFRESH")

            # 3. Enable fallback ingestion
            await self._set_flag("fallback_ingestion_enabled", True)
            actions.append("ENABLED_FALLBACK_INGESTION")

        elif twitter.get("status") == "DEGRADED":
            # Reduce batch size to avoid burning sessions
            await self._set_flag("twitter_actor_batch_limit", 5)
            actions.append("REDUCED_BATCH_SIZE_TO_5")

            # If no active sessions but data flowing, keep playwright
            if twitter.get("active_sessions", 0) == 0:
                await self._set_flag("twitter_mode", "PLAYWRIGHT")
                actions.append("SWITCHED_TO_PLAYWRIGHT")

        elif twitter.get("status") == "OK":
            # Restore normal mode
            await self._set_flag("twitter_mode", "COOKIES")
            await self._set_flag("twitter_actor_batch_limit", 20)
            await self._set_flag("fallback_ingestion_enabled", False)
            actions.append("RESTORED_NORMAL_MODE")

        if actions:
            log.info(f"[RECOVERY] Actions taken: {actions}")

        return actions

    async def _set_flag(self, key: str, value):
        now = datetime.now(timezone.utc).isoformat()
        await self.db["system_flags"].update_one(
            {"key": key},
            {"$set": {"value": value, "updated_at": now}},
            upsert=True,
        )

    async def get_flag(self, key: str, default=None):
        doc = await self.db["system_flags"].find_one({"key": key}, {"_id": 0})
        return doc.get("value", default) if doc else default
