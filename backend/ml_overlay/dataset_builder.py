"""
ML Overlay V1: Dataset Builder
Builds unified ML dataset from exchange_forecasts with outcomes.
Target: predict forecast ERROR (FP/FN/WEAK) — NOT market direction.
"""
from datetime import datetime, timezone


def safe_num(x, default=0.0):
    try:
        if x is None:
            return default
        return float(x)
    except (ValueError, TypeError):
        return default


def build_ml_row(doc):
    """
    Build a single ML overlay row from an exchange_forecast document.
    Returns dict or None if doc lacks required data.
    """
    outcome = doc.get("outcome")
    if not outcome or not isinstance(outcome, dict):
        return None

    label = outcome.get("label")
    if label is None or label == "NO_DATA":
        return None

    # Target: 1 = system error, 0 = correct
    target_error = 1 if label in ("FP", "FN", "WEAK") else 0
    target_fp = 1 if label == "FP" else 0

    audit = doc.get("audit") or {}
    regime_v2 = audit.get("regimeV2") or {}
    probs = regime_v2.get("probabilities") or {}
    features = audit.get("features") or {}
    interaction = audit.get("interaction") or {}

    row = {
        "forecast_id": str(doc.get("id", doc.get("_id", ""))),
        "createdAt": doc.get("createdAt"),
        "asset": doc.get("asset", "unknown"),
        "horizon": doc.get("horizon", "unknown"),

        # Core confidence
        "confidence": safe_num(doc.get("confidence")),
        "confidence_raw": safe_num(audit.get("confidenceRaw", doc.get("confidenceRaw"))),
        "confidence_direction": safe_num(audit.get("confidenceDirection")),
        "confidence_target": safe_num(audit.get("confidenceTarget")),
        "expected_move_pct": safe_num(doc.get("expectedMovePct")),

        # Regime
        "regime": regime_v2.get("dominant_regime") or audit.get("regime") or "unknown",
        "regime_confidence": safe_num(regime_v2.get("regime_confidence", audit.get("regimeConfidence"))),
        "regime_entropy": safe_num(regime_v2.get("regime_entropy")),

        # Regime probabilities
        "prob_trend": safe_num(probs.get("trend")),
        "prob_range": safe_num(probs.get("range")),
        "prob_pullback": safe_num(probs.get("pullback")),
        "prob_transition": safe_num(probs.get("transition")),
        "prob_breakdown": safe_num(probs.get("breakdown")),

        # Score
        "score_raw": safe_num(audit.get("scoreRaw")),
        "score_final": safe_num(audit.get("scoreFinal")),
        "degraded": 1 if audit.get("degraded") else 0,
        "rolling_win_rate": safe_num(audit.get("rollingWinRate")),

        # Market features (pre-prediction)
        "ret_1d": safe_num(features.get("ret_1d")),
        "ret_7d": safe_num(features.get("ret_7d")),
        "ret_14d": safe_num(features.get("ret_14d")),
        "volatility": safe_num(features.get("volatility")),
        "momentum": safe_num(features.get("momentum")),

        # Regime V2 features
        "trend_strength": safe_num((regime_v2.get("features") or {}).get("trend_strength")),
        "exhaustion": safe_num((regime_v2.get("features") or {}).get("exhaustion")),
        "reversal_risk": safe_num((regime_v2.get("features") or {}).get("reversal_risk")),
        "structure_alignment": safe_num((regime_v2.get("features") or {}).get("structure_alignment")),
        "volatility_expansion": safe_num((regime_v2.get("features") or {}).get("volatility_expansion")),

        # Interaction (if available)
        "interaction_state": interaction.get("state_group") or interaction.get("interaction_state") or "unknown",
        "alignment_score": safe_num(interaction.get("alignment_score")),
        "conflict_score": safe_num(interaction.get("conflict_score")),
        "confidence_modifier": safe_num(interaction.get("confidence_modifier")),

        # Direction
        "direction": doc.get("direction", "NEUTRAL"),
        "direction_class": audit.get("directionClass", doc.get("direction", "NEUTRAL")),

        # Target
        "target_error": target_error,
        "target_fp": target_fp,
        "outcome_label": label,

        "source_version": doc.get("modelVersion"),
    }
    return row


# Feature definitions for training
NUMERIC_FEATURES = [
    "confidence", "confidence_raw", "confidence_direction", "confidence_target",
    "expected_move_pct", "regime_confidence", "regime_entropy",
    "prob_trend", "prob_range", "prob_pullback", "prob_transition", "prob_breakdown",
    "score_raw", "score_final", "degraded", "rolling_win_rate",
    "ret_1d", "ret_7d", "ret_14d", "volatility", "momentum",
    "trend_strength", "exhaustion", "reversal_risk", "structure_alignment",
    "volatility_expansion",
    "alignment_score", "conflict_score", "confidence_modifier",
]

CATEGORICAL_FEATURES = [
    "asset", "horizon", "regime", "direction", "direction_class",
    "interaction_state",
]
