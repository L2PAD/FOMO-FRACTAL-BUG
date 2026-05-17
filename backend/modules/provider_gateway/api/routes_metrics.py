"""
Provider Metrics API Routes
===========================

Health monitoring and metrics endpoints:
- /api/providers/metrics - provider performance metrics
- /api/providers/scores - provider scores
- /api/providers/health - health check
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
import os

# DB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

from ..scoring import get_scoring_system, ProviderScoringSystem

router = APIRouter(prefix="/api/providers", tags=["Provider Metrics"])

def get_scoring() -> ProviderScoringSystem:
    return get_scoring_system(db)


# ═══════════════════════════════════════════════════════════════
# PROVIDER METRICS
# ═══════════════════════════════════════════════════════════════

@router.get("/metrics")
async def get_provider_metrics(
    provider_id: Optional[str] = Query(None, description="Filter by provider")
):
    """
    Get provider performance metrics.
    
    Returns:
    - provider_id
    - latency_ms
    - error_rate
    - calls_last_hour
    - success_rate
    - score
    """
    scoring = get_scoring()
    return await scoring.get_metrics(provider_id)


@router.get("/scores")
async def get_all_scores():
    """Get scores for all providers sorted by score"""
    scoring = get_scoring()
    scores = await scoring.get_all_scores()
    
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "providers": scores
    }


@router.get("/scores/{provider_id}")
async def get_provider_score(provider_id: str):
    """Get score for specific provider"""
    scoring = get_scoring()
    score = await scoring.get_score(provider_id)
    
    if not score:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    return score


@router.get("/scores/{provider_id}/history")
async def get_provider_history(
    provider_id: str,
    hours: int = Query(24, ge=1, le=168)
):
    """Get score history for provider"""
    scoring = get_scoring()
    history = await scoring.get_provider_history(provider_id, hours)
    
    return {
        "provider_id": provider_id,
        "hours": hours,
        "history": history
    }


@router.get("/best")
async def get_best_provider(
    providers: str = Query(..., description="Comma-separated provider IDs"),
    min_score: float = Query(0.5, ge=0, le=1)
):
    """Get best provider from list based on current scores"""
    scoring = get_scoring()
    
    provider_list = [p.strip() for p in providers.split(",")]
    best = await scoring.get_best_provider(provider_list, min_score)
    
    return {
        "best_provider": best,
        "from_providers": provider_list,
        "min_score": min_score
    }


@router.get("/stats")
async def get_scoring_stats():
    """Get overall scoring system statistics"""
    scoring = get_scoring()
    return await scoring.get_stats()


# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

@router.get("/health")
async def providers_health():
    """Quick health overview of all providers"""
    scoring = get_scoring()
    scores = await scoring.get_all_scores()
    
    healthy = [s for s in scores if s.get("status") == "healthy"]
    degraded = [s for s in scores if s.get("status") == "degraded"]
    down = [s for s in scores if s.get("status") == "down"]
    
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "total_providers": len(scores),
        "healthy": len(healthy),
        "degraded": len(degraded),
        "down": len(down),
        "providers": {
            "healthy": [s["provider_id"] for s in healthy],
            "degraded": [s["provider_id"] for s in degraded],
            "down": [s["provider_id"] for s in down]
        }
    }


# ═══════════════════════════════════════════════════════════════
# RECORD METRIC (Internal use)
# ═══════════════════════════════════════════════════════════════

@router.post("/record")
async def record_provider_metric(
    provider_id: str,
    success: bool,
    latency_ms: float,
    error: Optional[str] = None,
    endpoint: Optional[str] = None
):
    """Record a request metric for provider (internal use)"""
    scoring = get_scoring()
    
    await scoring.record_request(
        provider_id=provider_id,
        success=success,
        latency_ms=latency_ms,
        error=error,
        endpoint=endpoint
    )
    
    return {"ok": True, "provider_id": provider_id}
