"""
User Intent Score — Dynamic Conversion Pressure Engine.

Calculates user's purchase intent from behavior data.
Score 0-100 drives dynamic pressure level.

Formula:
  signal_views * 2 + detail_opens * 5 + cta_clicks * 10
  + missed_edges * 8 + session_minutes * 1.5
  × 0.9 decay per 24h

Interpretation:
  0-20   COLD      → reduce pressure
  20-50  WARM      → standard pressure
  50-80  HOT       → increase pressure
  80-100 VERY_HOT  → maximum pressure
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fomo_mobile")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Weight config
WEIGHTS = {
    "signal_view": 2,
    "VIEW_SCREEN": 1,
    "VIEW_ASSET": 1.5,
    "signal_detail_open": 5,
    "signal_click": 10,
    "edge_click": 8,
    "paywall_view": 12,
    "paywall_dismiss": 6,
    "TRACK_EDGE": 8,
    "TIME_ON_SCREEN": 0.5,  # per event (approx 30s each)
}

DECAY_PER_24H = 0.9
MAX_SCORE = 100


def calculate_intent_score(user_id: str) -> dict:
    """
    Calculate real-time user intent score from behavior events.
    Returns score + intent level + pressure modifier.
    """
    if not user_id:
        return {"score": 0, "level": "COLD", "modifier": -1}

    now = datetime.now(timezone.utc)
    # Look at last 7 days of behavior
    cutoff = now - timedelta(days=7)

    events = list(db.behavior_events.find({
        "userId": user_id,
        "createdAt": {"$gte": cutoff},
    }).sort("createdAt", DESCENDING))

    if not events:
        return {"score": 0, "level": "COLD", "modifier": -1}

    raw_score = 0.0

    for ev in events:
        ev_type = ev.get("type", "")
        weight = WEIGHTS.get(ev_type, 0)
        if weight == 0:
            continue

        # Time decay: older events worth less
        ev_time = ev.get("createdAt")
        if ev_time:
            if isinstance(ev_time, str):
                try:
                    ev_time = datetime.fromisoformat(ev_time.replace("Z", "+00:00"))
                except Exception:
                    ev_time = now
            if ev_time.tzinfo is None:
                ev_time = ev_time.replace(tzinfo=timezone.utc)
            days_ago = (now - ev_time).total_seconds() / 86400
            decay = DECAY_PER_24H ** days_ago
        else:
            decay = 0.5

        raw_score += weight * decay

    # Bonus: missed edges (from signal_history with outcome)
    missed = db.signal_history.count_documents({
        "outcome": {"$exists": True},
        "pnlPct": {"$gt": 0},
    })
    raw_score += min(missed, 5) * 8  # Cap at 5 missed

    # Normalize to 0-100
    score = min(MAX_SCORE, round(raw_score))

    # Determine level
    if score >= 80:
        level = "VERY_HOT"
        modifier = 2
    elif score >= 50:
        level = "HOT"
        modifier = 1
    elif score >= 20:
        level = "WARM"
        modifier = 0
    else:
        level = "COLD"
        modifier = -1

    return {
        "score": score,
        "level": level,
        "modifier": modifier,
        "eventsCount": len(events),
        "rawScore": round(raw_score, 1),
    }


def get_dynamic_pressure(signal_pressure_level: int, user_id: str) -> dict:
    """
    Combine signal-based pressure with user intent for personalized experience.

    signal_pressure_level: 1-4 from Decision Framework
    user_id: for behavior lookup

    Returns: adjusted pressure level + personalized text
    """
    intent = calculate_intent_score(user_id)
    modifier = intent["modifier"]

    # Final pressure = signal pressure + intent modifier, clamped to 1-4
    final_level = max(1, min(4, signal_pressure_level + modifier))

    # Dynamic pressure texts by level
    PRESSURE_TEXTS = {
        1: "PRO users already watching this",
        2: "PRO users already positioning",
        3: "Entry window active — PRO users inside",
        4: "You're late — PRO users already entered",
    }

    # Hot user gets personalized nudge
    NUDGE_TEXTS = {
        "VERY_HOT": "You've been watching this — PRO users already inside",
        "HOT": "You keep coming back to this — entry window narrowing",
        "WARM": None,
        "COLD": None,
    }

    pressure_text = PRESSURE_TEXTS[final_level]
    nudge = NUDGE_TEXTS.get(intent["level"])

    return {
        "pressureLevel": final_level,
        "pressureText": nudge or pressure_text,
        "intentScore": intent["score"],
        "intentLevel": intent["level"],
        "signalPressure": signal_pressure_level,
    }
