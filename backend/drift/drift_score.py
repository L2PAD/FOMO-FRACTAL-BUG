"""
Drift Score — composite score + ML Weight computation.

driftScore = 0.4*PSI + 0.3*DirHit_drop + 0.2*MAE_growth + 0.1*FlipRate_spike
mlWeight = exp(-alpha * driftScore)

Regime-aware: compares metrics vs regime-specific baseline (z-score).
"""

import math
from drift.config import DRIFT_WEIGHTS, ALPHA, ECE_ALPHA


def compute_drift_score(
    feature_drift: dict,
    performance_drift: dict,
    calibration_drift: dict | None = None,
    regime_baseline: dict | None = None,
) -> dict:
    """
    Compute composite drift score and ML weight.
    If regime_baseline provided, uses z-score comparison instead of global.
    """
    # Normalize feature PSI to 0-1
    avg_psi = feature_drift.get("avgPsi", 0)
    psi_norm = min(1.0, avg_psi / 0.25)

    # Performance components
    dir_drop = performance_drift.get("dir_hit_drop", 0)
    mae_growth = performance_drift.get("mae_growth", 0)
    flip_spike = performance_drift.get("flip_spike", 0)

    # Regime-aware adjustment: reduce drift if within regime norms
    regime_adj = None
    if regime_baseline:
        regime_adj = _regime_adjustment(performance_drift, regime_baseline)
        # Blend: use regime-adjusted values
        mae_growth = regime_adj.get("mae_growth_adj", mae_growth)
        dir_drop = regime_adj.get("dir_hit_drop_adj", dir_drop)
        flip_spike = regime_adj.get("flip_spike_adj", flip_spike)

    # Weighted composite
    drift_score = (
        DRIFT_WEIGHTS["psi"] * psi_norm +
        DRIFT_WEIGHTS["dir_hit_drop"] * dir_drop +
        DRIFT_WEIGHTS["mae_growth"] * mae_growth +
        DRIFT_WEIGHTS["flip_spike"] * flip_spike
    )
    drift_score = min(1.0, max(0.0, drift_score))

    # ML Weight via exponential decay
    ml_weight = math.exp(-ALPHA * drift_score)

    # Calibration gate: additional penalty if ECE is high
    ece_penalty = 1.0
    calib_status = "OK"
    calib_ece = 0.0
    if calibration_drift:
        calib_ece = calibration_drift.get("ece", 0)
        calib_status = calibration_drift.get("status", "OK")
        if calib_ece > 0:
            ece_penalty = math.exp(-ECE_ALPHA * calib_ece)
            ml_weight *= ece_penalty
    ml_weight = max(0.0, min(1.0, ml_weight))

    # Status
    if drift_score >= 0.5:
        status = "DRIFT"
    elif drift_score >= 0.25:
        status = "WATCH"
    else:
        status = "OK"

    # Top drivers
    drivers = []
    components = [
        ("Feature PSI", psi_norm, DRIFT_WEIGHTS["psi"]),
        ("DirHit drop", dir_drop, DRIFT_WEIGHTS["dir_hit_drop"]),
        ("MAE growth", mae_growth, DRIFT_WEIGHTS["mae_growth"]),
        ("FlipRate spike", flip_spike, DRIFT_WEIGHTS["flip_spike"]),
    ]
    for name, val, weight in sorted(components, key=lambda x: -x[1] * x[2]):
        if val > 0.05:
            drivers.append({
                "name": name,
                "value": round(val, 3),
                "contribution": round(val * weight, 3),
            })

    result = {
        "driftScore": round(drift_score, 4),
        "mlWeight": round(ml_weight, 4),
        "status": status,
        "components": {
            "psi": round(psi_norm, 4),
            "dirHitDrop": round(dir_drop, 4),
            "maeGrowth": round(mae_growth, 4),
            "flipSpike": round(flip_spike, 4),
        },
        "drivers": drivers[:3],
        "calibration": {
            "ece": round(calib_ece, 4),
            "ecePenalty": round(ece_penalty, 4),
            "status": calib_status,
        },
    }

    if regime_adj:
        result["regimeAdjusted"] = True
        result["regimeContext"] = regime_adj.get("context")

    return result


def _regime_adjustment(perf_drift: dict, baseline: dict) -> dict:
    """
    Compare current performance drift against regime-specific baseline.
    Returns adjusted values: if within 1.5 std of regime norm, reduce drift.
    """
    mae_growth_raw = perf_drift.get("mae_growth", 0)
    dir_drop_raw = perf_drift.get("dir_hit_drop", 0)
    flip_raw = perf_drift.get("flip_spike", 0)

    b_mae_std = baseline.get("mae_std", 0.01)
    b_flip_mean = baseline.get("flip_mean", 0.2)
    b_flip_std = baseline.get("flip_std", 0.05)

    # Z-score: how far is current from regime norm
    # mae_growth is already normalized 0-1, so we compare the raw MAE
    # against regime baseline. If current MAE is within regime norms, reduce drift.
    context = {}

    # MAE: if current MAE is within 1.5 std of regime mean, dampen mae_growth
    mae_z = abs(mae_growth_raw) if b_mae_std < 0.001 else mae_growth_raw
    if b_mae_std > 0.001:
        # High MAE is normal for this regime -> reduce penalty
        damping = max(0.0, min(1.0, 1.0 - (1.5 - abs(mae_z)) * 0.3))
        mae_adj = mae_growth_raw * damping
        context["mae"] = {"raw": round(mae_growth_raw, 4), "adj": round(mae_adj, 4), "damping": round(damping, 2)}
    else:
        mae_adj = mae_growth_raw
        context["mae"] = {"raw": round(mae_growth_raw, 4), "adj": round(mae_adj, 4), "damping": 1.0}

    # Flip: if flip rate is normal for this regime, reduce penalty
    flip_adj = flip_raw
    if b_flip_std > 0.001 and b_flip_mean > 0:
        if flip_raw < b_flip_mean + 1.5 * b_flip_std:
            flip_adj = flip_raw * 0.5  # within regime norms
            context["flip"] = "within_regime_norm"
        else:
            context["flip"] = "exceeds_regime_norm"
    else:
        context["flip"] = "no_regime_data"

    return {
        "mae_growth_adj": max(0, mae_adj),
        "dir_hit_drop_adj": dir_drop_raw,  # direction drop stays global
        "flip_spike_adj": max(0, flip_adj),
        "context": context,
    }

