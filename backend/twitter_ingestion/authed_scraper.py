"""
Cookie-authenticated Twitter scraper.

Uses cookies stored in `twitter_sessions` (populated by the FOMO X Connect
Chrome extension via POST /api/v4/twitter/sessions/webhook) to authenticate
against the Twitter Web GraphQL endpoints. Falls back gracefully when the
account is rate-limited.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger("twitter_authed_scraper")

# Public-web bearer used by the official twitter.com SPA (well-known constant).
WEB_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)


@dataclass
class AuthedTweet:
    tweet_id: str
    username: str
    text: str
    created_at: str
    metrics: dict
    tickers: List[str]


async def _ensure_twscrape_account(api, account_id: str, cookies_kv: str) -> bool:
    """Add the account once, then ensure it's active in twscrape's pool."""
    try:
        info = await api.pool.accounts_info()
        if not any(a.get("username") == account_id for a in info):
            await api.pool.add_account(
                account_id, "pwd_placeholder", "mail_x", "mail_pwd",
                cookies=cookies_kv,
            )
            await api.pool.set_active(account_id, True)
        return True
    except Exception as e:
        log.warning(f"_ensure_twscrape_account: {e!r}")
        return False


def _safe_text(t) -> str:
    for attr in ("rawContent", "content", "text"):
        v = getattr(t, attr, None)
        if v:
            return str(v)
    return ""


async def fetch_user_tweets_authed(
    db,
    username: str,
    account_id: str,
    limit: int = 30,
) -> List[AuthedTweet]:
    """
    Pull recent tweets for `username` using the cookie-authenticated session
    of `account_id` (default = the one synced from the Chrome extension).

    Returns empty list on rate-limit / not-found — never raises.
    """
    try:
        from twscrape import API, gather  # type: ignore
    except Exception as e:
        log.warning(f"twscrape not available: {e!r}")
        return []

    sess = await db.twitter_sessions.find_one({"accountId": account_id})
    if not sess:
        sess = await db.twitter_sessions.find_one({})
    if not sess:
        return []

    cookies = sess.get("cookies") or []
    wanted = {"auth_token", "ct0", "kdt", "twid", "guest_id", "personalization_id"}
    cookies_kv = "; ".join(
        f"{c['name']}={c['value']}" for c in cookies
        if c.get("name") in wanted and c.get("value")
    )
    if not cookies_kv or "auth_token" not in cookies_kv:
        return []

    api = API()
    ok = await _ensure_twscrape_account(api, account_id, cookies_kv)
    if not ok:
        return []

    try:
        user = await api.user_by_login(username)
        if not user or not getattr(user, "id", None):
            log.info(f"user_by_login({username}) → no user")
            return []
        tweets = await gather(api.user_tweets(user.id, limit=limit))
    except Exception as e:
        log.warning(f"authed_scrape({username}) failed: {e!r}")
        return []

    out: List[AuthedTweet] = []
    for t in tweets:
        text = _safe_text(t)
        if not text:
            continue
        # Crude $TICKER extraction
        import re
        tickers = list({m.upper() for m in re.findall(r"\$([A-Z]{2,8})", text)})
        out.append(
            AuthedTweet(
                tweet_id=str(getattr(t, "id", "")),
                username=username,
                text=text,
                created_at=str(getattr(t, "date", "")),
                metrics={
                    "retweets": getattr(t, "retweetCount", 0),
                    "likes": getattr(t, "likeCount", 0),
                    "replies": getattr(t, "replyCount", 0),
                    "quotes": getattr(t, "quoteCount", 0),
                },
                tickers=tickers,
            )
        )
    return out
