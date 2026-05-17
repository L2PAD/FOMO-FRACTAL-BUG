"""
fractal_runtime route — Stage A-5: structural perception layer.

NB: mounted BEFORE the trading-terminal gateway / node proxy in
server.py so /api/fractal/runtime/* literal routes win over upstream-503
forwarders.  Endpoints use /status instead of /health to avoid the node
proxy's `*/health` wildcard.
"""

from typing import Optional
from fastapi import APIRouter, Query

from services.fractal_runtime import (
    runtime,
    runtime_many,
    service_health,
)


router = APIRouter(prefix="/api/fractal/runtime", tags=["fractal-runtime"])


@router.get("/status")
def fractal_runtime_status():
    return service_health()


@router.get("/summary")
def fractal_runtime_summary(symbols: Optional[str] = Query(default="BTC,ETH,SOL")):
    syms = [s.strip().upper() for s in (symbols or "").split(",") if s.strip()]
    data = runtime_many(syms)
    live = sum(1 for v in data.values() if v.get("ok"))
    return {
        "ok": live > 0,
        "symbolsRequested": len(syms),
        "symbolsLive": live,
        "results": data,
    }


@router.get("/{symbol}")
def fractal_runtime_one(symbol: str):
    return runtime(symbol)
