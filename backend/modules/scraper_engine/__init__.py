"""
Scraper Engine
==============

Uses endpoint registry to fetch data without browser.
Supports automatic endpoint selection, retry, and failover.

Pipeline:
    endpoint_registry
    ↓
    scraper_engine
    ↓
    fetch data
    ↓
    parser layer
    ↓
    database
"""

import asyncio
import logging
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Result of a scrape operation"""
    endpoint_id: str
    domain: str
    url: str
    success: bool
    status_code: int = 0
    data: Any = None
    error: Optional[str] = None
    latency_ms: float = 0
    records_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ScraperEngine:
    """
    Scraper Engine that uses endpoint registry for data fetching.
    
    Features:
    - Automatic endpoint selection (best score)
    - Cookie/header replay
    - Retry with backoff
    - Failover to alternative endpoints
    - Result caching
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.endpoints = db.endpoint_registry
        self.scrape_logs = db.scrape_logs
        self.cache = db.scrape_cache
        
    async def scrape(
        self,
        domain: str = None,
        endpoint_id: str = None,
        capability: str = None,
        use_cache: bool = True,
        cache_ttl: int = 300  # 5 minutes
    ) -> ScrapeResult:
        """
        Scrape data using registered endpoint.
        
        Args:
            domain: Target domain (selects best endpoint)
            endpoint_id: Specific endpoint ID
            capability: Filter by capability
            use_cache: Use cached data if available
            cache_ttl: Cache time-to-live in seconds
            
        Returns:
            ScrapeResult with data or error
        """
        # Find endpoint
        if endpoint_id:
            endpoint = await self.endpoints.find_one({"id": endpoint_id}, {"_id": 0})
        elif domain:
            # Find best active endpoint for domain
            endpoint = await self._find_best_endpoint(domain, capability)
        else:
            return ScrapeResult(
                endpoint_id="",
                domain="",
                url="",
                success=False,
                error="Must specify domain or endpoint_id"
            )
        
        if not endpoint:
            return ScrapeResult(
                endpoint_id=endpoint_id or "",
                domain=domain or "",
                url="",
                success=False,
                error="No endpoint found"
            )
        
        # Check cache
        if use_cache:
            cached = await self._get_cache(endpoint["id"])
            if cached:
                logger.debug(f"[Scraper] Cache hit for {endpoint['id']}")
                return ScrapeResult(
                    endpoint_id=endpoint["id"],
                    domain=endpoint["domain"],
                    url=endpoint["url"],
                    success=True,
                    data=cached["data"],
                    records_count=cached.get("records_count", 0),
                    timestamp=cached["timestamp"]
                )
        
        # Fetch data
        result = await self._fetch_endpoint(endpoint)
        
        # Cache successful results
        if result.success and use_cache:
            await self._set_cache(endpoint["id"], result, cache_ttl)
        
        # Log scrape
        await self._log_scrape(result)
        
        # Update endpoint stats
        await self._update_endpoint_stats(endpoint["id"], result.success)
        
        return result
    
    async def scrape_all_active(
        self,
        domain: str = None,
        capability: str = None,
        parallel: int = 5
    ) -> List[ScrapeResult]:
        """
        Scrape all active endpoints for domain/capability.
        
        Args:
            domain: Filter by domain
            capability: Filter by capability
            parallel: Max parallel requests
            
        Returns:
            List of ScrapeResults
        """
        # Find active endpoints
        query = {"status": "active"}
        if domain:
            query["domain"] = domain
        if capability:
            query["capabilities"] = capability
        
        endpoints = []
        cursor = self.endpoints.find(query, {"_id": 0}).limit(50)
        async for ep in cursor:
            endpoints.append(ep)
        
        if not endpoints:
            return []
        
        # Scrape in parallel
        semaphore = asyncio.Semaphore(parallel)
        
        async def scrape_one(ep):
            async with semaphore:
                return await self._fetch_endpoint(ep)
        
        results = await asyncio.gather(*[scrape_one(ep) for ep in endpoints])
        
        return list(results)
    
    async def _find_best_endpoint(
        self, 
        domain: str, 
        capability: str = None
    ) -> Optional[Dict]:
        """Find best endpoint for domain"""
        query = {"domain": domain, "status": "active", "replay_success": True}
        if capability:
            query["capabilities"] = capability
        
        # Sort by latency (lower is better)
        endpoint = await self.endpoints.find_one(
            query, 
            {"_id": 0},
            sort=[("latency_ms", 1)]
        )
        
        return endpoint
    
    async def _fetch_endpoint(self, endpoint: Dict) -> ScrapeResult:
        """Fetch data from endpoint"""
        try:
            headers = endpoint.get("headers", {})
            cookies = endpoint.get("cookies", {})
            
            # Add cookies to headers
            if cookies:
                cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
                headers["Cookie"] = cookie_str
            
            async with httpx.AsyncClient(
                timeout=30, 
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ScraperEngine/1.0)"}
            ) as client:
                
                if endpoint.get("method", "GET") == "GET":
                    response = await client.get(endpoint["url"], headers=headers)
                else:
                    response = await client.post(
                        endpoint["url"],
                        headers=headers,
                        content=endpoint.get("body")
                    )
                
                latency = response.elapsed.total_seconds() * 1000 if response.elapsed else 0
                
                if response.status_code != 200:
                    return ScrapeResult(
                        endpoint_id=endpoint["id"],
                        domain=endpoint["domain"],
                        url=endpoint["url"],
                        success=False,
                        status_code=response.status_code,
                        error=f"HTTP {response.status_code}",
                        latency_ms=latency
                    )
                
                # Parse response
                content_type = response.headers.get("content-type", "")
                is_json = "json" in content_type
                
                if not is_json:
                    return ScrapeResult(
                        endpoint_id=endpoint["id"],
                        domain=endpoint["domain"],
                        url=endpoint["url"],
                        success=False,
                        status_code=response.status_code,
                        error="Not JSON response",
                        latency_ms=latency
                    )
                
                data = response.json()
                
                # Count records
                records_count = 0
                if isinstance(data, list):
                    records_count = len(data)
                elif isinstance(data, dict):
                    # Check common data wrappers
                    for key in ['data', 'result', 'results', 'items', 'records']:
                        if key in data and isinstance(data[key], list):
                            records_count = len(data[key])
                            break
                
                return ScrapeResult(
                    endpoint_id=endpoint["id"],
                    domain=endpoint["domain"],
                    url=endpoint["url"],
                    success=True,
                    status_code=response.status_code,
                    data=data,
                    latency_ms=latency,
                    records_count=records_count
                )
                
        except httpx.TimeoutException:
            return ScrapeResult(
                endpoint_id=endpoint["id"],
                domain=endpoint["domain"],
                url=endpoint["url"],
                success=False,
                error="Timeout"
            )
        except Exception as e:
            return ScrapeResult(
                endpoint_id=endpoint["id"],
                domain=endpoint["domain"],
                url=endpoint["url"],
                success=False,
                error=str(e)
            )
    
    async def _get_cache(self, endpoint_id: str) -> Optional[Dict]:
        """Get cached scrape result"""
        now = datetime.now(timezone.utc)
        
        cached = await self.cache.find_one({
            "endpoint_id": endpoint_id,
            "expires_at": {"$gt": now.isoformat()}
        }, {"_id": 0})
        
        return cached
    
    async def _set_cache(self, endpoint_id: str, result: ScrapeResult, ttl: int):
        """Cache scrape result"""
        now = datetime.now(timezone.utc)
        expires = datetime.fromtimestamp(now.timestamp() + ttl, tz=timezone.utc)
        
        doc = {
            "endpoint_id": endpoint_id,
            "data": result.data,
            "records_count": result.records_count,
            "timestamp": result.timestamp,
            "expires_at": expires.isoformat()
        }
        
        await self.cache.update_one(
            {"endpoint_id": endpoint_id},
            {"$set": doc},
            upsert=True
        )
    
    async def _log_scrape(self, result: ScrapeResult):
        """Log scrape result"""
        log = asdict(result)
        log.pop("data", None)  # Don't log full data
        
        await self.scrape_logs.insert_one(log)
    
    async def _update_endpoint_stats(self, endpoint_id: str, success: bool):
        """Update endpoint success rate"""
        update = {
            "$set": {
                "last_scraped": datetime.now(timezone.utc).isoformat()
            },
            "$inc": {
                "scrape_count": 1,
                "success_count": 1 if success else 0
            }
        }
        
        await self.endpoints.update_one({"id": endpoint_id}, update)
    
    # ═══════════════════════════════════════════════════════════════
    # DOMAIN-SPECIFIC SCRAPERS
    # ═══════════════════════════════════════════════════════════════
    
    async def scrape_defi_data(self, domain: str = "defillama.com") -> ScrapeResult:
        """Scrape DeFi protocol data"""
        return await self.scrape(domain=domain, capability="defi_data")
    
    async def scrape_market_data(self, domain: str = "coingecko.com") -> ScrapeResult:
        """Scrape market data"""
        return await self.scrape(domain=domain, capability="market_data")
    
    async def scrape_dex_data(self, domain: str = "dexscreener.com") -> ScrapeResult:
        """Scrape DEX/trading data"""
        return await self.scrape(domain=domain, capability="dex_data")
    
    async def scrape_funding_data(self, domain: str = "cryptorank.io") -> ScrapeResult:
        """Scrape VC/funding data"""
        return await self.scrape(domain=domain, capability="funding")
    
    # ═══════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_stats(self) -> Dict:
        """Get scraper statistics"""
        # Total scrapes
        total = await self.scrape_logs.count_documents({})
        
        # Success rate
        success = await self.scrape_logs.count_documents({"success": True})
        success_rate = (success / total * 100) if total > 0 else 0
        
        # By domain
        domain_pipeline = [
            {"$group": {"_id": "$domain", "count": {"$sum": 1}, 
                       "success": {"$sum": {"$cond": ["$success", 1, 0]}}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        domains = []
        async for doc in self.scrape_logs.aggregate(domain_pipeline):
            rate = (doc["success"] / doc["count"] * 100) if doc["count"] > 0 else 0
            domains.append({
                "domain": doc["_id"],
                "scrapes": doc["count"],
                "success_rate": round(rate, 1)
            })
        
        # Recent errors
        recent_errors = []
        cursor = self.scrape_logs.find(
            {"success": False, "error": {"$exists": True}},
            {"_id": 0, "domain": 1, "error": 1, "timestamp": 1}
        ).sort("timestamp", -1).limit(10)
        async for doc in cursor:
            recent_errors.append(doc)
        
        return {
            "total_scrapes": total,
            "success_count": success,
            "success_rate": round(success_rate, 1),
            "domains": domains,
            "recent_errors": recent_errors
        }
