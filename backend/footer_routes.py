"""
Footer Config + Legal Pages — admin-managed footer settings,
social links, Terms/Privacy content.
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger("footer_routes")

router = APIRouter(tags=["footer"])

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


def _get_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


DEFAULTS = {
    "social_links": {
        "twitter": "",
        "discord": "",
        "telegram": "",
    },
    "legal_pages": {
        "terms": {"title": "Terms of Service", "content": "Terms of Service content will be added here."},
        "privacy": {"title": "Privacy Policy", "content": "Privacy Policy content will be added here."},
    },
}


# ── Public: Get footer config ──
@router.get("/api/footer/config")
async def get_footer_config():
    db = _get_db()
    cfg = await db["footer_config"].find_one({"_id": "main"}, {"_id": 0})
    if not cfg:
        return {"ok": True, **DEFAULTS}
    return {"ok": True, **cfg}


# ── Public: Get legal page content ──
@router.get("/api/legal/{page_type}")
async def get_legal_page(page_type: str):
    if page_type not in ("terms", "privacy"):
        raise HTTPException(400, "Invalid page type")

    db = _get_db()
    cfg = await db["footer_config"].find_one({"_id": "main"}, {"_id": 0})
    pages = (cfg or DEFAULTS).get("legal_pages", DEFAULTS["legal_pages"])
    page = pages.get(page_type, DEFAULTS["legal_pages"][page_type])
    return {"ok": True, "page": page}


# ── Admin: Update footer config ──
@router.put("/api/admin/footer/config")
async def update_footer_config(request: Request):
    body = await request.json()
    db = _get_db()

    update = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if "social_links" in body:
        sl = body["social_links"]
        update["social_links"] = {
            "twitter": sl.get("twitter", ""),
            "discord": sl.get("discord", ""),
            "telegram": sl.get("telegram", ""),
        }

    if "legal_pages" in body:
        lp = body["legal_pages"]
        update["legal_pages"] = {}
        for key in ("terms", "privacy"):
            if key in lp:
                update["legal_pages"][key] = {
                    "title": lp[key].get("title", ""),
                    "content": lp[key].get("content", ""),
                }

    await db["footer_config"].update_one(
        {"_id": "main"},
        {"$set": update},
        upsert=True,
    )
    return {"ok": True}


# ── Admin: Get footer config (full) ──
@router.get("/api/admin/footer/config")
async def admin_get_footer_config(request: Request):
    db = _get_db()
    cfg = await db["footer_config"].find_one({"_id": "main"}, {"_id": 0})
    if not cfg:
        return {"ok": True, **DEFAULTS}
    return {"ok": True, **cfg}


# ══════════════════════════════════════════
#   NEWSLETTER / SUBSCRIBERS
# ══════════════════════════════════════════

@router.post("/api/newsletter/subscribe")
async def newsletter_subscribe(request: Request):
    """Public endpoint — subscribe email to signal newsletter."""
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Valid email required")

    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()

    existing = await db["newsletter_subscribers"].find_one({"email": email}, {"_id": 0})
    if existing:
        return {"ok": True, "status": "already_subscribed"}

    await db["newsletter_subscribers"].insert_one({
        "email": email,
        "subscribed_at": now,
        "source": body.get("source", "footer"),
        "active": True,
    })
    logger.info(f"[Newsletter] New subscriber: {email}")
    return {"ok": True, "status": "subscribed"}


@router.get("/api/admin/newsletter/subscribers")
async def admin_get_subscribers(request: Request):
    """Admin endpoint — list all newsletter subscribers."""
    db = _get_db()
    subs = await db["newsletter_subscribers"].find(
        {}, {"_id": 0}
    ).sort("subscribed_at", -1).to_list(length=500)

    total = await db["newsletter_subscribers"].count_documents({})
    active = await db["newsletter_subscribers"].count_documents({"active": True})

    return {
        "ok": True,
        "total": total,
        "active": active,
        "subscribers": subs,
    }


@router.delete("/api/admin/newsletter/subscribers/{email}")
async def admin_remove_subscriber(email: str, request: Request):
    """Admin endpoint — remove subscriber."""
    db = _get_db()
    result = await db["newsletter_subscribers"].delete_one({"email": email.lower()})
    if result.deleted_count == 0:
        raise HTTPException(404, "Subscriber not found")
    return {"ok": True}
