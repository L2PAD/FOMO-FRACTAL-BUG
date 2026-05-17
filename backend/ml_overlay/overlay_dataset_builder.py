"""
ML Overlay Dataset Builder
=============================
Block 5 — Task 5.2

Builds training dataset from evaluated forecasts + market data.

Label definitions:
  - error_risk: 1 if forecast direction was wrong
  - catastrophic_risk: 1 if |actual move| > threshold AND direction wrong

Key constraints:
  - No future leakage: features only from data AT or BEFORE forecast time
  - Time-based train/test split (no random shuffle)
  - Start with 7D horizon only (strongest signal)
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from ml_overlay.overlay_feature_builder import build_features_from_forecast_and_obs, get_feature_names


# ── Config ──
CATASTROPHIC_THRESHOLD_PCT = 5.0   # |move| > 5% with wrong direction = catastrophic
OBS_WINDOW_MS = 3600 * 1000        # look for observation within 1h of forecast


def _get_db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _find_nearest_obs(db, symbol: str, ts: float) -> dict | None:
    """Find the closest exchange_observation before/at a timestamp."""
    doc = db["exchange_observations"].find_one(
        {"symbol": symbol, "timestamp": {"$lte": ts, "$gte": ts - OBS_WINDOW_MS}},
        {"_id": 0},
        sort=[("timestamp", -1)],
    )
    return doc


def _find_funding_at(db, symbol: str, ts: float) -> dict | None:
    """Find the closest funding context before a timestamp."""
    doc = db["exchange_funding_context"].find_one(
        {"symbol": symbol, "ts": {"$lte": ts}},
        {"_id": 0},
        sort=[("ts", -1)],
    )
    return doc


def _compute_labels(forecast: dict) -> dict | None:
    """
    Compute ML labels from forecast outcome.
    Returns None if outcome is missing or unusable.
    """
    outcome = forecast.get("outcome")
    if not outcome:
        return None

    direction = (forecast.get("direction") or "NEUTRAL").upper()
    real_move = outcome.get("realMovePct") or outcome.get("errorPct") or 0
    dir_match = outcome.get("directionMatch", False)
    label = outcome.get("label", "")

    # error_risk: direction was wrong
    # For NEUTRAL forecasts: error if move was large (> 2%)
    if direction in ("NEUTRAL", "FLAT"):
        error = 1 if abs(real_move) > 2.0 else 0
    else:
        error = 0 if dir_match else 1

    # catastrophic_risk: large adverse move with wrong direction
    catastrophic = 1 if (abs(real_move) > CATASTROPHIC_THRESHOLD_PCT and error == 1) else 0

    return {
        "error_risk": error,
        "catastrophic_risk": catastrophic,
        "real_move_pct": real_move,
        "direction_match": dir_match,
        "outcome_label": label,
    }


def build_dataset(
    horizon_days: int = 7,
    asset: str = "BTC",
) -> dict:
    """
    Build ML training dataset from evaluated forecasts.

    Returns:
        {
            "rows": [...],
            "feature_names": [...],
            "stats": {...},
        }
    """
    print(f"[ML Dataset] Building for {asset} {horizon_days}D")
    db = _get_db()
    symbol = f"{asset}USDT"

    # Fetch all evaluated forecasts for this horizon
    forecasts = list(
        db["exchange_forecasts"]
        .find(
            {
                "evaluated": True,
                "horizonDays": horizon_days,
                "outcome": {"$exists": True, "$ne": None},
                "asset": asset,
            },
            {"_id": 0},
        )
        .sort("createdAt", 1)
    )

    print(f"[ML Dataset] Found {len(forecasts)} evaluated forecasts")

    rows = []
    skipped = {"no_labels": 0, "no_features": 0}

    for fc in forecasts:
        # Compute labels
        labels = _compute_labels(fc)
        if labels is None:
            skipped["no_labels"] += 1
            continue

        # Find nearest market observation
        fc_ts = fc.get("createdAt", 0)
        obs = _find_nearest_obs(db, symbol, fc_ts)
        funding = _find_funding_at(db, symbol, fc_ts)

        # Build features
        try:
            features = build_features_from_forecast_and_obs(fc, obs, funding)
        except Exception as e:
            print(f"[ML Dataset] Feature build error: {e}")
            skipped["no_features"] += 1
            continue

        rows.append({
            "forecast_id": fc.get("id", ""),
            "created_at": fc_ts,
            "horizon_days": horizon_days,
            "features": features,
            "labels": labels,
        })

    print(f"[ML Dataset] Built {len(rows)} rows, skipped: {skipped}")

    if not rows:
        return {"ok": False, "error": "No valid rows", "rows": [], "stats": {}}

    # ── Compute dataset stats ──
    stats = _compute_stats(rows)

    return {
        "ok": True,
        "rows": rows,
        "feature_names": get_feature_names(),
        "stats": stats,
    }


def _compute_stats(rows: list) -> dict:
    """Compute dataset statistics for reporting."""
    n = len(rows)

    # Label distribution
    error_pos = sum(1 for r in rows if r["labels"]["error_risk"] == 1)
    catastrophic_pos = sum(1 for r in rows if r["labels"]["catastrophic_risk"] == 1)

    # Time range
    timestamps = [r["created_at"] for r in rows]
    min_ts = min(timestamps)
    max_ts = max(timestamps)
    min_dt = datetime.fromtimestamp(min_ts / 1000, tz=timezone.utc)
    max_dt = datetime.fromtimestamp(max_ts / 1000, tz=timezone.utc)

    # Observation coverage
    with_obs = sum(1 for r in rows if r["features"].get("has_obs") == 1)
    with_funding = sum(1 for r in rows if r["features"].get("has_funding") == 1)

    # Train/test split (time-based, 80/20)
    split_idx = int(n * 0.8)
    train_rows = rows[:split_idx]
    test_rows = rows[split_idx:]

    train_error = sum(1 for r in train_rows if r["labels"]["error_risk"] == 1)
    test_error = sum(1 for r in test_rows if r["labels"]["error_risk"] == 1)

    # Feature stats
    feature_names = get_feature_names()
    feature_stats = {}
    for fname in feature_names:
        vals = [r["features"].get(fname, 0) for r in rows]
        vals_clean = [v for v in vals if v is not None]
        if vals_clean:
            feature_stats[fname] = {
                "min": round(min(vals_clean), 4),
                "max": round(max(vals_clean), 4),
                "mean": round(sum(vals_clean) / len(vals_clean), 4),
                "nonzero_pct": round(sum(1 for v in vals_clean if v != 0) / len(vals_clean) * 100, 1),
            }

    return {
        "n_rows": n,
        "time_range": {
            "start": min_dt.isoformat(),
            "end": max_dt.isoformat(),
            "days": (max_dt - min_dt).days,
        },
        "labels": {
            "error_risk": {
                "positive": error_pos,
                "negative": n - error_pos,
                "rate_pct": round(error_pos / n * 100, 1),
            },
            "catastrophic_risk": {
                "positive": catastrophic_pos,
                "negative": n - catastrophic_pos,
                "rate_pct": round(catastrophic_pos / n * 100, 1),
            },
        },
        "observation_coverage": {
            "with_obs": with_obs,
            "with_funding": with_funding,
            "obs_pct": round(with_obs / n * 100, 1),
            "funding_pct": round(with_funding / n * 100, 1),
        },
        "split": {
            "train_size": len(train_rows),
            "test_size": len(test_rows),
            "train_error_rate": round(train_error / max(len(train_rows), 1) * 100, 1),
            "test_error_rate": round(test_error / max(len(test_rows), 1) * 100, 1),
            "split_date": datetime.fromtimestamp(
                rows[split_idx]["created_at"] / 1000, tz=timezone.utc
            ).isoformat() if split_idx < n else None,
        },
        "feature_stats": feature_stats,
    }


def save_dataset(dataset: dict, path: str | None = None) -> str:
    """Save dataset to JSON file."""
    if path is None:
        path = str(Path(__file__).parent / "dataset_7d.json")

    # Save only stats and metadata (rows can be huge)
    meta = {
        "ok": dataset["ok"],
        "n_rows": len(dataset.get("rows", [])),
        "feature_names": dataset.get("feature_names", []),
        "stats": dataset.get("stats", {}),
    }

    with open(path, "w") as f:
        json.dump(meta, f, indent=2, default=str)

    # Save full dataset separately
    full_path = path.replace(".json", "_full.json")
    with open(full_path, "w") as f:
        json.dump(dataset, f, indent=2, default=str)

    print(f"[ML Dataset] Stats saved to {path}")
    print(f"[ML Dataset] Full data saved to {full_path}")
    return path


if __name__ == "__main__":
    dataset = build_dataset(horizon_days=7, asset="BTC")
    print("\n" + "=" * 70)
    print("BLOCK 5 — ML OVERLAY DATASET STATUS")
    print("=" * 70)

    if dataset["ok"]:
        stats = dataset["stats"]
        print(json.dumps(stats, indent=2, default=str))
        save_dataset(dataset)
    else:
        print(f"ERROR: {dataset.get('error')}")
