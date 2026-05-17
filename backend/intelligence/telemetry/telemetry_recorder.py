"""
Telemetry Recorder
====================
Block 4 — Task 4.1

Records every forecast as a decision-event for live monitoring.
Each event captures the full decision context: model outputs, regime,
uncertainty, execution mode, scenarios, and (later) outcomes.

Usage:
    from intelligence.telemetry.telemetry_recorder import record_forecast_event
    record_forecast_event(forecast_doc, scenarios=scenario_set)
"""

import os
from datetime import datetime, timezone

from pymongo import MongoClient


TELEMETRY_COL = "intelligence_telemetry"


def _get_db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    return MongoClient(mongo_url)[db_name]


def record_forecast_event(
    forecast_doc: dict,
    scenarios: dict | None = None,
    execution_status: dict | None = None,
    uncertainty_data: dict | None = None,
) -> str | None:
    """
    Record a single forecast as a telemetry event.

    Args:
        forecast_doc: The raw forecast document (from generator or DB)
        scenarios: ScenarioSet output (optional, 30D only)
        execution_status: Execution modulation data (optional)
        uncertainty_data: Uncertainty layer data (optional)

    Returns:
        event_id or None on failure
    """
    try:
        db = _get_db()

        # Extract audit data
        audit = forecast_doc.get("audit") or {}
        regime_v2 = audit.get("regimeV2") or {}
        regime_adj = audit.get("regimeAdjustments") or {}
        context = audit.get("context") or {}

        # Use original timestamp if available (backfill), else current time
        made_at = forecast_doc.get("madeAtTs") or forecast_doc.get("createdAt")
        if made_at and isinstance(made_at, (int, float)):
            ts = datetime.fromtimestamp(made_at / 1000, tz=timezone.utc).isoformat()
        elif made_at and isinstance(made_at, str):
            ts = made_at
        else:
            ts = datetime.now(timezone.utc).isoformat()

        # Build event
        event = {
            "event_id": f"tel_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')[:20]}_{forecast_doc.get('asset', 'UNK')}_{forecast_doc.get('horizonLabel', '?')}",
            "timestamp": ts,

            # Core
            "horizon": forecast_doc.get("horizonLabel") or f"{forecast_doc.get('horizonDays', 0)}D",
            "asset": forecast_doc.get("asset", "BTC"),

            # Model outputs
            "direction": forecast_doc.get("directionClass") or forecast_doc.get("direction"),
            "confidence": forecast_doc.get("confidence"),
            "expected_move_pct": forecast_doc.get("expectedMovePct"),
            "entry_price": forecast_doc.get("entryPrice"),
            "target_price": forecast_doc.get("targetPrice"),

            # Structure / Context
            "phase": context.get("phase"),
            "regime": regime_v2.get("dominant_regime") or forecast_doc.get("regime"),
            "regime_entropy": regime_v2.get("regime_entropy"),
            "uncertainty": regime_adj.get("decision_uncertainty"),
            "uncertainty_level": (
                "low" if (regime_adj.get("decision_uncertainty") or 0.5) < 0.3
                else "high" if (regime_adj.get("decision_uncertainty") or 0.5) >= 0.6
                else "mid"
            ),

            # Execution
            "execution_mode": execution_status.get("mode") if execution_status else None,
            "size_factor": execution_status.get("sizeFactor") if execution_status else None,

            # Scenario (30D)
            "dominant_scenario": scenarios.get("dominant") if scenarios else None,
            "scenario_confidence_tag": scenarios.get("confidence_tag") if scenarios else None,
            "scenario_probs": (
                {s["type"]: s["probability"] for s in scenarios["scenarios"]}
                if scenarios and scenarios.get("scenarios") else None
            ),
            "scenario_ranges": (
                {s["type"]: list(s["range"]) for s in scenarios["scenarios"]}
                if scenarios and scenarios.get("scenarios") else None
            ),
            "scenario_spread": scenarios.get("spread") if scenarios else None,

            # Outcome (filled later by outcome_resolver)
            "realized_return": None,
            "direction_correct": None,
            "scenario_hit": None,
            "pnl": None,
            "outcome_resolved": False,
            "outcome_date": None,
        }

        db[TELEMETRY_COL].insert_one(event)
        return event["event_id"]

    except Exception as e:
        print(f"[Telemetry] Failed to record event: {e}")
        return None


def record_from_stored_forecast(stored_doc: dict) -> str | None:
    """
    Record telemetry from a MongoDB-stored forecast document.
    Used for backfilling telemetry from existing forecasts.
    """
    scenarios = stored_doc.get("scenarios")
    audit = stored_doc.get("audit") or {}

    # Build execution_status from uncertainty
    execution_status = None
    regime_adj = audit.get("regimeAdjustments") or {}
    du = regime_adj.get("decision_uncertainty")
    if du is not None:
        if du < 0.3:
            execution_status = {"mode": "normal", "sizeFactor": 1.0}
        elif du < 0.6:
            execution_status = {"mode": "reduced", "sizeFactor": 0.75}
        else:
            execution_status = {"mode": "minimal", "sizeFactor": 0.5}

    return record_forecast_event(
        forecast_doc=stored_doc,
        scenarios=scenarios,
        execution_status=execution_status,
    )


def get_unresolved_events(limit: int = 100) -> list[dict]:
    """Get telemetry events that haven't been resolved yet."""
    db = _get_db()
    return list(db[TELEMETRY_COL].find(
        {"outcome_resolved": False},
        {"_id": 0},
    ).sort("timestamp", 1).limit(limit))


def get_recent_events(limit: int = 50, horizon: str | None = None) -> list[dict]:
    """Get recent telemetry events."""
    db = _get_db()
    query = {}
    if horizon:
        query["horizon"] = horizon
    return list(db[TELEMETRY_COL].find(
        query, {"_id": 0},
    ).sort("timestamp", -1).limit(limit))
