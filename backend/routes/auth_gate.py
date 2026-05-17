"""
P0: Auth Gate — single endpoint the Web frontend hits before opening any
paywall / checkout to decide between (1) force Google Auth modal, or (2)
open checkout directly.

Contract:
  GET /api/auth/gate?surface=web_paywall
  → 200 { authenticated: bool, user_id?, email?, plan?, google_client_id,
          auth_url? }
"""
import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/auth", tags=["auth_gate"])


@router.get("/gate")
async def auth_gate(request: Request, surface: str = "unknown"):
    """Cheap identity probe for the frontend paywall-intercept layer."""
    authenticated = False
    user = None
    try:
        from auth_routes import _get_current_user as auth_get_user
        user = await auth_get_user(request)
        if user and user.get("user_id"):
            authenticated = True
    except Exception:
        user = None

    response = {
        "ok": True,
        "authenticated": authenticated,
        "surface": surface,
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
    }
    if authenticated and user:
        response["user_id"] = user.get("user_id")
        response["email"] = user.get("email")
        response["plan"] = user.get("plan_status", "free")
    return JSONResponse(content=response)
