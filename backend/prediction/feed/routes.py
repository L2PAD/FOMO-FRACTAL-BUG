"""
Feed API Routes — Polymarket Event Feed with Intelligence Overlay.

GET  /api/feed                    — full event feed (HOT/ACTIONABLE/ALL)
GET  /api/feed/{event_id}         — single event detail
POST /api/feed/sync               — manual sync/refresh
GET  /api/feed/health             — feed health status

Legacy (kept for backward compat):
GET  /api/market-feed/markets     — old feed format
"""
from fastapi import APIRouter, Query

from prediction.feed.event_ingestion import ingest_feed
from prediction.feed.feed_health import get_health

router = APIRouter(prefix="/api/feed", tags=["feed"])


@router.get("")
async def get_feed(
    mode: str = Query("all", description="hot|actionable|all"),
    asset: str = Query(None, description="BTC|ETH|SOL|XRP|ALT"),
    category: str = Query(None, description="fdv|launch|etf|macro|price|direction"),
    ending_soon: bool = Query(False),
    high_edge: bool = Query(False),
):
    """Get event feed with filters."""
    feed = await ingest_feed()

    if not feed.get("ok"):
        return feed

    # Select tier
    if mode == "hot":
        events = feed.get("hot", [])
    elif mode == "actionable":
        events = feed.get("actionable", [])
    else:
        events = feed.get("all", [])

    # Enrich with live state
    try:
        from prediction.feed.live_engine import enrich_event_with_live
        events = [enrich_event_with_live(e) for e in events]
    except Exception:
        pass

    # Apply filters
    if asset:
        asset_upper = asset.upper()
        events = [e for e in events if e.get("asset_group") == asset_upper]

    if category:
        events = [e for e in events if e.get("category") == category]

    if ending_soon:
        events = [e for e in events if _is_ending_soon(e)]

    if high_edge:
        events = [e for e in events
                  if abs((e.get("overlay", {}).get("best_pick", {}) or {}).get("edge", 0)) > 0.05]

    return {
        "ok": True,
        "mode": mode,
        "total": len(events),
        "hot_count": feed.get("hot_count", 0),
        "actionable_count": feed.get("actionable_count", 0),
        "all_count": feed.get("total_events", 0),
        "events": events,
        "updated_at": feed.get("updated_at"),
        "freshness": feed.get("freshness"),
    }


@router.get("/event/{event_id}")
async def get_event_detail(event_id: str):
    """Get detailed view of a single event."""
    feed = await ingest_feed()
    if not feed.get("ok"):
        return {"ok": False, "error": "Feed not available"}

    for ev in feed.get("all", []):
        if ev.get("event_id") == event_id:
            return {"ok": True, "event": ev}

    return {"ok": False, "error": "Event not found"}


@router.post("/sync")
async def sync_feed():
    """Force refresh the feed."""
    feed = await ingest_feed(force_refresh=True)
    return {
        "ok": feed.get("ok", False),
        "total_events": feed.get("total_events", 0),
        "total_markets": feed.get("total_markets", 0),
        "hot_count": feed.get("hot_count", 0),
        "actionable_count": feed.get("actionable_count", 0),
    }


@router.get("/health")
async def feed_health():
    """Get feed health status."""
    return {"ok": True, **get_health()}


def _is_ending_soon(event: dict, hours: int = 48) -> bool:
    """Check if event ends within N hours."""
    from datetime import datetime, timezone
    end_date = event.get("end_date")
    if not end_date:
        return False
    try:
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        hours_left = (end - datetime.now(timezone.utc)).total_seconds() / 3600
        return 0 < hours_left < hours
    except Exception:
        return False


# === Legacy backward compat ===

legacy_router = APIRouter(prefix="/api/market-feed", tags=["market-feed-legacy"])


@legacy_router.get("/markets")
async def legacy_markets():
    """Legacy endpoint — redirects to new feed."""
    feed = await ingest_feed()
    if not feed.get("ok"):
        return feed

    # Flatten events into market-level items for backward compat
    flat = []
    for ev in feed.get("all", []):
        for m in ev.get("markets", []):
            flat.append({
                "market_id": m["market_id"],
                "question": m["question"],
                "yes_price": m["yes_price"],
                "no_price": m["no_price"],
                "volume": m.get("volume", 0),
                "liquidity": m.get("liquidity", 0),
                "spread": m.get("spread", 0),
                "event_type": ev.get("event_type", ""),
                "asset": ev.get("asset_group", ""),
                "tier": ev.get("tier", "all"),
                "overlay": m.get("overlay", {}),
                "clob": {
                    "best_bid": m.get("best_bid", 0),
                    "best_ask": m.get("best_ask", 0),
                    "spread_pct": round(m.get("spread", 0) / m.get("best_ask", 1) * 100, 2) if m.get("best_ask") else 0,
                    "depth_quality": "unknown",
                    "entry_hint": "LIMIT_PREFERRED",
                },
            })

    return {
        "ok": True,
        "total": len(flat),
        "hot_count": feed.get("hot_count", 0),
        "actionable_count": feed.get("actionable_count", 0),
        "markets": flat,
        "updated_at": feed.get("updated_at"),
    }
