"""
Asset Registry API Routes
=========================

REST API for Unified Asset Registry.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime, timezone
import os

from motor.motor_asyncio import AsyncIOMotorClient

from ..models import AssetCreate, AssetExternalIdCreate, AssetMarketSymbolCreate
from ..resolver import AssetResolver
from ..registry import AssetRegistry

router = APIRouter(prefix="/api/asset-registry", tags=["Asset Registry"])

# Database connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

# Services
resolver = AssetResolver(db)
registry = AssetRegistry(db)


# ═══════════════════════════════════════════════════════════════
# RESOLVE ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/resolve")
async def resolve_asset(
    q: str = Query(..., description="Any identifier: symbol, name, external_id, contract, trading pair"),
    source: Optional[str] = Query(None, description="Source hint: coingecko, binance, etc."),
    chain: Optional[str] = Query(None, description="Chain hint: ethereum, solana, etc.")
):
    """
    Resolve any identifier to canonical asset.
    
    Examples:
    - /api/assets/resolve?q=BTC
    - /api/assets/resolve?q=bitcoin&source=coingecko
    - /api/assets/resolve?q=BTCUSDT&source=binance
    - /api/assets/resolve?q=0x... (contract)
    """
    result = await resolver.resolve(q, source, chain)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/resolve/batch")
async def resolve_many(
    queries: List[str],
    source: Optional[str] = None
):
    """
    Resolve multiple identifiers at once.
    
    Request body: ["BTC", "ETH", "BTCUSDT", ...]
    """
    result = await resolver.resolve_many(queries, source)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.get("/search")
async def search_assets(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Search for assets by symbol or name.
    """
    results = await resolver.search(q, limit)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "query": q,
        "total": len(results),
        "results": results
    }


# ═══════════════════════════════════════════════════════════════
# ASSET CRUD ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def list_assets(
    status: Optional[str] = Query(None, description="Filter by status: active, inactive"),
    asset_type: Optional[str] = Query(None, description="Filter by type: token, coin, stablecoin"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List all assets with filters"""
    result = await registry.list_assets(status, asset_type, limit, offset)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("")
async def create_asset(data: AssetCreate):
    """Create new asset"""
    result = await registry.create_asset(data)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/stats")
async def get_registry_stats():
    """Get asset registry statistics"""
    stats = await registry.get_stats()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


@router.get("/{asset_id}")
async def get_asset(asset_id: str):
    """Get asset by ID"""
    asset = await registry.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "asset": asset
    }


@router.get("/{asset_id}/profile")
async def get_asset_profile(asset_id: str):
    """
    Get full asset profile with all linked data:
    - External IDs (CoinGecko, CoinMarketCap, etc.)
    - Market symbols (exchange trading pairs)
    - Linked project
    """
    profile = await registry.get_asset_profile(asset_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **profile
    }


# ═══════════════════════════════════════════════════════════════
# EXTERNAL ID ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/{asset_id}/sources")
async def get_asset_sources(asset_id: str):
    """Get all external source mappings for asset"""
    external_ids = await registry.get_external_ids(asset_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "asset_id": asset_id,
        "total": len(external_ids),
        "sources": external_ids
    }


@router.post("/{asset_id}/sources")
async def add_external_id(asset_id: str, data: AssetExternalIdCreate):
    """Add external source mapping for asset"""
    data.asset_id = asset_id
    result = await registry.add_external_id(data)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


# ═══════════════════════════════════════════════════════════════
# MARKET SYMBOLS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/{asset_id}/markets")
async def get_asset_markets(
    asset_id: str,
    exchange: Optional[str] = Query(None),
    market_type: Optional[str] = Query(None)
):
    """Get all exchange trading pairs for asset"""
    symbols = await registry.get_market_symbols(asset_id, exchange, market_type)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "asset_id": asset_id,
        "total": len(symbols),
        "markets": symbols
    }


@router.post("/{asset_id}/markets")
async def add_market_symbol(asset_id: str, data: AssetMarketSymbolCreate):
    """Add exchange trading pair for asset"""
    data.asset_id = asset_id
    result = await registry.add_market_symbol(data)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


# ═══════════════════════════════════════════════════════════════
# SYNC ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/sync/coingecko")
async def sync_from_coingecko():
    """
    Sync assets from CoinGecko market data.
    Creates assets and external IDs.
    """
    # Get coins from market_data collection
    coins = []
    cursor = db.market_data.find({}, {"_id": 0})
    async for coin in cursor:
        coins.append(coin)
    
    if not coins:
        return {"ok": False, "error": "No CoinGecko data found. Run coingecko sync first."}
    
    result = await registry.sync_from_coingecko(coins)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/sync/exchange/{exchange}")
async def sync_from_exchange(exchange: str):
    """
    Sync market symbols from exchange instruments.
    """
    # Import instrument registry
    from modules.market_data.services import instrument_registry
    from modules.market_data.domain.types import Venue
    
    # Get venue enum
    try:
        venue = Venue(exchange.lower())
    except ValueError:
        return {"ok": False, "error": f"Unknown exchange: {exchange}"}
    
    instruments = instrument_registry.list_instruments(venue=venue)
    if not instruments:
        return {"ok": False, "error": f"No instruments found for {exchange}"}
    
    # Convert to list of dicts
    instrument_dicts = []
    for inst in instruments:
        instrument_dicts.append({
            "symbol": inst.symbol,
            "base_asset": inst.base,
            "quote_asset": inst.quote,
            "market_type": "perp" if inst.is_perp else "spot"
        })
    
    result = await registry.sync_from_exchange(exchange.lower(), instrument_dicts)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "exchange": exchange,
        **result
    }


@router.post("/sync/projects")
async def sync_from_projects():
    """
    Sync assets from intel_projects collection.
    Links projects to assets.
    """
    created = 0
    linked = 0
    
    cursor = db.intel_projects.find({}, {"_id": 0})
    async for project in cursor:
        symbol = project.get("symbol", "")
        name = project.get("name", "")
        slug = project.get("slug", "")
        
        if not symbol:
            continue
        
        asset_id = registry._generate_asset_id(symbol)
        
        # Check if asset exists
        existing = await registry.get_asset(asset_id)
        
        if not existing:
            # Create asset
            result = await registry.create_asset(AssetCreate(
                canonical_symbol=symbol,
                canonical_name=name,
                project_id=project.get("key", f"seed:project:{slug}"),
                logo=project.get("logo"),
                website=project.get("website"),
                description=project.get("about")
            ))
            if result["ok"]:
                created += 1
        else:
            # Link to project
            await registry.update_asset(asset_id, {
                "project_id": project.get("key", f"seed:project:{slug}")
            })
            linked += 1
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "created": created,
        "linked": linked
    }


# ═══════════════════════════════════════════════════════════════
# BOOTSTRAP ENDPOINT
# ═══════════════════════════════════════════════════════════════

@router.post("/bootstrap")
async def bootstrap_registry():
    """
    Full bootstrap of asset registry:
    1. Sync from projects
    2. Sync from CoinGecko
    3. Sync from exchanges
    """
    results = {
        "projects": None,
        "coingecko": None,
        "exchanges": {}
    }
    
    # 1. Sync from projects
    projects_result = await sync_from_projects()
    results["projects"] = projects_result
    
    # 2. Sync from CoinGecko  
    cg_result = await sync_from_coingecko()
    results["coingecko"] = cg_result
    
    # 3. Sync from exchanges
    exchanges = ["binance", "coinbase", "bybit", "hyperliquid"]
    for exchange in exchanges:
        try:
            ex_result = await sync_from_exchange(exchange)
            results["exchanges"][exchange] = ex_result
        except Exception as e:
            results["exchanges"][exchange] = {"ok": False, "error": str(e)}
    
    # Get final stats
    stats = await registry.get_stats()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "results": results,
        "stats": stats
    }
