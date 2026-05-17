"""Sync MongoDB helper for Prediction Lab operations."""
import os

from pymongo import MongoClient

_client = None
_db = None


def get_sync_db():
    """Get sync pymongo database for prediction lab writes."""
    global _client, _db
    if _db is not None:
        return _db
    url = os.environ.get("MONGO_URL")
    name = os.environ.get("DB_NAME", "institutional")
    if not url:
        return None
    _client = MongoClient(url)
    _db = _client[name]
    return _db
