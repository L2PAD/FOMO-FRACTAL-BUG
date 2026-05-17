"""
Discovery Engine API Routes
===========================

Unified discovery API for:
- Browser-based discovery (Playwright)
- Simple HTTP probing
- Endpoint registry
- API Replay
"""

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import os
import logging

from motor.motor_asyncio import AsyncIOMotorClient

from ..models import DiscoveryJobCreate
from ..engine import DiscoveryEngine
from ..browser_engine import BrowserDiscoveryEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/discovery", tags=["Discovery Engine"])

# Database connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

# Services
engine = DiscoveryEngine(db)
browser_engine = BrowserDiscoveryEngine(db)


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════

class BrowserDiscoveryRequest(BaseModel):
    """Request for browser discovery"""
    url: str
    headless: bool = True
    scroll: bool = True
    wait_time: int = 8000
    human_simulation: bool = True


class ReplayRequest(BaseModel):
    """Request for endpoint replay"""
    endpoint_id: str


# ═══════════════════════════════════════════════════════════════
# BROWSER DISCOVERY (MAIN FEATURE)
# ═══════════════════════════════════════════════════════════════

@router.post("/browser")
async def browser_discovery(request: BrowserDiscoveryRequest):
    """
    Full browser-based discovery using Playwright.
    
    This is the MAIN discovery method that:
    1. Opens the site in a headless browser
    2. Captures all XHR/Fetch/GraphQL requests
    3. Extracts hidden API endpoints
    4. Saves endpoint blueprints to registry
    5. Returns results for UI
    
    Example:
        POST /api/discovery/browser
        {"url": "https://defillama.com"}
        
    Response:
        {
            "status": "success",
            "endpoints_found": 6,
            "registered": true,
            "scraper_ready": true,
            "endpoints": [...]
        }
    """
    result = await browser_engine.discover(
        url=request.url,
        headless=request.headless,
        scroll=request.scroll,
        wait_time=request.wait_time,
        human_simulation=request.human_simulation
    )
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/browser/{domain}")
async def browser_discover_domain(
    domain: str, 
    background_tasks: BackgroundTasks,
    sync: bool = Query(False, description="Run synchronously (slower but returns results)")
):
    """
    Browser discovery for domain (can run in background).
    
    Args:
        domain: Target domain (e.g., "defillama.com")
        sync: If True, wait for results. If False, run in background.
        
    Example: POST /api/discovery/browser/defillama.com?sync=true
    """
    url = f"https://{domain}"
    
    if sync:
        # Run synchronously
        result = await browser_engine.discover(url)
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            **result
        }
    else:
        # Run in background
        async def run_discovery():
            try:
                result = await browser_engine.discover(url)
                logger.info(f"Background discovery complete: {domain} - {result.get('endpoints_found', 0)} endpoints")
            except Exception as e:
                logger.error(f"Background discovery failed for {domain}: {e}")
        
        background_tasks.add_task(run_discovery)
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "ok": True,
            "message": f"Browser discovery started for {domain}",
            "status": "running"
        }


# ═══════════════════════════════════════════════════════════════
# DISCOVERY STATUS
# ═══════════════════════════════════════════════════════════════

@router.get("/status/{domain}")
async def get_discovery_status(domain: str):
    """
    Get discovery status for domain.
    
    Returns:
        {
            "domain": "defillama.com",
            "status": "ACTIVE",
            "discovered_endpoints": 6,
            "replay_success": true,
            "parser_ready": true
        }
    
    Status values:
        - ACTIVE: Discovery complete, endpoints working
        - PARTIAL: Discovery complete, some endpoints blocked
        - BLOCKED: Anti-bot protection detected
        - NOT_DISCOVERED: Never discovered
    """
    status = await browser_engine.get_discovery_status(domain)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **status
    }


@router.get("/status")
async def get_all_discovery_status():
    """Get discovery status for all domains"""
    stats = await browser_engine.get_stats()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


# ═══════════════════════════════════════════════════════════════
# ENDPOINT REGISTRY
# ═══════════════════════════════════════════════════════════════

@router.get("/endpoints")
async def list_endpoints(
    domain: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    capability: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500)
):
    """
    List discovered endpoints from registry.
    
    Filters:
        - domain: Filter by domain
        - status: Filter by status (active, blocked, discovered)
        - capability: Filter by capability (market_data, defi_data, etc.)
    """
    # Try browser engine first (new format)
    endpoints = await browser_engine.get_endpoints(domain, status, capability, limit)
    
    # Fallback to old engine
    if not endpoints:
        endpoints = await engine.get_endpoints(domain, status, capability, limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(endpoints),
        "endpoints": endpoints
    }


@router.get("/endpoints/{endpoint_id}")
async def get_endpoint(endpoint_id: str):
    """Get single endpoint by ID"""
    # Try new registry
    endpoint = await db.endpoint_registry.find_one({"id": endpoint_id}, {"_id": 0})
    
    # Fallback to old
    if not endpoint:
        endpoint = await engine.get_endpoint(endpoint_id)
    
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "endpoint": endpoint
    }


# ═══════════════════════════════════════════════════════════════
# API REPLAY
# ═══════════════════════════════════════════════════════════════

@router.post("/replay/{endpoint_id}")
async def replay_endpoint(endpoint_id: str):
    """
    Replay a discovered endpoint to fetch data.
    
    This uses the stored blueprint (headers, cookies) to
    make an API request without browser.
    
    Returns:
        {
            "ok": true,
            "status_code": 200,
            "is_json": true,
            "data": {...},
            "latency_ms": 150
        }
    """
    result = await browser_engine.replay_endpoint(endpoint_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/replay/batch")
async def replay_endpoints_batch(endpoint_ids: List[str]):
    """Replay multiple endpoints"""
    results = []
    for ep_id in endpoint_ids[:10]:  # Max 10 at a time
        result = await browser_engine.replay_endpoint(ep_id)
        results.append({"endpoint_id": ep_id, **result})
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "results": results
    }


# ═══════════════════════════════════════════════════════════════
# RE-DISCOVERY
# ═══════════════════════════════════════════════════════════════

@router.post("/rediscover/{domain}")
async def rediscover_domain(domain: str):
    """
    Force re-discovery for domain.
    
    Deletes old endpoints and runs fresh discovery.
    Use when site changes their API structure.
    """
    result = await browser_engine.rediscover(domain)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


# ═══════════════════════════════════════════════════════════════
# SEED DOMAINS
# ═══════════════════════════════════════════════════════════════

@router.get("/seeds")
async def get_seed_domains():
    """Get list of seed domains by category"""
    seeds = await engine.get_seed_domains()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "seeds": seeds
    }


@router.post("/seeds/{category}/{domain}")
async def discover_seed(category: str, domain: str, background_tasks: BackgroundTasks):
    """Discover specific seed domain"""
    result = await engine.discover_seed_domain(category, domain)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/seeds/all")
async def discover_all_seeds(background_tasks: BackgroundTasks):
    """
    Discover all seed domains.
    
    Runs in background due to long execution time.
    """
    async def run_all():
        results = await engine.discover_all_seeds()
        logger.info(f"Seed discovery complete: {results}")
    
    background_tasks.add_task(run_all)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ok": True,
        "message": "Seed discovery started in background"
    }


# ═══════════════════════════════════════════════════════════════
# SIMPLE DOMAIN DISCOVERY (HTTP Probe)
# ═══════════════════════════════════════════════════════════════

@router.post("/domain/{domain}")
async def discover_domain(domain: str):
    """
    Simple HTTP-based discovery for domain.
    
    Uses known API mappings and common endpoint probing.
    Faster but less comprehensive than browser discovery.
    
    Example: POST /api/discovery/domain/defillama.com
    """
    results = await engine.discover_domain(domain)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **results
    }


# ═══════════════════════════════════════════════════════════════
# DISCOVERY JOBS
# ═══════════════════════════════════════════════════════════════

@router.post("/jobs")
async def create_discovery_job(data: DiscoveryJobCreate):
    """Create new discovery job for domain"""
    result = await engine.create_job(data)
    return result


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get discovery job status"""
    job = await engine.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "job": job
    }


@router.post("/jobs/{job_id}/run")
async def run_job(job_id: str):
    """Execute discovery job"""
    result = await engine.run_job(job_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


# ═══════════════════════════════════════════════════════════════
# PROVIDER REGISTRATION
# ═══════════════════════════════════════════════════════════════

@router.post("/endpoints/{endpoint_id}/register")
async def register_as_provider(endpoint_id: str, provider_name: str = Query(...)):
    """
    Register discovered endpoint as provider.
    
    This creates a provider entry in Provider Gateway,
    enabling automatic data sync via scheduler.
    
    Example: POST /api/discovery/endpoints/abc123/register?provider_name=DefiLlama_TVL
    """
    result = await engine.register_discovered_provider(endpoint_id, provider_name)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


# ═══════════════════════════════════════════════════════════════
# ENDPOINT VALIDATION
# ═══════════════════════════════════════════════════════════════

@router.post("/endpoints/validate")
async def validate_endpoints(domain: Optional[str] = None):
    """Validate discovered endpoints"""
    result = await engine.validate_endpoints(domain)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


# ═══════════════════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_discovery_stats():
    """Get discovery statistics"""
    browser_stats = await browser_engine.get_stats()
    old_stats = await engine.get_stats()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "registry": browser_stats,
        "legacy": old_stats
    }


# ═══════════════════════════════════════════════════════════════
# DATA SOURCES (from Data Sources Registry)
# ═══════════════════════════════════════════════════════════════

@router.get("/sources")
async def get_data_sources():
    """Get all registered data sources"""
    sources = []
    cursor = db.data_sources.find({}, {"_id": 0}).sort("priority", 1)
    async for source in cursor:
        sources.append(source)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(sources),
        "sources": sources
    }


@router.get("/sources/{source_id}")
async def get_data_source(source_id: str):
    """Get single data source"""
    source = await db.data_sources.find_one({"id": source_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source": source
    }


@router.post("/sources/health-check")
async def run_sources_health_check(background_tasks: BackgroundTasks):
    """
    Run health check for all data sources.
    Проверяет реальную работоспособность каждого источника.
    """
    from ..health_check import run_health_check
    
    try:
        result = await run_health_check(db)
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "status": "completed",
            **result
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sources/{source_id}/check")
async def check_single_source(source_id: str):
    """Check health of a single data source"""
    from ..health_check import DataSourceHealthChecker
    
    checker = DataSourceHealthChecker(db)
    try:
        result = await checker.check_single_source(source_id)
        
        # Update status in database
        status_map = {
            "active": "active",
            "needs_key": "degraded",
            "rate_limited": "degraded",
            "timeout": "timeout",
            "offline": "offline",
            "error": "error"
        }
        db_status = status_map.get(result["status"], "unknown")
        
        await db.data_sources.update_one(
            {"id": source_id},
            {"$set": {
                "status": db_status,
                "last_check": result,
                "last_checked_at": result["checked_at"]
            }}
        )
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            **result
        }
    finally:
        await checker.close()


# ═══════════════════════════════════════════════════════════════
# DRIFT DETECTION
# ═══════════════════════════════════════════════════════════════

@router.get("/drift/check/{endpoint_id}")
async def check_endpoint_drift(endpoint_id: str):
    """
    Check single endpoint for drift.
    
    Detects:
    - Schema drift (field changes)
    - Status drift (errors)
    - Performance drift (latency)
    - Data drift (quality issues)
    """
    from ..drift_detector import DriftDetector
    detector = DriftDetector(db)
    
    drift = await detector.check_drift(endpoint_id)
    
    if drift:
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "drift_detected": True,
            "drift": {
                "type": drift.drift_type,
                "severity": drift.severity,
                "details": drift.details,
                "detected_at": drift.detected_at
            }
        }
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "drift_detected": False
    }


@router.get("/drift/domain/{domain}")
async def check_domain_drift(domain: str):
    """Check all endpoints in domain for drift"""
    from ..drift_detector import DriftDetector
    detector = DriftDetector(db)
    
    drifts = await detector.check_domain_drift(domain)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "domain": domain,
        "drifts_found": len(drifts),
        "drifts": [
            {"type": d.drift_type, "severity": d.severity, "endpoint_id": d.endpoint_id}
            for d in drifts
        ]
    }


@router.post("/drift/check-all")
async def check_all_drift(limit: int = Query(30, ge=1, le=100)):
    """Check all active endpoints for drift"""
    from ..drift_detector import DriftDetector
    detector = DriftDetector(db)
    
    drifts = await detector.check_all_drift(limit=limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total_checked": limit,
        "drifts_found": len(drifts),
        "drifts": [
            {"domain": d.domain, "type": d.drift_type, "severity": d.severity, "endpoint_id": d.endpoint_id}
            for d in drifts
        ]
    }


@router.get("/drift/stats")
async def get_drift_stats():
    """Get drift detection statistics"""
    from ..drift_detector import DriftDetector
    detector = DriftDetector(db)
    
    stats = await detector.get_drift_stats()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


# ═══════════════════════════════════════════════════════════════
# SCORING ENGINE
# ═══════════════════════════════════════════════════════════════

# Static routes MUST come before parameterized routes

@router.get("/score/best")
async def get_best_endpoint(
    domain: str = Query(None),
    capability: str = Query(None),
    min_score: float = Query(50, ge=0, le=100)
):
    """
    Get best endpoint for given criteria.
    
    Returns the highest-scored endpoint matching filters.
    """
    from ..scoring_engine import DiscoveryScoringEngine
    scorer = DiscoveryScoringEngine(db)
    
    endpoint = await scorer.get_best_endpoint(domain, capability, min_score)
    
    if not endpoint:
        raise HTTPException(status_code=404, detail="No matching endpoint found")
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "endpoint": endpoint
    }


@router.get("/score/ranked")
async def get_ranked_endpoints(
    domain: str = Query(None),
    capability: str = Query(None),
    limit: int = Query(10, ge=1, le=50)
):
    """Get endpoints ranked by score"""
    from ..scoring_engine import DiscoveryScoringEngine
    scorer = DiscoveryScoringEngine(db)
    
    endpoints = await scorer.get_ranked_endpoints(domain, capability, limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(endpoints),
        "endpoints": endpoints
    }


@router.get("/score/stats")
async def get_scoring_stats():
    """Get scoring statistics"""
    from ..scoring_engine import DiscoveryScoringEngine
    scorer = DiscoveryScoringEngine(db)
    
    stats = await scorer.get_scoring_stats()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


@router.post("/score/domain/{domain}")
async def score_domain_endpoints(domain: str):
    """Calculate scores for all endpoints in domain"""
    from ..scoring_engine import DiscoveryScoringEngine
    scorer = DiscoveryScoringEngine(db)
    
    scores = await scorer.calculate_domain_scores(domain)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "domain": domain,
        "endpoints_scored": len(scores),
        "scores": [s.to_dict() for s in scores]
    }


@router.post("/score/all")
async def score_all_endpoints(limit: int = Query(100, ge=1, le=500)):
    """Calculate scores for all active endpoints"""
    from ..scoring_engine import DiscoveryScoringEngine
    scorer = DiscoveryScoringEngine(db)
    
    scores = await scorer.calculate_all_scores(limit=limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "endpoints_scored": len(scores),
        "top_10": [s.to_dict() for s in scores[:10]]
    }


# Parameterized route MUST come AFTER static routes
@router.get("/score/{endpoint_id}")
async def get_endpoint_score(endpoint_id: str, recalculate: bool = Query(False)):
    """
    Get endpoint score.
    
    Scores are based on:
    - Reliability (success rate)
    - Performance (latency)
    - Data quality (completeness)
    - Coverage (capabilities)
    - Freshness (last verified)
    """
    from ..scoring_engine import DiscoveryScoringEngine
    scorer = DiscoveryScoringEngine(db)
    
    if recalculate:
        score = await scorer.calculate_score(endpoint_id)
        if not score:
            raise HTTPException(status_code=404, detail="Endpoint not found")
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            **score.to_dict()
        }
    
    # Get cached score
    endpoint = await db.endpoint_registry.find_one({"id": endpoint_id}, {"_id": 0, "score": 1, "score_breakdown": 1})
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "endpoint_id": endpoint_id,
        "total_score": endpoint.get("score"),
        "scores": endpoint.get("score_breakdown")
    }


# ═══════════════════════════════════════════════════════════════
# SELF-LEARNING SCHEDULER
# ═══════════════════════════════════════════════════════════════

@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get self-learning scheduler status"""
    from modules.scheduler.self_learning_scheduler import get_self_learning_scheduler
    scheduler = get_self_learning_scheduler(db)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **scheduler.get_status()
    }


@router.get("/scheduler/stats")
async def get_scheduler_comprehensive_stats():
    """Get comprehensive scheduler statistics including drift and scoring"""
    from modules.scheduler.self_learning_scheduler import get_self_learning_scheduler
    scheduler = get_self_learning_scheduler(db)
    
    stats = await scheduler.get_comprehensive_stats()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


@router.post("/scheduler/trigger/discovery")
async def trigger_discovery(domain: str = Query(None)):
    """Manually trigger discovery"""
    from modules.scheduler.self_learning_scheduler import get_self_learning_scheduler
    scheduler = get_self_learning_scheduler(db)
    
    result = await scheduler.trigger_discovery(domain)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/scheduler/trigger/drift-check")
async def trigger_drift_check(domain: str = Query(None)):
    """Manually trigger drift check"""
    from modules.scheduler.self_learning_scheduler import get_self_learning_scheduler
    scheduler = get_self_learning_scheduler(db)
    
    result = await scheduler.trigger_drift_check(domain)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/scheduler/trigger/scoring")
async def trigger_scoring(domain: str = Query(None)):
    """Manually trigger scoring"""
    from modules.scheduler.self_learning_scheduler import get_self_learning_scheduler
    scheduler = get_self_learning_scheduler(db)
    
    result = await scheduler.trigger_scoring(domain)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/scheduler/seed")
async def add_seed_domain(category: str = Query(...), domain: str = Query(...)):
    """Add new seed domain and trigger discovery"""
    from modules.scheduler.self_learning_scheduler import get_self_learning_scheduler
    scheduler = get_self_learning_scheduler(db)
    
    result = await scheduler.add_seed_domain(category, domain)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


# ═══════════════════════════════════════════════════════════════
# DISCOVERY DASHBOARD (AGGREGATED DATA FOR UI)
# ═══════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def get_discovery_dashboard():
    """
    Aggregated discovery dashboard data.
    
    Single endpoint for UI dashboard with:
    - Scheduler status & jobs
    - Source health metrics
    - Top scored endpoints
    - Recent drift alerts
    - Endpoint coverage by category
    - Discovery activity log
    """
    from modules.scheduler.self_learning_scheduler import get_self_learning_scheduler
    from ..drift_detector import DriftDetector
    from ..scoring_engine import DiscoveryScoringEngine
    
    scheduler = get_self_learning_scheduler(db)
    drift_detector = DriftDetector(db)
    scoring_engine = DiscoveryScoringEngine(db)
    
    # 1. Scheduler status
    scheduler_status = scheduler.get_status()
    
    # 2. Source health
    total_sources = await db.data_sources.count_documents({})
    active_sources = await db.data_sources.count_documents({"status": "active"})
    degraded_sources = await db.data_sources.count_documents({"status": {"$in": ["degraded", "partial"]}})
    paused_sources = await db.data_sources.count_documents({"status": "paused"})
    
    # 3. Endpoint stats
    total_endpoints = await db.endpoint_registry.count_documents({})
    active_endpoints = await db.endpoint_registry.count_documents({"status": "active"})
    scored_endpoints = await db.endpoint_registry.count_documents({"score": {"$exists": True}})
    
    # 4. Top endpoints (by score)
    top_endpoints = []
    cursor = db.endpoint_registry.find(
        {"status": "active", "score": {"$exists": True}},
        {"_id": 0, "id": 1, "domain": 1, "path": 1, "score": 1, "score_breakdown": 1, 
         "capabilities": 1, "latency_ms": 1, "replay_success": 1}
    ).sort("score", -1).limit(10)
    async for ep in cursor:
        top_endpoints.append({
            "id": ep.get("id"),
            "domain": ep.get("domain"),
            "path": ep.get("path", "/"),
            "score": round(ep.get("score", 0), 1),
            "reliability": ep.get("score_breakdown", {}).get("reliability", 0),
            "performance": ep.get("score_breakdown", {}).get("performance", 0),
            "latency_ms": round(ep.get("latency_ms", 0), 0),
            "capabilities": ep.get("capabilities", [])[:3],
            "replay_ok": ep.get("replay_success", False)
        })
    
    # 5. Recent drift alerts
    drift_alerts = []
    cursor = db.drift_logs.find(
        {},
        {"_id": 0}
    ).sort("detected_at", -1).limit(10)
    async for drift in cursor:
        drift_alerts.append({
            "domain": drift.get("domain"),
            "type": drift.get("drift_type"),
            "severity": drift.get("severity"),
            "details": drift.get("details", {}),
            "detected_at": drift.get("detected_at")
        })
    
    # 6. Endpoint coverage by capability
    coverage_pipeline = [
        {"$unwind": "$capabilities"},
        {"$group": {"_id": "$capabilities", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    coverage = {}
    async for doc in db.endpoint_registry.aggregate(coverage_pipeline):
        coverage[doc["_id"]] = doc["count"]
    
    # 7. Discovery activity (from logs)
    activity = []
    cursor = db.discovery_logs.find(
        {},
        {"_id": 0, "domain": 1, "timestamp": 1, "endpoints_found": 1, "status": 1, "type": 1}
    ).sort("timestamp", -1).limit(20)
    async for log in cursor:
        activity.append({
            "domain": log.get("domain", "system"),
            "type": log.get("type", "discovery"),
            "endpoints_found": log.get("endpoints_found", 0),
            "status": log.get("status", "completed"),
            "timestamp": log.get("timestamp")
        })
    
    # 8. Drift stats summary
    drift_by_severity = {}
    severity_pipeline = [
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
    ]
    async for doc in db.drift_logs.aggregate(severity_pipeline):
        drift_by_severity[doc["_id"]] = doc["count"]
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "scheduler": {
            "running": scheduler_status.get("running", False),
            "jobs": [
                {
                    "id": job.get("id"),
                    "name": job.get("name"),
                    "next_run": job.get("next_run"),
                    "status": "active" if job.get("next_run") else "stopped"
                }
                for job in scheduler_status.get("jobs", [])
            ],
            "stats": scheduler_status.get("stats", {})
        },
        "sources": {
            "total": total_sources,
            "active": active_sources,
            "degraded": degraded_sources,
            "paused": paused_sources
        },
        "endpoints": {
            "total": total_endpoints,
            "active": active_endpoints,
            "scored": scored_endpoints
        },
        "top_endpoints": top_endpoints,
        "drift_alerts": drift_alerts,
        "drift_summary": drift_by_severity,
        "coverage": coverage,
        "activity": activity
    }

