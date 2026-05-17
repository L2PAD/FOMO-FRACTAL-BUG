"""Behavior tracking routes — user state, events, affinity, feed mutations."""
from fastapi import APIRouter, Depends, Body, Query
from typing import Optional
from routes.auth import get_current_user, get_optional_user
from services.behavior_engine import (
    get_user_state, track_event, get_conversion_stats,
    get_push_effectiveness, get_personalized_push,
)
from services.affinity_service import (
    compute_affinity, get_cached_affinity, get_top_affinity_assets,
    compute_user_state, get_behavior_memory, get_feed_mutations,
)

router = APIRouter()


@router.get("/behavior/state")
def get_state(user=Depends(get_current_user)):
    """Get current user behavior state."""
    uid = str(user.get("_id", user.get("userId", "")))
    state = get_user_state(uid)
    return {"ok": True, "state": state}


@router.post("/behavior/track")
def track(
    event_type: str = Body(...),
    data: Optional[dict] = Body(default=None),
    user=Depends(get_current_user),
):
    """Track a user behavior event + funnel tracking."""
    uid = str(user.get("_id", user.get("userId", "")))
    state = track_event(uid, event_type, data)

    # Conversion funnel tracking — map behavior events to funnel steps
    try:
        from services.conversion_funnel import track_funnel_event
        signal_id = (data or {}).get("signalId", (data or {}).get("symbol", "BTC"))
        BEHAVIOR_TO_FUNNEL = {
            "signal_view": "viewed_signal",
            "signal_detail_open": "opened_detail",
            "VIEW_SCREEN": "opened_app",
            "VIEW_ASSET": "viewed_signal",
            "signal_click": "opened_detail",
            "paywall_view": "paywall_seen",
            "paywall_dismiss": "paywall_seen",
            "edge_click": "opened_detail",
            "cta_click": "cta_clicked",
            "purchase_complete": "converted",
        }
        funnel_step = BEHAVIOR_TO_FUNNEL.get(event_type)
        if funnel_step:
            track_funnel_event(uid, signal_id, funnel_step, {"source": event_type})
    except Exception:
        pass  # Never block behavior tracking for funnel errors

    return {"ok": True, "state": state}


@router.get("/behavior/affinity")
def affinity(userId: str = Query("dev_user")):
    """Get user's asset affinity scores (weighted + decayed)."""
    scores = compute_affinity(userId)
    top = get_top_affinity_assets(userId, limit=10)
    user_state = compute_user_state(userId)
    return {
        "ok": True,
        "affinity": scores,
        "topAssets": top,
        "userState": user_state,
    }


@router.get("/behavior/memory/{symbol}")
def memory(symbol: str, userId: str = Query("dev_user")):
    """Get behavior memory for a specific asset (for contextual pushes)."""
    mem = get_behavior_memory(userId, symbol)
    return {"ok": True, "memory": mem}


@router.get("/behavior/feed-mutations")
def feed_mutations(userId: str = Query("dev_user")):
    """Get feed personalization mutations (ordering, highlights, rewrites)."""
    mutations = get_feed_mutations(userId)
    return {"ok": True, **mutations}


@router.get("/behavior/next-push")
def next_push(user=Depends(get_current_user)):
    """Get personalized push for this user."""
    uid = str(user.get("_id", user.get("userId", "")))
    push = get_personalized_push(uid, {})
    return {"ok": True, "push": push}


@router.get("/behavior/stats")
def stats():
    """Get conversion and push stats (admin)."""
    return {
        "ok": True,
        "conversion": get_conversion_stats(),
        "pushEffectiveness": get_push_effectiveness(),
    }
