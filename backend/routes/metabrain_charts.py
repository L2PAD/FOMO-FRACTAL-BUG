"""MetaBrain Charts Routes (PROD-GAP-1.1 + 1.2)

Closes two long-standing dead UI contracts:
  GET /api/metabrain/candles/{symbol}        → daily OHLC, CCXT cascade fallback
  GET /api/metabrain/forecast-curve/{symbol} → forward curve from fractal+exchange+TA forecasts

Both endpoints follow the existing service patterns used in trading_runtime
and fractal_runtime, do not introduce new external dependencies, and degrade
gracefully (always 200 with `degraded` + `reason`) rather than 4xx so the UI
widgets never crash on missing data.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Path, Query
from pymongo import MongoClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metabrain", tags=["metabrain-charts"])


def _db():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "fomo_mobile")]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonicalize(sym: str) -> str:
    """Reuse same symbol canonicalisation as services/technical_analysis."""
    if not sym:
        return ""
    s = sym.upper().strip()
    for suf in ("USDT", "USDC", "USD", "-PERP", "-USD", "PERP"):
        if s.endswith(suf):
            s = s[: -len(suf)] if not s.endswith("-" + suf) else s[: -len(suf) - 1]
            break
    return s


# ---------------------------------------------------------------------------
# 1.1  GET /api/metabrain/candles/{symbol}
# ---------------------------------------------------------------------------

# In-process cache (90 sec) — same TTL pattern as ohlc_provider
_CANDLES_CACHE: Dict[str, Dict[str, Any]] = {}
_CANDLES_TTL_SEC = 90


def _fetch_ohlc_via_ccxt(symbol: str, days: int) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Try the CCXT cascade used elsewhere. Returns (candles, source) or ([], None)."""
    try:
        import ccxt  # type: ignore
    except Exception as e:
        logger.warning(f"[metabrain.candles] ccxt unavailable: {e}")
        return [], None

    base = _canonicalize(symbol)
    # Mirror order from market_data/ohlc_provider.py
    venues = [
        ("coinbase", "USD"),
        ("kraken",   "USD"),
        ("kucoin",   "USDT"),
        ("okx",      "USDT"),
        ("bybit",    "USDT"),
    ]
    timeframe = "1d"
    since_ms = int((time.time() - days * 86400) * 1000)
    limit = days + 5

    for venue_name, quote in venues:
        try:
            exch_cls = getattr(ccxt, venue_name, None)
            if exch_cls is None:
                continue
            ex = exch_cls({"enableRateLimit": True, "timeout": 8000})
            # Coinbase uses "BTC-USD"; kraken+others usually "BTC/USDT"
            if venue_name == "coinbase":
                pair = f"{base}-{quote}"
            else:
                pair = f"{base}/{quote}"
            ohlcv = ex.fetch_ohlcv(pair, timeframe=timeframe, since=since_ms, limit=limit)
            if not ohlcv or len(ohlcv) < 5:
                continue
            candles = [
                {
                    "t": int(row[0] // 1000),     # ts in seconds
                    "ts": int(row[0]),              # ms (UI lib expects)
                    "o": float(row[1]),
                    "h": float(row[2]),
                    "l": float(row[3]),
                    "c": float(row[4]),
                    "v": float(row[5] or 0.0),
                }
                for row in ohlcv
            ]
            return candles, f"ccxt:{venue_name}:{pair}"
        except Exception as e:
            logger.debug(f"[metabrain.candles] {venue_name} failed for {base}: {e}")
            continue
    return [], None


@router.get("/candles/{symbol}")
def get_candles(
    symbol: str = Path(..., description="Asset symbol (BTC, ETH, BTCUSDT, BTC-USD, etc.)"),
    days: int = Query(30, ge=7, le=365, description="Number of daily candles"),
) -> Dict[str, Any]:
    """Daily OHLC candles for chart widgets.

    Order of resolution:
        1. In-process cache (90s TTL)
        2. CCXT cascade (coinbase/kraken/kucoin/okx/bybit)
        3. Mongo collection `ohlc_daily_cache` (if previously persisted)
        4. Graceful degraded response with `candles: []`

    Always returns HTTP 200 so the chart widget never crashes; `degraded`
    flag tells the UI whether to show an empty-state message.
    """
    base = _canonicalize(symbol)
    cache_key = f"{base}:{days}"
    now = time.time()

    cached = _CANDLES_CACHE.get(cache_key)
    if cached and (now - cached["_ts"]) < _CANDLES_TTL_SEC:
        return {**cached["payload"], "cached": True}

    candles, source = _fetch_ohlc_via_ccxt(base, days)

    if not candles:
        # Try Mongo fallback (some legacy paths persist closes only)
        try:
            rec = _db()["ohlc_daily_cache"].find_one({"symbol": base})
            if rec and rec.get("candles"):
                candles = rec["candles"]
                source = rec.get("source", "mongo_cache")
        except Exception as e:
            logger.debug(f"[metabrain.candles] mongo cache miss: {e}")

    if not candles:
        return {
            "symbol":   base,
            "days":     days,
            "candles":  [],
            "source":   None,
            "degraded": True,
            "reason":   "no_ohlc_provider_available",
            "asOf":     _now_iso(),
        }

    payload = {
        "symbol":   base,
        "days":     days,
        "candles":  candles,
        "count":    len(candles),
        "source":   source,
        "degraded": False,
        "asOf":     _now_iso(),
    }
    _CANDLES_CACHE[cache_key] = {"_ts": now, "payload": payload}
    return payload


# ---------------------------------------------------------------------------
# 1.2  GET /api/metabrain/forecast-curve/{symbol}
# ---------------------------------------------------------------------------


def _collect_fractal_forecast_curve(base: str) -> List[Dict[str, Any]]:
    """Aggregate native fractal forecasts into a forward price curve.

    fractal_forecasts collection stores horizons (1d, 3d, 7d, 14d, 30d)
    with `targetPrice`, `direction`, `confidence`. We surface them as
    discrete points on a time axis.
    """
    try:
        coll = _db().get_collection(f"fractal_forecasts_{base.lower()}")
        # Newest doc per horizon
        out: List[Dict[str, Any]] = []
        seen = set()
        for doc in coll.find().sort("createdAt", -1).limit(200):
            horizon = doc.get("horizon") or doc.get("horizonLabel") or doc.get("horizonDays")
            if not horizon or horizon in seen:
                continue
            seen.add(horizon)
            target = doc.get("targetPrice") or doc.get("target") or doc.get("expectedPrice")
            if target is None:
                continue
            out.append({
                "horizon":    str(horizon),
                "horizonDays": doc.get("horizonDays"),
                "targetPrice": float(target),
                "direction":   doc.get("direction", "unknown"),
                "confidence":  float(doc.get("confidence", 0.0)),
                "source":      "fractal_native_v1",
            })
        return sorted(out, key=lambda p: p.get("horizonDays") or 0)
    except Exception as e:
        logger.debug(f"[forecast-curve] fractal miss: {e}")
        return []


def _collect_exchange_forecast_point(base: str) -> Optional[Dict[str, Any]]:
    try:
        doc = _db()["exchange_forecasts"].find_one(
            {"symbol": {"$in": [base, base + "USDT", base + "USD"]}},
            sort=[("createdAt", -1)],
        )
        if not doc:
            return None
        target = doc.get("targetPrice") or doc.get("target")
        if target is None:
            return None
        return {
            "horizon":     doc.get("horizon", "exchange_1d"),
            "horizonDays": doc.get("horizonDays", 1),
            "targetPrice": float(target),
            "direction":   doc.get("direction", "unknown"),
            "confidence":  float(doc.get("confidence", 0.0)),
            "source":      "exchange_forecasts",
        }
    except Exception as e:
        logger.debug(f"[forecast-curve] exchange miss: {e}")
        return None


def _collect_ta_anchor(base: str) -> Optional[Dict[str, Any]]:
    """Current TA snapshot becomes the t=0 anchor of the curve."""
    try:
        from services.technical_analysis import analyze as _ta
        snap = _ta(base)
        price = snap.get("currentPrice")
        if price is None:
            return None
        return {
            "horizon":     "now",
            "horizonDays": 0,
            "targetPrice": float(price),
            "direction":   snap.get("direction", "WAIT"),
            "confidence":  float(snap.get("confidence", 0.0)),
            "source":      "native_ta_v1",
        }
    except Exception as e:
        logger.debug(f"[forecast-curve] ta anchor miss: {e}")
        return None


@router.get("/forecast-curve/{symbol}")
def get_forecast_curve(
    symbol: str = Path(..., description="Asset symbol"),
) -> Dict[str, Any]:
    """Forward price curve: TA anchor (t=0) + exchange short-horizon + fractal 1d–30d.

    Output is a sorted list of `points` consumable by MetaBrainChart's
    forecast overlay. Always returns 200; `degraded` is true if zero
    forecast points were collectable.
    """
    base = _canonicalize(symbol)
    points: List[Dict[str, Any]] = []

    anchor = _collect_ta_anchor(base)
    if anchor:
        points.append(anchor)

    ex_pt = _collect_exchange_forecast_point(base)
    if ex_pt:
        points.append(ex_pt)

    points.extend(_collect_fractal_forecast_curve(base))

    # Sort by horizonDays asc
    points.sort(key=lambda p: p.get("horizonDays") or 0)

    degraded = len(points) <= 1
    return {
        "symbol":   base,
        "points":   points,
        "count":    len(points),
        "sources":  sorted({p["source"] for p in points}),
        "degraded": degraded,
        "reason":   "only_ta_anchor_no_forecasts" if degraded else None,
        "asOf":     _now_iso(),
    }
