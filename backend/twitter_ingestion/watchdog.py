"""
Twitter Watchdog V2 — Active Recovery Engine
=============================================
Not just monitoring — actively switches modes, restarts services,
expires stale sessions.

Runs every 15 minutes.
"""
import subprocess
from datetime import datetime, timezone, timedelta

from twitter_ingestion.cookie_client import TwitterCookieClient
from intelligence_os.core.logging_config import get_logger

log = get_logger("ops.twitter_watchdog_v2")


class TwitterWatchdogV2:
    """Active watchdog — monitors AND recovers."""

    def __init__(self, db):
        self.db = db
        self.cookie_client = TwitterCookieClient(db)

    async def run(self) -> dict:
        now = datetime.now(timezone.utc)
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        six_hours_ago = (now - timedelta(hours=6)).isoformat()

        # 1. Tweet flow metrics
        tweets_1h = await self.db["actor_signal_events"].count_documents(
            {"created_at": {"$gte": one_hour_ago}}
        )
        tweets_6h = await self.db["actor_signal_events"].count_documents(
            {"created_at": {"$gte": six_hours_ago}}
        )

        # 2. Source breakdown (last 6h)
        l0_count = await self.db["actor_signal_events"].count_documents(
            {"source": "public_scrape", "created_at": {"$gte": six_hours_ago}}
        )
        l1_count = await self.db["actor_signal_events"].count_documents(
            {"source": "twitter_kol", "created_at": {"$gte": six_hours_ago}}
        )
        l2_count = await self.db["actor_signal_events"].count_documents(
            {"source": "playwright_scrape", "created_at": {"$gte": six_hours_ago}}
        )
        l3_count = await self.db["actor_signal_events"].count_documents(
            {"source": "graph_inference", "created_at": {"$gte": six_hours_ago}}
        )

        # 3. Session health
        active_sessions = await self.db["twitter_sessions"].count_documents(
            {"status": {"$in": ["ACTIVE", "OK"]}}
        )
        stale_sessions = await self.db["twitter_sessions"].count_documents(
            {"status": "STALE"}
        )
        total_sessions = await self.db["twitter_sessions"].estimated_document_count()

        # 4. ACTION: Expire stale sessions
        expired = await self.cookie_client.expire_stale_sessions()
        if expired:
            log.info(f"[WATCHDOG] Auto-expired {expired} stale sessions")

        # 5. ACTION: Check parser health, restart if down
        parser_alive = await self._check_parser()
        if not parser_alive:
            log.warning("[WATCHDOG] Parser DOWN — attempting restart")
            await self._restart_parser()

        # 6. Determine status
        if tweets_1h == 0 and tweets_6h == 0:
            status = "DEAD"
            reason = "NO_DATA_FLOW"
        elif l0_count == 0 and l1_count == 0 and l2_count == 0:
            status = "DEGRADED"
            reason = "ONLY_INFERENCE"
        elif tweets_1h == 0:
            status = "DEGRADED"
            reason = "NO_RECENT_TWEETS"
        elif l0_count > 0:
            status = "OK"
            reason = None
        else:
            status = "OK"
            reason = None

        report = {
            "status": status,
            "reason": reason,
            "tweets_1h": tweets_1h,
            "tweets_6h": tweets_6h,
            "sources_6h": {
                "L0_public": l0_count,
                "L1_cookies": l1_count,
                "L2_playwright": l2_count,
                "L3_inference": l3_count,
            },
            "sessions": {
                "active": active_sessions,
                "stale": stale_sessions,
                "total": total_sessions,
            },
            "parser_alive": parser_alive,
            "sessions_expired": expired,
            "checked_at": now.isoformat(),
        }

        # 7. Log incident
        await self.db["ingestion_incidents"].insert_one({
            "kind": "twitter_watchdog_v2",
            "payload": report,
            "created_at": now.isoformat(),
        })

        log.info(
            f"[WATCHDOG V2] {status} | tweets_1h={tweets_1h} | "
            f"L0={l0_count} L1={l1_count} L2={l2_count} L3={l3_count} | "
            f"sessions={active_sessions}/{total_sessions} | parser={'UP' if parser_alive else 'DOWN'}"
        )

        return report

    async def _check_parser(self) -> bool:
        """Check if twitter-parser-v2 is alive."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get("http://127.0.0.1:5001/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def _restart_parser(self):
        """Attempt to restart parser via supervisor."""
        try:
            result = subprocess.run(
                ["sudo", "supervisorctl", "restart", "twitter-parser"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                log.info("[WATCHDOG] Parser restarted via supervisor")
            else:
                log.warning(f"[WATCHDOG] Supervisor restart failed: {result.stderr}")
        except Exception as e:
            log.warning(f"[WATCHDOG] Parser restart failed: {e}")
