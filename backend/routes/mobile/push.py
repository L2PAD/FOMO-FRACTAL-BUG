"""Push Notification routes — Push Intelligence Engine."""
from fastapi import APIRouter, Query, Depends
from routes.auth import get_current_user, get_optional_user
from services.asset_registry import normalize_symbol
from services.push_engine import (
    register_push_token, deactivate_push_token,
    get_push_status, mark_push_opened,
)
from services.push_triggers import (
    run_all_triggers, send_manual_push,
    check_pnl_triggers, check_edge_triggers, check_watchlist_triggers,
)
from services.daily_summary_engine import get_daily_summary

router = APIRouter()


@router.get("/daily-summary")
async def get_daily_summary_endpoint(asset: str = Query(default="BTC"), user=Depends(get_optional_user)):
    asset_key = normalize_symbol(asset)
    user_id = str(user['_id']) if user else None
    plan = 'FREE'
    if user:
        plan = user.get('plan', user.get('preferences', {}).get('plan', 'FREE'))
    return get_daily_summary(asset_key, user_id, plan)


@router.post("/push/register")
async def push_register(body: dict, user=Depends(get_current_user)):
    push_token = body.get('pushToken', '')
    platform = body.get('platform', 'unknown')
    if not push_token:
        return {"success": False, "error": "pushToken required"}
    return {"success": register_push_token(str(user['_id']), push_token, platform)}


@router.delete("/push/unregister")
async def push_unregister(body: dict, user=Depends(get_current_user)):
    return {"success": deactivate_push_token(str(user['_id']), body.get('pushToken', ''))}


@router.get("/push/status")
async def push_status(user=Depends(get_current_user)):
    return get_push_status(str(user['_id']))


@router.post("/push/opened")
async def push_opened(body: dict, user=Depends(get_current_user)):
    mark_push_opened(body.get('notificationId', ''), str(user['_id']))
    return {"ok": True}


# ═══════════════════════════════════════
#  PUSH INTELLIGENCE ENDPOINTS
# ═══════════════════════════════════════

@router.post("/push/send")
async def push_send(body: dict, user=Depends(get_optional_user)):
    """
    Manual push notification send.
    Body: { type: "PNL_ALERT"|"EDGE_ALERT"|"WATCHLIST_ALERT", userId?, symbol, pnl?, message? }
    """
    user_id = body.get('userId', 'dev_user')
    if user:
        user_id = str(user.get('_id', user_id))
    push_type = body.get('type', 'PNL_ALERT')
    symbol = body.get('symbol', 'BTC')
    pnl = body.get('pnl')
    message = body.get('message')
    return send_manual_push(user_id, push_type, symbol, pnl, message)


@router.post("/push/check-triggers")
async def push_check_triggers(user=Depends(get_optional_user)):
    """
    Run all push intelligence trigger checks for the current user.
    Returns generated notifications.
    """
    user_id = str(user['_id']) if user else 'dev_user'
    return {"ok": True, **run_all_triggers(user_id)}


@router.get("/push/triggers/pnl")
async def push_triggers_pnl(userId: str = Query("dev_user")):
    """Check PnL triggers only."""
    return {"ok": True, "triggers": check_pnl_triggers(userId)}


@router.get("/push/triggers/edge")
async def push_triggers_edge(userId: str = Query("dev_user")):
    """Check Edge triggers only."""
    return {"ok": True, "triggers": check_edge_triggers(userId)}


@router.get("/push/triggers/watchlist")
async def push_triggers_watchlist(userId: str = Query("dev_user")):
    """Check Watchlist triggers only."""
    return {"ok": True, "triggers": check_watchlist_triggers(userId)}
