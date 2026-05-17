"""
A/B Testing Layer — Alert variant testing + event tracking.
=============================================================
Variants:
  A — Urgency (LIVE EDGE, active now, expiring)
  B — Loss framing (mispriced, you may miss)
  C — Performance trust (82% accuracy, EXTREME: 100%)
  D — Combo (A+B+C)

Stable assignment per user via hash.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger("miniapp.ab_testing")

VARIANTS = ["A", "B", "C", "D"]


def assign_variant(user_id: str) -> str:
    """Stable variant assignment — same user always gets same variant."""
    seed = hash(str(user_id)) % 100
    if seed < 25:
        return "A"
    if seed < 50:
        return "B"
    if seed < 75:
        return "C"
    return "D"


async def track_event(db, user_id: str, event_type: str, variant: str, meta: dict = None):
    """Track an A/B test event."""
    doc = {
        "user_id": str(user_id),
        "event": event_type,
        "variant": variant,
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.ab_events.insert_one(doc)
    except Exception as e:
        logger.error(f"AB track error: {e}")


def format_alert_variant(edge: dict, variant: str, performance: dict = None) -> str:
    """Format edge alert based on A/B variant."""
    edge_pct = round(edge["edge"] * 100, 1)
    conf_pct = round(edge["confidence"] * 100)
    sign = "+" if edge_pct > 0 else ""
    direction = edge["direction"]
    asset = edge["asset"]
    ttl = edge.get("ttlHours", 12)

    base = (
        f"<b>{asset}</b>\n\n"
        f"EDGE: {sign}{edge_pct}% {direction}\n"
        f"Confidence: {conf_pct}%"
    )  # noqa: F841 - kept for reference

    if variant == "A":
        return (
            f"<b>LIVE EDGE ({asset})</b>\n\n"
            f"EDGE: {sign}{edge_pct}% {direction}\n"
            f"Confidence: {conf_pct}%\n\n"
            f"Signal active now\n"
            f"Valid: ~{ttl}h"
        )

    if variant == "B":
        mispriced = abs(edge_pct)
        return (
            f"<b>EDGE DETECTED ({asset})</b>\n\n"
            f"EDGE: {sign}{edge_pct}% {direction}\n"
            f"Confidence: {conf_pct}%\n\n"
            f"Market mispriced by {mispriced}%\n"
            f"You may miss this move"
        )

    if variant == "C":
        perf_line = ""
        if performance:
            acc = performance.get("directionalAccuracy", 0)
            if acc > 0:
                perf_line = f"\nSystem accuracy: {int(acc * 100)}%"
                ext = performance.get("extremeAccuracy")
                if ext is not None and ext > 0:
                    perf_line += f"\nEXTREME: {int(ext * 100)}%"
        return (
            f"<b>EDGE ({asset})</b>\n\n"
            f"EDGE: {sign}{edge_pct}% {direction}\n"
            f"Confidence: {conf_pct}%"
            f"{perf_line}"
        )

    # D — Combo
    mispriced = abs(edge_pct)
    perf_line = ""
    if performance:
        acc = performance.get("directionalAccuracy", 0)
        if acc > 0:
            perf_line = f"\n{int(acc * 100)}% accuracy"
    return (
        f"<b>LIVE EDGE ({asset})</b>\n\n"
        f"EDGE: {sign}{edge_pct}% {direction}\n"
        f"Confidence: {conf_pct}%\n\n"
        f"Market mispriced by {mispriced}%"
        f"{perf_line}\n\n"
        f"Signal active now | ~{ttl}h"
    )


def format_free_variant(edge: dict, variant: str) -> str:
    """Format FREE user alert based on A/B variant."""
    edge_pct = round(abs(edge["edge"] * 100), 1)
    conf_pct = round(edge["confidence"] * 100)
    asset = edge["asset"]
    ttl = edge.get("ttlHours", 12)

    if variant == "A":
        return (
            f"<b>LIVE EDGE ({asset})</b>\n\n"
            f"This edge is hidden\n"
            f"Signal active now | ~{ttl}h\n\n"
            f"Upgrade to PRO"
        )

    if variant == "B":
        return (
            f"<b>EDGE ({asset})</b>\n\n"
            f"This signal is locked\n"
            f"Potential move: {edge_pct}%\n"
            f"Confidence: {conf_pct}%\n\n"
            f"You may miss this move\n\n"
            f"Unlock this edge"
        )

    if variant == "C":
        return (
            f"<b>EDGE ({asset})</b>\n\n"
            f"This edge is hidden\n"
            f"Potential move: {edge_pct}%\n\n"
            f"System accuracy: 82%\n\n"
            f"Unlock full edge → PRO"
        )

    # D — Combo
    return (
        f"<b>LIVE EDGE ({asset})</b>\n\n"
        f"This signal is locked\n"
        f"Potential move: {edge_pct}%\n"
        f"Confidence: {conf_pct}%\n\n"
        f"You may miss this move\n"
        f"82% accuracy\n\n"
        f"Unlock this edge"
    )


async def get_ab_stats(db) -> dict:
    """Get A/B test statistics grouped by variant — with $/alert."""
    pipeline = [
        {"$group": {
            "_id": {"variant": "$variant", "event": "$event"},
            "count": {"$sum": 1},
        }}
    ]

    results = {}
    async for doc in db.ab_events.aggregate(pipeline):
        v = doc["_id"]["variant"]
        e = doc["_id"]["event"]
        if v not in results:
            results[v] = {}
        results[v][e] = doc["count"]

    stats = {}
    for v in VARIANTS:
        data = results.get(v, {})
        sent = data.get("alert_sent", 0)
        opened = data.get("alert_opened", 0)
        edge_viewed = data.get("edge_viewed", 0)
        upgrade_clicked = data.get("upgrade_clicked", 0)
        upgrade_completed = data.get("upgrade_completed", 0)

        stats[v] = {
            "sent": sent,
            "opened": opened,
            "ctr": round(opened / sent * 100, 1) if sent > 0 else 0,
            "edge_viewed": edge_viewed,
            "clicks": upgrade_clicked,
            "paid": upgrade_completed,
            "revenue_per_alert": round(upgrade_completed / sent, 4) if sent > 0 else 0,
        }

    return stats
