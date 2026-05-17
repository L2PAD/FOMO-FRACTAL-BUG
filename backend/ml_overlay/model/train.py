"""
Model Training — LightGBM residual overlay
"""

import lightgbm as lgb
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from ml_overlay.config import LGBM_PARAMS, FEATURES, MIN_TRAIN_ROWS


def train_model(
    dataset: pd.DataFrame,
    train_end: str,
    horizon_key: str,
) -> dict:
    """
    Train a LightGBM model on data up to train_end.

    Returns:
      {
        "model": trained LGBMRegressor,
        "horizon": horizon_key,
        "trainEnd": train_end,
        "trainRows": int,
        "featureImportance": dict,
        "trainedAt": ISO string,
      }
    """
    # Split strictly by time
    mask = dataset.index <= pd.Timestamp(train_end)
    train = dataset[mask].copy()

    if len(train) < MIN_TRAIN_ROWS:
        raise ValueError(f"Insufficient training data: {len(train)} rows (need {MIN_TRAIN_ROWS})")

    X_train = train[FEATURES].values
    y_train = train["y"].values

    model = lgb.LGBMRegressor(**LGBM_PARAMS)
    model.fit(X_train, y_train)

    # Feature importance
    importance = dict(zip(FEATURES, model.feature_importances_.tolist()))

    return {
        "model": model,
        "horizon": horizon_key,
        "trainEnd": train_end,
        "trainRows": len(train),
        "featureImportance": importance,
        "trainedAt": datetime.now(timezone.utc).isoformat(),
    }


def predict(model, features_array: np.ndarray) -> np.ndarray:
    """Run inference. Returns array of residual predictions."""
    return model.predict(features_array)
