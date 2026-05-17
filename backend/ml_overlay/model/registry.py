"""
Model Registry — save/load trained models to MongoDB + filesystem.
"""

import os
import joblib
import hashlib
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = "intelligence_engine"
REGISTRY_COLLECTION = "ml_overlay_registry"
MODEL_DIR = "/app/backend/ml_overlay/artifacts"


def _get_col():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME][REGISTRY_COLLECTION]


def save_model(train_result: dict, walk_forward_metrics: list) -> str:
    """
    Save model artifact to disk and metadata to MongoDB.
    Returns model_id.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)

    model = train_result["model"]
    horizon = train_result["horizon"]
    trained_at = train_result["trainedAt"]

    # Generate model ID
    model_id = hashlib.sha256(f"{horizon}_{trained_at}".encode()).hexdigest()[:16]
    filename = f"overlay_{horizon}_{model_id}.joblib"
    filepath = os.path.join(MODEL_DIR, filename)

    # Save to disk
    joblib.dump(model, filepath)

    # Save metadata to Mongo
    col = _get_col()
    doc = {
        "modelId": model_id,
        "modelName": f"overlay_{horizon}",
        "horizon": horizon,
        "trainEnd": train_result["trainEnd"],
        "trainRows": train_result["trainRows"],
        "trainedAt": trained_at,
        "artifactPath": filepath,
        "featureImportance": train_result["featureImportance"],
        "walkForwardMetrics": walk_forward_metrics,
        "status": "ACTIVE",
        "createdAt": int(datetime.now(timezone.utc).timestamp() * 1000),
    }
    col.insert_one(doc)

    return model_id


def load_model(horizon: str):
    """
    Load the latest active model for a given horizon.
    Returns (model, metadata) or (None, None).
    """
    col = _get_col()
    doc = col.find_one(
        {"horizon": horizon, "status": "ACTIVE"},
        {"_id": 0},
        sort=[("createdAt", DESCENDING)],
    )

    if not doc or not os.path.exists(doc.get("artifactPath", "")):
        return None, None

    model = joblib.load(doc["artifactPath"])
    return model, doc


def get_registry_status() -> list:
    """Get all registered models."""
    col = _get_col()
    return list(col.find({}, {"_id": 0}).sort("createdAt", DESCENDING).limit(10))


def register_model(metadata: dict) -> str:
    """
    Register a model directly with provided metadata.
    Used by apply-pruning to register pruned models.
    Returns model_id.
    """
    col = _get_col()
    doc = {
        **metadata,
        "createdAt": int(datetime.now(timezone.utc).timestamp() * 1000),
    }
    # Ensure no _id conflicts
    if "_id" in doc:
        del doc["_id"]
    col.insert_one(doc)
    return metadata.get("modelId", "")
