"""
TA route — Stage A-2: TA as perception layer.

Exposes the native Python TA service:
  GET  /api/ta/basic/{symbol}
  GET  /api/ta/summary?symbols=BTC,ETH
  GET  /api/ta/health

Truthful contract:
  ok=true            → state/direction/confidence/reasons are valid
  ok=false           → degraded=true, reason explains why (no fake data)
"""

from typing import Optional
from fastapi import APIRouter, Query

from services.technical_analysis import (
    analyze,
    analyze_many,
    service_health,
    SYMBOLS,
)


router = APIRouter(prefix="/api/ta", tags=["technical-analysis"])


@router.get("/health")
def ta_health():
    return service_health()


@router.get("/basic/{symbol}")
def ta_basic(symbol: str):
    return analyze(symbol)


@router.get("/summary")
def ta_summary(symbols: Optional[str] = Query(default=None, description="Comma-separated symbols; defaults to all tracked")):
    syms = None
    if symbols:
        syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    data = analyze_many(syms)
    live = sum(1 for v in data.values() if v.get("ok"))
    return {
        "ok": live > 0,
        "symbolsTracked": len(SYMBOLS),
        "symbolsLive": live,
        "results": data,
    }
