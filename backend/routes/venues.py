"""
Exchange Venues — public endpoints surfacing live multi-venue data.

All venues are read-only and key-less.  Mounts under  /api/venues/*
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pymongo import MongoClient

router = APIRouter(prefix="/api/venues", tags=["venues"])

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "fomo_intelligence")]

# Module-level cache so we don't hammer exchanges on every request
_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL_SEC = 30


def _get_cached(key: str) -> Optional[Any]:
    entry = _CACHE.get(key)
    if not entry: return None
    if (time.time() - entry["at"]) > _CACHE_TTL_SEC:
        return None
    return entry["data"]


def _set_cached(key: str, data: Any):
    _CACHE[key] = {"at": time.time(), "data": data}


@router.get("/hyperliquid/funding")
async def hyperliquid_funding():
    cached = _get_cached("hl_funding")
    if cached is not None:
        return {"ok": True, "data": cached, "cached": True}
    try:
        from market_data.hyperliquid_adapter import HyperliquidAdapter
        a = HyperliquidAdapter()
        data = await a.fetch_funding()
        await a.close()
        _set_cached("hl_funding", data)
        # mirror to mongo for cross-venue alpha
        try:
            now = datetime.now(timezone.utc)
            for r in data:
                _db.raw_funding.update_one(
                    {"venue": "hyperliquid", "symbol": r["symbol"]},
                    {"$set": {**r, "ingestedAt": now}},
                    upsert=True,
                )
        except Exception: pass
        return {"ok": True, "data": data, "count": len(data)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/hyperliquid/tickers")
async def hyperliquid_tickers():
    cached = _get_cached("hl_tickers")
    if cached is not None:
        return {"ok": True, "data": cached, "cached": True}
    try:
        from market_data.hyperliquid_adapter import HyperliquidAdapter
        a = HyperliquidAdapter()
        data = await a.fetch_tickers()
        await a.close()
        _set_cached("hl_tickers", data)
        return {"ok": True, "data": data, "count": len(data)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/coinbase/tickers")
async def coinbase_tickers():
    cached = _get_cached("cb_tickers")
    if cached is not None:
        return {"ok": True, "data": cached, "cached": True}
    try:
        from market_data.coinbase_adapter import CoinbaseAdapter
        a = CoinbaseAdapter()
        data = await a.fetch_tickers()
        await a.close()
        _set_cached("cb_tickers", data)
        return {"ok": True, "data": data, "count": len(data)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/coinbase/spreads")
async def coinbase_spreads():
    cached = _get_cached("cb_spreads")
    if cached is not None:
        return {"ok": True, "data": cached, "cached": True}
    try:
        from market_data.coinbase_adapter import CoinbaseAdapter
        a = CoinbaseAdapter()
        data = await a.fetch_orderbook_spreads()
        await a.close()
        _set_cached("cb_spreads", data)
        return {"ok": True, "data": data, "count": len(data)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/all/health")
async def all_venues_health(symbol: str = Query("BTC")):
    """One-shot multi-venue health snapshot for a symbol (cached)."""
    cache_key = f"all_health_{symbol}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    out: Dict[str, Any] = {"symbol": symbol, "venues": {}}
    try:
        from market_data.hyperliquid_adapter import HyperliquidAdapter
        from market_data.coinbase_adapter import CoinbaseAdapter
        hl = HyperliquidAdapter()
        cb = CoinbaseAdapter()
        # Race each fetch with a per-call timeout (12s) to keep total well below 25s.
        async def _safe(coro):
            try:
                return await asyncio.wait_for(coro, timeout=12)
            except Exception:
                return []
        hl_f, hl_t, cb_t = await asyncio.gather(
            _safe(hl.fetch_funding()), _safe(hl.fetch_tickers()), _safe(cb.fetch_tickers())
        )
        try:
            await hl.close()
        except Exception:
            pass
        try:
            await cb.close()
        except Exception:
            pass
        for r in hl_f:
            if r["symbol"] == symbol:
                out["venues"].setdefault("hyperliquid", {})["funding"] = r
        for r in hl_t:
            if r["symbol"] == symbol:
                out["venues"].setdefault("hyperliquid", {})["ticker"] = r
        for r in cb_t:
            if r["symbol"] == symbol:
                out["venues"].setdefault("coinbase", {})["ticker"] = r
        # Add stored Binance/Bybit data from mongo if recent
        for venue in ("binance", "bybit"):
            doc = _db.raw_funding.find_one({"venue": venue, "symbol": symbol},
                                            sort=[("ingestedAt", -1)])
            if doc:
                doc.pop("_id", None); doc.pop("ingestedAt", None)
                out["venues"].setdefault(venue, {})["funding"] = doc
        out["ok"] = True
        out["timestamp"] = datetime.now(timezone.utc).isoformat()
        _set_cached(cache_key, out)
        return out
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e), "venues": out["venues"]},
                            status_code=500)
