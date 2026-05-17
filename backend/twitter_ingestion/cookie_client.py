"""
L1 — Twitter Cookie Client (SECONDARY)
=======================================
Uses twitter-parser-v2 (Node.js on port 5001) with active sessions.
Auto-rotates sessions, auto-expires stale ones.
NOT the primary source — L0 public scrape comes first.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import httpx

from intelligence_os.core.logging_config import get_logger

log = get_logger("twitter.cookie_v2")


class TwitterCookieClient:
    """L1 — cookie-based fetching via twitter-parser-v2."""

    def __init__(self, db, parser_url: str = "http://127.0.0.1:5001", timeout_sec: int = 20):
        self.db = db
        self.parser_url = parser_url
        self.timeout_sec = timeout_sec

    async def fetch_actor(self, username: str) -> list[dict]:
        """Fetch tweets for actor. Raises if no active sessions or parser down."""
        session = await self._get_next_active_session()
        if not session:
            raise RuntimeError("NO_ACTIVE_TWITTER_SESSION")

        if not await self._is_parser_alive():
            raise ConnectionError("twitter-parser-v2 not reachable")

        try:
            from twitter_ingestion_legacy import ingest_actor_tweets
            import asyncio
            result = await asyncio.wait_for(ingest_actor_tweets(username, 30), timeout=15)

            if not result.get("ok"):
                await self._mark_session_fail(session)
                raise ConnectionError(f"Cookie fetch failed: {result.get('error')}")

            await self._mark_session_ok(session)
            signals = result.get("signals_created", 0)
            log.info(f"[COOKIE] {username}: OK, signals={signals}")
            return result.get("tokens_found", [])

        except Exception as e:
            await self._mark_session_fail(session)
            raise

    async def _get_next_active_session(self) -> Optional[dict]:
        """Get the least-recently-used active session."""
        return await self.db["twitter_sessions"].find_one(
            {"status": {"$in": ["ACTIVE", "OK"]}},
            sort=[("last_used_at", 1)],
        )

    async def _is_parser_alive(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{self.parser_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def _mark_session_ok(self, session: dict):
        await self.db["twitter_sessions"].update_one(
            {"sessionId": session.get("sessionId")},
            {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()},
             "$inc": {"requests_made": 1, "success_count": 1}},
        )

    async def _mark_session_fail(self, session: dict):
        await self.db["twitter_sessions"].update_one(
            {"sessionId": session.get("sessionId")},
            {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()},
             "$inc": {"requests_made": 1, "fail_count": 1}},
        )

    async def expire_stale_sessions(self) -> int:
        """Auto-expire sessions that are old or have too many failures."""
        now = datetime.now(timezone.utc)
        stale_cutoff = (now - timedelta(days=2)).isoformat()

        result = await self.db["twitter_sessions"].update_many(
            {"$or": [
                {"last_validated_at": {"$lt": stale_cutoff}},
                {"fail_count": {"$gte": 5}},
            ]},
            {"$set": {"status": "STALE"}},
        )
        return result.modified_count
