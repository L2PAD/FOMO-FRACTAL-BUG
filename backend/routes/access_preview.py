"""
P1: Web Soft Gate — Access Preview & Funnel Tracking

Contract:
  GET /api/access/preview
    → single source of truth for what each block on any screen should show.
    Fields per block: {visible, locked, unlock_reason, cta}

  POST /api/access/track
    → writes guest/auth funnel events (guest_session_id → user_id merge trail).
"""
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
router = APIRouter(prefix="/api/access", tags=["access"])

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fomo_db")


def _get_db():
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


def _feature_enabled() -> bool:
    """Feature flag — can be flipped without redeploy."""
    return os.getenv("WEB_SOFT_GATE_ENABLED", "true").lower() in ("1", "true", "yes", "on")


# ─── Access matrix: one source of truth per level/block ─────────────
# Each block exposes: {visible, locked, unlock_reason, cta}
def _build_access_blocks(level: str) -> dict:
    L = "auth_required"
    P = "pro_required"

    # Always-visible baseline (guest + auth_free + pro)
    base = {
        "decision":           {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
        "prediction_snapshot":{"visible": True, "locked": False, "unlock_reason": None, "cta": None},
        "market_state":       {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
        "drivers_preview":    {"visible": True, "locked": False, "unlock_reason": None, "cta": None, "limit": 2},
    }

    if level == "guest":
        locked_blocks = {
            # Tier A: auth unlocks these (partial reveal)
            "prediction_details": {"visible": False, "locked": True, "unlock_reason": L, "cta": "Continue to see analysis"},
            "full_breakdown":     {"visible": False, "locked": True, "unlock_reason": L, "cta": "Continue for full breakdown"},
            "feed_detail":        {"visible": False, "locked": True, "unlock_reason": L, "cta": "Continue to read feed"},
            "history_stats":      {"visible": False, "locked": True, "unlock_reason": L, "cta": "Continue to see history"},
            # Tier B: PRO unlocks (shown as auth-first to guest — progressive)
            "entry":              {"visible": False, "locked": True, "unlock_reason": L, "cta": "Continue to see entry"},
            "invalidation":       {"visible": False, "locked": True, "unlock_reason": L, "cta": "Continue to see invalidation"},
            "target":             {"visible": False, "locked": True, "unlock_reason": L, "cta": "Continue to see target"},
            "drivers_full":       {"visible": False, "locked": True, "unlock_reason": L, "cta": "Continue to see all drivers"},
        }
    elif level == "auth_free":
        locked_blocks = {
            # Tier A unlocked
            "prediction_details": {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            "full_breakdown":     {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            "feed_detail":        {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            "history_stats":      {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            "drivers_full":       {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            # Tier B still PRO-gated
            "entry":              {"visible": False, "locked": True, "unlock_reason": P, "cta": "Unlock exact entry"},
            "invalidation":       {"visible": False, "locked": True, "unlock_reason": P, "cta": "Unlock invalidation"},
            "target":             {"visible": False, "locked": True, "unlock_reason": P, "cta": "Unlock target"},
        }
    else:  # pro
        locked_blocks = {
            "prediction_details": {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            "full_breakdown":     {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            "feed_detail":        {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            "history_stats":      {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            "drivers_full":       {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            "entry":              {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            "invalidation":       {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
            "target":             {"visible": True, "locked": False, "unlock_reason": None, "cta": None},
        }

    return {**base, **locked_blocks}


async def _resolve_level(request: Request) -> tuple:
    """
    Return (level, user) where level is 'guest' | 'auth_free' | 'pro'.
    """
    # Try canonical user resolver from billing (supports session + JWT)
    user = None
    try:
        from billing_routes import _get_current_user as _auth
        try:
            user = await _auth(request)
        except Exception:
            user = None
    except Exception:
        user = None

    if not user or not user.get("user_id"):
        return "guest", None

    plan = (user.get("plan") or user.get("plan_status") or "FREE").upper()
    if plan in ("PRO", "PREMIUM", "ACTIVE"):
        return "pro", user
    return "auth_free", user


@router.get("/preview")
async def access_preview(request: Request):
    """Single source of truth for what each UI block renders per user level."""
    level, user = await _resolve_level(request)
    blocks = _build_access_blocks(level)

    # Feature flag — if disabled, treat everyone as 'pro' on Web so rollback
    # is one env var away (doesn't affect mobile because mobile ignores this).
    if not _feature_enabled():
        blocks = _build_access_blocks("pro")

    # Admin override via mongo `web_gate_config` (settings.access_level).
    # When admin sets `force_level` to 'pro' / 'auth_free' / 'guest' / 'disabled',
    # the gate is forced. This lets the panel toggle "free access for all" on/off
    # without a restart.
    try:
        db = _get_db()
        cfg = await db["web_gate_config"].find_one({"_id": "main"})
        if cfg:
            force_level = (cfg.get("force_level") or "").lower().strip()
            if force_level == "disabled":
                blocks = _build_access_blocks("pro")
            elif force_level in ("pro", "auth_free", "guest"):
                blocks = _build_access_blocks(force_level)
    except Exception:
        pass

    return JSONResponse({
        "ok": True,
        "level": level,
        "authenticated": user is not None,
        "user_id": (user or {}).get("user_id"),
        "email": (user or {}).get("email"),
        "plan": (user or {}).get("plan", "FREE"),
        "blocks": blocks,
        "feature_enabled": _feature_enabled(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ─── Admin-only: read/write the global force-level override ─────────
@router.get("/admin/config")
async def admin_access_config(request: Request):
    """Return current admin override config. Admin auth handled by caller."""
    try:
        db = _get_db()
        cfg = await db["web_gate_config"].find_one({"_id": "main"}, {"_id": 0})
        return JSONResponse({"ok": True, "config": cfg or {"force_level": None}})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/admin/config")
async def admin_set_access_config(request: Request):
    """
    Update the access override.
    Body: {"force_level": "disabled" | "pro" | "auth_free" | "guest" | null}
      - "disabled" → bypass all gates (free access for all)
      - "pro"      → everyone is treated as PRO
      - "auth_free"→ guests treated as auth_free (Tier A unlocked)
      - "guest"    → no overrides, falls back to hardcoded matrix
      - null       → remove override
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    force_level = body.get("force_level")
    if force_level is not None:
        force_level = str(force_level).lower().strip()
        if force_level not in ("disabled", "pro", "auth_free", "guest"):
            return JSONResponse({"ok": False, "error": "invalid force_level"}, status_code=400)
    try:
        db = _get_db()
        if force_level is None:
            await db["web_gate_config"].delete_one({"_id": "main"})
            return JSONResponse({"ok": True, "force_level": None, "note": "override cleared"})
        await db["web_gate_config"].update_one(
            {"_id": "main"},
            {"$set": {
                "force_level": force_level,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        return JSONResponse({"ok": True, "force_level": force_level})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ─── Funnel tracking ────────────────────────────────────────────────
_VALID_EVENTS = {
    "web_visit_guest", "web_cta_click", "web_auth_prompt_shown",
    "web_auth_completed", "web_paywall_shown", "web_checkout_started",
    "web_block_viewed_locked", "web_block_viewed_unlocked",
}


@router.post("/track")
async def track_funnel(request: Request):
    """Writes a single funnel event. guest_session_id is REQUIRED (P1 rule)."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    event = (body.get("event") or "").strip()
    if event not in _VALID_EVENTS:
        return JSONResponse({"ok": False, "error": "unknown_event"}, status_code=400)

    guest_session_id = (body.get("guest_session_id") or "").strip()
    if not guest_session_id:
        # Synthesize one so we never drop an event — but flag it.
        guest_session_id = f"synth_{uuid.uuid4().hex[:16]}"

    # Resolve current user (may be None for guests)
    level, user = await _resolve_level(request)

    rec = {
        "event": event,
        "guest_session_id": guest_session_id,
        "user_id": (user or {}).get("user_id"),
        "level": level,
        "surface": body.get("surface") or "unknown",
        "element": body.get("element") or "",
        "block_key": body.get("block_key") or "",
        "cta_label": body.get("cta_label") or "",
        "platform": body.get("platform") or "web",
        "extra": body.get("extra") or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        db = _get_db()
        await db["web_funnel_events"].insert_one(rec)
    except Exception:
        pass
    return JSONResponse({"ok": True})


@router.post("/merge-guest")
async def merge_guest_to_user(request: Request):
    """
    Called right after auth completes — attaches all earlier guest_session_id
    events to the new user_id so we have a full funnel story.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    guest_session_id = (body.get("guest_session_id") or "").strip()
    if not guest_session_id:
        return JSONResponse({"ok": False, "error": "guest_session_id required"}, status_code=400)

    level, user = await _resolve_level(request)
    if not user or not user.get("user_id"):
        return JSONResponse({"ok": False, "error": "not_authenticated"}, status_code=401)

    uid = user["user_id"]
    try:
        db = _get_db()
        res = await db["web_funnel_events"].update_many(
            {"guest_session_id": guest_session_id, "user_id": None},
            {"$set": {"user_id": uid, "merged_at": datetime.now(timezone.utc).isoformat()}}
        )
        return JSONResponse({"ok": True, "merged": res.modified_count, "user_id": uid})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
