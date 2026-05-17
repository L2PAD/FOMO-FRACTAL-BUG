"""
Enrichment Layer — Phase 2
============================
Replaces PLACEHOLDER modules with real enrichment:
1. Price Context — market state at signal time
2. Author Intel — actor quality metrics
3. Unified enriched signal assembly

Creates `enriched_signal_events` collection with full context.
"""

from datetime import datetime, timezone, timedelta
from ml_ops import get_db


# ─── Price Context ───

async def enrich_price_context(db, token, timestamp_iso):
    """
    Get price context at signal time.
    Returns: price_at_signal, ret_15m/1h/4h/24h, btc_relative returns, regime.
    """
    ts_ms = _iso_to_ms(timestamp_iso)
    if not ts_ms:
        return None

    price_col = db.market_price_history

    # Get price at signal time (nearest within 15min)
    price_at_signal = await _find_nearest_price(price_col, token, ts_ms, tolerance_ms=15 * 60 * 1000)
    if not price_at_signal:
        return None

    # Get prices at various intervals
    ret_15m = await _compute_return(price_col, token, ts_ms, 15 * 60 * 1000, price_at_signal)
    ret_1h = await _compute_return(price_col, token, ts_ms, 60 * 60 * 1000, price_at_signal)
    ret_4h = await _compute_return(price_col, token, ts_ms, 4 * 60 * 60 * 1000, price_at_signal)
    ret_24h = await _compute_return(price_col, token, ts_ms, 24 * 60 * 60 * 1000, price_at_signal)

    # BTC relative (if token != BTC)
    btc_rel_1h = 0
    btc_rel_4h = 0
    btc_rel_24h = 0
    if token.upper() != "BTC":
        btc_at = await _find_nearest_price(price_col, "BTC", ts_ms, tolerance_ms=15 * 60 * 1000)
        if btc_at:
            btc_ret_1h = await _compute_return(price_col, "BTC", ts_ms, 60 * 60 * 1000, btc_at) or 0
            btc_ret_4h = await _compute_return(price_col, "BTC", ts_ms, 4 * 60 * 60 * 1000, btc_at) or 0
            btc_ret_24h = await _compute_return(price_col, "BTC", ts_ms, 24 * 60 * 60 * 1000, btc_at) or 0
            btc_rel_1h = (ret_1h or 0) - btc_ret_1h
            btc_rel_4h = (ret_4h or 0) - btc_ret_4h
            btc_rel_24h = (ret_24h or 0) - btc_ret_24h

    # Simple regime detection
    regime = _detect_regime(ret_1h, ret_4h, ret_24h)

    # Volatility (simple: max spread of returns)
    rets = [r for r in [ret_1h, ret_4h, ret_24h] if r is not None]
    volatility = max(rets) - min(rets) if len(rets) >= 2 else 0

    # Momentum
    momentum = "UP" if (ret_1h or 0) > 0.5 else "DOWN" if (ret_1h or 0) < -0.5 else "FLAT"

    return {
        "price_at_signal": round(price_at_signal, 6),
        "ret_15m": _safe_round(ret_15m),
        "ret_1h": _safe_round(ret_1h),
        "ret_4h": _safe_round(ret_4h),
        "ret_24h": _safe_round(ret_24h),
        "btc_rel_1h": round(btc_rel_1h, 4),
        "btc_rel_4h": round(btc_rel_4h, 4),
        "btc_rel_24h": round(btc_rel_24h, 4),
        "regime": regime,
        "volatility": round(volatility, 4),
        "momentum": momentum,
    }


def _detect_regime(ret_1h, ret_4h, ret_24h):
    """Simple regime classification."""
    r1 = ret_1h or 0
    r4 = ret_4h or 0
    r24 = ret_24h or 0

    spread = abs(r1) + abs(r4) + abs(r24)
    if spread > 15:
        return "VOLATILE"
    if r1 > 2 and r4 > 4:
        return "OVERHEATED"
    if abs(r24) > 3 and (r1 * r24 > 0):  # same direction
        return "TRENDING"
    return "RANGE"


# ─── Author Intel ───

async def enrich_author_intel(db, actor_handle):
    """
    Get author intelligence from actor_intelligence collection.
    Returns: actor_score, role, hit_rate, early_ratio, consistency, live_state.
    """
    intel = await db.actor_intelligence.find_one(
        {"actor_handle": actor_handle},
        {"_id": 0},
    )

    if not intel:
        return {
            "actor_score": 0,
            "actor_role": "UNKNOWN",
            "actor_hit_rate": 0,
            "actor_early_ratio": 0,
            "actor_avg_rel_return": 0,
            "actor_consistency": 0,
            "actor_signal_count": 0,
            "actor_live_state": "COLD",
        }

    hit_rate = intel.get("hit_rate_24h", 0)
    early_ratio = intel.get("early_ratio", 0)
    avg_ret = intel.get("avg_rel_ret_24h", 0)
    signal_count = intel.get("total_signals", 0)
    role = intel.get("role", "UNKNOWN")

    # Composite actor score
    score = (
        hit_rate * 0.35
        + early_ratio * 0.25
        + min(avg_ret / 5, 1.0) * 0.20
        + min(signal_count / 20, 1.0) * 0.10
        + (1.0 if role == "DRIVER" else 0.5 if role == "AMPLIFIER" else 0.2) * 0.10
    )

    # Consistency: how stable is the actor's performance
    consistency = min(signal_count / 10, 1.0) * hit_rate

    # Live state: based on recency
    last_seen = intel.get("computed_at")
    now = datetime.now(timezone.utc)
    if last_seen:
        try:
            ls = datetime.fromisoformat(str(last_seen).replace("Z", "+00:00"))
            hours_since = (now - ls).total_seconds() / 3600
            if hours_since < 24:
                live_state = "HOT"
            elif hours_since < 72:
                live_state = "NORMAL"
            else:
                live_state = "COLD"
        except (ValueError, TypeError):
            live_state = "COLD"
    else:
        live_state = "COLD"

    return {
        "actor_score": round(score, 4),
        "actor_role": role,
        "actor_hit_rate": round(hit_rate, 4),
        "actor_early_ratio": round(early_ratio, 4),
        "actor_avg_rel_return": round(avg_ret, 4),
        "actor_consistency": round(consistency, 4),
        "actor_signal_count": signal_count,
        "actor_live_state": live_state,
    }


# ─── Signal Position ───

async def compute_signal_position(db, token, timestamp_iso, window_hours=4):
    """
    Determine EARLY/MID/LATE/EXIT_ZONE based on when this signal
    appeared relative to other signals for the same token.
    """
    ts_ms = _iso_to_ms(timestamp_iso)
    if not ts_ms:
        return "UNKNOWN"

    window_start = ts_ms - window_hours * 3600 * 1000

    # Count signals before this one in the window
    before_count = await db.actor_signal_events.count_documents({
        "token": token,
        "timestamp": {"$gte": _ms_to_iso(window_start), "$lt": timestamp_iso},
    })

    # Count signals after this one in the window
    window_end = ts_ms + window_hours * 3600 * 1000
    after_count = await db.actor_signal_events.count_documents({
        "token": token,
        "timestamp": {"$gt": timestamp_iso, "$lte": _ms_to_iso(window_end)},
    })

    total = before_count + after_count + 1

    if total <= 1:
        return "EARLY"  # Only signal

    position_ratio = before_count / total

    if position_ratio < 0.2:
        return "EARLY"
    elif position_ratio < 0.5:
        return "MID"
    elif position_ratio < 0.8:
        return "LATE"
    else:
        return "EXIT_ZONE"


# ─── Unified Enrichment Pipeline ───

async def build_enriched_event(db, event, sentiment=None):
    """
    Build a fully enriched signal event with all context layers.
    """
    actor = event.get("actor_handle", "")
    token = event.get("token", "")
    ts = event.get("timestamp", "")

    # Parallel enrichment
    price_ctx = await enrich_price_context(db, token, ts)
    author_intel = await enrich_author_intel(db, actor)
    position = await compute_signal_position(db, token, ts)

    # Get sentiment if not provided
    if not sentiment:
        existing = await db.sentiment_inference_events.find_one(
            {"source_id": event.get("tweet_id", "")},
            {"_id": 0},
        )
        if existing:
            sentiment = {
                "sentiment_label": existing.get("sentiment_label", "NEUTRAL"),
                "sentiment_score": existing.get("sentiment_score", 0),
                "confidence": existing.get("confidence", 0),
                "intent_label": existing.get("intent_label", "NOISE"),
                "uncertainty_flag": existing.get("uncertainty_flag", False),
            }

    enriched = {
        "tweet_id": event.get("tweet_id", ""),
        "source": event.get("source", "unknown"),
        "text": event.get("text", "")[:500],
        "actor_handle": actor,
        "token": token,
        "timestamp": ts,
        "signal_type": event.get("signal_type", ""),
        # Sentiment block
        "sentiment": sentiment or {},
        # Actor block
        "author_intel": author_intel,
        # Price block
        "price_context": price_ctx or {},
        # Signal block
        "signal_position": position,
        # Outcome block (to be filled by outcome tracker)
        "outcome": {
            "realized_return_1h": price_ctx.get("ret_1h") if price_ctx else None,
            "realized_return_4h": price_ctx.get("ret_4h") if price_ctx else None,
            "realized_return_24h": price_ctx.get("ret_24h") if price_ctx else None,
            "btc_rel_24h": price_ctx.get("btc_rel_24h") if price_ctx else None,
            "tradeable": None,  # To be labeled
        },
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }

    return enriched


async def run_enrichment_pipeline(limit=50, skip_enriched=True):
    """
    Process actor_signal_events → enriched_signal_events.
    Only processes real (twitter_kol) events with sentiment.
    """
    db = get_db()

    ALLOWED_ML_SOURCES = ["twitter_kol", "public_scrape", "playwright_scrape"]
    query = {"source": {"$in": ALLOWED_ML_SOURCES}}
    if skip_enriched:
        already = await db.enriched_signal_events.distinct("tweet_id")
        if already:
            query["tweet_id"] = {"$nin": already}

    # Get the price data time range to prioritize events with available prices
    newest_obs = await db.exchange_observations.find_one(
        {"symbol": "BTCUSDT"},
        {"_id": 0, "timestamp": 1},
        sort=[("timestamp", -1)],
    )
    oldest_obs = await db.exchange_observations.find_one(
        {"symbol": "BTCUSDT"},
        {"_id": 0, "timestamp": 1},
        sort=[("timestamp", 1)],
    )

    if newest_obs and oldest_obs:
        from datetime import datetime as dt_cls
        newest_ts = dt_cls.fromtimestamp(newest_obs["timestamp"] / 1000, tz=timezone.utc).isoformat()
        oldest_ts = dt_cls.fromtimestamp(oldest_obs["timestamp"] / 1000, tz=timezone.utc).isoformat()
        query["timestamp"] = {"$gte": oldest_ts, "$lte": newest_ts}

    events = await db.actor_signal_events.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    if not events:
        return {"ok": True, "processed": 0, "message": "no events to process"}

    processed = 0
    errors = 0
    no_price = 0

    for event in events:
        try:
            enriched = await build_enriched_event(db, event)

            # Skip if no price context (can't learn from it)
            if not enriched.get("price_context"):
                no_price += 1
                continue

            await db.enriched_signal_events.update_one(
                {"tweet_id": enriched["tweet_id"]},
                {"$set": enriched},
                upsert=True,
            )
            processed += 1
        except Exception:
            errors += 1

    return {
        "ok": True,
        "processed": processed,
        "errors": errors,
        "no_price_data": no_price,
        "total_events": len(events),
    }


async def get_enrichment_stats():
    """Get stats on enriched signal events."""
    db = get_db()
    total = await db.enriched_signal_events.count_documents({})

    # By position
    positions = {}
    async for doc in db.enriched_signal_events.aggregate([
        {"$group": {"_id": "$signal_position", "count": {"$sum": 1}}}
    ]):
        positions[doc["_id"]] = doc["count"]

    # By actor role
    roles = {}
    async for doc in db.enriched_signal_events.aggregate([
        {"$group": {"_id": "$author_intel.actor_role", "count": {"$sum": 1}}}
    ]):
        roles[doc["_id"]] = doc["count"]

    # By regime
    regimes = {}
    async for doc in db.enriched_signal_events.aggregate([
        {"$group": {"_id": "$price_context.regime", "count": {"$sum": 1}}}
    ]):
        regimes[doc["_id"]] = doc["count"]

    # By sentiment intent
    intents = {}
    async for doc in db.enriched_signal_events.aggregate([
        {"$group": {"_id": "$sentiment.intent_label", "count": {"$sum": 1}}}
    ]):
        intents[doc["_id"]] = doc["count"]

    # Avg actor score
    avg_actor_score = 0
    async for doc in db.enriched_signal_events.aggregate([
        {"$group": {"_id": None, "avg": {"$avg": "$author_intel.actor_score"}}}
    ]):
        avg_actor_score = round(doc["avg"], 4) if doc["avg"] else 0

    return {
        "ok": True,
        "total": total,
        "by_position": positions,
        "by_actor_role": roles,
        "by_regime": regimes,
        "by_intent": intents,
        "avg_actor_score": avg_actor_score,
    }


# ─── Helpers ───

def _iso_to_ms(ts_str):
    """Convert ISO timestamp to milliseconds."""
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        return dt.timestamp() * 1000
    except (ValueError, TypeError):
        return None


def _ms_to_iso(ts_ms):
    """Convert milliseconds to ISO string."""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def _safe_round(val, decimals=4):
    """Safely round a value."""
    if val is None:
        return None
    return round(val, decimals)


async def _find_nearest_price(col, token, ts_ms, tolerance_ms=900000):
    """Find nearest price observation within tolerance."""
    db = get_db()
    symbol = token.upper() + "USDT"

    # Try exchange_observations first (uses 'symbol', 'timestamp', and nested 'market.price')
    for offset in [0, 300000, 900000, 3600000, 7200000, 14400000]:
        for sign in [1, -1]:
            target = ts_ms + sign * offset
            doc = await db.exchange_observations.find_one(
                {"symbol": symbol, "timestamp": {"$gte": target - 600000, "$lte": target + 600000}},
                {"_id": 0, "market.price": 1},
            )
            if doc and doc.get("market", {}).get("price"):
                return float(doc["market"]["price"])
            if offset == 0:
                break

    # Fallback: market_price_history (uses 'symbol', 'ts', and 'c' for close price)
    for offset in [0, 3600000, 7200000, 14400000, 86400000]:
        for sign in [1, -1]:
            target = ts_ms + sign * offset
            doc = await db.market_price_history.find_one(
                {"symbol": symbol, "ts": {"$gte": target - 7200000, "$lte": target + 7200000}},
                {"_id": 0, "c": 1},
            )
            if doc and doc.get("c"):
                return float(doc["c"])
            if offset == 0:
                break

    return None


async def _compute_return(col, token, base_ts_ms, delta_ms, base_price):
    """Compute return from base_ts to base_ts + delta."""
    if not base_price or base_price == 0:
        return None

    future_price = await _find_nearest_price(col, token, base_ts_ms + delta_ms)
    if future_price is None:
        return None

    return round((future_price - base_price) / base_price * 100, 4)
