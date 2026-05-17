"""
paper_runtime route — Phase C foundation.

Endpoints under /api/paper:
    GET  /runtime/health        — gate state + collection counters
    GET  /accounts              — paper accounts list (empty in Phase C)
    GET  /positions             — paper positions list (empty in Phase C)
    GET  /orders                — paper orders list (empty in Phase C)
    GET  /events                — audit ledger of gate decisions / intents
    POST /orders/simulate       — gated; current state returns refusal

Phase C is a CONTRACT SKELETON.  No execution.  No deployment.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Query

from services.paper_runtime import (
    service_health as _health,
    list_accounts as _accounts,
    list_positions as _positions,
    list_orders as _orders,
    list_events as _events,
    simulate_order as _simulate,
)


router = APIRouter(prefix="/api/paper", tags=["paper-runtime"])


@router.get("/runtime/health")
async def paper_runtime_health():
    return await asyncio.to_thread(_health)


@router.get("/accounts")
async def paper_accounts():
    return await asyncio.to_thread(_accounts)


@router.get("/positions")
async def paper_positions():
    return await asyncio.to_thread(_positions)


@router.get("/orders")
async def paper_orders(limit: int = Query(50, ge=1, le=200)):
    return await asyncio.to_thread(_orders, limit)


@router.get("/events")
async def paper_events(limit: int = Query(50, ge=1, le=200)):
    return await asyncio.to_thread(_events, limit)


@router.post("/orders/simulate")
async def paper_orders_simulate(payload: Optional[dict] = Body(default=None)):
    return await asyncio.to_thread(_simulate, payload)
