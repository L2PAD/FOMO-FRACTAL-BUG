"""
Real vs Synthetic Validation Framework.

4 strict time-isolated tests:
  A: Train Synthetic → Test Real  (show overfit)
  B: Train Real Only → Test Real  (baseline truth)
  C: Train Mixed (70/30) → Test Real  (optimal blend?)
  D: Train Real Only → Test Live Holdout (last 3-5 days — THE metric)

Metrics per test: precision_top10, hit_rate, avg_return, median_return, profit_factor, max_drawdown
Plus: confidence buckets, actor bias, feature importance drift, decision logic, red flags.
"""

import numpy as np
import pickle
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

from ml_ops import get_db

# ─── Feature columns (matching what's in signal_training_dataset_v2) ───

NUMERIC_FEATURES = [
    "f_actor_hit_rate", "f_actor_early_ratio", "f_actor_avg_rel_ret", "f_actor_signal_count",
    "f_likes", "f_views", "f_reposts",
    "f_ret_1h", "f_ret_4h",
    "f_coord_unique_actors_1h", "f_coord_mentions_1h", "f_coord_density",
]

CATEGORICAL_MAPS = {
    "f_signal_position": {"EARLY": 0, "MID": 1, "LATE": 2, "UNKNOWN": 1},
    "f_actor_role": {"DRIVER": 3, "AMPLIFIER": 2, "TRACKER": 1, "NOISE": 0, "UNKNOWN": 0},
    "f_signal_type": {"conviction": 2, "accumulation": 2, "listing": 1, "rotation": 1, "warning": -1, "mention": 0},
}

ALL_FEATURE_NAMES = NUMERIC_FEATURES + list(CATEGORICAL_MAPS.keys())


def _extract_features(sample):
    """Extract feature vector from a dataset sample."""
    row = []
    for col in NUMERIC_FEATURES:
        val = sample.get(col)
        row.append(float(val) if val is not None else 0.0)
    for cat_col, mapping in CATEGORICAL_MAPS.items():
        val = sample.get(cat_col, "UNKNOWN")
        row.append(float(mapping.get(str(val), 0)))
    return row


def _build_matrix(samples):
    """Build X, y, meta from samples list."""
    X, y, meta = [], [], []
    for s in samples:
        X.append(_extract_features(s))
        y.append(1 if s.get("tradeable") else 0)
        meta.append({
            "actor": s.get("actor_handle", ""),
            "token": s.get("token", ""),
            "rel_ret_1h": float(s.get("rel_ret_1h") or 0),
            "rel_ret_24h": float(s.get("rel_ret_24h") or 0),
            "timestamp": s.get("timestamp", ""),
            "source": s.get("source", ""),
        })
    return np.array(X), np.array(y), meta


def _parse_ts(ts_str):
    """Parse timestamp string to datetime."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ─── Metrics Computation ───

def _compute_metrics(y_true, y_proba, meta, top_pct=0.10):
    """Compute full metric suite for a test."""
    n = len(y_true)
    if n < 5:
        return {"error": "too_few_samples", "n": n}

    top_k = max(int(n * top_pct), 3)
    top_indices = np.argsort(y_proba)[-top_k:]

    # Precision at top 10%
    top_actual = [int(y_true[i]) for i in top_indices]
    precision_top10 = sum(top_actual) / len(top_actual) if top_actual else 0

    # Returns of top-K signals
    top_returns = [meta[i]["rel_ret_24h"] for i in top_indices]

    # Hit rate
    hits = sum(1 for r in top_returns if r > 0)
    hit_rate = hits / len(top_returns) if top_returns else 0

    # Avg and median return
    avg_return = float(np.mean(top_returns)) if top_returns else 0
    median_return = float(np.median(top_returns)) if top_returns else 0

    # Profit factor
    gains = sum(r for r in top_returns if r > 0)
    losses = abs(sum(r for r in top_returns if r < 0))
    profit_factor = gains / losses if losses > 0 else (999.0 if gains > 0 else 0)

    # Max drawdown
    cum = 0
    peak = 0
    max_dd = 0
    for r in top_returns:
        cum += r
        peak = max(peak, cum)
        dd = cum - peak
        max_dd = min(max_dd, dd)

    return {
        "n_test": n,
        "n_top_k": top_k,
        "precision_top10": round(precision_top10, 4),
        "hit_rate": round(hit_rate, 4),
        "avg_return": round(avg_return * 100, 4),
        "median_return": round(median_return * 100, 4),
        "profit_factor": round(profit_factor, 4),
        "max_drawdown": round(max_dd * 100, 4),
    }


def _compute_confidence_buckets(y_true, y_proba, meta):
    """Bucket analysis: does higher confidence = higher win rate?"""
    buckets = [
        ("0.9+", 0.9, 1.01),
        ("0.8-0.9", 0.8, 0.9),
        ("0.7-0.8", 0.7, 0.8),
        ("0.6-0.7", 0.6, 0.7),
        ("0.5-0.6", 0.5, 0.6),
        ("<0.5", 0.0, 0.5),
    ]

    results = []
    for label, lo, hi in buckets:
        mask = (y_proba >= lo) & (y_proba < hi)
        indices = np.where(mask)[0]
        if len(indices) == 0:
            results.append({"bucket": label, "count": 0, "win_rate": None, "avg_return": None})
            continue

        wins = sum(1 for i in indices if meta[i]["rel_ret_24h"] > 0)
        avg_ret = float(np.mean([meta[i]["rel_ret_24h"] for i in indices]))
        results.append({
            "bucket": label,
            "count": int(len(indices)),
            "win_rate": round(wins / len(indices), 4),
            "avg_return": round(avg_ret * 100, 4),
        })

    # Check monotonicity
    win_rates = [b["win_rate"] for b in results if b["win_rate"] is not None]
    monotonic = all(win_rates[i] >= win_rates[i + 1] for i in range(len(win_rates) - 1)) if len(win_rates) >= 2 else True

    return {"buckets": results, "monotonic": monotonic}


def _compute_actor_bias(meta, y_proba, top_pct=0.10):
    """Actor concentration in top signals."""
    n = len(meta)
    top_k = max(int(n * top_pct), 3)
    top_indices = np.argsort(y_proba)[-top_k:]

    # Actor counts in top signals
    actor_counts = Counter(meta[i]["actor"] for i in top_indices)
    total_in_top = sum(actor_counts.values())

    # Top 3 actors dependency
    top3 = actor_counts.most_common(3)
    top3_share = sum(c for _, c in top3) / total_in_top if total_in_top > 0 else 0

    # Gini of actor counts
    counts = list(actor_counts.values())
    if len(counts) >= 2:
        sorted_v = sorted(counts)
        n_a = len(sorted_v)
        total_sum = sum(sorted_v)
        if total_sum > 0:
            gini_sum = sum((2 * (i + 1) - n_a - 1) * v for i, v in enumerate(sorted_v))
            actor_gini = round(gini_sum / (n_a * total_sum), 4)
        else:
            actor_gini = 0
    else:
        actor_gini = 0

    return {
        "top3_actors": [{"actor": a, "count": c, "share": round(c / total_in_top, 4)} for a, c in top3],
        "top3_dep": round(top3_share, 4),
        "actor_gini": actor_gini,
        "unique_actors_in_top": len(actor_counts),
        "total_in_top": total_in_top,
    }


def _train_and_evaluate(X_train, y_train, X_test, y_test, meta_test):
    """Train XGBoost and evaluate on test set. Return metrics + probabilities + model."""
    from xgboost import XGBClassifier

    pos = int(y_train.sum())
    neg = len(y_train) - pos
    scale = neg / max(pos, 1)

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        scale_pos_weight=scale,
        eval_metric="logloss",
        use_label_encoder=False,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_proba = model.predict_proba(X_test)[:, 1]
    metrics = _compute_metrics(y_test, y_proba, meta_test)
    importance = dict(zip(ALL_FEATURE_NAMES, model.feature_importances_.tolist()))
    importance = dict(sorted(importance.items(), key=lambda x: -x[1]))

    return metrics, y_proba, importance, model


# ─── Main Validation Pipeline ───

async def run_real_vs_synthetic_validation():
    """
    Execute 4 strict time-isolated tests + all validation metrics.
    Returns full validation report with decision.
    """
    db = get_db()

    # Load all dataset samples
    all_samples = await db.signal_training_dataset_v2.find({}, {"_id": 0}).to_list(length=50000)
    if len(all_samples) < 20:
        return {"ok": False, "error": f"Not enough data: {len(all_samples)} samples"}

    # ─── Separate real vs synthetic ───
    real_samples = [s for s in all_samples if s.get("source") not in ("expansion", "synthetic")]
    synth_samples = [s for s in all_samples if s.get("source") in ("expansion", "synthetic")]

    if len(real_samples) < 10:
        return {"ok": False, "error": f"Not enough real data: {len(real_samples)} samples. Need 10+."}

    # ─── Sort by timestamp for time isolation ───
    def _sort_key(s):
        ts = _parse_ts(s.get("timestamp"))
        return ts if ts else datetime.min.replace(tzinfo=timezone.utc)

    real_samples.sort(key=_sort_key)
    synth_samples.sort(key=_sort_key)

    # ─── Time splits ───
    # Real: 70% train (older), 30% test (newer)
    real_split = int(len(real_samples) * 0.7)
    real_train = real_samples[:real_split]
    real_test = real_samples[real_split:]

    # Live holdout: last 5 days from real data
    now = datetime.now(timezone.utc)
    holdout_cutoff = now - timedelta(days=5)
    live_holdout = [s for s in real_samples if (_parse_ts(s.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)) >= holdout_cutoff]
    real_train_no_holdout = [s for s in real_samples if (_parse_ts(s.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)) < holdout_cutoff]

    # If holdout is too small, expand to 3 days
    if len(live_holdout) < 5:
        holdout_cutoff = now - timedelta(days=3)
        live_holdout = [s for s in real_samples if (_parse_ts(s.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)) >= holdout_cutoff]
        real_train_no_holdout = [s for s in real_samples if (_parse_ts(s.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)) < holdout_cutoff]

    # If still too small, use last 30% as holdout
    if len(live_holdout) < 5:
        holdout_split = int(len(real_samples) * 0.7)
        live_holdout = real_samples[holdout_split:]
        real_train_no_holdout = real_samples[:holdout_split]

    # Synthetic: sort by time, take older 70% for training
    synth_split = int(len(synth_samples) * 0.7)
    synth_train = synth_samples[:synth_split]

    results = {}
    importances = {}

    # ═══════════════════════════════════════
    # TEST A: Train Synthetic → Test Real
    # ═══════════════════════════════════════
    if len(synth_train) >= 10 and len(real_test) >= 5:
        X_train, y_train, _ = _build_matrix(synth_train)
        X_test, y_test, meta_test = _build_matrix(real_test)
        metrics_a, proba_a, imp_a, _ = _train_and_evaluate(X_train, y_train, X_test, y_test, meta_test)
        metrics_a["train_size"] = len(synth_train)
        metrics_a["test_size"] = len(real_test)
        metrics_a["train_source"] = "synthetic_only"
        metrics_a["test_source"] = "real_newest_30pct"
        results["A_synth_train_real_test"] = metrics_a
        importances["A"] = imp_a
    else:
        results["A_synth_train_real_test"] = {"error": "insufficient_data", "synth": len(synth_train), "real_test": len(real_test)}

    # ═══════════════════════════════════════
    # TEST B: Train Real Only → Test Real
    # ═══════════════════════════════════════
    if len(real_train) >= 10 and len(real_test) >= 5:
        X_train, y_train, _ = _build_matrix(real_train)
        X_test, y_test, meta_test = _build_matrix(real_test)
        metrics_b, proba_b, imp_b, _ = _train_and_evaluate(X_train, y_train, X_test, y_test, meta_test)
        metrics_b["train_size"] = len(real_train)
        metrics_b["test_size"] = len(real_test)
        metrics_b["train_source"] = "real_oldest_70pct"
        metrics_b["test_source"] = "real_newest_30pct"
        results["B_real_only"] = metrics_b
        importances["B"] = imp_b
    else:
        results["B_real_only"] = {"error": "insufficient_data", "real_train": len(real_train), "real_test": len(real_test)}

    # ═══════════════════════════════════════
    # TEST C: Train Mixed (70% real + 30% synthetic) → Test Real
    # ═══════════════════════════════════════
    if len(real_train) >= 5 and len(synth_train) >= 5 and len(real_test) >= 5:
        # Mix: all real train + 30% volume of synthetic
        synth_budget = int(len(real_train) * 0.43)  # ~30% of total
        synth_for_mix = synth_train[:min(synth_budget, len(synth_train))]
        mixed_train = real_train + synth_for_mix

        X_train, y_train, _ = _build_matrix(mixed_train)
        X_test, y_test, meta_test = _build_matrix(real_test)
        metrics_c, proba_c, imp_c, _ = _train_and_evaluate(X_train, y_train, X_test, y_test, meta_test)
        metrics_c["train_size"] = len(mixed_train)
        metrics_c["test_size"] = len(real_test)
        metrics_c["train_source"] = f"mixed_real({len(real_train)})_synth({len(synth_for_mix)})"
        metrics_c["test_source"] = "real_newest_30pct"
        metrics_c["real_pct_in_train"] = round(len(real_train) / len(mixed_train), 4)
        results["C_mixed_70_30"] = metrics_c
        importances["C"] = imp_c
    else:
        results["C_mixed_70_30"] = {"error": "insufficient_data"}

    # ═══════════════════════════════════════
    # TEST D: Train Real Only → Test Live Holdout
    # THE ONLY METRIC THAT MATTERS
    # ═══════════════════════════════════════
    if len(real_train_no_holdout) >= 10 and len(live_holdout) >= 3:
        X_train, y_train, _ = _build_matrix(real_train_no_holdout)
        X_test, y_test, meta_test = _build_matrix(live_holdout)
        metrics_d, proba_d, imp_d, _ = _train_and_evaluate(X_train, y_train, X_test, y_test, meta_test)
        metrics_d["train_size"] = len(real_train_no_holdout)
        metrics_d["test_size"] = len(live_holdout)
        metrics_d["train_source"] = "real_before_holdout"
        metrics_d["test_source"] = f"live_holdout_last_{(now - holdout_cutoff).days}d"
        results["D_live_holdout"] = metrics_d
        importances["D"] = imp_d
    else:
        results["D_live_holdout"] = {
            "error": "insufficient_data",
            "real_train_no_holdout": len(real_train_no_holdout),
            "live_holdout": len(live_holdout),
            "note": "Need more real data. Run Twitter ingestion first."
        }

    # ═══════════════════════════════════════
    # CONFIDENCE BUCKETS (on real test only)
    # ═══════════════════════════════════════
    confidence_buckets_real = {"error": "not_computed"}
    if "B_real_only" in results and "error" not in results["B_real_only"]:
        X_test_b, y_test_b, meta_test_b = _build_matrix(real_test)
        X_train_b, y_train_b, _ = _build_matrix(real_train)
        _, proba_for_buckets, _, _ = _train_and_evaluate(X_train_b, y_train_b, X_test_b, y_test_b, meta_test_b)
        confidence_buckets_real = _compute_confidence_buckets(y_test_b, proba_for_buckets, meta_test_b)

    # ═══════════════════════════════════════
    # ACTOR BIAS CHECK
    # ═══════════════════════════════════════
    actor_stats = {}
    for test_name, test_data, proba_data in [
        ("B_real_only", real_test, proba_b if "B_real_only" in results and "error" not in results["B_real_only"] else None),
        ("C_mixed_70_30", real_test, proba_c if "C_mixed_70_30" in results and "error" not in results["C_mixed_70_30"] else None),
    ]:
        if proba_data is not None and len(test_data) >= 5:
            _, _, meta_for_bias = _build_matrix(test_data)
            actor_stats[test_name] = _compute_actor_bias(meta_for_bias, proba_data)

    # ═══════════════════════════════════════
    # SYNTHETIC OVERFIT CHECK (feature importance drift)
    # ═══════════════════════════════════════
    feature_drift = {}
    if "B" in importances and "C" in importances:
        imp_b_dict = importances["B"]
        imp_c_dict = importances["C"]
        drift_items = []
        for feat in ALL_FEATURE_NAMES:
            b_val = imp_b_dict.get(feat, 0)
            c_val = imp_c_dict.get(feat, 0)
            shift = c_val - b_val
            drift_items.append({
                "feature": feat,
                "real_only_importance": round(b_val, 4),
                "mixed_importance": round(c_val, 4),
                "shift": round(shift, 4),
            })
        drift_items.sort(key=lambda x: -abs(x["shift"]))
        feature_drift = {
            "top_shifts": drift_items[:5],
            "max_shift": round(max(abs(d["shift"]) for d in drift_items), 4) if drift_items else 0,
            "top_feature_real": list(imp_b_dict.keys())[0] if imp_b_dict else None,
            "top_feature_mixed": list(imp_c_dict.keys())[0] if imp_c_dict else None,
            "top_feature_changed": list(imp_b_dict.keys())[0] != list(imp_c_dict.keys())[0] if imp_b_dict and imp_c_dict else False,
        }

    # ═══════════════════════════════════════
    # RED FLAGS
    # ═══════════════════════════════════════
    red_flags = []

    # Flag 1: precision high but median_return <= 0
    for test_name, test_result in results.items():
        if isinstance(test_result, dict) and "error" not in test_result:
            if test_result.get("precision_top10", 0) > 0.7 and test_result.get("median_return", 0) <= 0:
                red_flags.append(f"[{test_name}] precision={test_result['precision_top10']} but median_return={test_result['median_return']}% — illusory accuracy")

    # Flag 2: profit_factor drops in mixed vs real-only
    b_pf = results.get("B_real_only", {}).get("profit_factor", 0) if isinstance(results.get("B_real_only"), dict) else 0
    c_pf = results.get("C_mixed_70_30", {}).get("profit_factor", 0) if isinstance(results.get("C_mixed_70_30"), dict) else 0
    if b_pf > 0 and c_pf > 0 and c_pf < b_pf * 0.8:
        red_flags.append(f"Profit factor DROPS in mixed ({c_pf}) vs real-only ({b_pf}) — synthetic is harmful")

    # Flag 3: confidence 0.9+ is NOT the best bucket
    if isinstance(confidence_buckets_real, dict) and "buckets" in confidence_buckets_real:
        buckets = confidence_buckets_real["buckets"]
        valid_buckets = [b for b in buckets if b["win_rate"] is not None and b["count"] > 0]
        if len(valid_buckets) >= 2:
            top_bucket = valid_buckets[0]  # 0.9+
            if top_bucket["bucket"] == "0.9+" and top_bucket["win_rate"] is not None:
                best_bucket = max(valid_buckets, key=lambda b: b["win_rate"])
                if best_bucket["bucket"] != "0.9+":
                    red_flags.append(f"Confidence 0.9+ win_rate={top_bucket['win_rate']} is NOT best (best: {best_bucket['bucket']}={best_bucket['win_rate']}) — miscalibrated")

    # Flag 4: ret_1h becomes top feature in mixed (simple feature gaining importance = overfit)
    if feature_drift and feature_drift.get("top_feature_changed"):
        if feature_drift.get("top_feature_mixed", "").startswith("f_ret_"):
            red_flags.append(f"Top feature shifted to {feature_drift['top_feature_mixed']} in mixed — synthetic amplifies simple price features")

    # Flag 5: top3_dep increases in mixed
    b_top3 = actor_stats.get("B_real_only", {}).get("top3_dep", 0)
    c_top3 = actor_stats.get("C_mixed_70_30", {}).get("top3_dep", 0)
    if b_top3 > 0 and c_top3 > b_top3 * 1.1:
        red_flags.append(f"Actor top3_dep INCREASES in mixed ({c_top3}) vs real ({b_top3}) — reject mixed")

    # ═══════════════════════════════════════
    # DECISION LOGIC
    # ═══════════════════════════════════════
    decision = _make_decision(results, confidence_buckets_real, actor_stats, red_flags)

    return {
        "ok": True,
        "data_summary": {
            "total_samples": len(all_samples),
            "real_samples": len(real_samples),
            "synthetic_samples": len(synth_samples),
            "real_pct": round(len(real_samples) / len(all_samples) * 100, 1),
            "live_holdout_samples": len(live_holdout),
            "holdout_cutoff": holdout_cutoff.isoformat(),
        },
        "tests": results,
        "confidence_buckets_real": confidence_buckets_real,
        "actor_stats": actor_stats,
        "feature_importance_drift": feature_drift,
        "red_flags": red_flags,
        "decision": decision,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def _make_decision(results, confidence_buckets, actor_stats, red_flags):
    """Strict decision logic: use_real_only | use_mixed | use_curriculum."""
    b = results.get("B_real_only", {})
    c = results.get("C_mixed_70_30", {})
    d = results.get("D_live_holdout", {})

    # If tests failed to run
    if isinstance(b, dict) and "error" in b:
        return {
            "action": "insufficient_data",
            "reason": "Cannot run Test B (real-only). Need more real data.",
            "recommendation": "Run Twitter ingestion to collect 50+ real samples."
        }

    if isinstance(d, dict) and "error" in d:
        return {
            "action": "insufficient_data_for_d",
            "reason": "Cannot run Test D (live holdout). Need fresh real data from last 3-5 days.",
            "recommendation": "Run Twitter ingestion, wait for price data, re-run validation.",
            "preliminary": _preliminary_decision(b, c, red_flags),
        }

    # ─── Hard reject mixed ───
    d_avg = d.get("avg_return", 0)
    d_median = d.get("median_return", 0)
    d_dd = d.get("max_drawdown", 0)

    b_avg = b.get("avg_return", 0)
    b_median = b.get("median_return", 0)
    b_dd = b.get("max_drawdown", 0)

    # Mixed metrics (if available)
    c_avg = c.get("avg_return", 0) if isinstance(c, dict) and "error" not in c else None

    # Check confidence monotonicity
    conf_mono = True
    if isinstance(confidence_buckets, dict) and "monotonic" in confidence_buckets:
        conf_mono = confidence_buckets["monotonic"]

    # ❌ REJECT mixed if:
    reject_reasons = []
    if isinstance(c, dict) and "error" not in c:
        if c.get("avg_return", 0) < b_avg:
            reject_reasons.append(f"mixed avg_return ({c['avg_return']}) < real ({b_avg})")
        if c.get("median_return", 0) < b_median:
            reject_reasons.append(f"mixed median_return ({c['median_return']}) < real ({b_median})")
        if c.get("max_drawdown", 0) < b_dd:  # more negative = worse
            reject_reasons.append(f"mixed drawdown ({c['max_drawdown']}) worse than real ({b_dd})")
        if not conf_mono:
            reject_reasons.append("confidence monotonicity broken")

    if len(red_flags) >= 2:
        reject_reasons.append(f"{len(red_flags)} red flags triggered")

    if reject_reasons:
        return {
            "action": "use_real_only",
            "reason": "Mixed data rejected: " + "; ".join(reject_reasons),
            "test_d_metrics": {
                "avg_return": d_avg,
                "median_return": d_median,
                "profit_factor": d.get("profit_factor", 0),
                "max_drawdown": d_dd,
            },
            "confidence": "high" if d_avg > 0 and d.get("profit_factor", 0) > 1 else "low",
        }

    # ✅ ACCEPT mixed if D is better
    if c_avg is not None and c_avg > b_avg and d_avg > 0 and d.get("profit_factor", 0) > 1 and conf_mono:
        return {
            "action": "use_mixed",
            "reason": "Mixed improves metrics without degrading quality",
            "test_d_metrics": {
                "avg_return": d_avg,
                "median_return": d_median,
                "profit_factor": d.get("profit_factor", 0),
                "max_drawdown": d_dd,
            },
            "confidence": "high",
        }

    # ⚖️ Edge case: curriculum
    return {
        "action": "use_curriculum",
        "reason": "Marginal case — use curriculum learning: train real first, then add synthetic with low weight",
        "curriculum_config": {
            "phase1_epochs": "1-3 (real only)",
            "phase2_epochs": "4-6 (add synthetic, weight 0.2-0.3)",
        },
        "test_d_metrics": {
            "avg_return": d_avg,
            "median_return": d_median,
            "profit_factor": d.get("profit_factor", 0),
            "max_drawdown": d_dd,
        },
        "confidence": "medium",
    }


def _preliminary_decision(b, c, red_flags):
    """Preliminary decision when Test D can't run."""
    if isinstance(b, dict) and "error" not in b:
        if b.get("avg_return", 0) > 0 and b.get("profit_factor", 0) > 1:
            return "real-only looks promising (need Test D to confirm)"
        else:
            return "real-only metrics are weak — need more data"
    return "insufficient_data"
