"""
Unified Billing Router — ONE surface for all providers.

Mount path: /api/billing/v2/*
After v1 → v2 migration this will be moved to /api/billing/*.

Endpoints:
    GET   /api/billing/v2/status             → orchestrator + provider config state
    GET   /api/billing/v2/plans              → plan catalog (provider-agnostic)
    POST  /api/billing/v2/checkout           → create checkout URL (auth required)
    GET   /api/billing/v2/subscription       → current user subscription status (auth required)
    POST  /api/billing/v2/portal             → self-serve portal URL (auth required)
    POST  /api/billing/v2/webhook/{provider} → provider webhook sink
    GET   /api/billing/v2/config             → admin-only: read provider_mode
    PUT   /api/billing/v2/config             → admin-only: switch provider_mode
"""
from __future__ import annotations

import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.billing import billing_service

try:
    from routes.auth import get_current_user, get_optional_user
except Exception:
    def get_current_user():  # type: ignore
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED"})
    def get_optional_user():  # type: ignore
        return None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing/v2", tags=["billing-v2"])


# ─── DTOs ────────────────────────────────────────────────────────────
PlanIdIn = Literal["month", "year"]
SurfaceIn = Literal["web", "telegram", "mobile", "admin"]
ProviderIn = Literal["nowpayments", "stripe"]


class CheckoutBody(BaseModel):
    plan_id: PlanIdIn = "month"
    surface: SurfaceIn = "web"
    origin_url: str = ""
    provider: ProviderIn | None = Field(default=None, description="Override auto-resolution")
    context: dict | None = Field(
        default=None,
        description="Attribution context: {state: cold|warm|hot, signalId, signal_source, ...}",
    )


class PortalBody(BaseModel):
    surface: SurfaceIn = "web"
    origin_url: str = ""
    provider: ProviderIn | None = None


class ConfigBody(BaseModel):
    provider_mode: Literal["nowpayments", "stripe", "dual"]


# ─── Auth helpers ────────────────────────────────────────────────────
def _is_admin(request: Request) -> bool:
    """Check admin bearer token (admin_accounts.password_hash via JWT)."""
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


def _user_ctx(user: dict) -> dict:
    """Normalise user dict for providers (mobile uses _id, others use user_id)."""
    if not user:
        return {}
    return {
        "user_id": str(user.get("user_id") or user.get("_id") or ""),
        "_id": user.get("_id"),
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "stripe_customer_id": user.get("stripe_customer_id", ""),
    }


# ─── Public endpoints ────────────────────────────────────────────────
@router.get("/status")
async def billing_status():
    """Top-level health: which providers are configured, which mode is active."""
    return await billing_service.status()


@router.get("/plans")
async def billing_plans():
    """Canonical, provider-agnostic plan catalog."""
    return await billing_service.plans()


@router.post("/checkout")
async def billing_checkout(body: CheckoutBody, user: dict = Depends(get_current_user)):
    """Create checkout — P0: hard auth gate (never anonymous).

    Body.context carries attribution payload: {state, signalId, signal_source}.
    Persisted into checkout_sessions for conversion funnel + payment_success emit.
    """
    result = await billing_service.create_checkout(
        _user_ctx(user),
        body.plan_id,
        surface=body.surface,
        origin_url=body.origin_url,
        provider=body.provider,
        context=body.context or {},
    )
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.get("/subscription")
async def billing_subscription(
    surface: SurfaceIn = "web",
    provider: ProviderIn | None = None,
    user: dict = Depends(get_current_user),
):
    """Current subscription status for the signed-in user."""
    return await billing_service.get_status(_user_ctx(user), surface=surface, provider=provider)


@router.post("/portal")
async def billing_portal(body: PortalBody, user: dict = Depends(get_current_user)):
    """Open self-serve billing portal (Stripe only — crypto will return not_supported)."""
    result = await billing_service.open_portal(
        _user_ctx(user), surface=body.surface, origin_url=body.origin_url, provider=body.provider
    )
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


# ─── Webhooks ────────────────────────────────────────────────────────
@router.post("/webhook/{provider_name}")
async def billing_webhook(provider_name: str, request: Request):
    """Public webhook sink — signature verified by the provider module itself."""
    body = await request.body()
    # Flatten headers to a plain dict (case-sensitive keys preserved)
    headers = {k: v for k, v in request.headers.items()}
    result = await billing_service.handle_webhook(provider_name, body, headers)
    # Always 200 on known provider to avoid retries storming us on bad signatures;
    # the audit goes into billing_events collection either way.
    return result


# ─── Admin-only: provider switch ─────────────────────────────────────
@router.get("/config")
async def billing_config_get(request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    return await billing_service.get_config()


@router.put("/config")
async def billing_config_put(body: ConfigBody, request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    updated = await billing_service.set_provider_mode(body.provider_mode)
    logger.info(f"[Billing] provider_mode -> {body.provider_mode}")
    return {"ok": True, "config": updated}
