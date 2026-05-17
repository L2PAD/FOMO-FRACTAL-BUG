"""
Decision History — Record, Evaluate, and Feedback.

Flow:
  1. record_decision(asset, horizon) → saves decision + entryPrice
  2. evaluate_pending() → checks matured decisions against real prices
  3. get_feedback_adjustments() → self-tuning based on accuracy by type
"""
import uuid
from datetime import datetime, timezone, timedelta
from notifications.decision_engine import compute_decision


# Horizon → evaluation delay mapping
_HORIZON_DELAYS = {
    "24H": timedelta(hours=24),
    "7D": timedelta(days=7),
    "30D": timedelta(days=30),
}


def _get_current_price(asset: str) -> float | None:
    """Get current price via forecast price_provider."""
    try:
        from forecast.price_provider import get_current_price
        return get_current_price(asset)
    except Exception:
        return None


async def record_decision(asset: str, horizon: str = "30D") -> dict:
    """Compute decision, attach entryPrice, save to history."""
    from notifications.storage.decision_history_repo import save_decision

    decision = compute_decision(asset, horizon)
    entry_price = _get_current_price(asset)

    if entry_price is None:
        return {"error": "no_price_data", "asset": asset}

    now = datetime.now(timezone.utc)
    delay = _HORIZON_DELAYS.get(horizon, timedelta(days=7))
    evaluate_after = now + delay

    doc = {
        "id": f"dec_{uuid.uuid4().hex[:12]}",
        "asset": decision["asset"],
        "horizon": decision["horizonRaw"],
        "decision": decision["decision"],
        "decisionType": decision.get("decisionType", "NORMAL"),
        "score": decision["score"],
        "confidence": decision["confidence"],
        "fusion": decision.get("components", {}).get("fusion", {}),
        "reasoning": decision["reasoning"],
        "entryPrice": entry_price,
        "timestamp": now.isoformat(),
        "evaluateAfter": evaluate_after.isoformat(),
        "status": "pending",
    }

    saved = await save_decision(doc)
    return saved


async def record_all_decisions() -> list:
    """Record decisions for all assets × horizons (daily batch)."""
    assets = ["BTC", "ETH", "SOL"]
    horizons = ["24H", "7D", "30D"]
    results = []
    for asset in assets:
        for h in horizons:
            r = await record_decision(asset, h)
            results.append(r)
    return results


async def evaluate_pending() -> dict:
    """Evaluate all matured pending decisions."""
    from notifications.storage.decision_history_repo import (
        get_pending_decisions, update_evaluation
    )

    pending = await get_pending_decisions()
    if not pending:
        return {"evaluated": 0, "message": "no matured decisions"}

    evaluated = 0
    results = []

    for dec in pending:
        asset = dec["asset"]
        entry_price = dec.get("entryPrice")
        if not entry_price:
            continue

        current_price = _get_current_price(asset)
        if current_price is None:
            continue

        real_move_pct = round(((current_price - entry_price) / entry_price) * 100, 3)
        decision = dec["decision"]

        # Evaluate correctness
        if decision == "WAIT":
            result = "neutral"
            is_catastrophic = abs(real_move_pct) > 5
        elif decision == "BUY":
            result = "correct" if real_move_pct > 0 else "wrong"
            is_catastrophic = result == "wrong" and abs(real_move_pct) > 5
        elif decision == "SELL":
            result = "correct" if real_move_pct < 0 else "wrong"
            is_catastrophic = result == "wrong" and abs(real_move_pct) > 5
        elif decision == "AVOID":
            result = "correct" if abs(real_move_pct) > 3 else "wrong"
            is_catastrophic = False
        else:
            result = "unknown"
            is_catastrophic = False

        update = {
            "status": "evaluated",
            "result": result,
            "realMovePct": real_move_pct,
            "exitPrice": current_price,
            "catastrophic": is_catastrophic,
            "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        }

        await update_evaluation(dec["id"], update)
        evaluated += 1
        results.append({
            "id": dec["id"],
            "asset": asset,
            "horizon": dec["horizon"],
            "decision": decision,
            "result": result,
            "realMovePct": real_move_pct,
            "catastrophic": is_catastrophic,
        })

    return {"evaluated": evaluated, "results": results}


async def get_feedback_adjustments() -> dict:
    """
    Light self-tuning: compare accuracy across decision types.
    Returns recommended fusion boost adjustments.
    """
    from notifications.storage.decision_history_repo import get_stats

    stats = await get_stats()
    by_type = stats.get("byType", {})

    normal_acc = by_type.get("NORMAL", {}).get("accuracy")
    high_acc = by_type.get("HIGH_CONVICTION", {}).get("accuracy")
    extreme_acc = by_type.get("EXTREME", {}).get("accuracy")

    adjustments = {"action": "none", "details": {}}

    if extreme_acc is not None and normal_acc is not None:
        if extreme_acc < normal_acc:
            adjustments["action"] = "reduce_extreme_boost"
            adjustments["details"]["reason"] = f"EXTREME accuracy ({extreme_acc:.1%}) < NORMAL ({normal_acc:.1%})"
            adjustments["details"]["recommendation"] = "Reduce extreme fusion boost from ±4 to ±3"
        elif extreme_acc > 0.7:
            adjustments["action"] = "boost_extreme"
            adjustments["details"]["reason"] = f"EXTREME accuracy ({extreme_acc:.1%}) > 70%"
            adjustments["details"]["recommendation"] = "EXTREME fusion is highly reliable — consider increasing boost"

    if high_acc is not None and normal_acc is not None:
        if high_acc < normal_acc:
            adjustments["action"] = "reduce_high_boost"
            adjustments["details"]["reason"] = f"HIGH_CONVICTION accuracy ({high_acc:.1%}) < NORMAL ({normal_acc:.1%})"

    adjustments["stats"] = {
        "normal": normal_acc,
        "highConviction": high_acc,
        "extreme": extreme_acc,
    }

    return adjustments
