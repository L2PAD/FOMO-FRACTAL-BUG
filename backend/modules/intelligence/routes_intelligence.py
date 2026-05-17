"""
API Routes for Entity Momentum, Compute Separation, and Narrative Linking
=========================================================================

New Architecture Endpoints:
- /api/momentum/* - Entity Momentum Engine
- /api/compute/* - Compute Job Queue
- /api/projections/* - Pre-computed Projections
- /api/narrative-linking/* - Narrative Entity Linking
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Intelligence Engine"])

# Lazy imports to avoid circular dependencies
_db = None


def _get_db():
    global _db
    if _db is None:
        from motor.motor_asyncio import AsyncIOMotorClient
        import os
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        _db = client[os.environ.get("DB_NAME", "test_database")]
    return _db


# =============================================================================
# ENTITY MOMENTUM ENDPOINTS
# =============================================================================

@router.get("/momentum/top")
async def get_top_momentum(
    entity_type: Optional[str] = Query(None, description="Filter by type: project, fund, person"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get top entities by momentum score.
    These are entities with highest structural influence.
    """
    from modules.intelligence.entity_momentum import get_momentum_engine
    engine = get_momentum_engine(_get_db())
    
    entities = await engine.get_top_momentum(entity_type=entity_type, limit=limit)
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "count": len(entities),
        "entities": entities
    }


@router.get("/momentum/fastest-growing")
async def get_fastest_growing(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get entities with highest momentum velocity (fastest growing).
    Rising stars in the ecosystem.
    """
    from modules.intelligence.entity_momentum import get_momentum_engine
    engine = get_momentum_engine(_get_db())
    
    entities = await engine.get_fastest_growing(entity_type=entity_type, limit=limit)
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "count": len(entities),
        "entities": entities
    }


@router.get("/momentum/entity/{entity_type}/{entity_id}")
async def get_entity_momentum(
    entity_type: str,
    entity_id: str,
    recalculate: bool = Query(False, description="Force recalculation")
):
    """
    Get momentum details for a specific entity.
    Shows all signal breakdowns.
    """
    from modules.intelligence.entity_momentum import get_momentum_engine
    engine = get_momentum_engine(_get_db())
    
    if recalculate:
        result = await engine.calculate_momentum(entity_type, entity_id)
    else:
        # Get from cache
        result = await engine.db.entity_momentum.find_one(
            {"entity_key": f"{entity_type}:{entity_id}"},
            {"_id": 0}
        )
        
        if not result:
            result = await engine.calculate_momentum(entity_type, entity_id)
    
    return {
        "ok": True,
        **result
    }


@router.get("/momentum/entity/{entity_type}/{entity_id}/history")
async def get_entity_momentum_history(
    entity_type: str,
    entity_id: str,
    days: int = Query(30, ge=1, le=365)
):
    """
    Get momentum history for an entity.
    Shows momentum score over time.
    """
    from modules.intelligence.entity_momentum import get_momentum_engine
    engine = get_momentum_engine(_get_db())
    
    history = await engine.get_entity_momentum_history(entity_type, entity_id, days=days)
    
    return {
        "ok": True,
        "entity_key": f"{entity_type}:{entity_id}",
        "days": days,
        "history": history
    }


@router.get("/momentum/narrative/{narrative_id}")
async def get_narrative_top_entities(
    narrative_id: str,
    limit: int = Query(10, ge=1, le=50)
):
    """
    Get top momentum entities for a narrative.
    Which entities are driving this narrative.
    """
    from modules.intelligence.entity_momentum import get_momentum_engine
    engine = get_momentum_engine(_get_db())
    
    entities = await engine.get_narrative_top_entities(narrative_id, limit=limit)
    
    return {
        "ok": True,
        "narrative_id": narrative_id,
        "count": len(entities),
        "entities": entities
    }


@router.post("/momentum/update")
async def trigger_momentum_update(
    entity_types: Optional[str] = Query(None, description="Comma-separated types"),
    limit: int = Query(500, ge=50, le=2000)
):
    """
    Trigger momentum calculation for entities.
    Normally runs on schedule.
    """
    from modules.intelligence.entity_momentum import get_momentum_engine
    engine = get_momentum_engine(_get_db())
    
    types_list = entity_types.split(",") if entity_types else None
    result = await engine.update_all_entities(entity_types=types_list, limit=limit)
    
    return {
        "ok": True,
        **result
    }


@router.get("/momentum/stats")
async def get_momentum_stats():
    """Get momentum engine statistics"""
    from modules.intelligence.entity_momentum import get_momentum_engine
    engine = get_momentum_engine(_get_db())
    
    stats = await engine.get_stats()
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        **stats
    }


# =============================================================================
# COMPUTE JOB QUEUE ENDPOINTS
# =============================================================================

@router.get("/compute/queue/stats")
async def get_queue_stats():
    """Get compute job queue statistics"""
    from modules.intelligence.compute_separation import get_compute_job_queue
    queue = get_compute_job_queue(_get_db())
    
    stats = await queue.get_queue_stats()
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        **stats
    }


@router.post("/compute/queue/enqueue")
async def enqueue_job(
    job_type: str = Query(..., description="Job type"),
    cluster: str = Query("intelligence", description="Cluster: ingestion or intelligence"),
    priority: int = Query(3, ge=1, le=5, description="Priority 1-5 (1=critical)")
):
    """
    Manually enqueue a compute job.
    For debugging/testing purposes.
    """
    from modules.intelligence.compute_separation import get_compute_job_queue, ComputeCluster, JobPriority
    queue = get_compute_job_queue(_get_db())
    
    cluster_enum = ComputeCluster.INGESTION if cluster == "ingestion" else ComputeCluster.INTELLIGENCE
    priority_enum = JobPriority(priority)
    
    job_id = await queue.enqueue(
        job_type=job_type,
        cluster=cluster_enum,
        priority=priority_enum
    )
    
    return {
        "ok": True,
        "job_id": job_id,
        "cluster": cluster,
        "job_type": job_type
    }


@router.get("/compute/metrics/{cluster}")
async def get_cluster_metrics(
    cluster: str,
    days: int = Query(7, ge=1, le=30)
):
    """Get metrics for a compute cluster"""
    from modules.intelligence.compute_separation import get_compute_job_queue, ComputeCluster
    queue = get_compute_job_queue(_get_db())
    
    cluster_enum = ComputeCluster.INGESTION if cluster == "ingestion" else ComputeCluster.INTELLIGENCE
    metrics = await queue.get_cluster_metrics(cluster_enum, days=days)
    
    return {
        "ok": True,
        "cluster": cluster,
        "days": days,
        "metrics": metrics
    }


@router.post("/compute/cleanup")
async def cleanup_old_jobs(
    days: int = Query(7, ge=1, le=30)
):
    """Remove completed jobs older than X days"""
    from modules.intelligence.compute_separation import get_compute_job_queue
    queue = get_compute_job_queue(_get_db())
    
    deleted = await queue.cleanup_old_jobs(days=days)
    
    return {
        "ok": True,
        "deleted_count": deleted
    }


# =============================================================================
# PROJECTION LAYER ENDPOINTS (FAST UI READS)
# =============================================================================

@router.get("/projections/feed")
async def get_feed_projection(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Get pre-computed feed cards.
    FAST PATH - reads from projection, no heavy compute.
    """
    from modules.intelligence.compute_separation import get_projection_layer
    layer = get_projection_layer(_get_db())
    
    cards = await layer.get_feed_cards(limit=limit, offset=offset)
    
    return {
        "ok": True,
        "source": "projection",
        "count": len(cards),
        "cards": cards
    }


@router.get("/projections/momentum/{ranking_type}")
async def get_momentum_projection(
    ranking_type: str = "top_overall"
):
    """
    Get pre-computed momentum ranking.
    FAST PATH - reads from projection.
    
    Types: top_overall, fastest_growing, top_project, top_fund, top_person
    """
    from modules.intelligence.compute_separation import get_projection_layer
    layer = get_projection_layer(_get_db())
    
    projection = await layer.get_momentum_ranking(ranking_type)
    
    return {
        "ok": True,
        "source": "projection",
        "ranking_type": ranking_type,
        **projection
    }


@router.post("/projections/update/feed")
async def update_feed_projection(
    limit: int = Query(100, ge=50, le=500)
):
    """Trigger feed projection update"""
    from modules.intelligence.compute_separation import get_projection_layer
    layer = get_projection_layer(_get_db())
    
    updated = await layer.update_feed_projection(limit=limit)
    
    return {
        "ok": True,
        "updated_cards": updated
    }


@router.post("/projections/update/momentum")
async def update_momentum_projection():
    """Trigger momentum projection update"""
    from modules.intelligence.compute_separation import get_projection_layer
    layer = get_projection_layer(_get_db())
    
    result = await layer.update_momentum_projection()
    
    return {
        "ok": True,
        **result
    }


@router.post("/projections/update/narratives")
async def update_narrative_projection():
    """Trigger narrative projection update"""
    from modules.intelligence.compute_separation import get_projection_layer
    layer = get_projection_layer(_get_db())
    
    updated = await layer.update_narrative_projection()
    
    return {
        "ok": True,
        "updated_narratives": updated
    }


# =============================================================================
# NARRATIVE ENTITY LINKING ENDPOINTS
# =============================================================================

@router.get("/narrative-linking/entity/{entity_type}/{entity_id}/narratives")
async def get_entity_narratives(
    entity_type: str,
    entity_id: str,
    limit: int = Query(5, ge=1, le=20)
):
    """
    Get top narratives for an entity.
    Which narratives is this entity part of.
    """
    from modules.intelligence.narrative_entity_linking import get_narrative_entity_linker
    linker = get_narrative_entity_linker(_get_db())
    
    narratives = await linker.get_top_narratives_for_entity(
        entity_type, entity_id, limit=limit
    )
    
    return {
        "ok": True,
        "entity_key": f"{entity_type}:{entity_id}",
        "count": len(narratives),
        "narratives": narratives
    }


@router.get("/narrative-linking/narrative/{narrative_id}/entities")
async def get_narrative_entities(
    narrative_id: str,
    entity_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get top entities for a narrative.
    Returns entities sorted by momentum.
    """
    from modules.intelligence.narrative_entity_linking import get_narrative_entity_linker
    linker = get_narrative_entity_linker(_get_db())
    
    entities = await linker.get_top_entities_for_narrative(
        narrative_id, entity_type=entity_type, limit=limit
    )
    
    return {
        "ok": True,
        "narrative_id": narrative_id,
        "count": len(entities),
        "entities": entities
    }


@router.get("/narrative-linking/entity/{entity_type}/{entity_id}/exposure")
async def get_entity_exposure(
    entity_type: str,
    entity_id: str
):
    """
    Get narrative exposure metrics for entity.
    How much is this entity part of active narratives.
    """
    from modules.intelligence.narrative_entity_linking import get_narrative_entity_linker
    linker = get_narrative_entity_linker(_get_db())
    
    exposure = await linker.get_entity_exposure(entity_type, entity_id)
    
    return {
        "ok": True,
        **exposure
    }


@router.get("/narrative-linking/top-exposed")
async def get_top_exposed_entities(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get entities with highest narrative exposure.
    Most connected to active narratives.
    """
    from modules.intelligence.narrative_entity_linking import get_narrative_entity_linker
    linker = get_narrative_entity_linker(_get_db())
    
    entities = await linker.get_top_exposed_entities(entity_type=entity_type, limit=limit)
    
    return {
        "ok": True,
        "count": len(entities),
        "entities": entities
    }


@router.post("/narrative-linking/entity/{entity_type}/{entity_id}/auto-link")
async def auto_link_entity(
    entity_type: str,
    entity_id: str
):
    """
    Auto-detect and link entity to relevant narratives.
    Uses keyword/topic matching.
    """
    from modules.intelligence.narrative_entity_linking import get_narrative_entity_linker
    linker = get_narrative_entity_linker(_get_db())
    
    links_created = await linker.auto_link_entity(entity_type, entity_id)
    
    return {
        "ok": True,
        "entity_key": f"{entity_type}:{entity_id}",
        "links_created": links_created
    }


@router.post("/narrative-linking/batch")
async def batch_link_entities(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=10, le=500)
):
    """
    Batch auto-link entities to narratives.
    For populating narrative-entity relationships.
    """
    from modules.intelligence.narrative_entity_linking import get_narrative_entity_linker
    linker = get_narrative_entity_linker(_get_db())
    
    result = await linker.batch_link_entities(entity_type=entity_type, limit=limit)
    
    return {
        "ok": True,
        **result
    }


@router.get("/narrative-linking/stats")
async def get_narrative_linking_stats():
    """Get narrative linking statistics"""
    from modules.intelligence.narrative_entity_linking import get_narrative_entity_linker
    linker = get_narrative_entity_linker(_get_db())
    
    stats = await linker.get_stats()
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        **stats
    }


# =============================================================================
# COMBINED INTELLIGENCE STATS
# =============================================================================

@router.get("/intelligence/stats")
async def get_intelligence_stats():
    """Get combined statistics for all intelligence modules"""
    from modules.intelligence.entity_momentum import get_momentum_engine
    from modules.intelligence.compute_separation import get_compute_job_queue, get_projection_layer
    from modules.intelligence.narrative_entity_linking import get_narrative_entity_linker
    
    db = _get_db()
    
    momentum_engine = get_momentum_engine(db)
    job_queue = get_compute_job_queue(db)
    projection_layer = get_projection_layer(db)
    linker = get_narrative_entity_linker(db)
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "momentum": await momentum_engine.get_stats(),
        "compute_queue": await job_queue.get_queue_stats(),
        "narrative_linking": await linker.get_stats()
    }
