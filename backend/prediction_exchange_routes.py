"""
Prediction Exchange Routes
============================
API endpoints for Exchange Prediction blocks 2-5:
  - /forecast (next targets + chart markers)
  - /alts (real-scored alt table)
  - /top-signals (compact signal list)
  - /model-health (per-horizon health)

Config is injected via FractalConfig — no direct os.environ reads.
"""

from fastapi import APIRouter, Query
from pymongo import MongoClient, DESCENDING
from datetime import datetime, timezone
import math
import httpx

router = APIRouter(prefix="/api/prediction/exchange", tags=["prediction-exchange"])


def _db():
    from forecast.repo import _cfg
    c = _cfg()
    return MongoClient(c.mongo_url)[c.db_name]


# ──────────────────────────────────────────────
# Block 2: Exchange Forecast (next targets)
# ──────────────────────────────────────────────

@router.get("/forecast")
async def get_forecast(
    asset: str = Query("BTC"),
    tf: str = Query("1d"),
    lookback: int = Query(90),
):
    db = _db()
    col = db["exchange_forecasts"]
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    # Get latest forecast per horizon
    targets = []
    for h in ["24H", "7D", "30D"]:
        doc = col.find_one(
            {"asset": asset, "horizon": h},
            {"_id": 0},
            sort=[("createdAt", DESCENDING)],
        )
        if not doc:
            continue

        status = "PENDING"
        if doc.get("evaluated"):
            status = "EVALUATED"
        elif doc.get("evaluateAfter", 0) < now_ms:
            status = "STALE"

        entry = doc.get("entryPrice") or doc.get("basePrice", 0)
        target = doc.get("targetPrice", entry)
        direction = doc.get("direction", "NEUTRAL")
        if direction == "UP":
            direction = "LONG"
        elif direction == "DOWN":
            direction = "SHORT"

        move_pct = 0
        if entry > 0:
            if direction == "LONG":
                move_pct = (target - entry) / entry * 100
            elif direction == "SHORT":
                move_pct = (entry - target) / entry * 100

        targets.append({
            "horizon": h,
            "createdAt": _ts_to_iso(doc.get("createdAt")),
            "evaluateAfter": _ts_to_iso(doc.get("evaluateAfter")),
            "entryPrice": round(entry, 2),
            "targetPrice": round(target, 2),
            "direction": direction,
            "confidence": doc.get("confidence", 0),
            "movePct": round(move_pct, 2),
            "status": status,
            "modelVersion": doc.get("modelVersion", "unknown"),
        })

    # Price series from observations
    from forecast.price_provider import get_price_series
    start = datetime.fromtimestamp((now_ms - lookback * 86400000) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prices = get_price_series(asset, start, end)
    series = [{"ts": int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()), "price": p} for d, p in sorted(prices.items())]

    return {
        "ok": True,
        "asset": asset,
        "tf": tf,
        "now": datetime.now(timezone.utc).isoformat(),
        "series": series,
        "targets": targets,
        "meta": {
            "source": "exchange_forecasts",
            "seriesSource": "yfinance",
            "lastSeriesTs": series[-1]["ts"] if series else None,
        },
    }


# ──────────────────────────────────────────────
# Block 3: Alt Table (real scoring)
# ──────────────────────────────────────────────

@router.get("/alts")
async def get_alts(
    horizon: str = Query("7D"),
    limit: int = Query(30),
):
    db = _db()
    snapshots = db["exchange_symbol_snapshots"]

    # Get all snapshots
    docs = list(snapshots.find(
        {"symbol": {"$ne": "BTCUSDT"}},
        {"_id": 0},
    ).limit(200))

    if not docs:
        return {"ok": True, "horizon": horizon, "rows": [], "universe": {"type": "exchange_snapshots", "count": 0}}

    # Extract features
    rows = []
    for doc in docs:
        sym = doc.get("symbol", "")
        ret_24h = doc.get("ret_24h") or doc.get("price_change_pct") or 0
        volume = doc.get("volume_24h") or doc.get("volume_24h_usd") or 0
        oi = doc.get("oi_usd") or doc.get("open_interest") or 0
        funding = doc.get("funding_annualized") or doc.get("funding_rate", 0) * 365 * 3
        score_up = doc.get("score_up") or doc.get("bullScore") or 0.5
        score_down = doc.get("score_down") or doc.get("bearScore") or 0.5

        # Coverage check
        fields_present = sum(1 for v in [ret_24h, volume, oi, funding] if v != 0)
        coverage_pct = fields_present / 4 * 100

        rows.append({
            "symbol": sym,
            "ret_24h": float(ret_24h),
            "volume": float(volume),
            "oi": float(oi),
            "funding": float(funding),
            "score_up": float(score_up),
            "score_down": float(score_down),
            "coverage_pct": coverage_pct,
        })

    if not rows:
        return {"ok": True, "horizon": horizon, "rows": [], "universe": {"type": "exchange_snapshots", "count": 0}}

    # Z-score normalization across universe
    def z_normalize(values):
        n = len(values)
        if n == 0:
            return [0.5] * n
        mean = sum(values) / n
        std = max((sum((v - mean) ** 2 for v in values) / n) ** 0.5, 1e-8)
        return [max(0, min(1, 0.5 + (v - mean) / std / 4)) for v in values]

    rets = z_normalize([r["ret_24h"] for r in rows])
    vols = z_normalize([math.log1p(r["volume"]) for r in rows])
    ois = z_normalize([math.log1p(r["oi"]) for r in rows])

    result_rows = []
    for i, r in enumerate(rows):
        momentum = rets[i]
        liquidity = vols[i]
        funding_penalty = min(abs(r["funding"]) / 0.6, 1.0)
        deriv = 0.5 * ois[i] + 0.5 * (1 - funding_penalty)

        raw_score = 0.45 * momentum + 0.35 * liquidity + 0.20 * deriv
        score = round(100 * raw_score)

        # Coverage/health
        if r["coverage_pct"] < 50:
            health_status = "DATA_GAP"
        elif r["coverage_pct"] < 70:
            health_status = "DEGRADED"
        else:
            health_status = "OK"

        # Risk
        if abs(r["ret_24h"]) > 0.12 or abs(r["funding"]) > 0.35:
            risk = "HIGH"
        elif abs(r["ret_24h"]) > 0.06:
            risk = "MED"
        else:
            risk = "LOW"

        # Bias
        if score >= 70 and health_status == "OK":
            bias = "BUY"
        elif score < 50 or risk == "HIGH":
            bias = "AVOID"
        else:
            bias = "WATCH"

        if health_status == "DEGRADED":
            bias = min(bias, "WATCH", key=lambda x: ["BUY", "WATCH", "AVOID"].index(x))

        # Drivers
        drivers = []
        if momentum > 0.6:
            drivers.append("momentum+")
        elif momentum < 0.4:
            drivers.append("momentum-")
        if liquidity > 0.6:
            drivers.append("volume+")
        if ois[i] > 0.6:
            drivers.append("oi+")
        if funding_penalty < 0.2:
            drivers.append("funding_ok")
        elif funding_penalty > 0.5:
            drivers.append("funding_hot")

        result_rows.append({
            "symbol": r["symbol"],
            "bias": bias,
            "score": score,
            "confidence": round(raw_score, 2),
            "risk": risk,
            "drivers": drivers,
            "health": {
                "status": health_status,
                "coveragePct": round(r["coverage_pct"]),
                "reasons": ["low_data"] if health_status != "OK" else [],
            },
            "metrics": {
                "ret_24h": round(r["ret_24h"], 4),
                "volume_24h_usd": round(r["volume"]),
                "oi_usd": round(r["oi"]),
                "funding_ann": round(r["funding"], 4),
                "score_up": round(r["score_up"], 2),
                "score_down": round(r["score_down"], 2),
            },
        })

    # Sort by score DESC
    result_rows.sort(key=lambda x: x["score"], reverse=True)

    return {
        "ok": True,
        "horizon": horizon,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "universe": {"type": "exchange_snapshots", "count": len(result_rows)},
        "rows": result_rows[:limit],
    }


# ──────────────────────────────────────────────
# Block 4: Top Signals
# ──────────────────────────────────────────────

@router.get("/top-signals")
async def get_top_signals(
    horizon: str = Query("7D"),
    limit: int = Query(10),
):
    db = _db()

    # Try exchange_verdicts first, fall back to exchange_observations
    verdicts = list(db["exchange_verdicts"].find({}, {"_id": 0}).sort("createdAt", -1).limit(50))

    if not verdicts:
        # Fall back to snapshots
        snapshots = list(db["exchange_symbol_snapshots"].find(
            {},
            {"_id": 0, "symbol": 1, "score_up": 1, "score_down": 1, "bullScore": 1, "bearScore": 1, "ret_24h": 1, "price_change_pct": 1},
        ).limit(50))

        signals = []
        for s in snapshots:
            sym = s.get("symbol", "")
            bull = s.get("score_up") or s.get("bullScore", 0.5)
            bear = s.get("score_down") or s.get("bearScore", 0.5)
            ret = s.get("ret_24h") or s.get("price_change_pct", 0)

            conviction = round(max(bull, bear) * 100)

            if bull > 0.6:
                action = "BUY"
                tier = "A" if bull > 0.7 else "B"
            elif bear > 0.6:
                action = "SELL"
                tier = "A" if bear > 0.7 else "B"
            else:
                action = "WATCH"
                tier = "C"

            risk = "High" if abs(ret) > 0.08 else "Med" if abs(ret) > 0.04 else "Low"

            signals.append({
                "symbol": sym,
                "action": action,
                "tier": tier,
                "horizon": "3-7d",
                "conviction": conviction,
                "oneLiner": f"{action} ({tier} 3-7d) | Conv {conviction} | ret {ret:+.1%} | Risk {risk}",
                "integrity": {"status": "OK", "coveragePct": 75, "reasons": []},
            })

        signals.sort(key=lambda x: x["conviction"], reverse=True)
        return {"ok": True, "horizon": horizon, "signals": signals[:limit]}

    # Parse verdicts
    signals = []
    for v in verdicts:
        sym = v.get("symbol", v.get("asset", ""))
        direction = v.get("direction", "NEUTRAL")
        action = "BUY" if direction == "UP" else "SELL" if direction == "DOWN" else "WATCH"
        confidence = v.get("confidence", 0.5)
        tier = "A" if confidence > 0.7 else "B" if confidence > 0.5 else "C"
        conviction = round(confidence * 100)

        signals.append({
            "symbol": sym,
            "action": action,
            "tier": tier,
            "horizon": "3-7d",
            "conviction": conviction,
            "oneLiner": f"{action} ({tier}) | Conv {conviction}% | {sym}",
            "integrity": {"status": "OK", "coveragePct": 80, "reasons": []},
        })

    signals.sort(key=lambda x: x["conviction"], reverse=True)
    return {"ok": True, "horizon": horizon, "signals": signals[:limit]}


# ──────────────────────────────────────────────
# Block 5: Model Health
# ──────────────────────────────────────────────

@router.get("/model-health")
async def get_model_health(asset: str = Query("BTC")):
    db = _db()
    col = db["exchange_forecasts"]
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    horizons = {}
    flags = []

    for h in ["24H", "7D", "30D"]:
        evaluated = list(col.find(
            {"asset": asset, "horizon": h, "evaluated": True, "outcome.label": {"$exists": True}},
            {"_id": 0, "outcome": 1},
        ))

        n = len(evaluated)
        if n < 30:
            flags.append(f"LOW_SAMPLE_{h}")

        tp = sum(1 for d in evaluated if d.get("outcome", {}).get("label") == "TP")
        fp = sum(1 for d in evaluated if d.get("outcome", {}).get("label") == "FP")
        weak = sum(1 for d in evaluated if d.get("outcome", {}).get("label") == "WEAK")

        denom = tp + fp + weak
        win_rate = tp / denom if denom > 0 else 0

        errors = [abs(d.get("outcome", {}).get("errorPct", 0) or 0) for d in evaluated if d.get("outcome", {}).get("errorPct") is not None]
        avg_err = sum(errors) / len(errors) if errors else 0

        overdue = col.count_documents({"asset": asset, "horizon": h, "evaluated": False, "evaluateAfter": {"$lte": now_ms}})
        if overdue > 0:
            flags.append(f"EVAL_LAG_{h}")

        horizons[h] = {
            "n": n,
            "winRate": round(win_rate, 3),
            "avgErrPct": round(avg_err, 3),
            "overdue": overdue,
            "tp": tp,
            "fp": fp,
            "weak": weak,
        }

    if not flags:
        flags.append("OK_SAMPLE")

    return {
        "ok": True,
        "asset": asset,
        "asOf": datetime.now(timezone.utc).isoformat(),
        "horizons": horizons,
        "flags": flags,
    }


def _ts_to_iso(ts_ms):
    if not ts_ms:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


# ──────────────────────────────────────────────
# Graph Endpoint (forecast segments + price)
# ──────────────────────────────────────────────

@router.get("/graph")
async def get_graph(
    asset: str = Query("BTC"),
    horizon: str = Query("7D"),
    lookback: int = Query(90),
):
    db = _db()
    col = db["exchange_forecasts"]
    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)
    cutoff_ms = now_ms - lookback * 86400 * 1000

    # 1) Price series from yfinance
    from forecast.price_provider import get_price_series
    start = datetime.fromtimestamp(cutoff_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    prices = get_price_series(asset, start, end)
    price_series = []
    for d, p in sorted(prices.items()):
        ts = int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        price_series.append({"time": ts, "value": round(p, 2)})

    # 2) All forecast segments for this horizon within lookback
    docs = list(col.find(
        {
            "asset": asset,
            "horizon": horizon,
            "createdAt": {"$gte": cutoff_ms},
        },
        {"_id": 0},
    ).sort("createdAt", 1))

    segments = []
    active_id = None

    for doc in docs:
        created_ms = doc.get("createdAt", 0)
        evaluate_ms = doc.get("evaluateAfter", 0)
        entry = doc.get("entryPrice") or doc.get("basePrice", 0)
        target = doc.get("targetPrice", entry)
        direction = doc.get("direction", "NEUTRAL")
        evaluated = doc.get("evaluated", False)
        outcome = doc.get("outcome") or {}

        # Determine status
        if evaluated and outcome.get("label"):
            status = "EVALUATED"
        elif evaluate_ms < now_ms:
            status = "OVERDUE"
        else:
            status = "ACTIVE"
            active_id = doc.get("id")

        # Normalize direction
        if direction == "UP":
            direction = "LONG"
        elif direction == "DOWN":
            direction = "SHORT"

        seg = {
            "id": doc.get("id", ""),
            "createdAt": int(created_ms / 1000),
            "evaluateAfter": int(evaluate_ms / 1000),
            "entryPrice": round(entry, 2),
            "targetPrice": round(target, 2),
            "direction": direction,
            "status": status,
            "confidence": doc.get("confidence", 0),
            "modelVersion": doc.get("modelVersion", ""),
        }

        if evaluated and outcome:
            seg["actualPrice"] = round(outcome.get("realPrice", 0), 2)
            seg["outcomeLabel"] = outcome.get("label", "")
            seg["hit"] = outcome.get("hit", False)

        segments.append(seg)

    return {
        "ok": True,
        "priceSeries": price_series,
        "forecastSegments": segments,
        "meta": {
            "asset": asset,
            "horizon": horizon,
            "lookback": lookback,
            "now": int(now.timestamp()),
            "activeForecastId": active_id,
            "segmentCount": len(segments),
        },
    }



# ──────────────────────────────────────────────
# Graph V3: Rolling forecast evolution (no segments, no curves)
# ──────────────────────────────────────────────

@router.get("/graph3")
async def get_graph3(
    asset: str = Query("BTC"),
    horizon: str = Query("7D"),
    lookback: int = Query(90, ge=14, le=365),
):
    """
    Clean graph endpoint: priceSeries + rollingForecasts + ML state.
    No segments, no artificial curves. Just real forecast evolution.
    """
    db = _db()
    col = db["exchange_forecasts"]
    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)

    # 1) Price series
    from forecast.price_provider import get_price_series as fps
    start = datetime.fromtimestamp((now_ms - lookback * 86400 * 1000) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    prices = fps(asset, start, end)
    price_series = []
    for d, p in sorted(prices.items()):
        ts_ms = int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
        price_series.append({"t": ts_ms, "p": round(p, 2)})

    now_ts = price_series[-1]["t"] if price_series else now_ms
    now_price = price_series[-1]["p"] if price_series else 0

    # 2) Rolling forecasts (last N by createdBucket, chronological)
    horizon_days = 7 if horizon == "7D" else 30
    forecasts = list(
        col.find(
            {"asset": asset, "horizon": horizon},
            {"_id": 0},
        ).sort("createdBucket", DESCENDING).limit(horizon_days)
    )
    forecasts = list(reversed(forecasts))  # chronological

    # 3) ML overlay state
    drift_snap = db["drift_snapshots"].find_one(
        {"asset": asset, "horizon": horizon},
        {"_id": 0, "mlWeight": 1, "driftScore": 1, "calibration": 1},
        sort=[("ts", DESCENDING)],
    )
    grad_doc = db["ml_overlay_state"].find_one(
        {"asset": asset, "horizon": horizon},
        {"_id": 0, "stage": 1, "mlAlpha": 1},
    )

    ml_weight = drift_snap.get("mlWeight", 1.0) if drift_snap else 1.0
    drift_score = drift_snap.get("driftScore", 0) if drift_snap else 0
    ece = drift_snap.get("calibration", {}).get("ece", 0) if drift_snap else 0
    stage = grad_doc.get("stage", "SHADOW") if grad_doc else "SHADOW"

    def _norm(doc):
        entry = doc.get("entryPrice") or doc.get("basePrice") or now_price
        rule_target = doc.get("targetPrice", entry)
        final_target = rule_target  # SHADOW: finalTarget = ruleTarget
        eval_after = doc.get("evaluateAfter", 0)

        outcome = doc.get("outcome")
        actual = outcome.get("realPrice") if outcome else None
        outcome_label = outcome.get("label") if outcome else None
        dir_match = outcome.get("directionMatch") if outcome else None

        result = {
            "createdBucket": doc.get("createdBucket", ""),
            "evalTs": int(eval_after) if eval_after else 0,
            "entryPrice": round(float(entry), 2),
            "ruleTarget": round(float(rule_target), 2),
            "finalTarget": round(float(final_target), 2),
            "direction": doc.get("direction", "NEUTRAL"),
            "confidence": round(float(doc.get("confidence", 0)), 4),
            "actual": round(float(actual), 2) if actual else None,
            "outcomeLabel": outcome_label,
            "directionMatch": dir_match,
            "forecastType": doc.get("forecastType", "point"),
        }

        # Band fields for 30D forecasts
        if doc.get("forecastType") == "band":
            result["medianTarget"] = doc.get("medianTarget")
            result["bandCoreLow"] = doc.get("bandCoreLow")
            result["bandCoreHigh"] = doc.get("bandCoreHigh")
            result["bandWideLow"] = doc.get("bandWideLow")
            result["bandWideHigh"] = doc.get("bandWideHigh")

        return result

    rolling = [_norm(f) for f in forecasts]
    current = rolling[-1] if rolling else None
    prev = rolling[-2] if len(rolling) > 1 else None

    # 4) Summary stats from ALL evaluated forecasts
    all_evaluated = list(col.find(
        {"asset": asset, "horizon": horizon, "outcome": {"$ne": None}},
        {"_id": 0, "outcome": 1, "entryPrice": 1, "basePrice": 1, "targetPrice": 1, "evaluateAfter": 1},
    ).sort("createdBucket", DESCENDING).limit(60))

    total_eval = len(all_evaluated)
    tp_count = sum(1 for d in all_evaluated if d.get("outcome", {}).get("label") == "TP")
    dir_hits = sum(1 for d in all_evaluated if d.get("outcome", {}).get("directionMatch"))
    win_rate = tp_count / total_eval if total_eval > 0 else 0

    avg_dev = 0.0
    if total_eval > 0:
        devs = [abs(d["outcome"].get("deviationPct", 0)) for d in all_evaluated if d.get("outcome")]
        avg_dev = sum(devs) / len(devs) if devs else 0

    pending_count = col.count_documents(
        {"asset": asset, "horizon": horizon, "outcome": None, "evaluateAfter": {"$lt": now_ms}}
    )

    summary = {
        "winRate": round(win_rate, 4),
        "dirHitRate": round(dir_hits / total_eval, 4) if total_eval > 0 else 0,
        "avgDeviation": round(avg_dev, 2),
        "evaluated": total_eval,
        "overdue": pending_count,
    }

    # 5) Risk & Probability Profile — from historical evaluated forecasts
    up_count = 0
    down_count = 0
    neutral_count = 0
    deviation_pcts = []
    for d in all_evaluated:
        oc = d.get("outcome", {})
        dev = oc.get("deviationPct", 0)
        deviation_pcts.append(dev)
        entry_p = d.get("entryPrice") or d.get("basePrice", 0)
        target_p = d.get("targetPrice", entry_p)
        if entry_p > 0:
            move = (target_p - entry_p) / entry_p
            if move > 0.01:
                up_count += 1
            elif move < -0.01:
                down_count += 1
            else:
                neutral_count += 1

    total_dist = up_count + down_count + neutral_count
    upside_pct = round(up_count / total_dist, 4) if total_dist > 0 else 0.33
    downside_pct = round(down_count / total_dist, 4) if total_dist > 0 else 0.33
    neutral_pct = round(neutral_count / total_dist, 4) if total_dist > 0 else 0.34

    # Volatility from deviation spread
    if deviation_pcts:
        sorted_devs = sorted(deviation_pcts)
        p10 = sorted_devs[max(0, int(len(sorted_devs) * 0.1))]
        p90 = sorted_devs[min(len(sorted_devs) - 1, int(len(sorted_devs) * 0.9))]
        vol_std = (sum((x - avg_dev) ** 2 for x in deviation_pcts) / len(deviation_pcts)) ** 0.5
    else:
        p10 = 0
        p90 = 0
        vol_std = 0

    # Best/worst case from current forecast
    cur_target = current["finalTarget"] if current else now_price
    worst_case = round(now_price * (1 + p10 / 100), 2) if p10 else round(now_price * 0.95, 2)
    best_case = round(now_price * (1 + p90 / 100), 2) if p90 else round(now_price * 1.05, 2)
    # Ensure worst < best
    if worst_case > best_case:
        worst_case, best_case = best_case, worst_case

    risk_profile = {
        "upside": upside_pct,
        "neutral": neutral_pct,
        "downside": downside_pct,
        "worstCase": worst_case,
        "bestCase": best_case,
        "expectedTarget": cur_target,
        "volatility": round(vol_std, 2),
        "sampleSize": total_dist,
    }

    # 6) Regime context — from latest drift snapshot
    drift_full = db["drift_snapshots"].find_one(
        {"asset": asset, "horizon": horizon},
        {"_id": 0, "regime": 1, "regimeConfidence": 1},
        sort=[("ts", DESCENDING)],
    )
    current_regime = drift_full.get("regime", "TRANSITION") if drift_full else "TRANSITION"
    regime_conf = drift_full.get("regimeConfidence", 0) if drift_full else 0

    # Regime baselines for the current horizon
    regime_baseline_doc = db["drift_regime_baselines"].find_one(
        {"regime": current_regime, "horizon": horizon},
        {"_id": 0, "baseline": 1},
    )
    regime_baseline = regime_baseline_doc.get("baseline", {}) if regime_baseline_doc else {}

    regime_info = {
        "current": current_regime,
        "confidence": round(regime_conf, 2),
        "baseline": {
            "maeMean": round(regime_baseline.get("mae_mean", 0), 4),
            "maeStd": round(regime_baseline.get("mae_std", 0), 4),
            "dirHitMean": round(regime_baseline.get("dir_hit_mean", 0), 4),
            "sampleSize": regime_baseline.get("n", 0),
        },
    }

    # 7) Band data for 30D (probabilistic range)
    band_data = None
    if horizon == "30D":
        m_ret = regime_baseline.get("median_return", 0.0)
        p25 = regime_baseline.get("p25_return", -0.05)
        p75 = regime_baseline.get("p75_return", 0.05)
        s_ret = regime_baseline.get("std_return", 0.05)

        iqr = p75 - p25
        p10_est = regime_baseline.get("p10_return", p25 - 0.75 * iqr)
        p90_est = regime_baseline.get("p90_return", p75 + 0.75 * iqr)

        shrinkage = 0.75
        if current_regime == "TRANSITION":
            shrinkage *= 0.6
        elif current_regime == "RISK_OFF":
            shrinkage *= 0.7

        neutral_thresh = 0.25 * s_ret
        if m_ret > neutral_thresh:
            bias = "LONG"
        elif m_ret < -neutral_thresh:
            bias = "SHORT"
        else:
            bias = "NEUTRAL"

        band_data = {
            "forecastType": "band",
            "medianTarget": round(now_price * (1 + m_ret * shrinkage), 2),
            "bandCore": {
                "low": round(now_price * (1 + p25), 2),
                "high": round(now_price * (1 + p75), 2),
            },
            "bandWide": {
                "low": round(now_price * (1 + p10_est), 2),
                "high": round(now_price * (1 + p90_est), 2),
            },
            "bias": bias,
            "signalStrength": round(abs(m_ret) / max(s_ret, 0.001), 4),
        }

    return {
        "ok": True,
        "asset": asset,
        "horizon": horizon,
        "nowTs": now_ts,
        "nowPrice": now_price,
        "priceSeries": price_series,
        "rollingForecasts": rolling,
        "current": current,
        "prev": prev,
        "summary": summary,
        "riskProfile": risk_profile,
        "regime": regime_info,
        "band": band_data,
        "ml": {
            "mlWeight": round(ml_weight, 4),
            "driftScore": round(drift_score, 4),
            "ece": round(ece, 4),
            "stage": stage,
        },
    }



# ──────────────────────────────────────────────
# Graph4 — Rolling Expectation Curve endpoint
# ──────────────────────────────────────────────

@router.get("/graph4")
async def get_graph4(
    asset: str = Query("BTC"),
    horizon: str = Query("7D"),
    lookback: int = Query(None, ge=7, le=365),
):
    """
    Graph4: rolling expectation curve data.
    Returns forecasts with madeAtTs + expectedMovePct for normalized curve building.
    Band data included for right panel numbers (30D only).
    """
    db = _db()
    col = db["exchange_forecasts"]
    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)

    horizon_days = {"7D": 7, "30D": 30, "24H": 1}.get(horizon, 7)
    if lookback is None:
        lookback = horizon_days * 3

    # 1) Price series (wider for chart context)
    from forecast.price_provider import get_price_series as fps
    price_lookback = max(90, lookback + 30)
    start = datetime.fromtimestamp((now_ms - price_lookback * 86400 * 1000) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    prices = fps(asset, start, end)
    price_series = []
    for d, p in sorted(prices.items()):
        ts_ms = int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
        price_series.append({"t": ts_ms, "p": round(p, 2)})

    now_ts = price_series[-1]["t"] if price_series else now_ms
    now_price = price_series[-1]["p"] if price_series else 0

    # 2) Rolling forecasts (lookback days from now)
    since_ms = now_ms - lookback * 86400 * 1000
    forecasts = list(
        col.find(
            {"asset": asset, "horizon": horizon, "createdAt": {"$gte": since_ms}},
            {"_id": 0},
        ).sort("createdAt", 1)
    )

    rolling = []
    for f in forecasts:
        entry = float(f.get("entryPrice", 0))
        target = float(f.get("targetPrice", 0))
        move = float(f.get("expectedMovePct", 0))
        # Derive move if missing
        if move == 0 and entry > 0 and target > 0:
            move = round(((target - entry) / entry) * 100, 4)

        outcome = f.get("outcome")
        rolling.append({
            "id": f.get("id", ""),
            "madeAtTs": f.get("createdAt", 0),
            "horizonDays": f.get("horizonDays", horizon_days),
            "entryPrice": round(entry, 2),
            "targetPrice": round(target, 2),
            "expectedMovePct": round(move, 4),
            "direction": f.get("direction", "NEUTRAL"),
            "confidence": round(float(f.get("confidence", 0)), 4),
            "evaluated": f.get("evaluated", False),
            "outcome": {
                "realPrice": round(float(outcome.get("realPrice", 0)), 2),
                "label": outcome.get("label"),
                "directionMatch": outcome.get("directionMatch"),
                "errorPct": round(float(outcome.get("errorPct", 0)), 4),
            } if outcome else None,
        })

    # 3) Stats from evaluated forecasts
    evaluated_list = [f for f in rolling if f["evaluated"] and f["outcome"]]
    eval_count = len(evaluated_list)
    if eval_count > 0:
        tp_count = sum(1 for f in evaluated_list if f["outcome"]["label"] == "TP")
        dir_hit = sum(1 for f in evaluated_list if f["outcome"]["directionMatch"])
        deviations = [abs(f["outcome"]["errorPct"]) for f in evaluated_list]
        stats = {
            "winRate": round(tp_count / eval_count, 4),
            "dirHit": round(dir_hit / eval_count, 4),
            "avgDev": round(sum(deviations) / eval_count, 4),
            "evaluatedCount": eval_count,
            "overdue": sum(1 for f in rolling if not f["evaluated"] and f["madeAtTs"] + f["horizonDays"] * 86400000 < now_ms),
        }
    else:
        stats = {"winRate": 0, "dirHit": 0, "avgDev": 0, "evaluatedCount": 0, "overdue": 0}

    latest_ts = rolling[-1]["madeAtTs"] if rolling else None

    # 4) Risk profile
    risk_profile = None
    if eval_count >= 5:
        outcomes_real = [f["outcome"]["realPrice"] for f in evaluated_list if f["outcome"]["realPrice"] > 0]
        entries = [f["entryPrice"] for f in evaluated_list if f["entryPrice"] > 0 and f["outcome"]["realPrice"] > 0]
        if outcomes_real and entries:
            returns = [(o - e) / e for o, e in zip(outcomes_real, entries)]
            up = sum(1 for r in returns if r > 0.02)
            down = sum(1 for r in returns if r < -0.02)
            neutral = len(returns) - up - down
            n = len(returns)
            vol = (sum(r ** 2 for r in returns) / n) ** 0.5 * 100 if n > 0 else 0
            risk_profile = {
                "upside": round(up / n, 4),
                "neutral": round(neutral / n, 4),
                "downside": round(down / n, 4),
                "volatility": round(vol, 2),
                "worstCase": round(now_price * (1 + min(returns)), 2) if returns else 0,
                "bestCase": round(now_price * (1 + max(returns)), 2) if returns else 0,
                "sampleSize": n,
            }

    # 5) Regime info
    drift_full = db["drift_snapshots"].find_one(
        {"asset": asset, "horizon": horizon},
        {"_id": 0},
        sort=[("ts", DESCENDING)],
    )
    current_regime = drift_full.get("regime", "TRANSITION") if drift_full else "TRANSITION"
    regime_conf = drift_full.get("regimeConfidence", 0.5) if drift_full else 0.5
    regime_baseline = db["drift_regime_baselines"].find_one(
        {"regime": current_regime, "horizon": horizon},
        {"_id": 0, "baseline": 1},
    )
    regime_baseline = regime_baseline.get("baseline", {}) if regime_baseline else {}

    regime_info = {
        "current": current_regime,
        "confidence": round(regime_conf, 2),
    }

    # 6) Band data for 30D (right panel numbers only)
    band_data = None
    if horizon == "30D":
        m_ret = regime_baseline.get("median_return", 0.0)
        p25 = regime_baseline.get("p25_return", -0.05)
        p75 = regime_baseline.get("p75_return", 0.05)
        s_ret = regime_baseline.get("std_return", 0.05)

        iqr = p75 - p25
        p10_est = regime_baseline.get("p10_return", p25 - 0.75 * iqr)
        p90_est = regime_baseline.get("p90_return", p75 + 0.75 * iqr)

        shrinkage = 0.75
        if current_regime == "TRANSITION":
            shrinkage *= 0.6
        elif current_regime == "RISK_OFF":
            shrinkage *= 0.7

        neutral_thresh = 0.25 * s_ret
        bias = "LONG" if m_ret > neutral_thresh else ("SHORT" if m_ret < -neutral_thresh else "NEUTRAL")

        band_data = {
            "medianTarget": round(now_price * (1 + m_ret * shrinkage), 2),
            "bandCore": {
                "low": round(now_price * (1 + p25), 2),
                "high": round(now_price * (1 + p75), 2),
            },
            "bandWide": {
                "low": round(now_price * (1 + p10_est), 2),
                "high": round(now_price * (1 + p90_est), 2),
            },
            "bias": bias,
            "signalStrength": round(abs(m_ret) / max(s_ret, 0.001), 4),
        }

    # 7) ETA to Target — historical avg time to hit
    eta_to_target_days = None
    if eval_count >= 5:
        current_dir = rolling[-1]["direction"] if rolling else "NEUTRAL"
        # Normalize direction mapping (LONG↔UP, SHORT↔DOWN)
        dir_aliases = {current_dir}
        if current_dir in ("LONG", "UP"):
            dir_aliases = {"LONG", "UP"}
        elif current_dir in ("SHORT", "DOWN"):
            dir_aliases = {"SHORT", "DOWN"}

        hit_times = []
        tp_errors = []
        for f in evaluated_list:
            if f["outcome"]["label"] == "TP" and f["direction"] in dir_aliases:
                hit_times.append(f["horizonDays"])
                tp_errors.append(abs(f["outcome"]["errorPct"]))

        # Fallback: if too few direction-matched TPs, use all TPs
        if len(hit_times) < 3:
            hit_times = [f["horizonDays"] for f in evaluated_list if f["outcome"]["label"] == "TP"]
            tp_errors = [abs(f["outcome"]["errorPct"]) for f in evaluated_list if f["outcome"]["label"] == "TP"]

        if len(hit_times) >= 3:
            avg_days = sum(hit_times) / len(hit_times)
            if tp_errors:
                avg_error = sum(tp_errors) / len(tp_errors)
                correction = 1.0 - (avg_error / 200)
                avg_days = avg_days * max(correction, 0.5)
            eta_to_target_days = round(avg_days, 1)

    return {
        "ok": True,
        "asset": asset,
        "horizon": horizon,
        "nowTs": now_ts,
        "nowPrice": now_price,
        "priceSeries": price_series,
        "rollingForecasts": rolling,
        "stats": stats,
        "latestForecastTs": latest_ts,
        "band": band_data,
        "riskProfile": risk_profile,
        "regime": regime_info,
        "etaToTargetDays": eta_to_target_days,
    }


# ──────────────────────────────────────────────
# Live BTC Price (Binance public ticker)
# ──────────────────────────────────────────────

@router.get("/live-price")
async def get_live_price(asset: str = Query("BTC")):
    symbol = f"{asset}USDT"
    async with httpx.AsyncClient(timeout=5) as client:
        # Try Binance US
        try:
            resp = await client.get(f"https://api.binance.us/api/v3/ticker/price?symbol={symbol}")
            if resp.status_code == 200:
                return {
                    "ok": True,
                    "asset": asset,
                    "price": round(float(resp.json()["price"]), 2),
                    "source": "binance",
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
        except Exception:
            pass
        # Fallback: CoinPaprika
        try:
            slug = {"BTC": "btc-bitcoin", "ETH": "eth-ethereum"}.get(asset, f"{asset.lower()}-{asset.lower()}")
            resp = await client.get(f"https://api.coinpaprika.com/v1/tickers/{slug}")
            if resp.status_code == 200:
                data = resp.json()
                price = data.get("quotes", {}).get("USD", {}).get("price", 0)
                return {
                    "ok": True,
                    "asset": asset,
                    "price": round(float(price), 2),
                    "source": "coinpaprika",
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
        except Exception:
            pass
    return {"ok": False, "asset": asset, "price": 0, "source": "unavailable"}
