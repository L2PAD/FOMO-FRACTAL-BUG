"""
market_prices — Stage A-1: Live Price Truth.

Single-file native Python price service with CoinGecko fallback.
NOT a market-data engine. NOT an exchange connector. NOT a TA service.

Just truthful live spot prices for the core symbol universe so that:
  - /api/miniapp/home no longer returns price=0
  - Trading OS Command/Market/Execution can compute meaningful
    asymmetry / risk / entry zones from a real reference price
  - readiness gates have a real anchor

Contract:
  get_price('BTC')  →  {
      symbol, price, source, asOf, ok, degraded
  }

Honest-degraded on failure:
    price=None, ok=False, degraded=True, source='unavailable'

Cache: in-memory TTL 60s.  No DB writes.

Symbol universe:
  BTC, ETH, SOL, AVAX, XRP, DOGE, LINK, MATIC, BNB, ADA
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, List

import requests


# ─── Universe ──────────────────────────────────────────────────────────
# (symbol → CoinGecko id)
SYMBOL_TO_CG_ID: Dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "AVAX": "avalanche-2",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "LINK": "chainlink",
    "MATIC": "matic-network",
    "BNB": "binancecoin",
    "ADA": "cardano",
    # P1-D · Production universe expansion (Layer-2 + extras).
    # `coingecko_id` may be rate-limited at runtime; downstream consumers
    # MUST treat absence of CoinGecko data as transient and fall back
    # through the venue cascade (market_data/ohlc_provider.py).
    "ARB":  "arbitrum",
    "OP":   "optimism",
    "ATOM": "cosmos",
    "NEAR": "near",
    "DOT":  "polkadot",
    "SUI":  "sui",
    "APT":  "aptos",
    "UNI":  "uniswap",
    "LTC":  "litecoin",
    "FIL":  "filecoin",
}

CG_ID_TO_SYMBOL: Dict[str, str] = {v: k for k, v in SYMBOL_TO_CG_ID.items()}

SYMBOLS: List[str] = list(SYMBOL_TO_CG_ID.keys())

CACHE_TTL_SEC = 60
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
HTTP_TIMEOUT = 6.0


# ─── In-memory cache ───────────────────────────────────────────────────
# Two-tier: per-symbol price + a single global "last-refresh" timestamp so a
# single batch CG fetch hydrates everyone.
_lock = threading.RLock()
_prices: Dict[str, dict] = {}        # symbol → record
_last_refresh: float = 0.0           # epoch seconds
_last_error: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(symbol: str, price: Optional[float], source: str, degraded: bool) -> dict:
    return {
        "symbol": symbol.upper(),
        "price": float(price) if (price is not None and price > 0) else None,
        "source": source,
        "asOf": _now_iso(),
        "ok": price is not None and price > 0,
        "degraded": degraded,
    }


# ─── CoinGecko fetcher (single batch via hardened provider) ───────────
_provider = None  # lazy CoinGeckoProvider instance

def _get_provider():
    global _provider
    if _provider is None:
        try:
            from services.market_providers import CoinGeckoProvider
            _provider = CoinGeckoProvider()
        except Exception:
            _provider = None
    return _provider


def _fetch_from_coingecko() -> Dict[str, dict]:
    """Per-symbol price fetch via hardened CoinGeckoProvider.
    Uses cooldown + persistent cache. Single batch behavior preserved at
    cache-layer level — each get_price call is fast when cache fresh."""
    provider = _get_provider()
    out: Dict[str, dict] = {}
    if provider is None:
        for sym in SYMBOLS:
            out[sym] = _record(sym, None, "unavailable", degraded=True)
        return out
    for sym in SYMBOLS:
        p = provider.get_price(sym)
        if not p:
            out[sym] = _record(sym, None, "unavailable", degraded=True)
            continue
        # Adapt canonical provider shape → legacy market_prices shape
        out[sym] = {
            "symbol": p.get("symbol", sym),
            "price": p.get("price"),
            "source": p.get("source", "coingecko"),
            "asOf": p.get("as_of") or _now_iso(),
            "ok": bool(p.get("ok")),
            "degraded": bool(p.get("degraded")),
        }
    return out


def _refresh_if_stale(force: bool = False) -> None:
    """Refresh the cache if older than TTL.  Thread-safe via lock."""
    global _last_refresh, _last_error
    with _lock:
        age = time.time() - _last_refresh
        if not force and _prices and age < CACHE_TTL_SEC:
            return
        try:
            fresh = _fetch_from_coingecko()
            _prices.update(fresh)
            _last_refresh = time.time()
            _last_error = None
        except Exception as e:  # network / parse / etc
            _last_error = f"{type(e).__name__}: {e}"
            # Don't wipe existing cache on failure — serve stale-but-honest with
            # `degraded: true` flag below.  If cache empty, emit unavailable.
            if not _prices:
                for sym in SYMBOLS:
                    _prices[sym] = _record(sym, None, "unavailable", degraded=True)


def _staleness_seconds() -> int:
    return int(time.time() - _last_refresh) if _last_refresh else 99999


def get_price(symbol: str) -> dict:
    """Public API: one-symbol price record.  Always returns a dict; the
    `ok` flag is the only truth signal."""
    sym = (symbol or "").upper().strip()
    if not sym:
        return _record("", None, "unavailable", degraded=True)
    if sym not in SYMBOL_TO_CG_ID:
        return {
            "symbol": sym,
            "price": None,
            "source": "unsupported_symbol",
            "asOf": _now_iso(),
            "ok": False,
            "degraded": True,
        }
    _refresh_if_stale()
    rec = _prices.get(sym)
    if rec is None:
        return _record(sym, None, "unavailable", degraded=True)
    # Tag with cache age — frontend can decide if stale enough to fade
    return {**rec, "cacheAgeSec": _staleness_seconds()}


def get_prices(symbols: Optional[List[str]] = None) -> Dict[str, dict]:
    """Public API: many-symbol price records.  If `symbols=None`, return all."""
    _refresh_if_stale()
    syms = [s.upper() for s in (symbols or SYMBOLS)]
    out: Dict[str, dict] = {}
    age = _staleness_seconds()
    for s in syms:
        rec = _prices.get(s)
        if rec is None and s in SYMBOL_TO_CG_ID:
            rec = _record(s, None, "unavailable", degraded=True)
        elif rec is None:
            rec = {
                "symbol": s, "price": None, "source": "unsupported_symbol",
                "asOf": _now_iso(), "ok": False, "degraded": True,
            }
        out[s] = {**rec, "cacheAgeSec": age}
    return out


def service_health() -> dict:
    """Diagnostic: cache state + last error.  No mongo write."""
    with _lock:
        ok_count = sum(1 for r in _prices.values() if r.get("ok"))
        return {
            "ok": ok_count > 0,
            "symbolsTracked": len(SYMBOL_TO_CG_ID),
            "symbolsLive": ok_count,
            "cacheAgeSec": _staleness_seconds(),
            "ttlSec": CACHE_TTL_SEC,
            "lastError": _last_error,
            "source": "coingecko",
            "asOf": _now_iso(),
        }
