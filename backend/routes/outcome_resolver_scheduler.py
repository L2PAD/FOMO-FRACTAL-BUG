"""
outcome_resolver_scheduler route — Phase B · Step 3.

Endpoints (mounted under /api/mbrain/outcomes/scheduler):
    GET  /status        — pull-only status, history, next ETA, totals
    POST /run-once      — single synchronous resolution pass (manual fallback)
    POST /enable        — start background loop (idempotent)
    POST /disable       — stop background loop (idempotent)

Memory maintenance ONLY.  Not trading automation.  Not signal generation.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from services.outcome_resolver_scheduler import (
    status as _status,
    run_once as _run_once,
    enable_scheduler as _enable,
    disable_scheduler as _disable,
)


router = APIRouter(
    prefix="/api/mbrain/outcomes/scheduler",
    tags=["mbrain-outcomes-scheduler"],
)


@router.get("/status")
async def scheduler_status():
    return await asyncio.to_thread(_status)


@router.post("/run-once")
async def scheduler_run_once():
    return await asyncio.to_thread(_run_once)


@router.post("/enable")
async def scheduler_enable():
    # Must be called from the running event loop directly so the
    # create_task call lands on the correct loop.
    return _enable()


@router.post("/disable")
async def scheduler_disable():
    return _disable()
