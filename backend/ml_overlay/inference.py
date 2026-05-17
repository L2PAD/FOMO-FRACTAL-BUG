"""
ML Overlay V1: Inference Module
Shadow mode: predict risk_score for forecasts.
"""
from pathlib import Path

import joblib
import pandas as pd

from ml_overlay.dataset_builder import NUMERIC_FEATURES, CATEGORICAL_FEATURES

MODEL_PATH = Path("/app/backend/artifacts/ml_overlay_v1/model.joblib")
_model = None


def load_model():
    global _model
    if _model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError("ML Overlay model not trained yet")
        _model = joblib.load(MODEL_PATH)
    return _model


def reload_model():
    """Force reload the model from disk."""
    global _model
    _model = None
    return load_model()


def feature_row_from_forecast(doc):
    """Extract feature row from a forecast document (same logic as dataset_builder)."""
    audit = doc.get("audit") or {}
    regime_v2 = audit.get("regimeV2") or {}
    probs = regime_v2.get("probabilities") or {}
    features = audit.get("features") or {}
    interaction = audit.get("interaction") or {}
    rv2_features = regime_v2.get("features") or {}

    return {
        "confidence": float(doc.get("confidence") or 0.0),
        "confidence_raw": float(audit.get("confidenceRaw", doc.get("confidenceRaw")) or 0.0),
        "confidence_direction": float(audit.get("confidenceDirection") or 0.0),
        "confidence_target": float(audit.get("confidenceTarget") or 0.0),
        "expected_move_pct": float(doc.get("expectedMovePct") or 0.0),
        "regime_confidence": float(regime_v2.get("regime_confidence", audit.get("regimeConfidence")) or 0.0),
        "regime_entropy": float(regime_v2.get("regime_entropy") or 0.0),
        "prob_trend": float(probs.get("trend") or 0.0),
        "prob_range": float(probs.get("range") or 0.0),
        "prob_pullback": float(probs.get("pullback") or 0.0),
        "prob_transition": float(probs.get("transition") or 0.0),
        "prob_breakdown": float(probs.get("breakdown") or 0.0),
        "score_raw": float(audit.get("scoreRaw") or 0.0),
        "score_final": float(audit.get("scoreFinal") or 0.0),
        "degraded": 1 if audit.get("degraded") else 0,
        "rolling_win_rate": float(audit.get("rollingWinRate") or 0.0),
        "ret_1d": float(features.get("ret_1d") or 0.0),
        "ret_7d": float(features.get("ret_7d") or 0.0),
        "ret_14d": float(features.get("ret_14d") or 0.0),
        "volatility": float(features.get("volatility") or 0.0),
        "momentum": float(features.get("momentum") or 0.0),
        "trend_strength": float(rv2_features.get("trend_strength") or 0.0),
        "exhaustion": float(rv2_features.get("exhaustion") or 0.0),
        "reversal_risk": float(rv2_features.get("reversal_risk") or 0.0),
        "structure_alignment": float(rv2_features.get("structure_alignment") or 0.0),
        "volatility_expansion": float(rv2_features.get("volatility_expansion") or 0.0),
        "alignment_score": float(interaction.get("alignment_score") or 0.0),
        "conflict_score": float(interaction.get("conflict_score") or 0.0),
        "confidence_modifier": float(interaction.get("confidence_modifier") or 0.0),
        "asset": doc.get("asset") or "unknown",
        "horizon": doc.get("horizon") or "unknown",
        "regime": regime_v2.get("dominant_regime") or audit.get("regime") or "unknown",
        "direction": doc.get("direction") or "NEUTRAL",
        "direction_class": audit.get("directionClass") or doc.get("direction") or "NEUTRAL",
        "interaction_state": interaction.get("state_group") or interaction.get("interaction_state") or "unknown",
    }


def risk_bucket(score):
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def preview_confidence_with_ml(conf, risk_score):
    out = float(conf)
    if risk_score >= 0.85:
        out *= 0.5
    elif risk_score >= 0.7:
        out *= 0.7
    elif risk_score >= 0.45:
        out *= 0.85
    return round(max(0.0, min(1.0, out)), 4)


def infer_ml_overlay(doc):
    """Run ML overlay inference on a forecast document. Returns shadow audit dict."""
    model = load_model()
    row = feature_row_from_forecast(doc)
    df = pd.DataFrame([row])
    score = float(model.predict_proba(df)[0, 1])

    return {
        "risk_score": round(score, 4),
        "risk_bucket": risk_bucket(score),
        "would_reduce_confidence": score >= 0.45,
        "confidence_before_ml": float(doc.get("confidence") or 0),
        "confidence_after_ml_preview": preview_confidence_with_ml(
            doc.get("confidence", 0), score
        ),
    }
