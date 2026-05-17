"""
API Routes for Graph Growth, Momentum Alerts, and Entity Discovery
===================================================================

Endpoints:
- /api/graph/metrics/growth - Graph growth metrics
- /api/alerts/momentum/* - Momentum velocity alerts
- /api/discovery/* - Entity-driven discovery
- /api/extraction/* - Incremental extraction state
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Growth & Discovery"])

# Lazy DB import
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
# GRAPH GROWTH METRICS
# =============================================================================

@router.get("/graph/metrics/growth")
async def get_graph_growth_metrics():
    """
    Get current graph growth metrics.
    Shows nodes, edges, growth velocity.
    """
    from modules.intelligence.graph_growth_monitor import get_graph_growth_monitor
    monitor = get_graph_growth_monitor(_get_db())
    
    metrics = await monitor.get_current_metrics()
    
    return {
        "ok": True,
        **metrics
    }


@router.get("/graph/metrics/growth/history")
async def get_graph_growth_history(
    days: int = Query(30, ge=1, le=365)
):
    """Get historical graph growth data"""
    from modules.intelligence.graph_growth_monitor import get_graph_growth_monitor
    monitor = get_graph_growth_monitor(_get_db())
    
    history = await monitor.get_growth_history(days=days)
    
    return {
        "ok": True,
        "days": days,
        "count": len(history),
        "history": history
    }


@router.post("/graph/metrics/growth/snapshot")
async def capture_growth_snapshot():
    """Manually trigger a growth snapshot capture"""
    from modules.intelligence.graph_growth_monitor import get_graph_growth_monitor
    monitor = get_graph_growth_monitor(_get_db())
    
    snapshot = await monitor.capture_snapshot()
    
    # Remove _id if present
    snapshot.pop("_id", None)
    
    return {
        "ok": True,
        "snapshot": snapshot
    }


@router.get("/graph/metrics/growth/alerts")
async def get_growth_alerts(
    status: Optional[str] = Query(None, description="Filter by status: active, acknowledged"),
    limit: int = Query(50, ge=1, le=200)
):
    """Get graph growth alerts"""
    from modules.intelligence.graph_growth_monitor import get_graph_growth_monitor
    monitor = get_graph_growth_monitor(_get_db())
    
    alerts = await monitor.get_growth_alerts(status=status, limit=limit)
    
    return {
        "ok": True,
        "count": len(alerts),
        "alerts": alerts
    }


# =============================================================================
# MOMENTUM VELOCITY ALERTS
# =============================================================================

@router.get("/alerts/momentum")
async def get_momentum_alerts(
    entity_key: Optional[str] = Query(None, description="Filter by entity"),
    alert_type: Optional[str] = Query(None, description="Filter by type: spike_up, spike_down, breakout_high"),
    status: Optional[str] = Query(None, description="Filter by status: active, acknowledged"),
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get momentum velocity alerts.
    Alerts when entities show significant momentum changes.
    """
    from modules.intelligence.momentum_alerts import get_momentum_alert_engine
    engine = get_momentum_alert_engine(_get_db())
    
    alerts = await engine.get_alerts(
        entity_key=entity_key,
        alert_type=alert_type,
        status=status,
        severity=severity,
        limit=limit
    )
    
    return {
        "ok": True,
        "count": len(alerts),
        "alerts": alerts
    }


@router.get("/alerts/momentum/stats")
async def get_momentum_alert_stats():
    """Get momentum alert statistics"""
    from modules.intelligence.momentum_alerts import get_momentum_alert_engine
    engine = get_momentum_alert_engine(_get_db())
    
    stats = await engine.get_stats()
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        **stats
    }


@router.post("/alerts/momentum/check")
async def trigger_momentum_alert_check():
    """Manually trigger momentum alert check for all entities"""
    from modules.intelligence.momentum_alerts import get_momentum_alert_engine
    engine = get_momentum_alert_engine(_get_db())
    
    result = await engine.check_all_entities()
    
    return {
        "ok": True,
        **result
    }


@router.post("/alerts/momentum/{alert_id}/acknowledge")
async def acknowledge_momentum_alert(alert_id: str):
    """Acknowledge a momentum alert"""
    from modules.intelligence.momentum_alerts import get_momentum_alert_engine
    engine = get_momentum_alert_engine(_get_db())
    
    success = await engine.acknowledge_alert(alert_id)
    
    return {
        "ok": success,
        "alert_id": alert_id,
        "status": "acknowledged" if success else "not_found"
    }


@router.post("/alerts/momentum/subscribe")
async def subscribe_to_entity(
    user_id: str = Query(..., description="User ID"),
    entity_key: str = Query(..., description="Entity key (type:id)")
):
    """Subscribe to momentum alerts for an entity"""
    from modules.intelligence.momentum_alerts import get_momentum_alert_engine
    engine = get_momentum_alert_engine(_get_db())
    
    sub = await engine.subscribe(user_id, entity_key)
    
    return {
        "ok": True,
        "subscription": sub
    }


@router.delete("/alerts/momentum/subscribe")
async def unsubscribe_from_entity(
    user_id: str = Query(...),
    entity_key: str = Query(...)
):
    """Unsubscribe from momentum alerts"""
    from modules.intelligence.momentum_alerts import get_momentum_alert_engine
    engine = get_momentum_alert_engine(_get_db())
    
    success = await engine.unsubscribe(user_id, entity_key)
    
    return {
        "ok": success
    }


# =============================================================================
# ENTITY DISCOVERY
# =============================================================================

@router.get("/discovery/queue/stats")
async def get_discovery_queue_stats():
    """Get entity discovery queue statistics"""
    from modules.intelligence.entity_discovery import get_entity_discovery_engine
    engine = get_entity_discovery_engine(_get_db())
    
    stats = await engine.get_queue_stats()
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        **stats
    }


@router.post("/discovery/enqueue")
async def enqueue_entity_for_discovery(
    entity_type: str = Query(..., description="Entity type: project, fund, person"),
    entity_id: str = Query(..., description="Entity ID/slug"),
    entity_name: Optional[str] = Query(None, description="Entity display name"),
    priority: int = Query(2, ge=1, le=3, description="Priority: 1=high, 2=normal, 3=low")
):
    """
    Add entity to discovery queue.
    System will automatically discover sources for this entity.
    """
    from modules.intelligence.entity_discovery import get_entity_discovery_engine
    engine = get_entity_discovery_engine(_get_db())
    
    entity_key = await engine.enqueue_entity(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        priority=priority
    )
    
    return {
        "ok": True,
        "entity_key": entity_key,
        "status": "enqueued"
    }


@router.post("/discovery/process")
async def process_discovery_queue(
    limit: int = Query(10, ge=1, le=100)
):
    """Process pending entities in discovery queue"""
    from modules.intelligence.entity_discovery import get_entity_discovery_engine
    engine = get_entity_discovery_engine(_get_db())
    
    result = await engine.process_queue(limit=limit)
    
    return {
        "ok": True,
        **result
    }


@router.get("/discovery/entity/{entity_type}/{entity_id}")
async def get_entity_discoveries(
    entity_type: str,
    entity_id: str
):
    """Get all discovered sources for an entity"""
    from modules.intelligence.entity_discovery import get_entity_discovery_engine
    engine = get_entity_discovery_engine(_get_db())
    
    entity_key = f"{entity_type}:{entity_id}"
    discoveries = await engine.get_entity_discoveries(entity_key)
    
    return {
        "ok": True,
        "entity_key": entity_key,
        "count": len(discoveries),
        "discoveries": discoveries
    }


@router.post("/discovery/discover/{entity_type}/{entity_id}")
async def discover_entity(
    entity_type: str,
    entity_id: str
):
    """
    Run discovery for a specific entity immediately.
    Searches across all configured sources.
    """
    from modules.intelligence.entity_discovery import get_entity_discovery_engine
    engine = get_entity_discovery_engine(_get_db())
    
    entity_key = f"{entity_type}:{entity_id}"
    
    # Ensure in queue
    await engine.enqueue_entity(entity_type, entity_id)
    
    # Run discovery
    result = await engine.discover_entity(entity_key)
    
    return {
        "ok": True,
        **result
    }


# =============================================================================
# INCREMENTAL EXTRACTION STATE
# =============================================================================

@router.get("/extraction/state/{source_id}")
async def get_extraction_state(source_id: str):
    """Get incremental extraction state for a source"""
    from modules.intelligence.entity_discovery import get_incremental_extractor
    extractor = get_incremental_extractor(_get_db())
    
    state = await extractor.get_state(source_id)
    
    return {
        "ok": True,
        "source_id": source_id,
        "state": state
    }


@router.get("/extraction/states")
async def get_all_extraction_states():
    """Get extraction states for all sources"""
    from modules.intelligence.entity_discovery import get_incremental_extractor
    extractor = get_incremental_extractor(_get_db())
    
    states = await extractor.get_all_states()
    
    return {
        "ok": True,
        "count": len(states),
        "states": states
    }


@router.post("/extraction/state/{source_id}")
async def update_extraction_state(
    source_id: str,
    cursor: Optional[str] = Query(None),
    last_item_id: Optional[str] = Query(None),
    items_fetched: int = Query(0, ge=0)
):
    """Update extraction state for a source"""
    from modules.intelligence.entity_discovery import get_incremental_extractor
    extractor = get_incremental_extractor(_get_db())
    
    state = await extractor.update_state(
        source_id=source_id,
        cursor=cursor,
        last_item_id=last_item_id,
        items_fetched=items_fetched
    )
    
    return {
        "ok": True,
        "source_id": source_id,
        "state": state
    }
