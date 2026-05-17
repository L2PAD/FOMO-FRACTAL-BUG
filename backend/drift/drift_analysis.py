"""
Drift Intelligence — Root Cause + Scoring + Alerts + Recommendations
=====================================================================
Block 6.3 / 6.4 / 6.5 / 6.7

Root Cause Engine: WHY drift happened
Drift Scoring: unified degradation score
Alerts: typed drift alerts
Recommendations: actionable advice based on drift zones
"""


# ══════════════════════════════════════════════════════════════
# Block 6.3 — Root Cause Engine
# ══════════════════════════════════════════════════════════════

def analyze_root_causes(drift_zones: list, metrics: dict) -> list:
    """
    For each drift zone, determine the most likely root cause.

    Returns list of root cause objects with explanation.
    """
    causes = []

    for zone in drift_zones:
        ztype = zone.get("type", "")

        if ztype == "time_drift":
            cause = _diagnose_time_drift(zone, metrics)
        elif ztype == "trend_drift":
            cause = _diagnose_trend_drift(zone, metrics)
        elif ztype == "confidence_inversion":
            cause = _diagnose_confidence_inversion(zone, metrics)
        elif ztype == "regime_drift":
            cause = _diagnose_regime_drift(zone, metrics)
        elif ztype == "label_shift":
            cause = _diagnose_label_shift(zone, metrics)
        elif ztype == "global_catastrophic":
            cause = _diagnose_catastrophic(zone, metrics)
        else:
            cause = {
                "zone": ztype,
                "cause": "unknown",
                "explanation": "Unable to determine root cause for this drift type",
                "confidence": "low",
            }

        causes.append(cause)

    return causes


def _diagnose_time_drift(zone, metrics):
    """Time-based accuracy drop root cause."""
    global_m = metrics.get("global", {})
    by_conf = metrics.get("by_confidence", {})

    # Check if it's a confidence calibration issue
    high_conf = by_conf.get("high", {})
    if high_conf.get("accuracy", 1) < 0.3:
        return {
            "zone": "time_drift",
            "cause": "confidence_miscalibration",
            "explanation": "High-confidence predictions are consistently wrong — confidence model needs recalibration",
            "confidence": "high",
        }

    # Check if catastrophic rate is elevated
    if global_m.get("catastrophic_rate", 0) > 0.3:
        return {
            "zone": "time_drift",
            "cause": "market_regime_shift",
            "explanation": "High catastrophic rate suggests the market entered a new regime not covered by the model",
            "confidence": "medium",
        }

    return {
        "zone": "time_drift",
        "cause": "general_accuracy_decline",
        "explanation": f"Accuracy dropped to {zone.get('accuracy', 0):.1%} from historical mean {zone.get('historical_mean', 0):.1%}. May indicate model staleness or market evolution.",
        "confidence": "medium",
    }


def _diagnose_trend_drift(zone, metrics):
    return {
        "zone": "trend_drift",
        "cause": "systematic_degradation",
        "explanation": "Accuracy has been declining across consecutive time windows — model may be losing predictive power",
        "confidence": "high",
    }


def _diagnose_confidence_inversion(zone, metrics):
    return {
        "zone": "confidence_inversion",
        "cause": "confidence_miscalibration",
        "explanation": f"High-confidence predictions ({zone.get('high_accuracy', 0):.1%}) perform worse than medium ({zone.get('medium_accuracy', 0):.1%}) — confidence scores do not reflect actual reliability",
        "confidence": "high",
    }


def _diagnose_regime_drift(zone, metrics):
    return {
        "zone": "regime_drift",
        "cause": "regime_specific_failure",
        "explanation": f"Performance in '{zone.get('regime', 'unknown')}' regime ({zone.get('accuracy', 0):.1%}) is far below average — model lacks edge in this market condition",
        "confidence": "high",
    }


def _diagnose_label_shift(zone, metrics):
    return {
        "zone": "label_shift",
        "cause": "increasing_false_positives",
        "explanation": "False positive rate is trending up — model is becoming overconfident in wrong direction calls",
        "confidence": "medium",
    }


def _diagnose_catastrophic(zone, metrics):
    return {
        "zone": "global_catastrophic",
        "cause": "tail_risk_exposure",
        "explanation": f"Catastrophic rate {zone.get('value', 0):.1%} is dangerously high — system is not protecting against large adverse moves",
        "confidence": "high",
    }


# ══════════════════════════════════════════════════════════════
# Block 6.4 — Drift Scoring
# ══════════════════════════════════════════════════════════════

def compute_drift_score(metrics: dict, drift_result: dict) -> dict:
    """
    Compute unified drift score (0..1).

    Formula:
        drift_score = accuracy_drop * 0.4 + pnl_drop * 0.3 + catastrophic * 0.3
    """
    global_m = metrics.get("global", {})
    by_time = metrics.get("by_time", {})

    # Accuracy component
    accuracy = global_m.get("accuracy", 0.5)
    # Baseline: 50% (random) → 0.0, 0% → 1.0
    accuracy_drop = max(0, (0.5 - accuracy) / 0.5)

    # PnL component: negative PnL = bad
    pnl = global_m.get("pnl", 0)
    pnl_drop = min(1.0, max(0, -pnl / 100))  # -100 PnL → score 1.0

    # Catastrophic component
    catastrophic = global_m.get("catastrophic_rate", 0)
    cat_score = min(1.0, catastrophic / 0.5)  # 50% catastrophic → score 1.0

    # Recent trend bonus: if recent windows are worse, add penalty
    trend_penalty = 0
    if by_time:
        windows = sorted(by_time.keys())
        if len(windows) >= 2:
            latest = by_time[windows[-1]]
            prev = by_time[windows[-2]]
            if latest.get("accuracy", 0) < prev.get("accuracy", 0) - 0.1:
                trend_penalty = 0.1

    score = (
        accuracy_drop * 0.4
        + pnl_drop * 0.3
        + cat_score * 0.3
        + trend_penalty
    )
    score = min(round(score, 3), 1.0)

    # Level
    if score > 0.7:
        level = "critical"
    elif score > 0.4:
        level = "high"
    elif score > 0.2:
        level = "medium"
    else:
        level = "low"

    return {
        "score": score,
        "level": level,
        "components": {
            "accuracy_drop": round(accuracy_drop, 3),
            "pnl_drop": round(pnl_drop, 3),
            "catastrophic": round(cat_score, 3),
            "trend_penalty": round(trend_penalty, 3),
        },
    }


# ══════════════════════════════════════════════════════════════
# Block 6.5 — Drift Alerts
# ══════════════════════════════════════════════════════════════

def generate_alerts(drift_zones: list, root_causes: list, drift_score: dict) -> list:
    """Generate typed drift alerts from analysis results."""
    alerts = []

    for zone, cause in zip(drift_zones, root_causes):
        severity = zone.get("severity", "medium")
        alert = {
            "type": _map_alert_type(zone.get("type", "")),
            "severity": severity,
            "cause": cause.get("cause", "unknown"),
            "message": zone.get("message", ""),
            "explanation": cause.get("explanation", ""),
            "confidence": cause.get("confidence", "low"),
        }
        alerts.append(alert)

    # Add score-based alert if critical
    if drift_score.get("level") in ("critical", "high"):
        alerts.insert(0, {
            "type": "system_health",
            "severity": "critical" if drift_score["level"] == "critical" else "high",
            "cause": "overall_degradation",
            "message": f"System drift score: {drift_score['score']:.2f} ({drift_score['level']})",
            "explanation": "Overall system health is degraded across multiple dimensions",
            "confidence": "high",
        })

    return alerts


def _map_alert_type(zone_type: str) -> str:
    mapping = {
        "time_drift": "accuracy_drift",
        "trend_drift": "accuracy_drift",
        "confidence_inversion": "calibration_drift",
        "regime_drift": "regime_drift",
        "label_shift": "execution_drift",
        "global_catastrophic": "risk_drift",
    }
    return mapping.get(zone_type, "general_drift")


# ══════════════════════════════════════════════════════════════
# Block 6.7 — Recommendation Engine
# ══════════════════════════════════════════════════════════════

def generate_recommendations(
    drift_zones: list,
    root_causes: list,
    drift_score: dict,
    metrics: dict,
) -> list:
    """Generate actionable recommendations based on drift analysis."""
    recs = []
    seen_types = set()

    for zone, cause in zip(drift_zones, root_causes):
        cause_type = cause.get("cause", "")
        if cause_type in seen_types:
            continue
        seen_types.add(cause_type)

        if cause_type == "confidence_miscalibration":
            recs.append({
                "priority": "high",
                "action": "recalibrate_confidence",
                "description": "Confidence scores do not reflect actual prediction quality. Recalibrate the confidence model or increase uncertainty damping.",
                "implementation": "Increase uncertainty multiplier in proto overlay; lower confidence output cap",
            })

        elif cause_type == "market_regime_shift":
            recs.append({
                "priority": "high",
                "action": "expand_regime_coverage",
                "description": "Market entered conditions not well-covered by the model. Consider adding new regime types or widening training data.",
                "implementation": "Review regime classifier thresholds; add transition sub-types",
            })

        elif cause_type == "systematic_degradation":
            recs.append({
                "priority": "critical",
                "action": "retrain_model",
                "description": "Accuracy declining over consecutive windows — model is losing predictive edge.",
                "implementation": "Trigger model retraining with recent data; consider walk-forward validation",
            })

        elif cause_type == "regime_specific_failure":
            regime = zone.get("regime", "unknown")
            recs.append({
                "priority": "high",
                "action": f"fix_{regime}_handling",
                "description": f"Performance in '{regime}' regime is critically low. This regime needs special handling.",
                "implementation": f"Add execution guards for '{regime}' regime; reduce position sizing in this regime",
            })

        elif cause_type == "increasing_false_positives":
            recs.append({
                "priority": "medium",
                "action": "reduce_false_positives",
                "description": "False positive rate is growing — model is overconfident in wrong calls.",
                "implementation": "Tighten direction confidence threshold; increase neutral zone",
            })

        elif cause_type == "tail_risk_exposure":
            recs.append({
                "priority": "critical",
                "action": "tighten_risk_controls",
                "description": "Catastrophic rate is dangerously high — immediate risk reduction needed.",
                "implementation": "Lower proto overlay thresholds; increase catastrophic guard multiplier; reduce max position size",
            })

        elif cause_type == "general_accuracy_decline":
            recs.append({
                "priority": "medium",
                "action": "investigate_data_quality",
                "description": "General accuracy decline without clear single cause.",
                "implementation": "Check data pipeline integrity; verify feature computation; compare against baseline",
            })

    # If no specific recs, add general
    if not recs and drift_score.get("score", 0) > 0.2:
        recs.append({
            "priority": "low",
            "action": "monitor_closely",
            "description": "Drift detected but at manageable level. Continue monitoring.",
            "implementation": "Increase monitoring frequency; review next drift report for progression",
        })

    return recs
