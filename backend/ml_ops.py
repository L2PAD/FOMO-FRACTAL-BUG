"""
ML Operations Pipeline — Production-grade monitoring, retrain, shadow, promotion, rollback.

Collections:
  ml_model_registry    — model versions with statuses (candidate/shadow/active/rolled_back/archived)
  ml_daily_metrics     — daily performance snapshot
  ml_drift_results     — feature/label/source drift (PSI)
  ml_shadow_predictions — parallel prod vs shadow predictions
  ml_signal_log        — individual signal outcomes with result tracking
  ml_retrain_jobs      — retrain history
  ml_promotion_log     — promotion/rollback history
  ml_data_health       — daily data pipeline health
  ml_calibration       — predicted vs actual calibration buckets
"""

import os
import pickle
import numpy as np
from datetime import datetime, timezone, timedelta
from collections import Counter
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

_client = None
_db = None


def get_db():
    global _client, _db
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URL)
        _db = _client[DB_NAME]
    return _db


# ─── THRESHOLDS ───
RETRAIN_MIN_NEW_SAMPLES = 300
RETRAIN_INTERVAL_DAYS = 7
DRIFT_DANGER_PSI = 0.25
DRIFT_WARNING_PSI = 0.10
KILL_MIN_HIT_RATE = 0.55
KILL_MAX_DRAWDOWN = -0.08
SHADOW_MIN_EVAL = 100
PROMOTION_PRECISION_DELTA = 0.03
SHADOW_WIN_STREAK_DAYS = 3

# Data health thresholds
MIN_SIGNALS_PER_DAY = 100
MIN_ACTORS_PER_DAY = 20
MIN_TOKENS_PER_DAY = 15
MIN_LABELED_PER_DAY = 20


# ─── MODEL REGISTRY ───
async def register_model(model_key, stage, metrics, feature_importance=None):
    """Register a model version in ml_model_registry."""
    db = get_db()
    doc = {
        "model_key": model_key,
        "status": "active" if stage == "production" else stage,
        "stage": stage,
        "metrics": metrics,
        "feature_importance": feature_importance or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "promoted_at": None,
        "rolled_back_at": None,
    }
    await db.ml_model_registry.update_one(
        {"model_key": model_key},
        {"$set": doc},
        upsert=True,
    )
    return doc


async def get_active_model():
    """Get the current active (production) model."""
    db = get_db()
    return await db.ml_model_registry.find_one(
        {"status": "active"}, {"_id": 0}
    )


# ─── TIME-BASED VALIDATION ───
def time_split(samples, train_ratio=0.70, valid_ratio=0.15):
    """Split samples by time: train (oldest) → valid → test (newest)."""
    sorted_samples = sorted(samples, key=lambda s: s.get("timestamp", ""))
    n = len(sorted_samples)
    train_end = int(n * train_ratio)
    valid_end = int(n * (train_ratio + valid_ratio))
    return sorted_samples[:train_end], sorted_samples[train_end:valid_end], sorted_samples[valid_end:]


# ─── RETRAIN JOB ───
async def retrain_job():
    """Full retrain pipeline: time-split → train → validate → register as candidate."""
    from signal_pipeline import _build_feature_matrix
    from xgboost import XGBClassifier
    from sklearn.metrics import precision_score
    
    db = get_db()
    
    samples = await db.signal_training_dataset_v2.find({}, {"_id": 0}).to_list(length=20000)
    if len(samples) < 100:
        return {"ok": False, "error": f"Not enough samples: {len(samples)}", "action": "skip"}
    
    train_set, valid_set, test_set = time_split(samples)
    
    if len(train_set) < 50 or len(test_set) < 10:
        return {"ok": False, "error": "Splits too small", "action": "skip"}
    
    X_train, y_train, meta_train, feature_names = _build_feature_matrix(train_set)
    X_valid, y_valid, meta_valid, _ = _build_feature_matrix(valid_set)
    X_test, y_test, meta_test, _ = _build_feature_matrix(test_set)
    
    pos = int(y_train.sum())
    neg = len(y_train) - pos
    scale_pos = neg / max(pos, 1)
    
    model = XGBClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.1,
        scale_pos_weight=scale_pos, eval_metric="logloss",
        use_label_encoder=False, random_state=42,
    )
    model.fit(X_train, y_train)
    
    # Evaluate on TEST set (unseen, newest data)
    y_proba_test = model.predict_proba(X_test)[:, 1]
    # Trading metrics on test set
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
    profit_factor = wins / losses if losses > 0 else float('inf')
    
    top_actual = [y_test[i] for i in top_idx]
    precision_top = sum(top_actual) / len(top_actual) if top_actual else 0
    hit_rate = top_hits / len(top_rets) if top_rets else 0
    
    importances = dict(zip(feature_names, model.feature_importances_.tolist()))
    importances_sorted = dict(sorted(importances.items(), key=lambda x: -x[1]))
    
    version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    model_key = f"signal_quality_xgb_{version}"
    
    metrics = {
        "precision_top10": round(precision_top, 4),
        "hit_rate": round(hit_rate, 4),
        "avg_return": round(top_avg * 100, 4),
        "median_return": round(median_ret * 100, 4),
        "max_drawdown": round(max_dd * 100, 4),
        "profit_factor": round(profit_factor, 4),
        "alpha_vs_baseline": round((top_avg - baseline_avg) * 100, 4),
        "test_samples": len(test_set),
        "train_samples": len(train_set),
    }
    
    # Save model binary
    model_bytes = pickle.dumps(model)
    await db.signal_models.update_one(
        {"name": model_key},
        {"$set": {
            "name": model_key, "type": "xgboost_binary", "target": "tradeable",
            "features": feature_names, "model_binary": model_bytes,
            "metrics": metrics, "feature_importance": importances_sorted,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    
    # Register as candidate
    await register_model(model_key, "candidate", metrics, importances_sorted)
    
    # Log retrain job
    await db.ml_retrain_jobs.insert_one({
        "model_key": model_key, "status": "completed",
        "trigger": "manual", "samples": len(samples),
        "splits": {"train": len(train_set), "valid": len(valid_set), "test": len(test_set)},
        "metrics": metrics,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    
    return {
        "ok": True,
        "model_key": model_key,
        "stage": "candidate",
        "splits": {"train": len(train_set), "valid": len(valid_set), "test": len(test_set)},
        "metrics": metrics,
        "feature_importance_top5": dict(list(importances_sorted.items())[:5]),
    }


# ─── DAILY METRICS JOB ───
async def compute_daily_metrics():
    """Compute and store daily ML performance metrics."""
    db = get_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    active = await get_active_model()
    model_key = active["model_key"] if active else "unknown"
    
    # Get recent signals
    samples = await db.signal_training_dataset_v2.find({}, {"_id": 0}).to_list(length=20000)
    
    total = len(samples)
    if total == 0:
        return {"ok": True, "message": "No data"}
    
    tradeable = [s for s in samples if s.get("tradeable")]
    tradeable_rets = [s["rel_ret_24h"] for s in tradeable if s.get("rel_ret_24h") is not None]
    
    label_dist = Counter(s.get("label_4class") for s in samples)
    
    hit_rate = sum(1 for r in tradeable_rets if r > 0) / len(tradeable_rets) if tradeable_rets else 0
    avg_ret = sum(tradeable_rets) / len(tradeable_rets) if tradeable_rets else 0
    median_ret = float(np.median(tradeable_rets)) if tradeable_rets else 0
    
    # Max drawdown
    cum, peak, max_dd = 0, 0, 0
    for r in sorted(tradeable_rets):
        cum += r
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)
    
    wins = sum(r for r in tradeable_rets if r > 0)
    losses = abs(sum(r for r in tradeable_rets if r < 0))
    profit_factor = wins / losses if losses > 0 else 0
    
    doc = {
        "date": today,
        "model_key": model_key,
        "n_signals": total,
        "n_tradeable": len(tradeable),
        "hit_rate": round(hit_rate, 4),
        "avg_return": round(avg_ret * 100, 4),
        "median_return": round(median_ret * 100, 4),
        "max_drawdown": round(max_dd * 100, 4),
        "profit_factor": round(profit_factor, 4),
        "entry_ratio": round(label_dist.get("ENTRY", 0) / total, 4),
        "follow_ratio": round(label_dist.get("FOLLOW", 0) / total, 4),
        "exit_ratio": round(label_dist.get("EXIT", 0) / total, 4),
        "noise_ratio": round(label_dist.get("NOISE", 0) / total, 4),
        "unique_actors": len(set(s.get("actor_handle") for s in samples)),
        "unique_tokens": len(set(s.get("token") for s in samples)),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.ml_daily_metrics.update_one(
        {"date": today}, {"$set": doc}, upsert=True
    )
    return {"ok": True, "metrics": doc}


# ─── DRIFT DETECTION ───
def _compute_psi(expected, actual, bins=10):
    """Population Stability Index between two distributions."""
    expected = np.array(expected, dtype=float)
    actual = np.array(actual, dtype=float)
    
    if len(expected) < 10 or len(actual) < 10:
        return 0.0
    
    breakpoints = np.percentile(expected, np.linspace(0, 100, bins + 1))
    breakpoints = np.unique(breakpoints)
    
    expected_hist = np.histogram(expected, bins=breakpoints)[0] + 1
    actual_hist = np.histogram(actual, bins=breakpoints)[0] + 1
    
    expected_pct = expected_hist / expected_hist.sum()
    actual_pct = actual_hist / actual_hist.sum()
    
    psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return round(float(psi), 6)


async def compute_drift():
    """Compute feature/label/source drift using PSI."""
    db = get_db()
    
    samples = await db.signal_training_dataset_v2.find({}, {"_id": 0}).to_list(length=20000)
    if len(samples) < 100:
        return {"ok": True, "message": "Not enough data for drift"}
    
    # Split by time: first 70% = reference, last 30% = current
    sorted_s = sorted(samples, key=lambda s: s.get("timestamp", ""))
    split = int(len(sorted_s) * 0.7)
    ref = sorted_s[:split]
    cur = sorted_s[split:]
    
    # Feature drift
    drift_features = ["f_actor_hit_rate", "f_coord_unique_actors_1h", "f_coord_density", "f_ret_1h"]
    feature_drift = {}
    for feat in drift_features:
        ref_vals = [s.get(feat, 0) for s in ref if s.get(feat) is not None]
        cur_vals = [s.get(feat, 0) for s in cur if s.get(feat) is not None]
        psi = _compute_psi(ref_vals, cur_vals)
        status = "OK" if psi < DRIFT_WARNING_PSI else "WARNING" if psi < DRIFT_DANGER_PSI else "DANGER"
        feature_drift[feat] = {"psi": psi, "status": status}
    
    # Label drift
    ref_labels = Counter(s.get("label_binary") for s in ref)
    cur_labels = Counter(s.get("label_binary") for s in cur)
    ref_trade_pct = ref_labels.get("TRADEABLE", 0) / len(ref)
    cur_trade_pct = cur_labels.get("TRADEABLE", 0) / len(cur)
    label_drift_pct = abs(cur_trade_pct - ref_trade_pct)
    
    # Source drift
    ref_actors = len(set(s.get("actor_handle") for s in ref))
    cur_actors = len(set(s.get("actor_handle") for s in cur))
    ref_tokens = len(set(s.get("token") for s in ref))
    cur_tokens = len(set(s.get("token") for s in cur))
    
    # Overall drift score
    psi_values = [v["psi"] for v in feature_drift.values()]
    overall_drift = sum(psi_values) / len(psi_values) if psi_values else 0
    danger_count = sum(1 for v in feature_drift.values() if v["status"] == "DANGER")
    
    overall_status = "OK"
    if danger_count >= 2:
        overall_status = "DANGER"
    elif any(v["status"] == "WARNING" for v in feature_drift.values()):
        overall_status = "WARNING"
    
    doc = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "feature_drift": feature_drift,
        "label_drift": {
            "ref_tradeable_pct": round(ref_trade_pct, 4),
            "cur_tradeable_pct": round(cur_trade_pct, 4),
            "shift": round(label_drift_pct, 4),
        },
        "source_drift": {
            "ref_actors": ref_actors, "cur_actors": cur_actors,
            "ref_tokens": ref_tokens, "cur_tokens": cur_tokens,
        },
        "overall_drift_score": round(overall_drift, 4),
        "overall_status": overall_status,
        "danger_features": danger_count,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.ml_drift_results.update_one(
        {"date": doc["date"]}, {"$set": doc}, upsert=True
    )
    return {"ok": True, "drift": doc}


# ─── KILL SWITCH / ROLLBACK ───
async def check_kill_switch():
    """Check if active model should be killed based on performance."""
    active = await get_active_model()
    if not active:
        return {"ok": True, "action": "none", "reason": "No active model"}
    
    metrics = active.get("metrics", {})
    hit_rate = metrics.get("hit_rate", 1.0)
    avg_ret = metrics.get("avg_return", 1.0)
    max_dd = metrics.get("max_drawdown", 0)
    
    reasons = []
    if hit_rate < KILL_MIN_HIT_RATE:
        reasons.append(f"hit_rate {hit_rate} < {KILL_MIN_HIT_RATE}")
    if avg_ret <= 0:
        reasons.append(f"avg_return {avg_ret} <= 0")
    if max_dd < KILL_MAX_DRAWDOWN * 100:
        reasons.append(f"drawdown {max_dd}% < {KILL_MAX_DRAWDOWN * 100}%")
    
    if reasons:
        return {"ok": True, "action": "rollback_needed", "reasons": reasons, "model": active["model_key"]}
    
    return {"ok": True, "action": "none", "model": active["model_key"], "status": "healthy"}


async def rollback_model():
    """Rollback active model to previous stable version."""
    db = get_db()
    
    active = await get_active_model()
    if not active:
        return {"ok": False, "error": "No active model to rollback"}
    
    # Mark current as rolled back
    await db.ml_model_registry.update_one(
        {"model_key": active["model_key"]},
        {"$set": {"status": "rolled_back", "rolled_back_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Find previous active model (most recent non-rolled-back, non-current)
    prev = await db.ml_model_registry.find_one(
        {"status": {"$in": ["archived", "rolled_back"]}, "model_key": {"$ne": active["model_key"]}},
        {"_id": 0},
        sort=[("created_at", -1)]
    )
    
    if prev:
        await db.ml_model_registry.update_one(
            {"model_key": prev["model_key"]},
            {"$set": {"status": "active", "stage": "production"}}
        )
        new_active = prev["model_key"]
    else:
        new_active = None
    
    await db.ml_promotion_log.insert_one({
        "action": "rollback",
        "from_model": active["model_key"],
        "to_model": new_active,
        "reason": "kill_switch or manual",
        "at": datetime.now(timezone.utc).isoformat(),
    })
    
    return {"ok": True, "rolled_back": active["model_key"], "restored": new_active}


# ─── PROMOTION ───
async def promote_model(model_key):
    """Promote a candidate/shadow model to active (production)."""
    db = get_db()
    
    candidate = await db.ml_model_registry.find_one({"model_key": model_key}, {"_id": 0})
    if not candidate:
        return {"ok": False, "error": f"Model {model_key} not found"}
    
    active = await get_active_model()
    
    # Validate promotion rules
    if active:
        active_metrics = active.get("metrics", {})
        cand_metrics = candidate.get("metrics", {})
        
        checks = {
            "precision_better": cand_metrics.get("precision_top10", 0) >= active_metrics.get("precision_top10", 0) + PROMOTION_PRECISION_DELTA,
            "return_better": cand_metrics.get("avg_return", 0) >= active_metrics.get("avg_return", 0),
            "drawdown_ok": cand_metrics.get("max_drawdown", -100) >= active_metrics.get("max_drawdown", -100),
        }
        
        if not all(checks.values()):
            return {"ok": False, "error": "Candidate does not meet promotion criteria", "checks": checks}
        
        # Archive current active
        await db.ml_model_registry.update_one(
            {"model_key": active["model_key"]},
            {"$set": {"status": "archived", "stage": "archived"}}
        )
    
    # Promote candidate
    await db.ml_model_registry.update_one(
        {"model_key": model_key},
        {"$set": {"status": "active", "stage": "production", "promoted_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    await db.ml_promotion_log.insert_one({
        "action": "promote",
        "from_model": active["model_key"] if active else None,
        "to_model": model_key,
        "at": datetime.now(timezone.utc).isoformat(),
    })
    
    return {"ok": True, "promoted": model_key, "archived": active["model_key"] if active else None}


# ─── DATA HEALTH ───
async def compute_data_health():
    """Check data pipeline health."""
    db = get_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    signals = await db.actor_signal_events.count_documents({})
    enriched = await db.actor_signal_events.count_documents({"enriched": True})
    dataset = await db.signal_training_dataset_v2.count_documents({})
    tradeable = await db.signal_training_dataset_v2.count_documents({"tradeable": True})
    
    actors = await db.actor_intelligence.count_documents({})
    
    # Check for missing data
    no_price = await db.actor_signal_events.count_documents({"enriched": True, "price.has_price": False})
    missing_price_pct = no_price / max(enriched, 1)
    
    doc = {
        "date": today,
        "total_signals": signals,
        "enriched_signals": enriched,
        "dataset_size": dataset,
        "tradeable_count": tradeable,
        "tradeable_pct": round(tradeable / max(dataset, 1), 4),
        "actor_profiles": actors,
        "missing_price_pct": round(missing_price_pct, 4),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.ml_data_health.update_one(
        {"date": today}, {"$set": doc}, upsert=True
    )
    return {"ok": True, "health": doc}


# ─── ML STATUS (aggregate view) ───
async def get_ml_status():
    """Get complete ML system status."""
    db = get_db()
    
    active = await get_active_model()
    latest_metrics = await db.ml_daily_metrics.find_one({}, {"_id": 0}, sort=[("date", -1)])
    latest_drift = await db.ml_drift_results.find_one({}, {"_id": 0}, sort=[("date", -1)])
    latest_health = await db.ml_data_health.find_one({}, {"_id": 0}, sort=[("date", -1)])
    latest_retrain = await db.ml_retrain_jobs.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    
    # Count models by status
    model_counts = {}
    async for doc in db.ml_model_registry.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
        model_counts[doc["_id"]] = doc["count"]
    
    kill_check = await check_kill_switch()
    
    return _sanitize_doc({
        "ok": True,
        "active_model": active.get("model_key") if active else None,
        "active_metrics": active.get("metrics") if active else None,
        "model_counts": model_counts,
        "latest_daily_metrics": latest_metrics,
        "drift": {
            "status": latest_drift.get("overall_status") if latest_drift else "UNKNOWN",
            "score": latest_drift.get("overall_drift_score") if latest_drift else None,
        },
        "data_health": latest_health,
        "last_retrain": latest_retrain.get("created_at") if latest_retrain else None,
        "kill_switch": kill_check,
    })


# ─── DECISION MAPPER (ML → ACTION + WHY) ───
def map_decision(probability, signal_position, actor_hit_rate=None, coordination_density=None):
    """Convert raw ML probability → actionable decision with explanation.
    
    NEVER expose raw probability to users.
    Returns: {"action": "ENTER"/"FOLLOW"/"WATCH"/"AVOID", "strength": "...", "why": [...]}
    """
    position = (signal_position or "UNKNOWN").upper()
    
    # Decision rules based on user spec
    if probability > 0.80 and position == "EARLY":
        action = "ENTER"
        strength = "STRONG"
    elif probability > 0.70 and position == "EARLY":
        action = "ENTER"
        strength = "MODERATE"
    elif probability > 0.65 and position in ("MID", "EARLY"):
        action = "FOLLOW"
        strength = "MODERATE"
    elif probability > 0.50:
        action = "WATCH"
        strength = "WEAK"
    else:
        action = "AVOID"
        strength = "NO_SIGNAL"
    
    # Build WHY from features
    why = []
    if actor_hit_rate is not None:
        if actor_hit_rate > 0.65:
            why.append("strong actor history")
        elif actor_hit_rate > 0.50:
            why.append("decent actor track record")
        else:
            why.append("weak actor history")
    
    if position == "EARLY":
        why.append("early positioning")
    elif position == "MID":
        why.append("mid-cycle signal")
    elif position == "LATE":
        why.append("late signal — higher risk")
    
    if coordination_density is not None:
        if coordination_density > 0.5:
            why.append("coordinated mentions detected")
        elif coordination_density > 0.2:
            why.append("some coordination")
    
    if not why:
        why.append("insufficient signal data")
    
    return {
        "action": action,
        "strength": strength,
        "why": why,
    }


# ─── SHADOW PREDICTION LOGGING ───
async def log_shadow_prediction(signal_id, token, prod_model_key, shadow_model_key,
                                prod_pred, shadow_pred, actor=None, position=None):
    """Log parallel predictions from production and shadow models."""
    db = get_db()
    doc = {
        "signal_id": signal_id,
        "token": token,
        "prod_model": prod_model_key,
        "shadow_model": shadow_model_key,
        "prod_pred": round(float(prod_pred), 4),
        "shadow_pred": round(float(shadow_pred), 4),
        "prod_decision": map_decision(prod_pred, position)["action"],
        "shadow_decision": map_decision(shadow_pred, position)["action"],
        "actor": actor,
        "position": position,
        "actual_result": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.ml_shadow_predictions.insert_one(doc)
    return {"ok": True, "logged": True}


async def backfill_shadow_outcomes():
    """Update shadow predictions with actual outcomes once returns are known."""
    db = get_db()
    pending = await db.ml_shadow_predictions.find(
        {"actual_result": None},
        {"_id": 0, "signal_id": 1, "token": 1, "timestamp": 1}
    ).to_list(length=5000)
    
    updated = 0
    for p in pending:
        sig = await db.actor_signal_events.find_one(
            {"signal_id": p.get("signal_id"), "enriched": True},
            {"_id": 0, "price": 1}
        )
        if sig and sig.get("price", {}).get("ret_24h") is not None:
            ret = sig["price"]["ret_24h"]
            result = "WIN" if ret > 0 else "LOSS"
            await db.ml_shadow_predictions.update_many(
                {"signal_id": p["signal_id"], "actual_result": None},
                {"$set": {"actual_result": result, "actual_return": round(ret, 6)}}
            )
            updated += 1
    
    return {"ok": True, "updated": updated, "pending": len(pending) - updated}


async def evaluate_shadow():
    """Compare shadow vs production models on evaluated predictions."""
    db = get_db()
    
    evaluated = await db.ml_shadow_predictions.find(
        {"actual_result": {"$ne": None}},
        {"_id": 0}
    ).to_list(length=10000)
    
    if len(evaluated) < SHADOW_MIN_EVAL:
        return {
            "ok": True,
            "status": "not_enough_data",
            "evaluated": len(evaluated),
            "required": SHADOW_MIN_EVAL,
        }
    
    # Compute metrics for each model
    def _model_metrics(preds, docs):
        """Calculate trading metrics for a model's predictions."""
        if not preds:
            return {}
        wins = sum(1 for p, d in zip(preds, docs) if d.get("actual_result") == "WIN")
        rets = [d.get("actual_return", 0) or 0 for d in docs]
        avg_ret = sum(rets) / len(rets) if rets else 0
        
        # Top 10% precision
        sorted_idx = sorted(range(len(preds)), key=lambda i: preds[i], reverse=True)
        top_k = max(int(len(preds) * 0.1), 3)
        top_wins = sum(1 for i in sorted_idx[:top_k] if docs[i].get("actual_result") == "WIN")
        
        cum, peak, max_dd = 0, 0, 0
        for i in sorted_idx[:top_k]:
            r = rets[i] if i < len(rets) else 0
            cum += r
            peak = max(peak, cum)
            max_dd = min(max_dd, cum - peak)
        
        return {
            "hit_rate": round(wins / len(preds), 4) if preds else 0,
            "avg_return": round(avg_ret * 100, 4),
            "precision_top10": round(top_wins / top_k, 4) if top_k > 0 else 0,
            "max_drawdown": round(max_dd * 100, 4),
        }
    
    prod_preds = [e["prod_pred"] for e in evaluated]
    shadow_preds = [e["shadow_pred"] for e in evaluated]
    
    prod_m = _model_metrics(prod_preds, evaluated)
    shadow_m = _model_metrics(shadow_preds, evaluated)
    
    precision_diff = shadow_m.get("precision_top10", 0) - prod_m.get("precision_top10", 0)
    return_diff = shadow_m.get("avg_return", 0) - prod_m.get("avg_return", 0)
    drawdown_diff = shadow_m.get("max_drawdown", 0) - prod_m.get("max_drawdown", 0)
    
    winner = "shadow" if (precision_diff > 0 and return_diff > 0) else "prod"
    
    doc = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "prod_model": evaluated[0].get("prod_model") if evaluated else None,
        "shadow_model": evaluated[0].get("shadow_model") if evaluated else None,
        "prod_metrics": prod_m,
        "shadow_metrics": shadow_m,
        "precision_diff": round(precision_diff, 4),
        "return_diff": round(return_diff, 4),
        "drawdown_diff": round(drawdown_diff, 4),
        "winner": winner,
        "evaluated_count": len(evaluated),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.ml_shadow_eval.update_one(
        {"date": doc["date"]}, {"$set": doc}, upsert=True
    )
    return {"ok": True, "eval": doc}


# ─── SIGNAL LOGGING ───
async def log_signal(signal_id, token, prediction, actor, position,
                     coordination=0, ret_1h=None, ret_4h=None, ret_24h=None):
    """Log individual signal with prediction, decision, and outcomes."""
    db = get_db()
    decision = map_decision(prediction, position)
    
    result = None
    if ret_24h is not None:
        result = "WIN" if ret_24h > 0 else "LOSS"
    
    doc = {
        "signal_id": signal_id,
        "token": token,
        "prediction": round(float(prediction), 4),
        "action": decision["action"],
        "strength": decision["strength"],
        "why": decision["why"],
        "actor": actor,
        "position": position,
        "coordination": coordination,
        "ret_1h": round(float(ret_1h), 6) if ret_1h is not None else None,
        "ret_4h": round(float(ret_4h), 6) if ret_4h is not None else None,
        "ret_24h": round(float(ret_24h), 6) if ret_24h is not None else None,
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.ml_signal_log.insert_one(doc)
    return {"ok": True, "action": decision["action"], "strength": decision["strength"]}


async def get_top_signals(limit=10):
    """Get top N signals ranked by prediction strength (ENTER/FOLLOW only)."""
    db = get_db()
    # Directly query actionable signals sorted by prediction desc
    signals = await db.ml_signal_log.find(
        {"action": {"$in": ["ENTER", "FOLLOW"]}},
        {"_id": 0}
    ).sort("prediction", -1).limit(limit).to_list(length=limit)
    
    return {"ok": True, "signals": signals, "count": len(signals)}


# ─── SMART RETRAIN TRIGGER CHECK ───
async def check_retrain_needed():
    """Check if retrain should be triggered based on conditions."""
    db = get_db()
    
    # 1. Check last retrain time
    last_retrain = await db.ml_retrain_jobs.find_one(
        {"status": "completed"},
        {"_id": 0, "created_at": 1, "samples": 1},
        sort=[("created_at", -1)]
    )
    
    days_since_retrain = RETRAIN_INTERVAL_DAYS + 1  # default: needs retrain
    last_sample_count = 0
    if last_retrain:
        try:
            last_dt = datetime.fromisoformat(last_retrain["created_at"])
            days_since_retrain = (datetime.now(timezone.utc) - last_dt).days
            last_sample_count = last_retrain.get("samples", 0)
        except (ValueError, TypeError):
            pass
    
    # 2. Current dataset size
    current_count = await db.signal_training_dataset_v2.count_documents({})
    new_samples = current_count - last_sample_count
    
    # 3. Latest drift
    latest_drift = await db.ml_drift_results.find_one(
        {}, {"_id": 0, "overall_drift_score": 1, "overall_status": 1},
        sort=[("date", -1)]
    )
    drift_score = latest_drift.get("overall_drift_score", 0) if latest_drift else 0
    drift_status = latest_drift.get("overall_status", "UNKNOWN") if latest_drift else "UNKNOWN"
    
    # 4. Performance degradation (3 days in a row)
    recent_metrics = await db.ml_daily_metrics.find(
        {}, {"_id": 0, "date": 1, "hit_rate": 1, "avg_return": 1}
    ).sort("date", -1).limit(3).to_list(length=3)
    
    perf_declining = False
    if len(recent_metrics) >= 3:
        hit_rates = [m.get("hit_rate", 1.0) for m in recent_metrics]
        perf_declining = all(h < KILL_MIN_HIT_RATE for h in hit_rates)
    
    # Evaluate triggers
    triggers = {
        "new_data": new_samples >= RETRAIN_MIN_NEW_SAMPLES,
        "time_elapsed": days_since_retrain >= RETRAIN_INTERVAL_DAYS,
        "high_drift": drift_score > DRIFT_DANGER_PSI,
        "perf_declining": perf_declining,
    }
    
    should_retrain = any(triggers.values())
    active_triggers = [k for k, v in triggers.items() if v]
    
    return {
        "ok": True,
        "should_retrain": should_retrain,
        "triggers": triggers,
        "active_triggers": active_triggers,
        "details": {
            "new_samples": new_samples,
            "days_since_retrain": days_since_retrain,
            "drift_score": drift_score,
            "drift_status": drift_status,
            "current_dataset": current_count,
        },
    }


# ─── CALIBRATION CHECK ───
async def compute_calibration():
    """Check predicted vs actual calibration in probability buckets."""
    db = get_db()
    
    signals = await db.ml_signal_log.find(
        {"result": {"$ne": None}},
        {"_id": 0, "prediction": 1, "result": 1}
    ).to_list(length=10000)
    
    if len(signals) < 20:
        return {"ok": True, "status": "not_enough_data", "count": len(signals)}
    
    # Bucket predictions into ranges
    buckets = {
        "0.0-0.2": [], "0.2-0.4": [], "0.4-0.6": [],
        "0.6-0.8": [], "0.8-1.0": [],
    }
    
    for s in signals:
        p = s["prediction"]
        actual = 1 if s["result"] == "WIN" else 0
        if p < 0.2:
            buckets["0.0-0.2"].append(actual)
        elif p < 0.4:
            buckets["0.2-0.4"].append(actual)
        elif p < 0.6:
            buckets["0.4-0.6"].append(actual)
        elif p < 0.8:
            buckets["0.6-0.8"].append(actual)
        else:
            buckets["0.8-1.0"].append(actual)
    
    calibration = {}
    for bucket, actuals in buckets.items():
        if actuals:
            actual_rate = sum(actuals) / len(actuals)
            # Compare to expected (midpoint of bucket)
            expected = (float(bucket.split("-")[0]) + float(bucket.split("-")[1])) / 2
            calibration[bucket] = {
                "count": len(actuals),
                "actual_win_rate": round(actual_rate, 4),
                "expected": round(expected, 2),
                "gap": round(actual_rate - expected, 4),
            }
    
    # Overall calibration error (ECE-like)
    total = sum(len(v) for v in buckets.values())
    ece = 0
    for bucket, data in calibration.items():
        weight = data["count"] / total if total > 0 else 0
        ece += weight * abs(data["gap"])
    
    needs_recalibration = ece > 0.15
    
    doc = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "buckets": calibration,
        "ece": round(ece, 4),
        "needs_recalibration": needs_recalibration,
        "total_signals": total,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.ml_calibration.update_one(
        {"date": doc["date"]}, {"$set": doc}, upsert=True
    )
    return {"ok": True, "calibration": doc}


# ─── COMPREHENSIVE DAILY JOB ───
async def run_daily_jobs():
    """Run all daily monitoring jobs in sequence."""
    results = {}
    
    results["metrics"] = await compute_daily_metrics()
    results["drift"] = await compute_drift()
    results["data_health"] = await compute_data_health()
    results["calibration"] = await compute_calibration()
    results["shadow_backfill"] = await backfill_shadow_outcomes()
    results["shadow_eval"] = await evaluate_shadow()
    results["retrain_check"] = await check_retrain_needed()
    results["kill_switch"] = await check_kill_switch()
    
    # Auto-rollback if kill switch triggered
    if results["kill_switch"].get("action") == "rollback_needed":
        results["auto_rollback"] = await rollback_model()
    
    return {"ok": True, "jobs": results}


# ─── LIST MODELS ───
def _sanitize_doc(doc):
    """Recursively convert non-JSON-serializable types to strings."""
    if isinstance(doc, dict):
        return {k: _sanitize_doc(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_sanitize_doc(v) for v in doc]
    if isinstance(doc, datetime):
        return doc.isoformat()
    if isinstance(doc, bytes):
        return "<binary>"
    if isinstance(doc, float) and (np.isnan(doc) or np.isinf(doc)):
        return None
    return doc


async def list_models(status=None):
    """List all registered models, optionally filtered by status."""
    db = get_db()
    query = {"status": status} if status else {}
    models = await db.ml_model_registry.find(
        query, {"_id": 0}
    ).sort("created_at", -1).to_list(length=100)
    return {"ok": True, "models": _sanitize_doc(models), "count": len(models)}


# ─── DAILY METRICS HISTORY ───
async def get_metrics_history(days=30):
    """Get daily metrics history for the last N days."""
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    metrics = await db.ml_daily_metrics.find(
        {"date": {"$gte": cutoff}},
        {"_id": 0}
    ).sort("date", -1).to_list(length=days)
    return {"ok": True, "metrics": metrics, "count": len(metrics)}


# ─── MODEL LOADING ───
async def _load_model_binary(model_name):
    """Load a pickled XGBoost model from signal_models collection."""
    db = get_db()
    doc = await db.signal_models.find_one(
        {"name": model_name},
        {"model_binary": 1, "features": 1}
    )
    if not doc or not doc.get("model_binary"):
        return None, None
    model = pickle.loads(doc["model_binary"])
    features = doc.get("features", [])
    return model, features


async def _load_active_model():
    """Load the active (production) model binary."""
    active = await get_active_model()
    if not active:
        return None, None, None
    model, features = await _load_model_binary(active["model_key"])
    return model, features, active["model_key"]


async def _load_shadow_model():
    """Load the shadow/candidate model binary (most recent non-active)."""
    db = get_db()
    shadow_reg = await db.ml_model_registry.find_one(
        {"status": {"$in": ["candidate", "shadow"]}},
        {"_id": 0, "model_key": 1},
        sort=[("created_at", -1)]
    )
    if not shadow_reg:
        return None, None, None
    model, features = await _load_model_binary(shadow_reg["model_key"])
    return model, features, shadow_reg["model_key"]


def _sample_to_feature_vector(sample):
    """Convert a training dataset sample to a feature vector for inference."""
    from signal_pipeline import FEATURE_COLS, CATEGORICAL_FEATURES
    row = []
    for col in FEATURE_COLS:
        val = sample.get(col)
        row.append(float(val) if val is not None else 0.0)
    for cat_col, mapping in CATEGORICAL_FEATURES.items():
        val = sample.get(cat_col, "UNKNOWN")
        row.append(float(mapping.get(val, 0)))
    return np.array([row])


# ─── LIVE PREDICTION ENGINE ───
async def run_live_predictions():
    """Run predictions on all dataset samples through active + shadow models.
    
    This is the core function that fills:
    - ml_shadow_predictions (prod vs shadow comparison)
    - ml_signal_log (signal outcomes with decisions)
    """
    db = get_db()
    
    # Load models
    prod_model, prod_features, prod_key = await _load_active_model()
    shadow_model, shadow_features, shadow_key = await _load_shadow_model()
    
    if not prod_model:
        return {"ok": False, "error": "No active model loaded"}
    
    # Load dataset samples
    samples = await db.signal_training_dataset_v2.find(
        {}, {"_id": 0}
    ).to_list(length=20000)
    
    if not samples:
        return {"ok": False, "error": "No dataset samples"}
    
    # Check which signals are already logged (avoid duplicates)
    existing_signals = set()
    existing_docs = await db.ml_signal_log.find(
        {}, {"_id": 0, "signal_id": 1}
    ).to_list(length=50000)
    for d in existing_docs:
        existing_signals.add(d.get("signal_id"))
    
    existing_shadow = set()
    existing_shadow_docs = await db.ml_shadow_predictions.find(
        {}, {"_id": 0, "signal_id": 1}
    ).to_list(length=50000)
    for d in existing_shadow_docs:
        existing_shadow.add(d.get("signal_id"))
    
    signal_logs = []
    shadow_logs = []
    
    for s in samples:
        signal_id = s.get("tweet_id", s.get("signal_id", ""))
        if not signal_id:
            continue
        
        # Feature vector
        X = _sample_to_feature_vector(s)
        
        # Production prediction
        prod_prob = float(prod_model.predict_proba(X)[0, 1])
        
        # Shadow prediction
        shadow_prob = None
        if shadow_model:
            shadow_prob = float(shadow_model.predict_proba(X)[0, 1])
        
        position = s.get("f_signal_position", "UNKNOWN")
        actor = s.get("actor_handle", "")
        token = s.get("token", "")
        actor_hit = s.get("f_actor_hit_rate", 0)
        coord = s.get("f_coord_density", 0)
        
        decision = map_decision(prod_prob, position, actor_hit, coord)
        
        # Determine result from actual returns
        ret_24h = s.get("rel_ret_24h")
        ret_1h = s.get("f_ret_1h")
        ret_4h = s.get("f_ret_4h")
        result = None
        if ret_24h is not None:
            result = "WIN" if ret_24h > 0 else "LOSS"
        
        # Signal log
        if signal_id not in existing_signals:
            signal_logs.append({
                "signal_id": signal_id,
                "token": token,
                "prediction": round(prod_prob, 4),
                "action": decision["action"],
                "strength": decision["strength"],
                "why": decision["why"],
                "actor": actor,
                "position": position,
                "coordination": round(coord, 4),
                "ret_1h": round(float(ret_1h), 6) if ret_1h is not None else None,
                "ret_4h": round(float(ret_4h), 6) if ret_4h is not None else None,
                "ret_24h": round(float(ret_24h), 6) if ret_24h is not None else None,
                "result": result,
                "model_key": prod_key,
                "timestamp": s.get("timestamp", datetime.now(timezone.utc).isoformat()),
            })
        
        # Shadow log (only if shadow model exists)
        if shadow_model and shadow_prob is not None and signal_id not in existing_shadow:
            shadow_decision = map_decision(shadow_prob, position, actor_hit, coord)
            shadow_logs.append({
                "signal_id": signal_id,
                "token": token,
                "prod_model": prod_key,
                "shadow_model": shadow_key,
                "prod_pred": round(prod_prob, 4),
                "shadow_pred": round(shadow_prob, 4),
                "prod_decision": decision["action"],
                "shadow_decision": shadow_decision["action"],
                "actor": actor,
                "position": position,
                "actual_result": result,
                "actual_return": round(float(ret_24h), 6) if ret_24h is not None else None,
                "timestamp": s.get("timestamp", datetime.now(timezone.utc).isoformat()),
            })
    
    # Bulk insert
    if signal_logs:
        await db.ml_signal_log.insert_many(signal_logs)
    if shadow_logs:
        await db.ml_shadow_predictions.insert_many(shadow_logs)
    
    # Count action distribution
    action_dist = Counter(s["action"] for s in signal_logs) if signal_logs else {}
    result_dist = Counter(s["result"] for s in signal_logs if s["result"]) if signal_logs else {}
    
    return {
        "ok": True,
        "prod_model": prod_key,
        "shadow_model": shadow_key,
        "signals_logged": len(signal_logs),
        "shadow_logged": len(shadow_logs),
        "skipped_existing": len(samples) - len(signal_logs),
        "action_distribution": dict(action_dist),
        "result_distribution": dict(result_dist),
    }


async def get_signal_stats():
    """Get aggregated signal statistics from ml_signal_log."""
    db = get_db()
    
    total = await db.ml_signal_log.count_documents({})
    if total == 0:
        return {"ok": True, "total": 0, "message": "No signals logged yet"}
    
    # Action distribution
    action_pipeline = [
        {"$group": {"_id": "$action", "count": {"$sum": 1}}}
    ]
    action_dist = {}
    async for doc in db.ml_signal_log.aggregate(action_pipeline):
        action_dist[doc["_id"]] = doc["count"]
    
    # Result distribution
    result_pipeline = [
        {"$match": {"result": {"$ne": None}}},
        {"$group": {"_id": "$result", "count": {"$sum": 1}}}
    ]
    result_dist = {}
    async for doc in db.ml_signal_log.aggregate(result_pipeline):
        result_dist[doc["_id"]] = doc["count"]
    
    # Top actors by ENTER/FOLLOW signals
    actor_pipeline = [
        {"$match": {"action": {"$in": ["ENTER", "FOLLOW"]}}},
        {"$group": {"_id": "$actor", "count": {"$sum": 1}, "avg_pred": {"$avg": "$prediction"}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    top_actors = []
    async for doc in db.ml_signal_log.aggregate(actor_pipeline):
        top_actors.append({
            "actor": doc["_id"],
            "actionable_signals": doc["count"],
            "avg_prediction": round(doc["avg_pred"], 4),
        })
    
    # Top tokens by signal count
    token_pipeline = [
        {"$match": {"action": {"$in": ["ENTER", "FOLLOW"]}}},
        {"$group": {"_id": "$token", "count": {"$sum": 1}, "avg_pred": {"$avg": "$prediction"}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    top_tokens = []
    async for doc in db.ml_signal_log.aggregate(token_pipeline):
        top_tokens.append({
            "token": doc["_id"],
            "actionable_signals": doc["count"],
            "avg_prediction": round(doc["avg_pred"], 4),
        })
    
    # Shadow stats
    shadow_total = await db.ml_shadow_predictions.count_documents({})
    shadow_evaluated = await db.ml_shadow_predictions.count_documents({"actual_result": {"$ne": None}})
    
    return {
        "ok": True,
        "total_signals": total,
        "action_distribution": action_dist,
        "result_distribution": result_dist,
        "top_actors": top_actors,
        "top_tokens": top_tokens,
        "shadow_predictions": shadow_total,
        "shadow_evaluated": shadow_evaluated,
    }
