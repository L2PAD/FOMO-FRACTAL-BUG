"""
Outcome Resolver
==================
Block 4 — Task 4.2

Resolves telemetry events with actual market outcomes.
Runs periodically to fill in realized_return, direction_correct,
scenario_hit, and pnl for past forecasts.

Usage:
    from intelligence.telemetry.outcome_resolver import resolve_outcomes
    stats = resolve_outcomes()
"""

import os
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient

from forecast.price_provider import get_price_series


TELEMETRY_COL = "intelligence_telemetry"

HORIZON_DAYS = {"7D": 7, "30D": 30, "24H": 1, "1D": 1}


def _get_db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    return MongoClient(mongo_url)[db_name]


def resolve_outcomes(asset: str = "BTC") -> dict:
    """
    Resolve all unresolved telemetry events that have matured.

    For each event:
      1. Check if enough time has passed (horizon days)
      2. Get actual price at outcome date
      3. Compute realized_return, direction_correct, scenario_hit, pnl
      4. Update the event in DB
    """
    db = _get_db()
    now = datetime.now(timezone.utc)

    # Get unresolved events
    unresolved = list(db[TELEMETRY_COL].find(
        {"outcome_resolved": False, "asset": asset},
        {"_id": 0, "event_id": 1, "timestamp": 1, "horizon": 1,
         "entry_price": 1, "direction": 1, "size_factor": 1,
         "scenario_ranges": 1, "dominant_scenario": 1, "scenario_probs": 1},
    ))

    if not unresolved:
        return {"resolved": 0, "pending": 0, "errors": 0}

    # Get price data
    prices = get_price_series(asset, "2024-01-01", "2027-01-01")

    resolved = 0
    pending = 0
    errors = 0

    for event in unresolved:
        try:
            horizon_str = event.get("horizon", "7D")
            horizon_days = HORIZON_DAYS.get(horizon_str, 7)

            event_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
            outcome_time = event_time + timedelta(days=horizon_days)

            # Check if outcome date has been reached
            if outcome_time > now:
                pending += 1
                continue

            # Find outcome price
            outcome_date = outcome_time.strftime("%Y-%m-%d")
            outcome_price = _find_closest_price(prices, outcome_date)

            if outcome_price is None or event.get("entry_price") is None:
                pending += 1
                continue

            entry_price = event["entry_price"]
            realized_return = ((outcome_price - entry_price) / entry_price) * 100
            real_direction = "UP" if realized_return > 0 else "DOWN"

            # Direction correct
            predicted_dir = event.get("direction", "NEUTRAL")
            direction_correct = _check_direction(predicted_dir, real_direction)

            # Scenario hit
            scenario_hit = False
            scenario_ranges = event.get("scenario_ranges")
            if scenario_ranges:
                for stype, srange in scenario_ranges.items():
                    if len(srange) == 2 and srange[0] <= realized_return <= srange[1]:
                        scenario_hit = True
                        break

            # PnL
            size_factor = event.get("size_factor", 1.0) or 1.0
            if predicted_dir in ("STRONG_BULL", "MILD_BULL"):
                pnl = realized_return * size_factor
            elif predicted_dir in ("STRONG_BEAR", "MILD_BEAR"):
                pnl = -realized_return * size_factor
            else:
                pnl = 0.0

            # Update event
            db[TELEMETRY_COL].update_one(
                {"event_id": event["event_id"]},
                {"$set": {
                    "realized_return": round(realized_return, 4),
                    "direction_correct": direction_correct,
                    "scenario_hit": scenario_hit,
                    "pnl": round(pnl, 4),
                    "outcome_resolved": True,
                    "outcome_date": outcome_date,
                    "outcome_price": round(outcome_price, 2),
                }},
            )
            resolved += 1

        except Exception:
            errors += 1

    return {"resolved": resolved, "pending": pending, "errors": errors}


def _find_closest_price(prices: dict, target_date: str) -> float | None:
    """Find the closest available price to target date (±3 days)."""
    for offset in range(0, 4):
        for delta in [offset, -offset]:
            check = (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")
            if check in prices:
                return prices[check]
    return None


def _check_direction(predicted: str, actual: str) -> bool:
    """Check if predicted direction matches actual."""
    if actual == "UP":
        return predicted in ("STRONG_BULL", "MILD_BULL")
    elif actual == "DOWN":
        return predicted in ("STRONG_BEAR", "MILD_BEAR")
    return predicted == "NEUTRAL"
