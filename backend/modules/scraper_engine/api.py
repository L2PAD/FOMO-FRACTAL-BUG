"""
Scraper Engine API Routes
=========================
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime, timezone
import os
import logging

from motor.motor_asyncio import AsyncIOMotorClient
from . import ScraperEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scraper", tags=["Scraper Engine"])

# Database connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

# Service
scraper = ScraperEngine(db)


@router.get("/fetch")
async def fetch_data(
    domain: str = Query(None, description="Target domain"),
    endpoint_id: str = Query(None, description="Specific endpoint ID"),
    capability: str = Query(None, description="Filter by capability"),
    use_cache: bool = Query(True, description="Use cached data")
):
    """
    Fetch data from endpoint registry.
    
    Uses stored blueprints (headers, cookies) to make API requests.
    
    Example: GET /api/scraper/fetch?domain=defillama.com
    """
    if not domain and not endpoint_id:
        raise HTTPException(status_code=400, detail="Must specify domain or endpoint_id")
    
    result = await scraper.scrape(
        domain=domain,
        endpoint_id=endpoint_id,
        capability=capability,
        use_cache=use_cache
    )
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "success": result.success,
        "endpoint_id": result.endpoint_id,
        "domain": result.domain,
        "url": result.url,
        "status_code": result.status_code,
        "data": result.data,
        "records_count": result.records_count,
        "latency_ms": result.latency_ms,
        "error": result.error
    }


@router.get("/fetch/all")
async def fetch_all_active(
    domain: str = Query(None),
    capability: str = Query(None),
    parallel: int = Query(5, ge=1, le=10)
):
    """
    Fetch from all active endpoints.
    
    Returns data from multiple endpoints in parallel.
    """
    results = await scraper.scrape_all_active(
        domain=domain,
        capability=capability,
        parallel=parallel
    )
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(results),
        "success": sum(1 for r in results if r.success),
        "results": [
            {
                "endpoint_id": r.endpoint_id,
                "domain": r.domain,
                "success": r.success,
                "records_count": r.records_count,
                "latency_ms": r.latency_ms,
                "error": r.error
            }
            for r in results
        ]
    }


@router.get("/defi")
async def fetch_defi_data(domain: str = Query("defillama.com")):
    """Fetch DeFi protocol data"""
    result = await scraper.scrape_defi_data(domain)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "success": result.success,
        "data": result.data,
        "records_count": result.records_count,
        "error": result.error
    }


@router.get("/market")
async def fetch_market_data(domain: str = Query("coingecko.com")):
    """Fetch market data"""
    result = await scraper.scrape_market_data(domain)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "success": result.success,
        "data": result.data,
        "records_count": result.records_count,
        "error": result.error
    }


@router.get("/dex")
async def fetch_dex_data(domain: str = Query("dexscreener.com")):
    """Fetch DEX data"""
    result = await scraper.scrape_dex_data(domain)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "success": result.success,
        "data": result.data,
        "records_count": result.records_count,
        "error": result.error
    }


@router.get("/stats")
async def get_scraper_stats():
    """Get scraper statistics"""
    stats = await scraper.get_stats()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }
