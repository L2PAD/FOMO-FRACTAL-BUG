"""
MetaBrain V2 Shadow Runner
Reads signals from meta_brain_runs, computes real market features,
runs V2 engine, saves to shadow collection.
"""
from __future__ import annotations
import math
import os
from datetime import datetime, timezone

import httpx
from pymongo import MongoClient

from .contracts import ProviderSignal
from .engine_v2 import MetaBrainV2

_client = None
_db = None
_candle_cache: dict = {}


def _get_db():
    global _client, _db
    if _db is None:
        mongo_url = os.environ.get("MONGO_URL", os.environ.get("MONGODB_URI", "mongodb://localhost:27017/intelligence_engine"))
        db_name = os.environ.get("DB_NAME", "intelligence_engine")
        _client = MongoClient(mongo_url)
        _db = _client[db_name]
    return _db


def _extract_signal(signals: list, module_id: str) -> ProviderSignal:
    for s in signals:
        if s.get("moduleId") == module_id:
            raw_score = s.get("score", 0)
            direction = s.get("direction", "NEUTRAL")
            if direction == "SHORT":
                raw_score = -abs(raw_score)
            elif direction == "LONG":
                raw_score = abs(raw_score)
            elif direction == "NEUTRAL":
                raw_score = raw_score * 0.3
            return ProviderSignal(
                score=raw_score,
                confidence=s.get("confidence", 0.5),
                health=s.get("health", "OK"),
                direction=direction,
            )
    return ProviderSignal(score=0, confidence=0.5, health="FAIL", direction="NEUTRAL")


def _fetch_candles_sync(asset: str) -> list:
    """Fetch daily candles from Node.js candle service (synchronous via httpx)."""
    global _candle_cache
    if asset in _candle_cache:
        return _candle_cache[asset]
    try:
        resp = httpx.get(
            f"http://localhost:8003/api/ui/candles?asset={asset}&years=2",
            timeout=10.0,
        )
        data = resp.json()
        if data.get("ok") and data.get("candles"):
            candles = [{"t": c["t"], "c": c["c"]} for c in data["candles"]]
            _candle_cache[asset] = candles
            return candles
    except Exception:
        pass
    return []


def _compute_market_features(candles: list, target_date: str = None) -> dict:
    """Compute real price-based features from candle data."""
    if not candles or len(candles) < 30:
        return {
            "price_now": candles[-1]["c"] if candles else 0,
            "price_change_1d": 0,
            "price_change_7d": 0,
            "price_change_30d": 0,
            "sma20_distance": 0,
            "volatility": 0.03,
        }

    # If target_date provided, slice candles up to that date
    if target_date:
        candles = [c for c in candles if c["t"] <= target_date]
        if len(candles) < 30:
            candles_full = _fetch_candles_sync(candles[0]["t"].split("-")[0] if candles else "BTC")
            candles = candles_full

    if not candles:
        return {"price_now": 0, "price_change_1d": 0, "price_change_7d": 0, "price_change_30d": 0, "sma20_distance": 0, "volatility": 0.03}

    price_now = candles[-1]["c"]
    price_1d = candles[-2]["c"] if len(candles) >= 2 else price_now
    price_7d = candles[-8]["c"] if len(candles) >= 8 else price_now
    price_30d = candles[-31]["c"] if len(candles) >= 31 else price_now

    change_1d = (price_now - price_1d) / price_1d * 100 if price_1d else 0
    change_7d = (price_now - price_7d) / price_7d * 100 if price_7d else 0
    change_30d = (price_now - price_30d) / price_30d * 100 if price_30d else 0

    # SMA20
    sma_window = candles[-20:] if len(candles) >= 20 else candles
    sma20 = sum(c["c"] for c in sma_window) / len(sma_window)
    sma20_distance = (price_now - sma20) / sma20 if sma20 else 0

    # Realized volatility (30D)
    closes = [c["c"] for c in candles[-31:]]
    log_returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            log_returns.append(math.log(closes[i] / closes[i - 1]))
    if log_returns:
        mean_r = sum(log_returns) / len(log_returns)
        var = sum((r - mean_r) ** 2 for r in log_returns) / len(log_returns)
        volatility = math.sqrt(var) * math.sqrt(365)
    else:
        volatility = 0.03

    return {
        "price_now": price_now,
        "price_change_1d": round(change_1d, 4),
        "price_change_7d": round(change_7d, 4),
        "price_change_30d": round(change_30d, 4),
        "sma20_distance": round(sma20_distance, 6),
        "volatility": round(volatility, 4),
    }


def run_v2_on_signals(run_doc: dict, db=None, candles: list = None) -> dict:
    """Run MetaBrain V2 on a single meta_brain_runs document."""
    if db is None:
        db = _get_db()

    signals = run_doc.get("signals", [])
    regime = run_doc.get("regime", "TREND")
    asset = run_doc.get("asset", "BTC")

    exchange = _extract_signal(signals, "exchange")
    sentiment = _extract_signal(signals, "sentiment")
    fractal = _extract_signal(signals, "fractal")
    onchain = _extract_signal(signals, "onchain")

    # Compute REAL market features from candles
    if candles is None:
        candles = _fetch_candles_sync(asset)

    # For historical backfill, we'd need to slice candles to the run date
    # For now, use latest market state
    market = _compute_market_features(candles)

    engine = MetaBrainV2()
    result = engine.predict(
        exchange=exchange,
        sentiment=sentiment,
        fractal=fractal,
        onchain=onchain,
        regime=regime,
        volatility=market["volatility"],
        price_now=market["price_now"],
        price_change_1d=market["price_change_1d"],
        price_change_7d=market["price_change_7d"],
        price_change_30d=market["price_change_30d"],
        sma20_distance=market["sma20_distance"],
    )

    return {
        "asset": asset,
        "runId": run_doc.get("runId", ""),
        "horizonDays": run_doc.get("horizonDays", 7),
        "priceNow": market["price_now"],
        "volatility": market["volatility"],
        "market_features": {
            "price_change_1d": market["price_change_1d"],
            "price_change_7d": market["price_change_7d"],
            "price_change_30d": market["price_change_30d"],
            "sma20_distance": market["sma20_distance"],
        },
        "v1_verdict": run_doc.get("metaFinalVerdict", "NEUTRAL"),
        "v1_score": run_doc.get("metaRawScore", 0),
        "v2_direction": result["direction"],
        "v2_confidence": result["confidence"],
        "v2_score": result["score"],
        "v2_threshold": result["threshold"],
        "v2_mode": result["mode"],
        "v2_targets": result["targets"],
        "v2_components": result["components"],
        "agreement": run_doc.get("metaFinalVerdict", "NEUTRAL") == result["direction"],
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def run_v2_latest(asset: str = "BTC") -> dict:
    """Run V2 on the most recent meta_brain_runs entry."""
    db = _get_db()
    latest_run = db["meta_brain_runs"].find_one(
        {"asset": asset}, sort=[("createdAt", -1)]
    )
    if not latest_run:
        return {"error": "No runs found"}

    candles = _fetch_candles_sync(asset)
    result = run_v2_on_signals(latest_run, db, candles)

    # Save to shadow collection
    db["meta_brain_v2_shadow"].insert_one({**result})
    result.pop("_id", None)
    return result


def backfill_v2(asset: str = "BTC") -> dict:
    """Run V2 on all historical meta_brain_runs using historical candle data."""
    db = _get_db()
    runs = list(
        db["meta_brain_runs"]
        .find({"asset": asset})
        .sort("createdAt", 1)
    )

    if not runs:
        return {"error": "No runs found", "processed": 0}

    candles = _fetch_candles_sync(asset)
    if not candles:
        return {"error": "Cannot fetch candle data", "processed": 0}

    stats = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0, "total": 0, "agreement": 0}
    sample_rows = []

    # Build date->candle-index map for historical slicing
    date_to_idx = {}
    for i, c in enumerate(candles):
        date_to_idx[c["t"]] = i

    for run_doc in runs:
        # Extract run date from runId (format: run_BTC_7D_2026-03-05T10)
        run_id = run_doc.get("runId", "")
        run_date = None
        parts = run_id.split("_")
        for p in parts:
            if p.startswith("20") and len(p) >= 10:
                run_date = p[:10]
                break

        # Slice candles to the run date for historical accuracy
        if run_date and run_date in date_to_idx:
            idx = date_to_idx[run_date] + 1
            historical_candles = candles[:idx]
        else:
            historical_candles = candles

        market = _compute_market_features(historical_candles)

        signals = run_doc.get("signals", [])
        regime = run_doc.get("regime", "TREND")

        exchange = _extract_signal(signals, "exchange")
        sentiment = _extract_signal(signals, "sentiment")
        fractal = _extract_signal(signals, "fractal")
        onchain = _extract_signal(signals, "onchain")

        engine = MetaBrainV2()
        result = engine.predict(
            exchange=exchange,
            sentiment=sentiment,
            fractal=fractal,
            onchain=onchain,
            regime=regime,
            volatility=market["volatility"],
            price_now=market["price_now"],
            price_change_1d=market["price_change_1d"],
            price_change_7d=market["price_change_7d"],
            price_change_30d=market["price_change_30d"],
            sma20_distance=market["sma20_distance"],
        )

        shadow_doc = {
            "asset": asset,
            "runId": run_doc.get("runId", ""),
            "runDate": run_date or "",
            "horizonDays": run_doc.get("horizonDays", 7),
            "priceNow": market["price_now"],
            "volatility": market["volatility"],
            "market_features": {
                "price_change_1d": market["price_change_1d"],
                "price_change_7d": market["price_change_7d"],
                "price_change_30d": market["price_change_30d"],
                "sma20_distance": market["sma20_distance"],
            },
            "v1_verdict": run_doc.get("metaFinalVerdict", "NEUTRAL"),
            "v1_score": run_doc.get("metaRawScore", 0),
            "v2_direction": result["direction"],
            "v2_confidence": result["confidence"],
            "v2_score": result["score"],
            "v2_threshold": result["threshold"],
            "v2_mode": result["mode"],
            "v2_targets": result["targets"],
            "v2_components": result["components"],
            "agreement": run_doc.get("metaFinalVerdict", "NEUTRAL") == result["direction"],
            "ts": datetime.now(timezone.utc).isoformat(),
        }

        stats[result["direction"]] += 1
        stats["total"] += 1
        if shadow_doc["agreement"]:
            stats["agreement"] += 1

        if len(sample_rows) < 5:
            sample_rows.append({
                "runId": shadow_doc["runId"],
                "runDate": shadow_doc["runDate"],
                "v1": shadow_doc["v1_verdict"],
                "v2": result["direction"],
                "score": result["score"],
                "conf": result["confidence"],
                "price": market["price_now"],
                "chg1d": market["price_change_1d"],
                "chg7d": market["price_change_7d"],
                "momentum": result["components"]["momentum_score"],
            })

        db["meta_brain_v2_shadow"].update_one(
            {"runId": shadow_doc["runId"]},
            {"$set": shadow_doc},
            upsert=True,
        )

    return {
        "processed": stats["total"],
        "distribution": {
            "LONG": stats["LONG"],
            "SHORT": stats["SHORT"],
            "NEUTRAL": stats["NEUTRAL"],
        },
        "pct_directional": round(
            (stats["LONG"] + stats["SHORT"]) / max(stats["total"], 1) * 100, 1
        ),
        "agreement_with_v1": round(
            stats["agreement"] / max(stats["total"], 1) * 100, 1
        ),
        "sample_rows": sample_rows,
    }


def backfill_v2_daily(asset: str = "BTC") -> dict:
    """Run V2 for each unique date in meta_brain_forecasts using real market features.

    This gives us 31 days of V2 results (1 per day) with actual price dynamics.
    Provider signals are taken from the closest meta_brain_runs entry for that date.
    """
    db = _get_db()
    candles = _fetch_candles_sync(asset)
    if not candles:
        return {"error": "Cannot fetch candle data", "processed": 0}

    # Get unique dates from forecasts
    pipeline = [
        {"$match": {"asset": asset}},
        {"$group": {"_id": "$date"}},
        {"$sort": {"_id": 1}},
    ]
    dates = [r["_id"] for r in db["meta_brain_forecasts"].aggregate(pipeline)]
    if not dates:
        return {"error": "No forecast snapshots", "processed": 0}

    # Build date->candle-index map
    date_to_idx = {}
    for i, c in enumerate(candles):
        date_to_idx[c["t"]] = i

    # Get ALL runs to pick closest signals per date
    all_runs = list(db["meta_brain_runs"].find({"asset": asset}))
    run_by_date = {}
    for r in all_runs:
        run_id = r.get("runId", "")
        parts = run_id.split("_")
        for p in parts:
            if p.startswith("20") and len(p) >= 10:
                rd = p[:10]
                run_by_date.setdefault(rd, []).append(r)
                break

    # Get latest forecast snapshot per date for priceNow + verdict
    snap_by_date = {}
    for snap in db["meta_brain_forecasts"].find({"asset": asset}, {"_id": 0}).sort("ts", -1):
        d = snap.get("date", "")
        if d and d not in snap_by_date:
            snap_by_date[d] = snap

    stats = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0, "total": 0}
    results = []

    for date_str in dates:
        idx = date_to_idx.get(date_str)
        if idx is None or idx < 30:
            continue

        historical_candles = candles[: idx + 1]
        market = _compute_market_features(historical_candles)

        # Use run signals if available, otherwise use static fallback
        run_list = run_by_date.get(date_str, [])
        if run_list:
            signals = run_list[0].get("signals", [])
            regime = run_list[0].get("regime", "TREND")
        else:
            # Fallback: use closest earlier date
            closest_run = None
            for d in sorted(run_by_date.keys(), reverse=True):
                if d <= date_str:
                    closest_run = run_by_date[d][0]
                    break
            if closest_run:
                signals = closest_run.get("signals", [])
                regime = closest_run.get("regime", "TREND")
            else:
                signals = []
                regime = "TREND"

        exchange = _extract_signal(signals, "exchange")
        sentiment = _extract_signal(signals, "sentiment")
        fractal = _extract_signal(signals, "fractal")
        onchain = _extract_signal(signals, "onchain")

        snap = snap_by_date.get(date_str, {})
        v1_verdict = snap.get("verdict", "NEUTRAL")

        engine = MetaBrainV2()
        result = engine.predict(
            exchange=exchange,
            sentiment=sentiment,
            fractal=fractal,
            onchain=onchain,
            regime=regime,
            volatility=market["volatility"],
            price_now=market["price_now"],
            price_change_1d=market["price_change_1d"],
            price_change_7d=market["price_change_7d"],
            price_change_30d=market["price_change_30d"],
            sma20_distance=market["sma20_distance"],
        )

        doc_id = f"daily_{asset}_{date_str}"
        shadow_doc = {
            "shadowId": doc_id,
            "asset": asset,
            "runDate": date_str,
            "horizonDays": 7,
            "priceNow": market["price_now"],
            "volatility": market["volatility"],
            "market_features": {
                "price_change_1d": market["price_change_1d"],
                "price_change_7d": market["price_change_7d"],
                "price_change_30d": market["price_change_30d"],
                "sma20_distance": market["sma20_distance"],
            },
            "v1_verdict": v1_verdict,
            "v2_direction": result["direction"],
            "v2_confidence": result["confidence"],
            "v2_score": result["score"],
            "v2_threshold": result["threshold"],
            "v2_mode": result["mode"],
            "v2_targets": result["targets"],
            "v2_components": result["components"],
            "agreement": v1_verdict == result["direction"],
            "ts": datetime.now(timezone.utc).isoformat(),
        }

        stats[result["direction"]] += 1
        stats["total"] += 1

        results.append({
            "date": date_str,
            "price": round(market["price_now"], 0),
            "v1": v1_verdict,
            "v2": result["direction"],
            "score": result["score"],
            "conf": result["confidence"],
            "chg1d": market["price_change_1d"],
            "chg7d": market["price_change_7d"],
            "sma20": round(market["sma20_distance"], 4),
            "momentum": round(result["components"]["momentum_score"], 4),
        })

        db["meta_brain_v2_daily"].update_one(
            {"shadowId": doc_id},
            {"$set": shadow_doc},
            upsert=True,
        )

    return {
        "processed": stats["total"],
        "distribution": {
            "LONG": stats["LONG"],
            "SHORT": stats["SHORT"],
            "NEUTRAL": stats["NEUTRAL"],
        },
        "pct_directional": round(
            (stats["LONG"] + stats["SHORT"]) / max(stats["total"], 1) * 100, 1
        ),
        "daily_results": results,
    }



def get_v1_vs_v2_comparison(asset: str = "BTC") -> dict:
    """Compare V1 vs V2 results from shadow collection."""
    db = _get_db()
    shadow_docs = list(
        db["meta_brain_v2_shadow"]
        .find({"asset": asset}, {"_id": 0})
        .sort("ts", -1)
        .limit(100)
    )

    if not shadow_docs:
        return {"error": "No shadow data. Run backfill first.", "rows": []}

    stats = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0, "total": 0, "agreement": 0}
    conf_sum = 0
    scores = []

    for doc in shadow_docs:
        d = doc.get("v2_direction", "NEUTRAL")
        stats[d] += 1
        stats["total"] += 1
        if doc.get("agreement"):
            stats["agreement"] += 1
        conf_sum += doc.get("v2_confidence", 0)
        scores.append(doc.get("v2_score", 0))

    total = max(stats["total"], 1)

    return {
        "total_runs": stats["total"],
        "v2_distribution": {
            "LONG": stats["LONG"],
            "SHORT": stats["SHORT"],
            "NEUTRAL": stats["NEUTRAL"],
        },
        "pct_directional": round((stats["LONG"] + stats["SHORT"]) / total * 100, 1),
        "pct_agreement_with_v1": round(stats["agreement"] / total * 100, 1),
        "avg_confidence": round(conf_sum / total, 4),
        "avg_score": round(sum(scores) / total, 4),
        "score_range": [round(min(scores), 4), round(max(scores), 4)] if scores else [0, 0],
        "rows": shadow_docs[:20],
    }


def get_live_metrics(asset: str = "BTC") -> dict:
    """Live metrics for V2 shadow runs."""
    db = _get_db()
    total = db["meta_brain_v2_shadow"].count_documents({"asset": asset})
    if total == 0:
        return {"error": "No shadow data", "total": 0}

    pipeline = [
        {"$match": {"asset": asset}},
        {
            "$group": {
                "_id": "$v2_direction",
                "count": {"$sum": 1},
                "avg_conf": {"$avg": "$v2_confidence"},
                "avg_score": {"$avg": "$v2_score"},
            }
        },
    ]
    direction_stats = {}
    for r in db["meta_brain_v2_shadow"].aggregate(pipeline):
        direction_stats[r["_id"]] = {
            "count": r["count"],
            "pct": round(r["count"] / total * 100, 1),
            "avg_confidence": round(r["avg_conf"], 4),
            "avg_score": round(r["avg_score"], 4),
        }

    latest = db["meta_brain_v2_shadow"].find_one(
        {"asset": asset}, {"_id": 0}, sort=[("ts", -1)]
    )

    return {
        "total_runs": total,
        "direction_stats": direction_stats,
        "pct_directional": round(
            (direction_stats.get("LONG", {}).get("count", 0)
             + direction_stats.get("SHORT", {}).get("count", 0))
            / total * 100, 1
        ),
        "latest": latest,
    }
