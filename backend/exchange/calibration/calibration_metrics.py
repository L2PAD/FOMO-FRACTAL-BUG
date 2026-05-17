"""
Calibration Metrics — Block 8.2
================================
Computes Brier Score, ECE, Sharpness, and bucket reliability data
from evaluated forecasts. This is the "truth measurement" layer.

Metrics:
  - Brier Score: mean((confidence - outcome)^2), lower = better
  - ECE: weighted average |avg_conf - real_accuracy| per bucket
  - Sharpness: variance of confidence distribution (higher = more decisive)
  - Bucket table: per-bucket avg_conf vs real_accuracy for reliability curve
"""

import os
from collections import defaultdict
from pymongo import MongoClient


def _get_db():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    return MongoClient(mongo_url)[db_name]


def _is_correct(outcome: dict) -> bool:
    """Determine if forecast outcome is correct (TP or WEAK)."""
    label = outcome.get("outcome", outcome.get("label", ""))
    return label in ("TP", "WEAK")


def _load_evaluated(asset: str | None = None, horizon: str | None = None) -> list[dict]:
    """Load evaluated forecasts with confidence and outcome."""
    db = _get_db()
    col = db["exchange_forecasts"]

    query = {"evaluated": True}
    if asset:
        query["asset"] = asset.upper()
    if horizon:
        query["horizon"] = horizon

    projection = {
        "_id": 0,
        "confidence": 1,
        "confidenceRaw": 1,
        "outcome": 1,
        "asset": 1,
        "horizon": 1,
    }

    docs = list(col.find(query, projection))
    results = []
    for doc in docs:
        outcome = doc.get("outcome")
        if not outcome or not isinstance(outcome, dict):
            continue
        label = outcome.get("outcome", outcome.get("label", ""))
        if not label:
            continue

        conf = doc.get("confidence")
        conf_raw = doc.get("confidenceRaw")
        if conf is None and conf_raw is None:
            continue

        results.append({
            "confidence": conf if conf is not None else conf_raw,
            "confidenceRaw": conf_raw if conf_raw is not None else conf,
            "correct": _is_correct(outcome),
            "asset": doc.get("asset", "BTC"),
            "horizon": doc.get("horizon", "7D"),
        })

    return results


def compute_brier_score(preds: list[dict]) -> float | None:
    """Brier Score = mean((p - y)^2). Lower is better. Range [0, 1]."""
    if not preds:
        return None
    total = 0.0
    for p in preds:
        conf = p["confidence"]
        y = 1.0 if p["correct"] else 0.0
        total += (conf - y) ** 2
    return round(total / len(preds), 6)


def compute_ece(preds: list[dict], n_bins: int = 5) -> tuple[float | None, list[dict]]:
    """Expected Calibration Error with bucket analysis.

    Returns (ece_value, bucket_list).
    """
    if not preds:
        return None, []

    # Create buckets
    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    buckets = []

    for i in range(n_bins):
        low = bin_edges[i]
        high = bin_edges[i + 1]

        in_bucket = [p for p in preds if low <= p["confidence"] < high]
        # Include upper edge in last bucket
        if i == n_bins - 1:
            in_bucket = [p for p in preds if low <= p["confidence"] <= high]

        if not in_bucket:
            buckets.append({
                "range": [round(low, 2), round(high, 2)],
                "avgConf": None,
                "accuracy": None,
                "gap": None,
                "count": 0,
            })
            continue

        avg_conf = sum(p["confidence"] for p in in_bucket) / len(in_bucket)
        n_correct = sum(1 for p in in_bucket if p["correct"])
        accuracy = n_correct / len(in_bucket)
        gap = avg_conf - accuracy

        buckets.append({
            "range": [round(low, 2), round(high, 2)],
            "avgConf": round(avg_conf, 4),
            "accuracy": round(accuracy, 4),
            "gap": round(gap, 4),
            "count": len(in_bucket),
        })

    # ECE = weighted average of |gap|
    total_n = len(preds)
    ece = 0.0
    for b in buckets:
        if b["count"] > 0 and b["gap"] is not None:
            ece += (b["count"] / total_n) * abs(b["gap"])

    return round(ece, 6), buckets


def compute_sharpness(preds: list[dict]) -> float | None:
    """Sharpness = variance of confidence. Higher = more decisive model."""
    if not preds:
        return None
    confs = [p["confidence"] for p in preds]
    mean_conf = sum(confs) / len(confs)
    var_conf = sum((c - mean_conf) ** 2 for c in confs) / len(confs)
    return round(var_conf, 6)


def compute_calibration_metrics(
    asset: str | None = None,
    horizon: str | None = None,
) -> dict:
    """Compute full calibration metrics suite.

    Args:
        asset: Filter by asset (None = all)
        horizon: Filter by horizon (None = all)

    Returns:
        Dict with brier, ece, sharpness, buckets, and metadata.
    """
    preds = _load_evaluated(asset, horizon)

    if not preds:
        return {
            "asset": asset or "ALL",
            "horizon": horizon or "ALL",
            "sampleSize": 0,
            "status": "INSUFFICIENT_DATA",
        }

    brier = compute_brier_score(preds)
    ece, buckets = compute_ece(preds, n_bins=5)
    sharpness = compute_sharpness(preds)

    # Accuracy
    n_correct = sum(1 for p in preds if p["correct"])
    accuracy = round(n_correct / len(preds), 4)

    # Avg confidence
    avg_conf = round(sum(p["confidence"] for p in preds) / len(preds), 4)

    # Monotonicity check: non-empty buckets should have increasing accuracy
    non_empty = [b for b in buckets if b["count"] > 0 and b["accuracy"] is not None]
    monotonic = True
    for i in range(1, len(non_empty)):
        if non_empty[i]["accuracy"] < non_empty[i - 1]["accuracy"] - 0.05:
            monotonic = False
            break

    # Verdict
    verdict = "OK"
    issues = []

    if brier is not None and brier > 0.25:
        issues.append("HIGH_BRIER")
    if ece is not None and ece > 0.10:
        issues.append("HIGH_ECE")
    if sharpness is not None and sharpness < 0.005:
        issues.append("FLAT_MODEL")
    if not monotonic:
        issues.append("NON_MONOTONIC")

    if issues:
        verdict = "NEEDS_ATTENTION"

    return {
        "asset": asset or "ALL",
        "horizon": horizon or "ALL",
        "sampleSize": len(preds),
        "accuracy": accuracy,
        "avgConfidence": avg_conf,
        "brierScore": brier,
        "ece": ece,
        "sharpness": sharpness,
        "bucketMonotonicity": monotonic,
        "verdict": verdict,
        "issues": issues,
        "buckets": buckets,
    }


def compute_before_after(asset: str | None = None, horizon: str | None = None) -> dict:
    """Compare calibration metrics: raw vs stored vs new calibrator.

    Three layers:
      - raw: original model confidence (no calibration)
      - stored: what's currently in DB (old calibration for old forecasts)
      - simulated: what Block 8.1 calibrator would produce from raw
    """
    from exchange.calibration.confidence_calibrator import calibrate_confidence

    preds = _load_evaluated(asset, horizon)
    if not preds:
        return {"status": "INSUFFICIENT_DATA"}

    # Layer 1: raw (no calibration)
    preds_raw = [{"confidence": p["confidenceRaw"], "correct": p["correct"]} for p in preds]
    brier_raw = compute_brier_score(preds_raw)
    ece_raw, _ = compute_ece(preds_raw, n_bins=5)
    sharp_raw = compute_sharpness(preds_raw)

    # Layer 2: stored (what's in DB — old calibration for old forecasts)
    brier_stored = compute_brier_score(preds)
    ece_stored, _ = compute_ece(preds, n_bins=5)
    sharp_stored = compute_sharpness(preds)

    # Layer 3: simulated new calibration (Block 8.1 applied to raw)
    preds_new = []
    for p in preds:
        new_conf = calibrate_confidence(p["confidenceRaw"], p["horizon"])
        preds_new.append({"confidence": new_conf, "correct": p["correct"]})

    brier_new = compute_brier_score(preds_new)
    ece_new, buckets_new = compute_ece(preds_new, n_bins=5)
    sharp_new = compute_sharpness(preds_new)

    return {
        "asset": asset or "ALL",
        "horizon": horizon or "ALL",
        "sampleSize": len(preds),
        "raw": {
            "brierScore": brier_raw,
            "ece": ece_raw,
            "sharpness": sharp_raw,
            "label": "raw (no calibration)",
        },
        "stored": {
            "brierScore": brier_stored,
            "ece": ece_stored,
            "sharpness": sharp_stored,
            "label": "stored (old calibration in DB)",
        },
        "newCalibration": {
            "brierScore": brier_new,
            "ece": ece_new,
            "sharpness": sharp_new,
            "label": "simulated (Block 8.1 calibrator)",
            "buckets": buckets_new,
        },
        "improvement": {
            "brierDelta": round(brier_raw - brier_new, 6) if brier_raw and brier_new else None,
            "eceDelta": round(ece_raw - ece_new, 6) if ece_raw and ece_new else None,
            "sharpnessDelta": round(sharp_new - sharp_raw, 6) if sharp_new and sharp_raw else None,
        },
    }
