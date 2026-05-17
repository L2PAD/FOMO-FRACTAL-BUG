"""
FOMO Intel Feed - Unified Event Stream
=======================================
Single unified feed combining all crypto intelligence events:
- Funding rounds
- Activities (airdrops, campaigns, testnets)
- Token unlocks
- News/announcements
- Listings

Endpoint:
- GET /api/intel-feed - Unified feed with type filters
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/intel-feed", tags=["Intel Feed"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# Feed Event Types
FEED_TYPES = [
    "funding",      # funding rounds
    "activity",     # airdrops, campaigns, testnets
    "unlock",       # token unlocks
    "news",         # news/announcements
    "listing",      # exchange listings
    "launch"        # mainnet/token launches
]


# ═══════════════════════════════════════════════════════════════
# UNIFIED INTEL FEED
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def get_intel_feed(
    types: Optional[str] = Query(None, description="Filter types (comma-sep): funding,activity,unlock,news,listing,launch"),
    project: Optional[str] = Query(None, description="Filter by project"),
    investor: Optional[str] = Query(None, description="Filter by investor"),
    from_date: Optional[str] = Query(None, description="From date (ISO)"),
    to_date: Optional[str] = Query(None, description="To date (ISO)"),
    importance: Optional[str] = Query(None, description="Filter: high, medium, low"),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100)
):
    """
    Get unified intel feed combining all event types.
    
    Types:
    - funding: funding rounds (seed, series A, etc.)
    - activity: airdrops, campaigns, testnets
    - unlock: token unlock events
    - news: project news/announcements
    - listing: exchange listings
    - launch: mainnet/token launches
    """
    from server import db
    
    skip = (page - 1) * limit
    now = datetime.now(timezone.utc)
    
    # Parse type filter
    type_filter = types.split(",") if types else FEED_TYPES
    type_filter = [t.strip() for t in type_filter]
    
    # Parse dates
    from_dt = datetime.fromisoformat(from_date) if from_date else None
    to_dt = datetime.fromisoformat(to_date) if to_date else None
    
    all_items = []
    
    # ─────────────────────────────────────────────────────────────
    # 1. Funding Events
    # ─────────────────────────────────────────────────────────────
    if "funding" in type_filter:
        query = {}
        if project:
            query["$or"] = [
                {"project": {"$regex": project, "$options": "i"}},
                {"project_key": {"$regex": project, "$options": "i"}}
            ]
        if investor:
            query["investors"] = {"$regex": investor, "$options": "i"}
        if from_dt:
            query["round_date"] = {"$gte": int(from_dt.timestamp() * 1000)}
        if to_dt:
            query.setdefault("round_date", {})["$lte"] = int(to_dt.timestamp() * 1000)
        
        cursor = db.intel_funding.find(query).sort("round_date", -1).limit(limit * 2)
        funding_rounds = await cursor.to_list(limit * 2)
        
        for r in funding_rounds:
            raised = r.get("raised_usd", 0) or 0
            importance_level = "high" if raised > 50_000_000 else "medium" if raised > 10_000_000 else "low"
            
            if importance and importance_level != importance:
                continue
            
            all_items.append({
                "type": "funding",
                "id": r.get("id", str(r.get("_id", ""))),
                "timestamp": r.get("round_date"),
                "date": datetime.fromtimestamp(r.get("round_date", 0) / 1000, tz=timezone.utc).isoformat() if r.get("round_date") else None,
                "project": r.get("project"),
                "project_id": r.get("project_key"),
                "symbol": r.get("symbol"),
                "title": f"{r.get('project', 'Unknown')} raised ${raised/1_000_000:.1f}M in {r.get('round_type', 'funding')} round",
                "description": f"Investors: {', '.join(r.get('investors', [])[:3])}",
                "round_type": r.get("round_type"),
                "raised_usd": raised,
                "valuation_usd": r.get("valuation_usd"),
                "investors": r.get("investors", [])[:5],
                "lead_investors": r.get("lead_investors", []),
                "importance": importance_level,
                "source": r.get("source"),
                "score": min(100, 50 + int(raised / 1_000_000))
            })
    
    # ─────────────────────────────────────────────────────────────
    # 2. Activity Events
    # ─────────────────────────────────────────────────────────────
    if "activity" in type_filter:
        query = {}
        if project:
            query["project_id"] = {"$regex": project, "$options": "i"}
        
        cursor = db.crypto_activities.find(query).sort("created_at", -1).limit(limit * 2)
        activities = await cursor.to_list(limit * 2)
        
        for act in activities:
            importance_level = "high" if act.get("score", 0) > 70 else "medium" if act.get("score", 0) > 40 else "low"
            
            if importance and importance_level != importance:
                continue
            
            all_items.append({
                "type": "activity",
                "id": act.get("id", str(act.get("_id", ""))),
                "timestamp": int(datetime.fromisoformat(act.get("created_at", now.isoformat())).timestamp() * 1000) if act.get("created_at") else ts_now(),
                "date": act.get("start_date") or act.get("created_at"),
                "project": act.get("project_name"),
                "project_id": act.get("project_id"),
                "title": act.get("title"),
                "description": act.get("description", "")[:150],
                "activity_type": act.get("type"),
                "category": act.get("category"),
                "status": act.get("status", "active"),
                "reward": act.get("reward"),
                "importance": importance_level,
                "source": act.get("source"),
                "source_url": act.get("source_url"),
                "score": act.get("score", 50)
            })
    
    # ─────────────────────────────────────────────────────────────
    # 3. Unlock Events
    # ─────────────────────────────────────────────────────────────
    if "unlock" in type_filter:
        query = {}
        if project:
            query["project_id"] = {"$regex": project, "$options": "i"}
        
        cursor = db.token_unlocks.find(query).sort("date", -1).limit(limit * 2)
        unlocks = await cursor.to_list(limit * 2)
        
        for u in unlocks:
            percent = u.get("percent_supply", 0) or 0
            importance_level = "high" if percent > 5 else "medium" if percent > 1 else "low"
            
            if importance and importance_level != importance:
                continue
            
            all_items.append({
                "type": "unlock",
                "id": u.get("id", str(u.get("_id", ""))),
                "timestamp": int(datetime.fromisoformat(u.get("date", now.isoformat())).timestamp() * 1000) if u.get("date") else ts_now(),
                "date": u.get("date"),
                "project": u.get("project_name"),
                "project_id": u.get("project_id"),
                "symbol": u.get("symbol"),
                "title": f"{u.get('project_name', 'Unknown')} token unlock: {percent:.2f}% of supply",
                "description": f"Category: {u.get('category', 'unknown')}, Amount: {u.get('amount_tokens', 0):,.0f} tokens",
                "category": u.get("category"),
                "amount_tokens": u.get("amount_tokens"),
                "amount_usd": u.get("amount_usd"),
                "percent_supply": percent,
                "is_future": u.get("is_future", False),
                "importance": importance_level,
                "score": min(100, 50 + int(percent * 10))
            })
    
    # ─────────────────────────────────────────────────────────────
    # 4. Listing Events (from activities with type=listing)
    # ─────────────────────────────────────────────────────────────
    if "listing" in type_filter:
        query = {"type": "listing"}
        if project:
            query["project_id"] = {"$regex": project, "$options": "i"}
        
        cursor = db.crypto_activities.find(query).sort("start_date", -1).limit(limit)
        listings = await cursor.to_list(limit)
        
        for lst in listings:
            all_items.append({
                "type": "listing",
                "id": lst.get("id", str(lst.get("_id", ""))),
                "timestamp": int(datetime.fromisoformat(lst.get("start_date", now.isoformat())).timestamp() * 1000) if lst.get("start_date") else ts_now(),
                "date": lst.get("start_date"),
                "project": lst.get("project_name"),
                "project_id": lst.get("project_id"),
                "title": lst.get("title"),
                "description": lst.get("description", "")[:150],
                "exchange": lst.get("exchange"),
                "importance": "medium",
                "source": lst.get("source"),
                "score": lst.get("score", 60)
            })
    
    # ─────────────────────────────────────────────────────────────
    # 5. Launch Events (mainnet, token launch)
    # ─────────────────────────────────────────────────────────────
    if "launch" in type_filter:
        query = {"type": {"$in": ["mainnet", "token_launch", "testnet"]}}
        if project:
            query["project_id"] = {"$regex": project, "$options": "i"}
        
        cursor = db.crypto_activities.find(query).sort("start_date", -1).limit(limit)
        launches = await cursor.to_list(limit)
        
        for lnch in launches:
            launch_type = lnch.get("type", "launch")
            importance_level = "high" if launch_type == "mainnet" else "medium"
            
            if importance and importance_level != importance:
                continue
            
            all_items.append({
                "type": "launch",
                "id": lnch.get("id", str(lnch.get("_id", ""))),
                "timestamp": int(datetime.fromisoformat(lnch.get("start_date", now.isoformat())).timestamp() * 1000) if lnch.get("start_date") else ts_now(),
                "date": lnch.get("start_date"),
                "project": lnch.get("project_name"),
                "project_id": lnch.get("project_id"),
                "title": lnch.get("title"),
                "description": lnch.get("description", "")[:150],
                "launch_type": launch_type,
                "importance": importance_level,
                "source": lnch.get("source"),
                "score": lnch.get("score", 70)
            })
    
    # ─────────────────────────────────────────────────────────────
    # Sort and paginate
    # ─────────────────────────────────────────────────────────────
    all_items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    
    total = len(all_items)
    paginated = all_items[skip:skip + limit]
    
    return {
        "ts": ts_now(),
        "page": page,
        "limit": limit,
        "total": total,
        "types_available": FEED_TYPES,
        "filters_applied": {
            "types": type_filter,
            "project": project,
            "investor": investor,
            "importance": importance
        },
        "items": paginated,
        "_meta": {"cache_sec": 120}
    }


# ═══════════════════════════════════════════════════════════════
# TRENDING FEED
# ═══════════════════════════════════════════════════════════════

@router.get("/trending")
async def get_trending_feed(
    period: str = Query("day", description="Period: day, week, month"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get trending events by score and recency.
    """
    from server import db
    
    now = datetime.now(timezone.utc)
    
    if period == "day":
        since = now - timedelta(days=1)
    elif period == "week":
        since = now - timedelta(days=7)
    else:
        since = now - timedelta(days=30)
    
    since_ts = int(since.timestamp() * 1000)
    
    all_items = []
    
    # Get high-value funding
    cursor = db.intel_funding.find({"round_date": {"$gte": since_ts}}).sort("raised_usd", -1).limit(10)
    funding_rounds = await cursor.to_list(10)
    
    for r in funding_rounds:
        raised = r.get("raised_usd", 0) or 0
        all_items.append({
            "type": "funding",
            "id": r.get("id"),
            "project": r.get("project"),
            "title": f"{r.get('project')} raised ${raised/1_000_000:.1f}M",
            "score": min(100, 50 + int(raised / 1_000_000)),
            "timestamp": r.get("round_date")
        })
    
    # Get high-score activities
    cursor = db.crypto_activities.find({}).sort("score", -1).limit(10)
    activities = await cursor.to_list(10)
    
    for act in activities:
        all_items.append({
            "type": "activity",
            "id": act.get("id"),
            "project": act.get("project_name"),
            "title": act.get("title"),
            "score": act.get("score", 50),
            "timestamp": ts_now()
        })
    
    # Sort by score
    all_items.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return {
        "ts": ts_now(),
        "period": period,
        "count": len(all_items[:limit]),
        "items": all_items[:limit],
        "_meta": {"cache_sec": 300}
    }
