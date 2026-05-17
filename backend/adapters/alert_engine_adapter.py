"""
Alert Engine Adapter — Python bridge to Node.js Alert Engine.

Provides:
  - process_alerts(cases) → trigger alert pipeline on processed cases
  - get_history(limit) → recent alert history
  - get_stats() → alert engine stats
"""
import os
import httpx

_NODE_URL = os.environ.get("NODE_BACKEND_URL", "http://127.0.0.1:8003")
_TIMEOUT = 10.0


async def process_alerts(cases: list[dict]) -> dict:
    """Send processed cases to alert engine for analysis."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/alert-engine/process",
                json={"cases": cases},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False}


async def get_history(limit: int = 50) -> list:
    """Get recent alert history."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_NODE_URL}/api/alert-engine/history",
                params={"limit": limit},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("alerts", [])
    except Exception:
        pass
    return []


async def get_stats() -> dict:
    """Get alert engine stats."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_NODE_URL}/api/alert-engine/stats")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("stats", {})
    except Exception:
        pass
    return {}
