"""
runtime_events route — operator-pulled continuity trace.

Endpoints under /api/runtime/events:
    GET /health        — ledger existence + capped config + latest entry
    GET /recent        — recent events (limit, optional type filter)

NO streaming.  NO websocket.  NO push.  Pull-only.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Query

from services.runtime_events import recent as _recent, health as _health, EVENT_TYPES


router = APIRouter(prefix="/api/runtime/events", tags=["runtime-events"])


@router.get("/health")
async def events_health():
    return await asyncio.to_thread(_health)


@router.get("/recent")
async def events_recent(
    limit: int = Query(50, ge=1, le=500),
    type: Optional[str] = Query(None, description=f"One of {sorted(EVENT_TYPES)}"),
):
    return await asyncio.to_thread(_recent, limit, type)
