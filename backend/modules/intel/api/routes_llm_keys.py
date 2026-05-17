"""
LLM Keys Admin Routes
=====================
Admin endpoints for managing LLM API keys (OpenAI, Anthropic, Gemini, etc.)
Used for text generation, image generation, and sentiment analysis in News Intelligence.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/llm-keys", tags=["LLM Keys Admin"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ═══════════════════════════════════════════════════════════════
# LLM PROVIDER CONFIGURATION
# ═══════════════════════════════════════════════════════════════

class LLMProvider(str, Enum):
    OPENAI = "openai"


# Provider configurations - Only OpenAI
LLM_PROVIDER_CONFIG = {
    LLMProvider.OPENAI: {
        "name": "OpenAI",
        "description": "GPT models for text, images, and sentiment analysis",
        "capabilities": ["text", "image", "audio", "video", "sentiment"],
        "models": {
            "text": ["gpt-4o", "gpt-4o-mini", "gpt-5.2"],
            "image": ["dall-e-3", "gpt-image-1"],
            "audio": ["whisper-1", "tts-1"],
            "video": ["sora-2"],
            "sentiment": ["gpt-4o", "gpt-4o-mini"]
        },
        "key_format": "sk-...",
        "key_prefix": "sk-",
        "test_endpoint": "https://api.openai.com/v1/models",
        "docs_url": "https://platform.openai.com/api-keys"
    }
}


# ═══════════════════════════════════════════════════════════════
# LLM KEYS MANAGER
# ═══════════════════════════════════════════════════════════════

class LLMKeysManager:
    """Manager for LLM API keys stored in MongoDB."""
    
    COLLECTION = "llm_keys"
    
    def __init__(self, db):
        self.db = db
    
    def _mask_key(self, key: str) -> str:
        """Mask API key for display."""
        if not key or len(key) < 8:
            return "****"
        return f"{key[:6]}...{key[-4:]}"
    
    async def get_keys(self, provider: Optional[str] = None, capability: Optional[str] = None) -> List[Dict]:
        """Get all LLM keys, optionally filtered."""
        query = {}
        if provider:
            query["provider"] = provider
        if capability:
            query["capabilities"] = capability
        
        keys = []
        async for key in self.db[self.COLLECTION].find(query).sort("created_at", -1):
            keys.append({
                "id": str(key.get("_id", "")),
                "provider": key.get("provider"),
                "name": key.get("name"),
                "api_key_masked": self._mask_key(key.get("api_key", "")),
                "capabilities": key.get("capabilities", []),
                "is_default": key.get("is_default", False),
                "enabled": key.get("enabled", True),
                "healthy": key.get("healthy", True),
                "requests_total": key.get("requests_total", 0),
                "requests_today": key.get("requests_today", 0),
                "last_used_at": key.get("last_used_at"),
                "last_error": key.get("last_error"),
                "created_at": key.get("created_at")
            })
        
        return keys
    
    async def add_key(
        self, 
        provider: str, 
        api_key: str, 
        name: Optional[str] = None,
        capabilities: List[str] = None,
        is_default: bool = False
    ) -> Dict[str, Any]:
        """Add a new LLM key."""
        # Validate provider
        try:
            provider_enum = LLMProvider(provider)
        except ValueError:
            return {"ok": False, "error": f"Invalid provider: {provider}"}
        
        config = LLM_PROVIDER_CONFIG.get(provider_enum, {})
        
        # Default capabilities from config
        if not capabilities:
            capabilities = config.get("capabilities", ["text"])
        
        # Check for duplicate
        existing = await self.db[self.COLLECTION].find_one({
            "provider": provider,
            "api_key": api_key
        })
        if existing:
            return {"ok": False, "error": "Key already exists"}
        
        # If setting as default, unset other defaults for same provider+capabilities
        if is_default:
            for cap in capabilities:
                await self.db[self.COLLECTION].update_many(
                    {"provider": provider, "capabilities": cap, "is_default": True},
                    {"$set": {"is_default": False}}
                )
        
        now = datetime.now(timezone.utc)
        key_doc = {
            "provider": provider,
            "api_key": api_key,
            "name": name or f"{config.get('name', provider)} Key",
            "capabilities": capabilities,
            "is_default": is_default,
            "enabled": True,
            "healthy": True,
            "requests_total": 0,
            "requests_today": 0,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
        result = await self.db[self.COLLECTION].insert_one(key_doc)
        
        logger.info(f"[LLMKeys] Added {provider} key: {self._mask_key(api_key)}")
        
        return {
            "ok": True,
            "id": str(result.inserted_id),
            "provider": provider,
            "message": f"Key added successfully"
        }
    
    async def remove_key(self, key_id: str) -> Dict[str, Any]:
        """Remove an LLM key."""
        from bson import ObjectId
        
        try:
            result = await self.db[self.COLLECTION].delete_one({"_id": ObjectId(key_id)})
            if result.deleted_count > 0:
                return {"ok": True, "message": "Key removed"}
            return {"ok": False, "error": "Key not found"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def toggle_key(self, key_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable a key."""
        from bson import ObjectId
        
        try:
            result = await self.db[self.COLLECTION].update_one(
                {"_id": ObjectId(key_id)},
                {"$set": {"enabled": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            if result.modified_count > 0:
                return {"ok": True, "enabled": enabled}
            return {"ok": False, "error": "Key not found"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def set_default(self, key_id: str, capability: str) -> Dict[str, Any]:
        """Set a key as default for a capability."""
        from bson import ObjectId
        
        try:
            # Get the key
            key = await self.db[self.COLLECTION].find_one({"_id": ObjectId(key_id)})
            if not key:
                return {"ok": False, "error": "Key not found"}
            
            # Unset other defaults for same provider+capability
            await self.db[self.COLLECTION].update_many(
                {"provider": key["provider"], "capabilities": capability, "is_default": True},
                {"$set": {"is_default": False}}
            )
            
            # Set this key as default
            await self.db[self.COLLECTION].update_one(
                {"_id": ObjectId(key_id)},
                {"$set": {"is_default": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            
            return {"ok": True, "message": f"Key set as default for {capability}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def get_key_for_capability(self, capability: str, provider: Optional[str] = None, 
                                       exclude_keys: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the best available key for a capability with fallback support.
        Returns key dict with id and api_key for tracking.
        """
        query = {
            "enabled": True,
            "healthy": True,
            "capabilities": capability
        }
        
        if provider:
            query["provider"] = provider
        
        if exclude_keys:
            from bson import ObjectId
            query["_id"] = {"$nin": [ObjectId(k) for k in exclude_keys]}
        
        # Try to get default key first
        key = await self.db[self.COLLECTION].find_one({**query, "is_default": True})
        
        if not key:
            # Get any available key, preferring ones with fewer requests and errors
            async for k in self.db[self.COLLECTION].find(query).sort([
                ("error_count", 1),
                ("requests_today", 1)
            ]).limit(1):
                key = k
                break
        
        if key:
            # Update usage
            await self.db[self.COLLECTION].update_one(
                {"_id": key["_id"]},
                {
                    "$inc": {"requests_total": 1, "requests_today": 1},
                    "$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}
                }
            )
            return {
                "id": str(key["_id"]),
                "api_key": key.get("api_key"),
                "provider": key.get("provider"),
                "name": key.get("name")
            }
        
        # Fallback to environment variable
        env_key = os.getenv("EMERGENT_LLM_KEY") or os.getenv("OPENAI_API_KEY")
        if env_key:
            return {
                "id": "env_fallback",
                "api_key": env_key,
                "provider": "emergent",
                "name": "Environment Fallback"
            }
        
        return None
    
    async def get_key_with_fallback(self, capability: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Get a key with automatic fallback on failure.
        Tries multiple keys if one fails.
        """
        excluded = []
        
        for attempt in range(max_retries):
            key_info = await self.get_key_for_capability(capability, exclude_keys=excluded)
            
            if not key_info:
                logger.warning(f"[LLMKeys] No more keys available for {capability} after {attempt} attempts")
                break
            
            # Return the key - caller should use record_success/record_error
            return {
                **key_info,
                "attempt": attempt + 1,
                "excluded_count": len(excluded)
            }
        
        return None
    
    async def record_success(self, key_id: str, latency_ms: int = 0, tokens_used: int = 0):
        """Record successful API call."""
        if key_id == "env_fallback":
            return
        
        from bson import ObjectId
        now = datetime.now(timezone.utc)
        
        await self.db[self.COLLECTION].update_one(
            {"_id": ObjectId(key_id)},
            {
                "$set": {
                    "healthy": True,
                    "last_success_at": now.isoformat(),
                    "last_latency_ms": latency_ms
                },
                "$inc": {
                    "success_count": 1,
                    "tokens_used_total": tokens_used
                },
                "$push": {
                    "recent_latencies": {
                        "$each": [latency_ms],
                        "$slice": -100  # Keep last 100
                    }
                }
            }
        )
        
        # Record to analytics collection
        await self._record_analytics(key_id, "success", latency_ms, tokens_used)
    
    async def record_error(self, key_id: str, error: str, error_code: str = None):
        """Record an error for a key."""
        if key_id == "env_fallback":
            return
        
        from bson import ObjectId
        now = datetime.now(timezone.utc)
        
        # Increment error count
        result = await self.db[self.COLLECTION].find_one_and_update(
            {"_id": ObjectId(key_id)},
            {
                "$set": {
                    "last_error": error,
                    "last_error_at": now.isoformat(),
                    "last_error_code": error_code
                },
                "$inc": {"error_count": 1}
            },
            return_document=True
        )
        
        # Mark as unhealthy if too many errors
        if result and result.get("error_count", 0) >= 5:
            error_rate = result.get("error_count", 0) / max(1, result.get("requests_total", 1))
            if error_rate > 0.3:  # 30% error rate
                await self.db[self.COLLECTION].update_one(
                    {"_id": ObjectId(key_id)},
                    {"$set": {"healthy": False}}
                )
                logger.warning(f"[LLMKeys] Key {key_id} marked unhealthy (error rate: {error_rate:.1%})")
        
        # Record to analytics
        await self._record_analytics(key_id, "error", error_code=error_code)
    
    async def _record_analytics(self, key_id: str, event_type: str, latency_ms: int = 0, 
                                 tokens_used: int = 0, error_code: str = None):
        """Record analytics event."""
        now = datetime.now(timezone.utc)
        
        await self.db["llm_analytics"].insert_one({
            "key_id": key_id,
            "event_type": event_type,
            "latency_ms": latency_ms,
            "tokens_used": tokens_used,
            "error_code": error_code,
            "timestamp": now.isoformat(),
            "hour": now.strftime("%Y-%m-%d-%H"),
            "day": now.strftime("%Y-%m-%d")
        })
    
    async def get_analytics(self, key_id: str = None, hours: int = 24) -> Dict[str, Any]:
        """Get analytics for keys."""
        from datetime import timedelta
        
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=hours)
        
        query = {"timestamp": {"$gte": start_time.isoformat()}}
        if key_id:
            query["key_id"] = key_id
        
        # Aggregate by hour
        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": {
                        "hour": "$hour",
                        "event_type": "$event_type"
                    },
                    "count": {"$sum": 1},
                    "avg_latency": {"$avg": "$latency_ms"},
                    "total_tokens": {"$sum": "$tokens_used"}
                }
            },
            {"$sort": {"_id.hour": 1}}
        ]
        
        results = await self.db["llm_analytics"].aggregate(pipeline).to_list(500)
        
        # Organize by hour
        hourly_data = {}
        for r in results:
            hour = r["_id"]["hour"]
            event_type = r["_id"]["event_type"]
            
            if hour not in hourly_data:
                hourly_data[hour] = {"success": 0, "error": 0, "avg_latency": 0, "tokens": 0}
            
            hourly_data[hour][event_type] = r["count"]
            if event_type == "success":
                hourly_data[hour]["avg_latency"] = r["avg_latency"] or 0
                hourly_data[hour]["tokens"] = r["total_tokens"] or 0
        
        # Get totals
        total_success = sum(h.get("success", 0) for h in hourly_data.values())
        total_error = sum(h.get("error", 0) for h in hourly_data.values())
        total_tokens = sum(h.get("tokens", 0) for h in hourly_data.values())
        
        return {
            "period_hours": hours,
            "total_requests": total_success + total_error,
            "success_count": total_success,
            "error_count": total_error,
            "success_rate": total_success / max(1, total_success + total_error),
            "total_tokens": total_tokens,
            "hourly": [
                {"hour": k, **v} for k, v in sorted(hourly_data.items())
            ]
        }
    
    async def get_key_analytics(self, key_id: str) -> Dict[str, Any]:
        """Get detailed analytics for a specific key."""
        from bson import ObjectId
        
        key = await self.db[self.COLLECTION].find_one({"_id": ObjectId(key_id)})
        if not key:
            return {"error": "Key not found"}
        
        # Get recent analytics
        analytics = await self.get_analytics(key_id, hours=24)
        
        # Calculate metrics
        recent_latencies = key.get("recent_latencies", [])
        avg_latency = sum(recent_latencies) / len(recent_latencies) if recent_latencies else 0
        p95_latency = sorted(recent_latencies)[int(len(recent_latencies) * 0.95)] if len(recent_latencies) > 20 else avg_latency
        
        return {
            "key_id": key_id,
            "provider": key.get("provider"),
            "name": key.get("name"),
            "requests_total": key.get("requests_total", 0),
            "requests_today": key.get("requests_today", 0),
            "success_count": key.get("success_count", 0),
            "error_count": key.get("error_count", 0),
            "tokens_used_total": key.get("tokens_used_total", 0),
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(p95_latency, 2),
            "last_success_at": key.get("last_success_at"),
            "last_error_at": key.get("last_error_at"),
            "last_error": key.get("last_error"),
            "healthy": key.get("healthy", True),
            "enabled": key.get("enabled", True),
            "analytics_24h": analytics
        }
    
    async def get_summary(self) -> Dict[str, Any]:
        """Get summary of all LLM keys."""
        pipeline = [
            {
                "$group": {
                    "_id": "$provider",
                    "total_keys": {"$sum": 1},
                    "enabled_keys": {"$sum": {"$cond": ["$enabled", 1, 0]}},
                    "healthy_keys": {"$sum": {"$cond": ["$healthy", 1, 0]}},
                    "requests_total": {"$sum": "$requests_total"},
                    "requests_today": {"$sum": "$requests_today"}
                }
            }
        ]
        
        results = await self.db[self.COLLECTION].aggregate(pipeline).to_list(10)
        
        # Get capability coverage
        capabilities_coverage = {}
        for cap in ["text", "image", "audio", "video"]:
            count = await self.db[self.COLLECTION].count_documents({
                "capabilities": cap, "enabled": True, "healthy": True
            })
            capabilities_coverage[cap] = count
        
        return {
            "by_provider": {r["_id"]: r for r in results},
            "capabilities_coverage": capabilities_coverage,
            "total_keys": sum(r["total_keys"] for r in results),
            "total_requests_today": sum(r["requests_today"] for r in results)
        }


# Singleton manager
_llm_keys_manager: Optional[LLMKeysManager] = None


def get_llm_keys_manager(db) -> LLMKeysManager:
    """Get or create LLM keys manager singleton."""
    global _llm_keys_manager
    if _llm_keys_manager is None:
        _llm_keys_manager = LLMKeysManager(db)
    return _llm_keys_manager


# ═══════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════

@router.get("/providers")
async def list_providers():
    """List all supported LLM providers and their capabilities."""
    providers = []
    for provider_id, config in LLM_PROVIDER_CONFIG.items():
        providers.append({
            "id": provider_id.value,
            "name": config["name"],
            "description": config["description"],
            "capabilities": config["capabilities"],
            "models": config["models"],
            "key_format": config["key_format"],
            "docs_url": config["docs_url"]
        })
    
    return {
        "ts": ts_now(),
        "providers": providers
    }


@router.get("/summary")
async def get_summary():
    """Get summary of all LLM keys."""
    from server import db
    
    manager = get_llm_keys_manager(db)
    summary = await manager.get_summary()
    
    # Check for Emergent key in environment
    emergent_key = os.getenv("EMERGENT_LLM_KEY")
    
    return {
        "ts": ts_now(),
        "emergent_key_configured": bool(emergent_key),
        **summary
    }


@router.get("")
async def list_keys(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    capability: Optional[str] = Query(None, description="Filter by capability (text, image, audio, video)")
):
    """List all LLM keys."""
    from server import db
    
    manager = get_llm_keys_manager(db)
    keys = await manager.get_keys(provider, capability)
    
    return {
        "ts": ts_now(),
        "total": len(keys),
        "keys": keys
    }


@router.post("")
async def add_key(
    provider: str = Body(..., description="Provider: openai, anthropic, google, emergent"),
    api_key: str = Body(..., description="The API key"),
    name: Optional[str] = Body(None, description="Friendly name"),
    capabilities: List[str] = Body(None, description="Capabilities: text, image, audio, video"),
    is_default: bool = Body(False, description="Set as default for capabilities")
):
    """Add a new LLM key."""
    from server import db
    
    manager = get_llm_keys_manager(db)
    result = await manager.add_key(provider, api_key, name, capabilities, is_default)
    
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Failed to add key"))
    
    return {
        "ts": ts_now(),
        **result
    }


@router.delete("/{key_id}")
async def remove_key(key_id: str):
    """Remove an LLM key."""
    from server import db
    
    manager = get_llm_keys_manager(db)
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
    """Enable or disable an LLM key."""
    from server import db
    
    manager = get_llm_keys_manager(db)
    result = await manager.toggle_key(key_id, enabled)
    
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Failed to toggle key"))
    
    return {
        "ts": ts_now(),
        **result
    }


@router.post("/{key_id}/set-default")
async def set_default_key(
    key_id: str,
    capability: str = Body(..., embed=True, description="Capability: text, image, audio, video")
):
    """Set a key as default for a capability."""
    from server import db
    
    manager = get_llm_keys_manager(db)
    result = await manager.set_default(key_id, capability)
    
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Failed to set default"))
    
    return {
        "ts": ts_now(),
        **result
    }


@router.post("/{key_id}/test")
async def test_key(key_id: str):
    """Test if an LLM key is working."""
    from server import db
    from bson import ObjectId
    import httpx
    
    key = await db.llm_keys.find_one({"_id": ObjectId(key_id)})
    if not key:
        raise HTTPException(404, "Key not found")
    
    provider = key.get("provider")
    api_key = key.get("api_key")
    config = LLM_PROVIDER_CONFIG.get(LLMProvider(provider), {})
    test_url = config.get("test_endpoint")
    
    result = {"ok": False, "provider": provider}
    
    if not test_url:
        # For Emergent, just verify key exists
        result["ok"] = bool(api_key)
        result["message"] = "Emergent key configured" if api_key else "No key"
    else:
        try:
            async with httpx.AsyncClient() as client:
                headers = {}
                if provider == "openai":
                    headers["Authorization"] = f"Bearer {api_key}"
                elif provider == "anthropic":
                    headers["x-api-key"] = api_key
                    headers["anthropic-version"] = "2023-06-01"
                elif provider == "google":
                    test_url = f"{test_url}?key={api_key}"
                
                resp = await client.get(test_url, headers=headers, timeout=10)
                
                if resp.status_code in [200, 201]:
                    result["ok"] = True
                    result["message"] = "Key is valid"
                    await db.llm_keys.update_one(
                        {"_id": ObjectId(key_id)},
                        {"$set": {"healthy": True, "last_tested_at": datetime.now(timezone.utc).isoformat()}}
                    )
                else:
                    result["message"] = f"API returned {resp.status_code}"
                    result["error"] = resp.text[:200]
                    await db.llm_keys.update_one(
                        {"_id": ObjectId(key_id)},
                        {"$set": {"healthy": False, "last_error": result["message"]}}
                    )
        except Exception as e:
            result["error"] = str(e)
            await db.llm_keys.update_one(
                {"_id": ObjectId(key_id)},
                {"$set": {"healthy": False, "last_error": str(e)}}
            )
    
    return {
        "ts": ts_now(),
        "key_id": key_id,
        **result
    }


@router.post("/reset-counters")
async def reset_daily_counters():
    """Reset daily request counters for all LLM keys."""
    from server import db
    
    result = await db.llm_keys.update_many(
        {},
        {"$set": {"requests_today": 0, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {
        "ts": ts_now(),
        "ok": True,
        "reset_count": result.modified_count
    }


# ═══════════════════════════════════════════════════════════════
# ANALYTICS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/analytics/overview")
async def get_analytics_overview(hours: int = Query(default=24, le=168)):
    """
    Get analytics overview for all LLM keys.
    Shows success/error rates, latency, token usage.
    """
    from server import db
    
    manager = get_llm_keys_manager(db)
    analytics = await manager.get_analytics(hours=hours)
    
    return {
        "ts": ts_now(),
        **analytics
    }


@router.get("/analytics/by-provider")
async def get_analytics_by_provider(hours: int = Query(default=24, le=168)):
    """Get analytics grouped by provider."""
    from server import db
    from datetime import timedelta
    
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)
    
    # Aggregate analytics by provider
    pipeline = [
        {"$match": {"timestamp": {"$gte": start_time.isoformat()}}},
        {
            "$lookup": {
                "from": "llm_keys",
                "let": {"key_id": {"$toObjectId": "$key_id"}},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$key_id"]}}}
                ],
                "as": "key_info"
            }
        },
        {"$unwind": {"path": "$key_info", "preserveNullAndEmptyArrays": True}},
        {
            "$group": {
                "_id": "$key_info.provider",
                "total_requests": {"$sum": 1},
                "success_count": {"$sum": {"$cond": [{"$eq": ["$event_type", "success"]}, 1, 0]}},
                "error_count": {"$sum": {"$cond": [{"$eq": ["$event_type", "error"]}, 1, 0]}},
                "avg_latency": {"$avg": "$latency_ms"},
                "total_tokens": {"$sum": "$tokens_used"}
            }
        },
        {"$sort": {"total_requests": -1}}
    ]
    
    try:
        results = await db.llm_analytics.aggregate(pipeline).to_list(20)
    except Exception:
        # If collection doesn't exist or is empty
        results = []
    
    providers_data = []
    for r in results:
        provider = r["_id"] or "unknown"
        total = r["total_requests"]
        success = r["success_count"]
        
        providers_data.append({
            "provider": provider,
            "total_requests": total,
            "success_count": success,
            "error_count": r["error_count"],
            "success_rate": success / max(1, total),
            "avg_latency_ms": round(r["avg_latency"] or 0, 2),
            "total_tokens": r["total_tokens"] or 0
        })
    
    return {
        "ts": ts_now(),
        "period_hours": hours,
        "providers": providers_data
    }


@router.get("/analytics/hourly")
async def get_hourly_analytics(hours: int = Query(default=24, le=168)):
    """Get hourly analytics for charts."""
    from server import db
    from datetime import timedelta
    
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)
    
    pipeline = [
        {"$match": {"timestamp": {"$gte": start_time.isoformat()}}},
        {
            "$group": {
                "_id": "$hour",
                "requests": {"$sum": 1},
                "success": {"$sum": {"$cond": [{"$eq": ["$event_type", "success"]}, 1, 0]}},
                "errors": {"$sum": {"$cond": [{"$eq": ["$event_type", "error"]}, 1, 0]}},
                "avg_latency": {"$avg": "$latency_ms"},
                "tokens": {"$sum": "$tokens_used"}
            }
        },
        {"$sort": {"_id": 1}}
    ]
    
    try:
        results = await db.llm_analytics.aggregate(pipeline).to_list(200)
    except Exception:
        results = []
    
    return {
        "ts": ts_now(),
        "period_hours": hours,
        "data": [
            {
                "hour": r["_id"],
                "requests": r["requests"],
                "success": r["success"],
                "errors": r["errors"],
                "success_rate": r["success"] / max(1, r["requests"]),
                "avg_latency_ms": round(r["avg_latency"] or 0, 2),
                "tokens": r["tokens"] or 0
            }
            for r in results
        ]
    }


@router.get("/analytics/{key_id}")
async def get_key_analytics(key_id: str):
    """Get detailed analytics for a specific key."""
    from server import db
    
    manager = get_llm_keys_manager(db)
    analytics = await manager.get_key_analytics(key_id)
    
    if "error" in analytics:
        raise HTTPException(404, analytics["error"])
    
    return {
        "ts": ts_now(),
        **analytics
    }


@router.post("/{key_id}/reset-health")
async def reset_key_health(key_id: str):
    """Reset key health status and error count."""
    from server import db
    from bson import ObjectId
    
    result = await db.llm_keys.update_one(
        {"_id": ObjectId(key_id)},
        {
            "$set": {
                "healthy": True,
                "error_count": 0,
                "last_error": None,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(404, "Key not found")
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Key health reset"
    }


# ═══════════════════════════════════════════════════════════════
# FALLBACK HELPER FUNCTION (for use by other modules)
# ═══════════════════════════════════════════════════════════════

async def get_llm_key_with_fallback(db, capability: str, max_retries: int = 3) -> Optional[Dict]:
    """
    Helper function to get LLM key with automatic fallback.
    Use this from story_builder.py and image_generator.py
    """
    manager = get_llm_keys_manager(db)
    return await manager.get_key_with_fallback(capability, max_retries)


async def record_llm_success(db, key_id: str, latency_ms: int = 0, tokens_used: int = 0):
    """Record successful LLM API call."""
    manager = get_llm_keys_manager(db)
    await manager.record_success(key_id, latency_ms, tokens_used)


async def record_llm_error(db, key_id: str, error: str, error_code: str = None):
    """Record failed LLM API call."""
    manager = get_llm_keys_manager(db)
    await manager.record_error(key_id, error, error_code)
