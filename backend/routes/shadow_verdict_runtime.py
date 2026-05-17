"""
shadow_verdict_runtime route — Stage A-7: Shadow Verdict Runtime.

Endpoints (mounted under /api/mbrain/shadow-runtime):
    GET  /health        — counters, per-status distribution, last sweep
    POST /sweep         — generate shadow verdicts for symbols (default BTC,ETH,SOL)
    GET  /recent        — latest verdicts (cognitionSnapshot excluded)
    GET  /summary       — latest per-symbol + distribution + top reasons / blocked-by

NB: MUST be mounted BEFORE the trading-terminal gateway in server.py so
/api/mbrain/shadow-runtime/* literal routes win over the upstream-503
catch-all forwarder.

Naming discipline (per stage spec):
    shadow verdicts are NOT trade signals, NOT setups, NOT entry triggers,
    NOT execution intents.  `blocked` is a healthy cognition state.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Query

from services.shadow_verdict_runtime import (
    sweep as _sweep,
    service_health as _health,
    recent as _recent,
    summary as _summary,
    DEFAULT_SYMBOLS,
)


router = APIRouter(prefix="/api/mbrain/shadow-runtime", tags=["mbrain-shadow-runtime"])


def _parse_symbols(symbols: Optional[str]):
    if not symbols:
        return None
    parsed = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    return parsed or None


@router.get("/health")
async def shadow_health():
    return await asyncio.to_thread(_health)


@router.post("/sweep")
async def shadow_sweep(
    symbols: Optional[str] = Query(
        default=None,
        description="Comma-separated symbols. Default = BTC,ETH,SOL.",
    ),
):
    syms = _parse_symbols(symbols)
    return await asyncio.to_thread(_sweep, syms)


@router.get("/recent")
async def shadow_recent(
    limit: int = Query(25, ge=1, le=200),
    symbol: Optional[str] = Query(None),
):
    return await asyncio.to_thread(_recent, limit, symbol)


@router.get("/summary")
async def shadow_summary(
    symbols: Optional[str] = Query(
        default=None,
        description="Comma-separated symbols. Default = BTC,ETH,SOL.",
    ),
):
    syms = _parse_symbols(symbols)
    return await asyncio.to_thread(_summary, syms)
