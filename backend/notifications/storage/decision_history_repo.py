"""
Decision History — Storage layer for decision tracking.

Collections:
  - decision_history: saved decisions with entryPrice and evaluation results
"""
import os
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient


def _get_db():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    return AsyncIOMotorClient(mongo_url)[db_name]


async def ensure_indexes():
    db = _get_db()
    col = db["decision_history"]
    await col.create_index("asset")
    await col.create_index("horizon")
    await col.create_index("status")
    await col.create_index("evaluateAfter")
    await col.create_index([("asset", 1), ("horizon", 1), ("timestamp", -1)])


async def save_decision(doc: dict) -> dict:
    db = _get_db()
    col = db["decision_history"]
    await col.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def get_pending_decisions() -> list:
    """Get decisions that are past evaluateAfter and still pending."""
    db = _get_db()
    col = db["decision_history"]
    now = datetime.now(timezone.utc).isoformat()
    cursor = col.find(
        {"status": "pending", "evaluateAfter": {"$lte": now}},
        {"_id": 0},
    ).sort("evaluateAfter", 1).limit(50)
    return await cursor.to_list(length=50)


async def update_evaluation(decision_id: str, update: dict):
    db = _get_db()
    col = db["decision_history"]
    await col.update_one(
        {"id": decision_id},
        {"$set": update},
    )


async def get_history(asset: str = None, status: str = None, limit: int = 50) -> list:
    db = _get_db()
    col = db["decision_history"]
    query = {}
    if asset:
        query["asset"] = asset.upper()
    if status:
        query["status"] = status
    cursor = col.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_stats() -> dict:
    """Compute accuracy stats from evaluated decisions."""
    db = _get_db()
    col = db["decision_history"]

    evaluated = await col.find(
        {"status": "evaluated"},
        {"_id": 0, "decision": 1, "decisionType": 1, "result": 1,
         "realMovePct": 1, "catastrophic": 1, "horizon": 1, "asset": 1},
    ).to_list(length=1000)

    if not evaluated:
        total_pending = await col.count_documents({"status": "pending"})
        return {
            "total": total_pending, "evaluated": 0, "pending": total_pending,
            "accuracy": None, "catastrophicRate": None,
            "avgMoveWhenCorrect": None,
            "byType": {}, "byHorizon": {}, "byAsset": {},
        }

    total_pending = await col.count_documents({"status": "pending"})

    correct = [d for d in evaluated if d.get("result") == "correct"]
    wrong = [d for d in evaluated if d.get("result") == "wrong"]
    catastrophic = [d for d in evaluated if d.get("catastrophic")]

    accuracy = len(correct) / len(evaluated) if evaluated else 0
    catastrophic_rate = len(catastrophic) / len(evaluated) if evaluated else 0

    correct_moves = [abs(d.get("realMovePct", 0)) for d in correct if d.get("realMovePct") is not None]
    avg_move_correct = sum(correct_moves) / len(correct_moves) if correct_moves else 0

    def _breakdown(items, key):
        groups = {}
        for d in items:
            val = d.get(key, "unknown")
            if val not in groups:
                groups[val] = []
            groups[val].append(d)
        result = {}
        for val, group in groups.items():
            g_correct = len([d for d in group if d.get("result") == "correct"])
            g_catastrophic = len([d for d in group if d.get("catastrophic")])
            result[val] = {
                "total": len(group),
                "accuracy": round(g_correct / len(group), 3),
                "catastrophicRate": round(g_catastrophic / len(group), 3),
            }
        return result

    by_type = _breakdown(evaluated, "decisionType")
    by_horizon = _breakdown(evaluated, "horizon")
    by_asset = _breakdown(evaluated, "asset")

    return {
        "total": len(evaluated) + total_pending,
        "evaluated": len(evaluated),
        "pending": total_pending,
        "accuracy": round(accuracy, 3),
        "catastrophicRate": round(catastrophic_rate, 3),
        "avgMoveWhenCorrect": round(avg_move_correct, 3),
        "byType": by_type,
        "byHorizon": by_horizon,
        "byAsset": by_asset,
    }
