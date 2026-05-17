"""
Bootstrap / Replay Routes
===========================
POST /api/system/bootstrap/replay — run historical simulation for cold start.
Generates forecasts, evaluates them, computes drift, and populates
all necessary data for the prediction engine.
"""

from fastapi import APIRouter, Query
from datetime import datetime, timezone, timedelta
import traceback

router = APIRouter(prefix="/api/system/bootstrap", tags=["system-bootstrap"])


@router.post("/replay")
async def replay_bootstrap(
    start: str = Query("2024-01-01", description="Start date YYYY-MM-DD"),
    end: str = Query(None, description="End date YYYY-MM-DD (default: today)"),
    asset: str = Query("BTC"),
):
    """
    Run a historical simulation to populate forecasts, evaluations,
    drift history, and calibration data for cold start.

    This replays the daily scheduler cycle (GEN → EVAL → DRIFT) for each day
    in the date range, using historical price data.
    """
    # Freeze guard: block mutations when system is frozen
    from forecast.repo import _cfg
    if _cfg().freeze_enabled:
        return {"ok": False, "error": "SYSTEM_FROZEN", "message": "Mutations blocked. System is frozen."}

    from pymongo import MongoClient
    from forecast import Horizon, HORIZON_DAYS
    from forecast.price_provider import get_price_series
    from forecast.repo import _get_col, _cfg

    c = _cfg()
    db = MongoClient(c.mongo_url)[c.db_name]
    col = _get_col()

    if end is None:
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        return {"ok": False, "error": "Invalid date format. Use YYYY-MM-DD."}

    if start_dt >= end_dt:
        return {"ok": False, "error": "start must be before end."}

    # Get full price history
    price_start = (start_dt - timedelta(days=45)).strftime("%Y-%m-%d")
    prices = get_price_series(asset, price_start, end)
    if not prices:
        return {"ok": False, "error": "No price data available for the requested range."}

    generated = 0
    evaluated = 0
    errors = 0
    skipped = 0

    # Iterate day by day
    current = start_dt
    while current <= end_dt:
        bucket = current.strftime("%Y-%m-%d")

        if bucket not in prices:
            current += timedelta(days=1)
            skipped += 1
            continue

        entry_price = prices[bucket]

        for horizon in [Horizon.D7, Horizon.D30]:
            horizon_key = horizon.value
            horizon_days = HORIZON_DAYS[horizon]

            # Check if already exists
            existing = col.find_one(
                {"asset": asset, "horizon": horizon_key, "createdBucket": bucket, "source": "bootstrap"},
            )
            if existing:
                skipped += 1
                continue

            try:
                # Get regime baseline for this horizon
                baseline_doc = db["drift_regime_baselines"].find_one(
                    {"horizon": horizon_key},
                    {"_id": 0, "baseline": 1, "regime": 1},
                )
                baseline = baseline_doc.get("baseline", {}) if baseline_doc else {}

                mean_ret = baseline.get("mean_return", 0.0)
                median_ret = baseline.get("median_return", 0.0)
                std_ret = baseline.get("std_return", 0.05)
                p25 = baseline.get("p25_return", -0.05)
                p75 = baseline.get("p75_return", 0.05)

                # Generate forecast
                created_ms = int(current.replace(tzinfo=timezone.utc).timestamp() * 1000)
                eval_ms = created_ms + horizon_days * 86_400_000
                eval_date = (current + timedelta(days=horizon_days)).strftime("%Y-%m-%d")

                if horizon_key == "30D":
                    # Band architecture
                    shrinkage = 0.75
                    median_target = round(entry_price * (1 + median_ret * shrinkage), 2)
                    target_price = median_target
                    direction = "LONG" if median_ret > 0.25 * std_ret else ("SHORT" if median_ret < -0.25 * std_ret else "NEUTRAL")
                    confidence = round(min(0.85, max(0.10, abs(median_ret) / max(std_ret, 0.001) * 0.7)), 4)
                    forecast_type = "band"
                    band_core_low = round(entry_price * (1 + p25), 2)
                    band_core_high = round(entry_price * (1 + p75), 2)
                    iqr = p75 - p25
                    band_wide_low = round(entry_price * (1 + p25 - 0.75 * iqr), 2)
                    band_wide_high = round(entry_price * (1 + p75 + 0.75 * iqr), 2)
                else:
                    # Point target
                    shrinkage = 0.75
                    move = mean_ret * shrinkage
                    target_price = round(entry_price * (1 + move), 2)
                    median_target = None
                    direction = "LONG" if mean_ret > 0.25 * std_ret else ("SHORT" if mean_ret < -0.25 * std_ret else "NEUTRAL")
                    confidence = round(min(0.85, max(0.10, baseline.get("dir_hit_mean", 0.5) * 0.85)), 4)
                    forecast_type = "point"
                    band_core_low = None
                    band_core_high = None
                    band_wide_low = None
                    band_wide_high = None

                move_pct = round(((target_price - entry_price) / entry_price) * 100, 2)

                forecast_doc = {
                    "id": f"bootstrap-{asset}-{horizon_key}-{bucket}",
                    "asset": asset,
                    "symbol": f"{asset}USDT",
                    "horizon": horizon_key,
                    "horizonDays": horizon_days,
                    "createdAt": created_ms,
                    "createdBucket": bucket,
                    "evaluateAfter": eval_ms,
                    "entryPrice": entry_price,
                    "targetPrice": target_price,
                    "expectedMovePct": move_pct,
                    "direction": direction,
                    "confidence": confidence,
                    "confidenceRaw": confidence,
                    "modelVersion": "v4.0.0-bootstrap",
                    "featuresHash": "bootstrap",
                    "immutableHash": "bootstrap",
                    "dataWindowEnd": created_ms,
                    "source": "bootstrap",
                    "forecastType": forecast_type,
                    "evaluated": False,
                    "outcome": None,
                }

                if forecast_type == "band":
                    forecast_doc["medianTarget"] = median_target
                    forecast_doc["bandCoreLow"] = band_core_low
                    forecast_doc["bandCoreHigh"] = band_core_high
                    forecast_doc["bandWideLow"] = band_wide_low
                    forecast_doc["bandWideHigh"] = band_wide_high

                # Evaluate if we have the eval date price
                if eval_date in prices:
                    actual_price = prices[eval_date]
                    error_pct = ((actual_price - target_price) / entry_price) * 100
                    deviation_pct = ((actual_price - entry_price) / entry_price) * 100

                    actual_dir = "LONG" if actual_price > entry_price else ("SHORT" if actual_price < entry_price else "NEUTRAL")
                    dir_match = (direction == actual_dir) or (direction in ("LONG", "UP") and actual_dir in ("LONG", "UP")) or (direction in ("SHORT", "DOWN") and actual_dir in ("SHORT", "DOWN"))

                    abs_error = abs(error_pct)
                    if horizon_key == "30D":
                        # For band: check if actual is within band
                        if band_core_low and band_core_high and band_core_low <= actual_price <= band_core_high:
                            label = "TP"
                        elif abs_error < 6.0:
                            label = "WEAK"
                        else:
                            label = "FP"
                    else:
                        if abs_error < 3.0:
                            label = "TP"
                        elif abs_error < 6.0:
                            label = "WEAK"
                        else:
                            label = "FP"

                    forecast_doc["evaluated"] = True
                    forecast_doc["outcome"] = {
                        "evaluatedAt": eval_ms,
                        "realPrice": actual_price,
                        "errorPct": round(error_pct, 4),
                        "deviationPct": round(deviation_pct, 4),
                        "label": label,
                        "directionMatch": dir_match,
                        "hit": label == "TP",
                    }
                    evaluated += 1

                col.insert_one(forecast_doc)
                generated += 1

            except Exception:
                errors += 1
                if errors <= 5:
                    traceback.print_exc()

        current += timedelta(days=1)

    return {
        "ok": True,
        "asset": asset,
        "dateRange": {"start": start, "end": end},
        "generated": generated,
        "evaluated": evaluated,
        "skipped": skipped,
        "errors": errors,
    }


@router.get("/status")
async def bootstrap_status(asset: str = Query("BTC")):
    """Check current bootstrap/forecast data status."""
    from pymongo import MongoClient
    from forecast.repo import _cfg
    c = _cfg()
    db = MongoClient(c.mongo_url)[c.db_name]
    col = db[c.forecasts_collection]

    total = col.count_documents({"asset": asset})
    bootstrap_count = col.count_documents({"asset": asset, "source": "bootstrap"})
    scheduler_count = col.count_documents({"asset": asset, "source": "scheduler"})
    evaluated_count = col.count_documents({"asset": asset, "evaluated": True})
    band_count = col.count_documents({"asset": asset, "forecastType": "band"})

    # Date range
    oldest = col.find_one({"asset": asset}, sort=[("createdAt", 1)])
    newest = col.find_one({"asset": asset}, sort=[("createdAt", -1)])

    # Per-horizon breakdown
    horizons = {}
    for h in ["7D", "30D"]:
        h_total = col.count_documents({"asset": asset, "horizon": h})
        h_eval = col.count_documents({"asset": asset, "horizon": h, "evaluated": True})
        h_tp = col.count_documents({"asset": asset, "horizon": h, "outcome.label": "TP"})
        horizons[h] = {
            "total": h_total,
            "evaluated": h_eval,
            "tp": h_tp,
            "winRate": round(h_tp / h_eval, 4) if h_eval > 0 else 0,
        }

    return {
        "ok": True,
        "asset": asset,
        "total": total,
        "bootstrap": bootstrap_count,
        "scheduler": scheduler_count,
        "evaluated": evaluated_count,
        "band": band_count,
        "dateRange": {
            "oldest": oldest.get("createdBucket") if oldest else None,
            "newest": newest.get("createdBucket") if newest else None,
        },
        "horizons": horizons,
    }
