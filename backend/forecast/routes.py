"""
Forecast Routes
================
API endpoints for scheduler admin and health monitoring.
"""

from fastapi import APIRouter
from forecast.scheduler import run_daily, run_eval_job, run_gen_job
from forecast.repo import get_last_run, get_stats, get_overdue_count, ensure_indexes

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


# ── Notification helpers ──

async def _emit_forecast_events(asset: str, results: dict):
    """Emit notification events for generated forecasts. Silent on error."""
    try:
        from notifications.emit import (
            emit_exchange_forecast, emit_exchange_divergence, emit_ml_risk
        )

        generated_horizons = {}
        for h, r in results.items():
            if r.get("status") in ("generated", "regenerated"):
                move_pct = r.get("expectedMovePct", 0) or 0
                # Filter: only emit if |move| > 0.5%
                if abs(move_pct) > 0.5:
                    await emit_exchange_forecast({
                        "asset": asset,
                        "horizon": h,
                        "direction": r.get("direction", "neutral"),
                        "confidence": r.get("confidence", 0),
                        "expectedMovePct": move_pct,
                    })
                generated_horizons[h] = r

                # ML Risk: emit if risk_score > 0.6
                risk_score = r.get("ml_risk_score", 0) or 0
                if risk_score > 0.6:
                    await emit_ml_risk(asset, risk_score, {"horizon": h})

        # Divergence: 7D vs 30D direction mismatch
        d7 = generated_horizons.get("7D", {}).get("direction", "").upper()
        d30 = generated_horizons.get("30D", {}).get("direction", "").upper()
        if (d7 and d30 and d7 != "NEUTRAL" and d30 != "NEUTRAL" and d7 != d30):
            await emit_exchange_divergence(asset, {
                "7D": d7, "30D": d30,
            })
    except Exception as e:
        print(f"[NotifEngine] emit_forecast_events error (non-fatal): {e}")


@router.get("/latest/{asset}")
async def get_latest_forecast(asset: str = "BTC"):
    """Block 7.5: Get the latest forecast for a specific asset across all horizons."""
    from pymongo import MongoClient, DESCENDING
    from datetime import datetime, timezone
    from assets.asset_registry import is_supported
    import os

    asset = asset.upper()
    if not is_supported(asset):
        return {"ok": False, "error": f"Asset {asset} not supported. Use BTC, ETH, or SOL."}

    try:
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        db = MongoClient(mongo_url)[db_name]
        col = db["exchange_forecasts"]
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        forecasts = {}
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
                status = "OVERDUE"

            forecasts[h] = {
                "direction": doc.get("direction"),
                "directionClass": doc.get("directionClass"),
                "confidence": doc.get("confidence"),
                "confidenceRaw": doc.get("confidenceRaw"),
                "confidenceDirection": doc.get("confidenceDirection"),
                "confidenceTarget": doc.get("confidenceTarget"),
                "entryPrice": doc.get("entryPrice"),
                "targetPrice": doc.get("targetPrice"),
                "expectedMovePct": doc.get("expectedMovePct"),
                "regime": (doc.get("audit") or {}).get("regime", "UNKNOWN"),
                "status": status,
                "createdBucket": doc.get("createdBucket"),
                "modelVersion": doc.get("modelVersion"),
                "scenarios": doc.get("scenarios"),
                "calibration": (doc.get("audit") or {}).get("calibration"),
            }

        return {
            "ok": True,
            "asset": asset,
            "horizons": forecasts,
            "count": len(forecasts),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/admin/run")
async def trigger_run(mode: str = "daily"):
    """Manually trigger a forecast run. Idempotent."""
    if mode == "eval":
        evaluated, errors = run_eval_job()
        return {"ok": True, "mode": "eval", "evaluated": evaluated, "errors": errors}
    elif mode == "gen":
        generated, errors = run_gen_job()
        return {"ok": True, "mode": "gen", "generated": generated, "errors": errors}
    else:
        result = run_daily()
        return {"ok": True, "mode": "daily", **result}


@router.post("/admin/generate/{asset}")
async def trigger_asset_gen(asset: str = "BTC"):
    """Block 7.5: Generate forecast for a single asset (all horizons). Idempotent."""
    from assets.asset_registry import is_supported
    from forecast import Horizon
    from forecast.generator_v41 import generate_forecast
    from forecast.repo import has_forecast_for_bucket, insert_forecast
    from datetime import datetime, timezone

    asset = asset.upper()
    if not is_supported(asset):
        return {"ok": False, "error": f"Asset {asset} not supported"}

    # Block 11: Sub-daily bucket
    from forecast.acceleration import get_current_bucket
    bucket = get_current_bucket()
    run_id = f"manual_{asset}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
    results = {}

    for horizon in Horizon:
        try:
            if has_forecast_for_bucket(asset, horizon.value, bucket):
                results[horizon.value] = {"status": "exists", "msg": f"Already generated for {bucket}"}
                continue

            record = generate_forecast(asset, horizon, run_id=run_id)
            if record:
                # ML Risk Overlay + Preflight Gate post-processing
                try:
                    from ml_overlay.post_process import apply_ml_risk_layers
                    record_d = record.model_dump()
                    record_d = apply_ml_risk_layers(record_d)
                    record.confidence = record_d["confidence"]
                    record.audit = record_d.get("audit", record.audit)
                except Exception:
                    pass  # Never break forecast on ML layer errors

                inserted = insert_forecast(record)
                ml_audit = (record.audit or {}).get("ml", {})
                results[horizon.value] = {
                    "status": "generated" if inserted else "duplicate",
                    "direction": record.direction,
                    "confidence": record.confidence,
                    "targetPrice": record.targetPrice,
                    "expectedMovePct": getattr(record, "expectedMovePct", 0),
                    "ml_risk_score": ml_audit.get("risk_score", 0),
                }
            else:
                results[horizon.value] = {"status": "failed", "msg": "No price data or features"}
        except Exception as e:
            results[horizon.value] = {"status": "error", "msg": str(e)}

    # Emit notification events (non-blocking, never fails the response)
    await _emit_forecast_events(asset, results)

    return {"ok": True, "asset": asset, "runId": run_id, "results": results}


@router.post("/admin/regenerate/{asset}")
async def force_regenerate(asset: str = "BTC"):
    """Block 8.1: Force regenerate forecast with new calibration (replaces today's)."""
    from assets.asset_registry import is_supported
    from forecast import Horizon
    from forecast.generator_v41 import generate_forecast
    from forecast.repo import insert_forecast
    from datetime import datetime, timezone
    from pymongo import MongoClient
    import os

    asset = asset.upper()
    if not is_supported(asset):
        return {"ok": False, "error": f"Asset {asset} not supported"}

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    db = MongoClient(mongo_url)[db_name]
    col = db["exchange_forecasts"]

    # Block 11: Delete current slot's forecast (not all day's)
    from forecast.acceleration import get_current_bucket
    bucket = get_current_bucket()
    run_id = f"recal_{asset}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
    results = {}

    for horizon in Horizon:
        try:
            col.delete_many({
                "asset": asset,
                "horizon": horizon.value,
                "createdBucket": bucket,
            })

            record = generate_forecast(asset, horizon, run_id=run_id)
            if record:
                # ML Risk Overlay + Preflight Gate post-processing
                try:
                    from ml_overlay.post_process import apply_ml_risk_layers
                    record_d = record.model_dump()
                    record_d = apply_ml_risk_layers(record_d)
                    record.confidence = record_d["confidence"]
                    record.audit = record_d.get("audit", record.audit)
                except Exception:
                    pass

                inserted = insert_forecast(record)
                ml_audit = (record.audit or {}).get("ml", {})
                results[horizon.value] = {
                    "status": "regenerated" if inserted else "duplicate",
                    "confidence": record.confidence,
                    "confidenceRaw": record.confidenceRaw,
                    "calibrationDelta": round(record.confidence - record.confidenceRaw, 4),
                    "direction": record.direction,
                    "directionClass": record.directionClass,
                    "targetPrice": record.targetPrice,
                    "expectedMovePct": getattr(record, "expectedMovePct", 0),
                    "ml_risk_score": ml_audit.get("risk_score", 0),
                }
            else:
                results[horizon.value] = {"status": "failed", "msg": "No price data"}
        except Exception as e:
            results[horizon.value] = {"status": "error", "msg": str(e)}

    # Emit notification events
    await _emit_forecast_events(asset, results)

    return {"ok": True, "asset": asset, "runId": run_id, "calibration": "v8.1", "results": results}


@router.get("/admin/calibration")
async def get_calibration_status():
    """Block 8.1: Get calibration configuration and live check."""
    from exchange.calibration.confidence_calibrator import (
        calibrate_confidence,
        calibrate_confidence_target,
        get_calibration_info,
        CALIBRATION_ANCHORS_BY_HORIZON,
    )

    horizons = {}
    for h in ["24H", "7D", "30D"]:
        info = get_calibration_info(h)
        # Test mapping at sample points
        samples = [0.05, 0.10, 0.20, 0.30, 0.45, 0.60, 0.80]
        mapping = []
        for raw in samples:
            mapping.append({
                "raw": raw,
                "calibratedDirection": calibrate_confidence(raw, h),
                "calibratedTarget": calibrate_confidence_target(raw, h),
            })
        info["sampleMapping"] = mapping
        horizons[h] = info

    return {"ok": True, "block": "8.1", "horizons": horizons}


@router.get("/calibration-metrics")
async def get_calibration_metrics(asset: str | None = None, horizon: str | None = None):
    """Block 8.2: Calibration truth metrics — Brier, ECE, Sharpness, Buckets."""
    from exchange.calibration.calibration_metrics import compute_calibration_metrics

    asset_val = asset.upper() if asset else None
    horizon_val = horizon.upper() if horizon else None

    metrics = compute_calibration_metrics(asset_val, horizon_val)
    return {"ok": True, "block": "8.2", **metrics}


@router.get("/calibration-metrics/compare")
async def get_calibration_comparison(asset: str | None = None, horizon: str | None = None):
    """Block 8.2: Before/after calibration comparison (raw vs calibrated)."""
    from exchange.calibration.calibration_metrics import compute_before_after

    asset_val = asset.upper() if asset else None
    horizon_val = horizon.upper() if horizon else None

    comparison = compute_before_after(asset_val, horizon_val)
    return {"ok": True, "block": "8.2", **comparison}


@router.get("/calibration-metrics/matrix")
async def get_calibration_matrix():
    """Block 8.2: Full calibration matrix — all asset/horizon combinations."""
    from exchange.calibration.calibration_metrics import compute_calibration_metrics

    matrix = {}
    for asset in ["BTC", "ETH", "SOL"]:
        matrix[asset] = {}
        for horizon in ["24H", "7D", "30D"]:
            metrics = compute_calibration_metrics(asset, horizon)
            matrix[asset][horizon] = {
                "sampleSize": metrics.get("sampleSize", 0),
                "brierScore": metrics.get("brierScore"),
                "ece": metrics.get("ece"),
                "sharpness": metrics.get("sharpness"),
                "accuracy": metrics.get("accuracy"),
                "verdict": metrics.get("verdict"),
                "issues": metrics.get("issues", []),
            }

    # Also compute aggregate per asset
    aggregates = {}
    for asset in ["BTC", "ETH", "SOL"]:
        agg = compute_calibration_metrics(asset, None)
        aggregates[asset] = {
            "sampleSize": agg.get("sampleSize", 0),
            "brierScore": agg.get("brierScore"),
            "ece": agg.get("ece"),
            "sharpness": agg.get("sharpness"),
            "verdict": agg.get("verdict"),
        }

    return {"ok": True, "block": "8.2", "matrix": matrix, "aggregates": aggregates}



@router.get("/scenario/calibration-metrics")
async def get_scenario_metrics(asset: str | None = None, horizon: str | None = None):
    """Block 8.3: Scenario probability calibration metrics."""
    from exchange.calibration.scenario_calibrator import compute_scenario_metrics

    asset_val = asset.upper() if asset else None
    horizon_val = horizon.upper() if horizon else None

    metrics = compute_scenario_metrics(asset_val, horizon_val)
    return {"ok": True, "block": "8.3", **metrics}


@router.get("/scenario/reliability")
async def get_scenario_reliability(asset: str | None = None, horizon: str | None = None):
    """Block 8.3: Raw scenario reliability analysis."""
    from exchange.calibration.scenario_calibrator import (
        build_scenario_dataset, compute_scenario_reliability,
    )

    asset_val = asset.upper() if asset else None
    horizon_val = horizon.upper() if horizon else None

    dataset = build_scenario_dataset(asset_val, horizon_val)
    reliability = compute_scenario_reliability(dataset)
    return {"ok": True, "block": "8.3", **reliability}



@router.get("/admin/status")
async def get_status():
    """Get scheduler health: last run, overdue count, stats by horizon."""
    last_run = get_last_run()
    stats = get_stats()
    overdue = get_overdue_count()

    return {
        "ok": True,
        "overdue": overdue,
        "lastRun": last_run,
        "stats": stats,
    }


@router.get("/health")
async def get_health():
    """Compact health for UI display."""
    stats = get_stats()
    overdue = get_overdue_count()
    last_run = get_last_run()

    total_evaluated = sum(s["evaluated"] for s in stats.values())
    total_pending = sum(s["pending"] for s in stats.values())

    # Emit system health event if overdue count is concerning
    if overdue >= 3:
        try:
            from notifications.emit import emit_system_health
            await emit_system_health(
                f"Forecast overdue count: {overdue}",
                "high" if overdue >= 6 else "medium",
            )
        except Exception:
            pass

    return {
        "ok": True,
        "totalEvaluated": total_evaluated,
        "totalPending": total_pending,
        "overdue": overdue,
        "lastRunTs": last_run["ts"] if last_run else None,
        "horizons": stats,
    }


@router.get("/kpi")
async def get_kpi():
    """v4.1 Recovery KPI monitor — neutral ratio, direction accuracy, ECE."""
    from forecast.kpi_monitor import compute_all_kpis, compute_legacy_baseline
    return {
        "ok": True,
        "current": compute_all_kpis(),
        "legacy": compute_legacy_baseline(),
    }


@router.get("/shadow/kpi")
async def get_shadow_kpi(horizon: str = None):
    """Structure A/B shadow comparison — accuracy lift, distribution shift, case analysis."""
    from forecast.structure.shadow import compute_shadow_kpi
    return {
        "ok": True,
        **compute_shadow_kpi(horizon=horizon),
    }


@router.get("/shadow/cases")
async def get_shadow_cases(case_type: str = None, horizon: str = None, limit: int = 20):
    """Individual shadow comparison cases for manual review."""
    from forecast.structure.shadow import get_shadow_cases as _get_cases
    cases = _get_cases(case_type=case_type, horizon=horizon, limit=limit)
    return {
        "ok": True,
        "count": len(cases),
        "cases": cases,
    }


# ═══════════════════════════════════════════════════════
# Historical Shadow Validation (Backfill)
# ═══════════════════════════════════════════════════════

@router.post("/backfill/run")
async def trigger_backfill(
    asset: str = "BTC",
    horizon: str = "7D",
    start_date: str = None,
    end_date: str = None,
    target_version: str = "v4.2.0",
):
    """Run historical shadow validation (backfill). May take 30-60 seconds."""
    from forecast.backfill.backfill_job import run_backfill
    result = run_backfill(
        asset=asset,
        horizon=horizon,
        start_date=start_date,
        end_date=end_date,
        target_version=target_version,
    )
    return result


@router.get("/backfill/latest")
async def get_latest_backfill(asset: str = "BTC", horizon: str = "7D"):
    """Get most recent backfill results (KPIs + verdict)."""
    from forecast.backfill.backfill_job import get_latest_backfill as _get_latest
    result = _get_latest(asset=asset, horizon=horizon)
    if not result:
        return {"ok": False, "error": "No backfill results found"}
    return {"ok": True, **result}


@router.get("/backfill/results/{run_id}")
async def get_backfill_results(run_id: str):
    """Get full results for a specific backfill run."""
    from forecast.backfill.backfill_job import get_backfill_results as _get_results
    result = _get_results(run_id)
    if not result:
        return {"ok": False, "error": "Run not found"}
    return {"ok": True, **result}


@router.get("/backfill/cases/{run_id}")
async def get_backfill_cases(
    run_id: str,
    case_type: str = None,
    pattern: str = None,
    limit: int = 50,
):
    """Get individual cases from a backfill run with optional filters."""
    from forecast.backfill.backfill_job import get_backfill_cases as _get_cases
    cases = _get_cases(run_id=run_id, case_type=case_type, pattern=pattern, limit=limit)
    return {
        "ok": True,
        "count": len(cases),
        "cases": cases,
    }



@router.get("/admin/acceleration")
async def get_acceleration_status():
    """Block 11: Data acceleration monitoring — rows/day, quality, duplicates."""
    from pymongo import MongoClient, DESCENDING
    from datetime import datetime, timezone, timedelta
    import os
    from forecast.acceleration import get_current_bucket, get_current_slot

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    db = MongoClient(mongo_url)[db_name]
    col = db["exchange_forecasts"]

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    # Count today's forecasts (new sub-daily format)
    today_new = col.count_documents({"createdBucket": {"$regex": f"^{today}_"}})
    today_old = col.count_documents({"createdBucket": today})
    today_total = today_new + today_old

    # Count last 7 days
    week_docs = list(col.find(
        {"createdAt": {"$gte": int((now - timedelta(days=7)).timestamp() * 1000)}},
        {"_id": 0, "asset": 1, "horizon": 1, "createdBucket": 1, "audit": 1},
    ))

    # Quality analysis
    quality_scores = []
    for doc in week_docs:
        accel = (doc.get("audit") or {}).get("acceleration", {})
        qs = accel.get("qualityScore")
        if qs is not None:
            quality_scores.append(qs)

    avg_quality = round(sum(quality_scores) / len(quality_scores), 4) if quality_scores else None

    # Per-asset counts
    asset_counts = {}
    for doc in week_docs:
        a = doc.get("asset", "BTC")
        asset_counts[a] = asset_counts.get(a, 0) + 1

    return {
        "ok": True,
        "block": "11",
        "currentBucket": get_current_bucket(),
        "currentSlot": get_current_slot(),
        "today": {
            "totalForecasts": today_total,
            "subDaily": today_new,
            "daily": today_old,
        },
        "last7Days": {
            "totalForecasts": len(week_docs),
            "avgPerDay": round(len(week_docs) / 7, 1),
            "perAsset": asset_counts,
        },
        "quality": {
            "avgQualityScore": avg_quality,
            "qualitySamples": len(quality_scores),
        },
        "target": {
            "forecastsPerDayPerAsset": 4,
            "expectedDailyTotal": 36,
        },
    }



# ══════════════════════════════════════════════════════════
# Block 10.1 — Prediction Output API
# ══════════════════════════════════════════════════════════

@router.get("/prediction/{asset}")
async def get_prediction(asset: str = "BTC"):
    """
    Block 10.1: Unified prediction output — single truth, clean format.

    Sources data from existing forecasts. No new computation.
    Designed for user display, Brain orchestration, and research layer.
    """
    from assets.asset_registry import is_supported
    from exchange.output.prediction_formatter import build_prediction_output

    asset = asset.upper()
    if not is_supported(asset):
        return {"ok": False, "error": f"Asset {asset} not supported. Use BTC, ETH, or SOL."}

    try:
        result = build_prediction_output(asset)
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}



@router.get("/execution/{asset}")
async def get_execution(asset: str = "BTC"):
    """
    Block 10.2: Execution adapter — terminal-friendly interpretation of prediction truth.

    Derived only from prediction output. No new market logic.
    """
    from assets.asset_registry import is_supported
    from exchange.output.execution_adapter import build_execution_adapter

    asset = asset.upper()
    if not is_supported(asset):
        return {"ok": False, "error": f"Asset {asset} not supported. Use BTC, ETH, or SOL."}

    try:
        result = build_execution_adapter(asset)
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}



# ══════════════════════════════════════════════════════════
# Exchange Health Dashboard — Stabilization Monitoring
# ══════════════════════════════════════════════════════════

@router.get("/admin/exchange/health")
async def exchange_health(
    asset: str = None,
    days: int = 14,
):
    """
    Mini Monitoring Dashboard: 3 metrics, 1 status.

    - Base Dominance Rate (30D)
    - Scenario Truthfulness
    - Catastrophic Rate
    - Overall Status: STABLE / WARNING / UNSTABLE
    """
    from exchange.monitoring.health_metrics import get_health_metrics

    try:
        result = get_health_metrics(asset=asset, days=days)

        # Emit system event if exchange health is degraded
        status = result.get("status", "STABLE")
        if status in ("WARNING", "UNSTABLE"):
            try:
                from notifications.emit import emit_system_health, emit_drift_warning
                severity = "critical" if status == "UNSTABLE" else "medium"
                await emit_system_health(
                    f"Exchange health: {status}. {result.get('issues', [])}",
                    severity,
                )
                # If drift score is provided, emit drift warning
                drift_val = result.get("driftScore") or result.get("compositeScore", 0)
                if drift_val and float(drift_val) > 0.5:
                    await emit_drift_warning(float(drift_val), {"status": status})
            except Exception:
                pass

        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}



# ══════════════════════════════════════════════════════════
# Exchange Frontend Data Endpoints
# ══════════════════════════════════════════════════════════

@router.get("/exchange/chart-data")
async def exchange_chart_data(asset: str = "BTC", horizon: str = "7D"):
    """
    Chart data for Exchange tab: price history + V2 forecast projections.
    Returns daily price series + current forecast with V2 fields.
    """
    from assets.asset_registry import is_supported
    from forecast.price_provider import get_current_price
    from pymongo import MongoClient, DESCENDING
    from datetime import datetime, timezone, timedelta
    import os
    import yfinance as yf

    asset = asset.upper()
    horizon = horizon.upper()
    # Map '1D' to '24H' for DB compatibility
    if horizon == '1D':
        horizon = '24H'
    if not is_supported(asset):
        return {"ok": False, "error": f"Asset {asset} not supported"}

    try:
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        db = MongoClient(mongo_url)[db_name]
        col = db["exchange_forecasts"]

        # 1. Price history from yfinance (90 days, daily)
        yf_ticker = "BTC-USD" if asset in ("BTC", "BTCUSDT") else f"{asset}-USD"
        df = yf.download(yf_ticker, period="90d", interval="1d", progress=False)
        price_series = []
        if not df.empty:
            for idx, row in df.iterrows():
                ts = int(idx.timestamp())
                price_series.append({
                    "time": ts,
                    "open": round(float(row["Open"].iloc[0]), 2),
                    "high": round(float(row["High"].iloc[0]), 2),
                    "low": round(float(row["Low"].iloc[0]), 2),
                    "close": round(float(row["Close"].iloc[0]), 2),
                })

        # 2. Current price
        current_price = get_current_price(asset) or 0
        now_ts = int(datetime.now(timezone.utc).timestamp())

        # 3. Latest forecast for this horizon
        doc = col.find_one(
            {"asset": asset, "horizon": horizon},
            {"_id": 0},
            sort=[("createdAt", DESCENDING)],
        )

        forecast_data = None
        if doc:
            audit = doc.get("audit") or {}
            scenarios_raw = doc.get("scenarios")
            scenarios = None
            if isinstance(scenarios_raw, dict) and "scenarios" in scenarios_raw:
                scenarios = scenarios_raw

            forecast_data = {
                "direction": doc.get("direction", "NEUTRAL"),
                "directionClass": doc.get("directionClass", "NEUTRAL"),
                "confidence": doc.get("confidence", 0),
                "confidenceRaw": doc.get("confidenceRaw", 0),
                "confidenceDirection": doc.get("confidenceDirection", 0),
                "entryPrice": doc.get("entryPrice", 0),
                "targetPrice": doc.get("targetPrice", 0),
                "expectedMovePct": doc.get("expectedMovePct", 0),
                "regime": audit.get("regime", "UNKNOWN"),
                "modelVersion": doc.get("modelVersion", "unknown"),
                "createdBucket": doc.get("createdBucket", ""),
                "createdAt": doc.get("createdAt", 0),
                "evaluateAfter": doc.get("evaluateAfter", 0),
                "evaluated": doc.get("evaluated", False),
                "scenarios": scenarios,
            }

        # 4. All 3 horizons summary (for multi-horizon display)
        horizons_summary = {}
        for h in ["24H", "7D", "30D"]:
            hdoc = col.find_one(
                {"asset": asset, "horizon": h},
                {"_id": 0},
                sort=[("createdAt", DESCENDING)],
            )
            if hdoc:
                h_audit = hdoc.get("audit") or {}
                h_scenarios = hdoc.get("scenarios")
                horizons_summary[h] = {
                    "direction": hdoc.get("direction", "NEUTRAL"),
                    "confidence": hdoc.get("confidence", 0),
                    "confidenceRaw": hdoc.get("confidenceRaw", 0),
                    "entryPrice": hdoc.get("entryPrice", 0),
                    "targetPrice": hdoc.get("targetPrice", 0),
                    "expectedMovePct": hdoc.get("expectedMovePct", 0),
                    "regime": h_audit.get("regime", "UNKNOWN"),
                    "evaluated": hdoc.get("evaluated", False),
                    "scenarios": h_scenarios if isinstance(h_scenarios, dict) else None,
                }

        # 5. Forecast projection points (future dates with target prices)
        horizon_days = {"24H": 1, "7D": 7, "30D": 30}.get(horizon, 7)
        projection_points = []
        if forecast_data:
            entry = forecast_data["entryPrice"]
            target = forecast_data["targetPrice"]
            eval_ts = forecast_data.get("evaluateAfter", 0)
            if eval_ts:
                eval_sec = int(eval_ts / 1000)
            else:
                eval_sec = now_ts + horizon_days * 86400

            # Create interpolated projection from now to target
            steps = min(horizon_days, 10)
            for i in range(1, steps + 1):
                frac = i / steps
                proj_ts = now_ts + int((eval_sec - now_ts) * frac)
                proj_price = entry + (target - entry) * frac
                projection_points.append({
                    "time": proj_ts,
                    "value": round(proj_price, 2),
                })

        return {
            "ok": True,
            "asset": asset,
            "horizon": horizon,
            "nowTs": now_ts,
            "currentPrice": current_price,
            "priceSeries": price_series,
            "forecast": forecast_data,
            "horizonsSummary": horizons_summary,
            "projectionPoints": projection_points,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


@router.get("/exchange/history")
async def exchange_history(asset: str = "BTC", horizon: str = "7D", limit: int = 30):
    """
    Historical forecast list for Exchange performance table.
    Returns recent forecasts from exchange_forecasts collection with V2 fields.
    """
    from assets.asset_registry import is_supported
    from pymongo import MongoClient, DESCENDING
    from datetime import datetime, timezone
    import os

    asset = asset.upper()
    horizon = horizon.upper()
    if not is_supported(asset):
        return {"ok": False, "error": f"Asset {asset} not supported"}

    try:
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        db = MongoClient(mongo_url)[db_name]
        col = db["exchange_forecasts"]
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        docs = list(col.find(
            {"asset": asset, "horizon": horizon},
            {"_id": 0},
            sort=[("createdAt", DESCENDING)],
        ).limit(limit))

        rows = []
        stats = {"total": 0, "evaluated": 0, "pending": 0, "overdue": 0, "hits": 0}

        for doc in docs:
            stats["total"] += 1
            audit = doc.get("audit") or {}
            evaluated = doc.get("evaluated", False)
            eval_after = doc.get("evaluateAfter", 0)

            if evaluated:
                status = "EVALUATED"
                stats["evaluated"] += 1
                # Check if direction was correct
                actual = doc.get("actualPrice")
                if actual and doc.get("entryPrice"):
                    predicted_up = doc.get("targetPrice", 0) > doc.get("entryPrice", 0)
                    actual_up = actual > doc.get("entryPrice", 0)
                    if predicted_up == actual_up:
                        stats["hits"] += 1
            elif eval_after and eval_after < now_ms:
                status = "OVERDUE"
                stats["overdue"] += 1
            else:
                status = "PENDING"
                stats["pending"] += 1

            scenarios_raw = doc.get("scenarios")
            scenarios = None
            if isinstance(scenarios_raw, dict) and "scenarios" in scenarios_raw:
                scenarios = {
                    "dominant": scenarios_raw.get("dominant"),
                    "confidence_tag": scenarios_raw.get("confidence_tag"),
                    "engine_version": scenarios_raw.get("engine_version"),
                    "scenarios": scenarios_raw.get("scenarios", []),
                }

            rows.append({
                "direction": doc.get("direction", "NEUTRAL"),
                "directionClass": doc.get("directionClass", "NEUTRAL"),
                "confidence": doc.get("confidence", 0),
                "confidenceRaw": doc.get("confidenceRaw", 0),
                "entryPrice": doc.get("entryPrice", 0),
                "targetPrice": doc.get("targetPrice", 0),
                "expectedMovePct": doc.get("expectedMovePct", 0),
                "regime": audit.get("regime", "UNKNOWN"),
                "modelVersion": doc.get("modelVersion", "unknown"),
                "createdBucket": doc.get("createdBucket", ""),
                "createdAt": doc.get("createdAt", 0),
                "evaluateAfter": doc.get("evaluateAfter", 0),
                "evaluated": evaluated,
                "status": status,
                "actualPrice": doc.get("actualPrice"),
                "scenarios": scenarios,
            })

        win_rate = stats["hits"] / stats["evaluated"] if stats["evaluated"] > 0 else 0

        return {
            "ok": True,
            "asset": asset,
            "horizon": horizon,
            "rows": rows,
            "stats": {
                **stats,
                "winRate": round(win_rate, 4),
            },
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}
