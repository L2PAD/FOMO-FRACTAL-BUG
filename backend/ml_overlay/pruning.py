"""
Feature Importance Stability Analysis & Pruning Pipeline.

Runs permutation importance across walk-forward folds,
computes stability metrics, prunes unstable/low-value features,
retrains models, and generates comparison report.
"""

import json
import os
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from ml_overlay.config import FEATURES, WALK_FORWARD_WINDOWS, HORIZONS
from ml_overlay.data.price_provider import get_ohlcv
from ml_overlay.data.dataset_builder import build_dataset
from ml_overlay.importance import permutation_importance_fold
from ml_overlay.model.train import train_model, predict
from ml_overlay.model.walk_forward import evaluate_fold


ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def _run_importance_all_folds(dataset, horizon_key):
    """Compute permutation importance for all folds."""
    fold_results = []
    for window in WALK_FORWARD_WINDOWS:
        fold_id = window["test_start"][:4]
        print(f"    Fold {fold_id}...", end=" ")
        try:
            imp = permutation_importance_fold(dataset, window, horizon_key, n_repeats=5)
            if imp:
                fold_results.append({
                    "foldId": fold_id,
                    "trainEnd": window["train_end"],
                    "testStart": window["test_start"],
                    "features": imp,
                })
                print(f"OK ({len(imp)} features)")
            else:
                print("SKIP (no data)")
        except Exception as e:
            print(f"ERROR: {e}")
    return fold_results


def _compute_stability(fold_results, features):
    """Compute stability metrics per feature."""
    stability = {}
    for feat in features:
        means = []
        for fold in fold_results:
            if feat in fold["features"]:
                means.append(fold["features"][feat]["mean"])

        if not means:
            stability[feat] = {
                "meanImportance": 0,
                "stdImportance": 0,
                "stabilityScore": 0,
                "foldValues": [],
            }
            continue

        mean_imp = float(np.mean(means))
        std_imp = float(np.std(means))
        stab = mean_imp / (std_imp + 1e-6)

        stability[feat] = {
            "meanImportance": round(mean_imp, 6),
            "stdImportance": round(std_imp, 6),
            "stabilityScore": round(stab, 3),
            "foldValues": [round(m, 6) for m in means],
        }

    return stability


def _apply_pruning(stability, features):
    """
    Apply pruning rules:
    - mean importance < percentile_30 -> prune
    - stability < percentile_25 -> prune
    - std > percentile_80 -> prune
    - single-fold spike (importance >> mean in one fold only) -> prune
    """
    vals = list(stability.values())
    means = [v["meanImportance"] for v in vals]
    stds = [v["stdImportance"] for v in vals]
    stabs = [v["stabilityScore"] for v in vals]

    p30_mean = np.percentile(means, 30) if means else 0
    p25_stab = np.percentile(stabs, 25) if stabs else 0
    p80_std = np.percentile(stds, 80) if stds else float("inf")

    selected = []
    pruned = []

    for feat in features:
        s = stability[feat]
        reasons = []

        if s["meanImportance"] < p30_mean:
            reasons.append("low_importance")
        if s["stabilityScore"] < p25_stab:
            reasons.append("low_stability")
        if s["stdImportance"] > p80_std:
            reasons.append("high_variance")

        # Single-fold spike check
        fv = s["foldValues"]
        if len(fv) >= 2:
            max_val = max(fv)
            others = [v for v in fv if v != max_val]
            if others and max_val > 0 and np.mean(others) > 0:
                spike_ratio = max_val / (np.mean(others) + 1e-8)
                if spike_ratio > 5.0:
                    reasons.append("single_fold_spike")

        if reasons:
            pruned.append({"name": feat, "reasons": reasons, **s})
        else:
            selected.append({"name": feat, **s})

    # Sort selected by stability (descending)
    selected.sort(key=lambda x: -x["stabilityScore"])
    pruned.sort(key=lambda x: x["meanImportance"])

    return selected, pruned


def _walk_forward_with_features(dataset, horizon_key, feature_list):
    """Run walk-forward evaluation with a specific feature set."""
    results = []
    for window in WALK_FORWARD_WINDOWS:
        train_end = window["train_end"]
        test_start = window["test_start"]
        test_end = window["test_end"]
        cap = HORIZONS[horizon_key]["cap"]

        mask = dataset.index <= pd.Timestamp(train_end)
        train = dataset[mask]

        if len(train) < 500:
            continue

        from ml_overlay.config import LGBM_PARAMS
        import lightgbm as lgb

        X_train = train[feature_list].values
        y_train = train["y"].values

        model = lgb.LGBMRegressor(**LGBM_PARAMS)
        model.fit(X_train, y_train)

        test_mask = (dataset.index >= pd.Timestamp(test_start)) & (dataset.index <= pd.Timestamp(test_end))
        test = dataset[test_mask]
        if len(test) < 10:
            continue

        X_test = test[feature_list].values
        y_test = test["y"].values
        r_rule = test["r_rule"].values
        r_real = test["r_real"].values

        y_hat = model.predict(X_test)
        y_hat_clipped = np.clip(y_hat, -cap, cap)
        r_final = r_rule + y_hat_clipped

        mae_residual = float(np.mean(np.abs(y_hat_clipped - y_test)))
        mae_baseline = float(np.mean(np.abs(y_test)))
        err_rule = float(np.mean(np.abs(r_real - r_rule)))
        err_final = float(np.mean(np.abs(r_real - r_final)))

        dir_real = np.sign(r_real)
        dir_rule = np.sign(r_rule)
        dir_final = np.sign(r_final)

        dir_hit_rule = float(np.mean(dir_rule == dir_real)) * 100
        dir_hit_final = float(np.mean(dir_final == dir_real)) * 100

        flips = int(np.sum(np.diff(np.sign(r_final)) != 0))
        flip_rate = flips / max(1, len(r_final) - 1) * 100

        results.append({
            "fold": window["test_start"][:4],
            "testRows": len(test),
            "mae_baseline": round(mae_baseline, 6),
            "mae_residual": round(mae_residual, 6),
            "mae_improvement_pct": round((mae_baseline - mae_residual) / mae_baseline * 100 if mae_baseline > 0 else 0, 2),
            "dir_hit_rule": round(dir_hit_rule, 1),
            "dir_hit_final": round(dir_hit_final, 1),
            "dir_improvement": round(dir_hit_final - dir_hit_rule, 1),
            "err_rule": round(err_rule, 6),
            "err_final": round(err_final, 6),
            "improvement_pct": round((err_rule - err_final) / err_rule * 100 if err_rule > 0 else 0, 2),
            "flip_rate": round(float(flip_rate), 1),
        })

    return results


def run_full_pruning_pipeline():
    """
    Full A1 pipeline:
    1. Build datasets
    2. Compute importance per fold
    3. Calculate stability
    4. Prune features
    5. Retrain with pruned features
    6. Compare before/after
    7. Generate artifacts
    """
    print("=" * 60)
    print("A1: Feature Importance Stability & Pruning Pipeline")
    print("=" * 60)

    # Step 1: Fetch data and build datasets
    print("\n[Step 1] Fetching OHLCV data...")
    ohlcv = get_ohlcv()
    print(f"  OHLCV: {len(ohlcv)} rows, {ohlcv.index[0]} to {ohlcv.index[-1]}")

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "modelVersion": "overlay_v1.2_pruned",
        "horizons": {},
    }

    selected_features_all = {
        "modelVersion": "overlay_v1.2_pruned",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "horizons": {},
    }

    summary_lines = ["# Overlay Feature Pruning Summary\n"]

    for horizon in ["7D", "30D"]:
        print(f"\n{'='*40}")
        print(f"[{horizon}] Processing...")
        print(f"{'='*40}")

        # Build dataset
        print(f"\n[Step 2] Building {horizon} dataset...")
        dataset = build_dataset(ohlcv, horizon)
        print(f"  Dataset: {len(dataset)} rows")

        # Step 3: Importance per fold (BEFORE pruning)
        print(f"\n[Step 3] Computing importance (ALL {len(FEATURES)} features)...")
        fold_results = _run_importance_all_folds(dataset, horizon)

        if not fold_results:
            print(f"  WARNING: No fold results for {horizon}")
            continue

        # Step 4: Stability metrics
        print(f"\n[Step 4] Computing stability metrics...")
        stability = _compute_stability(fold_results, FEATURES)
        for f in FEATURES:
            s = stability[f]
            print(f"  {f:20s}  mean={s['meanImportance']:8.5f}  std={s['stdImportance']:8.5f}  stability={s['stabilityScore']:8.2f}")

        # Step 5: Pruning
        print(f"\n[Step 5] Applying pruning rules...")
        selected, pruned = _apply_pruning(stability, FEATURES)

        selected_names = [s["name"] for s in selected]
        pruned_names = [p["name"] for p in pruned]
        print(f"  Selected: {len(selected)} features: {selected_names}")
        print(f"  Pruned: {len(pruned)} features: {pruned_names}")
        for p in pruned:
            print(f"    - {p['name']}: {p['reasons']}")

        # Step 6: Walk-forward BEFORE (full features)
        print(f"\n[Step 6] Walk-forward BEFORE pruning (all {len(FEATURES)} features)...")
        wf_before = _walk_forward_with_features(dataset, horizon, FEATURES)
        for r in wf_before:
            print(f"  {r['fold']}: MAE_imp={r['mae_improvement_pct']:.1f}%  DirHit={r['dir_hit_final']:.1f}  Flip={r['flip_rate']:.1f}")

        # Step 7: Walk-forward AFTER (selected features only)
        print(f"\n[Step 7] Walk-forward AFTER pruning ({len(selected_names)} features)...")
        wf_after = _walk_forward_with_features(dataset, horizon, selected_names)
        for r in wf_after:
            print(f"  {r['fold']}: MAE_imp={r['mae_improvement_pct']:.1f}%  DirHit={r['dir_hit_final']:.1f}  Flip={r['flip_rate']:.1f}")

        # Compute deltas
        deltas = []
        for b, a in zip(wf_before, wf_after):
            deltas.append({
                "fold": b["fold"],
                "mae_imp_before": b["mae_improvement_pct"],
                "mae_imp_after": a["mae_improvement_pct"],
                "dir_hit_before": b["dir_hit_final"],
                "dir_hit_after": a["dir_hit_final"],
                "flip_before": b["flip_rate"],
                "flip_after": a["flip_rate"],
                "flip_delta": round(a["flip_rate"] - b["flip_rate"], 1),
                "dir_delta": round(a["dir_hit_final"] - b["dir_hit_final"], 1),
            })

        print(f"\n[Comparison BEFORE vs AFTER]:")
        for d in deltas:
            flip_sym = "down" if d["flip_delta"] < 0 else ("up" if d["flip_delta"] > 0 else "=")
            dir_sym = "up" if d["dir_delta"] > 0 else ("down" if d["dir_delta"] < 0 else "=")
            print(f"  {d['fold']}: Flip {d['flip_before']:.1f} -> {d['flip_after']:.1f} ({flip_sym} {abs(d['flip_delta']):.1f})  DirHit {d['dir_hit_before']:.1f} -> {d['dir_hit_after']:.1f} ({dir_sym} {abs(d['dir_delta']):.1f})")

        # Save to report
        report["horizons"][horizon] = {
            "folds": fold_results,
            "stability": stability,
            "summary": {
                "totalFeatures": len(FEATURES),
                "pruned": len(pruned),
                "selected": len(selected),
            },
            "comparison": {
                "before": wf_before,
                "after": wf_after,
                "deltas": deltas,
            },
        }

        selected_features_all["horizons"][horizon] = {
            "selected": selected_names,
            "pruned": [{"name": p["name"], "reasons": p["reasons"]} for p in pruned],
        }

        # Summary
        avg_flip_delta = np.mean([d["flip_delta"] for d in deltas]) if deltas else 0
        avg_dir_delta = np.mean([d["dir_delta"] for d in deltas]) if deltas else 0
        summary_lines.append(f"## {horizon} Horizon")
        summary_lines.append(f"- Total features: {len(FEATURES)}")
        summary_lines.append(f"- Selected: {len(selected)} ({', '.join(selected_names)})")
        summary_lines.append(f"- Pruned: {len(pruned)}")
        summary_lines.append(f"")
        summary_lines.append(f"### Removed features:")
        for p in pruned:
            summary_lines.append(f"- **{p['name']}**: {', '.join(p['reasons'])}")
        summary_lines.append(f"")
        summary_lines.append(f"### Result:")
        summary_lines.append(f"- Avg FlipRate delta: {avg_flip_delta:+.1f}pp")
        summary_lines.append(f"- Avg DirHit delta: {avg_dir_delta:+.1f}pp")
        summary_lines.append(f"- MAE improvement maintained: {'YES' if all(d['mae_imp_after'] > 0 for d in deltas) else 'CHECK'}")
        summary_lines.append(f"")
        for d in deltas:
            summary_lines.append(f"  {d['fold']}: Flip {d['flip_before']:.1f} -> {d['flip_after']:.1f}  DirHit {d['dir_hit_before']:.1f} -> {d['dir_hit_after']:.1f}")
        summary_lines.append(f"")

    # Write artifacts
    report_path = os.path.join(ARTIFACTS_DIR, "importance_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n[SAVED] {report_path}")

    features_path = os.path.join(ARTIFACTS_DIR, "selected_features.json")
    with open(features_path, "w") as f:
        json.dump(selected_features_all, f, indent=2)
    print(f"[SAVED] {features_path}")

    summary_path = os.path.join(ARTIFACTS_DIR, "pruning_summary.md")
    with open(summary_path, "w") as f:
        f.write("\n".join(summary_lines))
    print(f"[SAVED] {summary_path}")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)

    return report


if __name__ == "__main__":
    run_full_pruning_pipeline()
