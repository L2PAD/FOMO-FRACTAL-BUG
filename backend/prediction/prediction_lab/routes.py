"""
Prediction Lab API Routes.

GET  /api/prediction-lab/overview      — Full lab dashboard
GET  /api/prediction-lab/calibration   — Calibration buckets
GET  /api/prediction-lab/families      — Family performance
GET  /api/prediction-lab/forecasts     — Forecast records
GET  /api/prediction-lab/results       — Resolved results
POST /api/prediction-lab/resolve       — Manual resolve cycle
POST /api/prediction-lab/recalculate   — Manual recalc analytics
"""
import logging
from fastapi import APIRouter

from prediction.prediction_lab.lab_orchestrator import (
    get_lab_overview,
    run_resolve_cycle,
    run_recalculate,
)

logger = logging.getLogger("prediction_lab.routes")

router = APIRouter(prefix="/api/prediction-lab", tags=["prediction-lab"])


def _get_db():
    from prediction.prediction_lab.db_helper import get_sync_db
    return get_sync_db()


@router.get("/overview")
def lab_overview():
    """Full Prediction Lab dashboard data."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    return get_lab_overview(db)


@router.get("/calibration")
def lab_calibration():
    """Calibration buckets (global + by family)."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    report = db.calibration_reports.find_one({"type": "latest"}, {"_id": 0})
    if not report:
        return {"global": [], "by_family": {}, "message": "Not calculated yet. Run /recalculate first."}
    return report


@router.get("/families")
def lab_families():
    """Family performance breakdown."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    families = list(db.family_performance.find(
        {"type": "family"},
        {"_id": 0}
    ).sort("correct_rate", -1))

    dimensions = {}
    for dim in ["market_type", "asset", "expiry_bucket", "liquidity_bucket"]:
        dims = list(db.family_performance.find(
            {"type": "dimension", "dimension": dim},
            {"_id": 0}
        ))
        if dims:
            dimensions[dim] = dims

    return {"families": families, "dimensions": dimensions}


@router.get("/forecasts")
def lab_forecasts(limit: int = 50, offset: int = 0, family: str | None = None):
    """List forecast records."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    query = {}
    if family:
        query["family_key"] = family

    total = db.forecast_records.count_documents(query)
    records = list(db.forecast_records.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit))

    return {"total": total, "records": records}


@router.get("/results")
def lab_results(limit: int = 50, offset: int = 0, correctness: str | None = None):
    """List resolved results."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    query = {}
    if correctness:
        query["correctness"] = correctness.upper()

    total = db.forecast_results.count_documents(query)
    results = list(db.forecast_results.find(
        query, {"_id": 0}
    ).sort("resolved_at", -1).skip(offset).limit(limit))

    return {"total": total, "results": results}


@router.post("/resolve")
async def lab_resolve():
    """Manually trigger resolve cycle."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    stats = await run_resolve_cycle(db)
    return {"ok": True, **stats}


@router.post("/recalculate")
def lab_recalculate():
    """Manually trigger analytics recalculation."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    stats = run_recalculate(db)
    return {"ok": True, **stats}


@router.get("/scheduler-status")
def lab_scheduler_status():
    """Get Prediction Lab scheduler status."""
    db = _get_db()
    if db is None:
        return {"error": "DB not initialized"}
    total = db.forecast_records.count_documents({})
    pending = db.forecast_records.count_documents({"resolved": False})
    stale = db.forecast_records.count_documents(
        {"resolved": False, "resolve_attempts": {"$gte": 5}}
    )
    return {
        "ok": True,
        "total_forecasts": total,
        "pending_forecasts": pending,
        "stale_forecasts": stale,
        "jobs": [
            {"name": "PriceTracker", "interval": "5min"},
            {"name": "Resolver", "interval": "10min"},
            {"name": "Recalculate", "interval": "60min"},
        ],
    }
