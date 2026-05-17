"""
Telegram Delivery Adapter — Python bridge to Node.js Telegram Delivery service.
"""
import os
import httpx

_NODE_URL = os.environ.get("NODE_BACKEND_URL", "http://127.0.0.1:8003")
_TIMEOUT = 15.0


async def connect(chat_id: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/telegram-delivery/connect",
                json={"chatId": chat_id},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False, "error": "connection failed"}


async def get_stats() -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_NODE_URL}/api/telegram-delivery/stats")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False}


async def test_alert(chat_id: str, alert_type: str = "ENTRY_ALERT") -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/telegram-delivery/test",
                json={"chatId": chat_id, "type": alert_type},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False}


async def update_preferences(chat_id: str, updates: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/telegram-delivery/preferences",
                json={"chatId": chat_id, **updates},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False}


async def get_subscribers() -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_NODE_URL}/api/telegram-delivery/subscribers")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False, "count": 0, "subscribers": []}


async def deliver_alert(payload: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/telegram-delivery/deliver",
                json=payload,
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False}


async def deliver_weekly(digest_data: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/telegram-delivery/deliver-weekly",
                json=digest_data,
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False}
