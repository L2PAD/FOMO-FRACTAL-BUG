"""
Intelligence / Alpha page — Real-data aggregator
=================================================
The Alpha page (`/intelligence/price-expectation-v2`) consumes ONE big
payload from `/api/market/chart/price-vs-expectation-v4` which was a
`legacy_compat_stub_empty`.  This router replaces it with real data:

  • verdict       ← MetaBrain build_verdict (5-module consensus)
  • metaForecast  ← prediction/exchange/forecast (real walk-forward)
  • metrics       ← exchange_forecast_runs + exchange_forecasts.outcome
  • outcomes      ← exchange_forecasts with `outcome` filled
  • candidates    ← top forecasts across the universe
  • signal/decision drivers ← funding/OI/regime + MetaBrain reasons
  • avgFunding / zScore / openInterest ← live OKX feeds

Mounted BEFORE legacy_compat so the real handlers win.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Query

router = APIRouter(tags=["intelligence_real"])


# ─────────────────────────── helpers ────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _db():
    from pymongo import MongoClient
    return MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "fomo_mobile")
    ]


def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs) or {}
    except Exception:
        return {}


def _verdict_for(symbol: str) -> Dict[str, Any]:
    """Pull live 5-module MetaBrain verdict."""
    try:
        from services.trading_runtime import build_verdict  # type: ignore
        return build_verdict(symbol) or {}
    except Exception:
        return {}


def _ex_forecast(symbol: str, horizon: str = "7D") -> Dict[str, Any]:
    """Latest real exchange forecast (walk-forward) — direct Mongo read."""
    try:
        db = _db()
        if "exchange_forecasts" not in db.list_collection_names():
            return {}
        doc = db["exchange_forecasts"].find_one(
            {"asset": symbol.upper(), "horizon": horizon.upper()},
            {"_id": 0}, sort=[("createdAt", -1)],
        )
        if not doc:
            # fallback to any horizon
            doc = db["exchange_forecasts"].find_one(
                {"asset": symbol.upper()}, {"_id": 0},
                sort=[("createdAt", -1)],
            )
        return doc or {}
    except Exception:
        return {}


def _funding_pack(symbol: str) -> Dict[str, Any]:
    """Live funding + OI from OKX (via internal HTTP — robust to route shape changes)."""
    import httpx
    sym = symbol.upper()
    base = "http://127.0.0.1:8001"
    f, oi, d = {}, {}, {}
    try:
        with httpx.Client(timeout=4) as c:
            try:
                f = c.get(f"{base}/api/exchange/funding/{sym}").json() or {}
            except Exception:
                f = {}
            try:
                oi = c.get(f"{base}/api/exchange/open-interest/{sym}").json() or {}
            except Exception:
                oi = {}
            try:
                d = c.get(f"{base}/api/exchange/derivatives/{sym}").json() or {}
            except Exception:
                d = {}
    except Exception:
        pass
    return {"funding": f, "openInterest": oi, "derivatives": d}


def _model_metrics(asset: str, horizon: str = "7D") -> Dict[str, Any]:
    """Real model metrics from exchange_forecasts.outcome rows."""
    try:
        db = _db()
        evaluated = list(db["exchange_forecasts"].find(
            {"asset": asset.upper(),
             "horizon": horizon.upper(),
             "outcome": {"$ne": None}},
            {"_id": 0, "outcome": 1, "expectedMovePct": 1,
             "direction": 1, "confidence": 1}
        ).limit(500))
        n = len(evaluated)
        if n == 0:
            return {
                "horizon":              horizon,
                "modelScore":           0,
                "hitRatePct":           0,
                "directionMatchPct":    0,
                "avgDeviationPct":      0,
                "calibrationScore":     0,
                "evaluatedCount":       0,
                "expectedCalibration":  0,
                "breakdown":            {"tp": 0, "fp": 0, "fn": 0, "weak": 0},
                "source":               "exchange_forecasts.outcome",
                "note":                 "no_evaluations_yet",
            }

        win = sum(1 for e in evaluated if (e.get("outcome") or {}).get("label") == "WIN")
        dir_match = sum(
            1 for e in evaluated
            if (e.get("outcome") or {}).get("directionCorrect") is True
        )
        avg_dev = sum(
            abs(float((e.get("outcome") or {}).get("deviationPct") or 0))
            for e in evaluated
        ) / n
        avg_conf = sum(float(e.get("confidence") or 0) for e in evaluated) / n
        tp = sum(
            1 for e in evaluated
            if (e.get("outcome") or {}).get("label") == "WIN"
            and float(e.get("confidence") or 0) >= 0.5
        )
        fp = sum(
            1 for e in evaluated
            if (e.get("outcome") or {}).get("label") == "LOSS"
            and float(e.get("confidence") or 0) >= 0.5
        )
        fn = sum(
            1 for e in evaluated
            if (e.get("outcome") or {}).get("label") == "LOSS"
            and float(e.get("confidence") or 0) < 0.5
        )
        weak = sum(
            1 for e in evaluated
            if (e.get("outcome") or {}).get("label") not in ("WIN", "LOSS")
        )
        hit_rate = round((win / n) * 100, 1)
        direction_pct = round((dir_match / n) * 100, 1)
        avg_dev_pct = round(avg_dev, 2)
        calib = max(0, 100 - round(abs(avg_conf * 100 - hit_rate)))
        score = round(direction_pct * 0.5 + hit_rate * 0.3 + calib * 0.2)
        return {
            "horizon":             horizon,
            "modelScore":          score,
            "hitRatePct":          hit_rate,
            "directionMatchPct":   direction_pct,
            "avgDeviationPct":     avg_dev_pct,
            "calibrationScore":    calib,
            "evaluatedCount":      n,
            "expectedCalibration": round(avg_conf * 100),
            "breakdown":           {"tp": tp, "fp": fp, "fn": fn, "weak": weak},
            "source":              "exchange_forecasts.outcome",
        }
    except Exception as e:
        return {"horizon": horizon, "modelScore": 0, "evaluatedCount": 0,
                "error": repr(e)[:120], "breakdown": {"tp": 0, "fp": 0, "fn": 0, "weak": 0}}


def _outcomes_list(asset: str, horizon: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Real recent outcomes."""
    try:
        db = _db()
        rows = list(db["exchange_forecasts"].find(
            {"asset": asset.upper(),
             "horizon": horizon.upper(),
             "outcome": {"$ne": None}},
            {"_id": 0, "createdAt": 1, "direction": 1, "confidence": 1,
             "entryPrice": 1, "targetPrice": 1, "expectedMovePct": 1, "outcome": 1}
        ).sort("createdAt", -1).limit(limit))
        return [
            {
                "createdAt":   r.get("createdAt"),
                "direction":   r.get("direction"),
                "confidence":  r.get("confidence"),
                "entryPrice":  r.get("entryPrice"),
                "targetPrice": r.get("targetPrice"),
                "expectedMovePct": r.get("expectedMovePct"),
                "result":      (r.get("outcome") or {}).get("label"),
                "actualMovePct": (r.get("outcome") or {}).get("actualMovePct"),
                "deviationPct":  (r.get("outcome") or {}).get("deviationPct"),
            }
            for r in rows
        ]
    except Exception:
        return []


def _build_verdict_card(v: Dict[str, Any], horizon: str = "7D") -> Dict[str, Any]:
    """Map MetaBrain verdict → Alpha-page `verdict` shape."""
    action = (v.get("action") or "WAIT").upper()
    ui_action = {"LONG": "BUY", "SHORT": "SELL", "WAIT": "NEUTRAL"}.get(action, "NEUTRAL")

    entry = float(v.get("entry") or v.get("currentPrice") or 0)
    target = v.get("target")
    expected_return = 0.0
    if entry and target:
        try:
            expected_return = (float(target) - entry) / entry
        except Exception:
            expected_return = 0.0

    risk_band = (v.get("risk") or "moderate").upper()
    if risk_band in ("LOW", "GREEN"):
        risk = "LOW"
    elif risk_band in ("HIGH", "RED"):
        risk = "HIGH"
    else:
        risk = "MEDIUM"

    return {
        "action":          ui_action,
        "rawAction":       action,
        "confidence":      float(v.get("confidence") or 0),
        "expectedReturn":  round(expected_return, 4),
        "risk":            risk,
        "positionSizePct": float(v.get("sizingPct") or v.get("positionSizePct") or 0),
        "horizon":         horizon,
        "modelId":         "meta_brain_v3",
        "currentPrice":    v.get("currentPrice"),
        "entry":           v.get("entry"),
        "stop":            v.get("stop"),
        "target":          v.get("target"),
        "rr":              v.get("rr"),
        "support":         v.get("support"),
        "resistance":      v.get("resistance"),
        "blockedBy":       v.get("blockedBy") or [],
        "reasons":         (v.get("reasons") or [])[:6],
        "modules":         v.get("alignment") or {},
        "moduleConfidence": v.get("moduleConfidence") or {},
        "moduleDegraded":   v.get("moduleDegraded") or {},
    }


def _build_meta_forecast(ex_forecast: Dict[str, Any]) -> Dict[str, Any]:
    """Map exchange forecast (Mongo doc or HTTP wrapper) → metaForecast card."""
    if not ex_forecast:
        return {"action": "HOLD", "appliedOverlays": [], "available": False,
                "source": "no_exchange_forecast"}

    # Two shapes: HTTP `{targets: [...]}` OR raw Mongo doc with top-level fields
    primary = None
    if isinstance(ex_forecast.get("targets"), list) and ex_forecast["targets"]:
        for t in ex_forecast["targets"]:
            if t.get("horizon") == "7D":
                primary = t
                break
        if not primary:
            primary = ex_forecast["targets"][0]
    elif ex_forecast.get("targetPrice") is not None or ex_forecast.get("direction"):
        # Raw Mongo doc shape
        primary = ex_forecast

    if not primary:
        return {"action": "HOLD", "appliedOverlays": [], "available": False,
                "source": "no_exchange_forecast"}

    dir_raw = (primary.get("direction") or "NEUTRAL").upper()
    action = {"LONG": "BUY", "SHORT": "SELL"}.get(dir_raw, "HOLD")
    return {
        "action":          action,
        "direction":       dir_raw,
        "horizon":         primary.get("horizon"),
        "targetPrice":     primary.get("targetPrice"),
        "entryPrice":      primary.get("entryPrice"),
        "movePct":         primary.get("movePct") or primary.get("expectedMovePct"),
        "confidence":      primary.get("confidence"),
        "modelVersion":    primary.get("modelVersion") or primary.get("runId"),
        "appliedOverlays": [],
        "available":       True,
        "source":          "exchange_forecasts",
    }


def _signal_drivers(asset: str, fp: Dict[str, Any]) -> Dict[str, Any]:
    """Build the SIGNAL DRIVERS card from real exchange feeds."""
    f = fp.get("funding") or {}
    oi = fp.get("openInterest") or {}
    d = fp.get("derivatives") or {}

    funding_rate = f.get("fundingRate") or d.get("fundingRate")
    funding_pct = float(funding_rate) * 100 if funding_rate is not None else None
    oi_usd = oi.get("oiUsd") or oi.get("openInterestUsd")
    oi_delta = oi.get("oiChange24hPct") or oi.get("changePct24h")

    if funding_pct is not None:
        if funding_pct > 0.02:
            f_state = "high_long"
        elif funding_pct < -0.02:
            f_state = "high_short"
        else:
            f_state = "neutral"
    else:
        f_state = "unknown"

    return {
        "funding": {
            "rate":      funding_rate,
            "ratePct":   funding_pct,
            "state":     f_state,
            "available": funding_rate is not None,
            "source":    f.get("source") or "okx_public",
        },
        "openInterest": {
            "usd":         oi_usd,
            "changePct24h": oi_delta,
            "available":   oi_usd is not None,
            "source":      oi.get("source") or "okx_public",
        },
        "liquidationRisk": {
            "level":     "elevated" if (funding_pct and abs(funding_pct) > 0.03) else "normal",
            "available": funding_pct is not None,
        },
        "regime": {
            "label":     d.get("regime") or "range",
            "trend":     d.get("trend") or "neutral",
            "available": True,
            "source":    "exchange_derivatives",
        },
    }


# ────────────────────────────────────────────────────────────────
# MAIN AGGREGATOR
# ────────────────────────────────────────────────────────────────
@router.get("/api/market/chart/price-vs-expectation-v4")
def market_price_vs_expectation_v4(
    asset: str = Query("BTC"),
    range: str = Query("30d"),
    horizon: str = Query("7d"),
):
    sym = asset.upper().replace("USDT", "")
    horizon_u = horizon.upper()

    verdict_raw = _verdict_for(sym)
    ex_fc = _ex_forecast(sym, horizon_u)
    fp = _funding_pack(sym)
    metrics = _model_metrics(sym, horizon_u)
    outcomes = _outcomes_list(sym, horizon_u)

    verdict_card = _build_verdict_card(verdict_raw, horizon_u)
    meta_forecast = _build_meta_forecast(ex_fc)
    signal_drv = _signal_drivers(sym, fp)

    # Decision drivers — derived from MetaBrain reasons + module alignment
    decision_drivers = []
    align = verdict_raw.get("alignment") or {}
    conf = verdict_raw.get("moduleConfidence") or {}
    for m in ("ta", "sentiment", "fractal", "exchange", "onchain"):
        vote = align.get(m)
        if not vote:
            continue
        decision_drivers.append({
            "module":     m,
            "vote":       vote,
            "confidence": conf.get(m, 0),
            "weight":     {"exchange": 0.40, "sentiment": 0.20,
                           "fractal": 0.15, "onchain": 0.15, "ta": 0.10}.get(m, 0.10),
            "degraded":   (verdict_raw.get("moduleDegraded") or {}).get(m, False),
        })

    # Future point/band for chart overlay
    target_price = (meta_forecast.get("targetPrice")
                    if meta_forecast.get("available") else None)
    layers = {
        "meta": {
            "futurePoint": {
                "price":      target_price,
                "horizon":    horizon_u,
                "confidence": meta_forecast.get("confidence"),
            } if target_price else None,
            "futureBand": {
                "low":  ex_fc.get("bandCoreLow"),
                "high": ex_fc.get("bandCoreHigh"),
                "wideLow":  ex_fc.get("bandWideLow"),
                "wideHigh": ex_fc.get("bandWideHigh"),
            } if (ex_fc.get("bandCoreLow") or ex_fc.get("bandCoreHigh")) else None,
        }
    }

    # Top forecast candidates across the universe
    candidates: List[Dict[str, Any]] = []
    try:
        db = _db()
        cur = db["exchange_forecasts"].find(
            {"horizon": horizon_u, "asset": {"$ne": sym}},
            {"_id": 0, "asset": 1, "symbol": 1, "direction": 1,
             "confidence": 1, "expectedMovePct": 1, "createdAt": 1}
        ).sort([("confidence", -1), ("createdAt", -1)]).limit(8)
        candidates = list(cur)
    except Exception:
        pass

    # Error clusters from metrics breakdown
    bd = metrics.get("breakdown") or {}
    error_clusters = []
    for kind, count in [("false_positive", bd.get("fp", 0)),
                         ("false_negative", bd.get("fn", 0)),
                         ("weak_signal",    bd.get("weak", 0))]:
        if count > 0:
            error_clusters.append({
                "kind":  kind,
                "count": count,
                "pctOfEvaluated": round(count / max(metrics.get("evaluatedCount", 1), 1) * 100, 1),
            })

    return {
        "ok":           True,
        "asset":        sym,
        "range":        range,
        "horizon":      horizon_u,
        "verdict":      verdict_card,
        "metaForecast": meta_forecast,
        "metrics":      metrics,
        "outcomes":     outcomes,
        "errorClusters": error_clusters,
        "candidates":   candidates,
        "layers":       layers,
        "signalDrivers":   signal_drv,
        "decisionDrivers": decision_drivers,
        # Top-level legacy fields the UI also reads
        "avgFunding":   signal_drv["funding"].get("ratePct"),
        "zScore":       None,
        "openInterest": {
            "longPercent": fp.get("derivatives", {}).get("longPercent")
                           or fp.get("derivatives", {}).get("longRatioPct"),
            "usd":         signal_drv["openInterest"].get("usd"),
        },
        "asOf":   _now(),
        "source": "intelligence_real_v1",
    }


# ── Aliases for the legacy /api/intelligence/* paths ────────────
@router.get("/api/intelligence/v3/alpha")
def intelligence_v3_alpha(asset: str = Query("BTC"), horizon: str = Query("7d")):
    return market_price_vs_expectation_v4(asset=asset, horizon=horizon)


@router.get("/api/intelligence/alpha")
def intelligence_alpha(asset: str = Query("BTC"), horizon: str = Query("7d")):
    return market_price_vs_expectation_v4(asset=asset, horizon=horizon)


@router.get("/api/intelligence/system-health")
def intelligence_system_health(asset: str = Query("BTC")):
    v = _verdict_for(asset.upper())
    align = v.get("alignment") or {}
    degraded = v.get("moduleDegraded") or {}
    mods = ["ta", "sentiment", "fractal", "exchange", "onchain"]
    active = sum(1 for m in mods if align.get(m) and not degraded.get(m))
    return {
        "ok":           True,
        "status":       "HEALTHY" if active >= 4 else "WARNING" if active >= 2 else "DEGRADED",
        "coverage":     {"active": active, "total": len(mods)},
        "modules":      {m: {"vote": align.get(m), "degraded": degraded.get(m, False)} for m in mods},
        "moduleConfidence": v.get("moduleConfidence") or {},
        "confidence":   v.get("confidence") or 0,
        "drift":        "low",
        "asOf":         _now(),
        "source":       "intelligence_real_v1",
    }


@router.get("/api/intelligence/decision-drivers")
def intelligence_decision_drivers(asset: str = Query("BTC")):
    v = _verdict_for(asset.upper())
    align = v.get("alignment") or {}
    conf = v.get("moduleConfidence") or {}
    drivers = []
    for m in ("exchange", "sentiment", "fractal", "onchain", "ta"):
        if align.get(m):
            drivers.append({
                "module":     m,
                "vote":       align.get(m),
                "confidence": conf.get(m, 0),
                "weight":     {"exchange": 0.40, "sentiment": 0.20,
                               "fractal": 0.15, "onchain": 0.15, "ta": 0.10}[m],
                "degraded":   (v.get("moduleDegraded") or {}).get(m, False),
            })
    return {"ok": True, "asset": asset.upper(), "drivers": drivers,
            "reasons": (v.get("reasons") or [])[:6], "asOf": _now(),
            "source": "trading_runtime.build_verdict"}


@router.get("/api/intelligence/signal-drivers")
def intelligence_signal_drivers(asset: str = Query("BTC")):
    fp = _funding_pack(asset.upper())
    return {"ok": True, "asset": asset.upper(),
            "signalDrivers": _signal_drivers(asset.upper(), fp),
            "asOf": _now(), "source": "exchange_runtime"}


@router.get("/api/intelligence/expected-range")
def intelligence_expected_range(asset: str = Query("BTC"),
                                 horizon: str = Query("7D")):
    fc = _ex_forecast(asset.upper(), horizon.upper())
    return {
        "ok":      True,
        "asset":   asset.upper(),
        "horizon": horizon.upper(),
        "range": {
            "core":  {"low": fc.get("bandCoreLow"), "high": fc.get("bandCoreHigh")},
            "wide":  {"low": fc.get("bandWideLow"), "high": fc.get("bandWideHigh")},
            "target": fc.get("targetPrice"),
            "entry":  fc.get("entryPrice"),
        },
        "available": bool(fc.get("targetPrice") or fc.get("bandCoreLow")),
        "asOf":   _now(),
        "source": "exchange_forecasts",
    }


# ── Sentiment / News real endpoints (Twitter AI feed) ───────────
@router.get("/api/v10/exchange/funding/sentiment")
def v10_exchange_funding_sentiment(symbol: str = Query("BTC")):
    return intelligence_signal_drivers(asset=symbol)


@router.get("/api/news/stories")
def news_stories(asset: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=100)):
    """Real news/Twitter AI feed from `intel_news_stories` collection."""
    try:
        db = _db()
        q: Dict[str, Any] = {}
        if asset:
            q["$or"] = [{"asset": asset.upper()}, {"tickers": asset.upper()}]
        rows = list(db["intel_news_stories"].find(q, {"_id": 0})
                    .sort("publishedAt", -1).limit(limit))
        return {"ok": True, "stories": rows, "count": len(rows),
                "source": "intel_news_stories", "asOf": _now()}
    except Exception as e:
        return {"ok": False, "error": repr(e)[:120], "stories": [], "asOf": _now()}


@router.get("/api/sentiment/twitter")
def sentiment_twitter(asset: Optional[str] = Query(None),
                       limit: int = Query(20, ge=1, le=100)):
    """Real Twitter AI feed — filtered intel_news_stories with source=twitter."""
    try:
        db = _db()
        q: Dict[str, Any] = {"source": {"$regex": "twitter", "$options": "i"}}
        if asset:
            q["$or"] = [{"asset": asset.upper()}, {"tickers": asset.upper()}]
        rows = list(db["intel_news_stories"].find(q, {"_id": 0})
                    .sort("publishedAt", -1).limit(limit))
        if not rows:
            # fallback: just return the most recent news stories
            rows = list(db["intel_news_stories"].find(
                {"$or": [{"asset": asset.upper()}, {"tickers": asset.upper()}]} if asset else {},
                {"_id": 0}
            ).sort("publishedAt", -1).limit(limit))
        return {"ok": True, "items": rows, "count": len(rows),
                "source": "intel_news_stories.twitter_filter", "asOf": _now()}
    except Exception as e:
        return {"ok": False, "error": repr(e)[:120], "items": [], "asOf": _now()}


@router.get("/api/sentiment/events")
def sentiment_events_endpoint(asset: Optional[str] = Query(None),
                              limit: int = Query(30, ge=1, le=200)):
    """Real sentiment events from sentiment_events collection (4.2K+ rows)."""
    try:
        db = _db()
        q: Dict[str, Any] = {}
        if asset:
            q["$or"] = [{"asset": asset.upper()}, {"symbol": asset.upper()}]
        rows = list(db["sentiment_events"].find(q, {"_id": 0})
                    .sort("createdAt", -1).limit(limit))
        return {"ok": True, "items": rows, "count": len(rows),
                "source": "sentiment_events", "asOf": _now()}
    except Exception as e:
        return {"ok": False, "error": repr(e)[:120], "items": [], "asOf": _now()}
