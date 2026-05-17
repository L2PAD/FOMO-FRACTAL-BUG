"""
Exchange Adapter — isolates Prediction module from Exchange internals.
Reads latest forecasts from DB only. Never imports Exchange services.

Returns enriched structure:
  - scenarios with probabilities + ranges
  - direction (5-level)
  - regime
  - structural_risk (reversal, breakdown, drawdown)
  - calibrated confidence
  - decision layer output
"""
import os
from pymongo import MongoClient, DESCENDING


def _get_db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "intelligence_engine")]


def get_forecast(asset: str, horizon: str = "30D") -> dict | None:
    """
    Get latest exchange forecast with full intelligence for an asset.
    Returns None if unavailable — caller must handle gracefully.
    """
    try:
        db = _get_db()
        doc = db["exchange_forecasts"].find_one(
            {"asset": asset.upper(), "horizon": horizon},
            {"_id": 0},
            sort=[("createdAt", DESCENDING)],
        )
        if not doc:
            return None

        audit = doc.get("audit", {})

        # --- Scenarios ---
        scenarios_raw = doc.get("scenarios", {})
        scenarios_list = scenarios_raw.get("scenarios", [])
        scenario_audit = audit.get("scenarioAudit", {})
        calibrated_probs = scenario_audit.get("calibrated_probs", {})

        parsed_scenarios = {}
        for s in scenarios_list:
            stype = s.get("type", "base")
            cal_prob = calibrated_probs.get(stype)
            parsed_scenarios[stype] = {
                "probability": float(cal_prob if cal_prob is not None else s.get("probability", 0)),
                "expected_move_pct": float(s.get("expected_move", 0)),
                "range_low_pct": float(s["range"][0]) if s.get("range") and len(s["range"]) >= 2 else 0,
                "range_high_pct": float(s["range"][1]) if s.get("range") and len(s["range"]) >= 2 else 0,
                "path_type": s.get("path_type", "unknown"),
                "confidence_tag": s.get("confidence_tag", "uncertain"),
            }

        # --- Direction (5-level from audit) ---
        direction = audit.get("directionClass", doc.get("direction", "NEUTRAL"))

        # --- Regime ---
        regime = audit.get("regime", "UNKNOWN")

        # --- Structural Risk (combined block) ---
        structure_v2 = audit.get("structure_v2", {})
        components = structure_v2.get("components", {})
        reversal_risk = float(components.get("reversal_pressure", 0))
        breakdown_risk = float(components.get("breakdown_support", 0))
        # Drawdown from structure bearish pressure
        drawdown_pressure = float(structure_v2.get("bearish", 0))
        combined_risk = (reversal_risk * 0.4 + breakdown_risk * 0.3 + drawdown_pressure * 0.3)

        structural_risk = {
            "reversal_risk": round(reversal_risk, 4),
            "breakdown_risk": round(breakdown_risk, 4),
            "drawdown_pressure": round(drawdown_pressure, 4),
            "combined_risk": round(combined_risk, 4),
        }

        # --- Decision Layer ---
        decision_layer = audit.get("decisionLayer", {})

        # --- Context phase from structure state ---
        context_phase = structure_v2.get("state", "unknown")

        return {
            "asset": doc.get("asset"),
            "horizon": doc.get("horizon"),
            "entry_price": float(doc.get("entryPrice", 0)),
            "target_price": float(doc.get("targetPrice", 0)),
            "expected_move_pct": float(doc.get("expectedMovePct", 0)),
            "direction": direction,
            "confidence": float(doc.get("confidence", 0)),
            "confidence_raw": float(doc.get("confidenceRaw", 0)),
            "regime": regime,
            "context_phase": context_phase,
            "scenarios": parsed_scenarios,
            "dominant_scenario": scenarios_raw.get("dominant", "base"),
            "structural_risk": structural_risk,
            "decision_layer": {
                "direction": decision_layer.get("direction", "NEUTRAL"),
                "strength": float(decision_layer.get("strength", 0)),
                "confidence": float(decision_layer.get("confidence", 0)),
                "rationale": decision_layer.get("rationale", []),
            },
            "created_at": doc.get("createdAt"),
        }
    except Exception:
        return None
