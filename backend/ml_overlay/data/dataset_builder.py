"""
Dataset Builder — constructs training data with strict anti-leakage.

For each date t:
  X(t) = features computed from [t-L ... t]  (past only)
  y(t) = r_real(t, t+h) - r_rule(t, t+h)    (residual)

r_real = close(t+h) / close(t) - 1
r_rule = computed from the same rule engine formula
"""

import numpy as np
import pandas as pd
import hashlib
from ml_overlay.features.compute_features import compute_features
from ml_overlay.config import HORIZONS


def _compute_rule_return(close_t: float, features_at_t: dict, horizon_days: int) -> float:
    """
    Replicate the rule engine formula to get rule_return.
    Must match forecast/generator.py exactly.
    """
    ret_1d = features_at_t.get("ret_1d", 0) or 0
    ret_7d = features_at_t.get("ret_7d", 0) or 0
    ret_14d = features_at_t.get("ret_14d", 0) or 0

    momentum = ret_1d * 0.5 + ret_7d * 0.3 + ret_14d * 0.2

    # Rule formula: target = price * (1 + momentum * sqrt(horizon_days) * 0.8)
    rule_return = momentum * (horizon_days ** 0.5) * 0.8
    return rule_return


def build_dataset(ohlcv: pd.DataFrame, horizon_key: str = "7D") -> pd.DataFrame:
    """
    Build training dataset for a given horizon.

    Returns DataFrame with:
      - Feature columns (X)
      - 'r_real': actual return over horizon
      - 'r_rule': rule engine return
      - 'y': residual (r_real - r_rule) — this is the ML target
      - 'close': close price at t
    """
    cfg = HORIZONS[horizon_key]
    h = cfg["days"]

    # Compute features (strictly from past)
    features = compute_features(ohlcv)

    # Align with close prices
    close = ohlcv["close"].reindex(features.index)

    # Compute forward return (this uses future data — ONLY for labels)
    future_close = ohlcv["close"].shift(-h).reindex(features.index)
    r_real = (future_close / close) - 1

    # Compute rule return for each row
    r_rule = pd.Series(index=features.index, dtype=float)
    for t in features.index:
        feat_dict = features.loc[t].to_dict()
        r_rule.loc[t] = _compute_rule_return(close.loc[t], feat_dict, h)

    # Residual target
    y = r_real - r_rule

    # Combine
    dataset = features.copy()
    dataset["r_real"] = r_real
    dataset["r_rule"] = r_rule
    dataset["y"] = y
    dataset["close"] = close

    # Drop rows where future return is not yet known
    dataset = dataset.dropna(subset=["r_real", "y"])

    return dataset
