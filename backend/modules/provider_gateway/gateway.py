"""
Provider Gateway
================

Unified gateway for making requests through providers.
Handles failover, rate limiting, and request routing.
"""

import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import ProviderStatus
from .registry import ProviderRegistry

logger = logging.getLogger(__name__)


class ProviderGateway:
    """
    Unified Provider Gateway.
    Routes requests through appropriate provider instances with failover.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.registry = ProviderRegistry(db)
        self.api_keys = db.api_keys
        self.proxies = db.proxies
        
        # Request timeout
        self.timeout = 30
    
    # ═══════════════════════════════════════════════════════════════
    # MAIN REQUEST METHOD
    # ═══════════════════════════════════════════════════════════════
    
    async def request(
        self,
        provider_id: str,
        path: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make request to provider with automatic failover.
        
        Args:
            provider_id: Target provider
            path: API path (without base URL)
            method: HTTP method
            params: Query parameters
            data: Request body
            headers: Additional headers
            
        Returns:
            {
                "ok": bool,
                "data": response_data,
                "provider": provider_id,
                "instance": instance_id,
                "latency_ms": float
            }
        """
        # Get provider config
        provider = await self.registry.get_provider(provider_id)
        if not provider:
            return {"ok": False, "error": f"Provider not found: {provider_id}"}
        
        if provider.get("status") == "disabled":
            return {"ok": False, "error": f"Provider disabled: {provider_id}"}
        
        # Get instances
        instances = await self.registry.get_instances(provider_id)
        
        # If no instances, create direct instance
        if not instances:
            direct_result = await self._make_direct_request(provider, path, method, params, data, headers)
            return direct_result
        
        # Try instances in order
        for instance in sorted(instances, key=lambda x: (x.get("error_count", 0), x.get("latency_ms") or 9999)):
            if instance.get("status") in ["down", "disabled"]:
                continue
            
            result = await self._make_instance_request(
                provider, instance, path, method, params, data, headers
            )
            
            if result["ok"]:
                return result
            
            # Log failure and try next
            logger.warning(f"Instance {instance['id']} failed: {result.get('error')}")
        
        # All instances failed, try direct
        return await self._make_direct_request(provider, path, method, params, data, headers)
    
    async def _make_instance_request(
        self,
        provider: dict,
        instance: dict,
        path: str,
        method: str,
        params: Optional[Dict],
        data: Optional[Dict],
        headers: Optional[Dict]
    ) -> Dict[str, Any]:
        """Make request through specific instance"""
        instance_id = instance["id"]
        
        # Build URL
        base_url = provider["endpoint"].rstrip("/")
        url = f"{base_url}/{path.lstrip('/')}"
        
        # Build headers
        req_headers = headers.copy() if headers else {}
        
        # Add API key if required
        if provider.get("requires_api_key") and instance.get("api_key_id"):
            api_key = await self._get_api_key(instance["api_key_id"])
            if api_key:
                header_name = provider.get("api_key_header", "Authorization")
                req_headers[header_name] = api_key
        
        # Get proxy if bound
        proxy_url = None
        if instance.get("proxy_id"):
            proxy_url = await self._get_proxy_url(instance["proxy_id"])
        
        # Make request
        start_time = datetime.now(timezone.utc)
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                proxy=proxy_url
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data if method in ["POST", "PUT", "PATCH"] else None,
                    headers=req_headers
                )
                
                latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                
                if response.status_code == 429:
                    # Rate limited
                    await self.registry.update_instance_status(
                        instance_id, 
                        ProviderStatus.RATE_LIMITED,
                        latency_ms,
                        "Rate limited"
                    )
                    return {"ok": False, "error": "Rate limited", "status": 429}
                
                if response.status_code >= 400:
                    await self.registry.update_instance_status(
                        instance_id,
                        ProviderStatus.DEGRADED,
                        latency_ms,
                        f"HTTP {response.status_code}"
                    )
                    return {
                        "ok": False, 
                        "error": f"HTTP {response.status_code}", 
                        "status": response.status_code
                    }
                
                # Success
                await self.registry.update_instance_status(
                    instance_id,
                    ProviderStatus.ACTIVE,
                    latency_ms
                )
                
                return {
                    "ok": True,
                    "data": response.json(),
                    "provider": provider["id"],
                    "instance": instance_id,
                    "latency_ms": latency_ms
                }
                
        except httpx.TimeoutException:
            latency_ms = self.timeout * 1000
            await self.registry.update_instance_status(
                instance_id,
                ProviderStatus.DOWN,
                latency_ms,
                "Timeout"
            )
            return {"ok": False, "error": "Timeout"}
            
        except Exception as e:
            await self.registry.update_instance_status(
                instance_id,
                ProviderStatus.DOWN,
                error=str(e)
            )
            return {"ok": False, "error": str(e)}
    
    async def _make_direct_request(
        self,
        provider: dict,
        path: str,
        method: str,
        params: Optional[Dict],
        data: Optional[Dict],
        headers: Optional[Dict]
    ) -> Dict[str, Any]:
        """Make direct request without instance (no proxy, first available key)"""
        base_url = provider["endpoint"].rstrip("/")
        url = f"{base_url}/{path.lstrip('/')}"
        
        req_headers = headers.copy() if headers else {}
        
        # Get first available API key
        if provider.get("requires_api_key"):
            api_key = await self._get_best_api_key(provider["id"])
            if not api_key:
                return {"ok": False, "error": f"No API key available for {provider['id']}"}
            header_name = provider.get("api_key_header", "Authorization")
            req_headers[header_name] = api_key
        
        start_time = datetime.now(timezone.utc)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data if method in ["POST", "PUT", "PATCH"] else None,
                    headers=req_headers
                )
                
                latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                
                if response.status_code >= 400:
                    return {
                        "ok": False,
                        "error": f"HTTP {response.status_code}",
                        "status": response.status_code,
                        "latency_ms": latency_ms
                    }
                
                return {
                    "ok": True,
                    "data": response.json(),
                    "provider": provider["id"],
                    "instance": "direct",
                    "latency_ms": latency_ms
                }
                
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════
    
    async def _get_api_key(self, key_id: str) -> Optional[str]:
        """Get API key value by ID"""
        key_doc = await self.api_keys.find_one({"id": key_id, "enabled": True})
        if key_doc:
            return key_doc.get("api_key")
        return None
    
    async def _get_best_api_key(self, provider_id: str) -> Optional[str]:
        """Get best available API key for provider"""
        # Map provider_id to service name
        service_map = {
            "coingecko": "coingecko",
            "coinmarketcap": "coinmarketcap",
            "messari": "messari"
        }
        service = service_map.get(provider_id, provider_id)
        
        key_doc = await self.api_keys.find_one(
            {"service": service, "enabled": True, "healthy": True},
            sort=[("requests_this_minute", 1)]
        )
        if key_doc:
            return key_doc.get("api_key")
        return None
    
    async def _get_proxy_url(self, proxy_id: str) -> Optional[str]:
        """Get proxy URL by ID"""
        proxy_doc = await self.proxies.find_one({"id": proxy_id, "enabled": True})
        if proxy_doc:
            server = proxy_doc.get("server", "")
            if proxy_doc.get("username"):
                # Authenticated proxy
                return f"http://{proxy_doc['username']}:{proxy_doc.get('password', '')}@{server}"
            return f"http://{server}"
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # CONVENIENCE METHODS FOR COMMON PROVIDERS
    # ═══════════════════════════════════════════════════════════════
    
    async def coingecko(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make CoinGecko API request"""
        return await self.request("coingecko", path, params=params)
    
    async def coinmarketcap(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make CoinMarketCap API request"""
        return await self.request("coinmarketcap", path, params=params)
    
    async def messari(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make Messari API request"""
        return await self.request("messari", path, params=params)
    
    async def defillama(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make DefiLlama API request"""
        return await self.request("defillama", path, params=params)
    
    async def dexscreener(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make DexScreener API request"""
        return await self.request("dexscreener", path, params=params)
    
    async def coinglass(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make CoinGlass API request"""
        return await self.request("coinglass", path, params=params)
    
    # ═══════════════════════════════════════════════════════════════
    # MULTI-PROVIDER QUERIES
    # ═══════════════════════════════════════════════════════════════
    
    async def get_price_from_any(self, symbol: str) -> Dict:
        """
        Get price from first available provider.
        Fallback order: CoinGecko → CoinMarketCap → DexScreener
        """
        providers = ["coingecko", "coinmarketcap", "dexscreener"]
        
        for provider_id in providers:
            provider = await self.registry.get_provider(provider_id)
            if not provider or provider.get("status") != "active":
                continue
            
            # Build provider-specific request
            if provider_id == "coingecko":
                result = await self.request(
                    "coingecko",
                    f"simple/price",
                    params={"ids": symbol.lower(), "vs_currencies": "usd"}
                )
            elif provider_id == "coinmarketcap":
                result = await self.request(
                    "coinmarketcap",
                    "cryptocurrency/quotes/latest",
                    params={"symbol": symbol.upper()}
                )
            elif provider_id == "dexscreener":
                result = await self.request(
                    "dexscreener",
                    f"dex/search",
                    params={"q": symbol}
                )
            else:
                continue
            
            if result["ok"]:
                return result
        
        return {"ok": False, "error": "No provider available for price data"}
