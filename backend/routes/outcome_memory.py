"""
outcome_memory route — Stage A-6: Cognitive Accountability Layer.

Endpoints (mounted under /api/mbrain/outcomes):
    GET  /health        — substrate honesty (pending/resolved/expired/classifications)
    POST /sweep         — create PENDING outcomes from decision_history
    POST /resolve       — close mature PENDING outcomes (resolves_at ≤ now)
    GET  /recent        — last resolved (no cognition_snapshot, no PII)

NB: MUST be mounted BEFORE the trading-terminal gateway in server.py
so /api/mbrain/outcomes/* literal routes win over the upstream-503
catch-all forwarder.

Cognitive Accountability — NOT reinforcement learning.
WAIT is a first-class remembered outcome.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Query

from services.outcome_memory import (
    sweep_outcomes,
    resolve_outcomes,
    service_health,
    recent_resolved,
)


router = APIRouter(prefix="/api/mbrain/outcomes", tags=["mbrain-outcomes"])


@router.get("/health")
async def outcomes_health():
    return await asyncio.to_thread(service_health)


@router.post("/sweep")
async def outcomes_sweep(limit: int = Query(500, ge=1, le=5000)):
    return await asyncio.to_thread(sweep_outcomes, limit)


@router.post("/resolve")
async def outcomes_resolve(limit: int = Query(200, ge=1, le=2000)):
    return await asyncio.to_thread(resolve_outcomes, limit)


@router.get("/recent")
async def outcomes_recent(limit: int = Query(25, ge=1, le=200)):
    return await asyncio.to_thread(recent_resolved, limit)
