"""
Shadow Logger — log ML overlay predictions for later evaluation.
"""

import os
import hashlib
from datetime import datetime, timezone
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = "intelligence_engine"
SHADOW_COLLECTION = "ml_overlay_shadow"


def _get_col():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME][SHADOW_COLLECTION]


def log_shadow(
    asset: str,
    horizon: str,
    created_bucket: str,
    entry_price: float,
    rule_target: float,
    overlay_result: dict,
    features_hash: str = "",
):
    """Log a shadow overlay prediction."""
    col = _get_col()
    col.insert_one({
        "asset": asset,
        "horizon": horizon,
        "createdBucket": created_bucket,
        "entryPrice": float(entry_price),
        "ruleTarget": float(rule_target),
        "mlCorrection": float(overlay_result.get("mlCorrection", 0)),
        "mlCorrectionRaw": float(overlay_result.get("mlCorrectionRaw", 0)),
        "finalTargetShadow": float(overlay_result.get("finalTargetPrice", rule_target)),
        "ruleReturn": float(overlay_result.get("ruleReturn", 0)),
        "finalReturnShadow": float(overlay_result.get("finalReturn", 0)),
        "modelId": overlay_result.get("modelId"),
        "mode": str(overlay_result.get("mode", "SHADOW")),
        "capped": bool(overlay_result.get("capped", False)),
        "featuresHash": features_hash,
        "evaluatedShadow": False,
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
    })


def get_shadow_count() -> int:
    return _get_col().estimated_document_count()
