"""
L2 — Twitter Playwright Client (RECOVERY ONLY)
===============================================
Uses Playwright with persistent context for session persistence.
NOT headless_shell — uses real Chromium.
Only activated when L0 + L1 both fail.
"""
import asyncio
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from intelligence_os.core.logging_config import get_logger

log = get_logger("twitter.playwright_v2")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")

CRYPTO_TOKENS = {
    "BTC", "ETH", "SOL", "MATIC", "LINK", "DOGE", "ARB", "OP", "UNI", "JUP",
    "AAVE", "MKR", "PEPE", "WIF", "BONK", "AVAX", "DOT", "ATOM", "FTM", "NEAR",
    "APT", "SUI", "SEI", "INJ", "TIA", "PYTH", "STX", "RUNE", "SNX", "CRV",
    "LDO", "PENDLE", "ENA", "ETHFI", "EIGEN", "ZRO", "STRK", "MANTA",
    "DYM", "ALT", "PIXEL", "PORTAL", "SAGA", "ONDO", "TAO", "RENDER",
    "XRP", "ADA", "BNB", "TRX", "TON", "SHIB", "HBAR", "XLM",
    "TRUMP", "DYDX", "BLUR", "HOP", "GTC", "FORTH", "ENS", "LOOKS",
}

USER_DATA_DIR = "/tmp/twitter-playwright-profile"


@dataclass
class ScrapedTweet:
    username: str
    tweet_id: str
    text: str
    tickers: List[str]
    created_at: Optional[str] = None
    source: str = "playwright_scrape"


class TwitterPlaywrightClient:
    """L2 — recovery only. Uses persistent context per-actor to avoid lock contention."""

    def __init__(self, user_data_dir: str = USER_DATA_DIR):
        self._base_dir = user_data_dir

    async def fetch_actor(self, username: str) -> List[ScrapedTweet]:
        if not USERNAME_RE.match(username):
            raise ValueError(f"Invalid username: {username}")

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("playwright not installed")

        # Per-actor persistent dir avoids cross-batch lock conflicts on
        # /tmp/twitter-playwright-profile/SingletonLock when the previous
        # chromium instance hasn't released the profile yet.
        import os as _os
        per_actor_dir = f"{self._base_dir}/{username.lower()}"
        Path(per_actor_dir).mkdir(parents=True, exist_ok=True)
        # Wipe stale singleton lock if any (left over from a SIGKILLed run)
        for stale in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            try:
                _os.unlink(_os.path.join(per_actor_dir, stale))
            except FileNotFoundError:
                pass
            except Exception:
                pass

        results: List[ScrapedTweet] = []

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=per_actor_dir,
                headless=True,
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-default-browser-check",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

            try:
                # Inject auth cookies from twitter_sessions (synced via Chrome extension)
                # so Playwright browses as the logged-in user — no 429 / no login wall.
                try:
                    import os as _os2
                    from motor.motor_asyncio import AsyncIOMotorClient
                    from dotenv import load_dotenv
                    load_dotenv("/app/backend/.env")
                    _client = AsyncIOMotorClient(_os2.environ.get("MONGO_URL", "mongodb://localhost:27017"))
                    _db = _client[_os2.environ.get("DB_NAME", "fomo_mobile")]
                    _sess = await _db.twitter_sessions.find_one({})
                    if _sess and _sess.get("cookies"):
                        pw_cookies = []
                        for c in _sess["cookies"]:
                            if not c.get("name") or c.get("value") in (None, "", "..."):
                                continue
                            pw_cookies.append({
                                "name": c["name"],
                                "value": c["value"],
                                "domain": c.get("domain") or ".x.com",
                                "path": c.get("path") or "/",
                                "secure": bool(c.get("secure", True)),
                                "httpOnly": bool(c.get("httpOnly", False)),
                                "sameSite": (c.get("sameSite") or "None").capitalize() if isinstance(c.get("sameSite"), str) else "None",
                            })
                        if pw_cookies:
                            # Normalize sameSite to Playwright's vocabulary
                            for c in pw_cookies:
                                ss = (c.get("sameSite") or "None").lower()
                                if ss in ("none", "no_restriction", "unspecified", ""):
                                    c["sameSite"] = "None"
                                elif ss in ("lax",):
                                    c["sameSite"] = "Lax"
                                elif ss in ("strict",):
                                    c["sameSite"] = "Strict"
                                else:
                                    c["sameSite"] = "None"
                            await context.add_cookies(pw_cookies)
                            log.info(f"[PLAYWRIGHT] {username}: injected {len(pw_cookies)} auth cookies")
                    _client.close()
                except Exception as _ce:
                    log.info(f"[PLAYWRIGHT] {username}: cookie injection skipped — {_ce}")

                page = context.pages[0] if context.pages else await context.new_page()

                try:
                    await page.goto(
                        f"https://x.com/{username}",
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                except Exception as e:
                    log.warning(f"[PLAYWRIGHT] {username}: navigation failed — {e}")
                    return results

                await page.wait_for_timeout(random.randint(2500, 5000))

                # Scroll to load tweets
                await page.evaluate("window.scrollBy(0, 600)")
                await page.wait_for_timeout(random.randint(1500, 3000))

                articles = await page.locator("article").all()

                for article in articles[:8]:
                    try:
                        text = (await article.inner_text()).strip()
                        if not text:
                            continue

                        # Extract tweet_id from status links
                        tweet_id = ""
                        links = await article.locator('a[href*="/status/"]').all()
                        for link in links:
                            href = await link.get_attribute("href")
                            if href and "/status/" in href:
                                tweet_id = href.split("/status/")[-1].split("?")[0]
                                break

                        tickers = self._extract_tickers(text)
                        results.append(ScrapedTweet(
                            username=username,
                            tweet_id=tweet_id,
                            text=text[:500],
                            tickers=tickers,
                        ))
                    except Exception:
                        continue

            finally:
                await context.close()

        log.info(f"[PLAYWRIGHT] {username}: scraped={len(results)}")
        return results

    def _extract_tickers(self, text: str) -> List[str]:
        tickers = set()
        upper = text.upper()
        for match in re.findall(r'\$([A-Z]{2,10})', upper):
            if match in CRYPTO_TOKENS:
                tickers.add(match)
        for token in CRYPTO_TOKENS:
            if re.search(rf'\b{token}\b', upper):
                tickers.add(token)
        return sorted(tickers)

    async def save_to_db(self, db, results: List[ScrapedTweet]) -> int:
        if not results:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        events = []

        for r in results:
            for ticker in r.tickers:
                events.append({
                    "actor_handle": r.username,
                    "tweet_id": r.tweet_id,
                    "text": r.text,
                    "token": ticker,
                    "signal_type": "mention",
                    "source": "playwright_scrape",
                    "created_at": now,
                    "ingested_at": now,
                    "enriched": False,
                    "inferred": False,
                    "metrics": {},
                })

        if events:
            await db["actor_signal_events"].insert_many(events)
        return len(events)
