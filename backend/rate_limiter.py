"""
R4.3 — Load Guardrails: Rate Limiter + Request Guardrails
In-memory sliding window rate limiter for FastAPI.
"""

import time
from collections import defaultdict
from typing import Dict, Tuple

# ── Config ──
DEFAULT_RATE_LIMIT = 200      # requests per window
DEFAULT_WINDOW_SEC = 60       # window size in seconds
RADAR_RATE_LIMIT = 30         # stricter limit for heavy radar endpoints
MAX_PAGE_SIZE = 100           # max allowed pageSize for list endpoints
DEFAULT_PAGE_SIZE = 25
REQUEST_TIMEOUT_SEC = 30      # per-request timeout for radar computations

# ── State ──
_buckets: Dict[str, list] = defaultdict(list)
_stats = {
    "totalRequests": 0,
    "rejectedRequests": 0,
}


def _cleanup_bucket(key: str, window: int):
    """Remove expired entries from bucket."""
    now = time.time()
    cutoff = now - window
    _buckets[key] = [ts for ts in _buckets[key] if ts > cutoff]


def check_rate_limit(client_ip: str, path: str) -> Tuple[bool, Dict]:
    """
    Check if request should be allowed.
    Returns (allowed: bool, info: dict with limit/remaining/reset).
    """
    _stats["totalRequests"] += 1
    
    # Determine limit based on path
    is_radar = "/radar/" in path or "/v11/" in path
    limit = RADAR_RATE_LIMIT if is_radar else DEFAULT_RATE_LIMIT
    window = DEFAULT_WINDOW_SEC
    
    key = f"{client_ip}:{('radar' if is_radar else 'general')}"
    
    _cleanup_bucket(key, window)
    
    now = time.time()
    count = len(_buckets[key])
    
    info = {
        "limit": limit,
        "remaining": max(0, limit - count),
        "reset": int(now + window),
        "window": window,
    }
    
    if count >= limit:
        _stats["rejectedRequests"] += 1
        return False, info
    
    _buckets[key].append(now)
    info["remaining"] = max(0, limit - count - 1)
    return True, info


def enforce_page_size(page_size: int | None) -> int:
    """Clamp pageSize to allowed range."""
    if page_size is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(page_size, MAX_PAGE_SIZE))


def get_stats() -> Dict:
    """Get rate limiter statistics."""
    active_clients = len(_buckets)
    return {
        "totalRequests": _stats["totalRequests"],
        "rejectedRequests": _stats["rejectedRequests"],
        "activeClients": active_clients,
        "config": {
            "defaultLimit": DEFAULT_RATE_LIMIT,
            "radarLimit": RADAR_RATE_LIMIT,
            "windowSec": DEFAULT_WINDOW_SEC,
            "maxPageSize": MAX_PAGE_SIZE,
            "requestTimeoutSec": REQUEST_TIMEOUT_SEC,
        },
    }


def periodic_cleanup():
    """Cleanup old buckets. Call periodically."""
    now = time.time()
    expired = []
    for key in _buckets:
        _buckets[key] = [ts for ts in _buckets[key] if ts > now - DEFAULT_WINDOW_SEC * 2]
        if not _buckets[key]:
            expired.append(key)
    for key in expired:
        del _buckets[key]
