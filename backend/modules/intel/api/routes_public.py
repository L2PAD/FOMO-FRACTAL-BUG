"""
Public API Layer - Full Architecture
=====================================

Entities:
- Global (market stats, trending, feed)
- Projects (tokens + ecosystem)
- Exchanges (trading venues)
- Funds (VCs, investors)
- Persons (people in crypto)
- Fundraising (investment rounds)
- Unlocks (token vesting)
- ICO (token sales)
- Events (unified event stream)
- Portfolio (cross-entity holdings)
- Search (unified search)
"""

from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import re

router = APIRouter(prefix="/api/v1", tags=["Public API v1"])


def get_db():
    from server import db
    return db


def _now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _clean_doc(doc):
    """Remove MongoDB _id from document"""
    if doc and '_id' in doc:
        del doc['_id']
    return doc


def _clean_docs(docs):
    """Remove MongoDB _id from list of documents"""
    return [_clean_doc(d) for d in docs]


# ═══════════════════════════════════════════════════════════════
# GLOBAL LAYER - Market Overview
# ═══════════════════════════════════════════════════════════════

@router.get("/global/stats")
async def get_global_stats(db=Depends(get_db)):
    """
    Global market statistics.
    
    Returns:
    - Total market cap
    - 24h volume
    - BTC dominance
    - Active projects count
    - Total funds count
    """
    # Get from intel_market or calculate
    market = await db.intel_market.find_one({"key": "global_stats"}, {"_id": 0})
    
    if not market:
        # Calculate from collections
        projects = await db.intel_projects.count_documents({})
        funds = await db.intel_investors.count_documents({})
        unlocks = await db.intel_unlocks.count_documents({})
        funding = await db.intel_fundraising.count_documents({})
        
        market = {
            "total_projects": projects,
            "total_funds": funds,
            "upcoming_unlocks": unlocks,
            "recent_funding_rounds": funding
        }
    
    return {"ts": _now_ms(), "data": market}


@router.get("/global/trending")
async def get_global_trending(
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db)
):
    """
    Trending projects right now.
    
    Based on:
    - Recent funding
    - Upcoming unlocks
    - Trading volume
    """
    # Get trending from intel_trending or intel_market
    cursor = db.intel_market.find(
        {"trending": True}, 
        {"_id": 0}
    ).limit(limit)
    items = await cursor.to_list(limit)
    
    if not items:
        # Fallback to recent funding as trending
        cursor = db.intel_fundraising.find({}, {"_id": 0}).sort("date", -1).limit(limit)
        items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/global/gainers")
async def get_global_gainers(
    period: str = Query("24h", description="Period: 1h, 24h, 7d"),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db)
):
    """Top gainers by price change"""
    cursor = db.intel_market.find(
        {"type": "gainer"},
        {"_id": 0}
    ).sort(f"price_change_{period}", -1).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "period": period, "count": len(items), "data": items}


@router.get("/global/accumulation")
async def get_global_accumulation(
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db)
):
    """Projects with high accumulation signals"""
    cursor = db.intel_market.find(
        {"accumulation_score": {"$exists": True}},
        {"_id": 0}
    ).sort("accumulation_score", -1).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/global/recently")
async def get_global_recently(
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db)
):
    """Recently added projects"""
    cursor = db.intel_projects.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/global/feed")
async def get_global_feed(
    limit: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = Query(None, description="Filter: funding, unlock, listing, ico"),
    db=Depends(get_db)
):
    """
    Global activity feed.
    
    Combines:
    - Funding rounds
    - Token unlocks
    - Exchange listings
    - ICO events
    """
    items = []
    
    # Funding rounds
    if not event_type or event_type == "funding":
        cursor = db.intel_fundraising.find({}, {"_id": 0}).sort("date", -1).limit(limit // 3)
        funding = await cursor.to_list(limit // 3)
        for f in funding:
            f["event_type"] = "funding"
        items.extend(funding)
    
    # Unlocks
    if not event_type or event_type == "unlock":
        cursor = db.intel_unlocks.find({}, {"_id": 0}).sort("unlock_date", 1).limit(limit // 3)
        unlocks = await cursor.to_list(limit // 3)
        for u in unlocks:
            u["event_type"] = "unlock"
        items.extend(unlocks)
    
    # ICO/Sales
    if not event_type or event_type == "ico":
        cursor = db.intel_ico.find({}, {"_id": 0}).sort("date", -1).limit(limit // 3)
        icos = await cursor.to_list(limit // 3)
        for i in icos:
            i["event_type"] = "ico"
        items.extend(icos)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


# ═══════════════════════════════════════════════════════════════
# PROJECTS LAYER - Main Entity
# ═══════════════════════════════════════════════════════════════

@router.get("/projects")
async def get_projects(
    category: Optional[str] = Query(None, description="Filter by category"),
    chain: Optional[str] = Query(None, description="Filter by blockchain"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort: str = Query("name", description="Sort by: name, market_cap, volume"),
    db=Depends(get_db)
):
    """
    List all projects.
    
    Project = Token + Ecosystem
    """
    query = {}
    if category:
        query["category"] = {"$regex": category, "$options": "i"}
    if chain:
        query["chain"] = {"$regex": chain, "$options": "i"}
    
    cursor = db.intel_projects.find(query, {"_id": 0}).skip(offset).limit(limit)
    items = await cursor.to_list(limit)
    total = await db.intel_projects.count_documents(query)
    
    return {
        "ts": _now_ms(),
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": items
    }


@router.get("/projects/{project}")
async def get_project(project: str, db=Depends(get_db)):
    """
    Get project details.
    
    Returns full project info including:
    - Basic info (name, symbol, description)
    - Market data
    - Links (website, twitter, github)
    - Team
    """
    # Try by slug, symbol, or key
    doc = await db.intel_projects.find_one(
        {"$or": [
            {"slug": project.lower()},
            {"symbol": project.upper()},
            {"key": {"$regex": project, "$options": "i"}}
        ]},
        {"_id": 0}
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"Project '{project}' not found")
    
    return {"ts": _now_ms(), "data": doc}


@router.get("/projects/{project}/exchanges")
async def get_project_exchanges(project: str, db=Depends(get_db)):
    """
    Get exchanges where project is traded.
    
    Returns:
    - Exchange name
    - Trading pair
    - Volume
    - Type (spot/perp)
    """
    # Find project first
    proj = await db.intel_projects.find_one(
        {"$or": [{"slug": project.lower()}, {"symbol": project.upper()}]},
        {"_id": 0}
    )
    
    symbol = proj.get("symbol", project.upper()) if proj else project.upper()
    
    # Get from exchange listings
    cursor = db.intel_listings.find(
        {"symbol": symbol},
        {"_id": 0}
    )
    items = await cursor.to_list(100)
    
    return {"ts": _now_ms(), "project": project, "count": len(items), "data": items}


@router.get("/projects/{project}/fundraising")
async def get_project_fundraising(project: str, db=Depends(get_db)):
    """Get all funding rounds for project"""
    cursor = db.intel_fundraising.find(
        {"$or": [
            {"project_key": {"$regex": project, "$options": "i"}},
            {"symbol": project.upper()},
            {"name": {"$regex": project, "$options": "i"}}
        ]},
        {"_id": 0}
    ).sort("date", -1)
    items = await cursor.to_list(50)
    
    return {"ts": _now_ms(), "project": project, "count": len(items), "data": items}


@router.get("/projects/{project}/unlocks")
async def get_project_unlocks(project: str, db=Depends(get_db)):
    """Get token unlock schedule for project"""
    cursor = db.intel_unlocks.find(
        {"$or": [
            {"symbol": project.upper()},
            {"name": {"$regex": project, "$options": "i"}}
        ]},
        {"_id": 0}
    ).sort("unlock_date", 1)
    items = await cursor.to_list(50)
    
    return {"ts": _now_ms(), "project": project, "count": len(items), "data": items}


@router.get("/projects/{project}/investors")
async def get_project_investors(project: str, db=Depends(get_db)):
    """Get investors who funded this project"""
    # First get funding rounds
    funding = await db.intel_fundraising.find(
        {"$or": [
            {"symbol": project.upper()},
            {"name": {"$regex": project, "$options": "i"}}
        ]},
        {"_id": 0, "investors": 1}
    ).to_list(50)
    
    # Extract unique investors
    investor_names = set()
    for f in funding:
        for inv in f.get("investors", []):
            if isinstance(inv, str):
                investor_names.add(inv)
            elif isinstance(inv, dict):
                investor_names.add(inv.get("name", ""))
    
    # Get investor details
    investors = []
    for name in investor_names:
        if name:
            inv = await db.intel_investors.find_one(
                {"name": {"$regex": name, "$options": "i"}},
                {"_id": 0}
            )
            if inv:
                investors.append(inv)
    
    return {"ts": _now_ms(), "project": project, "count": len(investors), "data": investors}


@router.get("/projects/{project}/persons")
async def get_project_persons(project: str, db=Depends(get_db)):
    """Get team members / key persons for project"""
    cursor = db.intel_persons.find(
        {"projects": {"$regex": project, "$options": "i"}},
        {"_id": 0}
    )
    items = await cursor.to_list(50)
    
    return {"ts": _now_ms(), "project": project, "count": len(items), "data": items}


@router.get("/projects/{project}/portfolio")
async def get_project_portfolio(project: str, db=Depends(get_db)):
    """Get project's portfolio / treasury holdings"""
    doc = await db.intel_portfolios.find_one(
        {"project": {"$regex": project, "$options": "i"}},
        {"_id": 0}
    )
    
    return {"ts": _now_ms(), "project": project, "data": doc or {}}


@router.get("/projects/{project}/events")
async def get_project_events(
    project: str,
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db)
):
    """Get all events related to project"""
    events = []
    
    # Funding events
    cursor = db.intel_fundraising.find(
        {"$or": [{"symbol": project.upper()}, {"name": {"$regex": project, "$options": "i"}}]},
        {"_id": 0}
    ).limit(limit // 3)
    funding = await cursor.to_list(limit // 3)
    for f in funding:
        f["event_type"] = "funding"
    events.extend(funding)
    
    # Unlock events
    cursor = db.intel_unlocks.find(
        {"$or": [{"symbol": project.upper()}, {"name": {"$regex": project, "$options": "i"}}]},
        {"_id": 0}
    ).limit(limit // 3)
    unlocks = await cursor.to_list(limit // 3)
    for u in unlocks:
        u["event_type"] = "unlock"
    events.extend(unlocks)
    
    return {"ts": _now_ms(), "project": project, "count": len(events), "data": events}


# ═══════════════════════════════════════════════════════════════
# EXCHANGES LAYER
# ═══════════════════════════════════════════════════════════════

@router.get("/exchanges")
async def get_exchanges(
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db)
):
    """List all exchanges"""
    cursor = db.intel_exchanges.find({}, {"_id": 0}).limit(limit)
    items = await cursor.to_list(limit)
    
    # Fallback to hardcoded if empty
    if not items:
        items = [
            {"name": "Binance", "slug": "binance", "type": "CEX", "volume_24h": None},
            {"name": "Coinbase", "slug": "coinbase", "type": "CEX", "volume_24h": None},
            {"name": "Bybit", "slug": "bybit", "type": "CEX", "volume_24h": None},
            {"name": "OKX", "slug": "okx", "type": "CEX", "volume_24h": None},
            {"name": "Kraken", "slug": "kraken", "type": "CEX", "volume_24h": None},
            {"name": "HyperLiquid", "slug": "hyperliquid", "type": "DEX", "volume_24h": None},
            {"name": "dYdX", "slug": "dydx", "type": "DEX", "volume_24h": None},
            {"name": "Uniswap", "slug": "uniswap", "type": "DEX", "volume_24h": None},
        ]
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/exchanges/{exchange}")
async def get_exchange(exchange: str, db=Depends(get_db)):
    """Get exchange details"""
    doc = await db.intel_exchanges.find_one(
        {"$or": [
            {"slug": exchange.lower()},
            {"name": {"$regex": exchange, "$options": "i"}}
        ]},
        {"_id": 0}
    )
    
    if not doc:
        # Return basic info
        doc = {"name": exchange.title(), "slug": exchange.lower(), "type": "CEX"}
    
    return {"ts": _now_ms(), "data": doc}


@router.get("/exchanges/{exchange}/pairs")
async def get_exchange_pairs(
    exchange: str,
    limit: int = Query(100, ge=1, le=500),
    db=Depends(get_db)
):
    """Get trading pairs on exchange"""
    cursor = db.intel_listings.find(
        {"exchange": {"$regex": exchange, "$options": "i"}},
        {"_id": 0}
    ).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "exchange": exchange, "count": len(items), "data": items}


# ═══════════════════════════════════════════════════════════════
# FUNDS / VC LAYER
# ═══════════════════════════════════════════════════════════════

@router.get("/funds")
async def get_funds(
    tier: Optional[str] = Query(None, description="Filter by tier: 1, 2, 3"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db=Depends(get_db)
):
    """List all funds / VCs"""
    query = {}
    if tier:
        query["tier"] = tier
    
    cursor = db.intel_investors.find(query, {"_id": 0}).skip(offset).limit(limit)
    items = await cursor.to_list(limit)
    total = await db.intel_investors.count_documents(query)
    
    return {
        "ts": _now_ms(),
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": items
    }


@router.get("/funds/{fund}")
async def get_fund(fund: str, db=Depends(get_db)):
    """Get fund details"""
    doc = await db.intel_investors.find_one(
        {"$or": [
            {"slug": fund.lower()},
            {"name": {"$regex": fund, "$options": "i"}}
        ]},
        {"_id": 0}
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"Fund '{fund}' not found")
    
    return {"ts": _now_ms(), "data": doc}


@router.get("/funds/{fund}/portfolio")
async def get_fund_portfolio(fund: str, db=Depends(get_db)):
    """Get fund's portfolio companies"""
    # Find fund first
    fund_doc = await db.intel_investors.find_one(
        {"$or": [{"slug": fund.lower()}, {"name": {"$regex": fund, "$options": "i"}}]},
        {"_id": 0}
    )
    
    fund_name = fund_doc.get("name", fund) if fund_doc else fund
    
    # Find all funding rounds where this fund participated
    cursor = db.intel_fundraising.find(
        {"investors": {"$regex": fund_name, "$options": "i"}},
        {"_id": 0}
    )
    rounds = await cursor.to_list(200)
    
    # Extract unique projects
    projects = {}
    for r in rounds:
        key = r.get("symbol") or r.get("name", "")
        if key and key not in projects:
            projects[key] = {
                "name": r.get("name"),
                "symbol": r.get("symbol"),
                "round": r.get("round"),
                "date": r.get("date")
            }
    
    return {
        "ts": _now_ms(),
        "fund": fund_name,
        "count": len(projects),
        "data": list(projects.values())
    }


@router.get("/funds/{fund}/investments")
async def get_fund_investments(fund: str, db=Depends(get_db)):
    """Get fund's investment history"""
    fund_doc = await db.intel_investors.find_one(
        {"$or": [{"slug": fund.lower()}, {"name": {"$regex": fund, "$options": "i"}}]},
        {"_id": 0}
    )
    
    fund_name = fund_doc.get("name", fund) if fund_doc else fund
    
    cursor = db.intel_fundraising.find(
        {"investors": {"$regex": fund_name, "$options": "i"}},
        {"_id": 0}
    ).sort("date", -1)
    items = await cursor.to_list(100)
    
    return {"ts": _now_ms(), "fund": fund_name, "count": len(items), "data": items}


# ═══════════════════════════════════════════════════════════════
# PERSONS LAYER
# ═══════════════════════════════════════════════════════════════

@router.get("/persons")
async def get_persons(
    role: Optional[str] = Query(None, description="Filter by role: founder, investor, advisor"),
    limit: int = Query(100, ge=1, le=500),
    db=Depends(get_db)
):
    """List notable persons in crypto"""
    query = {}
    if role:
        query["role"] = {"$regex": role, "$options": "i"}
    
    cursor = db.intel_persons.find(query, {"_id": 0}).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/persons/{person}")
async def get_person(person: str, db=Depends(get_db)):
    """Get person details"""
    doc = await db.intel_persons.find_one(
        {"$or": [
            {"slug": person.lower()},
            {"name": {"$regex": person, "$options": "i"}}
        ]},
        {"_id": 0}
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"Person '{person}' not found")
    
    return {"ts": _now_ms(), "data": doc}


@router.get("/persons/{person}/projects")
async def get_person_projects(person: str, db=Depends(get_db)):
    """Get projects associated with person"""
    cursor = db.intel_projects.find(
        {"team": {"$regex": person, "$options": "i"}},
        {"_id": 0}
    )
    items = await cursor.to_list(50)
    
    return {"ts": _now_ms(), "person": person, "count": len(items), "data": items}


@router.get("/persons/{person}/funds")
async def get_person_funds(person: str, db=Depends(get_db)):
    """Get funds associated with person"""
    cursor = db.intel_investors.find(
        {"team": {"$regex": person, "$options": "i"}},
        {"_id": 0}
    )
    items = await cursor.to_list(50)
    
    return {"ts": _now_ms(), "person": person, "count": len(items), "data": items}


# ═══════════════════════════════════════════════════════════════
# FUNDRAISING LAYER
# ═══════════════════════════════════════════════════════════════

@router.get("/fundraising")
async def get_fundraising(
    round_type: Optional[str] = Query(None, description="Filter: seed, series_a, series_b"),
    min_amount: Optional[float] = Query(None, description="Minimum raise amount in USD"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db=Depends(get_db)
):
    """List all fundraising rounds"""
    query = {}
    if round_type:
        query["round"] = {"$regex": round_type, "$options": "i"}
    if min_amount:
        query["raise_usd"] = {"$gte": min_amount}
    
    cursor = db.intel_fundraising.find(query, {"_id": 0}).sort("date", -1).skip(offset).limit(limit)
    items = await cursor.to_list(limit)
    total = await db.intel_fundraising.count_documents(query)
    
    return {
        "ts": _now_ms(),
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": items
    }


@router.get("/fundraising/recent")
async def get_recent_fundraising(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db)
):
    """Get recent fundraising rounds"""
    cursor = db.intel_fundraising.find({}, {"_id": 0}).sort("date", -1).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "days": days, "count": len(items), "data": items}


@router.get("/fundraising/top")
async def get_top_fundraising(
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db)
):
    """Get largest fundraising rounds"""
    cursor = db.intel_fundraising.find(
        {"raise_usd": {"$exists": True, "$ne": None}},
        {"_id": 0}
    ).sort("raise_usd", -1).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/fundraising/{project}")
async def get_project_fundraising_detail(project: str, db=Depends(get_db)):
    """Get fundraising history for specific project"""
    cursor = db.intel_fundraising.find(
        {"$or": [
            {"symbol": project.upper()},
            {"name": {"$regex": project, "$options": "i"}}
        ]},
        {"_id": 0}
    ).sort("date", -1)
    items = await cursor.to_list(50)
    
    return {"ts": _now_ms(), "project": project, "count": len(items), "data": items}


# ═══════════════════════════════════════════════════════════════
# UNLOCKS LAYER
# ═══════════════════════════════════════════════════════════════

@router.get("/unlocks")
async def get_unlocks(
    min_value: Optional[float] = Query(None, description="Minimum unlock value in USD"),
    limit: int = Query(100, ge=1, le=500),
    db=Depends(get_db)
):
    """List all token unlocks"""
    query = {}
    if min_value:
        query["value_usd"] = {"$gte": min_value}
    
    cursor = db.intel_unlocks.find(query, {"_id": 0}).sort("unlock_date", 1).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/unlocks/upcoming")
async def get_upcoming_unlocks(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db)
):
    """Get upcoming token unlocks"""
    cursor = db.intel_unlocks.find({}, {"_id": 0}).sort("unlock_date", 1).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "days_ahead": days, "count": len(items), "data": items}


@router.get("/unlocks/history")
async def get_unlock_history(
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db)
):
    """Get past token unlocks"""
    cursor = db.intel_unlocks.find({}, {"_id": 0}).sort("unlock_date", -1).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/unlocks/{project}")
async def get_project_unlocks_detail(project: str, db=Depends(get_db)):
    """Get unlock schedule for specific project"""
    cursor = db.intel_unlocks.find(
        {"$or": [
            {"symbol": project.upper()},
            {"name": {"$regex": project, "$options": "i"}}
        ]},
        {"_id": 0}
    ).sort("unlock_date", 1)
    items = await cursor.to_list(50)
    
    return {"ts": _now_ms(), "project": project, "count": len(items), "data": items}


# ═══════════════════════════════════════════════════════════════
# ICO / TOKEN SALE LAYER
# ═══════════════════════════════════════════════════════════════

@router.get("/ico")
async def get_icos(
    status: Optional[str] = Query(None, description="Filter: upcoming, active, completed"),
    limit: int = Query(100, ge=1, le=500),
    db=Depends(get_db)
):
    """List all ICOs / token sales"""
    query = {}
    if status:
        query["status"] = status.lower()
    
    cursor = db.intel_ico.find(query, {"_id": 0}).sort("date", -1).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/ico/upcoming")
async def get_upcoming_icos(db=Depends(get_db)):
    """Get upcoming ICOs"""
    cursor = db.intel_ico.find(
        {"status": "upcoming"},
        {"_id": 0}
    ).sort("date", 1).limit(50)
    items = await cursor.to_list(50)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/ico/active")
async def get_active_icos(db=Depends(get_db)):
    """Get currently active ICOs"""
    cursor = db.intel_ico.find(
        {"status": "active"},
        {"_id": 0}
    ).limit(50)
    items = await cursor.to_list(50)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/ico/completed")
async def get_completed_icos(
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db)
):
    """Get completed ICOs"""
    cursor = db.intel_ico.find(
        {"status": "completed"},
        {"_id": 0}
    ).sort("date", -1).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"ts": _now_ms(), "count": len(items), "data": items}


@router.get("/ico/{project}")
async def get_project_ico(project: str, db=Depends(get_db)):
    """Get ICO details for specific project"""
    doc = await db.intel_ico.find_one(
        {"$or": [
            {"symbol": project.upper()},
            {"name": {"$regex": project, "$options": "i"}}
        ]},
        {"_id": 0}
    )
    
    return {"ts": _now_ms(), "project": project, "data": doc or {}}


# ═══════════════════════════════════════════════════════════════
# PORTFOLIO LAYER
# ═══════════════════════════════════════════════════════════════

@router.get("/portfolio/{entity}")
async def get_portfolio(entity: str, db=Depends(get_db)):
    """
    Get portfolio for fund, person, or project.
    
    Tries to find:
    1. Fund portfolio (investments)
    2. Person portfolio (holdings)
    3. Project treasury
    """
    # Try as fund first
    fund = await db.intel_investors.find_one(
        {"$or": [{"slug": entity.lower()}, {"name": {"$regex": entity, "$options": "i"}}]},
        {"_id": 0}
    )
    
    if fund:
        fund_name = fund.get("name", entity)
        cursor = db.intel_fundraising.find(
            {"investors": {"$regex": fund_name, "$options": "i"}},
            {"_id": 0}
        )
        investments = await cursor.to_list(200)
        return {
            "ts": _now_ms(),
            "entity": fund_name,
            "type": "fund",
            "count": len(investments),
            "data": investments
        }
    
    # Try as project
    project = await db.intel_projects.find_one(
        {"$or": [{"slug": entity.lower()}, {"symbol": entity.upper()}]},
        {"_id": 0}
    )
    
    if project:
        treasury = await db.intel_portfolios.find_one(
            {"project": {"$regex": entity, "$options": "i"}},
            {"_id": 0}
        )
        return {
            "ts": _now_ms(),
            "entity": project.get("name", entity),
            "type": "project",
            "data": treasury or {}
        }
    
    return {"ts": _now_ms(), "entity": entity, "type": "unknown", "data": {}}


# ═══════════════════════════════════════════════════════════════
# EVENTS LAYER
# ═══════════════════════════════════════════════════════════════

@router.get("/events")
async def get_events(
    event_type: Optional[str] = Query(None, description="Filter: funding, unlock, listing, ico"),
    limit: int = Query(100, ge=1, le=500),
    db=Depends(get_db)
):
    """Get unified event stream"""
    events = []
    
    if not event_type or event_type == "funding":
        cursor = db.intel_fundraising.find({}, {"_id": 0}).sort("date", -1).limit(limit // 4)
        items = await cursor.to_list(limit // 4)
        for i in items:
            i["event_type"] = "funding"
        events.extend(items)
    
    if not event_type or event_type == "unlock":
        cursor = db.intel_unlocks.find({}, {"_id": 0}).sort("unlock_date", 1).limit(limit // 4)
        items = await cursor.to_list(limit // 4)
        for i in items:
            i["event_type"] = "unlock"
        events.extend(items)
    
    if not event_type or event_type == "ico":
        cursor = db.intel_ico.find({}, {"_id": 0}).sort("date", -1).limit(limit // 4)
        items = await cursor.to_list(limit // 4)
        for i in items:
            i["event_type"] = "ico"
        events.extend(items)
    
    return {"ts": _now_ms(), "count": len(events), "data": events}


@router.get("/events/{project}")
async def get_project_events_unified(
    project: str,
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db)
):
    """Get all events for specific project"""
    events = []
    query = {"$or": [
        {"symbol": project.upper()},
        {"name": {"$regex": project, "$options": "i"}}
    ]}
    
    # Funding
    cursor = db.intel_fundraising.find(query, {"_id": 0}).limit(limit // 3)
    items = await cursor.to_list(limit // 3)
    for i in items:
        i["event_type"] = "funding"
    events.extend(items)
    
    # Unlocks
    cursor = db.intel_unlocks.find(query, {"_id": 0}).limit(limit // 3)
    items = await cursor.to_list(limit // 3)
    for i in items:
        i["event_type"] = "unlock"
    events.extend(items)
    
    return {"ts": _now_ms(), "project": project, "count": len(events), "data": events}


# ═══════════════════════════════════════════════════════════════
# FEED LAYER (alias for global/feed)
# ═══════════════════════════════════════════════════════════════

@router.get("/feed")
async def get_feed(
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db)
):
    """Combined activity feed"""
    return await get_global_feed(limit=limit, db=db)


# ═══════════════════════════════════════════════════════════════
# SEARCH LAYER
# ═══════════════════════════════════════════════════════════════

@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db)
):
    """
    Unified search across all entities.
    
    Searches:
    - Projects
    - Funds
    - Persons
    - Exchanges
    """
    results = {
        "projects": [],
        "funds": [],
        "persons": [],
        "exchanges": []
    }
    
    regex = {"$regex": q, "$options": "i"}
    
    # Search projects
    cursor = db.intel_projects.find(
        {"$or": [{"name": regex}, {"symbol": regex}, {"slug": regex}]},
        {"_id": 0}
    ).limit(limit)
    results["projects"] = await cursor.to_list(limit)
    
    # Search funds
    cursor = db.intel_investors.find(
        {"$or": [{"name": regex}, {"slug": regex}]},
        {"_id": 0}
    ).limit(limit)
    results["funds"] = await cursor.to_list(limit)
    
    # Search persons
    cursor = db.intel_persons.find(
        {"$or": [{"name": regex}, {"slug": regex}]},
        {"_id": 0}
    ).limit(limit)
    results["persons"] = await cursor.to_list(limit)
    
    # Search exchanges
    cursor = db.intel_exchanges.find(
        {"$or": [{"name": regex}, {"slug": regex}]},
        {"_id": 0}
    ).limit(limit)
    results["exchanges"] = await cursor.to_list(limit)
    
    total = sum(len(v) for v in results.values())
    
    return {
        "ts": _now_ms(),
        "query": q,
        "total": total,
        "results": results
    }
