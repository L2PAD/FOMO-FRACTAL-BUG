"""
Admin API Routes
================
API endpoints for admin panel: API keys management, system settings.
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class SetKeyRequest(BaseModel):
    value: str


# ═══════════════════════════════════════════════════════════════
# API KEYS MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.get("/keys")
async def get_all_api_keys():
    """Get status of all API keys"""
    from server import db
    from modules.admin.api_keys import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    keys = await manager.get_all_keys_status()
    
    # Group by category - GitHub and Twitter removed (we don't parse them)
    categories = {
        "market_data": ["coingecko", "coinmarketcap"],
        "research": ["messari", "dune", "nansen", "glassnode"],
        "ai": ["openai"]
    }
    
    grouped = {}
    for cat, ids in categories.items():
        grouped[cat] = [k for k in keys if k["id"] in ids]
    
    # Add uncategorized
    categorized_ids = set(id for ids in categories.values() for id in ids)
    grouped["other"] = [k for k in keys if k["id"] not in categorized_ids]
    
    return {
        "ts": ts_now(),
        "keys": keys,
        "grouped": grouped,
        "total": len(keys),
        "configured": sum(1 for k in keys if k["is_set"])
    }


@router.get("/keys/{key_id}")
async def get_api_key(key_id: str):
    """Get status of specific API key"""
    from server import db
    from modules.admin.api_keys import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    keys = await manager.get_all_keys_status()
    
    key = next((k for k in keys if k["id"] == key_id), None)
    if not key:
        raise HTTPException(404, f"Key {key_id} not found")
    
    return {
        "ts": ts_now(),
        **key
    }


@router.post("/keys/{key_id}")
async def set_api_key(key_id: str, request: SetKeyRequest):
    """Set or update an API key"""
    from server import db
    from modules.admin.api_keys import get_api_keys_manager
    
    if not request.value or len(request.value) < 5:
        raise HTTPException(400, "Invalid key value")
    
    manager = get_api_keys_manager(db)
    result = await manager.set_key(key_id, request.value)
    
    if not result["ok"]:
        raise HTTPException(400, result.get("error", "Failed to set key"))
    
    return {
        "ts": ts_now(),
        **result
    }


@router.delete("/keys/{key_id}")
async def delete_api_key(key_id: str):
    """Delete an API key"""
    from server import db
    from modules.admin.api_keys import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    result = await manager.delete_key(key_id)
    
    return {
        "ts": ts_now(),
        **result
    }


@router.post("/keys/{key_id}/validate")
async def validate_api_key(key_id: str):
    """Validate an API key by testing the connection"""
    from server import db
    from modules.admin.api_keys import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    result = await manager.validate_key(key_id)
    
    return {
        "ts": ts_now(),
        **result
    }


@router.post("/keys/reload")
async def reload_api_keys():
    """Reload all API keys from database to environment"""
    from server import db
    from modules.admin.api_keys import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    loaded = await manager.load_keys_to_env()
    
    return {
        "ts": ts_now(),
        "ok": True,
        "loaded": loaded,
        "message": f"Loaded {loaded} API keys to environment"
    }


# ═══════════════════════════════════════════════════════════════
# SYSTEM STATUS
# ═══════════════════════════════════════════════════════════════

@router.get("/status")
async def get_admin_status():
    """Get overall admin/system status"""
    from server import db
    from modules.admin.api_keys import get_api_keys_manager
    
    manager = get_api_keys_manager(db)
    keys = await manager.get_all_keys_status()
    
    # Count data sources
    data_sources = await db.data_sources.find({}).to_list(100)
    active_sources = [s for s in data_sources if s.get("status") == "active"]
    
    return {
        "ts": ts_now(),
        "api_keys": {
            "total": len(keys),
            "configured": sum(1 for k in keys if k["is_set"]),
            "required_missing": sum(1 for k in keys if k["required"] and not k["is_set"])
        },
        "data_sources": {
            "total": len(data_sources),
            "active": len(active_sources)
        }
    }
