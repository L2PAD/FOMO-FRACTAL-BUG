"""
Event Feed Adapter — Python bridge to Node.js Event Feed service.

Provides:
  - get_curated_feed(asset, hours_back) → curated event clusters
  - get_related_events(entities, event_type) → related events for catalyst engine
"""
import os
import httpx

_NODE_URL = os.environ.get("NODE_BACKEND_URL", "http://127.0.0.1:8003")
_TIMEOUT = 15.0


async def get_curated_feed(
    asset: str | None = None,
    hours_back: int = 24,
    limit: int = 30,
    priority_band: str | None = None,
) -> dict:
    """Get curated event feed from Node service."""
    params: dict = {"hoursBack": str(hours_back), "limit": str(limit)}
    if asset:
        params["asset"] = asset
    if priority_band:
        params["priorityBand"] = priority_band

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_NODE_URL}/api/event-feed", params=params)
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False, "clusters": [], "meta": {}}


async def get_feed_for_asset(asset: str, hours_back: int = 24) -> list[dict]:
    """Get feed clusters for a specific asset."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_NODE_URL}/api/event-feed/asset/{asset}",
                params={"hoursBack": str(hours_back)},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("clusters", [])
    except Exception:
        pass
    return []


async def get_related_events(
    entities: list[str],
    event_type: str,
    hours_back: int = 48,
) -> list[dict]:
    """Get related events for entities (replaces _gather_related_events)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/event-feed/related",
                json={
                    "entities": entities,
                    "eventType": event_type,
                    "hoursBack": hours_back,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("events", [])
    except Exception:
        pass
    return []


async def get_feed_stats() -> dict:
    """Get feed statistics."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_NODE_URL}/api/event-feed/stats")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"ok": False}
