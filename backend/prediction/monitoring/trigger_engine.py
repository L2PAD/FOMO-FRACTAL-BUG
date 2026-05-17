"""
Trigger Engine — decides whether transitions warrant user attention.

Implements:
  - priority classification (high/medium/low)
  - decay logic (suppress repeat alerts within cooldown)
  - dedup by signal_hash
"""
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient


def _col():
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "intelligence_engine")]
    return db["prediction_alert_log"]


# Cooldown per alert type (minutes)
ALERT_DECAY = {
    "entry_window_open": 15,
    "repricing_started": 10,
    "overheated": 30,
    "thesis_weakened": 20,
    "new_mispricing": 10,
    "watch_to_actionable": 5,
    "size_upgraded": 15,
    "size_downgraded": 15,
    "entry_window_closed": 30,
    "new_market": 60,
}


def should_fire(market_id: str, alert_type: str, signal_hash: str) -> bool:
    """
    Check if this alert should fire (not suppressed by decay or dedup).

    Returns True if alert should be created.
    """
    decay_minutes = ALERT_DECAY.get(alert_type, 15)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=decay_minutes)

    # Check for recent same-type alert on same market
    existing = _col().find_one({
        "market_id": market_id,
        "alert_type": alert_type,
        "created_at": {"$gte": cutoff},
    })

    if existing:
        # Same hash = identical state, suppress
        if existing.get("signal_hash") == signal_hash:
            return False
        # Different hash but same type within decay window — suppress low priority
        return False

    return True


def classify_transitions(transitions: list[dict]) -> list[dict]:
    """
    Convert state transitions into alert triggers.

    Returns list of {alert_type, priority, transition}
    """
    triggers = []

    for t in transitions:
        field = t.get("field")
        to_val = t.get("to")
        from_val = t.get("from")
        ttype = t.get("type")
        prio = t.get("priority", "low")

        # Map to alert types
        if ttype == "new_market":
            triggers.append({"alert_type": "new_market", "priority": "low", "transition": t})

        elif field == "recommendation":
            if to_val in ("YES_NOW", "NO_NOW") and from_val in ("WATCH", "WAIT", "YES_SMALL", "NO_SMALL"):
                triggers.append({"alert_type": "watch_to_actionable", "priority": "high", "transition": t})
            elif prio == "high" and to_val == "AVOID":
                triggers.append({"alert_type": "thesis_weakened", "priority": "high", "transition": t})
            else:
                triggers.append({"alert_type": "recommendation_change", "priority": prio, "transition": t})

        elif field == "repricing_state":
            if to_val in ("fresh_mispricing",):
                triggers.append({"alert_type": "new_mispricing", "priority": "high", "transition": t})
            elif to_val in ("early_repricing",) and from_val in ("stalled", "fresh_mispricing"):
                triggers.append({"alert_type": "repricing_started", "priority": "high", "transition": t})
            elif to_val in ("overheated", "panic_move"):
                triggers.append({"alert_type": "overheated", "priority": "medium", "transition": t})
            else:
                triggers.append({"alert_type": "repricing_change", "priority": prio, "transition": t})

        elif field == "entry_action":
            if to_val == "enter_now":
                triggers.append({"alert_type": "entry_window_open", "priority": "high", "transition": t})
            elif to_val in ("too_late", "do_not_enter"):
                triggers.append({"alert_type": "entry_window_closed", "priority": "medium", "transition": t})

        elif field == "size":
            if ttype == "size_upgrade":
                triggers.append({"alert_type": "size_upgraded", "priority": "medium", "transition": t})
            elif ttype == "size_downgrade":
                triggers.append({"alert_type": "size_downgraded", "priority": "medium", "transition": t})

        elif field == "stage":
            if to_val == "triggered":
                triggers.append({"alert_type": "entry_window_open", "priority": "high", "transition": t})
            elif to_val == "invalidated":
                triggers.append({"alert_type": "thesis_weakened", "priority": "high", "transition": t})

    return triggers


def log_alert(market_id: str, alert_type: str, signal_hash: str, alert_data: dict) -> None:
    """Log fired alert to prevent re-triggering within decay window."""
    _col().insert_one({
        "market_id": market_id,
        "alert_type": alert_type,
        "signal_hash": signal_hash,
        "created_at": datetime.now(timezone.utc),
        "data": alert_data,
    })
