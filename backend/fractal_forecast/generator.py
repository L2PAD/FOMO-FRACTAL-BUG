"""
Fractal Forecast Generator
============================
Creates immutable forecast snapshots from Fractal Engine data.

Data sources:
  - /api/fractal/v2.1/terminal → horizonMatrix (7d, 14d, 30d)
  - /api/ui/overview → horizons (30d, 90d, 180d, 365d)
  - currentPrice from terminal response

Rules:
  - Each forecast is a snapshot — NEVER modified after creation
  - entryPrice is ALWAYS stored (point of reference)
  - targetPrice = entryPrice * (1 + expectedReturn)
  - One forecast per scope+horizon+day (idempotent via createdBucket)
  - modelVersion is locked per pipeline run
"""

import os
import httpx
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, ASCENDING, DESCENDING

NODE_URL = "http://127.0.0.1:8003"

HORIZONS = {
    "7D": 7,
    "30D": 30,
    "90D": 90,
    "180D": 180,
    "365D": 365,
}

STANCE_TO_DIR = {
    "BULLISH": "UP",
    "BEARISH": "DOWN",
    "HOLD": "NEUTRAL",
}


def _get_col():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "intelligence_engine")]
    return db["fractal_forecasts"]


def ensure_indexes():
    col = _get_col()
    col.create_index(
        [("scope", ASCENDING), ("horizon", ASCENDING), ("createdBucket", ASCENDING)],
        unique=True,
        name="idx_unique_per_day",
    )
    col.create_index(
        [("scope", ASCENDING), ("horizon", ASCENDING), ("createdAt", DESCENDING)],
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
    print("[FractalForecast] Indexes ensured")


def _get_model_version():
    """Get fractal engine version — stable per pipeline run."""
    freeze = os.environ.get("FREEZE_VERSION")
    if freeze:
        return freeze
    try:
        r = httpx.get(f"{NODE_URL}/api/fractal/v2.1/terminal?horizon=7d", timeout=10)
        if r.status_code == 200:
            meta = r.json().get("meta", {})
            return meta.get("contractVersion", "unknown")
    except Exception:
        pass
    return "unknown"


def _fetch_terminal_data():
    """Fetch horizonMatrix from fractal terminal (7d, 14d, 30d)."""
    try:
        r = httpx.get(f"{NODE_URL}/api/fractal/v2.1/terminal?horizon=30d", timeout=15)
        if r.status_code == 200:
            data = r.json()
            matrix = {}
            for h in data.get("horizonMatrix", []):
                matrix[h["horizon"]] = h
            current_price = data.get("chart", {}).get("currentPrice", 0)
            return matrix, current_price
    except Exception as e:
        print(f"[FractalForecast] Terminal fetch error: {e}")
    return {}, 0


def _fetch_overview_data():
    """Fetch overview horizons (30d, 90d, 180d, 365d)."""
    try:
        r = httpx.get(f"{NODE_URL}/api/ui/overview?asset=btc&horizon=30", timeout=15)
        if r.status_code == 200:
            data = r.json()
            horizons = {}
            for h in data.get("horizons", []):
                days = h.get("days")
                if days:
                    horizons[days] = h
            return horizons
    except Exception as e:
        print(f"[FractalForecast] Overview fetch error: {e}")
    return {}


def generate_forecasts(scope="BTC"):
    """
    Generate fractal forecast snapshots for all horizons.
    Idempotent: skips if forecast already exists for today (unique index).
    modelVersion is locked for the entire pipeline run.
    """
    col = _get_col()
    now = datetime.now(timezone.utc)
    today_bucket = now.strftime("%Y-%m-%d")

    # Lock version for this run
    model_version = _get_model_version()

    # Fetch data from fractal engine
    terminal_matrix, current_price = _fetch_terminal_data()
    overview_horizons = _fetch_overview_data()

    if current_price <= 0:
        print("[FractalForecast] No current price available, skipping generation")
        return 0

    generated = 0

    for horizon_key, horizon_days in HORIZONS.items():
        # Get data from the appropriate source
        direction = "NEUTRAL"
        expected_return = 0.0
        confidence = 0.0

        # Try terminal matrix first (7d, 30d)
        terminal_key = f"{horizon_days}d"
        if terminal_key in terminal_matrix:
            tm = terminal_matrix[terminal_key]
            direction = tm.get("direction", "NEUTRAL")
            expected_return = tm.get("expectedReturn", 0)
            confidence = tm.get("confidence", 0)

        # For 30d+ horizons, prefer overview data if terminal has zero confidence
        if horizon_days >= 30 and horizon_days in overview_horizons:
            ov = overview_horizons[horizon_days]
            ov_return = ov.get("medianProjectionPct", 0) / 100
            ov_conf = ov.get("confidencePct", 0) / 100
            ov_stance = ov.get("stance", "HOLD")

            if ov_conf > confidence:
                expected_return = ov_return
                confidence = ov_conf
                direction = STANCE_TO_DIR.get(ov_stance, "NEUTRAL")

        entry_price = current_price
        target_price = entry_price * (1 + expected_return)
        evaluate_at = now + timedelta(days=horizon_days)

        doc = {
            "scope": scope,
            "createdAt": now,
            "createdBucket": today_bucket,
            "evaluateAt": evaluate_at,
            "horizon": horizon_key,
            "entryPrice": entry_price,
            "targetPrice": target_price,
            "expectedReturn": expected_return,
            "direction": direction,
            "confidence": confidence,
            "modelVersion": model_version,
            "source": "fractal",
            "signalId": f"fractal:{scope}:{horizon_key}:{today_bucket}",
            "entryPriceSource": "market_close",
            "actualPrice": None,
            "errorPct": None,
            "hit": None,
            "directionCorrect": None,
            "status": "pending",
        }

        try:
            col.insert_one(doc)
            generated += 1
        except Exception as e:
            if "duplicate key" in str(e).lower() or "E11000" in str(e):
                continue
            print(f"[FractalForecast] Insert error ({horizon_key}): {e}")

    print(f"[FractalForecast] Generated {generated} forecasts for {scope} ({today_bucket}) v={model_version}")
    return generated
