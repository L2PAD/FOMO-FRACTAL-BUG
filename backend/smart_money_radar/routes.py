"""
Smart Money Radar + Brain Routes
==================================
GET /api/onchain/smart-money/radar      — Discovery feed (Events)
GET /api/onchain/smart-money/brain      — Alpha Score per token
GET /api/onchain/smart-money/patterns   — Market Phases
GET /api/onchain/smart-money/map        — Capital Routes
GET /api/onchain/smart-money/narrative  — Narrative Engine (Sprint 1.5)
GET /api/onchain/smart-money/top-actors — Top Smart Actors (Sprint 1.5)
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from .service import get_radar_events
from .brain import get_brain_signals
from .patterns import get_patterns

router = APIRouter(prefix="/api/onchain/smart-money", tags=["smart-money"])


@router.get("/intelligence-context")
async def token_intelligence_context(
    chainId: int = Query(1),
    window: str = Query("7d"),
):
    """Single aggregated endpoint for Token Intelligence page — replaces 6 parallel calls."""
    try:
        from .intelligence_context import get_token_intelligence_context
        ctx = get_token_intelligence_context(chain_id=chainId, window=window)
        return JSONResponse(content={"ok": True, **ctx, "meta": {"chainId": chainId, "window": window}})
    except Exception as e:
        print(f"[IntelligenceContext] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/context")
async def smart_money_context(
    chainId: int = Query(1),
    window: str = Query("24h"),
):
    try:
        from .context import get_smart_money_context
        ctx = get_smart_money_context(chain_id=chainId, window=window)
        return JSONResponse(content={"ok": True, **ctx, "meta": {"chainId": chainId, "window": window}})
    except Exception as e:
        print(f"[SmartMoneyContext] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/radar")
async def radar_feed(
    chainId: int = Query(1),
    window: str = Query("24h"),
    sort: str = Query("confidence"),
    limit: int = Query(20, le=50, ge=1),
):
    try:
        events = get_radar_events(chain_id=chainId, window=window, sort_by=sort, limit=limit)
        return JSONResponse(content={"ok": True, "events": events, "meta": {"chainId": chainId, "window": window, "sort": sort, "count": len(events)}})
    except Exception as e:
        print(f"[SmartMoneyRadar] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/brain")
async def brain_signals(
    chainId: int = Query(1),
    window: str = Query("24h"),
    limit: int = Query(10, le=30, ge=1),
):
    try:
        signals = get_brain_signals(chain_id=chainId, window=window, limit=limit)
        return JSONResponse(content={"ok": True, "signals": signals, "meta": {"chainId": chainId, "window": window, "count": len(signals)}})
    except Exception as e:
        print(f"[SmartMoneyBrain] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/patterns")
async def pattern_feed(
    chainId: int = Query(1),
    window: str = Query("24h"),
    limit: int = Query(10, le=20, ge=1),
):
    try:
        pats = get_patterns(chain_id=chainId, window=window, limit=limit)
        return JSONResponse(content={"ok": True, "patterns": pats, "meta": {"chainId": chainId, "window": window, "count": len(pats)}})
    except Exception as e:
        print(f"[SmartMoneyPatterns] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/map")
async def map_data(
    chainId: int = Query(1),
    window: str = Query("24h"),
    limit: int = Query(15, le=30, ge=1),
):
    try:
        from .map_service import get_map_data
        data = get_map_data(chain_id=chainId, window=window, limit=limit)
        return JSONResponse(content={"ok": True, **data, "meta": {"chainId": chainId, "window": window}})
    except Exception as e:
        print(f"[SmartMoneyMap] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})



@router.get("/narrative")
async def narrative_feed(
    chainId: int = Query(1),
    window: str = Query("24h"),
):
    try:
        from .narrative import get_narrative
        data = get_narrative(chain_id=chainId, window=window)
        return JSONResponse(content={"ok": True, **data, "meta": {"chainId": chainId, "window": window}})
    except Exception as e:
        print(f"[SmartMoneyNarrative] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/top-actors")
async def top_actors_feed(
    chainId: int = Query(1),
    window: str = Query("24h"),
    limit: int = Query(10, le=30, ge=1),
):
    try:
        from .top_actors import get_top_actors
        actors = get_top_actors(chain_id=chainId, window=window, limit=limit)
        return JSONResponse(content={"ok": True, "actors": actors, "meta": {"chainId": chainId, "window": window, "count": len(actors)}})
    except Exception as e:
        print(f"[SmartMoneyTopActors] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/signals")
async def signals_feed(
    chainId: int = Query(1),
    window: str = Query("24h"),
    limit: int = Query(15, le=30, ge=1),
):
    try:
        from .signals_engine import get_signals
        signals = get_signals(chain_id=chainId, window=window, limit=limit)
        return JSONResponse(content={"ok": True, "signals": signals, "meta": {"chainId": chainId, "window": window, "count": len(signals)}})
    except Exception as e:
        print(f"[SmartMoneySignals] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/wallet-strategies")
async def wallet_strategies_feed(
    chainId: int = Query(1),
    window: str = Query("24h"),
    limit: int = Query(15, le=30, ge=1),
):
    try:
        from .wallet_strategies import get_wallet_strategies
        strategies = get_wallet_strategies(chain_id=chainId, window=window, limit=limit)
        return JSONResponse(content={"ok": True, "strategies": strategies, "meta": {"chainId": chainId, "window": window, "count": len(strategies)}})
    except Exception as e:
        print(f"[WalletStrategies] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/playbooks")
async def playbooks_feed(
    chainId: int = Query(1),
    window: str = Query("24h"),
    limit: int = Query(8, le=15, ge=1),
):
    try:
        from .playbooks import get_playbooks
        playbooks = get_playbooks(chain_id=chainId, window=window, limit=limit)
        return JSONResponse(content={"ok": True, "playbooks": playbooks, "meta": {"chainId": chainId, "window": window, "count": len(playbooks)}})
    except Exception as e:
        print(f"[SmartMoneyPlaybooks] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/wallet/{address}/context")
async def wallet_context(
    address: str,
    chainId: int = Query(1),
    window: str = Query("24h"),
):
    try:
        from .wallet_context import get_wallet_context
        ctx = get_wallet_context(address=address, chain_id=chainId, window=window)
        return JSONResponse(content={"ok": True, **ctx, "meta": {"address": address, "chainId": chainId, "window": window}})
    except Exception as e:
        print(f"[WalletContext] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/token/{symbol}/context")
async def token_context(
    symbol: str,
    chainId: int = Query(1),
    window: str = Query("7d"),
):
    try:
        from .token_context import get_token_context
        ctx = get_token_context(symbol=symbol, chain_id=chainId, window=window)
        return JSONResponse(content={"ok": True, **ctx, "meta": {"symbol": symbol, "chainId": chainId, "window": window}})
    except Exception as e:
        print(f"[TokenContext] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/feed")
async def alpha_feed(
    chainId: int = Query(1),
    window: str = Query("24h"),
    min_conviction: int = Query(40, ge=0, le=100),
    signal_type: str = Query("all"),
    limit: int = Query(20, le=50, ge=1),
):
    try:
        from .signals_engine import get_signals
        all_signals = get_signals(chain_id=chainId, window=window, limit=50)
        filtered = [s for s in all_signals if s["conviction"] >= min_conviction]
        if signal_type != "all":
            filtered = [s for s in filtered if s["signal_type"] == signal_type]
        return JSONResponse(content={"ok": True, "signals": filtered[:limit], "meta": {"chainId": chainId, "window": window, "min_conviction": min_conviction, "signal_type": signal_type, "count": len(filtered[:limit])}})
    except Exception as e:
        print(f"[AlphaFeed] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
