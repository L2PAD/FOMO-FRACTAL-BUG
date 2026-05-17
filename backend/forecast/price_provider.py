"""
Forecast Price Provider — production universe edition
=====================================================
Single source of truth for historical price data used by the forecast
generator (`forecast/generator.py`).

P1-C · Provider cascade
-----------------------
1. **CCXT venue cascade** (coinbase/kraken/kucoin/okx) — primary.
   Reachable from this environment and consistently returns daily OHLC
   for the full production universe (BTC, ETH, SOL, DOGE, LINK, AVAX,
   ARB, OP, ADA, BNB, XRP, …).
2. **yfinance** — fallback for assets where Yahoo's ticker mapping is
   clean (BTC-USD, ETH-USD, etc.).  Useful when CCXT venues are all
   rate-limited simultaneously.

The cache layout is unchanged: `{asset_key: {"YYYY-MM-DD": close_float}}`.
The asset_key is the canonical bare ticker (BTC, ETH, …) so callers
don't need to know which provider succeeded.

Refresh cadence:
* TTL 30 min per asset.
* Per-asset refresh, not global, so a stale ARB does not block BTC.
"""

from __future__ import annotations

import time
import warnings
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

from market_data.ohlc_provider import fetch_daily_closes as _ccxt_closes

warnings.simplefilter("ignore")  # silence yfinance noise

_TTL_SEC = 1800  # 30 min per asset
_price_cache: dict[str, dict[str, float]] = {}   # canonical → {date: close}
_cache_ts: dict[str, float] = {}                  # canonical → last_refresh

# Canonical → Yahoo ticker overrides (only where the default `<SYM>-USD`
# pattern is broken or maps to an unrelated asset).
_YF_OVERRIDES = {
    "ARB": "ARB11841-USD",   # Arbitrum (default ARB-USD points to wrong asset)
    "OP":  "OP-USD",          # OP often works; CCXT is primary anyway
}


def _canonical(asset: str) -> str:
    if not asset:
        return ""
    s = asset.strip().upper()
    for suf in ("USDT", "USDC", "USD", "-PERP", "-USD"):
        if s.endswith(suf) and len(s) > len(suf):
            s = s[: -len(suf)]
            while s and s[-1] in ("-", "_", "/", ":"):
                s = s[:-1]
            break
    return s


def _yf_ticker(canonical: str) -> str:
    return _YF_OVERRIDES.get(canonical, f"{canonical}-USD")


def _refresh_from_ccxt(canonical: str, days: int) -> dict[str, float]:
    """Fetch via CCXT cascade, build {date_str: close} ascending."""
    closes, err = _ccxt_closes(canonical, days)
    if not closes:
        return {}
    # We don't get timestamps back from the helper (only closes asc by time).
    # Re-fetch with timestamps for date-accurate keys.
    import asyncio

    import ccxt.async_support as ccxt_async

    async def _fetch_ohlcv():
        for venue, quote in (("coinbase", "USD"), ("kraken", "USD"), ("kucoin", "USDT"), ("okx", "USDT")):
            try:
                cls = getattr(ccxt_async, venue, None)
                if cls is None:
                    continue
                c = cls({"enableRateLimit": True, "timeout": 10_000})
                try:
                    sym = f"{canonical}/{quote}"
                    ohlcv = await c.fetch_ohlcv(sym, timeframe="1d", limit=days)
                finally:
                    try:
                        await c.close()
                    except Exception:
                        pass
                if ohlcv and len(ohlcv) >= 14:
                    return ohlcv
            except Exception:
                continue
        return []

    try:
        ohlcv = asyncio.run(_fetch_ohlcv())
    except RuntimeError:
        # already in loop (rare here) — bail to closes-only path below
        ohlcv = []

    out: dict[str, float] = {}
    if ohlcv:
        for row in ohlcv:
            if not (isinstance(row, list) and len(row) >= 5 and row[4] is not None):
                continue
            ts_ms = int(row[0])
            date_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            out[date_str] = float(row[4])
        return out

    # Fallback: synthesise date keys ascending from today (least accurate but
    # forecast generator only requires ordering, not exact dates).
    today = datetime.now(timezone.utc).date()
    from datetime import timedelta as _td
    for i, p in enumerate(reversed(closes)):
        d = (today - _td(days=i)).isoformat()
        out[d] = float(p)
    return out


def _refresh_from_yfinance(canonical: str, days: int) -> dict[str, float]:
    ticker = _yf_ticker(canonical)
    try:
        df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
        if df is None or df.empty:
            return {}
    except Exception as e:
        print(f"[PriceProvider] yfinance fail {ticker}: {e}")
        return {}
    out: dict[str, float] = {}
    for idx, row in df.iterrows():
        try:
            date_str = str(idx)[:10]
            close_val = row["Close"]
            # yfinance may return a Series here when multiple tickers requested
            if hasattr(close_val, "iloc"):
                close_val = close_val.iloc[0]
            out[date_str] = float(close_val)
        except Exception:
            continue
    return out


def _refresh_cache(asset_key: str, days: int = 150) -> None:
    """Refresh the price cache for one canonical asset key."""
    canonical = _canonical(asset_key)
    if not canonical:
        return
    now = time.time()
    last = _cache_ts.get(canonical, 0.0)
    if last > 0 and (now - last) < _TTL_SEC and _price_cache.get(canonical):
        return

    # Primary: CCXT cascade (reliable in this environment).
    prices = _refresh_from_ccxt(canonical, days)
    # Fallback: yfinance.
    if not prices or len(prices) < 14:
        yf_prices = _refresh_from_yfinance(canonical, days)
        if yf_prices and len(yf_prices) >= 14:
            prices = yf_prices

    if prices and len(prices) >= 14:
        _price_cache[canonical] = prices
        _cache_ts[canonical] = now


def _resolve(asset: str) -> dict[str, float]:
    canonical = _canonical(asset)
    if not canonical:
        return {}
    _refresh_cache(canonical)
    return _price_cache.get(canonical, {})


def get_price(asset: str, ts_ms: int) -> Optional[float]:
    """Get close price for asset at given timestamp (nearest earlier date)."""
    prices = _resolve(asset)
    if not prices:
        return None
    target_date = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    if target_date in prices:
        return prices[target_date]
    for d in sorted(prices.keys(), reverse=True):
        if d <= target_date:
            return prices[d]
    return None


def get_current_price(asset: str) -> Optional[float]:
    """Get the most recent available price."""
    prices = _resolve(asset)
    if not prices:
        return None
    latest_date = max(prices.keys())
    return prices[latest_date]


def get_price_series(asset: str, start_date: str, end_date: str) -> dict[str, float]:
    """Get price series between two ISO dates (inclusive)."""
    prices = _resolve(asset)
    return {d: p for d, p in prices.items() if start_date <= d <= end_date}
