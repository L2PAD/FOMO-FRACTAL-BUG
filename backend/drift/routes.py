"""
Drift Monitoring — API Routes
"""

import traceback
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/drift", tags=["drift"])


@router.get("/status")
async def drift_status(
    horizon: str = Query("7D"),
    asset: str = Query("BTC"),
):
    """Get current drift status and ML weight."""
    from drift.service import compute_drift_snapshot
    try:
        snapshot = compute_drift_snapshot(horizon, asset)
        return {"ok": True, **snapshot}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )


@router.get("/history")
async def drift_history(
    horizon: str = Query("7D"),
    asset: str = Query("BTC"),
    days: int = Query(45),
):
    """Get drift score history."""
    from drift.service import get_drift_history
    history = get_drift_history(horizon, asset, days)
    return {"ok": True, "history": history, "count": len(history)}


@router.get("/history/chart")
async def drift_history_chart(
    horizon: str = Query("7D"),
    asset: str = Query("BTC"),
    days: int = Query(45),
):
    """Lightweight drift history for charting."""
    from drift.service import get_drift_history_chart
    data = get_drift_history_chart(horizon, asset, days)
    return {"ok": True, "data": data, "count": len(data)}


@router.get("/weight")
async def ml_weight(
    horizon: str = Query("7D"),
    asset: str = Query("BTC"),
):
    """Get current ML weight with explanation."""
    from drift.service import get_current_ml_weight, compute_drift_snapshot
    try:
        snapshot = compute_drift_snapshot(horizon, asset)
        return {
            "ok": True,
            "mlWeight": snapshot["mlWeight"],
            "driftScore": snapshot["driftScore"],
            "status": snapshot["status"],
            "drivers": snapshot["drivers"],
        }
    except Exception as e:
        return {"ok": False, "mlWeight": 1.0, "error": str(e)}


@router.get("/regime-baselines")
async def regime_baselines(horizon: str = Query("7D")):
    """Get stored regime baselines."""
    import os
    from pymongo import MongoClient
    db = MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]
    docs = list(db["drift_regime_baselines"].find(
        {"horizon": horizon}, {"_id": 0},
    ))
    return {"ok": True, "baselines": {d["regime"]: d.get("baseline", {}) for d in docs}, "count": len(docs)}



# ══════════════════════════════════════════════════════════════
# BLOCK 6 — Drift Intelligence Layer
# ══════════════════════════════════════════════════════════════

@router.get("/intelligence")
async def drift_intelligence(
    horizon: int = Query(7, description="Forecast horizon in days"),
    asset: str = Query("BTC"),
    window: int = Query(14, description="Rolling window size in days"),
):
    """
    Block 6 — Full Drift Intelligence Report.

    Returns drift_score, alerts, root_causes, recommendations,
    and detailed metrics by: time, confidence, version, regime, direction.
    """
    try:
        from drift.drift_metrics_engine import compute_drift_metrics
        from drift.drift_detector import detect_drift
        from drift.drift_analysis import (
            analyze_root_causes,
            compute_drift_score as compute_intelligence_score,
            generate_alerts,
            generate_recommendations,
        )

        metrics = compute_drift_metrics(
            horizon_days=horizon, asset=asset, rolling_window_days=window,
        )
        if not metrics.get("ok"):
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": metrics.get("error", "No data")},
            )

        drift_result = detect_drift(metrics)
        root_causes = analyze_root_causes(drift_result["drift_zones"], metrics)
        drift_score = compute_intelligence_score(metrics, drift_result)
        alerts = generate_alerts(drift_result["drift_zones"], root_causes, drift_score)
        recommendations = generate_recommendations(
            drift_result["drift_zones"], root_causes, drift_score, metrics
        )

        return {
            "ok": True,
            "drift_score": drift_score["score"],
            "level": drift_score["level"],
            "score_components": drift_score["components"],
            "has_drift": drift_result["has_drift"],
            "drift_count": drift_result["drift_count"],
            "alerts": alerts,
            "top_issues": [
                {"cause": c["cause"], "zone": c["zone"], "confidence": c["confidence"]}
                for c in root_causes[:3]
            ],
            "recommendations": recommendations,
            "metrics": {
                "global": metrics["global"],
                "by_time": metrics["by_time"],
                "by_confidence": metrics["by_confidence"],
                "by_version": metrics["by_version"],
                "by_direction": metrics["by_direction"],
                "by_regime": metrics.get("by_regime", {}),
                "regime_coverage": metrics.get("regime_coverage", 0),
                "label_trend": metrics.get("label_trend", {}),
            },
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )
