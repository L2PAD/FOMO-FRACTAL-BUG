"""
Forecast Recorder — logs every prediction as a truth snapshot.

Records the FULL outcome set per event (not just the selected pick),
enabling ranking quality analysis and structure edge validation.

Called strictly AFTER event_decision.decide_event() produces the final decision.
"""
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("prediction_lab.recorder")


def record_forecast(event: dict, overlay: dict, outcome_overlays: list[dict],
                    structure_analysis: dict | None, db) -> str | None:
    """Record a forecast snapshot for later validation.

    Returns forecastId or None if not eligible for recording.
    """
    action = overlay.get("action", "WATCH")

    # Only record forecasts with meaningful signals
    if action == "AVOID" and overlay.get("confidence") == "low":
        return None

    bp = overlay.get("best_pick")
    sizing = overlay.get("sizing", {})
    event_id = event.get("event_id", "")
    market_id = bp.get("market_id", "") if bp else ""

    # Build family key
    family_key = _build_family_key(event, overlay)

    # Build full outcomes array (critical for ranking validation)
    outcomes = []
    for ov in outcome_overlays:
        outcomes.append({
            "market_id": ov.get("market_id", ""),
            "label": ov.get("_label", ""),
            "market_prob": ov.get("market_prob", 0),
            "fair_prob": ov.get("fair_prob", 0),
            "edge": ov.get("edge", 0),
            "edge_pct": ov.get("edge_pct", 0),
            "confidence": ov.get("confidence", "low"),
            "action": ov.get("action", "WATCH"),
            "structure_edge": ov.get("structure_edge", 0),
            "selected": ov.get("market_id") == market_id,
        })

    # Sort by edge descending for ranking
    outcomes.sort(key=lambda o: abs(o.get("edge", 0)), reverse=True)

    forecast_id = str(uuid.uuid4())[:12]

    record = {
        "forecast_id": forecast_id,
        "event_id": event_id,
        "market_id": market_id,
        "platform": "polymarket",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": event.get("end_date"),
        "resolved": False,
        "resolve_attempts": 0,

        # Classification
        "market_type": event.get("event_type", "other"),
        "family_key": family_key,
        "asset": event.get("asset_group", ""),
        "category": event.get("category", ""),
        "is_multi": event.get("is_multi", False),
        "question": event.get("title", ""),

        # Primary prediction
        "market_prob": bp.get("market_prob", 0) if bp else 0,
        "fair_prob": bp.get("fair_prob", 0) if bp else 0,
        "edge": bp.get("edge", 0) if bp else 0,
        "edge_pct": bp.get("edge_pct", 0) if bp else 0,
        "confidence": overlay.get("confidence", "low"),
        "edge_quality": overlay.get("edge_quality", "low"),

        # Decision
        "action": action,
        "urgency": overlay.get("urgency", "watch"),
        "size_label": sizing.get("size_label", "NONE"),
        "size_fraction": sizing.get("size_fraction", 0),

        # Structure
        "structure_edge": bp.get("structure_edge", 0) if bp else 0,

        # Reasoning
        "summary": overlay.get("summary", ""),
        "why": overlay.get("why", []),
        "competition": overlay.get("competition", ""),

        # Full outcome set (critical for multi-outcome validation)
        "outcomes": outcomes,
        "outcomes_count": len(outcomes),

        # Price trajectory (populated by price_tracker background job)
        "price_snapshots": [],

        # Structure analysis snapshot
        "structure_snapshot": {
            "ladder_quality": structure_analysis.get("ladder_quality", 0) if structure_analysis else None,
            "monotonic": structure_analysis.get("monotonic") if structure_analysis else None,
            "best_pick": structure_analysis.get("best_pick") if structure_analysis else None,
        } if structure_analysis else None,
    }

    try:
        # Deduplicate: don't record same event_id + market_id within same session
        existing = db.forecast_records.find_one(
            {"event_id": event_id, "market_id": market_id, "resolved": False}
        )
        if existing:
            return existing.get("forecast_id")

        db.forecast_records.insert_one(record)
        db.forecast_records.create_index("forecast_id", unique=True, background=True)
        db.forecast_records.create_index("resolved", background=True)
        db.forecast_records.create_index("family_key", background=True)
        db.forecast_records.create_index("created_at", background=True)
        logger.info(f"Recorded forecast {forecast_id} for {event_id} [{action}]")
        return forecast_id
    except Exception as e:
        logger.error(f"Failed to record forecast: {e}")
        return None


def _build_family_key(event: dict, overlay: dict) -> str:
    """Build family key: marketType:asset:expiryBucket:liquidityBucket"""
    market_type = event.get("event_type", "other")
    asset = event.get("asset_group", "na") or "na"
    end_date = event.get("end_date")
    liquidity = event.get("liquidity", 0)
    return build_family_key(market_type, asset, end_date, liquidity)


def build_family_key(market_type: str, asset: str, end_date: str | None, liquidity: float) -> str:
    """Public utility: build family key from components."""
    asset = asset or "na"

    # Expiry bucket
    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            hours = max(0, (end - datetime.now(timezone.utc)).total_seconds() / 3600)
            if hours < 6:
                expiry = "lt_6h"
            elif hours < 24:
                expiry = "lt_24h"
            elif hours < 168:
                expiry = "lt_7d"
            else:
                expiry = "gt_7d"
        except Exception:
            expiry = "unknown"
    else:
        expiry = "unknown"

    # Liquidity bucket
    if liquidity < 10000:
        liq_bucket = "low_liq"
    elif liquidity < 100000:
        liq_bucket = "mid_liq"
    else:
        liq_bucket = "high_liq"

    return f"{market_type}:{asset}:{expiry}:{liq_bucket}"
