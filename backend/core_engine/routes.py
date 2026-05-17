"""
Core Engine V2.1 API Routes.
Supports tf parameter, search with preview, relative metrics.
"""

from fastapi import APIRouter, Query
from .service import get_snapshot_with_relative, get_universe, get_explain, search_symbols, get_snapshot

router = APIRouter(tags=["core-engine"])


# ── V2 Endpoints ──

@router.get("/api/core-engine/snapshot")
async def core_snapshot(
    scope: str = Query("global", regex="^(global|asset)$"),
    symbol: str = Query("BTCUSDT"),
    tf: str = Query("1h"),
):
    if scope == "global":
        return get_snapshot_with_relative(scope="global", symbol="BTCUSDT", tf=tf)
    return get_snapshot_with_relative(scope="asset", symbol=symbol, tf=tf)


@router.get("/api/core-engine/universe")
async def core_universe(tf: str = Query("1h")):
    return get_universe(tf=tf)


@router.get("/api/core-engine/explain")
async def core_explain(symbol: str = Query("BTCUSDT"), tf: str = Query("1h")):
    return get_explain(symbol, tf=tf)


@router.get("/api/core-engine/search")
async def core_search(q: str = Query("", min_length=1), tf: str = Query("1h")):
    return search_symbols(q, tf=tf)


# ── Legacy Endpoints ──

@router.get("/api/core/global")
async def legacy_core_global():
    return get_snapshot(scope="global", symbol="BTCUSDT")


@router.get("/api/core/asset")
async def legacy_core_asset(symbol: str = Query("BTCUSDT")):
    return get_snapshot(scope="asset", symbol=symbol)


@router.get("/api/core/universe")
async def legacy_core_universe():
    return get_universe()
