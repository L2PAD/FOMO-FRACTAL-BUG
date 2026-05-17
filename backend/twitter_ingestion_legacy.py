"""
Twitter Ingestion Adapter — bridges Python backend to Node.js Twitter Parser v2.

Reads cookies from the existing config, calls the parser for real tweet data,
and inserts into actor_signal_events with source='real' / 'twitter_kol'.

The Node.js parser is at /app/connections-service/twitter-parser-v2/
and exposes:
  POST /search/:keyword  { cookies, limit, proxyUrl }
  POST /tweets/:username { cookies, limit, proxyUrl }
"""

import os
import json
import httpx
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

from ml_ops import get_db


def _parse_twitter_date(date_str):
    """Parse Twitter date format 'Wed Mar 25 02:23:09 +0000 2026' to ISO string."""
    if not date_str:
        return datetime.now(timezone.utc).isoformat()
    # Already ISO format
    if "T" in str(date_str):
        return str(date_str)
    try:
        # Twitter format: "Wed Mar 25 02:23:09 +0000 2026"
        dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.isoformat()
    except (ValueError, TypeError):
        pass
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except (ValueError, TypeError):
        pass
    return datetime.now(timezone.utc).isoformat()

# ─── Config ───

PARSER_URL = os.environ.get("TWITTER_PARSER_URL", "http://localhost:5001")

# Cookie locations to try (in priority order)
COOKIE_PATHS = [
    "/app/backend/cookies_decrypted.json",
    "/app/backend/cookies.json",
    "/app/connections-service/twitter-parser-v2/cookies/cookies.json",
]

# Known crypto tokens for extraction
CRYPTO_TOKENS = {
    "BTC", "ETH", "SOL", "MATIC", "LINK", "DOGE", "ARB", "OP", "UNI", "JUP",
    "AAVE", "MKR", "PEPE", "WIF", "BONK", "AVAX", "DOT", "ATOM", "FTM", "NEAR",
    "APT", "SUI", "SEI", "INJ", "TIA", "PYTH", "STX", "RUNE", "SNX", "CRV",
    "LDO", "PENDLE", "ENA", "ETHFI", "EIGEN", "ZRO", "STRK", "MANTA",
    "DYM", "ALT", "PIXEL", "PORTAL", "SAGA", "ONDO", "TAO", "RENDER",
    "XRP", "ADA", "BNB", "TRX", "TON", "SHIB", "HBAR", "XLM",
}

# Signal type keywords
CONVICTION_WORDS = ["bullish", "buying", "accumulating", "long", "moon", "pump", "send it", "aping", "all in", "load"]
WARNING_WORDS = ["bearish", "dump", "crash", "sell", "short", "rug", "scam", "overvalued", "exit"]


def _load_cookies():
    """Load Twitter cookies from known locations or decrypt from DB."""
    for path in COOKIE_PATHS:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    cookies = json.load(f)
                if isinstance(cookies, list) and len(cookies) > 0:
                    # Check it's not placeholder
                    first_val = cookies[0].get("value", "")
                    if first_val and first_val != "...":
                        return cookies
            except (json.JSONDecodeError, IOError):
                continue

    # Fallback: decrypt from DB
    try:
        return _decrypt_cookies_from_db()
    except Exception:
        pass

    return None


def _decrypt_cookies_from_db():
    """Decrypt cookies from twitter_sessions collection."""
    import base64
    from motor.motor_asyncio import AsyncIOMotorClient
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    mongo_url = os.environ.get("MONGO_URL", "").strip('"')
    enc_key = os.environ.get("COOKIE_ENC_KEY", "")
    if not mongo_url or not enc_key:
        return None

    import asyncio

    async def _decrypt():
        client = AsyncIOMotorClient(mongo_url)
        db_name = os.environ.get("DB_NAME", "intelligence_engine").strip('"')
        db = client[db_name]

        session = await db.twitter_sessions.find_one({"status": "OK"}, {"_id": 0, "encryptedCookies": 1})
        if not session:
            session = await db.twitter_sessions.find_one({}, {"_id": 0, "encryptedCookies": 1})
        if not session or not session.get("encryptedCookies"):
            return None

        encrypted = session["encryptedCookies"]
        parts = encrypted.split(":")
        if len(parts) != 3:
            return None

        iv = base64.b64decode(parts[0])
        auth_tag = base64.b64decode(parts[1])
        ciphertext = base64.b64decode(parts[2])
        key = bytes.fromhex(enc_key)

        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, auth_tag))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        cookies = json.loads(decrypted.decode("utf-8"))

        # Cache for next time
        with open("/app/backend/cookies_decrypted.json", "w") as f:
            json.dump(cookies, f)

        return cookies

    loop = asyncio.get_event_loop()
    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _decrypt())
            return future.result(timeout=10)
    else:
        return asyncio.run(_decrypt())


def _extract_tokens(text):
    """Extract crypto token mentions from tweet text."""
    tokens = set()
    upper_text = text.upper()

    # $TOKEN pattern
    for match in re.findall(r'\$([A-Z]{2,10})', upper_text):
        if match in CRYPTO_TOKENS:
            tokens.add(match)

    # Direct mention (word boundary)
    for token in CRYPTO_TOKENS:
        if re.search(rf'\b{token}\b', upper_text):
            tokens.add(token)

    return list(tokens)


def _classify_signal(text):
    """Classify tweet signal type."""
    t = text.lower()
    if any(w in t for w in WARNING_WORDS):
        return "warning"
    if any(w in t for w in CONVICTION_WORDS):
        return "conviction"
    return "mention"


async def check_parser_health():
    """Check if the Twitter parser Node.js service is running."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{PARSER_URL}/health")
            return resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e), "parser_url": PARSER_URL}


async def search_tweets(keyword, limit=50):
    """Search tweets via the Node.js parser."""
    cookies = _load_cookies()
    if not cookies:
        return {"ok": False, "error": "No valid Twitter cookies found", "checked_paths": COOKIE_PATHS}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{PARSER_URL}/search/{keyword}",
                json={"cookies": cookies, "limit": limit},
            )
            return resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def get_user_tweets(username, limit=50):
    """Get tweets from a specific user via the Node.js parser."""
    cookies = _load_cookies()
    if not cookies:
        return {"ok": False, "error": "No valid Twitter cookies found"}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{PARSER_URL}/tweets/{username}",
                json={"cookies": cookies, "limit": limit},
            )
            return resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def ingest_actor_tweets(username, limit=50):
    """Fetch tweets from an actor and ingest into actor_signal_events as real data."""
    result = await get_user_tweets(username, limit)
    if not result.get("ok"):
        return result

    # Handle nested response: data.tweets.tweets or data.tweets (list)
    raw_tweets = result.get("data", {}).get("tweets", [])
    if isinstance(raw_tweets, dict):
        tweets = raw_tweets.get("tweets", [])
    elif isinstance(raw_tweets, list):
        tweets = raw_tweets
    else:
        tweets = []

    if not tweets:
        return {"ok": True, "message": "No tweets returned", "username": username}

    db = get_db()
    events = []
    skipped = 0

    for tw in tweets:
        text = tw.get("text", "")
        tokens = _extract_tokens(text)
        if not tokens:
            skipped += 1
            continue

        author = tw.get("author", {})
        created_at = _parse_twitter_date(tw.get("createdAt"))

        for token in tokens:
            events.append({
                "tweet_id": tw.get("id", ""),
                "actor_handle": author.get("username", username),
                "actor_id": author.get("id", ""),
                "text": text[:500],
                "token": token,
                "timestamp": created_at,
                "signal_type": _classify_signal(text),
                "source": "twitter_kol",
                "metrics": {
                    "likes": tw.get("likes", 0),
                    "reposts": tw.get("reposts", 0),
                    "replies": tw.get("replies", 0),
                    "views": tw.get("views", 0),
                },
                "enriched": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    if events:
        # Dedup: check existing tweet_ids for this actor
        existing_ids = set(await db.actor_signal_events.distinct(
            "tweet_id",
            {"actor_handle": username}
        ))
        new_events = [e for e in events if e["tweet_id"] not in existing_ids]

        if new_events:
            await db.actor_signal_events.insert_many(new_events)

        return {
            "ok": True,
            "username": username,
            "tweets_fetched": len(tweets),
            "signals_created": len(new_events),
            "duplicates_skipped": len(events) - len(new_events),
            "no_token_skipped": skipped,
            "tokens_found": list(set(e["token"] for e in new_events)),
        }

    return {"ok": True, "username": username, "tweets_fetched": len(tweets), "signals_created": 0, "no_token_skipped": skipped}


async def ingest_search(keyword, limit=50):
    """Search for a keyword (e.g. '$SOL') and ingest results as real signals."""
    result = await search_tweets(keyword, limit)
    if not result.get("ok"):
        return result

    # Handle nested response: data.tweets or data (list)
    raw_data = result.get("data", {})
    if isinstance(raw_data, dict):
        raw_tweets = raw_data.get("tweets", [])
        if isinstance(raw_tweets, dict):
            tweets = raw_tweets.get("tweets", [])
        elif isinstance(raw_tweets, list):
            tweets = raw_tweets
        else:
            tweets = []
    elif isinstance(raw_data, list):
        tweets = raw_data
    else:
        tweets = []

    if not tweets:
        return {"ok": True, "message": "No tweets found", "keyword": keyword}

    db = get_db()
    events = []
    skipped = 0

    for tw in tweets:
        text = tw.get("text", "")
        tokens = _extract_tokens(text)
        if not tokens:
            skipped += 1
            continue

        author = tw.get("author", {})
        handle = author.get("username", "unknown")
        created_at = _parse_twitter_date(tw.get("createdAt"))

        for token in tokens:
            events.append({
                "tweet_id": tw.get("id", ""),
                "actor_handle": handle,
                "actor_id": author.get("id", ""),
                "text": text[:500],
                "token": token,
                "timestamp": created_at,
                "signal_type": _classify_signal(text),
                "source": "twitter_kol",
                "metrics": {
                    "likes": tw.get("likes", 0),
                    "reposts": tw.get("reposts", 0),
                    "replies": tw.get("replies", 0),
                    "views": tw.get("views", 0),
                },
                "enriched": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    if events:
        existing_ids = set(await db.actor_signal_events.distinct("tweet_id"))
        new_events = [e for e in events if e["tweet_id"] not in existing_ids]

        if new_events:
            await db.actor_signal_events.insert_many(new_events)

        return {
            "ok": True,
            "keyword": keyword,
            "tweets_fetched": len(tweets),
            "signals_created": len(new_events),
            "duplicates_skipped": len(events) - len(new_events),
            "no_token_skipped": skipped,
            "unique_actors": len(set(e["actor_handle"] for e in new_events)),
            "tokens_found": list(set(e["token"] for e in new_events)),
        }

    return {"ok": True, "keyword": keyword, "tweets_fetched": len(tweets), "signals_created": 0, "no_token_skipped": skipped}


async def mass_ingest_actors(actors_list, tweets_per_actor=30):
    """Ingest tweets from a list of actors. Returns aggregated results."""
    total_signals = 0
    total_fetched = 0
    errors = []
    per_actor = []

    for actor in actors_list:
        try:
            result = await ingest_actor_tweets(actor, tweets_per_actor)
            if result.get("ok"):
                created = result.get("signals_created", 0)
                total_signals += created
                total_fetched += result.get("tweets_fetched", 0)
                per_actor.append({"actor": actor, "signals": created, "ok": True})
            else:
                errors.append({"actor": actor, "error": result.get("error", "unknown")})
                per_actor.append({"actor": actor, "ok": False, "error": result.get("error")})
        except Exception as e:
            errors.append({"actor": actor, "error": str(e)})
            per_actor.append({"actor": actor, "ok": False, "error": str(e)})

    return {
        "ok": True,
        "actors_attempted": len(actors_list),
        "total_tweets_fetched": total_fetched,
        "total_signals_created": total_signals,
        "errors": errors,
        "per_actor": per_actor,
    }


async def get_ingestion_status():
    """Get current ingestion stats: real vs synthetic breakdown."""
    db = get_db()

    # Events breakdown
    total_events = await db.actor_signal_events.count_documents({})
    real_events = await db.actor_signal_events.count_documents({"source": "twitter_kol"})
    synth_events = await db.actor_signal_events.count_documents({"source": "expansion"})

    # Dataset breakdown
    total_ds = await db.signal_training_dataset_v2.count_documents({})
    real_ds = await db.signal_training_dataset_v2.count_documents({"source": {"$nin": ["expansion", "synthetic"]}})
    synth_ds = await db.signal_training_dataset_v2.count_documents({"source": {"$in": ["expansion", "synthetic"]}})

    # Unique actors
    real_actors = await db.actor_signal_events.distinct("actor_handle", {"source": "twitter_kol"})
    synth_actors = await db.actor_signal_events.distinct("actor_handle", {"source": "expansion"})

    return {
        "ok": True,
        "events": {
            "total": total_events,
            "real": real_events,
            "synthetic": synth_events,
            "real_pct": round(real_events / total_events * 100, 1) if total_events > 0 else 0,
        },
        "dataset": {
            "total": total_ds,
            "real": real_ds,
            "synthetic": synth_ds,
            "real_pct": round(real_ds / total_ds * 100, 1) if total_ds > 0 else 0,
        },
        "actors": {
            "real_unique": len(real_actors),
            "synth_unique": len(synth_actors),
            "overlap": len(set(real_actors) & set(synth_actors)),
        },
    }
