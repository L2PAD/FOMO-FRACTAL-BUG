"""
V2 Bootstrap Pretrain — One-shot script.
Trains on signal_training_dataset_v2 (3,307 records) with sample_weight=0.3.
Saves as a bootstrap candidate ONLY. Does NOT replace the active model.

Usage:
  python3 pretrain_v2_bootstrap.py
"""

import os
import sys
import pickle
import numpy as np
from datetime import datetime, timezone
from collections import Counter

# Ensure backend is in path
sys.path.insert(0, os.path.dirname(__file__))

from pymongo import MongoClient
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, precision_score
from sklearn.model_selection import cross_val_predict

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

# Feature columns (same as signal_pipeline.py)
FEATURE_COLS = [
    "f_actor_hit_rate",
    "f_actor_early_ratio",
    "f_actor_avg_rel_ret",
    "f_actor_signal_count",
    "f_likes",
    "f_views",
    "f_reposts",
    "f_ret_1h",
    "f_ret_4h",
    "f_coord_unique_actors_1h",
    "f_coord_mentions_1h",
    "f_coord_density",
]

CATEGORICAL_FEATURES = {
    "f_signal_position": {"EARLY": 0, "MID": 1, "LATE": 2, "UNKNOWN": 1},
    "f_actor_role": {"DRIVER": 3, "AMPLIFIER": 2, "TRACKER": 1, "NOISE": 0, "UNKNOWN": 0},
    "f_signal_type": {"conviction": 2, "accumulation": 2, "listing": 1, "rotation": 1, "warning": -1, "mention": 0},
}

SAMPLE_WEIGHT = 0.3


def build_feature_matrix(samples):
    """Convert samples to feature matrix + labels."""
    X, y, meta = [], [], []

    for s in samples:
        row = []
        for col in FEATURE_COLS:
            val = s.get(col)
            row.append(float(val) if val is not None else 0.0)

        for cat_col, mapping in CATEGORICAL_FEATURES.items():
            val = s.get(cat_col, "UNKNOWN")
            row.append(float(mapping.get(val, 0)))

        X.append(row)
        y.append(1 if s.get("tradeable") else 0)
        meta.append({
            "actor": s.get("actor_handle"),
            "token": s.get("token"),
            "rel_ret_24h": s.get("rel_ret_24h", 0),
            "label_4class": s.get("label_4class"),
        })

    feature_names = FEATURE_COLS + list(CATEGORICAL_FEATURES.keys())
    return np.array(X), np.array(y), meta, feature_names


def time_split(samples, train_ratio=0.70, valid_ratio=0.15):
    """Split by time: train (oldest) -> valid -> test (newest)."""
    sorted_samples = sorted(samples, key=lambda s: s.get("timestamp", ""))
    n = len(sorted_samples)
    train_end = int(n * train_ratio)
    valid_end = int(n * (train_ratio + valid_ratio))
    return sorted_samples[:train_end], sorted_samples[train_end:valid_end], sorted_samples[valid_end:]


def main():
    print("=" * 60)
    print("V2 BOOTSTRAP PRETRAIN")
    print(f"sample_weight = {SAMPLE_WEIGHT}")
    print("=" * 60)

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    # 1. Load v2 dataset
    samples = list(db.signal_training_dataset_v2.find({}, {"_id": 0}))
    print(f"\n[1] Loaded {len(samples)} v2 samples")

    label_dist = Counter(s.get("label_4class") for s in samples)
    binary_dist = Counter(s.get("label_binary") for s in samples)
    print(f"    4-class: {dict(label_dist)}")
    print(f"    Binary:  {dict(binary_dist)}")

    # 2. Time-split
    train_set, valid_set, test_set = time_split(samples)
    print(f"\n[2] Time-split: train={len(train_set)} valid={len(valid_set)} test={len(test_set)}")

    # 3. Build feature matrices
    X_train, y_train, meta_train, feature_names = build_feature_matrix(train_set)
    X_valid, y_valid, meta_valid, _ = build_feature_matrix(valid_set)
    X_test, y_test, meta_test, _ = build_feature_matrix(test_set)

    print(f"\n[3] Features: {len(feature_names)}")
    print(f"    Train pos/neg: {int(y_train.sum())}/{len(y_train) - int(y_train.sum())}")
    print(f"    Test  pos/neg: {int(y_test.sum())}/{len(y_test) - int(y_test.sum())}")

    # 4. Build sample weights (all = 0.3 for v2 bootstrap)
    train_weights = np.full(len(y_train), SAMPLE_WEIGHT)

    # Class balance via scale_pos_weight
    pos = int(y_train.sum())
    neg = len(y_train) - pos
    scale_pos = neg / max(pos, 1)
    print(f"\n[4] scale_pos_weight = {scale_pos:.3f}")

    # 5. Train XGBoost
    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        scale_pos_weight=scale_pos,
        eval_metric="logloss",
        use_label_encoder=False,
        random_state=42,
    )
    model.fit(X_train, y_train, sample_weight=train_weights)
    print("\n[5] Model trained with sample_weight=0.3")

    # 6. Evaluate on TEST set (unseen, newest data)
    y_proba_test = model.predict_proba(X_test)[:, 1]
    y_pred_test = (y_proba_test > 0.5).astype(int)

    report = classification_report(y_test, y_pred_test,
                                   target_names=["NON_TRADEABLE", "TRADEABLE"],
                                   output_dict=True)

    print("\n[6] Test Set Classification Report:")
    print(classification_report(y_test, y_pred_test,
                                target_names=["NON_TRADEABLE", "TRADEABLE"]))

    # 7. Trading metrics on test set (top 10%)
    top_k = max(int(len(y_proba_test) * 0.1), 3)
    top_idx = np.argsort(y_proba_test)[-top_k:]

    top_rets = [meta_test[i]["rel_ret_24h"] for i in top_idx if meta_test[i].get("rel_ret_24h") is not None]
    all_rets = [m["rel_ret_24h"] for m in meta_test if m.get("rel_ret_24h") is not None]

    top_hits = sum(1 for r in top_rets if r > 0)
    top_avg = sum(top_rets) / len(top_rets) if top_rets else 0
    baseline_avg = sum(all_rets) / len(all_rets) if all_rets else 0
    median_ret = float(np.median(top_rets)) if top_rets else 0

    # Max drawdown
    cum, peak, max_dd = 0, 0, 0
    for r in top_rets:
        cum += r
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)

    # Profit factor
    wins = sum(r for r in top_rets if r > 0)
    losses = abs(sum(r for r in top_rets if r < 0))
    profit_factor = wins / losses if losses > 0 else float("inf")

    hit_rate = top_hits / len(top_rets) if top_rets else 0

    print(f"\n[7] Trading Metrics (top {top_k} signals):")
    print(f"    Hit rate:      {hit_rate:.4f}")
    print(f"    Avg return:    {top_avg * 100:.4f}%")
    print(f"    Median return: {median_ret * 100:.4f}%")
    print(f"    Baseline avg:  {baseline_avg * 100:.4f}%")
    print(f"    Alpha:         {(top_avg - baseline_avg) * 100:.4f}%")
    print(f"    Max drawdown:  {max_dd * 100:.4f}%")
    print(f"    Profit factor: {profit_factor:.4f}")

    # 8. Feature importance
    importances = dict(zip(feature_names, model.feature_importances_.tolist()))
    importances_sorted = dict(sorted(importances.items(), key=lambda x: -x[1]))

    print("\n[8] Feature Importance (top 5):")
    for i, (k, v) in enumerate(importances_sorted.items()):
        if i >= 5:
            break
        print(f"    {k}: {v:.4f}")

    # 9. Save to DB as BOOTSTRAP candidate (NOT active)
    version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    model_key = f"bootstrap_v2_pretrain_{version}"

    model_bytes = pickle.dumps(model)

    metrics = {
        "precision_top10": round(hit_rate, 4),
        "hit_rate": round(hit_rate, 4),
        "avg_return": round(top_avg * 100, 4),
        "median_return": round(median_ret * 100, 4),
        "max_drawdown": round(max_dd * 100, 4),
        "profit_factor": round(profit_factor, 4),
        "alpha_vs_baseline": round((top_avg - baseline_avg) * 100, 4),
        "test_samples": len(test_set),
        "train_samples": len(train_set),
        "valid_samples": len(valid_set),
        "total_v2_samples": len(samples),
        "sample_weight": SAMPLE_WEIGHT,
        "classification_report": report,
    }

    # Save model binary
    db.signal_models.update_one(
        {"name": model_key},
        {"$set": {
            "name": model_key,
            "type": "xgboost_binary_bootstrap",
            "target": "tradeable",
            "features": feature_names,
            "model_binary": model_bytes,
            "metrics": metrics,
            "feature_importance": importances_sorted,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "source_dataset": "signal_training_dataset_v2",
            "sample_weight": SAMPLE_WEIGHT,
            "is_bootstrap": True,
        }},
        upsert=True,
    )
    print(f"\n[9] Saved to signal_models: {model_key}")

    # Register as BOOTSTRAP (not candidate, not active)
    db.ml_model_registry.update_one(
        {"model_key": model_key},
        {"$set": {
            "model_key": model_key,
            "status": "bootstrap",
            "stage": "bootstrap",
            "metrics": metrics,
            "feature_importance": importances_sorted,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "promoted_at": None,
            "rolled_back_at": None,
            "source_dataset": "signal_training_dataset_v2",
            "sample_weight": SAMPLE_WEIGHT,
            "note": "V2 bootstrap pretrain. NOT for production. Use as base for v3 finetuning.",
        }},
        upsert=True,
    )
    print(f"    Registered in ml_model_registry as 'bootstrap'")

    # Log pretrain job
    db.ml_retrain_jobs.insert_one({
        "model_key": model_key,
        "status": "completed",
        "trigger": "bootstrap_v2_pretrain",
        "samples": len(samples),
        "splits": {"train": len(train_set), "valid": len(valid_set), "test": len(test_set)},
        "metrics": metrics,
        "sample_weight": SAMPLE_WEIGHT,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    print(f"    Logged in ml_retrain_jobs")

    print("\n" + "=" * 60)
    print(f"BOOTSTRAP PRETRAIN COMPLETE: {model_key}")
    print(f"Status: bootstrap (NOT active, NOT candidate)")
    print(f"Active model unchanged.")
    print("=" * 60)

    client.close()
    return model_key, metrics


if __name__ == "__main__":
    main()
