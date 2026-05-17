"""
R4.1 — Exchange Health Layer
Comprehensive health check for the Exchange Intelligence system.
Returns HEALTHY / DEGRADED / CRITICAL with detailed pipeline status.
"""

import time
import os
import psutil
from datetime import datetime, timezone
from typing import Dict, Any

# ── Startup tracking ──
_start_time = time.time()

# ── Cache metrics (shared with cache module) ──
_cache_stats: Dict[str, Any] = {
    "hits": 0,
    "misses": 0,
    "evictions": 0,
    "size": 0,
    "maxSize": 0,
}


def update_cache_stats(stats: Dict[str, Any]):
    """Called by cache layer to update health metrics."""
    _cache_stats.update(stats)


def get_cache_stats() -> Dict[str, Any]:
    total = _cache_stats["hits"] + _cache_stats["misses"]
    hit_rate = round(_cache_stats["hits"] / total * 100, 1) if total > 0 else 0
    return {**_cache_stats, "hitRate": hit_rate, "totalRequests": total}


# ── Rate limiter metrics ──
_rate_limiter_stats: Dict[str, Any] = {
    "totalRequests": 0,
    "rejectedRequests": 0,
    "activeClients": 0,
}


def update_rate_limiter_stats(stats: Dict[str, Any]):
    _rate_limiter_stats.update(stats)


def get_rate_limiter_stats() -> Dict[str, Any]:
    return {**_rate_limiter_stats}


# ── Pipeline freshness tracking ──
_pipeline_timestamps: Dict[str, float] = {}


def record_pipeline_hit(pipeline: str):
    """Record that a pipeline was accessed/ran."""
    _pipeline_timestamps[pipeline] = time.time()


def _check_mongo() -> Dict[str, Any]:
    """Check MongoDB connectivity."""
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        db_name = os.environ.get("DB_NAME", "intelligence_engine")
        db = client[db_name]
        collections = db.list_collection_names()
        client.close()
        return {
            "status": "connected",
            "collections": len(collections),
            "latencyMs": 0,
        }
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


def _check_node_backend() -> Dict[str, Any]:
    """Check Node.js backend availability."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(('127.0.0.1', 8003))
        s.close()
        if result == 0:
            return {"status": "connected", "port": 8003}
        return {"status": "disconnected", "port": 8003}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


def _check_resources() -> Dict[str, Any]:
    """Check system resource usage."""
    proc = psutil.Process(os.getpid())
    mem = proc.memory_info()
    
    # Total system memory
    sys_mem = psutil.virtual_memory()
    
    return {
        "python": {
            "rss_mb": round(mem.rss / 1024 / 1024, 1),
            "vms_mb": round(mem.vms / 1024 / 1024, 1),
            "cpu_pct": round(proc.cpu_percent(interval=0.1), 1),
        },
        "system": {
            "total_mb": round(sys_mem.total / 1024 / 1024, 1),
            "used_mb": round(sys_mem.used / 1024 / 1024, 1),
            "pct": sys_mem.percent,
        },
        "uptime_s": round(time.time() - _start_time, 0),
    }


def _check_radar() -> Dict[str, Any]:
    """Check Radar V11 engine status."""
    try:
        from radar_v11.universe import get_universe_counts
        counts = get_universe_counts()
        total = counts.get("spotMainCount", 0) + counts.get("spotAlphaCount", 0) + counts.get("futuresCount", 0)
        return {
            "status": "ok" if total > 0 else "empty",
            "spotMain": counts.get("spotMainCount", 0),
            "spotAlpha": counts.get("spotAlphaCount", 0),
            "futures": counts.get("futuresCount", 0),
            "totalSymbols": total,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _check_pipelines() -> Dict[str, Any]:
    """Check data pipeline freshness."""
    now = time.time()
    stale_threshold = 300  # 5 min
    pipelines = {}
    
    for name, ts in _pipeline_timestamps.items():
        age = round(now - ts, 0)
        pipelines[name] = {
            "lastHitAgo_s": age,
            "status": "fresh" if age < stale_threshold else "stale",
        }
    
    if not pipelines:
        return {"status": "no_data", "detail": "No pipeline activity recorded yet"}
    
    stale_count = sum(1 for p in pipelines.values() if p["status"] == "stale")
    return {
        "status": "ok" if stale_count == 0 else "degraded",
        "staleCount": stale_count,
        "pipelines": pipelines,
    }


def compute_health() -> Dict[str, Any]:
    """
    Compute comprehensive health status.
    Returns full health report with status: HEALTHY / DEGRADED / CRITICAL
    """
    mongo = _check_mongo()
    node = _check_node_backend()
    resources = _check_resources()
    radar = _check_radar()
    pipelines = _check_pipelines()
    rate_limiter = get_rate_limiter_stats()

    # R4.2: Get cache stats from radar_cache
    try:
        import radar_cache
        cache = radar_cache.get_stats()
    except Exception:
        cache = {"enabled": False}
    
    # ── Determine overall status ──
    issues = []
    
    # Critical checks
    if mongo["status"] != "connected":
        issues.append(("CRITICAL", "MongoDB disconnected"))
    if resources["system"]["pct"] > 90:
        issues.append(("CRITICAL", f"System memory at {resources['system']['pct']}%"))
    
    # Degraded checks
    if node["status"] != "connected":
        issues.append(("DEGRADED", "Node.js backend disconnected"))
    if resources["system"]["pct"] > 70:
        issues.append(("DEGRADED", f"System memory at {resources['system']['pct']}%"))
    if radar.get("status") == "error":
        issues.append(("DEGRADED", "Radar engine error"))
    if radar.get("status") == "empty":
        issues.append(("DEGRADED", "Radar universe empty"))
    
    # Determine worst status
    has_critical = any(level == "CRITICAL" for level, _ in issues)
    has_degraded = any(level == "DEGRADED" for level, _ in issues)
    
    if has_critical:
        status = "CRITICAL"
    elif has_degraded:
        status = "DEGRADED"
    else:
        status = "HEALTHY"
    
    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_s": round(time.time() - _start_time, 0),
        "issues": [msg for _, msg in issues],
        "services": {
            "mongodb": mongo,
            "nodeBackend": node,
        },
        "radar": radar,
        "resources": resources,
        "pipelines": pipelines,
        "cache": cache,
        "rateLimiter": rate_limiter,
        "profile": os.environ.get("SYSTEM_PROFILE", "dev"),
    }
