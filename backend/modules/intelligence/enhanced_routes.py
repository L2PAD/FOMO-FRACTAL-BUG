"""
Enhanced API Routes

API routes for enhanced architecture components:
- Feed projection API
- Observability API
- Narrative lifecycle API
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime

router = APIRouter(prefix="/api/enhanced", tags=["Enhanced Architecture"])


# =============================================================================
# FEED PROJECTION API
# =============================================================================

@router.get("/feed")
async def get_feed(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    card_type: Optional[str] = None,
    min_fomo: float = Query(0, ge=0, le=100),
    entity: Optional[str] = None,
    narrative_id: Optional[str] = None
):
    """
    Get feed cards (optimized for UI)
    
    This is the main feed endpoint - uses pre-computed feed_cards collection
    """
    from server import db
    from modules.intelligence.feed_projection import FeedProjectionService, FeedCardType
    
    service = FeedProjectionService(db)
    
    card_type_enum = None
    if card_type:
        try:
            card_type_enum = FeedCardType(card_type)
        except ValueError:
            pass
    
    cards = await service.get_feed(
        limit=limit,
        offset=offset,
        card_type=card_type_enum,
        min_fomo=min_fomo,
        entity_symbol=entity,
        narrative_id=narrative_id
    )
    
    return {
        "cards": [c.dict() for c in cards],
        "count": len(cards),
        "offset": offset
    }


@router.get("/feed/breaking")
async def get_breaking_feed(limit: int = Query(10, ge=1, le=20)):
    """Get breaking/high priority news"""
    from server import db
    from modules.intelligence.feed_projection import FeedProjectionService
    
    service = FeedProjectionService(db)
    cards = await service.get_breaking_feed(limit=limit)
    
    return {"cards": [c.dict() for c in cards]}


@router.get("/feed/entity/{symbol}")
async def get_entity_feed(symbol: str, limit: int = Query(30, ge=1, le=100)):
    """Get feed for specific asset/entity"""
    from server import db
    from modules.intelligence.feed_projection import FeedProjectionService
    
    service = FeedProjectionService(db)
    cards = await service.get_entity_feed(symbol=symbol, limit=limit)
    
    return {"cards": [c.dict() for c in cards], "entity": symbol.upper()}


# =============================================================================
# OBSERVABILITY API
# =============================================================================

@router.get("/health/sources")
async def get_source_health():
    """Get health status of all data sources"""
    from server import db
    from modules.system.observability import ObservabilityService
    
    service = ObservabilityService(db)
    
    # Get summary
    summary = await service.get_source_health_summary()
    
    # Get individual source health
    sources = await db.source_health.find().to_list(length=100)
    
    return {
        "summary": summary,
        "sources": sources
    }


@router.get("/health/dashboard")
async def get_health_dashboard():
    """Get system health dashboard data"""
    from server import db
    from modules.system.observability import ObservabilityService
    
    service = ObservabilityService(db)
    return await service.get_system_dashboard()


@router.get("/alerts")
async def get_alerts(
    severity: Optional[str] = None,
    source_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100)
):
    """Get active system alerts"""
    from server import db
    from modules.system.observability import ObservabilityService, AlertSeverity
    
    service = ObservabilityService(db)
    
    severity_enum = None
    if severity:
        try:
            severity_enum = AlertSeverity(severity)
        except ValueError:
            pass
    
    alerts = await service.get_active_alerts(
        severity=severity_enum,
        source_id=source_id,
        limit=limit
    )
    
    return {"alerts": [a.dict() for a in alerts]}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, notes: Optional[str] = None):
    """Mark an alert as resolved"""
    from server import db
    from modules.system.observability import ObservabilityService
    
    service = ObservabilityService(db)
    await service.resolve_alert(alert_id, notes)
    
    return {"status": "resolved", "alert_id": alert_id}


# =============================================================================
# NARRATIVE LIFECYCLE API
# =============================================================================

@router.get("/narratives/emerging")
async def get_emerging_narratives(limit: int = Query(10, ge=1, le=50)):
    """
    Get emerging narratives (early detection)
    
    These are narratives just starting to form with positive velocity
    """
    from server import db
    from modules.narrative.enhanced_narrative import EnhancedNarrativeService
    
    service = EnhancedNarrativeService(db)
    narratives = await service.get_emerging_narratives(limit=limit)
    
    return {"narratives": narratives, "lifecycle_state": "emerging"}


@router.get("/narratives/peaking")
async def get_peaking_narratives(limit: int = Query(10, ge=1, le=50)):
    """
    Get narratives at peak
    
    Maximum attention, may start declining soon
    """
    from server import db
    from modules.narrative.enhanced_narrative import EnhancedNarrativeService
    
    service = EnhancedNarrativeService(db)
    narratives = await service.get_peaking_narratives(limit=limit)
    
    return {"narratives": narratives, "lifecycle_state": "peak"}


@router.get("/narratives/{narrative_id}/cluster")
async def get_narrative_cluster(narrative_id: str):
    """
    Get entity cluster for a narrative
    
    Returns projects, funds, persons associated with narrative
    """
    from server import db
    from modules.narrative.enhanced_narrative import EnhancedNarrativeService
    
    service = EnhancedNarrativeService(db)
    cluster = await service.get_narrative_cluster(narrative_id)
    
    return {"narrative_id": narrative_id, "cluster": cluster}


@router.post("/narratives/{narrative_id}/lifecycle/update")
async def update_narrative_lifecycle(narrative_id: str):
    """Force update lifecycle metrics for a narrative"""
    from server import db
    from modules.narrative.enhanced_narrative import EnhancedNarrativeService
    
    service = EnhancedNarrativeService(db)
    await service.update_lifecycle_metrics(narrative_id)
    
    # Get updated narrative
    narrative = await db.narratives.find_one({"id": narrative_id})
    
    return {
        "narrative_id": narrative_id,
        "lifecycle_state": narrative.get("lifecycle_state") if narrative else None,
        "momentum_velocity": narrative.get("momentum_velocity") if narrative else None,
        "momentum_acceleration": narrative.get("momentum_acceleration") if narrative else None
    }


# =============================================================================
# FEED WORKER API (Hot/Archive Split)
# =============================================================================

@router.get("/feed/stats")
async def get_feed_stats():
    """Get feed projection statistics"""
    from server import db
    from modules.intelligence.feed_worker import FeedProjectionWorker
    
    worker = FeedProjectionWorker(db)
    await worker.initialize()
    
    return await worker.get_stats()


@router.post("/feed/project")
async def trigger_projection(limit: int = Query(200, ge=1, le=1000)):
    """Manually trigger feed projection for new events"""
    from server import db
    from modules.intelligence.feed_worker import FeedProjectionWorker
    
    worker = FeedProjectionWorker(db)
    await worker.initialize()
    
    stats = await worker.project_new_events(limit=limit)
    
    return {"status": "completed", "stats": stats}


@router.post("/feed/archive")
async def trigger_archive():
    """Manually trigger archive job"""
    from server import db
    from modules.intelligence.feed_worker import FeedProjectionWorker
    
    worker = FeedProjectionWorker(db)
    await worker.initialize()
    
    stats = await worker.archive_old_cards()
    
    return {"status": "completed", "stats": stats}


# =============================================================================
# QUEUE API
# =============================================================================

@router.get("/queue/stats")
async def get_queue_stats():
    """Get job queue statistics"""
    from modules.queue.enhanced_queue import get_job_queue
    from server import db
    
    queue = get_job_queue(db)
    return queue.get_stats()


@router.get("/queue/dlq")
async def get_dead_letter_queue(limit: int = Query(50, ge=1, le=100)):
    """Get dead letter queue jobs"""
    from modules.queue.enhanced_queue import get_job_queue
    from server import db
    
    queue = get_job_queue(db)
    jobs = await queue.get_dlq_jobs(limit=limit)
    
    return {"jobs": jobs, "count": len(jobs)}


@router.post("/queue/dlq/{job_id}/retry")
async def retry_dlq_job(job_id: str):
    """Retry a job from dead letter queue"""
    from modules.queue.enhanced_queue import get_job_queue
    from server import db
    
    queue = get_job_queue(db)
    job = await queue.retry_dlq_job(job_id)
    
    if job:
        return {"status": "requeued", "job_id": job_id}
    else:
        raise HTTPException(status_code=404, detail="Job not found in DLQ")


# =============================================================================
# SCORING API
# =============================================================================

@router.post("/score/article")
async def score_article(
    title: str,
    content: str = "",
    source: str = "",
    entities: List[str] = []
):
    """
    Score an article with enhanced 5-axis scoring
    
    Returns: sentiment, importance, confidence, rumor, impact, fomo_score
    """
    from modules.intelligence.enhanced_scoring import enhanced_scoring_pipeline
    
    scores = enhanced_scoring_pipeline.score_article(
        title=title,
        content=content,
        source=source,
        entities=entities
    )
    
    return scores.dict()


# =============================================================================
# CONFLICT STRATEGY API
# =============================================================================

@router.get("/ownership/strategies")
async def get_conflict_strategies():
    """Get all field conflict resolution strategies"""
    from modules.ownership.conflict_strategy import FIELD_CONFLICT_STRATEGY
    
    return {
        field: {
            "strategy": rule.strategy.value,
            "merge_method": rule.merge_method,
            "min_sources_for_vote": rule.min_sources_for_vote,
            "confidence_threshold": rule.confidence_threshold
        }
        for field, rule in FIELD_CONFLICT_STRATEGY.items()
    }


@router.get("/ownership/strategies/{field}")
async def get_field_strategy(field: str):
    """Get conflict strategy for a specific field"""
    from modules.ownership.conflict_strategy import FIELD_CONFLICT_STRATEGY
    
    rule = FIELD_CONFLICT_STRATEGY.get(field)
    if not rule:
        raise HTTPException(status_code=404, detail=f"No strategy for field: {field}")
    
    return rule.dict()
