"""
Coinbase Advanced (spot) adapter — public, key-less.

Wraps ccxt.coinbase for read-only ticker/orderbook/funding-style data.
We use Coinbase for spot venue diversification (no funding for spot, but
price/volume + spread normalisation).

REST: https://api.exchange.coinbase.com  (public)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import ccxt.async_support as ccxt_async

log = logging.getLogger("market_data.coinbase")

_COINBASE_SYMBOLS = [
    "BTC/USD", "ETH/USD", "SOL/USD",
    "AVAX/USD", "LINK/USD", "DOGE/USD",
    "ADA/USD", "ARB/USD",
    "OP/USD", "NEAR/USD", "ATOM/USD",
]


class CoinbaseAdapter:
    venue = "coinbase"

    def __init__(self):
        self._client: Optional[ccxt_async.coinbase] = None

    async def _client_get(self):
        if self._client is None:
            self._client = ccxt_async.coinbase({
                "enableRateLimit": True,
                "timeout": 10_000,
            })
        return self._client

    async def fetch_tickers(self) -> List[Dict[str, Any]]:
        c = await self._client_get()
        out: List[Dict[str, Any]] = []
        # Per-symbol fetch — robust to deprecated/renamed listings (e.g. MATIC → POL).
        for sym in _COINBASE_SYMBOLS:
            try:
                t = await c.fetch_ticker(sym)
                base = sym.split("/")[0]
                out.append({
                    "venue":   "coinbase",
                    "symbol":  base,
                    "price":   t.get("last") or t.get("close"),
                    "bid":     t.get("bid"),
                    "ask":     t.get("ask"),
                    "volume":  t.get("baseVolume"),
                    "change24h": t.get("percentage"),
                    "ts":      t.get("timestamp"),
                })
            except Exception as e:
                log.debug(f"coinbase ticker {sym}: {e}")
        return out

    async def fetch_orderbook_spreads(self, depth_pct: float = 0.5) -> List[Dict[str, Any]]:
        """Snapshot bid/ask spreads (proxy for liquidity)."""
        c = await self._client_get()
        out: List[Dict[str, Any]] = []
        for sym in _COINBASE_SYMBOLS[:6]:   # limit to top-6 to stay under rate
            try:
                ob = await c.fetch_order_book(sym, limit=20)
                bid = (ob["bids"][0][0] if ob.get("bids") else None)
                ask = (ob["asks"][0][0] if ob.get("asks") else None)
                spread_bps = (
                    (ask - bid) / ((ask + bid) / 2) * 10_000 if bid and ask else None
                )
                out.append({
                    "venue": "coinbase",
                    "symbol": sym.split("/")[0],
                    "bid": bid, "ask": ask,
                    "spread_bps": spread_bps,
                    "ts": ob.get("timestamp"),
                })
            except Exception as e:
                log.debug(f"coinbase ob {sym}: {e}")
        return out

    async def close(self):
        if self._client is not None:
            try: await self._client.close()
            except Exception: pass
            self._client = None


def fetch_tickers_sync() -> List[Dict[str, Any]]:
    a = CoinbaseAdapter()
    try: return asyncio.run(a.fetch_tickers())
    finally:
        try: asyncio.run(a.close())
        except Exception: pass


def fetch_spreads_sync() -> List[Dict[str, Any]]:
    a = CoinbaseAdapter()
    try: return asyncio.run(a.fetch_orderbook_spreads())
    finally:
        try: asyncio.run(a.close())
        except Exception: pass
