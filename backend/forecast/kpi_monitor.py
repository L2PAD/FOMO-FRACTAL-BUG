"""
Recovery KPI Monitor v4.1
===========================
Computes key metrics after v4.1 release to track recovery:
- neutral_ratio per horizon
- direction_accuracy per horizon
- share of mild/strong calls
- ECE (Expected Calibration Error)
"""

from pymongo import MongoClient, DESCENDING
from datetime import datetime, timezone
import os


def _get_db():
    try:
        from forecast.repo import _cfg
        c = _cfg()
        return MongoClient(c.mongo_url)[c.db_name]
    except Exception:
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
        db_name = os.environ.get("DB_NAME", "intelligence_engine")
        return MongoClient(mongo_url)[db_name]


def compute_recovery_kpi(horizon: str = "7D", window_days: int = 30) -> dict:
    """Compute KPIs for a given horizon over a time window."""
    db = _get_db()
    col = db["exchange_forecasts"]

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff = now_ms - window_days * 86_400_000

    all_docs = list(col.find(
        {"horizon": horizon, "createdAt": {"$gte": cutoff}},
        {"_id": 0, "direction": 1, "directionClass": 1, "confidence": 1,
         "evaluated": 1, "outcome": 1, "modelVersion": 1, "degraded": 1},
    ))

    total = len(all_docs)
    if total == 0:
        return {"horizon": horizon, "window": window_days, "total": 0}

    # Direction distribution
    dir_counts = {}
    for d in all_docs:
        dc = d.get("directionClass") or d.get("direction", "NEUTRAL")
        dir_counts[dc] = dir_counts.get(dc, 0) + 1

    neutral_count = dir_counts.get("NEUTRAL", 0)
    neutral_ratio = neutral_count / total

    mild_count = sum(v for k, v in dir_counts.items() if k.startswith("MILD"))
    strong_count = sum(v for k, v in dir_counts.items() if k.startswith("STRONG"))
    directional_count = total - neutral_count

    # Evaluated subset
    evaluated = [d for d in all_docs if d.get("evaluated")]
    eval_total = len(evaluated)

    # Direction accuracy
    dir_correct = 0
    target_hits = 0
    for d in evaluated:
        outcome = d.get("outcome", {})
        if isinstance(outcome, dict):
            if outcome.get("directionMatch"):
                dir_correct += 1
            if outcome.get("hit"):
                target_hits += 1

    direction_accuracy = dir_correct / eval_total if eval_total > 0 else 0
    win_rate = target_hits / eval_total if eval_total > 0 else 0

    # ECE (Expected Calibration Error)
    # Bucket by confidence and compare predicted vs actual hit rate
    ece = 0.0
    ece_bins = {}
    for d in evaluated:
        conf = d.get("confidence", 0)
        outcome = d.get("outcome", {})
        hit = 1 if (isinstance(outcome, dict) and outcome.get("hit")) else 0
        bucket = round(conf * 10) / 10  # 0.1 intervals
        if bucket not in ece_bins:
            ece_bins[bucket] = {"predicted": [], "actual": []}
        ece_bins[bucket]["predicted"].append(conf)
        ece_bins[bucket]["actual"].append(hit)

    ece_total_weight = 0
    for bucket, vals in ece_bins.items():
        n = len(vals["actual"])
        avg_pred = sum(vals["predicted"]) / n
        avg_actual = sum(vals["actual"]) / n
        ece += abs(avg_pred - avg_actual) * n
        ece_total_weight += n
    ece = ece / ece_total_weight if ece_total_weight > 0 else 0

    # Model version breakdown
    version_counts = {}
    for d in all_docs:
        v = d.get("modelVersion", "unknown")
        version_counts[v] = version_counts.get(v, 0) + 1

    # Degradation stats
    degraded_count = sum(1 for d in all_docs if d.get("degraded"))

    return {
        "horizon": horizon,
        "window": window_days,
        "total": total,
        "evaluated": eval_total,
        "neutralRatio": round(neutral_ratio, 4),
        "directionalCount": directional_count,
        "mildCount": mild_count,
        "strongCount": strong_count,
        "directionAccuracy": round(direction_accuracy, 4),
        "winRate": round(win_rate, 4),
        "ece": round(ece, 4),
        "directionDistribution": dir_counts,
        "modelVersions": version_counts,
        "degradedCount": degraded_count,
    }


def compute_all_kpis() -> dict:
    """Compute KPIs for all horizons."""
    results = {}
    for h in ["7D", "30D", "24H"]:
        results[h] = compute_recovery_kpi(h, window_days=90)
    return results


def compute_legacy_baseline() -> dict:
    """
    Compute baseline metrics from v4.0 legacy forecasts for comparison.
    Uses forecasts with modelVersion starting with 'v4.0'.
    """
    db = _get_db()
    col = db["exchange_forecasts"]

    results = {}
    for h in ["7D", "30D"]:
        docs = list(col.find(
            {"horizon": h, "evaluated": True, "outcome": {"$ne": None}},
            {"_id": 0, "direction": 1, "directionClass": 1, "confidence": 1, "outcome": 1},
        ))

        total = len(docs)
        if total == 0:
            results[h] = {"total": 0}
            continue

        neutral = sum(1 for d in docs if d.get("direction") in ("NEUTRAL", None))
        dir_correct = sum(1 for d in docs if isinstance(d.get("outcome", {}), dict) and d.get("outcome", {}).get("directionMatch"))
        hits = sum(1 for d in docs if isinstance(d.get("outcome", {}), dict) and d.get("outcome", {}).get("hit"))

        results[h] = {
            "total": total,
            "neutralRatio": round(neutral / total, 4),
            "directionAccuracy": round(dir_correct / total, 4),
            "winRate": round(hits / total, 4),
        }

    return results
