"""
Structure A/B Shadow System
=============================
Records parallel forecasts: one WITH structure delta, one WITHOUT.
Tracks outcomes to prove (or disprove) that structure provides edge.

Shadow comparison flow:
  1. During forecast generation → record_shadow() stores both variants
  2. During evaluation → evaluate_shadow() checks actual price vs both predictions
  3. API endpoint → returns aggregated metrics comparing A (base) vs B (structure)

Collection: exchange_forecast_shadow
"""

from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING

from forecast.v41_config import classify_direction, classify_direction_shadow, SHADOW_MILD_THRESHOLD

SHADOW_COLLECTION = "exchange_forecast_shadow"


def _get_db():
    import os
    try:
        from forecast.repo import _cfg
        c = _cfg()
        return MongoClient(c.mongo_url)[c.db_name]
    except RuntimeError:
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
        db_name = os.environ.get("DB_NAME", "intelligence_engine")
        return MongoClient(mongo_url)[db_name]


def record_shadow(
    forecast_id: str,
    asset: str,
    horizon: str,
    entry_price: float,
    base_score: float,
    structure_score: float,
    structure_features: dict,
    structure_delta: float,
    sign_flip: bool,
    evaluate_after: int,
    bucket: str,
) -> None:
    """
    Record an A/B shadow comparison at forecast time.
    Called from generator_v41.py after structure delta is computed.
    """
    db = _get_db()

    base_direction = classify_direction(base_score)
    struct_direction = classify_direction(structure_score)
    direction_changed = base_direction != struct_direction

    # Shadow threshold comparison (A2 experiment)
    shadow_base_dir = classify_direction(base_score, SHADOW_MILD_THRESHOLD) if SHADOW_MILD_THRESHOLD else base_direction

    doc = {
        "forecastId": forecast_id,
        "asset": asset,
        "horizon": horizon,
        "bucket": bucket,
        "entryPrice": entry_price,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "evaluateAfter": evaluate_after,
        "forecast_base": {
            "score": round(base_score, 6),
            "direction": base_direction,
        },
        "forecast_structure": {
            "score": round(structure_score, 6),
            "direction": struct_direction,
        },
        "threshold_shadow": {
            "live_threshold": 0.20,
            "shadow_threshold": SHADOW_MILD_THRESHOLD,
            "live_direction": base_direction,
            "shadow_direction": shadow_base_dir,
            "differs": base_direction != shadow_base_dir,
        },
        "structure_delta": {
            "delta": round(structure_delta, 6),
            "sign_flip": sign_flip,
            "direction_changed": direction_changed,
        },
        "structure_features": structure_features,
        "evaluated": False,
        "outcome": None,
    }

    db[SHADOW_COLLECTION].update_one(
        {"forecastId": forecast_id, "horizon": horizon},
        {"$set": doc},
        upsert=True,
    )


def evaluate_shadows(limit: int = 200) -> dict:
    """
    Evaluate matured shadow records against actual prices.
    Called from scheduler after regular eval phase.
    """
    from forecast.price_provider import get_price

    db = _get_db()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    pending = list(db[SHADOW_COLLECTION].find(
        {"evaluated": False, "evaluateAfter": {"$lte": now_ms}},
        {"_id": 0},
    ).limit(limit))

    evaluated = 0
    skipped = 0

    for doc in pending:
        actual_price = get_price(doc["asset"], doc["evaluateAfter"])
        if actual_price is None:
            skipped += 1
            continue

        entry = doc["entryPrice"]
        real_move = (actual_price - entry) / entry
        real_direction = "BULL" if real_move > 0.005 else ("BEAR" if real_move < -0.005 else "FLAT")

        base_dir = doc["forecast_base"]["direction"]
        struct_dir = doc["forecast_structure"]["direction"]

        base_correct = _direction_match(base_dir, real_direction)
        struct_correct = _direction_match(struct_dir, real_direction)

        # A2: Shadow threshold comparison
        threshold_shadow = doc.get("threshold_shadow", {})
        shadow_dir = threshold_shadow.get("shadow_direction", base_dir)
        shadow_correct = _direction_match(shadow_dir, real_direction)

        # Classify the comparison case
        if struct_correct and not base_correct:
            case_type = "structure_improved"
        elif not struct_correct and base_correct:
            case_type = "structure_hurt"
        elif struct_correct and base_correct:
            case_type = "both_correct"
        else:
            case_type = "both_wrong"

        outcome = {
            "actualPrice": round(actual_price, 2),
            "realMovePct": round(real_move * 100, 2),
            "realDirection": real_direction,
            "baseDirectionCorrect": base_correct,
            "structDirectionCorrect": struct_correct,
            "shadowThresholdCorrect": shadow_correct,
            "caseType": case_type,
            "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        }

        db[SHADOW_COLLECTION].update_one(
            {"forecastId": doc["forecastId"], "horizon": doc["horizon"]},
            {"$set": {"evaluated": True, "outcome": outcome}},
        )
        evaluated += 1

    return {"evaluated": evaluated, "skipped": skipped, "pending": len(pending)}


def compute_shadow_kpi(horizon: str = None, limit: int = 100) -> dict:
    """
    Compute A/B comparison metrics from evaluated shadow records.
    Returns comprehensive stats for validating structure edge.
    """
    db = _get_db()

    query = {"evaluated": True, "outcome": {"$ne": None}}
    if horizon:
        query["horizon"] = horizon

    docs = list(db[SHADOW_COLLECTION].find(
        query, {"_id": 0},
    ).sort("evaluateAfter", DESCENDING).limit(limit))

    if not docs:
        return {
            "n": 0,
            "verdict": "INSUFFICIENT_DATA",
            "base": {},
            "structure": {},
            "comparison": {},
        }

    n = len(docs)

    # Direction accuracy
    base_correct = sum(1 for d in docs if d["outcome"]["baseDirectionCorrect"])
    struct_correct = sum(1 for d in docs if d["outcome"]["structDirectionCorrect"])

    # Case type distribution
    cases = {"structure_improved": 0, "structure_hurt": 0, "both_correct": 0, "both_wrong": 0}
    for d in docs:
        ct = d["outcome"].get("caseType", "both_wrong")
        cases[ct] = cases.get(ct, 0) + 1

    # Direction distribution (neutral ratio, mild ratio, strong ratio)
    base_dirs = [d["forecast_base"]["direction"] for d in docs]
    struct_dirs = [d["forecast_structure"]["direction"] for d in docs]

    base_dist = _direction_distribution(base_dirs)
    struct_dist = _direction_distribution(struct_dirs)

    # Delta statistics
    deltas = [d["structure_delta"]["delta"] for d in docs]
    avg_delta = sum(deltas) / len(deltas)
    abs_deltas = [abs(d) for d in deltas]
    avg_abs_delta = sum(abs_deltas) / len(abs_deltas)
    max_delta = max(abs_deltas)
    direction_changed = sum(1 for d in docs if d["structure_delta"]["direction_changed"])
    sign_flips = sum(1 for d in docs if d["structure_delta"]["sign_flip"])

    # Score shift
    base_scores = [d["forecast_base"]["score"] for d in docs]
    struct_scores = [d["forecast_structure"]["score"] for d in docs]
    avg_base_score = sum(base_scores) / len(base_scores)
    avg_struct_score = sum(struct_scores) / len(struct_scores)

    base_accuracy = base_correct / n if n > 0 else 0
    struct_accuracy = struct_correct / n if n > 0 else 0
    accuracy_lift = struct_accuracy - base_accuracy

    # Verdict
    if n < 10:
        verdict = "INSUFFICIENT_DATA"
    elif accuracy_lift > 0.05:
        verdict = "STRUCTURE_POSITIVE"
    elif accuracy_lift < -0.05:
        verdict = "STRUCTURE_NEGATIVE"
    else:
        verdict = "NEUTRAL_IMPACT"

    return {
        "n": n,
        "verdict": verdict,
        "base": {
            "accuracy": round(base_accuracy, 4),
            "avg_score": round(avg_base_score, 6),
            "distribution": base_dist,
        },
        "structure": {
            "accuracy": round(struct_accuracy, 4),
            "avg_score": round(avg_struct_score, 6),
            "distribution": struct_dist,
        },
        "comparison": {
            "accuracy_lift": round(accuracy_lift, 4),
            "avg_delta": round(avg_delta, 6),
            "avg_abs_delta": round(avg_abs_delta, 6),
            "max_abs_delta": round(max_delta, 6),
            "direction_changed_count": direction_changed,
            "sign_flip_count": sign_flips,
            "cases": cases,
        },
    }


def get_shadow_cases(case_type: str = None, horizon: str = None, limit: int = 20) -> list:
    """
    Retrieve individual shadow comparison cases for manual review.
    Useful for inspecting structure_improved and structure_hurt cases.
    """
    db = _get_db()

    query = {"evaluated": True, "outcome": {"$ne": None}}
    if case_type:
        query["outcome.caseType"] = case_type
    if horizon:
        query["horizon"] = horizon

    docs = list(db[SHADOW_COLLECTION].find(
        query, {"_id": 0},
    ).sort("evaluateAfter", DESCENDING).limit(limit))

    return docs


def _direction_match(predicted: str, actual: str) -> bool:
    """Check if predicted direction matches actual market move."""
    bullish = {"STRONG_BULL", "MILD_BULL"}
    bearish = {"STRONG_BEAR", "MILD_BEAR"}

    if actual == "BULL":
        return predicted in bullish
    elif actual == "BEAR":
        return predicted in bearish
    else:
        return predicted == "NEUTRAL"


def _direction_distribution(directions: list[str]) -> dict:
    """Compute distribution of direction classes."""
    n = len(directions) or 1
    counts = {}
    for d in directions:
        counts[d] = counts.get(d, 0) + 1

    neutral = counts.get("NEUTRAL", 0)
    mild = counts.get("MILD_BULL", 0) + counts.get("MILD_BEAR", 0)
    strong = counts.get("STRONG_BULL", 0) + counts.get("STRONG_BEAR", 0)

    return {
        "neutral_ratio": round(neutral / n, 4),
        "mild_ratio": round(mild / n, 4),
        "strong_ratio": round(strong / n, 4),
        "counts": counts,
    }
