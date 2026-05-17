"""
Exchange / CEX — Real-data extras router
=========================================
Replaces the `legacy_compat_stub_empty` responses for the remaining
exchange endpoints consumed by the Web SPA cockpit, the operator
console and the alt-screener page.

This router is mounted **BEFORE** `legacy_compat` in server.py so any
collision is resolved in favour of real handlers.

Endpoints covered (15 stubs replaced):
  • Screener (AltScreenerPage):
      /api/exchange/screener/ml/predict
      /api/exchange/screener/candidates
      /api/exchange/screener/winners
      /api/exchange/screener/health
  • Segments (SegmentedForecastChart):
      /api/exchange/segments
      /api/exchange/segment-candles
  • Operator/Admin:
      /api/exchange/providers/health
      /api/exchange/proxy-config
      /api/exchange/test-connection         (POST + GET)
      /api/exchange/test-order              (POST + GET)
      /api/exchange/sync                    (POST + GET)
      /api/exchange/sync-fills              (POST + GET)
      /api/exchange/fills
  • Registry:
      /api/exchanges
      /api/exchanges/stats

All handlers either return real data from MongoDB / live venue feeds or
emit an honest `{ok: false|true, note: "..._not_configured_or_no_data"}`
shape — never `legacy_compat_stub_empty`, never fabricated metrics.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(tags=["exchange_extras_real"])


# ───────────────────────────────────── helpers ──────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _db():
    """In-process MongoDB handle (same one server.py / pred_exchange uses)."""
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "fomo_mobile")
    return MongoClient(mongo_url)[db_name]


def _venues_snapshot() -> Dict[str, Any]:
    """Reuse the proven /api/exchange/venues logic from exchange_runtime
    so providers/health and registry endpoints stay in sync."""
    try:
        from routes.exchange_runtime import exchange_health  # type: ignore
        return exchange_health()
    except Exception as e:
        return {"ok": False, "error": repr(e), "venues": [],
                "primary": None, "online": 0, "total": 0,
                "asOf": _now_iso()}


def _fetch_candles_real(symbol: str, interval: str = "1H",
                        limit: int = 200) -> List[Dict[str, Any]]:
    """Reuse OKX/CoinGecko fetcher (same source as /api/ta-engine/mtf)."""
    try:
        from routes.tech_analysis_runtime import (
            _fetch_candles, _to_binance_pair,
        )
        return _fetch_candles(_to_binance_pair(symbol), interval.upper(), limit) or []
    except Exception:
        return []


# ──────────────────────────── 1 · SCREENER (AltScreenerPage) ────────────────────
@router.get("/api/exchange/screener/health")
def screener_health():
    """Honest health probe.  Returns trained-model count from
    `screener_ml_models` collection (0 means UI shows
    `Tip: Run ML training job first`)."""
    try:
        db = _db()
        models_count = db.list_collection_names()
        models_count = db["screener_ml_models"].count_documents({}) \
            if "screener_ml_models" in models_count else 0
        winners_total = db["exchange_forecasts"].count_documents(
            {"outcome.label": "WIN"}
        ) if "exchange_forecasts" in db.list_collection_names() else 0
        return {
            "ok": True,
            "models": {"count": int(models_count),
                       "source": "screener_ml_models"},
            "winnerMemory": {"total": int(winners_total),
                             "source": "exchange_forecasts.outcome.label==WIN"},
            "asOf": _now_iso(),
            "source": "exchange_extras_real",
        }
    except Exception as e:
        return {"ok": False, "error": repr(e),
                "models": {"count": 0}, "winnerMemory": {"total": 0},
                "asOf": _now_iso()}


def _build_ml_predict_payload(horizon: str, limit: int) -> Dict[str, Any]:
    """No trained ML model exists yet → honest `NO_MODEL`.

    UI handles this case explicitly: `data?.ok === false && data?.error
    === 'NO_MODEL'` triggers the training-tip banner."""
    db = _db()
    has_model = ("screener_ml_models" in db.list_collection_names()
                 and db["screener_ml_models"].count_documents({}) > 0)

    if not has_model:
        return {
            "ok":    False,
            "error": "NO_MODEL",
            "message": "No screener_ml_models trained. "
                       "Train via POST /api/admin/exchange/screener/ml/train",
            "horizon": horizon,
            "predictions": [],
            "asOf": _now_iso(),
            "source": "exchange_extras_real",
        }

    # If a model exists, pull its last batch of predictions from Mongo.
    rows = list(db["screener_ml_predictions"].find(
        {"horizon": horizon}, {"_id": 0}
    ).sort("createdAt", -1).limit(limit))
    return {
        "ok":          True,
        "horizon":     horizon,
        "predictions": rows,
        "count":       len(rows),
        "asOf":        _now_iso(),
        "source":      "screener_ml_predictions",
    }


@router.get("/api/exchange/screener/ml/predict")
def screener_ml_predict(
    horizon: str = Query("4h"),
    limit: int = Query(30, ge=1, le=200),
):
    return _build_ml_predict_payload(horizon.lower(), limit)


@router.get("/api/exchange/screener/candidates")
def screener_candidates(
    horizon: str = Query("4h"),
    limit: int = Query(20, ge=1, le=100),
    fundingFilter: Optional[str] = Query(None),
):
    """Pattern-based candidates derived from the live OKX ticker universe
    + the real exchange_forecasts memory.  Returns up to `limit` symbols
    ranked by absolute confidence."""
    try:
        from routes.exchange_runtime import tickers as _ex_tickers  # type: ignore
        # tickers(limit, sort) → {ok, items:[{symbol, last, changePct24h, ...}]}
        tick = _ex_tickers(limit=max(30, limit * 3), sort="volume")
    except Exception as e:
        return {"ok": False, "error": repr(e), "candidates": [],
                "horizon": horizon, "asOf": _now_iso()}

    tickers_list = (tick or {}).get("items") or (tick or {}).get("tickers") or []
    # Map symbol → most recent forecast (real data) when available
    db = _db()
    fc_map: Dict[str, Dict[str, Any]] = {}
    if "exchange_forecasts" in db.list_collection_names():
        cursor = db["exchange_forecasts"].find(
            {"horizon": {"$regex": f"^{horizon}", "$options": "i"}},
            {"_id": 0, "asset": 1, "symbol": 1, "direction": 1,
             "confidence": 1, "expectedMovePct": 1, "targetPrice": 1,
             "entryPrice": 1, "createdAt": 1},
        ).sort("createdAt", -1).limit(500)
        for f in cursor:
            sym = (f.get("symbol") or f.get("asset") or "").upper()
            if sym and sym not in fc_map:
                fc_map[sym] = f

    out: List[Dict[str, Any]] = []
    for t in tickers_list:
        sym = (t.get("symbol") or "").upper()
        if not sym:
            continue
        f = fc_map.get(sym) or fc_map.get(sym.replace("USDT", "")) or fc_map.get(f"{sym}USDT")
        if not f:
            continue
        out.append({
            "symbol":       sym.replace("USDT", "") or sym,
            "lastPrice":    t.get("last") or t.get("lastPx"),
            "changePct24h": t.get("changePct24h") or t.get("changePct"),
            "volume24h":    t.get("volUsdt24h") or t.get("volume24h"),
            "direction":    f.get("direction"),
            "confidence":   f.get("confidence"),
            "expectedMovePct": f.get("expectedMovePct"),
            "targetPrice":  f.get("targetPrice"),
            "entryPrice":   f.get("entryPrice"),
            "forecastedAt": f.get("createdAt"),
            "source":       "exchange_forecasts+okx_tickers",
        })

    # Rank by |confidence|, take top N
    out.sort(key=lambda r: float(r.get("confidence") or 0.0), reverse=True)
    return {
        "ok":         True,
        "horizon":    horizon,
        "candidates": out[:limit],
        "count":      min(limit, len(out)),
        "universeSize": len(tickers_list),
        "forecastsConsidered": len(fc_map),
        "asOf":       _now_iso(),
        "source":     "exchange_extras_real",
    }


@router.get("/api/exchange/screener/winners")
def screener_winners(
    horizon: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(30, ge=1, le=200),
):
    """Historical winning forecasts from `exchange_forecasts`."""
    try:
        db = _db()
        if "exchange_forecasts" not in db.list_collection_names():
            return {"ok": True, "winners": [], "count": 0,
                    "note": "exchange_forecasts_collection_missing",
                    "asOf": _now_iso()}
        cutoff_ms = int((time.time() - days * 86400) * 1000)
        q: Dict[str, Any] = {
            "createdAt": {"$gte": cutoff_ms},
            "outcome.label": "WIN",
        }
        if horizon:
            q["horizon"] = {"$regex": f"^{horizon}", "$options": "i"}
        rows = list(db["exchange_forecasts"].find(
            q, {"_id": 0}
        ).sort("createdAt", -1).limit(limit))
        return {
            "ok":      True,
            "horizon": horizon,
            "days":    days,
            "winners": rows,
            "count":   len(rows),
            "asOf":    _now_iso(),
            "source":  "exchange_forecasts",
        }
    except Exception as e:
        return {"ok": False, "error": repr(e), "winners": [],
                "asOf": _now_iso()}


# ──────────────────────────── 2 · SEGMENTS (SegmentedForecastChart) ─────────────
@router.get("/api/exchange/segments")
def exchange_segments(
    asset: str = Query("BTC"),
    horizon: str = Query("30D"),
    limit: int = Query(50, ge=1, le=200),
):
    """Segmented forecast timeline backed by `exchange_forecasts`.

    Each row of `exchange_forecasts` becomes one segment:
      • status = ACTIVE      → most recent for (asset, horizon)
      • status = SUPERSEDED  → older entries not yet evaluated
      • status = RESOLVED    → entries with `outcome` set
    """
    asset_u = asset.upper().replace("USDT", "")
    horizon_u = horizon.upper()
    try:
        db = _db()
        if "exchange_forecasts" not in db.list_collection_names():
            return {"ok": True, "data": {"items": []},
                    "asset": asset_u, "horizon": horizon_u,
                    "note": "exchange_forecasts_collection_missing",
                    "asOf": _now_iso()}

        docs = list(db["exchange_forecasts"].find(
            {"asset": asset_u, "horizon": horizon_u},
            {"_id": 0},
        ).sort("createdAt", -1).limit(limit))

        items: List[Dict[str, Any]] = []
        for idx, d in enumerate(docs):
            has_outcome = bool(d.get("outcome"))
            if has_outcome:
                status = "RESOLVED"
            else:
                status = "ACTIVE" if idx == 0 else "SUPERSEDED"
            items.append({
                "segmentId":    d.get("id") or str(uuid.uuid4()),
                "status":       status,
                "asset":        d.get("asset", asset_u),
                "symbol":       d.get("symbol", f"{asset_u}USDT"),
                "horizon":      d.get("horizon", horizon_u),
                "horizonDays":  d.get("horizonDays"),
                "createdAt":    d.get("createdAt"),
                "evaluateAfter": d.get("evaluateAfter"),
                "entryPrice":   d.get("entryPrice"),
                "targetPrice":  d.get("targetPrice"),
                "direction":    d.get("direction"),
                "confidence":   d.get("confidence"),
                "expectedMovePct": d.get("expectedMovePct"),
                "bandCoreLow":  d.get("bandCoreLow"),
                "bandCoreHigh": d.get("bandCoreHigh"),
                "bandWideLow":  d.get("bandWideLow"),
                "bandWideHigh": d.get("bandWideHigh"),
                "outcome":      d.get("outcome"),
                "runId":        d.get("runId"),
            })

        return {
            "ok":      True,
            "asset":   asset_u,
            "horizon": horizon_u,
            "data": {
                "items":      items,
                "totalCount": len(items),
            },
            "asOf":    _now_iso(),
            "source":  "exchange_forecasts",
        }
    except Exception as e:
        return {"ok": False, "error": repr(e),
                "data": {"items": []},
                "asset": asset_u, "horizon": horizon_u,
                "asOf": _now_iso()}


@router.get("/api/exchange/segment-candles")
def exchange_segment_candles(
    segmentId: str = Query(..., description="exchange_forecasts.id"),
):
    """Real OKX candles covering the segment's lifetime (createdAt →
    evaluateAfter, or last 200 candles if still active)."""
    try:
        db = _db()
        if "exchange_forecasts" not in db.list_collection_names():
            return {"ok": False, "error": "exchange_forecasts_missing",
                    "data": {"candles": []}, "asOf": _now_iso()}
        seg = db["exchange_forecasts"].find_one(
            {"id": segmentId}, {"_id": 0}
        )
        if not seg:
            return {"ok": False, "error": "segment_not_found",
                    "segmentId": segmentId, "data": {"candles": []},
                    "asOf": _now_iso()}

        asset = (seg.get("asset") or "BTC").upper()
        horizon_days = int(seg.get("horizonDays") or 7)

        # Pick interval based on horizon: ≤2D→1H, ≤14D→4H, else→1D
        if horizon_days <= 2:
            interval, span = "1H", 48
        elif horizon_days <= 14:
            interval, span = "4H", max(60, horizon_days * 6)
        else:
            interval, span = "1D", max(60, horizon_days + 30)

        bars = _fetch_candles_real(asset, interval, span)
        candles: List[Dict[str, Any]] = []
        created_ts = seg.get("createdAt") or 0
        eval_ts = seg.get("evaluateAfter") or (created_ts + horizon_days * 86400 * 1000)
        for b in bars:
            ts_ms = b.get("openTime") or (b.get("time", 0) * 1000)
            try:
                ts_ms = int(ts_ms)
            except Exception:
                continue
            # Window: ±20% padding around the segment
            pad = int((eval_ts - created_ts) * 0.2) if eval_ts > created_ts else 0
            if ts_ms < created_ts - pad or ts_ms > eval_ts + pad:
                continue
            candles.append({
                "time":  ts_ms // 1000,  # lightweight-charts second-precision
                "open":  b.get("open"),
                "high":  b.get("high"),
                "low":   b.get("low"),
                "close": b.get("close"),
            })

        return {
            "ok":   True,
            "segmentId": segmentId,
            "data": {
                "candles":  candles,
                "interval": interval,
                "windowFrom": created_ts,
                "windowTo":   eval_ts,
            },
            "asOf":   _now_iso(),
            "source": "okx_candles + exchange_forecasts",
        }
    except Exception as e:
        return {"ok": False, "error": repr(e),
                "data": {"candles": []}, "segmentId": segmentId,
                "asOf": _now_iso()}


# ──────────────────────────── 3 · OPERATOR / ADMIN ──────────────────────────────
@router.get("/api/exchange/providers/health")
def exchange_providers_health():
    """Real provider health from the live OKX/Binance/Bybit ping data."""
    v = _venues_snapshot()
    venues = v.get("venues") or []
    providers = []
    for ven in venues:
        providers.append({
            "name":      ven.get("venue"),
            "status":    ven.get("status"),
            "latencyMs": ven.get("latencyMs"),
            "note":      ven.get("note"),
            "healthy":   ven.get("status") == "online",
        })
    online = sum(1 for p in providers if p["healthy"])
    return {
        "ok":        True,
        "providers": providers,
        "primary":   v.get("primary"),
        "online":    online,
        "total":     len(providers),
        "asOf":      _now_iso(),
        "source":    "exchange_runtime.venues",
    }


@router.get("/api/exchange/proxy-config")
def exchange_proxy_config():
    """Return the proxy configuration **without** exposing secrets."""
    http_proxy = os.environ.get("EXCHANGE_HTTP_PROXY") or os.environ.get("HTTP_PROXY")
    https_proxy = os.environ.get("EXCHANGE_HTTPS_PROXY") or os.environ.get("HTTPS_PROXY")
    socks_proxy = os.environ.get("EXCHANGE_SOCKS_PROXY")

    def _mask(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        # mask credentials in user:pass@host
        try:
            from urllib.parse import urlparse
            p = urlparse(url)
            if p.username or p.password:
                host = p.hostname or ""
                port = f":{p.port}" if p.port else ""
                return f"{p.scheme}://***@{host}{port}"
            return url
        except Exception:
            return "configured"

    return {
        "ok": True,
        "proxy": {
            "http":  _mask(http_proxy),
            "https": _mask(https_proxy),
            "socks": _mask(socks_proxy),
            "enabled": bool(http_proxy or https_proxy or socks_proxy),
        },
        "venues": (_venues_snapshot().get("venues") or []),
        "asOf":   _now_iso(),
        "source": "env_vars",
    }


def _test_connection_payload() -> Dict[str, Any]:
    """Live ping to each venue (reuses /venues which already does ping)."""
    v = _venues_snapshot()
    venues = v.get("venues") or []
    return {
        "ok":         True,
        "results":    venues,
        "summary": {
            "tested":  len(venues),
            "online":  sum(1 for ve in venues if ve.get("status") == "online"),
            "blocked": sum(1 for ve in venues if ve.get("status") == "blocked"),
        },
        "primary":    v.get("primary"),
        "asOf":       _now_iso(),
        "source":     "exchange_runtime.venues_live_ping",
    }


@router.get("/api/exchange/test-connection")
def exchange_test_connection_get():
    return _test_connection_payload()


@router.post("/api/exchange/test-connection")
def exchange_test_connection_post():
    return _test_connection_payload()


def _test_order_payload(symbol: str = "BTC",
                        side: str = "buy",
                        qty: float = 0.001) -> Dict[str, Any]:
    """Paper-mode dry-run: validates against current price + venue
    availability.  No real order is submitted."""
    v = _venues_snapshot()
    online_venue = next((ve for ve in (v.get("venues") or [])
                         if ve.get("status") == "online"), None)
    bars = _fetch_candles_real(symbol, "1H", 1)
    last_price = (bars[-1].get("close") if bars else None)
    can_submit = bool(online_venue and last_price)
    return {
        "ok":         True,
        "mode":       "paper",
        "submitted":  False,  # this is a dry-run
        "wouldRoute": online_venue.get("venue") if online_venue else None,
        "symbol":     symbol.upper(),
        "side":       side.lower(),
        "qty":        qty,
        "lastPrice":  last_price,
        "estCost":    (last_price * qty) if last_price else None,
        "venueStatus": online_venue.get("status") if online_venue else "none_online",
        "canSubmit":  can_submit,
        "reason":     None if can_submit else "no_online_venue_or_price",
        "asOf":       _now_iso(),
        "source":     "exchange_extras_real.paper_dry_run",
    }


@router.get("/api/exchange/test-order")
def exchange_test_order_get(symbol: str = Query("BTC"),
                            side: str = Query("buy"),
                            qty: float = Query(0.001)):
    return _test_order_payload(symbol, side, qty)


@router.post("/api/exchange/test-order")
def exchange_test_order_post():
    return _test_order_payload()


def _sync_status() -> Dict[str, Any]:
    """Return real last-sync info from exchange_forecast_runs (closest
    proxy for back-end sync activity)."""
    try:
        db = _db()
        last_run = None
        if "exchange_forecast_runs" in db.list_collection_names():
            last_run = db["exchange_forecast_runs"].find_one(
                {}, {"_id": 0}, sort=[("ts", -1)],
            )
        orders_total = 0
        if "paper_orders_v2" in db.list_collection_names():
            orders_total = db["paper_orders_v2"].count_documents({})
        return {
            "ok":         True,
            "lastRun":    last_run,
            "ordersTotal": orders_total,
            "asOf":       _now_iso(),
            "source":     "exchange_forecast_runs + paper_orders_v2",
        }
    except Exception as e:
        return {"ok": False, "error": repr(e), "asOf": _now_iso()}


@router.get("/api/exchange/sync")
def exchange_sync_get():
    return _sync_status()


@router.post("/api/exchange/sync")
def exchange_sync_post():
    return _sync_status()


@router.get("/api/exchange/sync-fills")
def exchange_sync_fills_get():
    return _sync_status()


@router.post("/api/exchange/sync-fills")
def exchange_sync_fills_post():
    return _sync_status()


@router.get("/api/exchange/fills")
def exchange_fills(limit: int = Query(50, ge=1, le=500)):
    """Real fills from the paper-trading collection."""
    try:
        db = _db()
        if "paper_orders_v2" not in db.list_collection_names():
            return {"ok": True, "fills": [], "count": 0,
                    "note": "no_paper_orders_yet",
                    "asOf": _now_iso(),
                    "source": "paper_orders_v2"}
        rows = list(db["paper_orders_v2"].find(
            {"status": "FILLED"}, {"_id": 0},
        ).sort("filledAt", -1).limit(limit))
        return {"ok": True, "fills": rows, "count": len(rows),
                "asOf": _now_iso(), "source": "paper_orders_v2"}
    except Exception as e:
        return {"ok": False, "error": repr(e), "fills": [],
                "asOf": _now_iso()}


# ──────────────────────────── 4 · REGISTRY ──────────────────────────────────────
@router.get("/api/exchanges")
def exchanges_list():
    """Plural-form registry — alias of /api/exchange/venues."""
    v = _venues_snapshot()
    venues = v.get("venues") or []
    return {
        "ok":      True,
        "items":   [{
            "id":         ve.get("venue"),
            "name":       (ve.get("venue") or "").upper(),
            "status":     ve.get("status"),
            "latencyMs":  ve.get("latencyMs"),
            "note":       ve.get("note"),
            "primary":    ve.get("venue") == v.get("primary"),
        } for ve in venues],
        "count":   len(venues),
        "primary": v.get("primary"),
        "online":  v.get("online"),
        "total":   v.get("total"),
        "asOf":    _now_iso(),
        "source":  "exchange_runtime.venues",
    }


@router.get("/api/exchanges/stats")
def exchanges_stats():
    """Per-venue real stats from MongoDB collections."""
    v = _venues_snapshot()
    venues = v.get("venues") or []
    try:
        db = _db()
        fc_total = db["exchange_forecasts"].count_documents({}) \
            if "exchange_forecasts" in db.list_collection_names() else 0
        runs_total = db["exchange_forecast_runs"].count_documents({}) \
            if "exchange_forecast_runs" in db.list_collection_names() else 0
        paper_total = db["paper_orders_v2"].count_documents({}) \
            if "paper_orders_v2" in db.list_collection_names() else 0
    except Exception:
        fc_total = runs_total = paper_total = 0

    return {
        "ok":      True,
        "stats": {
            "venuesTotal":         len(venues),
            "venuesOnline":        sum(1 for ve in venues if ve.get("status") == "online"),
            "venuesBlocked":       sum(1 for ve in venues if ve.get("status") == "blocked"),
            "forecastsStored":     fc_total,
            "forecastRunsLogged":  runs_total,
            "paperOrdersStored":   paper_total,
            "primary":             v.get("primary"),
        },
        "asOf":    _now_iso(),
        "source":  "exchange_runtime.venues + mongo",
    }
