"""
Twitter Hybrid Service — Unified Entry Point
==============================================
L1 (Cookies) → L2 (Playwright) → L3 (Fallback/Inference)

This is the ONLY way Twitter data enters the system.
"""
import asyncio
import random
from intelligence_os.ingestion.twitter.cookie_client import TwitterCookieClient
from intelligence_os.ingestion.twitter.playwright_client import TwitterPlaywrightClient
from intelligence_os.ingestion.twitter.fallback_client import TwitterFallbackClient
from intelligence_os.core.logging_config import get_logger

log = get_logger("twitter.hybrid")

# Rate limits
MAX_ACTORS_PER_CYCLE = 20
MAX_REQUESTS_PER_SESSION = 50
DELAY_BETWEEN_ACTORS = (3, 8)  # seconds


class TwitterHybridService:
    def __init__(self, db):
        self.db = db
        self.cookie_client = TwitterCookieClient(db)
        self.playwright_client = TwitterPlaywrightClient(db)
        self.fallback_client = TwitterFallbackClient(db)
        self._request_count = 0

    async def fetch_actor(self, username: str) -> dict:
        """Fetch data for one actor through L1 → L2 → L3."""
        import asyncio

        # L1 — Cookies (primary)
        try:
            tokens = await asyncio.wait_for(
                self.cookie_client.fetch_actor(username), timeout=20
            )
            return {
                "username": username,
                "source": "cookies",
                "ok": True,
                "tokens": tokens,
            }
        except Exception as e:
            log.info(f"[HYBRID] {username}: Cookie failed ({type(e).__name__}), trying Playwright")

        # L2 — Playwright (secondary)
        try:
            results = await asyncio.wait_for(
                self.playwright_client.fetch_actor(username), timeout=25
            )
            if results:
                saved = await self.playwright_client.save_scraped_to_db(results)
                return {
                    "username": username,
                    "source": "playwright",
                    "ok": True,
                    "scraped": len(results),
                    "saved": saved,
                }
        except Exception as e:
            log.info(f"[HYBRID] {username}: Playwright failed ({type(e).__name__}), using Fallback")

        # L3 — Fallback (backup)
        try:
            results = await self.fallback_client.infer(username)
            saved = await self.fallback_client.save_inferred_to_db(results)
            return {
                "username": username,
                "source": "fallback",
                "ok": True,
                "inferred": len(results),
                "saved": saved,
            }
        except Exception as e:
            log.error(f"[HYBRID] {username}: ALL METHODS FAILED — {e}")
            return {
                "username": username,
                "source": "none",
                "ok": False,
                "error": str(e)[:200],
            }

    async def run_batch(self, actors: list[str]) -> dict:
        """Run hybrid ingestion for a batch of actors."""
        actors = actors[:MAX_ACTORS_PER_CYCLE]
        results = []
        sources_used = {"cookies": 0, "playwright": 0, "fallback": 0, "none": 0}

        log.info(f"[HYBRID] Starting batch: {len(actors)} actors")

        for actor in actors:
            result = await self.fetch_actor(actor)
            results.append(result)
            sources_used[result["source"]] = sources_used.get(result["source"], 0) + 1

            # Rate limiting
            delay = random.uniform(*DELAY_BETWEEN_ACTORS)
            await asyncio.sleep(delay)

        ok_count = sum(1 for r in results if r.get("ok"))
        log.info(
            f"[HYBRID] Batch complete: {ok_count}/{len(actors)} OK | "
            f"cookies={sources_used['cookies']} playwright={sources_used['playwright']} "
            f"fallback={sources_used['fallback']} failed={sources_used['none']}"
        )

        return {
            "ok": True,
            "actors_total": len(actors),
            "actors_ok": ok_count,
            "sources": sources_used,
            "results": results,
        }
