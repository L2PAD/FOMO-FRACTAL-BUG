"""
Twitter Ingestion Pipeline — Python
=====================================

1. Decrypt cookies from twitter_sessions (AES-256-GCM)
2. Use Twitter GraphQL API to search crypto keywords
3. Store tweets in twitter_results collection
4. Extract entities → update entity_graph mentions
5. Generate sentiment events

Requires: COOKIE_ENC_KEY in backend/.env
Target: 100-300 tweets per run
"""

import asyncio
import os
import sys
import json
import re
import time
import logging
import base64
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("TwitterPipeline")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

# Load COOKIE_ENC_KEY from backend .env
COOKIE_ENC_KEY = None
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith("COOKIE_ENC_KEY="):
                COOKIE_ENC_KEY = line.strip().split("=", 1)[1]
                break

if not COOKIE_ENC_KEY:
    COOKIE_ENC_KEY = os.environ.get("COOKIE_ENC_KEY", "")

# Crypto keywords to search for on Twitter
SEARCH_KEYWORDS = [
    "bitcoin", "ethereum", "solana", "crypto regulation",
    "DeFi", "NFT market", "web3", "L2 scaling",
    "crypto whale", "altcoin season", "stablecoin",
    "airdrop crypto", "blockchain funding",
]

# Entity extraction
CRYPTO_ENTITIES = {
    "bitcoin": "bitcoin", "btc": "bitcoin", "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana", "cardano": "cardano", "ada": "cardano",
    "polkadot": "polkadot", "dot": "polkadot", "avalanche": "avalanche", "avax": "avalanche",
    "polygon": "polygon", "matic": "polygon", "chainlink": "chainlink", "link": "chainlink",
    "uniswap": "uniswap", "uni": "uniswap", "aave": "aave", "maker": "maker", "mkr": "maker",
    "compound": "compound", "comp": "compound", "curve": "curve-finance", "crv": "curve-finance",
    "lido": "lido", "arbitrum": "arbitrum", "arb": "arbitrum", "optimism": "optimism", "op": "optimism",
    "base": "base", "sui": "sui", "aptos": "aptos", "apt": "aptos", "near": "near",
    "cosmos": "cosmos", "atom": "cosmos", "celestia": "celestia", "tia": "celestia",
    "starknet": "starknet", "zksync": "zksync", "eigenlayer": "eigenlayer",
    "pendle": "pendle", "gmx": "gmx", "dydx": "dydx", "injective": "injective",
    "sei": "sei", "mantle": "mantle", "blast": "blast", "monad": "monad",
    "binance": "binance", "bnb": "binance", "coinbase": "coinbase",
    "a16z": "a16z", "paradigm": "paradigm", "pantera": "pantera",
}

ENTITY_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in sorted(CRYPTO_ENTITIES.keys(), key=len, reverse=True)) + r')\b',
    re.IGNORECASE
)

# Twitter Parser V2 API (Playwright-based, runs on port 5001)
PARSER_V2_URL = os.environ.get("TWITTER_PARSER_URL", "http://localhost:5001")


def decrypt_session_cookies(encrypted_data: str) -> list:
    """Decrypt cookies from twitter_sessions using COOKIE_ENC_KEY"""
    if not COOKIE_ENC_KEY:
        logger.error("COOKIE_ENC_KEY not set!")
        return []
    try:
        parts = encrypted_data.split(':')
        if len(parts) != 3:
            return []
        iv = base64.b64decode(parts[0])
        tag = base64.b64decode(parts[1])
        ciphertext = base64.b64decode(parts[2])
        key = bytes.fromhex(COOKIE_ENC_KEY)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(iv, ciphertext + tag, None)
        cookies = json.loads(plaintext.decode('utf-8'))
        return cookies if isinstance(cookies, list) else cookies.get('cookies', [cookies])
    except Exception as e:
        logger.error(f"Cookie decryption failed: {e}")
        return []


def extract_entities(text: str) -> list:
    if not text:
        return []
    matches = ENTITY_PATTERN.findall(text.lower())
    return list(set(CRYPTO_ENTITIES[m.lower()] for m in matches if m.lower() in CRYPTO_ENTITIES))


def build_twitter_headers(cookies: list) -> dict:
    """Not needed for parser-v2 approach, kept for reference"""
    return {}


async def search_via_parser(client: httpx.AsyncClient, cookies: list, keyword: str, count: int = 20) -> list:
    """Search Twitter via parser-v2 Playwright service"""
    try:
        resp = await client.post(
            f"{PARSER_V2_URL}/search/{keyword}",
            json={"limit": count, "cookies": cookies},
            timeout=90,  # Playwright is slower than direct API
        )
        if resp.status_code == 403:
            logger.warning(f"[SEARCH] Blocked/auth error on '{keyword}': {resp.text[:200]}")
            return []
        if resp.status_code == 429:
            logger.warning(f"[SEARCH] Rate limited on '{keyword}'")
            return []
        if resp.status_code != 200:
            logger.warning(f"[SEARCH] HTTP {resp.status_code} for '{keyword}': {resp.text[:200]}")
            return []

        data = resp.json()
        if not data.get("ok"):
            logger.warning(f"[SEARCH] Parser error on '{keyword}': {data.get('error', '?')}")
            return []

        result = data.get("data", {})
        raw_tweets = result.get("tweets", [])

        tweets = []
        for t in raw_tweets:
            tweet_id = t.get("id") or t.get("tweetId", "")
            text = t.get("text", "")
            if not tweet_id or not text:
                continue

            author = t.get("author", {})
            tweets.append({
                "tweetId": str(tweet_id),
                "text": text,
                "username": author.get("username", t.get("username", "")),
                "displayName": author.get("name", t.get("displayName", "")),
                "likes": t.get("likes", 0),
                "reposts": t.get("reposts", t.get("retweets", 0)),
                "replies": t.get("replies", 0),
                "views": t.get("views", 0),
                "author": {
                    "id": author.get("id", ""),
                    "username": author.get("username", ""),
                    "name": author.get("name", ""),
                    "verified": author.get("verified", False),
                    "followers": author.get("followers", 0),
                },
                "tweetedAt": t.get("created_at", t.get("tweetedAt", "")),
                "keyword": keyword,
            })

        return tweets
    except httpx.TimeoutException:
        logger.warning(f"[SEARCH] Timeout for '{keyword}' (parser may be slow)")
        return []
    except Exception as e:
        logger.error(f"[SEARCH] Error for '{keyword}': {type(e).__name__}: {e}")
        return []


async def run_twitter_ingestion(db, max_keywords=10, tweets_per_keyword=20):
    """Main ingestion: search keywords -> save tweets"""
    logger.info("=" * 60)
    logger.info("TWITTER INGESTION — START")
    logger.info("=" * 60)

    # Get active session
    session = await db.twitter_sessions.find_one(
        {"status": "OK"},
        {"_id": 0},
        sort=[("lastSyncedAt", -1)]
    )
    if not session:
        logger.error("No active (OK) twitter sessions found!")
        return {"tweets": 0, "error": "NO_ACTIVE_SESSION"}

    logger.info(f"Using session: {session['sessionId']} (synced: {session['lastSyncedAt']})")

    cookies = decrypt_session_cookies(session["encryptedCookies"])
    if not cookies:
        logger.error("Failed to decrypt cookies!")
        return {"tweets": 0, "error": "DECRYPT_FAILED"}

    auth_token = next((c for c in cookies if c.get("name") == "auth_token"), None)
    ct0 = next((c for c in cookies if c.get("name") == "ct0"), None)
    logger.info(f"Cookies: {len(cookies)} total, auth_token={'YES' if auth_token else 'NO'}, ct0={'YES' if ct0 else 'NO'}")

    if not auth_token or not ct0:
        return {"tweets": 0, "error": "MISSING_AUTH"}

    # Check parser-v2 health
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            health = await client.get(f"{PARSER_V2_URL}/health", timeout=5)
            if health.status_code != 200:
                logger.error(f"Parser-v2 not healthy: {health.status_code}")
                return {"tweets": 0, "error": "PARSER_UNHEALTHY"}
            logger.info(f"Parser-v2: {health.json()}")
        except Exception as e:
            logger.error(f"Parser-v2 unreachable: {e}")
            return {"tweets": 0, "error": "PARSER_UNREACHABLE"}

    total_tweets = 0
    total_new = 0
    keywords_ok = 0
    keywords_failed = 0
    tweets_before = await db.twitter_results.count_documents({})

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for keyword in SEARCH_KEYWORDS[:max_keywords]:
            tweets = await search_via_parser(client, cookies, keyword, tweets_per_keyword)

            if not tweets:
                keywords_failed += 1
                continue

            keywords_ok += 1
            for tweet in tweets:
                entities = extract_entities(tweet["text"])
                doc = {
                    "ownerType": "SYSTEM",
                    "source": "SEARCH",
                    "query": keyword,
                    "tweetId": tweet["tweetId"],
                    "text": tweet["text"],
                    "username": tweet["username"],
                    "displayName": tweet["displayName"],
                    "likes": tweet["likes"],
                    "reposts": tweet["reposts"],
                    "replies": tweet["replies"],
                    "views": tweet["views"],
                    "author": tweet["author"],
                    "keyword": keyword,
                    "tweetedAt": tweet.get("tweetedAt"),
                    "parsedAt": datetime.now(timezone.utc),
                    "entities_mentioned": entities,
                    "entity_count": len(entities),
                }

                res = await db.twitter_results.update_one(
                    {"tweetId": tweet["tweetId"]},
                    {"$set": doc},
                    upsert=True,
                )
                total_tweets += 1
                if res.upserted_id:
                    total_new += 1

            logger.info(f"[SEARCH] '{keyword}': {len(tweets)} tweets")
            await asyncio.sleep(2)  # Rate limit

    tweets_after = await db.twitter_results.count_documents({})

    logger.info("=" * 50)
    logger.info("[TWITTER] INGESTION SUMMARY:")
    logger.info(f"  Keywords OK: {keywords_ok}/{max_keywords}")
    logger.info(f"  Keywords failed: {keywords_failed}")
    logger.info(f"  Tweets processed: {total_tweets}")
    logger.info(f"  Tweets NEW: {total_new}")
    logger.info(f"  DB before: {tweets_before}, after: {tweets_after}")
    logger.info(f"  Net new: {tweets_after - tweets_before}")
    logger.info("=" * 50)

    return {
        "tweets": total_tweets,
        "new": total_new,
        "keywords_ok": keywords_ok,
        "keywords_failed": keywords_failed,
    }


async def generate_twitter_signals(db):
    """Generate entity signals from tweets"""
    logger.info("[SIGNALS] Generating twitter entity signals...")
    now = datetime.now(timezone.utc)
    window_24h = now - timedelta(hours=24)

    entity_mentions = defaultdict(lambda: {"count": 0, "likes": 0, "views": 0})

    cursor = db.twitter_results.find(
        {"entity_count": {"$gt": 0}, "parsedAt": {"$gte": window_24h}},
        {"_id": 0, "entities_mentioned": 1, "likes": 1, "views": 1}
    )

    async for tweet in cursor:
        for entity in tweet.get("entities_mentioned", []):
            entity_mentions[entity]["count"] += 1
            entity_mentions[entity]["likes"] += tweet.get("likes", 0)
            entity_mentions[entity]["views"] += tweet.get("views", 0)

    signals_created = 0
    for entity, stats in entity_mentions.items():
        await db.sentiment_events.update_one(
            {"entity": entity, "source": "twitter"},
            {"$set": {
                "entity": entity,
                "source": "twitter",
                "type": "twitter_mentions",
                "mention_count_24h": stats["count"],
                "total_likes": stats["likes"],
                "total_views": stats["views"],
                "signal_strength": min(10, stats["count"] / 3),
                "updated_at": now,
            }},
            upsert=True,
        )
        signals_created += 1

    logger.info(f"[SIGNALS] Created {signals_created} twitter sentiment events")
    return signals_created


async def ensure_twitter_indexes(db):
    await db.twitter_results.create_index("tweetId", unique=True)
    await db.twitter_results.create_index("keyword")
    await db.twitter_results.create_index("parsedAt")
    await db.twitter_results.create_index("entities_mentioned")
    await db.twitter_results.create_index([("entity_count", -1)])
    await db.twitter_results.create_index([("likes", -1)])
    await db.twitter_results.create_index([("views", -1)])
    logger.info("[INDEXES] Twitter indexes created")


async def run_twitter_pipeline():
    start = time.time()
    logger.info("=" * 60)
    logger.info("TWITTER PIPELINE — START")
    logger.info("=" * 60)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    result = await run_twitter_ingestion(db, max_keywords=10, tweets_per_keyword=20)

    if result.get("error"):
        logger.error(f"Ingestion failed: {result['error']}")
        client.close()
        return result

    signals = await generate_twitter_signals(db)
    await ensure_twitter_indexes(db)

    logger.info("=" * 60)
    logger.info("TWITTER PIPELINE — RESULTS")
    logger.info("=" * 60)
    for col in ["twitter_results", "sentiment_events"]:
        cnt = await db[col].count_documents({})
        logger.info(f"  {col}: {cnt}")

    elapsed = time.time() - start
    logger.info(f"\nTotal time: {elapsed:.1f}s")
    logger.info("=" * 60)

    client.close()
    return result


if __name__ == "__main__":
    asyncio.run(run_twitter_pipeline())
