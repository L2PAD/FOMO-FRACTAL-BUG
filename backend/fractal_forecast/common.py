"""
Fractal Forecast — Shared utilities
=====================================
DB access, index management, constants shared across all pipelines.
"""

import os
from pymongo import MongoClient, ASCENDING, DESCENDING

# DEPRECATED P1: Node :8003 sidecar has been retired in favour of the
# Python-native fractal engine (fractal_forecast.native_engine).  We
# keep this constant only to surface a clear error if any caller still
# references it.  No live request should ever hit this URL.
NODE_URL = "http://127.0.0.1:8003"  # DEPRECATED — DO NOT USE

STANDARD_HORIZONS = {
    "7D": 7,
    "30D": 30,
    "90D": 90,
    "180D": 180,
    "365D": 365,
}

HIT_THRESHOLDS = {
    "7D": 0.03,
    "30D": 0.05,
    "90D": 0.08,
    "180D": 0.12,
    "365D": 0.15,
}

STANCE_TO_DIR = {
    "BULLISH": "UP",
    "BEARISH": "DOWN",
    "HOLD": "NEUTRAL",
    "LONG": "UP",
    "SHORT": "DOWN",
    "BUY": "UP",
    "SELL": "DOWN",
}


def get_db():
    # TRADING-ACTIVATION-3: align with rest of codebase — use safe default
    # for MONGO_URL (.env may not be loaded in standalone CLI calls).
    # Default DB switched to fomo_mobile to match canonical Decision Engine
    # source-of-truth (per TRADING-ACTIVATION-1 migration).
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "fomo_mobile")]


def get_forecast_col(scope: str):
    """Each scope gets its own collection."""
    db = get_db()
    col_name = f"{scope.lower()}_fractal_forecasts"
    return db[col_name]


def get_ohlcv_col():
    db = get_db()
    return db["fractal_canonical_ohlcv"]


def ensure_indexes_for_scope(scope: str):
    col = get_forecast_col(scope)
    col.create_index(
        [("horizon", ASCENDING), ("createdBucket", ASCENDING)],
        unique=True,
        name="idx_unique_per_day",
    )
    col.create_index(
        [("horizon", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_perf_query",
    )
    col.create_index(
        [("status", ASCENDING), ("evaluateAt", ASCENDING)],
        name="idx_eval_lookup",
    )
    col.create_index(
        [("createdAt", ASCENDING)],
        expireAfterSeconds=365 * 24 * 3600,
        name="idx_ttl_12mo",
    )
    print(f"[FractalForecast] Indexes ensured for {scope}")
