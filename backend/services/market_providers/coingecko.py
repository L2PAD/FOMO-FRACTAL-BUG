"""
CoinGeckoProvider — Phase D · Pass 1.

Hardened wrapper for the public CoinGecko price API.

Behaviors:
    • In-memory rate-limit cooldown after 429 (exponential backoff, capped)
    • Persistent degraded cache in `market_price_cache` collection
    • Cache hit during cooldown → degraded=true, source='coingecko-cached'
    • Hard failure (provider unreachable + no cache) → None

NOT a multi-provider engine.  NOT freshness ranking.  NOT consensus.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from pymongo import MongoClient

from .provider_contract import MarketProvider


# Symbol → CoinGecko ID mapping.  Kept here (not in market_prices.py) so
# the provider is self-contained.
SYMBOL_TO_CG_ID = {
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
}

PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"
HTTP_TIMEOUT = 6.0

CACHE_COLLECTION = "market_price_cache"
CACHE_TTL_SECONDS = 600           # cache considered fresh up to 10 min
DEGRADED_CACHE_TTL_SECONDS = 86400  # serve degraded from cache up to 24h

COOLDOWN_INITIAL_SEC = 30
COOLDOWN_MAX_SEC = 600


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


class CoinGeckoProvider(MarketProvider):
    name = "coingecko"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._client: Optional[MongoClient] = None
        self._cooldown_until: float = 0.0     # monotonic timestamp
        self._cooldown_step: float = 0.0      # current backoff
        self._last_429_at: Optional[float] = None
        self._consec_429: int = 0

    # ── DB ─────────────────────────────────────────────────────────────
    def _db(self):
        if self._client is None:
            self._client = MongoClient(os.environ.get("MONGO_URL"))
        return self._client[os.environ.get("DB_NAME", "test_database")]

    # ── Public ────────────────────────────────────────────────────────
    def supports(self, symbol: str) -> bool:
        return symbol.upper() in SYMBOL_TO_CG_ID

    def get_price(self, symbol: str) -> Optional[dict]:
        sym = symbol.upper()
        cg_id = SYMBOL_TO_CG_ID.get(sym)
        if not cg_id:
            return {
                "ok": False, "symbol": sym, "price": None,
                "source": self.name, "degraded": False,
                "as_of": _now_iso(),
                "reason": "unsupported_symbol",
            }

        now = time.monotonic()

        # Fresh-cache short-circuit (cheap)
        fresh = self._cache_lookup(sym, max_age_sec=CACHE_TTL_SECONDS)
        if fresh is not None:
            return fresh

        # In cooldown? → degraded cache or honest None
        if now < self._cooldown_until:
            stale = self._cache_lookup(sym, max_age_sec=DEGRADED_CACHE_TTL_SECONDS)
            if stale is not None:
                stale = {**stale, "degraded": True, "source": "coingecko-cached"}
                return stale
            return {
                "ok": False, "symbol": sym, "price": None,
                "source": self.name, "degraded": True,
                "as_of": _now_iso(),
                "reason": "cooldown_active_no_cache",
            }

        # Live fetch
        try:
            r = requests.get(
                PRICE_URL,
                params={"ids": cg_id, "vs_currencies": "usd"},
                timeout=HTTP_TIMEOUT,
            )
            if r.status_code == 429:
                self._enter_cooldown()
                stale = self._cache_lookup(sym, max_age_sec=DEGRADED_CACHE_TTL_SECONDS)
                if stale is not None:
                    return {**stale, "degraded": True, "source": "coingecko-cached"}
                return {
                    "ok": False, "symbol": sym, "price": None,
                    "source": self.name, "degraded": True,
                    "as_of": _now_iso(),
                    "reason": "rate_limited_no_cache",
                }
            if r.status_code != 200:
                stale = self._cache_lookup(sym, max_age_sec=DEGRADED_CACHE_TTL_SECONDS)
                if stale is not None:
                    return {**stale, "degraded": True, "source": "coingecko-cached"}
                return {
                    "ok": False, "symbol": sym, "price": None,
                    "source": self.name, "degraded": True,
                    "as_of": _now_iso(),
                    "reason": f"http_{r.status_code}",
                }
            data = r.json()
            price = (data.get(cg_id) or {}).get("usd")
            if price is None:
                return {
                    "ok": False, "symbol": sym, "price": None,
                    "source": self.name, "degraded": False,
                    "as_of": _now_iso(),
                    "reason": "no_price_in_response",
                }

            # Success — reset cooldown, write cache
            self._reset_cooldown()
            payload = {
                "ok": True,
                "symbol": sym,
                "price": float(price),
                "source": self.name,
                "degraded": False,
                "as_of": _now_iso(),
                "reason": None,
            }
            self._cache_write(sym, payload)
            return payload
        except Exception:
            stale = self._cache_lookup(sym, max_age_sec=DEGRADED_CACHE_TTL_SECONDS)
            if stale is not None:
                return {**stale, "degraded": True, "source": "coingecko-cached"}
            return {
                "ok": False, "symbol": sym, "price": None,
                "source": self.name, "degraded": True,
                "as_of": _now_iso(),
                "reason": "network_error",
            }

    # ── Cache ─────────────────────────────────────────────────────────
    def _cache_lookup(self, symbol: str, max_age_sec: int) -> Optional[dict]:
        try:
            doc = self._db()[CACHE_COLLECTION].find_one(
                {"symbol": symbol}, {"_id": 0},
            )
            if not doc:
                return None
            cached_at = doc.get("cached_at_epoch") or 0
            if (time.time() - cached_at) > max_age_sec:
                return None
            return {
                "ok": True,
                "symbol": symbol,
                "price": float(doc.get("price")),
                "source": doc.get("source", self.name),
                "degraded": False,
                "as_of": doc.get("as_of") or _now_iso(),
                "reason": None,
            }
        except Exception:
            return None

    def _cache_write(self, symbol: str, payload: dict) -> None:
        try:
            self._db()[CACHE_COLLECTION].update_one(
                {"symbol": symbol},
                {"$set": {
                    "symbol": symbol,
                    "price": payload["price"],
                    "source": payload.get("source", self.name),
                    "as_of": payload.get("as_of", _now_iso()),
                    "cached_at_epoch": time.time(),
                }},
                upsert=True,
            )
        except Exception:
            pass

    # ── Cooldown ──────────────────────────────────────────────────────
    def _enter_cooldown(self) -> None:
        with self._lock:
            self._consec_429 += 1
            step = min(
                COOLDOWN_MAX_SEC,
                COOLDOWN_INITIAL_SEC * (2 ** max(0, self._consec_429 - 1)),
            )
            self._cooldown_step = step
            self._cooldown_until = time.monotonic() + step
            self._last_429_at = time.time()

    def _reset_cooldown(self) -> None:
        with self._lock:
            self._consec_429 = 0
            self._cooldown_step = 0.0
            self._cooldown_until = 0.0
