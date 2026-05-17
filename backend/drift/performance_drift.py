"""
Performance Drift — MAE growth, DirHit drop, FlipRate spike
"""

import numpy as np


def compute_performance_drift(
    baseline_metrics: dict,
    production_metrics: dict,
) -> dict:
    """
    Compare production performance vs baseline.

    baseline_metrics / production_metrics should have:
      mae, dir_hit, flip_rate (all as floats)

    Returns normalized drift components (0-1 each).
    """
    b_mae = baseline_metrics.get("mae", 0.05)
    p_mae = production_metrics.get("mae", 0.05)
    b_dir = baseline_metrics.get("dir_hit", 0.5)
    p_dir = production_metrics.get("dir_hit", 0.5)
    b_flip = baseline_metrics.get("flip_rate", 0.25)
    p_flip = production_metrics.get("flip_rate", 0.25)

    # MAE growth (0-1): how much worse is prod MAE vs baseline
    mae_growth = max(0, (p_mae - b_mae) / (b_mae + 1e-8))
    mae_growth_norm = float(np.clip(mae_growth / 0.5, 0, 1))  # 50% growth = 1.0

    # DirHit drop (0-1): how much worse is prod direction accuracy
    dir_drop = max(0, b_dir - p_dir)
    dir_drop_norm = float(np.clip(dir_drop / 0.10, 0, 1))  # 10pp drop = 1.0

    # FlipRate spike (0-1): how much more unstable
    flip_spike = max(0, p_flip - b_flip)
    flip_spike_norm = float(np.clip(flip_spike / 0.10, 0, 1))  # 10pp spike = 1.0

    return {
        "mae_growth": round(mae_growth_norm, 4),
        "dir_hit_drop": round(dir_drop_norm, 4),
        "flip_spike": round(flip_spike_norm, 4),
        "raw": {
            "mae_baseline": round(b_mae, 6),
            "mae_prod": round(p_mae, 6),
            "dir_baseline": round(b_dir, 4),
            "dir_prod": round(p_dir, 4),
            "flip_baseline": round(b_flip, 4),
            "flip_prod": round(p_flip, 4),
        },
    }
