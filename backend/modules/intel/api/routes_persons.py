"""
FOMO Persons Analytics API
==========================
Person profiles, portfolios, and performance analytics.

Endpoints:
- GET /api/persons - List persons
- GET /api/persons/{personId} - Person profile
- GET /api/persons/{personId}/portfolio - Person portfolio
- GET /api/persons/{personId}/investments - Person investments
- GET /api/persons/{personId}/performance - Person performance
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/persons", tags=["Persons"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ═══════════════════════════════════════════════════════════════
# PERSONS LIST
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def list_persons(
    search: str = Query(None, description="Search by name"),
    role: str = Query(None, description="Filter by role"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List all persons (founders, investors, team members).
    """
    from server import db
    
    skip = (page - 1) * limit
    
    query = {}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    if role:
        query["role"] = {"$regex": role, "$options": "i"}
    
    cursor = db.intel_persons.find(query).sort("name", 1).skip(skip).limit(limit)
    persons = await cursor.to_list(limit)
    
    total = await db.intel_persons.count_documents(query)
    
    items = []
    for person in persons:
        items.append({
            "id": person.get("key", str(person.get("_id", ""))),
            "name": person.get("name", ""),
            "slug": person.get("slug", ""),
            "role": person.get("role", ""),
            "photo": person.get("photo_url", ""),
            "twitter": person.get("twitter", ""),
            "linkedin": person.get("linkedin", ""),
            "projects": person.get("projects", [])[:5]
        })
    
    return {
        "ts": ts_now(),
        "page": page,
        "limit": limit,
        "total": total,
        "items": items,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# PERSON PROFILE
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}")
async def get_person_profile(person_id: str):
    """
    Get detailed person profile.
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [
            {"key": person_id},
            {"slug": person_id}
        ]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person.pop("_id", None)
    
    # Get projects this person is associated with
    projects = person.get("projects", [])
    
    # Get funding rounds for these projects
    project_count = len(projects)
    
    return {
        "ts": ts_now(),
        "person": {
            "id": person.get("key"),
            "name": person.get("name"),
            "slug": person.get("slug"),
            "role": person.get("role"),
            "bio": person.get("bio", ""),
            "photo": person.get("photo_url", ""),
            "twitter": person.get("twitter", ""),
            "linkedin": person.get("linkedin", "")
        },
        "stats": {
            "projects_count": project_count,
            "projects": projects[:10]
        },
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# PERSON PORTFOLIO
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}/portfolio")
async def get_person_portfolio(person_id: str, limit: int = Query(50, ge=1, le=100)):
    """
    Get person's project portfolio.
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [{"key": person_id}, {"slug": person_id}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    projects_keys = person.get("projects", [])
    
    # Get project details
    portfolio = []
    for key in projects_keys[:limit]:
        project = await db.intel_projects.find_one({"key": key})
        if project:
            portfolio.append({
                "key": key,
                "name": project.get("name"),
                "symbol": project.get("symbol"),
                "category": project.get("category"),
                "logo": project.get("logo_url"),
                "role": person.get("role")
            })
    
    return {
        "ts": ts_now(),
        "person_id": person_id,
        "person_name": person.get("name"),
        "portfolio_count": len(portfolio),
        "portfolio": portfolio,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# PERSON INVESTMENTS
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}/investments")
async def get_person_investments(person_id: str, limit: int = Query(50, ge=1, le=100)):
    """
    Get person's investment history (if angel investor).
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [{"key": person_id}, {"slug": person_id}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person_name = person.get("name", "")
    
    # Search for funding rounds where this person is mentioned
    cursor = db.intel_funding.find({
        "investors": {"$regex": person_name, "$options": "i"}
    }).sort("round_date", -1).limit(limit)
    
    rounds = await cursor.to_list(limit)
    
    investments = []
    for round in rounds:
        investments.append({
            "project": round.get("project"),
            "project_key": round.get("project_key"),
            "symbol": round.get("symbol"),
            "round_type": round.get("round_type"),
            "date": round.get("round_date"),
            "raised_usd": round.get("raised_usd")
        })
    
    return {
        "ts": ts_now(),
        "person_id": person_id,
        "person_name": person_name,
        "investments_count": len(investments),
        "investments": investments,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# PERSON PERFORMANCE
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}/performance")
async def get_person_performance(person_id: str):
    """
    Get person performance metrics.
    """
    # Get investments
    investments_data = await get_person_investments(person_id, limit=100)
    
    investments = investments_data["investments"]
    
    if not investments:
        return {
            "ts": ts_now(),
            "person_id": person_id,
            "person_name": investments_data["person_name"],
            "performance": {
                "investments_count": 0,
                "total_invested_usd": 0,
                "message": "No investment data available"
            },
            "_meta": {"cache_sec": 300}
        }
    
    # Calculate basic stats
    total_raised = sum(i.get("raised_usd", 0) or 0 for i in investments)
    
    # Categories breakdown
    categories = {}
    for inv in investments:
        cat = "other"
        categories[cat] = categories.get(cat, 0) + 1
    
    return {
        "ts": ts_now(),
        "person_id": person_id,
        "person_name": investments_data["person_name"],
        "performance": {
            "investments_count": len(investments),
            "total_raised_in_rounds": total_raised,
            "categories": [
                {"category": k, "count": v}
                for k, v in sorted(categories.items(), key=lambda x: -x[1])
            ]
        },
        "_meta": {"cache_sec": 300, "note": "Performance metrics are estimates"}
    }


# ═══════════════════════════════════════════════════════════════
# PERSONS LEADERBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/leaderboard/active")
async def get_persons_leaderboard(limit: int = Query(20, ge=1, le=50)):
    """
    Get most active persons leaderboard.
    """
    from server import db
    
    # Get persons with most projects
    cursor = db.intel_persons.find({}).sort("projects", -1).limit(limit)
    persons = await cursor.to_list(limit)
    
    leaderboard = []
    for i, person in enumerate(persons):
        projects = person.get("projects", [])
        leaderboard.append({
            "rank": i + 1,
            "person": {
                "id": person.get("key"),
                "name": person.get("name"),
                "role": person.get("role"),
                "photo": person.get("photo_url")
            },
            "projects_count": len(projects) if isinstance(projects, list) else 0
        })
    
    return {
        "ts": ts_now(),
        "leaderboard": leaderboard,
        "_meta": {"cache_sec": 600}
    }
