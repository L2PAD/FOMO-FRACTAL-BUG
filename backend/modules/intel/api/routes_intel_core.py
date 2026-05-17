"""
Intel Entities & Events API Routes
==================================
API endpoints for intel entities and events.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intel-core", tags=["Intel Layer Core"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ═══════════════════════════════════════════════════════════════
# ENTITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/entities")
async def list_entities(
    type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0)
):
    """List all intel entities"""
    from server import db
    from modules.intel.intel_entities_events import IntelEntitiesService
    
    service = IntelEntitiesService(db)
    result = await service.list_entities(
        entity_type=type,
        limit=limit,
        offset=offset
    )
    
    return {
        "ts": ts_now(),
        **result
    }


@router.get("/entities/search")
async def search_entities(
    q: str = Query(..., min_length=2),
    type: Optional[str] = Query(None),
    limit: int = Query(20, le=100)
):
    """Search entities by name, symbol, or slug"""
    from server import db
    from modules.intel.intel_entities_events import IntelEntitiesService
    
    service = IntelEntitiesService(db)
    entities = await service.search_entities(q, entity_type=type, limit=limit)
    
    return {
        "ts": ts_now(),
        "query": q,
        "total": len(entities),
        "entities": entities
    }


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str):
    """Get entity by ID"""
    from server import db
    from modules.intel.intel_entities_events import IntelEntitiesService
    
    service = IntelEntitiesService(db)
    entity = await service.get_entity(entity_id)
    
    if not entity:
        raise HTTPException(404, "Entity not found")
    
    return {
        "ts": ts_now(),
        "entity": entity
    }


@router.post("/entities/sync")
async def sync_entities(background_tasks: BackgroundTasks):
    """Sync entities from all data sources"""
    from server import db
    from modules.intel.intel_entities_events import IntelEntitiesService
    
    service = IntelEntitiesService(db)
    
    async def run_sync():
        result = await service.sync_entities_from_sources()
        logger.info(f"Entities sync complete: {result}")
    
    background_tasks.add_task(run_sync)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Entities sync started"
    }


# ═══════════════════════════════════════════════════════════════
# EVENTS
# ═══════════════════════════════════════════════════════════════

@router.get("/events")
async def list_events(
    type: Optional[str] = Query(None, description="Event type filter"),
    entity: Optional[str] = Query(None, description="Filter by entity ID"),
    severity: Optional[str] = Query(None, description="Severity filter"),
    days: int = Query(30, le=365, description="Days to look back"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0)
):
    """List intel events"""
    from server import db
    from modules.intel.intel_entities_events import IntelEventsService
    
    service = IntelEventsService(db)
    result = await service.list_events(
        event_type=type,
        entity_id=entity,
        severity=severity,
        days=days,
        limit=limit,
        offset=offset
    )
    
    return {
        "ts": ts_now(),
        **result
    }


@router.get("/events/upcoming")
async def get_upcoming_events(
    days: int = Query(30, le=180),
    limit: int = Query(20, le=100)
):
    """Get upcoming events"""
    from server import db
    from modules.intel.intel_entities_events import IntelEventsService
    
    service = IntelEventsService(db)
    events = await service.get_upcoming_events(days=days, limit=limit)
    
    return {
        "ts": ts_now(),
        "days": days,
        "total": len(events),
        "events": events
    }


@router.get("/events/{event_id}")
async def get_event(event_id: str):
    """Get event by ID"""
    from server import db
    from modules.intel.intel_entities_events import IntelEventsService
    
    service = IntelEventsService(db)
    event = await service.get_event(event_id)
    
    if not event:
        raise HTTPException(404, "Event not found")
    
    return {
        "ts": ts_now(),
        "event": event
    }


@router.post("/events/sync")
async def sync_events(background_tasks: BackgroundTasks):
    """Generate events from all data sources"""
    from server import db
    from modules.intel.intel_entities_events import IntelEventsService
    
    service = IntelEventsService(db)
    
    async def run_sync():
        result = await service.sync_events_from_sources()
        logger.info(f"Events sync complete: {result}")
    
    background_tasks.add_task(run_sync)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Events sync started"
    }


@router.post("/sync-all")
async def sync_all_intel(background_tasks: BackgroundTasks):
    """Sync both entities and events"""
    from server import db
    from modules.intel.intel_entities_events import IntelEntitiesService, IntelEventsService
    
    async def run_full_sync():
        entities_service = IntelEntitiesService(db)
        events_service = IntelEventsService(db)
        
        entities_result = await entities_service.sync_entities_from_sources()
        events_result = await events_service.sync_events_from_sources()
        
        logger.info(f"Full intel sync: entities={entities_result}, events={events_result}")
    
    background_tasks.add_task(run_full_sync)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Full intel sync started (entities + events)"
    }
