"""
Catastrophic Risk Classifier — Block 12.1
==========================================
Binary classifier predicting whether a forecast will be catastrophically wrong.

Catastrophic = direction wrong AND significant adverse move.

Two-tier feature strategy:
  - BASIC features (available for all 300+ evaluated forecasts):
    confidence, direction encoding, expected move, horizon
  - RICH features (available for newer v4.1+ forecasts):
    confidence_raw, regime_confidence, volatility, momentum, scenario_spread

Model: Logistic Regression (simple, interpretable, robust for small datasets).
"""

import os
import logging
import numpy as np
import time

logger = logging.getLogger("catastrophic_risk")

# Catastrophic thresholds per horizon
CATASTROPHIC_THRESHOLDS = {
    "24H": 2.0,   # wrong direction + >2% move
    "7D": 5.0,    # wrong direction + >5% move
    "30D": 8.0,   # wrong direction + >8% move
}

# Basic features available for ALL forecasts
BASIC_FEATURES = [
    "confidence",
    "direction_bull",
    "direction_bear",
    "expected_move_abs",
    "horizon_days",
]

# Rich features (appended when available, filled with 0 otherwise)
RICH_FEATURES = [
    "confidence_raw",
    "confidence_direction",
    "regime_confidence",
    "regime_shrinkage",
    "rolling_win_rate",
    "score_final",
    "degraded",
    "ret_1d",
    "ret_7d",
    "volatility",
    "momentum",
    "scenario_spread",
]

ALL_FEATURES = BASIC_FEATURES + RICH_FEATURES


def _get_db():
    from pymongo import MongoClient
    return MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]


def _is_catastrophic(direction: str, real_move_pct: float, horizon: str) -> bool:
    """Label a forecast as catastrophic based on direction mismatch + significant move."""
    threshold = CATASTROPHIC_THRESHOLDS.get(horizon, 5.0)
    d = (direction or "NEUTRAL").upper()

    if d == "LONG" and real_move_pct < -threshold:
        return True
    if d == "SHORT" and real_move_pct > threshold:
        return True
    if d == "NEUTRAL" and abs(real_move_pct) > threshold * 1.5:
        return True
    return False


def _horizon_to_days(h: str) -> float:
    return {"24H": 1, "7D": 7, "30D": 30}.get(h, 7)


def _extract_features(doc: dict) -> dict | None:
    """Extract feature vector from a forecast document. Works with any model version."""
    confidence = doc.get("confidence")
    if confidence is None:
        return None

    direction = (doc.get("direction") or "NEUTRAL").upper()
    entry = doc.get("entryPrice") or 0
    target = doc.get("targetPrice") or entry
    horizon = doc.get("horizon", "7D")

    expected_move = abs((target - entry) / entry) if entry > 0 else 0.0

    feats = {
        # Basic (always available)
        "confidence": float(confidence),
        "direction_bull": 1.0 if direction == "LONG" else 0.0,
        "direction_bear": 1.0 if direction == "SHORT" else 0.0,
        "expected_move_abs": float(expected_move),
        "horizon_days": float(_horizon_to_days(horizon)),
        # Rich (filled from audit when available)
        "confidence_raw": 0.0,
        "confidence_direction": 0.0,
        "regime_confidence": 0.5,
        "regime_shrinkage": 1.0,
        "rolling_win_rate": 0.5,
        "score_final": 0.0,
        "degraded": 0.0,
        "ret_1d": 0.0,
        "ret_7d": 0.0,
        "volatility": 0.0,
        "momentum": 0.0,
        "scenario_spread": 0.0,
    }

    # Enrich from audit when available
    audit = doc.get("audit") or {}
    if audit.get("confidenceRaw") is not None:
        feats["confidence_raw"] = float(audit["confidenceRaw"])
    if audit.get("confidenceDirection") is not None:
        feats["confidence_direction"] = float(audit["confidenceDirection"])
    if audit.get("regimeConfidence") is not None:
        feats["regime_confidence"] = float(audit["regimeConfidence"])
    if audit.get("regimeShrinkage") is not None:
        feats["regime_shrinkage"] = float(audit["regimeShrinkage"])
    if audit.get("rollingWinRate") is not None:
        feats["rolling_win_rate"] = float(audit["rollingWinRate"])
    if audit.get("scoreFinal") is not None:
        feats["score_final"] = float(audit["scoreFinal"])
    if audit.get("degraded"):
        feats["degraded"] = 1.0

    market_feats = audit.get("features") or {}
    for mf in ["ret_1d", "ret_7d", "volatility", "momentum"]:
        if market_feats.get(mf) is not None:
            feats[mf] = float(market_feats[mf])

    scenarios = doc.get("scenarios") or {}
    if scenarios.get("spread") is not None:
        feats["scenario_spread"] = float(scenarios["spread"])

    return feats


def build_dataset(horizon: str = None) -> list[dict]:
    """
    Build labeled dataset from evaluated forecasts.
    Computes realMovePct from prices when not directly available.
    """
    db = _get_db()
    query = {"evaluated": True, "outcome": {"$ne": None}}
    if horizon:
        query["horizon"] = horizon

    docs = list(db["exchange_forecasts"].find(query, {"_id": 0}))

    dataset = []
    for doc in docs:
        outcome = doc.get("outcome") or {}
        entry = doc.get("entryPrice") or 0

        # Get real move — compute from prices if not directly available
        real_move = outcome.get("realMovePct")
        if real_move is None:
            actual = outcome.get("actualPriceAtEval") or outcome.get("realPrice", 0) or 0
            if entry > 0 and actual > 0:
                real_move = ((actual - entry) / entry) * 100
            else:
                continue

        feats = _extract_features(doc)
        if feats is None:
            continue

        h = doc.get("horizon", "7D")
        direction = doc.get("direction", "NEUTRAL")
        label = 1 if _is_catastrophic(direction, real_move, h) else 0

        dataset.append({
            "features": feats,
            "label": label,
            "horizon": h,
            "direction": direction,
            "real_move_pct": real_move,
        })

    return dataset


def train_model(dataset: list[dict] = None, horizon: str = None):
    """
    Train logistic regression classifier on catastrophic risk dataset.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
    from sklearn.model_selection import cross_val_predict

    if dataset is None:
        dataset = build_dataset(horizon=horizon)

    if len(dataset) < 20:
        return {
            "status": "INSUFFICIENT_DATA",
            "samples": len(dataset),
            "min_required": 20,
        }

    X = np.array([[row["features"][f] for f in ALL_FEATURES] for row in dataset])
    y = np.array([row["label"] for row in dataset])

    # Handle NaN/inf
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    pos_count = int(y.sum())
    neg_count = len(y) - pos_count

    if pos_count < 3 or neg_count < 3:
        return {
            "status": "INSUFFICIENT_POSITIVE_SAMPLES",
            "samples": len(dataset),
            "positive": pos_count,
            "negative": neg_count,
        }

    model = LogisticRegression(
        max_iter=500,
        class_weight="balanced",
        C=0.5,
        solver="lbfgs",
    )

    # Cross-validated predictions for metrics
    n_splits = min(5, min(pos_count, neg_count))
    if n_splits >= 2:
        cv_probs = cross_val_predict(model, X, y, cv=n_splits, method="predict_proba")[:, 1]
        cv_preds = (cv_probs >= 0.5).astype(int)
        auc = roc_auc_score(y, cv_probs) if len(set(y)) > 1 else 0.0
        precision = precision_score(y, cv_preds, zero_division=0)
        recall = recall_score(y, cv_preds, zero_division=0)
        f1 = f1_score(y, cv_preds, zero_division=0)
    else:
        auc = precision = recall = f1 = 0.0

    # Final model on all data
    model.fit(X, y)

    # Feature importance (absolute coefficients)
    coefficients = model.coef_[0]
    importance = {ALL_FEATURES[i]: round(float(abs(coefficients[i])), 4) for i in range(len(ALL_FEATURES))}
    importance_sorted = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    return {
        "status": "OK",
        "model": model,
        "samples": len(dataset),
        "positive_rate": round(pos_count / len(dataset), 4),
        "metrics": {
            "auc": round(auc, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
        "feature_importance": importance_sorted,
        "class_distribution": {"catastrophic": pos_count, "normal": neg_count},
    }


# ── Singleton model cache ──
_cached_model = None
_cached_at = 0.0
_CACHE_TTL = 3600


def _get_or_train_model():
    """Lazy-load and cache the trained model."""
    global _cached_model, _cached_at

    now = time.time()
    if _cached_model and _cached_model.get("status") == "OK" and (now - _cached_at < _CACHE_TTL):
        return _cached_model

    try:
        result = train_model()
        if result.get("status") == "OK":
            _cached_model = result
            _cached_at = now
            logger.info(
                "Catastrophic risk model trained: samples=%d, AUC=%.4f, pos_rate=%.2f%%",
                result["samples"], result["metrics"]["auc"], result["positive_rate"] * 100,
            )
        return result
    except Exception as e:
        logger.warning("Failed to train catastrophic risk model: %s", e)
        return {"status": "TRAIN_ERROR", "error": str(e)}


def predict_catastrophic_risk(forecast_doc: dict) -> dict:
    """
    Predict catastrophic risk for a single forecast.
    """
    model_result = _get_or_train_model()
    if model_result.get("status") != "OK":
        return {
            "catastrophic_risk": 0.0,
            "risk_level": "unknown",
            "model_status": model_result.get("status", "ERROR"),
        }

    feats = _extract_features(forecast_doc)
    if feats is None:
        return {
            "catastrophic_risk": 0.0,
            "risk_level": "unknown",
            "model_status": "NO_FEATURES",
        }

    model = model_result["model"]
    X = np.array([[feats[f] for f in ALL_FEATURES]])
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    prob = float(model.predict_proba(X)[0][1])

    if prob > 0.6:
        risk_level = "high"
    elif prob > 0.4:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "catastrophic_risk": round(prob, 4),
        "risk_level": risk_level,
        "model_status": "OK",
    }


def predict_from_asset(asset: str, horizon: str = "7D") -> dict:
    """Predict catastrophic risk for the latest forecast of an asset."""
    from pymongo import DESCENDING
    db = _get_db()
    doc = db["exchange_forecasts"].find_one(
        {"asset": asset.upper(), "horizon": horizon},
        {"_id": 0},
        sort=[("createdAt", DESCENDING)],
    )
    if not doc:
        return {
            "catastrophic_risk": 0.0,
            "risk_level": "unknown",
            "model_status": "NO_FORECAST",
            "asset": asset,
            "horizon": horizon,
        }

    result = predict_catastrophic_risk(doc)
    result["asset"] = asset.upper()
    result["horizon"] = horizon
    return result
