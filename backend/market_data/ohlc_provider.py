"""
CCXT OHLC fallback provider — production-stable daily candles.

WHY
---
In this environment Binance returns HTTP 451 (geo-block) and CoinGecko
returns HTTP 429 (rate-limit) within seconds.  Both providers used by
`services.technical_analysis._fetch_history()` are therefore unreliable
as a substrate.  This module wraps `ccxt` to fetch daily OHLC from a
cascading list of venues that *are* reachable from the container:

  coinbase (USD)  →  kraken (USD)  →  kucoin (USDT)  →  okx (USDT)

The function is synchronous (drives async ccxt under the hood via
`asyncio.run`), returns a list[float] of closes ordered ascending by
time — matching the schema TA already consumes.

Honest by construction:
  * On total failure returns ([], reason_string).  Never fabricates.
  * Each venue gets one shot; we don't retry within a venue to avoid
    blocking the TA fetch loop.
  * Rate-limit / network errors are surfaced explicitly in the reason
    string for `_classify_module_health()` to inspect.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Tuple

import ccxt.async_support as ccxt_async

log = logging.getLogger("market_data.ohlc_provider")

# Venue order matters: most permissive / lowest-cost first.
# (venue_name, quote_currency)
_VENUE_CASCADE: List[Tuple[str, str]] = [
    ("coinbase", "USD"),
    ("kraken",   "USD"),
    ("kucoin",   "USDT"),
    ("okx",      "USDT"),
]

# Per-venue symbol overrides where the canonical ticker isn't the base.
# (Most venues use the canonical ticker — overrides are rare.)
_VENUE_SYMBOL_OVERRIDE: dict = {
    # ("kraken", "BTC"): "XBT",  # Kraken historically used XBT; modern ccxt maps it.
}


def _venue_symbol(venue: str, base: str, quote: str) -> str:
    override = _VENUE_SYMBOL_OVERRIDE.get((venue, base.upper()))
    if override:
        return f"{override}/{quote}"
    return f"{base.upper()}/{quote}"


async def _try_venue(venue: str, quote: str, symbol: str, days: int) -> Tuple[List[float], Optional[str]]:
    """Single-venue OHLC fetch.  Returns (closes_asc, err_or_None)."""
    try:
        cls = getattr(ccxt_async, venue, None)
        if cls is None:
            return [], f"{venue}_not_in_ccxt"
        client = cls({"enableRateLimit": True, "timeout": 10_000})
        try:
            mkt_sym = _venue_symbol(venue, symbol, quote)
            ohlcv = await client.fetch_ohlcv(mkt_sym, timeframe="1d", limit=days)
        finally:
            try:
                await client.close()
            except Exception:
                pass
        if not ohlcv:
            return [], f"{venue}_empty"
        # OHLCV row: [ts_ms, open, high, low, close, volume]
        closes = [float(row[4]) for row in ohlcv if isinstance(row, list) and len(row) >= 5 and row[4] is not None]
        return closes, None
    except Exception as e:
        return [], f"{venue}_{type(e).__name__}"


async def _fetch_async(symbol: str, days: int) -> Tuple[List[float], Optional[str]]:
    """Cascade through venues until one returns enough candles."""
    errors: List[str] = []
    for venue, quote in _VENUE_CASCADE:
        closes, err = await _try_venue(venue, quote, symbol, days)
        if closes and len(closes) >= 14:  # MIN_CANDLES bar — matches TA
            return closes, None
        if err:
            errors.append(err)
    return [], "ccxt_cascade_failed:" + ",".join(errors)


def fetch_daily_closes(symbol: str, days: int = 30) -> Tuple[List[float], Optional[str]]:
    """
    Synchronous entrypoint used by `services.technical_analysis`.

    Returns (closes_asc, err_or_None).  When err is None, closes has
    len ≥ 14 (TA's MIN_CANDLES).  Caller is responsible for caching.
    """
    if not symbol:
        return [], "empty_symbol"
    try:
        # asyncio.run is fine here — TA's _fetch_history is invoked from
        # both sync (HTTP) and threaded contexts; we manage our own loop.
        return asyncio.run(_fetch_async(symbol.upper(), int(days)))
    except RuntimeError:
        # Already inside an event loop — schedule in a fresh loop in a thread.
        # In practice TA is called from a thread (asyncio.to_thread), so this
        # path is exercised only under unusual circumstances.
        import threading
        result_box: dict = {}

        def _runner():
            loop = asyncio.new_event_loop()
            try:
                result_box["res"] = loop.run_until_complete(_fetch_async(symbol.upper(), int(days)))
            finally:
                loop.close()

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join(timeout=45.0)
        return result_box.get("res", ([], "ccxt_runner_timeout"))
    except Exception as e:
        return [], f"ccxt_runner_{type(e).__name__}"
