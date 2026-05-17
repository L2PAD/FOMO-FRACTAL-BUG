"""
Execution Score Adapter — Python bridge to Node.js Execution Score service.
"""
import os
import httpx

_NODE_URL = os.environ.get("NODE_BACKEND_URL", "http://127.0.0.1:8003")
_TIMEOUT = 15.0


async def batch_evaluate(cases: list[dict]) -> dict:
    """Batch execution scoring for all pipeline cases."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/execution-score/evaluate/batch",
                json={"cases": cases},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("results", {})
    except Exception:
        pass
    return {}


async def get_style_performance() -> dict:
    """Get execution style performance stats."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_NODE_URL}/api/execution-score/styles")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data
    except Exception:
        pass
    return {}
