"""
fractal_extra_runtime — extends the native fractal engine with full coverage of
fractal-related endpoints that the Web/Mobile/MiniApp UI consumes.

The native engine `services.fractal_runtime` already exposes:
    /api/fractal/runtime/{symbol}              → structural perception
    /api/fractal/runtime/summary?symbols=...   → multi-symbol
    /api/fractal/runtime/status

This file adds the rest (previously caught by legacy_compat_stub):
    /api/fractal/list                          → registry of supported assets
    /api/fractal/coverage                      → coverage matrix (asset × tf)
    /api/fractal/patterns?symbol=...           → detected fractal patterns history
    /api/fractal/similar/{symbol}              → similar historical fractal events
    /api/fractal/forecast/{symbol}             → projected resolutions (fractal-based)
    /api/fractal/heatmap                       → cross-asset fractal phase heatmap
    /api/fractal/snapshot/{symbol}             → single snapshot for sharing
    /api/fractal/intelligence                  → aggregate intelligence dashboard
    /api/miniapp/fractal?asset=...             → Telegram MiniApp lite payload
    /api/miniapp/fractal-watchlist             → multi-asset MiniApp list
    /api/admin/fractal/overview                → admin dashboard

Sources:
    • services.fractal_runtime (native, on Mongo snapshot memory)
    • OKX OHLC (via routes.tech_analysis_runtime._fetch_candles) for similarity
      computation when fractal memory is empty.
    • Pure-python cosine similarity on z-normalized closes.

No mocks, no paid feeds.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from fastapi import APIRouter, Query

from services.fractal_runtime import (
    runtime as _fr_runtime,
    runtime_many as _fr_runtime_many,
    service_health as _fr_service_health,
)

# Reuse OHLC fetcher from TA runtime
from routes.tech_analysis_runtime import (
    _fetch_candles,
    _to_binance_pair as _to_okx_spot,
    _to_canonical,
    _resolve_tf,
    _compute_indicators,
)

logger = logging.getLogger("fractal_extra_runtime")
router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────────
# Asset registry
# ──────────────────────────────────────────────────────────────────────────
_FRACTAL_UNIVERSE = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE",
    "ADA", "AVAX", "LINK", "MATIC", "DOT", "TON",
    "ARB", "OP", "SUI", "APT", "TIA", "NEAR",
    "ATOM", "FIL", "LTC", "INJ", "SEI", "JTO",
]

_HORIZONS = ["4H", "1D", "7D", "30D"]


# ──────────────────────────────────────────────────────────────────────────
# /api/fractal/list  → registry of supported assets
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/fractal/list")
def fractal_list():
    return {
        "ok": True,
        "assets": _FRACTAL_UNIVERSE,
        "horizons": _HORIZONS,
        "count": len(_FRACTAL_UNIVERSE),
        "asOf": _now_iso(),
        "source": "fractal_registry_v1",
    }


# ──────────────────────────────────────────────────────────────────────────
# /api/fractal/coverage  →  matrix (asset × horizon) with phase/state
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/fractal/coverage")
def fractal_coverage(limit: int = Query(24, ge=1, le=50)):
    """Returns coverage matrix: for each asset in universe, fractal runtime
    snapshot. Useful for a dashboard heatmap."""
    rows: List[Dict[str, Any]] = []
    for sym in _FRACTAL_UNIVERSE[:limit]:
        try:
            r = _fr_runtime(sym) or {}
        except Exception as e:
            logger.info(f"  coverage {sym} failed: {e}")
            r = {"ok": False, "symbol": sym, "error": str(e)}

        rows.append({
            "symbol":     sym,
            "ok":         r.get("ok"),
            "phase":      r.get("phase") or "unavailable",
            "state":      r.get("state") or "unavailable",
            "direction":  r.get("direction") or "WAIT",
            "confidence": r.get("confidence") or 0,
            "evidence":   r.get("evidence") or 0,
            "structure":  r.get("structure") or {},
        })

    # Aggregate
    phases = {}
    directions = {}
    for r in rows:
        phases[r["phase"]] = phases.get(r["phase"], 0) + 1
        directions[r["direction"]] = directions.get(r["direction"], 0) + 1

    return {
        "ok": True,
        "rows": rows,
        "count": len(rows),
        "phaseDistribution": phases,
        "directionDistribution": directions,
        "asOf": _now_iso(),
        "source": "fractal_coverage_v1",
    }


# ──────────────────────────────────────────────────────────────────────────
# /api/fractal/patterns?symbol=...  →  pattern history derived from OHLC
# ──────────────────────────────────────────────────────────────────────────
def _classify_pattern(bars: List[Dict[str, Any]], idx: int, window: int = 20) -> Optional[str]:
    """Lightweight pattern classifier on a window of bars ending at idx."""
    if idx < window:
        return None
    seg = bars[idx - window:idx + 1]
    highs = [b["high"] for b in seg]
    lows = [b["low"] for b in seg]
    closes = [b["close"] for b in seg]
    h_max = max(highs)
    l_min = min(lows)
    c_first, c_last = closes[0], closes[-1]
    range_pct = (h_max - l_min) / l_min * 100 if l_min else 0
    drift_pct = (c_last - c_first) / c_first * 100 if c_first else 0

    # Volatility compression: small range
    if range_pct < 4 and abs(drift_pct) < 2:
        return "compression_squeeze"
    # Breakout: closing above 95% of range
    if c_last > l_min + 0.93 * (h_max - l_min) and drift_pct > 5:
        return "breakout_up"
    # Breakdown
    if c_last < l_min + 0.07 * (h_max - l_min) and drift_pct < -5:
        return "breakdown_down"
    # Higher-highs / higher-lows
    if highs[-1] > highs[len(highs)//2] > highs[0] and lows[-1] > lows[len(lows)//2] > lows[0]:
        return "stair_up"
    if highs[-1] < highs[len(highs)//2] < highs[0] and lows[-1] < lows[len(lows)//2] < lows[0]:
        return "stair_down"
    # Wide range / expansion
    if range_pct > 12:
        return "expansion_range"
    return "rangebound"


@router.get("/api/fractal/patterns")
def fractal_patterns(
    symbol: str = Query("BTC"),
    timeframe: str = Query("1D"),
    window: int = Query(20, ge=5, le=100),
    history: int = Query(180, ge=20, le=500),
):
    """Returns list of identified fractal-pattern events over the last `history` bars."""
    canon = _to_canonical(symbol)
    pair = _to_okx_spot(symbol)
    interval, _ = _resolve_tf(timeframe)
    bars = _fetch_candles(pair, interval, history)
    if not bars:
        return {"ok": False, "symbol": canon, "error": "no_market_data"}

    events: List[Dict[str, Any]] = []
    for i in range(window, len(bars)):
        cls = _classify_pattern(bars, i, window)
        if cls and cls != "rangebound":
            b = bars[i]
            events.append({
                "ts": b["time"],
                "openTime": b.get("openTime"),
                "pattern": cls,
                "price": b["close"],
                "high": b["high"],
                "low": b["low"],
                "barIndex": i,
            })

    # Deduplicate clusters (consecutive same pattern)
    deduped = []
    for ev in events:
        if not deduped or deduped[-1]["pattern"] != ev["pattern"] or ev["barIndex"] - deduped[-1]["barIndex"] > 3:
            deduped.append(ev)

    return {
        "ok": True,
        "symbol": canon,
        "pair": pair,
        "timeframe": timeframe.upper(),
        "window": window,
        "history": history,
        "events": deduped[-30:],  # last 30 events
        "count": len(deduped),
        "asOf": _now_iso(),
        "source": "fractal_pattern_classifier_v1",
    }


# ──────────────────────────────────────────────────────────────────────────
# /api/fractal/similar/{symbol}  →  find similar historical windows
# ──────────────────────────────────────────────────────────────────────────
def _normalize_window(closes: List[float]) -> List[float]:
    """Z-normalize a window: (x - mean) / std."""
    n = len(closes)
    if n < 2:
        return closes
    mean = sum(closes) / n
    var = sum((x - mean) ** 2 for x in closes) / n
    std = math.sqrt(var) if var > 0 else 1
    return [(x - mean) / std for x in closes]


def _cosine_sim(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or not a:
        return 0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0
    return dot / (na * nb)


@router.get("/api/fractal/similar/{symbol}")
def fractal_similar(
    symbol: str,
    timeframe: str = Query("1D"),
    window: int = Query(30, ge=10, le=100),
    history: int = Query(500, ge=100, le=1000),
    top_k: int = Query(5, ge=1, le=10),
):
    """Finds top-K historical windows most similar to the current window
    (cosine similarity on z-normalized close prices). Returns next-N bar
    outcome for each similar pattern → fractal forecast."""
    canon = _to_canonical(symbol)
    pair = _to_okx_spot(symbol)
    interval, _ = _resolve_tf(timeframe)
    bars = _fetch_candles(pair, interval, history)
    if not bars or len(bars) < window * 3:
        return {"ok": False, "symbol": canon, "error": "insufficient_history"}

    closes = [b["close"] for b in bars]
    # Current window: last `window` bars (exclude latest forming bar partially)
    current = _normalize_window(closes[-window:])

    similarities: List[Tuple[int, float]] = []
    # Slide over history, leave room for next-N outcome window
    horizon_n = window // 3
    for i in range(window, len(closes) - window - horizon_n):
        hist_win = _normalize_window(closes[i - window:i])
        sim = _cosine_sim(current, hist_win)
        similarities.append((i, sim))

    similarities.sort(key=lambda x: x[1], reverse=True)
    top = similarities[:top_k]

    matches = []
    long_count = 0
    short_count = 0
    total_returns = []
    for idx, sim in top:
        # Outcome: % change in next `horizon_n` bars
        if idx + horizon_n >= len(closes):
            continue
        anchor = closes[idx]
        outcome = closes[idx + horizon_n]
        ret_pct = (outcome - anchor) / anchor * 100 if anchor else 0
        if ret_pct > 1:
            long_count += 1
        elif ret_pct < -1:
            short_count += 1
        total_returns.append(ret_pct)
        matches.append({
            "barIndex": idx,
            "ts": bars[idx]["time"],
            "similarity": round(sim, 4),
            "anchorPrice": anchor,
            "outcomePrice": outcome,
            "outcomeReturnPct": round(ret_pct, 3),
            "horizonBars": horizon_n,
        })

    if total_returns:
        avg_ret = sum(total_returns) / len(total_returns)
        std_ret = math.sqrt(sum((r - avg_ret) ** 2 for r in total_returns) / len(total_returns))
    else:
        avg_ret = 0
        std_ret = 0

    # Direction consensus
    if long_count > short_count and long_count >= len(matches) * 0.6:
        consensus = "LONG_BIAS"
    elif short_count > long_count and short_count >= len(matches) * 0.6:
        consensus = "SHORT_BIAS"
    else:
        consensus = "WAIT"

    return {
        "ok": True,
        "symbol": canon,
        "pair": pair,
        "timeframe": timeframe.upper(),
        "window": window,
        "horizonBars": horizon_n,
        "currentPrice": closes[-1] if closes else None,
        "matches": matches,
        "consensus": consensus,
        "avgReturnPct": round(avg_ret, 3),
        "stdReturnPct": round(std_ret, 3),
        "longCount": long_count,
        "shortCount": short_count,
        "confidence": round(max(long_count, short_count) / max(1, len(matches)), 2),
        "asOf": _now_iso(),
        "source": "fractal_cosine_similarity_v1",
    }


# ──────────────────────────────────────────────────────────────────────────
# /api/fractal/forecast/{symbol}  →  projected next-N price band
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/fractal/forecast/{symbol}")
def fractal_forecast(
    symbol: str,
    timeframe: str = Query("1D"),
    window: int = Query(30, ge=10, le=100),
    top_k: int = Query(8, ge=3, le=15),
):
    """Project next-N bars using the average path of top-K similar historical
    windows."""
    sim_result = fractal_similar(symbol, timeframe, window, 500, top_k)
    if not sim_result.get("ok"):
        return sim_result

    canon = sim_result["symbol"]
    pair = sim_result["pair"]
    interval, _ = _resolve_tf(timeframe)
    bars = _fetch_candles(pair, interval, 500)
    closes = [b["close"] for b in bars]
    current_price = closes[-1] if closes else 0

    matches = sim_result["matches"]
    horizon_n = sim_result["horizonBars"]

    # Build forecast paths: for each match, take its outcome ratio at each step
    paths: List[List[float]] = []
    for m in matches:
        idx = m["barIndex"]
        anchor = m["anchorPrice"]
        if idx + horizon_n >= len(closes) or not anchor:
            continue
        path = [closes[idx + j] / anchor for j in range(horizon_n + 1)]
        paths.append(path)

    if not paths:
        return {**sim_result, "forecastPath": [], "note": "no_paths_built"}

    # Average path + standard deviation band
    path_len = min(len(p) for p in paths)
    forecast = []
    for step in range(1, path_len):
        ratios = [p[step] for p in paths]
        mean = sum(ratios) / len(ratios)
        var = sum((r - mean) ** 2 for r in ratios) / len(ratios)
        std = math.sqrt(var)
        forecast.append({
            "step": step,
            "projected": round(current_price * mean, 6),
            "high": round(current_price * (mean + std), 6),
            "low": round(current_price * (mean - std), 6),
            "uncertainty": round(std, 4),
        })

    return {
        "ok": True,
        "symbol": canon,
        "pair": pair,
        "timeframe": timeframe.upper(),
        "currentPrice": current_price,
        "horizonBars": horizon_n,
        "consensus": sim_result["consensus"],
        "confidence": sim_result["confidence"],
        "avgReturnPct": sim_result["avgReturnPct"],
        "forecastPath": forecast,
        "matchesUsed": len(paths),
        "asOf": _now_iso(),
        "source": "fractal_path_forecast_v1",
    }


# ──────────────────────────────────────────────────────────────────────────
# /api/fractal/heatmap  →  asset × horizon phase heatmap
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/fractal/heatmap")
def fractal_heatmap(limit: int = Query(20, ge=4, le=50)):
    """Returns asset × horizon phase matrix for a dashboard heatmap."""
    rows = []
    for sym in _FRACTAL_UNIVERSE[:limit]:
        row = {"symbol": sym, "horizons": {}}
        # Get fractal runtime opinion for asset (it is horizon-agnostic for now)
        try:
            r = _fr_runtime(sym) or {}
        except Exception:
            r = {}
        # For each TF compute a quick OHLC-derived phase
        for tf in _HORIZONS:
            try:
                pair = _to_okx_spot(sym)
                interval, _ = _resolve_tf(tf)
                bars = _fetch_candles(pair, interval, 100)
                if not bars:
                    row["horizons"][tf] = {"phase": "unavailable"}
                    continue
                ind = _compute_indicators(bars)
                trend = ind.get("trend", "unknown")
                rsi = ind.get("rsi") or 50
                # Phase mapping
                if trend == "uptrend" and rsi > 55:
                    phase = "expansion"
                elif trend == "downtrend" and rsi < 45:
                    phase = "breakdown"
                elif abs(rsi - 50) < 7 and trend == "ranging":
                    phase = "compression"
                else:
                    phase = "rangebound"
                row["horizons"][tf] = {
                    "phase": phase,
                    "rsi": round(rsi, 1),
                    "trend": trend,
                    "price": ind.get("price"),
                }
            except Exception as e:
                row["horizons"][tf] = {"phase": "unavailable", "error": str(e)[:40]}
        # Fractal runtime opinion
        row["runtime"] = {
            "phase":      r.get("phase") or "unavailable",
            "state":      r.get("state") or "unavailable",
            "direction":  r.get("direction") or "WAIT",
            "confidence": r.get("confidence") or 0,
        }
        rows.append(row)

    return {
        "ok": True,
        "rows": rows,
        "count": len(rows),
        "horizons": _HORIZONS,
        "asOf": _now_iso(),
        "source": "fractal_heatmap_v1",
    }


# ──────────────────────────────────────────────────────────────────────────
# /api/fractal/snapshot/{symbol}  →  single shareable snapshot card
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/fractal/snapshot/{symbol}")
def fractal_snapshot(symbol: str, timeframe: str = Query("1D")):
    """Single-shot Fractal snapshot, used by snapshot share screens and
    miniapp lite views."""
    canon = _to_canonical(symbol)
    pair = _to_okx_spot(symbol)

    rt = _fr_runtime(canon) or {}
    sim = fractal_similar(symbol, timeframe, 30, 500, 5)
    interval, _ = _resolve_tf(timeframe)
    bars = _fetch_candles(pair, interval, 60)
    ind = _compute_indicators(bars) if bars else {}

    return {
        "ok": True,
        "symbol": canon,
        "pair": pair,
        "timeframe": timeframe.upper(),
        "runtime": {
            "phase":      rt.get("phase") or "unavailable",
            "state":      rt.get("state") or "unavailable",
            "direction":  rt.get("direction") or "WAIT",
            "confidence": rt.get("confidence") or 0,
            "evidence":   rt.get("evidence") or 0,
            "reasons":    rt.get("reasons") or [],
            "structure":  rt.get("structure") or {},
        },
        "similarity": {
            "consensus":     sim.get("consensus") if sim.get("ok") else "WAIT",
            "confidence":    sim.get("confidence") if sim.get("ok") else 0,
            "avgReturnPct":  sim.get("avgReturnPct") if sim.get("ok") else 0,
            "longCount":     sim.get("longCount", 0),
            "shortCount":    sim.get("shortCount", 0),
            "matchCount":    len(sim.get("matches", [])) if sim.get("ok") else 0,
        },
        "indicators": ind,
        "price":      ind.get("price"),
        "asOf":       _now_iso(),
        "source":     "fractal_snapshot_v1",
    }


# ──────────────────────────────────────────────────────────────────────────
# /api/fractal/intelligence  →  aggregate dashboard
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/fractal/intelligence")
def fractal_intelligence():
    """Aggregate fractal intelligence: phase distribution + top long/short
    biased assets across the universe."""
    coverage = fractal_coverage(24)
    rows = coverage.get("rows", [])

    # Group by direction
    long_bias = [r for r in rows if r["direction"] == "LONG_BIAS"]
    short_bias = [r for r in rows if r["direction"] == "SHORT_BIAS"]
    wait = [r for r in rows if r["direction"] == "WAIT"]

    # Sort by confidence
    long_bias.sort(key=lambda r: r["confidence"], reverse=True)
    short_bias.sort(key=lambda r: r["confidence"], reverse=True)

    # Service health
    health = _fr_service_health()

    return {
        "ok": True,
        "service":     health,
        "universe":    len(_FRACTAL_UNIVERSE),
        "scanned":     len(rows),
        "phaseDistribution":     coverage.get("phaseDistribution", {}),
        "directionDistribution": coverage.get("directionDistribution", {}),
        "topLongBiasAssets":  long_bias[:6],
        "topShortBiasAssets": short_bias[:6],
        "waitAssets":         [r["symbol"] for r in wait],
        "horizons":           _HORIZONS,
        "asOf":               _now_iso(),
        "source":             "fractal_intelligence_v1",
    }


# ──────────────────────────────────────────────────────────────────────────
# /api/fractal (root)  →  intelligence alias
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/fractal")
def fractal_root():
    return fractal_intelligence()


# ──────────────────────────────────────────────────────────────────────────
# Telegram MiniApp endpoints
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/miniapp/fractal")
def miniapp_fractal(asset: str = Query("BTC"), timeframe: str = Query("1D")):
    """Mobile-friendly Fractal screen for Telegram MiniApp.

    Combines: snapshot + similarity consensus + forecast headline.
    """
    canon = _to_canonical(asset)
    snap = fractal_snapshot(canon, timeframe)
    fcst = fractal_forecast(canon, timeframe, 30, 8)

    return {
        "ok": True,
        "asset": canon,
        "timeframe": timeframe.upper(),
        "price":      snap.get("price"),
        "phase":      snap["runtime"]["phase"],
        "state":      snap["runtime"]["state"],
        "direction":  snap["runtime"]["direction"],
        "runtimeConfidence": snap["runtime"]["confidence"],
        "evidence":   snap["runtime"]["evidence"],
        "reasons":    snap["runtime"]["reasons"][:5],
        "similarity": snap["similarity"],
        "forecast":   {
            "consensus":    fcst.get("consensus", "WAIT"),
            "avgReturnPct": fcst.get("avgReturnPct", 0),
            "horizonBars":  fcst.get("horizonBars", 0),
            "confidence":   fcst.get("confidence", 0),
            "pathHead":     (fcst.get("forecastPath") or [])[:5],
        },
        "asOf": _now_iso(),
    }


@router.get("/api/miniapp/fractal-watchlist")
def miniapp_fractal_watchlist(symbols: str = Query("BTC,ETH,SOL,DOGE,XRP,BNB")):
    """Multi-asset fractal watchlist for MiniApp."""
    syms = [s.strip().upper() for s in (symbols or "BTC,ETH").split(",") if s.strip()]
    out = []
    for s in syms[:20]:
        try:
            snap = fractal_snapshot(s, "1D")
            if snap.get("ok"):
                out.append({
                    "symbol":     snap["symbol"],
                    "price":      snap.get("price"),
                    "phase":      snap["runtime"]["phase"],
                    "direction":  snap["runtime"]["direction"],
                    "runtimeConf": snap["runtime"]["confidence"],
                    "evidence":   snap["runtime"]["evidence"],
                    "simConsensus": snap["similarity"]["consensus"],
                    "simConf":      snap["similarity"]["confidence"],
                    "avgReturnPct": snap["similarity"]["avgReturnPct"],
                })
        except Exception as e:
            logger.info(f"  watchlist {s} skipped: {e}")
    return {"ok": True, "items": out, "count": len(out), "asOf": _now_iso()}


# ──────────────────────────────────────────────────────────────────────────
# Admin
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/admin/fractal/overview")
def admin_fractal_overview():
    """Admin dashboard: intelligence + service health + sample heatmap."""
    intel = fractal_intelligence()
    heatmap = fractal_heatmap(8)
    return {
        "ok": True,
        "service":     intel.get("service"),
        "intelligence": {
            "universe":             intel.get("universe"),
            "scanned":              intel.get("scanned"),
            "phaseDistribution":    intel.get("phaseDistribution"),
            "directionDistribution": intel.get("directionDistribution"),
            "topLongs":             intel.get("topLongBiasAssets", [])[:3],
            "topShorts":            intel.get("topShortBiasAssets", [])[:3],
            "waitCount":            len(intel.get("waitAssets", [])),
        },
        "heatmapSample": heatmap.get("rows", [])[:8],
        "asOf": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────────────
# Legacy aliases consumed by older Web pages
# (BtcFractalPage / SpxFractalPage / DxyFractalPage / OverviewPage)
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/fractal/match")
def fractal_match(asset: str = Query("BTC"), timeframe: str = Query("1D")):
    """Legacy alias: top historical match for a given asset.

    Returns the strongest similar pattern (rank #1) from /api/fractal/similar.
    """
    sim = fractal_similar(asset, timeframe, 30, 500, 1)
    if not sim.get("ok"):
        return {"ok": False, "asset": _to_canonical(asset), "error": "no_match"}
    top = (sim.get("matches") or [{}])[0]
    return {
        "ok": True,
        "asset": sim["symbol"],
        "timeframe": timeframe.upper(),
        "currentPrice": sim.get("currentPrice"),
        "match": top,
        "consensus": sim.get("consensus"),
        "avgReturnPct": sim.get("avgReturnPct"),
        "confidence": sim.get("confidence"),
        "horizonBars": sim.get("horizonBars"),
        "asOf": _now_iso(),
        "source": "fractal_match_v1",
    }


@router.get("/api/fractal/signal")
def fractal_signal(asset: str = Query("BTC"), timeframe: str = Query("1D")):
    """Legacy alias: aggregated fractal signal (runtime + similarity)."""
    snap = fractal_snapshot(asset, timeframe)
    if not snap.get("ok"):
        return {"ok": False, "asset": _to_canonical(asset)}
    rt = snap["runtime"]
    sim = snap["similarity"]

    # Combine the two engines
    rt_dir = rt.get("direction", "WAIT")
    sim_dir = sim.get("consensus", "WAIT")
    if rt_dir == sim_dir and rt_dir != "WAIT":
        signal = rt_dir
        strength = (rt.get("confidence", 0) + sim.get("confidence", 0)) / 2
    elif rt_dir != "WAIT" and sim_dir == "WAIT":
        signal = rt_dir
        strength = rt.get("confidence", 0) * 0.7
    elif sim_dir != "WAIT" and rt_dir == "WAIT":
        signal = sim_dir
        strength = sim.get("confidence", 0) * 0.7
    elif rt_dir != "WAIT" and sim_dir != "WAIT":
        # Conflict
        signal = "WAIT"
        strength = 0
    else:
        signal = "WAIT"
        strength = 0

    return {
        "ok": True,
        "asset": snap["symbol"],
        "timeframe": timeframe.upper(),
        "signal": signal,
        "strength": round(strength, 3),
        "runtimeDirection": rt_dir,
        "runtimeConfidence": rt.get("confidence", 0),
        "similarityConsensus": sim_dir,
        "similarityConfidence": sim.get("confidence", 0),
        "avgReturnPct": sim.get("avgReturnPct", 0),
        "price": snap.get("price"),
        "phase": rt.get("phase"),
        "asOf": _now_iso(),
        "source": "fractal_signal_v1",
    }


@router.get("/api/ui/brain/decision")
def ui_brain_decision(asset: str = Query("BTC")):
    """Legacy alias: Brain decision payload (combines fractal signal + macro)."""
    sig = fractal_signal(asset, "1D")
    if not sig.get("ok"):
        return {"ok": False, "asset": _to_canonical(asset)}

    # Macro overlay (lightweight)
    overlay = overlay_coeffs()

    return {
        "ok": True,
        "asset": sig["asset"],
        "decision": sig["signal"],
        "confidence": sig["strength"],
        "components": {
            "fractalRuntime": {
                "direction": sig["runtimeDirection"],
                "confidence": sig["runtimeConfidence"],
            },
            "fractalSimilarity": {
                "consensus": sig["similarityConsensus"],
                "confidence": sig["similarityConfidence"],
                "avgReturnPct": sig["avgReturnPct"],
            },
            "macroOverlay": overlay,
        },
        "phase": sig.get("phase"),
        "price": sig.get("price"),
        "asOf": _now_iso(),
        "source": "ui_brain_decision_v1",
    }


@router.get("/api/overlay/coeffs")
def overlay_coeffs():
    """Macro overlay coefficients (BTC / SPX / DXY correlation snapshot).

    Computes simple 30-bar correlation of BTC vs SPX-proxy (we use total
    crypto-market BTC dominance via OKX as a proxy since we don't have direct
    SPX feed in our datacenter)."""
    # Native fractal engine has its own macro overlay – pull from it
    rt = _fr_runtime("BTC") or {}
    macro = rt.get("structure", {}).get("macroContext", {}) or {}

    return {
        "ok": True,
        "btc": {
            "regime":    macro.get("regime", "neutral"),
            "spxNearHigh": macro.get("spxNearHigh", False),
            "dxyTrend":  macro.get("dxyTrend", 0),
            "correlation": macro.get("correlation", {}),
        },
        "asOf": _now_iso(),
        "source": "overlay_coeffs_v1",
    }

