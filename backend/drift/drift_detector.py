"""
Drift Intelligence — Drift Detector
======================================
Block 6.2

Detects performance degradation using statistical methods:
  - Z-score based detection on rolling windows
  - Trend detection (monotonic decline)
  - Minimum sample threshold to avoid noise

Drift = not just "worse", but "significantly worse in a specific zone"
"""

import math
from collections import defaultdict


# ── Thresholds ──
Z_SCORE_THRESHOLD = -1.5        # z < -1.5 → drift alert
MIN_SAMPLES_FOR_ALERT = 10      # need at least N samples in a window
TREND_DECLINE_WINDOWS = 3       # 3 consecutive declining windows → trend drift
CATASTROPHIC_RATE_ALERT = 0.3   # >30% catastrophic → alert


def detect_drift(metrics: dict) -> dict:
    """
    Analyze drift metrics and detect degradation.

    Args:
        metrics: Output from drift_metrics_engine.compute_drift_metrics()

    Returns:
        {
            "has_drift": bool,
            "drift_zones": [...],  # where drift was detected
            "details": {...},
        }
    """
    if not metrics.get("ok"):
        return {"has_drift": False, "drift_zones": [], "details": {}}

    drift_zones = []

    # ── 1. Time-series drift (rolling window accuracy decline) ──
    time_drift = _detect_time_drift(metrics.get("by_time", {}))
    if time_drift:
        drift_zones.extend(time_drift)

    # ── 2. Confidence bucket anomaly ──
    conf_drift = _detect_confidence_anomaly(metrics.get("by_confidence", {}))
    if conf_drift:
        drift_zones.extend(conf_drift)

    # ── 3. Regime-specific degradation ──
    regime_drift = _detect_regime_drift(metrics.get("by_regime", {}))
    if regime_drift:
        drift_zones.extend(regime_drift)

    # ── 4. Label distribution shift ──
    label_drift = _detect_label_shift(metrics.get("label_trend", {}))
    if label_drift:
        drift_zones.extend(label_drift)

    # ── 5. Global catastrophic rate ──
    global_m = metrics.get("global", {})
    if global_m.get("catastrophic_rate", 0) > CATASTROPHIC_RATE_ALERT:
        drift_zones.append({
            "type": "global_catastrophic",
            "severity": "critical",
            "metric": "catastrophic_rate",
            "value": global_m["catastrophic_rate"],
            "threshold": CATASTROPHIC_RATE_ALERT,
            "message": f"Global catastrophic rate {global_m['catastrophic_rate']:.1%} exceeds threshold",
        })

    return {
        "has_drift": len(drift_zones) > 0,
        "drift_count": len(drift_zones),
        "drift_zones": drift_zones,
    }


def _detect_time_drift(by_time: dict) -> list:
    """Detect drift in rolling time windows using z-score."""
    zones = []
    windows = sorted(by_time.keys())
    if len(windows) < 3:
        return zones

    # Get accuracy series
    accuracies = [by_time[w].get("accuracy", 0) for w in windows]
    counts = [by_time[w].get("n", 0) for w in windows]

    # Compute mean and std of all windows
    valid = [(a, n) for a, n in zip(accuracies, counts) if n >= MIN_SAMPLES_FOR_ALERT]
    if len(valid) < 3:
        return zones

    vals = [v[0] for v in valid]
    mean_acc = sum(vals) / len(vals)
    if len(vals) > 1:
        std_acc = math.sqrt(sum((v - mean_acc) ** 2 for v in vals) / (len(vals) - 1))
    else:
        std_acc = 0

    # Check latest window(s) for z-score drift
    if std_acc > 0.01:  # avoid division by near-zero
        latest_acc = accuracies[-1]
        latest_n = counts[-1]
        if latest_n >= MIN_SAMPLES_FOR_ALERT:
            z = (latest_acc - mean_acc) / std_acc
            if z < Z_SCORE_THRESHOLD:
                zones.append({
                    "type": "time_drift",
                    "severity": "high" if z < -2.0 else "medium",
                    "window": windows[-1],
                    "accuracy": latest_acc,
                    "historical_mean": round(mean_acc, 3),
                    "z_score": round(z, 2),
                    "message": f"Accuracy dropped to {latest_acc:.1%} (mean: {mean_acc:.1%}, z={z:.2f})",
                })

    # Check for monotonic decline trend
    if len(accuracies) >= TREND_DECLINE_WINDOWS:
        recent = accuracies[-TREND_DECLINE_WINDOWS:]
        if all(recent[i] < recent[i - 1] for i in range(1, len(recent))):
            if all(counts[-TREND_DECLINE_WINDOWS + i] >= 5 for i in range(TREND_DECLINE_WINDOWS)):
                zones.append({
                    "type": "trend_drift",
                    "severity": "medium",
                    "windows": windows[-TREND_DECLINE_WINDOWS:],
                    "accuracies": recent,
                    "message": f"Accuracy declining for {TREND_DECLINE_WINDOWS} consecutive windows",
                })

    return zones


def _detect_confidence_anomaly(by_confidence: dict) -> list:
    """Detect when high-confidence predictions are underperforming."""
    zones = []
    high = by_confidence.get("high", {})
    medium = by_confidence.get("medium", {})

    # High confidence should perform better than medium
    if high.get("n", 0) >= MIN_SAMPLES_FOR_ALERT and medium.get("n", 0) >= MIN_SAMPLES_FOR_ALERT:
        if high.get("accuracy", 1) < medium.get("accuracy", 0):
            zones.append({
                "type": "confidence_inversion",
                "severity": "high",
                "high_accuracy": high["accuracy"],
                "medium_accuracy": medium["accuracy"],
                "message": f"High-confidence ({high['accuracy']:.1%}) underperforms medium ({medium['accuracy']:.1%})",
            })

    return zones


def _detect_regime_drift(by_regime: dict) -> list:
    """Detect regimes where accuracy is significantly below average."""
    zones = []
    if not by_regime:
        return zones

    all_accs = [m.get("accuracy", 0) for m in by_regime.values() if m.get("n", 0) >= 5]
    if not all_accs:
        return zones

    mean_acc = sum(all_accs) / len(all_accs)

    for regime, m in by_regime.items():
        if m.get("n", 0) < 5:
            continue
        if m["accuracy"] < mean_acc * 0.5:  # less than 50% of average
            zones.append({
                "type": "regime_drift",
                "severity": "high",
                "regime": regime,
                "accuracy": m["accuracy"],
                "mean_accuracy": round(mean_acc, 3),
                "n": m["n"],
                "message": f"Regime '{regime}' accuracy {m['accuracy']:.1%} far below average {mean_acc:.1%}",
            })

    return zones


def _detect_label_shift(label_trend: dict) -> list:
    """Detect shift in outcome label distribution over time."""
    zones = []
    windows = sorted(label_trend.keys())
    if len(windows) < 3:
        return zones

    # Check if FP rate is increasing over recent windows
    fp_rates = [label_trend[w].get("FP", 0) for w in windows]
    if len(fp_rates) >= 3:
        recent_fp = fp_rates[-3:]
        if all(recent_fp[i] > recent_fp[i - 1] for i in range(1, len(recent_fp))):
            if recent_fp[-1] > 0.4:  # >40% FP in latest
                zones.append({
                    "type": "label_shift",
                    "severity": "medium",
                    "metric": "FP_rate",
                    "recent_values": recent_fp,
                    "message": f"False positive rate increasing: {[round(x, 2) for x in recent_fp]}",
                })

    return zones
