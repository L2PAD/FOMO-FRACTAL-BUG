"""
Event Bus — single entry point for ALL platform events.

Usage:
    from notifications.events.event_bus import publish_event
    await publish_event({
        "type": "exchange.prediction.updated",
        "source": "exchange",
        "asset": "BTC",
        "severity": "medium",
        "title": "BTC 30D outlook updated",
        "payload": {"horizon": "30D", "direction": "bearish", "confidence": 0.57},
    })
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from notifications.events.event_types import EventType, EventSource, Severity
from notifications.storage.event_repo import save_event, check_dedupe


async def publish_event(event: dict) -> dict:
    """
    Normalize, dedupe-check, persist event.
    Returns the saved event dict (with generated id).
    """
    # --- Normalize ---
    if "id" not in event:
        event["id"] = f"evt_{uuid.uuid4().hex[:12]}"
    if "timestamp" not in event:
        event["timestamp"] = datetime.now(timezone.utc).isoformat()

    # Validate required fields
    assert "type" in event, "Event must have 'type'"
    assert "source" in event, "Event must have 'source'"
    event.setdefault("severity", Severity.MEDIUM.value)
    event.setdefault("title", event["type"])
    event.setdefault("payload", {})

    # --- Dedupe ---
    dedupe_key = event.get("dedupeKey")
    if not dedupe_key:
        dedupe_key = _build_dedupe_key(event)
        event["dedupeKey"] = dedupe_key

    if await check_dedupe(dedupe_key):
        return {"skipped": True, "reason": "dedupe", "dedupeKey": dedupe_key}

    # --- Persist ---
    saved = await save_event(event)

    # --- Evaluate rules → create notifications ---
    try:
        from notifications.rules.rule_engine import evaluate_rules
        notifications = await evaluate_rules(saved)
        saved["_notifications_created"] = len(notifications)
    except Exception as e:
        saved["_rule_error"] = str(e)

    return saved


def _build_dedupe_key(event: dict) -> str:
    """Build a default dedupe key from type + asset + distinguishing payload + date."""
    parts = [event["type"]]
    if event.get("asset"):
        parts.append(event["asset"])
    # Add horizon for exchange forecasts to distinguish 7D vs 30D
    payload = event.get("payload", {})
    if payload.get("horizon"):
        parts.append(str(payload["horizon"]))
    ts = event.get("timestamp", "")
    if ts:
        date_part = ts[:10]
        parts.append(date_part)
    return ":".join(parts)
