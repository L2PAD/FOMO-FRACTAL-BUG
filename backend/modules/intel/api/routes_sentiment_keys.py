"""
Sentiment API Keys Admin Routes
===============================
Admin endpoints for managing Sentiment Analysis API keys.
Supports external sentiment services and internal LLM-based analysis.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/sentiment-keys", tags=["Sentiment API Admin"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ═══════════════════════════════════════════════════════════════
# SENTIMENT PROVIDER CONFIGURATION
# ═══════════════════════════════════════════════════════════════

class SentimentProvider(str, Enum):
    OPENAI = "openai"           # GPT-based sentiment
    ANTHROPIC = "anthropic"     # Claude-based sentiment
    HUGGINGFACE = "huggingface" # HuggingFace models
    CUSTOM = "custom"           # Custom API endpoint
    INTERNAL = "internal"       # Using existing LLM keys
    EMERGENT = "emergent"       # Emergent LLM Key (Universal)


SENTIMENT_PROVIDER_CONFIG = {
    SentimentProvider.EMERGENT: {
        "name": "Emergent (Universal Key)",
        "description": "Uses Emergent Universal LLM Key - works with OpenAI/Anthropic/Gemini",
        "capabilities": ["sentiment", "summary", "topics", "importance"],
        "models": ["gpt-4o-mini", "gpt-4o", "claude-3-sonnet"],
        "key_format": "Auto (from environment)",
        "docs_url": None,
        "cost_per_1k": 0.005
    },
    SentimentProvider.OPENAI: {
        "name": "OpenAI GPT",
        "description": "GPT-based sentiment analysis with summary generation",
        "capabilities": ["sentiment", "summary", "topics", "importance"],
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-5.2"],
        "key_format": "sk-...",
        "docs_url": "https://platform.openai.com/api-keys",
        "cost_per_1k": 0.01
    },
    SentimentProvider.ANTHROPIC: {
        "name": "Anthropic Claude",
        "description": "Claude-based sentiment analysis",
        "capabilities": ["sentiment", "summary", "topics"],
        "models": ["claude-3-haiku", "claude-3-sonnet", "claude-4-sonnet"],
        "key_format": "sk-ant-...",
        "docs_url": "https://console.anthropic.com/settings/keys",
        "cost_per_1k": 0.008
    },
    SentimentProvider.HUGGINGFACE: {
        "name": "HuggingFace",
        "description": "Open-source sentiment models (FinBERT, etc.)",
        "capabilities": ["sentiment", "topics"],
        "models": ["finbert", "distilbert-sentiment", "roberta-sentiment"],
        "key_format": "hf_...",
        "docs_url": "https://huggingface.co/settings/tokens",
        "cost_per_1k": 0.001
    },
    SentimentProvider.CUSTOM: {
        "name": "Custom API",
        "description": "Your own sentiment analysis endpoint",
        "capabilities": ["sentiment", "summary", "topics", "importance"],
        "models": ["custom"],
        "key_format": "Any",
        "docs_url": None,
        "cost_per_1k": 0
    },
    SentimentProvider.INTERNAL: {
        "name": "Internal (LLM Keys)",
        "description": "Uses existing LLM Keys for sentiment analysis",
        "capabilities": ["sentiment", "summary", "topics", "importance"],
        "models": ["Uses configured LLM"],
        "key_format": "N/A - Uses LLM Keys",
        "docs_url": None,
        "cost_per_1k": 0
    }
}


# ═══════════════════════════════════════════════════════════════
# SENTIMENT KEYS MANAGER
# ═══════════════════════════════════════════════════════════════

class SentimentKeysManager:
    """Manager for Sentiment API keys stored in MongoDB."""
    
    COLLECTION = "sentiment_keys"
    
    def __init__(self, db):
        self.db = db
    
    def _mask_key(self, key: str) -> str:
        """Mask API key for display."""
        if not key or len(key) < 8:
            return "****"
        return f"{key[:6]}...{key[-4:]}"
    
    async def get_keys(self, provider: Optional[str] = None) -> List[Dict]:
        """Get all sentiment keys."""
        query = {}
        if provider:
            query["provider"] = provider
        
        keys = []
        async for key in self.db[self.COLLECTION].find(query).sort("created_at", -1):
            keys.append({
                "id": str(key.get("_id", "")),
                "provider": key.get("provider"),
                "name": key.get("name"),
                "api_key_masked": self._mask_key(key.get("api_key", "")),
                "endpoint_url": key.get("endpoint_url"),  # For custom providers
                "model": key.get("model"),
                "is_default": key.get("is_default", False),
                "enabled": key.get("enabled", True),
                "healthy": key.get("healthy", True),
                "requests_total": key.get("requests_total", 0),
                "requests_today": key.get("requests_today", 0),
                "avg_latency_ms": key.get("avg_latency_ms", 0),
                "last_used_at": key.get("last_used_at"),
                "created_at": key.get("created_at")
            })
        
        return keys
    
    async def add_key(
        self, 
        provider: str, 
        api_key: str = None,
        name: Optional[str] = None,
        model: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        is_default: bool = False
    ) -> Dict[str, Any]:
        """Add a new sentiment key."""
        try:
            provider_enum = SentimentProvider(provider)
        except ValueError:
            return {"ok": False, "error": f"Invalid provider: {provider}"}
        
        config = SENTIMENT_PROVIDER_CONFIG.get(provider_enum, {})
        
        # For internal provider, no API key needed
        if provider == "internal":
            api_key = "internal"
        
        # Check for duplicate
        existing = await self.db[self.COLLECTION].find_one({
            "provider": provider,
            "api_key": api_key
        })
        if existing:
            return {"ok": False, "error": "Key already exists"}
        
        # If setting as default, unset other defaults
        if is_default:
            await self.db[self.COLLECTION].update_many(
                {"is_default": True},
                {"$set": {"is_default": False}}
            )
        
        now = datetime.now(timezone.utc)
        key_doc = {
            "provider": provider,
            "api_key": api_key or "",
            "name": name or f"{config.get('name', provider)} Sentiment",
            "model": model or (config.get("models", ["default"])[0]),
            "endpoint_url": endpoint_url,
            "is_default": is_default,
            "enabled": True,
            "healthy": True,
            "requests_total": 0,
            "requests_today": 0,
            "avg_latency_ms": 0,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
        result = await self.db[self.COLLECTION].insert_one(key_doc)
        
        logger.info(f"[SentimentKeys] Added {provider} key")
        
        return {
            "ok": True,
            "id": str(result.inserted_id),
            "provider": provider
        }
    
    async def remove_key(self, key_id: str) -> Dict[str, Any]:
        """Remove a sentiment key."""
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
    
    async def set_default(self, key_id: str) -> Dict[str, Any]:
        """Set a key as default."""
        from bson import ObjectId
        
        try:
            # Unset other defaults
            await self.db[self.COLLECTION].update_many(
                {"is_default": True},
                {"$set": {"is_default": False}}
            )
            
            # Set this key as default
            result = await self.db[self.COLLECTION].update_one(
                {"_id": ObjectId(key_id)},
                {"$set": {"is_default": True}}
            )
            
            if result.modified_count > 0:
                return {"ok": True}
            return {"ok": False, "error": "Key not found"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def get_default_key(self) -> Optional[Dict]:
        """Get the default sentiment key."""
        key = await self.db[self.COLLECTION].find_one({
            "enabled": True,
            "healthy": True,
            "is_default": True
        })
        
        if not key:
            # Get any available key
            key = await self.db[self.COLLECTION].find_one({
                "enabled": True,
                "healthy": True
            })
        
        if key:
            return {
                "id": str(key["_id"]),
                "provider": key["provider"],
                "api_key": key["api_key"],
                "model": key.get("model"),
                "endpoint_url": key.get("endpoint_url")
            }
        
        return None
    
    async def record_usage(self, key_id: str, latency_ms: int):
        """Record sentiment API usage."""
        if key_id == "internal":
            return
        
        from bson import ObjectId
        
        await self.db[self.COLLECTION].update_one(
            {"_id": ObjectId(key_id)},
            {
                "$inc": {"requests_total": 1, "requests_today": 1},
                "$set": {
                    "last_used_at": datetime.now(timezone.utc).isoformat(),
                    "avg_latency_ms": latency_ms  # Simplified - could be rolling avg
                }
            }
        )
    
    async def get_summary(self) -> Dict[str, Any]:
        """Get summary of sentiment keys."""
        pipeline = [
            {
                "$group": {
                    "_id": "$provider",
                    "total_keys": {"$sum": 1},
                    "enabled_keys": {"$sum": {"$cond": ["$enabled", 1, 0]}},
                    "requests_total": {"$sum": "$requests_total"},
                    "requests_today": {"$sum": "$requests_today"}
                }
            }
        ]
        
        results = await self.db[self.COLLECTION].aggregate(pipeline).to_list(10)
        
        return {
            "by_provider": {r["_id"]: r for r in results},
            "total_keys": sum(r["total_keys"] for r in results),
            "total_requests_today": sum(r["requests_today"] for r in results),
            "has_default": bool(await self.db[self.COLLECTION].find_one({"is_default": True}))
        }


# Singleton
_sentiment_keys_manager: Optional[SentimentKeysManager] = None


def get_sentiment_keys_manager(db) -> SentimentKeysManager:
    global _sentiment_keys_manager
    if _sentiment_keys_manager is None:
        _sentiment_keys_manager = SentimentKeysManager(db)
    return _sentiment_keys_manager


# ═══════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════

@router.get("/providers")
async def list_providers():
    """List all supported sentiment providers."""
    providers = []
    for provider_id, config in SENTIMENT_PROVIDER_CONFIG.items():
        providers.append({
            "id": provider_id.value,
            "name": config["name"],
            "description": config["description"],
            "capabilities": config["capabilities"],
            "models": config["models"],
            "key_format": config["key_format"],
            "docs_url": config["docs_url"],
            "cost_per_1k": config.get("cost_per_1k", 0)
        })
    
    return {
        "ts": ts_now(),
        "providers": providers
    }


@router.get("/summary")
async def get_summary():
    """Get summary of sentiment keys."""
    from server import db
    
    manager = get_sentiment_keys_manager(db)
    summary = await manager.get_summary()
    
    return {
        "ts": ts_now(),
        **summary
    }


@router.get("")
async def list_keys(provider: Optional[str] = Query(None)):
    """List all sentiment keys."""
    from server import db
    
    manager = get_sentiment_keys_manager(db)
    keys = await manager.get_keys(provider)
    
    return {
        "ts": ts_now(),
        "total": len(keys),
        "keys": keys
    }


@router.post("")
async def add_key(
    provider: str = Body(...),
    api_key: Optional[str] = Body(None),
    name: Optional[str] = Body(None),
    model: Optional[str] = Body(None),
    endpoint_url: Optional[str] = Body(None),
    is_default: bool = Body(False)
):
    """Add a new sentiment key."""
    from server import db
    
    manager = get_sentiment_keys_manager(db)
    result = await manager.add_key(provider, api_key, name, model, endpoint_url, is_default)
    
    if not result.get("ok"):
        raise HTTPException(400, result.get("error"))
    
    return {"ts": ts_now(), **result}


@router.delete("/{key_id}")
async def remove_key(key_id: str):
    """Remove a sentiment key."""
    from server import db
    
    manager = get_sentiment_keys_manager(db)
    result = await manager.remove_key(key_id)
    
    if not result.get("ok"):
        raise HTTPException(404, result.get("error"))
    
    return {"ts": ts_now(), **result}


@router.post("/{key_id}/toggle")
async def toggle_key(key_id: str, enabled: bool = Body(..., embed=True)):
    """Enable or disable a sentiment key."""
    from server import db
    
    manager = get_sentiment_keys_manager(db)
    result = await manager.toggle_key(key_id, enabled)
    
    if not result.get("ok"):
        raise HTTPException(400, result.get("error"))
    
    return {"ts": ts_now(), **result}


@router.post("/{key_id}/set-default")
async def set_default_key(key_id: str):
    """Set a key as default."""
    from server import db
    
    manager = get_sentiment_keys_manager(db)
    result = await manager.set_default(key_id)
    
    if not result.get("ok"):
        raise HTTPException(400, result.get("error"))
    
    return {"ts": ts_now(), **result}


@router.post("/reset-counters")
async def reset_daily_counters():
    """Reset daily request counters."""
    from server import db
    
    result = await db.sentiment_keys.update_many(
        {},
        {"$set": {"requests_today": 0}}
    )
    
    return {
        "ts": ts_now(),
        "ok": True,
        "reset_count": result.modified_count
    }


@router.post("/add-emergent")
async def add_emergent_provider():
    """
    Quick add Emergent provider using Universal Key from environment.
    One-click setup.
    """
    from server import db
    import os
    
    emergent_key = os.environ.get("EMERGENT_API_KEY") or os.environ.get("LLM_API_KEY")
    
    if not emergent_key:
        raise HTTPException(400, "Emergent API Key not found in environment")
    
    # Check if already exists
    existing = await db.sentiment_keys.find_one({"provider": "emergent"})
    if existing:
        return {
            "ts": ts_now(),
            "ok": True,
            "message": "Emergent provider already configured",
            "key_id": str(existing["_id"])
        }
    
    manager = get_sentiment_keys_manager(db)
    result = await manager.add_key(
        provider="emergent",
        api_key=emergent_key,
        name="Emergent Universal",
        model="gpt-4o-mini",
        endpoint_url=None,
        is_default=False
    )
    
    if not result.get("ok"):
        raise HTTPException(400, result.get("error"))
    
    return {
        "ts": ts_now(),
        **result,
        "message": "Emergent provider added successfully"
    }


@router.get("/emergent-status")
async def get_emergent_status():
    """Check if Emergent key is available and configured."""
    from server import db
    import os
    
    emergent_key = os.environ.get("EMERGENT_API_KEY") or os.environ.get("LLM_API_KEY")
    existing = await db.sentiment_keys.find_one({"provider": "emergent"})
    
    return {
        "ts": ts_now(),
        "key_available": bool(emergent_key),
        "configured": bool(existing),
        "key_id": str(existing["_id"]) if existing else None
    }

