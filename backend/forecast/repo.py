"""
Forecast Repository
====================
MongoDB read/write + indexes + idempotency.
All writes go through this module — no direct collection access elsewhere.
Config is injected via init_repo() — no os.environ reads here.
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timezone

from forecast import ForecastRecord, Horizon
from forecast.config import FractalConfig

# Module-level config — set once via init_repo()
_config: FractalConfig | None = None


def init_repo(config: FractalConfig):
    """Initialize repo with injected config. Called once at module startup."""
    global _config
    _config = config


def _cfg() -> FractalConfig:
    if _config is None:
        raise RuntimeError("Forecast repo not initialized. Call init_repo(config) first.")
    return _config


def _get_col():
    c = _cfg()
    client = MongoClient(c.mongo_url)
    return client[c.db_name][c.forecasts_collection]


def _get_runs_col():
    c = _cfg()
    client = MongoClient(c.mongo_url)
    return client[c.db_name][c.runs_collection]


def ensure_indexes():
    """Create required indexes for idempotency and query performance."""
    col = _get_col()

    # Unique: one forecast per asset+horizon+bucket_slot+source (Block 11: sub-daily)
    col.create_index(
        [("asset", ASCENDING), ("horizon", ASCENDING), ("createdBucket", ASCENDING), ("source", ASCENDING)],
        unique=True,
        name="idx_unique_forecast_per_slot",
    )

    # Fast eval lookup
    col.create_index(
        [("evaluateAfter", ASCENDING), ("evaluated", ASCENDING)],
        name="idx_eval_lookup",
    )

    # Performance query
    col.create_index(
        [("asset", ASCENDING), ("horizon", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_perf_query",
    )

    # Run grouping: find all forecasts from one run
    col.create_index(
        [("asset", ASCENDING), ("runId", ASCENDING)],
        name="idx_run_grouping",
    )

    print("[Repo] Indexes ensured")


def insert_forecast(record: ForecastRecord) -> bool:
    """Insert forecast. Returns True if inserted, False if duplicate (idempotent)."""
    col = _get_col()
    try:
        doc = record.to_mongo()
        col.insert_one(doc)

        # Block 4: Auto-record telemetry
        try:
            from intelligence.telemetry.telemetry_recorder import record_forecast_event
            scenarios = record.scenarios if hasattr(record, 'scenarios') else None
            audit = record.audit or {}
            regime_adj = (audit.get("regimeAdjustments") or {})
            du = regime_adj.get("decision_uncertainty")
            exec_status = None
            if du is not None:
                if du < 0.3:
                    exec_status = {"mode": "normal", "sizeFactor": 1.0}
                elif du < 0.6:
                    exec_status = {"mode": "reduced", "sizeFactor": 0.75}
                else:
                    exec_status = {"mode": "minimal", "sizeFactor": 0.5}

                # FIX 4.7: Phase Risk Flagging — unstable_transition penalty
                adj_flags = regime_adj.get("flags") or []
                if "transition_caution" in adj_flags or "transition_hard_dampen" in adj_flags:
                    exec_status["sizeFactor"] = round(exec_status["sizeFactor"] * 0.7, 2)
                    exec_status["phaseRisk"] = "unstable_transition"

                # FIX 6.1: NEUTRAL Regime Correction
                regime_v2 = audit.get("regimeV2") or {}
                dom_regime = (regime_v2.get("dominant_regime") or "").lower()
                if dom_regime in ("neutral", "range"):
                    exec_status["sizeFactor"] = round(exec_status["sizeFactor"] * 0.6, 2)
                    exec_status["regimeRisk"] = "neutral_correction"
                    entropy = regime_v2.get("regime_entropy", 0.5)
                    if entropy > 0.7:
                        exec_status["sizeFactor"] = round(exec_status["sizeFactor"] * 0.7, 2)
                # FLOOR: prevent stacking from killing execution
                exec_status["sizeFactor"] = max(exec_status["sizeFactor"], 0.3)
            record_forecast_event(doc, scenarios=scenarios, execution_status=exec_status)
        except Exception:
            pass  # Telemetry failure should never block forecast storage

        return True
    except DuplicateKeyError:
        return False


def get_pending_eval(limit: int = 100) -> list[dict]:
    """Find forecasts where evaluateAfter <= now and not yet evaluated."""
    col = _get_col()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return list(
        col.find(
            {"evaluated": False, "evaluateAfter": {"$lte": now_ms}},
            {"_id": 0},
        )
        .sort("evaluateAfter", ASCENDING)
        .limit(limit)
    )


def update_eval(forecast_id: str, eval_data: dict):
    """Update only eval fields on a forecast. Never touches immutable fields."""
    col = _get_col()
    col.update_one(
        {"id": forecast_id},
        {
            "$set": {
                "evaluated": True,
                "outcome": eval_data,
            }
        },
    )


def has_forecast_for_bucket(asset: str, horizon: str, bucket: str) -> bool:
    """Check if a forecast already exists for this asset+horizon+day."""
    col = _get_col()
    return col.count_documents(
        {"asset": asset, "horizon": horizon, "createdBucket": bucket, "source": {"$ne": "backfill"}}
    ) > 0


def get_overdue_count() -> int:
    """Count forecasts that should have been evaluated but weren't."""
    col = _get_col()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return col.count_documents({"evaluated": False, "evaluateAfter": {"$lte": now_ms}})


def log_run(mode: str, generated: int, evaluated: int, errors: int, duration_ms: int, run_id: str = ""):
    """Log a scheduler run for health monitoring."""
    runs = _get_runs_col()
    runs.insert_one({
        "mode": mode,
        "runId": run_id,
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "generated": generated,
        "evaluated": evaluated,
        "errors": errors,
        "durationMs": duration_ms,
    })


def get_last_run() -> dict | None:
    """Get the most recent scheduler run."""
    runs = _get_runs_col()
    return runs.find_one({}, {"_id": 0}, sort=[("ts", DESCENDING)])


def get_stats() -> dict:
    """Get collection statistics for health monitoring."""
    col = _get_col()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    stats = {}
    for h in ["24H", "7D", "30D"]:
        total = col.count_documents({"horizon": h})
        evaluated = col.count_documents({"horizon": h, "evaluated": True})
        pending = col.count_documents({"horizon": h, "evaluated": False, "evaluateAfter": {"$gt": now_ms}})
        overdue = col.count_documents({"horizon": h, "evaluated": False, "evaluateAfter": {"$lte": now_ms}})
        stats[h] = {"total": total, "evaluated": evaluated, "pending": pending, "overdue": overdue}

    return stats
