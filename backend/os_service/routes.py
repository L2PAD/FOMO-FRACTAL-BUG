"""
OS Routes — Market Intelligence OS
====================================
GET /api/os/state          — full OS state
GET /api/os/opportunities  — ranked opportunities
GET /api/os/market-pulse   — market activity pulse
GET /api/os/regime-timeline — regime change history
GET /api/os/actor-radar    — actor activity radar
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/os", tags=["os"])


@router.get("/state")
def os_state():
    """Full OS state — aggregated from snapshot data. Zero calculations."""
    try:
        from .service import get_os_state
        state = get_os_state()
        return JSONResponse(content={"ok": True, **state})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/opportunities")
def os_opportunities():
    """Ranked market opportunities."""
    try:
        from .service import get_os_opportunities
        opps = get_os_opportunities()
        return JSONResponse(content={"ok": True, "opportunities": opps, "count": len(opps)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/market-pulse")
def os_market_pulse():
    """Market Pulse — activity level indicator."""
    try:
        from .service import get_market_pulse
        pulse = get_market_pulse()
        return JSONResponse(content={"ok": True, **pulse})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/regime-timeline")
def os_regime_timeline(limit: int = Query(20)):
    """Regime change timeline."""
    try:
        from .service import get_regime_timeline
        timeline = get_regime_timeline(limit=limit)
        return JSONResponse(content={"ok": True, "timeline": timeline, "count": len(timeline)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/actor-radar")
def os_actor_radar():
    """Actor activity radar — who is moving the market."""
    try:
        from .service import get_actor_radar
        radar = get_actor_radar()
        return JSONResponse(content={"ok": True, **radar})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/liquidity-evolution")
def os_liquidity_evolution():
    """Liquidity zone dynamics — strengthening/weakening/stable trends."""
    try:
        from .service import get_liquidity_evolution
        evolution = get_liquidity_evolution()
        return JSONResponse(content={"ok": True, "dynamics": evolution, "count": len(evolution)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
