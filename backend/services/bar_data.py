"""
bar_data — minimal 1-minute OHLC fetcher for paper-runtime hit detection.

Pulls 1m klines from Binance public REST (`/api/v3/klines`) for the
symbols we paper-trade. Returns COMPLETED bars only (open & close time
known). Caller is responsible for interpreting high/low ranges.

Fallback contract: returns `[]` (not None, not exception) on any network
failure — caller MUST treat empty list as "no bar data, fall back to
last-tick price".
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import requests

logger = logging.getLogger("bar_data")

# Internal symbol → Binance trading pair
SYMBOL_TO_BINANCE = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "DOGE": "DOGEUSDT",
    "XRP": "XRPUSDT",
    "ADA": "ADAUSDT",
    "AVAX": "AVAXUSDT",
    "LINK": "LINKUSDT",
    "MATIC": "MATICUSDT",
    "DOT": "DOTUSDT",
    "TON": "TONUSDT",
}

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
HTTP_TIMEOUT = 4.0

# (symbol, bucket_start_ms) → list of bars · TTL ~30s
_cache: dict[str, dict] = {}
_cache_lock = threading.RLock()
_CACHE_TTL = 25.0


def _now_ms() -> int:
    return int(time.time() * 1000)


def fetch_recent_1m_bars(
    symbol: str,
    since_ms: Optional[int] = None,
    limit: int = 5,
) -> list[dict]:
    """Fetch up to `limit` recent COMPLETED 1m bars for symbol.

    If `since_ms` is provided, returns bars whose openTime >= since_ms.
    Returns `[{openTime, open, high, low, close, closeTime}]` ascending.

    Network failures → returns `[]` (NOT raises). Caller falls back to tick.
    """
    sym = symbol.upper()
    pair = SYMBOL_TO_BINANCE.get(sym)
    if not pair:
        return []

    cache_key = f"{sym}:{since_ms or 0}"
    with _cache_lock:
        ent = _cache.get(cache_key)
        if ent and time.time() - ent["fetched_at"] < _CACHE_TTL:
            return list(ent["bars"])

    params: dict[str, str | int] = {"symbol": pair, "interval": "1m", "limit": max(1, min(limit, 50))}
    if since_ms is not None:
        # Binance startTime is inclusive — we want bars STRICTLY since last eval.
        params["startTime"] = since_ms + 1

    try:
        r = requests.get(BINANCE_KLINES_URL, params=params, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        raw = r.json() or []
    except Exception as e:
        logger.warning(f"[bar_data] binance fetch failed for {sym}: {e}")
        return []

    bars: list[dict] = []
    now = _now_ms()
    for k in raw:
        if not isinstance(k, list) or len(k) < 7:
            continue
        try:
            close_time = int(k[6])
            # Only include CLOSED bars
            if close_time >= now:
                continue
            bars.append({
                "openTime": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "closeTime": close_time,
            })
        except (TypeError, ValueError):
            continue

    with _cache_lock:
        _cache[cache_key] = {"fetched_at": time.time(), "bars": bars}

    return bars


def supported(symbol: str) -> bool:
    return symbol.upper() in SYMBOL_TO_BINANCE
