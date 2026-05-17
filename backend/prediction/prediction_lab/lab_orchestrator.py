"""
Prediction Lab Orchestrator — ties all components together.

Provides high-level methods for:
  - Recording forecasts from the pipeline
  - Resolving pending forecasts
  - Recalculating analytics
  - Serving the lab overview (decision-grade dashboard)
"""
import logging

from prediction.prediction_lab.forecast_recorder import record_forecast
from prediction.prediction_lab.forecast_resolver import resolve_pending_forecasts
from prediction.prediction_lab.calibration_analyzer import recalculate_calibration
from prediction.prediction_lab.family_analyzer import recalculate_family_performance

logger = logging.getLogger("prediction_lab.orchestrator")


def record_from_pipeline(event: dict, overlay: dict, outcome_overlays: list[dict],
                         structure_analysis: dict | None, db) -> str | None:
    """Called from event_ingestion pipeline after decide_event()."""
    return record_forecast(event, overlay, outcome_overlays, structure_analysis, db)


async def run_resolve_cycle(db, limit: int = 50) -> dict:
    """Run a resolve cycle for pending forecasts."""
    return await resolve_pending_forecasts(db, limit)


def run_recalculate(db) -> dict:
    """Recalculate all analytics (calibration + families)."""
    calibration = recalculate_calibration(db)
    families = recalculate_family_performance(db)
    return {
        "calibration_samples": calibration.get("total_samples", 0),
        "families_analyzed": len(families),
    }


def get_lab_overview(db) -> dict:
    """Get the full Prediction Lab overview for UI (decision-grade)."""
    # Forecast counts
    total = db.forecast_records.count_documents({})
    resolved = db.forecast_records.count_documents({"resolved": True})
    pending = total - resolved
    stale = db.forecast_records.count_documents(
        {"resolved": False, "resolve_attempts": {"$gte": 5}}
    )

    # Results
    results = list(db.forecast_results.find(
        {"correctness": {"$in": ["CORRECT", "WRONG"]}},
        {"_id": 0}
    ))

    n_results = len(results)
    if n_results == 0:
        return {
            "total_forecasts": total,
            "resolved_forecasts": resolved,
            "pending_forecasts": pending,
            "stale_forecasts": stale,
            "validated_results": 0,
            "accuracy": None,
            "avg_brier": None,
            "avg_realized_edge": None,
            "avg_entry_quality": None,
            "opportunity_rate": None,
            "calibration_verdict": "Insufficient data",
            "calibration": [],
            "best_families": [],
            "worst_families": [],
            "recent_mistakes": [],
            "recent_correct": [],
            "dimensions": {},
        }

    # Accuracy
    correct = sum(1 for r in results if r.get("binary_correct"))
    accuracy = round(correct / n_results, 4)

    # Avg Brier
    briers = [r["brier_score"] for r in results if r.get("brier_score") is not None]
    avg_brier = round(sum(briers) / len(briers), 4) if briers else None

    # Avg realized edge
    edges = [r["realized_edge"] for r in results if r.get("realized_edge") is not None]
    avg_realized = round(sum(edges) / len(edges), 4) if edges else None

    # Avg entry quality
    eq_vals = [r["entry_quality"] for r in results if r.get("entry_quality") is not None]
    avg_entry_quality = round(sum(eq_vals) / len(eq_vals), 4) if eq_vals else None

    # Opportunity capture rate
    opp_vals = [r["opportunity_captured"] for r in results if r.get("opportunity_captured") is not None]
    opportunity_rate = round(sum(1 for o in opp_vals if o) / len(opp_vals), 4) if opp_vals else None

    # Calibration
    cal_report = db.calibration_reports.find_one({"type": "latest"}, {"_id": 0})
    cal_buckets = cal_report.get("global", []) if cal_report else []

    # Calibration verdict
    if cal_buckets:
        non_empty = [b for b in cal_buckets if b["sample_size"] > 0]
        if non_empty:
            avg_cal_err = sum(b["calibration_error"] for b in non_empty) / len(non_empty)
            if avg_cal_err < 0.05:
                cal_verdict = "Well calibrated"
            elif avg_cal_err < 0.10:
                cal_verdict = "Slightly overconfident"
            elif avg_cal_err < 0.15:
                cal_verdict = "Overconfident"
            else:
                cal_verdict = "Poorly calibrated"
        else:
            cal_verdict = "Insufficient data"
    else:
        cal_verdict = "Not calculated yet"

    # Best / worst families
    families = list(db.family_performance.find(
        {"type": "family"},
        {"_id": 0}
    ).sort("correct_rate", -1))

    best_families = [f for f in families if f.get("verdict") == "STRONG"][:5]
    worst_families = [f for f in families if f.get("verdict") == "WEAK"][:5]

    # Dimensions
    dims = {}
    for dim_name in ["market_type", "asset", "expiry_bucket", "liquidity_bucket"]:
        dim_results = list(db.family_performance.find(
            {"type": "dimension", "dimension": dim_name},
            {"_id": 0}
        ))
        if dim_results:
            dims[dim_name] = dim_results

    # Recent mistakes (last 10)
    wrong = list(db.forecast_results.find(
        {"correctness": "WRONG"},
        {"_id": 0}
    ).sort("resolved_at", -1).limit(10))

    # Recent correct (last 10)
    right = list(db.forecast_results.find(
        {"correctness": "CORRECT"},
        {"_id": 0}
    ).sort("resolved_at", -1).limit(10))

    return {
        "total_forecasts": total,
        "resolved_forecasts": resolved,
        "pending_forecasts": pending,
        "stale_forecasts": stale,
        "validated_results": n_results,
        "accuracy": accuracy,
        "avg_brier": avg_brier,
        "avg_realized_edge": avg_realized,
        "avg_entry_quality": avg_entry_quality,
        "opportunity_rate": opportunity_rate,
        "calibration_verdict": cal_verdict,
        "calibration": cal_buckets,
        "best_families": best_families,
        "worst_families": worst_families,
        "recent_mistakes": wrong,
        "recent_correct": right,
        "dimensions": dims,
    }
