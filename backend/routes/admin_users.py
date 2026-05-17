"""
Admin Users & Platform Routes
==============================

Endpoints for admin to view users, their platforms, and sync status.
"""
from fastapi import APIRouter, HTTPException, Query
from pymongo import MongoClient, DESCENDING
from datetime import datetime, timezone
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "intelligence_engine")
_db = MongoClient(MONGO_URL)[DB_NAME]


@router.get("/list")
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    plan: str = Query(None),
    platform: str = Query(None),
):
    """
    List all users with platform info and subscription status.
    
    Returns:
        {
            "users": [...],
            "total": 100,
            "page": 1,
            "pages": 5
        }
    """
    query = {}
    if plan:
        query["plan"] = plan.upper()
    if platform:
        query[f"linkedApps.{platform}"] = True

    total = _db.users.count_documents(query)
    skip = (page - 1) * limit
    
    users = list(_db.users.find(query).sort("createdAt", DESCENDING).skip(skip).limit(limit))
    
    formatted = []
    for u in users:
        formatted.append({
            "id": u.get("_id"),
            "email": u.get("email"),
            "name": u.get("name"),
            "plan": u.get("plan", "FREE"),
            "planStatus": u.get("planStatus", "ACTIVE"),
            "createdAt": u.get("createdAt").isoformat() if u.get("createdAt") else None,
            "authProviders": u.get("authProviders", {}),
            "linkedApps": u.get("linkedApps", {}),
            "subscription": {
                "plan": u.get("subscription", {}).get("plan", "FREE"),
                "status": u.get("subscription", {}).get("status", "INACTIVE"),
                "paymentMethod": u.get("subscription", {}).get("paymentMethod"),
                "lastPaymentId": u.get("subscription", {}).get("lastPaymentId"),
            },
            "expiresAt": u.get("expiresAt").isoformat() if u.get("expiresAt") else None,
            "telegramLinked": bool(u.get("telegramChatId")),
            "telegramUsername": u.get("telegramUsername"),
            "twoFactorEnabled": u.get("twoFactorEnabled", False),
        })

    return {
        "users": formatted,
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
    }


@router.get("/stats")
async def user_stats():
    """
    Get aggregated user statistics for admin dashboard.
    """
    total = _db.users.count_documents({})
    pro = _db.users.count_documents({"plan": "PRO"})
    free = _db.users.count_documents({"plan": "FREE"})
    
    # Platform breakdown
    mobile = _db.users.count_documents({"linkedApps.mobile": True})
    web = _db.users.count_documents({"linkedApps.web": True})
    miniapp = _db.users.count_documents({"linkedApps.miniapp": True})
    
    # Auth providers
    google = _db.users.count_documents({"authProviders.google": True})
    email = _db.users.count_documents({"authProviders.email": True})
    telegram = _db.users.count_documents({"authProviders.telegram": True})
    
    # Payments
    total_payments = _db.payments.count_documents({"status": "finished"})
    
    return {
        "total": total,
        "byPlan": {"PRO": pro, "FREE": free},
        "byPlatform": {"mobile": mobile, "web": web, "miniapp": miniapp},
        "byAuthProvider": {"google": google, "email": email, "telegram": telegram},
        "totalPayments": total_payments,
    }


@router.get("/{user_id}")
async def get_user_detail(user_id: str):
    """
    Get detailed user info for admin panel.
    """
    user = _db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(404, "User not found")
    
    # Get user's payments
    payments = list(_db.payments.find(
        {"order_id": user_id},
        {"_id": 0}
    ).sort("processed_at", DESCENDING).limit(10))
    
    return {
        "id": user.get("_id"),
        "email": user.get("email"),
        "name": user.get("name"),
        "plan": user.get("plan", "FREE"),
        "planStatus": user.get("planStatus"),
        "expiresAt": user.get("expiresAt").isoformat() if user.get("expiresAt") else None,
        "createdAt": user.get("createdAt").isoformat() if user.get("createdAt") else None,
        "authProviders": user.get("authProviders", {}),
        "linkedApps": user.get("linkedApps", {}),
        "subscription": user.get("subscription", {}),
        "telegramLinked": bool(user.get("telegramChatId")),
        "telegramUsername": user.get("telegramUsername"),
        "twoFactorEnabled": user.get("twoFactorEnabled", False),
        "payments": payments,
        "access": user.get("access", {}),
        "preferences": user.get("preferences", {}),
        "stats": user.get("stats", {}),
    }


@router.post("/{user_id}/set-plan")
async def set_user_plan(user_id: str, plan: str = Query("PRO")):
    """Admin action: manually set user's plan."""
    user = _db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(404, "User not found")
    
    now = datetime.now(timezone.utc)
    update = {
        "plan": plan.upper(),
        "planStatus": "ACTIVE" if plan.upper() != "FREE" else "INACTIVE",
        "updatedAt": now,
    }
    
    if plan.upper() == "PRO":
        from datetime import timedelta
        update["expiresAt"] = now + timedelta(days=30)
        update["subscription.plan"] = "PRO"
        update["subscription.status"] = "ACTIVE"
        update["access.fullSignals"] = True
        update["access.fullIntel"] = True
        update["access.edge"] = True
    else:
        update["expiresAt"] = None
        update["subscription.plan"] = "FREE"
        update["subscription.status"] = "INACTIVE"
        update["access.fullSignals"] = False
        update["access.fullIntel"] = False
        update["access.edge"] = False
    
    _db.users.update_one({"_id": user_id}, {"$set": update})
    
    return {"ok": True, "user_id": user_id, "plan": plan.upper()}
