"""
Feed Health — monitors feed data quality and freshness.

Tracks:
  - Active events count
  - Active outcomes count
  - Snapshot freshness
  - Overlay freshness
  - Source status
"""
import time
import logging

logger = logging.getLogger("feed.health")

_health_state = {
    "last_sync": 0,
    "events_count": 0,
    "markets_count": 0,
    "overlays_count": 0,
    "sync_errors": 0,
    "sync_success": 0,
}


def update_health(events: int, markets: int, overlays: int):
    _health_state["last_sync"] = time.time()
    _health_state["events_count"] = events
    _health_state["markets_count"] = markets
    _health_state["overlays_count"] = overlays
    _health_state["sync_success"] += 1


def record_error():
    _health_state["sync_errors"] += 1


def get_health() -> dict:
    now = time.time()
    last = _health_state["last_sync"]
    age = round(now - last) if last > 0 else -1

    if age < 0:
        status = "no_data"
    elif age < 120:
        status = "healthy"
    elif age < 600:
        status = "degraded"
    else:
        status = "stale"

    return {
        "status": status,
        "last_sync_age_seconds": age,
        "events_count": _health_state["events_count"],
        "markets_count": _health_state["markets_count"],
        "overlays_count": _health_state["overlays_count"],
        "sync_success": _health_state["sync_success"],
        "sync_errors": _health_state["sync_errors"],
    }
