"""
Notification Service — creates notification objects from events + rules,
then dispatches to delivery channels (UI, Telegram user, Telegram admin).
"""
import uuid
from datetime import datetime, timezone

from notifications.notifications.notification_templates import build_template
from notifications.storage.notification_repo import save_notification, check_notification_dedupe


async def create_notifications_for_rule(event: dict, rule: dict) -> list:
    """
    For a matched rule, create one notification per channel.
    Returns list of saved notification dicts.
    """
    templated = build_template(event, rule.get("audience", "user"))
    channels = rule.get("channels", ["ui"])
    cooldown = rule.get("cooldownMinutes", 60)
    created = []

    for channel in channels:
        dedupe_key = f"{event.get('dedupeKey', event['id'])}:{rule.get('audience', 'user')}:{channel}"

        if await check_notification_dedupe(dedupe_key, cooldown):
            continue

        notification = {
            "id": f"ntf_{uuid.uuid4().hex[:12]}",
            "eventId": event["id"],
            "eventType": event["type"],
            "audience": rule.get("audience", "user"),
            "channel": channel,
            "status": "pending",
            "title": templated["title"],
            "message": templated["message"],
            "priority": event.get("severity", "medium"),
            "asset": event.get("asset"),
            "source": event.get("source"),
            "dedupeKey": dedupe_key,
            "ruleId": rule.get("id"),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "sentAt": None,
            "readAt": None,
        }

        saved = await save_notification(notification)

        # Dispatch to delivery channel
        await _deliver(saved, event, channel)

        created.append(saved)

    return created


async def _deliver(notification: dict, event: dict, channel: str):
    """Route notification to the right delivery channel."""
    from notifications.storage.notification_repo import _col
    now = datetime.now(timezone.utc).isoformat()

    if channel == "ui":
        await _col().update_one(
            {"id": notification["id"]},
            {"$set": {"status": "sent", "sentAt": now}}
        )
        notification["status"] = "sent"

    elif channel == "telegram_user":
        try:
            from notifications.delivery.telegram_aggregator import buffer_telegram_event
            await buffer_telegram_event(notification, event)
            # Status will be updated by aggregator when flush happens
            notification["status"] = "buffered"
        except Exception as e:
            # Fallback: send directly if aggregator fails
            try:
                from notifications.delivery.telegram_user import send_telegram_user
                result = await send_telegram_user(notification, event)
                if result.get("ok") and not result.get("skipped"):
                    await _col().update_one(
                        {"id": notification["id"]},
                        {"$set": {"status": "sent", "sentAt": now, "deliveryResult": result}}
                    )
                    notification["status"] = "sent"
                elif result.get("skipped"):
                    await _col().update_one(
                        {"id": notification["id"]},
                        {"$set": {"status": "filtered", "deliveryResult": result}}
                    )
                    notification["status"] = "filtered"
            except Exception as e2:
                await _col().update_one(
                    {"id": notification["id"]},
                    {"$set": {"status": "error", "deliveryError": str(e2)}}
                )

    elif channel == "telegram_admin":
        try:
            from notifications.delivery.telegram_admin import send_telegram_admin
            result = await send_telegram_admin(notification, event)
            if result.get("ok") and not result.get("skipped"):
                await _col().update_one(
                    {"id": notification["id"]},
                    {"$set": {"status": "sent", "sentAt": now, "deliveryResult": result}}
                )
                notification["status"] = "sent"
            elif result.get("skipped"):
                await _col().update_one(
                    {"id": notification["id"]},
                    {"$set": {"status": "filtered", "deliveryResult": result}}
                )
                notification["status"] = "filtered"
            else:
                await _col().update_one(
                    {"id": notification["id"]},
                    {"$set": {"status": "failed", "deliveryResult": result}}
                )
                notification["status"] = "failed"
        except Exception as e:
            await _col().update_one(
                {"id": notification["id"]},
                {"$set": {"status": "error", "deliveryError": str(e)}}
            )
