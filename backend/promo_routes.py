"""
Promo Codes & Referral System routes.
Admin generates promo groups (with optional referral settings).
Users validate promo codes. Referral conversions are tracked.
"""
import os
import uuid
import string
import random
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/api/admin/billing/promos", tags=["admin-promos"])
user_router = APIRouter(prefix="/api/billing", tags=["billing-promos"])

def _get_db():
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
    return client[os.environ.get("DB_NAME", "intelligence_engine")]


def _generate_code(prefix: str = "", length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    code = "".join(random.choices(chars, k=length))
    return f"{prefix}{code}" if prefix else code


# ─── Admin: Promo Groups ──────────────────────────────────────────

@router.get("/groups")
async def list_promo_groups():
    """List all promo groups with usage stats and referral info."""
    db = _get_db()
    groups = []
    async for g in db["promo_groups"].find({}, {"_id": 0}).sort("created_at", -1):
        codes = await db["promo_codes"].count_documents({"group_id": g["group_id"]})
        used = await db["promo_codes"].count_documents({"group_id": g["group_id"], "used_by": {"$ne": None}})
        g["total_codes"] = codes
        g["used_codes"] = used
        # Referral stats
        if g.get("referral_enabled"):
            conversions = await db["referral_conversions"].count_documents({"group_id": g["group_id"]})
            g["referral_conversions"] = conversions
        groups.append(g)
    return {"ok": True, "groups": groups}


@router.post("/groups")
async def create_promo_group(request: Request):
    """Create a promo group and generate codes. Supports referral config."""
    body = await request.json()
    name = body.get("name", "").strip()
    discount_percent = body.get("discount_percent", 0)
    count = body.get("count", 10)
    prefix = body.get("prefix", "").upper().strip()
    referral_enabled = body.get("referral_enabled", False)
    referral_reward_percent = body.get("referral_reward_percent", 0)

    if not name:
        raise HTTPException(400, "name required")
    if discount_percent < 0 or discount_percent > 100:
        raise HTTPException(400, "discount_percent must be 0-100")
    if count < 1 or count > 500:
        raise HTTPException(400, "count must be 1-500")
    if referral_reward_percent < 0 or referral_reward_percent > 100:
        raise HTTPException(400, "referral_reward_percent must be 0-100")

    db = _get_db()
    group_id = f"grp_{uuid.uuid4().hex[:10]}"

    # Generate unique codes
    codes = []
    existing_codes = set()
    async for c in db["promo_codes"].find({}, {"code": 1, "_id": 0}):
        existing_codes.add(c["code"])

    for _ in range(count):
        for _attempt in range(20):
            code = _generate_code(prefix=f"{prefix}-" if prefix else "", length=8)
            if code not in existing_codes:
                existing_codes.add(code)
                codes.append(code)
                break

    # Save group
    await db["promo_groups"].insert_one({
        "group_id": group_id,
        "name": name,
        "discount_percent": int(discount_percent),
        "prefix": prefix,
        "referral_enabled": bool(referral_enabled),
        "referral_reward_percent": int(referral_reward_percent) if referral_enabled else 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Save codes
    code_docs = [{
        "code": c,
        "group_id": group_id,
        "discount_percent": int(discount_percent),
        "referral_enabled": bool(referral_enabled),
        "referral_reward_percent": int(referral_reward_percent) if referral_enabled else 0,
        "used_by": None,
        "used_at": None,
        "referrer_user_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    } for c in codes]

    if code_docs:
        await db["promo_codes"].insert_many(code_docs)

    return {
        "ok": True,
        "group_id": group_id,
        "codes_generated": len(codes),
        "sample_codes": codes[:5],
    }


@router.get("/groups/{group_id}/codes")
async def get_group_codes(group_id: str):
    """Get all codes for a promo group."""
    db = _get_db()
    codes = []
    async for c in db["promo_codes"].find({"group_id": group_id}, {"_id": 0}):
        codes.append(c)
    return {"ok": True, "codes": codes}


@router.delete("/groups/{group_id}")
async def delete_promo_group(group_id: str):
    """Delete a promo group and its codes."""
    db = _get_db()
    await db["promo_groups"].delete_one({"group_id": group_id})
    result = await db["promo_codes"].delete_many({"group_id": group_id})
    await db["referral_conversions"].delete_many({"group_id": group_id})
    return {"ok": True, "deleted_codes": result.deleted_count}


@router.put("/groups/{group_id}")
async def update_promo_group(group_id: str, request: Request):
    """Update referral settings for a promo group."""
    body = await request.json()
    db = _get_db()

    group = await db["promo_groups"].find_one({"group_id": group_id})
    if not group:
        raise HTTPException(404, "Group not found")

    update = {}
    if "referral_enabled" in body:
        update["referral_enabled"] = bool(body["referral_enabled"])
    if "referral_reward_percent" in body:
        val = int(body["referral_reward_percent"])
        if val < 0 or val > 100:
            raise HTTPException(400, "referral_reward_percent must be 0-100")
        update["referral_reward_percent"] = val
    if "name" in body:
        update["name"] = body["name"].strip()
    if "discount_percent" in body:
        val = int(body["discount_percent"])
        if val < 0 or val > 100:
            raise HTTPException(400, "discount_percent must be 0-100")
        update["discount_percent"] = val

    if update:
        await db["promo_groups"].update_one({"group_id": group_id}, {"$set": update})
        # Sync referral fields to codes
        code_update = {}
        if "referral_enabled" in update:
            code_update["referral_enabled"] = update["referral_enabled"]
        if "referral_reward_percent" in update:
            code_update["referral_reward_percent"] = update["referral_reward_percent"]
        if "discount_percent" in update:
            code_update["discount_percent"] = update["discount_percent"]
        if code_update:
            await db["promo_codes"].update_many({"group_id": group_id}, {"$set": code_update})

    updated = await db["promo_groups"].find_one({"group_id": group_id}, {"_id": 0})
    return {"ok": True, "group": updated}


# ─── Admin: Referral Conversions ──────────────────────────────────

@router.get("/referrals")
async def list_referral_conversions():
    """Get all referral conversions for admin overview."""
    db = _get_db()
    conversions = []
    async for c in db["referral_conversions"].find({}, {"_id": 0}).sort("created_at", -1).limit(100):
        conversions.append(c)

    total_rewards = 0
    total_conversions = 0
    async for c in db["referral_conversions"].find({}, {"_id": 0}):
        total_conversions += 1
        total_rewards += c.get("reward_amount", 0)

    return {
        "ok": True,
        "conversions": conversions,
        "total_conversions": total_conversions,
        "total_rewards": round(total_rewards, 2),
    }


@router.get("/groups/{group_id}/referrals")
async def get_group_referrals(group_id: str):
    """Get referral conversions for a specific group."""
    db = _get_db()
    conversions = []
    async for c in db["referral_conversions"].find({"group_id": group_id}, {"_id": 0}).sort("created_at", -1):
        conversions.append(c)
    return {"ok": True, "conversions": conversions}


# ─── Assign referral code to a user (for influencers) ─────────────

@router.post("/groups/{group_id}/assign")
async def assign_referral_code(group_id: str, request: Request):
    """Assign an unused code from a group to a specific user (influencer)."""
    body = await request.json()
    user_email = body.get("user_email", "").strip()
    if not user_email:
        raise HTTPException(400, "user_email required")

    db = _get_db()
    group = await db["promo_groups"].find_one({"group_id": group_id}, {"_id": 0})
    if not group:
        raise HTTPException(404, "Group not found")

    # Find user
    user = await db["users"].find_one({"email": user_email}, {"_id": 0})
    if not user:
        raise HTTPException(404, f"User with email {user_email} not found")

    # Find unused code without a referrer
    code_doc = await db["promo_codes"].find_one({
        "group_id": group_id,
        "used_by": None,
        "referrer_user_id": None,
    }, {"_id": 0})

    if not code_doc:
        raise HTTPException(400, "No available codes in this group")

    # Assign
    await db["promo_codes"].update_one(
        {"code": code_doc["code"]},
        {"$set": {"referrer_user_id": user.get("user_id", user_email)}}
    )

    return {
        "ok": True,
        "code": code_doc["code"],
        "assigned_to": user_email,
    }


@router.post("/codes/{code}/unassign")
async def unassign_referral_code(code: str):
    """Remove referrer assignment from a code."""
    db = _get_db()
    result = await db["promo_codes"].update_one(
        {"code": code, "used_by": None},
        {"$set": {"referrer_user_id": None}}
    )
    if result.modified_count == 0:
        raise HTTPException(400, "Code not found, already used, or not assigned")
    return {"ok": True}


@router.post("/codes/{code}/reassign")
async def reassign_referral_code(code: str, request: Request):
    """Reassign a code to a different user."""
    body = await request.json()
    user_email = body.get("user_email", "").strip()
    if not user_email:
        raise HTTPException(400, "user_email required")

    db = _get_db()
    code_doc = await db["promo_codes"].find_one({"code": code}, {"_id": 0})
    if not code_doc:
        raise HTTPException(404, "Code not found")
    if code_doc.get("used_by"):
        raise HTTPException(400, "Cannot reassign a used code")

    user = await db["users"].find_one({"email": user_email}, {"_id": 0})
    if not user:
        raise HTTPException(404, f"User with email {user_email} not found")

    await db["promo_codes"].update_one(
        {"code": code},
        {"$set": {"referrer_user_id": user.get("user_id", user_email)}}
    )
    return {"ok": True, "code": code, "assigned_to": user_email}



# ─── User: Validate Promo Code ────────────────────────────────────

@user_router.post("/validate-promo")
async def validate_promo_code(request: Request):
    """Validate a promo code and return discount info."""
    body = await request.json()
    code = body.get("code", "").strip().upper()

    if not code:
        raise HTTPException(400, "code required")

    db = _get_db()
    promo = await db["promo_codes"].find_one({"code": code}, {"_id": 0})

    if not promo:
        return {"ok": False, "error": "Invalid promo code"}

    if promo.get("used_by"):
        return {"ok": False, "error": "Promo code already used"}

    group = await db["promo_groups"].find_one({"group_id": promo["group_id"]}, {"_id": 0})

    return {
        "ok": True,
        "discount_percent": promo["discount_percent"],
        "group_name": group.get("name", "") if group else "",
        "referral_enabled": promo.get("referral_enabled", False),
    }
