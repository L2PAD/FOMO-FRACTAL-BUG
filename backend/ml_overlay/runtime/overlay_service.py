"""
Overlay Service — compute ML correction with full gate pipeline.
"""

import numpy as np
from ml_overlay.config import HORIZONS, FEATURES
from ml_overlay.model.registry import load_model
from ml_overlay.gates import apply_full_pipeline


def compute_overlay(
    horizon_key: str,
    entry_price: float,
    rule_target_price: float,
    features_dict: dict,
    conf_rule: float = 0.1,
    r_ml_prev: float | None = None,
    risk_off_prob: float = 0.0,
    regime: str = "TREND",
) -> dict:
    """
    Compute ML overlay correction with full gate pipeline + drift-based mlWeight.
    """
    cfg = HORIZONS.get(horizon_key)
    if not cfg:
        return _no_overlay(entry_price, rule_target_price, "UNKNOWN_HORIZON")

    # Load model
    model, meta = load_model(horizon_key)
    if model is None:
        return _no_overlay(entry_price, rule_target_price, "NO_MODEL")

    # Use model-specific features if pruned, otherwise default FEATURES
    model_features = meta.get("features", FEATURES) if meta else FEATURES

    # Build feature vector and predict
    try:
        feat_array = np.array([[features_dict.get(f, 0) for f in model_features]])
        r_ml_raw = float(model.predict(feat_array)[0])
    except Exception:
        return _no_overlay(entry_price, rule_target_price, "PREDICT_ERROR")

    # Rule return
    r_rule = (rule_target_price / entry_price) - 1 if entry_price > 0 else 0

    # Full gate pipeline
    pipeline = apply_full_pipeline(
        r_rule=r_rule,
        r_ml_raw=r_ml_raw,
        conf_rule=conf_rule,
        horizon=horizon_key,
        r_ml_prev=r_ml_prev,
        risk_off_prob=risk_off_prob,
        regime=regime,
    )

    # Drift-based adaptive ML weight
    drift_weight = 1.0
    drift_info = None
    try:
        from drift.service import get_current_ml_weight
        drift_weight = get_current_ml_weight(horizon=horizon_key, asset="BTC")
        drift_info = {"mlWeight": round(drift_weight, 4), "source": "drift_snapshot"}
    except Exception:
        drift_info = {"mlWeight": 1.0, "source": "default"}

    # Graduation stage (mlAlpha)
    ml_alpha = 0.0
    stage = "SHADOW"
    try:
        from ml_overlay.graduation import get_effective_alpha
        grad = get_effective_alpha(horizon=horizon_key, asset="BTC")
        ml_alpha = grad["mlAlpha"]
        stage = grad["stage"]
    except Exception:
        pass

    effective_alpha = round(ml_alpha * drift_weight, 4)

    # Apply effectiveAlpha to ML correction: r_ml_used * effectiveAlpha
    r_ml_used_raw = pipeline["r_ml_used"]
    r_ml_used_weighted = r_ml_used_raw * effective_alpha

    # Recalculate final with graduated + drift-weighted ML
    r_final = r_rule + r_ml_used_weighted
    final_target = entry_price * (1 + r_final)

    # Mode: SHADOW if alpha=0, LIVE otherwise
    mode = "SHADOW" if ml_alpha == 0 else "LIVE"

    return {
        "mlCorrection": round(float(r_ml_used_weighted), 6),
        "mlCorrectionRaw": pipeline["r_ml_raw"],
        "mlCorrectionBeforeDrift": round(float(r_ml_used_raw), 6),
        "mlCorrectionPrice": round(float(final_target - rule_target_price), 2),
        "finalTargetPrice": round(float(final_target), 2),
        "ruleReturn": pipeline["r_rule"],
        "finalReturn": round(float(r_final), 6),
        "mode": mode,
        "stage": stage,
        "mlAlpha": ml_alpha,
        "effectiveAlpha": effective_alpha,
        "modelId": meta.get("modelId") if meta else None,
        "capped": bool(pipeline["gates"]["cap"]["applied"]),
        "cap": float(cfg["cap"]),
        "weight": pipeline["weight"],
        "driftWeight": round(drift_weight, 4),
        "drift": drift_info,
        "gates": pipeline["gates"],
        "directionPreserved": bool(
            np.sign(r_rule) == 0 or np.sign(r_final) == np.sign(r_rule)
        ),
    }


def _no_overlay(entry_price, rule_target_price, reason):
    r_rule = (rule_target_price / entry_price) - 1 if entry_price > 0 else 0
    return {
        "mlCorrection": 0.0,
        "mlCorrectionRaw": 0.0,
        "mlCorrectionPrice": 0.0,
        "finalTargetPrice": round(float(rule_target_price), 2),
        "ruleReturn": round(float(r_rule), 6),
        "finalReturn": round(float(r_rule), 6),
        "mode": "DISABLED",
        "modelId": None,
        "capped": False,
        "cap": 0.0,
        "weight": 0.0,
        "gates": {},
        "directionPreserved": True,
        "reason": reason,
    }
