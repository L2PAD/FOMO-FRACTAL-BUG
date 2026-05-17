"""
Drift Service — orchestrates daily drift computation.

Pulls data from:
- ml_overlay_registry (baseline train metrics)
- exchange_forecasts (evaluated outcomes for performance)
- OHLCV features (for feature drift)

Writes to:
- drift_snapshots (daily drift results)
"""

import os
import numpy as np
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

from drift.feature_drift import compute_feature_drift
from drift.performance_drift import compute_performance_drift
from drift.calibration_drift import compute_calibration_drift
from drift.drift_score import compute_drift_score
from drift.config import PERF_WINDOW_DAYS, FEATURE_WINDOW_DAYS

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def compute_drift_snapshot(horizon: str = "7D", asset: str = "BTC") -> dict:
    """
    Compute a full drift snapshot for the given horizon.
    """
    db = _db()
    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)

    # ── 1. Performance drift ──
    # Baseline: walk-forward metrics from registry
    registry_doc = db["ml_overlay_registry"].find_one(
        {"horizon": horizon, "status": "ACTIVE"},
        {"_id": 0},
        sort=[("createdAt", DESCENDING)],
    )

    baseline_perf = {"mae": 0.08, "dir_hit": 0.52, "flip_rate": 0.25}
    if registry_doc and registry_doc.get("walkForwardMetrics"):
        # Use last fold as baseline
        last_fold = [f for f in registry_doc["walkForwardMetrics"] if "error" not in f]
        if last_fold:
            lf = last_fold[-1]
            baseline_perf = {
                "mae": lf.get("err_rule", 0.08),
                "dir_hit": lf.get("dir_hit_final", 52) / 100,
                "flip_rate": lf.get("flip_rate", 25) / 100,
            }

    # Production: recent evaluated forecasts
    cutoff_ms = now_ms - PERF_WINDOW_DAYS * 86400 * 1000
    eval_docs = list(db["exchange_forecasts"].find(
        {"asset": asset, "horizon": horizon, "evaluated": True, "createdAt": {"$gte": cutoff_ms}},
        {"_id": 0, "outcome": 1, "direction": 1, "confidence": 1, "targetPrice": 1, "entryPrice": 1, "basePrice": 1},
    ))

    dir_hits = []
    confidences = []

    if len(eval_docs) >= 5:
        errors = []
        directions = []

        for doc in eval_docs:
            outcome = doc.get("outcome", {})
            entry = doc.get("entryPrice") or doc.get("basePrice", 0)
            target = doc.get("targetPrice", entry)
            real_price = outcome.get("realPrice", 0)

            if entry > 0 and real_price > 0:
                r_real = (real_price / entry) - 1
                r_rule = (target / entry) - 1
                errors.append(abs(r_real - r_rule))
                dir_match = (r_real > 0) == (r_rule > 0) if r_rule != 0 else False
                dir_hits.append(1 if dir_match else 0)
                directions.append(1 if r_rule > 0 else -1)
                confidences.append(doc.get("confidence", 0.1))

        prod_mae = float(np.mean(errors)) if errors else 0.08
        prod_dir_hit = float(np.mean(dir_hits)) if dir_hits else 0.5
        # Flip rate
        flips = sum(1 for i in range(1, len(directions)) if directions[i] != directions[i-1])
        prod_flip = flips / max(1, len(directions) - 1) if len(directions) > 1 else 0.25

        prod_perf = {"mae": prod_mae, "dir_hit": prod_dir_hit, "flip_rate": prod_flip}
    else:
        prod_perf = baseline_perf.copy()

    perf_drift = compute_performance_drift(baseline_perf, prod_perf)

    # ── 2. Feature drift ──
    # Use the feature data from the overlay model training as baseline
    feature_drift_result = {"avgPsi": 0, "maxPsi": 0, "driftedCount": 0, "watchCount": 0, "features": {}}
    try:
        from ml_overlay.data.price_provider import get_ohlcv
        from ml_overlay.features.compute_features import compute_features
        from ml_overlay.config import FEATURES

        ohlcv = get_ohlcv("BTC-USD", years=3)
        all_features = compute_features(ohlcv)

        # Baseline: train period (>60 days ago)
        baseline_end = now - timedelta(days=FEATURE_WINDOW_DAYS)
        baseline_start = baseline_end - timedelta(days=365)
        base_mask = (all_features.index >= baseline_start) & (all_features.index < baseline_end)
        prod_mask = all_features.index >= baseline_end

        base_df = all_features[base_mask]
        prod_df = all_features[prod_mask]

        if len(base_df) > 30 and len(prod_df) > 10:
            base_dict = {f: base_df[f].values for f in FEATURES if f in base_df.columns}
            prod_dict = {f: prod_df[f].values for f in FEATURES if f in prod_df.columns}
            feature_drift_result = compute_feature_drift(base_dict, prod_dict)
    except Exception:
        pass

    # ── 3. Calibration drift ──
    calib_result = {"brier": 0, "ece": 0, "status": "OK", "n": 0}
    if confidences and dir_hits:
        calib_result = compute_calibration_drift(
            np.array(confidences, dtype=float),
            np.array(dir_hits, dtype=float),
        )

    # ── 4. Composite drift score (regime-aware) ──
    # Get regime baseline for context-aware comparison
    regime_baseline = None
    regime = "UNKNOWN"
    regime_confidence = 0.0

    # First try macro_state
    try:
        macro_doc = db["macro_state"].find_one({}, {"_id": 0, "regime": 1, "confidence": 1}, sort=[("ts", DESCENDING)])
        if macro_doc:
            regime = macro_doc.get("regime", "UNKNOWN")
            regime_confidence = macro_doc.get("confidence", 0)
    except Exception:
        pass

    # Fallback: infer from price data if macro_state has unknown/insufficient regime
    if regime in ("UNKNOWN", ""):
        try:
            from drift.regime_classifier import get_current_regime_from_price
            from ml_overlay.data.price_provider import get_ohlcv
            recent = get_ohlcv("BTC-USD", years=1)
            regime = get_current_regime_from_price(recent)
        except Exception:
            regime = "TRANSITION"

    # Fetch regime-specific baseline
    try:
        from drift.regime_classifier import get_regime_baseline
        regime_baseline = get_regime_baseline(horizon, regime)
    except Exception:
        pass

    score = compute_drift_score(feature_drift_result, perf_drift, calib_result, regime_baseline)

    regime_adjusted = score.get("regimeAdjusted", False)

    snapshot = {
        "asset": asset,
        "horizon": horizon,
        "date": now.strftime("%Y-%m-%d"),
        "ts": now_ms,
        "driftScore": score["driftScore"],
        "mlWeight": score["mlWeight"],
        "status": score["status"],
        "components": score["components"],
        "drivers": score["drivers"],
        "regime": regime,
        "regimeConfidence": round(regime_confidence, 2),
        "regimeAdjusted": regime_adjusted,
        "regimeContext": score.get("regimeContext"),
        "performance": {
            "baseline": baseline_perf,
            "production": prod_perf,
            "drift": perf_drift,
        },
        "features": {
            "avgPsi": feature_drift_result.get("avgPsi", 0),
            "maxPsi": feature_drift_result.get("maxPsi", 0),
            "driftedCount": feature_drift_result.get("driftedCount", 0),
            "topDrifted": _top_drifted(feature_drift_result.get("features", {})),
        },
        "calibration": calib_result,
    }

    # Store snapshot
    db["drift_snapshots"].update_one(
        {"asset": asset, "horizon": horizon, "date": snapshot["date"]},
        {"$set": snapshot},
        upsert=True,
    )

    return snapshot


def _top_drifted(features: dict, limit: int = 3) -> list:
    """Get top drifted features by PSI."""
    items = [(k, v) for k, v in features.items() if v.get("psi", 0) > 0.05]
    items.sort(key=lambda x: -x[1]["psi"])
    return [{"name": k, **v} for k, v in items[:limit]]


def get_drift_history(horizon: str = "7D", asset: str = "BTC", days: int = 45) -> list:
    """Get drift snapshots history."""
    db = _db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_ms = int(cutoff.timestamp() * 1000)
    docs = list(db["drift_snapshots"].find(
        {"asset": asset, "horizon": horizon, "ts": {"$gte": cutoff_ms}},
        {"_id": 0},
    ).sort("ts", 1))
    return docs


def get_drift_history_chart(horizon: str = "7D", asset: str = "BTC", days: int = 45) -> list:
    """Lightweight drift history for charting (only key metrics)."""
    db = _db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_ms = int(cutoff.timestamp() * 1000)
    docs = list(db["drift_snapshots"].find(
        {"asset": asset, "horizon": horizon, "ts": {"$gte": cutoff_ms}},
        {"_id": 0, "date": 1, "driftScore": 1, "mlWeight": 1, "status": 1,
         "regime": 1, "performance.production.mae": 1, "performance.baseline.mae": 1,
         "performance.production.dir_hit": 1, "performance.baseline.dir_hit": 1},
    ).sort("ts", 1))
    result = []
    for d in docs:
        prod = d.get("performance", {}).get("production", {})
        base = d.get("performance", {}).get("baseline", {})
        result.append({
            "date": d.get("date"),
            "driftScore": d.get("driftScore", 0),
            "mlWeight": d.get("mlWeight", 1),
            "status": d.get("status", "OK"),
            "regime": d.get("regime", ""),
            "maeRule": round(base.get("mae", 0), 6),
            "maeProd": round(prod.get("mae", 0), 6),
            "dirHitRule": round(base.get("dir_hit", 0), 4),
            "dirHitProd": round(prod.get("dir_hit", 0), 4),
        })
    return result


def get_current_ml_weight(horizon: str = "7D", asset: str = "BTC") -> float:
    """Get the latest ML weight for the overlay."""
    db = _db()
    doc = db["drift_snapshots"].find_one(
        {"asset": asset, "horizon": horizon},
        {"_id": 0, "mlWeight": 1},
        sort=[("ts", DESCENDING)],
    )
    return doc.get("mlWeight", 1.0) if doc else 1.0
