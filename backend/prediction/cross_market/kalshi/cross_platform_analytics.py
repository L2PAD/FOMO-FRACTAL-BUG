"""
Cross-Platform Analytics — tracks signals and computes performance metrics.

Stores each signal in MongoDB for outcome tracking.
Provides grouped analytics by edge_case_type and platform_pair.

Metrics:
  count, win_rate, avg_predicted_edge, avg_realized_edge,
  edge_capture_ratio, execution_success_rate
"""
import os
import logging
from datetime import datetime, timezone

from pymongo import MongoClient

logger = logging.getLogger("cross_market.kalshi.analytics")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

_client = None
_db = None

COLLECTION = "cross_platform_signals"


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URL)
        _db = _client[DB_NAME]
    return _db


def store_signal(signal: dict, strategy: dict | None = None) -> str | None:
    """Store a cross-platform signal for tracking.

    Returns signal_id or None on error.
    """
    try:
        db = _get_db()
        doc = {
            "timestamp": datetime.now(timezone.utc),
            "entity": signal.get("entity", ""),
            "platform_pair": "poly_kalshi",
            "edge_case_type": signal.get("edge_case_type", "UNKNOWN"),
            "constraint_type": signal.get("constraint_type", ""),
            "gap": signal.get("gap", 0),
            "gap_pct": signal.get("gap_pct", 0),
            "score": signal.get("score", 0),
            "actionability_score": signal.get("actionability_score", 0),
            "real_edge_score": signal.get("real_edge_score"),
            "severity": signal.get("severity", "MEDIUM"),
            "actionable": signal.get("actionable", False),
            "edge_badge": signal.get("edge_badge", ""),
            "trap_flags": signal.get("trap_flags", []),
            "poly_price": signal.get("poly_price"),
            "kalshi_price": signal.get("kalshi_price"),
            "poly_volume": signal.get("components", {}).get("liquidity_score"),
            "liquidity_score": signal.get("components", {}).get("liquidity_score"),
            "execution_feasibility": signal.get("components", {}).get("execution_feasibility"),
            "cluster_id": signal.get("cluster_id", ""),
            "poly_market_id": signal.get("poly_market_id", ""),
            "kalshi_market_id": signal.get("kalshi_market_id", ""),
            "strategy_type": strategy.get("strategy_type", "") if strategy else "",
            "legs": strategy.get("legs", []) if strategy else [],
            # Outcome tracking (filled later via update_outcome)
            "outcome": None,
            "realized_edge": None,
            "execution_success": None,
            "closed_at": None,
        }
        result = db[COLLECTION].insert_one(doc)
        signal_id = str(result.inserted_id)
        logger.info(f"[Analytics] Stored signal: {signal.get('entity')} {signal.get('edge_case_type')} gap={signal.get('gap_pct')}%")

        # Auto-create validation entry
        try:
            from prediction.cross_market.kalshi.manual_validation import create_validation_entry
            val_data = {**signal, "signal_id": signal_id}
            if strategy:
                val_data["strategy_type"] = strategy.get("strategy_type", "")
                val_data["legs"] = strategy.get("legs", [])
            create_validation_entry(val_data)
        except Exception as ve:
            logger.warning(f"[Analytics] Failed to create validation entry: {ve}")

        return signal_id
    except Exception as e:
        logger.error(f"[Analytics] Failed to store signal: {e}")
        return None


def store_batch(mispricings: list[dict], strategies_map: dict | None = None):
    """Store a batch of signals from a pipeline run."""
    strategies_map = strategies_map or {}
    stored = 0
    for m in mispricings:
        cluster_id = m.get("cluster_id", "")
        strat = strategies_map.get(cluster_id)
        if store_signal(m, strat):
            stored += 1
    logger.info(f"[Analytics] Stored batch: {stored}/{len(mispricings)}")
    return stored


def get_analytics_by_edge_type() -> list[dict]:
    """Get performance analytics grouped by edge_case_type."""
    try:
        db = _get_db()
        pipeline = [
            {"$group": {
                "_id": "$edge_case_type",
                "count": {"$sum": 1},
                "actionable_count": {
                    "$sum": {"$cond": [{"$eq": ["$actionable", True]}, 1, 0]}
                },
                "avg_predicted_edge": {"$avg": "$gap_pct"},
                "avg_score": {"$avg": "$score"},
                "avg_actionability": {"$avg": "$actionability_score"},
                # Outcome metrics (only where outcome is set)
                "outcomes_tracked": {
                    "$sum": {"$cond": [{"$ne": ["$outcome", None]}, 1, 0]}
                },
                "wins": {
                    "$sum": {"$cond": [{"$eq": ["$outcome", True]}, 1, 0]}
                },
                "avg_realized_edge": {
                    "$avg": {"$cond": [
                        {"$ne": ["$realized_edge", None]},
                        "$realized_edge",
                        None
                    ]}
                },
                "executed": {
                    "$sum": {"$cond": [{"$eq": ["$execution_success", True]}, 1, 0]}
                },
                "execution_tracked": {
                    "$sum": {"$cond": [{"$ne": ["$execution_success", None]}, 1, 0]}
                },
                # Severity distribution
                "strong_count": {
                    "$sum": {"$cond": [{"$eq": ["$severity", "STRONG"]}, 1, 0]}
                },
                "high_count": {
                    "$sum": {"$cond": [{"$eq": ["$severity", "HIGH"]}, 1, 0]}
                },
                "medium_count": {
                    "$sum": {"$cond": [{"$eq": ["$severity", "MEDIUM"]}, 1, 0]}
                },
            }},
            {"$sort": {"count": -1}},
        ]
        results = list(db[COLLECTION].aggregate(pipeline))

        analytics = []
        for r in results:
            edge_type = r["_id"] or "UNKNOWN"
            count = r["count"]
            outcomes = r["outcomes_tracked"]
            wins = r["wins"]
            exec_tracked = r["execution_tracked"]
            executed = r["executed"]
            avg_predicted = r.get("avg_predicted_edge") or 0
            avg_realized = r.get("avg_realized_edge") or 0

            analytics.append({
                "edge_case_type": edge_type,
                "count": count,
                "actionable_count": r["actionable_count"],
                "avg_predicted_edge": round(avg_predicted, 2),
                "avg_score": round(r.get("avg_score") or 0, 3),
                "avg_actionability": round(r.get("avg_actionability") or 0, 3),
                "win_rate": round(wins / outcomes * 100, 1) if outcomes > 0 else None,
                "avg_realized_edge": round(avg_realized, 2) if avg_realized else None,
                "edge_capture_ratio": round(avg_realized / avg_predicted, 2) if avg_predicted > 0 and avg_realized else None,
                "execution_success_rate": round(executed / exec_tracked * 100, 1) if exec_tracked > 0 else None,
                "outcomes_tracked": outcomes,
                "severity_distribution": {
                    "strong": r["strong_count"],
                    "high": r["high_count"],
                    "medium": r["medium_count"],
                },
            })

        return analytics
    except Exception as e:
        logger.error(f"[Analytics] Failed to get analytics: {e}")
        return []


def get_analytics_by_platform_pair_and_type() -> list[dict]:
    """Get analytics grouped by platform_pair + edge_case_type."""
    try:
        db = _get_db()
        pipeline = [
            {"$group": {
                "_id": {
                    "platform_pair": "$platform_pair",
                    "edge_case_type": "$edge_case_type",
                },
                "count": {"$sum": 1},
                "actionable_count": {
                    "$sum": {"$cond": [{"$eq": ["$actionable", True]}, 1, 0]}
                },
                "avg_predicted_edge": {"$avg": "$gap_pct"},
                "avg_score": {"$avg": "$score"},
                "outcomes_tracked": {
                    "$sum": {"$cond": [{"$ne": ["$outcome", None]}, 1, 0]}
                },
                "wins": {
                    "$sum": {"$cond": [{"$eq": ["$outcome", True]}, 1, 0]}
                },
                "avg_realized_edge": {
                    "$avg": {"$cond": [
                        {"$ne": ["$realized_edge", None]},
                        "$realized_edge",
                        None
                    ]}
                },
                "executed": {
                    "$sum": {"$cond": [{"$eq": ["$execution_success", True]}, 1, 0]}
                },
                "execution_tracked": {
                    "$sum": {"$cond": [{"$ne": ["$execution_success", None]}, 1, 0]}
                },
            }},
            {"$sort": {"count": -1}},
        ]
        results = list(db[COLLECTION].aggregate(pipeline))

        analytics = []
        for r in results:
            gid = r["_id"]
            count = r["count"]
            outcomes = r["outcomes_tracked"]
            wins = r["wins"]
            exec_tracked = r["execution_tracked"]
            executed = r["executed"]
            avg_predicted = r.get("avg_predicted_edge") or 0
            avg_realized = r.get("avg_realized_edge") or 0

            analytics.append({
                "platform_pair": gid.get("platform_pair", "poly_kalshi"),
                "edge_case_type": gid.get("edge_case_type", "UNKNOWN"),
                "count": count,
                "actionable_count": r["actionable_count"],
                "avg_predicted_edge": round(avg_predicted, 2),
                "avg_score": round(r.get("avg_score") or 0, 3),
                "win_rate": round(wins / outcomes * 100, 1) if outcomes > 0 else None,
                "avg_realized_edge": round(avg_realized, 2) if avg_realized else None,
                "edge_capture_ratio": round(avg_realized / avg_predicted, 2) if avg_predicted > 0 and avg_realized else None,
                "execution_success_rate": round(executed / exec_tracked * 100, 1) if exec_tracked > 0 else None,
                "outcomes_tracked": outcomes,
            })

        return analytics
    except Exception as e:
        logger.error(f"[Analytics] Failed to get platform analytics: {e}")
        return []


def get_recent_signals(limit: int = 50) -> list[dict]:
    """Get recent signals for review."""
    try:
        db = _get_db()
        cursor = db[COLLECTION].find(
            {},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
        signals = []
        for doc in cursor:
            if "timestamp" in doc and doc["timestamp"]:
                doc["timestamp"] = doc["timestamp"].isoformat()
            if "closed_at" in doc and doc["closed_at"]:
                doc["closed_at"] = doc["closed_at"].isoformat()
            signals.append(doc)
        return signals
    except Exception as e:
        logger.error(f"[Analytics] Failed to get recent signals: {e}")
        return []


def get_signal_count() -> int:
    """Get total signal count."""
    try:
        db = _get_db()
        return db[COLLECTION].count_documents({})
    except Exception:
        return 0
