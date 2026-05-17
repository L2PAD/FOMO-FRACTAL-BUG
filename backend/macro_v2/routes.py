"""Macro V2 API routes."""
from fastapi import APIRouter, Query
from .service import compute_macro, compute_macro_history
from .sync import compute_alignment
from .position import compute_position_size
from .hybrid import compute_hybrid
from .providers import get_data_source
from .live_data import is_live_available

router = APIRouter(tags=["macro-v2"])


@router.get("/api/core/macro/snapshot")
async def macro_v2_snapshot():
    """Full macro snapshot with computed metrics, capital flow, drivers, LMI, riskSplit."""
    return compute_macro()


@router.get("/api/core/macro/history")
async def macro_v2_history(limit: int = Query(90, ge=7, le=365)):
    """Historical macro computed data for charts."""
    return compute_macro_history(limit)


@router.get("/api/core/macro-sync")
async def macro_sync(symbol: str = Query("BTCUSDT"), tf: str = Query("1h")):
    """Cross-system sync: Core Engine ↔ Macro V2 alignment."""
    from core_engine.service import compute_snapshot
    core_snap = compute_snapshot(symbol, tf=tf)
    macro_snap = compute_macro()
    sync_result = compute_alignment(core_snap, macro_snap)
    return {"ok": True, **sync_result}


@router.get("/api/core/position-size")
async def position_size(asset: str = Query("BTCUSDT"), tf: str = Query("1h")):
    """Position Sizing Policy — nonlinear execution intelligence."""
    from core_engine.service import compute_snapshot
    core_snap = compute_snapshot(asset, tf=tf)
    macro_snap = compute_macro()
    sync_result = compute_alignment(core_snap, macro_snap)
    risk_split = macro_snap.get("riskSplit", {"structural": 50, "tactical": 50})

    result = compute_position_size(core_snap, macro_snap, sync_result, risk_split)
    result["asset"] = asset
    result["ok"] = True
    return result


@router.get("/api/core/hybrid-layer")
async def hybrid_layer():
    """BTC ↔ SPX Hybrid Layer — cross-market correlation intelligence."""
    macro_snap = compute_macro()
    riskoff = macro_snap.get("computed", {}).get("riskOffProb", 0.5)
    return compute_hybrid(riskoff_prob=riskoff)


@router.get("/api/core/macro/status")
async def macro_status():
    """Data source health and status."""
    live_ok = is_live_available()
    source = get_data_source()
    return {
        "dataSource": source,
        "liveApiAvailable": live_ok,
        "apis": {
            "cryptocompare": "reachable" if live_ok else "unreachable",
            "coinpaprika": "used" if source == "live" else "unused",
            "alternativeme": "used" if source == "live" else "unused",
        },
    }
