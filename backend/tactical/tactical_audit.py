"""
Tactical Audit
================
Block X — Task X.5

Logs the complete tactical decision path for transparency and debugging.
Every tactical call can be reconstructed from its audit trail.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _get_db():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    return MongoClient(mongo_url)[db_name]


def log_tactical_decision(
    asset: str,
    snapshot: dict,
    signals: dict,
    fusion: dict,
    advice: dict,
    source: str = "live",
) -> str:
    """
    Log a complete tactical decision path to the database.

    Returns the audit ID.
    """
    db = _get_db()

    doc = {
        "asset": asset,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input": {
            "imbalance": snapshot.get("imbalance"),
            "dominance": snapshot.get("dominance"),
            "aggressor_bias": snapshot.get("aggressor_bias"),
            "cascade_active": snapshot.get("cascade_active"),
            "cascade_direction": snapshot.get("cascade_direction"),
            "cascade_phase": snapshot.get("cascade_phase"),
            "funding_score": snapshot.get("funding_score"),
            "funding_label": snapshot.get("funding_label"),
            "absorption": snapshot.get("absorption"),
            "absorption_side": snapshot.get("absorption_side"),
            "oi_delta_pct": snapshot.get("oi_delta_pct"),
            "volume_delta": snapshot.get("volume_delta"),
            "uncertainty": snapshot.get("uncertainty"),
            "regime": snapshot.get("regime"),
            "phase": snapshot.get("phase"),
        },
        "signals": {
            k: v for k, v in signals.items()
            if v is True or (isinstance(v, str) and v)
        },
        "fusion": {
            "score": fusion.get("score"),
            "bias": fusion.get("bias"),
            "signal_strength": fusion.get("signal_strength"),
            "active_signals": fusion.get("active_signals"),
            "bearish_count": fusion.get("bearish_count"),
            "bullish_count": fusion.get("bullish_count"),
        },
        "advice": advice,
    }

    result = db["tactical_audit_log"].insert_one(doc)
    return str(result.inserted_id)


def get_recent_audits(asset: str = "BTC", limit: int = 20) -> list:
    """Retrieve recent tactical audit entries."""
    db = _get_db()
    docs = list(
        db["tactical_audit_log"]
        .find({"asset": asset}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )
    return docs
