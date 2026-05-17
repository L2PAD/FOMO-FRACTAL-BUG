"""Overview V2.3 — API Routes: overview + history + labs + admin + WebSocket."""

import asyncio
import json
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from .engine import (
    compute_overview, get_position_history, compute_labs_drilldown,
    get_config, update_config, freeze_system, unfreeze_system,
    get_config_defaults, compute_alt_rotation,
)

router = APIRouter(prefix="/api", tags=["overview"])

_ws_clients = set()


def _get_core_snapshot(scope="global", tf="1h"):
    try:
        from core_engine.service import get_snapshot
        return get_snapshot(scope, tf)
    except Exception:
        return _empty_core()


def _get_macro_snapshot():
    try:
        from macro_v2.service import compute_macro
        return compute_macro()
    except Exception:
        return _empty_macro()


def _get_signals_snapshot(asset="BTCUSDT", tf="1h"):
    try:
        from signals.aggregator import compute_unified_signal
        core = _get_core_snapshot("global", tf)
        macro = _get_macro_snapshot()
        return compute_unified_signal(core, macro, asset)
    except Exception:
        return {"ok": False, "execution": {"score": 0, "bias": "balanced", "executionMode": "LOW_ACTIVITY", "contributors": {"exchange": 0, "accDist": 0, "onchain": 0}}, "events": [], "coreAlignment": {"status": "MIXED", "detail": ""}}


def _get_position_data(asset="BTCUSDT", tf="1h"):
    try:
        from macro_v2.position import compute_position_size
        core = _get_core_snapshot("global", tf)
        macro = _get_macro_snapshot()
        return compute_position_size(core, macro, asset)
    except Exception:
        return {"ok": False, "sizeMult": 0, "mode": "DEFENSIVE"}


def _get_hybrid_data():
    try:
        from macro_v2.hybrid import compute_hybrid as compute_hybrid_fn
        return compute_hybrid_fn()
    except Exception:
        return {"ok": False}


def _build_overview(asset="BTCUSDT", tf="1h"):
    core = _get_core_snapshot("global", tf)
    macro = _get_macro_snapshot()
    signals = _get_signals_snapshot(asset, tf)
    position = _get_position_data(asset, tf)
    hybrid_raw = _get_hybrid_data()
    return compute_overview(core, macro, signals, position, hybrid_raw, asset)


# ═══════════ OVERVIEW ═══════════

@router.get("/overview")
def get_overview(
    asset: str = Query("BTCUSDT"),
    tf: str = Query("1h"),
):
    return _build_overview(asset, tf)


# ═══════════ POSITION HISTORY ═══════════

@router.get("/overview/history")
def get_overview_history(
    asset: str = Query("BTCUSDT"),
    range: str = Query("30d"),
    step: str = Query("30m"),
):
    step_map = {"5m": 300, "15m": 900, "30m": 1800, "1h": 3600}
    step_sec = step_map.get(step, 1800)
    return get_position_history(asset, range, step_sec)


# ═══════════ LABS DRILLDOWN ═══════════

@router.get("/labs/drilldown")
def get_labs_drilldown(
    asset: str = Query("BTCUSDT"),
    tf: str = Query("1h"),
):
    core = _get_core_snapshot("global", tf)
    macro = _get_macro_snapshot()
    signals = _get_signals_snapshot(asset, tf)
    hybrid_raw = _get_hybrid_data()
    from .engine import compute_hybrid as ch, compute_alt_outlook as cao, compute_decision as cd
    hybrid = ch(hybrid_raw, macro.get("computed", {}).get("riskOffProb", 0.5))
    alt = cao(macro)
    decision = cd(core, macro, signals, hybrid, alt, asset)
    return compute_labs_drilldown(core, macro, signals, decision)


# ═══════════ ADMIN ═══════════

@router.get("/admin/config")
def admin_get_config():
    cfg = get_config()
    defaults = get_config_defaults()
    return {"ok": True, "config": cfg, "defaults": defaults}


# ═══════════ ALT ROTATION ═══════════

@router.get("/overview/alt-rotation")
def get_alt_rotation(
    asset: str = Query("BTCUSDT"),
    tf: str = Query("1h"),
):
    macro = _get_macro_snapshot()
    signals = _get_signals_snapshot(asset, tf)
    return compute_alt_rotation(macro, signals)


@router.patch("/admin/config")
def admin_patch_config(body: dict):
    updated = update_config(body)
    return {"ok": True, "config": updated}


@router.post("/admin/freeze")
def admin_freeze(body: dict = None):
    reason = (body or {}).get("reason", "Manual freeze")
    freeze_system(reason)
    return {"ok": True, "frozen": True, "reason": reason}


@router.post("/admin/unfreeze")
def admin_unfreeze():
    unfreeze_system()
    return {"ok": True, "frozen": False}


# ═══════════ WEBSOCKET ═══════════

@router.websocket("/overview/ws")
async def overview_ws(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    asset, tf = "BTCUSDT", "1h"
    prev_action, prev_regime = None, None

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                msg = json.loads(raw)
                asset = msg.get("asset", asset)
                tf = msg.get("tf", tf)
            except (asyncio.TimeoutError, json.JSONDecodeError):
                pass

            data = await asyncio.get_event_loop().run_in_executor(None, _build_overview, asset, tf)
            cur_action = data.get("decision", {}).get("action")
            cur_regime = data.get("macro", {}).get("regime")
            changed = (prev_action is not None and cur_action != prev_action) or \
                      (prev_regime is not None and cur_regime != prev_regime)
            data["_ws"] = {"changed": changed, "prevAction": prev_action, "prevRegime": prev_regime}
            prev_action, prev_regime = cur_action, cur_regime

            await websocket.send_json(data)
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _ws_clients.discard(websocket)


# ═══════════ EMPTY FALLBACKS ═══════════

def _empty_core():
    return {
        "ok": False,
        "regime": {"dominant": "range", "confidence": 0.25, "probabilities": {}},
        "risk": {"totalIndex": 50, "level": "moderate"},
        "factors": {"structure": 50, "flow": 50, "liquidity": 50, "smartMoney": 50, "stability": 50},
        "pressure": {"netBias": 0, "biasLabel": "neutral", "biasScore": 0},
        "transition": {"shiftProbability": 0.2},
        "execution": {"aggressionMultiplier": 0.5, "signalAmplification": 0.5, "strongActionsBlocked": False},
    }


def _empty_macro():
    return {
        "ok": False,
        "raw": {"fearGreed": 50, "btcDom": 50, "stableDom": 10},
        "computed": {"regime": "NEUTRAL", "regimeProbs": {"NEUTRAL": 0.5}, "riskOffProb": 0.5, "macroMult": 0.7, "strongActionsBlocked": False},
        "capitalFlow": {"btc": {"pressure": "FLAT", "delta7d": 0}, "stable": {"pressure": "FLAT", "delta7d": 0}},
        "lmi": {"score": 0},
        "riskSplit": {"structural": 50, "tactical": 50},
        "transitions": {"from": "NEUTRAL", "probabilities": {"NEUTRAL": 0.7}, "cpiDrift": 0, "riskoffMomentum": 0},
        "riskoffDrivers": {},
        "drivers": {},
    }
