"""
Exchange Health Metrics — Stabilization Dashboard
===================================================
3 metrics only. Nothing more.

1. Base Dominance Rate — % of 30D forecasts where base = dominant
2. Scenario Truthfulness — % of correct dominant scenario predictions
3. Catastrophic Rate — % of direction-wrong + significant-move forecasts

Status: STABLE / WARNING / UNSTABLE
"""

import os
from datetime import datetime, timezone, timedelta

CATASTROPHIC_THRESHOLDS = {"24H": 2.0, "7D": 5.0, "30D": 8.0}


def _get_db():
    from pymongo import MongoClient
    return MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]


def _get_forecasts(asset: str = None, horizon: str = None, days: int = 14):
    """Fetch recent forecasts within the given time window."""
    db = _get_db()
    cutoff_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    query = {"createdAt": {"$gte": cutoff_ms}}
    if asset:
        query["asset"] = asset.upper()
    if horizon:
        query["horizon"] = horizon

    return list(db["exchange_forecasts"].find(query, {"_id": 0}))


def _compute_base_dominance(forecasts: list) -> dict:
    """Metric 1: Base Dominance Rate for 30D forecasts."""
    f30d = [f for f in forecasts if f.get("horizon") == "30D"]
    if not f30d:
        return {"rate": 0.0, "count": 0, "total": 0, "status": "no_data"}

    base_count = 0
    for f in f30d:
        scenarios = f.get("scenarios") or {}
        dominant = scenarios.get("dominant", "")
        if dominant == "base":
            base_count += 1

    rate = base_count / len(f30d)

    if rate > 0.60:
        status = "problem"
    elif rate > 0.45:
        status = "watch"
    else:
        status = "ok"

    return {"rate": round(rate, 4), "count": base_count, "total": len(f30d), "status": status}


def _compute_scenario_truthfulness(forecasts: list) -> dict:
    """Metric 2: Scenario Truthfulness — correct dominant scenario vs reality."""
    evaluated = [f for f in forecasts if f.get("evaluated") and f.get("outcome")]
    if not evaluated:
        return {"rate": 0.0, "correct": 0, "total": 0, "status": "no_data"}

    correct = 0
    total = 0

    for f in evaluated:
        scenarios = f.get("scenarios") or {}
        dominant = scenarios.get("dominant")
        if not dominant:
            continue

        outcome = f.get("outcome") or {}
        entry = f.get("entryPrice") or 0
        actual = outcome.get("actualPriceAtEval") or outcome.get("realPrice", 0) or 0
        if entry <= 0 or actual <= 0:
            continue

        real_move_pct = ((actual - entry) / entry) * 100
        horizon = f.get("horizon", "7D")
        threshold = CATASTROPHIC_THRESHOLDS.get(horizon, 5.0) * 0.5

        # Determine actual scenario outcome
        if real_move_pct > threshold:
            actual_scenario = "bullish"
        elif real_move_pct < -threshold:
            actual_scenario = "bearish"
        else:
            actual_scenario = "base"

        total += 1
        if dominant == actual_scenario:
            correct += 1

    rate = correct / total if total > 0 else 0.0

    if total == 0:
        status = "no_data"
    elif rate >= 0.55:
        status = "ok"
    elif rate >= 0.45:
        status = "watch"
    else:
        status = "problem"

    return {"rate": round(rate, 4), "correct": correct, "total": total, "status": status}


def _compute_catastrophic_rate(forecasts: list) -> dict:
    """Metric 3: Catastrophic Rate — direction wrong + big adverse move."""
    evaluated = [f for f in forecasts if f.get("evaluated") and f.get("outcome")]
    if not evaluated:
        return {"rate": 0.0, "count": 0, "total": 0, "status": "no_data"}

    catastrophic = 0
    total = 0

    for f in evaluated:
        outcome = f.get("outcome") or {}
        entry = f.get("entryPrice") or 0
        actual = outcome.get("actualPriceAtEval") or outcome.get("realPrice", 0) or 0
        if entry <= 0 or actual <= 0:
            continue

        real_move_pct = ((actual - entry) / entry) * 100
        direction = (f.get("direction") or "NEUTRAL").upper()
        horizon = f.get("horizon", "7D")
        threshold = CATASTROPHIC_THRESHOLDS.get(horizon, 5.0)

        total += 1

        is_cat = False
        if direction == "LONG" and real_move_pct < -threshold:
            is_cat = True
        elif direction == "SHORT" and real_move_pct > threshold:
            is_cat = True
        elif direction == "NEUTRAL" and abs(real_move_pct) > threshold * 1.5:
            is_cat = True

        if is_cat:
            catastrophic += 1

    rate = catastrophic / total if total > 0 else 0.0

    if rate < 0.20:
        status = "ok"
    elif rate < 0.30:
        status = "watch"
    else:
        status = "problem"

    return {"rate": round(rate, 4), "count": catastrophic, "total": total, "status": status}


def _compute_overall_status(base: dict, accuracy: dict, catastrophic: dict) -> str:
    """Derive overall system status from 3 metrics."""
    # Metrics with no_data don't count as problems
    active_metrics = [m for m in [base, accuracy, catastrophic] if m.get("status") != "no_data"]
    problems = sum(1 for m in active_metrics if m.get("status") == "problem")
    warnings = sum(1 for m in active_metrics if m.get("status") == "watch")

    if problems >= 2:
        return "UNSTABLE"
    if problems >= 1 or warnings >= 2:
        return "WARNING"
    return "STABLE"


def get_health_metrics(asset: str = None, days: int = 14) -> dict:
    """
    Main entry: compute all 3 health metrics.

    Args:
        asset: Filter by asset (None = all assets)
        days: Lookback window in days
    """
    forecasts = _get_forecasts(asset=asset, days=days)

    base = _compute_base_dominance(forecasts)
    accuracy = _compute_scenario_truthfulness(forecasts)
    catastrophic = _compute_catastrophic_rate(forecasts)
    status = _compute_overall_status(base, accuracy, catastrophic)

    return {
        "asset": asset or "ALL",
        "window_days": days,
        "forecast_count": len(forecasts),
        "base_dominance": base,
        "scenario_accuracy": accuracy,
        "catastrophic_rate": catastrophic,
        "status": status,
    }
