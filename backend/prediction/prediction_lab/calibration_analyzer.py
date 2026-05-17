"""
Calibration Analyzer — measures predicted vs actual hit rates.

Builds calibration buckets at two levels:
  1. Global calibration (all forecasts)
  2. Family calibration (per familyKey)

Checks how well the system's fairProb estimates match reality.
"""
import logging

logger = logging.getLogger("prediction_lab.calibration")

# Default calibration bucket boundaries
BUCKETS = [
    (0.50, 0.55),
    (0.55, 0.60),
    (0.60, 0.70),
    (0.70, 0.80),
    (0.80, 0.90),
    (0.90, 1.00),
]


def recalculate_calibration(db) -> dict:
    """Recalculate calibration buckets (global + by family).

    Returns: {"global": [...buckets], "by_family": {"familyKey": [...buckets]}}
    """
    results = list(db.forecast_results.find(
        {"correctness": {"$in": ["CORRECT", "WRONG"]}},
        {"_id": 0, "fair_prob": 1, "binary_correct": 1, "family_key": 1}
    ))

    if not results:
        return {"global": [], "by_family": {}}

    # Global calibration
    global_buckets = _compute_buckets(results)

    # Family calibration
    families = {}
    for r in results:
        fk = r.get("family_key", "unknown")
        if fk not in families:
            families[fk] = []
        families[fk].append(r)

    family_buckets = {}
    for fk, fam_results in families.items():
        if len(fam_results) >= 5:  # min sample
            family_buckets[fk] = _compute_buckets(fam_results)

    # Store report
    report = {
        "global": global_buckets,
        "by_family": family_buckets,
        "total_samples": len(results),
        "families_analyzed": len(family_buckets),
    }

    db.calibration_reports.delete_many({})
    db.calibration_reports.insert_one({**report, "type": "latest"})
    logger.info(f"Calibration recalculated: {len(results)} samples, {len(family_buckets)} families")

    return report


def _compute_buckets(results: list[dict]) -> list[dict]:
    """Compute calibration buckets for a set of results."""
    buckets = []

    for lo, hi in BUCKETS:
        in_bucket = [r for r in results if lo <= abs(r.get("fair_prob", 0)) < hi]

        if not in_bucket:
            buckets.append({
                "bucket": f"{int(lo*100)}-{int(hi*100)}%",
                "min_prob": lo,
                "max_prob": hi,
                "sample_size": 0,
                "avg_predicted": 0,
                "actual_hit_rate": 0,
                "calibration_error": 0,
            })
            continue

        avg_predicted = sum(abs(r.get("fair_prob", 0)) for r in in_bucket) / len(in_bucket)
        hits = sum(1 for r in in_bucket if r.get("binary_correct"))
        hit_rate = hits / len(in_bucket)
        cal_error = abs(avg_predicted - hit_rate)

        buckets.append({
            "bucket": f"{int(lo*100)}-{int(hi*100)}%",
            "min_prob": lo,
            "max_prob": hi,
            "sample_size": len(in_bucket),
            "avg_predicted": round(avg_predicted, 4),
            "actual_hit_rate": round(hit_rate, 4),
            "calibration_error": round(cal_error, 4),
        })

    return buckets
