"""
Notification Scanner — scans recent data for extreme OnChain and Sentiment conditions.

Called as a stage in the cron ingestion pipeline.
Emits events to the Unified Notification Engine when thresholds are breached.
"""
from datetime import datetime, timezone, timedelta


async def run_notification_scan(db) -> dict:
    """
    Scan recent data for notification-worthy conditions:
    1. OnChain: extreme signal scores from graph_signal_engine
    2. Sentiment: strong sentiment spikes from actor_signal_events
    3. Health: pipeline failures

    Returns summary of emitted events.
    """
    emitted = []

    try:
        onchain_results = await _scan_onchain_signals(db)
        emitted.extend(onchain_results)
    except Exception as e:
        emitted.append({"type": "onchain_scan_error", "error": str(e)})

    try:
        sentiment_results = await _scan_sentiment_spikes(db)
        emitted.extend(sentiment_results)
    except Exception as e:
        emitted.append({"type": "sentiment_scan_error", "error": str(e)})

    return {
        "events_emitted": len([e for e in emitted if e.get("emitted")]),
        "events_skipped": len([e for e in emitted if e.get("skipped")]),
        "details": emitted,
    }


async def _scan_onchain_signals(db) -> list:
    """
    Scan signal_log for recent extreme signals that indicate whale/smart money activity.
    Looks for: high confidence + strong directional signals in the last cycle.
    """
    from notifications.emit import emit_onchain_whale, emit_fractal_signal

    results = []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

    # Look for strong token signals from graph signal engine
    cursor = db.signal_log.find(
        {
            "created_at": {"$gte": cutoff},
            "signal_type": {"$in": ["whale_accumulation", "smart_money_entry", "large_flow", "fund_flow"]},
            "confidence": {"$gte": 0.6},
        },
        {"_id": 0}
    ).sort("created_at", -1).limit(10)

    seen_assets = set()
    async for signal in cursor:
        asset = signal.get("token") or signal.get("asset", "")
        if not asset or asset in seen_assets:
            continue
        seen_assets.add(asset)

        signal_type = signal.get("signal_type", "")
        confidence = signal.get("confidence", 0)
        details = signal.get("details", {})

        # Determine direction and wallet type
        direction = "outflow"
        wallet_type = "whale"
        if signal_type in ("smart_money_entry", "fund_flow"):
            wallet_type = "smart_money"
            direction = "inflow"
        elif signal_type == "whale_accumulation":
            direction = "inflow"

        amount = details.get("amount", details.get("volume", 0))
        value_usd = details.get("value_usd", amount * 50000)  # rough estimate if not provided

        # Only emit for significant amounts (> $3M)
        if value_usd < 3_000_000 and confidence < 0.8:
            results.append({"asset": asset, "skipped": True, "reason": f"value_usd={value_usd} < 3M"})
            continue

        r = await emit_onchain_whale(
            asset=asset.upper(),
            amount=amount,
            from_addr=details.get("from", ""),
            to_addr=details.get("to", ""),
        )
        results.append({"asset": asset, "emitted": not r.get("skipped", False), "type": signal_type})

    # Also check for extreme onchain scores from unified signal
    # Look for tokens with very high/low onchain scores
    recent_signals = db.signal_log.find(
        {
            "created_at": {"$gte": cutoff},
            "signal_type": "onchain_extreme",
            "confidence": {"$gte": 0.7},
        },
        {"_id": 0}
    ).sort("created_at", -1).limit(5)

    async for signal in recent_signals:
        asset = signal.get("token", "")
        if not asset or asset in seen_assets:
            continue
        seen_assets.add(asset)
        r = await emit_fractal_signal(asset.upper(), signal.get("signal_type", "extreme"), signal.get("details", {}))
        results.append({"asset": asset, "emitted": not r.get("skipped", False), "type": "onchain_extreme"})

    return results


async def _scan_sentiment_spikes(db) -> list:
    """
    Scan recent sentiment analysis for strong spikes.
    Compares recent sentiment average vs historical average.
    """
    from notifications.emit import emit_sentiment_spike

    results = []
    cutoff_recent = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    cutoff_baseline = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    # Get top tokens that have recent sentiment data
    pipeline = [
        {"$match": {
            "sentiment.sentiment_score": {"$exists": True, "$ne": None},
            "created_at": {"$gte": cutoff_recent},
        }},
        {"$group": {
            "_id": "$token",
            "avg_score": {"$avg": "$sentiment.sentiment_score"},
            "count": {"$sum": 1},
            "max_score": {"$max": "$sentiment.sentiment_score"},
            "min_score": {"$min": "$sentiment.sentiment_score"},
        }},
        {"$match": {"count": {"$gte": 3}}},  # Need at least 3 data points
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]

    recent_by_token = {}
    async for doc in db.actor_signal_events.aggregate(pipeline):
        token = doc["_id"]
        if token:
            recent_by_token[token] = doc

    # Compare with 24h baseline
    for token, recent in recent_by_token.items():
        baseline_pipeline = [
            {"$match": {
                "token": token,
                "sentiment.sentiment_score": {"$exists": True, "$ne": None},
                "created_at": {"$gte": cutoff_baseline, "$lt": cutoff_recent},
            }},
            {"$group": {
                "_id": None,
                "avg_score": {"$avg": "$sentiment.sentiment_score"},
                "count": {"$sum": 1},
            }},
        ]

        baseline_avg = 0
        async for doc in db.actor_signal_events.aggregate(baseline_pipeline):
            baseline_avg = doc.get("avg_score", 0)

        # Compute delta
        delta = recent["avg_score"] - baseline_avg

        # Only emit if delta is significant (> 0.2)
        if abs(delta) < 0.2:
            results.append({"asset": token, "skipped": True, "delta": round(delta, 3)})
            continue

        r = await emit_sentiment_spike(
            asset=token.upper(),
            delta=round(delta, 3),
            window="4h",
        )
        results.append({"asset": token, "emitted": not r.get("skipped", False), "delta": round(delta, 3)})

    return results
