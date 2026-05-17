"""
Unified Notification Engine — API Routes

Events, Rules, Notifications (Bell + Feed).
"""
from fastapi import APIRouter
from notifications.events.event_bus import publish_event
from notifications.storage.event_repo import (
    get_recent_events, get_event_by_id, get_event_stats,
    ensure_indexes as event_ensure_indexes
)
from notifications.storage.rule_repo import (
    get_all_rules, update_rule, create_rule, delete_rule, seed_default_rules,
    ensure_indexes as rule_ensure_indexes
)
from notifications.storage.notification_repo import (
    get_ui_notifications, get_unread_count, mark_as_read, mark_all_read,
    get_notifications, get_notification_stats,
    ensure_indexes as notif_ensure_indexes
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ── Events ──

@router.post("/events/publish")
async def api_publish_event(body: dict):
    """Publish a new event into the notification bus."""
    result = await publish_event(body)
    return {"ok": True, "event": result}


@router.post("/events/onchain-whale")
async def api_emit_whale(body: dict):
    """Emit an OnChain whale transfer event. Requires: asset, amount. Optional: valueUsd, direction, walletType."""
    from notifications.emit import emit_onchain_whale
    asset = body.get("asset", "BTC")
    amount = float(body.get("amount", 0))
    value_usd = float(body.get("valueUsd", 0))

    # Filter: only significant
    if value_usd > 0 and value_usd < 3_000_000:
        return {"ok": True, "skipped": True, "reason": f"valueUsd={value_usd} < $3M threshold"}

    result = await emit_onchain_whale(
        asset=asset,
        amount=amount,
        from_addr=body.get("from", ""),
        to_addr=body.get("to", ""),
    )
    return {"ok": True, "event": result}


@router.post("/events/sentiment-spike")
async def api_emit_sentiment(body: dict):
    """Emit a sentiment spike event. Requires: asset, delta. Optional: window."""
    from notifications.emit import emit_sentiment_spike
    asset = body.get("asset", "BTC")
    delta = float(body.get("delta", 0))
    window = body.get("window", "4h")

    # Filter: only significant
    if abs(delta) < 0.2:
        return {"ok": True, "skipped": True, "reason": f"|delta|={abs(delta)} < 0.2 threshold"}

    result = await emit_sentiment_spike(asset=asset, delta=delta, window=window)
    return {"ok": True, "event": result}


@router.get("/events")
async def api_list_events(limit: int = 50, source: str = None, type: str = None):
    """List recent events with optional filters."""
    events = await get_recent_events(limit=limit, source=source, event_type=type)
    return {"ok": True, "count": len(events), "events": events}


@router.get("/events/{event_id}")
async def api_get_event(event_id: str):
    event = await get_event_by_id(event_id)
    if not event:
        return {"ok": False, "error": "Event not found"}
    return {"ok": True, "event": event}


@router.get("/events-stats")
async def api_event_stats():
    stats = await get_event_stats()
    return {"ok": True, "stats": stats}


# ── Rules ──

@router.get("/rules")
async def api_list_rules():
    """List all notification rules."""
    rules = await get_all_rules()
    return {"ok": True, "count": len(rules), "rules": rules}


@router.post("/rules")
async def api_create_rule(body: dict):
    """Create a custom notification rule."""
    import uuid
    if "id" not in body:
        body["id"] = f"rule_{uuid.uuid4().hex[:8]}"
    body.setdefault("isEnabled", True)
    body.setdefault("isBuiltin", False)
    rule = await create_rule(body)
    return {"ok": True, "rule": rule}


@router.put("/rules/{rule_id}")
async def api_update_rule(rule_id: str, body: dict):
    """Update a rule (enable/disable, change conditions, channels, etc.)."""
    ok = await update_rule(rule_id, body)
    return {"ok": ok}


@router.delete("/rules/{rule_id}")
async def api_delete_rule(rule_id: str):
    """Delete a custom rule (builtin rules cannot be deleted)."""
    ok = await delete_rule(rule_id)
    return {"ok": ok}


# ── Notifications (Bell / Feed) ──

@router.get("/feed")
async def api_notification_feed(audience: str = "user", limit: int = 20):
    """Get notifications for UI bell/feed."""
    notifications = await get_ui_notifications(audience=audience, limit=limit)
    unread = await get_unread_count(audience=audience)
    return {"ok": True, "unread": unread, "count": len(notifications), "notifications": notifications}


@router.get("/unread-count")
async def api_unread_count(audience: str = "user"):
    """Get unread notification count (for bell badge)."""
    count = await get_unread_count(audience=audience)
    return {"ok": True, "unread": count}


@router.post("/read/{notification_id}")
async def api_mark_read(notification_id: str):
    """Mark a single notification as read."""
    ok = await mark_as_read(notification_id)
    return {"ok": ok}


@router.post("/read-all")
async def api_mark_all_read(audience: str = "user"):
    """Mark all notifications as read for audience."""
    count = await mark_all_read(audience=audience)
    return {"ok": True, "marked": count}


@router.get("/stats")
async def api_notification_stats():
    """Dashboard stats for notifications."""
    stats = await get_notification_stats()
    return {"ok": True, "stats": stats}


# ── Init / Setup ──

@router.post("/init")
async def api_init():
    """Create indexes and seed default rules."""
    await event_ensure_indexes()
    await rule_ensure_indexes()
    await notif_ensure_indexes()
    await seed_default_rules()
    from notifications.storage.decision_history_repo import ensure_indexes as dh_ensure_indexes
    await dh_ensure_indexes()
    return {"ok": True, "message": "Indexes created, default rules seeded"}


@router.post("/scan")
async def api_run_scan():
    """Manually trigger notification scan (OnChain + Sentiment)."""
    import os
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    from notifications.notification_scanner import run_notification_scan
    result = await run_notification_scan(db)
    return {"ok": True, "result": result}


@router.get("/telegram/status")
async def api_telegram_status():
    """Check Telegram bot configuration status."""
    import os
    user_token = bool(os.environ.get("TG_BOT_TOKEN", ""))
    user_chat = bool(os.environ.get("TG_USER_CHAT_ID", ""))
    admin_token = bool(os.environ.get("TG_ADMIN_BOT_TOKEN", "") or os.environ.get("TG_BOT_TOKEN", ""))
    admin_chat = bool(os.environ.get("TG_ADMIN_CHAT_ID", ""))
    return {
        "ok": True,
        "user_bot": {"token_set": user_token, "chat_id_set": user_chat, "ready": user_token and user_chat},
        "admin_bot": {"token_set": admin_token, "chat_id_set": admin_chat, "ready": admin_token and admin_chat},
    }


@router.post("/telegram/test")
async def api_telegram_test(audience: str = "admin"):
    """Send a test message to Telegram. Use audience=user or audience=admin."""
    test_event = {
        "id": "test_event",
        "type": "system.health.warning" if audience == "admin" else "exchange.prediction.updated",
        "source": "system" if audience == "admin" else "exchange",
        "asset": "BTC",
        "severity": "medium",
        "title": "Test notification",
        "payload": {
            "message": "Telegram delivery test",
            "horizon": "7D",
            "direction": "bullish",
            "expectedMovePct": 2.5,
            "confidence": 0.65,
        },
    }
    test_notification = {"id": "test_ntf", "title": "Test", "message": "Test"}

    if audience == "admin":
        from notifications.delivery.telegram_admin import send_telegram_admin
        result = await send_telegram_admin(test_notification, test_event)
    else:
        from notifications.delivery.telegram_user import send_telegram_user
        result = await send_telegram_user(test_notification, test_event)

    return {"ok": True, "audience": audience, "result": result}


@router.get("/telegram/aggregation/status")
async def api_aggregation_status():
    """Get current Telegram aggregation buffer state."""
    from notifications.delivery.telegram_aggregator import get_buffer_status
    return {"ok": True, "buffer": get_buffer_status()}


@router.post("/telegram/aggregation/flush")
async def api_aggregation_flush():
    """Manually flush all aggregation buffers."""
    from notifications.delivery.telegram_aggregator import flush_all
    await flush_all()
    return {"ok": True, "message": "All buffers flushed"}


@router.post("/telegram/aggregation/test")
async def api_aggregation_test():
    """
    Test aggregation by buffering 3 different events for BTC,
    then flushing to produce a single aggregated message.
    """
    from notifications.delivery.telegram_aggregator import (
        buffer_telegram_event, _flush_asset
    )

    test_events = [
        {
            "id": "test_agg_1", "type": "exchange.prediction.updated",
            "source": "exchange", "asset": "BTC", "severity": "high",
            "payload": {"horizon": "7D", "direction": "bearish",
                        "expectedMovePct": -2.1, "confidence": 0.72},
        },
        {
            "id": "test_agg_2", "type": "onchain.whale.transfer",
            "source": "onchain", "asset": "BTC", "severity": "high",
            "payload": {"direction": "inflow", "amount": 1500,
                        "valueUsd": 5_000_000, "walletType": "whale"},
        },
        {
            "id": "test_agg_3", "type": "sentiment.spike",
            "source": "sentiment", "asset": "BTC", "severity": "medium",
            "payload": {"delta": -0.45, "window": "4h"},
        },
    ]

    for event in test_events:
        ntf = {"id": f"ntf_test_{event['id']}", "title": "Test", "message": "Test"}
        await buffer_telegram_event(ntf, event)

    await _flush_asset("BTC")
    return {"ok": True, "message": "3 BTC events buffered and flushed as aggregated message"}


# ── Decision History (static routes BEFORE dynamic {asset}) ──

@router.post("/decision/record")
async def api_record_decision(body: dict = None):
    """Record a single decision for an asset+horizon with entryPrice."""
    from notifications.decision_history import record_decision
    body = body or {}
    asset = body.get("asset", "BTC")
    horizon = body.get("horizon", "30D")
    result = await record_decision(asset, horizon)
    if "error" in result:
        return {"ok": False, **result}
    return {"ok": True, "decision": result}


@router.post("/decision/record-all")
async def api_record_all():
    """Record decisions for all assets × horizons (daily batch)."""
    from notifications.decision_history import record_all_decisions
    results = await record_all_decisions()
    errors = [r for r in results if "error" in r]
    saved = [r for r in results if "error" not in r]
    return {"ok": True, "saved": len(saved), "errors": len(errors), "results": results}


@router.post("/decision/evaluate")
async def api_evaluate_decisions():
    """Evaluate all matured pending decisions against real prices."""
    from notifications.decision_history import evaluate_pending
    result = await evaluate_pending()
    return {"ok": True, **result}


@router.get("/decision/history")
async def api_decision_history(asset: str = None, status: str = None, limit: int = 50):
    """Get decision history with optional filters."""
    from notifications.storage.decision_history_repo import get_history
    history = await get_history(asset=asset, status=status, limit=limit)
    return {"ok": True, "count": len(history), "history": history}


@router.get("/decision/stats")
async def api_decision_stats():
    """Get accuracy stats for the decision engine."""
    from notifications.storage.decision_history_repo import get_stats
    stats = await get_stats()
    return {"ok": True, **stats}


@router.get("/decision/feedback")
async def api_decision_feedback():
    """Get self-tuning feedback adjustments based on accuracy."""
    from notifications.decision_history import get_feedback_adjustments
    adjustments = await get_feedback_adjustments()
    return {"ok": True, **adjustments}


# ── Decision Engine ──

@router.get("/decision/{asset}")
async def api_decision(asset: str, horizon: str = "30D"):
    """Compute a multi-layer decision signal for an asset."""
    from notifications.decision_engine import compute_decision
    result = compute_decision(asset, horizon)
    return {"ok": True, **result}


@router.get("/decisions/overview")
async def api_decisions_overview():
    """Get decisions for all main assets × horizons."""
    from notifications.decision_engine import compute_decision
    assets = ["BTC", "ETH", "SOL"]
    horizons = ["24H", "7D", "30D"]
    overview = []
    for asset in assets:
        for h in horizons:
            d = compute_decision(asset, h)
            overview.append({
                "asset": d["asset"],
                "horizon": d["horizonRaw"],
                "decision": d["decision"],
                "confidence": d["confidence"],
                "score": d["score"],
                "reasoning": d["reasoning"],
            })
    return {"ok": True, "overview": overview}


@router.post("/decision/{asset}/send")
async def api_decision_send(asset: str, horizon: str = "30D"):
    """Compute decision AND send to Telegram."""
    from notifications.decision_engine import compute_decision
    result = compute_decision(asset, horizon)

    # Format Telegram message
    decision = result["decision"]
    decision_type = result.get("decisionType", "NORMAL")
    confidence = result["confidence"]
    score = result["score"]
    reasoning = result["reasoning"]
    fusion = result.get("components", {}).get("fusion", {})

    # Build header based on fusion strength
    if decision_type == "EXTREME":
        header = f"<b>{asset} EXTREME {decision} SIGNAL</b>"
    elif decision_type == "HIGH_CONVICTION":
        header = f"<b>{asset} HIGH CONVICTION {decision}</b>"
    else:
        header = f"<b>{asset} DECISION: {decision}</b>"

    lines = [
        header,
        f"Confidence: {confidence}%",
        f"Score: {score:+.1f}",
        "",
    ]
    for r in reasoning:
        lines.append(f"  {r}")

    # Add fusion summary
    if fusion.get("strength") not in (None, "normal"):
        alignment = fusion.get("direction", "")
        aligned = fusion.get("alignedSignals", 0)
        lines.append("")
        lines.append(f"→ {aligned} sources aligned {alignment}")

    text = "\n".join(lines)

    # Send to user Telegram
    delivery_result = {"skipped": True}
    try:
        from notifications.delivery.telegram_user import _send_tg
        import os
        token = os.environ.get("TG_BOT_TOKEN", "")
        chat_id = os.environ.get("TG_USER_CHAT_ID", "")
        if token and chat_id:
            delivery_result = await _send_tg(token, chat_id, text)
    except Exception as e:
        delivery_result = {"error": str(e)}

    result["telegram_sent"] = delivery_result.get("ok", False)
    return {"ok": True, **result}
