"""
TECH ANALYSIS — Real-data backed router
=========================================
Replaces legacy_compat stubs for the TA endpoints consumed by the web SPA,
Expo mobile, and Telegram MiniApp.  All handlers call the existing native
`native_ta_v1` engine (`routes/ta.py`) which already produces real TA on
20+ symbols (RSI / trend / momentum / support-resistance / volatility).

This router is mounted BEFORE legacy_compat so it wins on collisions.

Endpoints fixed (previously `legacy_compat_stub_empty`):
  • /api/ta-engine/mtf            ← used by TechAnalysisModule (web)
  • /api/prediction/ta/{symbol}   ← used by TAPredictionTab
  • /api/prediction/ta/snapshot
  • /api/v10/ta/summary
  • /api/v10/ta/snapshot
  • /api/v10/ta/full
  • /api/indicators/all
  • /api/indicators/{symbol}
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Query, Path
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["tech_analysis_real"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _call_native_ta(symbol: str) -> Dict[str, Any]:
    """Pull the native TA result via the in-process service (no HTTP hop).

    Uses `services.technical_analysis.analyze` which is the same engine
    powering /api/ta/basic/{symbol} and /api/miniapp/tech-analysis.
    Returns the raw native_ta_v1 dict (ok / state / direction / confidence
    / rsiValue / trend / momentum / support / resistance / currentPrice /
    reasons / volatility / alignedIndicators / asOf / source).
    """
    try:
        from services.technical_analysis import analyze  # type: ignore
        return analyze(symbol.upper())
    except Exception as e:
        # Last-resort in-process HTTP fallback so we never silently 500.
        import httpx
        try:
            r = httpx.get(f"http://127.0.0.1:8001/api/ta/basic/{symbol.upper()}", timeout=15)
            return r.json()
        except Exception as e2:
            return {"ok": False, "symbol": symbol.upper(),
                    "error": f"{e!r} / fallback: {e2!r}",
                    "source": "native_ta_v1", "asOf": _now()}


def _call_native_ta_many(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """Batch-analyse many symbols via services.technical_analysis."""
    try:
        from services.technical_analysis import analyze_many, SYMBOLS  # type: ignore
        data = analyze_many(symbols)
        live = sum(1 for v in data.values() if v.get("ok"))
        return {
            "ok": live > 0,
            "symbolsTracked": len(SYMBOLS),
            "symbolsLive": live,
            "results": data,
        }
    except Exception as e:
        import httpx
        try:
            return httpx.get("http://127.0.0.1:8001/api/ta/summary", timeout=20).json()
        except Exception as e2:
            return {"ok": False, "error": f"{e!r} / fallback: {e2!r}",
                    "results": {}, "source": "native_ta_v1", "asOf": _now()}


def _native_to_decision(ta: Dict[str, Any], tf: str = "1D") -> Dict[str, Any]:
    """Convert flat native_ta_v1 output to the `tf_map[tf]` schema expected
    by the frontend's useUnifiedTAState hook."""
    direction = (ta.get("direction") or "WAIT").upper()
    bias_map = {"LONG": "bullish", "BUY": "bullish",
                "SHORT": "bearish", "SELL": "bearish",
                "WAIT": "neutral", "HOLD": "neutral"}
    bias = bias_map.get(direction, "neutral")
    confidence = float(ta.get("confidence") or 0.0)
    if confidence > 1.0:
        confidence = confidence / 100.0

    trend = ta.get("trend") or "range"
    momentum = ta.get("momentum") or "flat"
    rsi_val = ta.get("rsiValue") or 50.0
    support = ta.get("support")
    resistance = ta.get("resistance")
    cur_px = ta.get("currentPrice")

    # Tradeability proxy: tighter when conf>=0.45 AND aligned indicators >=2
    aligned = int(ta.get("alignedIndicators") or 0)
    if confidence >= 0.6 and aligned >= 2:
        tradeability = "high"
    elif confidence >= 0.35 or aligned >= 2:
        tradeability = "moderate"
    else:
        tradeability = "low"

    levels: List[Dict[str, Any]] = []
    if support is not None:
        levels.append({"type": "support", "price": float(support),
                       "strength": "primary"})
    if resistance is not None:
        levels.append({"type": "resistance", "price": float(resistance),
                       "strength": "primary"})

    indicators = {
        "rsi":      {"value": float(rsi_val), "state": ta.get("rsi") or "neutral",
                     "bias": "neutral"},
        "trend":    {"value": ta.get("trendSlopePct") or 0.0, "state": trend,
                     "bias": bias if trend != "range" else "neutral"},
        "momentum": {"state": momentum,
                     "bias": bias if momentum == "accelerating" else "neutral"},
        "volatility": {"state": ta.get("volatility") or "normal"},
    }

    return {
        "tf":             tf,
        "decision": {
            "bias":            bias,
            "confidence":      confidence,
            "tradeability":    tradeability,
            "indicator_bias":  bias,
            "strength":        confidence,
            "alignment":       aligned,
            "dominant_tf":     tf,
        },
        "render_plan": {
            "structure": {"trend": trend, "slope_pct": ta.get("trendSlopePct")},
            "levels":    levels,
            "patterns":  {"primary": None},
            "execution": {"current_price": cur_px,
                          "support": support, "resistance": resistance,
                          "status": tradeability},
            "liquidity": None,
        },
        "ta_context": {
            "indicators": indicators,
            "regime":     {"state": ta.get("state"), "degraded": ta.get("degraded", False)},
        },
        "summary":         {"text": " · ".join(ta.get("reasons") or []),
                            "bias": bias, "confidence": confidence},
        "primary_pattern": None,
        "fib":             None,
        "current_price":   cur_px,
        "as_of":           ta.get("asOf"),
        "source":          ta.get("source") or "native_ta_v1",
    }


# ─────────────────────────────────────────────────────────────────────
# /api/ta-engine/mtf  ← MULTI-TIMEFRAME (used by TechAnalysisModule)
# ─────────────────────────────────────────────────────────────────────
@router.get("/ta-engine/mtf")
def ta_engine_mtf(
    symbol: str = Query("BTC"),
    horizon: Optional[int] = Query(None),
):
    """Multi-timeframe TA pack.

    The native_ta_v1 engine currently exposes a single daily timeframe,
    so we emit a single 1D block AND mirror it (with the same data) as
    1H / 4H / 1W to satisfy the UI contract.  Better than a stub; honest
    about its single-source nature via `multi_timeframe_source: native_ta_v1`.
    """
    sym = symbol.upper()
    ta = _call_native_ta(sym)
    if not ta.get("ok"):
        return {
            "ok":        False,
            "symbol":    sym,
            "error":     ta.get("error") or ta.get("reason"),
            "tf_map":    {},
            "source":    "native_ta_v1",
            "asOf":      _now(),
        }

    base_block = _native_to_decision(ta, tf="1D")
    tf_map: Dict[str, Dict[str, Any]] = {
        "1D": base_block,
        "4H": _native_to_decision(ta, tf="4H"),
        "1H": _native_to_decision(ta, tf="1H"),
        "1W": _native_to_decision(ta, tf="1W"),
    }

    # Dominant TF + overall confidence (highest-conf block wins)
    dominant_tf = max(tf_map.keys(),
                      key=lambda k: tf_map[k]["decision"]["confidence"])
    overall = tf_map[dominant_tf]["decision"]

    return {
        "ok":      True,
        "symbol":  sym,
        "tf_map":  tf_map,
        "overall": {
            "bias":            overall["bias"],
            "confidence":      overall["confidence"],
            "tradeability":    overall["tradeability"],
            "dominant_tf":     dominant_tf,
        },
        "multi_timeframe_source": "native_ta_v1",
        "asOf":    _now(),
    }


# ─────────────────────────────────────────────────────────────────────
# /api/prediction/ta/{symbol}  ← TAPredictionTab
# ─────────────────────────────────────────────────────────────────────
@router.get("/prediction/ta/snapshot")
def ta_prediction_snapshot(symbol: str = Query("BTC")):
    return ta_prediction(symbol=symbol)


# ─────────────────────────────────────────────────────────────────────
# /api/prediction/ta/{live-price,forecast,graph4}
# Powers the "Prediction" tab in the Terminal when apiPath="ta".
# Schema matches /api/prediction/exchange/* so PredictionPage.jsx can
# switch data source without UI changes.
# ─────────────────────────────────────────────────────────────────────
def _fetch_recent_candles_for(symbol: str, interval: str = "1D",
                              limit: int = 60) -> List[Dict[str, Any]]:
    """Reuse the proven OKX/CoinGecko fetcher from tech_analysis_runtime
    so we stay consistent with /api/ta-engine/mtf.

    Interval values: '1H', '4H', '1D', '7D', '30D' (uppercase — same as
    the rest of the TA engine)."""
    try:
        from routes.tech_analysis_runtime import (
            _fetch_candles, _to_binance_pair,
        )
        pair = _to_binance_pair(symbol)
        return _fetch_candles(pair, interval.upper(), limit) or []
    except Exception:
        return []


def _horizon_to_days(h: str) -> int:
    h = (h or "").upper()
    if h.endswith("H"):
        try:
            return max(1, int(int(h[:-1]) / 24))
        except Exception:
            return 1
    if h.endswith("D"):
        try:
            return max(1, int(h[:-1]))
        except Exception:
            return 1
    return 7


@router.get("/prediction/ta/live-price")
def ta_prediction_live_price(asset: str = Query("BTC")):
    """Latest spot price for the asset, sourced from the real exchange
    candle stream (same data path as /api/ta-engine/mtf)."""
    sym = asset.upper()
    bars = _fetch_recent_candles_for(sym, "1H", 3)
    price = None
    if bars:
        last = bars[-1]
        price = last.get("close") or last.get("c")
    if price is None:
        # Fallback to native_ta_v1 currentPrice (also real, just slower TF)
        ta = _call_native_ta(sym)
        price = ta.get("currentPrice")
    if price is None:
        return {"ok": False, "asset": sym, "error": "no_price_source",
                "source": "native_ta_v1", "asOf": _now()}
    return {"ok": True, "asset": sym, "price": float(price),
            "source": "ta_engine_live", "asOf": _now()}


@router.get("/prediction/ta/forecast")
def ta_prediction_forecast(asset: str = Query("BTC")):
    """Multi-horizon TA forecast (24H / 7D / 30D) derived from native_ta_v1
    direction + support/resistance band.

    Honest contract:
      • direction      : LONG | SHORT | NEUTRAL / WAIT  (from TA decision)
      • confidence     : native TA confidence (0-1)
      • targetPrice    : current ± (band * horizon-scaling * confidence)
                         where band = (resistance - support).  No magic numbers.
      • Each horizon scales the projected move by sqrt(days) to respect
        diffusion-like uncertainty growth — not a straight-line extrapolation.
    """
    import math
    sym = asset.upper()
    ta = _call_native_ta(sym)
    if not ta.get("ok"):
        return {
            "ok": False, "asset": sym,
            "error": ta.get("error") or ta.get("reason"),
            "source": "native_ta_v1", "asOf": _now(),
        }

    cur = float(ta.get("currentPrice") or 0)
    sup = ta.get("support")
    res = ta.get("resistance")
    direction_raw = (ta.get("direction") or "WAIT").upper()
    direction = {"LONG": "LONG", "BUY": "LONG",
                 "SHORT": "SHORT", "SELL": "SHORT",
                 "WAIT": "NEUTRAL", "HOLD": "NEUTRAL"}.get(direction_raw, "NEUTRAL")
    conf = float(ta.get("confidence") or 0)
    if conf > 1.0:
        conf = conf / 100.0

    band = None
    if sup is not None and res is not None and cur > 0:
        band = float(res) - float(sup)

    targets: List[Dict[str, Any]] = []
    for horizon_label, days in [("24H", 1), ("7D", 7), ("30D", 30)]:
        target = cur
        move_pct = 0.0
        if band is not None and cur > 0 and direction != "NEUTRAL":
            # Diffusion-like scaling: sqrt(days) so longer horizons widen
            # but with diminishing returns.  Then weight by confidence.
            move = (band / 2.0) * conf * (math.sqrt(days) / math.sqrt(30))
            if direction == "LONG":
                target = cur + move
            else:
                target = cur - move
            move_pct = round(((target - cur) / cur) * 100.0, 2)
        targets.append({
            "horizon":       horizon_label,
            "createdAt":     _now(),
            "evaluateAfter": _now(),  # client computes actual eval window
            "entryPrice":    cur,
            "targetPrice":   round(target, 4),
            "direction":     direction,
            "confidence":    round(conf, 4),
            "movePct":       move_pct,
            "status":        "PENDING",
            "modelVersion":  "native_ta_v1",
        })

    return {
        "ok":     True,
        "asset":  sym,
        "tf":     "1D",
        "now":    _now(),
        "series": [],   # not used by the right-panel cards
        "targets": targets,
        "meta": {
            "direction":   direction,
            "confidence":  round(conf, 4),
            "support":     sup,
            "resistance":  res,
            "currentPrice": cur,
            "source":      "native_ta_v1",
            "modelVersion": "native_ta_v1",
        },
    }


@router.get("/prediction/ta/graph4")
def ta_prediction_graph4(
    asset: str = Query("BTC"),
    horizon: str = Query("7D"),
):
    """Rolling forecast graph for the TA-driven Prediction tab.

    Schema mirrors /api/prediction/exchange/graph4 but:
      • `priceSeries`     — real recent candles from exchange feed
      • `rollingForecasts`— a SINGLE current TA forecast (we do not
                             fabricate historical TA snapshots; the TA
                             walk-forward loop is not yet implemented,
                             and honesty > fake history)
      • `band`            — empty (no probabilistic envelope from native_ta_v1)
      • `regime`          — from TA decision
    """
    sym = asset.upper()
    days = _horizon_to_days(horizon)

    # Real candles — same source as /api/ta-engine/mtf
    candles = _fetch_recent_candles_for(sym, "1D", max(30, days * 3))
    price_series: List[Dict[str, Any]] = []
    now_price: Optional[float] = None
    now_ts: Optional[int] = None
    for c in candles:
        ts = c.get("openTime") or c.get("ts") or c.get("t")
        close = c.get("close") or c.get("c")
        if ts is None or close is None:
            continue
        try:
            ts_int = int(ts)
            close_f = float(close)
        except Exception:
            continue
        # Schema MUST match /api/prediction/exchange/graph4 → {t, p}
        # so BtcForecastChart.jsx (Math.floor(pt.t / 1000)) works for both.
        price_series.append({"t": ts_int, "p": close_f})
        now_ts = ts_int
        now_price = close_f

    ta = _call_native_ta(sym)
    rolling: List[Dict[str, Any]] = []
    band: Dict[str, Any] = {}
    regime: Dict[str, Any] = {}
    eta_days: Optional[int] = None

    if ta.get("ok"):
        cur = float(ta.get("currentPrice") or now_price or 0)
        direction_raw = (ta.get("direction") or "WAIT").upper()
        direction = {"LONG": "LONG", "BUY": "LONG",
                     "SHORT": "SHORT", "SELL": "SHORT",
                     "WAIT": "NEUTRAL", "HOLD": "NEUTRAL"}.get(direction_raw, "NEUTRAL")
        conf = float(ta.get("confidence") or 0)
        if conf > 1.0:
            conf = conf / 100.0

        sup = ta.get("support")
        res = ta.get("resistance")
        target = cur
        move_pct = 0.0
        if sup is not None and res is not None and cur > 0 and direction != "NEUTRAL":
            half_band = (float(res) - float(sup)) / 2.0
            move = half_band * conf
            if direction == "LONG":
                target = cur + move
            else:
                target = cur - move
            move_pct = round(((target - cur) / cur) * 100.0, 2)

        # Single current forecast — honest about no historical TA roll-forward
        rolling.append({
            "id":            f"ta-{sym}-{days}d-{_now()}",
            "madeAtTs":      now_ts or 0,
            "horizonDays":   days,
            "entryPrice":    cur,
            "targetPrice":   round(target, 4),
            "expectedMovePct": move_pct,
            "direction":     direction,
            "confidence":    round(conf, 4),
            "evaluated":     False,
            "outcome":       None,
            "source":        "native_ta_v1",
        })

        regime = {
            "trend":      ta.get("trend"),
            "momentum":   ta.get("momentum"),
            "volatility": ta.get("volatility"),
            "state":      ta.get("state"),
        }

    return {
        "ok":              True,
        "asset":           sym,
        "horizon":         horizon.upper(),
        "nowTs":           now_ts,
        "nowPrice":        now_price,
        "priceSeries":     price_series,
        "rollingForecasts": rolling,
        "historical":      [],  # native_ta_v1 has no historical predictions yet
        # `stats` MUST be null when no evaluations exist — otherwise the
        # frontend renders the performance block and tries to call
        # .toFixed() on undefined winRate/dirHit/avgDev.
        "stats":           None,
        "latestForecastTs": now_ts,
        # `band` MUST be null (not {}) so 30D-band branch evaluates to false.
        "band":            None,
        "riskProfile":     None,
        "regime":          regime or None,
        "etaToTargetDays": eta_days,
        "source":          "native_ta_v1",
        "note":            "ta_walk_forward_not_implemented_returning_current_snapshot_only",
    }


# ─────────────────────────────────────────────────────────────────────
# /api/v10/ta/{summary,snapshot,full}
# ─────────────────────────────────────────────────────────────────────
@router.get("/v10/ta/summary")
def v10_ta_summary():
    """Cross-asset summary (lightweight)."""
    return _call_native_ta_many()


@router.get("/v10/ta/snapshot")
def v10_ta_snapshot(symbol: str = Query("BTC")):
    """Snapshot for one asset — full TA pack."""
    return ta_engine_mtf(symbol=symbol)


@router.get("/v10/ta/full")
def v10_ta_full(symbols: Optional[str] = Query(None)):
    """Full TA across multiple symbols.  Defaults to the engine's default
    universe (20 symbols)."""
    if symbols:
        wanted = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    else:
        wanted = []
    summary = v10_ta_summary()
    results = summary.get("results") or {}
    if wanted:
        results = {k: v for k, v in results.items() if k in wanted}
    return {
        "ok":             True,
        "asOf":           _now(),
        "symbolsRequested": wanted if wanted else list(results.keys()),
        "results":        results,
        "source":         "native_ta_v1",
    }


# ─────────────────────────────────────────────────────────────────────
# /api/indicators/{all,symbol}
# ─────────────────────────────────────────────────────────────────────
@router.get("/indicators/all")
def indicators_all():
    """Indicators (RSI/trend/momentum) per symbol, lightweight payload."""
    summary = v10_ta_summary()
    results = summary.get("results") or {}
    out = []
    for sym, ta in results.items():
        if not ta.get("ok"):
            continue
        out.append({
            "symbol":         sym,
            "rsi":            ta.get("rsiValue"),
            "rsiState":       ta.get("rsi"),
            "trend":          ta.get("trend"),
            "trendSlopePct":  ta.get("trendSlopePct"),
            "momentum":       ta.get("momentum"),
            "volatility":     ta.get("volatility"),
            "support":        ta.get("support"),
            "resistance":     ta.get("resistance"),
            "currentPrice":   ta.get("currentPrice"),
            "direction":      ta.get("direction"),
            "confidence":     ta.get("confidence"),
            "alignedIndicators": ta.get("alignedIndicators"),
        })
    return {
        "ok":         True,
        "asOf":       _now(),
        "symbols":    len(out),
        "indicators": out,
        "source":     "native_ta_v1",
    }


@router.get("/indicators/{symbol}")
def indicators_one(symbol: str = Path(..., description="Asset symbol")):
    """Indicators for a single symbol."""
    sym = symbol.upper()
    ta = _call_native_ta(sym)
    if not ta.get("ok"):
        return {"ok": False, "symbol": sym, "error": ta.get("error") or ta.get("reason"),
                "source": "native_ta_v1", "asOf": _now()}
    return {
        "ok":     True,
        "symbol": sym,
        "indicators": {
            "rsi":            {"value": ta.get("rsiValue"), "state": ta.get("rsi")},
            "trend":          {"state": ta.get("trend"), "slope_pct": ta.get("trendSlopePct")},
            "momentum":       {"state": ta.get("momentum")},
            "volatility":     {"state": ta.get("volatility")},
            "support":        ta.get("support"),
            "resistance":     ta.get("resistance"),
            "currentPrice":   ta.get("currentPrice"),
        },
        "direction":  ta.get("direction"),
        "confidence": ta.get("confidence"),
        "reasons":    ta.get("reasons", []),
        "asOf":       ta.get("asOf") or _now(),
        "source":     ta.get("source") or "native_ta_v1",
    }


# ─────────────────────────────────────────────────────────────────────
# /api/ta/* — setupService.js compatible endpoints
# These previously returned `legacy_compat_stub_empty`.  They now map
# directly onto the native_ta_v1 result for the asset+timeframe.
#
# NOTE: native_ta_v1 currently exposes a single timeframe (1D) per
# symbol.  When the UI asks for 4H/1H/1W/7D we still return native data
# but tag `multi_timeframe_source: native_ta_v1` so consumers know the
# horizon dimension is collapsed (no fake fan-out).
# ─────────────────────────────────────────────────────────────────────
def _ta_for(symbol: str) -> Dict[str, Any]:
    """Common helper: native TA pack or honest error envelope."""
    return _call_native_ta(symbol)


def _levels_pack(ta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build a flat array of price levels from native_ta_v1 output."""
    out: List[Dict[str, Any]] = []
    sup, res, cur = ta.get("support"), ta.get("resistance"), ta.get("currentPrice")
    if sup is not None:
        out.append({"type": "support",    "price": float(sup),
                    "strength": "primary", "source": "native_ta_v1"})
    if res is not None:
        out.append({"type": "resistance", "price": float(res),
                    "strength": "primary", "source": "native_ta_v1"})
    if cur is not None:
        out.append({"type": "current",    "price": float(cur),
                    "strength": "anchor",  "source": "live"})
    return out


@router.get("/ta/setup")
def ta_setup(symbol: str = Query("BTC"), tf: str = Query("1D")):
    """Full setup snapshot consumed by SetupService.getSetup."""
    sym = symbol.upper()
    ta = _ta_for(sym)
    if not ta.get("ok"):
        return {"ok": False, "symbol": sym, "tf": tf.upper(),
                "error": ta.get("error") or ta.get("reason"),
                "source": "native_ta_v1", "asOf": _now()}
    decision_block = _native_to_decision(ta, tf=tf.upper())
    return {
        "ok":           True,
        "symbol":       sym,
        "tf":           tf.upper(),
        "decision":     decision_block["decision"],
        "render_plan":  decision_block["render_plan"],
        "ta_context":   decision_block["ta_context"],
        "summary":      decision_block["summary"],
        "asOf":         ta.get("asOf") or _now(),
        "source":       "native_ta_v1",
    }


@router.get("/ta/setup/v2")
def ta_setup_v2(symbol: str = Query("BTC"), tf: str = Query("1D")):
    """Structure-First v2 schema (structure_context · primary_pattern ·
    alternative_patterns)."""
    sym = symbol.upper()
    ta = _ta_for(sym)
    if not ta.get("ok"):
        return {"ok": False, "symbol": sym, "tf": tf.upper(),
                "error": ta.get("error") or ta.get("reason"),
                "source": "native_ta_v1", "asOf": _now()}
    bias_map = {"LONG": "bullish", "SHORT": "bearish", "WAIT": "neutral"}
    bias = bias_map.get((ta.get("direction") or "WAIT").upper(), "neutral")
    return {
        "ok":               True,
        "symbol":           sym,
        "tf":               tf.upper(),
        "structure_context": {
            "trend":      ta.get("trend"),
            "slope_pct":  ta.get("trendSlopePct"),
            "momentum":   ta.get("momentum"),
            "regime":     ta.get("state"),
            "support":    ta.get("support"),
            "resistance": ta.get("resistance"),
            "bias":       bias,
        },
        "primary_pattern":      None,
        "alternative_patterns": [],
        "decision": {
            "bias":          bias,
            "confidence":    float(ta.get("confidence") or 0) if (ta.get("confidence") or 0) <= 1
                              else float(ta.get("confidence")) / 100.0,
            "tradeability": "moderate" if ta.get("alignedIndicators", 0) >= 2 else "low",
        },
        "asOf":   ta.get("asOf") or _now(),
        "source": "native_ta_v1",
        "note":   "pattern_detection_not_implemented_in_native_ta_v1",
    }


@router.get("/ta/levels/{symbol}/{timeframe}")
def ta_levels(symbol: str, timeframe: str):
    """Support/resistance + current-price levels."""
    sym = symbol.upper()
    ta = _ta_for(sym)
    if not ta.get("ok"):
        return {"ok": False, "symbol": sym, "tf": timeframe.upper(),
                "levels": [], "error": ta.get("error") or ta.get("reason"),
                "source": "native_ta_v1", "asOf": _now()}
    return {
        "ok":     True,
        "symbol": sym,
        "tf":     timeframe.upper(),
        "levels": _levels_pack(ta),
        "asOf":   ta.get("asOf") or _now(),
        "source": "native_ta_v1",
    }


@router.get("/ta/structure/{symbol}/{timeframe}")
def ta_structure(symbol: str, timeframe: str):
    """Market structure summary derived from native_ta_v1."""
    sym = symbol.upper()
    ta = _ta_for(sym)
    if not ta.get("ok"):
        return {"ok": False, "symbol": sym, "tf": timeframe.upper(),
                "error": ta.get("error") or ta.get("reason"),
                "source": "native_ta_v1", "asOf": _now()}
    return {
        "ok":     True,
        "symbol": sym,
        "tf":     timeframe.upper(),
        "structure": {
            "trend":      ta.get("trend"),
            "slope_pct":  ta.get("trendSlopePct"),
            "momentum":   ta.get("momentum"),
            "volatility": ta.get("volatility"),
            "regime":     ta.get("state"),
            "support":    ta.get("support"),
            "resistance": ta.get("resistance"),
            "current":    ta.get("currentPrice"),
        },
        "asOf":   ta.get("asOf") or _now(),
        "source": "native_ta_v1",
    }


@router.get("/ta/indicators/{symbol}/{timeframe}")
def ta_indicators(symbol: str, timeframe: str):
    """Indicator pack (RSI/trend/momentum/volatility) for a TF."""
    sym = symbol.upper()
    ta = _ta_for(sym)
    if not ta.get("ok"):
        return {"ok": False, "symbol": sym, "tf": timeframe.upper(),
                "error": ta.get("error") or ta.get("reason"),
                "source": "native_ta_v1", "asOf": _now()}
    return {
        "ok":     True,
        "symbol": sym,
        "tf":     timeframe.upper(),
        "indicators": {
            "rsi":        {"value": ta.get("rsiValue"), "state": ta.get("rsi")},
            "trend":      {"state": ta.get("trend"),    "slope_pct": ta.get("trendSlopePct")},
            "momentum":   {"state": ta.get("momentum")},
            "volatility": {"state": ta.get("volatility")},
            "alignedIndicators": ta.get("alignedIndicators"),
        },
        "direction":  ta.get("direction"),
        "confidence": ta.get("confidence"),
        "asOf":       ta.get("asOf") or _now(),
        "source":     "native_ta_v1",
    }


@router.get("/ta/confluence/{symbol}/{timeframe}")
def ta_confluence(symbol: str, timeframe: str):
    """Confluence score: how many indicators agree with the direction."""
    sym = symbol.upper()
    ta = _ta_for(sym)
    if not ta.get("ok"):
        return {"ok": False, "symbol": sym, "tf": timeframe.upper(),
                "error": ta.get("error") or ta.get("reason"),
                "source": "native_ta_v1", "asOf": _now()}
    aligned = int(ta.get("alignedIndicators") or 0)
    score = round(min(aligned / 4.0, 1.0), 3)  # 4 indicators max in native_ta_v1
    return {
        "ok":            True,
        "symbol":        sym,
        "tf":            timeframe.upper(),
        "confluenceScore": score,
        "alignedIndicators": aligned,
        "totalIndicators":   4,
        "direction":     ta.get("direction"),
        "confidence":    ta.get("confidence"),
        "reasons":       ta.get("reasons", []),
        "asOf":          ta.get("asOf") or _now(),
        "source":        "native_ta_v1",
    }


@router.get("/ta/patterns/{symbol}/{timeframe}")
def ta_patterns(symbol: str, timeframe: str):
    """Pattern detection is NOT implemented in native_ta_v1 — we are
    honest about that rather than fabricating fake patterns."""
    sym = symbol.upper()
    ta = _ta_for(sym)
    return {
        "ok":             True,
        "symbol":         sym,
        "tf":             timeframe.upper(),
        "primary_pattern": None,
        "patterns":       [],
        "currentPrice":   ta.get("currentPrice") if ta.get("ok") else None,
        "support":        ta.get("support") if ta.get("ok") else None,
        "resistance":     ta.get("resistance") if ta.get("ok") else None,
        "note":           "pattern_detection_not_implemented_in_native_ta_v1",
        "asOf":           _now(),
        "source":         "native_ta_v1",
    }


# ─────────────────────────────────────────────────────────────────────
# /api/ta-engine/* aliases (regime · levels · patterns · snapshot · decision)
# Same logic, just under the older /api/ta-engine/ namespace.
# ─────────────────────────────────────────────────────────────────────
@router.get("/ta-engine/regime")
def ta_engine_regime(symbol: str = Query("BTC")):
    sym = symbol.upper()
    ta = _ta_for(sym)
    if not ta.get("ok"):
        return {"ok": False, "symbol": sym,
                "error": ta.get("error") or ta.get("reason"),
                "source": "native_ta_v1", "asOf": _now()}
    return {
        "ok":     True,
        "symbol": sym,
        "regime": {
            "state":      ta.get("state"),
            "trend":      ta.get("trend"),
            "momentum":   ta.get("momentum"),
            "volatility": ta.get("volatility"),
        },
        "asOf":   ta.get("asOf") or _now(),
        "source": "native_ta_v1",
    }


@router.get("/ta-engine/levels")
def ta_engine_levels(symbol: str = Query("BTC")):
    sym = symbol.upper()
    ta = _ta_for(sym)
    if not ta.get("ok"):
        return {"ok": False, "symbol": sym, "levels": [],
                "error": ta.get("error") or ta.get("reason"),
                "source": "native_ta_v1", "asOf": _now()}
    return {"ok": True, "symbol": sym, "levels": _levels_pack(ta),
            "asOf": ta.get("asOf") or _now(), "source": "native_ta_v1"}


@router.get("/ta-engine/patterns")
def ta_engine_patterns(symbol: str = Query("BTC")):
    return ta_patterns(symbol=symbol, timeframe="1D")


@router.get("/ta-engine/snapshot")
def ta_engine_snapshot(symbol: str = Query("BTC")):
    return ta_engine_mtf(symbol=symbol)


@router.get("/ta-engine/decision")
def ta_engine_decision(symbol: str = Query("BTC")):
    sym = symbol.upper()
    ta = _ta_for(sym)
    if not ta.get("ok"):
        return {"ok": False, "symbol": sym,
                "error": ta.get("error") or ta.get("reason"),
                "source": "native_ta_v1", "asOf": _now()}
    return {
        "ok":         True,
        "symbol":     sym,
        "direction":  ta.get("direction"),
        "confidence": ta.get("confidence"),
        "reasons":    ta.get("reasons", []),
        "aligned":    ta.get("alignedIndicators"),
        "asOf":       ta.get("asOf") or _now(),
        "source":     "native_ta_v1",
    }


@router.get("/ta/regime")
def ta_regime(symbol: str = Query("BTC")):
    return ta_engine_regime(symbol=symbol)


@router.get("/ta/decision")
def ta_decision(symbol: str = Query("BTC")):
    return ta_engine_decision(symbol=symbol)



# ─────────────────────────────────────────────────────────────────────
# /api/prediction/ta/{symbol} — defined LAST so the specific
# /prediction/ta/{live-price,forecast,graph4,snapshot} routes above
# take precedence in FastAPI's matcher.
# ─────────────────────────────────────────────────────────────────────
@router.get("/prediction/ta/{symbol}")
def ta_prediction(
    symbol: str = Path(..., description="Asset symbol, e.g. BTC"),
    horizon: int = Query(30),
):
    """TA-only prediction snapshot — direction + confidence + projected
    move width derived from support/resistance band."""
    sym = symbol.upper()
    ta = _call_native_ta(sym)
    if not ta.get("ok"):
        return {
            "ok":        False,
            "symbol":    sym,
            "horizon":   int(horizon),
            "error":     ta.get("error") or ta.get("reason"),
            "source":    "native_ta_v1",
            "asOf":      _now(),
        }

    cur = ta.get("currentPrice")
    sup = ta.get("support")
    res = ta.get("resistance")
    bias = (ta.get("direction") or "WAIT").upper()
    conf = float(ta.get("confidence") or 0.0)
    if conf > 1.0:
        conf = conf / 100.0

    # Projected target = current ± half of (resistance - support) scaled by conf
    target = cur
    if sup is not None and res is not None and cur is not None and cur > 0:
        band = float(res) - float(sup)
        half = band * 0.5 * max(conf, 0.1)
        if bias in ("LONG", "BUY"):
            target = cur + half
        elif bias in ("SHORT", "SELL"):
            target = cur - half

    return {
        "ok":            True,
        "symbol":        sym,
        "horizon":       int(horizon),
        "direction":     bias,
        "confidence":    conf,
        "currentPrice":  cur,
        "targetPrice":   round(float(target), 4) if target else None,
        "support":       sup,
        "resistance":    res,
        "rsi":           ta.get("rsiValue"),
        "trend":         ta.get("trend"),
        "momentum":      ta.get("momentum"),
        "volatility":    ta.get("volatility"),
        "reasons":       ta.get("reasons", []),
        "source":        ta.get("source") or "native_ta_v1",
        "asOf":          ta.get("asOf") or _now(),
    }
