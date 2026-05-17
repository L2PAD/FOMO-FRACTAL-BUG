"""Feed routes — Polymarket + Exchange intelligence feed."""
from fastapi import APIRouter, Query
from typing import Optional
from services.feed_service import get_feed, get_feed_with_influence
from services.feed_intelligence import build_feed_intelligence

router = APIRouter()


@router.get("/feed")
async def get_feed_endpoint(asset: Optional[str] = Query(default="BTC"), limit: int = Query(default=20)):
    """
    Feed endpoint — Retention Engine.
    Returns signal events + outcomes + pressure + sentiment + market events.
    Falls back to Polymarket feed if no events.
    """
    from services.feed_events_service import build_feed_events
    asset_upper = asset.upper().strip() if asset else None
    events = build_feed_events(asset_upper, limit=limit)
    if events:
        return {"ok": True, "items": events, "count": len(events)}
    # Fallback to original Polymarket feed
    return get_feed(asset_upper or "BTC", limit=limit)


@router.get("/feed/intelligence")
def get_feed_intelligence(asset: Optional[str] = Query(default="BTC")):
    """
    Feed 2.0 — Market Intelligence Layer.
    CONTRADICTION → WHY → WHAT TO DO
    """
    return build_feed_intelligence(asset.upper().strip() if asset else "BTC")

