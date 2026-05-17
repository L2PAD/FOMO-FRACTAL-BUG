"""
Feature computation — all features computed strictly from past data.
NO lookahead. Every feature at time t uses only data [t-L, t].
"""

import numpy as np
import pandas as pd


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute feature matrix from OHLCV DataFrame.
    Input: df with columns [open, high, low, close, volume], DatetimeIndex
    Output: DataFrame with feature columns, same index (rows with NaN dropped)
    """
    c = df["close"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    v = df["volume"].values.astype(float)
    n = len(c)

    feat = pd.DataFrame(index=df.index)

    # Returns
    feat["ret_1d"] = pd.Series(c, index=df.index).pct_change(1)
    feat["ret_3d"] = pd.Series(c, index=df.index).pct_change(3)
    feat["ret_7d"] = pd.Series(c, index=df.index).pct_change(7)
    feat["ret_14d"] = pd.Series(c, index=df.index).pct_change(14)

    # Volatility (std of daily returns)
    daily_ret = pd.Series(c, index=df.index).pct_change(1)
    feat["vol_7d"] = daily_ret.rolling(7).std()
    feat["vol_30d"] = daily_ret.rolling(30).std()

    # RSI 14
    delta = pd.Series(c, index=df.index).diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    feat["rsi_14"] = 100 - (100 / (1 + rs))

    # MA slopes (normalized)
    ma20 = pd.Series(c, index=df.index).rolling(20).mean()
    ma50 = pd.Series(c, index=df.index).rolling(50).mean()
    feat["ma20_slope"] = ma20.pct_change(5)  # 5-day slope of MA20
    feat["ma50_slope"] = ma50.pct_change(5)

    # ATR 14
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    feat["atr_14"] = pd.Series(tr, index=df.index).rolling(14).mean() / pd.Series(c, index=df.index)

    # Volume z-score (rolling 30d)
    vol_series = pd.Series(v, index=df.index)
    vol_mean = vol_series.rolling(30).mean()
    vol_std = vol_series.rolling(30).std()
    feat["volume_z"] = (vol_series - vol_mean) / vol_std.replace(0, np.nan)

    # Drop NaN rows (from rolling windows)
    feat = feat.dropna()

    # Winsorize outliers (clip at ±5 sigma)
    for col in feat.columns:
        mu = feat[col].mean()
        sigma = feat[col].std()
        if sigma > 0:
            feat[col] = feat[col].clip(mu - 5 * sigma, mu + 5 * sigma)

    return feat


def compute_features_single(ohlcv_df: pd.DataFrame, date: str) -> dict | None:
    """
    Compute features for a single date from OHLCV history.
    Returns dict of feature values or None if insufficient data.
    """
    if len(ohlcv_df) < 60:
        return None

    features = compute_features(ohlcv_df)
    target_date = pd.Timestamp(date)

    # Find closest date <= target_date
    valid = features.index[features.index <= target_date]
    if len(valid) == 0:
        return None

    row = features.loc[valid[-1]]
    return row.to_dict()
