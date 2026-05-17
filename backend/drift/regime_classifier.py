"""
Deterministic Regime Classifier + Regime Baseline Generator.

Uses 3 metrics: 30D realized vol, 30D MA slope, 7D drawdown.
Hysteresis: minimum 5 days in regime before switching.
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pymongo import MongoClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

# Regime thresholds (tuned for BTC daily)
THRESHOLDS = {
    "vol_high": 0.65,        # annualized vol percentile
    "vol_low": 0.35,
    "slope_strong": 0.002,   # daily MA slope (0.2% per day = ~6% monthly)
    "drawdown_risk": -0.10,  # 7D drawdown < -10%
    "hysteresis_days": 5,    # min days before regime switch
}


def classify_regimes(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """
    Classify each day into a regime based on vol, trend, drawdown.
    Returns DataFrame with 'regime' column.
    """
    df = ohlcv.copy()
    close = df["close"]

    # 30D realized volatility (annualized)
    ret = close.pct_change()
    vol_30d = ret.rolling(30).std() * np.sqrt(365)

    # 30D MA slope
    ma30 = close.rolling(30).mean()
    ma_slope = ma30.pct_change(5)  # 5-day change in MA = trend direction

    # 7D drawdown
    rolling_max_7 = close.rolling(7).max()
    drawdown_7d = (close - rolling_max_7) / rolling_max_7

    # Percentile-based vol thresholds (adaptive)
    vol_p_high = vol_30d.quantile(THRESHOLDS["vol_high"])
    vol_p_low = vol_30d.quantile(THRESHOLDS["vol_low"])

    # Raw classification
    raw_regime = pd.Series("TRANSITION", index=df.index)

    # RISK_OFF: high vol + significant drawdown
    risk_off = (drawdown_7d < THRESHOLDS["drawdown_risk"]) & (vol_30d > vol_p_low)
    raw_regime[risk_off] = "RISK_OFF"

    # TREND: strong slope + not risk-off
    trend = (ma_slope.abs() > THRESHOLDS["slope_strong"]) & (~risk_off) & (vol_30d <= vol_p_high)
    raw_regime[trend] = "TREND"

    # RANGE: low vol + flat slope + no drawdown
    range_cond = (
        (vol_30d <= vol_p_low) &
        (ma_slope.abs() <= THRESHOLDS["slope_strong"]) &
        (drawdown_7d > THRESHOLDS["drawdown_risk"]) &
        (~risk_off)
    )
    raw_regime[range_cond] = "RANGE"

    # Apply hysteresis: minimum N days before regime switch
    stable_regime = _apply_hysteresis(raw_regime, THRESHOLDS["hysteresis_days"])

    df["vol_30d"] = vol_30d
    df["ma_slope"] = ma_slope
    df["drawdown_7d"] = drawdown_7d
    df["raw_regime"] = raw_regime
    df["regime"] = stable_regime

    return df


def _apply_hysteresis(raw: pd.Series, min_days: int) -> pd.Series:
    """Apply hysteresis: don't switch regime until it's stable for min_days."""
    result = raw.copy()
    current = raw.iloc[0] if len(raw) > 0 else "TRANSITION"
    streak = 0

    for i in range(len(raw)):
        if raw.iloc[i] == current:
            streak += 1
            result.iloc[i] = current
        else:
            streak += 1
            candidate = raw.iloc[i]
            # Count how many upcoming days also have this candidate
            lookahead = min(min_days, len(raw) - i)
            same_count = sum(1 for j in range(i, i + lookahead) if raw.iloc[j] == candidate)
            if same_count >= min_days:
                current = candidate
                streak = 1
                result.iloc[i] = current
            else:
                result.iloc[i] = current

    return result


def compute_regime_baselines(ohlcv: pd.DataFrame, horizons=None) -> dict:
    """
    Compute performance baselines per regime per horizon.
    Uses historical forecast evaluation data + regime labels.
    """
    if horizons is None:
        horizons = ["7D", "30D"]

    from ml_overlay.data.dataset_builder import build_dataset

    df = classify_regimes(ohlcv)
    regime_dist = df["regime"].value_counts()
    print(f"\nRegime distribution:")
    total = len(df.dropna(subset=["regime"]))
    for r, c in regime_dist.items():
        print(f"  {r}: {c} days ({c/total*100:.1f}%)")

    baselines = {}

    for horizon in horizons:
        print(f"\n[{horizon}] Computing regime baselines...")
        dataset = build_dataset(ohlcv, horizon)

        # Merge regime labels into dataset
        dataset = dataset.join(df[["regime"]], how="left")
        dataset = dataset.dropna(subset=["regime", "y"])

        horizon_baselines = {}

        for regime in ["TREND", "RANGE", "RISK_OFF", "TRANSITION"]:
            subset = dataset[dataset["regime"] == regime]
            n = len(subset)

            if n < 30:
                print(f"  {regime}: {n} rows (insufficient, skip)")
                continue

            # MAE of residual (how much rule misses)
            mae_vals = np.abs(subset["y"].values)  # y = r_real - r_rule
            # Direction accuracy of rule
            if "r_rule" in subset.columns and "r_real" in subset.columns:
                dir_hit = np.mean(np.sign(subset["r_rule"]) == np.sign(subset["r_real"]))
                # Flip rate of rule
                dir_signs = np.sign(subset["r_rule"].values)
                flips = np.sum(np.diff(dir_signs) != 0) / max(1, len(dir_signs) - 1)
            else:
                dir_hit = 0.5
                flips = 0.3

            baseline = {
                "n": int(n),
                "mae_mean": round(float(np.mean(mae_vals)), 6),
                "mae_std": round(float(np.std(mae_vals)), 6),
                "mae_p75": round(float(np.percentile(mae_vals, 75)), 6),
                "dir_hit_mean": round(float(dir_hit), 4),
                "flip_mean": round(float(flips), 4),
                "flip_std": round(float(np.std(np.abs(np.diff(dir_signs)))), 4) if n > 1 else 0.1,
            }

            # Add actual return stats for regime-anchored forecasting
            if "r_real" in subset.columns:
                real_returns = subset["r_real"].values
                baseline["mean_return"] = round(float(np.mean(real_returns)), 6)
                baseline["std_return"] = round(float(np.std(real_returns)), 6)
                baseline["median_return"] = round(float(np.median(real_returns)), 6)
                baseline["p10_return"] = round(float(np.percentile(real_returns, 10)), 6)
                baseline["p25_return"] = round(float(np.percentile(real_returns, 25)), 6)
                baseline["p75_return"] = round(float(np.percentile(real_returns, 75)), 6)
                baseline["p90_return"] = round(float(np.percentile(real_returns, 90)), 6)
            else:
                baseline["mean_return"] = 0.0
                baseline["std_return"] = baseline["mae_mean"]
                baseline["median_return"] = 0.0
                baseline["p10_return"] = -baseline["mae_mean"] * 1.5
                baseline["p25_return"] = -baseline["mae_mean"]
                baseline["p75_return"] = baseline["mae_mean"]
                baseline["p90_return"] = baseline["mae_mean"] * 1.5

            horizon_baselines[regime] = baseline
            print(f"  {regime}: n={n}  MAE={baseline['mae_mean']:.5f}+/-{baseline['mae_std']:.5f}  DirHit={baseline['dir_hit_mean']:.3f}  Flip={baseline['flip_mean']:.3f}")

        baselines[horizon] = horizon_baselines

    return {
        "baselines": baselines,
        "regimeDistribution": {r: int(c) for r, c in regime_dist.items()},
        "totalDays": total,
    }


def store_regime_baselines(baselines_data: dict):
    """Store regime baselines to MongoDB."""
    db = MongoClient(MONGO_URL)[DB_NAME]
    col = db["drift_regime_baselines"]

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    for horizon, regimes in baselines_data["baselines"].items():
        for regime, baseline in regimes.items():
            col.update_one(
                {"horizon": horizon, "regime": regime},
                {"$set": {
                    "horizon": horizon,
                    "regime": regime,
                    "baseline": baseline,
                    "generatedAt": now_ms,
                    "totalDays": baselines_data["totalDays"],
                }},
                upsert=True,
            )

    print(f"\n[Stored] {sum(len(r) for r in baselines_data['baselines'].values())} regime baselines to MongoDB")


def get_regime_baseline(horizon: str, regime: str) -> dict:
    """Get stored regime baseline from MongoDB."""
    db = MongoClient(MONGO_URL)[DB_NAME]
    doc = db["drift_regime_baselines"].find_one(
        {"horizon": horizon, "regime": regime},
        {"_id": 0},
    )
    return doc.get("baseline") if doc else None


def get_current_regime_from_price(ohlcv_recent: pd.DataFrame = None) -> str:
    """
    Infer current regime from recent price data.
    Fallback when macro_state doesn't have reliable regime.
    """
    if ohlcv_recent is None or len(ohlcv_recent) < 35:
        return "TRANSITION"

    close = ohlcv_recent["close"]
    ret = close.pct_change()
    vol = ret.rolling(30).std().iloc[-1] * np.sqrt(365)
    ma30 = close.rolling(30).mean()
    slope = ma30.pct_change(5).iloc[-1]
    dd = (close.iloc[-1] - close.rolling(7).max().iloc[-1]) / close.rolling(7).max().iloc[-1]

    vol_p_high = ret.rolling(30).std().quantile(THRESHOLDS["vol_high"]) * np.sqrt(365)
    vol_p_low = ret.rolling(30).std().quantile(THRESHOLDS["vol_low"]) * np.sqrt(365)

    if dd < THRESHOLDS["drawdown_risk"] and vol > vol_p_low:
        return "RISK_OFF"
    if abs(slope) > THRESHOLDS["slope_strong"] and vol <= vol_p_high:
        return "TREND"
    if vol <= vol_p_low and abs(slope) <= THRESHOLDS["slope_strong"]:
        return "RANGE"
    return "TRANSITION"


def run_regime_baseline_pipeline():
    """Full A2 pipeline: classify history, compute baselines, store."""
    print("=" * 60)
    print("A2: Regime-Specific Drift Baselines")
    print("=" * 60)

    from ml_overlay.data.price_provider import get_ohlcv
    ohlcv = get_ohlcv("BTC-USD", years=7)
    print(f"OHLCV: {len(ohlcv)} rows, {ohlcv.index[0].date()} to {ohlcv.index[-1].date()}")

    result = compute_regime_baselines(ohlcv)
    store_regime_baselines(result)

    # Save artifact
    artifact_path = os.path.join(os.path.dirname(__file__), "..", "drift", "regime_baselines.json")
    with open(artifact_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n[SAVED] {artifact_path}")

    return result


if __name__ == "__main__":
    run_regime_baseline_pipeline()
