"""
Health Monitor
==============

Monitors health of all providers and instances.
Runs periodic checks and updates status.
"""

import asyncio
import httpx
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import ProviderStatus, HealthCheckResult
from .registry import ProviderRegistry

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Provider Health Monitor.
    Periodically checks all providers and updates status.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.registry = ProviderRegistry(db)
        self.timeout = 10  # Health check timeout
        self._running = False
        self._task = None
    
    # ═══════════════════════════════════════════════════════════════
    # HEALTH CHECK METHODS
    # ═══════════════════════════════════════════════════════════════
    
    async def check_provider(self, provider_id: str) -> HealthCheckResult:
        """Check single provider health"""
        provider = await self.registry.get_provider(provider_id)
        if not provider:
            return HealthCheckResult(
                provider_id=provider_id,
                status=ProviderStatus.DOWN,
                latency_ms=0,
                success=False,
                error="Provider not found"
            )
        
        # Build health check URL
        endpoint = provider["endpoint"]
        
        # Provider-specific health endpoints
        health_paths = {
            "coingecko": "/ping",
            "coinmarketcap": "/cryptocurrency/map?limit=1",
            "messari": "/assets?limit=1",
            "defillama": "/protocols",
            "dexscreener": "/dex/pairs/ethereum/0x0000000000000000000000000000000000000000",
            "geckoterminal": "/networks",
            "coinglass": "/funding",
        }
        
        path = health_paths.get(provider_id, "/")
        url = f"{endpoint.rstrip('/')}{path}"
        
        start_time = datetime.now(timezone.utc)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Add API key if required
                headers = {}
                if provider.get("requires_api_key"):
                    # Get any available key
                    key_doc = await self.db.api_keys.find_one(
                        {"service": provider_id, "enabled": True}
                    )
                    if key_doc:
                        header_name = provider.get("api_key_header", "Authorization")
                        headers[header_name] = key_doc.get("api_key")
                
                response = await client.get(url, headers=headers)
                latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                
                if response.status_code < 400:
                    return HealthCheckResult(
                        provider_id=provider_id,
                        status=ProviderStatus.ACTIVE,
                        latency_ms=latency_ms,
                        success=True
                    )
                elif response.status_code == 429:
                    return HealthCheckResult(
                        provider_id=provider_id,
                        status=ProviderStatus.RATE_LIMITED,
                        latency_ms=latency_ms,
                        success=False,
                        error="Rate limited"
                    )
                else:
                    return HealthCheckResult(
                        provider_id=provider_id,
                        status=ProviderStatus.DEGRADED,
                        latency_ms=latency_ms,
                        success=False,
                        error=f"HTTP {response.status_code}"
                    )
                    
        except httpx.TimeoutException:
            return HealthCheckResult(
                provider_id=provider_id,
                status=ProviderStatus.DOWN,
                latency_ms=self.timeout * 1000,
                success=False,
                error="Timeout"
            )
        except Exception as e:
            return HealthCheckResult(
                provider_id=provider_id,
                status=ProviderStatus.DOWN,
                latency_ms=0,
                success=False,
                error=str(e)
            )
    
    async def check_all_providers(self) -> List[HealthCheckResult]:
        """Check health of all active providers"""
        providers = await self.registry.list_providers(status="active")
        results = []
        
        for provider in providers:
            result = await self.check_provider(provider["id"])
            results.append(result)
            
            # Update provider status
            await self.registry.update_provider(
                provider["id"],
                {"status": result.status.value}
            )
        
        return results
    
    async def check_instance(self, instance_id: str) -> HealthCheckResult:
        """Check specific instance health"""
        instance = await self.db.provider_instances.find_one({"id": instance_id})
        if not instance:
            return HealthCheckResult(
                provider_id="unknown",
                instance_id=instance_id,
                status=ProviderStatus.DOWN,
                latency_ms=0,
                success=False,
                error="Instance not found"
            )
        
        provider = await self.registry.get_provider(instance["provider_id"])
        if not provider:
            return HealthCheckResult(
                provider_id=instance["provider_id"],
                instance_id=instance_id,
                status=ProviderStatus.DOWN,
                latency_ms=0,
                success=False,
                error="Provider not found"
            )
        
        # Build request with instance config
        endpoint = provider["endpoint"]
        url = f"{endpoint.rstrip('/')}/ping"  # Generic ping
        
        headers = {}
        proxy_url = None
        
        # Get API key if bound
        if instance.get("api_key_id"):
            key_doc = await self.db.api_keys.find_one({"id": instance["api_key_id"]})
            if key_doc:
                header_name = provider.get("api_key_header", "Authorization")
                headers[header_name] = key_doc.get("api_key")
        
        # Get proxy if bound
        if instance.get("proxy_id"):
            proxy_doc = await self.db.proxies.find_one({"id": instance["proxy_id"]})
            if proxy_doc:
                server = proxy_doc.get("server", "")
                if proxy_doc.get("username"):
                    proxy_url = f"http://{proxy_doc['username']}:{proxy_doc.get('password', '')}@{server}"
                else:
                    proxy_url = f"http://{server}"
        
        start_time = datetime.now(timezone.utc)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=proxy_url) as client:
                response = await client.get(url, headers=headers)
                latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                
                success = response.status_code < 400
                status = ProviderStatus.ACTIVE if success else ProviderStatus.DEGRADED
                
                # Update instance
                await self.registry.update_instance_status(
                    instance_id, status, latency_ms,
                    None if success else f"HTTP {response.status_code}"
                )
                
                return HealthCheckResult(
                    provider_id=instance["provider_id"],
                    instance_id=instance_id,
                    status=status,
                    latency_ms=latency_ms,
                    success=success,
                    error=None if success else f"HTTP {response.status_code}"
                )
                
        except Exception as e:
            await self.registry.update_instance_status(
                instance_id, ProviderStatus.DOWN, error=str(e)
            )
            return HealthCheckResult(
                provider_id=instance["provider_id"],
                instance_id=instance_id,
                status=ProviderStatus.DOWN,
                latency_ms=0,
                success=False,
                error=str(e)
            )
    
    # ═══════════════════════════════════════════════════════════════
    # AGGREGATED HEALTH
    # ═══════════════════════════════════════════════════════════════
    
    async def get_gateway_health(self) -> Dict:
        """Get overall gateway health status"""
        providers = await self.registry.list_providers()
        stats = await self.registry.get_stats()
        
        # Calculate health score
        active = stats.get("active_providers", 0)
        total = stats.get("total_providers", 0)
        health_score = (active / total * 100) if total > 0 else 0
        
        # Get recent health checks
        results = []
        for provider in providers[:10]:  # Check top 10
            result = await self.check_provider(provider["id"])
            results.append({
                "provider_id": provider["id"],
                "provider_name": provider["name"],
                "status": result.status.value,
                "latency_ms": result.latency_ms,
                "success": result.success,
                "error": result.error
            })
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "health_score": health_score,
            "stats": stats,
            "providers": results
        }
    
    # ═══════════════════════════════════════════════════════════════
    # BACKGROUND MONITORING
    # ═══════════════════════════════════════════════════════════════
    
    async def start_monitoring(self, interval_seconds: int = 60):
        """Start background health monitoring"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(interval_seconds))
        logger.info(f"Health monitor started with {interval_seconds}s interval")
    
    async def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Health monitor stopped")
    
    async def _monitor_loop(self, interval: int):
        """Background monitoring loop"""
        while self._running:
            try:
                await self.check_all_providers()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            await asyncio.sleep(interval)
