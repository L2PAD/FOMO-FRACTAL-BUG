"""
Network Discovery Routes
========================
Unified search across local database and external sources.
Implements cascading search: local → external sources

Flow:
1. Search local database first
2. If not found or insufficient results, query external sources
3. Cache results for future searches
4. Track which sources provided data
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
import asyncio
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/discovery", tags=["Network Discovery"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ═══════════════════════════════════════════════════════════════
# SEARCH ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/search")
async def unified_search(
    q: str = Query(..., min_length=2, description="Search query"),
    type: Optional[str] = Query(None, description="Filter by type: project, investor, person, funding"),
    sources: Optional[str] = Query(None, description="Comma-separated source IDs to search"),
    include_external: bool = Query(True, description="Include external sources if local not found"),
    limit: int = Query(20, le=100)
):
    """
    Unified search across all data sources.
    
    Priority:
    1. Local database (instant)
    2. External APIs if local results < threshold
    
    Returns sources used for tracking.
    """
    from server import db
    
    results = {
        "ts": ts_now(),
        "query": q,
        "type_filter": type,
        "items": [],
        "sources_used": [],
        "local_count": 0,
        "external_count": 0
    }
    
    # ───────────────────────────────────────────────────────────
    # STEP 1: Search local database
    # ───────────────────────────────────────────────────────────
    local_results = await _search_local(db, q, type, limit)
    results["items"].extend(local_results)
    results["local_count"] = len(local_results)
    results["sources_used"].append({"id": "local", "name": "Local Database", "count": len(local_results)})
    
    # ───────────────────────────────────────────────────────────
    # STEP 2: If insufficient, search external sources
    # ───────────────────────────────────────────────────────────
    if include_external and len(local_results) < 5:
        external_results = await _search_external(db, q, type, limit - len(local_results))
        results["items"].extend(external_results["items"])
        results["external_count"] = len(external_results["items"])
        results["sources_used"].extend(external_results["sources"])
    
    # Deduplicate and rank
    results["items"] = _deduplicate_results(results["items"])[:limit]
    results["total"] = len(results["items"])
    
    return results


@router.get("/project/{query}")
async def search_project(
    query: str,
    include_external: bool = Query(True)
):
    """Search for a specific project by name, symbol, or slug"""
    from server import db
    
    # Search local first
    local = await _search_local_project(db, query)
    
    if local:
        return {
            "ts": ts_now(),
            "found": True,
            "source": "local",
            "project": local
        }
    
    # Try external if not found locally
    if include_external:
        external = await _search_external_project(query)
        if external:
            # Cache the result
            await _cache_project(db, external)
            return {
                "ts": ts_now(),
                "found": True,
                "source": external.get("source", "external"),
                "project": external
            }
    
    return {
        "ts": ts_now(),
        "found": False,
        "query": query,
        "suggestions": await _get_similar_projects(db, query)
    }


@router.get("/investor/{query}")
async def search_investor(
    query: str,
    include_external: bool = Query(True)
):
    """Search for investor/fund by name or slug"""
    from server import db
    
    # Search local first
    local = await _search_local_investor(db, query)
    
    if local:
        return {
            "ts": ts_now(),
            "found": True,
            "source": "local",
            "investor": local
        }
    
    # External search
    if include_external:
        external = await _search_external_investor(query)
        if external:
            await _cache_investor(db, external)
            return {
                "ts": ts_now(),
                "found": True,
                "source": external.get("source", "external"),
                "investor": external
            }
    
    return {
        "ts": ts_now(),
        "found": False,
        "query": query
    }


@router.get("/funding")
async def search_funding(
    project: Optional[str] = Query(None, description="Project name/symbol"),
    investor: Optional[str] = Query(None, description="Investor name"),
    round_type: Optional[str] = Query(None, description="Round type: seed, series_a, etc."),
    min_amount: Optional[int] = Query(None, description="Minimum USD amount"),
    limit: int = Query(20, le=100)
):
    """Search funding rounds with filters"""
    from server import db
    
    query = {}
    if project:
        query["$or"] = [
            {"project": {"$regex": project, "$options": "i"}},
            {"symbol": {"$regex": project, "$options": "i"}}
        ]
    if investor:
        query["investors"] = {"$regex": investor, "$options": "i"}
    if round_type:
        query["round_type"] = round_type
    if min_amount:
        query["raised_usd"] = {"$gte": min_amount}
    
    rounds = await db.intel_funding.find(query, {"_id": 0}).sort("round_date", -1).to_list(limit)
    
    return {
        "ts": ts_now(),
        "total": len(rounds),
        "rounds": rounds,
        "filters": {"project": project, "investor": investor, "round_type": round_type}
    }


@router.get("/unlock")
async def search_unlocks(
    project: Optional[str] = Query(None),
    days_ahead: int = Query(90, description="Days to look ahead"),
    min_percent: float = Query(0, description="Minimum % of supply"),
    limit: int = Query(20, le=100)
):
    """Search upcoming token unlocks"""
    from server import db
    from datetime import timedelta
    
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=days_ahead)
    
    query = {
        "date": {"$gte": now.isoformat(), "$lte": future.isoformat()}
    }
    if project:
        query["$or"] = [
            {"project_name": {"$regex": project, "$options": "i"}},
            {"symbol": {"$regex": project, "$options": "i"}}
        ]
    if min_percent > 0:
        query["percent_supply"] = {"$gte": min_percent}
    
    unlocks = await db.token_unlocks.find(query, {"_id": 0}).sort("date", 1).to_list(limit)
    
    return {
        "ts": ts_now(),
        "total": len(unlocks),
        "unlocks": unlocks,
        "days_ahead": days_ahead
    }


# ═══════════════════════════════════════════════════════════════
# DATA SOURCES MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.get("/sources")
async def get_data_sources(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    filter: Optional[str] = Query(None, description="Filter: all, new, active, planned")
):
    """Get all configured data sources with their status"""
    from server import db
    from modules.intel.data_sources_registry import DataSourcesRegistry
    
    registry = DataSourcesRegistry(db)
    sources = await registry.get_all_sources(category=category, status=status)
    
    # Enrich with sync stats and is_new flag
    for source in sources:
        if source.get("status") == "active":
            source["synced"] = True
            source["last_sync_ago"] = _format_time_ago(source.get("last_sync"))
        else:
            source["synced"] = False
        
        # Ensure is_new field exists
        if "is_new" not in source:
            source["is_new"] = False
    
    # Apply filter
    if filter == "new":
        sources = [s for s in sources if s.get("is_new")]
    elif filter == "active":
        sources = [s for s in sources if s.get("status") == "active"]
    elif filter == "planned":
        sources = [s for s in sources if s.get("status") == "planned"]
    
    return {
        "ts": ts_now(),
        "total": len(sources),
        "sources": sources
    }


@router.post("/sources/seed")
async def seed_data_sources():
    """Seed all predefined data sources to database"""
    from server import db
    from modules.intel.data_sources_registry import DataSourcesRegistry
    
    registry = DataSourcesRegistry(db)
    result = await registry.seed_sources()
    
    return {
        "ts": ts_now(),
        "ok": True,
        **result
    }


@router.get("/sources/summary")
async def get_sources_summary():
    """Get summary of data sources status"""
    from server import db
    from modules.intel.data_sources_registry import DataSourcesRegistry
    
    registry = DataSourcesRegistry(db)
    summary = await registry.get_sync_summary()
    
    return {
        "ts": ts_now(),
        **summary
    }


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

async def _search_local(db, query: str, type_filter: Optional[str], limit: int) -> List[Dict]:
    """Search local database across all collections"""
    results = []
    regex = {"$regex": query, "$options": "i"}
    
    # Search projects
    if not type_filter or type_filter == "project":
        projects = await db.intel_projects.find(
            {"$or": [{"name": regex}, {"symbol": regex}, {"slug": regex}]},
            {"_id": 0}
        ).limit(limit // 2).to_list(limit // 2)
        for p in projects:
            p["_type"] = "project"
            p["_source"] = "local"
        results.extend(projects)
    
    # Search investors
    if not type_filter or type_filter == "investor":
        investors = await db.intel_investors.find(
            {"$or": [{"name": regex}, {"slug": regex}]},
            {"_id": 0}
        ).limit(limit // 4).to_list(limit // 4)
        for i in investors:
            i["_type"] = "investor"
            i["_source"] = "local"
        results.extend(investors)
    
    # Search persons
    if not type_filter or type_filter == "person":
        persons = await db.intel_persons.find(
            {"$or": [{"name": regex}, {"slug": regex}]},
            {"_id": 0}
        ).limit(limit // 4).to_list(limit // 4)
        for p in persons:
            p["_type"] = "person"
            p["_source"] = "local"
        results.extend(persons)
    
    # Search funding
    if not type_filter or type_filter == "funding":
        funding = await db.intel_funding.find(
            {"$or": [{"project": regex}, {"symbol": regex}]},
            {"_id": 0}
        ).sort("round_date", -1).limit(limit // 4).to_list(limit // 4)
        for f in funding:
            f["_type"] = "funding"
            f["_source"] = "local"
        results.extend(funding)
    
    return results


async def _search_external(db, query: str, type_filter: Optional[str], limit: int) -> Dict:
    """Search external sources (CoinGecko, CryptoRank, etc.)"""
    results = {"items": [], "sources": []}
    
    # CoinGecko search
    try:
        coingecko_results = await _search_coingecko(query, limit)
        if coingecko_results:
            results["items"].extend(coingecko_results)
            results["sources"].append({
                "id": "coingecko",
                "name": "CoinGecko",
                "count": len(coingecko_results)
            })
            # Update source sync status
            await _update_source_sync(db, "coingecko", True, len(coingecko_results))
    except Exception as e:
        logger.warning(f"CoinGecko search failed: {e}")
        await _update_source_sync(db, "coingecko", False, 0, str(e))
    
    return results


async def _search_coingecko(query: str, limit: int) -> List[Dict]:
    """Search CoinGecko for coins"""
    results = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Use search endpoint
            resp = await client.get(
                f"https://api.coingecko.com/api/v3/search",
                params={"query": query}
            )
            if resp.status_code == 200:
                data = resp.json()
                coins = data.get("coins", [])[:limit]
                for coin in coins:
                    results.append({
                        "id": coin.get("id"),
                        "name": coin.get("name"),
                        "symbol": coin.get("symbol"),
                        "market_cap_rank": coin.get("market_cap_rank"),
                        "thumb": coin.get("thumb"),
                        "_type": "project",
                        "_source": "coingecko"
                    })
    except Exception as e:
        logger.error(f"CoinGecko search error: {e}")
    
    return results


async def _search_local_project(db, query: str) -> Optional[Dict]:
    """Search for specific project in local db"""
    regex = {"$regex": f"^{query}$", "$options": "i"}
    
    project = await db.intel_projects.find_one(
        {"$or": [{"name": regex}, {"symbol": regex}, {"slug": regex}]},
        {"_id": 0}
    )
    
    if project:
        # Enrich with additional data
        profile = await db.project_profiles.find_one(
            {"project_id": project.get("key")},
            {"_id": 0}
        )
        links = await db.project_links.find_one(
            {"project_id": project.get("key")},
            {"_id": 0}
        )
        market = await db.market_data.find_one(
            {"$or": [
                {"symbol": {"$regex": f"^{project.get('symbol', '')}$", "$options": "i"}},
                {"name": {"$regex": f"^{project.get('name', '')}$", "$options": "i"}}
            ]},
            {"_id": 0}
        )
        
        if profile:
            project["profile"] = profile
        if links:
            project["links"] = links
        if market:
            project["market_data"] = market
    
    return project


async def _search_external_project(query: str) -> Optional[Dict]:
    """Search external sources for project"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Try CoinGecko first
            resp = await client.get(
                f"https://api.coingecko.com/api/v3/coins/{query.lower()}"
            )
            if resp.status_code == 200:
                coin = resp.json()
                return {
                    "id": coin.get("id"),
                    "name": coin.get("name"),
                    "symbol": coin.get("symbol", "").upper(),
                    "description": coin.get("description", {}).get("en", ""),
                    "image": coin.get("image", {}).get("large"),
                    "market_cap_rank": coin.get("market_cap_rank"),
                    "market_data": {
                        "current_price": coin.get("market_data", {}).get("current_price", {}).get("usd"),
                        "market_cap": coin.get("market_data", {}).get("market_cap", {}).get("usd"),
                        "total_volume": coin.get("market_data", {}).get("total_volume", {}).get("usd"),
                        "price_change_24h": coin.get("market_data", {}).get("price_change_percentage_24h")
                    },
                    "links": {
                        "website": coin.get("links", {}).get("homepage", [None])[0],
                        "twitter": f"https://twitter.com/{coin.get('links', {}).get('twitter_screen_name', '')}" if coin.get('links', {}).get('twitter_screen_name') else None,
                        "telegram": coin.get("links", {}).get("telegram_channel_identifier"),
                        "github": coin.get("links", {}).get("repos_url", {}).get("github", [None])[0]
                    },
                    "source": "coingecko"
                }
    except Exception as e:
        logger.error(f"External project search error: {e}")
    
    return None


async def _search_local_investor(db, query: str) -> Optional[Dict]:
    """Search for investor in local db"""
    regex = {"$regex": f"^{query}$", "$options": "i"}
    
    investor = await db.intel_investors.find_one(
        {"$or": [{"name": regex}, {"slug": regex}, {"id": regex}]},
        {"_id": 0}
    )
    
    return investor


async def _search_external_investor(query: str) -> Optional[Dict]:
    """Search external sources for investor (placeholder)"""
    # TODO: Implement RootData/Crunchbase search
    return None


async def _cache_project(db, project: Dict):
    """Cache external project data to local db"""
    if not project or not project.get("id"):
        return
    
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "key": f"external:{project['id']}",
        "source": project.get("source", "external"),
        "name": project.get("name"),
        "symbol": project.get("symbol"),
        "slug": project.get("id"),
        "category": "External",
        "created_at": now,
        "updated_at": now
    }
    
    await db.intel_projects.update_one(
        {"key": doc["key"]},
        {"$set": doc},
        upsert=True
    )


async def _cache_investor(db, investor: Dict):
    """Cache external investor data to local db"""
    pass  # TODO


async def _get_similar_projects(db, query: str) -> List[Dict]:
    """Get similar project suggestions"""
    regex = {"$regex": query[:3], "$options": "i"}
    
    similar = await db.intel_projects.find(
        {"$or": [{"name": regex}, {"symbol": regex}]},
        {"_id": 0, "name": 1, "symbol": 1, "slug": 1}
    ).limit(5).to_list(5)
    
    return similar


async def _update_source_sync(db, source_id: str, success: bool, 
                               count: int = 0, error: Optional[str] = None):
    """Update data source sync status"""
    now = datetime.now(timezone.utc).isoformat()
    
    update = {
        "updated_at": now
    }
    
    if success:
        update["last_sync"] = now
        await db.data_sources.update_one(
            {"id": source_id},
            {"$set": update, "$inc": {"sync_count": 1}}
        )
    else:
        update["last_error"] = error
        await db.data_sources.update_one(
            {"id": source_id},
            {"$set": update, "$inc": {"error_count": 1}}
        )


def _deduplicate_results(results: List[Dict]) -> List[Dict]:
    """Remove duplicate results based on name/id"""
    seen = set()
    unique = []
    
    for item in results:
        key = (item.get("name", ""), item.get("id", ""), item.get("_type", ""))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    
    return unique


def _format_time_ago(iso_time: Optional[str]) -> str:
    """Format ISO time as 'X ago'"""
    if not iso_time:
        return "Never"
    
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "Just now"
    except:
        return "Unknown"



# ═══════════════════════════════════════════════════════════════
# AUTO-DISCOVERY ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/auto/status")
async def get_auto_discovery_status():
    """Get auto-discovery engine status"""
    from server import db
    from modules.intel.auto_discovery import get_discovery_engine
    
    engine = get_discovery_engine(db)
    return await engine.get_discovery_status()


@router.post("/auto/audit")
async def run_endpoint_audit():
    """
    Audit all endpoints to find what's working and what's missing.
    This helps identify gaps in data coverage.
    """
    from server import db
    from modules.intel.auto_discovery import get_discovery_engine
    import os
    
    engine = get_discovery_engine(db)
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
    
    return await engine.audit_endpoints(base_url)


@router.post("/auto/discover")
async def run_full_discovery():
    """
    Run full auto-discovery process:
    1. Audit endpoints
    2. Search known sources for missing data
    3. Discover new sources if needed
    """
    from server import db
    from modules.intel.auto_discovery import get_discovery_engine
    import os
    
    engine = get_discovery_engine(db)
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
    
    return await engine.run_full_discovery(base_url)


@router.post("/auto/source/{source_id}/seen")
async def mark_source_as_seen(source_id: str):
    """Mark a new source as seen (removes NEW badge)"""
    from server import db
    from modules.intel.auto_discovery import get_discovery_engine
    
    engine = get_discovery_engine(db)
    result = await engine.mark_source_as_seen(source_id)
    
    return {
        "ts": ts_now(),
        "ok": result,
        "source_id": source_id
    }



# ═══════════════════════════════════════════════════════════════
# FULL AUTO-DISCOVERY (Complete System)
# ═══════════════════════════════════════════════════════════════

@router.get("/auto/full/status")
async def get_full_discovery_status():
    """Get full auto-discovery system status including new sources"""
    from server import db
    from modules.intel.full_auto_discovery import get_full_discovery
    
    engine = get_full_discovery(db)
    return await engine.get_status()


@router.post("/auto/full/audit")
async def run_full_endpoint_audit():
    """
    Run complete endpoint audit.
    Checks every documented endpoint and returns detailed status.
    """
    from server import db
    from modules.intel.full_auto_discovery import get_full_discovery
    import os
    
    engine = get_full_discovery(db)
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
    
    return await engine.run_full_audit(base_url)


@router.post("/auto/full/discover")
async def run_full_discovery_cycle():
    """
    Run complete discovery cycle:
    1. Audit all endpoints
    2. Find missing categories  
    3. Search providers for missing data
    4. Auto-register new providers
    5. Add new sources with NEW badge
    
    This is the main entry point for the auto-discovery system.
    """
    from server import db
    from modules.intel.full_auto_discovery import get_full_discovery
    import os
    
    engine = get_full_discovery(db)
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
    
    return await engine.run_full_discovery_cycle(base_url)


@router.post("/auto/full/mark-seen")
async def mark_all_discoveries_seen():
    """Mark all new discoveries as seen (removes NEW badges)"""
    from server import db
    from modules.intel.full_auto_discovery import get_full_discovery
    
    engine = get_full_discovery(db)
    count = await engine.mark_all_seen()
    
    return {
        "ts": ts_now(),
        "marked_count": count,
        "ok": True
    }


@router.get("/auto/providers/{category}")
async def get_providers_for_category(category: str):
    """Get available providers that can fulfill a specific category"""
    from server import db
    from modules.intel.full_auto_discovery import get_full_discovery
    
    engine = get_full_discovery(db)
    providers = await engine.find_provider_for_category(category)
    
    return {
        "ts": ts_now(),
        "category": category,
        "providers": providers
    }


# ═══════════════════════════════════════════════════════════════
# WEB SCRAPING DISCOVERY
# ═══════════════════════════════════════════════════════════════

@router.get("/web/status")
async def get_web_discovery_status():
    """Get web discovery status and discovered providers"""
    from server import db
    from modules.intel.web_discovery import get_web_discovery
    
    engine = get_web_discovery(db)
    
    return {
        "ts": ts_now(),
        "discovered_count": len(engine._discovered),
        "verified_count": len([p for p in engine._discovered if p.get("verified")]),
        "providers": engine._discovered[:10] if engine._discovered else []
    }


@router.post("/web/discover")
async def run_web_discovery(verify: bool = Query(True)):
    """
    Discover new crypto data providers from the web.
    Searches:
    - GitHub public-apis repository
    - Known crypto API marketplaces
    - Web search results
    
    Set verify=True to check if each API is accessible.
    """
    from server import db
    from modules.intel.web_discovery import get_web_discovery
    
    engine = get_web_discovery(db)
    return await engine.discover_new_providers(verify=verify)


@router.post("/web/add-providers")
async def add_web_discovered_providers(
    provider_ids: str = Query(None, description="Comma-separated provider IDs to add, or empty for all verified")
):
    """
    Add web-discovered providers to the registry.
    Only adds verified providers by default.
    """
    from server import db
    from modules.intel.web_discovery import get_web_discovery
    
    engine = get_web_discovery(db)
    
    ids = [pid.strip() for pid in provider_ids.split(",")] if provider_ids else None
    
    return await engine.add_discovered_to_registry(ids)
