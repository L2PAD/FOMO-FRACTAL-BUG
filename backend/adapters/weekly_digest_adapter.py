"""
Weekly Digest Adapter — Python bridge to Node.js Weekly Digest service.

Provides:
  - generate(from_date, to_date) → generate and return a new digest
  - get_latest() → most recent digest
  - get_history(limit) → digest history
"""
import os
import httpx

_NODE_URL = os.environ.get("NODE_BACKEND_URL", "http://127.0.0.1:8003")
_TIMEOUT = 30.0


async def generate(from_date: str = None, to_date: str = None) -> dict | None:
    """Generate a new weekly digest."""
    try:
        payload = {}
        if from_date:
            payload["from"] = from_date
        if to_date:
            payload["to"] = to_date

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/weekly-digest/generate",
                json=payload,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("digest")
    except Exception:
        pass
    return None


async def get_latest() -> dict | None:
    """Get the most recent digest."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_NODE_URL}/api/weekly-digest/latest")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("digest")
    except Exception:
        pass
    return None


async def get_history(limit: int = 10) -> list:
    """Get digest history."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_NODE_URL}/api/weekly-digest/history",
                params={"limit": limit},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("digests", [])
    except Exception:
        pass
    return []
