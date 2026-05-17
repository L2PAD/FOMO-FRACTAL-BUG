"""
Twitter Sentiment Step
======================
Periodic task that:
  1. Pulls fresh tweets for a list of crypto actors via TwitterPublicScraper
     (level L0 — no auth, uses x.com syndication endpoint)
  2. Saves them into  actor_signal_events  (token + actor + text)
  3. Scores them with VADER → sentiment_events with source = "twitter_native"
     so the Sentiment runtime has a primary social signal.

Designed to be a single async step plugged into run_news_substrate.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app/backend")

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from twitter_ingestion.public_scraper import TwitterPublicScraper

log = logging.getLogger("twitter_sentiment_step")

# Default crypto actors — high-signal accounts. Extended on each tick with the
# admin-configured handles from twitter_parser_accounts.
DEFAULT_ACTORS: list[str] = [
    "elonmusk", "VitalikButerin", "cz_binance", "saylor",
    "CryptoHayes", "APompliano", "TheCryptoDog", "Pentosh1",
    "DocumentingBTC", "rektcapital", "AltcoinDailyio", "WatcherGuru",
    "BitMEXResearch", "balajis", "RaoulGMI", "WuBlockchain",
]

# Token aliases for plain-text mention → canonical symbol
TICKER_MAP: dict[str, str] = {
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH", "ether": "ETH",
    "solana": "SOL", "sol": "SOL",
    "cardano": "ADA", "ada": "ADA",
    "polygon": "MATIC", "matic": "MATIC",
    "chainlink": "LINK", "link": "LINK",
    "polkadot": "DOT", "dot": "DOT",
    "avalanche": "AVAX", "avax": "AVAX",
    "ripple": "XRP", "xrp": "XRP",
    "doge": "DOGE", "dogecoin": "DOGE",
    "shib": "SHIB", "shiba": "SHIB",
    "binance": "BNB", "bnb": "BNB",
    "arbitrum": "ARB", "arb": "ARB",
    "optimism": "OP", "op": "OP",
    "sui": "SUI", "aptos": "APT",
    "celestia": "TIA", "injective": "INJ",
    "sei": "SEI", "near": "NEAR",
    "cosmos": "ATOM", "atom": "ATOM",
    "litecoin": "LTC", "ltc": "LTC",
    "tron": "TRX", "trx": "TRX",
    "uniswap": "UNI", "uni": "UNI",
    "aave": "AAVE",
    "lido": "LDO", "ldo": "LDO",
    "pendle": "PENDLE",
    "gmx": "GMX",
    "dydx": "DYDX",
}

_analyzer = SentimentIntensityAnalyzer()


def _extract_symbols(text: str, tickers: list[str]) -> list[str]:
    syms: set[str] = set()
    for t in tickers or []:
        t = (t or "").strip().lstrip("$").upper()
        if t:
            syms.add(t)
    low = (text or "").lower()
    for word, sym in TICKER_MAP.items():
        if word in low:
            syms.add(sym)
    return sorted(syms)


def _score(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"compound": 0.0, "weighted": 0.5}
    s = _analyzer.polarity_scores(text)
    weighted = round((s["compound"] + 1.0) / 2.0, 4)
    if abs(weighted - 0.5) < 1e-3:
        weighted = 0.501
    s["weighted"] = weighted
    return s


async def _resolve_actors(db, extra_limit: int = 32) -> list[str]:
    """Combine default actor list with admin-configured Twitter handles."""
    actors: list[str] = list(DEFAULT_ACTORS)
    seen = {a.lower() for a in actors}

    try:
        cursor = db.twitter_parser_accounts.find(
            {"$or": [{"status": "ACTIVE"}, {"status": {"$exists": False}}]},
            {"_id": 0, "handle": 1, "username": 1},
        ).limit(extra_limit)
        async for a in cursor:
            handle = (a.get("handle") or a.get("username") or "").strip().lstrip("@")
            if handle and handle.lower() not in seen:
                actors.append(handle)
                seen.add(handle.lower())
    except Exception as e:
        log.warning(f"twitter_parser_accounts read failed: {e!r}")

    return actors


async def run_twitter_sentiment_tick(db, lookback_hours: int = 24, max_actors: int = 8) -> dict:
    """
    Run one ingest+score tick.
    Returns counts of fetched tweets, saved events and scored sentiments.

    Spacing: 6-10s random delay between actors to avoid x.com 429 throttle.
    Default cap: 8 actors per tick (paired with a 15-min substrate cycle this
    rotates through 30+ accounts inside an hour).
    """
    import asyncio
    import random
    from itertools import cycle

    actors = await _resolve_actors(db)
    # Rotate the starting position so subsequent ticks pick different actors
    state = db["twitter_tick_state"]
    cursor_doc = await state.find_one({"id": "cursor"})
    offset = int((cursor_doc or {}).get("offset", 0)) % max(1, len(actors))
    rotated = actors[offset:] + actors[:offset]
    batch = rotated[:max_actors]
    await state.update_one(
        {"id": "cursor"},
        {"$set": {"id": "cursor", "offset": (offset + max_actors) % max(1, len(actors))}},
        upsert=True,
    )

    log.info(f"twitter_sentiment_tick start | actors_in_batch={len(batch)} (offset={offset})")

    scraper = TwitterPublicScraper(timeout_sec=15)
    total_tweets = 0
    total_saved = 0
    sentiments_written = 0
    per_actor: list[dict] = []
    now = datetime.now(timezone.utc)

    for h in batch:
        try:
            tweets = await asyncio.wait_for(scraper.fetch_actor(h), timeout=20)
        except Exception as e:
            per_actor.append({"actor": h, "ok": False, "error": repr(e)[:160]})
            await asyncio.sleep(random.uniform(6, 10))
            continue

        # Fallback: if public (L0) returned nothing, try cookie-authed (L1).
        used_authed = False
        used_playwright = False
        if not tweets:
            try:
                from twitter_ingestion.authed_scraper import fetch_user_tweets_authed, AuthedTweet
                # Look up which session to use — prefer the admin-managed account
                sess = await db.twitter_sessions.find_one({}) or {}
                account_id = sess.get("accountId")
                if account_id:
                    # Cap L1 to 15s — twscrape can wait minutes for account quotas
                    # which would block the whole tick. Better to fail fast → L2.
                    authed = await asyncio.wait_for(
                        fetch_user_tweets_authed(db, h, account_id, limit=20),
                        timeout=15,
                    )
                    if authed:
                        used_authed = True
                        # Adapt AuthedTweet → PublicTweet shape so existing save path works
                        from twitter_ingestion.public_scraper import PublicTweet
                        tweets = [
                            PublicTweet(
                                tweet_id=t.tweet_id,
                                username=t.username,
                                text=t.text,
                                created_at=t.created_at,
                                metrics=t.metrics,
                                tickers=t.tickers,
                            )
                            for t in authed
                        ]
            except asyncio.TimeoutError:
                log.info(f"L1 authed timed out for {h} (>15s) → falling through to L2")
            except Exception as e:
                log.warning(f"authed_scraper failed for {h}: {e!r}")

        # L2 Playwright fallback — if L0 + L1 both empty, use the real browser
        # that already has the admin's Twitter cookies. This is the path the
        # MetaBrain hybrid pipeline uses; it must also feed sentiment_events.
        if not tweets:
            try:
                from twitter_ingestion.playwright_client import TwitterPlaywrightClient
                from twitter_ingestion.public_scraper import PublicTweet
                pw = TwitterPlaywrightClient()
                # Cap L2 at 60s — playwright + navigation + scroll typically 6-12s.
                scraped = await asyncio.wait_for(pw.fetch_actor(h), timeout=60)
                if scraped:
                    used_playwright = True
                    tweets = [
                        PublicTweet(
                            tweet_id=s.tweet_id or "",
                            username=s.username,
                            text=s.text,
                            created_at=s.created_at,
                            metrics={},
                            tickers=s.tickers,
                        )
                        for s in scraped
                    ]
            except asyncio.TimeoutError:
                log.info(f"L2 playwright timed out for {h} (>60s) → no tweets")
            except Exception as e:
                log.warning(f"playwright fallback failed for {h}: {e!r}")

        total_tweets += len(tweets)
        if not tweets:
            per_actor.append({"actor": h, "ok": True, "tweets": 0})
            await asyncio.sleep(random.uniform(6, 10))
            continue

        try:
            saved = await scraper.save_to_db(db, tweets)
        except Exception:
            saved = 0
        total_saved += saved

        # Score each tweet (independent of save) — even tweets with no tickers
        # contribute to the actor's general mood.
        per_tweet_writes = 0
        for t in tweets:
            text = t.text or ""
            tickers = list(t.tickers or [])
            symbols = _extract_symbols(text, tickers)
            if not symbols:
                continue
            s = _score(text)
            for sym in symbols:
                ev_id = hashlib.md5(
                    f"twitter_native:{t.username}:{t.tweet_id}:{sym}".encode()
                ).hexdigest()
                await db.sentiment_events.update_one(
                    {"id": ev_id},
                    {
                        "$set": {
                            "id": ev_id,
                            "symbol": sym,
                            "source": "twitter_native",
                            "type": "tweet",
                            "actorHandle": t.username,
                            "tweetId": t.tweet_id,
                            "url": f"https://x.com/{t.username}/status/{t.tweet_id}"
                                   if t.tweet_id else None,
                            "text": text[:300],
                            "weightedScore": s["weighted"],
                            "polarity": s.get("compound", 0.0),
                            "pos": s.get("pos", 0.0),
                            "neg": s.get("neg", 0.0),
                            "neu": s.get("neu", 0.0),
                            "createdAt": now,
                            "raw": {
                                "llm_analysis": {
                                    "engine": "vader",
                                    "compound": s.get("compound", 0.0),
                                    "pos": s.get("pos", 0.0),
                                    "neg": s.get("neg", 0.0),
                                    "neu": s.get("neu", 0.0),
                                },
                                "metrics": t.metrics,
                            },
                        }
                    },
                    upsert=True,
                )
                per_tweet_writes += 1

        sentiments_written += per_tweet_writes
        per_actor.append({
            "actor": h, "ok": True, "tweets": len(tweets),
            "saved_actor_events": saved, "sentiment_writes": per_tweet_writes,
            "via": ("L2_playwright" if used_playwright else
                    "L1_authed" if used_authed else "L0_public"),
        })
        await asyncio.sleep(random.uniform(6, 10))

    cutoff = now - timedelta(hours=lookback_hours)
    fresh = await db.sentiment_events.count_documents(
        {"source": "twitter_native", "createdAt": {"$gte": cutoff.replace(tzinfo=None)}}
    )

    log.info(
        f"twitter_sentiment_tick done | actors={len(actors)} "
        f"tweets={total_tweets} actor_events_saved={total_saved} "
        f"sentiment_writes={sentiments_written} fresh_24h={fresh}"
    )

    return {
        "ok": True,
        "actors": len(actors),
        "tweets_total": total_tweets,
        "actor_signal_events_saved": total_saved,
        "sentiment_events_written": sentiments_written,
        "twitter_native_24h": fresh,
        "per_actor_summary": per_actor[:8],  # cap for log size
    }
