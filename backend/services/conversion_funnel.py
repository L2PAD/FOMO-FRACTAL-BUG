"""
Conversion Funnel Tracking — единственный слой, который превращает систему в бизнес.

Отслеживает каждый шаг воронки:
  Telegram → App open → Signal view → Detail open → Paywall seen → CTA click → Converted

Формула денег:
  1000 сигналов → 600 open → 400 detail → 350 paywall → 40 click → 8 купили
  Знаешь где дыра → знаешь что чинить.
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

# Ensure index
db.conversion_funnel.create_index([("userId", 1), ("signalId", 1)], unique=True, sparse=True)
db.conversion_funnel.create_index("updatedAt")
db.conversion_funnel.create_index("stage")


FUNNEL_STEPS = [
    "seen_telegram",
    "opened_app",
    "viewed_signal",
    "opened_detail",
    "paywall_seen",
    "cta_clicked",
    "converted",
]


def track_funnel_event(user_id: str, signal_id: str, event: str, meta: dict = None):
    """
    Track a single funnel event for a user+signal pair.
    Idempotent — same event won't overwrite.
    """
    if event not in FUNNEL_STEPS:
        return

    now = datetime.now(timezone.utc)

    # Get or create funnel document
    doc = db.conversion_funnel.find_one({"userId": user_id, "signalId": signal_id})

    if not doc:
        # Infer stage and intent from current signal data
        from services.intent_score_service import calculate_intent_score
        intent = calculate_intent_score(user_id)

        doc = {
            "userId": user_id,
            "signalId": signal_id,
            "stage": "UNKNOWN",
            "intent": intent.get("level", "COLD"),
            "intentScore": intent.get("score", 0),
            "events": {step: False for step in FUNNEL_STEPS},
            "timestamps": {},
            "meta": {},
            "createdAt": now,
            "updatedAt": now,
        }
        try:
            db.conversion_funnel.insert_one(doc)
        except Exception:
            doc = db.conversion_funnel.find_one({"userId": user_id, "signalId": signal_id})
            if not doc:
                return

    # Update event
    update = {
        f"events.{event}": True,
        f"timestamps.{event}": now.isoformat(),
        "updatedAt": now,
    }
    if meta:
        for k, v in meta.items():
            update[f"meta.{k}"] = v

    # Update furthest step reached
    current_idx = FUNNEL_STEPS.index(event)
    for step in FUNNEL_STEPS[:current_idx]:
        update[f"events.{step}"] = True
        if f"timestamps.{step}" not in (doc.get("timestamps") or {}):
            update[f"timestamps.{step}"] = now.isoformat()

    db.conversion_funnel.update_one(
        {"userId": user_id, "signalId": signal_id},
        {"$set": update}
    )


def get_funnel_stats(hours: int = 24) -> dict:
    """
    Get conversion funnel stats for admin dashboard.
    Shows where users drop off.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    total = db.conversion_funnel.count_documents({"createdAt": {"$gte": cutoff}})

    if total == 0:
        # Fallback: use all-time stats
        total = db.conversion_funnel.count_documents({})
        cutoff_filter = {}
    else:
        cutoff_filter = {"createdAt": {"$gte": cutoff}}

    steps = {}
    for step in FUNNEL_STEPS:
        count = db.conversion_funnel.count_documents({
            f"events.{step}": True,
            **cutoff_filter,
        })
        steps[step] = {
            "count": count,
            "rate": round(count / max(total, 1) * 100, 1),
        }

    # Drop-off analysis
    dropoffs = []
    for i in range(1, len(FUNNEL_STEPS)):
        prev = steps[FUNNEL_STEPS[i - 1]]["count"]
        curr = steps[FUNNEL_STEPS[i]]["count"]
        drop = prev - curr
        drop_rate = round(drop / max(prev, 1) * 100, 1) if prev > 0 else 0
        dropoffs.append({
            "from": FUNNEL_STEPS[i - 1],
            "to": FUNNEL_STEPS[i],
            "lost": drop,
            "dropRate": drop_rate,
        })

    # Find biggest leak
    biggest_leak = max(dropoffs, key=lambda d: d["lost"]) if dropoffs else None

    # Intent breakdown
    intent_stats = {}
    for level in ["COLD", "WARM", "HOT", "VERY_HOT"]:
        intent_total = db.conversion_funnel.count_documents({"intent": level, **cutoff_filter})
        intent_converted = db.conversion_funnel.count_documents({
            "intent": level, "events.converted": True, **cutoff_filter
        })
        intent_stats[level] = {
            "total": intent_total,
            "converted": intent_converted,
            "rate": round(intent_converted / max(intent_total, 1) * 100, 1),
        }

    return {
        "period": f"last_{hours}h",
        "totalFunnels": total,
        "steps": steps,
        "dropoffs": dropoffs,
        "biggestLeak": biggest_leak,
        "intentBreakdown": intent_stats,
        "recommendation": _get_recommendation(steps, biggest_leak),
    }


def _get_recommendation(steps: dict, leak: dict) -> str:
    """Generate actionable recommendation based on funnel data."""
    if not leak:
        return "Not enough data — keep driving traffic"

    fr = leak["from"]
    to = leak["to"]
    drop = leak["dropRate"]

    if fr == "viewed_signal" and to == "opened_detail":
        return f"Signal cards not compelling enough — {drop}% leave without opening. Test stronger headlines."
    elif fr == "opened_detail" and to == "paywall_seen":
        return f"Users browse but don't scroll to paywall — {drop}% drop. Move paywall higher or add earlier CTA."
    elif fr == "paywall_seen" and to == "cta_clicked":
        return f"Paywall seen but not clicked — {drop}% ignore. Test CTA text, pricing, or add urgency."
    elif fr == "cta_clicked" and to == "converted":
        return f"Users click but don't pay — {drop}% abandon. Check payment flow, pricing, or add trial."
    elif fr == "seen_telegram" and to == "opened_app":
        return f"Telegram messages not driving opens — {drop}% ignore. Test message format and timing."
    elif fr == "opened_app" and to == "viewed_signal":
        return f"Users open app but don't view signals — {drop}% bounce. Check home screen engagement."
    else:
        return f"Biggest drop: {fr} → {to} ({drop}%). Focus optimization here."
