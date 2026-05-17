"""
Admin API Routes
Source management, data control, configuration, bootstrap
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_db():
    """Dependency to get database"""
    from server import db
    return db


def get_source_manager():
    """Dependency to get source manager"""
    from server import db
    from modules.intel.engine.source_manager import create_source_manager
    return create_source_manager(db)


def get_coingecko_sync():
    """Dependency to get CoinGecko sync service"""
    from server import db
    from modules.intel.sources.coingecko.sync import CoinGeckoSync
    return CoinGeckoSync(db)


def get_coingecko_pool():
    """Get CoinGecko pool"""
    from modules.intel.sources.coingecko.client import coingecko_pool
    return coingecko_pool


# ═══════════════════════════════════════════════════════════════
# BOOTSTRAP / COLD START
# ═══════════════════════════════════════════════════════════════

@router.post("/bootstrap")
async def run_bootstrap(db=Depends(get_db)):
    """
    Bootstrap the platform with seed data.
    
    Seeds:
    - Persons (notable crypto figures)
    - Exchanges (CEX/DEX)
    - Projects (tokens)
    - API Documentation
    
    Safe to run multiple times (upsert).
    """
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc)
    results = {}
    
    # Persons
    PERSONS_DATA = [
        {"name": "Vitalik Buterin", "slug": "vitalik-buterin", "role": "founder", "projects": ["Ethereum"]},
        {"name": "Changpeng Zhao (CZ)", "slug": "cz-binance", "role": "founder", "projects": ["Binance"]},
        {"name": "Brian Armstrong", "slug": "brian-armstrong", "role": "founder", "projects": ["Coinbase"]},
        {"name": "Anatoly Yakovenko", "slug": "anatoly-yakovenko", "role": "founder", "projects": ["Solana"]},
        {"name": "Hayden Adams", "slug": "hayden-adams", "role": "founder", "projects": ["Uniswap"]},
        {"name": "Andre Cronje", "slug": "andre-cronje", "role": "founder", "projects": ["Yearn Finance"]},
        {"name": "Stani Kulechov", "slug": "stani-kulechov", "role": "founder", "projects": ["Aave"]},
        {"name": "Sergey Nazarov", "slug": "sergey-nazarov", "role": "founder", "projects": ["Chainlink"]},
        {"name": "Gavin Wood", "slug": "gavin-wood", "role": "founder", "projects": ["Polkadot"]},
        {"name": "Charles Hoskinson", "slug": "charles-hoskinson", "role": "founder", "projects": ["Cardano"]},
        {"name": "Marc Andreessen", "slug": "marc-andreessen", "role": "investor", "projects": ["a16z"]},
        {"name": "Chris Dixon", "slug": "chris-dixon", "role": "investor", "projects": ["a16z crypto"]},
        {"name": "Fred Ehrsam", "slug": "fred-ehrsam", "role": "investor", "projects": ["Paradigm"]},
        {"name": "Matt Huang", "slug": "matt-huang", "role": "investor", "projects": ["Paradigm"]},
        {"name": "Olaf Carlson-Wee", "slug": "olaf-carlson-wee", "role": "investor", "projects": ["Polychain"]},
        {"name": "Naval Ravikant", "slug": "naval-ravikant", "role": "investor", "projects": ["AngelList"]},
        {"name": "Balaji Srinivasan", "slug": "balaji-srinivasan", "role": "investor", "projects": ["a16z"]},
        {"name": "Dan Morehead", "slug": "dan-morehead", "role": "investor", "projects": ["Pantera Capital"]},
        {"name": "Haseeb Qureshi", "slug": "haseeb-qureshi", "role": "investor", "projects": ["Dragonfly"]},
        {"name": "Arthur Hayes", "slug": "arthur-hayes", "role": "founder", "projects": ["BitMEX"]},
    ]
    
    for person in PERSONS_DATA:
        doc = {"key": f"seed:person:{person['slug']}", "source": "seed", **person, "updated_at": now}
        await db.intel_persons.update_one({"key": doc["key"]}, {"$set": doc}, upsert=True)
    results["persons"] = len(PERSONS_DATA)
    
    # Exchanges
    EXCHANGES_DATA = [
        {"name": "Binance", "slug": "binance", "type": "CEX", "volume_rank": 1},
        {"name": "Coinbase", "slug": "coinbase", "type": "CEX", "volume_rank": 2},
        {"name": "Bybit", "slug": "bybit", "type": "CEX", "volume_rank": 3},
        {"name": "OKX", "slug": "okx", "type": "CEX", "volume_rank": 4},
        {"name": "Kraken", "slug": "kraken", "type": "CEX", "volume_rank": 5},
        {"name": "KuCoin", "slug": "kucoin", "type": "CEX", "volume_rank": 6},
        {"name": "Gate.io", "slug": "gate-io", "type": "CEX", "volume_rank": 7},
        {"name": "Huobi", "slug": "huobi", "type": "CEX", "volume_rank": 8},
        {"name": "MEXC", "slug": "mexc", "type": "CEX", "volume_rank": 9},
        {"name": "Bitget", "slug": "bitget", "type": "CEX", "volume_rank": 10},
        {"name": "Uniswap", "slug": "uniswap", "type": "DEX", "chain": "Ethereum"},
        {"name": "dYdX", "slug": "dydx", "type": "DEX", "chain": "Cosmos"},
        {"name": "HyperLiquid", "slug": "hyperliquid", "type": "DEX", "chain": "Arbitrum"},
        {"name": "PancakeSwap", "slug": "pancakeswap", "type": "DEX", "chain": "BSC"},
        {"name": "Curve", "slug": "curve", "type": "DEX", "chain": "Ethereum"},
        {"name": "GMX", "slug": "gmx", "type": "DEX", "chain": "Arbitrum"},
        {"name": "Raydium", "slug": "raydium", "type": "DEX", "chain": "Solana"},
        {"name": "Jupiter", "slug": "jupiter", "type": "DEX", "chain": "Solana"},
        {"name": "1inch", "slug": "1inch", "type": "DEX", "chain": "Multi-chain"},
    ]
    
    for exchange in EXCHANGES_DATA:
        doc = {"key": f"seed:exchange:{exchange['slug']}", "source": "seed", **exchange, "updated_at": now}
        await db.intel_exchanges.update_one({"key": doc["key"]}, {"$set": doc}, upsert=True)
    results["exchanges"] = len(EXCHANGES_DATA)
    
    # Projects
    PROJECTS_DATA = [
        {"name": "Bitcoin", "symbol": "BTC", "slug": "bitcoin", "category": "Currency"},
        {"name": "Ethereum", "symbol": "ETH", "slug": "ethereum", "category": "Smart Contracts"},
        {"name": "Solana", "symbol": "SOL", "slug": "solana", "category": "Smart Contracts"},
        {"name": "Arbitrum", "symbol": "ARB", "slug": "arbitrum", "category": "Layer 2"},
        {"name": "Optimism", "symbol": "OP", "slug": "optimism", "category": "Layer 2"},
        {"name": "Polygon", "symbol": "MATIC", "slug": "polygon", "category": "Layer 2"},
        {"name": "Avalanche", "symbol": "AVAX", "slug": "avalanche", "category": "Smart Contracts"},
        {"name": "Chainlink", "symbol": "LINK", "slug": "chainlink", "category": "Oracle"},
        {"name": "Uniswap", "symbol": "UNI", "slug": "uniswap", "category": "DEX"},
        {"name": "Aave", "symbol": "AAVE", "slug": "aave", "category": "DeFi Lending"},
        {"name": "Lido", "symbol": "LDO", "slug": "lido", "category": "Liquid Staking"},
        {"name": "Maker", "symbol": "MKR", "slug": "maker", "category": "DeFi"},
        {"name": "Celestia", "symbol": "TIA", "slug": "celestia", "category": "Modular"},
        {"name": "Sui", "symbol": "SUI", "slug": "sui", "category": "Smart Contracts"},
        {"name": "Aptos", "symbol": "APT", "slug": "aptos", "category": "Smart Contracts"},
        {"name": "Starknet", "symbol": "STRK", "slug": "starknet", "category": "Layer 2"},
        {"name": "LayerZero", "symbol": "ZRO", "slug": "layerzero", "category": "Cross-chain"},
        {"name": "EigenLayer", "symbol": "EIGEN", "slug": "eigenlayer", "category": "Restaking"},
        {"name": "Pyth Network", "symbol": "PYTH", "slug": "pyth", "category": "Oracle"},
        {"name": "Jupiter", "symbol": "JUP", "slug": "jupiter", "category": "DEX"},
    ]
    
    for project in PROJECTS_DATA:
        doc = {"key": f"seed:project:{project['slug']}", "source": "seed", **project, "updated_at": now}
        await db.intel_projects.update_one({"key": doc["key"]}, {"$set": doc}, upsert=True)
    results["projects"] = len(PROJECTS_DATA)
    
    # Seed API Docs
    try:
        from modules.intel.api.documentation_registry import API_DOCUMENTATION
        for endpoint in API_DOCUMENTATION:
            doc = {
                "endpoint_id": endpoint.endpoint_id,
                "path": endpoint.path,
                "method": endpoint.method.value,
                "title_en": endpoint.title_en,
                "title_ru": endpoint.title_ru,
                "description_en": endpoint.description_en,
                "description_ru": endpoint.description_ru,
                "category": endpoint.category,
                "tags": endpoint.tags,
                "updated_at": now
            }
            await db.intel_docs.update_one(
                {"endpoint_id": doc["endpoint_id"]},
                {"$set": doc},
                upsert=True
            )
        results["api_docs"] = len(API_DOCUMENTATION)
    except Exception as e:
        results["api_docs"] = f"error: {str(e)}"
    
    # Get final counts
    final_stats = {
        "persons": await db.intel_persons.count_documents({}),
        "exchanges": await db.intel_exchanges.count_documents({}),
        "projects": await db.intel_projects.count_documents({}),
        "investors": await db.intel_investors.count_documents({}),
        "fundraising": await db.intel_fundraising.count_documents({}),
        "unlocks": await db.intel_unlocks.count_documents({}),
        "api_docs": await db.intel_docs.count_documents({}),
        "proxies": await db.system_proxies.count_documents({}),
    }
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "status": "bootstrap_complete",
        "seeded": results,
        "totals": final_stats
    }


@router.get("/stats")
async def get_system_stats(db=Depends(get_db)):
    """Get system-wide statistics"""
    stats = {
        "persons": await db.intel_persons.count_documents({}),
        "exchanges": await db.intel_exchanges.count_documents({}),
        "projects": await db.intel_projects.count_documents({}),
        "investors": await db.intel_investors.count_documents({}),
        "fundraising": await db.intel_fundraising.count_documents({}),
        "unlocks": await db.intel_unlocks.count_documents({}),
        "api_docs": await db.intel_docs.count_documents({}),
        "proxies": await db.system_proxies.count_documents({}),
        "categories": await db.intel_categories.count_documents({}),
    }
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "stats": stats
    }


# ═══════════════════════════════════════════════════════════════
# SOURCE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.get("/sources")
async def list_all_sources(
    status: Optional[str] = Query(None, description="Filter by status: active, paused, disabled"),
    sm = Depends(get_source_manager)
):
    """List all data sources with their status"""
    sources = await sm.list_sources(status)
    health = await sm.get_all_health()
    
    # Merge health data
    health_map = {h['source']: h for h in health}
    for source in sources:
        source['health'] = health_map.get(source['name'], {})
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'total': len(sources),
        'sources': sources
    }


@router.post("/sources/register")
async def register_source(
    request: Request,
    sm = Depends(get_source_manager)
):
    """
    Register a new data source
    
    Body:
    {
        "name": "coingecko",
        "type": "api",
        "endpoints": ["market", "categories", "trending"],
        "rate_limit": 30,
        "priority": 3,
        "interval_hours": 1
    }
    """
    data = await request.json()
    
    await sm.register_source(
        name=data['name'],
        source_type=data.get('type', 'api'),
        endpoints=data.get('endpoints', []),
        rate_limit=data.get('rate_limit', 10),
        priority=data.get('priority', 5),
        interval_hours=data.get('interval_hours', 6)
    )
    
    return {'ok': True, 'source': data['name'], 'status': 'registered'}


@router.post("/sources/{name}/status")
async def set_source_status(
    name: str,
    status: str = Query(..., description="Status: active, paused, disabled"),
    sm = Depends(get_source_manager)
):
    """Set source status"""
    if status not in ['active', 'paused', 'disabled']:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    await sm.set_status(name, status)
    return {'ok': True, 'source': name, 'status': status}


@router.post("/sources/{name}/priority")
async def set_source_priority(
    name: str,
    priority: int = Query(..., ge=1, le=10, description="Priority 1-10 (1=highest)"),
    db = Depends(get_db)
):
    """Set source priority"""
    result = await db.data_sources.update_one(
        {'name': name},
        {'$set': {'priority': priority, 'updated_at': datetime.now(timezone.utc)}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return {'ok': True, 'source': name, 'priority': priority}


@router.get("/sources/priority/{entity}")
async def get_sources_for_entity(
    entity: str,
    sm = Depends(get_source_manager)
):
    """Get sources in priority order for an entity type"""
    sources = await sm.get_priority_for_entity(entity)
    return {
        'entity': entity,
        'sources': sources
    }


# ═══════════════════════════════════════════════════════════════
# DROPSTAB SSR SCRAPER STATUS
# ═══════════════════════════════════════════════════════════════

@router.get("/dropstab/status")
async def get_dropstab_status():
    """Check Dropstab SSR scraper status"""
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'method': 'ssr_scrape',
        'requires_api_key': False,
        'description': 'Extracts data from Next.js __NEXT_DATA__ (coinsBody.coins)',
        'pages_scraped': [
            '/ - market data (100 coins)',
            '/vesting - token unlocks',
            '/categories - category list',
            '/top-performance - gainers/losers',
            '/investors - VC list',
            '/latest-fundraising-rounds - funding rounds',
            '/activities - listings, events'
        ],
        'note': 'SSR gives ~100 coins per page. BFF API (extra-bff.dropstab.com) requires session/cookies.'
    }


@router.post("/dropstab/test")
async def test_dropstab_scraper():
    """Test Dropstab SSR scraping"""
    from modules.intel.dropstab.scraper import dropstab_scraper
    
    coins = await dropstab_scraper.scrape_coins()
    
    if coins:
        return {
            'ok': True,
            'method': 'ssr_scrape',
            'message': f'Successfully scraped {len(coins)} coins from __NEXT_DATA__',
            'sample': coins[:2] if len(coins) > 2 else coins
        }
    else:
        return {
            'ok': False,
            'method': 'ssr_scrape',
            'message': 'No data found - page structure may have changed',
            'tip': 'Check if dropstab.com loads correctly'
        }


# ═══════════════════════════════════════════════════════════════
# COINGECKO POOL MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.get("/coingecko/pool")
async def get_coingecko_pool_status(pool = Depends(get_coingecko_pool)):
    """Get CoinGecko API pool status"""
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        **pool.get_status()
    }


@router.post("/coingecko/pool/add")
async def add_coingecko_instance(
    name: str = Query(..., description="Instance name"),
    api_key: Optional[str] = Query(None, description="Pro API key (optional)"),
    rate_limit: int = Query(10, description="Rate limit per minute"),
    pool = Depends(get_coingecko_pool)
):
    """Add new CoinGecko API instance to pool"""
    pool.add_instance(name, api_key, rate_limit)
    return {
        'ok': True,
        'instance': name,
        'rate_limit': rate_limit,
        'has_api_key': bool(api_key),
        'pool_status': pool.get_status()
    }


@router.post("/coingecko/pool/reset")
async def reset_coingecko_instances(pool = Depends(get_coingecko_pool)):
    """Reset unhealthy instances for retry"""
    pool.reset_unhealthy()
    return {
        'ok': True,
        'pool_status': pool.get_status()
    }


@router.post("/coingecko/sync")
async def sync_coingecko_all(sync = Depends(get_coingecko_sync)):
    """Run full CoinGecko sync"""
    result = await sync.sync_all()
    return result


@router.post("/coingecko/sync/{entity}")
async def sync_coingecko_entity(
    entity: str,
    sync = Depends(get_coingecko_sync)
):
    """Sync specific entity from CoinGecko"""
    if entity == 'global':
        result = await sync.sync_global_market()
    elif entity == 'categories':
        result = await sync.sync_categories()
    elif entity == 'trending':
        result = await sync.sync_trending()
    elif entity == 'top_coins':
        result = await sync.sync_top_coins()
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown entity: {entity}. Available: global, categories, trending, top_coins"
        )
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': 'coingecko',
        'entity': entity,
        **result
    }


@router.post("/coingecko/sync/coin/{coin_id}")
async def sync_coingecko_coin(
    coin_id: str,
    sync = Depends(get_coingecko_sync)
):
    """Sync specific coin from CoinGecko"""
    result = await sync.sync_coin(coin_id)
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': 'coingecko',
        **result
    }


# ═══════════════════════════════════════════════════════════════
# DATA MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.get("/data/overview")
async def get_data_overview(db = Depends(get_db)):
    """Get overview of all data in system"""
    collections = {
        'intel_investors': await db.intel_investors.count_documents({}),
        'intel_unlocks': await db.intel_unlocks.count_documents({}),
        'intel_fundraising': await db.intel_fundraising.count_documents({}),
        'intel_projects': await db.intel_projects.count_documents({}),
        'intel_activity': await db.intel_activity.count_documents({}),
        'intel_launchpads': await db.intel_launchpads.count_documents({}),
        'intel_categories': await db.intel_categories.count_documents({}),
        'intel_market': await db.intel_market.count_documents({}),
        'market_unlocks': await db.market_unlocks.count_documents({}),
        'moderation_queue': await db.moderation_queue.count_documents({})
    }
    
    # By source
    sources = {}
    for coll_name in ['intel_projects', 'intel_investors', 'intel_fundraising']:
        coll = db[coll_name]
        pipeline = [
            {'$group': {'_id': '$source', 'count': {'$sum': 1}}}
        ]
        async for doc in coll.aggregate(pipeline):
            source = doc['_id'] or 'unknown'
            if source not in sources:
                sources[source] = {}
            sources[source][coll_name] = doc['count']
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'collections': collections,
        'by_source': sources,
        'total_records': sum(collections.values())
    }


@router.get("/data/sources/{source}")
async def get_data_by_source(
    source: str,
    db = Depends(get_db)
):
    """Get data counts by source"""
    collections = [
        'intel_investors', 'intel_unlocks', 'intel_fundraising',
        'intel_projects', 'intel_activity', 'intel_launchpads',
        'intel_categories', 'intel_market'
    ]
    
    counts = {}
    for coll_name in collections:
        coll = db[coll_name]
        count = await coll.count_documents({'source': source})
        counts[coll_name] = count
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': source,
        'counts': counts,
        'total': sum(counts.values())
    }


@router.delete("/data/source/{source}")
async def delete_data_by_source(
    source: str,
    confirm: bool = Query(False, description="Confirm deletion"),
    db = Depends(get_db)
):
    """Delete all data from a specific source"""
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Set confirm=true to delete data"
        )
    
    collections = [
        'intel_investors', 'intel_unlocks', 'intel_fundraising',
        'intel_projects', 'intel_activity', 'intel_launchpads',
        'intel_categories', 'intel_market'
    ]
    
    deleted = {}
    for coll_name in collections:
        coll = db[coll_name]
        result = await coll.delete_many({'source': source})
        deleted[coll_name] = result.deleted_count
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': source,
        'deleted': deleted,
        'total_deleted': sum(deleted.values())
    }


# ═══════════════════════════════════════════════════════════════
# DATA FIELD CONFIG
# ═══════════════════════════════════════════════════════════════

@router.get("/config/fields")
async def get_field_config(db = Depends(get_db)):
    """Get field display configuration"""
    cursor = db.field_config.find({}, {'_id': 0})
    configs = await cursor.to_list(100)
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'configs': configs
    }


@router.post("/config/fields")
async def set_field_config(
    request: Request,
    db = Depends(get_db)
):
    """
    Set field display configuration
    
    Body:
    {
        "entity": "project",
        "fields": {
            "market_cap": {"show": true, "source_priority": ["dropstab", "coingecko"]},
            "fdv": {"show": true, "source_priority": ["coingecko", "dropstab"]},
            "circulating_supply": {"show": true, "source_priority": ["coingecko"]}
        }
    }
    """
    data = await request.json()
    
    doc = {
        'entity': data['entity'],
        'fields': data['fields'],
        'updated_at': datetime.now(timezone.utc)
    }
    
    await db.field_config.update_one(
        {'entity': data['entity']},
        {'$set': doc},
        upsert=True
    )
    
    return {'ok': True, 'entity': data['entity']}


# ═══════════════════════════════════════════════════════════════
# HEALTH & MONITORING
# ═══════════════════════════════════════════════════════════════

@router.get("/health/sources")
async def get_sources_health(sm = Depends(get_source_manager)):
    """Get health status of all sources"""
    health = await sm.get_all_health()
    unhealthy = await sm.get_unhealthy_sources()
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'all': health,
        'unhealthy': unhealthy
    }


@router.get("/logs/sync")
async def get_sync_logs(
    source: Optional[str] = None,
    limit: int = Query(50, le=200),
    db = Depends(get_db)
):
    """Get sync operation logs"""
    query = {}
    if source:
        query['source'] = source
    
    cursor = db.sync_logs.find(query, {'_id': 0})
    logs = await cursor.sort('timestamp', -1).limit(limit).to_list(limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'logs': logs
    }



# ═══════════════════════════════════════════════════════════════
# SCHEDULER V2 - SOURCE BASED
# ═══════════════════════════════════════════════════════════════

@router.post("/scheduler/v2/start")
async def start_scheduler_v2(db = Depends(get_db)):
    """
    Start SOURCE-BASED scheduler.
    
    Architecture:
    - Scraper collects ALL data from source
    - Parser detects entity types automatically
    - Pipeline normalizes and dedupes
    """
    from modules.intel.scheduler_v2 import init_scheduler_v2, scheduler_v2
    
    if scheduler_v2 is None:
        init_scheduler_v2(db)
    
    from modules.intel.scheduler_v2 import scheduler_v2 as sched
    result = await sched.start()
    return result


@router.post("/scheduler/v2/stop")
async def stop_scheduler_v2():
    """Stop source-based scheduler"""
    from modules.intel.scheduler_v2 import scheduler_v2
    
    if scheduler_v2 is None:
        return {"status": "not_initialized"}
    
    return await scheduler_v2.stop()


@router.get("/scheduler/v2/status")
async def get_scheduler_v2_status():
    """Get source-based scheduler status"""
    from modules.intel.scheduler_v2 import scheduler_v2
    
    if scheduler_v2 is None:
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "running": False,
            "message": "Scheduler not initialized"
        }
    
    return scheduler_v2.get_status()


@router.post("/scheduler/v2/sync/{source}")
async def run_source_sync(source: str, db = Depends(get_db)):
    """
    Run full sync for a source immediately.
    
    Sources: coingecko, dropstab, cryptorank
    """
    from modules.intel.scheduler_v2 import init_scheduler_v2, scheduler_v2
    
    if scheduler_v2 is None:
        init_scheduler_v2(db)
    
    from modules.intel.scheduler_v2 import scheduler_v2 as sched
    return await sched.run_source(source)


@router.post("/scheduler/v2/enable/{source}")
async def enable_source_sync(source: str):
    """Enable sync for a source"""
    from modules.intel.scheduler_v2 import scheduler_v2
    
    if scheduler_v2 is None:
        return {"error": "Scheduler not initialized"}
    
    return scheduler_v2.enable_source(source)


@router.post("/scheduler/v2/disable/{source}")
async def disable_source_sync(source: str):
    """Disable sync for a source"""
    from modules.intel.scheduler_v2 import scheduler_v2
    
    if scheduler_v2 is None:
        return {"error": "Scheduler not initialized"}
    
    return scheduler_v2.disable_source(source)


# ═══════════════════════════════════════════════════════════════
# PARSER - SMART DATA TYPE DETECTION
# ═══════════════════════════════════════════════════════════════

@router.post("/parser/parse/{source}")
async def parse_source_data(source: str, db = Depends(get_db)):
    """
    Parse ALL raw data from a source.
    Parser automatically detects entity types.
    
    Flow:
    1. Load raw JSON files from /app/data/raw/{source}/
    2. Detect entity type for each record
    3. Transform to unified schema
    4. Save to normalized tables
    """
    from modules.intel.parser import init_parser, intel_parser
    
    if intel_parser is None:
        init_parser(db)
    
    from modules.intel.parser import intel_parser as parser
    return await parser.parse_source(source)


@router.get("/parser/detect")
async def detect_entity_type(request: Request):
    """
    Test entity type detection on sample data.
    
    Body: raw JSON record
    Returns: detected type and confidence
    """
    from modules.intel.parser import EntityDetector
    
    data = await request.json()
    entity_type, confidence = EntityDetector.detect(data)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "detected_type": entity_type,
        "confidence": round(confidence, 3),
        "keys_analyzed": list(data.keys())[:20]
    }


# ═══════════════════════════════════════════════════════════════
# ENTITY INTELLIGENCE ENGINE
# ═══════════════════════════════════════════════════════════════

@router.post("/entity/resolve")
async def resolve_entity(request: Request, db = Depends(get_db)):
    """
    Resolve entity name to canonical entity_id.
    
    Body: {"name": "LayerZero Labs", "symbol": "ZRO"}
    Returns: {"entity_id": "layerzero", "confidence": 0.95, "match_type": "alias"}
    """
    from modules.intel.engine.entity_intelligence import init_entity_engine, entity_engine
    
    if entity_engine is None:
        init_entity_engine(db)
    
    from modules.intel.engine.entity_intelligence import entity_engine as engine
    
    data = await request.json()
    name = data.get("name", "")
    symbol = data.get("symbol")
    source = data.get("source")
    
    match = await engine.resolve(name, symbol, source)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "entity_id": match.entity_id,
        "name": match.name,
        "confidence": round(match.confidence, 3),
        "match_type": match.match_type
    }


@router.get("/entity/stats")
async def get_entity_stats(db = Depends(get_db)):
    """Get entity engine statistics"""
    from modules.intel.engine.entity_intelligence import init_entity_engine, entity_engine
    
    if entity_engine is None:
        init_entity_engine(db)
    
    from modules.intel.engine.entity_intelligence import entity_engine as engine
    
    stats = await engine.get_stats()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


@router.get("/entity/search/{query}")
async def search_entities(query: str, limit: int = 20, db = Depends(get_db)):
    """Search entities by name"""
    from modules.intel.engine.entity_intelligence import init_entity_engine, entity_engine
    
    if entity_engine is None:
        init_entity_engine(db)
    
    from modules.intel.engine.entity_intelligence import entity_engine as engine
    
    results = await engine.search_entities(query, limit)
    
    # Remove MongoDB _id
    for r in results:
        r.pop("_id", None)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "query": query,
        "count": len(results),
        "entities": results
    }


@router.get("/entity/{entity_id}")
async def get_entity(entity_id: str, db = Depends(get_db)):
    """Get entity details"""
    from modules.intel.engine.entity_intelligence import init_entity_engine, entity_engine
    
    if entity_engine is None:
        init_entity_engine(db)
    
    from modules.intel.engine.entity_intelligence import entity_engine as engine
    
    entity = await engine.get_entity(entity_id)
    
    if not entity:
        return {"error": f"Entity not found: {entity_id}"}
    
    # Remove MongoDB _id
    entity.pop("_id", None)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "entity": entity
    }


@router.post("/entity/merge")
async def merge_entities(request: Request, db = Depends(get_db)):
    """
    Merge two entities.
    
    Body: {"source": "layerzero-labs", "target": "layerzero"}
    """
    from modules.intel.engine.entity_intelligence import init_entity_engine, entity_engine
    
    if entity_engine is None:
        init_entity_engine(db)
    
    from modules.intel.engine.entity_intelligence import entity_engine as engine
    
    data = await request.json()
    source_id = data.get("source")
    target_id = data.get("target")
    
    result = await engine.merge_entities(source_id, target_id)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }



# ═══════════════════════════════════════════════════════════════
# EVENT INTELLIGENCE ENGINE
# ═══════════════════════════════════════════════════════════════

@router.post("/events/process")
async def process_all_events(db = Depends(get_db)):
    """
    Process all normalized data into unified events.
    
    Converts:
    - funding → funding events
    - unlocks → unlock events
    - sales → token_sale events
    """
    from modules.intel.engine.event_intelligence import init_event_engine, event_engine
    
    if event_engine is None:
        init_event_engine(db)
    
    from modules.intel.engine.event_intelligence import event_engine as engine
    
    results = await engine.process_all_events()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **results
    }


@router.get("/events/timeline/{entity_id}")
async def get_entity_timeline(entity_id: str, limit: int = 100, db = Depends(get_db)):
    """Get event timeline for entity"""
    from modules.intel.engine.event_intelligence import init_event_engine, event_engine
    
    if event_engine is None:
        init_event_engine(db)
    
    from modules.intel.engine.event_intelligence import event_engine as engine
    
    events = await engine.get_timeline(entity_id, limit)
    
    # Remove MongoDB _id
    for e in events:
        e.pop("_id", None)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "entity_id": entity_id,
        "count": len(events),
        "timeline": events
    }


@router.get("/events/upcoming")
async def get_upcoming_events(days: int = 30, limit: int = 100, db = Depends(get_db)):
    """Get upcoming events (unlocks, sales)"""
    from modules.intel.engine.event_intelligence import init_event_engine, event_engine
    
    if event_engine is None:
        init_event_engine(db)
    
    from modules.intel.engine.event_intelligence import event_engine as engine
    
    events = await engine.get_upcoming_events(days, limit)
    
    for e in events:
        e.pop("_id", None)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "days": days,
        "count": len(events),
        "events": events
    }


@router.get("/events/type/{event_type}")
async def get_events_by_type(event_type: str, limit: int = 100, db = Depends(get_db)):
    """Get events by type"""
    from modules.intel.engine.event_intelligence import init_event_engine, event_engine
    
    if event_engine is None:
        init_event_engine(db)
    
    from modules.intel.engine.event_intelligence import event_engine as engine
    
    events = await engine.get_events_by_type(event_type, limit)
    
    for e in events:
        e.pop("_id", None)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "event_type": event_type,
        "count": len(events),
        "events": events
    }


@router.get("/events/stats")
async def get_event_stats(db = Depends(get_db)):
    """Get event statistics"""
    from modules.intel.engine.event_intelligence import init_event_engine, event_engine
    
    if event_engine is None:
        init_event_engine(db)
    
    from modules.intel.engine.event_intelligence import event_engine as engine
    
    stats = await engine.get_stats()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


# ═══════════════════════════════════════════════════════════════
# CONFIDENCE ENGINE
# ═══════════════════════════════════════════════════════════════

@router.get("/confidence/weights")
async def get_source_weights():
    """Get source reliability weights"""
    from modules.intel.engine.confidence_scoring import init_confidence_engine, confidence_engine
    
    if confidence_engine is None:
        init_confidence_engine()
    
    from modules.intel.engine.confidence_scoring import confidence_engine as engine
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "weights": engine.get_source_weights()
    }


@router.post("/confidence/score")
async def score_fact(request: Request):
    """
    Score a fact's confidence.
    
    Body: {"source": "cryptorank", "observed_at": "2026-03-05T12:00:00Z", "agreement_ratio": 0.8}
    """
    from modules.intel.engine.confidence_scoring import init_confidence_engine, confidence_engine
    
    if confidence_engine is None:
        init_confidence_engine()
    
    from modules.intel.engine.confidence_scoring import confidence_engine as engine
    
    data = await request.json()
    
    result = engine.score_fact(
        source=data.get("source", "unknown"),
        observed_at=data.get("observed_at"),
        endpoint_stats=data.get("endpoint_stats"),
        agreement_ratio=data.get("agreement_ratio", 0.5),
        auth_level=data.get("auth_level", "public")
    )
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result.to_dict()
    }



# ═══════════════════════════════════════════════════════════════
# SOURCE DISCOVERY ENGINE
# ═══════════════════════════════════════════════════════════════

@router.post("/discovery/scan/seeds")
async def discover_seed_sources(db = Depends(get_db)):
    """
    Scan all seed domains for capabilities and endpoints.
    Seeds: dropstab, cryptorank, coingecko, defillama, messari, rootdata...
    """
    from modules.intel.engine.source_discovery import init_discovery_engine, discovery_engine
    
    if discovery_engine is None:
        init_discovery_engine(db)
    
    from modules.intel.engine.source_discovery import discovery_engine as engine
    
    result = await engine.discover_seeds()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/discovery/scan/{domain}")
async def scan_domain(domain: str, db = Depends(get_db)):
    """
    Scan specific domain for capabilities and API endpoints.
    
    Example: /api/admin/discovery/scan/defillama.com
    """
    from modules.intel.engine.source_discovery import init_discovery_engine, discovery_engine
    
    if discovery_engine is None:
        init_discovery_engine(db)
    
    from modules.intel.engine.source_discovery import discovery_engine as engine
    
    source = await engine.scan_domain(domain)
    
    if not source:
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "domain": domain,
            "found": False,
            "message": "No capabilities detected"
        }
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "found": True,
        **source.to_dict()
    }


@router.get("/discovery/sources")
async def list_discovered_sources(db = Depends(get_db)):
    """Get all discovered sources"""
    from modules.intel.engine.source_discovery import init_discovery_engine, discovery_engine
    
    if discovery_engine is None:
        init_discovery_engine(db)
    
    from modules.intel.engine.source_discovery import discovery_engine as engine
    
    sources = await engine.get_all_sources()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "count": len(sources),
        "sources": sources
    }


@router.post("/discovery/activate/{domain}")
async def activate_source(domain: str, db = Depends(get_db)):
    """Activate a discovered source for regular scraping"""
    from modules.intel.engine.source_discovery import init_discovery_engine, discovery_engine
    
    if discovery_engine is None:
        init_discovery_engine(db)
    
    from modules.intel.engine.source_discovery import discovery_engine as engine
    
    result = await engine.activate_source(domain)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.get("/discovery/stats")
async def discovery_stats(db = Depends(get_db)):
    """Get source discovery statistics"""
    from modules.intel.engine.source_discovery import init_discovery_engine, discovery_engine
    
    if discovery_engine is None:
        init_discovery_engine(db)
    
    from modules.intel.engine.source_discovery import discovery_engine as engine
    
    stats = await engine.get_stats()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


@router.get("/discovery/capability/{capability}")
async def sources_by_capability(capability: str, db = Depends(get_db)):
    """
    Get sources that provide a specific data type.
    
    Capabilities: unlocks, funding, investors, sales, tvl, markets, airdrops
    """
    from modules.intel.engine.source_discovery import init_discovery_engine, discovery_engine
    
    if discovery_engine is None:
        init_discovery_engine(db)
    
    from modules.intel.engine.source_discovery import discovery_engine as engine
    
    sources = await engine.get_sources_with_capability(capability)
    for s in sources:
        s.pop("_id", None)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "capability": capability,
        "count": len(sources),
        "sources": sources
    }


# ═══════════════════════════════════════════════════════════════
# FULL PIPELINE MANUAL TRIGGER
# ═══════════════════════════════════════════════════════════════

@router.post("/pipeline/run")
async def run_full_pipeline(db = Depends(get_db)):
    """
    Run full post-processing pipeline manually:
    Dedup → Entity Resolution → Event Building
    """
    from modules.intel.scheduler_v2 import init_scheduler_v2, scheduler_v2
    
    if scheduler_v2 is None:
        init_scheduler_v2(db)
    
    from modules.intel.scheduler_v2 import scheduler_v2 as sched
    result = await sched._run_post_pipeline("manual")
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


# ═══════════════════════════════════════════════════════════════
# DATA DRIFT DETECTION
# ═══════════════════════════════════════════════════════════════

@router.post("/drift/check")
async def check_data_drift(db = Depends(get_db)):
    """
    Run data drift detection across all sources.
    Checks for schema changes, count anomalies, freshness issues.
    """
    from modules.intel.engine.consistency_engine import DataConsistencyEngine
    
    engine = DataConsistencyEngine(db)
    checks = await engine.run_all_checks()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **engine.get_health_status()
    }


@router.get("/drift/reliability")
async def get_source_reliability(db = Depends(get_db)):
    """Get reliability scores for all data sources"""
    from modules.intel.engine.consistency_engine import DataConsistencyEngine
    
    engine = DataConsistencyEngine(db)
    await engine.run_all_checks()
    reliability = engine.get_source_reliability()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "sources": {k: v.to_dict() for k, v in reliability.items()}
    }


# ═══════════════════════════════════════════════════════════════
# CRYPTORANK INGEST - Funding/Unlocks/Investors
# ═══════════════════════════════════════════════════════════════

def get_cryptorank_sync():
    """Dependency to get CryptoRank sync service"""
    from server import db
    from modules.intel.sources.cryptorank.sync import CryptoRankSync
    return CryptoRankSync(db)


@router.post("/cryptorank/ingest/funding")
async def ingest_cryptorank_funding(
    request: Request,
    sync = Depends(get_cryptorank_sync)
):
    """
    Ingest funding rounds from CryptoRank.
    
    Body: CryptoRank API response ({"total": N, "data": [...]})
    or raw list of funding records
    """
    data = await request.json()
    result = await sync.ingest_funding(data)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source": "cryptorank",
        "entity": "funding",
        **result
    }


@router.post("/cryptorank/ingest/investors")
async def ingest_cryptorank_investors(
    request: Request,
    sync = Depends(get_cryptorank_sync)
):
    """
    Ingest investors from CryptoRank.
    
    Body: List of investor records
    """
    data = await request.json()
    result = await sync.ingest_investors(data)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source": "cryptorank",
        "entity": "investors",
        **result
    }


@router.post("/cryptorank/ingest/unlocks")
async def ingest_cryptorank_unlocks(
    request: Request,
    unlock_type: str = Query("vesting", description="Type: vesting or tge"),
    sync = Depends(get_cryptorank_sync)
):
    """
    Ingest token unlocks from CryptoRank.
    
    Body: List of unlock records
    Query: unlock_type=vesting|tge
    """
    data = await request.json()
    result = await sync.ingest_unlocks(data, unlock_type)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source": "cryptorank",
        "entity": f"unlocks_{unlock_type}",
        **result
    }


@router.post("/cryptorank/ingest/all")
async def ingest_cryptorank_all(
    request: Request,
    sync = Depends(get_cryptorank_sync)
):
    """
    Ingest all CryptoRank data at once.
    
    Body: {
        "funding": {...},
        "investors": [...],
        "unlocks": [...],
        "tge_unlocks": [...],
        "categories": [...],
        "launchpads": [...],
        "market": {...}
    }
    """
    data = await request.json()
    result = await sync.ingest_all(data)
    return result


@router.get("/cryptorank/stats")
async def get_cryptorank_stats(sync = Depends(get_cryptorank_sync)):
    """Get CryptoRank sync statistics"""
    return await sync.get_sync_stats()


@router.post("/cryptorank/fetch/funding")
async def fetch_and_ingest_funding(
    limit: int = Query(100, description="Number of records to fetch"),
    offset: int = Query(0, description="Offset for pagination"),
    db = Depends(get_db)
):
    """
    Fetch funding rounds directly from CryptoRank API and ingest.
    
    Scrapes: https://api.cryptorank.io/v0/coins/funding-rounds
    """
    import aiohttp
    from modules.intel.sources.cryptorank.sync import CryptoRankSync
    
    url = f"https://api.cryptorank.io/v0/coins/funding-rounds?limit={limit}&offset={offset}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=30) as resp:
            if resp.status != 200:
                return {"error": f"CryptoRank API returned {resp.status}"}
            data = await resp.json()
    
    sync = CryptoRankSync(db)
    result = await sync.ingest_funding(data)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source": "cryptorank",
        "entity": "funding",
        "api_total": data.get("total", 0),
        **result
    }


@router.post("/cryptorank/fetch/unlocks")
async def fetch_and_ingest_unlocks(
    days: int = Query(30, description="Days ahead to fetch"),
    db = Depends(get_db)
):
    """
    Fetch upcoming token unlocks directly from CryptoRank API and ingest.
    
    Scrapes: https://api.cryptorank.io/v0/token-unlocks/unlocks
    """
    import aiohttp
    from datetime import datetime, timedelta
    from modules.intel.sources.cryptorank.sync import CryptoRankSync
    
    # Calculate date range
    today = datetime.now().strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    
    url = f"https://api.cryptorank.io/v0/token-unlocks/unlocks?dateFrom={today}&dateTo={end_date}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=30) as resp:
            if resp.status != 200:
                return {"error": f"CryptoRank API returned {resp.status}"}
            data = await resp.json()
    
    sync = CryptoRankSync(db)
    result = await sync.ingest_unlocks(data.get("data", data), "vesting")
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source": "cryptorank",
        "entity": "unlocks",
        "date_range": f"{today} to {end_date}",
        **result
    }


@router.post("/cryptorank/fetch/investors")
async def fetch_and_ingest_investors(
    limit: int = Query(100, description="Number of investors to fetch"),
    db = Depends(get_db)
):
    """
    Fetch top investors directly from CryptoRank API and ingest.
    
    Scrapes investor data from funding rounds
    """
    import aiohttp
    from modules.intel.sources.cryptorank.sync import CryptoRankSync
    from modules.intel.sources.cryptorank.parsers.investors import parse_investors_from_funding
    
    # Fetch funding rounds which contain investor data
    url = f"https://api.cryptorank.io/v0/coins/funding-rounds?limit={limit}&offset=0"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=30) as resp:
            if resp.status != 200:
                return {"error": f"CryptoRank API returned {resp.status}"}
            data = await resp.json()
    
    # Extract unique investors from funding rounds
    all_investors = []
    seen = set()
    
    for funding in data.get("data", []):
        for fund in funding.get("funds", []):
            key = fund.get("key")
            if key and key not in seen:
                seen.add(key)
                all_investors.append(fund)
    
    # Parse and ingest
    sync = CryptoRankSync(db)
    docs = parse_investors_from_funding(all_investors)
    
    collection = db.intel_investors
    changed = 0
    
    from modules.intel.common.storage import upsert_with_diff
    for doc in docs:
        result = await upsert_with_diff(collection, doc)
        if result['changed']:
            changed += 1
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source": "cryptorank",
        "entity": "investors",
        "total": len(docs),
        "changed": changed,
        "from_funding_rounds": len(data.get("data", []))
    }


@router.post("/cryptorank/sync/all")
async def sync_all_cryptorank(db = Depends(get_db)):
    """
    Full CryptoRank sync - funding, unlocks, investors.
    
    Fetches from CryptoRank API and ingests all data.
    """
    import aiohttp
    from datetime import datetime as dt, timedelta
    from modules.intel.sources.cryptorank.sync import CryptoRankSync
    from modules.intel.sources.cryptorank.parsers.investors import parse_investors_from_funding
    from modules.intel.common.storage import upsert_with_diff
    
    sync = CryptoRankSync(db)
    results = {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source": "cryptorank",
        "synced": {}
    }
    
    async with aiohttp.ClientSession() as session:
        # 1. Funding rounds (multiple pages)
        try:
            all_funding = []
            for offset in range(0, 500, 100):
                url = f"https://api.cryptorank.io/v0/coins/funding-rounds?limit=100&offset={offset}"
                async with session.get(url, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        all_funding.extend(data.get("data", []))
                        if len(data.get("data", [])) < 100:
                            break
            
            if all_funding:
                result = await sync.ingest_funding({"data": all_funding})
                results["synced"]["funding"] = result
                
                # Extract investors from funding
                all_investors = []
                seen = set()
                for funding in all_funding:
                    for fund in funding.get("funds", []):
                        key = fund.get("key")
                        if key and key not in seen:
                            seen.add(key)
                            all_investors.append(fund)
                
                docs = parse_investors_from_funding(all_investors)
                collection = db.intel_investors
                changed = 0
                for doc in docs:
                    res = await upsert_with_diff(collection, doc)
                    if res['changed']:
                        changed += 1
                results["synced"]["investors"] = {"total": len(docs), "changed": changed}
        except Exception as e:
            results["synced"]["funding"] = {"error": str(e)}
        
        # 2. Token unlocks
        try:
            today = dt.now().strftime("%Y-%m-%d")
            end_date = (dt.now() + timedelta(days=90)).strftime("%Y-%m-%d")
            url = f"https://api.cryptorank.io/v0/token-unlocks/unlocks?dateFrom={today}&dateTo={end_date}"
            
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = await sync.ingest_unlocks(data.get("data", data), "vesting")
                    results["synced"]["unlocks"] = result
        except Exception as e:
            results["synced"]["unlocks"] = {"error": str(e)}
    
    return results
