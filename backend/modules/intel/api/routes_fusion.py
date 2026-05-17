"""
Fusion API Routes
=================

API endpoints для Data Fusion Engine:
- /api/fusion/events - unified event feed
- /api/fusion/signals - market signals
- /api/fusion/entities - fused entities
- /api/fusion/run - trigger fusion
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
import os

# DB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
_client = AsyncIOMotorClient(mongo_url)
_db = _client[os.environ.get('DB_NAME', 'test_database')]

from ..fusion.engine import get_fusion_engine, DataFusionEngine
from ..fusion.models import EventType, SignalType

router = APIRouter(prefix="/api/fusion", tags=["Data Fusion"])

# Initialize engine
def get_engine() -> DataFusionEngine:
    engine = get_fusion_engine(_db)
    if engine is None:
        engine = get_fusion_engine(_db)
    return engine


# ═══════════════════════════════════════════════════════════════
# UNIFIED EVENT FEED
# ═══════════════════════════════════════════════════════════════

@router.get("/feed")
async def get_unified_feed(
    types: Optional[str] = Query(None, description="Comma-separated event types"),
    entity: Optional[str] = Query(None, description="Filter by entity ID"),
    min_impact: int = Query(0, ge=0, le=100, description="Minimum impact score"),
    min_confidence: float = Query(0, ge=0, le=1, description="Minimum confidence"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Get unified event feed from all sources.
    
    Returns funding, unlocks, activities, news in single feed.
    """
    engine = get_engine()
    
    event_types = types.split(",") if types else None
    
    return await engine.get_unified_feed(
        event_types=event_types,
        entity_id=entity,
        min_impact=min_impact,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset
    )


@router.get("/events")
async def get_fused_events(
    event_type: Optional[str] = Query(None, description="Event type filter"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Get fused events with optional type filter"""
    engine = get_engine()
    
    types = [event_type] if event_type else None
    
    return await engine.get_unified_feed(
        event_types=types,
        limit=limit,
        offset=offset
    )


@router.get("/events/{event_id}")
async def get_event_by_id(event_id: str):
    """Get specific fused event by ID"""
    engine = get_engine()
    
    doc = await engine.fused_events.find_one(
        {"id": event_id},
        {"_id": 0}
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return doc


@router.get("/events/project/{project_id}")
async def get_project_events(
    project_id: str,
    limit: int = Query(50, ge=1, le=200)
):
    """Get all events for a project"""
    engine = get_engine()
    return await engine.get_entity_timeline(project_id, limit)


# ═══════════════════════════════════════════════════════════════
# SIGNALS
# ═══════════════════════════════════════════════════════════════

@router.get("/signals")
async def get_signals(
    signal_type: Optional[str] = Query(None, description="Signal type filter"),
    min_score: int = Query(50, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100)
):
    """Get active market signals"""
    engine = get_engine()
    return await engine.get_top_signals(signal_type, min_score, limit)


@router.get("/signals/{asset_id}")
async def get_asset_signals(
    asset_id: str,
    limit: int = Query(10, ge=1, le=50)
):
    """Get signals for specific asset"""
    engine = get_engine()
    
    cursor = engine.fused_signals.find(
        {"asset_id": asset_id},
        {"_id": 0}
    ).sort([("date", -1)]).limit(limit)
    
    signals = []
    async for doc in cursor:
        signals.append(doc)
    
    return {"asset_id": asset_id, "signals": signals}


@router.get("/signals/top")
async def get_top_signals(
    min_score: int = Query(70, ge=0, le=100),
    limit: int = Query(10, ge=1, le=50)
):
    """Get top signals by score"""
    engine = get_engine()
    return await engine.get_top_signals(min_score=min_score, limit=limit)


# ═══════════════════════════════════════════════════════════════
# ENTITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/entities")
async def get_fused_entities(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Get fused entities"""
    engine = get_engine()
    
    query = {}
    if entity_type:
        query["entity_type"] = entity_type
    
    total = await engine.fused_entities.count_documents(query)
    
    cursor = engine.fused_entities.find(query, {"_id": 0}).skip(offset).limit(limit)
    
    entities = []
    async for doc in cursor:
        entities.append(doc)
    
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "limit": limit,
        "offset": offset,
        "entities": entities
    }


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str):
    """Get fused entity by ID"""
    engine = get_engine()
    
    entity = await engine.find_entity(entity_id)
    
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    return entity.model_dump()


@router.get("/entities/{entity_id}/timeline")
async def get_entity_timeline(
    entity_id: str,
    limit: int = Query(50, ge=1, le=200)
):
    """Get event timeline for entity"""
    engine = get_engine()
    return await engine.get_entity_timeline(entity_id, limit)


# ═══════════════════════════════════════════════════════════════
# ADMIN / RUN FUSION
# ═══════════════════════════════════════════════════════════════

@router.post("/run")
async def run_fusion():
    """Run full data fusion pipeline"""
    engine = get_engine()
    return await engine.run_full_fusion()


@router.post("/run/funding")
async def run_funding_fusion():
    """Run funding event fusion"""
    engine = get_engine()
    return await engine.fuse_funding_events()


@router.post("/run/unlocks")
async def run_unlock_fusion():
    """Run unlock event fusion"""
    engine = get_engine()
    return await engine.fuse_unlock_events()


@router.post("/run/activities")
async def run_activity_fusion():
    """Run activity event fusion"""
    engine = get_engine()
    return await engine.fuse_activity_events()


@router.post("/run/news")
async def run_news_fusion():
    """Run news event fusion (includes Incrypted and other news sources)"""
    engine = get_engine()
    return await engine.fuse_news_events()


@router.get("/stats")
async def get_fusion_stats():
    """Get fusion engine statistics"""
    engine = get_engine()
    return await engine.get_stats()


# ═══════════════════════════════════════════════════════════════
# EVENT TYPES & SIGNAL TYPES
# ═══════════════════════════════════════════════════════════════

@router.get("/types/events")
async def get_event_types():
    """Get all event types"""
    return {
        "event_types": [e.value for e in EventType],
        "descriptions": {
            "funding_event": "Funding rounds and investments",
            "unlock_event": "Token unlocks and vesting",
            "listing_event": "Exchange listings",
            "ico_event": "ICO/IDO/IEO events",
            "activity_event": "Airdrops, testnets, campaigns",
            "news_event": "News articles and announcements",
            "market_signal": "Market-related signals",
            "onchain_signal": "On-chain activity signals"
        }
    }


@router.get("/types/signals")
async def get_signal_types():
    """Get all signal types"""
    return {
        "signal_types": [s.value for s in SignalType],
        "descriptions": {
            "pump_setup": "Potential pump setup detected",
            "dump_risk": "Dump risk elevated",
            "unlock_risk": "Upcoming unlock pressure",
            "smart_money_entry": "Smart money accumulation",
            "funding_stress": "Funding rate stress",
            "oi_shock": "Open interest shock",
            "rotation_signal": "Sector rotation signal",
            "narrative_breakout": "Narrative momentum building"
        }
    }
