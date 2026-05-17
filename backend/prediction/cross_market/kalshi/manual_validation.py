"""
Manual Validation Framework for Cross-Platform Signals.

Allows manual classification of each signal as:
  REAL_EDGE, FAKE_EDGE, EXECUTION_TRAP, TIMING_TRAP, AMBIGUOUS_RULES, SKIP

Stores verdicts in MongoDB, computes performance metrics.
"""
import os
import logging
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient

logger = logging.getLogger("cross_market.kalshi.validation")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

_client = None
_db = None

VALIDATIONS_COLLECTION = "cross_market_validations"
SIGNALS_COLLECTION = "cross_platform_signals"

MANUAL_VERDICTS = [
    "REAL_EDGE",
    "FAKE_EDGE",
    "EXECUTION_TRAP",
    "TIMING_TRAP",
    "AMBIGUOUS_RULES",
    "SKIP",
]


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URL)
        _db = _client[DB_NAME]
    return _db


def create_validation_entry(signal: dict) -> str | None:
    """Auto-create a validation entry when a signal is stored."""
    try:
        db = _get_db()

        doc = {
            "signal_id": signal.get("signal_id", ""),
            "cluster_id": signal.get("cluster_id", ""),
            "entity": signal.get("entity", ""),
            "edge_case_type": signal.get("edge_case_type", "UNKNOWN"),
            "constraint_type": signal.get("constraint_type", ""),
            "score": signal.get("score", 0),
            "actionability_score": signal.get("actionability_score", 0),
            "real_edge_score": signal.get("real_edge_score"),
            "severity": signal.get("severity", ""),
            "edge_badge": signal.get("edge_badge", ""),
            "trap_flags": signal.get("trap_flags", []),
            "gap": signal.get("gap", 0),
            "gap_pct": signal.get("gap_pct", 0),
            "poly_price": signal.get("poly_price"),
            "kalshi_price": signal.get("kalshi_price"),
            "confidence_at_validation": signal.get("score", 0),
            "strategy_type": signal.get("strategy_type", ""),
            "legs": signal.get("legs", []),
            # Validation fields (filled by analyst)
            "manual_verdict": None,
            "verdict_reason": None,
            "execution_possible": None,
            "execution_notes": None,
            # Outcome
            "outcome_status": "PENDING",
            "resolved_at": None,
            # Timestamps
            "created_at": datetime.now(timezone.utc),
            "validated_at": None,
        }
        result = db[VALIDATIONS_COLLECTION].insert_one(doc)
        vid = str(result.inserted_id)
        logger.info(f"[Validation] Created entry for {signal.get('entity')} {signal.get('edge_case_type')}")
        return vid
    except Exception as e:
        logger.error(f"[Validation] Failed to create entry: {e}")
        return None


def submit_verdict(validation_id: str, verdict: str, execution_possible: bool | None = None,
                   verdict_reason: str = "", execution_notes: str = "") -> bool:
    """Submit a manual verdict for a validation entry."""
    if verdict not in MANUAL_VERDICTS:
        logger.warning(f"[Validation] Invalid verdict: {verdict}")
        return False

    try:
        db = _get_db()
        result = db[VALIDATIONS_COLLECTION].update_one(
            {"_id": ObjectId(validation_id)},
            {"$set": {
                "manual_verdict": verdict,
                "execution_possible": execution_possible,
                "verdict_reason": verdict_reason,
                "execution_notes": execution_notes,
                "validated_at": datetime.now(timezone.utc),
            }}
        )
        if result.modified_count > 0:
            logger.info(f"[Validation] Verdict submitted: {validation_id} → {verdict}")
            return True
        return False
    except Exception as e:
        logger.error(f"[Validation] Failed to submit verdict: {e}")
        return False


def get_validation_queue(status: str = "PENDING", limit: int = 50) -> list[dict]:
    """Get validation entries that need manual review."""
    try:
        db = _get_db()
        query = {}
        if status == "PENDING":
            query["manual_verdict"] = None
        elif status == "VALIDATED":
            query["manual_verdict"] = {"$ne": None}

        cursor = db[VALIDATIONS_COLLECTION].find(
            query,
            {"_id": 1, "signal_id": 1, "cluster_id": 1, "entity": 1,
             "edge_case_type": 1, "score": 1, "actionability_score": 1,
             "real_edge_score": 1, "severity": 1, "edge_badge": 1,
             "trap_flags": 1, "gap_pct": 1, "poly_price": 1, "kalshi_price": 1,
             "manual_verdict": 1, "verdict_reason": 1, "execution_possible": 1,
             "execution_notes": 1, "outcome_status": 1,
             "confidence_at_validation": 1, "strategy_type": 1, "legs": 1,
             "created_at": 1, "validated_at": 1}
        ).sort("created_at", -1).limit(limit)

        entries = []
        for doc in cursor:
            doc["validation_id"] = str(doc.pop("_id"))
            if "created_at" in doc and doc["created_at"]:
                doc["created_at"] = doc["created_at"].isoformat()
            if "validated_at" in doc and doc["validated_at"]:
                doc["validated_at"] = doc["validated_at"].isoformat()
            entries.append(doc)
        return entries
    except Exception as e:
        logger.error(f"[Validation] Failed to get queue: {e}")
        return []


def get_validation_metrics() -> dict:
    """Compute validation performance metrics."""
    try:
        db = _get_db()
        total = db[VALIDATIONS_COLLECTION].count_documents({})
        validated = db[VALIDATIONS_COLLECTION].count_documents({"manual_verdict": {"$ne": None}})
        pending = total - validated

        if validated == 0:
            return {
                "total": total,
                "validated": 0,
                "pending": pending,
                "verdicts": {},
                "real_edge_rate": None,
                "execution_rate": None,
                "trap_rate": None,
                "by_edge_type": [],
                "by_confidence_bucket": [],
                "sample_sufficient": False,
            }

        # Count verdicts
        pipeline_verdicts = [
            {"$match": {"manual_verdict": {"$ne": None}}},
            {"$group": {"_id": "$manual_verdict", "count": {"$sum": 1}}},
        ]
        verdict_counts = {}
        for r in db[VALIDATIONS_COLLECTION].aggregate(pipeline_verdicts):
            verdict_counts[r["_id"]] = r["count"]

        real_count = verdict_counts.get("REAL_EDGE", 0)
        exec_trap = verdict_counts.get("EXECUTION_TRAP", 0)
        timing_trap = verdict_counts.get("TIMING_TRAP", 0)
        skip_count = verdict_counts.get("SKIP", 0)

        meaningful = validated - skip_count
        real_edge_rate = round(real_count / meaningful * 100, 1) if meaningful > 0 else None
        execution_possible_count = db[VALIDATIONS_COLLECTION].count_documents(
            {"execution_possible": True, "manual_verdict": {"$ne": None}}
        )
        exec_rate = round(execution_possible_count / meaningful * 100, 1) if meaningful > 0 else None
        trap_rate = round((exec_trap + timing_trap) / meaningful * 100, 1) if meaningful > 0 else None

        # By edge_case_type
        by_type_pipeline = [
            {"$match": {"$and": [{"manual_verdict": {"$ne": None}}, {"manual_verdict": {"$ne": "SKIP"}}]}},
            {"$group": {
                "_id": "$edge_case_type",
                "total": {"$sum": 1},
                "real": {"$sum": {"$cond": [{"$eq": ["$manual_verdict", "REAL_EDGE"]}, 1, 0]}},
                "fake": {"$sum": {"$cond": [{"$eq": ["$manual_verdict", "FAKE_EDGE"]}, 1, 0]}},
                "exec_trap": {"$sum": {"$cond": [{"$eq": ["$manual_verdict", "EXECUTION_TRAP"]}, 1, 0]}},
                "timing_trap": {"$sum": {"$cond": [{"$eq": ["$manual_verdict", "TIMING_TRAP"]}, 1, 0]}},
                "ambiguous": {"$sum": {"$cond": [{"$eq": ["$manual_verdict", "AMBIGUOUS_RULES"]}, 1, 0]}},
                "avg_score": {"$avg": "$score"},
            }},
            {"$sort": {"total": -1}},
        ]
        by_type = []
        for r in db[VALIDATIONS_COLLECTION].aggregate(by_type_pipeline):
            t = r["total"]
            by_type.append({
                "edge_case_type": r["_id"] or "UNKNOWN",
                "total": t,
                "real": r["real"],
                "fake": r["fake"],
                "exec_trap": r["exec_trap"],
                "timing_trap": r["timing_trap"],
                "ambiguous": r["ambiguous"],
                "real_edge_rate": round(r["real"] / t * 100, 1) if t > 0 else None,
                "avg_score": round(r["avg_score"] or 0, 3),
            })

        # By confidence bucket
        bucket_pipeline = [
            {"$match": {"$and": [{"manual_verdict": {"$ne": None}}, {"manual_verdict": {"$ne": "SKIP"}}]}},
            {"$addFields": {
                "conf_bucket": {
                    "$cond": [{"$gte": ["$score", 0.75]}, "0.75+",
                    {"$cond": [{"$gte": ["$score", 0.65]}, "0.65-0.75",
                    "0.55-0.65"]}]
                }
            }},
            {"$group": {
                "_id": "$conf_bucket",
                "total": {"$sum": 1},
                "real": {"$sum": {"$cond": [{"$eq": ["$manual_verdict", "REAL_EDGE"]}, 1, 0]}},
            }},
            {"$sort": {"_id": -1}},
        ]
        by_bucket = []
        for r in db[VALIDATIONS_COLLECTION].aggregate(bucket_pipeline):
            t = r["total"]
            by_bucket.append({
                "bucket": r["_id"],
                "total": t,
                "real": r["real"],
                "real_edge_rate": round(r["real"] / t * 100, 1) if t > 0 else None,
            })

        return {
            "total": total,
            "validated": validated,
            "pending": pending,
            "verdicts": verdict_counts,
            "real_edge_rate": real_edge_rate,
            "execution_rate": exec_rate,
            "trap_rate": trap_rate,
            "by_edge_type": by_type,
            "by_confidence_bucket": by_bucket,
            "sample_sufficient": meaningful >= 10,
        }
    except Exception as e:
        logger.error(f"[Validation] Failed to get metrics: {e}")
        return {"total": 0, "validated": 0, "pending": 0, "error": str(e)}
