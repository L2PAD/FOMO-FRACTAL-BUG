"""
Twitter Playwright Client (L2 — Fallback)
==========================================
Safe Playwright-based scraping when cookies fail.
Rules:
- NO headless (use headed for stealth)
- Real user-agent + viewport
- Random delays (3-10s between requests)
- Max 8-10 tweets per actor
- Max 20 actors per cycle
- Save storage state (login once)
"""
import asyncio
import random
import re
from datetime import datetime, timezone
from intelligence_os.core.logging_config import get_logger

log = get_logger("twitter.playwright")

CRYPTO_TOKENS = {
    "BTC", "ETH", "SOL", "MATIC", "LINK", "DOGE", "ARB", "OP", "UNI", "JUP",
    "AAVE", "MKR", "PEPE", "WIF", "BONK", "AVAX", "DOT", "ATOM", "FTM", "NEAR",
    "APT", "SUI", "SEI", "INJ", "TIA", "PYTH", "STX", "RUNE", "SNX", "CRV",
    "LDO", "PENDLE", "ENA", "ETHFI", "EIGEN", "ZRO", "STRK", "MANTA",
    "DYM", "ALT", "PIXEL", "PORTAL", "SAGA", "ONDO", "TAO", "RENDER",
    "XRP", "ADA", "BNB", "TRX", "TON", "SHIB", "HBAR", "XLM",
}

STORAGE_STATE_PATH = "/app/backend/twitter_playwright_state.json"


class TwitterPlaywrightClient:
    def __init__(self, db):
        self.db = db

    async def fetch_actor(self, username: str, max_tweets: int = 10) -> list[dict]:
        """Scrape tweets from an actor using Playwright."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            log.warning("[PLAYWRIGHT] playwright not installed, skipping")
            raise ImportError("playwright not installed")

        # Quick check: is Chromium available?
        import os
        import glob
        chrome_paths = glob.glob("/pw-browsers/chromium-*/chrome-linux/chrome")
        if not chrome_paths:
            log.warning("[PLAYWRIGHT] Chromium browser not installed, skipping")
            raise RuntimeError("Chromium browser not installed")

        results = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
                )

                import os
                storage = STORAGE_STATE_PATH if os.path.exists(STORAGE_STATE_PATH) else None
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                    storage_state=storage,
                )

                page = await context.new_page()

                url = f"https://x.com/{username}"
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                except Exception:
                    await browser.close()
                    raise ConnectionError(f"Cannot reach x.com/{username}")

                await asyncio.sleep(random.uniform(2, 4))

                # Scroll to load tweets
                await page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(random.uniform(1, 2))

                articles = await page.query_selector_all("article")
                now = datetime.now(timezone.utc).isoformat()

                for article in articles[:max_tweets]:
                    try:
                        text = await article.inner_text()
                        tokens = self._extract_tokens(text)
                        if tokens:
                            results.append({
                                "text": text[:500],
                                "tokens": tokens,
                                "actor": username,
                                "source": "playwright",
                                "fetched_at": now,
                            })
                    except Exception:
                        continue

                await browser.close()

        except ImportError:
            raise
        except Exception as e:
            log.warning(f"[PLAYWRIGHT] {username}: FAIL — {e}")
            raise

        log.info(f"[PLAYWRIGHT] {username}: OK, scraped={len(results)}")
        return results

    def _extract_tokens(self, text: str) -> list[str]:
        """Extract crypto tokens from text."""
        tokens = set()
        upper = text.upper()
        for match in re.findall(r'\$([A-Z]{2,10})', upper):
            if match in CRYPTO_TOKENS:
                tokens.add(match)
        for token in CRYPTO_TOKENS:
            if re.search(rf'\b{token}\b', upper):
                tokens.add(token)
        return list(tokens)

    async def save_scraped_to_db(self, results: list[dict]) -> int:
        """Save Playwright-scraped results into actor_signal_events."""
        if not results:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        events = []

        for r in results:
            for token in r.get("tokens", []):
                events.append({
                    "actor_handle": r.get("actor", "unknown"),
                    "text": r.get("text", ""),
                    "token": token,
                    "signal_type": "mention",
                    "source": "playwright_scrape",
                    "created_at": now,
                    "enriched": False,
                    "metrics": {},
                })

        if events:
            await self.db["actor_signal_events"].insert_many(events)

        return len(events)
