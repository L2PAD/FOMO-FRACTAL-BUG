"""
Paywall Router — /api/paywall/*

Endpoints:
    GET  /api/paywall/context    — behavior-driven copy for current user (auth optional)
    GET  /api/paywall/identity   — post-conversion identity-loop message (auth required)
    GET  /api/paywall/kpi        — funnel metrics per state (admin only)
    GET  /api/paywall/config     — current copy + thresholds (admin)
    PUT  /api/paywall/copy       — tune copy per state (admin)
    PUT  /api/paywall/thresholds — tune WARM/lookback thresholds (admin)
"""
from __future__ import annotations

import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from services.paywall import paywall_resolver

try:
    from routes.auth import get_current_user, get_optional_user
except Exception:
    def get_current_user():  # type: ignore
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED"})
    def get_optional_user():  # type: ignore
        return None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/paywall", tags=["paywall"])


SurfaceIn = Literal["hero", "edge", "missed", "feed", "push", "unknown"]


class CopyPatch(BaseModel):
    state: Literal["cold", "warm", "hot"]
    headline: str | None = None
    subline: str | None = None
    cta: str | None = None


class ThresholdsPatch(BaseModel):
    warm_edge_open: int | None = None
    warm_hero_tap: int | None = None
    lookback_hours: int | None = None


def _is_admin(request: Request) -> bool:
    auth = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return False
    try:
        import jwt
        secret = os.environ.get("ADMIN_JWT_SECRET", "") or os.environ.get("JWT_ACCESS_SECRET", "")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("role") in ("superadmin", "admin")
    except Exception:
        return False


def _uid(user) -> str:
    if not user:
        return ""
    return str(user.get("user_id") or user.get("_id") or "")


# ─── Public ──────────────────────────────────────────────────────────
@router.get("/context")
async def paywall_context(
    surface: SurfaceIn = "edge",
    user=Depends(get_optional_user),
):
    """
    Returns contextual paywall copy. Anonymous users get COLD state.
    Frontend should call this right before rendering the paywall line
    in EdgeScreen / Missed → Edge transition / Hero CTA.
    """
    user_id = _uid(user)
    return await paywall_resolver.resolve(user_id=user_id, surface=surface)


@router.get("/identity")
async def paywall_identity(user: dict = Depends(get_current_user)):
    """Post-conversion identity loop — "You're now ahead of X% of users"."""
    user_id = _uid(user)
    return await paywall_resolver.identity_message(user_id)


# ─── Admin ───────────────────────────────────────────────────────────
@router.get("/config")
async def paywall_config_get(request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    return {"ok": True, **await paywall_resolver.get_config()}


@router.put("/copy")
async def paywall_copy_put(body: CopyPatch, request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    patch = {k: v for k, v in body.model_dump().items() if k != "state" and v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail={"error": "EMPTY_PATCH"})
    updated = await paywall_resolver.set_copy(body.state, patch)
    logger.info(f"[Paywall] copy[{body.state}] updated: {list(patch.keys())}")
    return {"ok": True, "state": body.state, "copy": updated}


@router.put("/thresholds")
async def paywall_thresholds_put(body: ThresholdsPatch, request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail={"error": "EMPTY_PATCH"})
    updated = await paywall_resolver.set_thresholds(patch)
    logger.info(f"[Paywall] thresholds updated: {patch}")
    return {"ok": True, "thresholds": updated}


@router.get("/kpi")
async def paywall_kpi(request: Request, hours: int = 24):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    return await paywall_resolver.funnel_kpi(hours=hours)


@router.get("/conversion")
async def paywall_conversion(request: Request, hours: int = 24):
    """Full view→click→checkout→paid funnel by state.
    The KPI that matters: HOT end_to_end rate vs COLD end_to_end rate.
    If HOT ≤ COLD → paywall isn't earning its contextual framing."""
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    return await paywall_resolver.conversion_funnel(hours=hours)
