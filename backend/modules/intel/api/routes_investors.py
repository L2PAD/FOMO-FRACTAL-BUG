"""
FOMO Unified Investors API
===========================
Unified investor layer - could be Fund, Angel, DAO, Exchange, Family Office.

Endpoints:
- GET /api/investors - List all investors
- GET /api/investors/{id} - Investor profile
- GET /api/investors/{id}/investments - Investments
- GET /api/investors/{id}/network - Co-investor network
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

router = APIRouter(prefix="/api/investors", tags=["Investors (Unified)"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ═══════════════════════════════════════════════════════════════
# INVESTORS LIST
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def list_investors(
    type: str = Query(None, description="Type: fund, angel, exchange, dao"),
    tier: int = Query(None, description="Filter by tier: 1, 2, 3, 4"),
    search: str = Query(None, description="Search by name"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List all investors (funds, angels, exchanges, DAOs).
    """
    from server import db
    
    skip = (page - 1) * limit
    
    query = {}
    if type:
        query["investor_type"] = type
    if tier:
        query["tier"] = tier
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    
    # Get from intel_investors
    cursor = db.intel_investors.find(query).sort("investments_count", -1).skip(skip).limit(limit)
    investors = await cursor.to_list(limit)
    
    total = await db.intel_investors.count_documents(query)
    
    items = []
    for inv in investors:
        # Determine type
        name_lower = inv.get("name", "").lower()
        if "ventures" in name_lower or "capital" in name_lower or "labs" in name_lower:
            inv_type = "fund"
        elif "exchange" in name_lower or inv.get("name") in ["Binance", "Coinbase", "OKX"]:
            inv_type = "exchange"
        else:
            inv_type = inv.get("investor_type", "fund")
        
        items.append({
            "id": inv.get("id", str(inv.get("_id", ""))),
            "name": inv.get("name", ""),
            "investor_type": inv_type,
            "fund_id": inv.get("id") if inv_type == "fund" else None,
            "person_id": None,
            "tier": inv.get("tier", 3),
            "location": inv.get("region", ""),
            "stats": {
                "total_deals": inv.get("investments_count", 0),
                "deals_12m": 0,  # Would need calculation
                "last_deal_at": None
            },
            "focus": {
                "stage": inv.get("stage_focus", []),
                "sectors": inv.get("sector_focus", [])
            },
            "links": {
                "website": inv.get("website"),
                "twitter": inv.get("twitter")
            }
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
# INVESTOR PROFILE
# ═══════════════════════════════════════════════════════════════

@router.get("/{investor_id}")
async def get_investor_profile(investor_id: str):
    """
    Get investor profile (unified view).
    """
    from server import db
    
    investor = await db.intel_investors.find_one({
        "$or": [{"id": investor_id}, {"slug": investor_id}]
    })
    
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")
    
    # Get investments
    cursor = db.intel_funding.find({
        "investors": {"$regex": investor.get("name", ""), "$options": "i"}
    })
    investments = await cursor.to_list(200)
    
    # Determine type
    name_lower = investor.get("name", "").lower()
    if "ventures" in name_lower or "capital" in name_lower:
        inv_type = "fund"
    else:
        inv_type = investor.get("investor_type", "fund")
    
    return {
        "ts": ts_now(),
        "investor": {
            "id": investor.get("id", str(investor.get("_id", ""))),
            "name": investor.get("name"),
            "investor_type": inv_type,
            "tier": investor.get("tier", 3),
            "location": investor.get("region"),
            "website": investor.get("website"),
            "twitter": investor.get("twitter"),
            "description": investor.get("description")
        },
        "stats": {
            "total_deals": len(investments),
            "portfolio": investor.get("portfolio", [])[:10],
            "focus_sectors": list(set(inv.get("category", "other") for inv in investments))[:5]
        },
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# INVESTOR INVESTMENTS
# ═══════════════════════════════════════════════════════════════

@router.get("/{investor_id}/investments")
async def get_investor_investments(investor_id: str, limit: int = Query(50, ge=1, le=100)):
    """
    Get investor's investment history.
    """
    from server import db
    
    investor = await db.intel_investors.find_one({
        "$or": [{"id": investor_id}, {"slug": investor_id}]
    })
    
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")
    
    investor_name = investor.get("name", "")
    
    cursor = db.intel_funding.find({
        "investors": {"$regex": investor_name, "$options": "i"}
    }).sort("round_date", -1).limit(limit)
    
    rounds = await cursor.to_list(limit)
    
    investments = []
    for funding_round in rounds:
        is_lead = investor_name.lower() in [l.lower() for l in funding_round.get("lead_investors", [])]
        
        investments.append({
            "project": funding_round.get("project"),
            "project_key": funding_round.get("project_key"),
            "symbol": funding_round.get("symbol"),
            "round_type": funding_round.get("round_type"),
            "date": funding_round.get("round_date"),
            "raised_usd": funding_round.get("raised_usd"),
            "role": "lead" if is_lead else "participant"
        })
    
    return {
        "ts": ts_now(),
        "investor_id": investor_id,
        "investor_name": investor_name,
        "investments_count": len(investments),
        "investments": investments,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# INVESTOR NETWORK
# ═══════════════════════════════════════════════════════════════

@router.get("/{investor_id}/network")
async def get_investor_network(investor_id: str, limit: int = Query(20, ge=1, le=50)):
    """
    Get investor's co-investment network.
    """
    from server import db
    
    investor = await db.intel_investors.find_one({
        "$or": [{"id": investor_id}, {"slug": investor_id}]
    })
    
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")
    
    investor_name = investor.get("name", "")
    
    # Get all rounds
    cursor = db.intel_funding.find({
        "investors": {"$regex": investor_name, "$options": "i"}
    })
    rounds = await cursor.to_list(200)
    
    # Build network
    network = {}
    for funding_round in rounds:
        for other in funding_round.get("investors", []):
            if other.lower() != investor_name.lower():
                key = other.lower()
                if key not in network:
                    network[key] = {"name": other, "count": 0}
                network[key]["count"] += 1
    
    sorted_network = sorted(network.values(), key=lambda x: -x["count"])[:limit]
    
    return {
        "ts": ts_now(),
        "investor_id": investor_id,
        "investor_name": investor_name,
        "network": sorted_network,
        "_meta": {"cache_sec": 600}
    }
