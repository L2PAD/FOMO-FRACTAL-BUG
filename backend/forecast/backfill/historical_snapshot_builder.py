"""
Historical Snapshot Builder
=============================
Builds point-in-time snapshots for replay.
CRITICAL: Only uses data available at as_of date. No future leakage.
"""

import hashlib
import math
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient, DESCENDING

from forecast.v41_config import BASELINE_BLEND


def _get_db():
    import os
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    return MongoClient(mongo_url)[db_name]


def build_snapshot(
    asset: str,
    as_of: str,
    horizon: str,
    prices: dict[str, float],
) -> dict | None:
    """
    Build point-in-time snapshot for a given date.
    Only uses prices up to as_of.
    Reconstructs baselines from historically available data.
    """
    # Filter prices to point-in-time
    pit_prices = {d: p for d, p in prices.items() if d <= as_of}

    if len(pit_prices) < 14:
        return None

    features = _compute_features_pit(pit_prices, as_of)
    if not features:
        return None

    regime = _compute_regime_pit(pit_prices)
    baseline = _compute_baseline_pit(asset, horizon, regime, as_of)
    perf = _compute_recent_perf_pit(asset, horizon, as_of)

    return {
        "as_of": as_of,
        "asset": asset,
        "horizon": horizon,
        "prices": pit_prices,
        "features": features,
        "regime": regime,
        "regime_confidence": 0.6,
        "baseline": baseline,
        "recent_perf": perf,
    }


def _compute_features_pit(prices: dict, as_of: str) -> dict | None:
    """Compute features using only data up to as_of."""
    sorted_dates = sorted(d for d in prices if d <= as_of)
    if len(sorted_dates) < 14:
        return None

    closes = [prices[d] for d in sorted_dates[-14:]]
    current = closes[-1]
    ret_1d = (closes[-1] - closes[-2]) / closes[-2]
    ret_7d = (closes[-1] - closes[-8]) / closes[-8] if len(closes) >= 8 else 0
    ret_14d = (closes[-1] - closes[0]) / closes[0]

    daily_returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    volatility = (sum(r ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5

    momentum = ret_1d * 0.5 + ret_7d * 0.3 + ret_14d * 0.2

    features_hash = hashlib.sha256(
        f"{current:.2f}:{ret_1d:.6f}:{ret_7d:.6f}:{volatility:.6f}".encode()
    ).hexdigest()[:16]

    return {
        "price": current,
        "ret_1d": ret_1d,
        "ret_7d": ret_7d,
        "ret_14d": ret_14d,
        "volatility": volatility,
        "momentum": momentum,
        "features_hash": features_hash,
    }


def _compute_regime_pit(prices: dict) -> str:
    """
    Compute regime from price data only. No DB writes, no hysteresis.
    Pure point-in-time computation.
    """
    dates = sorted(prices.keys())
    if len(dates) < 14:
        return "TRANSITION"

    n = min(30, len(dates))
    price_list = [prices[d] for d in dates[-n:]]
    returns = [(price_list[i] - price_list[i - 1]) / price_list[i - 1] for i in range(1, len(price_list))]

    vol_30d = (sum(r ** 2 for r in returns) / len(returns)) ** 0.5 * math.sqrt(365) if returns else 0
    ma_period = len(price_list)
    ma = sum(price_list) / ma_period
    ma_5ago = sum(price_list[:-5]) / max(1, ma_period - 5) if ma_period > 5 else ma
    slope = (ma - ma_5ago) / ma_5ago if ma_5ago > 0 else 0
    max_7d = max(price_list[-7:]) if len(price_list) >= 7 else price_list[-1]
    drawdown = (price_list[-1] - max_7d) / max_7d if max_7d > 0 else 0

    if drawdown < -0.10 and vol_30d > 0.50:
        return "RISK_OFF"
    if abs(slope) > 0.002 and vol_30d <= 0.85:
        return "TREND"
    if vol_30d <= 0.45 and abs(slope) <= 0.002 and drawdown > -0.10:
        return "RANGE"
    return "TRANSITION"


def _compute_baseline_pit(asset: str, horizon: str, regime: str, as_of: str) -> dict:
    """
    Reconstruct blended baseline using only forecasts evaluated BEFORE as_of.
    Point-in-time: no future data.
    """
    db = _get_db()
    cfg = BASELINE_BLEND
    as_of_dt = datetime.strptime(as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    as_of_ms = int(as_of_dt.timestamp() * 1000)

    # Long-term baseline from stored regime baselines (considered stable)
    baseline_doc = db["drift_regime_baselines"].find_one(
        {"regime": regime, "horizon": horizon},
        {"_id": 0, "baseline": 1},
    )
    long_bl = baseline_doc.get("baseline", {}) if baseline_doc else {}
    long_data = {
        "meanReturn": long_bl.get("mean_return", 0.0),
        "stdReturn": long_bl.get("std_return", 0.05),
        "maeMean": long_bl.get("mae_mean", 0.05),
        "dirHitMean": long_bl.get("dir_hit_mean", 0.5),
        "medianReturn": long_bl.get("median_return", 0.0),
        "p25Return": long_bl.get("p25_return", -0.05),
        "p75Return": long_bl.get("p75_return", 0.05),
        "sampleSize": long_bl.get("n", 0),
    }

    # Recent baseline: only from forecasts created AND evaluable before as_of
    recent_cutoff = as_of_ms - cfg["recent_window_days"] * 86_400_000

    recent_docs = list(db["exchange_forecasts"].find(
        {
            "asset": asset,
            "horizon": horizon,
            "evaluated": True,
            "outcome": {"$ne": None},
            "createdAt": {"$gte": recent_cutoff, "$lt": as_of_ms},
        },
        {"_id": 0, "outcome": 1, "direction": 1, "targetPrice": 1, "entryPrice": 1},
    ))

    if len(recent_docs) < cfg["min_recent_samples"]:
        fallback_cutoff = as_of_ms - cfg["fallback_window_days"] * 86_400_000
        recent_docs = list(db["exchange_forecasts"].find(
            {
                "asset": asset,
                "horizon": horizon,
                "evaluated": True,
                "outcome": {"$ne": None},
                "createdAt": {"$gte": fallback_cutoff, "$lt": as_of_ms},
            },
            {"_id": 0, "outcome": 1, "direction": 1, "targetPrice": 1, "entryPrice": 1},
        ))

    if len(recent_docs) >= cfg["min_recent_samples"]:
        import numpy as np
        errors, dir_hits, returns = [], [], []
        for doc in recent_docs:
            outcome = doc.get("outcome", {})
            entry = doc.get("entryPrice", 0)
            target = doc.get("targetPrice", entry)
            real_price = outcome.get("realPrice") or outcome.get("actualPriceAtEval", 0)
            if entry > 0 and real_price and real_price > 0:
                r_real = (real_price / entry) - 1
                r_rule = (target / entry) - 1
                returns.append(r_real)
                errors.append(abs(r_real - r_rule))
                dir_match = (r_real > 0) == (r_rule > 0) if r_rule != 0 else False
                dir_hits.append(1 if dir_match else 0)

        if returns:
            recent_data = {
                "meanReturn": float(np.mean(returns)),
                "stdReturn": float(np.std(returns)) if len(returns) > 1 else 0.05,
                "maeMean": float(np.mean(errors)) if errors else 0.05,
                "dirHitMean": float(np.mean(dir_hits)) if dir_hits else 0.5,
                "medianReturn": float(np.median(returns)),
                "p25Return": float(np.percentile(returns, 25)),
                "p75Return": float(np.percentile(returns, 75)),
                "sampleSize": len(returns),
            }

            rw, lw = cfg["recent_weight"], cfg["long_weight"]
            blended = {}
            for key in ("meanReturn", "stdReturn", "maeMean", "dirHitMean", "medianReturn", "p25Return", "p75Return"):
                blended[key] = rw * recent_data[key] + lw * long_data[key]
            blended["sampleSize"] = recent_data["sampleSize"] + long_data["sampleSize"]
            blended["baselineSource"] = "blended"
            blended["recentSamples"] = recent_data["sampleSize"]
            return blended

    long_data["baselineSource"] = "long_only"
    long_data["recentSamples"] = 0
    return long_data


def _compute_recent_perf_pit(asset: str, horizon: str, as_of: str) -> dict:
    """
    Compute rolling recent performance using only forecasts
    with outcomes known BEFORE as_of.
    """
    db = _get_db()
    as_of_dt = datetime.strptime(as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    as_of_ms = int(as_of_dt.timestamp() * 1000)

    recent = list(db["exchange_forecasts"].find(
        {
            "asset": asset,
            "horizon": horizon,
            "outcome": {"$ne": None},
            "createdAt": {"$lt": as_of_ms},
        },
        {"_id": 0, "outcome": 1},
    ).sort("createdBucket", DESCENDING).limit(5))

    if not recent:
        return {"rollingWinRate": 0.5, "recentCount": 0}

    wins = sum(1 for r in recent if r.get("outcome", {}).get("label") == "TP")
    return {"rollingWinRate": wins / len(recent), "recentCount": len(recent)}
