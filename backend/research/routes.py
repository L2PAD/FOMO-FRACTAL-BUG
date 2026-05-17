"""
R1.3 — Research V3 Routes
GET /api/v11/exchange/research/global     — market context
GET /api/v11/exchange/research/asset/{sym} — per-asset context
GET /api/v11/exchange/research/universe   — cross-universe stats
GET /api/v11/exchange/research/symbols    — available symbols for search
"""

from fastapi import APIRouter, Query
from .engine import build_global_report, build_asset_report, build_universe_report

research_router = APIRouter(prefix="/api/v11/exchange/research", tags=["research-v3"])


@research_router.get("/global")
async def get_global_research(
    timeframe: str = Query("15m"),
    force: bool = Query(False),
):
    """Global market context — regime, risk, horizon bias, execution style."""
    return await build_global_report(timeframe, force)


@research_router.get("/asset/{symbol}")
async def get_asset_research(
    symbol: str,
    timeframe: str = Query("15m"),
    force: bool = Query(False),
):
    """Per-asset research — includes asset overlay from Radar."""
    sym = symbol.upper()
    if not sym.endswith("USDT"):
        sym += "USDT"
    return await build_asset_report(sym, timeframe, force)


@research_router.get("/universe")
async def get_universe_research(
    timeframe: str = Query("15m"),
    force: bool = Query(False),
):
    """Universe insight — dominant patterns across all symbols."""
    return await build_universe_report(timeframe, force)


@research_router.get("/symbols")
async def get_research_symbols():
    """Available symbols for asset research search."""
    try:
        from radar_v11.universe import get_spot_alpha_symbols
        symbols = get_spot_alpha_symbols()
        return {"ok": True, "symbols": sorted(symbols), "count": len(symbols)}
    except Exception:
        return {"ok": False, "symbols": [], "count": 0}


# Keep old endpoint for backwards compat
@research_router.get("/report")
async def get_research_report_compat(
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("15m"),
    force: bool = Query(False),
):
    """Legacy endpoint — redirects to global or asset based on symbol."""
    if symbol == "BTCUSDT":
        return await build_global_report(timeframe, force)
    return await build_asset_report(symbol, timeframe, force)
