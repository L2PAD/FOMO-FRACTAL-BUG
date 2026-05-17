"""
System Pipeline Status API
===========================
Real-time pipeline status for UI dashboard.
Aggregates status from all system components.
"""

from fastapi import APIRouter
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["System"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


@router.get("/pipeline-status")
async def get_pipeline_status():
    """
    Get real pipeline status from all components.
    This is the source of truth for UI status display.
    """
    from server import db
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # ═══════════════════════════════════════════════════════════════
    # 1. SCHEDULER STATUS
    # ═══════════════════════════════════════════════════════════════
    scheduler_status = {"running": False, "jobs_active": 0, "jobs_failed": 0}
    try:
        from modules.scheduler.data_sync_scheduler import get_scheduler
        scheduler = get_scheduler(db)
        status = scheduler.get_status()
        
        jobs_success = sum(1 for j in status['jobs'] if j.get('status') == 'success')
        jobs_failed = sum(1 for j in status['jobs'] if j.get('status') == 'error')
        
        scheduler_status = {
            "running": status['running'],
            "jobs_active": status['job_count'],
            "jobs_success": jobs_success,
            "jobs_failed": jobs_failed
        }
    except Exception as e:
        logger.error(f"Scheduler status error: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # 2. PARSER JOBS STATUS
    # ═══════════════════════════════════════════════════════════════
    parsers_status = {"total": 0, "active": 0, "pending": 0, "failed": 0, "jobs": []}
    try:
        from modules.scheduler.data_sync_scheduler import get_scheduler
        scheduler = get_scheduler(db)
        status = scheduler.get_status()
        
        jobs = []
        for job in status['jobs']:
            job_status = job.get('status', 'pending')
            last_run = job.get('last_run')
            
            # Determine actual status
            if job_status == 'success':
                display_status = 'active'
            elif job_status == 'error':
                display_status = 'failed'
            else:
                display_status = 'pending'
            
            jobs.append({
                "id": job['id'],
                "name": job['name'],
                "status": display_status,
                "last_run": last_run,
                "next_run": job.get('next_run'),
                "error": job.get('error')
            })
        
        parsers_status = {
            "total": len(jobs),
            "active": sum(1 for j in jobs if j['status'] == 'active'),
            "pending": sum(1 for j in jobs if j['status'] == 'pending'),
            "failed": sum(1 for j in jobs if j['status'] == 'failed'),
            "jobs": jobs
        }
    except Exception as e:
        logger.error(f"Parser status error: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # 3. NEWS PIPELINE STATUS
    # ═══════════════════════════════════════════════════════════════
    news_status = {
        "sources": 0,
        "articles_today": 0,
        "articles_total": 0,
        "events_detected": 0,
        "stories_generated": 0
    }
    try:
        # Count news sources
        news_sources = await db.news_sources.count_documents({})
        
        # Count articles today
        articles_today = await db.raw_articles.count_documents({
            "created_at": {"$gte": today_start.isoformat()}
        })
        articles_total = await db.raw_articles.count_documents({})
        
        # Count normalized/processed
        normalized = await db.normalized_articles.count_documents({})
        
        # Count news events
        events = await db.news_events.count_documents({})
        
        # Count AI stories
        stories = await db.news_stories.count_documents({})
        
        news_status = {
            "sources": news_sources,
            "articles_today": articles_today,
            "articles_total": articles_total,
            "normalized": normalized,
            "events_detected": events,
            "stories_generated": stories
        }
    except Exception as e:
        logger.error(f"News status error: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # 4. DISCOVERY ENGINE STATUS
    # ═══════════════════════════════════════════════════════════════
    discovery_status = {
        "running": False,
        "last_run": None,
        "next_run": None,
        "endpoints_discovered": 0,
        "providers_registered": 0
    }
    try:
        from modules.scheduler.discovery_scheduler import get_discovery_scheduler
        disc_scheduler = get_discovery_scheduler(db)
        disc_status = disc_scheduler.get_status()
        
        # Count discovered endpoints
        endpoints_count = await db.discovered_endpoints.count_documents({})
        providers_count = await db.providers.count_documents({})
        
        discovery_status = {
            "running": disc_status.get('running', False),
            "last_run": disc_status.get('last_run'),
            "next_run": disc_status.get('next_run'),
            "run_count": disc_status.get('run_count', 0),
            "endpoints_discovered": endpoints_count,
            "providers_registered": providers_count
        }
    except Exception as e:
        logger.error(f"Discovery status error: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # 5. DATA COLLECTIONS STATUS
    # ═══════════════════════════════════════════════════════════════
    collections_status = {}
    try:
        collections = [
            "intel_projects",
            "intel_investors", 
            "intel_persons",
            "intel_exchanges",
            "intel_funding",
            "intel_unlocks",
            "defi_protocols",
            "chain_tvl",
            "market_data",
            "assets"
        ]
        
        for coll in collections:
            count = await db[coll].count_documents({})
            collections_status[coll] = count
    except Exception as e:
        logger.error(f"Collections status error: {e}")
    
    return {
        "ts": ts_now(),
        "scheduler": scheduler_status,
        "parsers": parsers_status,
        "news_pipeline": news_status,
        "discovery": discovery_status,
        "collections": collections_status,
        "health": {
            "scheduler_ok": scheduler_status.get('running', False),
            "parsers_ok": parsers_status.get('active', 0) > 0 or parsers_status.get('pending', 0) > 0,
            "news_ok": news_status.get('articles_total', 0) > 0,
            "discovery_ok": discovery_status.get('running', False)
        }
    }


@router.get("/sources")
async def get_all_sources():
    """
    Get all sources (data + news) unified.
    P0 #5: Combine all 46+ sources into one list.
    """
    from server import db
    
    sources = []
    now = datetime.now(timezone.utc)
    
    # ═══════════════════════════════════════════════════════════════
    # 1. DATA SOURCES (market, funding, etc.)
    # ═══════════════════════════════════════════════════════════════
    try:
        data_sources_cursor = db.data_sources.find({})
        async for source in data_sources_cursor:
            # Calculate real status based on sync history
            last_sync = source.get('last_sync')
            status = 'pending'
            
            if last_sync:
                last_sync_dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00')) if isinstance(last_sync, str) else last_sync
                hours_since = (now - last_sync_dt).total_seconds() / 3600
                
                if hours_since < 1:
                    status = 'active'
                elif hours_since < 24:
                    status = 'stale'
                else:
                    status = 'inactive'
            
            if source.get('status') == 'error':
                status = 'error'
            
            sources.append({
                "id": source.get('id'),
                "name": source.get('name'),
                "type": source.get('source_type', 'market'),
                "tier": source.get('priority', 'medium').upper()[0],  # high -> H, etc.
                "status": status,
                "categories": source.get('categories', []),
                "website": source.get('website'),
                "has_api": source.get('has_api', False),
                "last_sync": last_sync,
                "sync_count": source.get('sync_count', 0)
            })
    except Exception as e:
        logger.error(f"Data sources error: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # 2. NEWS SOURCES
    # ═══════════════════════════════════════════════════════════════
    try:
        news_sources_cursor = db.news_sources.find({})
        async for source in news_sources_cursor:
            last_fetch = source.get('last_fetch')
            status = 'pending'
            
            if last_fetch:
                try:
                    last_fetch_dt = datetime.fromisoformat(last_fetch.replace('Z', '+00:00')) if isinstance(last_fetch, str) else last_fetch
                    hours_since = (now - last_fetch_dt).total_seconds() / 3600
                    
                    if hours_since < 0.5:  # 30 min
                        status = 'active'
                    elif hours_since < 2:
                        status = 'stale'
                    else:
                        status = 'inactive'
                except:
                    pass
            
            if source.get('status') == 'error':
                status = 'error'
            
            # Determine tier based on priority or default
            tier = source.get('tier', 'B')
            if isinstance(tier, str) and len(tier) == 1:
                pass
            elif source.get('priority') == 'high':
                tier = 'A'
            elif source.get('priority') == 'medium':
                tier = 'B'
            else:
                tier = 'C'
            
            sources.append({
                "id": source.get('id'),
                "name": source.get('name'),
                "type": "news",
                "tier": tier,
                "status": status,
                "categories": ["news", source.get('language', 'en')],
                "website": source.get('rss_url') or source.get('url'),
                "has_api": True,  # RSS is an API
                "last_sync": last_fetch,
                "articles_count": source.get('articles_count', 0),
                "language": source.get('language', 'en')
            })
    except Exception as e:
        logger.error(f"News sources error: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # 3. ADD MISSING NEWS SOURCES FROM CONFIG
    # ═══════════════════════════════════════════════════════════════
    try:
        from modules.news_intelligence.ingestion.sources import NEWS_SOURCES
        
        existing_ids = {s['id'] for s in sources if s.get('type') == 'news'}
        
        for ns in NEWS_SOURCES:
            if ns['id'] not in existing_ids:
                sources.append({
                    "id": ns['id'],
                    "name": ns['name'],
                    "type": "news",
                    "tier": ns.get('tier', 'B'),
                    "status": "pending",
                    "categories": ["news", ns.get('language', 'en')],
                    "website": ns.get('rss_url') or ns.get('url'),
                    "has_api": True,
                    "last_sync": None,
                    "language": ns.get('language', 'en')
                })
    except Exception as e:
        logger.error(f"Config news sources error: {e}")
    
    # Sort: active first, then by tier
    tier_order = {'A': 0, 'B': 1, 'C': 2, 'H': 0, 'M': 1, 'L': 2}
    status_order = {'active': 0, 'stale': 1, 'pending': 2, 'inactive': 3, 'error': 4}
    
    sources.sort(key=lambda x: (
        status_order.get(x.get('status', 'pending'), 5),
        tier_order.get(x.get('tier', 'C'), 3),
        x.get('name', '')
    ))
    
    return {
        "ts": ts_now(),
        "total": len(sources),
        "by_type": {
            "news": sum(1 for s in sources if s['type'] == 'news'),
            "market": sum(1 for s in sources if s['type'] == 'market'),
            "funding": sum(1 for s in sources if s['type'] == 'funding'),
            "other": sum(1 for s in sources if s['type'] not in ('news', 'market', 'funding'))
        },
        "by_status": {
            "active": sum(1 for s in sources if s['status'] == 'active'),
            "stale": sum(1 for s in sources if s['status'] == 'stale'),
            "pending": sum(1 for s in sources if s['status'] == 'pending'),
            "inactive": sum(1 for s in sources if s['status'] == 'inactive'),
            "error": sum(1 for s in sources if s['status'] == 'error')
        },
        "sources": sources
    }


@router.post("/parsers/{parser_id}/run")
async def run_parser_now(parser_id: str):
    """Trigger a specific parser to run immediately"""
    from server import db
    from modules.scheduler.data_sync_scheduler import get_scheduler
    
    scheduler = get_scheduler(db)
    scheduler.run_job_now(parser_id)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": f"Parser {parser_id} triggered"
    }
