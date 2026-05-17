"""
Trading Runtime API — /api/trading/*

Native FastAPI module replacing the retired Trading Terminal side-car.
All endpoints read in-process cognition state (no HTTP loop-back, no :8002).

TIER-2 — Backend Capability Enforcement
=======================================

Every endpoint below is guarded by a `Depends(require_capability(...))`.
Frontend visibility is decorative ONLY; the security boundary lives here.

Endpoint → capability map:

  /runtime/status                  → tradingOsVisible (operational view)
  /verdict/{symbol}                → authenticated (anyone w/ auth can read cognition)
  /opportunities                   → authenticated
  /intelligence/calibration*       → authenticated (analytics, no execution)

  /paper/account, /paper/orders,
  /paper/positions, /paper/events  → executionConsole (operator-only view)

  /paper/submit                    → paperTrading (must be paper-approved)
  /paper/close                     → paperTrading
  /paper/evaluate-hits             → paperTrading

  /paper/scheduler/status          → executionConsole
  /paper/scheduler/enable,
  /paper/scheduler/disable,
  /paper/scheduler/run-once        → executionConsole

Any caller without a valid auth header → 401
Authenticated caller without the listed capability → 403 with explicit
`required` + `granted` lists in the response body so the client UI can
explain *why* it was refused.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, HTTPException

from services import trading_runtime as svc
from services.security import (
    require_authenticated,
    require_capability,
)

router = APIRouter(prefix="/api/trading", tags=["trading-runtime"])


# Pre-built guards — declared once, reused per endpoint
_GUARD_AUTH = require_authenticated
_GUARD_TRADING_OS = require_capability(trading_os_visible=True)
_GUARD_EXEC = require_capability(execution_console=True)
_GUARD_PAPER = require_capability(paper_trading=True)


# ── Status ────────────────────────────────────────────────────────────


@router.get("/runtime/status")
async def trading_runtime_status(ctx: dict = Depends(_GUARD_TRADING_OS)):
    return await asyncio.to_thread(svc.runtime_status)


# ── Verdict / opportunities ───────────────────────────────────────────


@router.get("/verdict/{symbol}")
async def trading_verdict(symbol: str, ctx: dict = Depends(_GUARD_AUTH)):
    sym = (symbol or "").strip().upper()
    if not sym:
        raise HTTPException(status_code=400, detail={"error": "symbol_required"})
    return await asyncio.to_thread(svc.build_verdict, sym)


@router.get("/opportunities")
async def trading_opportunities(
    symbols: str = Query(
        "BTC,ETH,SOL",
        description="Comma-separated watchlist (e.g. BTC,ETH,SOL,DOGE)",
    ),
    ctx: dict = Depends(_GUARD_AUTH),
):
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail={"error": "no_symbols"})
    return await asyncio.to_thread(svc.scan_opportunities, syms)


# ── Paper account / read endpoints (operator view) ────────────────────


@router.get("/paper/account")
async def paper_account(
    accountId: str = Query(svc.DEFAULT_ACCOUNT_ID),
    ctx: dict = Depends(_GUARD_PAPER),
):
    return await asyncio.to_thread(svc.get_account, accountId)


@router.get("/paper/orders")
async def paper_orders(
    accountId: str = Query(svc.DEFAULT_ACCOUNT_ID),
    limit: int = Query(50, ge=1, le=200),
    ctx: dict = Depends(_GUARD_PAPER),
):
    out = await asyncio.to_thread(svc.list_orders, accountId, limit)
    return {"ok": True, "count": len(out), "orders": out}


@router.get("/paper/positions")
async def paper_positions(
    accountId: str = Query(svc.DEFAULT_ACCOUNT_ID),
    status: str = Query("OPEN", description="OPEN | CLOSED | ALL"),
    ctx: dict = Depends(_GUARD_PAPER),
):
    out = await asyncio.to_thread(svc.list_positions, accountId, status.upper())
    return {"ok": True, "count": len(out), "positions": out}


@router.get("/paper/events")
async def paper_events(
    accountId: str = Query(svc.DEFAULT_ACCOUNT_ID),
    limit: int = Query(50, ge=1, le=200),
    ctx: dict = Depends(_GUARD_PAPER),
):
    out = await asyncio.to_thread(svc.list_events, accountId, limit)
    return {"ok": True, "count": len(out), "events": out}


# ── Paper submit / close / evaluate (mutating ops) ────────────────────


@router.post("/paper/submit")
async def paper_submit(
    payload: Optional[dict] = Body(default=None),
    ctx: dict = Depends(_GUARD_PAPER),
):
    payload = payload or {}
    symbol = (payload.get("symbol") or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail={"error": "symbol_required"})
    return await asyncio.to_thread(
        svc.submit_paper_order,
        symbol,
        payload.get("accountId") or svc.DEFAULT_ACCOUNT_ID,
        payload.get("action"),
        payload.get("sizeUsd"),
    )


@router.post("/paper/close")
async def paper_close(
    payload: Optional[dict] = Body(default=None),
    ctx: dict = Depends(_GUARD_PAPER),
):
    payload = payload or {}
    position_id = (payload.get("positionId") or "").strip()
    if not position_id:
        raise HTTPException(status_code=400, detail={"error": "positionId_required"})
    return await asyncio.to_thread(
        svc.close_paper_position,
        position_id,
        payload.get("accountId") or svc.DEFAULT_ACCOUNT_ID,
        payload.get("reason") or "manual",
    )


@router.post("/paper/evaluate-hits")
async def paper_evaluate_hits(
    payload: Optional[dict] = Body(default=None),
    ctx: dict = Depends(_GUARD_PAPER),
):
    """Sweep open positions; auto-close any that hit stop/target."""
    payload = payload or {}
    return await asyncio.to_thread(
        svc.evaluate_stop_target_hits,
        payload.get("accountId") or svc.DEFAULT_ACCOUNT_ID,
    )


# ── Scheduler control (T3) ────────────────────────────────────────────


@router.get("/paper/scheduler/status")
async def scheduler_status(ctx: dict = Depends(_GUARD_EXEC)):
    from services import paper_runtime_scheduler as sched
    return await asyncio.to_thread(sched.status)


@router.post("/paper/scheduler/enable")
async def scheduler_enable(ctx: dict = Depends(_GUARD_EXEC)):
    # NOT to_thread — enable_scheduler() needs the running event loop
    # to create the background task. Calling via to_thread strands it
    # in a worker thread that has no bound loop on py3.10+.
    from services import paper_runtime_scheduler as sched
    return sched.enable_scheduler()


@router.post("/paper/scheduler/disable")
async def scheduler_disable(ctx: dict = Depends(_GUARD_EXEC)):
    from services import paper_runtime_scheduler as sched
    return sched.disable_scheduler()


@router.post("/paper/scheduler/run-once")
async def scheduler_run_once(ctx: dict = Depends(_GUARD_EXEC)):
    """Force one synchronous evaluation pass — useful for tests/debug."""
    from services import paper_runtime_scheduler as sched
    return await asyncio.to_thread(sched.force_run_once)


# ── Calibration / Feedback (T4) ───────────────────────────────────────


@router.get("/intelligence/calibration")
async def calibration_report(
    symbol: str = Query(..., description="Asset symbol, e.g. BTC"),
    ctx: dict = Depends(_GUARD_AUTH),
):
    """Per-symbol calibration table: buckets, win rates, reliability, warnings."""
    sym = (symbol or "").strip().upper()
    if not sym:
        raise HTTPException(status_code=400, detail={"error": "symbol_required"})
    from services import calibration as _calib
    return await asyncio.to_thread(_calib.report, sym)


@router.get("/intelligence/calibration/cell")
async def calibration_cell(
    symbol: str = Query(..., description="Asset symbol"),
    side: str = Query(..., description="LONG | SHORT"),
    bucket: str = Query(..., description="alignment bucket, e.g. 0.33_0.67"),
    risk: str = Query(..., description="LOW | MED | HIGH | N/A"),
    ctx: dict = Depends(_GUARD_AUTH),
):
    """Single calibration cell lookup."""
    from services import calibration as _calib
    cell = await asyncio.to_thread(
        _calib.lookup, symbol.upper(), side.upper(), bucket, risk
    )
    if cell is None:
        return {"ok": True, "found": False, "cell": None}
    return {"ok": True, "found": True, "cell": cell}
