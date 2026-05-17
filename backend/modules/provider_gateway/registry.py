"""
Provider Registry
=================

Built-in registry of all supported data providers.
Pre-configured with endpoints, capabilities, and auth requirements.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import (
    Provider, ProviderCreate, ProviderInstance, ProviderInstanceCreate,
    AuthType, ProviderStatus, ProviderCategory, ProviderCapability
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# DEFAULT PROVIDERS REGISTRY
# ═══════════════════════════════════════════════════════════════

DEFAULT_PROVIDERS = [
    # ═══════════════════════════════════════════════════════════
    # CATEGORY A: API Key Required
    # ═══════════════════════════════════════════════════════════
    {
        "id": "coingecko",
        "name": "CoinGecko",
        "endpoint": "https://api.coingecko.com/api/v3",
        "auth_type": "api_key",
        "requires_api_key": True,
        "api_key_header": "x-cg-demo-api-key",
        "category": "market_data",
        "capabilities": ["asset_price", "asset_marketcap", "asset_volume", "candles", "global_metrics", "trending"],
        "rate_limit": 30,
        "rate_limit_window": "minute",
        "priority": 1,
        "website": "https://coingecko.com",
        "docs_url": "https://docs.coingecko.com",
        "description": "Primary market data provider with comprehensive crypto coverage"
    },
    {
        "id": "coinmarketcap",
        "name": "CoinMarketCap",
        "endpoint": "https://pro-api.coinmarketcap.com/v1",
        "auth_type": "api_key",
        "requires_api_key": True,
        "api_key_header": "X-CMC_PRO_API_KEY",
        "category": "market_data",
        "capabilities": ["asset_price", "asset_marketcap", "asset_volume", "global_metrics", "trending"],
        "rate_limit": 333,
        "rate_limit_window": "day",
        "priority": 2,
        "website": "https://coinmarketcap.com",
        "docs_url": "https://coinmarketcap.com/api/documentation/v1/",
        "description": "Fallback market data with good historical coverage"
    },
    {
        "id": "messari",
        "name": "Messari",
        "endpoint": "https://data.messari.io/api/v1",
        "auth_type": "api_key",
        "requires_api_key": True,
        "api_key_header": "x-messari-api-key",
        "category": "research",
        "capabilities": ["project_profile", "token_metrics", "news"],
        "rate_limit": 20,
        "rate_limit_window": "minute",
        "priority": 1,
        "website": "https://messari.io",
        "docs_url": "https://messari.io/api/docs",
        "description": "Research profiles and protocol analytics"
    },
    
    # ═══════════════════════════════════════════════════════════
    # CATEGORY B: Public APIs (No API Key)
    # ═══════════════════════════════════════════════════════════
    {
        "id": "defillama",
        "name": "DefiLlama",
        "endpoint": "https://api.llama.fi",
        "auth_type": "none",
        "requires_api_key": False,
        "category": "defi",
        "capabilities": ["tvl", "yields", "bridges", "stablecoins", "airdrops", "protocols"],
        "rate_limit": 100,
        "rate_limit_window": "minute",
        "priority": 1,
        "website": "https://defillama.com",
        "docs_url": "https://defillama.com/docs/api",
        "description": "Primary DeFi data: TVL, yields, protocols, bridges"
    },
    {
        "id": "dexscreener",
        "name": "DexScreener",
        "endpoint": "https://api.dexscreener.com/latest",
        "auth_type": "none",
        "requires_api_key": False,
        "category": "dex",
        "capabilities": ["dex_pairs", "dex_volume", "new_tokens", "liquidity_pools"],
        "rate_limit": 60,
        "rate_limit_window": "minute",
        "priority": 1,
        "website": "https://dexscreener.com",
        "docs_url": "https://docs.dexscreener.com",
        "description": "DEX pairs, liquidity, and new token listings"
    },
    {
        "id": "geckoterminal",
        "name": "GeckoTerminal",
        "endpoint": "https://api.geckoterminal.com/api/v2",
        "auth_type": "none",
        "requires_api_key": False,
        "category": "dex",
        "capabilities": ["dex_pairs", "dex_volume", "liquidity_pools"],
        "rate_limit": 30,
        "rate_limit_window": "minute",
        "priority": 2,
        "website": "https://geckoterminal.com",
        "docs_url": "https://www.geckoterminal.com/api-docs",
        "description": "CoinGecko DEX data aggregator"
    },
    {
        "id": "coinglass",
        "name": "CoinGlass",
        "endpoint": "https://open-api.coinglass.com/public/v2",
        "auth_type": "none",
        "requires_api_key": False,
        "category": "derivatives",
        "capabilities": ["funding_rates", "open_interest", "liquidations", "futures"],
        "rate_limit": 30,
        "rate_limit_window": "minute",
        "priority": 1,
        "website": "https://coinglass.com",
        "docs_url": "https://coinglass.com/api",
        "description": "Derivatives data: funding, OI, liquidations"
    },
    {
        "id": "cryptofees",
        "name": "CryptoFees",
        "endpoint": "https://cryptofees.info/api",
        "auth_type": "none",
        "requires_api_key": False,
        "category": "onchain",
        "capabilities": ["chain_analytics"],
        "rate_limit": 60,
        "rate_limit_window": "minute",
        "priority": 1,
        "website": "https://cryptofees.info",
        "description": "Protocol fees ranking"
    },
    {
        "id": "llama_yields",
        "name": "DefiLlama Yields",
        "endpoint": "https://yields.llama.fi",
        "auth_type": "none",
        "requires_api_key": False,
        "category": "defi",
        "capabilities": ["yields"],
        "rate_limit": 60,
        "rate_limit_window": "minute",
        "priority": 1,
        "website": "https://defillama.com/yields",
        "description": "DeFi yields aggregator"
    },
    {
        "id": "llama_bridges",
        "name": "DefiLlama Bridges",
        "endpoint": "https://bridges.llama.fi",
        "auth_type": "none",
        "requires_api_key": False,
        "category": "defi",
        "capabilities": ["bridges"],
        "rate_limit": 60,
        "rate_limit_window": "minute",
        "priority": 1,
        "website": "https://defillama.com/bridges",
        "description": "Cross-chain bridge analytics"
    },
    {
        "id": "llama_stables",
        "name": "DefiLlama Stablecoins",
        "endpoint": "https://stablecoins.llama.fi",
        "auth_type": "none",
        "requires_api_key": False,
        "category": "defi",
        "capabilities": ["stablecoins"],
        "rate_limit": 60,
        "rate_limit_window": "minute",
        "priority": 1,
        "website": "https://defillama.com/stablecoins",
        "description": "Stablecoin supply and flows"
    }
]


class ProviderRegistry:
    """
    Provider Registry Service.
    Manages provider configurations and instances.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.providers = db.providers
        self.instances = db.provider_instances
    
    # ═══════════════════════════════════════════════════════════════
    # INITIALIZATION
    # ═══════════════════════════════════════════════════════════════
    
    async def initialize_defaults(self) -> dict:
        """Initialize default providers if not exists"""
        created = 0
        updated = 0
        
        for provider_data in DEFAULT_PROVIDERS:
            provider_id = provider_data["id"]
            
            # Check if exists
            existing = await self.providers.find_one({"id": provider_id})
            
            if not existing:
                # Create new provider
                now = datetime.now(timezone.utc)
                doc = {
                    **provider_data,
                    "status": ProviderStatus.ACTIVE.value,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat()
                }
                await self.providers.insert_one(doc)
                created += 1
                logger.info(f"Created provider: {provider_id}")
            else:
                # Update existing
                await self.providers.update_one(
                    {"id": provider_id},
                    {"$set": {
                        "endpoint": provider_data.get("endpoint"),
                        "capabilities": provider_data.get("capabilities", []),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                updated += 1
        
        return {
            "ok": True,
            "created": created,
            "updated": updated,
            "total": len(DEFAULT_PROVIDERS)
        }
    
    # ═══════════════════════════════════════════════════════════════
    # PROVIDER CRUD
    # ═══════════════════════════════════════════════════════════════
    
    async def get_provider(self, provider_id: str) -> Optional[dict]:
        """Get provider by ID"""
        provider = await self.providers.find_one({"id": provider_id})
        if provider:
            provider.pop("_id", None)
        return provider
    
    async def list_providers(
        self,
        category: Optional[str] = None,
        auth_type: Optional[str] = None,
        status: Optional[str] = None,
        requires_api_key: Optional[bool] = None
    ) -> List[dict]:
        """List providers with filters"""
        query = {}
        if category:
            query["category"] = category
        if auth_type:
            query["auth_type"] = auth_type
        if status:
            query["status"] = status
        if requires_api_key is not None:
            query["requires_api_key"] = requires_api_key
        
        providers = []
        cursor = self.providers.find(query, {"_id": 0}).sort("priority", 1)
        async for provider in cursor:
            providers.append(provider)
        
        return providers
    
    async def create_provider(self, data: ProviderCreate) -> dict:
        """Create custom provider"""
        now = datetime.now(timezone.utc)
        
        # Check if exists
        existing = await self.providers.find_one({"id": data.id})
        if existing:
            return {"ok": False, "error": "Provider already exists"}
        
        doc = {
            "id": data.id,
            "name": data.name,
            "endpoint": data.endpoint,
            "auth_type": data.auth_type.value if isinstance(data.auth_type, AuthType) else data.auth_type,
            "requires_api_key": data.requires_api_key,
            "api_key_header": data.api_key_header,
            "category": data.category.value if isinstance(data.category, ProviderCategory) else data.category,
            "capabilities": data.capabilities,
            "rate_limit": data.rate_limit,
            "rate_limit_window": data.rate_limit_window,
            "priority": data.priority,
            "website": data.website,
            "docs_url": data.docs_url,
            "description": data.description,
            "status": ProviderStatus.ACTIVE.value,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
        await self.providers.insert_one(doc)
        doc.pop("_id", None)
        
        logger.info(f"Created provider: {data.id}")
        return {"ok": True, "provider_id": data.id, "provider": doc}
    
    async def update_provider(self, provider_id: str, updates: dict) -> dict:
        """Update provider"""
        now = datetime.now(timezone.utc)
        updates["updated_at"] = now.isoformat()
        
        result = await self.providers.update_one(
            {"id": provider_id},
            {"$set": updates}
        )
        
        if result.modified_count:
            return {"ok": True, "provider_id": provider_id}
        return {"ok": False, "error": "Provider not found"}
    
    async def delete_provider(self, provider_id: str) -> dict:
        """Delete custom provider"""
        # Don't allow deleting default providers
        default_ids = [p["id"] for p in DEFAULT_PROVIDERS]
        if provider_id in default_ids:
            return {"ok": False, "error": "Cannot delete default provider"}
        
        result = await self.providers.delete_one({"id": provider_id})
        if result.deleted_count:
            # Also delete instances
            await self.instances.delete_many({"provider_id": provider_id})
            return {"ok": True}
        return {"ok": False, "error": "Provider not found"}
    
    # ═══════════════════════════════════════════════════════════════
    # PROVIDER INSTANCES
    # ═══════════════════════════════════════════════════════════════
    
    async def create_instance(self, data: ProviderInstanceCreate) -> dict:
        """Create provider instance with proxy/key binding"""
        now = datetime.now(timezone.utc)
        
        # Verify provider exists
        provider = await self.get_provider(data.provider_id)
        if not provider:
            return {"ok": False, "error": "Provider not found"}
        
        # Generate instance ID
        instance_count = await self.instances.count_documents({"provider_id": data.provider_id})
        instance_id = f"{data.provider_id}_instance_{instance_count + 1}"
        
        doc = {
            "id": instance_id,
            "provider_id": data.provider_id,
            "proxy_id": data.proxy_id,
            "api_key_id": data.api_key_id,
            "status": ProviderStatus.ACTIVE.value,
            "latency_ms": None,
            "success_count": 0,
            "error_count": 0,
            "last_error": None,
            "last_check": None,
            "last_success": None,
            "created_at": now.isoformat()
        }
        
        await self.instances.insert_one(doc)
        doc.pop("_id", None)
        
        logger.info(f"Created instance: {instance_id}")
        return {"ok": True, "instance_id": instance_id, "instance": doc}
    
    async def get_instances(self, provider_id: str) -> List[dict]:
        """Get all instances for provider"""
        instances = []
        cursor = self.instances.find({"provider_id": provider_id}, {"_id": 0})
        async for inst in cursor:
            instances.append(inst)
        return instances
    
    async def get_healthy_instance(self, provider_id: str) -> Optional[dict]:
        """Get best healthy instance for provider"""
        instance = await self.instances.find_one(
            {
                "provider_id": provider_id,
                "status": {"$in": ["active", "degraded"]}
            },
            {"_id": 0},
            sort=[("error_count", 1), ("latency_ms", 1)]
        )
        return instance
    
    async def update_instance_status(
        self, 
        instance_id: str, 
        status: ProviderStatus,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None
    ) -> dict:
        """Update instance status after request"""
        now = datetime.now(timezone.utc)
        
        updates = {
            "status": status.value,
            "last_check": now.isoformat()
        }
        
        if latency_ms is not None:
            updates["latency_ms"] = latency_ms
        
        if status == ProviderStatus.ACTIVE:
            updates["last_success"] = now.isoformat()
            await self.instances.update_one(
                {"id": instance_id},
                {
                    "$set": updates,
                    "$inc": {"success_count": 1}
                }
            )
        else:
            updates["last_error"] = error
            await self.instances.update_one(
                {"id": instance_id},
                {
                    "$set": updates,
                    "$inc": {"error_count": 1}
                }
            )
        
        return {"ok": True}
    
    async def delete_instance(self, instance_id: str) -> dict:
        """Delete provider instance"""
        result = await self.instances.delete_one({"id": instance_id})
        if result.deleted_count:
            return {"ok": True}
        return {"ok": False, "error": "Instance not found"}
    
    # ═══════════════════════════════════════════════════════════════
    # QUERIES
    # ═══════════════════════════════════════════════════════════════
    
    async def get_providers_by_capability(self, capability: str) -> List[dict]:
        """Find providers that have specific capability"""
        providers = []
        cursor = self.providers.find(
            {"capabilities": capability, "status": "active"},
            {"_id": 0}
        ).sort("priority", 1)
        async for provider in cursor:
            providers.append(provider)
        return providers
    
    async def get_provider_profile(self, provider_id: str) -> Optional[dict]:
        """Get provider with all instances"""
        provider = await self.get_provider(provider_id)
        if not provider:
            return None
        
        instances = await self.get_instances(provider_id)
        
        # Calculate health
        healthy = sum(1 for i in instances if i.get("status") in ["active", "degraded"])
        avg_latency = 0
        latencies = [i.get("latency_ms") for i in instances if i.get("latency_ms")]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
        
        error_rate = 0
        total_requests = sum(i.get("success_count", 0) + i.get("error_count", 0) for i in instances)
        total_errors = sum(i.get("error_count", 0) for i in instances)
        if total_requests:
            error_rate = total_errors / total_requests
        
        return {
            "provider": provider,
            "instances": instances,
            "health": {
                "status": provider.get("status"),
                "instances_total": len(instances),
                "instances_healthy": healthy,
                "avg_latency_ms": avg_latency,
                "error_rate": error_rate
            }
        }
    
    async def get_stats(self) -> dict:
        """Get gateway statistics"""
        total = await self.providers.count_documents({})
        active = await self.providers.count_documents({"status": "active"})
        api_key = await self.providers.count_documents({"requires_api_key": True})
        public = await self.providers.count_documents({"requires_api_key": False})
        
        total_instances = await self.instances.count_documents({})
        healthy_instances = await self.instances.count_documents(
            {"status": {"$in": ["active", "degraded"]}}
        )
        
        # By category
        categories_pipeline = [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}}
        ]
        categories = {}
        async for doc in self.providers.aggregate(categories_pipeline):
            categories[doc["_id"]] = doc["count"]
        
        # By capability
        capabilities_pipeline = [
            {"$unwind": "$capabilities"},
            {"$group": {"_id": "$capabilities", "count": {"$sum": 1}}}
        ]
        capabilities = {}
        async for doc in self.providers.aggregate(capabilities_pipeline):
            capabilities[doc["_id"]] = doc["count"]
        
        return {
            "total_providers": total,
            "active_providers": active,
            "api_key_providers": api_key,
            "public_providers": public,
            "total_instances": total_instances,
            "healthy_instances": healthy_instances,
            "providers_by_category": categories,
            "capabilities_count": capabilities
        }
