"""
Event Source — Polymarket Gamma API event fetcher.

Fetches full crypto event universe via events endpoint with pagination.
Each event contains multiple markets (outcomes).

Endpoints:
  GET /events?active=true&closed=false&limit=X&offset=Y
  GET /markets?id=X (single market detail)
"""
import logging
import httpx

logger = logging.getLogger("feed.event_source")

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"


async def fetch_events_page(offset: int = 0, limit: int = 100) -> list[dict]:
    """Fetch one page of active events from Gamma API."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GAMMA_API}/events",
            params={
                "active": "true",
                "closed": "false",
                "limit": limit,
                "offset": offset,
                "order": "volume24hr",
                "ascending": "false",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_all_active_events(max_pages: int = 5) -> list[dict]:
    """Paginate through all active events."""
    all_events = []
    for page in range(max_pages):
        offset = page * 100
        events = await fetch_events_page(offset=offset, limit=100)
        if not events:
            break
        all_events.extend(events)
        logger.info(f"Fetched events page {page + 1}: {len(events)} events (total: {len(all_events)})")
        if len(events) < 100:
            break
    return all_events


async def fetch_clob_book(token_id: str) -> dict | None:
    """Fetch single orderbook from CLOB API."""
    if not token_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(f"{CLOB_API}/book", params={"token_id": token_id})
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"CLOB book fetch error: {e}")
    return None


async def fetch_clob_midpoint(token_id: str) -> float | None:
    """Fetch midpoint price for a token."""
    if not token_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{CLOB_API}/midpoint", params={"token_id": token_id})
            if resp.status_code == 200:
                data = resp.json()
                return float(data.get("mid", 0))
    except Exception as e:
        logger.warning(f"CLOB midpoint error: {e}")
    return None
