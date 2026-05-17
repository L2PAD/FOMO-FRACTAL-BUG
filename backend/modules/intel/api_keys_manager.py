"""
API Keys Manager
================
Manage multiple API keys for external services with:
- Round-robin load balancing
- Rate limit tracking
- Health monitoring
- Auto-failover

Supported services:
- CoinGecko (free tier: 10-30 req/min)
- CoinMarketCap (free tier: 333 req/day)
- Messari (free tier: 20 req/min)
- DefiLlama (no key needed, but track usage)
- CryptoRank (no key needed)
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import httpx

logger = logging.getLogger(__name__)


class ServiceType(str, Enum):
    COINGECKO = "coingecko"
    COINMARKETCAP = "coinmarketcap"
    MESSARI = "messari"
    DEFILLAMA = "defillama"
    CRYPTORANK = "cryptorank"
    ROOTDATA = "rootdata"
    TOKENUNLOCKS = "tokenunlocks"
    GITHUB = "github"
    TWITTER = "twitter"
    OPENAI = "openai"


# Service configurations
SERVICE_CONFIG = {
    ServiceType.COINGECKO: {
        "name": "CoinGecko",
        "base_url": "https://api.coingecko.com/api/v3",
        "pro_url": "https://pro-api.coingecko.com/api/v3",
        "header_name": "x-cg-demo-api-key",  # or x-cg-pro-api-key for pro
        "free_rate_limit": 30,  # requests per minute
        "pro_rate_limit": 500,
        "test_endpoint": "/ping",
        "key_required": False,
        "env_var": "COINGECKO_API_KEY",
        "docs_url": "https://www.coingecko.com/en/api/pricing"
    },
    ServiceType.COINMARKETCAP: {
        "name": "CoinMarketCap",
        "base_url": "https://pro-api.coinmarketcap.com/v1",
        "header_name": "X-CMC_PRO_API_KEY",
        "free_rate_limit": 333,  # requests per day
        "rate_limit_window": "day",
        "test_endpoint": "/cryptocurrency/map?limit=1",
        "key_required": True,
        "env_var": "CMC_API_KEY",
        "docs_url": "https://pro.coinmarketcap.com/account"
    },
    ServiceType.MESSARI: {
        "name": "Messari",
        "base_url": "https://data.messari.io/api",
        "header_name": "x-messari-api-key",
        "free_rate_limit": 20,  # requests per minute
        "test_endpoint": "/v1/assets?limit=1",
        "key_required": False,
        "env_var": "MESSARI_API_KEY",
        "docs_url": "https://messari.io/api"
    },
    ServiceType.DEFILLAMA: {
        "name": "DefiLlama",
        "base_url": "https://api.llama.fi",
        "header_name": None,
        "free_rate_limit": 100,
        "test_endpoint": "/protocols",
        "key_required": False
    },
    ServiceType.CRYPTORANK: {
        "name": "CryptoRank",
        "base_url": "https://api.cryptorank.io/v1",
        "header_name": "api-key",
        "free_rate_limit": 30,
        "test_endpoint": "/currencies?limit=1",
        "key_required": False
    },
    ServiceType.GITHUB: {
        "name": "GitHub",
        "base_url": "https://api.github.com",
        "header_name": "Authorization",
        "header_prefix": "Bearer ",
        "free_rate_limit": 60,  # 60 req/hour without token
        "pro_rate_limit": 5000,  # 5000 req/hour with token
        "rate_limit_window": "hour",
        "test_endpoint": "/user",
        "key_required": False,
        "env_var": "GITHUB_TOKEN",
        "docs_url": "https://github.com/settings/tokens",
        "description": "Personal Access Token increases rate limit from 60 to 5000 req/hour"
    },
    ServiceType.TWITTER: {
        "name": "Twitter/X",
        "base_url": "https://api.twitter.com/2",
        "header_name": "Authorization",
        "header_prefix": "Bearer ",
        "free_rate_limit": 100,
        "test_endpoint": "/users/me",
        "key_required": True,
        "env_var": "TWITTER_BEARER_TOKEN",
        "docs_url": "https://developer.twitter.com/en/portal/dashboard"
    },
    ServiceType.OPENAI: {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "header_name": "Authorization",
        "header_prefix": "Bearer ",
        "free_rate_limit": 60,
        "test_endpoint": "/models",
        "key_required": True,
        "env_var": "OPENAI_API_KEY",
        "docs_url": "https://platform.openai.com/api-keys"
    }
}


@dataclass
class APIKeyStats:
    """Statistics for an API key"""
    requests_made: int = 0
    requests_today: int = 0
    requests_this_minute: int = 0
    last_request: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_error: Optional[datetime] = None
    last_error_message: Optional[str] = None
    consecutive_errors: int = 0
    minute_window_start: Optional[datetime] = None
    day_window_start: Optional[datetime] = None


class APIKeysManager:
    """
    Manages API keys for multiple services with load balancing
    and rate limit tracking.
    """
    
    def __init__(self, db):
        self.db = db
        self.collection = db.api_keys
        self._stats: Dict[str, APIKeyStats] = {}
        self._lock = asyncio.Lock()
    
    # ═══════════════════════════════════════════════════════════════
    # CRUD Operations
    # ═══════════════════════════════════════════════════════════════
    
    async def add_key(
        self,
        service: str,
        api_key: str,
        name: Optional[str] = None,
        is_pro: bool = False,
        proxy_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a new API key for a service"""
        now = datetime.now(timezone.utc).isoformat()
        
        # Generate unique ID
        key_id = self._generate_key_id(service, api_key)
        
        # Check if already exists
        existing = await self.collection.find_one({"id": key_id})
        if existing:
            return {"ok": False, "error": "Key already exists", "id": key_id}
        
        doc = {
            "id": key_id,
            "service": service,
            "api_key": api_key,
            "name": name or f"{service}-key-{key_id[:8]}",
            "is_pro": is_pro,
            "enabled": True,
            "healthy": True,
            "proxy_id": proxy_id,  # Bind to specific proxy
            # Stats
            "requests_total": 0,
            "requests_today": 0,
            "requests_this_minute": 0,
            "last_request": None,
            "last_success": None,
            "last_error": None,
            "last_error_message": None,
            "consecutive_errors": 0,
            # Rate limits
            "rate_limit": SERVICE_CONFIG.get(service, {}).get("free_rate_limit", 30),
            "rate_limit_window": SERVICE_CONFIG.get(service, {}).get("rate_limit_window", "minute"),
            # Timestamps
            "created_at": now,
            "updated_at": now
        }
        
        await self.collection.insert_one(doc)
        
        # Initialize stats
        self._stats[key_id] = APIKeyStats()
        
        logger.info(f"API Key added: {service} / {doc['name']}")
        
        return {"ok": True, "id": key_id, "name": doc["name"]}
    
    async def remove_key(self, key_id: str) -> Dict[str, Any]:
        """Remove an API key"""
        result = await self.collection.delete_one({"id": key_id})
        
        if result.deleted_count > 0:
            if key_id in self._stats:
                del self._stats[key_id]
            return {"ok": True, "deleted": key_id}
        
        return {"ok": False, "error": "Key not found"}
    
    async def toggle_key(self, key_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable an API key"""
        result = await self.collection.update_one(
            {"id": key_id},
            {"$set": {"enabled": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        if result.modified_count > 0:
            return {"ok": True, "id": key_id, "enabled": enabled}
        
        return {"ok": False, "error": "Key not found or already in that state"}
    
    async def get_keys(self, service: Optional[str] = None) -> List[Dict]:
        """Get all API keys, optionally filtered by service"""
        query = {}
        if service:
            query["service"] = service
        
        keys = await self.collection.find(query, {"_id": 0}).to_list(100)
        
        # Mask API keys for security (show only first/last 4 chars)
        for key in keys:
            api_key = key.get("api_key", "")
            if len(api_key) > 8:
                key["api_key_masked"] = f"{api_key[:4]}...{api_key[-4:]}"
            else:
                key["api_key_masked"] = "****"
            del key["api_key"]
        
        return keys
    
    async def get_key_stats(self, key_id: str) -> Optional[Dict]:
        """Get detailed stats for a key"""
        key = await self.collection.find_one({"id": key_id}, {"_id": 0})
        if not key:
            return None
        
        config = SERVICE_CONFIG.get(key["service"], {})
        
        # Calculate remaining requests
        rate_limit = key.get("rate_limit", config.get("free_rate_limit", 30))
        window = key.get("rate_limit_window", "minute")
        
        if window == "minute":
            used = key.get("requests_this_minute", 0)
        else:
            used = key.get("requests_today", 0)
        
        remaining = max(0, rate_limit - used)
        
        return {
            **key,
            "rate_limit": rate_limit,
            "rate_limit_window": window,
            "requests_used": used,
            "requests_remaining": remaining,
            "usage_percent": round((used / rate_limit) * 100, 1) if rate_limit > 0 else 0
        }
    
    # ═══════════════════════════════════════════════════════════════
    # Load Balancing
    # ═══════════════════════════════════════════════════════════════
    
    async def get_next_key(self, service: str) -> Optional[Dict]:
        """
        Get next available API key using round-robin with rate limit awareness.
        Returns the key with most remaining capacity.
        """
        async with self._lock:
            keys = await self.collection.find({
                "service": service,
                "enabled": True,
                "healthy": True
            }, {"_id": 0}).to_list(100)
            
            if not keys:
                # Try disabled healthy keys as fallback
                keys = await self.collection.find({
                    "service": service,
                    "healthy": True
                }, {"_id": 0}).to_list(100)
            
            if not keys:
                return None
            
            # Reset minute counters if needed
            now = datetime.now(timezone.utc)
            for key in keys:
                await self._maybe_reset_counters(key, now)
            
            # Sort by remaining capacity (most available first)
            def get_remaining(k):
                rate_limit = k.get("rate_limit", 30)
                window = k.get("rate_limit_window", "minute")
                if window == "minute":
                    used = k.get("requests_this_minute", 0)
                else:
                    used = k.get("requests_today", 0)
                return rate_limit - used
            
            keys.sort(key=get_remaining, reverse=True)
            
            # Return key with most capacity
            best_key = keys[0]
            remaining = get_remaining(best_key)
            
            if remaining <= 0:
                logger.warning(f"All {service} keys at rate limit")
                return None
            
            return best_key
    
    async def record_request(
        self,
        key_id: str,
        success: bool,
        error_message: Optional[str] = None
    ):
        """Record a request made with an API key"""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        
        update = {
            "last_request": now_iso,
            "updated_at": now_iso,
            "$inc": {
                "requests_total": 1,
                "requests_today": 1,
                "requests_this_minute": 1
            }
        }
        
        if success:
            update["last_success"] = now_iso
            update["consecutive_errors"] = 0
            update["healthy"] = True
        else:
            update["last_error"] = now_iso
            update["last_error_message"] = error_message
            update["$inc"]["consecutive_errors"] = 1
            
            # Mark as unhealthy after 3 consecutive errors
            key = await self.collection.find_one({"id": key_id})
            if key and key.get("consecutive_errors", 0) >= 2:
                update["healthy"] = False
        
        # Separate $set and $inc operations
        set_fields = {k: v for k, v in update.items() if not k.startswith("$")}
        inc_fields = update.get("$inc", {})
        
        await self.collection.update_one(
            {"id": key_id},
            {"$set": set_fields, "$inc": inc_fields}
        )
    
    async def _maybe_reset_counters(self, key: Dict, now: datetime):
        """Reset rate limit counters if window has passed"""
        key_id = key["id"]
        
        # Reset minute counter
        last_request = key.get("last_request")
        if last_request:
            try:
                last_dt = datetime.fromisoformat(last_request.replace("Z", "+00:00"))
                if (now - last_dt).total_seconds() > 60:
                    await self.collection.update_one(
                        {"id": key_id},
                        {"$set": {"requests_this_minute": 0}}
                    )
            except Exception:
                pass
        
        # Reset daily counter at midnight
        window = key.get("rate_limit_window", "minute")
        if window == "day":
            # Simple daily reset - if it's a new day
            last_request = key.get("last_request")
            if last_request:
                try:
                    last_dt = datetime.fromisoformat(last_request.replace("Z", "+00:00"))
                    if last_dt.date() < now.date():
                        await self.collection.update_one(
                            {"id": key_id},
                            {"$set": {"requests_today": 0}}
                        )
                except Exception:
                    pass
    
    # ═══════════════════════════════════════════════════════════════
    # Health Checking
    # ═══════════════════════════════════════════════════════════════
    
    async def check_key_health(self, key_id: str) -> Dict[str, Any]:
        """Test if an API key is working"""
        key = await self.collection.find_one({"id": key_id})
        if not key:
            return {"ok": False, "error": "Key not found"}
        
        service = key["service"]
        config = SERVICE_CONFIG.get(service)
        if not config:
            return {"ok": False, "error": f"Unknown service: {service}"}
        
        # Build test request
        base_url = config["base_url"]
        if key.get("is_pro") and config.get("pro_url"):
            base_url = config["pro_url"]
        
        test_url = base_url + config["test_endpoint"]
        headers = {}
        
        if config.get("header_name") and key.get("api_key"):
            headers[config["header_name"]] = key["api_key"]
        
        # Make test request
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                start = datetime.now(timezone.utc)
                resp = await client.get(test_url, headers=headers)
                latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                
                healthy = resp.status_code == 200
                
                # Update key status
                await self.collection.update_one(
                    {"id": key_id},
                    {"$set": {
                        "healthy": healthy,
                        "last_health_check": datetime.now(timezone.utc).isoformat(),
                        "last_latency_ms": latency
                    }}
                )
                
                return {
                    "ok": True,
                    "healthy": healthy,
                    "status_code": resp.status_code,
                    "latency_ms": round(latency, 2)
                }
        
        except Exception as e:
            await self.collection.update_one(
                {"id": key_id},
                {"$set": {
                    "healthy": False,
                    "last_health_check": datetime.now(timezone.utc).isoformat(),
                    "last_error_message": str(e)[:200]
                }}
            )
            return {"ok": False, "error": str(e)}
    
    async def check_all_keys_health(self, service: Optional[str] = None) -> Dict[str, Any]:
        """Check health of all keys"""
        query = {}
        if service:
            query["service"] = service
        
        keys = await self.collection.find(query, {"_id": 0, "id": 1, "service": 1, "name": 1}).to_list(100)
        
        results = []
        for key in keys:
            result = await self.check_key_health(key["id"])
            results.append({
                "id": key["id"],
                "service": key["service"],
                "name": key["name"],
                **result
            })
        
        healthy_count = sum(1 for r in results if r.get("healthy"))
        
        return {
            "total": len(results),
            "healthy": healthy_count,
            "unhealthy": len(results) - healthy_count,
            "results": results
        }
    
    async def get_service_summary(self) -> Dict[str, Any]:
        """Get summary of API keys by service"""
        pipeline = [
            {
                "$group": {
                    "_id": "$service",
                    "total_keys": {"$sum": 1},
                    "enabled_keys": {"$sum": {"$cond": ["$enabled", 1, 0]}},
                    "healthy_keys": {"$sum": {"$cond": ["$healthy", 1, 0]}},
                    "total_requests": {"$sum": "$requests_total"},
                    "requests_today": {"$sum": "$requests_today"}
                }
            }
        ]
        
        results = await self.collection.aggregate(pipeline).to_list(20)
        
        summary = {}
        for r in results:
            service = r["_id"]
            config = SERVICE_CONFIG.get(service, {})
            summary[service] = {
                "name": config.get("name", service),
                "total_keys": r["total_keys"],
                "enabled_keys": r["enabled_keys"],
                "healthy_keys": r["healthy_keys"],
                "total_requests": r["total_requests"],
                "requests_today": r["requests_today"],
                "key_required": config.get("key_required", False)
            }
        
        return summary
    
    # ═══════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════
    
    def _generate_key_id(self, service: str, api_key: str) -> str:
        """Generate unique ID for an API key"""
        hash_input = f"{service}:{api_key}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════
# HTTP Client with Key Rotation
# ═══════════════════════════════════════════════════════════════

class BalancedAPIClient:
    """
    HTTP client that automatically rotates API keys
    and tracks rate limits.
    """
    
    def __init__(self, db, service: str):
        self.manager = APIKeysManager(db)
        self.service = service
        self.config = SERVICE_CONFIG.get(service, {})
    
    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request with automatic key rotation"""
        
        # Get next available key
        key = await self.manager.get_next_key(self.service)
        
        # Build URL
        base_url = self.config.get("base_url", "")
        if key and key.get("is_pro") and self.config.get("pro_url"):
            base_url = self.config["pro_url"]
        
        url = base_url + endpoint
        
        # Build headers
        headers = {}
        if key and self.config.get("header_name"):
            # Get full API key from DB
            full_key = await self.manager.collection.find_one(
                {"id": key["id"]},
                {"api_key": 1}
            )
            if full_key and full_key.get("api_key"):
                headers[self.config["header_name"]] = full_key["api_key"]
        
        # Make request
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params, headers=headers)
                
                success = resp.status_code == 200
                
                # Record request
                if key:
                    error_msg = None if success else f"HTTP {resp.status_code}"
                    await self.manager.record_request(key["id"], success, error_msg)
                
                if success:
                    return {"ok": True, "data": resp.json(), "key_used": key["id"] if key else None}
                else:
                    return {"ok": False, "error": f"HTTP {resp.status_code}", "key_used": key["id"] if key else None}
        
        except Exception as e:
            if key:
                await self.manager.record_request(key["id"], False, str(e)[:200])
            return {"ok": False, "error": str(e)}


# Global instance
_api_keys_manager: Optional[APIKeysManager] = None


def get_api_keys_manager(db) -> APIKeysManager:
    """Get or create API keys manager"""
    global _api_keys_manager
    if _api_keys_manager is None:
        _api_keys_manager = APIKeysManager(db)
    return _api_keys_manager
