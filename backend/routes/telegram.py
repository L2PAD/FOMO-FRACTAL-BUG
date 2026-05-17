"""
Telegram Bot Webhook Route
Receives updates from Telegram and delegates to support service.
"""
import os
import logging
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.telegram_support import (
    handle_update,
    process_responses,
    set_bot_commands,
    update_user_plan_by_chat,
)

logger = logging.getLogger(__name__)

telegram_router = APIRouter(prefix="/api/telegram", tags=["telegram"])

# Secret for MiniApp plan updates (can be shared with MiniApp backend)
MINIAPP_SECRET = os.getenv("MINIAPP_WEBHOOK_SECRET", "fomo_miniapp_sync_2025")


@telegram_router.post("/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram webhook updates and process them."""
    try:
        update = await request.json()
        logger.info(f"Telegram update received: {update.get('update_id', 'unknown')}")

        # Process update and get list of response actions
        responses = await handle_update(update)

        # Send all response actions to Telegram
        if responses:
            await process_responses(responses)

        return {"ok": True}
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}", exc_info=True)
        return {"ok": True}  # Always return 200 to Telegram


@telegram_router.post("/setup-webhook")
async def setup_webhook(request: Request):
    """Set up Telegram webhook URL. Call once after deploy."""
    import httpx

    body = await request.json()
    webhook_url = body.get("webhook_url")
    if not webhook_url:
        return {"error": "webhook_url required"}

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return {"error": "TELEGRAM_BOT_TOKEN not configured"}

    async with httpx.AsyncClient() as client:
        # Set webhook with callback_query support
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={
                "url": webhook_url,
                "allowed_updates": ["message", "callback_query"],
            },
        )
        webhook_result = resp.json()

    # Set bot commands
    commands_result = await set_bot_commands()

    return {
        "webhook": webhook_result,
        "commands": commands_result,
    }


class PlanUpdateRequest(BaseModel):
    chat_id: int
    plan: str  # FREE, TRIAL, PRO, INSTITUTIONAL
    secret: str


@telegram_router.post("/update-plan")
async def update_plan_from_miniapp(body: PlanUpdateRequest):
    """
    Called by MiniApp backend when a user's subscription changes.
    Updates plan for all users linked to this Telegram chatId.
    Protected by shared secret.
    """
    # Validate secret
    if not hmac.compare_digest(body.secret, MINIAPP_SECRET):
        raise HTTPException(status_code=403, detail="Invalid secret")

    if body.plan not in ("FREE", "TRIAL", "PRO", "INSTITUTIONAL"):
        raise HTTPException(status_code=400, detail="Invalid plan")

    updated = await update_user_plan_by_chat(body.chat_id, body.plan)

    if updated:
        # Notify user in Telegram
        from services.telegram_support import send_telegram_message
        plan_emoji = "⭐" if body.plan in ("PRO", "INSTITUTIONAL") else "📋"
        await send_telegram_message(
            body.chat_id,
            f"{plan_emoji} *План обновлён: {body.plan}*\n\n"
            f"Ваша подписка синхронизирована между MiniApp и мобильным приложением.",
            parse_mode="Markdown",
        )

    return {
        "success": True,
        "updated": updated,
        "chat_id": body.chat_id,
        "plan": body.plan,
    }


@telegram_router.get("/webhook-info")
async def get_webhook_info():
    """Get current webhook info from Telegram."""
    import httpx

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return {"error": "TELEGRAM_BOT_TOKEN not configured"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.telegram.org/bot{token}/getWebhookInfo"
        )
        return resp.json()
