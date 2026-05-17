"""
Dataset V3 Builder — Unified Signal Dataset.
Assembles enriched events into production-grade training samples
with all context layers: text, sentiment, actor, market, signal, outcome, quality.
"""

from datetime import datetime, timezone, timedelta
from dqs import compute_dqs, dqs_bucket
from ml_ops import get_db


COLLECTION = "sentiment_training_dataset_v3"


def _safe(val, default=0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def build_dataset_row(enriched_event):
    """Build a v3 dataset row from an enriched_signal_events document."""
    e = enriched_event
    sentiment = e.get("sentiment", {})
    author = e.get("author_intel", {})
    price = e.get("price_context", {})
    outcome = e.get("outcome", {})

    # Compute freshness (seconds since signal to enrichment)
    ts = e.get("timestamp", "")
    enriched_at = e.get("enriched_at", "")
    freshness_sec = 300  # default 5min
    try:
        t1 = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        t2 = datetime.fromisoformat(str(enriched_at).replace("Z", "+00:00"))
        freshness_sec = max(0, (t2 - t1).total_seconds())
    except (ValueError, TypeError):
        pass

    row = {
        "meta": {
            "source": e.get("source", "twitter"),
            "source_id": e.get("tweet_id", ""),
            "created_at": ts,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "version": 3,
        },
        "text": {
            "raw": e.get("text", "")[:500],
            "tokens": [e.get("token", "")] if e.get("token") else [],
        },
        "sentiment": {
            "label": sentiment.get("sentiment_label", "NEUTRAL"),
            "score": _safe(sentiment.get("sentiment_score", 0)),
            "confidence": _safe(sentiment.get("confidence", 0)),
            "intent": sentiment.get("intent_label", "NOISE"),
            "uncertain": bool(sentiment.get("uncertainty_flag", False)),
        },
        "actor": {
            "handle": e.get("actor_handle", ""),
            "score": _safe(author.get("actor_score", 0)),
            "role": author.get("actor_role", "UNKNOWN"),
            "hit_rate": _safe(author.get("actor_hit_rate", 0)),
            "early_ratio": _safe(author.get("actor_early_ratio", 0)),
            "consistency": _safe(author.get("actor_consistency", 0)),
            "live_state": author.get("actor_live_state", "COLD"),
            "signal_count": int(author.get("actor_signal_count", 0)),
        },
        "market": {
            "token": e.get("token", ""),
            "price_at_signal": _safe(price.get("price_at_signal", 0)),
            "ret": {
                "m15": _safe(price.get("ret_15m", 0)),
                "h1": _safe(price.get("ret_1h", 0)),
                "h4": _safe(price.get("ret_4h", 0)),
                "h24": _safe(price.get("ret_24h", 0)),
            },
            "rel_ret": {
                "m15": _safe(price.get("ret_15m", 0)),  # same as ret for now (BTC relative later)
                "h1": _safe(price.get("btc_rel_1h", 0)) if price.get("btc_rel_1h") else _safe(price.get("ret_1h", 0)),
                "h4": _safe(price.get("btc_rel_4h", 0)) if price.get("btc_rel_4h") else _safe(price.get("ret_4h", 0)),
                "h24": _safe(price.get("btc_rel_24h", 0)) if price.get("btc_rel_24h") else _safe(price.get("ret_24h", 0)),
            },
            "regime": price.get("regime", "UNKNOWN"),
            "volatility": _safe(price.get("volatility", 0)),
            "momentum": _safe(1 if price.get("momentum") == "UP" else -1 if price.get("momentum") == "DOWN" else 0),
        },
        "signal": {
            "position": e.get("signal_position", "UNKNOWN"),
            "mentions_1h": 0,  # will be computed in signal enrichment
            "unique_actors_1h": 0,
            "coordination": 0,
            "freshness_sec": freshness_sec,
            "cluster_size_1h": 0,
        },
        "outcome": {
            "tradeable": None,
            "label": "UNRESOLVED",
            "pnl_1h": _safe(outcome.get("realized_return_1h")),
            "pnl_4h": _safe(outcome.get("realized_return_4h")),
            "pnl_24h": _safe(outcome.get("realized_return_24h")),
            "resolved": False,
            "resolved_at": None,
        },
        "quality": {},
    }

    # Compute signal metrics from DB (mentions, coordination)
    # This will be filled by enrich_signal_metrics()

    return row


async def enrich_signal_metrics(db, row):
    """Enrich signal block with coordination and mention metrics."""
    token = row["market"]["token"]
    ts = row["meta"]["created_at"]
    if not token or not ts:
        return row

    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        window_start = (t - timedelta(hours=1)).isoformat()
        window_end = t.isoformat()

        # Count mentions in 1h window
        mentions = await db.actor_signal_events.count_documents({
            "token": token,
            "timestamp": {"$gte": window_start, "$lte": window_end},
        })
        row["signal"]["mentions_1h"] = mentions

        # Unique actors in window
        actors = await db.actor_signal_events.distinct("actor_handle", {
            "token": token,
            "timestamp": {"$gte": window_start, "$lte": window_end},
        })
        row["signal"]["unique_actors_1h"] = len(actors)

        # Coordination = unique_actors / mentions (0=single, 1=all different)
        if mentions > 0:
            row["signal"]["coordination"] = round(len(actors) / mentions, 4)

        # Cluster size
        row["signal"]["cluster_size_1h"] = mentions

    except (ValueError, TypeError):
        pass

    return row


async def resolve_outcome(row):
    """Label the outcome based on price return."""
    pnl_1h = _safe(row["outcome"]["pnl_1h"])
    pnl_4h = _safe(row["outcome"]["pnl_4h"])
    pnl_24h = _safe(row["outcome"]["pnl_24h"])

    # Tradeable if 24h return > 2% (BTC-relative)
    if pnl_24h > 2.0:
        row["outcome"]["tradeable"] = True
        row["outcome"]["label"] = "GOOD"
    elif pnl_24h < -2.0:
        row["outcome"]["tradeable"] = False
        row["outcome"]["label"] = "BAD"
    else:
        row["outcome"]["tradeable"] = False
        row["outcome"]["label"] = "NEUTRAL"

    row["outcome"]["resolved"] = True
    row["outcome"]["resolved_at"] = datetime.now(timezone.utc).isoformat()

    return row


async def is_duplicate(db, row, window_hours=2):
    """Check if a similar signal already exists in dataset v3."""
    actor = row["actor"]["handle"]
    token = row["market"]["token"]
    ts = row["meta"]["created_at"]

    if not actor or not token or not ts:
        return False

    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        start = (t - timedelta(hours=window_hours)).isoformat()
        end = (t + timedelta(hours=window_hours)).isoformat()

        existing = await db[COLLECTION].find_one({
            "actor.handle": actor,
            "market.token": token,
            "meta.created_at": {"$gte": start, "$lte": end},
        })

        return existing is not None
    except (ValueError, TypeError):
        return False


async def build_dataset_v3(limit=100):
    """
    Build dataset v3 from enriched_signal_events.
    Full pipeline: build row → signal metrics → resolve outcome → DQS → dedup → insert.
    """
    db = get_db()

    # Get enriched events not yet in v3
    already = await db[COLLECTION].distinct("meta.source_id")
    query = {}
    if already:
        query["tweet_id"] = {"$nin": already}

    events = await db.enriched_signal_events.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    if not events:
        return {"ok": True, "processed": 0, "message": "no new events"}

    processed = 0
    duplicates = 0
    low_quality = 0
    errors = 0

    for event in events:
        try:
            # Build row
            row = build_dataset_row(event)

            # Enrich signal metrics
            row = await enrich_signal_metrics(db, row)

            # Resolve outcome
            row = await resolve_outcome(row)

            # Compute DQS
            dqs_val = compute_dqs(row)
            row["quality"]["dqs"] = dqs_val
            row["quality"]["bucket"] = dqs_bucket(dqs_val)
            row["quality"]["duplicate"] = False

            # Dedup check
            if await is_duplicate(db, row):
                duplicates += 1
                continue

            # Insert
            await db[COLLECTION].insert_one(row)
            processed += 1

            if dqs_val < 0.4:
                low_quality += 1

        except Exception:
            errors += 1

    return {
        "ok": True,
        "processed": processed,
        "duplicates": duplicates,
        "low_quality": low_quality,
        "errors": errors,
        "total_events": len(events),
    }


async def get_dataset_v3_stats():
    """Get dataset v3 statistics + data health."""
    db = get_db()
    col = db[COLLECTION]

    total = await col.count_documents({})
    if total == 0:
        return {"ok": True, "total": 0, "message": "empty dataset"}

    resolved = await col.count_documents({"outcome.resolved": True})
    tradeable = await col.count_documents({"outcome.tradeable": True})

    # DQS stats
    high = await col.count_documents({"quality.bucket": "HIGH"})
    medium = await col.count_documents({"quality.bucket": "MEDIUM"})
    low = await col.count_documents({"quality.bucket": "LOW"})

    avg_dqs = 0
    async for doc in col.aggregate([
        {"$group": {"_id": None, "avg": {"$avg": "$quality.dqs"}}}
    ]):
        avg_dqs = round(doc["avg"], 4) if doc["avg"] else 0

    # Distribution stats
    by_intent = {}
    async for doc in col.aggregate([
        {"$group": {"_id": "$sentiment.intent", "count": {"$sum": 1}}}
    ]):
        by_intent[doc["_id"]] = doc["count"]

    by_position = {}
    async for doc in col.aggregate([
        {"$group": {"_id": "$signal.position", "count": {"$sum": 1}}}
    ]):
        by_position[doc["_id"]] = doc["count"]

    by_role = {}
    async for doc in col.aggregate([
        {"$group": {"_id": "$actor.role", "count": {"$sum": 1}}}
    ]):
        by_role[doc["_id"]] = doc["count"]

    by_regime = {}
    async for doc in col.aggregate([
        {"$group": {"_id": "$market.regime", "count": {"$sum": 1}}}
    ]):
        by_regime[doc["_id"]] = doc["count"]

    # Unique actors and tokens
    unique_actors = len(await col.distinct("actor.handle"))
    unique_tokens = len(await col.distinct("market.token"))

    # Actor Gini (concentration)
    actor_counts = []
    async for doc in col.aggregate([
        {"$group": {"_id": "$actor.handle", "count": {"$sum": 1}}},
        {"$sort": {"count": 1}},
    ]):
        actor_counts.append(doc["count"])

    actor_gini = _compute_gini(actor_counts) if len(actor_counts) >= 2 else 0

    # Token Gini
    token_counts = []
    async for doc in col.aggregate([
        {"$group": {"_id": "$market.token", "count": {"$sum": 1}}},
        {"$sort": {"count": 1}},
    ]):
        token_counts.append(doc["count"])

    token_gini = _compute_gini(token_counts) if len(token_counts) >= 2 else 0

    return {
        "ok": True,
        "total": total,
        "resolved": resolved,
        "tradeable": tradeable,
        "tradeable_pct": round(tradeable / resolved * 100, 1) if resolved > 0 else 0,
        "quality": {
            "avg_dqs": avg_dqs,
            "high": high,
            "high_pct": round(high / total * 100, 1),
            "medium": medium,
            "low": low,
            "low_pct": round(low / total * 100, 1),
        },
        "distribution": {
            "by_intent": by_intent,
            "by_position": by_position,
            "by_role": by_role,
            "by_regime": by_regime,
        },
        "diversity": {
            "unique_actors": unique_actors,
            "unique_tokens": unique_tokens,
            "actor_gini": actor_gini,
            "token_gini": token_gini,
        },
    }


def _compute_gini(counts):
    """Compute Gini coefficient from sorted list of counts."""
    n = len(counts)
    total = sum(counts)
    if total == 0 or n < 2:
        return 0
    gini_sum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(counts))
    return round(gini_sum / (n * total), 4)


# ─── Feature extraction for ML training ───

def extract_features(row):
    """
    Extract production feature vector from a v3 dataset row.
    Returns dict of feature_name → value.
    NO label leakage (no ret_1h/4h/24h as features).
    """
    s = row.get("sentiment", {})
    a = row.get("actor", {})
    m = row.get("market", {})
    sig = row.get("signal", {})

    intent = s.get("intent", "NOISE")
    position = sig.get("position", "UNKNOWN")
    regime = m.get("regime", "RANGE")

    # A. Sentiment features
    f_intent_bullish = 1 if intent == "BULLISH_SIGNAL" else 0
    f_intent_bearish = 1 if intent == "BEARISH_SIGNAL" else 0
    f_intent_hype = 1 if intent == "HYPE" else 0
    f_intent_warning = 1 if intent == "WARNING" else 0
    f_sent_conf = _safe(s.get("confidence", 0))
    f_bullish_conf = f_sent_conf if f_intent_bullish else 0
    f_bearish_conf = f_sent_conf if f_intent_bearish else 0

    # B. Actor features
    f_actor_score = _safe(a.get("score", 0))
    f_actor_hit = _safe(a.get("hit_rate", 0))
    f_actor_early = _safe(a.get("early_ratio", 0))
    f_actor_consistency = _safe(a.get("consistency", 0))
    f_actor_hot = 1 if a.get("live_state") == "HOT" else 0
    f_actor_role_driver = 1 if a.get("role") == "DRIVER" else 0
    f_actor_role_amplifier = 1 if a.get("role") == "AMPLIFIER" else 0

    # C. Price context features (NO ret_1h/4h/24h — that's leakage!)
    f_volatility = _safe(m.get("volatility", 0))
    f_momentum = _safe(m.get("momentum", 0))
    f_regime_trending = 1 if regime == "TRENDING" else 0
    f_regime_overheated = 1 if regime == "OVERHEATED" else 0
    f_regime_range = 1 if regime == "RANGE" else 0

    # D. Signal structure
    f_mentions = _safe(sig.get("mentions_1h", 0))
    f_unique_actors = _safe(sig.get("unique_actors_1h", 0))
    f_coordination = _safe(sig.get("coordination", 0))
    f_cluster_size = _safe(sig.get("cluster_size_1h", 0))

    # E. Timing
    f_early = 1 if position == "EARLY" else 0
    f_mid = 1 if position == "MID" else 0
    f_late = 1 if position == "LATE" else 0

    # F. Composite alpha features
    f_actor_weighted_signal = f_actor_score * f_sent_conf
    f_momentum_alignment = _safe(s.get("score", 0)) * f_momentum
    f_signal_strength = f_mentions * f_coordination if f_mentions > 0 else 0
    f_early_bullish = f_early * f_intent_bullish
    f_alpha_1 = f_early * f_actor_score * f_sent_conf
    f_alpha_2 = f_actor_score * f_coordination
    f_alpha_3 = f_sent_conf * f_cluster_size
    f_alpha_4 = f_early * f_cluster_size * f_actor_score

    return {
        # Sentiment
        "f_intent_bullish": f_intent_bullish,
        "f_intent_bearish": f_intent_bearish,
        "f_intent_hype": f_intent_hype,
        "f_intent_warning": f_intent_warning,
        "f_sent_conf": round(f_sent_conf, 4),
        "f_bullish_conf": round(f_bullish_conf, 4),
        "f_bearish_conf": round(f_bearish_conf, 4),
        # Actor
        "f_actor_score": round(f_actor_score, 4),
        "f_actor_hit": round(f_actor_hit, 4),
        "f_actor_early": round(f_actor_early, 4),
        "f_actor_consistency": round(f_actor_consistency, 4),
        "f_actor_hot": f_actor_hot,
        "f_actor_role_driver": f_actor_role_driver,
        "f_actor_role_amplifier": f_actor_role_amplifier,
        # Price context (no ret leakage)
        "f_volatility": round(f_volatility, 4),
        "f_momentum": f_momentum,
        "f_regime_trending": f_regime_trending,
        "f_regime_overheated": f_regime_overheated,
        "f_regime_range": f_regime_range,
        # Signal
        "f_mentions": f_mentions,
        "f_unique_actors": f_unique_actors,
        "f_coordination": round(f_coordination, 4),
        "f_cluster_size": f_cluster_size,
        # Timing
        "f_early": f_early,
        "f_mid": f_mid,
        "f_late": f_late,
        # Alpha composites
        "f_actor_weighted_signal": round(f_actor_weighted_signal, 4),
        "f_momentum_alignment": round(f_momentum_alignment, 4),
        "f_signal_strength": round(f_signal_strength, 4),
        "f_early_bullish": f_early_bullish,
        "f_alpha_1": round(f_alpha_1, 4),
        "f_alpha_2": round(f_alpha_2, 4),
        "f_alpha_3": round(f_alpha_3, 4),
        "f_alpha_4": round(f_alpha_4, 4),
    }


async def get_data_health():
    """Anti-degradation: check if dataset quality is declining."""
    db = get_db()
    col = db[COLLECTION]

    total = await col.count_documents({})
    if total < 10:
        return {"ok": True, "status": "insufficient_data", "total": total}

    # Last 24h vs previous 7d
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(days=1)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()

    avg_dqs_24h = 0
    async for doc in col.aggregate([
        {"$match": {"meta.ingested_at": {"$gte": day_ago}}},
        {"$group": {"_id": None, "avg": {"$avg": "$quality.dqs"}}},
    ]):
        avg_dqs_24h = round(doc["avg"], 4) if doc["avg"] else 0

    avg_dqs_7d = 0
    async for doc in col.aggregate([
        {"$match": {"meta.ingested_at": {"$gte": week_ago, "$lt": day_ago}}},
        {"$group": {"_id": None, "avg": {"$avg": "$quality.dqs"}}},
    ]):
        avg_dqs_7d = round(doc["avg"], 4) if doc["avg"] else 0

    alerts = []
    if avg_dqs_24h > 0 and avg_dqs_7d > 0 and avg_dqs_24h < avg_dqs_7d * 0.85:
        alerts.append(f"DQS declining: 24h={avg_dqs_24h} vs 7d={avg_dqs_7d}")

    # Diversity checks
    stats = await get_dataset_v3_stats()
    diversity = stats.get("diversity", {})
    if diversity.get("actor_gini", 0) > 0.6:
        alerts.append(f"Actor concentration too high: gini={diversity['actor_gini']}")
    if diversity.get("token_gini", 0) > 0.6:
        alerts.append(f"Token concentration too high: gini={diversity['token_gini']}")

    return {
        "ok": True,
        "status": "degrading" if alerts else "healthy",
        "avg_dqs_24h": avg_dqs_24h,
        "avg_dqs_7d": avg_dqs_7d,
        "alerts": alerts,
        "total": total,
    }
