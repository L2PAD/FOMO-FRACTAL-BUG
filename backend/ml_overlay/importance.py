"""
Permutation Importance — compute stable feature importance across walk-forward folds.
"""

import numpy as np
import pandas as pd
from ml_overlay.config import FEATURES, WALK_FORWARD_WINDOWS, HORIZONS
from ml_overlay.model.train import train_model, predict


def permutation_importance_fold(
    dataset: pd.DataFrame,
    window: dict,
    horizon_key: str,
    n_repeats: int = 5,
) -> dict:
    """
    Compute permutation importance for one walk-forward fold.
    """
    train_end = window["train_end"]
    test_start = window["test_start"]
    test_end = window["test_end"]

    result = train_model(dataset, train_end, horizon_key)
    model = result["model"]

    test_mask = (dataset.index >= pd.Timestamp(test_start)) & (dataset.index <= pd.Timestamp(test_end))
    test = dataset[test_mask]
    if len(test) < 10:
        return {}

    X_test = test[FEATURES].values
    y_test = test["y"].values

    # Baseline MAE
    y_hat = predict(model, X_test)
    base_mae = np.mean(np.abs(y_hat - y_test))

    importances = {}
    rng = np.random.RandomState(42)

    for i, feat in enumerate(FEATURES):
        deltas = []
        for _ in range(n_repeats):
            X_perm = X_test.copy()
            X_perm[:, i] = rng.permutation(X_perm[:, i])
            y_hat_perm = predict(model, X_perm)
            perm_mae = np.mean(np.abs(y_hat_perm - y_test))
            deltas.append(perm_mae - base_mae)

        importances[feat] = {
            "mean": round(float(np.mean(deltas)), 6),
            "std": round(float(np.std(deltas)), 6),
        }

    return importances


def compute_stable_importance(dataset: pd.DataFrame, horizon_key: str) -> dict:
    """
    Compute permutation importance across all walk-forward folds.
    Returns features ranked by stability and average importance.
    """
    fold_importances = []

    for window in WALK_FORWARD_WINDOWS:
        try:
            imp = permutation_importance_fold(dataset, window, horizon_key)
            if imp:
                fold_importances.append(imp)
        except Exception:
            continue

    if not fold_importances:
        return {"features": [], "warnings": ["No folds computed"]}

    # Aggregate across folds
    features = []
    for feat in FEATURES:
        means = [f[feat]["mean"] for f in fold_importances if feat in f]
        if not means:
            continue

        avg_importance = np.mean(means)
        stability = 1.0 - (np.std(means) / (np.mean(np.abs(means)) + 1e-8))

        features.append({
            "name": feat,
            "avgImportance": round(float(avg_importance), 6),
            "stability": round(float(np.clip(stability, 0, 1)), 3),
            "foldValues": [round(float(m), 6) for m in means],
            "isNoise": avg_importance < 0.0001 and stability < 0.3,
        })

    # Sort by avg importance (descending)
    features.sort(key=lambda x: -x["avgImportance"])

    # Warnings
    warnings = []
    noise_feats = [f["name"] for f in features if f["isNoise"]]
    if noise_feats:
        warnings.append(f"Noise features (consider pruning): {noise_feats}")

    top3 = [f["name"] for f in features[:3]]
    suspect = [f for f in top3 if "future" in f.lower() or "target" in f.lower()]
    if suspect:
        warnings.append(f"LEAKAGE SUSPECT in top features: {suspect}")

    return {
        "horizon": horizon_key,
        "features": features,
        "warnings": warnings,
        "folds": len(fold_importances),
    }
