"""
Data Sources Health Check Service
=================================

Проверяет реальную работоспособность каждого источника данных.
Обновляет статусы в Discovery на основе реальных проверок.
"""

import asyncio
import httpx
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


# Health check configurations for each data source
# Updated with working public API endpoints
HEALTH_CHECKS = {
    # ═══════════════════════════════════════════════════════════════
    # MARKET DATA
    # ═══════════════════════════════════════════════════════════════
    "coingecko": {
        "url": "https://api.coingecko.com/api/v3/ping",
        "method": "GET",
        "expected_status": [200, 429],  # 429 = rate limited (free tier)
        "timeout": 10,
        "requires_key": True,
        "note": "Free tier has strict rate limits, API key recommended",
    },
    "coinmarketcap": {
        "url": "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
        "method": "GET",
        "expected_status": [200, 401, 1002],
        "timeout": 10,
        "requires_key": True,
        "note": "Requires API key from coinmarketcap.com/api",
    },
    "messari": {
        "url": "https://data.messari.io/api/v1/assets",
        "method": "GET",
        "expected_status": [200, 401, 429],
        "timeout": 10,
        "requires_key": True,
        "note": "Requires API key from messari.io/api",
    },
    
    # ═══════════════════════════════════════════════════════════════
    # DEFI - FREE PUBLIC APIs
    # ═══════════════════════════════════════════════════════════════
    "defillama": {
        "url": "https://api.llama.fi/protocols",
        "method": "GET",
        "expected_status": 200,
        "timeout": 15,
        "requires_key": False,
        "note": "Free public API, no key required",
    },
    "tokenterminal": {
        "url": "https://api.tokenterminal.com/v2/projects",
        "method": "GET",
        "expected_status": [200, 401, 403],
        "timeout": 10,
        "requires_key": False,
        "note": "Public endpoints available, premium for full access",
    },
    
    # ═══════════════════════════════════════════════════════════════
    # DEX - FREE PUBLIC APIs
    # ═══════════════════════════════════════════════════════════════
    "dexscreener": {
        "url": "https://api.dexscreener.com/latest/dex/search?q=eth",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "note": "Free public API, no key required",
    },
    "geckoterminal": {
        "url": "https://api.geckoterminal.com/api/v2/networks/eth/trending_pools",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "note": "Free public API, no key required",
    },
    "dextools": {
        "url": "https://public-api.dextools.io/trial/v2/token/ether/0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2/info",
        "method": "GET",
        "expected_status": [200, 401, 403, 429],
        "timeout": 10,
        "requires_key": False,
        "note": "Trial endpoint available, may have rate limits",
    },
    "defined": {
        "url": "https://api.defined.fi/",
        "method": "GET",
        "expected_status": [200, 401, 404],
        "timeout": 10,
        "requires_key": False,
        "note": "GraphQL API, may need query",
    },
    
    # ═══════════════════════════════════════════════════════════════
    # INTEL / FUNDING - PARSING + PUBLIC APIs
    # ═══════════════════════════════════════════════════════════════
    "cryptorank": {
        "url": "https://api.cryptorank.io/v1/currencies",
        "method": "GET",
        "expected_status": [200, 401, 403],
        "timeout": 10,
        "requires_key": False,
        "note": "Basic endpoints free, premium for full access",
    },
    "dropstab": {
        "url": "https://dropstab.com/api/v1/activities",
        "method": "GET",
        "expected_status": [200, 403, 404],
        "timeout": 10,
        "requires_key": False,
        "note": "Web parsing available as fallback",
    },
    "rootdata": {
        "url": "https://api.rootdata.com/open/ser_inv",
        "method": "GET",
        "expected_status": [200, 401, 403],
        "timeout": 10,
        "requires_key": False,
        "note": "Public API available with limits",
    },
    "crunchbase": {
        "url": "https://www.crunchbase.com/",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "type": "html",
        "note": "Web parsing, no public API",
    },
    
    # ═══════════════════════════════════════════════════════════════
    # TOKEN UNLOCKS - PUBLIC APIs
    # ═══════════════════════════════════════════════════════════════
    "tokenunlocks": {
        "url": "https://token.unlocks.app/api/v2/token",
        "method": "GET",
        "expected_status": [200, 401, 403, 404],
        "timeout": 10,
        "requires_key": False,
        "note": "Public endpoints available",
    },
    "vestlab": {
        "url": "https://vestlab.io/api/v1/vesting",
        "method": "GET",
        "expected_status": [200, 401, 404],
        "timeout": 10,
        "requires_key": False,
        "note": "Public API for vesting data",
    },
    
    # ═══════════════════════════════════════════════════════════════
    # DERIVATIVES - PUBLIC APIs
    # ═══════════════════════════════════════════════════════════════
    "coinglass": {
        "url": "https://open-api.coinglass.com/public/v2/funding",
        "method": "GET",
        "expected_status": [200, 401, 403],
        "timeout": 10,
        "requires_key": False,
        "note": "Public funding endpoint available",
    },
    "laevitas": {
        "url": "https://api.laevitas.ch/analytics/options/btc/summary",
        "method": "GET",
        "expected_status": [200, 401, 403],
        "timeout": 10,
        "requires_key": False,
        "note": "Some public endpoints available",
    },
    "velodata": {
        "url": "https://velodata.app/api/v1/",
        "method": "GET",
        "expected_status": [200, 401, 404],
        "timeout": 10,
        "requires_key": False,
        "note": "Derivatives analytics API",
    },
    
    # ═══════════════════════════════════════════════════════════════
    # ON-CHAIN ANALYTICS
    # ═══════════════════════════════════════════════════════════════
    "nansen": {
        "url": "https://www.nansen.ai/",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "type": "html",
        "note": "Premium service, web parsing only",
    },
    "arkham": {
        "url": "https://platform.arkhamintelligence.com/",
        "method": "GET",
        "expected_status": [200, 403],
        "timeout": 10,
        "requires_key": False,
        "type": "html",
        "note": "Premium service, limited public access",
    },
    "dune": {
        "url": "https://api.dune.com/api/v1/query/1/results",
        "method": "GET",
        "expected_status": [200, 401, 403],
        "timeout": 10,
        "requires_key": False,
        "note": "API key for queries, public dashboards available",
    },
    "glassnode": {
        "url": "https://api.glassnode.com/v1/metrics/market/price_usd_close?a=btc",
        "method": "GET",
        "expected_status": [200, 401],
        "timeout": 10,
        "requires_key": False,
        "note": "Free tier with basic metrics",
    },
    "santiment": {
        "url": "https://api.santiment.net/graphql",
        "method": "GET",
        "expected_status": [200, 400, 401],
        "timeout": 10,
        "requires_key": False,
        "note": "GraphQL API, free tier available",
    },
    
    # ═══════════════════════════════════════════════════════════════
    # L2 ANALYTICS - FREE PUBLIC APIs
    # ═══════════════════════════════════════════════════════════════
    "l2beat": {
        "url": "https://api.l2beat.com/api/tvl",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "note": "Free public API",
    },
    "growthepie": {
        "url": "https://api.growthepie.xyz/v1/chains.json",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "note": "Free public API",
    },
    "artemis": {
        "url": "https://api.artemisxyz.com/",
        "method": "GET",
        "expected_status": [200, 401, 404],
        "timeout": 10,
        "requires_key": False,
        "note": "Chain analytics API",
    },
    
    # ═══════════════════════════════════════════════════════════════
    # AIRDROPS & ACTIVITIES - WEB PARSING
    # ═══════════════════════════════════════════════════════════════
    "icodrops": {
        "url": "https://icodrops.com/",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "type": "html",
        "note": "Web parsing for ICO/IDO data",
    },
    "dappradar": {
        "url": "https://dappradar.com/api/",
        "method": "GET",
        "expected_status": [200, 401, 404],
        "timeout": 10,
        "requires_key": False,
        "note": "API available, some endpoints public",
    },
    "dropsearn": {
        "url": "https://dropsearn.com/airdrops/",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "type": "html",
        "note": "Web parsing for airdrop data",
    },
    "airdropalert": {
        "url": "https://airdropalert.com/",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "type": "html",
        "note": "Web parsing for airdrop alerts",
    },
    
    # ═══════════════════════════════════════════════════════════════
    # NEWS - RSS FEEDS (Always work)
    # ═══════════════════════════════════════════════════════════════
    "cointelegraph": {
        "url": "https://cointelegraph.com/rss",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "type": "rss",
        "note": "RSS feed, always available",
    },
    "theblock": {
        "url": "https://www.theblock.co/rss.xml",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "type": "rss",
        "note": "RSS feed, always available",
    },
    "coindesk": {
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "method": "GET",
        "expected_status": [200, 301, 308],
        "timeout": 10,
        "requires_key": False,
        "type": "rss",
        "note": "RSS feed, may redirect",
    },
    "incrypted": {
        "url": "https://incrypted.com/feed/",
        "method": "GET",
        "expected_status": 200,
        "timeout": 10,
        "requires_key": False,
        "type": "rss",
        "note": "RSS feed, always available",
    },
}


class DataSourceHealthChecker:
    """
    Проверяет работоспособность источников данных.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )
    
    async def close(self):
        await self.client.aclose()
    
    async def check_single_source(self, source_id: str) -> Dict[str, Any]:
        """Check a single data source and return detailed status"""
        config = HEALTH_CHECKS.get(source_id)
        note = config.get("note", "") if config else ""
        
        if not config:
            return {
                "source_id": source_id,
                "status": "unknown",
                "message": "No health check configured for this source",
                "note": "Parser-based source, no direct API check",
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
        
        try:
            url = config["url"]
            method = config.get("method", "GET")
            timeout = config.get("timeout", 10)
            expected = config.get("expected_status", 200)
            requires_key = config.get("requires_key", False)
            source_type = config.get("type", "api")
            
            # Make request
            if method == "GET":
                resp = await self.client.get(url, timeout=timeout)
            else:
                resp = await self.client.post(url, timeout=timeout)
            
            # Check status
            if isinstance(expected, list):
                is_ok = resp.status_code in expected
            else:
                is_ok = resp.status_code == expected
            
            # Determine status with detailed messages
            if is_ok:
                if resp.status_code == 200:
                    status = "active"
                    message = "Working correctly"
                    if source_type == "rss":
                        message = "RSS feed active"
                    elif source_type == "html":
                        message = "Web parser ready"
                elif resp.status_code in [301, 308]:
                    status = "active"
                    message = "Redirect OK, following links"
                elif resp.status_code == 401:
                    if requires_key:
                        status = "needs_key"
                        message = "API key required for access"
                    else:
                        status = "degraded"
                        message = "Authentication required (unexpected)"
                elif resp.status_code == 403:
                    status = "degraded"
                    message = "Access forbidden - may need auth or IP whitelist"
                elif resp.status_code == 404:
                    status = "degraded"
                    message = "Endpoint not found - API may have changed"
                elif resp.status_code == 429:
                    status = "rate_limited"
                    message = "Rate limited - too many requests"
                else:
                    status = "active"
                    message = f"OK (HTTP {resp.status_code})"
            else:
                # Unexpected status
                if resp.status_code == 403:
                    status = "offline"
                    message = f"Access denied (HTTP 403) - blocked by server"
                elif resp.status_code == 404:
                    status = "offline"
                    message = f"Not found (HTTP 404) - endpoint may have moved"
                elif resp.status_code == 500:
                    status = "error"
                    message = f"Server error (HTTP 500) - source is down"
                elif resp.status_code == 502:
                    status = "error"
                    message = f"Bad gateway (HTTP 502) - server unreachable"
                elif resp.status_code == 503:
                    status = "error"
                    message = f"Service unavailable (HTTP 503) - maintenance?"
                else:
                    status = "error"
                    message = f"Unexpected response: HTTP {resp.status_code}"
            
            # Check response content for RSS/HTML
            if source_type == "rss" and resp.status_code == 200:
                content = resp.text[:500]
                if "<rss" in content or "<feed" in content or "<?xml" in content:
                    status = "active"
                    message = "RSS feed working"
                else:
                    status = "degraded"
                    message = "RSS format issue - unexpected content"
            
            elif source_type == "html" and resp.status_code == 200:
                content = resp.text[:500]
                if "<html" in content.lower() or "<!doctype" in content.lower():
                    status = "active"
                    message = "Web parser ready"
                else:
                    status = "degraded"
                    message = "HTML format issue - unexpected content"
            
            return {
                "source_id": source_id,
                "status": status,
                "http_status": resp.status_code,
                "message": message,
                "note": note,
                "response_time_ms": int(resp.elapsed.total_seconds() * 1000),
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
            
        except httpx.TimeoutException:
            return {
                "source_id": source_id,
                "status": "timeout",
                "message": f"Connection timeout after {config.get('timeout', 10)}s - server too slow",
                "note": note,
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
        except httpx.ConnectError as e:
            error_msg = str(e)[:100]
            if "Name or service not known" in error_msg:
                message = "DNS error - domain not found"
            elif "Connection refused" in error_msg:
                message = "Connection refused - server down"
            elif "Network unreachable" in error_msg:
                message = "Network unreachable"
            else:
                message = f"Connection failed: {error_msg}"
            return {
                "source_id": source_id,
                "status": "offline",
                "message": message,
                "note": note,
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "source_id": source_id,
                "status": "error",
                "message": f"Check failed: {str(e)[:80]}",
                "note": note,
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
    
    async def check_all_sources(self) -> Dict[str, Any]:
        """Check all configured data sources in parallel"""
        results = []
        
        # Get all sources from DB
        cursor = self.db.data_sources.find({}, {"_id": 0})
        sources = await cursor.to_list(length=100)
        
        # Check sources in parallel (batches of 10)
        batch_size = 10
        for i in range(0, len(sources), batch_size):
            batch = sources[i:i+batch_size]
            tasks = [self.check_single_source(s.get("id")) for s in batch if s.get("id")]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    results.append({
                        "source_id": "unknown",
                        "status": "error",
                        "message": str(result)[:100],
                        "checked_at": datetime.now(timezone.utc).isoformat()
                    })
                else:
                    results.append(result)
        
        # Update statuses in database (parallel)
        update_tasks = []
        for result in results:
            status = result["status"]
            
            # Map status to DB status
            if status == "active":
                db_status = "active"
            elif status in ["needs_key", "rate_limited"]:
                db_status = "degraded"
            elif status == "timeout":
                db_status = "timeout"
            elif status == "offline":
                db_status = "offline"
            else:
                db_status = "error"
            
            update_tasks.append(
                self.db.data_sources.update_one(
                    {"id": result["source_id"]},
                    {"$set": {
                        "status": db_status,
                        "last_check": result,
                        "last_checked_at": result["checked_at"]
                    }}
                )
            )
        
        if update_tasks:
            await asyncio.gather(*update_tasks)
        
        # Summary
        summary = {
            "total": len(results),
            "active": len([r for r in results if r["status"] == "active"]),
            "degraded": len([r for r in results if r["status"] in ["needs_key", "rate_limited", "degraded"]]),
            "offline": len([r for r in results if r["status"] in ["timeout", "offline", "error"]]),
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
        
        return {
            "summary": summary,
            "results": results
        }


async def run_health_check(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """Run health check for all data sources"""
    checker = DataSourceHealthChecker(db)
    try:
        return await checker.check_all_sources()
    finally:
        await checker.close()
