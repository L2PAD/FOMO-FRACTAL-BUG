"""
Feature Drift — PSI and KS statistics
"""

import numpy as np
from drift.config import PSI_BINS


def compute_psi(baseline: np.ndarray, production: np.ndarray, bins: int = PSI_BINS) -> float:
    """
    Population Stability Index between baseline and production distributions.
    PSI < 0.10 → OK, 0.10-0.20 → Watch, > 0.20 → Drift
    """
    if len(baseline) < 20 or len(production) < 20:
        return 0.0

    # Create bins from baseline
    edges = np.percentile(baseline, np.linspace(0, 100, bins + 1))
    edges[0] = -np.inf
    edges[-1] = np.inf
    # Remove duplicate edges
    edges = np.unique(edges)
    if len(edges) < 3:
        return 0.0

    q = np.histogram(baseline, bins=edges)[0] / len(baseline)
    p = np.histogram(production, bins=edges)[0] / len(production)

    # Avoid division by zero
    eps = 1e-6
    q = np.clip(q, eps, None)
    p = np.clip(p, eps, None)

    psi = np.sum((p - q) * np.log(p / q))
    return float(np.clip(psi, 0, 5))


def compute_ks(baseline: np.ndarray, production: np.ndarray) -> float:
    """
    Kolmogorov-Smirnov statistic between two distributions.
    KS > 0.12 → Watch, > 0.20 → Drift
    """
    if len(baseline) < 20 or len(production) < 20:
        return 0.0

    from scipy.stats import ks_2samp
    stat, _ = ks_2samp(baseline, production)
    return float(stat)


def compute_feature_drift(
    baseline_features: dict[str, np.ndarray],
    production_features: dict[str, np.ndarray],
) -> dict:
    """
    Compute PSI and KS for each feature.
    Returns per-feature drift metrics and aggregate PSI.
    """
    results = {}
    psi_values = []

    for feat_name in baseline_features:
        base = baseline_features[feat_name]
        prod = production_features.get(feat_name)
        if prod is None or len(prod) < 10:
            continue

        psi = compute_psi(base, prod)
        ks = compute_ks(base, prod)
        psi_values.append(psi)

        status = "OK"
        if psi >= 0.20 or ks >= 0.20:
            status = "DRIFT"
        elif psi >= 0.10 or ks >= 0.12:
            status = "WATCH"

        results[feat_name] = {
            "psi": round(psi, 4),
            "ks": round(ks, 4),
            "status": status,
        }

    avg_psi = float(np.mean(psi_values)) if psi_values else 0.0

    return {
        "features": results,
        "avgPsi": round(avg_psi, 4),
        "maxPsi": round(float(max(psi_values)) if psi_values else 0.0, 4),
        "driftedCount": sum(1 for f in results.values() if f["status"] == "DRIFT"),
        "watchCount": sum(1 for f in results.values() if f["status"] == "WATCH"),
    }
