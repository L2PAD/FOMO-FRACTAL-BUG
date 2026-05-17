"""
News Intelligence API Routes
=============================

REST API for news intelligence layer.
"""

import logging
import asyncio
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query

from ..models import EventFeedItem, EventDetail, EventType
from ..ranking import EventRanker
from ..jobs import NewsIntelligencePipeline
from ..ingestion import get_active_sources

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/news-intelligence", tags=["News Intelligence"])

# Database reference (set by main app)
_db = None


def set_database(db):
    """Set database reference."""
    global _db
    _db = db


def get_db():
    """Get database reference."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return _db


# ═══════════════════════════════════════════════════════════════
# FEED ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/feed")
async def get_news_feed(
    limit: int = Query(default=20, le=100),
    event_type: Optional[str] = None,
    asset: Optional[str] = None,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    language: str = Query(default="en")
):
    """
    Get news event feed.
    
    Returns ranked list of news events.
    """
    db = get_db()
    ranker = EventRanker(db)
    
    events = await ranker.get_ranked_events(
        limit=limit,
        event_type=event_type,
        asset=asset,
        min_confidence=min_confidence
    )
    
    feed_items = []
    for event in events:
        # Choose language
        headline = event.get("title_en") or event.get("title_seed", "")
        summary = event.get("summary_en") or ""
        
        if language == "ru":
            headline = event.get("title_ru") or headline
            summary = event.get("summary_ru") or summary
        
        item = EventFeedItem(
            id=event.get("id", ""),
            headline=headline,
            summary=summary,
            event_type=event.get("event_type", "news"),
            status=event.get("status", "candidate"),
            confidence=event.get("confidence_score", 0),
            source_count=event.get("source_count", 0),
            article_count=event.get("article_count", 0),
            assets=event.get("primary_assets", []),
            entities=event.get("primary_entities", []),
            regions=event.get("regions", []),
            cover_image=event.get("cover_image_url") or event.get("cover_image_base64"),
            published_at=str(event.get("published_at", "")) if event.get("published_at") else None,
            first_seen_at=str(event.get("first_seen_at", "")),
            feed_score=event.get("feed_score", 0),
            fomo_score=event.get("fomo_score")
        )
        item_dict = item.model_dump()
        # Add full story data for modal view
        item_dict["story_en"] = event.get("story_en")
        item_dict["story_ru"] = event.get("story_ru") 
        item_dict["ai_view"] = event.get("ai_view") or event.get("ai_view_en")
        item_dict["key_facts"] = event.get("key_facts", [])
        item_dict["confidence_score"] = event.get("confidence_score", 0)
        feed_items.append(item_dict)
    
    return {
        "ok": True,
        "events": feed_items,
        "total": len(feed_items),
        "language": language
    }


@router.get("/events/{event_id}")
async def get_event_detail(event_id: str, language: str = "en"):
    """
    Get detailed event information.
    """
    db = get_db()
    
    event = await db.news_events.find_one({"id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Choose language
    headline = event.get("title_en") or event.get("title_seed", "")
    summary = event.get("summary_en") or ""
    story = event.get("story_en")
    ai_view = event.get("ai_view_en")
    
    if language == "ru":
        headline = event.get("title_ru") or headline
        summary = event.get("summary_ru") or summary
        story = event.get("story_ru") or story
        ai_view = event.get("ai_view_ru") or ai_view
    
    # Get source info
    sources = []
    for article_id in event.get("article_ids", [])[:10]:
        article = await db.normalized_articles.find_one(
            {"id": article_id},
            {"_id": 0, "source_name": 1, "canonical_url": 1, "published_at": 1, "title": 1}
        )
        if article:
            sources.append({
                "name": article.get("source_name", "Unknown"),
                "url": article.get("canonical_url", ""),
                "title": article.get("title", ""),
                "published_at": article.get("published_at", "")
            })
    
    detail = EventDetail(
        id=event.get("id", ""),
        headline=headline,
        summary=summary,
        story=story,
        ai_view=ai_view,
        event_type=event.get("event_type", "news"),
        status=event.get("status", "candidate"),
        confidence=event.get("confidence_score", 0),
        importance=event.get("importance_score", 0),
        source_count=event.get("source_count", 0),
        article_count=event.get("article_count", 0),
        assets=event.get("primary_assets", []),
        entities=event.get("primary_entities", []),
        organizations=event.get("organizations", []),
        persons=event.get("persons", []),
        regions=event.get("regions", []),
        facts=event.get("extracted_facts", []),
        conflicts=event.get("fact_conflicts", []),
        sources=sources,
        cover_image=event.get("cover_image_url"),
        published_at=str(event.get("published_at", "")) if event.get("published_at") else None,
        first_seen_at=str(event.get("first_seen_at", "")),
        last_seen_at=str(event.get("last_seen_at", ""))
    )
    
    return detail.model_dump()


@router.get("/assets/{symbol}")
async def get_events_by_asset(
    symbol: str,
    limit: int = Query(default=20, le=50)
):
    """
    Get events for a specific asset.
    """
    db = get_db()
    
    cursor = db.news_events.find({
        "primary_assets": symbol.upper(),
        "status": {"$in": ["developing", "confirmed", "official"]}
    }).sort("feed_score", -1).limit(limit)
    
    events = []
    async for event in cursor:
        events.append({
            "id": event.get("id"),
            "headline": event.get("title_en") or event.get("title_seed"),
            "summary": event.get("summary_en", ""),
            "event_type": event.get("event_type"),
            "status": event.get("status"),
            "source_count": event.get("source_count"),
            "confidence": event.get("confidence_score"),
            "first_seen_at": event.get("first_seen_at"),
            "feed_score": event.get("feed_score")
        })
    
    return {
        "ok": True,
        "asset": symbol.upper(),
        "events": events,
        "total": len(events)
    }


@router.get("/breaking")
async def get_breaking_news(limit: int = 5):
    """
    Get latest breaking/developing news.
    """
    db = get_db()
    
    cursor = db.news_events.find({
        "status": {"$in": ["developing", "confirmed"]},
        "source_count": {"$gte": 2}
    }).sort("first_seen_at", -1).limit(limit)
    
    events = []
    async for event in cursor:
        events.append({
            "id": event.get("id"),
            "headline": event.get("title_en") or event.get("title_seed"),
            "event_type": event.get("event_type"),
            "status": event.get("status"),
            "assets": event.get("primary_assets", []),
            "source_count": event.get("source_count"),
            "fomo_score": event.get("fomo_score"),
            "first_seen_at": event.get("first_seen_at")
        })
    
    return {
        "ok": True,
        "events": events
    }


# ═══════════════════════════════════════════════════════════════
# ADMIN/PIPELINE ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/pipeline/run")
async def run_pipeline():
    """
    Manually trigger the news intelligence pipeline.
    """
    db = get_db()
    pipeline = NewsIntelligencePipeline(db)
    
    result = await pipeline.run_full_pipeline()
    return result


@router.post("/pipeline/fetch")
async def run_fetch():
    """
    Run only the fetch stage.
    """
    db = get_db()
    pipeline = NewsIntelligencePipeline(db)
    
    result = await pipeline.run_fetch_only()
    return result


@router.post("/pipeline/process")
async def run_process():
    """
    Run processing stages (normalize, embed, cluster).
    """
    db = get_db()
    pipeline = NewsIntelligencePipeline(db)
    
    result = await pipeline.run_process_only()
    return result


@router.post("/pipeline/synthesize")
async def run_synthesis():
    """
    Run synthesis for confirmed events.
    """
    db = get_db()
    pipeline = NewsIntelligencePipeline(db)
    
    result = await pipeline.run_synthesis_only()
    return result


@router.post("/pipeline/merge")
async def run_merge():
    """
    Run event merge to combine similar events.
    """
    db = get_db()
    from ..clustering import EventClusteringEngine
    
    clustering = EventClusteringEngine(db)
    result = await clustering.merge_similar_events()
    return {"ok": True, **result}


# ═══════════════════════════════════════════════════════════════
# SCHEDULER ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/scheduler/start")
async def start_scheduler(interval_minutes: int = 10):
    """
    Start the background news intelligence scheduler.
    Default interval: 10 minutes.
    """
    db = get_db()
    from ..jobs.scheduler import NewsScheduler
    
    scheduler = NewsScheduler(db)
    success = scheduler.start(interval_seconds=interval_minutes * 60)
    
    return {
        "ok": success,
        "message": f"Scheduler started with {interval_minutes} minute interval" if success else "Scheduler already running",
        "status": scheduler.get_status()
    }


@router.post("/scheduler/stop")
async def stop_scheduler():
    """
    Stop the background scheduler.
    """
    from ..jobs.scheduler import NewsScheduler
    
    scheduler = NewsScheduler(None)
    success = scheduler.stop()
    
    return {
        "ok": success,
        "message": "Scheduler stopped" if success else "Scheduler not running"
    }


@router.get("/scheduler/status")
async def get_scheduler_status():
    """
    Get scheduler status and last run info.
    """
    from ..jobs.scheduler import NewsScheduler
    
    return {
        "ok": True,
        **NewsScheduler.get_status()
    }


@router.get("/events/{event_id}/generation-status")
async def get_event_generation_status(event_id: str):
    """
    Get generation progress for a specific event.
    
    Stages:
    - DETECTED: Event detected from articles
    - CLUSTERING: Clustering related articles
    - AI_WRITING: Generating AI content (30-70%)
    - IMAGE_GENERATION: Creating cover image (70-90%)
    - READY: Generation complete
    - PUBLISHED: Story published
    - ERROR: Generation failed
    """
    from ..jobs.scheduler import get_generation_progress
    
    progress = get_generation_progress(event_id)
    
    # If not in active generation, check if event has story
    if progress.get("stage") == "unknown":
        db = get_db()
        event = await db.news_events.find_one(
            {"id": event_id},
            {"_id": 0, "story_en": 1, "cover_image_base64": 1, "story_generated_at": 1}
        )
        
        if event:
            if event.get("story_en") and event.get("cover_image_base64"):
                return {
                    "ok": True,
                    "event_id": event_id,
                    "stage": "PUBLISHED",
                    "progress": 100,
                    "message": "Story published",
                    "generated_at": event.get("story_generated_at")
                }
            elif event.get("story_en"):
                return {
                    "ok": True,
                    "event_id": event_id,
                    "stage": "READY",
                    "progress": 90,
                    "message": "Story ready (no image)"
                }
            else:
                return {
                    "ok": True,
                    "event_id": event_id,
                    "stage": "DETECTED",
                    "progress": 10,
                    "message": "Event detected, pending generation"
                }
        else:
            return {
                "ok": False,
                "event_id": event_id,
                "stage": "NOT_FOUND",
                "progress": 0,
                "message": "Event not found"
            }
    
    return {
        "ok": True,
        "event_id": event_id,
        **progress
    }


@router.get("/generation/active")
async def get_active_generations():
    """
    Get all currently active generation processes.
    """
    from ..jobs.scheduler import _generation_progress
    
    return {
        "ok": True,
        "active_count": len(_generation_progress),
        "generations": _generation_progress
    }


@router.post("/scheduler/run-top-events")
async def run_top_events_now():
    """
    Manually trigger top events AI generation.
    Generates stories for top 3 events with score > 70 and >= 3 sources.
    """
    db = get_db()
    from ..jobs.scheduler import NewsScheduler
    
    scheduler = NewsScheduler(db)
    result = await scheduler.run_top_events_generation()
    
    return {
        "ok": True,
        **result
    }


@router.get("/stats")
async def get_stats():
    """
    Get news intelligence pipeline statistics.
    """
    db = get_db()
    pipeline = NewsIntelligencePipeline(db)
    
    stats = await pipeline.get_pipeline_stats()
    return {
        "ok": True,
        "stats": stats
    }


@router.get("/sources")
async def get_sources():
    """
    Get configured news sources.
    """
    sources = get_active_sources()
    
    return {
        "ok": True,
        "sources": [
            {
                "id": s.id,
                "name": s.name,
                "domain": s.domain,
                "type": s.source_type,
                "tier": s.tier,
                "language": s.language,
                "is_active": s.is_active
            }
            for s in sources
        ],
        "total": len(sources)
    }


@router.get("/sources-registry")
async def get_full_sources_list(
    tier: str = Query(None, description="Filter by tier: A, B, C, D"),
    language: str = Query(None, description="Filter by language: en, ru, zh, jp, de, ua"),
    category: str = Query(None, description="Filter by category: news, research, official, analytics, security, defi, aggregator"),
    status: str = Query(None, description="Filter by status: active, degraded, paused, disabled")
):
    """
    Get full list of all news sources from database with filtering.
    Returns comprehensive info for UI display including health metrics.
    """
    from ..ingestion.health import get_health_monitor
    db = get_db()
    health_monitor = get_health_monitor()
    
    # Build query
    query = {}
    if tier:
        query["tier"] = tier.upper()
    if language:
        query["language"] = language.lower()
    if category:
        query["category"] = category.lower()
    
    # Fetch from database
    sources = []
    cursor = db.news_sources.find(query, {"_id": 0}).sort([("tier", 1), ("name", 1)])
    async for source in cursor:
        source_id = source.get("id")
        if not source_id:
            continue
        
        # Set default status to active for all sources
        health_status = source.get("status", "active")
        health_score = 0.8  # Default healthy
        articles_today = 0
        last_fetch = None
        
        # Try to get health metrics if available
        try:
            if source_id in health_monitor.sources:
                metrics = health_monitor.sources[source_id]
                health_score = metrics.health_score() if hasattr(metrics, "health_score") else 0.8
                articles_today = getattr(metrics, "total_fetches", 0) if hasattr(metrics, "total_fetches") else 0
                last_fetch = getattr(metrics, "last_fetch_time", None) if hasattr(metrics, "last_fetch_time") else None
                
                if health_score >= 0.8:
                    health_status = "active"
                elif health_score >= 0.5:
                    health_status = "degraded"
                elif health_score > 0:
                    health_status = "paused"
                else:
                    health_status = "disabled"
        except Exception:
            pass  # Keep default status
        
        # Apply status filter
        if status and health_status != status.lower():
            continue
        
        sources.append({
            "id": source_id,
            "name": source.get("name"),
            "domain": source.get("domain"),
            "tier": source.get("tier"),
            "language": source.get("language"),
            "category": source.get("category", "news"),
            "rss_url": source.get("rss_url"),
            "status": health_status,
            "health_score": round(health_score, 2),
            "articles_today": articles_today,
            "last_fetch": str(last_fetch) if last_fetch else None
        })
    
    # Stats by category
    stats = {
        "total": len(sources),
        "by_tier": {},
        "by_language": {},
        "by_category": {},
        "by_status": {}
    }
    
    for s in sources:
        # By tier
        tier_key = s.get("tier", "?")
        stats["by_tier"][tier_key] = stats["by_tier"].get(tier_key, 0) + 1
        
        # By language
        lang_key = s.get("language", "?")
        stats["by_language"][lang_key] = stats["by_language"].get(lang_key, 0) + 1
        
        # By category
        cat_key = s.get("category", "?")
        stats["by_category"][cat_key] = stats["by_category"].get(cat_key, 0) + 1
        
        # By status
        status_key = s.get("status", "unknown")
        stats["by_status"][status_key] = stats["by_status"].get(status_key, 0) + 1
    
    return {
        "ok": True,
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "sources": sources,
        "stats": stats
    }


@router.get("/event-types")
async def get_event_types():
    """
    Get available event types.
    """
    return {
        "ok": True,
        "types": [t.value for t in EventType]
    }



# ═══════════════════════════════════════════════════════════════
# HEALTH MONITORING ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/health/sources")
async def get_sources_health():
    """
    Get health metrics for all news sources.
    Includes fetch success rate, validation rate, and parser drift detection.
    """
    from ..ingestion.health import get_health_monitor
    from ..ingestion.validator import get_validator
    from ..ingestion.sandbox import get_sandbox
    
    health_monitor = get_health_monitor()
    validator = get_validator()
    sandbox = get_sandbox()
    
    sources_health = health_monitor.get_all_health()
    
    # Enrich with validation stats
    for source_health in sources_health:
        source_id = source_health["source_id"]
        
        # Add validation health
        validation_health = validator.get_source_validation_health(source_id)
        source_health["validation"] = {
            "valid_rate": validation_health.get("valid_rate", 1.0),
            "avg_confidence": validation_health.get("avg_confidence", 1.0),
            "common_issues": validation_health.get("common_issues", {})
        }
        
        # Add sandbox health
        sandbox_health = sandbox.get_source_health(source_id)
        source_health["sandbox"] = {
            "avg_duration_ms": sandbox_health.get("avg_duration_ms", 0),
            "timeouts": sandbox_health.get("timeouts", 0)
        }
        
        # Detect drift
        source_health["drift_detected"] = (
            validator.detect_parser_drift(source_id) or 
            health_monitor.detect_drift(source_id)
        )
    
    return {
        "ok": True,
        "sources": sources_health,
        "summary": health_monitor.get_summary()
    }


@router.get("/health/summary")
async def get_health_summary():
    """
    Get summary of source health system.
    """
    from ..ingestion.health import get_health_monitor
    from ..ingestion.sandbox import get_sandbox
    
    health_monitor = get_health_monitor()
    sandbox = get_sandbox()
    
    return {
        "ok": True,
        "health_summary": health_monitor.get_summary(),
        "sandbox_stats": {
            "sources_tracked": len(sandbox.execution_stats)
        }
    }


@router.post("/health/unpause/{source_id}")
async def unpause_source(source_id: str):
    """
    Manually unpause a paused source.
    """
    from ..ingestion.health import get_health_monitor, SourceStatus
    
    health_monitor = get_health_monitor()
    
    if source_id not in health_monitor.sources:
        return {"ok": False, "message": "Source not found"}
    
    metrics = health_monitor.sources[source_id]
    metrics.status = SourceStatus.DEGRADED
    metrics.paused_until = None
    metrics.consecutive_errors = 0
    
    return {
        "ok": True,
        "message": f"Source {source_id} unpaused",
        "new_status": metrics.status.value
    }



# ═══════════════════════════════════════════════════════════════
# COVER IMAGE GENERATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/generate-image/{event_id}")
async def generate_event_image(event_id: str):
    """
    Generate cover image for a specific event.
    Only works for confirmed/developing events.
    """
    from ..synthesis.image_generator import get_image_generator, set_image_generator_db
    
    db = get_db()
    set_image_generator_db(db)
    
    # Get event
    event = await db.news_events.find_one({"id": event_id})
    if not event:
        return {"ok": False, "error": "Event not found"}
    
    generator = get_image_generator()
    result = await generator.generate_for_event(event)
    
    return {"ok": True, **result}


@router.post("/generate-images/batch")
async def generate_batch_images(limit: int = 5):
    """
    Generate cover images for confirmed events without images.
    """
    from ..synthesis.image_generator import get_image_generator, set_image_generator_db
    
    db = get_db()
    set_image_generator_db(db)
    
    generator = get_image_generator()
    results = await generator.generate_batch(limit=limit)
    
    return {"ok": True, **results}


# ═══════════════════════════════════════════════════════════════
# LEAD SOURCE DETECTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/lead-sources")
async def get_lead_sources():
    """
    Get lead source ranking and metrics.
    Shows which sources are fastest at breaking news.
    """
    from ..clustering.lead_detector import get_lead_detector, set_lead_detector_db
    
    db = get_db()
    set_lead_detector_db(db)
    
    detector = get_lead_detector()
    await detector.load_from_db()
    
    return {
        "ok": True,
        "sources": detector.get_all_metrics(),
        "ranking": detector.get_lead_ranking(10)
    }


@router.post("/lead-sources/analyze")
async def analyze_lead_sources():
    """
    Analyze all events to calculate lead source metrics.
    Run this periodically to update source rankings.
    """
    from ..clustering.lead_detector import get_lead_detector, set_lead_detector_db
    
    db = get_db()
    set_lead_detector_db(db)
    
    detector = get_lead_detector()
    results = await detector.analyze_all_events()
    
    return {"ok": True, **results}


@router.get("/lead-sources/tiers")
async def get_source_tiers():
    """
    Get sources grouped by dynamically calculated tiers.
    Tier A = fastest sources (refresh every 3 min)
    Tier B = medium sources (refresh every 10 min)
    Tier C = slow sources (refresh every 30 min)
    """
    from ..clustering.lead_detector import get_lead_detector, set_lead_detector_db
    
    db = get_db()
    set_lead_detector_db(db)
    
    detector = get_lead_detector()
    await detector.load_from_db()
    tiers = detector.recalculate_tiers()
    
    return {
        "ok": True,
        "tiers": tiers,
        "counts": {k: len(v) for k, v in tiers.items()},
        "refresh_intervals": detector.tier_intervals
    }


# ═══════════════════════════════════════════════════════════════
# SOURCE STATISTICS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/sources/count")
async def get_sources_count():
    """
    Get count of news sources by tier.
    """
    from ..ingestion.sources import get_source_count
    
    counts = get_source_count()
    
    return {
        "ok": True,
        **counts
    }



# ═══════════════════════════════════════════════════════════════
# CUSTOM NEWS GENERATION ENDPOINT
# ═══════════════════════════════════════════════════════════════

@router.post("/generate-story")
async def generate_custom_story(
    topic: str = Query(..., description="Topic for the news story"),
    event_type: str = Query(default="news", description="Type: funding, regulation, listing, partnership, hack, launch"),
    assets: str = Query(default="", description="Comma-separated assets like BTC,ETH,SOL")
):
    """
    Generate a unique AI-powered news story on a given topic.
    Creates headline, summary, full story in BOTH EN and RU, plus cover image.
    Uses parallel generation for ~3x faster execution.
    Tracks progress via /events/{id}/generation-status endpoint.
    """
    from ..synthesis.story_builder import StorySynthesizer
    from ..synthesis.image_generator import CoverImageGenerator
    from ..jobs.scheduler import set_generation_progress, clear_generation_progress
    import uuid
    import time
    
    start_time = time.time()
    db = get_db()
    synthesizer = StorySynthesizer(db)
    
    # Parse assets
    assets_list = [a.strip().upper() for a in assets.split(",") if a.strip()]
    
    # Create event seed
    event_id = f"evt_custom_{uuid.uuid4().hex[:12]}"
    event = {
        "id": event_id,
        "title_seed": topic,
        "event_type": event_type,
        "status": "confirmed",
        "primary_assets": assets_list,
        "primary_entities": assets_list,
        "source_count": 1,
        "article_count": 1,
        "confidence_score": 1.0,
        "regions": [],
        "key_facts": [topic]
    }
    
    try:
        # Stage 1: DETECTED
        set_generation_progress(event_id, "DETECTED", 10, "Processing request...")
        
        # Stage 2: AI_WRITING
        set_generation_progress(event_id, "AI_WRITING", 30, "Generating story content...")
        
        # Generate all story components in parallel
        story_data = await synthesizer.generate_full_story_parallel(event)
        
        # Merge story data into event
        event.update(story_data)
        
        set_generation_progress(event_id, "AI_WRITING", 60, "Story generated, saving...")
        
        # Save to database first (before image generation)
        event["created_at"] = datetime.now(timezone.utc).isoformat()
        event["is_custom"] = True
        event["feed_score"] = 0.99
        event["fomo_score"] = 90.0
        event["first_seen_at"] = datetime.now(timezone.utc).isoformat()
        
        await db.news_events.update_one(
            {"id": event_id},
            {"$set": event},
            upsert=True
        )
        
        # Stage 3: IMAGE_GENERATION
        set_generation_progress(event_id, "IMAGE_GENERATION", 70, "Generating cover image...")
        
        # Generate cover image
        generator = CoverImageGenerator(db)
        image_result = await generator.generate_for_event(event)
        
        cover_image = None
        if image_result and image_result.get("status") == "success":
            updated = await db.news_events.find_one({"id": event_id})
            if updated:
                cover_image = updated.get("cover_image_base64")
        
        # Stage 4: READY/PUBLISHED
        set_generation_progress(event_id, "PUBLISHED", 100, "Story published!")
        
        generation_time = round(time.time() - start_time, 2)
        logger.info(f"[GenerateStory] Completed in {generation_time}s for event {event_id}")
        
        # Clear progress after short delay
        asyncio.create_task(clear_progress_delayed(event_id, 30))
        
        return {
            "ok": True,
            "event_id": event_id,
            "headline_en": story_data.get("title_en"),
            "headline_ru": story_data.get("title_ru"),
            "summary_en": story_data.get("summary_en"),
            "summary_ru": story_data.get("summary_ru"),
            "story_en": story_data.get("story_en"),
            "story_ru": story_data.get("story_ru"),
            "ai_view_en": story_data.get("ai_view_en"),
            "ai_view_ru": story_data.get("ai_view_ru"),
            "cover_image": cover_image,
            "assets": assets_list,
            "event_type": event_type,
            "generation_time_seconds": generation_time
        }
        
    except Exception as e:
        logger.error(f"[CustomStory] Error generating story: {e}")
        set_generation_progress(event_id, "ERROR", 0, str(e))
        import traceback
        traceback.print_exc()
        return {
            "ok": False,
            "event_id": event_id,
            "error": str(e)
        }


async def clear_progress_delayed(event_id: str, delay: int = 30):
    """Clear progress after delay."""
    from ..jobs.scheduler import clear_generation_progress
    await asyncio.sleep(delay)
    clear_generation_progress(event_id)


@router.post("/generate-stories-batch")
async def generate_stories_batch(count: int = Query(default=3, le=10)):
    """
    Generate multiple AI stories from current trending topics.
    """
    db = get_db()
    
    # Get top events without stories
    events = await db.news_events.find({
        "status": {"$in": ["confirmed", "developing"]},
        "$or": [
            {"story_en": {"$exists": False}},
            {"story_en": ""}
        ]
    }).sort("feed_score", -1).limit(count).to_list(count)
    
    if not events:
        return {"ok": True, "message": "No events need stories", "generated": 0}
    
    from ..synthesis.story_builder import StorySynthesizer
    from ..synthesis.image_generator import CoverImageGenerator
    
    synthesizer = StorySynthesizer()
    generator = CoverImageGenerator(db)
    
    results = []
    
    for event in events:
        try:
            # Generate headline if missing
            headline = event.get("title_en")
            if not headline:
                headline = await synthesizer.generate_headline(event)
                if not headline:
                    headline = event.get("title_seed", "Crypto News")
            
            # Generate summary if missing
            summary = event.get("summary_en")
            if not summary:
                summary = await synthesizer.generate_summary(event, headline)
                if not summary:
                    summary = headline
            
            # Generate story
            story = await synthesizer.generate_story(event, headline, summary, "", "English")
            
            # Generate AI view
            ai_view = await synthesizer.generate_ai_view(event, headline, summary, "English")
            
            # Generate image
            image_result = await generator.generate_for_event(event)
            
            # Update in database
            await db.news_events.update_one(
                {"id": event["id"]},
                {"$set": {
                    "title_en": headline,
                    "summary_en": summary,
                    "story_en": story or "",
                    "ai_view": ai_view or "",
                    "story_generated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            results.append({
                "event_id": event["id"],
                "headline": headline,
                "has_story": bool(story),
                "has_image": image_result.get("status") == "success" if image_result else False
            })
            
        except Exception as e:
            logger.error(f"[BatchStories] Error for {event.get('id')}: {e}")
            results.append({
                "event_id": event.get("id"),
                "error": str(e)
            })
    
    return {
        "ok": True,
        "generated": len([r for r in results if not r.get("error")]),
        "results": results
    }



# ═══════════════════════════════════════════════════════════════
# CACHE MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/cache/stats")
async def get_cache_stats():
    """Get generation cache statistics."""
    from ..synthesis.story_builder import GenerationCache
    
    db = get_db()
    cache = GenerationCache(db)
    stats = await cache.get_stats()
    
    return {
        "ok": True,
        "cache_stats": stats
    }


@router.delete("/cache/invalidate/{event_id}")
async def invalidate_cache(event_id: str, component: str = Query(default=None)):
    """
    Invalidate cache for a specific event.
    Optionally invalidate only a specific component (headline, summary, story, ai_view).
    """
    from ..synthesis.story_builder import GenerationCache
    
    db = get_db()
    cache = GenerationCache(db)
    await cache.invalidate(event_id, component)
    
    return {
        "ok": True,
        "invalidated": {
            "event_id": event_id,
            "component": component or "all"
        }
    }


@router.get("/cache/event/{event_id}")
async def get_event_cache(event_id: str):
    """Get all cached components for a specific event."""
    from ..synthesis.story_builder import GenerationCache
    
    db = get_db()
    cache = GenerationCache(db)
    cached_data = await cache.get_event_cache(event_id)
    
    return {
        "ok": True,
        "event_id": event_id,
        "cached_components": list(cached_data.keys()),
        "data": cached_data
    }



# ═══════════════════════════════════════════════════════════════
# SENTIMENT & IMPORTANCE SCORING API
# ═══════════════════════════════════════════════════════════════

@router.get("/sentiment/analyze")
async def analyze_sentiment(
    text: str = Query(None, description="Text to analyze"),
    url: str = Query(None, description="URL to fetch and analyze"),
    event_id: str = Query(None, description="Event ID to analyze")
):
    """
    Analyze sentiment of text, URL, or event.
    
    Returns:
    - sentiment: positive/negative/neutral
    - sentiment_score: -1.0 to 1.0
    - summary: Brief summary
    - topics: Key topics
    - confidence: 0.0 to 1.0
    """
    from ..scoring.news_intelligence_engine import get_news_intelligence_engine
    
    db = get_db()
    engine = get_news_intelligence_engine(db)
    
    # Get text from different sources
    analyze_text = text
    
    if event_id:
        event = await db.news_events.find_one({"id": event_id})
        if event:
            analyze_text = event.get("summary_en") or event.get("title_seed") or ""
    
    if url and not analyze_text:
        # TODO: Fetch URL content
        return {"ok": False, "error": "URL fetching not implemented yet"}
    
    if not analyze_text:
        return {"ok": False, "error": "Provide text, url, or event_id"}
    
    result = await engine.sentiment_analyzer.analyze(analyze_text)
    
    return {
        "ok": True,
        **result
    }


@router.get("/importance/calculate")
async def calculate_importance(
    sources: List[str] = Query(None, description="List of source names"),
    source_count: int = Query(1, description="Number of sources"),
    entities: List[str] = Query(None, description="Entities mentioned"),
    sentiment_score: float = Query(0, description="Sentiment score -1 to 1"),
    event_id: str = Query(None, description="Event ID for novelty calculation")
):
    """
    Calculate importance score for an article/event.
    
    Formula:
    score = (0.35 * source_weight) + (0.25 * source_count) + (0.20 * entity_importance) + (0.10 * sentiment_strength) + (0.10 * novelty)
    
    Returns score 0-100 and breakdown.
    """
    from ..scoring.news_intelligence_engine import ImportanceScorer
    
    db = get_db()
    scorer = ImportanceScorer(db)
    
    result = await scorer.calculate_score(
        sources=sources,
        source_count=source_count,
        entities=entities,
        sentiment_score=sentiment_score,
        event_id=event_id
    )
    
    return {
        "ok": True,
        **result
    }


@router.post("/events/{event_id}/analyze")
async def analyze_event(event_id: str):
    """
    Full analysis of an event: sentiment + importance scoring.
    Updates the event with new scores.
    """
    from ..scoring.news_intelligence_engine import get_news_intelligence_engine
    
    db = get_db()
    engine = get_news_intelligence_engine(db)
    
    result = await engine.update_event_scores(event_id)
    
    if not result.get("ok"):
        raise HTTPException(404, result.get("error", "Analysis failed"))
    
    return result


@router.post("/events/batch-analyze")
async def batch_analyze_events(
    limit: int = Query(default=10, le=50, description="Max events to analyze")
):
    """
    Batch analyze events that don't have sentiment/importance scores.
    """
    from ..scoring.news_intelligence_engine import get_news_intelligence_engine
    
    db = get_db()
    engine = get_news_intelligence_engine(db)
    
    # Find events without scores
    events = await db.news_events.find({
        "$or": [
            {"importance_score": {"$exists": False}},
            {"sentiment": {"$exists": False}}
        ]
    }).sort("feed_score", -1).limit(limit).to_list(limit)
    
    results = {
        "total": len(events),
        "analyzed": 0,
        "errors": []
    }
    
    for event in events:
        try:
            await engine.update_event_scores(event["id"])
            results["analyzed"] += 1
        except Exception as e:
            results["errors"].append(f"{event['id']}: {str(e)}")
    
    return {
        "ok": True,
        **results
    }


@router.get("/feed-ranked")
async def get_ranked_feed(
    limit: int = Query(default=20, le=100),
    min_importance: int = Query(default=0, description="Minimum importance score"),
    sentiment: str = Query(None, description="Filter by sentiment: positive/negative/neutral"),
    collapsed: bool = Query(default=False, description="Return collapsed stories instead of individual events")
):
    """
    Get news feed sorted by importance score.
    
    Filters:
    - sentiment: positive, negative, neutral
    - min_importance: 0-100
    - collapsed: if true, returns grouped stories (no duplicates)
    
    Returns events with:
    - importance_score (0-100)
    - sentiment
    - summary
    - topics
    """
    db = get_db()
    
    # If collapsed mode, use Story Engine
    if collapsed:
        from ..clustering.story_engine import get_story_engine
        story_engine = get_story_engine(db)
        stories = await story_engine.get_story_feed(
            limit=limit,
            sentiment=sentiment,
            min_importance=min_importance
        )
        return {
            "ok": True,
            "total": len(stories),
            "collapsed": True,
            "events": stories
        }
    
    query = {}
    
    if min_importance > 0:
        query["importance_score"] = {"$gte": min_importance}
    
    if sentiment:
        query["sentiment"] = sentiment
    
    events_raw = await db.news_events.find(
        query,
        {
            "_id": 0,
            "id": 1,
            "title_en": 1,
            "title_ru": 1,
            "title_seed": 1,
            "headline": 1,
            "summary_en": 1,
            "ai_summary": 1,
            "sentiment": 1,
            "sentiment_score": 1,
            "sentiment_confidence": 1,
            "importance_score": 1,
            "importance_breakdown": 1,
            "confidence_score": 1,
            "confidence_level": 1,
            "rumor_score": 1,
            "rumor_level": 1,
            "key_takeaway": 1,
            "topics": 1,
            "primary_assets": 1,
            "primary_entities": 1,
            "source_count": 1,
            "fomo_score": 1,
            "event_type": 1,
            "status": 1,
            "first_seen_at": 1,
            "cover_image_base64": 1,
            "story_id": 1
        }
    ).sort([("importance_score", -1), ("fomo_score", -1)]).limit(limit).to_list(limit)
    
    # Transform events for frontend
    events = []
    for e in events_raw:
        events.append({
            "id": e.get("id"),
            "headline": e.get("title_en") or e.get("headline") or e.get("title_seed"),
            "summary": e.get("summary_en") or e.get("ai_summary"),
            "sentiment": e.get("sentiment"),
            "sentiment_score": e.get("sentiment_score"),
            "sentiment_confidence": e.get("sentiment_confidence"),
            "importance_score": e.get("importance_score"),
            "importance_breakdown": e.get("importance_breakdown"),
            "confidence_score": e.get("confidence_score"),
            "confidence_level": e.get("confidence_level"),
            "rumor_score": e.get("rumor_score"),
            "rumor_level": e.get("rumor_level"),
            "key_takeaway": e.get("key_takeaway"),
            "topics": e.get("topics", []),
            "assets": e.get("primary_assets", []),
            "entities": e.get("primary_entities", []),
            "source_count": e.get("source_count", 1),
            "fomo_score": e.get("fomo_score"),
            "event_type": e.get("event_type", "news"),
            "status": e.get("status", "pending"),
            "first_seen_at": e.get("first_seen_at"),
            "cover_image": f"data:image/png;base64,{e['cover_image_base64']}" if e.get("cover_image_base64") else None,
            "story_id": e.get("story_id")
        })
    
    return {
        "ok": True,
        "total": len(events),
        "collapsed": False,
        "events": events
    }


# ═══════════════════════════════════════════════════════════════
# SOURCE RELIABILITY ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/sources/weights")
async def get_source_weights():
    """
    Get all source reliability weights.
    Returns list of sources with their weights and tiers.
    """
    from ..scoring.source_reliability import get_source_reliability_manager
    
    db = get_db()
    manager = get_source_reliability_manager(db)
    weights = await manager.get_all_weights()
    
    return {
        "ok": True,
        "total": len(weights),
        "weights": weights
    }


@router.put("/sources/weights/{source_id}")
async def set_source_weight(
    source_id: str,
    weight: float = Query(..., ge=0.0, le=1.0, description="Weight 0.0-1.0"),
    reason: str = Query(None, description="Reason for weight change")
):
    """
    Set custom reliability weight for a source.
    Weight affects importance_score calculation.
    """
    from ..scoring.source_reliability import get_source_reliability_manager
    
    db = get_db()
    manager = get_source_reliability_manager(db)
    result = await manager.set_weight(source_id, weight, reason)
    
    return {
        "ok": True,
        **result
    }


@router.post("/sources/weights/seed")
async def seed_source_weights():
    """
    Seed default source weights to database.
    """
    from ..scoring.source_reliability import get_source_reliability_manager
    
    db = get_db()
    manager = get_source_reliability_manager(db)
    result = await manager.seed_defaults()
    
    return {
        "ok": True,
        **result
    }


# ═══════════════════════════════════════════════════════════════
# STORY ENGINE ENDPOINTS (Duplicate Collapse)
# ═══════════════════════════════════════════════════════════════

@router.get("/stories")
async def get_stories(
    limit: int = Query(default=20, le=100),
    min_sources: int = Query(default=1, description="Minimum number of sources"),
    sentiment: str = Query(None, description="Filter: positive/negative/neutral")
):
    """
    Get collapsed stories (grouped events).
    Each story combines multiple articles about the same event.
    Shows 'Sources: N' instead of duplicate cards.
    """
    from ..clustering.story_engine import get_story_engine
    
    db = get_db()
    engine = get_story_engine(db)
    stories = await engine.get_story_feed(
        limit=limit,
        min_sources=min_sources,
        sentiment=sentiment
    )
    
    return {
        "ok": True,
        "total": len(stories),
        "stories": stories
    }


@router.get("/stories/{story_id}")
async def get_story_detail(story_id: str):
    """
    Get full story detail with all linked articles.
    """
    from ..clustering.story_engine import get_story_engine
    
    db = get_db()
    engine = get_story_engine(db)
    story = await engine.get_story_detail(story_id)
    
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    
    return {
        "ok": True,
        "story": story
    }


@router.post("/stories/collapse")
async def collapse_duplicates(limit: int = Query(default=100, le=500)):
    """
    Manually trigger duplicate collapse.
    Groups similar events into stories.
    """
    from ..clustering.story_engine import get_story_engine
    
    db = get_db()
    engine = get_story_engine(db)
    result = await engine.collapse_existing_events(limit=limit)
    
    return {
        "ok": True,
        **result
    }



# ═══════════════════════════════════════════════════════════════
# CONFIDENCE ENGINE ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/events/{event_id}/confidence")
async def get_event_confidence(event_id: str):
    """
    Calculate confidence score for an event.
    
    Confidence factors:
    - source_quality (40%): Average weight of sources
    - source_count (30%): Number of sources
    - source_diversity (20%): Unique domains
    - time_confirmation (10%): Time since first seen
    
    Levels: LOW (0-40), MEDIUM (40-70), HIGH (70-90), CONFIRMED (90+)
    """
    from ..scoring.confidence_engine import get_confidence_engine
    
    db = get_db()
    engine = get_confidence_engine(db)
    result = await engine.update_event_confidence(event_id)
    
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Event not found"))
    
    return result


@router.post("/confidence/batch-update")
async def batch_update_confidence(limit: int = Query(default=50, le=200)):
    """
    Batch update confidence scores for events without them.
    """
    from ..scoring.confidence_engine import get_confidence_engine
    
    db = get_db()
    engine = get_confidence_engine(db)
    result = await engine.batch_update_confidence(limit=limit)
    
    return {
        "ok": True,
        **result
    }


# ═══════════════════════════════════════════════════════════════
# RUMOR DETECTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/events/{event_id}/rumor-status")
async def get_event_rumor_status(event_id: str):
    """
    Get rumor detection status for an event.
    
    Analyzes text for rumor indicators like:
    - "may", "might", "reportedly", "allegedly"
    - "sources say", "unconfirmed", "rumored"
    
    Levels: CONFIRMED (0-30), SPECULATION (30-60), RUMOR (60-100)
    """
    from ..scoring.rumor_detector import get_rumor_detector
    
    db = get_db()
    detector = get_rumor_detector(db)
    result = await detector.update_event_rumor_status(event_id)
    
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Event not found"))
    
    return result


@router.post("/rumor/analyze-text")
async def analyze_text_for_rumors(text: str = Query(..., min_length=10)):
    """
    Analyze any text for rumor indicators.
    Useful for testing or analyzing external content.
    """
    from ..scoring.rumor_detector import RumorDetector
    
    detector = RumorDetector(None)
    result = detector.analyze_text(text)
    
    return {
        "ok": True,
        **result
    }


@router.post("/rumor/batch-analyze")
async def batch_analyze_rumors(limit: int = Query(default=50, le=200)):
    """
    Batch analyze events for rumor detection.
    """
    from ..scoring.rumor_detector import get_rumor_detector
    
    db = get_db()
    detector = get_rumor_detector(db)
    result = await detector.batch_analyze_rumors(limit=limit)
    
    return {
        "ok": True,
        **result
    }


# ═══════════════════════════════════════════════════════════════
# SENTIMENT TREND ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/sentiment/trend/{asset}")
async def get_asset_sentiment_trend(
    asset: str,
    period: str = Query(default="24h", description="Time period: 1h, 6h, 12h, 24h, 48h, 7d, 30d"),
    interval: str = Query(default="1h", description="Aggregation: 15m, 30m, 1h, 4h, 1d")
):
    """
    Get sentiment trend for a specific asset.
    
    Returns time-series data with:
    - sentiment_score per interval
    - weighted_sentiment (by importance)
    - event_count per interval
    - trend direction (improving/declining/stable)
    """
    from ..analytics.sentiment_trends import get_sentiment_analytics
    
    db = get_db()
    analytics = get_sentiment_analytics(db)
    result = await analytics.get_asset_trend(asset, period, interval)
    
    return {
        "ok": True,
        **result
    }


@router.get("/sentiment/market-trend")
async def get_market_sentiment_trend(
    period: str = Query(default="24h", description="Time period: 1h, 6h, 12h, 24h, 48h, 7d, 30d"),
    interval: str = Query(default="1h", description="Aggregation: 15m, 30m, 1h, 4h, 1d")
):
    """
    Get overall market sentiment trend.
    Aggregates all events regardless of asset.
    """
    from ..analytics.sentiment_trends import get_sentiment_analytics
    
    db = get_db()
    analytics = get_sentiment_analytics(db)
    result = await analytics.get_market_trend(period, interval)
    
    return {
        "ok": True,
        **result
    }


@router.get("/sentiment/top-assets")
async def get_top_assets_sentiment(limit: int = Query(default=10, le=50)):
    """
    Get sentiment summary for top assets by event count.
    """
    from ..analytics.sentiment_trends import get_sentiment_analytics
    
    db = get_db()
    analytics = get_sentiment_analytics(db)
    result = await analytics.get_top_assets_sentiment(limit)
    
    return {
        "ok": True,
        "assets": result,
        "total": len(result)
    }


@router.get("/sentiment/shift-detection")
async def detect_sentiment_shift(
    asset: str = Query(None, description="Specific asset or None for all"),
    threshold: float = Query(default=0.3, ge=0.1, le=1.0, description="Minimum change to detect"),
    window_hours: int = Query(default=6, ge=1, le=48, description="Time window for comparison")
):
    """
    Detect significant sentiment shifts.
    Compares current window to previous window.
    """
    from ..analytics.sentiment_trends import get_sentiment_analytics
    
    db = get_db()
    analytics = get_sentiment_analytics(db)
    result = await analytics.detect_sentiment_shift(asset, threshold, window_hours)
    
    return {
        "ok": True,
        **result
    }


# ═══════════════════════════════════════════════════════════════
# KEY TAKEAWAY ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/events/{event_id}/takeaway")
async def get_event_takeaway(event_id: str):
    """
    Generate key takeaway for an event.
    
    Returns a concise, actionable summary:
    - First sentence: What happened (factual)
    - Second sentence: What it means (implication)
    """
    from ..synthesis.key_takeaway import get_takeaway_generator
    
    db = get_db()
    generator = get_takeaway_generator(db)
    result = await generator.generate(event_id)
    
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Event not found"))
    
    return result


@router.post("/takeaway/batch-generate")
async def batch_generate_takeaways(limit: int = Query(default=50, le=200)):
    """
    Batch generate key takeaways for events without them.
    """
    from ..synthesis.key_takeaway import get_takeaway_generator
    
    db = get_db()
    generator = get_takeaway_generator(db)
    result = await generator.batch_generate(limit=limit)
    
    return {
        "ok": True,
        **result
    }


# ═══════════════════════════════════════════════════════════════
# COMBINED ANALYSIS ENDPOINT
# ═══════════════════════════════════════════════════════════════

@router.post("/events/{event_id}/full-analysis")
async def run_full_event_analysis(event_id: str):
    """
    Run full analysis on an event:
    - Sentiment analysis
    - Importance scoring
    - Confidence calculation
    - Rumor detection
    - Key takeaway generation
    
    Returns all scores in one response.
    """
    from ..scoring.news_intelligence_engine import get_news_intelligence_engine
    from ..scoring.confidence_engine import get_confidence_engine
    from ..scoring.rumor_detector import get_rumor_detector
    from ..synthesis.key_takeaway import get_takeaway_generator
    
    db = get_db()
    
    # Check event exists
    event = await db.news_events.find_one({"id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    results = {}
    
    # 1. Sentiment + Importance
    try:
        engine = get_news_intelligence_engine(db)
        await engine.update_event_scores(event_id)
        results["sentiment_importance"] = "updated"
    except Exception as e:
        results["sentiment_importance_error"] = str(e)
    
    # 2. Confidence
    try:
        conf_engine = get_confidence_engine(db)
        conf_result = await conf_engine.update_event_confidence(event_id)
        results["confidence"] = {
            "score": conf_result.get("confidence_score"),
            "level": conf_result.get("confidence_level")
        }
    except Exception as e:
        results["confidence_error"] = str(e)
    
    # 3. Rumor detection
    try:
        detector = get_rumor_detector(db)
        rumor_result = await detector.update_event_rumor_status(event_id)
        results["rumor"] = {
            "score": rumor_result.get("rumor_score"),
            "level": rumor_result.get("rumor_level"),
            "keywords": rumor_result.get("keywords_detected", [])
        }
    except Exception as e:
        results["rumor_error"] = str(e)
    
    # 4. Key takeaway
    try:
        generator = get_takeaway_generator(db)
        takeaway_result = await generator.generate(event_id)
        results["key_takeaway"] = takeaway_result.get("key_takeaway")
    except Exception as e:
        results["takeaway_error"] = str(e)
    
    # Get updated event
    updated_event = await db.news_events.find_one(
        {"id": event_id},
        {"_id": 0, "sentiment": 1, "sentiment_score": 1, "importance_score": 1,
         "confidence_score": 1, "confidence_level": 1, "rumor_score": 1,
         "rumor_level": 1, "key_takeaway": 1}
    )
    
    return {
        "ok": True,
        "event_id": event_id,
        "analysis": results,
        "event": updated_event
    }


@router.post("/batch/full-analysis")
async def batch_full_analysis(limit: int = Query(default=30, le=100)):
    """
    Run full analysis pipeline on multiple events.
    Processes events without complete analysis.
    """
    from ..scoring.news_intelligence_engine import get_news_intelligence_engine
    from ..scoring.confidence_engine import get_confidence_engine
    from ..scoring.rumor_detector import get_rumor_detector
    from ..synthesis.key_takeaway import get_takeaway_generator
    
    db = get_db()
    
    # Find events needing analysis
    cursor = db.news_events.find({
        "$or": [
            {"confidence_level": {"$exists": False}},
            {"rumor_level": {"$exists": False}},
            {"key_takeaway": {"$exists": False}}
        ]
    }).limit(limit)
    
    events = await cursor.to_list(limit)
    
    results = {
        "processed": 0,
        "errors": []
    }
    
    engine = get_news_intelligence_engine(db)
    conf_engine = get_confidence_engine(db)
    detector = get_rumor_detector(db)
    generator = get_takeaway_generator(db)
    
    for event in events:
        event_id = event["id"]
        try:
            await engine.update_event_scores(event_id)
            await conf_engine.update_event_confidence(event_id)
            await detector.update_event_rumor_status(event_id)
            await generator.generate(event_id)
            results["processed"] += 1
        except Exception as e:
            results["errors"].append(f"{event_id}: {str(e)}")
    
    return {
        "ok": True,
        "found": len(events),
        **results
    }



# ═══════════════════════════════════════════════════════════════
# MULTI-PROVIDER SENTIMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/sentiment/multi-analyze")
async def multi_provider_sentiment_analyze(
    text: str = Query(..., min_length=10, description="Text to analyze"),
    providers: str = Query(None, description="Comma-separated providers: custom,emergent,openai,anthropic")
):
    """
    Analyze sentiment using multiple providers in parallel.
    Returns consensus result and individual provider results.
    
    Providers:
    - custom: Your own sentiment API
    - emergent: Emergent Universal Key (OpenAI/Anthropic/Gemini)
    - openai: Direct OpenAI API
    - anthropic: Direct Anthropic API
    
    Response includes:
    - consensus: weighted average sentiment
    - provider_results: individual results from each provider
    - agreement: how much providers agree (0-1)
    """
    from ..scoring.multi_provider_sentiment import get_multi_provider_sentiment
    
    db = get_db()
    engine = get_multi_provider_sentiment(db)
    
    # Parse providers
    use_providers = None
    if providers:
        use_providers = [p.strip() for p in providers.split(",")]
    
    result = await engine.analyze_with_consensus(text, use_providers)
    
    return {
        "ok": True,
        "text_length": len(text),
        **result
    }


@router.get("/sentiment/providers/active")
async def get_active_sentiment_providers():
    """
    Get list of active sentiment providers with their status.
    """
    from ..scoring.multi_provider_sentiment import get_multi_provider_sentiment
    
    db = get_db()
    engine = get_multi_provider_sentiment(db)
    
    providers = await engine.get_active_providers()
    emergent_key = await engine.get_emergent_key()
    
    result = []
    for p in providers:
        result.append({
            "provider": p.get("provider"),
            "name": p.get("name"),
            "enabled": p.get("enabled", True),
            "has_endpoint": bool(p.get("endpoint_url")),
            "is_default": p.get("is_default", False)
        })
    
    # Add Emergent if available
    if emergent_key:
        result.append({
            "provider": "emergent",
            "name": "Emergent (Universal Key)",
            "enabled": True,
            "has_endpoint": True,
            "is_default": False,
            "note": "Auto-configured from environment"
        })
    
    return {
        "ok": True,
        "total": len(result),
        "providers": result,
        "emergent_available": bool(emergent_key)
    }


@router.post("/sentiment/compare")
async def compare_sentiment_providers(
    text: str = Query(..., min_length=10)
):
    """
    Compare sentiment results from all available providers.
    Useful for testing and calibration.
    """
    from ..scoring.multi_provider_sentiment import get_multi_provider_sentiment
    
    db = get_db()
    engine = get_multi_provider_sentiment(db)
    
    result = await engine.analyze_with_consensus(text)
    
    # Format comparison table
    comparison = []
    for r in result.get("provider_results", []):
        comparison.append({
            "provider": r.get("provider"),
            "sentiment": r.get("sentiment"),
            "score": r.get("sentiment_score"),
            "confidence": r.get("confidence")
        })
    
    return {
        "ok": True,
        "text": text[:100] + "..." if len(text) > 100 else text,
        "consensus": result.get("consensus"),
        "agreement": result.get("agreement"),
        "comparison": comparison
    }
