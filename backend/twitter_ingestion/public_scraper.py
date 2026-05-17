"""
L0 — Twitter Public Scraper (PRIMARY)
======================================
No cookies, no login, no Playwright.
Uses Twitter syndication endpoint to fetch public timeline data.
Returns structured tweets with tweet_id, text, tickers, metrics.

This is the MAIN source. Everything else is fallback.
"""
import asyncio
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional

import httpx

TICKER_RE = re.compile(r"(?:^|(?<!\w))\$([A-Z]{2,10})(?!\w)")
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

SYNDICATION_URL = "https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://x.com/",
}


@dataclass
class PublicTweet:
    username: str
    tweet_id: str
    text: str
    created_at: Optional[str]
    tickers: List[str]
    metrics: dict
    source: str = "public_scrape"


class TwitterPublicScraper:
    """
    L0 layer — primary source.
    Fetches public tweets via syndication endpoint.
    No auth, no cookies, no browser.
    """

    def __init__(self, timeout_sec: int = 15, proxy_url: str = None):
        self.timeout_sec = timeout_sec
        self.proxy_url = proxy_url
        self._rate_limited_until: float = 0

    @staticmethod
    def _validate_username(username: str) -> str:
        if not USERNAME_RE.match(username):
            raise ValueError(f"Invalid Twitter username: {username}")
        return username

    async def fetch_actor(self, username: str) -> List[PublicTweet]:
        username = self._validate_username(username)

        # Cooldown check — skip if recently rate-limited
        if self._rate_limited_until and datetime.now(timezone.utc).timestamp() < self._rate_limited_until:
            return []

        url = SYNDICATION_URL.format(username=username)

        async with httpx.AsyncClient(
            timeout=self.timeout_sec,
            headers=HEADERS,
            follow_redirects=True,
            proxy=self.proxy_url,
        ) as client:
            for attempt in range(3):
                try:
                    resp = await client.get(url)
                    if resp.status_code == 429:
                        # Rate limited — set cooldown (10 min)
                        self._rate_limited_until = datetime.now(timezone.utc).timestamp() + 600
                        return []
                    if resp.status_code != 200:
                        return []
                    html = resp.text
                    break
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        return []
            else:
                return []

        return self._parse_syndication_html(username, html)

    def _parse_syndication_html(self, username: str, html: str) -> List[PublicTweet]:
        """Extract __NEXT_DATA__ JSON from syndication HTML."""
        tweets: List[PublicTweet] = []

        match = re.search(
            r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
            html, re.DOTALL,
        )
        if not match:
            return tweets

        try:
            next_data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return tweets

        entries = (
            next_data
            .get("props", {})
            .get("pageProps", {})
            .get("timeline", {})
            .get("entries", [])
        )

        for entry in entries[:20]:
            if entry.get("type") != "tweet":
                continue

            tweet = entry.get("content", {}).get("tweet", {})
            if not tweet:
                continue

            text = tweet.get("full_text") or tweet.get("text", "")
            tweet_id = tweet.get("id_str", "")
            created_at = tweet.get("created_at")

            tickers = self._extract_tickers(text, tweet.get("entities", {}))
            metrics = {
                "likes": tweet.get("favorite_count", 0),
                "retweets": tweet.get("retweet_count", 0),
                "replies": tweet.get("reply_count", 0),
                "quotes": tweet.get("quote_count", 0),
            }

            tweets.append(PublicTweet(
                username=username,
                tweet_id=tweet_id,
                text=text,
                created_at=created_at,
                tickers=tickers,
                metrics=metrics,
            ))

        return tweets

    def _extract_tickers(self, text: str, entities: dict) -> List[str]:
        """Extract crypto tickers from text and entities."""
        tickers = set()

        # From entities.symbols (most reliable)
        for sym in entities.get("symbols", []):
            t = sym.get("text", "").upper()
            if t in CRYPTO_TOKENS:
                tickers.add(t)

        # From text via regex
        for m in TICKER_RE.finditer(text):
            t = m.group(1).upper()
            if t in CRYPTO_TOKENS:
                tickers.add(t)

        # Word boundary match
        upper = text.upper()
        for token in CRYPTO_TOKENS:
            if re.search(rf'\b{token}\b', upper):
                tickers.add(token)

        return sorted(tickers)

    async def save_to_db(self, db, tweets: List[PublicTweet]) -> int:
        """Save public tweets into actor_signal_events."""
        if not tweets:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        events = []

        for t in tweets:
            if not t.tickers:
                continue
            for ticker in t.tickers:
                events.append({
                    "actor_handle": t.username,
                    "tweet_id": t.tweet_id,
                    "text": t.text[:500],
                    "token": ticker,
                    "signal_type": "mention",
                    "source": "public_scrape",
                    "created_at": t.created_at or now,
                    "ingested_at": now,
                    "enriched": False,
                    "inferred": False,
                    "metrics": t.metrics,
                })

        if events:
            # Deduplicate by tweet_id+token
            existing = set()
            for e in events:
                key = f"{e['tweet_id']}_{e['token']}"
                if key in existing:
                    continue
                existing.add(key)

            # Check DB for existing tweet_ids
            tweet_ids = list({e["tweet_id"] for e in events})
            existing_docs = await db["actor_signal_events"].distinct(
                "tweet_id", {"tweet_id": {"$in": tweet_ids}}
            )
            existing_set = set(existing_docs)

            new_events = [e for e in events if e["tweet_id"] not in existing_set]
            if new_events:
                await db["actor_signal_events"].insert_many(new_events)
                return len(new_events)

        return 0
