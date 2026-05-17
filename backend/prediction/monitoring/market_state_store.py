"""
Market State Store — diff-aware persisted state per market in MongoDB.

Stores last known analysis derivatives so watcher can detect real transitions
without recomputing everything from scratch.

Collection: prediction_market_states
"""
import os
from datetime import datetime, timezone
from pymongo import MongoClient, ReturnDocument


def _col():
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "intelligence_engine")]
    return db["prediction_market_states"]


def get_state(market_id: str) -> dict | None:
    doc = _col().find_one({"market_id": market_id}, {"_id": 0})
    return doc


def get_all_states() -> list[dict]:
    return list(_col().find({}, {"_id": 0}))


def upsert_state(market_id: str, state: dict) -> dict:
    """
    Upsert market state. Returns the updated document.
    state should include: last_edge, last_confidence, last_alignment,
    last_repricing_state, last_entry_action, last_stage, last_recommendation,
    last_size, last_move_1h, last_move_6h, last_signal_hash, etc.
    """
    state["market_id"] = market_id
    state["last_updated_at"] = datetime.now(timezone.utc).isoformat()

    doc = _col().find_one_and_update(
        {"market_id": market_id},
        {"$set": state},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    return doc


def compute_signal_hash(case: dict) -> str:
    """Compute a hash of the key decision fields to detect real changes."""
    import hashlib
    reco = case.get("recommendation", {})
    sizing = case.get("sizing", {})
    key = f"{reco.get('action')}|{reco.get('conviction')}|{sizing.get('size')}|{case.get('repricing',{}).get('repricing_state','')}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def build_state_from_case(case: dict) -> dict:
    """Extract state fields from a full case object."""
    a = case.get("analysis", {})
    reco = case.get("recommendation", {})
    sizing = case.get("sizing", {})
    repricing = case.get("repricing", {})
    entry = case.get("entry_timing", {})

    return {
        "question": case.get("question", "")[:120],
        "asset": case.get("asset"),
        "market_type": case.get("market_type"),
        "event_type": case.get("event_type"),

        "last_edge": a.get("net_edge", 0),
        "last_confidence": a.get("model_confidence", 0),
        "last_alignment": a.get("alignment_score", 0),
        "last_fair_prob": a.get("fair_prob", 0),
        "last_market_prob": a.get("market_prob", 0),

        "last_recommendation": reco.get("action"),
        "last_conviction": reco.get("conviction"),
        "last_size": sizing.get("size"),
        "last_size_fraction": sizing.get("size_fraction", 0),

        "last_repricing_state": repricing.get("repricing_state"),
        "last_entry_action": entry.get("entry_action"),
        "last_stage": case.get("market_stage"),

        "last_move_1h": repricing.get("move_1h", 0),
        "last_move_6h": repricing.get("move_6h", 0),

        "last_signal_hash": compute_signal_hash(case),
    }
