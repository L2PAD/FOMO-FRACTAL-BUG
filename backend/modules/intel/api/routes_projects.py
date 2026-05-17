"""
FOMO Projects Profile API
=========================
Project profiles with market data, exchanges, tokenomics, and investors.

Endpoints:
- GET /api/projects - List projects
- GET /api/projects/{id}/profile - Project profile
- GET /api/projects/{id}/exchanges - Project exchanges
- GET /api/projects/{id}/investors - Project investors
- GET /api/projects/{id}/funding - Project funding history
- GET /api/projects/{id}/token - Project token info
- GET /api/projects/{id}/related - Related projects
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

router = APIRouter(prefix="/api/projects", tags=["Projects"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ═══════════════════════════════════════════════════════════════
# PROJECTS LIST
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def list_projects(
    search: str = Query(None, description="Search by name or symbol"),
    category: str = Query(None, description="Filter by category"),
    tags: str = Query(None, description="Filter by tags (comma-separated)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List all projects.
    """
    from server import db
    
    skip = (page - 1) * limit
    
    query = {}
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"symbol": {"$regex": search, "$options": "i"}},
            {"key": {"$regex": search, "$options": "i"}}
        ]
    
    if category:
        query["category"] = {"$regex": category, "$options": "i"}
    
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        query["tags"] = {"$in": tag_list}
    
    cursor = db.intel_projects.find(query).sort("name", 1).skip(skip).limit(limit)
    projects = await cursor.to_list(limit)
    
    total = await db.intel_projects.count_documents(query)
    
    items = []
    for p in projects:
        items.append({
            "key": p.get("key"),
            "name": p.get("name"),
            "symbol": p.get("symbol"),
            "category": p.get("category"),
            "logo": p.get("logo_url"),
            "slug": p.get("slug"),
            "source": p.get("source")
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
# PROJECT PROFILE
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/profile")
async def get_project_profile(project_id: str):
    """
    Get comprehensive project profile with market data.
    """
    from server import db
    
    # Find project
    project = await db.intel_projects.find_one({
        "$or": [
            {"key": project_id},
            {"slug": project_id},
            {"symbol": project_id.upper()}
        ]
    })
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project.pop("_id", None)
    
    symbol = project.get("symbol", "")
    
    # Try to get market data
    market_data = None
    try:
        from modules.market_data.api.market_routes import get_quote
        quote = await get_quote(symbol)
        market_data = {
            "price": quote.get("price"),
            "change_1h": quote.get("change_1h"),
            "change_24h": quote.get("change_24h"),
            "change_7d": quote.get("change_7d"),
            "volume_24h": quote.get("volume_24h"),
            "market_cap": quote.get("market_cap"),
            "fdv": quote.get("fdv")
        }
    except:
        pass
    
    # Get funding summary
    cursor = db.intel_funding.find({"project_key": project.get("key")})
    funding_rounds = await cursor.to_list(50)
    
    total_raised = sum(r.get("raised_usd", 0) or 0 for r in funding_rounds)
    
    # Get unique investors
    all_investors = set()
    for r in funding_rounds:
        all_investors.update(r.get("investors", []))
    
    return {
        "ts": ts_now(),
        "project": {
            "key": project.get("key"),
            "name": project.get("name"),
            "symbol": symbol,
            "category": project.get("category"),
            "description": project.get("description", ""),
            "logo": project.get("logo_url"),
            "website": project.get("website"),
            "twitter": project.get("twitter"),
            "discord": project.get("discord"),
            "github": project.get("github"),
            "contracts": project.get("contracts", [])
        },
        "market": market_data,
        "funding_summary": {
            "total_rounds": len(funding_rounds),
            "total_raised_usd": total_raised,
            "total_investors": len(all_investors),
            "last_round": funding_rounds[0].get("round_type") if funding_rounds else None,
            "last_round_date": funding_rounds[0].get("round_date") if funding_rounds else None
        },
        "_meta": {"cache_sec": 120}
    }


# ═══════════════════════════════════════════════════════════════
# PROJECT EXCHANGES
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/exchanges")
async def get_project_exchanges(
    project_id: str,
    market: str = Query("all", description="Market type: all, spot, derivative, dex")
):
    """
    Get exchanges where project token is traded.
    """
    from server import db
    
    # Find project
    project = await db.intel_projects.find_one({
        "$or": [
            {"key": project_id},
            {"slug": project_id},
            {"symbol": project_id.upper()}
        ]
    })
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    symbol = project.get("symbol", "")
    
    # Try to get exchange data from market routes
    exchanges = []
    try:
        from modules.market_data.api.market_routes import get_exchanges_for_token
        result = await get_exchanges_for_token(symbol)
        exchanges = result.get("exchanges", [])
    except:
        pass
    
    # Filter by market type if needed
    if market != "all" and exchanges:
        exchanges = [e for e in exchanges if e.get("market_type") == market]
    
    # Calculate summary
    total_volume = sum(e.get("volume_24h", 0) or 0 for e in exchanges)
    
    # Find dominant exchange
    top_exchange = None
    if exchanges:
        sorted_ex = sorted(exchanges, key=lambda x: x.get("volume_24h", 0) or 0, reverse=True)
        if sorted_ex:
            top_exchange = sorted_ex[0].get("exchange")
    
    # Calculate concentration (HHI)
    hhi = 0
    if total_volume > 0 and exchanges:
        for ex in exchanges:
            share = (ex.get("volume_24h", 0) or 0) / total_volume
            hhi += share * share * 10000
    
    return {
        "ts": ts_now(),
        "project_key": project_id,
        "symbol": symbol,
        "market_filter": market,
        "summary": {
            "total_exchanges": len(exchanges),
            "total_volume_24h": total_volume,
            "top_exchange": top_exchange,
            "concentration_hhi": round(hhi, 1)
        },
        "exchanges": exchanges,
        "_meta": {"cache_sec": 120}
    }


# ═══════════════════════════════════════════════════════════════
# PROJECT INVESTORS
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/investors")
async def get_project_investors(project_id: str):
    """
    Get all investors who funded this project.
    """
    from server import db
    
    # Find project
    project = await db.intel_projects.find_one({
        "$or": [
            {"key": project_id},
            {"slug": project_id}
        ]
    })
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get funding rounds
    cursor = db.intel_funding.find({"project_key": project.get("key")})
    funding_rounds = await cursor.to_list(50)
    
    # Aggregate investors
    investor_data = {}
    
    for round in funding_rounds:
        round_type = round.get("round_type", "unknown")
        round_date = round.get("round_date")
        lead_investors = round.get("lead_investors", [])
        
        for inv in round.get("investors", []):
            key = inv.lower()
            if key not in investor_data:
                investor_data[key] = {
                    "name": inv,
                    "rounds": [],
                    "is_lead": False,
                    "first_investment": round_date
                }
            
            investor_data[key]["rounds"].append({
                "type": round_type,
                "date": round_date
            })
            
            if inv in lead_investors:
                investor_data[key]["is_lead"] = True
            
            if round_date and (not investor_data[key]["first_investment"] or round_date < investor_data[key]["first_investment"]):
                investor_data[key]["first_investment"] = round_date
    
    # Convert to list and sort
    investors = sorted(
        investor_data.values(),
        key=lambda x: (not x["is_lead"], -len(x["rounds"]))
    )
    
    return {
        "ts": ts_now(),
        "project_key": project_id,
        "project_name": project.get("name"),
        "total_investors": len(investors),
        "investors": [
            {
                "name": inv["name"],
                "is_lead": inv["is_lead"],
                "rounds_participated": len(inv["rounds"]),
                "rounds": inv["rounds"],
                "first_investment": inv["first_investment"]
            }
            for inv in investors
        ],
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# PROJECT FUNDING
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/funding")
async def get_project_funding(project_id: str):
    """
    Get complete funding history for project.
    """
    from modules.intel.api.routes_funding import get_project_funding as _get_project_funding
    
    return await _get_project_funding(project_id)


# ═══════════════════════════════════════════════════════════════
# PROJECT TOKEN
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/token")
async def get_project_token(project_id: str):
    """
    Get token information for project.
    """
    from server import db
    
    # Find project
    project = await db.intel_projects.find_one({
        "$or": [
            {"key": project_id},
            {"slug": project_id}
        ]
    })
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    symbol = project.get("symbol", "")
    
    # Get market data
    token_data = {
        "symbol": symbol,
        "name": project.get("name"),
        "contracts": project.get("contracts", [])
    }
    
    # Try to get current market data
    try:
        from modules.market_data.api.market_routes import get_quote
        quote = await get_quote(symbol)
        token_data["market"] = {
            "price": quote.get("price"),
            "market_cap": quote.get("market_cap"),
            "fdv": quote.get("fdv"),
            "volume_24h": quote.get("volume_24h"),
            "circulating_supply": quote.get("circulating_supply"),
            "total_supply": quote.get("total_supply"),
            "max_supply": quote.get("max_supply")
        }
    except:
        token_data["market"] = None
    
    # Try to get tokenomics
    try:
        from modules.market_data.api.tokenomics_routes import get_tokenomics_overview
        tokenomics = await get_tokenomics_overview(symbol)
        token_data["tokenomics"] = tokenomics.get("allocation")
    except:
        token_data["tokenomics"] = None
    
    return {
        "ts": ts_now(),
        "project_key": project_id,
        "token": token_data,
        "_meta": {"cache_sec": 120}
    }


# ═══════════════════════════════════════════════════════════════
# RELATED PROJECTS
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/related")
async def get_related_projects(project_id: str, limit: int = Query(10, ge=1, le=20)):
    """
    Get projects related by category, investors, or other signals.
    """
    from server import db
    
    # Find project
    project = await db.intel_projects.find_one({
        "$or": [
            {"key": project_id},
            {"slug": project_id}
        ]
    })
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    category = project.get("category")
    project_key = project.get("key")
    
    # Find projects in same category
    related = []
    
    if category:
        cursor = db.intel_projects.find({
            "category": category,
            "key": {"$ne": project_key}
        }).limit(limit)
        
        category_projects = await cursor.to_list(limit)
        
        for p in category_projects:
            related.append({
                "key": p.get("key"),
                "name": p.get("name"),
                "symbol": p.get("symbol"),
                "category": p.get("category"),
                "logo": p.get("logo_url"),
                "relation": "same_category"
            })
    
    # Find projects with same investors
    cursor = db.intel_funding.find({"project_key": project_key})
    our_rounds = await cursor.to_list(50)
    
    our_investors = set()
    for r in our_rounds:
        our_investors.update(r.get("investors", []))
    
    if our_investors and len(related) < limit:
        # Find other projects funded by same investors
        for investor in list(our_investors)[:5]:
            cursor = db.intel_funding.find({
                "investors": {"$regex": investor, "$options": "i"},
                "project_key": {"$ne": project_key}
            }).limit(5)
            
            other_rounds = await cursor.to_list(5)
            
            for r in other_rounds:
                if len(related) >= limit:
                    break
                
                other_project = await db.intel_projects.find_one({"key": r.get("project_key")})
                if other_project and not any(rel["key"] == r.get("project_key") for rel in related):
                    related.append({
                        "key": r.get("project_key"),
                        "name": other_project.get("name", r.get("project")),
                        "symbol": r.get("symbol"),
                        "category": other_project.get("category"),
                        "logo": other_project.get("logo_url"),
                        "relation": f"shared_investor:{investor}"
                    })
    
    return {
        "ts": ts_now(),
        "project_key": project_id,
        "related_count": len(related),
        "related": related[:limit],
        "_meta": {"cache_sec": 600}
    }
