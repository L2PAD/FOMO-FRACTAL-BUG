"""
Project Intelligence Adapter — Python bridge to Node.js Project Intelligence service.

Provides:
  - analyze(asset, dynamic_data) → full project intel
  - quick_assess(asset, dynamic_data) → quick tokenomics+valuation+unlock summary
  - batch_analyze(assets) → batch analysis
"""
import os
import httpx

_NODE_URL = os.environ.get("NODE_BACKEND_URL", "http://127.0.0.1:8003")
_TIMEOUT = 15.0


async def analyze(asset: str, dynamic_data: dict | None = None) -> dict:
    """Full single-asset project intelligence analysis."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/project-intelligence/analyze",
                json={"asset": asset, "dynamicData": dynamic_data or {}},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False, "intel": None}


async def quick_assess(asset: str, dynamic_data: dict | None = None) -> dict:
    """Quick assessment for pipeline use."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/project-intelligence/quick",
                json={"asset": asset, "dynamicData": dynamic_data or {}},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False}


async def batch_analyze(assets: list[str], dynamic_data: dict | None = None) -> dict:
    """Batch analysis for multiple assets."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/project-intelligence/batch",
                json={"assets": assets, "dynamicData": dynamic_data or {}},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False, "results": {}}
