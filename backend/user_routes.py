"""
User Profile routes — nickname, avatar, 2FA (TOTP).
Auth is Google OAuth; passwords/email changes are not applicable.
"""
import os
import io
import uuid
import base64
import logging
import requests as sync_requests
import pyotp
import qrcode

from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response, HTTPException, UploadFile, File

logger = logging.getLogger("user_routes")

router = APIRouter(prefix="/api/user", tags=["user"])

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

# Object Storage
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "prediction-os"
_storage_key = None

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5MB


def _get_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


def _init_storage():
    global _storage_key
    if _storage_key:
        return _storage_key
    resp = sync_requests.post(
        f"{STORAGE_URL}/init",
        json={"emergent_key": EMERGENT_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    logger.info("[Storage] Initialized successfully")
    return _storage_key


def _put_object(path: str, data: bytes, content_type: str) -> dict:
    key = _init_storage()
    resp = sync_requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def _get_object(path: str):
    key = _init_storage()
    resp = sync_requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


async def _require_user(request: Request) -> dict:
    from auth_routes import _get_current_user
    user = await _get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


# ── Profile Update ──
@router.put("/profile")
async def update_profile(request: Request):
    """Update user nickname/display name."""
    user = await _require_user(request)
    body = await request.json()
    nickname = body.get("nickname", "").strip()
    if not nickname:
        raise HTTPException(400, "Nickname is required")
    if len(nickname) > 50:
        raise HTTPException(400, "Nickname too long (max 50)")

    db = _get_db()
    await db["users"].update_one(
        {"user_id": user["user_id"]},
        {"$set": {"nickname": nickname, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "nickname": nickname}


# ── Avatar Upload ──
@router.post("/avatar")
async def upload_avatar(request: Request, file: UploadFile = File(...)):
    """Upload user avatar image."""
    user = await _require_user(request)

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Invalid image type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}")

    data = await file.read()
    if len(data) > MAX_AVATAR_SIZE:
        raise HTTPException(400, "File too large (max 5MB)")

    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    storage_path = f"{APP_NAME}/avatars/{user['user_id']}/{uuid.uuid4()}.{ext}"

    result = _put_object(storage_path, data, file.content_type)

    db = _get_db()
    await db["users"].update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "avatar_path": result["path"],
            "avatar_content_type": file.content_type,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"ok": True, "avatar_url": f"/api/user/avatar/{user['user_id']}"}


@router.get("/avatar/{user_id}")
async def get_avatar(user_id: str):
    """Serve user avatar from object storage."""
    db = _get_db()
    user = await db["users"].find_one({"user_id": user_id}, {"_id": 0, "avatar_path": 1, "avatar_content_type": 1})
    if not user or not user.get("avatar_path"):
        raise HTTPException(404, "No avatar")

    data, ct = _get_object(user["avatar_path"])
    return Response(
        content=data,
        media_type=user.get("avatar_content_type", ct),
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ── 2FA (TOTP) ──
@router.post("/2fa/setup")
async def setup_2fa(request: Request):
    """Generate TOTP secret and QR code for 2FA setup."""
    user = await _require_user(request)
    db = _get_db()

    existing = await db["users"].find_one({"user_id": user["user_id"]}, {"_id": 0, "totp_enabled": 1})
    if existing and existing.get("totp_enabled"):
        raise HTTPException(400, "2FA is already enabled")

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.get("email", "user"),
        issuer_name="Prediction OS",
    )

    # Generate QR code as base64
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    # Store secret temporarily (not yet enabled)
    await db["users"].update_one(
        {"user_id": user["user_id"]},
        {"$set": {"totp_secret_pending": secret}},
    )

    return {
        "ok": True,
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_b64}",
        "provisioning_uri": provisioning_uri,
    }


@router.post("/2fa/verify")
async def verify_2fa(request: Request):
    """Verify TOTP code and enable 2FA."""
    user = await _require_user(request)
    body = await request.json()
    code = body.get("code", "").strip()
    if not code:
        raise HTTPException(400, "Code is required")

    db = _get_db()
    u = await db["users"].find_one({"user_id": user["user_id"]}, {"_id": 0, "totp_secret_pending": 1, "totp_secret": 1})

    secret = u.get("totp_secret_pending") or u.get("totp_secret")
    if not secret:
        raise HTTPException(400, "No 2FA setup in progress")

    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(400, "Invalid code")

    await db["users"].update_one(
        {"user_id": user["user_id"]},
        {
            "$set": {
                "totp_secret": secret,
                "totp_enabled": True,
                "totp_enabled_at": datetime.now(timezone.utc).isoformat(),
            },
            "$unset": {"totp_secret_pending": ""},
        },
    )
    return {"ok": True, "message": "2FA enabled successfully"}


@router.post("/2fa/disable")
async def disable_2fa(request: Request):
    """Disable 2FA. Requires valid TOTP code."""
    user = await _require_user(request)
    body = await request.json()
    code = body.get("code", "").strip()
    if not code:
        raise HTTPException(400, "Code is required")

    db = _get_db()
    u = await db["users"].find_one({"user_id": user["user_id"]}, {"_id": 0, "totp_secret": 1, "totp_enabled": 1})
    if not u or not u.get("totp_enabled"):
        raise HTTPException(400, "2FA is not enabled")

    totp = pyotp.TOTP(u["totp_secret"])
    if not totp.verify(code, valid_window=1):
        raise HTTPException(400, "Invalid code")

    await db["users"].update_one(
        {"user_id": user["user_id"]},
        {
            "$unset": {"totp_secret": "", "totp_secret_pending": "", "totp_enabled": "", "totp_enabled_at": ""},
        },
    )
    return {"ok": True, "message": "2FA disabled"}


@router.get("/profile")
async def get_profile(request: Request):
    """Get full user profile including 2FA status."""
    user = await _require_user(request)
    db = _get_db()
    u = await db["users"].find_one(
        {"user_id": user["user_id"]},
        {"_id": 0, "totp_secret": 0, "totp_secret_pending": 0},
    )
    if not u:
        raise HTTPException(404, "User not found")

    has_avatar = bool(u.get("avatar_path"))
    avatar_url = f"/api/user/avatar/{u['user_id']}" if has_avatar else None

    return {
        "ok": True,
        "profile": {
            "user_id": u["user_id"],
            "email": u.get("email", ""),
            "name": u.get("name", ""),
            "nickname": u.get("nickname", ""),
            "picture": u.get("picture", ""),
            "avatar_url": avatar_url,
            "plan_status": u.get("plan_status", "free"),
            "totp_enabled": u.get("totp_enabled", False),
            "created_at": u.get("created_at", ""),
        },
    }


# ── User Referral Dashboard ──

@router.get("/referrals")
async def get_user_referrals(request: Request):
    """Get referral dashboard data for the current user."""
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "Not authenticated")

    user_id = user.get("user_id", "")
    email = user.get("email", "")

    # Find codes assigned to this user (as referrer)
    my_codes = []
    async for c in db["promo_codes"].find(
        {"referrer_user_id": {"$in": [user_id, email]}},
        {"_id": 0}
    ):
        group = await db["promo_groups"].find_one({"group_id": c["group_id"]}, {"_id": 0})
        my_codes.append({
            "code": c["code"],
            "group_name": group.get("name", "") if group else "",
            "discount_percent": c.get("discount_percent", 0),
            "referral_reward_percent": group.get("referral_reward_percent", 0) if group else 0,
            "used_by": c.get("used_by"),
            "used_at": c.get("used_at"),
        })

    # Find conversions where this user is the referrer
    conversions = []
    total_earned = 0
    async for conv in db["referral_conversions"].find(
        {"referrer_user_id": {"$in": [user_id, email]}},
        {"_id": 0}
    ).sort("created_at", -1):
        conversions.append(conv)
        total_earned += conv.get("reward_amount", 0)

    # Stats
    total_codes = len(my_codes)
    used_codes = sum(1 for c in my_codes if c.get("used_by"))
    total_conversions = len(conversions)

    return {
        "ok": True,
        "codes": my_codes,
        "conversions": conversions,
        "stats": {
            "total_codes": total_codes,
            "used_codes": used_codes,
            "total_conversions": total_conversions,
            "total_earned": round(total_earned, 2),
        },
    }
