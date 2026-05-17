"""
Calibration Drift — Brier score and ECE
"""

import numpy as np


def compute_brier(confidences: np.ndarray, outcomes: np.ndarray) -> float:
    """Brier score: mean (confidence - outcome)^2"""
    if len(confidences) < 5:
        return 0.0
    return float(np.mean((confidences - outcomes) ** 2))


def compute_ece(confidences: np.ndarray, outcomes: np.ndarray, n_bins: int = 5) -> float:
    """Expected Calibration Error."""
    if len(confidences) < 10:
        return 0.0

    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        mask = (confidences >= bin_edges[i]) & (confidences < bin_edges[i + 1])
        if mask.sum() == 0:
            continue
        avg_conf = confidences[mask].mean()
        avg_hit = outcomes[mask].mean()
        ece += mask.sum() / len(confidences) * abs(avg_hit - avg_conf)

    return float(ece)


def compute_calibration_drift(
    confidences: np.ndarray,
    dir_hits: np.ndarray,
) -> dict:
    """
    Compute calibration metrics.
    confidences: model confidence (0-1)
    dir_hits: 1 if direction was correct, 0 otherwise
    """
    brier = compute_brier(confidences, dir_hits)
    ece = compute_ece(confidences, dir_hits)

    status = "OK"
    if ece >= 0.12:
        status = "DRIFT"
    elif ece >= 0.08:
        status = "WATCH"

    return {
        "brier": round(brier, 4),
        "ece": round(ece, 4),
        "status": status,
        "n": int(len(confidences)),
    }
