"""
sentiment_runtime route — Stage A-4: events-based sentiment pressure layer.

Exposes the LLM-independent sentiment runtime so that surfaces can
consume truthful crowd pressure even when the LLM budget is exhausted.

  GET  /api/sentiment/runtime/health
  GET  /api/sentiment/runtime/{symbol}
  GET  /api/sentiment/runtime/summary?symbols=BTC,ETH

NB: must be mounted BEFORE the trading-terminal gateway / node proxy so
literal paths win over upstream-503 forwarders.
"""

from typing import Optional
from fastapi import APIRouter, Query

from services.sentiment_runtime import (
    runtime,
    runtime_many,
    service_health,
)


router = APIRouter(prefix="/api/sentiment/runtime", tags=["sentiment-runtime"])


@router.get("/status")
def sentiment_runtime_health():
    return service_health()


@router.get("/summary")
def sentiment_runtime_summary(symbols: Optional[str] = Query(default="BTC,ETH,SOL")):
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
def sentiment_runtime_one(symbol: str):
    return runtime(symbol)
