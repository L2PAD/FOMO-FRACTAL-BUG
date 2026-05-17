"""
API Keys Management System
==========================
Secure storage and management of API keys for third-party services.

Features:
- Encrypted storage in MongoDB (base64 encoded)
- Validation before saving
- Runtime access via environment fallback
- Health check for key validity
"""

import os
import base64
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class APIKeyConfig(BaseModel):
    """Configuration for an API key"""
    id: str
    name: str
    service: str
    description: str
    required: bool = False
    env_var: str
    docs_url: Optional[str] = None
    rate_limit: Optional[str] = None
    validation_endpoint: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# SUPPORTED API KEYS REGISTRY
# ═══════════════════════════════════════════════════════════════

API_KEYS_REGISTRY = [
    APIKeyConfig(
        id="github",
        name="GitHub Token",
        service="GitHub",
        description="Personal Access Token for GitHub API. Increases rate limit from 60 to 5000 requests/hour.",
        required=False,
        env_var="GITHUB_TOKEN",
        docs_url="https://github.com/settings/tokens",
        rate_limit="5000 req/hour (with token), 60 req/hour (without)",
        validation_endpoint="https://api.github.com/user"
    ),
    APIKeyConfig(
        id="coinmarketcap",
        name="CoinMarketCap API Key",
        service="CoinMarketCap",
        description="API key for CoinMarketCap market data.",
        required=False,
        env_var="CMC_API_KEY",
        docs_url="https://pro.coinmarketcap.com/account",
        rate_limit="30 req/min",
        validation_endpoint="https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    ),
    APIKeyConfig(
        id="messari",
        name="Messari API Key",
        service="Messari",
        description="API key for Messari research and metrics data.",
        required=False,
        env_var="MESSARI_API_KEY",
        docs_url="https://messari.io/api",
        rate_limit="20 req/min",
        validation_endpoint="https://data.messari.io/api/v1/assets"
    ),
    APIKeyConfig(
        id="twitter",
        name="Twitter/X Bearer Token",
        service="Twitter/X",
        description="Bearer token for Twitter API v2.",
        required=False,
        env_var="TWITTER_BEARER_TOKEN",
        docs_url="https://developer.twitter.com/en/portal/dashboard",
        rate_limit="Varies by endpoint"
    ),
    APIKeyConfig(
        id="openai",
        name="OpenAI API Key",
        service="OpenAI",
        description="API key for GPT models and embeddings.",
        required=False,
        env_var="OPENAI_API_KEY",
        docs_url="https://platform.openai.com/api-keys",
        rate_limit="Varies by tier"
    ),
    APIKeyConfig(
        id="coingecko",
        name="CoinGecko Pro API Key",
        service="CoinGecko",
        description="Pro API key for higher rate limits. Free tier works without key.",
        required=False,
        env_var="COINGECKO_API_KEY",
        docs_url="https://www.coingecko.com/en/api/pricing",
        rate_limit="500 req/min (Pro), 50 req/min (Free)"
    ),
    APIKeyConfig(
        id="dune",
        name="Dune Analytics API Key",
        service="Dune Analytics",
        description="API key for on-chain analytics queries.",
        required=False,
        env_var="DUNE_API_KEY",
        docs_url="https://dune.com/settings/api",
        rate_limit="10 req/min"
    ),
    APIKeyConfig(
        id="nansen",
        name="Nansen API Key",
        service="Nansen",
        description="API key for Nansen on-chain analytics.",
        required=False,
        env_var="NANSEN_API_KEY",
        docs_url="https://nansen.ai",
        rate_limit="Varies by plan"
    ),
    APIKeyConfig(
        id="glassnode",
        name="Glassnode API Key",
        service="Glassnode",
        description="API key for on-chain metrics.",
        required=False,
        env_var="GLASSNODE_API_KEY",
        docs_url="https://studio.glassnode.com/settings/api",
        rate_limit="10 req/min"
    ),
]


def _encode_key(key: str) -> str:
    """Encode API key for storage (base64)"""
    return base64.b64encode(key.encode()).decode()


def _decode_key(encoded: str) -> str:
    """Decode API key from storage"""
    return base64.b64decode(encoded.encode()).decode()


def _mask_key(key: str) -> str:
    """Mask API key for display (show first 4 and last 4 chars)"""
    if not key or len(key) < 12:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


class APIKeysManager:
    """Manager for API keys storage and retrieval"""
    
    def __init__(self, db):
        self.db = db
        self.collection = db.api_keys
        self._cache: Dict[str, str] = {}  # Runtime cache
        self._registry = {k.id: k for k in API_KEYS_REGISTRY}
    
    async def get_key(self, key_id: str) -> Optional[str]:
        """
        Get API key by ID.
        Priority: DB → Environment → None
        """
        # Check cache first
        if key_id in self._cache:
            return self._cache[key_id]
        
        # Check DB
        doc = await self.collection.find_one({"id": key_id})
        if doc and doc.get("value"):
            key = _decode_key(doc["value"])
            self._cache[key_id] = key
            return key
        
        # Fallback to environment
        config = self._registry.get(key_id)
        if config:
            env_key = os.environ.get(config.env_var)
            if env_key:
                self._cache[key_id] = env_key
                return env_key
        
        return None
    
    async def set_key(self, key_id: str, value: str) -> Dict[str, Any]:
        """Save or update an API key"""
        config = self._registry.get(key_id)
        if not config:
            return {"ok": False, "error": f"Unknown key ID: {key_id}"}
        
        now = datetime.now(timezone.utc).isoformat()
        
        doc = {
            "id": key_id,
            "name": config.name,
            "service": config.service,
            "env_var": config.env_var,
            "value": _encode_key(value),
            "masked": _mask_key(value),
            "is_set": True,
            "updated_at": now
        }
        
        await self.collection.update_one(
            {"id": key_id},
            {"$set": doc},
            upsert=True
        )
        
        # Update cache
        self._cache[key_id] = value
        
        # Also set in environment for current runtime
        os.environ[config.env_var] = value
        
        logger.info(f"[APIKeys] Set key: {key_id} ({_mask_key(value)})")
        
        return {
            "ok": True,
            "key_id": key_id,
            "masked": _mask_key(value)
        }
    
    async def delete_key(self, key_id: str) -> Dict[str, Any]:
        """Delete an API key"""
        result = await self.collection.delete_one({"id": key_id})
        
        # Clear cache
        if key_id in self._cache:
            del self._cache[key_id]
        
        # Clear environment
        config = self._registry.get(key_id)
        if config and config.env_var in os.environ:
            del os.environ[config.env_var]
        
        return {
            "ok": True,
            "deleted": result.deleted_count > 0
        }
    
    async def get_all_keys_status(self) -> List[Dict[str, Any]]:
        """Get status of all registered API keys"""
        result = []
        
        for config in API_KEYS_REGISTRY:
            # Check if key is set
            doc = await self.collection.find_one({"id": config.id})
            
            is_set_db = bool(doc and doc.get("value"))
            is_set_env = bool(os.environ.get(config.env_var))
            is_set = is_set_db or is_set_env
            
            status = {
                "id": config.id,
                "name": config.name,
                "service": config.service,
                "description": config.description,
                "required": config.required,
                "env_var": config.env_var,
                "docs_url": config.docs_url,
                "rate_limit": config.rate_limit,
                "is_set": is_set,
                "source": "database" if is_set_db else ("environment" if is_set_env else None),
                "masked": doc.get("masked") if doc else (_mask_key(os.environ.get(config.env_var, "")) if is_set_env else None),
                "updated_at": doc.get("updated_at") if doc else None
            }
            
            result.append(status)
        
        return result
    
    async def validate_key(self, key_id: str) -> Dict[str, Any]:
        """Validate an API key by making a test request"""
        import httpx
        
        config = self._registry.get(key_id)
        if not config:
            return {"ok": False, "error": f"Unknown key ID: {key_id}"}
        
        key = await self.get_key(key_id)
        if not key:
            return {"ok": False, "valid": False, "error": "Key not set"}
        
        if not config.validation_endpoint:
            return {"ok": True, "valid": None, "message": "No validation endpoint configured"}
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {}
                
                # Service-specific header setup
                if key_id == "github":
                    headers["Authorization"] = f"Bearer {key}"
                elif key_id == "coinmarketcap":
                    headers["X-CMC_PRO_API_KEY"] = key
                elif key_id == "messari":
                    headers["x-messari-api-key"] = key
                elif key_id == "twitter":
                    headers["Authorization"] = f"Bearer {key}"
                elif key_id == "coingecko":
                    headers["x-cg-pro-api-key"] = key
                
                resp = await client.get(config.validation_endpoint, headers=headers)
                
                valid = resp.status_code in [200, 201]
                
                # Update validation status in DB
                await self.collection.update_one(
                    {"id": key_id},
                    {"$set": {
                        "last_validated": datetime.now(timezone.utc).isoformat(),
                        "validation_status": "valid" if valid else "invalid",
                        "validation_code": resp.status_code
                    }}
                )
                
                return {
                    "ok": True,
                    "valid": valid,
                    "status_code": resp.status_code,
                    "message": "Key is valid" if valid else f"Validation failed: {resp.status_code}"
                }
                
        except Exception as e:
            return {
                "ok": False,
                "valid": False,
                "error": str(e)
            }
    
    async def load_keys_to_env(self):
        """Load all stored keys into environment variables"""
        docs = await self.collection.find({}).to_list(100)
        loaded = 0
        
        for doc in docs:
            config = self._registry.get(doc["id"])
            if config and doc.get("value"):
                key = _decode_key(doc["value"])
                os.environ[config.env_var] = key
                self._cache[doc["id"]] = key
                loaded += 1
        
        logger.info(f"[APIKeys] Loaded {loaded} keys to environment")
        return loaded


# Global manager instance
_manager: Optional[APIKeysManager] = None


def get_api_keys_manager(db) -> APIKeysManager:
    """Get or create API keys manager instance"""
    global _manager
    if _manager is None:
        _manager = APIKeysManager(db)
    return _manager


async def load_api_keys_on_startup(db):
    """Load API keys from DB to environment on startup"""
    manager = get_api_keys_manager(db)
    return await manager.load_keys_to_env()
