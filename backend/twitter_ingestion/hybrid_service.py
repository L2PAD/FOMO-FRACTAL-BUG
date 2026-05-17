"""
Twitter Hybrid Service — Unified Entry Point (V2)
==================================================
L0 (public scrape) → L1 (cookies) → L2 (playwright) → L3 (inference)

This is the ONLY way Twitter data enters the system.
"""
import asyncio
import random
from dataclasses import asdict
from datetime import datetime, timezone

from twitter_ingestion.public_scraper import TwitterPublicScraper
from twitter_ingestion.cookie_client import TwitterCookieClient
from twitter_ingestion.playwright_client import TwitterPlaywrightClient
from intelligence_os.ingestion.twitter.fallback_client import TwitterFallbackClient
from intelligence_os.core.logging_config import get_logger

log = get_logger("twitter.hybrid_v2")

MAX_ACTORS_PER_CYCLE = 20
DELAY_BETWEEN_ACTORS = (2, 6)


class TwitterHybridServiceV2:
    """
    4-layer cascade:
    L0 public scrape → L1 cookies → L2 playwright → L3 inference
    """

    def __init__(self, db):
        self.db = db
        # Load proxy from DB
        proxy_url = self._load_proxy(db)
        self.public_scraper = TwitterPublicScraper(proxy_url=proxy_url)
        self.cookie_client = TwitterCookieClient(db)
        self.playwright_client = TwitterPlaywrightClient()
        self.fallback_client = TwitterFallbackClient(db)
    
    @staticmethod
    def _load_proxy(db) -> str:
        """Load proxy URL from proxy_pool or networkconfigs collection."""
        try:
            # Try proxy_pool first (sync read for __init__)
            import pymongo
            sync_client = pymongo.MongoClient(
                db.client.address[0] if hasattr(db, 'client') else 'localhost',
                db.client.address[1] if hasattr(db, 'client') else 27017
            )
            sync_db = sync_client[db.name]
            
            proxy_doc = sync_db.proxy_pool.find_one({"enabled": True, "healthy": True})
            if proxy_doc:
                url = proxy_doc.get("server", "")
                username = proxy_doc.get("username", "")
                password = proxy_doc.get("password", "")
                if username and password and url and "@" not in url:
                    parts = url.split("://", 1)
                    url = f"{parts[0]}://{username}:{password}@{parts[1]}"
                if url:
                    log.info(f"[HYBRID] Proxy loaded: {url[:30]}...")
                    return url
            
            # Try networkconfigs
            net_cfg = sync_db.networkconfigs.find_one({})
            if net_cfg:
                pool = net_cfg.get("proxyPool", [])
                for p in pool:
                    if p.get("enabled") and p.get("url"):
                        log.info(f"[HYBRID] Proxy from networkconfigs: {p['url'][:30]}...")
                        return p["url"]
        except Exception as e:
            log.warning(f"[HYBRID] Failed to load proxy: {e}")
        return None

    async def fetch_actor(self, username: str) -> dict:
        """Fetch data for one actor through L0 → L1 → L2 → L3."""

        # L0 — Public Scrape (PRIMARY)
        try:
            tweets = await asyncio.wait_for(
                self.public_scraper.fetch_actor(username), timeout=20
            )
            if tweets:
                saved = await self.public_scraper.save_to_db(self.db, tweets)
                return {
                    "username": username,
                    "layer": "L0",
                    "source": "public_scrape",
                    "ok": True,
                    "tweets": len(tweets),
                    "tickers": list({t for tw in tweets for t in tw.tickers}),
                    "saved": saved,
                }
        except Exception as e:
            log.info(f"[HYBRID] {username}: L0 public scrape failed ({type(e).__name__})")

        # L1 — Cookies (SECONDARY)
        try:
            tokens = await asyncio.wait_for(
                self.cookie_client.fetch_actor(username), timeout=20
            )
            return {
                "username": username,
                "layer": "L1",
                "source": "twitter_kol",
                "ok": True,
                "tokens": tokens,
                "saved": len(tokens) if tokens else 0,
            }
        except Exception as e:
            log.info(f"[HYBRID] {username}: L1 cookies failed ({type(e).__name__})")

        # L2 — Playwright (RECOVERY)
        try:
            results = await asyncio.wait_for(
                self.playwright_client.fetch_actor(username), timeout=70
            )
            if results:
                saved = await self.playwright_client.save_to_db(self.db, results)
                return {
                    "username": username,
                    "layer": "L2",
                    "source": "playwright_scrape",
                    "ok": True,
                    "scraped": len(results),
                    "saved": saved,
                }
        except Exception as e:
            log.warning(f"[HYBRID] {username}: L2 playwright failed ({type(e).__name__}: {str(e)[:160]})")

        # L3 — Inference (BACKUP)
        try:
            results = await self.fallback_client.infer(username)
            saved = await self.fallback_client.save_inferred_to_db(results)
            return {
                "username": username,
                "layer": "L3",
                "source": "graph_inference",
                "ok": True,
                "inferred": len(results),
                "saved": saved,
            }
        except Exception as e:
            log.error(f"[HYBRID] {username}: ALL LAYERS FAILED — {e}")
            return {
                "username": username,
                "layer": "NONE",
                "source": "none",
                "ok": False,
                "error": str(e)[:200],
            }

    async def run_batch(self, actors: list[str]) -> dict:
        """Run hybrid ingestion for a batch of actors."""
        actors = actors[:MAX_ACTORS_PER_CYCLE]
        results = []
        sources = {"L0": 0, "L1": 0, "L2": 0, "L3": 0, "NONE": 0}

        log.info(f"[HYBRID V2] Starting batch: {len(actors)} actors")

        for actor in actors:
            result = await self.fetch_actor(actor)
            results.append(result)
            layer = result.get("layer", "NONE")
            sources[layer] = sources.get(layer, 0) + 1

            delay = random.uniform(*DELAY_BETWEEN_ACTORS)
            await asyncio.sleep(delay)

        ok_count = sum(1 for r in results if r.get("ok"))
        log.info(
            f"[HYBRID V2] Batch complete: {ok_count}/{len(actors)} OK | "
            f"L0={sources['L0']} L1={sources['L1']} "
            f"L2={sources['L2']} L3={sources['L3']} FAIL={sources['NONE']}"
        )

        return {
            "ok": True,
            "actors_total": len(actors),
            "actors_ok": ok_count,
            "sources": sources,
            "results": results,
        }
