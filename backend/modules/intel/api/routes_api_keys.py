"""
API Keys Admin Routes
=====================
Admin endpoints for managing API keys.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/api-keys", tags=["API Keys Admin"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ═══════════════════════════════════════════════════════════════
# SERVICES INFO
# ═══════════════════════════════════════════════════════════════

@router.get("/services")
async def list_services():
    """List supported services for API Keys (only services that require/use API keys)"""
    from modules.intel.api_keys_manager import SERVICE_CONFIG, ServiceType
    
    # Include services that benefit from API keys
    # Note: GitHub and Twitter removed - we don't parse them
    ALLOWED_SERVICES = [
        ServiceType.COINGECKO, 
        ServiceType.COINMARKETCAP, 
        ServiceType.MESSARI,
        ServiceType.OPENAI
    ]
    
    services = []
    for service_id in ALLOWED_SERVICES:
        config = SERVICE_CONFIG.get(service_id, {})
        services.append({
            "id": service_id.value if hasattr(service_id, 'value') else service_id,
            "name": config.get("name"),
            "base_url": config.get("base_url"),
            "key_required": config.get("key_required", False),
            "free_rate_limit": config.get("free_rate_limit"),
            "pro_rate_limit": config.get("pro_rate_limit"),
            "rate_limit_window": config.get("rate_limit_window", "minute"),
            "header_name": config.get("header_name"),
            "env_var": config.get("env_var"),
            "docs_url": config.get("docs_url"),
            "description": config.get("description", "")
        })
    
    return {
        "ts": ts_now(),
        "services": services
    }


@router.get("/summary")
async def get_summary():
    """Get summary of all API keys by service"""
    from server import db
    from modules.intel.api_keys_manager import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    summary = await manager.get_service_summary()
    
    return {
        "ts": ts_now(),
        "summary": summary
    }


# ═══════════════════════════════════════════════════════════════
# API KEYS CRUD
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def list_keys(
    service: Optional[str] = Query(None, description="Filter by service")
):
    """List all API keys (masked)"""
    from server import db
    from modules.intel.api_keys_manager import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    keys = await manager.get_keys(service)
    
    return {
        "ts": ts_now(),
        "total": len(keys),
        "keys": keys
    }


@router.post("")
async def add_key(
    service: str = Body(..., description="Service ID (coingecko, coinmarketcap, etc)"),
    api_key: str = Body(..., description="The API key"),
    name: Optional[str] = Body(None, description="Friendly name for the key"),
    is_pro: bool = Body(False, description="Is this a pro/paid tier key"),
    proxy_id: Optional[str] = Body(None, description="Bind to specific proxy ID")
):
    """Add a new API key"""
    from server import db
    from modules.intel.api_keys_manager import get_api_keys_manager, SERVICE_CONFIG
    
    # Validate service
    valid_services = [s.value if hasattr(s, 'value') else s for s in SERVICE_CONFIG.keys()]
    if service not in valid_services:
        raise HTTPException(400, f"Invalid service. Must be one of: {valid_services}")
    
    manager = get_api_keys_manager(db)
    result = await manager.add_key(service, api_key, name, is_pro, proxy_id)
    
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Failed to add key"))
    
    return {
        "ts": ts_now(),
        **result
    }


@router.delete("/{key_id}")
async def remove_key(key_id: str):
    """Remove an API key"""
    from server import db
    from modules.intel.api_keys_manager import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    result = await manager.remove_key(key_id)
    
    if not result.get("ok"):
        raise HTTPException(404, result.get("error", "Key not found"))
    
    return {
        "ts": ts_now(),
        **result
    }


@router.post("/{key_id}/toggle")
async def toggle_key(
    key_id: str,
    enabled: bool = Body(..., embed=True)
):
    """Enable or disable an API key"""
    from server import db
    from modules.intel.api_keys_manager import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    result = await manager.toggle_key(key_id, enabled)
    
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Failed to toggle key"))
    
    return {
        "ts": ts_now(),
        **result
    }


# ═══════════════════════════════════════════════════════════════
# HEALTH & MONITORING
# ═══════════════════════════════════════════════════════════════

@router.get("/{key_id}/stats")
async def get_key_stats(key_id: str):
    """Get detailed stats for an API key"""
    from server import db
    from modules.intel.api_keys_manager import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    stats = await manager.get_key_stats(key_id)
    
    if not stats:
        raise HTTPException(404, "Key not found")
    
    # Mask API key
    if "api_key" in stats:
        api_key = stats["api_key"]
        if len(api_key) > 8:
            stats["api_key_masked"] = f"{api_key[:4]}...{api_key[-4:]}"
        else:
            stats["api_key_masked"] = "****"
        del stats["api_key"]
    
    return {
        "ts": ts_now(),
        **stats
    }


@router.post("/{key_id}/health")
async def check_key_health(key_id: str):
    """Test if an API key is working"""
    from server import db
    from modules.intel.api_keys_manager import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    result = await manager.check_key_health(key_id)
    
    return {
        "ts": ts_now(),
        "key_id": key_id,
        **result
    }


@router.post("/health/all")
async def check_all_keys_health(
    service: Optional[str] = Query(None, description="Filter by service")
):
    """Check health of all API keys"""
    from server import db
    from modules.intel.api_keys_manager import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    result = await manager.check_all_keys_health(service)
    
    return {
        "ts": ts_now(),
        **result
    }


# ═══════════════════════════════════════════════════════════════
# USAGE STATS
# ═══════════════════════════════════════════════════════════════

@router.get("/usage/by-service")
async def get_usage_by_service():
    """Get request usage grouped by service"""
    from server import db
    
    pipeline = [
        {
            "$group": {
                "_id": "$service",
                "total_keys": {"$sum": 1},
                "requests_total": {"$sum": "$requests_total"},
                "requests_today": {"$sum": "$requests_today"},
                "requests_this_minute": {"$sum": "$requests_this_minute"}
            }
        },
        {"$sort": {"requests_total": -1}}
    ]
    
    results = await db.api_keys.aggregate(pipeline).to_list(20)
    
    return {
        "ts": ts_now(),
        "usage": [
            {
                "service": r["_id"],
                "total_keys": r["total_keys"],
                "requests_total": r["requests_total"],
                "requests_today": r["requests_today"],
                "requests_this_minute": r["requests_this_minute"]
            }
            for r in results
        ]
    }


@router.post("/reset-counters")
async def reset_daily_counters():
    """Reset daily request counters for all keys"""
    from server import db
    
    result = await db.api_keys.update_many(
        {},
        {"$set": {
            "requests_today": 0,
            "requests_this_minute": 0,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {
        "ts": ts_now(),
        "ok": True,
        "reset_count": result.modified_count
    }
