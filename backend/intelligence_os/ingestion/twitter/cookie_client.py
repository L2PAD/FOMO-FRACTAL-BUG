"""
Twitter Cookie Client (L1 — Primary)
=====================================
Uses existing twitter_ingestion.py to fetch tweets via cookies.
This is the fastest, most reliable method when cookies are valid.
"""
import sys
sys.path.insert(0, "/app/backend")

from intelligence_os.core.logging_config import get_logger

log = get_logger("twitter.cookie")


class TwitterCookieClient:
    def __init__(self, db):
        self.db = db

    async def fetch_actor(self, username: str, limit: int = 30) -> list[dict]:
        """Fetch tweets for an actor using cookie-based parser."""
        import asyncio

        # Check if any active sessions exist first
        active = await self.db["twitter_sessions"].count_documents({"status": {"$in": ["ACTIVE", "OK"]}})
        if active == 0:
            raise ConnectionError("No active Twitter sessions")

        # Check if parser service is reachable
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get("http://localhost:5001/health")
                if resp.status_code != 200:
                    raise ConnectionError("Twitter parser service not healthy")
        except Exception:
            raise ConnectionError("Twitter parser service not reachable at port 5001")

        from twitter_ingestion import ingest_actor_tweets
        result = await asyncio.wait_for(ingest_actor_tweets(username, limit), timeout=15)

        if not result.get("ok"):
            error = result.get("error", "Unknown error")
            log.warning(f"[COOKIE] {username}: FAIL — {error}")
            raise ConnectionError(f"Cookie client failed: {error}")

        signals = result.get("signals_created", 0)
        log.info(f"[COOKIE] {username}: OK, signals={signals}")
        return result.get("tokens_found", [])

    async def search(self, keyword: str, limit: int = 30) -> dict:
        """Search tweets by keyword."""
        from twitter_ingestion import ingest_search
        result = await ingest_search(keyword, limit)

        if not result.get("ok"):
            raise ConnectionError(f"Cookie search failed: {result.get('error')}")

        return result

    async def is_healthy(self) -> bool:
        """Check if cookie-based parsing is available."""
        session = await self.db["twitter_sessions"].find_one(
            {"status": "ACTIVE"}, {"_id": 0, "status": 1}
        )
        if not session:
            return False

        from twitter_ingestion import check_parser_health
        health = await check_parser_health()
        return health.get("ok", False)
