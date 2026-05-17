"""
Entity Intelligence API Routes

Provides "manna from heaven" API:
- One endpoint → full entity data + events + provenance
- Any identifier → same result (symbol, name, address, slug)
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intel/entity", tags=["entity-intelligence"])


def get_entity_engine():
    """Get entity intelligence engine"""
    from server import db
    from ..engine.entity_intelligence_v2 import init_entity_intelligence, get_entity_intelligence
    engine = get_entity_intelligence()
    if engine is None:
        engine = init_entity_intelligence(db)
    return engine


# ═══════════════════════════════════════════════════════════════
# STATIC ROUTES (must be before /{query})
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
async def entity_stats():
    """Get entity intelligence statistics"""
    engine = get_entity_engine()
    return await engine.get_stats()


@router.post("/resolve")
async def resolve_entity(query: str = Query(..., description="Identifier to resolve")):
    """
    Resolve any identifier to entity_id.
    
    Returns the canonical entity_id for any input.
    """
    engine = get_entity_engine()
    entity_id = await engine.resolver.resolve(query)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "query": query,
        "entity_id": entity_id,
        "resolved": entity_id is not None
    }


@router.post("/resolution/run")
async def run_entity_resolution(limit: int = Query(1000, ge=1, le=10000)):
    """
    Run entity resolution job.
    
    Processes normalized entities, creates/resolves entities, builds index.
    """
    engine = get_entity_engine()
    result = await engine.run_entity_resolution(limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ok": True,
        **result
    }


@router.post("/merge")
async def merge_entities(
    primary_id: str = Query(..., description="Primary entity to keep"),
    secondary_id: str = Query(..., description="Entity to merge into primary")
):
    """
    Merge two entities.
    
    Secondary entity will be merged into primary:
    - Aliases combined
    - Keys merged
    - Events reassigned
    - Secondary deleted
    """
    engine = get_entity_engine()
    result = await engine.merger.merge_entities(primary_id, secondary_id)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.get("/search")
async def search_entities(
    q: str = Query(..., min_length=1, description="Search query"),
    type: Optional[str] = Query(None, description="Entity type filter"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Search entities by name, symbol, or alias.
    
    Types: token, project, fund, exchange, launchpad, investor
    """
    engine = get_entity_engine()
    results = await engine.search_entities(q, type, limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "query": q,
        "type": type,
        "count": len(results),
        "entities": results
    }


# ═══════════════════════════════════════════════════════════════
# DYNAMIC ROUTES (/{query} must be last)
# ═══════════════════════════════════════════════════════════════

@router.get("/{query}")
async def get_entity(query: str):
    """
    Get entity by any identifier.
    
    Query can be:
    - Symbol: BTC, ETH, ARB
    - Name: Bitcoin, Ethereum, Arbitrum
    - Slug: bitcoin, ethereum, arbitrum
    - Address: 0x912ce59144191c1204e64559fe8253a0e49e6548
    - External key: coingecko:bitcoin, cryptorank:arb
    
    Returns full entity profile with event counts.
    """
    engine = get_entity_engine()
    result = await engine.get_entity_profile(query)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.get("/{query}/timeline")
async def get_entity_timeline(
    query: str,
    types: Optional[str] = Query(None, description="Comma-separated event types"),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get chronological event timeline for entity.
    
    Types: funding_round, unlock_event, token_sale, listing, investor_activity
    """
    engine = get_entity_engine()
    
    event_types = types.split(",") if types else None
    result = await engine.get_entity_timeline(query, event_types, limit)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.get("/{query}/events")
async def get_entity_events(
    query: str,
    type: Optional[str] = Query(None, description="Event type filter"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get events for entity.
    
    Optionally filter by event type.
    """
    engine = get_entity_engine()
    result = await engine.get_entity_events(query, type, limit)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.get("/{query}/funding")
async def get_entity_funding(query: str, limit: int = Query(50, ge=1, le=100)):
    """Get funding rounds for entity"""
    engine = get_entity_engine()
    result = await engine.get_entity_events(query, "funding_round", limit)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "entity": result.get("entity"),
        "funding": result.get("events", []),
        "count": result.get("count", 0)
    }


@router.get("/{query}/unlocks")
async def get_entity_unlocks(query: str, limit: int = Query(50, ge=1, le=100)):
    """Get unlock events for entity"""
    engine = get_entity_engine()
    result = await engine.get_entity_events(query, "unlock_event", limit)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "entity": result.get("entity"),
        "unlocks": result.get("events", []),
        "count": result.get("count", 0)
    }


@router.get("/{query}/sales")
async def get_entity_sales(query: str, limit: int = Query(50, ge=1, le=100)):
    """Get token sales for entity"""
    engine = get_entity_engine()
    result = await engine.get_entity_events(query, "token_sale", limit)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "entity": result.get("entity"),
        "sales": result.get("events", []),
        "count": result.get("count", 0)
    }


@router.get("/{query}/listings")
async def get_entity_listings(query: str, limit: int = Query(50, ge=1, le=100)):
    """Get exchange listings for entity"""
    engine = get_entity_engine()
    result = await engine.get_entity_events(query, "listing", limit)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "entity": result.get("entity"),
        "listings": result.get("events", []),
        "count": result.get("count", 0)
    }
