"""
Walk-Forward Validation — no random splits, strict temporal ordering.
"""

import numpy as np
import pandas as pd
from ml_overlay.config import WALK_FORWARD_WINDOWS, FEATURES, HORIZONS
from ml_overlay.model.train import train_model, predict


def evaluate_fold(dataset: pd.DataFrame, window: dict, horizon_key: str) -> dict:
    """
    Train on data up to train_end, test on [test_start, test_end].
    Returns metrics dict.
    """
    train_end = window["train_end"]
    test_start = window["test_start"]
    test_end = window["test_end"]
    cap = HORIZONS[horizon_key]["cap"]

    # Train
    result = train_model(dataset, train_end, horizon_key)
    model = result["model"]

    # Test split
    test_mask = (dataset.index >= pd.Timestamp(test_start)) & (dataset.index <= pd.Timestamp(test_end))
    test = dataset[test_mask].copy()

    if len(test) < 10:
        return {"error": f"Insufficient test data: {len(test)} rows", "window": window}

    X_test = test[FEATURES].values
    y_test = test["y"].values
    r_rule = test["r_rule"].values
    r_real = test["r_real"].values

    # Predict residual
    y_hat = predict(model, X_test)
    y_hat_clipped = np.clip(y_hat, -cap, cap)

    # Final return
    r_final = r_rule + y_hat_clipped

    # Metrics
    # 1. MAE of residual prediction
    mae_residual = np.mean(np.abs(y_hat_clipped - y_test))
    mae_baseline = np.mean(np.abs(y_test))  # baseline = no correction (y_hat=0)

    # 2. Direction accuracy
    dir_rule = np.sign(r_rule)
    dir_final = np.sign(r_final)
    dir_real = np.sign(r_real)

    dir_hit_rule = np.mean(dir_rule == dir_real)
    dir_hit_final = np.mean(dir_final == dir_real)

    # 3. Error improvement
    err_rule = np.mean(np.abs(r_real - r_rule))
    err_final = np.mean(np.abs(r_real - r_final))
    improvement = (err_rule - err_final) / err_rule * 100 if err_rule > 0 else 0

    # 4. Flip rate
    flips = np.sum(np.diff(np.sign(r_final)) != 0)
    flip_rate = flips / max(1, len(r_final) - 1) * 100

    # 5. Sharpe proxy
    daily_pnl = r_final * np.sign(r_final)  # simplified
    sharpe = np.mean(daily_pnl) / (np.std(daily_pnl) + 1e-8) * np.sqrt(252)

    return {
        "window": window,
        "horizon": horizon_key,
        "trainRows": result["trainRows"],
        "testRows": len(test),
        "mae_baseline": round(float(mae_baseline), 6),
        "mae_residual": round(float(mae_residual), 6),
        "mae_improvement_pct": round(float((mae_baseline - mae_residual) / mae_baseline * 100) if mae_baseline > 0 else 0, 2),
        "dir_hit_rule": round(float(dir_hit_rule) * 100, 1),
        "dir_hit_final": round(float(dir_hit_final) * 100, 1),
        "dir_improvement": round(float(dir_hit_final - dir_hit_rule) * 100, 1),
        "err_rule": round(float(err_rule), 6),
        "err_final": round(float(err_final), 6),
        "improvement_pct": round(float(improvement), 2),
        "flip_rate": round(float(flip_rate), 1),
        "sharpe": round(float(sharpe), 3),
    }


def run_walk_forward(dataset: pd.DataFrame, horizon_key: str) -> list[dict]:
    """Run all walk-forward windows and return metrics for each."""
    results = []
    for window in WALK_FORWARD_WINDOWS:
        try:
            metrics = evaluate_fold(dataset, window, horizon_key)
            results.append(metrics)
        except Exception as e:
            results.append({"window": window, "error": str(e)})
    return results
