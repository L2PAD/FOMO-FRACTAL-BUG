"""
META BRAIN — Real-data backed router
======================================
Replaces the legacy_compat stubs for /meta-brain-v2/* (status, state,
signals/aligned, drift, correlation, dataset/stats, dataset/runs,
performance, influence) and /v10/meta-brain/snapshots with implementations
that pull from real Mongo data:

  • signal_history (14+)        → signals/aligned, performance
  • signal_log (32+)            → drift score (variance-of-confidence)
  • actor_signal_events (197+)  → influence-by-actor
  • regime_signals (33+)        → state, status
  • *_fractal_forecasts (5×N)   → snapshots, dataset/runs
  • mbrain_verdicts (if any)    → status verdict

This router is mounted in server.py BEFORE legacy_compat so the
real-data handlers win on collisions.
"""

from __future__ import annotations

import os
import statistics as stats
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Query
from pymongo import MongoClient, DESCENDING, ASCENDING

router = APIRouter(prefix="/api", tags=["meta_brain_v2"])

_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME   = os.environ.get("DB_NAME", "fomo_mobile")
_client    = MongoClient(_MONGO_URL)
_db        = _client[_DB_NAME]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_count(name: str) -> int:
    try:
        return _db[name].count_documents({})
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────────
# /meta-brain-v2/status
# ─────────────────────────────────────────────────────────────────────
@router.get("/meta-brain-v2/status")
def mb_status():
    """Live system status — real counters + module health."""
    try:
        from services.trading_runtime import build_verdict
        v = build_verdict("BTC")
        align = v.get("alignment", {})
        active_modules = align.get("activeModules") or []
    except Exception:
        active_modules = []
        v = {}

    counts = {
        "signal_history":      _safe_count("signal_history"),
        "signal_log":          _safe_count("signal_log"),
        "actor_signal_events": _safe_count("actor_signal_events"),
        "regime_signals":      _safe_count("regime_signals"),
        "fractal_forecasts":   sum(_safe_count(f"{a}_fractal_forecasts")
                                   for a in ["btc", "spx", "dxy", "eth", "sol",
                                             "bnb", "xrp", "ada", "avax", "doge"]),
    }

    # Latest regime signal
    latest_regime = None
    try:
        latest_regime = _db.regime_signals.find_one({}, {"_id": 0}, sort=[("ts", DESCENDING)])
    except Exception:
        pass

    return {
        "ok":              True,
        "asOf":            _now(),
        "status":          "operational",
        "activeModules":   active_modules,
        "totalModules":    5,
        "verdict":         v.get("verdict") if isinstance(v, dict) else None,
        "confidence":      v.get("confidence") if isinstance(v, dict) else None,
        "counters":        counts,
        "latestRegime":    latest_regime,
    }


# ─────────────────────────────────────────────────────────────────────
# /meta-brain-v2/state
# ─────────────────────────────────────────────────────────────────────
@router.get("/meta-brain-v2/state")
def mb_state():
    """Most recent meta-brain state assembled from current data."""
    try:
        from services.trading_runtime import build_verdict
        v = build_verdict("BTC")
    except Exception:
        v = {}

    # Latest 10 signals
    try:
        recent = list(_db.signal_log.find({}, {"_id": 0}).sort("ts", DESCENDING).limit(10))
    except Exception:
        recent = []

    # Module confidences
    module_confidence = (v.get("moduleConfidence") or {}) if isinstance(v, dict) else {}
    avg_conf = (sum(module_confidence.values()) / max(1, len(module_confidence))) if module_confidence else 0.0

    return {
        "ok":               True,
        "asOf":             _now(),
        "state":            {
            "verdict":          v.get("verdict") if isinstance(v, dict) else None,
            "confidence":       v.get("confidence") if isinstance(v, dict) else None,
            "alignment":        v.get("alignment") if isinstance(v, dict) else None,
            "moduleConfidence": module_confidence,
            "avgConfidence":    round(avg_conf, 4),
        },
        "recentSignals":    recent,
        "recentSignalCount": len(recent),
    }


# ─────────────────────────────────────────────────────────────────────
# /meta-brain-v2/signals/aligned
# ─────────────────────────────────────────────────────────────────────
@router.get("/meta-brain-v2/signals/aligned")
def mb_signals_aligned(limit: int = Query(20)):
    """Aligned signals across modules — signal_history filtered by alignment >= 0.6."""
    try:
        rows = list(_db.signal_history.find(
            {},
            {"_id": 0},
        ).sort("ts", DESCENDING).limit(limit * 4))
    except Exception:
        rows = []

    aligned = []
    for r in rows:
        # Consider a signal "aligned" when its confidence/alignment marker is high.
        score = r.get("alignment") or r.get("alignmentScore") or r.get("confidence")
        if isinstance(score, (int, float)) and score >= 0.6:
            aligned.append(r)
        if len(aligned) >= limit:
            break

    return {
        "ok":      True,
        "asOf":    _now(),
        "aligned": aligned,
        "count":   len(aligned),
        "total":   len(rows),
    }


# ─────────────────────────────────────────────────────────────────────
# /meta-brain-v2/drift
# ─────────────────────────────────────────────────────────────────────
@router.get("/meta-brain-v2/drift")
def mb_drift(window_days: int = Query(7)):
    """Drift = variance of module-confidence across the recent window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(window_days))
    cutoff_iso = cutoff.isoformat()
    try:
        # signal_log uses "timestamp" string field, confidence on 0-100 scale
        rows = list(_db.signal_log.find(
            {"timestamp": {"$gte": cutoff_iso}},
            {"_id": 0, "confidence": 1, "strength": 1, "timestamp": 1},
        ).sort("timestamp", DESCENDING).limit(500))
    except Exception:
        rows = []

    confs: List[float] = []
    for r in rows:
        c = r.get("confidence")
        if isinstance(c, (int, float)):
            # normalise 0-100 → 0-1
            confs.append(float(c) / 100.0 if c > 1.0 else float(c))
        s = r.get("strength")
        if isinstance(s, (int, float)):
            confs.append(float(s) / 100.0 if s > 1.0 else float(s))

    if len(confs) >= 3:
        sigma = stats.pstdev(confs)
        mean  = stats.fmean(confs)
        drift_score = float(round(sigma, 4))
        if sigma < 0.08:
            level = "low"
        elif sigma < 0.18:
            level = "moderate"
        else:
            level = "high"
    else:
        sigma = 0.0; mean = 0.0; drift_score = 0.0; level = "insufficient_data"

    return {
        "ok":           True,
        "asOf":         _now(),
        "windowDays":   int(window_days),
        "drift":        level,
        "score":        drift_score,
        "stdev":        float(round(sigma, 4)),
        "mean":         float(round(mean, 4)),
        "samples":      len(confs),
    }


# ─────────────────────────────────────────────────────────────────────
# /meta-brain-v2/influence
# ─────────────────────────────────────────────────────────────────────
@router.get("/meta-brain-v2/influence")
def mb_influence(limit: int = Query(20)):
    """Per-actor influence = number of recent signal events × avg confidence."""
    try:
        rows = list(_db.actor_signal_events.find(
            {},
            {"_id": 0, "actor_handle": 1, "actor": 1, "actorId": 1,
             "confidence": 1, "ingested_at": 1, "signal_type": 1, "token": 1},
        ).sort("ingested_at", DESCENDING).limit(2000))
    except Exception:
        rows = []

    agg: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        a = r.get("actor_handle") or r.get("actor") or r.get("actorId") or "unknown"
        if a not in agg:
            agg[a] = {"actor": a, "events": 0, "confSum": 0.0, "confN": 0, "tokens": set()}
        agg[a]["events"] += 1
        c = r.get("confidence")
        if isinstance(c, (int, float)):
            agg[a]["confSum"] += float(c) / 100.0 if c > 1.0 else float(c)
            agg[a]["confN"]   += 1
        if r.get("token"):
            agg[a]["tokens"].add(r["token"])

    influence: List[Dict[str, Any]] = []
    for d in agg.values():
        avg_c = (d["confSum"] / d["confN"]) if d["confN"] > 0 else 0.5
        influence.append({
            "actor":         d["actor"],
            "events":        d["events"],
            "avgConfidence": round(avg_c, 4),
            "score":         round(d["events"] * (0.5 + avg_c), 4),
            "tokens":        sorted(list(d["tokens"]))[:10],
        })
    influence.sort(key=lambda x: -x["score"])
    return {
        "ok":         True,
        "asOf":       _now(),
        "influence":  influence[:limit],
        "totalActors": len(influence),
    }


# ─────────────────────────────────────────────────────────────────────
# /meta-brain-v2/performance
# ─────────────────────────────────────────────────────────────────────
@router.get("/meta-brain-v2/performance")
def mb_performance(window_days: int = Query(30)):
    """Performance from signal_history: hit-rate (resolved outcome direction)
    + sharpe-like z-score from returns column."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(window_days))
    try:
        rows = list(_db.signal_history.find(
            {"ts": {"$gte": cutoff.isoformat()}, "outcome": {"$exists": True}},
            {"_id": 0},
        ).sort("ts", DESCENDING).limit(500))
    except Exception:
        rows = []

    hits = 0
    losses = 0
    returns: List[float] = []
    for r in rows:
        outcome = (r.get("outcome") or "").upper()
        if outcome in ("HIT", "TP", "WIN"):
            hits += 1
        elif outcome in ("MISS", "FP", "LOSS"):
            losses += 1
        ret = r.get("realizedReturn") or r.get("return")
        if isinstance(ret, (int, float)):
            returns.append(float(ret))

    samples = hits + losses
    win_rate = (hits / samples) if samples > 0 else None
    sharpe = None
    if len(returns) >= 3:
        mu = stats.fmean(returns)
        sd = stats.pstdev(returns)
        sharpe = float(round(mu / sd, 4)) if sd > 0 else None

    return {
        "ok":         True,
        "asOf":       _now(),
        "windowDays": int(window_days),
        "samples":    int(samples),
        "hits":       hits,
        "losses":     losses,
        "winRate":    round(win_rate, 4) if win_rate is not None else None,
        "sharpe":     sharpe,
        "returns":    len(returns),
    }


# ─────────────────────────────────────────────────────────────────────
# /meta-brain-v2/correlation
# ─────────────────────────────────────────────────────────────────────
@router.get("/meta-brain-v2/correlation")
def mb_correlation(window_days: int = Query(120)):
    """Cross-asset Pearson correlation of daily log returns (BTC/SPX/DXY)
    computed from real candle collections.  Proxies a thin slice of what
    the Node sidecar /api/brain/v2/cross-asset returns."""
    import math
    cutoff_ts = datetime.now(timezone.utc) - timedelta(days=int(window_days) + 5)

    def series(coll, sym_filter, candle_kind="flat"):
        try:
            proj = {"_id": 0, "ts": 1, "date": 1, "close": 1, "ohlcv.c": 1}
            sort_field = "ts" if candle_kind != "spx_legacy" else "ts"
            cursor = _db[coll].find(
                sym_filter, proj
            ).sort(sort_field, ASCENDING).limit(int(window_days) + 60)
            out = []
            for d in cursor:
                # Prefer nested ohlcv.c, fallback to flat close
                ohlcv = d.get("ohlcv") or {}
                cl = ohlcv.get("c") if ohlcv else None
                if cl is None:
                    cl = d.get("close")
                if cl is None:
                    continue
                try:
                    out.append(float(cl))
                except (TypeError, ValueError):
                    continue
            return out
        except Exception:
            return []

    btc = series("fractal_canonical_ohlcv", {"meta.symbol": "BTC", "meta.timeframe": "1d"})
    spx = series("spx_candles", {})
    dxy = series("dxy_candles", {})

    def lret(arr):
        return [math.log(arr[i+1] / arr[i]) for i in range(len(arr)-1)
                if arr[i] > 0 and arr[i+1] > 0]

    btc_r = lret(btc[-(int(window_days)+1):])
    spx_r = lret(spx[-(int(window_days)+1):])
    dxy_r = lret(dxy[-(int(window_days)+1):])
    n = min(len(btc_r), len(spx_r), len(dxy_r))
    btc_r = btc_r[-n:]; spx_r = spx_r[-n:]; dxy_r = dxy_r[-n:]

    def corr(a, b):
        if len(a) < 5 or len(b) < 5:
            return None
        ma = sum(a)/len(a); mb = sum(b)/len(b)
        num = sum((a[i]-ma)*(b[i]-mb) for i in range(len(a)))
        da  = math.sqrt(sum((x-ma)**2 for x in a))
        db_ = math.sqrt(sum((x-mb)**2 for x in b))
        if da == 0 or db_ == 0: return None
        return round(num / (da * db_), 4)

    return {
        "ok":             True,
        "asOf":           _now(),
        "windowDays":     int(window_days),
        "sampleN":        n,
        "corr_btc_spx":   corr(btc_r, spx_r),
        "corr_btc_dxy":   corr(btc_r, dxy_r),
        "corr_spx_dxy":   corr(spx_r, dxy_r),
    }


# ─────────────────────────────────────────────────────────────────────
# /meta-brain-v2/dataset/stats
# ─────────────────────────────────────────────────────────────────────
@router.get("/meta-brain-v2/dataset/stats")
def mb_dataset_stats():
    """Aggregate ML dataset stats — counters across module collections."""
    samples = {}
    for c in ["signal_history", "signal_log", "actor_signal_events",
              "regime_signals", "exchange_forecasts",
              "btc_fractal_forecasts", "spx_fractal_forecasts",
              "dxy_fractal_forecasts"]:
        samples[c] = _safe_count(c)

    total = sum(samples.values())
    # Latest timestamps
    latest_ts = {}
    for c in samples.keys():
        try:
            d = _db[c].find_one({}, {"_id": 0, "ts": 1, "createdAt": 1},
                                sort=[("ts", DESCENDING)])
            if d:
                latest_ts[c] = d.get("ts") or d.get("createdAt")
        except Exception:
            pass

    return {
        "ok":        True,
        "asOf":      _now(),
        "totalSamples": total,
        "byCollection": samples,
        "latestTs":  latest_ts,
    }


# ─────────────────────────────────────────────────────────────────────
# /meta-brain-v2/dataset/runs
# ─────────────────────────────────────────────────────────────────────
@router.get("/meta-brain-v2/dataset/runs")
def mb_dataset_runs(limit: int = Query(20)):
    """Recent forecast-runs across modules (5 fractal scopes + exchange)."""
    runs: List[Dict[str, Any]] = []
    for asset in ["btc", "spx", "dxy"]:
        c = f"{asset}_fractal_forecasts"
        try:
            rows = list(_db[c].find({}, {"_id": 0}).sort("createdAt", DESCENDING).limit(8))
            for r in rows:
                r["_scope"] = "fractal"
                r["_asset"] = asset.upper()
                runs.append(r)
        except Exception:
            pass

    try:
        rows = list(_db.exchange_forecast_runs.find({}, {"_id": 0})
                       .sort("createdAt", DESCENDING).limit(8))
        for r in rows:
            r["_scope"] = "exchange"
            runs.append(r)
    except Exception:
        pass

    # Sort by createdAt desc
    def _ts(r):
        return str(r.get("createdAt") or r.get("ts") or "")
    runs.sort(key=_ts, reverse=True)
    runs = runs[:limit]

    return {
        "ok":     True,
        "asOf":   _now(),
        "runs":   runs,
        "count":  len(runs),
    }


# ─────────────────────────────────────────────────────────────────────
# /v10/meta-brain/snapshots
# ─────────────────────────────────────────────────────────────────────
@router.get("/v10/meta-brain/snapshots")
def mb_snapshots(limit: int = Query(20)):
    """Meta Brain decision snapshots assembled from latest forecasts +
    regime signals.  Each snapshot binds (asset, asOf, verdict, modules)."""
    snaps: List[Dict[str, Any]] = []
    for asset in ["btc", "spx", "dxy"]:
        c = f"{asset}_fractal_forecasts"
        try:
            rows = list(_db[c].find({}, {"_id": 0})
                           .sort("createdAt", DESCENDING).limit(limit))
        except Exception:
            rows = []
        for r in rows:
            snaps.append({
                "asset":     asset.upper(),
                "asOf":      r.get("createdAt") or r.get("evaluateAt"),
                "horizon":   r.get("horizon"),
                "direction": r.get("direction"),
                "confidence": r.get("confidence"),
                "entry":     r.get("entryPrice"),
                "target":    r.get("targetPrice"),
                "source":    r.get("source"),
            })

    snaps.sort(key=lambda x: str(x.get("asOf") or ""), reverse=True)
    snaps = snaps[:limit]
    return {
        "ok":        True,
        "asOf":      _now(),
        "snapshots": snaps,
        "count":     len(snaps),
    }
