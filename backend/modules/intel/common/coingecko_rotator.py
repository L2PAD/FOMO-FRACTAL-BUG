"""
CoinGecko Key Rotation System
=============================
Manages CoinGecko API access through proxy rotation.
CoinGecko free tier (Demo API) doesn't require API key registration.
Rate limit: ~30 req/min per IP

Strategy:
1. Each proxy gets its own rate limit quota
2. When one proxy hits limit, switch to next
3. Auto-rotate through all available proxies
4. Track rate limits per proxy
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import httpx

logger = logging.getLogger(__name__)


@dataclass
class ProxyQuota:
    """Rate limit tracking per proxy"""
    proxy_id: str
    requests_this_minute: int = 0
    minute_window_start: Optional[datetime] = None
    last_request: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_errors: int = 0
    is_rate_limited: bool = False
    rate_limit_until: Optional[datetime] = None
    
    def reset_minute_window(self):
        self.requests_this_minute = 0
        self.minute_window_start = datetime.now(timezone.utc)
    
    def check_rate_limit(self, limit: int = 30) -> bool:
        """Check if this proxy is rate limited"""
        now = datetime.now(timezone.utc)
        
        # Check if rate limit cooldown expired
        if self.rate_limit_until and now > self.rate_limit_until:
            self.is_rate_limited = False
            self.rate_limit_until = None
        
        if self.is_rate_limited:
            return True
        
        # Reset minute window if needed
        if not self.minute_window_start or (now - self.minute_window_start).total_seconds() >= 60:
            self.reset_minute_window()
        
        return self.requests_this_minute >= limit
    
    def record_request(self):
        self.requests_this_minute += 1
        self.last_request = datetime.now(timezone.utc)
    
    def record_rate_limit(self, cooldown_seconds: int = 60):
        """Mark proxy as rate limited"""
        self.is_rate_limited = True
        self.rate_limit_until = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
        logger.warning(f"[CoinGeckoRotator] Proxy {self.proxy_id} rate limited until {self.rate_limit_until}")
    
    def record_success(self):
        self.consecutive_errors = 0
        self.last_error = None
    
    def record_error(self, error: str):
        self.consecutive_errors += 1
        self.last_error = error


class CoinGeckoProxyRotator:
    """
    Manages CoinGecko API access with proxy rotation.
    
    Usage:
        rotator = CoinGeckoProxyRotator(db)
        data = await rotator.request("/coins/list")
    """
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    RATE_LIMIT_PER_PROXY = 30  # requests per minute
    
    def __init__(self, db):
        self.db = db
        self._proxy_quotas: Dict[str, ProxyQuota] = {}
        self._lock = asyncio.Lock()
        self._current_proxy_idx = 0
    
    async def _get_proxies(self) -> List[Dict]:
        """Get available proxies from proxy manager"""
        try:
            from modules.intel.common.proxy_manager import proxy_manager
            await proxy_manager.load_from_db()
            status = proxy_manager.get_status()
            return [p for p in status.get('proxies', []) if p.get('enabled')]
        except Exception as e:
            logger.error(f"[CoinGeckoRotator] Failed to get proxies: {e}")
            return []
    
    def _get_or_create_quota(self, proxy_id: str) -> ProxyQuota:
        """Get or create quota tracker for proxy"""
        if proxy_id not in self._proxy_quotas:
            self._proxy_quotas[proxy_id] = ProxyQuota(proxy_id=proxy_id)
        return self._proxy_quotas[proxy_id]
    
    async def _get_available_proxy(self) -> Optional[Dict]:
        """Get next available proxy (not rate limited)"""
        proxies = await self._get_proxies()
        
        if not proxies:
            # No proxies - use direct connection
            return None
        
        # Try to find available proxy
        for _ in range(len(proxies)):
            proxy = proxies[self._current_proxy_idx % len(proxies)]
            quota = self._get_or_create_quota(str(proxy['id']))
            
            if not quota.check_rate_limit(self.RATE_LIMIT_PER_PROXY):
                return proxy
            
            # Move to next proxy
            self._current_proxy_idx += 1
        
        # All proxies rate limited - wait and return first that unlocks
        logger.warning("[CoinGeckoRotator] All proxies rate limited, waiting...")
        await asyncio.sleep(5)
        
        # Return first proxy anyway (will retry later)
        return proxies[0] if proxies else None
    
    async def request(
        self, 
        endpoint: str, 
        params: Dict = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Make CoinGecko API request with automatic proxy rotation.
        
        Args:
            endpoint: API endpoint (e.g., "/coins/list")
            params: Query parameters
            timeout: Request timeout in seconds
            
        Returns:
            API response data
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        async with self._lock:
            proxy = await self._get_available_proxy()
            proxy_id = str(proxy['id']) if proxy else 'direct'
            quota = self._get_or_create_quota(proxy_id)
        
        # Build proxy URL
        proxy_url = None
        if proxy:
            proxy_server = proxy.get('server', '')
            if proxy.get('has_auth'):
                # Need to get full proxy URL with auth
                from modules.intel.common.proxy_manager import proxy_manager
                for p in proxy_manager._proxies:
                    if p.id == proxy['id']:
                        proxy_url = p.url
                        break
            else:
                proxy_url = proxy_server
        
        try:
            async with httpx.AsyncClient(
                proxy=proxy_url,
                timeout=timeout
            ) as client:
                response = await client.get(url, params=params)
                
                # Record request
                quota.record_request()
                
                # Check for rate limit
                if response.status_code == 429:
                    quota.record_rate_limit(60)
                    # Retry with different proxy
                    return await self.request(endpoint, params, timeout)
                
                response.raise_for_status()
                
                quota.record_success()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                quota.record_rate_limit(60)
                return await self.request(endpoint, params, timeout)
            quota.record_error(str(e))
            raise
            
        except Exception as e:
            quota.record_error(str(e))
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get rotator status"""
        return {
            "proxy_quotas": {
                pid: {
                    "requests_this_minute": q.requests_this_minute,
                    "is_rate_limited": q.is_rate_limited,
                    "rate_limit_until": q.rate_limit_until.isoformat() if q.rate_limit_until else None,
                    "consecutive_errors": q.consecutive_errors,
                    "last_error": q.last_error
                }
                for pid, q in self._proxy_quotas.items()
            },
            "current_proxy_idx": self._current_proxy_idx
        }


# Singleton
_rotator: Optional[CoinGeckoProxyRotator] = None


def get_coingecko_rotator(db) -> CoinGeckoProxyRotator:
    """Get or create CoinGecko rotator"""
    global _rotator
    if _rotator is None:
        _rotator = CoinGeckoProxyRotator(db)
    return _rotator
