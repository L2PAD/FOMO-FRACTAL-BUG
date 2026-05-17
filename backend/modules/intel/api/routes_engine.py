"""
Intel Engine API Routes

Routes for:
- Event Correlation Engine
- Source Trust Engine
- Query Engine
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intel/engine", tags=["intel-engine"])


def get_db():
    """Get database dependency"""
    from server import db
    return db


# ═══════════════════════════════════════════════════════════════
# EVENT CORRELATION ENGINE
# ═══════════════════════════════════════════════════════════════

def get_correlation_engine():
    """Get or init correlation engine"""
    from server import db
    from ..engine.event_correlation import init_correlation_engine, get_correlation_engine
    engine = get_correlation_engine()
    if engine is None:
        engine = init_correlation_engine(db)
    return engine


@router.get("/correlation/stats")
async def correlation_stats():
    """Get correlation engine statistics"""
    engine = get_correlation_engine()
    stats = await engine.get_stats()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


@router.post("/correlation/run")
async def run_correlation(
    limit: int = Query(500, ge=1, le=5000, description="Max entities to process")
):
    """
    Run correlation for all entities.
    
    Builds relationship graph between events.
    """
    engine = get_correlation_engine()
    result = await engine.correlate_all_entities(limit)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ok": True,
        **result
    }


@router.post("/correlation/entity/{entity_id}")
async def correlate_entity(entity_id: str):
    """
    Run correlation for specific entity.
    
    Returns discovered relations.
    """
    engine = get_correlation_engine()
    relations = await engine.correlate_entity_events(entity_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "entity_id": entity_id,
        "relations_found": len(relations),
        "relations": relations
    }


@router.get("/correlation/entity/{entity_id}/timeline")
async def get_entity_timeline(entity_id: str):
    """
    Get full event timeline with relations for entity.
    
    Shows lifecycle: Funding -> Sale -> Listing -> Unlock
    """
    engine = get_correlation_engine()
    timeline = await engine.get_entity_timeline(entity_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **timeline
    }


@router.get("/correlation/relations")
async def list_relations(
    entity_id: Optional[str] = Query(None),
    relation_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db = Depends(get_db)
):
    """List event relations"""
    query = {}
    if entity_id:
        query["entity_id"] = entity_id
    if relation_type:
        query["relation_type"] = relation_type
    
    cursor = db.intel_event_relations.find(query, {"_id": 0})
    relations = await cursor.limit(limit).to_list(limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "count": len(relations),
        "relations": relations
    }


# ═══════════════════════════════════════════════════════════════
# SOURCE TRUST ENGINE
# ═══════════════════════════════════════════════════════════════

def get_trust_engine():
    """Get or init source trust engine"""
    from server import db
    from ..engine.source_trust import init_source_trust_engine, get_source_trust_engine
    engine = get_source_trust_engine()
    if engine is None:
        engine = init_source_trust_engine(db)
    return engine


@router.get("/trust/stats")
async def trust_stats():
    """Get source trust engine statistics"""
    engine = get_trust_engine()
    stats = await engine.get_stats()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


@router.get("/trust/scores")
async def get_trust_scores():
    """
    Get trust scores for all sources.
    
    Higher score = more reliable source.
    """
    engine = get_trust_engine()
    scores = await engine.get_all_trust_scores()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "count": len(scores),
        "sources": scores
    }


@router.get("/trust/source/{source_id}")
async def get_source_trust(source_id: str):
    """Get detailed trust info for specific source"""
    engine = get_trust_engine()
    details = await engine.get_source_details(source_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **details
    }


@router.post("/trust/recompute")
async def recompute_trust():
    """
    Recompute trust scores for all sources.
    
    Usually run as scheduled job (every 24h).
    """
    engine = get_trust_engine()
    result = await engine.recompute_all_trust()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ok": True,
        **result
    }


@router.post("/trust/source/{source_id}/compute")
async def compute_source_trust(source_id: str):
    """Compute trust for specific source"""
    engine = get_trust_engine()
    trust = await engine.compute_trust(source_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source_id": source_id,
        "trust_score": trust
    }


# ═══════════════════════════════════════════════════════════════
# QUERY ENGINE
# ═══════════════════════════════════════════════════════════════

def get_query_engine():
    """Get or init query engine"""
    from server import db
    from ..engine.query_engine import init_query_engine, get_query_engine
    engine = get_query_engine()
    if engine is None:
        engine = init_query_engine(db)
    return engine


@router.post("/query/events")
async def query_events(
    entity: Optional[str] = Query(None, description="Filter by entity ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    investor: Optional[str] = Query(None, description="Filter by investor"),
    min_amount: Optional[float] = Query(None, description="Minimum amount USD"),
    max_amount: Optional[float] = Query(None, description="Maximum amount USD"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    days_back: Optional[int] = Query(None, description="Days back from now"),
    days_ahead: Optional[int] = Query(None, description="Days ahead from now"),
    source: Optional[str] = Query(None, description="Filter by source"),
    min_confidence: Optional[float] = Query(None, ge=0, le=1, description="Minimum confidence"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("date", description="Sort field"),
    sort_order: int = Query(-1, description="-1=desc, 1=asc")
):
    """
    Query events with flexible filters.
    
    Examples:
    - ?investor=a16z&event_type=funding
    - ?min_amount=50000000&event_type=unlock
    - ?days_back=30&event_type=funding
    """
    from ..engine.query_engine import IntelQuery
    
    engine = get_query_engine()
    
    query = IntelQuery(
        entity=entity,
        event_type=event_type,
        investor=investor,
        min_amount=min_amount,
        max_amount=max_amount,
        start_date=start_date,
        end_date=end_date,
        days_back=days_back,
        days_ahead=days_ahead,
        source=source,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    result = await engine.query_events(query)
    return result


@router.get("/query/funded-before-listing")
async def query_funded_before_listing(
    entity: Optional[str] = Query(None, description="Filter by entity")
):
    """
    Find projects that received funding before exchange listing.
    
    Cross-event query that joins funding and listing events.
    """
    engine = get_query_engine()
    result = await engine.funded_before_listing(entity)
    return result


@router.get("/query/investor/{investor}/portfolio")
async def query_investor_portfolio(investor: str):
    """
    Get investor's portfolio.
    
    Shows all projects they've invested in with amounts and rounds.
    """
    engine = get_query_engine()
    result = await engine.investor_portfolio(investor)
    return result


@router.get("/query/unlocks/upcoming")
async def query_upcoming_unlocks(
    days: int = Query(30, ge=1, le=365, description="Days ahead"),
    min_usd: float = Query(0, ge=0, description="Minimum USD value")
):
    """
    Get upcoming token unlocks.
    
    Returns unlocks within time window with total exposure.
    """
    engine = get_query_engine()
    result = await engine.upcoming_unlocks(days, min_usd)
    return result


@router.get("/query/search")
async def search_intel(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Search across events and entities.
    
    Full-text search on names, symbols, descriptions.
    """
    engine = get_query_engine()
    result = await engine.search(q, limit)
    return result


@router.post("/query/custom")
async def run_custom_query(pipeline: list):
    """
    Execute custom aggregation pipeline.
    
    WARNING: Advanced use only. Allows arbitrary MongoDB aggregation.
    
    Example body:
    [
        {"$match": {"event_type": "funding"}},
        {"$group": {"_id": "$entity_id", "total": {"$sum": "$payload.amount_usd"}}},
        {"$sort": {"total": -1}},
        {"$limit": 10}
    ]
    """
    engine = get_query_engine()
    result = await engine.run_custom_query(pipeline)
    return result


# ═══════════════════════════════════════════════════════════════
# COMBINED PIPELINE ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/pipeline/full")
async def run_full_pipeline():
    """
    Run full post-processing pipeline:
    1. Dedup
    2. Entity Resolution
    3. Event Building
    4. Correlation
    5. Trust Recompute
    
    Usually scheduled every 24h.
    """
    results = {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "stages": {}
    }
    
    try:
        # Correlation
        correlation_engine = get_correlation_engine()
        correlation_result = await correlation_engine.correlate_all_entities(1000)
        results["stages"]["correlation"] = correlation_result
    except Exception as e:
        results["stages"]["correlation"] = {"error": str(e)}
    
    try:
        # Trust
        trust_engine = get_trust_engine()
        trust_result = await trust_engine.recompute_all_trust()
        results["stages"]["trust"] = trust_result
    except Exception as e:
        results["stages"]["trust"] = {"error": str(e)}
    
    results["ok"] = True
    return results


@router.get("/status")
async def engine_status():
    """
    Get status of all intel engines.
    """
    status = {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "engines": {}
    }
    
    # Correlation engine
    try:
        correlation = get_correlation_engine()
        status["engines"]["correlation"] = {
            "initialized": correlation is not None,
            "entities_processed": correlation.entities_processed if correlation else 0,
            "relations_created": correlation.relations_created if correlation else 0
        }
    except Exception as e:
        status["engines"]["correlation"] = {"error": str(e)}
    
    # Trust engine
    try:
        trust = get_trust_engine()
        status["engines"]["trust"] = {
            "initialized": trust is not None,
            "cached_scores": len(trust._cache) if trust else 0
        }
    except Exception as e:
        status["engines"]["trust"] = {"error": str(e)}
    
    # Query engine
    try:
        query = get_query_engine()
        status["engines"]["query"] = {
            "initialized": query is not None
        }
    except Exception as e:
        status["engines"]["query"] = {"error": str(e)}
    
    return status
