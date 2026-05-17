"""
FOMO Funding Feed API
=====================
Complete funding intelligence with FOMO Score and Red Flags.

Endpoints:
- GET /api/funding/feed - Main funding feed
- GET /api/funding/spotlight - Top spotlight cards
- GET /api/funding/round/{roundId} - Round details
- GET /api/funding/project/{projectId} - Project funding history
- GET /api/funding/stats - Funding statistics
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import asyncio

router = APIRouter(prefix="/api/funding", tags=["Funding Feed"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# Tier 1 investors for FOMO Score calculation
TIER1_INVESTORS = {
    "a16z", "andreessen horowitz", "paradigm", "sequoia", "polychain",
    "multicoin", "coinbase ventures", "binance labs", "pantera",
    "dragonfly", "framework", "electric capital", "placeholder",
    "variant", "haun ventures", "galaxy digital"
}

# Hot categories for scoring
HOT_CATEGORIES = {"ai", "depin", "gaming", "l2", "zk", "restaking", "rwa"}


def calculate_fomo_score(project: dict, funding: dict, investors: list) -> dict:
    """
    Calculate FOMO Score (0-100) for a funding round.
    
    Components:
    - 35% investor_quality (tier1 funds)
    - 25% amount_raised
    - 20% category_heat
    - 20% token_status
    """
    components = {}
    
    # 1. Investor Quality (35%)
    tier1_count = sum(1 for inv in investors if any(t in inv.lower() for t in TIER1_INVESTORS))
    investor_score = min(tier1_count * 20, 100)  # Max 5 tier1 = 100
    components["investor_quality"] = investor_score
    
    # 2. Amount Raised (25%)
    raised = funding.get("raised_usd", 0) or 0
    if raised >= 100_000_000:
        amount_score = 100
    elif raised >= 50_000_000:
        amount_score = 85
    elif raised >= 20_000_000:
        amount_score = 70
    elif raised >= 10_000_000:
        amount_score = 55
    elif raised >= 5_000_000:
        amount_score = 40
    elif raised >= 1_000_000:
        amount_score = 25
    else:
        amount_score = 10
    components["amount_raised"] = amount_score
    
    # 3. Category Heat (20%)
    category = project.get("category", "").lower()
    if any(hot in category for hot in HOT_CATEGORIES):
        category_score = 80
    else:
        category_score = 40
    components["category_heat"] = category_score
    
    # 4. Token Status (20%)
    has_token = project.get("symbol") and len(project.get("symbol", "")) > 0
    token_score = 70 if has_token else 30
    components["token_status"] = token_score
    
    # Calculate weighted total
    total = (
        components["investor_quality"] * 0.35 +
        components["amount_raised"] * 0.25 +
        components["category_heat"] * 0.20 +
        components["token_status"] * 0.20
    )
    
    return {
        "score": round(total),
        "components": components,
        "rank": None  # Calculated at list level
    }


def detect_red_flags(project: dict, funding: dict) -> dict:
    """
    Detect red flags in project/funding.
    """
    flags = []
    
    # Check for missing critical info
    if not project.get("website"):
        flags.append("no_website")
    
    # Anonymous team
    if not project.get("team") or len(project.get("team", [])) == 0:
        flags.append("no_team_info")
    
    # Very high valuation with low raised
    raised = funding.get("raised_usd", 0) or 0
    valuation = funding.get("valuation_usd", 0) or 0
    if valuation > 0 and raised > 0:
        if valuation / raised > 100:
            flags.append("extreme_valuation")
    
    # Very recent project with huge raise
    if raised > 50_000_000:
        created = project.get("created_at", "")
        if created:
            try:
                created_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
                if (datetime.now(timezone.utc) - created_date).days < 30:
                    flags.append("very_new_large_raise")
            except:
                pass
    
    return {
        "count": len(flags),
        "reasons": flags
    }


# ═══════════════════════════════════════════════════════════════
# FUNDING FEED
# ═══════════════════════════════════════════════════════════════

@router.get("/feed")
async def get_funding_feed(
    mode: str = Query("all", description="Mode: all, trending, new7d, smart"),
    category: str = Query(None, description="Filter by category"),
    search: str = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Main funding feed - list of funding rounds with FOMO Score.
    
    Modes:
    - all: All funding rounds, newest first
    - trending: High FOMO Score rounds
    - new7d: Rounds from last 7 days
    - smart: AI-selected interesting rounds
    """
    from server import db
    
    skip = (page - 1) * limit
    
    # Build query
    query = {}
    
    if mode == "new7d":
        seven_days_ago = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp() * 1000)
        query["round_date"] = {"$gte": seven_days_ago}
    
    if category:
        query["category"] = {"$regex": category, "$options": "i"}
    
    if search:
        query["$or"] = [
            {"project": {"$regex": search, "$options": "i"}},
            {"symbol": {"$regex": search, "$options": "i"}}
        ]
    
    # Get funding rounds
    cursor = db.intel_funding.find(query).sort("round_date", -1).skip(skip).limit(limit)
    rounds = await cursor.to_list(limit)
    
    # Get total count
    total = await db.intel_funding.count_documents(query)
    
    # Enrich with project data and scores
    items = []
    for funding in rounds:
        # Get project info
        project = await db.intel_projects.find_one({"key": funding.get("project_key")})
        if not project:
            project = {"name": funding.get("project", ""), "symbol": funding.get("symbol", "")}
        
        # Get investors
        investors = funding.get("investors", [])
        
        # Calculate FOMO Score
        fomo = calculate_fomo_score(project, funding, investors)
        
        # Detect red flags
        red_flags = detect_red_flags(project, funding)
        
        items.append({
            "round_id": funding.get("id", str(funding.get("_id", ""))),
            "project": {
                "key": funding.get("project_key"),
                "name": project.get("name", funding.get("project", "")),
                "symbol": funding.get("symbol", project.get("symbol", "")),
                "logo": project.get("logo_url", ""),
                "category": project.get("category", "")
            },
            "round": {
                "type": funding.get("round_type", "unknown"),
                "date": funding.get("round_date"),
                "raised_usd": funding.get("raised_usd"),
                "valuation_usd": funding.get("valuation_usd")
            },
            "investors": {
                "count": len(investors),
                "top": investors[:5],
                "lead": funding.get("lead_investors", [])
            },
            "token": {
                "has_token": bool(funding.get("symbol")),
                "symbol": funding.get("symbol")
            },
            "fomo_score": fomo,
            "red_flags": red_flags
        })
    
    # Sort by FOMO Score for trending mode
    if mode == "trending":
        items.sort(key=lambda x: x["fomo_score"]["score"], reverse=True)
    
    # Add ranks
    for i, item in enumerate(items):
        item["fomo_score"]["rank"] = skip + i + 1
    
    return {
        "ts": ts_now(),
        "mode": mode,
        "page": page,
        "limit": limit,
        "total": total,
        "items": items,
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# SPOTLIGHT
# ═══════════════════════════════════════════════════════════════

@router.get("/spotlight")
async def get_funding_spotlight(limit: int = Query(5, ge=1, le=10)):
    """
    Top spotlight cards - highest FOMO Score rounds from last 30 days.
    """
    from server import db
    
    thirty_days_ago = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp() * 1000)
    
    cursor = db.intel_funding.find({
        "round_date": {"$gte": thirty_days_ago}
    }).sort("raised_usd", -1).limit(50)
    
    rounds = await cursor.to_list(50)
    
    # Score and sort
    scored = []
    for funding in rounds:
        project = await db.intel_projects.find_one({"key": funding.get("project_key")})
        if not project:
            project = {}
        
        investors = funding.get("investors", [])
        fomo = calculate_fomo_score(project, funding, investors)
        
        scored.append({
            "funding": funding,
            "project": project,
            "fomo_score": fomo["score"]
        })
    
    scored.sort(key=lambda x: x["fomo_score"], reverse=True)
    
    items = []
    for item in scored[:limit]:
        funding = item["funding"]
        project = item["project"]
        
        items.append({
            "project": {
                "key": funding.get("project_key"),
                "name": project.get("name", funding.get("project", "")),
                "symbol": funding.get("symbol", project.get("symbol", "")),
                "logo": project.get("logo_url", ""),
                "category": project.get("category", "")
            },
            "round": {
                "type": funding.get("round_type"),
                "raised_usd": funding.get("raised_usd"),
                "valuation_usd": funding.get("valuation_usd")
            },
            "fomo_score": item["fomo_score"],
            "investors_top": funding.get("investors", [])[:3]
        })
    
    return {
        "ts": ts_now(),
        "items": items,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# ROUND DETAILS
# ═══════════════════════════════════════════════════════════════

@router.get("/round/{round_id}")
async def get_funding_round(round_id: str):
    """
    Get detailed funding round information.
    """
    from server import db
    
    funding = await db.intel_funding.find_one({"id": round_id})
    if not funding:
        raise HTTPException(status_code=404, detail="Round not found")
    
    # Remove MongoDB _id
    funding.pop("_id", None)
    funding.pop("raw_data", None)
    
    # Get project info
    project = await db.intel_projects.find_one({"key": funding.get("project_key")})
    if project:
        project.pop("_id", None)
    
    # Calculate scores
    investors = funding.get("investors", [])
    fomo = calculate_fomo_score(project or {}, funding, investors)
    red_flags = detect_red_flags(project or {}, funding)
    
    return {
        "ts": ts_now(),
        "round": funding,
        "project": project,
        "fomo_score": fomo,
        "red_flags": red_flags,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# PROJECT FUNDING HISTORY
# ═══════════════════════════════════════════════════════════════

@router.get("/project/{project_key}")
async def get_project_funding(project_key: str):
    """
    Get all funding rounds for a project.
    """
    from server import db
    
    # Get project
    project = await db.intel_projects.find_one({"key": project_key})
    if not project:
        project = await db.intel_projects.find_one({"slug": project_key})
    
    # Get all funding rounds
    cursor = db.intel_funding.find({"project_key": project_key}).sort("round_date", -1)
    rounds = await cursor.to_list(100)
    
    # Calculate totals
    total_raised = sum(r.get("raised_usd", 0) or 0 for r in rounds)
    
    # Get unique investors
    all_investors = set()
    for r in rounds:
        all_investors.update(r.get("investors", []))
    
    # Format rounds
    formatted_rounds = []
    for r in rounds:
        formatted_rounds.append({
            "id": r.get("id"),
            "type": r.get("round_type"),
            "date": r.get("round_date"),
            "raised_usd": r.get("raised_usd"),
            "valuation_usd": r.get("valuation_usd"),
            "investors": r.get("investors", []),
            "lead": r.get("lead_investors", [])
        })
    
    return {
        "ts": ts_now(),
        "project_key": project_key,
        "project": {
            "name": project.get("name") if project else project_key,
            "symbol": project.get("symbol") if project else None,
            "category": project.get("category") if project else None
        },
        "summary": {
            "total_rounds": len(rounds),
            "total_raised_usd": total_raised,
            "total_investors": len(all_investors),
            "last_round_date": rounds[0].get("round_date") if rounds else None
        },
        "rounds": formatted_rounds,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# FUNDING STATS
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_funding_stats():
    """
    Global funding statistics.
    """
    from server import db
    
    # Get totals
    total_rounds = await db.intel_funding.count_documents({})
    
    # Get recent stats (30 days)
    thirty_days_ago = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp() * 1000)
    recent_rounds = await db.intel_funding.count_documents({"round_date": {"$gte": thirty_days_ago}})
    
    # Calculate total raised (all time)
    pipeline = [
        {"$group": {"_id": None, "total": {"$sum": "$raised_usd"}}}
    ]
    result = await db.intel_funding.aggregate(pipeline).to_list(1)
    total_raised = result[0]["total"] if result else 0
    
    # Calculate recent raised (30 days)
    pipeline = [
        {"$match": {"round_date": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": None, "total": {"$sum": "$raised_usd"}}}
    ]
    result = await db.intel_funding.aggregate(pipeline).to_list(1)
    recent_raised = result[0]["total"] if result else 0
    
    # Top categories (30 days)
    pipeline = [
        {"$match": {"round_date": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}, "raised": {"$sum": "$raised_usd"}}},
        {"$sort": {"raised": -1}},
        {"$limit": 10}
    ]
    categories = await db.intel_funding.aggregate(pipeline).to_list(10)
    
    return {
        "ts": ts_now(),
        "all_time": {
            "total_rounds": total_rounds,
            "total_raised_usd": total_raised
        },
        "last_30_days": {
            "rounds": recent_rounds,
            "raised_usd": recent_raised
        },
        "top_categories": [
            {"category": c["_id"] or "other", "rounds": c["count"], "raised_usd": c["raised"]}
            for c in categories
        ],
        "_meta": {"cache_sec": 300}
    }
