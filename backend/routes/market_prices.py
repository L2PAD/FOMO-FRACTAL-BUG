"""
market_prices route — Stage A-1: Live Price Truth.

Exposes the native Python price service:
  GET  /api/market/price/{symbol}
  GET  /api/market/prices            (?symbols=BTC,ETH or all)
  GET  /api/market/health            (cache + last-error diagnostics)

All endpoints return JSON whose `ok` flag is the single truth signal.
No fake 0 prices, no fake bullish defaults.
"""

from typing import Optional
from fastapi import APIRouter, Query
from services.market_prices import get_price, get_prices, service_health, SYMBOLS

router = APIRouter(prefix="/api/market", tags=["market-prices"])


@router.get("/health")
def market_health():
    return service_health()


@router.get("/price/{symbol}")
def market_price(symbol: str):
    return get_price(symbol)


@router.get("/prices")
def market_prices(symbols: Optional[str] = Query(default=None, description="Comma-separated, e.g. BTC,ETH; defaults to all tracked")):
    syms = None
    if symbols:
        syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    data = get_prices(syms)
    return {
        "ok": any(v.get("ok") for v in data.values()),
        "symbolsTracked": len(SYMBOLS),
        "prices": data,
    }
