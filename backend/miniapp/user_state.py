"""
User State Machine — manages user lifecycle in Mini App.
========================================================
States: guest → telegram_only → linked_google → active_sub → expired_sub

Links telegram_id ↔ email ↔ nowpayments_order_id for seamless flow.
"""

from datetime import datetime, timezone

# State constants
STATE_GUEST = "guest"
STATE_TELEGRAM = "telegram_only"
STATE_LINKED = "linked_google"
STATE_ACTIVE = "active_sub"
STATE_EXPIRED = "expired_sub"

VALID_STATES = {STATE_GUEST, STATE_TELEGRAM, STATE_LINKED, STATE_ACTIVE, STATE_EXPIRED}


def compute_state(user: dict, subscription: dict = None) -> str:
    """Compute user state from user doc + subscription."""
    has_telegram = bool(user.get("telegram_id"))
    has_google = bool(user.get("google_email") or user.get("email"))

    if subscription:
        status = subscription.get("status", "")
        if status in ("active", "trialing"):
            return STATE_ACTIVE
        if status in ("past_due", "canceled"):
            return STATE_EXPIRED

    if has_google and has_telegram:
        return STATE_LINKED
    if has_telegram:
        return STATE_TELEGRAM
    return STATE_GUEST


async def get_user_state(db, telegram_id: str) -> dict:
    """Get full user state for a telegram user."""
    user = await db.miniapp_users.find_one(
        {"telegram_id": telegram_id}, {"_id": 0}
    )
    if not user:
        return {"state": STATE_GUEST, "telegram_id": telegram_id}

    sub = await db.miniapp_subscriptions.find_one(
        {"telegram_id": telegram_id}, {"_id": 0}
    )

    state = compute_state(user, sub)

    return {
        "state": state,
        "telegram_id": telegram_id,
        "name": user.get("name", ""),
        "google_email": user.get("google_email"),
        "nowpayments_order_id": user.get("nowpayments_order_id"),
        "plan_status": "active" if state == STATE_ACTIVE else ("expired" if state == STATE_EXPIRED else "free"),
        "linked": {
            "telegram": True,
            "google": bool(user.get("google_email")),
            "nowpayments": bool(user.get("nowpayments_order_id")),
        },
    }


async def link_google_account(db, telegram_id: str, email: str, name: str = "") -> dict:
    """
    Link a Google account to a Telegram user.
    Merges data from users collection if email exists there.
    """
    if not telegram_id or not email:
        return {"success": False, "message": "telegram_id and email required"}

    # Check if email already exists in main users collection
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})

    # Get or create miniapp user
    miniapp_user = await db.miniapp_users.find_one(
        {"telegram_id": telegram_id}, {"_id": 0}
    )
    if not miniapp_user:
        miniapp_user = {
            "telegram_id": telegram_id,
            "name": name or "Telegram User",
            "plan_status": "free",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.miniapp_users.insert_one(miniapp_user)
        miniapp_user.pop("_id", None)

    # Merge data
    update = {
        "google_email": email,
        "name": name or miniapp_user.get("name", "Telegram User"),
        "linked_at": datetime.now(timezone.utc).isoformat(),
    }

    # If user has subscription in main users, inherit it
    if existing_user:
        if existing_user.get("nowpayments_order_id"):
            update["nowpayments_order_id"] = existing_user["nowpayments_order_id"]
        if existing_user.get("plan_status") == "active":
            update["plan_status"] = "active"
        if existing_user.get("user_id"):
            update["linked_user_id"] = existing_user["user_id"]

    await db.miniapp_users.update_one(
        {"telegram_id": telegram_id},
        {"$set": update},
    )

    # Also update main users collection with telegram_id
    if existing_user:
        await db.users.update_one(
            {"email": email},
            {"$set": {"telegram_id": telegram_id}},
        )
    else:
        # Create user in main collection too
        import uuid
        await db.users.insert_one({
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": email,
            "name": name,
            "telegram_id": telegram_id,
            "plan_status": miniapp_user.get("plan_status", "free"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "success": True,
        "message": f"Linked {email} to Telegram account",
        "state": STATE_LINKED,
    }


async def unlink_google_account(db, telegram_id: str) -> dict:
    """Unlink Google account."""
    await db.miniapp_users.update_one(
        {"telegram_id": telegram_id},
        {"$unset": {"google_email": "", "linked_at": "", "linked_user_id": ""}},
    )
    return {"success": True, "message": "Google account unlinked"}
