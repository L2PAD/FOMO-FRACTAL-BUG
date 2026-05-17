"""
Telegram MiniApp Bot
====================
Clean 2-button UI: Signal Settings + dynamic CTA (Upgrade/Dashboard).
No slash commands except /start.
"""

import os
import asyncio
import httpx
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

BOT_TOKEN = os.environ.get("MINIAPP_BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("MINIAPP_URL", "")


def _tg_api():
    return f"https://api.telegram.org/bot{BOT_TOKEN}"


async def setup_miniapp_bot():
    """Configure bot: menu button, description. No slash commands."""
    if not BOT_TOKEN or not WEBAPP_URL:
        print("[MiniApp Bot] Missing MINIAPP_BOT_TOKEN or MINIAPP_URL, skip")
        return

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{_tg_api()}/setChatMenuButton", json={
            "menu_button": {
                "type": "web_app",
                "text": "FOMO Intelligence",
                "web_app": {"url": WEBAPP_URL}
            }
        })
        print(f"[MiniApp Bot] setChatMenuButton: {r.json()}")

        await client.post(f"{_tg_api()}/deleteMyCommands")

        r = await client.post(f"{_tg_api()}/setMyDescription", json={
            "description": "AI crypto intelligence — real-time alerts, edge signals, and market decisions."
        })
        print(f"[MiniApp Bot] setMyDescription: {r.json()}")

        r = await client.post(f"{_tg_api()}/setMyShortDescription", json={
            "short_description": "AI-powered crypto edge alerts & market intelligence"
        })
        print(f"[MiniApp Bot] setMyShortDescription: {r.json()}")

        r = await client.get(f"{_tg_api()}/getMe")
        bot_info = r.json()
        print(f"[MiniApp Bot] Bot: @{bot_info.get('result', {}).get('username', '?')}")


# ── Welcome ──

WELCOME_TEXT = """Welcome to FOMO

AI crypto intelligence — real-time edge alerts with 82% accuracy.

Tap below to get started."""

# ── Callbacks ──
CB_SETTINGS = "nav_settings"
CB_SET_BTC = "set_btc"
CB_SET_ETH = "set_eth"
CB_SET_SOL = "set_sol"
CB_SET_ALL = "set_all"
CB_BACK = "set_back"


# ── Main handler ──

async def handle_update(update: dict):
    """Handle messages and callback queries."""
    cb = update.get("callback_query")
    if cb:
        await _handle_callback(cb)
        return

    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    if not chat_id:
        return

    # Save user info
    try:
        from ml_ops import get_db as _get_db
        db = _get_db()
        if db is not None:
            now = datetime.now(timezone.utc).isoformat()
            await db.miniapp_bot_chats.update_one(
                {"chat_id": chat_id},
                {"$set": {
                    "chat_id": chat_id,
                    "username": msg.get("from", {}).get("username", ""),
                    "first_name": msg.get("from", {}).get("first_name", ""),
                    "last_name": msg.get("from", {}).get("last_name", ""),
                    "last_seen": now,
                },
                "$setOnInsert": {"first_interaction": now}},
                upsert=True,
            )
    except Exception:
        pass

    # Referral tracking
    if text.startswith("/start") and " ref_" in text:
        try:
            from ml_ops import get_db as _get_db
            db = _get_db()
            if db is not None:
                ref_code = text.split("ref_")[1].split()[0]
                await db.miniapp_referral_clicks.insert_one({
                    "code": ref_code, "chat_id": chat_id,
                    "at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception:
            pass

    await _send_welcome(chat_id)


# ── Helpers ──

async def _is_pro(chat_id: int) -> bool:
    try:
        from ml_ops import get_db as _get_db
        db = _get_db()
        if db is not None:
            user = await db.miniapp_users.find_one(
                {"telegram_id": str(chat_id)}, {"_id": 0, "plan_status": 1}
            )
            return user.get("plan_status") == "active" if user else False
    except Exception:
        return False


async def _main_kb(chat_id: int):
    pro = await _is_pro(chat_id)
    cta = "Open Dashboard" if pro else "Upgrade to PRO"
    # Always pass an explicit ?tab=... so the lite page never has to
    # disambiguate a bare URL — guards against any future routing change.
    tab = "?tab=home" if pro else "?tab=profile"
    rows = [
        [{"text": "Signal Settings", "callback_data": CB_SETTINGS}],
    ]
    if WEBAPP_URL:
        rows.append([{"text": cta, "web_app": {"url": f"{WEBAPP_URL}{tab}"}}])
    return {"inline_keyboard": rows}


async def _send_welcome(chat_id: int):
    kb = await _main_kb(chat_id)
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{_tg_api()}/sendMessage", json={
            "chat_id": chat_id,
            "text": WELCOME_TEXT,
            "reply_markup": kb,
        })


# ── Callbacks ──

async def _handle_callback(cb: dict):
    data = cb.get("data", "")
    chat_id = cb.get("message", {}).get("chat", {}).get("id")
    cb_id = cb.get("id")
    if not chat_id:
        return

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{_tg_api()}/answerCallbackQuery", json={
            "callback_query_id": cb_id,
        })

    if data == CB_SETTINGS:
        await _send_settings(chat_id)
    elif data in (CB_SET_BTC, CB_SET_ETH, CB_SET_SOL):
        asset = {"set_btc": "BTC", "set_eth": "ETH", "set_sol": "SOL"}[data]
        await _toggle_asset(chat_id, asset)
    elif data == CB_SET_ALL:
        await _toggle_all(chat_id)
    elif data == CB_BACK:
        await _send_welcome(chat_id)


# ── Signal Settings ──

async def _get_settings(chat_id: int) -> dict:
    try:
        from ml_ops import get_db as _get_db
        db = _get_db()
        if db is not None:
            s = await db.miniapp_settings.find_one(
                {"telegram_id": str(chat_id)}, {"_id": 0}
            )
            if s:
                return s
    except Exception:
        pass
    return {"alertsEnabled": True, "assets": ["BTC", "ETH", "SOL"]}


async def _save_settings(chat_id: int, assets: list, enabled: bool):
    try:
        from ml_ops import get_db as _get_db
        db = _get_db()
        if db is not None:
            await db.miniapp_settings.update_one(
                {"telegram_id": str(chat_id)},
                {"$set": {
                    "telegram_id": str(chat_id),
                    "alertsEnabled": enabled,
                    "assets": assets,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True,
            )
    except Exception:
        pass


async def _send_settings(chat_id: int):
    s = await _get_settings(chat_id)
    assets = s.get("assets", ["BTC", "ETH", "SOL"])
    enabled = s.get("alertsEnabled", True)

    text = (
        f"Signal Settings\n\n"
        f"Alerts: {'ON' if enabled else 'OFF'}\n"
        f"Assets: {', '.join(assets) if assets else 'none'}\n\n"
        f"Tap to toggle:"
    )

    kb = {"inline_keyboard": [
        [
            {"text": f"{'[x]' if 'BTC' in assets else '[ ]'} BTC", "callback_data": CB_SET_BTC},
            {"text": f"{'[x]' if 'ETH' in assets else '[ ]'} ETH", "callback_data": CB_SET_ETH},
            {"text": f"{'[x]' if 'SOL' in assets else '[ ]'} SOL", "callback_data": CB_SET_SOL},
        ],
        [{"text": f"{'Disable' if enabled else 'Enable'} All Alerts", "callback_data": CB_SET_ALL}],
        [{"text": "Back", "callback_data": CB_BACK}],
    ]}

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{_tg_api()}/sendMessage", json={
            "chat_id": chat_id, "text": text, "reply_markup": kb,
        })


async def _toggle_asset(chat_id: int, asset: str):
    s = await _get_settings(chat_id)
    assets = s.get("assets", ["BTC", "ETH", "SOL"])
    enabled = s.get("alertsEnabled", True)
    if asset in assets:
        assets.remove(asset)
    else:
        assets.append(asset)
    await _save_settings(chat_id, assets, enabled)
    await _send_settings(chat_id)


async def _toggle_all(chat_id: int):
    s = await _get_settings(chat_id)
    enabled = s.get("alertsEnabled", True)
    assets = s.get("assets", ["BTC", "ETH", "SOL"])
    await _save_settings(chat_id, assets if not enabled else assets, not enabled)
    await _send_settings(chat_id)


# ── Alert sending (used by edge_alerts.py) ──

async def send_miniapp_button(chat_id: int, asset: str):
    if not WEBAPP_URL:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{_tg_api()}/sendMessage", json={
            "chat_id": chat_id,
            "text": f"{asset} Intelligence — open for real-time analysis.",
            "reply_markup": {"inline_keyboard": [[{
                "text": f"Open {asset} Analysis",
                "web_app": {"url": f"{WEBAPP_URL}?asset={asset}"}
            }]]}
        })


async def send_truncated_alert(chat_id: int, asset: str, direction: str, edge_pct: float, tier: str):
    if not WEBAPP_URL or not BOT_TOKEN:
        return {"ok": False}

    edge_str = f"+{edge_pct:.1f}%" if edge_pct > 0 else f"{edge_pct:.1f}%"
    tier_label = "EXTREME" if tier == "EXTREME" else "HIGH CONVICTION" if tier == "HIGH_CONVICTION" else ""

    lines = [f"LIVE EDGE — {asset}"]
    if tier_label:
        lines[0] += f" [{tier_label}]"
    lines.append(f"Direction: {direction} | Edge: {edge_str}")
    lines.append("")
    lines.append("Open for full analysis:")

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{_tg_api()}/sendMessage", json={
            "chat_id": chat_id,
            "text": "\n".join(lines),
            "reply_markup": {"inline_keyboard": [
                [{"text": f"Open {asset} Analysis", "web_app": {"url": f"{WEBAPP_URL}?asset={asset}&tab=home"}}],
            ]}
        })
        return r.json()


if __name__ == "__main__":
    asyncio.run(setup_miniapp_bot())
