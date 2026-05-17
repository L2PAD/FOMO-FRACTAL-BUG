"""
Market Family Analyzer — performance breakdown by market family.

Analyzes prediction quality across dimensions:
  - Market type (price, fdv, launch, etf, etc.)
  - Asset (BTC, ETH, SOL, ALT)
  - Expiry bucket (lt_6h, lt_24h, lt_7d, gt_7d)
  - Liquidity bucket (low, mid, high)

Determines which families the model is strong/weak in.
"""
import logging

logger = logging.getLogger("prediction_lab.family")

# Minimum sample size for reliable analysis
MIN_SAMPLE = 5


def recalculate_family_performance(db) -> list[dict]:
    """Recalculate performance metrics per market family.

    Returns list of family performance records.
    """
    results = list(db.forecast_results.find(
        {"correctness": {"$in": ["CORRECT", "WRONG"]}},
        {"_id": 0}
    ))

    if not results:
        return []

    # Group by family_key
    families = {}
    for r in results:
        fk = r.get("family_key", "unknown")
        if fk not in families:
            families[fk] = []
        families[fk].append(r)

    performances = []

    for fk, fam_results in families.items():
        if len(fam_results) < MIN_SAMPLE:
            continue

        perf = _compute_family_metrics(fk, fam_results)
        performances.append(perf)

    # Also compute dimension breakdowns
    dimensions = _compute_dimension_breakdowns(results)

    # Store
    db.family_performance.delete_many({})
    if performances:
        db.family_performance.insert_many([{**p, "type": "family"} for p in performances])
    for dim_name, dim_results in dimensions.items():
        for dr in dim_results:
            db.family_performance.insert_one({**dr, "type": "dimension", "dimension": dim_name})

    logger.info(f"Family performance: {len(performances)} families, {len(dimensions)} dimensions")
    return performances


def _compute_family_metrics(family_key: str, results: list[dict]) -> dict:
    """Compute metrics for a single family."""
    n = len(results)
    correct = sum(1 for r in results if r.get("binary_correct"))
    correct_rate = correct / n if n > 0 else 0

    brier_scores = [r["brier_score"] for r in results if r.get("brier_score") is not None]
    avg_brier = sum(brier_scores) / len(brier_scores) if brier_scores else None

    edges = [r["edge"] for r in results if r.get("edge") is not None]
    avg_edge = sum(edges) / len(edges) if edges else 0

    realized = [r["realized_edge"] for r in results if r.get("realized_edge") is not None]
    avg_realized = sum(realized) / len(realized) if realized else 0

    conf_map = {"high": 0.8, "medium": 0.55, "low": 0.3}
    confs = [conf_map.get(r.get("confidence", "low"), 0.3) for r in results]
    avg_conf = sum(confs) / len(confs) if confs else 0

    conf_errors = [r["confidence_error"] for r in results if r.get("confidence_error") is not None]
    avg_cal_error = sum(conf_errors) / len(conf_errors) if conf_errors else 0

    # Parse family key for metadata
    parts = family_key.split(":")
    market_type = parts[0] if len(parts) > 0 else ""
    asset = parts[1] if len(parts) > 1 else ""

    # Strength determination
    strong = (n >= 20 and correct_rate >= 0.58 and avg_cal_error <= 0.15)
    weak = (n >= 10 and correct_rate < 0.45)

    if strong:
        verdict = "STRONG"
    elif weak:
        verdict = "WEAK"
    else:
        verdict = "MODERATE"

    return {
        "family_key": family_key,
        "market_type": market_type,
        "asset": asset,
        "sample_size": n,
        "correct_rate": round(correct_rate, 4),
        "avg_brier": round(avg_brier, 4) if avg_brier is not None else None,
        "avg_edge": round(avg_edge, 4),
        "avg_realized_edge": round(avg_realized, 4),
        "avg_confidence": round(avg_conf, 4),
        "avg_calibration_error": round(avg_cal_error, 4),
        "strong": strong,
        "verdict": verdict,
    }


def _compute_dimension_breakdowns(results: list[dict]) -> dict:
    """Compute breakdowns by individual dimensions."""
    dims = {
        "market_type": {},
        "asset": {},
        "expiry_bucket": {},
        "liquidity_bucket": {},
    }

    for r in results:
        fk = r.get("family_key", "")
        parts = fk.split(":")
        if len(parts) >= 4:
            for i, dim in enumerate(["market_type", "asset", "expiry_bucket", "liquidity_bucket"]):
                key = parts[i]
                if key not in dims[dim]:
                    dims[dim][key] = []
                dims[dim][key].append(r)

    output = {}
    for dim_name, dim_groups in dims.items():
        dim_results = []
        for key, group in dim_groups.items():
            if len(group) >= MIN_SAMPLE:
                metrics = _compute_family_metrics(f"{dim_name}:{key}", group)
                metrics["dimension_value"] = key
                dim_results.append(metrics)
        if dim_results:
            output[dim_name] = dim_results

    return output
