"""
Telegram Admin Bot Delivery.

Sends system alerts to admin Telegram chat.
Uses TG_ADMIN_BOT_TOKEN (or falls back to TG_BOT_TOKEN) + TG_ADMIN_CHAT_ID.
"""
import os
import logging
import httpx
from notifications.delivery.telegram_filter import should_send_admin
from notifications.delivery.telegram_formatter import format_admin_message

logger = logging.getLogger(__name__)

TG_ADMIN_BOT_TOKEN = os.environ.get("TG_ADMIN_BOT_TOKEN", "") or os.environ.get("TG_BOT_TOKEN", "")
TG_ADMIN_CHAT_ID = os.environ.get("TG_ADMIN_CHAT_ID", "")


async def _send_tg(token: str, chat_id: str, text: str) -> dict:
    """Low-level Telegram sendMessage."""
    if not token or not chat_id:
        return {"ok": False, "reason": "not_configured"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if not data.get("ok"):
                logger.warning(f"Telegram admin send failed: {data}")
            return data
    except Exception as e:
        logger.error(f"Telegram admin send error: {e}")
        return {"ok": False, "error": str(e)}


async def send_telegram_admin(notification: dict, event: dict) -> dict:
    """
    Deliver notification to admin Telegram bot.
    Returns delivery result.
    """
    if not TG_ADMIN_BOT_TOKEN:
        return {"ok": False, "reason": "TG_ADMIN_BOT_TOKEN not configured", "skipped": True}

    if not TG_ADMIN_CHAT_ID:
        return {"ok": False, "reason": "TG_ADMIN_CHAT_ID not configured", "skipped": True}

    # Apply Telegram-specific filter
    if not should_send_admin(event):
        return {"ok": True, "reason": "filtered_out", "skipped": True}

    text = format_admin_message(event)
    result = await _send_tg(TG_ADMIN_BOT_TOKEN, TG_ADMIN_CHAT_ID, text)
    return result
