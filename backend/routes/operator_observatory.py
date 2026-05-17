"""
operator_observatory route — Operator Cognition Observatory.

Endpoint:
    GET /api/mbrain/observatory/state

Read-only aggregator over already-live cognitive substrate.  Manual
refresh only — UI calls this on mount and on explicit refresh action.
No scheduler.  No background work.  No telemetry sink.

If decision_history is empty, returns:
    { ok: false, reason: 'insufficient_decision_context',
      phrase: 'Insufficient continuity for interpretive surface.' }
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from services.operator_observatory import observatory_state


router = APIRouter(prefix="/api/mbrain/observatory", tags=["operator-observatory"])


@router.get("/state")
async def observatory_state_endpoint():
    return await asyncio.to_thread(observatory_state)
