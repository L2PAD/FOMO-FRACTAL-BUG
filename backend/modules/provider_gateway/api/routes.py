"""
Provider Gateway API Routes
===========================

REST API for Provider Gateway management.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime, timezone
import os

from motor.motor_asyncio import AsyncIOMotorClient

from ..models import ProviderCreate, ProviderInstanceCreate, ProviderCategory, AuthType
from ..registry import ProviderRegistry
from ..gateway import ProviderGateway
from ..health import HealthMonitor

router = APIRouter(prefix="/api/providers", tags=["Providers"])

# Database connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

# Services
registry = ProviderRegistry(db)
gateway = ProviderGateway(db)
health_monitor = HealthMonitor(db)


# ═══════════════════════════════════════════════════════════════
# INITIALIZATION
# ═══════════════════════════════════════════════════════════════

@router.post("/initialize")
async def initialize_providers():
    """
    Initialize default providers in the registry.
    Creates providers if they don't exist.
    """
    result = await registry.initialize_defaults()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


# ═══════════════════════════════════════════════════════════════
# PROVIDER CRUD
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def list_providers(
    category: Optional[str] = Query(None, description="Filter by category"),
    auth_type: Optional[str] = Query(None, description="Filter by auth type"),
    requires_api_key: Optional[bool] = Query(None, description="Filter by API key requirement")
):
    """List all providers"""
    providers = await registry.list_providers(
        category=category,
        auth_type=auth_type,
        requires_api_key=requires_api_key
    )
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(providers),
        "providers": providers
    }


@router.get("/stats")
async def get_gateway_stats():
    """Get provider gateway statistics"""
    stats = await registry.get_stats()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


@router.get("/categories")
async def list_categories():
    """List all provider categories"""
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "categories": [
            {"id": c.value, "name": c.name.replace("_", " ").title()}
            for c in ProviderCategory
        ]
    }


@router.get("/capabilities")
async def list_capabilities():
    """List all provider capabilities"""
    from ..models import ProviderCapability
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "capabilities": [
            {"id": c.value, "name": c.name.replace("_", " ").title()}
            for c in ProviderCapability
        ]
    }


@router.post("")
async def create_provider(data: ProviderCreate):
    """Create custom provider"""
    result = await registry.create_provider(data)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/{provider_id}")
async def get_provider(provider_id: str):
    """Get provider by ID"""
    provider = await registry.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "provider": provider
    }


@router.get("/{provider_id}/profile")
async def get_provider_profile(provider_id: str):
    """Get provider with all instances and health"""
    profile = await registry.get_provider_profile(provider_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **profile
    }


@router.patch("/{provider_id}")
async def update_provider(provider_id: str, updates: dict):
    """Update provider configuration"""
    result = await registry.update_provider(provider_id, updates)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.delete("/{provider_id}")
async def delete_provider(provider_id: str):
    """Delete custom provider"""
    result = await registry.delete_provider(provider_id)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


# ═══════════════════════════════════════════════════════════════
# PROVIDER INSTANCES
# ═══════════════════════════════════════════════════════════════

@router.get("/{provider_id}/instances")
async def list_instances(provider_id: str):
    """List all instances for provider"""
    instances = await registry.get_instances(provider_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "provider_id": provider_id,
        "total": len(instances),
        "instances": instances
    }


@router.post("/{provider_id}/instances")
async def create_instance(provider_id: str, data: ProviderInstanceCreate):
    """Create provider instance with proxy/key binding"""
    data.provider_id = provider_id
    result = await registry.create_instance(data)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str):
    """Delete provider instance"""
    result = await registry.delete_instance(instance_id)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


# ═══════════════════════════════════════════════════════════════
# HEALTH CHECKS
# ═══════════════════════════════════════════════════════════════

@router.get("/health/overview")
async def get_health_overview():
    """Get overall gateway health"""
    health = await health_monitor.get_gateway_health()
    return health


@router.post("/{provider_id}/health")
async def check_provider_health(provider_id: str):
    """Run health check for specific provider"""
    result = await health_monitor.check_provider(provider_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "provider_id": result.provider_id,
        "status": result.status.value,
        "latency_ms": result.latency_ms,
        "success": result.success,
        "error": result.error
    }


@router.post("/health/check-all")
async def check_all_providers():
    """Run health check for all providers"""
    results = await health_monitor.check_all_providers()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(results),
        "healthy": sum(1 for r in results if r.success),
        "results": [
            {
                "provider_id": r.provider_id,
                "status": r.status.value,
                "latency_ms": r.latency_ms,
                "success": r.success,
                "error": r.error
            }
            for r in results
        ]
    }


# ═══════════════════════════════════════════════════════════════
# GATEWAY REQUESTS (Proxy to providers)
# ═══════════════════════════════════════════════════════════════

@router.get("/{provider_id}/request/{path:path}")
async def proxy_get_request(
    provider_id: str,
    path: str,
    params: Optional[str] = Query(None, description="Query params as JSON string")
):
    """
    Proxy GET request to provider.
    
    Example: /api/providers/defillama/request/protocols
    """
    import json
    query_params = json.loads(params) if params else None
    
    result = await gateway.request(provider_id, path, params=query_params)
    
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error"))
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "provider": result.get("provider"),
        "instance": result.get("instance"),
        "latency_ms": result.get("latency_ms"),
        "data": result.get("data")
    }


# ═══════════════════════════════════════════════════════════════
# CONVENIENCE ENDPOINTS (Direct provider access)
# ═══════════════════════════════════════════════════════════════

@router.get("/defillama/protocols")
async def defillama_protocols():
    """Get all DeFi protocols from DefiLlama"""
    result = await gateway.defillama("protocols")
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error"))
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "latency_ms": result.get("latency_ms"),
        "total": len(result.get("data", [])),
        "protocols": result.get("data", [])[:100]  # Limit response
    }


@router.get("/defillama/tvl/{protocol}")
async def defillama_tvl(protocol: str):
    """Get TVL for specific protocol"""
    result = await gateway.defillama(f"protocol/{protocol}")
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error"))
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "latency_ms": result.get("latency_ms"),
        "protocol": protocol,
        "data": result.get("data")
    }


@router.get("/defillama/chains")
async def defillama_chains():
    """Get TVL by chain"""
    result = await gateway.defillama("chains")
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error"))
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "latency_ms": result.get("latency_ms"),
        "total": len(result.get("data", [])),
        "chains": result.get("data", [])
    }


@router.get("/coinglass/funding")
async def coinglass_funding():
    """Get funding rates from CoinGlass"""
    result = await gateway.coinglass("funding")
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error"))
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "latency_ms": result.get("latency_ms"),
        "data": result.get("data")
    }


@router.get("/dexscreener/pairs/{chain}/{pair}")
async def dexscreener_pair(chain: str, pair: str):
    """Get DEX pair info from DexScreener"""
    result = await gateway.dexscreener(f"dex/pairs/{chain}/{pair}")
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error"))
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "latency_ms": result.get("latency_ms"),
        "data": result.get("data")
    }


@router.get("/dexscreener/search")
async def dexscreener_search(q: str = Query(..., description="Search query")):
    """Search tokens on DexScreener"""
    result = await gateway.dexscreener("dex/search", params={"q": q})
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error"))
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "latency_ms": result.get("latency_ms"),
        "query": q,
        "data": result.get("data")
    }
