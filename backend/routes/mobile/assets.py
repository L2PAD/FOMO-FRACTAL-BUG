"""Asset Universe + Intelligence routes."""
from fastapi import APIRouter, Query
from typing import Optional
from services.asset_registry import get_all_assets, search_assets as registry_search, get_categories
from services.asset_intelligence import (
    get_system_picks,
    get_asset_intelligence,
    get_watchlist,
    add_to_watchlist,
    remove_from_watchlist,
    search_assets as intel_search,
)

router = APIRouter()


@router.get("/assets")
async def get_assets_list(q: Optional[str] = Query(None)):
    if q:
        assets = registry_search(q)
    else:
        assets = get_all_assets()
    return {
        "total": len(assets),
        "assets": [
            {
                "symbol": a["symbol"],
                "name": a["name"],
                "category": a["category"],
                "rank": a["rank"],
                "binance": a["binance"],
                "bybit": a["bybit"],
            }
            for a in assets
        ],
    }


@router.get("/assets/categories")
async def get_asset_categories():
    cats = get_categories()
    return {
        "categories": {
            cat: [
                {"symbol": a["symbol"], "name": a["name"], "rank": a["rank"]}
                for a in items
            ]
            for cat, items in cats.items()
        }
    }


# ═══════════════════════════════════════════
#  ASSET INTELLIGENCE ENDPOINTS
# ═══════════════════════════════════════════

@router.get("/assets/system-picks")
async def system_picks():
    return {"ok": True, "picks": get_system_picks()}


@router.get("/assets/search-intel")
async def asset_search_intel(q: str = Query("")):
    return {"ok": True, "results": intel_search(q)}


@router.get("/assets/{symbol}/intelligence")
async def asset_intel(symbol: str):
    return get_asset_intelligence(symbol.upper())


@router.get("/watchlist")
async def watchlist_get(userId: str = Query("dev_user")):
    return {"ok": True, "assets": get_watchlist(userId)}


@router.post("/watchlist/{symbol}")
async def watchlist_add(symbol: str, userId: str = Query("dev_user")):
    assets = add_to_watchlist(userId, symbol)
    return {"ok": True, "assets": assets}


@router.delete("/watchlist/{symbol}")
async def watchlist_remove(symbol: str, userId: str = Query("dev_user")):
    assets = remove_from_watchlist(userId, symbol)
    return {"ok": True, "assets": assets}
