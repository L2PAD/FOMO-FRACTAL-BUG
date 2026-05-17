"""
API Routes for Architecture Enhancements
========================================

Endpoints for:
- Graph Projection Layer
- Event Entity Registry
- Source Reliability Scoring
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/architecture", tags=["Architecture"])

# Lazy imports to avoid circular dependencies
_db = None
_projection_service = None
_event_registry = None
_reliability_system = None


def _get_db():
    global _db
    if _db is None:
        from motor.motor_asyncio import AsyncIOMotorClient
        import os
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        _db = client[os.environ.get("DB_NAME", "test_database")]
    return _db


def _get_projection_service():
    global _projection_service
    if _projection_service is None:
        from modules.knowledge_graph.graph_projection import get_projection_service
        _projection_service = get_projection_service(_get_db())
    return _projection_service


def _get_event_registry():
    global _event_registry
    if _event_registry is None:
        from modules.intelligence.event_entity_registry import get_event_entity_registry
        _event_registry = get_event_entity_registry(_get_db())
    return _event_registry


def _get_reliability_system():
    global _reliability_system
    if _reliability_system is None:
        from modules.provider_gateway.source_reliability import get_source_reliability
        _reliability_system = get_source_reliability(_get_db())
    return _reliability_system


# =============================================================================
# GRAPH PROJECTION ENDPOINTS
# =============================================================================

@router.get("/graph/projection/{entity_type}/{entity_id}")
async def get_graph_projection(
    entity_type: str,
    entity_id: str,
    max_age_minutes: int = Query(30, description="Max cache age in minutes"),
    rebuild_if_missing: bool = Query(True, description="Build projection if not cached")
):
    """
    Get pre-computed graph projection for entity.
    Much faster than real-time graph queries.
    """
    service = _get_projection_service()
    
    # Try to get cached projection
    projection = await service.get_projection(entity_type, entity_id, max_age_minutes)
    
    if projection:
        return {
            "ok": True,
            "source": "cache",
            **projection
        }
    
    if rebuild_if_missing:
        # Build new projection
        projection = await service.build_projection(entity_type, entity_id)
        return {
            "ok": True,
            "source": "built",
            **projection
        }
    
    return {
        "ok": False,
        "error": "Projection not found",
        "entity_key": f"{entity_type}:{entity_id}"
    }


@router.post("/graph/projection/rebuild")
async def rebuild_hot_graphs():
    """
    Manually trigger rebuild of all hot entity projections.
    Normally runs on schedule.
    """
    service = _get_projection_service()
    result = await service.rebuild_hot_graphs()
    return {
        "ok": True,
        **result
    }


@router.post("/graph/projection/invalidate/{entity_type}/{entity_id}")
async def invalidate_projection(entity_type: str, entity_id: str):
    """Invalidate (delete) cached projection for entity"""
    service = _get_projection_service()
    await service.invalidate_projection(entity_type, entity_id)
    return {
        "ok": True,
        "invalidated": f"{entity_type}:{entity_id}"
    }


@router.get("/graph/projection/stats")
async def get_projection_stats():
    """Get projection cache statistics"""
    service = _get_projection_service()
    stats = await service.get_stats()
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        **stats
    }


# =============================================================================
# EVENT ENTITY REGISTRY ENDPOINTS
# =============================================================================

@router.get("/events/entity/{entity_type}/{entity_id}")
async def get_entity_events(
    entity_type: str,
    entity_id: str,
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    roles: Optional[str] = Query(None, description="Comma-separated roles"),
    days: int = Query(30, description="Look back days"),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get all events for an entity.
    Returns timeline of events where this entity was involved.
    """
    registry = _get_event_registry()
    
    event_type_list = event_types.split(",") if event_types else None
    role_list = roles.split(",") if roles else None
    
    events = await registry.get_entity_events(
        entity_type, entity_id,
        event_types=event_type_list,
        roles=role_list,
        limit=limit,
        days=days
    )
    
    return {
        "ok": True,
        "entity_key": f"{entity_type}:{entity_id}",
        "count": len(events),
        "events": events
    }


@router.get("/events/entity/{entity_type}/{entity_id}/momentum")
async def get_entity_momentum(
    entity_type: str,
    entity_id: str,
    days: int = Query(30, ge=1, le=365),
    bucket_hours: int = Query(24, ge=1, le=168)
):
    """
    Get entity momentum - event activity over time.
    Higher momentum = entity is hot/trending.
    """
    registry = _get_event_registry()
    momentum = await registry.get_entity_momentum(
        entity_type, entity_id,
        days=days,
        bucket_hours=bucket_hours
    )
    return {
        "ok": True,
        **momentum
    }


@router.get("/events/entity/{entity_type}/{entity_id}/co-occurring")
async def get_co_occurring_entities(
    entity_type: str,
    entity_id: str,
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get entities that often appear in the same events.
    Useful for finding related projects/funds.
    """
    registry = _get_event_registry()
    entities = await registry.get_co_occurring_entities(
        entity_type, entity_id,
        limit=limit
    )
    return {
        "ok": True,
        "entity_key": f"{entity_type}:{entity_id}",
        "co_occurring": entities
    }


@router.get("/events/{event_id}/entities")
async def get_event_entities(event_id: str):
    """Get all entities linked to an event"""
    registry = _get_event_registry()
    entities = await registry.get_event_entities(event_id)
    return {
        "ok": True,
        "event_id": event_id,
        "entities": entities
    }


@router.post("/events/backfill")
async def backfill_event_entities(limit: int = Query(1000, ge=100, le=10000)):
    """
    Backfill event_entities from existing news_events.
    One-time migration task.
    """
    registry = _get_event_registry()
    result = await registry.backfill_from_news_events(limit=limit)
    return {
        "ok": True,
        **result
    }


@router.get("/events/registry/stats")
async def get_event_registry_stats():
    """Get event entity registry statistics"""
    registry = _get_event_registry()
    stats = await registry.get_stats()
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        **stats
    }


# =============================================================================
# SOURCE RELIABILITY ENDPOINTS
# =============================================================================

@router.get("/sources/reliability")
async def get_all_source_metrics():
    """Get reliability metrics for all sources"""
    system = _get_reliability_system()
    metrics = await system.get_all_metrics()
    stats = await system.get_stats()
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "sources": metrics
    }


@router.get("/sources/reliability/{source_id}")
async def get_source_metrics(source_id: str):
    """Get reliability metrics for a specific source"""
    system = _get_reliability_system()
    metrics = await system.get_source_metrics(source_id)
    
    return {
        "ok": True,
        **metrics
    }


@router.get("/sources/reliability/{source_id}/history")
async def get_source_history(
    source_id: str,
    hours: int = Query(24, ge=1, le=168)
):
    """Get reliability score history for a source"""
    system = _get_reliability_system()
    history = await system.get_source_history(source_id, hours=hours)
    
    return {
        "ok": True,
        "source_id": source_id,
        "hours": hours,
        "history": history
    }


@router.get("/sources/best")
async def get_best_source(
    data_type: str = Query(..., description="Type of data: funding, prices, tvl, etc."),
    min_score: float = Query(0.3, ge=0, le=1)
):
    """
    Get best source for a data type.
    Scheduler uses this to choose providers.
    """
    system = _get_reliability_system()
    best = await system.get_best_source(data_type=data_type, min_score=min_score)
    
    if best:
        metrics = await system.get_source_metrics(best)
        return {
            "ok": True,
            "data_type": data_type,
            "best_source": best,
            "metrics": metrics
        }
    
    return {
        "ok": False,
        "error": f"No source available for {data_type}"
    }


@router.get("/sources/ranking")
async def get_source_ranking(
    data_type: Optional[str] = Query(None, description="Filter by data type"),
    limit: int = Query(10, ge=1, le=50)
):
    """Get ranked list of sources by reliability score"""
    system = _get_reliability_system()
    ranking = await system.get_source_ranking(data_type=data_type, limit=limit)
    
    return {
        "ok": True,
        "data_type": data_type,
        "ranking": ranking
    }


@router.post("/sources/seed")
async def seed_sources():
    """Seed initial source metrics with default values"""
    system = _get_reliability_system()
    count = await system.seed_initial_sources()
    
    return {
        "ok": True,
        "seeded": count
    }


# =============================================================================
# GRAPH LAYER SEPARATION ENDPOINTS
# =============================================================================

_layer_service = None

def _get_layer_service():
    global _layer_service
    if _layer_service is None:
        from modules.knowledge_graph.graph_layers import get_graph_layer_service
        _layer_service = get_graph_layer_service(_get_db())
    return _layer_service


@router.get("/graph/layers/stats")
async def get_graph_layer_stats():
    """Get statistics for each graph layer"""
    service = _get_layer_service()
    stats = await service.get_layer_stats()
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        **stats
    }


@router.get("/graph/layers/{entity_key:path}")
async def get_entity_graph_by_layers(
    entity_key: str,
    layers: str = Query("factual", description="Comma-separated layers: factual,derived,intelligence,all"),
    max_nodes: int = Query(50, ge=1, le=200),
    max_edges: int = Query(80, ge=1, le=500),
    depth: int = Query(1, ge=1, le=3)
):
    """
    Get entity graph with specific layers.
    
    Layers:
    - factual: Core facts (invested_in, founded, works_at)
    - derived: Computed relationships (coinvested_with, worked_together)
    - intelligence: Analytical links (event_linked, narrative_linked)
    - all: All layers combined
    """
    service = _get_layer_service()
    
    layer_list = [l.strip() for l in layers.split(",")]
    
    graph = await service.get_entity_graph(
        entity_key,
        layers=layer_list,
        max_nodes=max_nodes,
        max_edges=max_edges,
        depth=depth
    )
    
    return {
        "ok": True,
        **graph
    }


@router.post("/graph/layers/migrate")
async def migrate_graph_layers(batch_size: int = Query(1000, ge=100, le=10000)):
    """
    Migrate existing edges to appropriate layer collections.
    One-time migration task.
    """
    service = _get_layer_service()
    result = await service.migrate_existing_edges(batch_size=batch_size)
    
    return {
        "ok": True,
        **result
    }


@router.post("/graph/layers/compute-derived")
async def compute_derived_edges(
    relation_type: str = Query("coinvested_with", description="Type: coinvested_with or shares_investor_with")
):
    """
    Compute derived edges from factual data.
    - coinvested_with: Funds that invested in the same project
    - shares_investor_with: Projects that share the same investor
    """
    service = _get_layer_service()
    count = await service.compute_derived_edges(relation_type=relation_type)
    
    return {
        "ok": True,
        "relation_type": relation_type,
        "computed_edges": count
    }


@router.post("/graph/layers/link-events")
async def link_events_to_graph(limit: int = Query(500, ge=50, le=2000)):
    """
    Create intelligence edges from event co-mentions.
    Links entities that appear together in news events.
    """
    service = _get_layer_service()
    count = await service.link_events_to_entities(limit=limit)
    
    return {
        "ok": True,
        "intelligence_edges_created": count
    }


# =============================================================================
# SOURCE ALERTING ENDPOINTS
# =============================================================================

_alerting_system = None

def _get_alerting_system():
    global _alerting_system
    if _alerting_system is None:
        from modules.provider_gateway.source_alerting import get_source_alerting
        _alerting_system = get_source_alerting(_get_db())
    return _alerting_system


@router.get("/alerts")
async def get_alerts(
    source_id: Optional[str] = Query(None, description="Filter by source"),
    severity: Optional[str] = Query(None, description="Filter by severity: critical, warning, info"),
    include_resolved: bool = Query(False, description="Include resolved alerts"),
    limit: int = Query(50, ge=1, le=200)
):
    """Get source alerts"""
    system = _get_alerting_system()
    alerts = await system.get_alerts(
        source_id=source_id,
        severity=severity,
        include_resolved=include_resolved,
        limit=limit
    )
    stats = await system.get_alert_stats()
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "alerts": alerts
    }


@router.get("/alerts/active")
async def get_active_alerts(severity: Optional[str] = Query(None)):
    """Get only active (unresolved) alerts"""
    system = _get_alerting_system()
    alerts = await system.get_active_alerts(severity=severity)
    
    return {
        "ok": True,
        "count": len(alerts),
        "alerts": alerts
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert"""
    system = _get_alerting_system()
    success = await system.acknowledge_alert(alert_id)
    
    return {
        "ok": success,
        "alert_id": alert_id,
        "action": "acknowledged"
    }


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, note: Optional[str] = Query(None)):
    """Resolve an alert"""
    system = _get_alerting_system()
    success = await system.resolve_alert(alert_id, note=note)
    
    return {
        "ok": success,
        "alert_id": alert_id,
        "action": "resolved"
    }


@router.post("/alerts/check")
async def trigger_alert_check():
    """Manually trigger alert check for all sources"""
    system = _get_alerting_system()
    new_alerts = await system.check_sources_and_alert()
    
    return {
        "ok": True,
        "new_alerts": len(new_alerts),
        "alerts": new_alerts
    }


# =============================================================================
# COMBINED STATS
# =============================================================================

@router.get("/stats")
async def get_architecture_stats():
    """Get combined statistics for all architecture enhancements"""
    projection_service = _get_projection_service()
    event_registry = _get_event_registry()
    reliability_system = _get_reliability_system()
    layer_service = _get_layer_service()
    alerting_system = _get_alerting_system()
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "graph_projection": await projection_service.get_stats(),
        "event_registry": await event_registry.get_stats(),
        "source_reliability": await reliability_system.get_stats(),
        "graph_layers": await layer_service.get_layer_stats(),
        "alerts": await alerting_system.get_alert_stats()
    }
