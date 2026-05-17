"""
Fractal Forecast Evaluator V2 (Multi-metric)
==============================================
Sprint 5: F1-F5 blocks.

Evaluation metrics:
  F1 — tolerance_hit: abs(predicted - actual) / actual < threshold
  F2 — range_hit: actual falls within predicted band
  F3 — direction_hit: sign(predicted_move) == sign(actual_move)
  F4 — multi-metric audit: fractal_eval dict
  F5 — probabilistic composite score (not just exact TP)

Each scope resolves against its own candle/price data.
Once resolved, a forecast is NEVER modified again.
"""

from datetime import datetime, timezone

from fractal_forecast.common import get_forecast_col, get_ohlcv_col, HIT_THRESHOLDS


# ── Range expansion factors per horizon ──
RANGE_BAND_PCT = {
    "7D": 0.03,
    "30D": 0.05,
    "90D": 0.08,
    "180D": 0.12,
    "365D": 0.15,
}

# ── Direction tolerance: for NEUTRAL, market must stay within this % ──
NEUTRAL_TOLERANCE = {
    "7D": 0.02,
    "30D": 0.04,
    "90D": 0.06,
    "180D": 0.10,
    "365D": 0.15,
}


def _get_historical_price(target_date, scope="BTC"):
    """
    Get close price for a specific date.
    Uses fractal_canonical_ohlcv with meta.symbol matching the scope.
    """
    col = get_ohlcv_col()
    symbol = scope

    day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start.replace(hour=23, minute=59, second=59)

    doc = col.find_one(
        {"meta.symbol": symbol, "ts": {"$gte": day_start, "$lte": day_end}},
        {"_id": 0, "ohlcv.c": 1},
    )
    if doc and doc.get("ohlcv", {}).get("c"):
        return doc["ohlcv"]["c"]

    # Fallback: closest earlier date
    doc = col.find_one(
        {"meta.symbol": symbol, "ts": {"$lte": day_end}},
        {"_id": 0, "ohlcv.c": 1},
        sort=[("ts", -1)],
    )
    if doc and doc.get("ohlcv", {}).get("c"):
        return doc["ohlcv"]["c"]

    return None


def _evaluate_forecast(forecast, actual_price):
    """
    Multi-metric evaluation for a single forecast.
    Returns evaluation dict with F1-F5 metrics.
    """
    target = forecast["targetPrice"]
    entry = forecast.get("entryPrice", target)
    direction = forecast.get("direction", "NEUTRAL")
    horizon = forecast.get("horizon", "7D")

    # Actual move from entry
    actual_move_pct = (actual_price - entry) / entry if entry > 0 else 0
    # Predicted move from entry
    predicted_move_pct = (target - entry) / entry if entry > 0 else 0

    # ── F1: Tolerance-based hit ──
    error_pct = abs(actual_price - target) / target if target > 0 else 1.0
    tolerance = HIT_THRESHOLDS.get(horizon, 0.05)
    tolerance_hit = error_pct < tolerance

    # ── F2: Range hit ──
    # Build predicted band around target
    band_pct = RANGE_BAND_PCT.get(horizon, 0.05)
    if direction == "NEUTRAL":
        # For NEUTRAL: band around entry price
        range_low = entry * (1 - band_pct)
        range_high = entry * (1 + band_pct)
    else:
        # For directional: band around the path from entry to target
        range_low = min(entry, target) * (1 - band_pct)
        range_high = max(entry, target) * (1 + band_pct)
    range_hit = range_low <= actual_price <= range_high

    # ── F3: Direction hit ──
    if direction == "UP":
        direction_hit = actual_price > entry
    elif direction == "DOWN":
        direction_hit = actual_price < entry
    elif direction == "NEUTRAL":
        # NEUTRAL is correct if market didn't move much
        neutral_tol = NEUTRAL_TOLERANCE.get(horizon, 0.02)
        direction_hit = abs(actual_move_pct) < neutral_tol
    else:
        direction_hit = None

    # ── F5: Probabilistic composite score ──
    # Weights: direction_hit (most important), tolerance_hit, range_hit
    score_components = {
        "direction": 0.5 if direction_hit else 0.0,
        "tolerance": 0.3 if tolerance_hit else 0.0,
        "range": 0.2 if range_hit else 0.0,
    }
    composite_score = sum(score_components.values())

    # Composite hit: score >= 0.5 (at minimum direction must be correct)
    composite_hit = composite_score >= 0.5

    # ── F4: Multi-metric audit ──
    fractal_eval = {
        "tolerance_hit": tolerance_hit,
        "range_hit": range_hit,
        "direction_hit": direction_hit,
        "composite_hit": composite_hit,
        "composite_score": round(composite_score, 4),
        "score_breakdown": score_components,
        "error_pct": round(error_pct, 6),
        "actual_move_pct": round(actual_move_pct, 6),
        "predicted_move_pct": round(predicted_move_pct, 6),
        "range_band": {
            "low": round(range_low, 2),
            "high": round(range_high, 2),
        },
        "tolerance_threshold": tolerance,
    }

    return {
        "actualPrice": actual_price,
        "errorPct": round(error_pct, 6),
        "hit": composite_hit,
        "directionCorrect": direction_hit,
        "fractal_eval": fractal_eval,
        "status": "resolved",
        "resolvedAt": datetime.now(timezone.utc),
    }


def resolve_forecasts(scope: str):
    """
    Resolve pending forecasts for a specific scope.
    Uses multi-metric evaluation (F1-F5).
    """
    col = get_forecast_col(scope)
    now = datetime.now(timezone.utc)

    pending = list(
        col.find(
            {"status": "pending", "evaluateAt": {"$lte": now}},
            {"_id": 1, "scope": 1, "horizon": 1, "targetPrice": 1,
             "entryPrice": 1, "evaluateAt": 1, "direction": 1},
        ).limit(200)
    )

    if not pending:
        return 0

    resolved = 0
    for forecast in pending:
        actual_price = _get_historical_price(
            forecast["evaluateAt"],
            forecast.get("scope", scope),
        )

        if actual_price is None:
            continue

        eval_result = _evaluate_forecast(forecast, actual_price)

        col.update_one(
            {"_id": forecast["_id"]},
            {"$set": eval_result},
        )
        resolved += 1

    print(f"[FractalForecast] Resolved {resolved}/{len(pending)} {scope} forecasts (V2 evaluator)")
    return resolved
