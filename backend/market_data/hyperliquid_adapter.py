"""
Hyperliquid adapter — native, public, key-less.

Pulls funding / OI / mark-price from Hyperliquid via the official ccxt
binding (ccxt.hyperliquid). Read-only — no API keys, no signing.

API endpoint reached:  https://api.hyperliquid.xyz/info
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import ccxt.async_support as ccxt_async

log = logging.getLogger("market_data.hyperliquid")

_HYPERLIQUID_SYMBOLS = [
    "BTC/USDC:USDC", "ETH/USDC:USDC", "SOL/USDC:USDC",
    "ARB/USDC:USDC", "OP/USDC:USDC", "AVAX/USDC:USDC",
    "DOGE/USDC:USDC", "LINK/USDC:USDC",
]


class HyperliquidAdapter:
    venue = "hyperliquid"

    def __init__(self):
        self._client: Optional[ccxt_async.hyperliquid] = None

    async def _client_get(self):
        if self._client is None:
            self._client = ccxt_async.hyperliquid({
                "enableRateLimit": True,
                "timeout": 10_000,
            })
        return self._client

    async def fetch_funding(self) -> List[Dict[str, Any]]:
        """Pull funding rates for the configured symbol set."""
        c = await self._client_get()
        out: List[Dict[str, Any]] = []
        try:
            try:
                rates = await c.fetch_funding_rates(_HYPERLIQUID_SYMBOLS)
            except Exception:
                rates = {}
                for sym in _HYPERLIQUID_SYMBOLS:
                    try:
                        rates[sym] = await c.fetch_funding_rate(sym)
                    except Exception as e:
                        log.debug(f"funding_rate {sym}: {e}")
            for sym, raw in (rates.items() if isinstance(rates, dict) else []):
                if not raw:
                    continue
                base = sym.split("/")[0]
                out.append({
                    "venue": "hyperliquid",
                    "symbol": base,
                    "fundingRate": raw.get("fundingRate") or raw.get("interestRate"),
                    "markPrice": raw.get("markPrice"),
                    "indexPrice": raw.get("indexPrice"),
                    "nextFundingAt": raw.get("nextFundingTimestamp"),
                    "ts": raw.get("timestamp"),
                })
        except Exception as e:
            log.warning(f"hyperliquid fetch_funding failed: {e}")
        return out

    async def fetch_tickers(self) -> List[Dict[str, Any]]:
        """Pull last/bid/ask/24h volume for the symbol set."""
        c = await self._client_get()
        out: List[Dict[str, Any]] = []
        try:
            tickers = await c.fetch_tickers(_HYPERLIQUID_SYMBOLS)
            for sym, t in tickers.items():
                base = sym.split("/")[0]
                out.append({
                    "venue":   "hyperliquid",
                    "symbol":  base,
                    "price":   t.get("last") or t.get("close"),
                    "bid":     t.get("bid"),
                    "ask":     t.get("ask"),
                    "volume":  t.get("baseVolume"),
                    "change24h": t.get("percentage"),
                    "ts":      t.get("timestamp"),
                })
        except Exception as e:
            log.warning(f"hyperliquid fetch_tickers failed: {e}")
        return out

    async def close(self):
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None


# ───────────────── Sync helpers (for callers that don't run async loops) ─
def fetch_funding_sync() -> List[Dict[str, Any]]:
    a = HyperliquidAdapter()
    try:
        return asyncio.run(a.fetch_funding())
    finally:
        try: asyncio.run(a.close())
        except Exception: pass


def fetch_tickers_sync() -> List[Dict[str, Any]]:
    a = HyperliquidAdapter()
    try:
        return asyncio.run(a.fetch_tickers())
    finally:
        try: asyncio.run(a.close())
        except Exception: pass
