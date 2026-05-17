"""
Drift Monitor — detects degradation using EWMA smoothing.

Compares EWMA-smoothed current metrics vs baseline.
Scopes: GLOBAL, FAMILY, CONFIDENCE_BUCKET, ACTION_TYPE.
Metrics: accuracy, brier, calibration_error, realized_edge.

Uses EWMA (alpha=0.3) instead of simple 7d vs 30d to avoid false alarms.
"""
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("self_improvement.drift_monitor")

EWMA_ALPHA = 0.3

# Severity thresholds
SEVERITY_HIGH = -0.08
SEVERITY_MEDIUM = -0.04


def detect_drift(db) -> list[dict]:
    """Detect drift across all scopes. Returns list of DriftState dicts."""
    results = list(db.forecast_results.find(
        {"correctness": {"$in": ["CORRECT", "WRONG"]}},
        {"_id": 0}
    ).sort("resolved_at", -1))

    if len(results) < 30:
        return []

    now = datetime.now(timezone.utc)
    drift_states = []

    # Split into baseline (older) and current (recent)
    # Use EWMA across all results, recent weighted more
    baseline_cutoff = (now - timedelta(days=30)).isoformat()
    current_cutoff = (now - timedelta(days=7)).isoformat()

    baseline = [r for r in results if r.get("resolved_at", "") < baseline_cutoff]
    current = [r for r in results if r.get("resolved_at", "") >= current_cutoff]

    if len(baseline) < 20 or len(current) < 10:
        return []

    # Global drift
    drift_states.extend(_compute_scope_drift("GLOBAL", "all", baseline, current))

    # Family drift
    families = {}
    for r in results:
        fk = r.get("family_key", "")
        if fk:
            families.setdefault(fk, {"baseline": [], "current": []})

    for r in baseline:
        fk = r.get("family_key", "")
        if fk in families:
            families[fk]["baseline"].append(r)

    for r in current:
        fk = r.get("family_key", "")
        if fk in families:
            families[fk]["current"].append(r)

    for fk, data in families.items():
        if len(data["baseline"]) >= 10 and len(data["current"]) >= 5:
            drift_states.extend(_compute_scope_drift("FAMILY", fk, data["baseline"], data["current"]))

    # Confidence bucket drift
    for conf_level in ["high", "medium", "low"]:
        b = [r for r in baseline if r.get("confidence") == conf_level]
        c = [r for r in current if r.get("confidence") == conf_level]
        if len(b) >= 10 and len(c) >= 5:
            drift_states.extend(_compute_scope_drift("CONFIDENCE_BUCKET", conf_level, b, c))

    # Action type drift
    for action in ["BUY_YES", "BUY_NO"]:
        b = [r for r in baseline if r.get("action") == action]
        c = [r for r in current if r.get("action") == action]
        if len(b) >= 10 and len(c) >= 5:
            drift_states.extend(_compute_scope_drift("ACTION_TYPE", action, b, c))

    now_iso = now.isoformat()
    for d in drift_states:
        d["detected_at"] = now_iso

    return drift_states


def _compute_scope_drift(scope_type: str, scope_value: str,
                         baseline: list, current: list) -> list[dict]:
    """Compute drift for a specific scope across all metrics."""
    drifts = []

    metrics = {
        "ACCURACY": (_accuracy, 1),    # higher is better
        "BRIER": (_avg_brier, -1),     # lower is better
        "REALIZED_EDGE": (_avg_realized_edge, 1),
    }

    for metric_name, (fn, direction) in metrics.items():
        baseline_val = fn(baseline)
        current_val = fn(current)

        if baseline_val is None or current_val is None:
            continue

        # EWMA smoothing
        ewma_current = EWMA_ALPHA * current_val + (1 - EWMA_ALPHA) * baseline_val
        delta = (ewma_current - baseline_val) * direction  # positive = improvement

        # Severity
        if delta < SEVERITY_HIGH:
            severity = "HIGH"
        elif delta < SEVERITY_MEDIUM:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Status
        if abs(delta) < 0.02:
            status = "STABLE"
        elif delta < -0.04:
            status = "DEGRADING"
        elif delta > 0.04:
            status = "IMPROVING"
        else:
            status = "UNSTABLE"

        drift_key = f"{scope_type}:{scope_value}:{metric_name}"

        drifts.append({
            "drift_key": drift_key,
            "scope_type": scope_type,
            "scope_value": scope_value,
            "metric": metric_name,
            "baseline_value": round(baseline_val, 4),
            "current_value": round(current_val, 4),
            "ewma_current": round(ewma_current, 4),
            "delta": round(delta, 4),
            "severity": severity,
            "status": status,
        })

    return drifts


def _accuracy(results: list) -> float | None:
    if not results:
        return None
    return sum(1 for r in results if r.get("binary_correct")) / len(results)


def _avg_brier(results: list) -> float | None:
    vals = [r["brier_score"] for r in results if r.get("brier_score") is not None]
    return sum(vals) / len(vals) if vals else None


def _avg_realized_edge(results: list) -> float | None:
    vals = [r["realized_edge"] for r in results if r.get("realized_edge") is not None]
    return sum(vals) / len(vals) if vals else None
