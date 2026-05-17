"""
Twitter Watchdog — Monitors Twitter pipeline health
=====================================================
Checks every 15 minutes: are tweets flowing? Are sessions alive?
Classifies system state as OK / DEGRADED / DEAD.
"""
from datetime import datetime, timezone, timedelta
from intelligence_os.core.logging_config import get_logger

log = get_logger("ops.twitter_watchdog")


class TwitterWatchdog:
    def __init__(self, db):
        self.db = db

    async def check(self) -> dict:
        now = datetime.now(timezone.utc)
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        six_hours_ago = (now - timedelta(hours=6)).isoformat()

        # Tweet flow
        tweets_1h = await self.db["actor_signal_events"].count_documents(
            {"created_at": {"$gte": one_hour_ago}}
        )
        tweets_6h = await self.db["actor_signal_events"].count_documents(
            {"created_at": {"$gte": six_hours_ago}}
        )

        # Session health
        active_sessions = await self.db["twitter_sessions"].count_documents(
            {"status": {"$in": ["ACTIVE", "OK"]}}
        )
        stale_sessions = await self.db["twitter_sessions"].count_documents(
            {"status": "STALE"}
        )
        total_sessions = await self.db["twitter_sessions"].estimated_document_count()

        # Determine status
        if tweets_1h == 0 and tweets_6h == 0 and active_sessions == 0:
            status = "DEAD"
            reason = "NO_ACTIVE_SESSIONS_NO_TWEETS"
        elif tweets_1h == 0 and active_sessions == 0:
            status = "DEAD"
            reason = "NO_ACTIVE_SESSIONS"
        elif tweets_1h == 0 and tweets_6h > 0:
            status = "DEGRADED"
            reason = "NO_RECENT_TWEETS"
        elif active_sessions == 0 and tweets_1h > 0:
            status = "DEGRADED"
            reason = "SESSIONS_STALE_BUT_DATA_FLOWING"
        else:
            status = "OK"
            reason = None

        report = {
            "status": status,
            "reason": reason,
            "tweets_1h": tweets_1h,
            "tweets_6h": tweets_6h,
            "active_sessions": active_sessions,
            "stale_sessions": stale_sessions,
            "total_sessions": total_sessions,
            "checked_at": now.isoformat(),
        }

        log.info(f"[TWITTER WATCHDOG] {status} | tweets_1h={tweets_1h} tweets_6h={tweets_6h} sessions={active_sessions}/{total_sessions}")
        return report
