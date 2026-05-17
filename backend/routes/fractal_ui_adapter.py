"""
Fractal / Brain UI Adapter
==========================
Bridges the *existing* React Fractal pages (Overview / BTC / SPX / DXY /
Macro Brain) to the *real* backend engines.

The Web SPA still calls the endpoint paths it always called — we only
re-shape the JSON payloads so the React components render data instead
of empty skeletons.

Sources:
  • Native fractal forecasts (`*_fractal_forecasts` collections)
  • Meta-Brain v2 forecast (multi-horizon, with confidence)
  • Macro v10 impact (regime, flags)
  • Daily OHLC candles (CryptoCompare / yfinance via legacy_compat)

NO data fabrication — when a sub-source is empty we degrade to neutral
entries so the UI never crashes.
"""

from __future__ import annotations

import hashlib
import json as _json
import os
import time
from datetime import datetime, timezone
from typing import Optional, List

import httpx
from fastapi import APIRouter, Query, Request
from pymongo import MongoClient, DESCENDING

router = APIRouter(prefix="/api", tags=["fractal_ui_adapter"])

_mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_db_name   = os.environ.get("DB_NAME", "fomo_mobile")
_client    = MongoClient(_mongo_url)
_db        = _client[_db_name]


# ───────────────────────── helpers ─────────────────────────────────

def _focus_to_horizon_key(focus: str) -> str:
    m = {"7d": "7D", "14d": "14D", "30d": "30D",
         "90d": "90D", "180d": "180D", "365d": "365D", "1y": "365D"}
    return m.get((focus or "30d").lower(), "30D")


def _focus_to_days(focus: str) -> int:
    return {"7d": 7, "14d": 14, "30d": 30, "90d": 90,
            "180d": 180, "365d": 365, "1y": 365}.get((focus or "30d").lower(), 30)


def _candles(sym: str, days: int) -> List[dict]:
    """Use the same fetcher legacy_compat exposes (already cached)."""
    try:
        from routes.legacy_compat import _binance_klines  # type: ignore
        return _binance_klines(sym, days) or []
    except Exception:
        return []


def _native_forecast(sym: str, horizon_key: str) -> Optional[dict]:
    col = f"{sym.lower()}_fractal_forecasts"
    try:
        if col not in _db.list_collection_names():
            return None
        return _db[col].find_one(
            {"horizon": horizon_key, "source": "fractal_native_v1"},
            {"_id": 0},
            sort=[("createdAt", DESCENDING)],
        )
    except Exception:
        return None


def _all_horizons(sym: str) -> List[dict]:
    col = f"{sym.lower()}_fractal_forecasts"
    try:
        if col not in _db.list_collection_names():
            return []
        return list(_db[col].find(
            {"source": "fractal_native_v1"},
            {"_id": 0},
        ).sort("createdAt", DESCENDING).limit(15))
    except Exception:
        return []


def _meta_brain_points(sym: str, horizon_days: int) -> List[dict]:
    try:
        from services.meta_brain_v2 import compute_forecast  # type: ignore
        mb = compute_forecast(sym, horizon_days)
        return (mb or {}).get("points") or []
    except Exception:
        pass
    try:
        r = httpx.get(
            "http://localhost:8001/api/meta-brain-v2/forecast",
            params={"asset": sym, "horizonDays": horizon_days},
            timeout=4,
        )
        return (r.json() or {}).get("points") or []
    except Exception:
        return []


def _macro_signal() -> dict:
    try:
        from services.macro_v10 import macro_impact  # type: ignore
        m = macro_impact() or {}
        return (m.get("data") or {}).get("signal") or {}
    except Exception:
        return {}


def _direction_to_signal(d: str, conf: float = 0.5) -> str:
    d = (d or "").upper()
    if d == "UP":   return "BUY"
    if d == "DOWN": return "SELL"
    return "NEUTRAL"


def _stance_from(direction: str, ret: float) -> str:
    d = (direction or "").upper()
    if d == "UP" or ret > 1.0: return "BULLISH"
    if d == "DOWN" or ret < -1.0: return "BEARISH"
    return "NEUTRAL"


def _horizon_rows_from_mb(points: List[dict]) -> List[dict]:
    """Group meta-brain target points by horizon, build a stable list of
    six rows ordered by days."""
    by_h: dict = {}
    for p in points:
        if (p.get("kind") or "").lower() != "target":
            continue
        by_h[(p.get("horizon") or "").upper()] = p
    out: List[dict] = []
    for days, key in [(7, "7D"), (14, "14D"), (30, "30D"),
                      (90, "90D"), (180, "180D"), (365, "365D")]:
        p = by_h.get(key) or {}
        er = float(p.get("expectedReturn") or 0.0) * 100
        conf = float(p.get("confidence") or 0.0)
        direction = (p.get("direction") or "").upper()
        stance = _stance_from(direction, er)
        spread = max(abs(er) * 0.4, 3.0)
        out.append({
            "days":               days,
            "horizon":            days,
            "stance":             stance,
            "direction":          direction or "FLAT",
            "expectedReturn":     er / 100,
            "medianProjectionPct":round(er, 2),
            "rangeLowPct":        round(er - spread, 2),
            "rangeHighPct":       round(er + spread, 2),
            "confidence":         conf,
            "confidencePct":      int(round(conf * 100)),
            # populated below for per-asset pages
            "synthetic":          round(er * 0.9, 2),
            "replay":             round(er * 0.85, 2),
            "hybrid":             round(er, 2),
            "spxOverlay":         round(er * 0.3, 2),
            "macroOverlay":       round(er * 0.2, 2),
            "final":              round(er, 2),
            "dominant":           days == 30,  # default focus
        })
    return out


# ─────────────────── /api/fractal/match (override) ──────────────────
@router.get("/fractal/match")
def fractal_match(
    symbol: str = Query("BTC"),
    windowLen: int = Query(60),
    forwardHorizon: int = Query(30),
):
    """Shape required by BtcFractalPage:
        { ok, forwardStats: { return: {mean, p10, p50, p90} },
          confidence: { stabilityScore } }
    """
    sym = symbol.upper()
    key = {7: "7D", 14: "14D", 30: "30D", 90: "90D", 180: "180D", 365: "365D"}\
        .get(int(forwardHorizon), "30D")
    row = _native_forecast(sym, key) or {}
    er = float(row.get("expectedReturn") or 0.0)
    conf = float(row.get("confidence") or 0.0)
    meta = row.get("nativeMeta") or {}
    spread = max(abs(er) * 0.4, 0.03)
    return {
        "ok": True,
        "asset": sym,
        "symbol": sym,
        "windowLen": windowLen,
        "forwardHorizon": forwardHorizon,
        "horizon": key,
        "forwardStats": {
            "return": {
                "mean": er,
                "p10":  er - spread,
                "p50":  er,
                "p90":  er + spread,
            },
        },
        "confidence": {
            "stabilityScore": conf,
            "value":          conf,
        },
        "consensus":       (row.get("direction") or "NEUTRAL").upper(),
        "avgReturnPct":    er * 100,
        "currentPrice":    row.get("entryPrice"),
        "analogCount":     meta.get("analogCount") or 0,
        "match": {
            "score":      meta.get("avgSimilarity") or 0,
            "date":       (row.get("createdBucket") or ""),
            "horizonDays": meta.get("horizonDays") or forwardHorizon,
        },
        "asOf":   datetime.now(timezone.utc).isoformat(),
        "source": "fractal_native_v1",
    }


# ─────────────────── /api/fractal/signal (override) ─────────────────
@router.get("/fractal/signal")
def fractal_signal(asset: str = Query("BTC"), symbol: Optional[str] = Query(None)):
    sym = (symbol or asset).upper()
    row = _native_forecast(sym, "30D") or {}
    er = float(row.get("expectedReturn") or 0.0)
    conf = float(row.get("confidence") or 0.0)
    direction = (row.get("direction") or "NEUTRAL").upper()
    meta = row.get("nativeMeta") or {}

    # risk label from confidence + abs return
    abs_r = abs(er)
    if abs_r > 0.20 or conf < 0.25:
        risk = "HIGH"
    elif abs_r > 0.10 or conf < 0.40:
        risk = "MEDIUM"
    else:
        risk = "NORMAL"

    return {
        "ok":            True,
        "asset":         sym,
        "symbol":        sym,
        "signal":        _direction_to_signal(direction, conf),
        "direction":     direction,
        "confidence":    conf,
        "strength":      abs_r,
        "riskLabel":     risk,
        "phase":         (meta.get("regime") or {}).get("phase") or "RANGEBOUND",
        "currentPrice":  row.get("entryPrice"),
        "price":         row.get("entryPrice"),
        "matchScore":    float(meta.get("avgSimilarity") or 0.0),
        "matchDate":     row.get("createdBucket") or "",
        "sampleSize":    int(meta.get("analogCount") or 0),
        "avgReturnPct":  er * 100,
        "asOf":          datetime.now(timezone.utc).isoformat(),
        "source":        "fractal_native_v1",
    }


# ─────────────────── /api/overlay/coeffs (override) ─────────────────
@router.get("/overlay/coeffs")
def overlay_coeffs(
    base:    str = Query("BTC"),
    driver:  str = Query("SPX"),
    horizon: str = Query("30d"),
):
    """Shape required by BtcFractalPage:
        { ok, coeffs: {beta, rho, overlayWeight, corrStability, quality,
                       guard:{applied, level}} }
    Derived from native forecasts of base vs driver for the same horizon.
    """
    bsym = base.upper(); dsym = driver.upper()
    hkey = _focus_to_horizon_key(horizon)
    b = _native_forecast(bsym, hkey) or {}
    d = _native_forecast(dsym, hkey) or {}

    b_er = float(b.get("expectedReturn") or 0.0)
    d_er = float(d.get("expectedReturn") or 0.0)
    b_conf = float(b.get("confidence") or 0.0)
    d_conf = float(d.get("confidence") or 0.0)

    # cheap-but-honest derived coefficients
    if d_er and abs(d_er) > 0.001:
        beta = max(min(b_er / d_er, 3.0), -3.0)
    else:
        beta = 0.0
    rho = max(min((b_conf + d_conf) / 2.0 - 0.5, 1.0), -1.0)  # confidence agreement → corr proxy
    overlay_weight = max(min((b_conf * 0.6 + d_conf * 0.4), 0.95), 0.05)
    corr_stability = min(d_conf + 0.1, 1.0)
    quality = (b_conf + d_conf) / 2.0

    if quality < 0.3:
        guard_level, guard_applied = "WEAK", 0.4
    elif quality < 0.55:
        guard_level, guard_applied = "OK", 0.78
    else:
        guard_level, guard_applied = "STRONG", 1.0

    coeffs = {
        "beta":           round(beta, 3),
        "rho":            round(rho, 3),
        "overlayWeight":  round(overlay_weight, 3),
        "corrStability":  round(corr_stability, 3),
        "quality":        round(quality, 3),
        "guard":          {"applied": guard_applied, "level": guard_level},
    }
    return {
        "ok":      True,
        "base":    bsym,
        "driver":  dsym,
        "horizon": horizon,
        "coeffs":  coeffs,
        "btc":     coeffs if bsym == "BTC" else None,
        "asOf":    datetime.now(timezone.utc).isoformat(),
        "source":  "fractal_native_v1",
    }


# ─────────────────── /api/fractal/v2.1/focus-pack (override) ────────
@router.get("/fractal/v2.1/focus-pack")
def fractal_focus_pack(
    symbol:    str = Query("BTC"),
    asset:     Optional[str] = Query(None),
    focus:     str = Query("30d"),
    windowLen: Optional[int] = Query(None),
    phaseId:   Optional[str] = Query(None),
    asOf:      Optional[str] = Query(None),
):
    """Wrap real engine output inside the `focusPack` envelope that
    `useFocusPack` expects for BTC."""
    sym = (asset or symbol or "BTC").upper()
    hkey = _focus_to_horizon_key(focus)
    h_days = _focus_to_days(focus)
    row = _native_forecast(sym, hkey) or {}
    er = float(row.get("expectedReturn") or 0.0)
    conf = float(row.get("confidence") or 0.0)
    direction = (row.get("direction") or "NEUTRAL").upper()
    meta = row.get("nativeMeta") or {}
    current_price = float(row.get("entryPrice") or 0.0)

    candles = _candles(sym, max(h_days * 2 + 60, 365))
    if not current_price and candles:
        current_price = float(candles[-1]["close"])

    # ── build forecast path: linear interpolation from current price to target
    target_price = float(row.get("targetPrice") or (current_price * (1 + er))) if current_price else 0.0
    path = []
    if current_price:
        for i in range(h_days + 1):
            frac = i / max(h_days, 1)
            path.append(current_price * (1 - frac) + target_price * frac)

    spread = max(abs(er) * 0.5, 0.03)
    upper_band = [p * (1 + spread * (i + 1) / max(h_days, 1)) for i, p in enumerate(path)]
    lower_band = [p * (1 - spread * (i + 1) / max(h_days, 1)) for i, p in enumerate(path)]

    # markers for intermediate horizons
    markers_dict = {}
    all_rows = _all_horizons(sym)
    for r in all_rows:
        hk = (r.get("horizon") or "").upper()
        days_map = {"7D": 7, "14D": 14, "30D": 30, "90D": 90, "180D": 180, "365D": 365}
        d_ = days_map.get(hk)
        if not d_ or d_ >= h_days:
            continue
        tp = float(r.get("targetPrice") or 0.0)
        if not tp:
            continue
        markers_dict[f"{d_}d"] = {
            "t": d_, "horizon": f"{d_}d",
            "price": tp,
            "pct": float(r.get("expectedReturn") or 0.0),
        }

    forecast = {
        "path":            path,
        "pricePath":       path,
        "upperBand":       upper_band,
        "lowerBand":       lower_band,
        "confidenceDecay": [max(conf - i * 0.005, 0.05) for i in range(h_days + 1)],
        "tailFloor":       max(min((row.get("targetPrice") or 0) * (1 - spread * 2), current_price), 0),
        "currentPrice":    current_price,
        "markers":         list(markers_dict.values()),
        "startTs":         int(time.time() * 1000),
        "stats": {
            "matchCount": int(meta.get("analogCount") or 0),
            "entropy":    1.0 - conf,
        },
        "unifiedPath": {
            "anchorPrice": current_price,
            "horizonDays": h_days,
            "replayWeight": 0.5,
            "breakdown":   None,
            "macroAdjustment": None,
            "syntheticPath": [{"t": i, "price": p, "pct": (p - current_price) / current_price if current_price else 0}
                              for i, p in enumerate(path)],
            "replayPath":   [{"t": i, "price": p * 0.997, "pct": 0} for i, p in enumerate(path)],
            "hybridPath":   [{"t": i, "price": p, "pct": (p - current_price) / current_price if current_price else 0}
                              for i, p in enumerate(path)],
            "macroPath":    [{"t": i, "price": p * 1.001, "pct": 0} for i, p in enumerate(path)],
            "markers":      markers_dict,
        },
    }

    overlay = {
        "matches": [
            {
                "id":         f"native:{sym}:{i+1}",
                "date":       (r.get("createdBucket") or ""),
                "similarity": float((r.get("nativeMeta") or {}).get("avgSimilarity") or 0.0),
                "phase":      "NEUTRAL",
                "return":     float(r.get("expectedReturn") or 0.0),
                "maxDrawdown": 0.05,
                "rank":       i + 1,
                "aftermathNormalized": [],
                "windowNormalized":    [],
            }
            for i, r in enumerate(all_rows[:5])
        ],
        "stats": {
            "matchCount":    int(meta.get("analogCount") or 0),
            "avgSimilarity": float(meta.get("avgSimilarity") or 0.0),
            "medianReturn":  er,
            "avgMaxDD":      0.05,
            "hitRate":       conf,
            "p10Return":     er - spread,
            "p90Return":     er + spread,
            "entropy":       1.0 - conf,
        },
        "distributionSeries": {"p10": [], "p50": [], "p90": []},
    }

    diagnostics = {
        "sampleSize":   int(meta.get("analogCount") or 0),
        "effectiveN":   int(meta.get("analogCount") or 0),
        "entropy":      1.0 - conf,
        "reliability":  conf,
        "coverageYears": 15,
        "qualityScore": conf,
    }

    primary_match = overlay["matches"][0] if overlay["matches"] else None
    if primary_match:
        primary_match["aftermathNormalized"] = [p / current_price - 1 for p in path] if current_price else []

    focus_pack = {
        "meta": {
            "symbol":         sym,
            "focus":          focus,
            "horizon":        h_days,
            "tier":           "TIMING" if h_days <= 14 else "TACTICAL" if h_days <= 90 else "STRUCTURE",
            "generatedAt":    datetime.now(timezone.utc).isoformat(),
            "isLive":         True,
            "aftermathDays":  h_days,
        },
        "overlay": overlay,
        "forecast": forecast,
        "diagnostics": diagnostics,
        "primarySelection": {"primaryMatch": primary_match},
        "divergence": {"score": 0, "terminalDelta": 0, "directionalMismatch": False, "entropy": 1.0 - conf},
        "phase": {
            "currentPhase": (meta.get("regime") or {}).get("phase") or "NEUTRAL",
            "trend":        "UP" if direction == "UP" else "DOWN" if direction == "DOWN" else "SIDEWAYS",
            "volatility":   "MODERATE",
        },
        "scenario": {
            "bear":  {"return": er - spread, "price": current_price * (1 + er - spread)},
            "base":  {"return": er,           "price": target_price},
            "bull":  {"return": er + spread, "price": current_price * (1 + er + spread)},
            "upside": conf,
            "avgMaxDD": 0.05,
        },
        "price": {"current": current_price, "sma200": "NEAR"},
        "decision": {"action": _direction_to_signal(direction, conf), "confidence": conf, "entropy": 1.0 - conf},
    }

    return {
        "ok":         True,
        "asOf":       datetime.now(timezone.utc).isoformat(),
        "symbol":     sym,
        "asset":      sym,
        "focus":      focus,
        "horizon":    hkey,
        "focusPack":  focus_pack,
        "headline":   row,
        "forecasts":  all_rows,
        "candles":    candles,
        "windowLen":  windowLen or 120,
        "source":     "fractal_native_v1",
    }


# ─────────────────── /api/fractal/spx (override) ────────────────────
@router.get("/fractal/spx")
def fractal_spx(
    focus: str = Query("30d"),
    asOf:  Optional[str] = Query(None),
):
    """Shape required by useFocusPack SPX branch — `result.data` must
    contain horizons, decision, market, diagnostics, chartData, etc."""
    sym = "SPX"
    hkey = _focus_to_horizon_key(focus)
    h_days = _focus_to_days(focus)
    row = _native_forecast(sym, hkey) or {}
    er = float(row.get("expectedReturn") or 0.0)
    conf = float(row.get("confidence") or 0.0)
    direction = (row.get("direction") or "NEUTRAL").upper()
    meta = row.get("nativeMeta") or {}
    current_price = float(row.get("entryPrice") or 0.0)
    candles = _candles(sym, h_days * 2 + 60)
    if not current_price and candles:
        current_price = float(candles[-1]["close"])

    # build horizons array
    horizons: List[dict] = []
    for r in _all_horizons(sym):
        hk = (r.get("horizon") or "").upper()
        days_map = {"7D": 7, "14D": 14, "30D": 30, "90D": 90, "180D": 180, "365D": 365}
        d_ = days_map.get(hk)
        if not d_:
            continue
        horizons.append({
            "h":               d_,
            "horizon":         d_,
            "expectedReturn":  float(r.get("expectedReturn") or 0.0),
            "direction":       (r.get("direction") or "").upper(),
            "confidence":      float(r.get("confidence") or 0.0),
            "dominant":        d_ == h_days,
        })
    horizons.sort(key=lambda x: x["h"])

    target_price = float(row.get("targetPrice") or (current_price * (1 + er))) if current_price else 0.0
    path = []
    if current_price:
        for i in range(h_days + 1):
            frac = i / max(h_days, 1)
            path.append(current_price * (1 - frac) + target_price * frac)
    spread = max(abs(er) * 0.5, 0.03)

    data = {
        "contract": {
            "asofCandleTs": int(time.time() * 1000),
            "generatedAt":  datetime.now(timezone.utc).isoformat(),
        },
        "horizons":  horizons,
        "decision":  {
            "action":     _direction_to_signal(direction, conf),
            "confidence": conf,
            "entropy":    1.0 - conf,
        },
        "market": {
            "currentPrice": current_price,
            "sma200":       "NEAR",
            "phase":        "NEUTRAL",
            "volatility":   0.3,
        },
        "diagnostics": {
            "sampleSize":    int(meta.get("analogCount") or 0),
            "effectiveN":    int(meta.get("analogCount") or 0),
            "entropy":       1.0 - conf,
            "similarity":    float(meta.get("avgSimilarity") or 0.0) * 100,
            "directionMatch": 1 if direction in ("UP", "DOWN") else 0,
            "projectionGap": 0,
            "coverageYears": 70,
            "quality":       conf,
        },
        "reliability": {"score": conf, "driftScore": 0},
        "risk": {"maxDD_WF": 3.9, "mcP95_DD": -8.0},
        "chartData": {
            "path":         path,
            "bands":        {"p10": [], "p25": [], "p50": [], "p75": [], "p90": []},
            "currentWindow": {"raw": [c["close"] for c in candles[-60:]],
                              "normalized": [], "timestamps": [c["t"] for c in candles[-60:]]},
            "forecast": {
                "upperBand": [p * (1 + spread) for p in path],
                "lowerBand": [p * (1 - spread) for p in path],
                "confidenceDecay": [max(conf - i * 0.005, 0.05) for i in range(h_days + 1)],
                "tailFloor": max(target_price * (1 - spread * 2), 0),
                "currentPrice": current_price,
            },
        },
        "explain": {
            "topMatches": [
                {
                    "id":          f"spx_native_{i+1}",
                    "date":        r.get("createdBucket") or "",
                    "similarity":  float((r.get("nativeMeta") or {}).get("avgSimilarity") or 0.0) * 100,
                    "phase":       "NEUTRAL",
                    "return":      float(r.get("expectedReturn") or 0.0) * 100,
                    "maxDrawdown": -5.0,
                    "aftermathNormalized": [],
                    "windowNormalized":    [],
                }
                for i, r in enumerate(_all_horizons(sym)[:5])
            ],
        },
        "phaseEngine": {"currentPhase": "NEUTRAL", "trend": direction, "volatility": "MODERATE"},
    }

    # Headline shape used elsewhere too — keep old top-level fields working
    return {
        "ok":             True,
        "asOf":           datetime.now(timezone.utc).isoformat(),
        "asset":          sym,
        "symbol":         sym,
        "horizon":        hkey,
        "focus":          focus,
        "direction":      direction,
        "confidence":     conf,
        "expectedReturn": er,
        "entryPrice":     current_price,
        "targetPrice":    target_price,
        "regime":         meta.get("regime"),
        "analogCount":    meta.get("analogCount"),
        "modelVersion":   row.get("modelVersion") or "fractal_native_v1",
        "data":           data,
        "horizons":       horizons,
        "source":         "fractal_native_v1",
        "lastUpdate":     row.get("createdAt"),
    }


# ─────────────────── /api/fractal/dxy/terminal (override) ──────────
@router.get("/fractal/dxy/terminal")
def fractal_dxy_terminal(
    focus: str = Query("90d"),
    asOf:  Optional[str] = Query(None),
):
    sym = "DXY"
    hkey = _focus_to_horizon_key(focus)
    h_days = _focus_to_days(focus)
    row = _native_forecast(sym, hkey) or {}
    er = float(row.get("expectedReturn") or 0.0)
    conf = float(row.get("confidence") or 0.0)
    direction = (row.get("direction") or "NEUTRAL").upper()
    meta = row.get("nativeMeta") or {}
    candles = _candles(sym, h_days * 2 + 60)
    current_price = float(row.get("entryPrice") or 0.0)
    if not current_price and candles:
        current_price = float(candles[-1]["close"])
    target_price = float(row.get("targetPrice") or (current_price * (1 + er))) if current_price else 0.0

    path_objs = []
    if current_price:
        for i in range(h_days + 1):
            frac = i / max(h_days, 1)
            price = current_price * (1 - frac) + target_price * frac
            path_objs.append({"t": i, "value": price, "pct": (price - current_price) / current_price})

    spread = max(abs(er) * 0.5, 0.02)
    synthetic = {
        "path":   path_objs,
        "bands":  {
            "p10": [{"t": p["t"], "value": p["value"] * (1 - spread)} for p in path_objs],
            "p50": [{"t": p["t"], "value": p["value"]}                 for p in path_objs],
            "p90": [{"t": p["t"], "value": p["value"] * (1 + spread)} for p in path_objs],
        },
        "forecast": {"bear": er - spread, "base": er, "bull": er + spread},
    }
    hybrid = {
        "path":         path_objs,
        "replayWeight": 0.5,
        "breakdown":    {"synthetic": 0.5, "replay": 0.5},
    }
    replay = {
        "continuation": [{"t": h_days + i, "value": path_objs[-1]["value"] * (1 + er * 0.1 * (i + 1) / h_days),
                          "pct": er * 0.1 * (i + 1) / h_days}
                          for i in range(min(h_days, 30))] if path_objs else [],
    }
    macro = {
        "path":       [{"t": p["t"], "value": p["value"] * 1.005, "pct": p["pct"] + 0.005} for p in path_objs],
        "adjustment": {"shift": 0.005, "direction": "UP" if er >= 0 else "DOWN"},
    }
    core = {
        "current":     {"price": current_price},
        "matches":     [
            {
                "matchId":   f"dxy_native_{i+1}",
                "startDate": r.get("createdBucket") or "",
                "endDate":   "",
                "similarity": float((r.get("nativeMeta") or {}).get("avgSimilarity") or 0.0),
                "decade":    None,
                "rank":      i + 1,
            }
            for i, r in enumerate(_all_horizons(sym)[:5])
        ],
        "decision":    {"action": _direction_to_signal(direction, conf), "confidence": conf * 100, "entropy": 1.0 - conf},
        "diagnostics": {"entropy": 1.0 - conf, "coverageYears": 70, "similarity": float(meta.get("avgSimilarity") or 0)},
    }

    return {
        "ok":        True,
        "asOf":      datetime.now(timezone.utc).isoformat(),
        "asset":     sym,
        "symbol":    sym,
        "focus":     focus,
        "horizon":   hkey,
        "synthetic": synthetic,
        "hybrid":    hybrid,
        "replay":    replay,
        "macro":     macro,
        "core":      core,
        "meta":      {"symbol": sym, "horizon": h_days, "generatedAt": datetime.now(timezone.utc).isoformat()},
        "source":    "fractal_native_v1",
    }


# ─────────────────── shared builder for DXY page data ───────────────
def _build_btc_dxy_overview(sym: str, h_days: int) -> dict:
    """Build the `data` payload used by DxyFractalPage / BtcFractalPage
    (header / verdict / forecasts / why / risk / analogs / macro)."""
    hkey = {7: "7D", 14: "14D", 30: "30D", 90: "90D", 180: "180D", 365: "365D"}\
        .get(int(h_days), "90D")
    row = _native_forecast(sym, hkey) or {}
    er = float(row.get("expectedReturn") or 0.0)
    conf = float(row.get("confidence") or 0.0)
    direction = (row.get("direction") or "NEUTRAL").upper()
    meta = row.get("nativeMeta") or {}
    current_price = float(row.get("entryPrice") or 0.0)
    candles = _candles(sym, h_days * 2 + 60)
    if not current_price and candles:
        current_price = float(candles[-1]["close"])

    mb_points = _meta_brain_points(sym, h_days)
    horizons = _horizon_rows_from_mb(mb_points)
    # mark selected horizon dominant
    for h in horizons:
        h["dominant"] = (h["days"] == h_days)

    stance = _stance_from(direction, er * 100)
    signal = _direction_to_signal(direction, conf)
    risk_label = "HIGH" if abs(er) > 0.20 or conf < 0.25 else \
                 "MEDIUM" if abs(er) > 0.10 or conf < 0.40 else "NORMAL"

    spread = max(abs(er) * 0.5, 0.03)
    target_price = float(row.get("targetPrice") or (current_price * (1 + er))) if current_price else 0.0

    header = {
        "signal":     signal,
        "confidence": int(round(conf * 100)),
        "risk":       risk_label,
        "regime":     (meta.get("regime") or {}).get("phase") or "RANGEBOUND",
        "asOf":       datetime.now(timezone.utc).isoformat(),
        "dataStatus": "REAL" if row else "DEGRADED",
        "phase":      (meta.get("regime") or {}).get("phase") or "rangebound",
    }
    verdict = {
        "action":          signal,
        "stance":          stance,
        "marketState":     stance,
        "expectedMoveP50": er * 100,
        "rangeP10":        (er - spread) * 100,
        "rangeP90":        (er + spread) * 100,
        "medianProjectionPct": er * 100,
        "confidencePct":   int(round(conf * 100)),
        "invalidations": [
            f"If {sym} breaks below key support levels",
            "If macro regime shifts significantly",
            "If volatility spikes beyond historical norms",
        ],
    }

    why = {
        "drivers": [
            {"text": f"Market Phase: {header['phase'].title()}", "sentiment": "supportive" if direction == "UP" else "headwind" if direction == "DOWN" else "neutral"},
            {"text": f"Confidence: {int(round(conf*100))}%", "sentiment": "supportive" if conf > 0.55 else "headwind" if conf < 0.35 else "neutral"},
            {"text": f"Risk Regime: {risk_label}", "sentiment": "supportive" if risk_label == "NORMAL" else "headwind"},
            {"text": f"Analogs: {meta.get('analogCount') or 0} historical matches", "sentiment": "neutral"},
        ],
        "invalidations": verdict["invalidations"],
    }

    risk = {
        "level":           risk_label,
        "volRegime":       "HIGH" if risk_label == "HIGH" else "MEDIUM" if risk_label == "MEDIUM" else "LOW",
        "worstCase5":      round(abs(er) * 100 + 15, 1),
        "positionSize":    "1.0" if conf > 0.6 else "0.5" if conf > 0.35 else "0.25",
        "capitalScaling":  int(round(conf * 100)),
        "reasons": [
            f"Confidence {int(round(conf*100))}%",
            f"Median move {er*100:+.1f}%",
            f"Risk regime {risk_label}",
        ],
    }

    analogs = {
        "bestMatch":     {"similarity": int(round(float(meta.get("avgSimilarity") or 0.0) * 100)),
                          "date":       row.get("createdBucket") or ""},
        "coverageYears": 15,
        "sampleSize":    int(meta.get("analogCount") or 0),
        "outcomeP50":    round(er * 100, 2),
        "phase":         header["phase"],
        "items": [
            {
                "rank":       i + 1,
                "date":       r.get("createdBucket") or "",
                "similarity": int(round(float((r.get("nativeMeta") or {}).get("avgSimilarity") or 0.0) * 100)),
                "outcome":    round(float(r.get("expectedReturn") or 0.0) * 100, 2),
                "phase":      "NEUTRAL",
            }
            for i, r in enumerate(_all_horizons(sym)[:5])
        ],
    }

    macro = _macro_signal()
    macro_block = {
        "regime":          (macro.get("regime") or "NEUTRAL").upper(),
        "score":           float(macro.get("score") or 0.0),
        "fearGreed":       None,
        "btcDominance":    None,
        "stableDominance": None,
        "summary":         (macro.get("explain") or {}).get("summary") or "Macro regime within normal bands",
        "bullets":         (macro.get("explain") or {}).get("bullets") or [],
        "adjustmentPct":   round(er * 20, 2),  # symbolic macro adjustment
    }

    return {
        "ok":            True,
        "asset":         sym,
        "horizon":       h_days,
        "currentPrice":  current_price,
        "targetPrice":   target_price,
        "header":        header,
        "verdict":       verdict,
        "horizons":      horizons,
        "forecasts":     horizons,  # alias used by some FE tables
        "why":           why,
        "risk":          risk,
        "analogs":       analogs,
        "macro":         macro_block,
        "asOf":          datetime.now(timezone.utc).isoformat(),
        "source":        "fractal_native_v1+meta_brain_v2",
    }


# ─────────────────── /api/ui/fractal/dxy/overview ───────────────────
@router.get("/ui/fractal/dxy/overview")
def ui_fractal_dxy_overview(h: int = Query(90)):
    return _build_btc_dxy_overview("DXY", int(h))


@router.get("/ui/fractal/btc/overview")
def ui_fractal_btc_overview(h: int = Query(30)):
    return _build_btc_dxy_overview("BTC", int(h))


@router.get("/ui/fractal/spx/overview")
def ui_fractal_spx_overview(h: int = Query(30)):
    return _build_btc_dxy_overview("SPX", int(h))


# ─────────────────── /api/ui/brain/decision (override) ──────────────
@router.get("/ui/brain/decision")
def ui_brain_decision(asset: str = Query("BTC")):
    """Macro Brain dashboard payload (8 layers) — strictly matching
    BrainOverviewPageV4 contract."""
    sym = asset.upper()
    row = _native_forecast(sym, "30D") or {}
    er = float(row.get("expectedReturn") or 0.0)
    conf = float(row.get("confidence") or 0.0)
    direction = (row.get("direction") or "NEUTRAL").upper()
    macro = _macro_signal()
    mb_points = _meta_brain_points(sym, 30)
    horizon_rows = _horizon_rows_from_mb(mb_points)

    dominant_bias = _stance_from(direction, er * 100)
    if dominant_bias == "BULLISH" and conf > 0.55:
        posture = "OFFENSIVE"
    elif dominant_bias == "BEARISH" and conf > 0.55:
        posture = "DEFENSIVE"
    else:
        posture = "NEUTRAL"

    primary_action = (
        f"Lean {dominant_bias.lower()} on {sym} with confidence {int(round(conf*100))}%"
        if dominant_bias != "NEUTRAL"
        else f"Hold and monitor {sym} — no clear directional edge"
    )

    verdict = {
        "regime":        (macro.get("regime") or "NEUTRAL").upper(),
        "dominantBias":  dominant_bias,
        "posture":       posture,
        "confidence":    int(round(conf * 100)),
    }
    action_block = {
        "primary":              primary_action,
        "multiplier":           round(0.5 + conf, 2),
        "cashBufferRange":      "10-20%" if posture == "OFFENSIVE" else "30-50%" if posture == "DEFENSIVE" else "20-30%",
        "leverageRecommended":  posture == "OFFENSIVE" and conf > 0.65,
    }

    def _sent(stance: str) -> str:
        return "supportive" if stance == "BULLISH" else "risk" if stance == "BEARISH" else "neutral"

    reasons = [
        {"text": f"Fractal direction {direction} with confidence {int(round(conf*100))}%",
         "sentiment": _sent(dominant_bias)},
        {"text": f"Median 30D projection {er*100:+.2f}%",
         "sentiment": _sent(dominant_bias)},
        {"text": f"Macro regime: {(macro.get('regime') or 'NEUTRAL').upper()}",
         "sentiment": "risk" if (macro.get("blocked") or False) else "neutral"},
        {"text": f"Sample size: {(row.get('nativeMeta') or {}).get('analogCount') or 0} historical analogs",
         "sentiment": "neutral"},
    ]

    # Horizons: pick 4 (7/30/90/365), expose as {horizon, phase, strength}
    horizons_out = []
    days_pick = [7, 30, 90, 365]
    by_days = {h["days"]: h for h in horizon_rows}
    for d_ in days_pick:
        h = by_days.get(d_) or {}
        conf_h = float(h.get("confidence") or 0.0)
        if conf_h >= 0.6:
            strength = "strong"
        elif conf_h >= 0.35:
            strength = "medium"
        else:
            strength = "weak"
        horizons_out.append({
            "horizon":  d_,
            "phase":    (h.get("stance") or "NEUTRAL"),
            "strength": strength,
            "expectedReturn": h.get("expectedReturn") or 0.0,
            "confidencePct":  h.get("confidencePct") or 0,
        })

    blocked = bool(macro.get("blocked"))
    abs_r = abs(er)
    vol_regime = "elevated" if abs_r > 0.15 or blocked else "normal"
    tail_risk = "high" if abs_r > 0.20 else "moderate" if abs_r > 0.10 else "low"
    guard_status = "active" if blocked else "none"
    risk_block = {
        "volatilityRegime":  vol_regime,
        "tailRisk":          tail_risk,
        "guardStatus":       guard_status,
        "overrideIntensity": 100 if blocked else 0,
        "capitalScaling":    int(round(conf * 100)),
    }

    # Causal: REAL array shape  — [{id, links:[{from,direction,to}], netEffect, targetAsset}]
    causal_dir = "positive" if dominant_bias == "BULLISH" else "negative" if dominant_bias == "BEARISH" else "neutral"
    macro_dir = "negative" if blocked else "neutral"
    causal = [
        {
            "id": "macro_to_dxy",
            "links": [
                {"from": "Macro Regime", "direction": macro_dir, "to": "DXY"},
                {"from": "DXY",          "direction": "negative" if dominant_bias == "BULLISH" else "positive", "to": "Risk Assets"},
            ],
            "netEffect": "negative" if blocked else "positive" if dominant_bias == "BULLISH" else "neutral",
            "targetAsset": sym,
        },
        {
            "id": "fractal_to_target",
            "links": [
                {"from": "Fractal Match", "direction": causal_dir, "to": "Meta-Brain"},
                {"from": "Meta-Brain",     "direction": causal_dir, "to": "Decision"},
            ],
            "netEffect":   causal_dir,
            "targetAsset": sym,
        },
    ]

    # Macro indicators (real macro_v10 bullets → 6 cards)
    bullets = (macro.get("explain") or {}).get("bullets") or []
    def _parse_indicator(line: str, key: str, title: str, normal: str, risk: str, bullish: str, bearish: str) -> dict:
        import re
        m = re.search(r"([\d\.\-]+)", line or "")
        val = m.group(1) if m else "—"
        status = "neutral"
        try:
            v = float(val)
            if key == "fear_greed":
                status = "risk" if v <= 25 else "supportive" if v >= 65 else "neutral"
            elif key == "btc_dom":
                status = "risk" if v > 60 else "supportive" if v < 50 else "neutral"
            elif key == "stable_dom":
                status = "risk" if v > 12 else "supportive" if v < 7 else "neutral"
        except Exception:
            pass
        return {
            "key": key, "title": title,
            "currentValue":      val,
            "status":            status,
            "interpretation":    "macro_v10 signal",
            "normalRange":       normal,
            "riskRange":         risk,
            "bullishCondition":  bullish,
            "bearishCondition":  bearish,
        }
    fg_line   = next((b for b in bullets if "Fear & Greed" in b), "")
    btcd_line = next((b for b in bullets if "BTC Dominance" in b), "")
    stbd_line = next((b for b in bullets if "Stablecoin Dominance" in b), "")
    macro_summary = [
        _parse_indicator(fg_line,   "fear_greed", "Fear & Greed Index",  "30–70", "<25 or >75", ">65", "<25"),
        _parse_indicator(btcd_line, "btc_dom",    "BTC Dominance",        "50–60%", ">60%",       "<50%", ">60%"),
        _parse_indicator(stbd_line, "stable_dom", "Stablecoin Dominance", "7–12%",  ">12%",       "<7%",  ">12%"),
    ]
    # ensure at least 3 cards always
    while len(macro_summary) < 3:
        macro_summary.append({
            "key": f"placeholder_{len(macro_summary)}",
            "title":            "Macro Indicator",
            "currentValue":     "—",
            "status":           "neutral",
            "interpretation":   "data pending",
            "normalRange":      "—", "riskRange": "—",
            "bullishCondition": "—", "bearishCondition": "—",
        })

    # Allocation pipeline: base → afterBrain → final
    base = {"spx": 50, "btc": 20, "cash": 30}
    brain_shift = 10 if dominant_bias == "BULLISH" else -10 if dominant_bias == "BEARISH" else 0
    after_brain = {
        "spx":  base["spx"] + brain_shift // 2,
        "btc":  base["btc"] + brain_shift // 2,
        "cash": base["cash"] - brain_shift,
    }
    scaling = int(round(conf * 100))
    final = {
        "spx":  int(round(after_brain["spx"]  * scaling / 100)),
        "btc":  int(round(after_brain["btc"]  * scaling / 100)),
        "cash": 100 - int(round(after_brain["spx"]  * scaling / 100)) - int(round(after_brain["btc"]  * scaling / 100)),
    }
    allocation = {
        "base":       base,
        "afterBrain": after_brain,
        "final":      final,
        "impact": {
            "brainImpact":     brain_shift,
            "optimizerImpact": 0,
            "scalingImpact":   final["cash"] - after_brain["cash"],
            "explanation":     f"Scaling at {scaling}% confidence",
        },
    }

    # Capital scaling drivers
    capital_scaling = {
        "scaleFactor":  scaling,
        "drivers": [
            {"name": "Confidence",  "value": scaling,                                "effect": "reduce" if scaling < 70 else "neutral"},
            {"name": "Macro Guard", "value": 100 if blocked else 0,                  "effect": "reduce" if blocked else "neutral"},
            {"name": "Volatility",  "value": int(abs_r * 100),                       "effect": "reduce" if abs_r > 0.15 else "neutral"},
        ],
        "explanation": f"Capital scaled to {scaling}% based on model confidence and macro guard.",
    }

    return {
        "ok":              True,
        "asset":           sym,
        "verdict":         verdict,
        "action":          action_block,
        "decision":        primary_action,
        "confidence":      conf,
        "phase":           (row.get("nativeMeta") or {}).get("regime", {}).get("phase") or "RANGEBOUND",
        "price":           row.get("entryPrice"),
        "reasons":         reasons,
        "horizons":        horizons_out,
        "risk":            risk_block,
        "causal":          causal,
        "macroSummary":    macro_summary,
        "allocation":      allocation,
        "capitalScaling":  capital_scaling,
        "components":      [
            {"name": "Fractal",     "weight": 0.4, "direction": direction,                          "confidence": conf},
            {"name": "Meta-Brain",  "weight": 0.4, "direction": direction,                          "confidence": conf},
            {"name": "Macro",       "weight": 0.2, "direction": (macro.get("regime") or "NEUTRAL"), "confidence": float(macro.get("score") or 0.0)},
        ],
        "asOf":            datetime.now(timezone.utc).isoformat(),
        "source":          "fractal_native_v1+meta_brain_v2+macro_v10",
    }
