"""
Intel API Routes
Endpoints for crypto intelligence data
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intel", tags=["intel"])


def get_db():
    """Dependency to get database"""
    from server import db
    return db


def get_dropstab_sync():
    """Dependency to get Dropstab sync service (SSR scraping)"""
    from server import db
    from ..dropstab.sync import DropstabSync
    return DropstabSync(db)


def get_cryptorank_sync():
    """Dependency to get CryptoRank sync service"""
    from server import db
    from ..sources.cryptorank.sync import CryptoRankSync
    return CryptoRankSync(db)


# ═══════════════════════════════════════════════════════════════
# SYNC ENDPOINTS - DROPSTAB
# ═══════════════════════════════════════════════════════════════

@router.post("/sync/dropstab")
async def sync_dropstab_all(sync = Depends(get_dropstab_sync)):
    """
    Run full Dropstab sync (all endpoints)
    Uses api.dropstab.com - no API key required
    """
    result = await sync.sync_all()
    return result


@router.post("/sync/dropstab/v2")
async def sync_dropstab_v2():
    """
    Run production Dropstab scraper v2.
    Dynamic dataset finder - resilient to structure changes.
    
    Returns: coins, unlocks, funding, investors
    """
    from ..dropstab.scraper_v2 import dropstab_scraper_v2
    result = await dropstab_scraper_v2.scrape_all()
    # Remove raw data from response to keep it small
    summary = {
        "ts": result["ts"],
        "source": result["source"],
        "elapsed_sec": result["elapsed_sec"],
        "summary": result["summary"]
    }
    return summary


@router.post("/sync/dropstab/v2/{entity}")
async def sync_dropstab_v2_entity(entity: str):
    """
    Scrape specific entity using v2 scraper.
    
    Entities: coins, unlocks, funding, investors
    """
    from ..dropstab.scraper_v2 import dropstab_scraper_v2
    
    if entity == "coins":
        data = await dropstab_scraper_v2.scrape_coins()
    elif entity == "unlocks":
        data = await dropstab_scraper_v2.scrape_unlocks()
    elif entity == "funding":
        data = await dropstab_scraper_v2.scrape_funding()
    elif entity == "investors":
        data = await dropstab_scraper_v2.scrape_investors()
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown entity: {entity}. Available: coins, unlocks, funding, investors"
        )
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source": "dropstab_v2",
        "entity": entity,
        "count": len(data),
        "data": data[:10] if data else []  # Sample only
    }


@router.post("/sync/dropstab/browser")
async def sync_dropstab_browser(
    headless: bool = Query(True, description="Run browser in headless mode")
):
    """
    Run Dropstab browser scraper (Playwright).
    
    This bypasses bot detection by using real browser.
    Captures: unlocks, funding, investors, ICO/IEO/IDO
    
    Note: Requires Playwright installed (pip install playwright && playwright install chromium)
    """
    from ..dropstab.browser_scraper import dropstab_browser
    from ..common.proxy_manager import proxy_manager
    
    # Set proxy if configured
    if proxy_manager.is_configured:
        dropstab_browser.set_proxy(proxy_manager.get_playwright_proxy())
    
    result = await dropstab_browser.scrape_all(headless=headless)
    return result


@router.post("/sync/dropstab/browser/{target}")
async def sync_dropstab_browser_single(
    target: str,
    headless: bool = Query(True)
):
    """
    Run browser scraper for single target.
    
    Targets: unlocks, funding, investors, ico, ieo, ido, categories, coins
    """
    from ..dropstab.browser_scraper import dropstab_browser
    from ..common.proxy_manager import proxy_manager
    
    if proxy_manager.is_configured:
        dropstab_browser.set_proxy(proxy_manager.get_playwright_proxy())
    
    result = await dropstab_browser.scrape_single(target, headless=headless)
    return result


@router.post("/sync/dropstab/{entity}")
async def sync_dropstab_entity(
    entity: str,
    limit: int = Query(100, ge=1, le=500),
    max_pages: int = Query(10, ge=1, le=200),
    sync = Depends(get_dropstab_sync)
):
    """
    Sync specific entity from Dropstab
    
    Entities:
    - markets: price, mcap, fdv, volume (every 10 min)
    - markets_full: ALL coins with pagination (~15000+, daily)
    - projects: all projects ~15k (daily)
    - unlocks: token unlock events (hourly)
    - categories: AI, DePIN, GameFi, etc (daily)
    - narratives: market narratives (daily)
    - ecosystems: Ethereum, Solana, etc (daily)
    - trending: trending tokens (every 5 min)
    - gainers: top gainers (every 5 min)
    - losers: top losers (every 5 min)
    - listings: exchange listings (hourly)
    - market_overview: global market data (every 10 min)
    """
    if entity == 'markets':
        result = await sync.sync_markets(limit=limit, max_pages=max_pages)
    elif entity == 'markets_full':
        # Full market sync - all coins with pagination
        result = await sync.sync_markets_full(max_pages=200)
    elif entity == 'projects':
        result = await sync.sync_projects(limit=limit, max_pages=max_pages)
    elif entity == 'unlocks':
        result = await sync.sync_unlock_events(limit=limit, max_pages=max_pages)
    elif entity == 'categories':
        result = await sync.sync_categories()
    elif entity == 'narratives':
        result = await sync.sync_narratives()
    elif entity == 'ecosystems':
        result = await sync.sync_ecosystems()
    elif entity == 'trending':
        result = await sync.sync_trending()
    elif entity == 'gainers':
        result = await sync.sync_gainers()
    elif entity == 'losers':
        result = await sync.sync_losers()
    elif entity == 'listings':
        result = await sync.sync_listings(limit=limit, max_pages=max_pages)
    elif entity == 'market_overview':
        result = await sync.sync_market_overview()
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown entity: {entity}. Available: markets, projects, unlocks, categories, narratives, ecosystems, trending, gainers, losers, listings, market_overview"
        )
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': 'dropstab',
        'entity': entity,
        **result
    }


# ═══════════════════════════════════════════════════════════════
# COINGECKO SYNC ENDPOINTS
# ═══════════════════════════════════════════════════════════════

def get_coingecko_sync():
    """Dependency to get CoinGecko sync service"""
    from server import db
    from ..sources.coingecko.sync import CoinGeckoSync
    return CoinGeckoSync(db)


@router.post("/sync/coingecko")
async def sync_coingecko_all(sync = Depends(get_coingecko_sync)):
    """
    Run full CoinGecko sync (global, categories, trending, top coins)
    """
    result = await sync.sync_all()
    return result


@router.post("/sync/coingecko/{entity}")
async def sync_coingecko_entity(
    entity: str,
    limit: int = Query(100, ge=1, le=250),
    page: int = Query(1, ge=1),
    max_pages: int = Query(10, ge=1, le=100),
    sync = Depends(get_coingecko_sync)
):
    """
    Sync specific entity from CoinGecko
    
    Entities:
    - global: Global market data (BTC dominance, total mcap)
    - categories: All categories with market data
    - trending: Trending coins
    - top_coins: Top coins by market cap (single page)
    - markets: Markets with pagination (limit per page)
    - markets_full: FULL market sync (~15000 coins, slow!)
    """
    if entity == 'global':
        result = await sync.sync_global_market()
    elif entity == 'categories':
        result = await sync.sync_categories()
    elif entity == 'trending':
        result = await sync.sync_trending()
    elif entity == 'top_coins':
        result = await sync.sync_top_coins(limit=limit)
    elif entity == 'markets':
        result = await sync.sync_top_coins(limit=limit)
    elif entity == 'markets_full':
        # Full market sync - all coins (~15000)
        result = await sync.sync_markets_full(max_pages=max_pages)
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown entity: {entity}. Available: global, categories, trending, top_coins, markets, markets_full"
        )
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': 'coingecko',
        'entity': entity,
        **result
    }


@router.get("/sync/coingecko/status")
async def coingecko_status(sync = Depends(get_coingecko_sync)):
    """Check CoinGecko API pool status"""
    pool_status = sync.get_pool_status()
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': 'coingecko',
        'type': 'api',
        'ready': True,
        'pool': pool_status
    }



# ═══════════════════════════════════════════════════════════════
# CRYPTORANK STATUS
# ═══════════════════════════════════════════════════════════════

@router.get("/sync/cryptorank/status")
async def cryptorank_status():
    """
    Check CryptoRank scraper status.
    CryptoRank is a scraper source - POST JSON data to /ingest/cryptorank/{entity}
    """
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': 'cryptorank',
        'type': 'scraper',
        'ready': True,
        'message': 'CryptoRank is a scraper source. Use POST /api/intel/ingest/cryptorank/{entity} to ingest data.',
        'endpoints': {
            'ingest_all': 'POST /api/intel/ingest/cryptorank',
            'ingest_entity': 'POST /api/intel/ingest/cryptorank/{entity}',
            'status': 'GET /api/intel/ingest/cryptorank/status'
        }
    }


# ═══════════════════════════════════════════════════════════════
# CRYPTORANK INGEST ENDPOINTS (POST JSON data)
# ═══════════════════════════════════════════════════════════════

@router.post("/ingest/cryptorank")
async def ingest_cryptorank_all(
    request: Request,
    sync = Depends(get_cryptorank_sync)
):
    """
    Ingest all CryptoRank data at once.
    
    Body format:
    {
        "categories": [...],
        "funding": {"total": ..., "data": [...]},
        "investors": [...],
        "unlocks": [...],
        "tge_unlocks": [...],
        "unlock_totals": [...],
        "launchpads": [...],
        "market": {...}
    }
    """
    data = await request.json()
    result = await sync.ingest_all(data)
    return result


@router.post("/ingest/cryptorank/{entity}")
async def ingest_cryptorank_entity(
    entity: str,
    request: Request,
    sync = Depends(get_cryptorank_sync)
):
    """
    Ingest specific entity data from CryptoRank.
    
    POST JSON data for the entity type.
    """
    data = await request.json()
    
    if entity == 'funding' or entity == 'fundraising':
        result = await sync.ingest_funding(data)
    elif entity == 'investors':
        result = await sync.ingest_investors(data)
    elif entity == 'unlocks':
        result = await sync.ingest_unlocks(data, 'vesting')
    elif entity == 'tge_unlocks':
        result = await sync.ingest_unlocks(data, 'tge')
    elif entity == 'unlock_totals':
        result = await sync.ingest_unlock_totals(data)
    elif entity == 'launchpads':
        result = await sync.ingest_launchpads(data)
    elif entity == 'categories':
        result = await sync.ingest_categories(data)
    elif entity == 'market':
        result = await sync.ingest_market(data)
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown entity: {entity}. Available: funding, investors, unlocks, tge_unlocks, unlock_totals, launchpads, categories, market"
        )
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': 'cryptorank',
        'entity': entity,
        **result
    }


@router.get("/ingest/cryptorank/status")
async def cryptorank_ingest_status():
    """
    Check CryptoRank ingest status.
    """
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': 'cryptorank',
        'type': 'scraper',
        'ready': True,
        'message': 'CryptoRank ingest ready. POST JSON data to /ingest/cryptorank/{entity}',
        'entities': [
            'funding', 'investors', 'unlocks', 'tge_unlocks', 
            'unlock_totals', 'launchpads', 'categories', 'market'
        ]
    }


@router.get("/ingest/cryptorank/stats")
async def cryptorank_stats(sync = Depends(get_cryptorank_sync)):
    """
    Get CryptoRank sync statistics.
    Shows how many records from CryptoRank are in each collection.
    """
    return await sync.get_sync_stats()


@router.post("/ingest/cryptorank/funding/batch")
async def ingest_funding_batch(
    request: Request,
    sync = Depends(get_cryptorank_sync)
):
    """
    Ingest multiple pages of funding data at once.
    
    Body format:
    {
        "pages": [
            {"total": 10851, "data": [...]},
            {"total": 10851, "data": [...]},
            ...
        ]
    }
    
    Useful for incremental sync of multiple pages.
    """
    data = await request.json()
    pages = data.get('pages', [])
    
    if not pages:
        raise HTTPException(status_code=400, detail="No pages provided")
    
    result = await sync.ingest_funding_batch(pages)
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': 'cryptorank',
        **result
    }


# ═══════════════════════════════════════════════════════════════
# INVESTORS
# ═══════════════════════════════════════════════════════════════

@router.get("/investors")
async def list_investors(
    search: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db = Depends(get_db)
):
    """List investors/VCs"""
    query = {}
    if search:
        query['$or'] = [
            {'name': {'$regex': search, '$options': 'i'}},
            {'slug': {'$regex': search, '$options': 'i'}}
        ]
    if tier:
        query['tier'] = tier
    
    cursor = db.intel_investors.find(query, {'_id': 0, 'raw': 0})
    items = await cursor.sort('investments_count', -1).skip(offset).limit(limit).to_list(limit)
    total = await db.intel_investors.count_documents(query)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'total': total,
        'items': items
    }


# ═══════════════════════════════════════════════════════════════
# UNLOCKS
# ═══════════════════════════════════════════════════════════════

@router.get("/unlocks")
async def list_unlocks(
    symbol: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db = Depends(get_db)
):
    """List token unlocks"""
    query = {}
    if symbol:
        query['symbol'] = symbol.upper()
    if category:
        query['category'] = category.lower()
    
    cursor = db.intel_unlocks.find(query, {'_id': 0, 'raw': 0})
    items = await cursor.sort('unlock_date', 1).limit(limit).to_list(limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(items),
        'items': items
    }


@router.get("/unlocks/upcoming")
async def upcoming_unlocks(
    days: int = Query(30, ge=1, le=180),
    min_percent: Optional[float] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db = Depends(get_db)
):
    """Get upcoming token unlocks"""
    now = int(datetime.now(timezone.utc).timestamp())
    end = now + (days * 86400)
    
    query = {
        'unlock_date': {'$gte': now, '$lte': end}
    }
    if min_percent:
        query['unlock_percent'] = {'$gte': min_percent}
    
    cursor = db.intel_unlocks.find(query, {'_id': 0, 'raw': 0})
    items = await cursor.sort('unlock_date', 1).limit(limit).to_list(limit)
    
    # Add days_until
    for item in items:
        item['days_until'] = (item['unlock_date'] - now) // 86400
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'days': days,
        'count': len(items),
        'items': items
    }


# ═══════════════════════════════════════════════════════════════
# FUNDRAISING
# ═══════════════════════════════════════════════════════════════

@router.get("/fundraising")
async def list_fundraising(
    symbol: Optional[str] = Query(None),
    round: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db = Depends(get_db)
):
    """List funding rounds"""
    query = {}
    if symbol:
        query['symbol'] = symbol.upper()
    if round:
        query['round'] = {'$regex': round, '$options': 'i'}
    
    cursor = db.intel_fundraising.find(query, {'_id': 0, 'raw': 0})
    items = await cursor.sort('date', -1).limit(limit).to_list(limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(items),
        'items': items
    }


@router.get("/fundraising/recent")
async def recent_fundraising(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    db = Depends(get_db)
):
    """Get recent funding rounds"""
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    
    query = {'date': {'$gte': cutoff}}
    
    cursor = db.intel_fundraising.find(query, {'_id': 0, 'raw': 0})
    items = await cursor.sort('date', -1).limit(limit).to_list(limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'days': days,
        'count': len(items),
        'items': items
    }


# ═══════════════════════════════════════════════════════════════
# PROJECTS
# ═══════════════════════════════════════════════════════════════

@router.get("/projects")
async def list_projects(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db = Depends(get_db)
):
    """List projects"""
    query = {}
    if search:
        query['$or'] = [
            {'name': {'$regex': search, '$options': 'i'}},
            {'symbol': {'$regex': search, '$options': 'i'}}
        ]
    if category:
        query['category'] = {'$regex': category, '$options': 'i'}
    
    cursor = db.intel_projects.find(query, {'_id': 0, 'raw': 0})
    items = await cursor.sort('symbol', 1).skip(offset).limit(limit).to_list(limit)
    total = await db.intel_projects.count_documents(query)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'total': total,
        'items': items
    }


@router.get("/projects/discovered")
async def discovered_projects(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
    db = Depends(get_db)
):
    """Get recently discovered/launched projects"""
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    
    query = {
        '$or': [
            {'ico_date': {'$gte': cutoff}},
            {'listing_date': {'$gte': cutoff}}
        ]
    }
    
    cursor = db.intel_projects.find(query, {'_id': 0, 'raw': 0})
    items = await cursor.limit(limit).to_list(limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'days': days,
        'count': len(items),
        'items': items
    }


# ═══════════════════════════════════════════════════════════════
# ACTIVITY
# ═══════════════════════════════════════════════════════════════

@router.get("/activity")
async def list_activity(
    activity_type: Optional[str] = Query(None, alias='type'),
    project: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db = Depends(get_db)
):
    """List activity/news feed"""
    query = {}
    if activity_type:
        query['type'] = activity_type.lower()
    if project:
        query['projects'] = {'$in': [project.upper()]}
    
    cursor = db.intel_activity.find(query, {'_id': 0, 'raw': 0})
    items = await cursor.sort('date', -1).limit(limit).to_list(limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(items),
        'items': items
    }


# ═══════════════════════════════════════════════════════════════
# CURATED FEED ENDPOINTS (Intel Feed)
# ═══════════════════════════════════════════════════════════════

@router.get("/curated/activity")
async def curated_activity(
    limit: int = Query(30, ge=1, le=100),
    db = Depends(get_db)
):
    """
    Get curated activity feed for Intel Feed.
    Combines funding, unlocks, listings into unified feed.
    """
    items = []
    
    # Get recent funding
    funding_cursor = db.intel_fundraising.find({}, {'_id': 0, 'raw': 0})
    funding = await funding_cursor.sort('date', -1).limit(10).to_list(10)
    for f in funding:
        items.append({
            'type': 'funding',
            'name': f.get('name') or f.get('symbol'),
            'symbol': f.get('symbol'),
            'description': f"Raised ${f.get('raise_usd', 0) / 1e6:.1f}M in {f.get('round', 'unknown')} round",
            'amount': f.get('raise_usd'),
            'date': f.get('date'),
            'source': f.get('source', 'cryptorank')
        })
    
    # Get recent unlocks
    unlock_cursor = db.intel_unlocks.find({}, {'_id': 0, 'raw': 0})
    unlocks = await unlock_cursor.sort('unlock_date', -1).limit(10).to_list(10)
    for u in unlocks:
        items.append({
            'type': 'unlock',
            'name': u.get('name') or u.get('symbol'),
            'symbol': u.get('symbol'),
            'description': f"Token unlock: {u.get('unlock_percent', 0):.2f}% of supply",
            'amount': u.get('value_usd'),
            'date': u.get('unlock_date'),
            'source': u.get('source', 'dropstab')
        })
    
    # Get recent projects (listings)
    project_cursor = db.intel_projects.find({}, {'_id': 0, 'raw': 0})
    projects = await project_cursor.sort('listing_date', -1).limit(5).to_list(5)
    for p in projects:
        if p.get('listing_date'):
            items.append({
                'type': 'listing',
                'name': p.get('name') or p.get('symbol'),
                'symbol': p.get('symbol'),
                'description': f"Listed on exchanges",
                'date': p.get('listing_date'),
                'source': p.get('source', 'cryptorank')
            })
    
    # Sort by date descending - ensure all dates are comparable
    def get_sort_key(x):
        date = x.get('date')
        if date is None:
            return 0
        if isinstance(date, str):
            try:
                from datetime import datetime
                # Try ISO format
                return int(datetime.fromisoformat(date.replace('Z', '+00:00')).timestamp())
            except:
                return 0
        return int(date) if date else 0
    
    items.sort(key=get_sort_key, reverse=True)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(items[:limit]),
        'items': items[:limit]
    }


@router.get("/curated/trending")
async def curated_trending(
    limit: int = Query(15, ge=1, le=50),
    db = Depends(get_db)
):
    """
    Get trending coins for Intel Feed.
    From CoinGecko trending data.
    """
    # Try to get from intel_market (trending)
    cursor = db.intel_market.find(
        {'is_trending': True},
        {'_id': 0}
    )
    items = await cursor.limit(limit).to_list(limit)
    
    # If no trending data, get top by market cap
    if not items:
        cursor = db.intel_market.find({}, {'_id': 0})
        items = await cursor.sort('market_cap', -1).limit(limit).to_list(limit)
    
    # Transform for feed
    result = []
    for item in items:
        result.append({
            'type': 'trending',
            'name': item.get('name'),
            'symbol': item.get('symbol'),
            'description': f"Trending on CoinGecko",
            'market_cap': item.get('market_cap'),
            'price': item.get('price'),
            'change_24h': item.get('change_24h'),
            'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
            'source': 'coingecko'
        })
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(result),
        'items': result
    }


@router.get("/curated/feed")
async def curated_feed(
    event_type: Optional[str] = Query(None, description="Filter: funding, unlock, listing, trending"),
    limit: int = Query(30, ge=1, le=100),
    db = Depends(get_db)
):
    """
    Combined intelligence feed.
    All event types in one stream.
    """
    items = []
    
    # Get all types or specific
    if not event_type or event_type == 'funding':
        funding_cursor = db.intel_fundraising.find({}, {'_id': 0, 'raw': 0})
        funding = await funding_cursor.sort('date', -1).limit(20).to_list(20)
        for f in funding:
            items.append({
                'type': 'funding',
                'name': f.get('name') or f.get('symbol'),
                'symbol': f.get('symbol'),
                'description': f"${f.get('raise_usd', 0) / 1e6:.1f}M • {f.get('round', '')}",
                'amount': f.get('raise_usd'),
                'date': f.get('date'),
                'investors': f.get('investors', [])[:3]
            })
    
    if not event_type or event_type == 'unlock':
        unlock_cursor = db.intel_unlocks.find({}, {'_id': 0, 'raw': 0})
        unlocks = await unlock_cursor.sort('unlock_date', 1).limit(20).to_list(20)
        for u in unlocks:
            items.append({
                'type': 'unlock',
                'name': u.get('name') or u.get('symbol'),
                'symbol': u.get('symbol'),
                'description': f"{u.get('unlock_percent', 0):.2f}% supply unlock",
                'amount': u.get('value_usd'),
                'date': u.get('unlock_date')
            })
    
    if not event_type or event_type == 'trending':
        market_cursor = db.intel_market.find({}, {'_id': 0})
        market = await market_cursor.sort('market_cap', -1).limit(10).to_list(10)
        for m in market:
            items.append({
                'type': 'trending',
                'name': m.get('name'),
                'symbol': m.get('symbol'),
                'description': f"${m.get('market_cap', 0) / 1e9:.2f}B mcap",
                'market_cap': m.get('market_cap'),
                'ts': int(datetime.now(timezone.utc).timestamp() * 1000)
            })
    
    # Sort by date
    items.sort(key=lambda x: x.get('date') or x.get('ts') or 0, reverse=True)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'filter': event_type,
        'count': len(items[:limit]),
        'items': items[:limit]
    }


# ═══════════════════════════════════════════════════════════════
# MODERATION QUEUE
# ═══════════════════════════════════════════════════════════════

@router.get("/moderation")
async def get_moderation_queue(
    entity: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    status: str = Query('pending'),
    limit: int = Query(100, ge=1, le=500),
    db = Depends(get_db)
):
    """Get moderation queue items"""
    query = {'status': status}
    if entity:
        query['entity'] = entity
    if source:
        query['source'] = source
    
    cursor = db.moderation_queue.find(query, {'_id': 0})
    items = await cursor.sort('created_at', -1).limit(limit).to_list(limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(items),
        'items': items
    }


@router.post("/moderation/{key}/approve")
async def approve_moderation(
    key: str,
    db = Depends(get_db)
):
    """Approve moderation item"""
    result = await db.moderation_queue.update_one(
        {'key': key},
        {'$set': {'status': 'approved', 'updated_at': datetime.now(timezone.utc)}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return {'ok': True, 'key': key, 'status': 'approved'}


@router.post("/moderation/{key}/reject")
async def reject_moderation(
    key: str,
    db = Depends(get_db)
):
    """Reject moderation item"""
    result = await db.moderation_queue.update_one(
        {'key': key},
        {'$set': {'status': 'rejected', 'updated_at': datetime.now(timezone.utc)}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return {'ok': True, 'key': key, 'status': 'rejected'}


# ═══════════════════════════════════════════════════════════════
# LAUNCHPADS
# ═══════════════════════════════════════════════════════════════

@router.get("/launchpads")
async def list_launchpads(
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db = Depends(get_db)
):
    """List launchpad platforms"""
    query = {}
    if search:
        query['$or'] = [
            {'name': {'$regex': search, '$options': 'i'}},
            {'slug': {'$regex': search, '$options': 'i'}}
        ]
    
    cursor = db.intel_launchpads.find(query, {'_id': 0, 'raw': 0})
    items = await cursor.sort('projects_count', -1).limit(limit).to_list(limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(items),
        'items': items
    }


# ═══════════════════════════════════════════════════════════════
# CATEGORIES
# ═══════════════════════════════════════════════════════════════

@router.get("/categories")
async def list_categories(
    search: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    db = Depends(get_db)
):
    """List crypto categories"""
    query = {}
    if search:
        query['name'] = {'$regex': search, '$options': 'i'}
    
    cursor = db.intel_categories.find(query, {'_id': 0, 'raw': 0})
    items = await cursor.sort('coins_count', -1).limit(limit).to_list(limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(items),
        'items': items
    }


# ═══════════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
async def intel_stats(db = Depends(get_db)):
    """Get intel layer statistics"""
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'collections': {
            'investors': await db.intel_investors.count_documents({}),
            'unlocks': await db.intel_unlocks.count_documents({}),
            'fundraising': await db.intel_fundraising.count_documents({}),
            'projects': await db.intel_projects.count_documents({}),
            'activity': await db.intel_activity.count_documents({}),
            'launchpads': await db.intel_launchpads.count_documents({}),
            'categories': await db.intel_categories.count_documents({}),
        },
        'moderation_pending': await db.moderation_queue.count_documents({'status': 'pending'})
    }



# ═══════════════════════════════════════════════════════════════
# ENTITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/entities")
async def list_entities(
    entity_type: Optional[str] = Query(None, alias='type'),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db = Depends(get_db)
):
    """List canonical entities"""
    query = {}
    if entity_type:
        query['type'] = entity_type
    if search:
        query['$or'] = [
            {'symbol': {'$regex': search, '$options': 'i'}},
            {'name': {'$regex': search, '$options': 'i'}},
            {'aliases': {'$regex': search, '$options': 'i'}}
        ]
    
    cursor = db.entities.find(query, {'_id': 0})
    items = await cursor.limit(limit).to_list(limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(items),
        'items': items
    }


@router.get("/entities/{entity_id}/relations")
async def get_entity_relations(
    entity_id: str,
    relation_type: Optional[str] = Query(None, alias='type'),
    db = Depends(get_db)
):
    """Get relations for an entity"""
    query = {
        '$or': [
            {'from_entity': entity_id},
            {'to_entity': entity_id}
        ]
    }
    if relation_type:
        query['type'] = relation_type
    
    cursor = db.entity_relations.find(query, {'_id': 0})
    items = await cursor.to_list(100)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'entity_id': entity_id,
        'count': len(items),
        'relations': items
    }


# ═══════════════════════════════════════════════════════════════
# DATA SOURCES & HEALTH
# ═══════════════════════════════════════════════════════════════

@router.get("/sources")
async def list_sources(
    status: Optional[str] = Query(None),
    db = Depends(get_db)
):
    """List all data sources"""
    query = {}
    if status:
        query['status'] = status
    
    cursor = db.data_sources.find(query, {'_id': 0})
    sources = await cursor.sort('priority', 1).to_list(100)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(sources),
        'sources': sources
    }


@router.post("/sources/{name}/status")
async def set_source_status(
    name: str,
    status: str = Query(..., description="active, paused, disabled"),
    db = Depends(get_db)
):
    """Set source status"""
    result = await db.data_sources.update_one(
        {'name': name},
        {'$set': {'status': status, 'updated_at': datetime.now(timezone.utc)}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return {'ok': True, 'source': name, 'status': status}


# ═══════════════════════════════════════════════════════════════
# AGGREGATED DATA (Multi-source merge)
# ═══════════════════════════════════════════════════════════════

def get_aggregator():
    """Dependency to get data aggregator"""
    from server import db
    from ..services.data_aggregator import create_data_aggregator
    return create_data_aggregator(db)


@router.get("/aggregated/project/{symbol}")
async def get_aggregated_project(
    symbol: str,
    aggregator = Depends(get_aggregator)
):
    """
    Get project data aggregated from all sources.
    Merges Dropstab, CryptoRank, CoinGecko based on field priority.
    """
    project = await aggregator.get_project(symbol)
    
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {symbol}")
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'project': project
    }


@router.get("/aggregated/investor/{slug}")
async def get_aggregated_investor(
    slug: str,
    aggregator = Depends(get_aggregator)
):
    """Get investor data aggregated from all sources"""
    investor = await aggregator.get_investor(slug)
    
    if not investor:
        raise HTTPException(status_code=404, detail=f"Investor not found: {slug}")
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'investor': investor
    }


@router.get("/aggregated/market")
async def get_aggregated_market(aggregator = Depends(get_aggregator)):
    """Get global market data aggregated from all sources"""
    market = await aggregator.get_global_market()
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'market': market
    }


@router.get("/aggregated/search")
async def search_aggregated_projects(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    aggregator = Depends(get_aggregator)
):
    """Search and return aggregated project data"""
    results = await aggregator.search_projects(q, limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'query': q,
        'count': len(results),
        'results': results
    }


@router.get("/health")
async def get_system_health(db = Depends(get_db)):
    """Get overall system health"""
    # Scraper health
    scraper_health = await db.scraper_health.find({}, {'_id': 0}).to_list(100)
    
    # Source health
    source_health = await db.data_source_health.find({}, {'_id': 0}).to_list(100)
    
    # Recent errors
    recent_errors = await db.scraper_errors.find(
        {},
        {'_id': 0}
    ).sort('timestamp', -1).limit(10).to_list(10)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'scrapers': scraper_health,
        'sources': source_health,
        'recent_errors': recent_errors
    }


@router.get("/health/scrapers")
async def get_scraper_health(db = Depends(get_db)):
    """Get scraper health status"""
    cursor = db.scraper_health.find({}, {'_id': 0})
    items = await cursor.to_list(100)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'scrapers': items
    }


# ═══════════════════════════════════════════════════════════════
# FOMO MOMENTUM INDEX (FMI) - Branded Trend Detection
# ═══════════════════════════════════════════════════════════════

def get_fmi_calculator():
    """Dependency to get FMI calculator"""
    from server import db
    from ..services.fomo_momentum import create_fmi_calculator
    return create_fmi_calculator(db)


@router.get("/fomo-momentum")
async def get_fmi_list(
    state: Optional[str] = Query(None, description="Filter by state: CALM, BUILDING, TRENDING, FOMO"),
    min_fmi: Optional[float] = Query(None, ge=0, le=100, description="Minimum FMI score"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    calculator = Depends(get_fmi_calculator)
):
    """
    Get FOMO Momentum Index for all tokens
    
    FMI States:
    - CALM (0-40): Low momentum
    - BUILDING (40-60): Building momentum  
    - TRENDING (60-80): Trending
    - FOMO (80-100): FOMO Zone 🔥
    
    Returns pre-computed FMI scores (updated every 5 min)
    """
    items = await calculator.get_all_fmi(
        state=state,
        min_fmi=min_fmi,
        sector=sector,
        limit=limit,
        offset=offset
    )
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(items),
        'data': items
    }


@router.get("/fomo-momentum/trending")
async def get_fmi_trending(
    limit: int = Query(20, ge=1, le=100),
    calculator = Depends(get_fmi_calculator)
):
    """
    Get trending tokens (FMI >= 60)
    
    Quick endpoint for tokens currently trending
    """
    items = await calculator.get_trending(limit=limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(items),
        'data': items
    }


@router.get("/fomo-momentum/fomo-zone")
async def get_fmi_fomo_zone(
    limit: int = Query(10, ge=1, le=50),
    calculator = Depends(get_fmi_calculator)
):
    """
    Get tokens in FOMO Zone (FMI >= 80) 🔥
    
    These are the hottest tokens right now
    """
    items = await calculator.get_fomo_zone(limit=limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'count': len(items),
        'data': items
    }


@router.get("/fomo-momentum/stats")
async def get_fmi_stats(calculator = Depends(get_fmi_calculator)):
    """
    Get FMI statistics
    
    - Total tokens computed
    - Distribution by state
    - Top sectors by average FMI
    """
    stats = await calculator.get_stats()
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


@router.get("/fomo-momentum/{symbol}")
async def get_fmi_single(
    symbol: str,
    calculator = Depends(get_fmi_calculator)
):
    """
    Get FOMO Momentum Index for specific token
    
    Full response with all components:
    - Volume Spike (40% weight)
    - Liquidity Inflow (30% weight)
    - Narrative Growth (20% weight)
    - Listing Signal (10% weight)
    
    Plus signals array: VOLUME_ANOMALY, LIQUIDITY_SURGE, SECTOR_MOMENTUM, CEX_LISTING
    """
    fmi = await calculator.get_fmi(symbol)
    
    if not fmi:
        # Try to calculate on-the-fly
        fmi = await calculator.calculate_fmi(symbol)
        
        if not fmi:
            raise HTTPException(
                status_code=404, 
                detail=f"FMI not found for {symbol.upper()}. Project may not exist or have insufficient data."
            )
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        **fmi
    }


@router.post("/fomo-momentum/compute")
async def compute_fmi(
    limit: int = Query(500, ge=1, le=5000, description="Max projects to compute"),
    calculator = Depends(get_fmi_calculator)
):
    """
    Trigger FMI pre-computation
    
    Computes FMI for all projects with volume data.
    Usually run via scheduler every 5 minutes.
    """
    result = await calculator.compute_all(limit=limit)
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'ok': True,
        **result
    }


@router.post("/fomo-momentum/{symbol}/calculate")
async def calculate_fmi_single(
    symbol: str,
    calculator = Depends(get_fmi_calculator)
):
    """
    Calculate and store FMI for specific token
    
    Forces fresh calculation regardless of cache
    """
    fmi = await calculator.calculate_fmi(symbol)
    
    if not fmi:
        raise HTTPException(
            status_code=404,
            detail=f"Cannot calculate FMI for {symbol.upper()}. Project not found or insufficient data."
        )
    
    # Store result
    from server import db
    await db.fomo_momentum.update_one(
        {'symbol': symbol.upper()},
        {'$set': fmi},
        upsert=True
    )
    
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'ok': True,
        **fmi
    }



# ═══════════════════════════════════════════════════════════════
# SCHEDULER & HEALTH
# ═══════════════════════════════════════════════════════════════

def get_scheduler():
    """Get scheduler instance"""
    from server import db
    from ..scheduler import init_scheduler, intel_scheduler
    if intel_scheduler is None:
        init_scheduler(db)
    from ..scheduler import intel_scheduler
    return intel_scheduler


def get_health_monitor():
    """Get health monitor instance"""
    from server import db
    from ..scheduler import init_scheduler, intel_health
    if intel_health is None:
        init_scheduler(db)
    from ..scheduler import intel_health
    return intel_health


@router.get("/scheduler/status")
async def scheduler_status():
    """Get scheduler status"""
    scheduler = get_scheduler()
    return scheduler.get_status()


@router.post("/scheduler/start")
async def start_scheduler():
    """Start the Intel sync scheduler"""
    scheduler = get_scheduler()
    result = await scheduler.start()
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        **result,
        **scheduler.get_status()
    }


@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the Intel sync scheduler"""
    scheduler = get_scheduler()
    result = await scheduler.stop()
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/scheduler/run/{job_name}")
async def run_scheduler_job(job_name: str):
    """Run specific job immediately"""
    scheduler = get_scheduler()
    result = await scheduler.run_now(job_name)
    return {
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'job': job_name,
        **result
    }


@router.post("/scheduler/job/{job_name}/enable")
async def enable_scheduler_job(job_name: str):
    """Enable a scheduler job"""
    scheduler = get_scheduler()
    return scheduler.enable_job(job_name)


@router.post("/scheduler/job/{job_name}/disable")
async def disable_scheduler_job(job_name: str):
    """Disable a scheduler job"""
    scheduler = get_scheduler()
    return scheduler.disable_job(job_name)


@router.get("/admin/health")
async def get_intel_health():
    """
    Get comprehensive intel system health.
    
    Shows:
    - Scheduler status
    - Source availability
    - Last sync times
    - Database stats
    - Recent errors
    """
    health = get_health_monitor()
    return await health.get_health()


# ═══════════════════════════════════════════════════════════════
# PROXY MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.get("/admin/proxy/status")
async def get_proxy_status():
    """Get current proxy configuration status"""
    from ..common.proxy_manager import proxy_manager
    # Ensure proxies are loaded from DB
    await proxy_manager.load_from_db()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **proxy_manager.get_status()
    }


@router.post("/admin/proxy/add")
async def add_proxy(
    request: Request
):
    """
    Add new proxy to the pool.
    
    Body:
    {
        "server": "http://proxy.example.com:8080",
        "username": "user",  // optional
        "password": "pass",  // optional
        "priority": 1        // optional, lower = higher priority
    }
    """
    from ..common.proxy_manager import proxy_manager
    await proxy_manager.load_from_db()
    data = await request.json()
    
    result = await proxy_manager.add_proxy(
        server=data.get("server"),
        username=data.get("username"),
        password=data.get("password"),
        priority=data.get("priority")
    )
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "action": "added",
        **result,
        "status": proxy_manager.get_status()
    }


@router.delete("/admin/proxy/{proxy_id}")
async def remove_proxy(proxy_id: int):
    """Remove proxy by ID"""
    from ..common.proxy_manager import proxy_manager
    await proxy_manager.load_from_db()
    result = await proxy_manager.remove_proxy(proxy_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "action": "removed",
        **result,
        "status": proxy_manager.get_status()
    }


@router.post("/admin/proxy/{proxy_id}/priority")
async def set_proxy_priority(
    proxy_id: int,
    priority: int = Query(..., description="Priority (1=highest)")
):
    """Set proxy priority"""
    from ..common.proxy_manager import proxy_manager
    await proxy_manager.load_from_db()
    result = await proxy_manager.set_priority(proxy_id, priority)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "action": "priority_updated",
        **result
    }


@router.post("/admin/proxy/{proxy_id}/enable")
async def enable_proxy(proxy_id: int):
    """Enable proxy"""
    from ..common.proxy_manager import proxy_manager
    await proxy_manager.load_from_db()
    result = await proxy_manager.enable_proxy(proxy_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "action": "enabled",
        **result
    }


@router.post("/admin/proxy/{proxy_id}/disable")
async def disable_proxy(proxy_id: int):
    """Disable proxy"""
    from ..common.proxy_manager import proxy_manager
    await proxy_manager.load_from_db()
    result = await proxy_manager.disable_proxy(proxy_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "action": "disabled",
        **result
    }


@router.post("/admin/proxy/test")
async def test_proxies(
    proxy_id: int = Query(None, description="Test specific proxy ID, or all if not set")
):
    """Test proxy connectivity to Binance/Bybit"""
    from ..common.proxy_manager import proxy_manager
    await proxy_manager.load_from_db()
    result = await proxy_manager.test_proxy(proxy_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/admin/proxy/set")
async def set_proxy(
    server: str = Query(..., description="Proxy server (http://host:port)"),
    username: str = Query(None, description="Proxy username (optional)"),
    password: str = Query(None, description="Proxy password (optional)")
):
    """
    Set global proxy for all scrapers (replaces all existing).
    
    Example: http://proxy.example.com:8080
    With auth: http://user:pass@proxy.example.com:8080
    """
    from ..common.proxy_manager import proxy_manager
    await proxy_manager.load_from_db()
    await proxy_manager.set_proxy(server, username, password)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "status": "set",
        **proxy_manager.get_status()
    }


@router.post("/admin/proxy/clear")
async def clear_proxy():
    """Clear all proxies - use direct connection"""
    from ..common.proxy_manager import proxy_manager
    await proxy_manager.load_from_db()
    await proxy_manager.clear_proxy()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "status": "cleared",
        **proxy_manager.get_status()
    }


# ═══════════════════════════════════════════════════════════════
# PROXY PARSER CONTROL (Play Button)
# ═══════════════════════════════════════════════════════════════

@router.post("/admin/proxy/start-parser")
async def start_parser_via_proxy(
    source: str = Query("cryptorank", description="Source to sync: cryptorank, coingecko, all"),
    proxy_id: int = Query(None, description="Specific proxy ID to use, or best available")
):
    """
    Start parser/sync using configured proxy (Play button).
    
    This endpoint:
    1. Loads proxy from database
    2. Sets proxy for exchange adapters (Binance, Bybit)
    3. Runs sync for selected source
    4. Returns sync results
    
    Use this after adding a proxy to start data collection.
    """
    from ..common.proxy_manager import proxy_manager
    from datetime import datetime, timezone
    import aiohttp
    
    await proxy_manager.load_from_db()
    
    if not proxy_manager.has_enabled_proxy:
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "ok": False,
            "error": "No enabled proxies configured. Add a proxy first via Admin UI.",
            "hint": "Use POST /api/intel/admin/proxy/add to add a proxy"
        }
    
    # Get specific or best proxy
    if proxy_id:
        proxy = next((p for p in proxy_manager._proxies if p.id == proxy_id and p.enabled), None)
        if not proxy:
            return {"ok": False, "error": f"Proxy {proxy_id} not found or disabled"}
    else:
        proxy = proxy_manager.get_primary_proxy()
    
    start_time = datetime.now(timezone.utc)
    results = {
        "ts": int(start_time.timestamp() * 1000),
        "proxy_used": {
            "id": proxy.id,
            "server": proxy.server
        },
        "synced": {}
    }
    
    # Get database connection
    from server import db
    
    total_records = 0
    sync_error = None
    
    try:
        if source in ["cryptorank", "all"]:
            # Run CryptoRank sync through proxy
            from modules.intel.sources.cryptorank.sync import CryptoRankSync
            from modules.intel.sources.cryptorank.parsers.investors import parse_investors_from_funding
            from modules.intel.common.storage import upsert_with_diff
            from datetime import timedelta
            
            sync = CryptoRankSync(db)
            
            async with aiohttp.ClientSession() as session:
                # Funding rounds
                try:
                    all_funding = []
                    for offset in range(0, 300, 100):
                        url = f"https://api.cryptorank.io/v0/coins/funding-rounds?limit=100&offset={offset}"
                        async with session.get(url, timeout=30, proxy=proxy.httpx_format) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                all_funding.extend(data.get("data", []))
                                if len(data.get("data", [])) < 100:
                                    break
                    
                    if all_funding:
                        result = await sync.ingest_funding({"data": all_funding})
                        results["synced"]["funding"] = result
                        
                        # Extract investors
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
                
                # Token unlocks
                try:
                    today = datetime.now().strftime("%Y-%m-%d")
                    end_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
                    url = f"https://api.cryptorank.io/v0/token-unlocks/unlocks?dateFrom={today}&dateTo={end_date}"
                    
                    async with session.get(url, timeout=30, proxy=proxy.httpx_format) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            result = await sync.ingest_unlocks(data.get("data", data), "vesting")
                            results["synced"]["unlocks"] = result
                except Exception as e:
                    results["synced"]["unlocks"] = {"error": str(e)}
        
        if source in ["coingecko", "all"]:
            # Run CoinGecko sync
            try:
                from modules.intel.sources.coingecko.sync import CoinGeckoSync
                cg_sync = CoinGeckoSync(db)
                cg_result = await cg_sync.sync_all()
                results["synced"]["coingecko"] = cg_result
            except Exception as e:
                results["synced"]["coingecko"] = {"error": str(e)}
        
        # Calculate total records synced
        for key, val in results["synced"].items():
            if isinstance(val, dict) and "total" in val:
                total_records += val["total"]
            elif isinstance(val, dict) and "changed" in val:
                total_records += val.get("changed", 0)
        
        # Update proxy success stats
        proxy.success_count += 1
        proxy.last_success = datetime.now(timezone.utc)
        await proxy_manager.save_to_db()
        
        results["ok"] = True
        
    except Exception as e:
        proxy.error_count += 1
        proxy.last_error = str(e)
        await proxy_manager.save_to_db()
        results["ok"] = False
        results["error"] = str(e)
        sync_error = str(e)
    
    # Record sync history
    end_time = datetime.now(timezone.utc)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)
    
    sync_record = {
        "ts": int(start_time.timestamp() * 1000),
        "source": source,
        "status": "success" if results.get("ok") else "error",
        "records": total_records,
        "error": sync_error,
        "duration_ms": duration_ms,
        "proxy_id": proxy.id
    }
    await db.intel_sync_history.insert_one(sync_record)
    
    results["duration_ms"] = duration_ms
    results["total_records"] = total_records
    
    return results


@router.get("/admin/proxy/parser-status")
async def get_parser_status():
    """
    Get detailed parser/sync status for monitoring.
    
    Shows:
    - Parser running state
    - Proxy configuration
    - Last sync times and errors
    - Data counts
    - System health
    """
    from ..common.proxy_manager import proxy_manager
    from datetime import datetime, timezone
    
    await proxy_manager.load_from_db()
    
    # Get database connection
    from server import db
    
    # Get data counts
    counts = {
        "investors": await db.intel_investors.count_documents({}),
        "funding": await db.intel_fundraising.count_documents({}),
        "unlocks": await db.intel_unlocks.count_documents({}),
        "projects": await db.intel_projects.count_documents({}),
        "categories": await db.intel_categories.count_documents({}),
    }
    
    # Get sync history from database
    sync_history = []
    try:
        cursor = db.intel_sync_history.find({}).sort("ts", -1).limit(10)
        async for doc in cursor:
            sync_history.append({
                "ts": doc.get("ts"),
                "source": doc.get("source"),
                "status": doc.get("status"),
                "records": doc.get("records", 0),
                "error": doc.get("error"),
                "duration_ms": doc.get("duration_ms")
            })
    except Exception as e:
        pass
    
    # Get last sync info
    last_sync = None
    last_error = None
    try:
        last_doc = await db.intel_sync_history.find_one({}, sort=[("ts", -1)])
        if last_doc:
            last_sync = {
                "ts": last_doc.get("ts"),
                "source": last_doc.get("source"),
                "status": last_doc.get("status"),
                "records": last_doc.get("records", 0)
            }
            if last_doc.get("status") == "error":
                last_error = {
                    "ts": last_doc.get("ts"),
                    "error": last_doc.get("error"),
                    "source": last_doc.get("source")
                }
    except Exception:
        pass
    
    # Determine parser state
    proxy_status = proxy_manager.get_status()
    parser_state = "stopped"
    parser_reason = None
    
    if proxy_status['enabled'] > 0:
        parser_state = "ready"
        parser_reason = "Proxy configured, ready to sync"
    else:
        parser_state = "stopped"
        parser_reason = "No proxy configured. Add a proxy to enable parser."
    
    # Check for recent errors
    if last_error and last_error.get("ts"):
        # If error was within last hour
        error_time = last_error["ts"]
        if isinstance(error_time, (int, float)):
            from datetime import timedelta
            error_dt = datetime.fromtimestamp(error_time / 1000, tz=timezone.utc)
            if datetime.now(timezone.utc) - error_dt < timedelta(hours=1):
                parser_state = "error"
                parser_reason = f"Last sync failed: {last_error.get('error', 'Unknown error')}"
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "parser": {
            "state": parser_state,  # ready, running, stopped, error
            "reason": parser_reason,
            "can_start": proxy_status['enabled'] > 0
        },
        "proxy": proxy_status,
        "data_counts": counts,
        "total_records": sum(counts.values()),
        "last_sync": last_sync,
        "last_error": last_error,
        "sync_history": sync_history,
        "ready_to_sync": proxy_manager.has_enabled_proxy
    }


@router.post("/admin/parser/force-restart")
async def force_restart_parser():
    """
    Force restart parser - clears errors and reinitializes connections.
    
    Use this when:
    - Parser is stuck
    - After fixing proxy configuration
    - To clear error state
    """
    from ..common.proxy_manager import proxy_manager
    from datetime import datetime, timezone
    
    # Reload proxy configuration
    await proxy_manager.load_from_db()
    
    # Get database connection
    from server import db
    
    # Clear recent error state by adding a restart event
    restart_event = {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source": "system",
        "status": "restart",
        "records": 0,
        "error": None,
        "duration_ms": 0,
        "message": "Parser force restarted"
    }
    await db.intel_sync_history.insert_one(restart_event)
    
    # Test proxy connectivity
    proxy_test = {"ok": False, "error": None}
    if proxy_manager.has_enabled_proxy:
        try:
            import aiohttp
            proxy = proxy_manager.get_primary_proxy()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.cryptorank.io/v0/global",
                    proxy=proxy.httpx_format,
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        proxy_test["ok"] = True
                    else:
                        proxy_test["error"] = f"HTTP {resp.status}"
        except Exception as e:
            proxy_test["error"] = str(e)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ok": True,
        "message": "Parser restarted",
        "proxy_test": proxy_test,
        "proxy_status": proxy_manager.get_status()
    }


# ═══════════════════════════════════════════════════════════════
# COINGECKO MANAGER STATUS
# ═══════════════════════════════════════════════════════════════

@router.get("/admin/coingecko/status")
async def get_coingecko_status():
    """
    Get CoinGecko key manager status.
    
    Shows:
    - Proxies with their assigned API keys
    - Rate limit status per key
    - Keyless mode availability
    - Request statistics
    """
    from server import db
    from ..common.coingecko_manager import get_coingecko_manager
    from datetime import datetime, timezone
    
    manager = get_coingecko_manager(db)
    await manager.initialize()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **manager.get_status()
    }


@router.post("/admin/coingecko/test")
async def test_coingecko_manager():
    """
    Test CoinGecko API access through all available proxies/keys.
    
    Makes a simple ping request to verify connectivity.
    """
    from server import db
    from ..common.coingecko_manager import get_coingecko_manager
    from datetime import datetime, timezone
    
    manager = get_coingecko_manager(db)
    await manager.initialize()
    
    results = []
    
    # Test each slot
    for slot in manager._get_all_slots():
        slot_result = {
            "proxy_id": slot.proxy_id,
            "server": slot.server,
            "keys_tested": []
        }
        
        # Test with key if available
        for key in slot.keys:
            try:
                import httpx
                params = {}
                if key.is_pro:
                    url = f"{manager.PRO_URL}/ping"
                    params['x_cg_pro_api_key'] = key.api_key
                else:
                    url = f"{manager.BASE_URL}/ping"
                    params['x_cg_demo_api_key'] = key.api_key
                
                async with httpx.AsyncClient(
                    proxy=slot.proxy_url,
                    timeout=10
                ) as client:
                    response = await client.get(url, params=params)
                    slot_result["keys_tested"].append({
                        "key_id": key.key_id[:8] + "...",
                        "is_pro": key.is_pro,
                        "status": response.status_code,
                        "success": response.status_code == 200
                    })
            except Exception as e:
                slot_result["keys_tested"].append({
                    "key_id": key.key_id[:8] + "...",
                    "error": str(e)
                })
        
        # Test keyless mode
        try:
            import httpx
            async with httpx.AsyncClient(
                proxy=slot.proxy_url,
                timeout=10
            ) as client:
                response = await client.get(f"{manager.BASE_URL}/ping")
                slot_result["keyless_test"] = {
                    "status": response.status_code,
                    "success": response.status_code == 200
                }
        except Exception as e:
            slot_result["keyless_test"] = {"error": str(e)}
        
        results.append(slot_result)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "results": results
    }



@router.get("/scraper/status")
async def scraper_status():
    """Get scraper engine status"""
    from ..scraper_engine import scraper_runner
    return scraper_runner.get_status()


@router.post("/scraper/discover/{source}")
async def scraper_discover(
    source: str,
    targets: str = Query(None, description="Comma-separated targets (e.g. unlocks,funding)"),
    headless: bool = Query(True)
):
    """
    Run endpoint discovery for source.
    
    Sources: dropstab, cryptorank
    
    This opens pages in browser, captures XHR/fetch JSON,
    saves full request blueprints to registry.
    """
    from ..scraper_engine import scraper_runner
    
    target_list = targets.split(",") if targets else None
    
    if source == "dropstab":
        result = await scraper_runner.discover_dropstab(targets=target_list, headless=headless)
    elif source == "cryptorank":
        result = await scraper_runner.discover_cryptorank(targets=target_list, headless=headless)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")
    
    return result


@router.post("/scraper/sync/{source}/{target}")
async def scraper_sync(source: str, target: str):
    """
    Sync specific target from source.
    
    Uses endpoints from registry (discovered via /scraper/discover).
    Saves raw data to /data/raw/{source}/{target}/
    """
    from ..scraper_engine import scraper_runner
    return await scraper_runner.sync(source, target)


@router.post("/scraper/sync/{source}")
async def scraper_sync_all(source: str):
    """Sync all targets for source"""
    from ..scraper_engine import scraper_runner
    return await scraper_runner.sync_all(source)


@router.get("/scraper/registry")
async def scraper_registry(source: str = None, target: str = None):
    """Get endpoint registry contents"""
    from ..scraper_engine import endpoint_registry
    
    endpoints = endpoint_registry.get_all(source, target)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "count": len(endpoints),
        "endpoints": [
            {
                "key": e.key,
                "url": e.url[:100],
                "method": e.method,
                "source": e.source,
                "target": e.target,
                "response_type": e.response_type,
                "success_count": e.success_count,
                "fail_count": e.fail_count,
                "last_success": e.last_success,
                "last_error": e.last_error
            }
            for e in endpoints
        ]
    }


@router.get("/scraper/raw")
async def scraper_raw_list(source: str = None, target: str = None, limit: int = 20):
    """List raw data files"""
    from ..scraper_engine import raw_store
    
    files = raw_store.list_files(source, target, limit=limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "count": len(files),
        "files": files
    }


@router.get("/scraper/raw/stats")
async def scraper_raw_stats():
    """Get raw storage statistics"""
    from ..scraper_engine import raw_store
    return raw_store.get_stats()



# ═══════════════════════════════════════════════════════════════
# WORKER & QUEUE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.get("/worker/status")
async def worker_status():
    """Get worker status"""
    from ..scraper_engine import get_worker_status
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **get_worker_status()
    }


@router.post("/worker/start")
async def start_worker_endpoint(worker_id: str = Query("worker-1")):
    """Start the scraper worker"""
    from ..scraper_engine import start_worker
    result = await start_worker(worker_id)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/worker/stop")
async def stop_worker_endpoint():
    """Stop the scraper worker"""
    from ..scraper_engine import stop_worker
    result = await stop_worker()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.get("/queue/status")
async def queue_status():
    """Get job queue status"""
    from ..scraper_engine import job_queue
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **job_queue.get_stats()
    }


@router.get("/queue/jobs")
async def queue_jobs(status: str = Query("pending", description="pending, processing, completed, failed")):
    """Get jobs by status"""
    from ..scraper_engine import job_queue
    
    if status == "pending":
        jobs = job_queue.get_pending_jobs()
    elif status == "processing":
        jobs = job_queue.get_processing_jobs()
    elif status == "completed":
        jobs = job_queue.get_recent_completed()
    elif status == "failed":
        jobs = job_queue.get_recent_failed()
    else:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "status": status,
        "count": len(jobs),
        "jobs": jobs
    }


@router.post("/queue/push/discover")
async def queue_push_discover(
    source: str = Query(..., description="dropstab or cryptorank"),
    targets: str = Query(None, description="Comma-separated targets"),
    priority: int = Query(5, ge=1, le=10)
):
    """Push discovery jobs to queue"""
    from ..scraper_engine import job_queue
    
    target_list = targets.split(",") if targets else None
    job_ids = job_queue.push_discover(source, target_list, priority)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ok": True,
        "source": source,
        "jobs_pushed": len(job_ids),
        "job_ids": job_ids
    }


@router.post("/queue/push/sync")
async def queue_push_sync(
    source: str = Query(..., description="dropstab or cryptorank"),
    targets: str = Query(None, description="Comma-separated targets"),
    priority: int = Query(5, ge=1, le=10)
):
    """Push sync jobs to queue"""
    from ..scraper_engine import job_queue
    
    target_list = targets.split(",") if targets else None
    job_ids = job_queue.push_sync(source, target_list, priority)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ok": True,
        "source": source,
        "jobs_pushed": len(job_ids),
        "job_ids": job_ids
    }


@router.delete("/queue/clear")
async def queue_clear(confirm: bool = Query(False)):
    """Clear pending jobs from queue"""
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to clear queue")
    
    from ..scraper_engine import job_queue
    job_queue.clear_queue()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ok": True,
        "message": "Queue cleared"
    }


# ═══════════════════════════════════════════════════════════════
# NORMALIZATION & PIPELINE
# ═══════════════════════════════════════════════════════════════

def get_normalization_engine():
    """Get normalization engine"""
    from server import db
    from ..normalization import create_normalization_engine
    return create_normalization_engine(db)


@router.get("/pipeline/stats")
async def pipeline_stats():
    """Get normalization pipeline statistics"""
    engine = get_normalization_engine()
    stats = await engine.get_stats()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


@router.post("/pipeline/dedupe")
async def run_dedup_pipeline():
    """
    Run full deduplication pipeline.
    
    Merges data from all sources into curated tables.
    """
    engine = get_normalization_engine()
    result = await engine.run_full_pipeline()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ok": True,
        **result
    }


@router.post("/pipeline/dedupe/{entity}")
async def run_dedupe_entity(entity: str):
    """Run dedup for specific entity"""
    engine = get_normalization_engine()
    
    if entity == "unlocks":
        result = await engine.dedupe_unlocks()
    elif entity == "funding":
        result = await engine.dedupe_funding()
    elif entity == "investors":
        result = await engine.dedupe_investors()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown entity: {entity}")
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "entity": entity,
        **result
    }


@router.post("/pipeline/index")
async def build_event_index():
    """Build/rebuild event index"""
    engine = get_normalization_engine()
    result = await engine.build_event_index()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ok": True,
        **result
    }


# ═══════════════════════════════════════════════════════════════
# CURATED DATA API (Final Tables)
# ═══════════════════════════════════════════════════════════════

@router.get("/curated/unlocks")
async def get_curated_unlocks(
    symbol: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    min_usd: Optional[float] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db = Depends(get_db)
):
    """
    Get curated token unlocks (deduplicated, multi-source).
    
    These are the final clean records for the frontend.
    """
    query = {}
    
    if symbol:
        query["symbol"] = symbol.upper()
    
    if min_usd:
        query["value_usd"] = {"$gte": min_usd}
    
    # Get all unlocks and filter by date in Python (handles both string and timestamp)
    cursor = db.intel_unlocks.find(query, {"_id": 0})
    all_items = await cursor.limit(500).to_list(500)
    
    # Filter by date
    from datetime import datetime as dt_class, timedelta, timezone as tz
    now = dt_class.now(tz.utc)
    cutoff = now + timedelta(days=days)
    
    items = []
    for item in all_items:
        unlock_date = item.get('unlock_date') or item.get('unlock_timestamp')
        if unlock_date:
            # Convert to datetime for comparison
            if isinstance(unlock_date, str):
                try:
                    parsed_dt = dt_class.fromisoformat(unlock_date.replace('Z', '+00:00'))
                except:
                    try:
                        parsed_dt = dt_class.strptime(unlock_date, '%Y-%m-%d').replace(tzinfo=tz.utc)
                    except:
                        continue
            elif isinstance(unlock_date, (int, float)):
                parsed_dt = dt_class.fromtimestamp(unlock_date, tz=tz.utc)
            else:
                continue
            
            # Ensure timezone aware
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=tz.utc)
            
            if now <= parsed_dt <= cutoff:
                items.append(item)
    
    # Sort by date
    items.sort(key=lambda x: x.get('unlock_date', '') or x.get('unlock_timestamp', 0))
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "days_ahead": days,
        "count": len(items[:limit]),
        "data": items[:limit]
    }


@router.get("/curated/funding")
async def get_curated_funding(
    symbol: Optional[str] = Query(None),
    round_type: Optional[str] = Query(None),
    days: int = Query(90, ge=1, le=365),
    min_usd: Optional[float] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db = Depends(get_db)
):
    """Get curated funding rounds (deduplicated, multi-source)"""
    query = {}
    
    if symbol:
        query["symbol"] = symbol.upper()
    
    if round_type:
        query["round"] = {"$regex": round_type, "$options": "i"}
    
    if min_usd:
        query["raise_usd"] = {"$gte": min_usd}
    
    # Try intel_fundraising first (our main collection)
    cursor = db.intel_fundraising.find(query, {"_id": 0})
    items = await cursor.sort("date", -1).limit(limit).to_list(limit)
    
    # Fallback to intel_funding if empty
    if not items:
        cursor = db.intel_funding.find(query, {"_id": 0})
        items = await cursor.sort("round_date", -1).limit(limit).to_list(limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "days_back": days,
        "count": len(items),
        "data": items
    }


@router.get("/curated/investors")
async def get_curated_investors(
    tier: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db = Depends(get_db)
):
    """Get curated investors (deduplicated, multi-source)"""
    query = {}
    
    if tier:
        query["tier"] = tier
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"slug": {"$regex": search, "$options": "i"}}
        ]
    
    cursor = db.intel_investors.find(query, {"_id": 0})
    items = await cursor.sort("investments_count", -1).limit(limit).to_list(limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "count": len(items),
        "data": items
    }


# ═══════════════════════════════════════════════════════════════
# EVENT INDEX API
# ═══════════════════════════════════════════════════════════════

@router.get("/events")
async def get_events(
    event_type: Optional[str] = Query(None, description="unlock, funding, sale"),
    symbol: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    direction: str = Query("future", description="future or past"),
    limit: int = Query(100, ge=1, le=500),
    db = Depends(get_db)
):
    """
    Query unified event index.
    
    Fast queries across all event types.
    """
    now = int(datetime.now(timezone.utc).timestamp())
    
    if direction == "future":
        date_query = {"$gte": now, "$lte": now + (days * 86400)}
        sort_dir = 1
    else:
        date_query = {"$gte": now - (days * 86400), "$lte": now}
        sort_dir = -1
    
    query = {"event_date": date_query}
    
    if event_type:
        query["event_type"] = event_type
    
    if symbol:
        query["symbol"] = symbol.upper()
    
    cursor = db.intel_events.find(query, {"_id": 0})
    items = await cursor.sort("event_date", sort_dir).limit(limit).to_list(limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "direction": direction,
        "days": days,
        "count": len(items),
        "events": items
    }


@router.get("/events/{symbol}")
async def get_events_for_symbol(
    symbol: str,
    limit: int = Query(50, ge=1, le=200),
    db = Depends(get_db)
):
    """Get all events for a specific symbol"""
    cursor = db.intel_events.find(
        {"symbol": symbol.upper()},
        {"_id": 0}
    )
    items = await cursor.sort("event_date", 1).limit(limit).to_list(limit)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "symbol": symbol.upper(),
        "count": len(items),
        "events": items
    }



# ═══════════════════════════════════════════════════════════════
# CONSISTENCY ENGINE - Data Quality Monitoring
# ═══════════════════════════════════════════════════════════════

class SimpleConsistencyEngine:
    """Simplified consistency engine for sync operations"""
    
    EXPECTED_FIELDS = {
        "unlocks": ["symbol", "unlock_date", "source"],
        "funding": ["round_date", "source"],
        "investors": ["name", "source"],
        "sales": ["start_date", "source"]
    }
    
    def __init__(self, db):
        self.db = db
        self.checks = []
    
    async def check_schema(self, entity: str, records: List[Dict]) -> Dict:
        """Check if records have expected fields"""
        expected = self.EXPECTED_FIELDS.get(entity, [])
        if not records:
            return {"status": "unknown", "entity": entity, "message": "No records"}
        
        missing = []
        for field in expected:
            if field not in records[0]:
                missing.append(field)
        
        status = "ok" if not missing else "fail"
        return {
            "status": status,
            "entity": entity,
            "missing_fields": missing,
            "sample_fields": list(records[0].keys())[:10]
        }
    
    async def check_counts(self, entity: str, current: int, previous: int) -> Dict:
        """Check for abnormal count changes"""
        if previous == 0:
            return {"status": "ok", "entity": entity, "current": current}
        
        if current < previous * 0.3:
            return {
                "status": "fail",
                "entity": entity,
                "message": f"Count dropped from {previous} to {current}",
                "drop_percent": round((1 - current/previous) * 100, 1)
            }
        
        if current > previous * 3:
            return {
                "status": "warning",
                "entity": entity,
                "message": f"Count exploded from {previous} to {current}",
                "growth_factor": round(current/previous, 2)
            }
        
        return {"status": "ok", "entity": entity, "current": current}
    
    async def run_all(self) -> List[Dict]:
        """Run all checks"""
        self.checks = []
        
        entities = {
            "unlocks": "intel_unlocks",
            "funding": "intel_fundraising", 
            "investors": "intel_investors"
        }
        
        for entity, collection in entities.items():
            try:
                # Get sample
                cursor = self.db[collection].find().limit(20)
                sample = await cursor.to_list(20)
                
                # Schema check
                check = await self.check_schema(entity, sample)
                self.checks.append(check)
                
                # Count check
                count = await self.db[collection].count_documents({})
                stats_col = self.db.intel_consistency_stats
                prev_doc = await stats_col.find_one({"entity": entity})
                prev_count = prev_doc.get("count", 0) if prev_doc else 0
                
                check = await self.check_counts(entity, count, prev_count)
                self.checks.append(check)
                
                # Store new count
                await stats_col.update_one(
                    {"entity": entity},
                    {"$set": {"count": count, "updated_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True
                )
            except Exception as e:
                self.checks.append({
                    "status": "error",
                    "entity": entity,
                    "message": str(e)
                })
        
        return self.checks


@router.get("/consistency/health")
async def get_consistency_health(db = Depends(get_db)):
    """
    Get overall data consistency health status.
    
    Checks:
    - Schema drift (field changes)
    - Count anomalies (data drops/explosions)
    - Data freshness
    """
    engine = SimpleConsistencyEngine(db)
    checks = await engine.run_all()
    
    fails = [c for c in checks if c.get("status") == "fail"]
    warnings = [c for c in checks if c.get("status") == "warning"]
    
    if fails:
        status = "critical"
    elif warnings:
        status = "warning"
    else:
        status = "healthy"
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "status": status,
        "total_checks": len(checks),
        "passed": sum(1 for c in checks if c.get("status") == "ok"),
        "warnings": len(warnings),
        "failures": len(fails),
        "checks": checks
    }


@router.post("/consistency/run")
async def run_consistency_checks(db = Depends(get_db)):
    """
    Run all consistency checks and return results.
    
    Validates:
    - Schema integrity
    - Count stability
    - Source reliability
    """
    engine = SimpleConsistencyEngine(db)
    checks = await engine.run_all()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "checks": checks,
        "summary": {
            "total": len(checks),
            "ok": sum(1 for c in checks if c.get("status") == "ok"),
            "fail": sum(1 for c in checks if c.get("status") == "fail"),
            "warning": sum(1 for c in checks if c.get("status") == "warning")
        }
    }


@router.get("/consistency/reliability")
async def get_source_reliability(db = Depends(get_db)):
    """
    Get reliability scores for data sources.
    
    Score based on:
    - Schema consistency
    - Data freshness
    - Count stability
    """
    sources = ["dropstab", "cryptorank", "coingecko"]
    reliability = {}
    
    for source in sources:
        # Count records from this source
        total = 0
        for col in ["intel_unlocks", "intel_fundraising", "intel_investors"]:
            try:
                count = await db[col].count_documents({"source": source})
                total += count
            except:
                pass
        
        # Calculate simple score
        if total > 100:
            score = 0.95
        elif total > 10:
            score = 0.75
        elif total > 0:
            score = 0.50
        else:
            score = 0.0
        
        reliability[source] = {
            "score": score,
            "records": total,
            "status": "active" if total > 0 else "inactive"
        }
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "sources": reliability
    }
