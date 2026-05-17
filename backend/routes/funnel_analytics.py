"""
P1.1: Funnel Analytics & Decision Engine

Three admin-only endpoints that turn `web_funnel_events` into actionable
insights (not just counts):

  GET /api/access/funnel           — step conversion + avg time-to-next +
                                     by_intent split + biggest-drop diagnosis
  GET /api/access/blocks-heatmap   — which locked blocks people see vs. click
  GET /api/access/cohort           — daily time-series of the same metrics

Design rules:
  - read-only, never mutates state
  - protected by get_admin (existing admin auth)
  - auto-diagnosis is rule-based so output is actionable, not generic
"""
import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from routes.admin_auth import get_admin

load_dotenv()
router = APIRouter(prefix="/api/access", tags=["funnel_analytics"])

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fomo_db")


def _db():
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


# Funnel order — each step in sequence. `converted` is derived from
# `checkout_sessions.status == completed` (not emitted by frontend).
FUNNEL_STEPS = [
    "web_visit_guest",
    "web_cta_click",
    "web_auth_prompt_shown",
    "web_auth_completed",
    "web_paywall_shown",
    "web_checkout_started",
    "converted",
]


INTENT_BUCKETS = ["COLD", "WARM", "HOT", "VERY_HOT"]


def _iso_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


async def _count_step(db, step: str, since_iso: str, platform: str = "web") -> int:
    if step == "converted":
        # `converted` = completed checkout sessions in window.
        return await db["checkout_sessions"].count_documents({
            "status": "completed",
            "completed_at": {"$gte": since_iso},
        })
    q = {"event": step, "timestamp": {"$gte": since_iso}}
    if platform:
        q["platform"] = platform
    return await db[step_collection()].count_documents(q)


def step_collection() -> str:
    return "web_funnel_events"


async def _session_step_times(db, since_iso: str, platform: str) -> dict:
    """
    Return {step: [durations_seconds...]} where each duration is the time
    between *this step* and the *next step* for the same guest_session_id.
    Ignores sessions that didn't reach the next step.
    """
    events_col = db["web_funnel_events"]
    # Group by session
    pipeline = [
        {"$match": {"timestamp": {"$gte": since_iso}, "platform": platform}},
        {"$sort": {"timestamp": 1}},
        {"$group": {
            "_id": "$guest_session_id",
            "events": {"$push": {"event": "$event", "ts": "$timestamp"}},
        }},
    ]
    out = {s: [] for s in FUNNEL_STEPS}
    async for row in events_col.aggregate(pipeline):
        events = row.get("events") or []
        # For each funnel step, find the first occurrence and measure
        # time until the NEXT funnel step (if any).
        step_ts = {}
        for e in events:
            ev = e["event"]
            if ev in FUNNEL_STEPS and ev not in step_ts:
                try:
                    step_ts[ev] = datetime.fromisoformat(e["ts"].replace("Z", "+00:00"))
                except Exception:
                    continue
        for i, s in enumerate(FUNNEL_STEPS[:-1]):
            if s in step_ts:
                # find earliest *later* funnel step
                for s2 in FUNNEL_STEPS[i+1:]:
                    if s2 in step_ts and step_ts[s2] >= step_ts[s]:
                        delta = (step_ts[s2] - step_ts[s]).total_seconds()
                        if 0 <= delta <= 3600:  # clamp — anything > 1h is session-break noise
                            out[s].append(delta)
                        break
    return out


async def _by_intent_counts(db, since_iso: str) -> dict:
    """
    Returns {INTENT: {step: count}} by joining users.intent_score
    to events via user_id (only for authed steps).
    """
    # Load intent per user_id (if users collection has it)
    uid_to_intent = {}
    try:
        async for u in db["users"].find(
            {"intent_score": {"$exists": True}}, {"user_id": 1, "intent_score": 1, "intent_level": 1}
        ):
            uid = u.get("user_id")
            if not uid:
                continue
            lvl = (u.get("intent_level") or "").upper()
            if lvl not in INTENT_BUCKETS:
                score = float(u.get("intent_score") or 0)
                if score >= 0.75: lvl = "VERY_HOT"
                elif score >= 0.5: lvl = "HOT"
                elif score >= 0.25: lvl = "WARM"
                else: lvl = "COLD"
            uid_to_intent[uid] = lvl
    except Exception:
        pass

    out = {b: {s: 0 for s in FUNNEL_STEPS} for b in INTENT_BUCKETS}
    out["UNKNOWN"] = {s: 0 for s in FUNNEL_STEPS}
    async for e in db["web_funnel_events"].find(
        {"timestamp": {"$gte": since_iso}, "user_id": {"$ne": None}},
        {"event": 1, "user_id": 1, "_id": 0}
    ):
        bucket = uid_to_intent.get(e.get("user_id"), "UNKNOWN")
        ev = e.get("event")
        if ev in FUNNEL_STEPS:
            out[bucket][ev] = out[bucket].get(ev, 0) + 1
    # converted
    async for cs in db["checkout_sessions"].find(
        {"status": "completed", "completed_at": {"$gte": since_iso}},
        {"user_id": 1, "_id": 0}
    ):
        bucket = uid_to_intent.get(cs.get("user_id"), "UNKNOWN")
        out[bucket]["converted"] = out[bucket].get("converted", 0) + 1

    # Compute conversions per bucket (visit→converted)
    result = {}
    for b, counts in out.items():
        visits = counts.get("web_visit_guest", 0) or max(counts.get("web_cta_click", 0), 1)
        converted = counts.get("converted", 0)
        result[b] = {
            "counts": counts,
            "conversion": round(converted / visits, 5) if visits > 0 else 0.0,
            "visits": visits,
            "converted": converted,
        }
    return result


def _diagnose(drop_from: str, drop_to: str, rate: float, avg_time: float) -> str:
    """Rule-based diagnosis — actionable, not generic."""
    if drop_from == "web_visit_guest" and drop_to == "web_cta_click":
        return (
            "LOW PREVIEW VALUE — visitors don't click any CTA. "
            "Strengthen Prediction Snapshot / add FOMO signal above fold. "
            "Do NOT touch paywall."
        )
    if drop_from == "web_cta_click" and drop_to == "web_auth_prompt_shown":
        return "CTA handler broken — clicks register but modal doesn't open. Check AuthGateModal import."
    if drop_from == "web_auth_prompt_shown" and drop_to == "web_auth_completed":
        if avg_time and avg_time > 15:
            return (
                f"AUTH FRICTION — users take {avg_time:.0f}s on Google modal. "
                "Modal is slow / confusing. Reduce modal copy, check Google SDK latency."
            )
        return (
            "LOW TRUST AT SIGN-IN — fast abandon. Reframe CTA copy (not 'login', "
            "use 'continue to see' or 'unlock preview')."
        )
    if drop_from == "web_auth_completed" and drop_to == "web_paywall_shown":
        return (
            "PAYWALL NOT TRIGGERED — users auth but don't hit paywall path. "
            "Check GatedBlock wiring on post-auth surfaces."
        )
    if drop_from == "web_paywall_shown" and drop_to == "web_checkout_started":
        return (
            "PAYWALL NOT CONVINCING — users see price but abandon. "
            "Improve value proposition, add pressure ('PRO users already inside'), A/B test price copy."
        )
    if drop_from == "web_checkout_started" and drop_to == "converted":
        return (
            "PAYMENT FRICTION — users start checkout but don't finish. "
            "Investigate Stripe/NOW provider UX, check for 3DS failures, slow redirects."
        )
    return f"Drop {drop_from} → {drop_to} at rate {rate:.2f}. Review UX between these steps."


@router.get("/funnel")
async def funnel_report(
    days: int = Query(7, ge=1, le=90),
    platform: str = Query("web"),
    admin=Depends(get_admin),
):
    """Step-by-step funnel + time_to_next + by_intent + auto-diagnosis."""
    db = _db()
    since = _iso_ago(days)

    # 1) Counts per step
    counts = {}
    for s in FUNNEL_STEPS:
        counts[s] = await _count_step(db, s, since, platform)

    # 2) Avg time-to-next per step
    step_times = await _session_step_times(db, since, platform)
    avg_times = {}
    for s in FUNNEL_STEPS:
        arr = step_times.get(s, [])
        avg_times[s] = round(sum(arr) / len(arr), 1) if arr else None

    # 3) Build funnel list
    funnel = []
    prev_count = None
    biggest_drop = None
    for s in FUNNEL_STEPS:
        rate = None
        if prev_count is not None and prev_count > 0:
            rate = round(counts[s] / prev_count, 4)
            # Track biggest drop (lowest rate, only for real drops)
            if counts[s] > 0 and (biggest_drop is None or rate < biggest_drop["rate_from_prev"]):
                biggest_drop = {
                    "from": FUNNEL_STEPS[FUNNEL_STEPS.index(s) - 1],
                    "to": s,
                    "rate_from_prev": rate,
                    "avg_time_sec": avg_times.get(FUNNEL_STEPS[FUNNEL_STEPS.index(s) - 1]),
                }
        funnel.append({
            "step": s,
            "count": counts[s],
            "rate_from_prev": rate,
            "avg_time_to_next_sec": avg_times.get(s),
        })
        prev_count = counts[s]

    # 4) Diagnosis
    diagnosis = None
    if biggest_drop:
        diagnosis = _diagnose(
            biggest_drop["from"], biggest_drop["to"],
            biggest_drop["rate_from_prev"], biggest_drop.get("avg_time_sec") or 0,
        )
        biggest_drop["diagnosis"] = diagnosis

    # 5) By intent split
    by_intent = await _by_intent_counts(db, since)

    first = counts.get("web_visit_guest", 0)
    converted = counts.get("converted", 0)
    overall_conv = round(converted / first, 5) if first > 0 else 0.0

    return JSONResponse({
        "ok": True,
        "period": f"{days}d",
        "platform": platform,
        "since": since,
        "overall_conversion": overall_conv,
        "funnel": funnel,
        "biggest_drop": biggest_drop,
        "by_intent": by_intent,
    })


@router.get("/blocks-heatmap")
async def blocks_heatmap(
    days: int = Query(7, ge=1, le=90),
    admin=Depends(get_admin),
):
    """For each block: how many sessions saw it locked, how many clicked unlock."""
    db = _db()
    since = _iso_ago(days)

    # visible_sessions proxy = how many unique guest_sessions reached the page
    # that *would* show this block (approximated as all visitors).
    total_visible = await db["web_funnel_events"].distinct(
        "guest_session_id", {"event": "web_visit_guest", "timestamp": {"$gte": since}}
    )
    total_visible_count = len(total_visible) or 1

    # Locked views per block
    pipeline_view = [
        {"$match": {
            "event": "web_block_viewed_locked",
            "timestamp": {"$gte": since},
        }},
        {"$group": {"_id": "$block_key", "count": {"$sum": 1},
                    "sessions": {"$addToSet": "$guest_session_id"}}}
    ]
    view_stats = {}
    async for row in db["web_funnel_events"].aggregate(pipeline_view):
        view_stats[row["_id"]] = {
            "locked_views": row["count"],
            "unique_sessions": len(row.get("sessions") or []),
        }

    # Clicks per block
    pipeline_click = [
        {"$match": {
            "event": "web_cta_click",
            "timestamp": {"$gte": since},
        }},
        {"$group": {"_id": "$block_key", "count": {"$sum": 1}}}
    ]
    click_stats = {}
    async for row in db["web_funnel_events"].aggregate(pipeline_click):
        click_stats[row["_id"]] = row["count"]

    # Merge
    all_blocks = set(view_stats.keys()) | set(click_stats.keys())
    all_blocks.discard("")
    result = []
    for b in all_blocks:
        v = view_stats.get(b, {"locked_views": 0, "unique_sessions": 0})
        c = click_stats.get(b, 0)
        view_rate = round(v["unique_sessions"] / total_visible_count, 4) if total_visible_count > 0 else 0
        unlock_rate = round(c / v["locked_views"], 4) if v["locked_views"] > 0 else 0
        result.append({
            "block_key": b,
            "visible_sessions": v["unique_sessions"],
            "locked_views": v["locked_views"],
            "view_rate": view_rate,            # % of visitors that saw this locked block
            "unlock_clicks": c,
            "unlock_rate": unlock_rate,        # % of viewers that clicked CTA
            "impact_score": round(v["locked_views"] * unlock_rate, 2),
        })
    result.sort(key=lambda x: x["impact_score"], reverse=True)

    return JSONResponse({
        "ok": True,
        "period": f"{days}d",
        "total_visible_sessions": total_visible_count,
        "blocks": result,
    })


@router.get("/cohort")
async def cohort_daily(
    days: int = Query(14, ge=1, le=90),
    platform: str = Query("web"),
    admin=Depends(get_admin),
):
    """Daily time-series of funnel counts + conversion rate."""
    db = _db()
    since = _iso_ago(days)
    pipeline = [
        {"$match": {"timestamp": {"$gte": since}, "platform": platform}},
        {"$project": {
            "event": 1,
            "day": {"$substr": ["$timestamp", 0, 10]},
        }},
        {"$group": {
            "_id": {"day": "$day", "event": "$event"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id.day": 1}},
    ]
    buckets = {}
    async for row in db["web_funnel_events"].aggregate(pipeline):
        day = row["_id"]["day"]
        ev = row["_id"]["event"]
        buckets.setdefault(day, {s: 0 for s in FUNNEL_STEPS})[ev] = row["count"]

    # converted per day
    async for cs in db["checkout_sessions"].find(
        {"status": "completed", "completed_at": {"$gte": since}},
        {"completed_at": 1, "_id": 0}
    ):
        day = (cs.get("completed_at") or "")[:10]
        if day:
            buckets.setdefault(day, {s: 0 for s in FUNNEL_STEPS})
            buckets[day]["converted"] = buckets[day].get("converted", 0) + 1

    days_out = []
    for day in sorted(buckets.keys()):
        c = buckets[day]
        visits = c.get("web_visit_guest", 0) or 1
        converted = c.get("converted", 0)
        days_out.append({
            "day": day,
            "counts": c,
            "conversion": round(converted / visits, 5) if visits > 0 else 0.0,
        })

    return JSONResponse({
        "ok": True,
        "period": f"{days}d",
        "platform": platform,
        "days": days_out,
    })
