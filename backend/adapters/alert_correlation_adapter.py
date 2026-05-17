"""
Alert Correlation Adapter — Python bridge to Node.js Correlation Engine.
"""
import os
import httpx

_NODE_URL = os.environ.get("NODE_BACKEND_URL", "http://127.0.0.1:8003")
_TIMEOUT = 15.0


async def analyze(alerts: list) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/alert-correlation/analyze",
                json={"alerts": alerts},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False, "metaAlerts": [], "count": 0}


async def get_meta_alerts(limit: int = 20) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_NODE_URL}/api/alert-correlation/meta-alerts",
                params={"limit": limit},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False, "metaAlerts": [], "count": 0}


async def get_history(limit: int = 50) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_NODE_URL}/api/alert-correlation/history",
                params={"limit": limit},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False, "metaAlerts": [], "count": 0}


async def get_regime() -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_NODE_URL}/api/alert-correlation/regime")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False, "regime": None}
