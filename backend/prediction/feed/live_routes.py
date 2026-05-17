"""
Live Intelligence API Routes.

GET  /api/live/feed    — HOT/ACTIONABLE markets with live state
GET  /api/live/health  — Live engine metrics
"""
from fastapi import APIRouter, Query

from prediction.feed.event_ingestion import ingest_feed
from prediction.feed.live_engine import (
    enrich_event_with_live,
    get_live_metrics,
)

router = APIRouter(prefix="/api/live", tags=["live"])


@router.get("/feed")
async def live_feed(
    mode: str = Query("hot", description="hot|actionable|all"),
    asset: str = Query(None),
    category: str = Query(None),
    limit: int = Query(50),
):
    """Get live-enriched feed. Client polls this every 5-10s."""
    feed = await ingest_feed()

    if not feed.get("ok"):
        return {"ok": False, "events": []}

    if mode == "hot":
        events = feed.get("hot", [])
    elif mode == "actionable":
        events = feed.get("actionable", [])
    else:
        events = feed.get("all", [])

    # Filters
    if asset:
        asset_upper = asset.upper()
        events = [e for e in events if e.get("asset_group") == asset_upper]
    if category:
        events = [e for e in events if e.get("category") == category]

    # Enrich with live state
    enriched = [enrich_event_with_live(e) for e in events[:limit]]

    return {
        "ok": True,
        "mode": mode,
        "total": len(enriched),
        "events": enriched,
        "updated_at": feed.get("updated_at"),
    }


@router.get("/health")
async def live_health():
    """Get live engine metrics."""
    metrics = get_live_metrics()
    return {"ok": True, **metrics}
