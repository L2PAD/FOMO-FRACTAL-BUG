"""
Telegram User Bot Delivery.

Sends filtered, formatted messages to users via Telegram.
Uses TG_BOT_TOKEN from env. Gracefully skips if not configured.
"""
import os
import logging
import httpx
from typing import Optional
from notifications.delivery.telegram_filter import should_send_user
from notifications.delivery.telegram_formatter import format_user_message

logger = logging.getLogger(__name__)

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_USER_CHAT_ID = os.environ.get("TG_USER_CHAT_ID", "")


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
                logger.warning(f"Telegram user send failed: {data}")
            return data
    except Exception as e:
        logger.error(f"Telegram user send error: {e}")
        return {"ok": False, "error": str(e)}


async def send_telegram_user(notification: dict, event: dict) -> dict:
    """
    Deliver notification to user Telegram bot.
    Returns delivery result.
    """
    if not TG_BOT_TOKEN:
        return {"ok": False, "reason": "TG_BOT_TOKEN not configured", "skipped": True}

    if not TG_USER_CHAT_ID:
        return {"ok": False, "reason": "TG_USER_CHAT_ID not configured", "skipped": True}

    # Apply Telegram-specific filter (stricter than UI)
    if not should_send_user(event):
        return {"ok": True, "reason": "filtered_out", "skipped": True}

    text = format_user_message(event)
    result = await _send_tg(TG_BOT_TOKEN, TG_USER_CHAT_ID, text)
    return result
