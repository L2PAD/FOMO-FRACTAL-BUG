"""
Cache Layer with different TTL per data type
"""

import time
import asyncio
from typing import Any, Optional, Dict
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    data: Any
    expires_at: float
    created_at: float = field(default_factory=time.time)


class CacheLayer:
    """In-memory cache with configurable TTL per data type"""
    
    # TTL configurations (seconds)
    TTL_QUOTE = 10          # Single quote - 10s
    TTL_BULK_QUOTES = 10    # Bulk quotes - 10s
    TTL_OVERVIEW = 60       # Market overview - 60s
    TTL_CANDLES = 300       # Candles - 5 min
    TTL_EXCHANGES = 30      # Exchange info - 30s
    TTL_ORDERBOOK = 5       # Orderbook - 5s (very volatile)
    TTL_TRADES = 5          # Recent trades - 5s
    TTL_HEALTH = 30         # Provider health - 30s
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0
        }
    
    def _get_ttl(self, cache_type: str) -> int:
        """Get TTL for cache type"""
        ttl_map = {
            "quote": self.TTL_QUOTE,
            "quotes": self.TTL_BULK_QUOTES,
            "overview": self.TTL_OVERVIEW,
            "candles": self.TTL_CANDLES,
            "exchanges": self.TTL_EXCHANGES,
            "orderbook": self.TTL_ORDERBOOK,
            "trades": self.TTL_TRADES,
            "health": self.TTL_HEALTH,
        }
        return ttl_map.get(cache_type, 30)  # default 30s
    
    def _make_key(self, cache_type: str, *args) -> str:
        """Create cache key"""
        parts = [cache_type] + [str(a) for a in args if a is not None]
        return ":".join(parts)
    
    async def get(self, cache_type: str, *args) -> Optional[Any]:
        """Get from cache if not expired"""
        key = self._make_key(cache_type, *args)
        
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats["misses"] += 1
                return None
            
            if time.time() > entry.expires_at:
                # Expired
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            
            self._stats["hits"] += 1
            return entry.data
    
    async def set(self, cache_type: str, data: Any, *args):
        """Set cache with appropriate TTL"""
        key = self._make_key(cache_type, *args)
        ttl = self._get_ttl(cache_type)
        
        async with self._lock:
            self._cache[key] = CacheEntry(
                data=data,
                expires_at=time.time() + ttl
            )
            self._stats["sets"] += 1
    
    async def invalidate(self, cache_type: str, *args):
        """Invalidate specific cache entry"""
        key = self._make_key(cache_type, *args)
        async with self._lock:
            self._cache.pop(key, None)
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching pattern"""
        async with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
    
    async def clear(self):
        """Clear all cache"""
        async with self._lock:
            self._cache.clear()
    
    async def cleanup_expired(self):
        """Remove expired entries"""
        now = time.time()
        async with self._lock:
            expired_keys = [k for k, v in self._cache.items() if now > v.expires_at]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        return {
            **self._stats,
            "total_requests": total,
            "hit_rate": round(hit_rate, 2),
            "entries": len(self._cache)
        }


# Global cache instance
cache_layer = CacheLayer()
