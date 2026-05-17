"""
Shadow Evaluation — compare rule vs ML overlay after evaluateAfter.

Rolling evaluation windows (30D/60D) with GO/NO-GO criteria.
"""

import os
import numpy as np
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

# GO/NO-GO thresholds
GO_CRITERIA = {
    "dir_hit_delta_min": -0.5,   # DirHit_final >= DirHit_rule - 0.5pp
    "mae_ratio_max": 0.97,       # MAE_final <= MAE_rule * 0.97
    "flip_delta_max": 3.0,       # FlipRate_final <= FlipRate_rule + 3pp
    "drift_score_max": 0.55,     # DriftScore <= 0.55
}


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def evaluate_shadow_forecasts() -> dict:
    """
    Evaluate shadow overlay predictions that have matured.
    Compares: rule_error vs final_error.
    Writes results to ml_overlay_eval.
    """
    db = _db()
    shadow_col = db["ml_overlay_shadow"]
    eval_col = db["ml_overlay_eval"]
    forecast_col = db["exchange_forecasts"]

    evaluated = 0
    skipped = 0

    # Find unevaluated shadow records
    pending = list(shadow_col.find({"evaluatedShadow": False}))

    for s in pending:
        asset = s["asset"]
        horizon = s["horizon"]
        bucket = s["createdBucket"]

        # Find the matching evaluated forecast
        forecast = forecast_col.find_one({
            "asset": asset,
            "horizon": horizon,
            "createdBucket": bucket,
            "evaluated": True,
        }, {"_id": 0})

        if not forecast:
            skipped += 1
            continue

        outcome = forecast.get("outcome", {})
        real_price = outcome.get("realPrice", 0)
        if not real_price:
            skipped += 1
            continue

        entry = s["entryPrice"]
        r_real = (real_price / entry - 1) if entry > 0 else 0
        r_rule = s["ruleReturn"]
        r_final = s["finalReturnShadow"]

        err_rule = abs(r_real - r_rule)
        err_final = abs(r_real - r_final)
        improvement = (err_rule - err_final) / err_rule * 100 if err_rule > 0 else 0

        dir_real = 1 if r_real > 0 else (-1 if r_real < 0 else 0)
        dir_rule = 1 if r_rule > 0 else (-1 if r_rule < 0 else 0)
        dir_final = 1 if r_final > 0 else (-1 if r_final < 0 else 0)

        eval_doc = {
            "asset": asset,
            "horizon": horizon,
            "createdBucket": bucket,
            "entryPrice": float(entry),
            "realPrice": float(real_price),
            "r_real": round(float(r_real), 6),
            "r_rule": round(float(r_rule), 6),
            "r_final_shadow": round(float(r_final), 6),
            "err_rule": round(float(err_rule), 6),
            "err_final": round(float(err_final), 6),
            "improvement_pct": round(float(improvement), 2),
            "dir_hit_rule": bool(dir_rule == dir_real),
            "dir_hit_final": bool(dir_final == dir_real),
            "dir_rule": int(dir_rule),
            "dir_final": int(dir_final),
            "mlCorrection": float(s.get("mlCorrection", 0)),
            "modelId": s.get("modelId"),
            "evaluatedAt": int(datetime.now(timezone.utc).timestamp() * 1000),
        }

        eval_col.insert_one(eval_doc)

        # Mark shadow as evaluated
        shadow_col.update_one(
            {"_id": s["_id"]},
            {"$set": {"evaluatedShadow": True}},
        )
        evaluated += 1

    return {
        "evaluated": evaluated,
        "skipped": skipped,
        "pending": len(pending),
    }


def compute_rolling_verdict(horizon: str, window_days: int = 30, asset: str = "BTC") -> dict:
    """
    Compute rolling shadow eval metrics and GO/NO-GO verdict.
    Window: last N days of evaluated shadow predictions.
    """
    db = _db()
    eval_col = db["ml_overlay_eval"]

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    cutoff_ms = int(cutoff.timestamp() * 1000)

    docs = list(eval_col.find(
        {"horizon": horizon, "asset": asset, "evaluatedAt": {"$gte": cutoff_ms}},
        {"_id": 0},
    ).sort("createdBucket", -1))

    n = len(docs)
    if n < 3:
        return {
            "horizon": horizon,
            "window": window_days,
            "n": n,
            "verdict": "INSUFFICIENT_DATA",
            "message": f"Need >= 3 evaluated shadows, have {n}",
        }

    # MAE
    mae_rule = np.mean([d["err_rule"] for d in docs])
    mae_final = np.mean([d["err_final"] for d in docs])
    mae_ratio = mae_final / mae_rule if mae_rule > 0 else 1.0

    # DirHit
    dir_hit_rule = np.mean([1 if d["dir_hit_rule"] else 0 for d in docs]) * 100
    dir_hit_final = np.mean([1 if d["dir_hit_final"] else 0 for d in docs]) * 100
    dir_delta = dir_hit_final - dir_hit_rule

    # FlipRate
    dirs_rule = [d.get("dir_rule", 0) for d in docs]
    dirs_final = [d.get("dir_final", 0) for d in docs]
    flip_rule = sum(1 for i in range(1, len(dirs_rule)) if dirs_rule[i] != dirs_rule[i-1]) / max(1, len(dirs_rule) - 1) * 100 if len(dirs_rule) > 1 else 0
    flip_final = sum(1 for i in range(1, len(dirs_final)) if dirs_final[i] != dirs_final[i-1]) / max(1, len(dirs_final) - 1) * 100 if len(dirs_final) > 1 else 0
    flip_delta = flip_final - flip_rule

    # Get current drift score
    drift_score = 0.0
    drift_doc = db["drift_snapshots"].find_one(
        {"horizon": horizon, "asset": asset},
        {"_id": 0, "driftScore": 1},
        sort=[("ts", DESCENDING)],
    )
    if drift_doc:
        drift_score = drift_doc.get("driftScore", 0)

    # GO/NO-GO checks
    checks = {
        "dir_hit_ok": dir_delta >= GO_CRITERIA["dir_hit_delta_min"],
        "mae_ok": mae_ratio <= GO_CRITERIA["mae_ratio_max"],
        "flip_ok": flip_delta <= GO_CRITERIA["flip_delta_max"],
        "drift_ok": drift_score <= GO_CRITERIA["drift_score_max"],
    }

    fail_count = sum(1 for v in checks.values() if not v)
    if fail_count == 0:
        verdict = "SHADOW_OK"
    elif fail_count <= 1:
        verdict = "SHADOW_WARN"
    else:
        verdict = "SHADOW_FAIL"

    return {
        "horizon": horizon,
        "window": window_days,
        "n": n,
        "verdict": verdict,
        "metrics": {
            "mae_rule": round(float(mae_rule), 6),
            "mae_final": round(float(mae_final), 6),
            "mae_ratio": round(float(mae_ratio), 4),
            "mae_improvement_pct": round(float((1 - mae_ratio) * 100), 2),
            "dir_hit_rule": round(float(dir_hit_rule), 1),
            "dir_hit_final": round(float(dir_hit_final), 1),
            "dir_delta": round(float(dir_delta), 1),
            "flip_rule": round(float(flip_rule), 1),
            "flip_final": round(float(flip_final), 1),
            "flip_delta": round(float(flip_delta), 1),
            "drift_score": round(float(drift_score), 4),
        },
        "checks": checks,
    }


def get_shadow_eval_summary() -> dict:
    """
    Aggregate shadow eval results with rolling verdicts.
    Returns rolling metrics for each horizon at 30D and 60D windows.
    """
    db = _db()
    eval_col = db["ml_overlay_eval"]

    summary = {}
    for h in ["7D", "30D"]:
        docs = list(eval_col.find({"horizon": h}, {"_id": 0}).sort("createdBucket", -1).limit(60))
        if not docs:
            summary[h] = {
                "n": 0,
                "message": "No evaluated shadow data yet",
                "rolling_30d": compute_rolling_verdict(h, 30),
                "rolling_60d": compute_rolling_verdict(h, 60),
            }
            continue

        n = len(docs)
        mae_rule = sum(d["err_rule"] for d in docs) / n
        mae_final = sum(d["err_final"] for d in docs) / n
        dir_hit_rule = sum(1 for d in docs if d["dir_hit_rule"]) / n * 100
        dir_hit_final = sum(1 for d in docs if d["dir_hit_final"]) / n * 100
        avg_improvement = sum(d["improvement_pct"] for d in docs) / n

        summary[h] = {
            "n": n,
            "mae_rule": round(mae_rule, 6),
            "mae_final": round(mae_final, 6),
            "mae_improvement": round((mae_rule - mae_final) / mae_rule * 100, 2) if mae_rule > 0 else 0,
            "dir_hit_rule": round(dir_hit_rule, 1),
            "dir_hit_final": round(dir_hit_final, 1),
            "dir_delta": round(dir_hit_final - dir_hit_rule, 1),
            "avg_improvement": round(avg_improvement, 2),
            "rolling_30d": compute_rolling_verdict(h, 30),
            "rolling_60d": compute_rolling_verdict(h, 60),
        }

    return summary
