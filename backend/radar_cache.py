"""
R4.2 — LRU Cache Layer (Production Grade)
In-memory LRU cache with TTL for Radar list endpoints.

- Max keys: 400
- TTL: 45s (list), 15s (debug)
- Eviction: expired-first, then LRU
- Thread-safe via threading.Lock
"""

import time
import hashlib
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

# ── Config ──
MAX_KEYS = 400
LIST_TTL = 45       # seconds
DEBUG_TTL = 15      # seconds
ADMIN_TTL = 0       # no cache

# ── Stats ──
_stats = {
    "hits": 0,
    "misses": 0,
    "evictions": 0,
    "sets": 0,
    "expired_purges": 0,
}

# ── Storage ──
# OrderedDict: key → (value, expires_at)
_store: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
_lock = threading.Lock()


def build_cache_key(
    universe: str,
    horizon: str = "auto",
    sort: str = "conviction",
    page: int = 1,
    page_size: int = 25,
    search: Optional[str] = None,
    verdict: Optional[str] = None,
    min_conv: Optional[int] = None,
) -> str:
    """Build normalized cache key from request parameters."""
    # Normalize filters into a stable hash
    filter_parts = []
    if search:
        filter_parts.append(f"s={search.lower().strip()}")
    if verdict and verdict != "all":
        filter_parts.append(f"v={verdict.lower()}")
    if min_conv is not None and min_conv > 0:
        filter_parts.append(f"mc={min_conv}")

    filters_hash = ""
    if filter_parts:
        raw = "&".join(sorted(filter_parts))
        filters_hash = hashlib.md5(raw.encode()).hexdigest()[:8]

    return f"radar:{universe}:{horizon}:{sort}:{page}:{page_size}:{filters_hash}"


def _evict_expired() -> int:
    """Remove all expired entries. Returns count removed. Must hold _lock."""
    now = time.time()
    expired = [k for k, (_, exp) in _store.items() if exp <= now]
    for k in expired:
        del _store[k]
    count = len(expired)
    _stats["expired_purges"] += count
    _stats["evictions"] += count
    return count


def _evict_lru(count: int = 1):
    """Remove oldest entries. Must hold _lock."""
    for _ in range(count):
        if _store:
            _store.popitem(last=False)
            _stats["evictions"] += 1


def get(key: str) -> Optional[Any]:
    """Get cached value. Returns None on miss or expired."""
    with _lock:
        entry = _store.get(key)
        if entry is None:
            _stats["misses"] += 1
            return None

        value, expires_at = entry
        if time.time() > expires_at:
            # Expired — remove it
            del _store[key]
            _stats["misses"] += 1
            _stats["expired_purges"] += 1
            return None

        # Hit — move to end (most recently used)
        _store.move_to_end(key)
        _stats["hits"] += 1
        return value


def set(key: str, value: Any, ttl: int = LIST_TTL):
    """Store value with TTL. Evicts if at capacity."""
    if ttl <= 0:
        return  # Don't cache admin endpoints

    with _lock:
        # If key exists, update in place
        if key in _store:
            _store[key] = (value, time.time() + ttl)
            _store.move_to_end(key)
            _stats["sets"] += 1
            return

        # Evict expired first
        _evict_expired()

        # If still at capacity, evict LRU
        while len(_store) >= MAX_KEYS:
            _evict_lru(1)

        _store[key] = (value, time.time() + ttl)
        _stats["sets"] += 1


def invalidate(pattern: Optional[str] = None):
    """Invalidate cache entries. If pattern given, only matching keys."""
    with _lock:
        if pattern is None:
            count = len(_store)
            _store.clear()
            return count

        to_remove = [k for k in _store if pattern in k]
        for k in to_remove:
            del _store[k]
        return len(to_remove)


def get_stats() -> Dict[str, Any]:
    """Get cache statistics for health endpoint."""
    with _lock:
        total = _stats["hits"] + _stats["misses"]
        hit_rate = round(_stats["hits"] / total, 4) if total > 0 else 0

        # Count expired vs active
        now = time.time()
        active = sum(1 for _, (_, exp) in _store.items() if exp > now)

        return {
            "enabled": True,
            "keys": len(_store),
            "activeKeys": active,
            "maxKeys": MAX_KEYS,
            "hits": _stats["hits"],
            "misses": _stats["misses"],
            "hitRate": hit_rate,
            "sets": _stats["sets"],
            "evictions": _stats["evictions"],
            "expiredPurges": _stats["expired_purges"],
            "ttl": {
                "list": LIST_TTL,
                "debug": DEBUG_TTL,
                "admin": ADMIN_TTL,
            },
        }
