"""
FOMO ICO / Echo API
==================
ICO projects listing, details, and statistics.

Endpoints:
- GET /api/ico/projects - List ICO projects
- GET /api/ico/{projectId} - ICO project details
- GET /api/ico/stats - ICO statistics
- GET /api/ico/calendar - ICO calendar
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/ico", tags=["ICO / Echo"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ═══════════════════════════════════════════════════════════════
# ICO PROJECTS LIST
# ═══════════════════════════════════════════════════════════════

@router.get("/projects")
async def list_ico_projects(
    status: str = Query("all", description="Status: all, active, upcoming, ended"),
    category: str = Query(None, description="Filter by category"),
    search: str = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List ICO/IEO/IDO projects.
    """
    from server import db
    
    skip = (page - 1) * limit
    now = ts_now()
    
    # Build query - look for sales in intel_sales or funding with token_sale=true
    query = {}
    
    if status == "active":
        query["$and"] = [
            {"start_date": {"$lte": now}},
            {"end_date": {"$gte": now}}
        ]
    elif status == "upcoming":
        query["start_date"] = {"$gt": now}
    elif status == "ended":
        query["end_date"] = {"$lt": now}
    
    if category:
        query["category"] = {"$regex": category, "$options": "i"}
    
    if search:
        query["$or"] = [
            {"project": {"$regex": search, "$options": "i"}},
            {"symbol": {"$regex": search, "$options": "i"}}
        ]
    
    # Try intel_sales collection first
    try:
        cursor = db.intel_sales.find(query).sort("start_date", -1).skip(skip).limit(limit)
        sales = await cursor.to_list(limit)
        total = await db.intel_sales.count_documents(query)
    except:
        sales = []
        total = 0
    
    # If no sales collection, use funding rounds with token_sale flag
    if not sales:
        query_funding = {}
        if search:
            query_funding["$or"] = [
                {"project": {"$regex": search, "$options": "i"}},
                {"symbol": {"$regex": search, "$options": "i"}}
            ]
        
        cursor = db.intel_funding.find(query_funding).sort("round_date", -1).skip(skip).limit(limit)
        funding_rounds = await cursor.to_list(limit)
        total = await db.intel_funding.count_documents(query_funding)
        
        # Convert funding to ICO-like format
        for r in funding_rounds:
            sales.append({
                "id": r.get("id"),
                "project": r.get("project"),
                "project_key": r.get("project_key"),
                "symbol": r.get("symbol"),
                "sale_type": r.get("round_type", "private"),
                "platform": "",
                "start_date": r.get("round_date"),
                "end_date": None,
                "raise_usd": r.get("raised_usd"),
                "roi_usd": None,
                "status": "ended"
            })
    
    items = []
    for sale in sales:
        # Determine status
        start = sale.get("start_date")
        end = sale.get("end_date")
        
        if start and end:
            if now < start:
                calc_status = "upcoming"
            elif now > end:
                calc_status = "ended"
            else:
                calc_status = "active"
        else:
            calc_status = "ended"
        
        # Calculate progress if active
        progress = 0
        if calc_status == "active" and sale.get("raise_target_usd") and sale.get("raise_usd"):
            progress = min(sale["raise_usd"] / sale["raise_target_usd"] * 100, 100)
        
        # Get project info
        project = await db.intel_projects.find_one({"key": sale.get("project_key")})
        
        items.append({
            "id": sale.get("id", str(sale.get("_id", ""))),
            "project": {
                "key": sale.get("project_key"),
                "name": project.get("name") if project else sale.get("project"),
                "symbol": sale.get("symbol"),
                "logo": project.get("logo_url") if project else None,
                "category": project.get("category") if project else None
            },
            "sale": {
                "type": sale.get("sale_type"),
                "platform": sale.get("platform"),
                "status": calc_status,
                "start_date": start,
                "end_date": end
            },
            "financials": {
                "raised_usd": sale.get("raise_usd"),
                "target_usd": sale.get("raise_target_usd"),
                "progress_pct": round(progress, 1),
                "price_usd": sale.get("price_usd")
            },
            "roi": {
                "current": sale.get("roi_usd"),
                "ath": sale.get("ath_roi_usd")
            }
        })
    
    return {
        "ts": ts_now(),
        "status": status,
        "page": page,
        "limit": limit,
        "total": total,
        "items": items,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# ICO STATS (must be before /{project_id})
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_ico_stats():
    """
    Global ICO statistics.
    """
    from server import db
    
    now = ts_now()
    thirty_days_ago = now - (30 * 24 * 60 * 60 * 1000)
    
    # Try sales collection first
    try:
        total_sales = await db.intel_sales.count_documents({})
        active = await db.intel_sales.count_documents({
            "start_date": {"$lte": now},
            "end_date": {"$gte": now}
        })
        upcoming = await db.intel_sales.count_documents({
            "start_date": {"$gt": now}
        })
        
        # Total raised
        pipeline = [
            {"$group": {"_id": None, "total": {"$sum": "$raise_usd"}}}
        ]
        result = await db.intel_sales.aggregate(pipeline).to_list(1)
        total_raised = result[0]["total"] if result else 0
        
    except:
        # Fallback to funding data
        total_sales = await db.intel_funding.count_documents({})
        active = 0
        upcoming = 0
        
        pipeline = [
            {"$group": {"_id": None, "total": {"$sum": "$raised_usd"}}}
        ]
        result = await db.intel_funding.aggregate(pipeline).to_list(1)
        total_raised = result[0]["total"] if result else 0
    
    # Top categories
    try:
        pipeline = [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        categories = await db.intel_funding.aggregate(pipeline).to_list(10)
    except:
        categories = []
    
    return {
        "ts": ts_now(),
        "overview": {
            "total_projects": total_sales,
            "active": active,
            "upcoming": upcoming,
            "total_raised_usd": total_raised
        },
        "trending_categories": [
            {"category": c["_id"] or "other", "count": c["count"]}
            for c in categories
        ],
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# ICO CALENDAR (must be before /{project_id})
# ═══════════════════════════════════════════════════════════════

@router.get("/calendar")
async def get_ico_calendar(
    days: int = Query(30, ge=1, le=90, description="Days ahead to look")
):
    """
    Upcoming ICO calendar.
    """
    from server import db
    
    now = ts_now()
    future = now + (days * 24 * 60 * 60 * 1000)
    
    # Try sales collection
    try:
        cursor = db.intel_sales.find({
            "start_date": {"$gte": now, "$lte": future}
        }).sort("start_date", 1).limit(50)
        
        upcoming = await cursor.to_list(50)
    except:
        upcoming = []
    
    events = []
    for sale in upcoming:
        project = await db.intel_projects.find_one({"key": sale.get("project_key")})
        
        events.append({
            "date": sale.get("start_date"),
            "type": "ico_start",
            "project": {
                "key": sale.get("project_key"),
                "name": project.get("name") if project else sale.get("project"),
                "symbol": sale.get("symbol"),
                "category": project.get("category") if project else None
            },
            "sale": {
                "type": sale.get("sale_type"),
                "platform": sale.get("platform"),
                "target_usd": sale.get("raise_target_usd")
            }
        })
    
    return {
        "ts": ts_now(),
        "days_ahead": days,
        "events_count": len(events),
        "events": events,
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# ICO PROJECT DETAILS (dynamic route must be last)
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}")
async def get_ico_project(project_id: str):
    """
    Get detailed ICO project information.
    """
    from server import db
    
    # Try to find sale
    sale = await db.intel_sales.find_one({
        "$or": [
            {"id": project_id},
            {"project_key": project_id}
        ]
    })
    
    # If no sale, try funding
    if not sale:
        sale = await db.intel_funding.find_one({
            "$or": [
                {"id": project_id},
                {"project_key": project_id}
            ]
        })
    
    if not sale:
        raise HTTPException(status_code=404, detail="ICO project not found")
    
    sale.pop("_id", None)
    sale.pop("raw_data", None)
    
    # Get project info
    project = await db.intel_projects.find_one({"key": sale.get("project_key")})
    if project:
        project.pop("_id", None)
    
    # Get tokenomics if available
    tokenomics = await db.intel_tokenomics.find_one({"project_key": sale.get("project_key")}) if hasattr(db, "intel_tokenomics") else None
    if tokenomics:
        tokenomics.pop("_id", None)
    
    # Get investors
    investors = sale.get("investors", [])
    
    return {
        "ts": ts_now(),
        "sale": {
            "id": sale.get("id"),
            "type": sale.get("sale_type", sale.get("round_type")),
            "platform": sale.get("platform", ""),
            "start_date": sale.get("start_date", sale.get("round_date")),
            "end_date": sale.get("end_date"),
            "price_usd": sale.get("price_usd"),
            "raised_usd": sale.get("raise_usd", sale.get("raised_usd")),
            "target_usd": sale.get("raise_target_usd")
        },
        "project": project,
        "tokenomics": tokenomics,
        "investors": investors,
        "roi": {
            "current": sale.get("roi_usd"),
            "ath": sale.get("ath_roi_usd"),
            "current_price": sale.get("current_price_usd")
        },
        "_meta": {"cache_sec": 300}
    }

