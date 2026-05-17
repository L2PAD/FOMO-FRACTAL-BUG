"""
Alt Season + Lifecycle + Narrative Routes
"""

from fastapi import APIRouter
from alt_season_engine import run_altseason_pipeline
from lifecycle_engine import run_lifecycle_pipeline
from narrative_engine import run_narrative_flow

router = APIRouter()


@router.get("/api/altseason")
async def get_altseason():
    """Single endpoint: returns index, state, components, momentum, opportunities."""
    try:
        result = run_altseason_pipeline()
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── LIFECYCLE ENDPOINTS ──────────────────────────────────

_lifecycle_cache = {"data": None, "ts": 0}

def _get_lifecycle():
    """Cache lifecycle for 60s."""
    import time
    now = time.time()
    if _lifecycle_cache["data"] and now - _lifecycle_cache["ts"] < 60:
        return _lifecycle_cache["data"]
    result = run_lifecycle_pipeline()
    _lifecycle_cache["data"] = result
    _lifecycle_cache["ts"] = now
    return result


@router.get("/api/connections/lifecycle")
async def get_asset_lifecycle():
    """Asset-level lifecycle states + market state + pump signals."""
    try:
        data = _get_lifecycle()
        return {
            "ok": True,
            "data": data["assets"],
            "marketState": data.get("marketState"),
            "pumpSignals": data.get("pumpSignals", []),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "data": []}


@router.get("/api/connections/cluster-lifecycle")
async def get_cluster_lifecycle():
    """Cluster-level lifecycle states."""
    try:
        data = _get_lifecycle()
        return {"ok": True, "data": data["clusters"]}
    except Exception as e:
        return {"ok": False, "error": str(e), "data": []}


@router.get("/api/connections/early-rotation/active")
async def get_early_rotations():
    """Active rotation signals."""
    try:
        data = _get_lifecycle()
        return {"ok": True, "data": data["rotations"]}
    except Exception as e:
        return {"ok": False, "error": str(e), "data": []}


# ─── NARRATIVE FLOW ENDPOINT ──────────────────────────────

_narrative_cache = {"data": None, "ts": 0}

@router.get("/api/narrative-flow")
async def get_narrative_flow():
    """All-in-one narrative decision engine: scores, rotations, front-runs, tokens."""
    import time
    now = time.time()
    if _narrative_cache["data"] and now - _narrative_cache["ts"] < 60:
        return _narrative_cache["data"]
    try:
        result = run_narrative_flow()
        _narrative_cache["data"] = result
        _narrative_cache["ts"] = now
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

