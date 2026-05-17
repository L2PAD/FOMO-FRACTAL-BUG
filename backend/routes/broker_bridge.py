"""
Broker Readiness Bridge API — /api/broker/*  (T10.1 / T10.2B)

Read-only + preflight + always-refused live submit. NO real orders today.

TIER-2 — Backend Capability Enforcement
=======================================

Every endpoint below is guarded. Frontend visibility is decorative ONLY.

Endpoint → capability map:

  /status, /heartbeat,
  /balances, /markets        → tradingOsVisible (operator observability)
  /preflight                 → executionConsole (operator preflight tool)
  /audit                     → executionConsole (operator audit log)
  /live/submit               → liveTrading (admin-approved live operator only)

Even though the T10.1 invariant guarantees the submit endpoint refuses
EVERY caller right now, we still gate the call site at the FastAPI layer
so non-live operators (paper-only / unauthorized) cannot even POST a
"safe-mode refused" attempt to the audit log. This keeps the audit
ledger free of meaningless attempt rows from non-operators.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, HTTPException

from services import broker_bridge as svc
from services.security import require_capability

router = APIRouter(prefix="/api/broker", tags=["broker-bridge"])


_GUARD_OBSERVE = require_capability(trading_os_visible=True)
_GUARD_EXEC = require_capability(execution_console=True)
_GUARD_LIVE = require_capability(live_trading=True)


@router.get("/status")
async def status(ctx: dict = Depends(_GUARD_OBSERVE)):
    return await asyncio.to_thread(svc.broker_status)


@router.get("/heartbeat")
async def heartbeat(ctx: dict = Depends(_GUARD_OBSERVE)):
    return await asyncio.to_thread(svc.heartbeat_probe)


@router.get("/balances")
async def balances(ctx: dict = Depends(_GUARD_OBSERVE)):
    return await asyncio.to_thread(svc.list_balances)


@router.get("/markets")
async def markets(ctx: dict = Depends(_GUARD_OBSERVE)):
    return await asyncio.to_thread(svc.list_markets)


@router.post("/preflight")
async def preflight(
    payload: Optional[dict] = Body(default=None),
    ctx: dict = Depends(_GUARD_EXEC),
):
    payload = payload or {}
    if not (payload.get("symbol") or "").strip():
        raise HTTPException(status_code=400, detail={"error": "symbol_required"})
    return await asyncio.to_thread(svc.preflight, payload, None)


@router.post("/live/submit")
async def live_submit(
    payload: Optional[dict] = Body(default=None),
    ctx: dict = Depends(_GUARD_LIVE),
):
    """
    T10.1 invariant: backend ALWAYS refuses (broker submit path not wired).
    TIER-2 invariant: only liveTrading-approved operators reach this point.

    Even when this function runs, the response is:
      * finalStatus: 'refused' | 'refused_t10_1_safe_mode'
      * full preflight + gateChecks + verdict/sizing/gate snapshots
      * auditId written to broker_audit_v1
    """
    payload = payload or {}
    if not (payload.get("symbol") or "").strip():
        raise HTTPException(status_code=400, detail={"error": "symbol_required"})
    return await asyncio.to_thread(svc.attempt_live_submit, payload)


@router.get("/audit")
async def audit(
    limit: int = Query(50, ge=1, le=200),
    ctx: dict = Depends(_GUARD_EXEC),
):
    out = await asyncio.to_thread(svc.list_audit, limit)
    return {"ok": True, "count": len(out), "audit": out}
