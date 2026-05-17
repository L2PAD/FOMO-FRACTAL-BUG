"""
Drift Intelligence — Metrics Engine
======================================
Block 6.1

Computes performance metrics sliced by multiple dimensions:
  - Time (rolling windows)
  - Model version
  - Confidence bucket
  - Direction
  - Regime (from obs join where available)
  - Outcome label distribution

Data sources:
  - exchange_forecasts (evaluated=True, with outcomes)
  - exchange_observations (for regime join)
"""

import os
import math
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

OBS_WINDOW_MS = 3600 * 1000


def _get_db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _compute_bucket_metrics(forecasts: list) -> dict:
    """Compute accuracy, PnL, catastrophic rate from a list of forecasts."""
    n = len(forecasts)
    if n == 0:
        return {"n": 0, "accuracy": 0, "pnl": 0, "catastrophic_rate": 0, "avg_error": 0}

    correct = 0
    pnl = 0
    catastrophic = 0
    total_error = 0

    for f in forecasts:
        outcome = f.get("outcome") or {}
        real_move = outcome.get("realMovePct") or 0
        dir_match = outcome.get("directionMatch", False)
        label = outcome.get("label", "")
        direction = (f.get("direction") or "NEUTRAL").upper()

        # Accuracy: TP or direction match
        if label == "TP" or dir_match:
            correct += 1

        # PnL simulation (simplified: long if LONG, short if SHORT, flat if NEUTRAL)
        if direction in ("LONG", "UP"):
            pnl += real_move
        elif direction in ("SHORT", "DOWN"):
            pnl -= real_move

        # Catastrophic
        if abs(real_move) > 5 and not dir_match:
            catastrophic += 1

        total_error += abs(outcome.get("errorPct") or real_move or 0)

    return {
        "n": n,
        "accuracy": round(correct / n, 3) if n > 0 else 0,
        "pnl": round(pnl, 2),
        "catastrophic_rate": round(catastrophic / n, 3) if n > 0 else 0,
        "avg_error": round(total_error / n, 2) if n > 0 else 0,
        "hit_rate": round(sum(1 for f in forecasts if (f.get("outcome") or {}).get("hit")) / n, 3) if n > 0 else 0,
    }


def _confidence_bucket(conf: float) -> str:
    if conf < 0.2:
        return "very_low"
    elif conf < 0.35:
        return "low"
    elif conf < 0.5:
        return "medium"
    else:
        return "high"


def compute_drift_metrics(
    horizon_days: int = 7,
    asset: str = "BTC",
    rolling_window_days: int = 14,
) -> dict:
    """
    Compute performance metrics across multiple dimensions.

    Returns metrics sliced by: global, time windows, confidence, model version,
    direction, outcome distribution, and regime (where available).
    """
    db = _get_db()
    symbol = f"{asset}USDT"

    forecasts = list(
        db["exchange_forecasts"]
        .find(
            {
                "evaluated": True,
                "horizonDays": horizon_days,
                "outcome": {"$exists": True, "$ne": None},
                "asset": asset,
            },
            {"_id": 0},
        )
        .sort("createdAt", 1)
    )

    n = len(forecasts)
    if n == 0:
        return {"ok": False, "error": "No evaluated forecasts"}

    # ── Global metrics ──
    global_metrics = _compute_bucket_metrics(forecasts)

    # ── By time windows (rolling) ──
    window_ms = rolling_window_days * 24 * 3600 * 1000
    time_buckets = defaultdict(list)
    for f in forecasts:
        ts = f.get("createdAt", 0)
        bucket_start = ts - (ts % window_ms)
        dt = datetime.fromtimestamp(bucket_start / 1000, tz=timezone.utc)
        key = dt.strftime("%Y-%m-%d")
        time_buckets[key].append(f)

    by_time = {}
    for key in sorted(time_buckets.keys()):
        by_time[key] = _compute_bucket_metrics(time_buckets[key])

    # ── By confidence bucket ──
    conf_buckets = defaultdict(list)
    for f in forecasts:
        bucket = _confidence_bucket(f.get("confidence", 0))
        conf_buckets[bucket].append(f)

    by_confidence = {k: _compute_bucket_metrics(v) for k, v in conf_buckets.items()}

    # ── By model version ──
    version_buckets = defaultdict(list)
    for f in forecasts:
        version_buckets[f.get("modelVersion", "unknown")].append(f)

    by_version = {k: _compute_bucket_metrics(v) for k, v in version_buckets.items()}

    # ── By direction ──
    dir_buckets = defaultdict(list)
    for f in forecasts:
        dir_buckets[f.get("direction", "NEUTRAL")].append(f)

    by_direction = {k: _compute_bucket_metrics(v) for k, v in dir_buckets.items()}

    # ── Outcome label distribution over time ──
    label_trend = {}
    for key in sorted(time_buckets.keys()):
        labels = defaultdict(int)
        for f in time_buckets[key]:
            lbl = (f.get("outcome") or {}).get("label", "UNKNOWN")
            labels[lbl] += 1
        total = sum(labels.values())
        label_trend[key] = {k: round(v / total, 3) for k, v in labels.items()}

    # ── By regime (from obs join, limited coverage) ──
    by_regime = defaultdict(list)
    regime_coverage = 0
    for f in forecasts:
        ts = f.get("createdAt", 0)
        obs = db["exchange_observations"].find_one(
            {"$or": [{"asset": asset}, {"symbol": symbol}], "timestamp": {"$lte": ts, "$gte": ts - OBS_WINDOW_MS}},
            {"_id": 0, "regime": 1},
        )
        if obs and obs.get("regime"):
            regime_type = obs["regime"].get("type", "UNKNOWN")
            by_regime[regime_type].append(f)
            regime_coverage += 1

    by_regime_metrics = {k: _compute_bucket_metrics(v) for k, v in by_regime.items()}

    return {
        "ok": True,
        "horizon": f"{horizon_days}D",
        "total_forecasts": n,
        "rolling_window_days": rolling_window_days,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "global": global_metrics,
        "by_time": by_time,
        "by_confidence": by_confidence,
        "by_version": by_version,
        "by_direction": by_direction,
        "by_regime": by_regime_metrics,
        "regime_coverage": round(regime_coverage / n, 3) if n > 0 else 0,
        "label_trend": label_trend,
    }
