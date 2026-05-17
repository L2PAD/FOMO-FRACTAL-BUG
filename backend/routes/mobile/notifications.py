"""Notification routes — in-app alerts (system + signal), bilingual (en/ru)."""
from fastapi import APIRouter, Query, Depends
from routes.auth import get_current_user
from services.notification_engine import (
    get_user_notifications,
    get_unread_count,
    mark_read,
    mark_all_read,
    broadcast_system_notification,
    seed_initial_notifications,
)

router = APIRouter()

# Seed on import
seed_initial_notifications()


@router.get("/notifications")
async def notifications_list(
    type: str = Query(default=None, description="SYSTEM or SIGNAL"),
    lang: str = Query(default="en", description="Language: en or ru"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_current_user),
):
    """Get user's notifications localized to requested language."""
    effective_lang = lang if lang in ("en", "ru") else "en"
    return get_user_notifications(str(user['_id']), lang=effective_lang, ntype=type, limit=limit, offset=offset)


@router.get("/notifications/unread-count")
async def unread_count(user=Depends(get_current_user)):
    """Get unread notification count (for bell badge)."""
    return get_unread_count(str(user['_id']))


@router.post("/notifications/read")
async def read_notification(body: dict, user=Depends(get_current_user)):
    """Mark a specific notification as read."""
    nid = body.get('notificationId', '')
    if not nid:
        return {"success": False, "error": "notificationId required"}
    ok = mark_read(str(user['_id']), nid)
    return {"success": ok}


@router.post("/notifications/read-all")
async def read_all_notifications(user=Depends(get_current_user)):
    """Mark all notifications as read."""
    count = mark_all_read(str(user['_id']))
    return {"success": True, "marked": count}


@router.post("/notifications/broadcast")
async def admin_broadcast(body: dict, user=Depends(get_current_user)):
    """
    Admin broadcasts a bilingual system notification.
    Body: { title_en, title_ru, body_en, body_ru, priority?, data? }
    Also accepts { title, body } as fallback (stored as both languages).
    """
    title_en = body.get('title_en', '').strip() or body.get('title', '').strip()
    title_ru = body.get('title_ru', '').strip() or body.get('title', '').strip()
    body_en = body.get('body_en', '').strip() or body.get('body', '').strip() or body.get('message', '').strip()
    body_ru = body.get('body_ru', '').strip() or body.get('body', '').strip() or body.get('message', '').strip()
    priority = body.get('priority', 'MEDIUM')
    data = body.get('data', {})

    if not title_en and not title_ru:
        return {"success": False, "error": "title required"}
    if not body_en and not body_ru:
        return {"success": False, "error": "body required"}

    nid = broadcast_system_notification(title_en, title_ru, body_en, body_ru, data, priority)
    return {"success": True, "notificationId": nid}
