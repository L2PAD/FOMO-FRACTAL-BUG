"""
Prediction Output Formatter — Block 10.1
==========================================
Formats existing forecast data into a clean, unified prediction output.

NO new logic — only formatting and assembly of existing truth model results.

Output designed for:
  - User-facing display
  - Brain orchestration
  - Research layer / canonical truth reference
"""

import os
from pymongo import MongoClient, DESCENDING
from datetime import datetime, timezone


def _get_db():
    return MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]


def _map_direction(direction_class: str | None) -> str:
    """Map 5-state directionClass to user-friendly direction."""
    if not direction_class:
        return "neutral"
    dc = direction_class.upper()
    if dc in ("STRONG_BULL", "MILD_BULL"):
        return "bullish"
    if dc in ("STRONG_BEAR", "MILD_BEAR"):
        return "bearish"
    return "neutral"


def _map_uncertainty(confidence: float | None) -> str:
    """Derive uncertainty level from calibrated confidence."""
    if confidence is None:
        return "high"
    if confidence >= 0.60:
        return "low"
    if confidence >= 0.40:
        return "medium"
    return "high"


def _format_horizon_1d_7d(doc: dict) -> dict:
    """Format 24H or 7D forecast into prediction output."""
    confidence = doc.get("confidenceDirection") or doc.get("confidence") or 0.0
    return {
        "direction": _map_direction(doc.get("directionClass")),
        "confidence": round(confidence, 4),
        "uncertainty": _map_uncertainty(confidence),
        "entry_price": doc.get("entryPrice"),
        "target_price": doc.get("targetPrice"),
        "expected_move_pct": doc.get("expectedMovePct"),
        "regime": (doc.get("audit") or {}).get("regime", "unknown"),
        "model_version": doc.get("modelVersion"),
        "generated_at": doc.get("createdBucket"),
    }


def _format_horizon_30d(doc: dict) -> dict:
    """Format 30D forecast into prediction output (with scenarios)."""
    confidence = doc.get("confidenceDirection") or doc.get("confidence") or 0.0
    scenarios = doc.get("scenarios")

    base = {
        "direction": _map_direction(doc.get("directionClass")),
        "confidence": round(confidence, 4),
        "uncertainty": _map_uncertainty(confidence),
        "entry_price": doc.get("entryPrice"),
        "target_price": doc.get("targetPrice"),
        "expected_move_pct": doc.get("expectedMovePct"),
        "regime": (doc.get("audit") or {}).get("regime", "unknown"),
        "model_version": doc.get("modelVersion"),
        "generated_at": doc.get("createdBucket"),
    }

    if scenarios and isinstance(scenarios, dict):
        scenario_list = scenarios.get("scenarios", [])

        # Extract probabilities
        probs = {}
        for s in scenario_list:
            stype = s.get("type")
            if stype:
                probs[stype] = round(s.get("probability", 0.0), 4)

        # Dominant scenario
        dominant = scenarios.get("dominant", "base")

        # Path type of dominant scenario
        path = "range"
        for s in scenario_list:
            if s.get("type") == dominant:
                path = s.get("path_type", "range_hold")
                break

        # Confidence tag
        confidence_tag = scenarios.get("confidence_tag", "uncertain")

        # Engine version
        engine_version = scenarios.get("engine_version", "v1")

        base["dominant"] = dominant
        base["probabilities"] = probs
        base["path"] = path
        base["scenario_confidence_tag"] = confidence_tag
        base["engine_version"] = engine_version

        # Scenario details (compact)
        base["scenario_details"] = [
            {
                "type": s.get("type"),
                "probability": round(s.get("probability", 0), 4),
                "path_type": s.get("path_type"),
                "confidence_tag": s.get("confidence_tag"),
                "target_low": s.get("target_low"),
                "target_high": s.get("target_high"),
                "narrative": s.get("narrative"),
            }
            for s in scenario_list
        ]

    return base


def build_prediction_output(asset: str) -> dict:
    """
    Build unified prediction output for an asset across all horizons.

    Sources data ONLY from existing forecasts — no computation.
    """
    db = _get_db()
    col = db["exchange_forecasts"]
    now = datetime.now(timezone.utc)

    horizons = {}

    for horizon in ["24H", "7D", "30D"]:
        doc = col.find_one(
            {"asset": asset.upper(), "horizon": horizon},
            {"_id": 0},
            sort=[("createdAt", DESCENDING)],
        )
        if not doc:
            continue

        if horizon == "30D":
            horizons[horizon] = _format_horizon_30d(doc)
        else:
            horizons[horizon] = _format_horizon_1d_7d(doc)

    # Cross-horizon summary
    directions = [h.get("direction", "neutral") for h in horizons.values()]
    confidences = [h.get("confidence", 0) for h in horizons.values() if h.get("confidence")]

    # Consensus direction (majority vote)
    from collections import Counter
    dir_counts = Counter(directions)
    consensus = dir_counts.most_common(1)[0][0] if dir_counts else "neutral"

    # Agreement score: how aligned are the horizons
    if len(directions) > 1:
        agreement = dir_counts.most_common(1)[0][1] / len(directions)
    else:
        agreement = 1.0

    return {
        "asset": asset.upper(),
        "generated_at": now.isoformat(),
        "horizons": horizons,
        "summary": {
            "consensus_direction": consensus,
            "horizon_agreement": round(agreement, 2),
            "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
            "horizons_available": list(horizons.keys()),
        },
    }
