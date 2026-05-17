"""
Alert Boost — Resend + Accuracy enhancement layer.
====================================================
Two independent boosts, controlled by feature flags in miniapp_settings:

1. RESEND: If edge > 20% and alert not opened after 45min, resend once.
2. ACCURACY: Prepend "Model accuracy: 82%" line to all alerts.

Both are OFF by default. Enable via Admin Settings after A/B data collected.
"""

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("miniapp.alert_boost")

RESEND_DELAY_MINUTES = 45
RESEND_EDGE_THRESHOLD = 0.20
MAX_RESENDS_PER_ALERT = 1


async def get_boost_flags(db) -> dict:
    """Read boost flags from settings. Defaults to all OFF."""
    settings = await db.miniapp_settings.find_one({"type": "global"}, {"_id": 0})
    if not settings:
        return {"resend_enabled": False, "accuracy_enabled": False}
    boost = settings.get("boost", {})
    return {
        "resend_enabled": boost.get("resend_enabled", False),
        "accuracy_enabled": boost.get("accuracy_enabled", False),
    }


def inject_accuracy_line(text: str, accuracy_pct: int) -> str:
    """
    Inject 'Model accuracy: X%' line into alert text.
    Placed at the END of the message to reinforce trust without breaking first impulse.
    Does NOT change A/B variant logic — just adds a factual line.
    """
    if accuracy_pct <= 0:
        return text
    accuracy_line = f"\n\nModel accuracy: {accuracy_pct}%"
    return text.rstrip() + accuracy_line


async def process_resend_queue(db):
    """
    Check for unopened alerts sent > RESEND_DELAY_MINUTES ago.
    Resend once if edge > RESEND_EDGE_THRESHOLD.
    
    Returns stats dict. Does nothing if feature flag is off.
    """
    flags = await get_boost_flags(db)
    if not flags["resend_enabled"]:
        return {"status": "disabled", "resent": 0}

    from miniapp.edge_alerts import send_telegram_message, _edge_open_button, _upgrade_button

    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(minutes=RESEND_DELAY_MINUTES + 30)).isoformat()
    window_end = (now - timedelta(minutes=RESEND_DELAY_MINUTES)).isoformat()

    # Find alerts sent in the resend window
    candidates = await db.miniapp_alert_log.find({
        "sent_at": {"$gte": window_start, "$lte": window_end},
        "resent": {"$ne": True},
    }, {"_id": 0}).to_list(length=100)

    resent = 0
    skipped = 0

    for alert in candidates:
        chat_id = alert.get("chat_id")
        asset = alert.get("asset")
        if not chat_id or not asset:
            continue

        # Check if edge was strong enough
        edge_event = await db.ab_events.find_one({
            "user_id": chat_id,
            "event": "alert_sent",
            "meta.asset": asset,
        }, {"_id": 0}, sort=[("created_at", -1)])

        if not edge_event:
            continue

        edge_val = abs((edge_event.get("meta") or {}).get("edge", 0))
        if edge_val < RESEND_EDGE_THRESHOLD:
            skipped += 1
            continue

        # Check if already opened
        opened = await db.ab_events.count_documents({
            "user_id": chat_id,
            "event": "alert_opened",
            "meta.asset": asset,
        })
        if opened > 0:
            skipped += 1
            continue

        # Check resend limit
        already_resent = await db.miniapp_alert_log.count_documents({
            "chat_id": chat_id,
            "asset": asset,
            "type": "resend",
        })
        if already_resent >= MAX_RESENDS_PER_ALERT:
            skipped += 1
            continue

        # Resend with urgency text
        variant = edge_event.get("variant", "")
        text = (
            f"<b>Edge still active ({asset})</b>\n\n"
            f"Edge: {round(edge_val * 100, 1)}%\n"
            f"Signal has not been viewed\n\n"
            f"Edge expires soon"
        )

        is_pro = (edge_event.get("meta") or {}).get("is_pro", False)
        markup = _edge_open_button(asset, variant) if is_pro else _upgrade_button(variant)

        result = await send_telegram_message(chat_id, text, markup)
        if result.get("ok"):
            # Log the resend
            await db.miniapp_alert_log.insert_one({
                "chat_id": chat_id,
                "type": "resend",
                "asset": asset,
                "direction": alert.get("direction", ""),
                "sent_at": now.isoformat(),
                "original_sent_at": alert.get("sent_at"),
                "resent": True,
            })
            # Mark original as resent
            await db.miniapp_alert_log.update_one(
                {"chat_id": chat_id, "asset": asset, "sent_at": alert["sent_at"]},
                {"$set": {"resent": True}},
            )
            # Track A/B event
            from miniapp.ab_testing import track_event
            await track_event(db, chat_id, "alert_resent", variant, {
                "asset": asset, "edge": edge_val,
            })
            resent += 1
        else:
            logger.warning(f"Resend failed for {chat_id}: {result}")

    return {"status": "active", "resent": resent, "skipped": skipped, "candidates": len(candidates)}
