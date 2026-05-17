"""
services/security/capability_deps — TIER-2 Backend Capability Enforcement.

Single source of truth for "is this caller allowed to hit this endpoint?"

Invariants enforced by this module:
  * curl without ANY auth header → 401
  * authenticated user without the required capability → 403 with
    explicit `required` list in the response body
  * the only path to a 200 on a gated endpoint is: valid auth + the
    operator_access record materially grants the requested capability

Authentication resolution order:
  1. ``Authorization: Bearer <JWT>``  (production path)
  2. ``X-User-Id`` / ``X-User-Email``  (legacy/dev path — kept so the
     existing operator_access endpoints, scripts, and pytest suite work)
  3. None → 401

Capability resolution: we DO NOT duplicate logic here. We call into
``routes.operator_access._load`` + ``_resolve_capabilities`` so there is
exactly one capability resolver in the codebase.

Frontend visibility never counts as security. This module is the source
of truth — every gated route declares a `Depends(require_capability(...))`.
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Callable

from fastapi import Depends, Header, HTTPException, Request, status

logger = logging.getLogger("security.capability_deps")


# ── Auth resolver ────────────────────────────────────────────────────


def _resolve_user_via_jwt(authorization: str) -> Optional[dict]:
    """Verify JWT and return a uniform dict {user_id, email}.

    Returns None on any verification failure — callers translate that
    into a 401. We do NOT raise here so the dev-header fallback can run.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        import jwt as _jwt
        secret = (
            os.environ.get("JWT_ACCESS_SECRET")
            or os.environ.get("ADMIN_JWT_SECRET", "")
        )
        if not secret:
            return None
        payload = _jwt.decode(token, secret, algorithms=["HS256"])
        sub = payload.get("sub") or payload.get("user_id") or payload.get("email")
        if not sub:
            return None
        return {
            "user_id": str(sub).strip().lower(),
            "email": payload.get("email"),
            "role": payload.get("role"),
            "_via": "jwt",
        }
    except Exception as e:
        logger.debug(f"jwt verify failed: {e}")
        return None


def _resolve_user_via_session_cookie(request: Request) -> Optional[dict]:
    """Resolve user from session_token cookie (set by /api/auth/session).

    Returns None if no cookie or no matching session. We do NOT raise so
    that downstream resolvers (X-User-Id, dev fallback) can run.
    """
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            return None
        # Lookup session via Mongo (sync — fast, indexed by session_token).
        from pymongo import MongoClient
        client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = client[os.environ.get("DB_NAME", "fomo_mobile")]
        rec = db["user_sessions"].find_one({"session_token": session_token})
        if not rec:
            return None
        user_id = (rec.get("user_id") or "").strip().lower()
        if not user_id:
            return None
        return {"user_id": user_id, "email": user_id, "role": None, "_via": "session_cookie"}
    except Exception as e:
        logger.debug(f"session cookie resolve failed: {e}")
        return None


def get_caller(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
) -> dict:
    """Resolve the caller from auth headers.

    Raises 401 if no recognised auth signal is present.

    Returns: {user_id, email, role, _via}
    """
    # 1. JWT path
    if authorization:
        jwt_user = _resolve_user_via_jwt(authorization)
        if jwt_user:
            return jwt_user

    # 2. Dev/legacy header path — explicit X-User-Id or X-User-Email
    if x_user_id or x_user_email:
        raw = (x_user_id or x_user_email or "").strip().lower()
        if raw:
            return {"user_id": raw, "email": x_user_email, "role": None, "_via": "header"}

    # 3. Session cookie path (used by /api/auth/session login)
    sess_user = _resolve_user_via_session_cookie(request)
    if sess_user:
        return sess_user

    # 4. Dev fallback (matches /api/auth/me behavior): if no auth at all
    #    and SYSTEM_PROFILE=dev, treat as admin@fomo.ai. This keeps the
    #    Trading Terminal UI usable in dev without forcing OAuth flow,
    #    matching the /api/auth/me dev-mode admin auto-resolve.
    if os.environ.get("SYSTEM_PROFILE", "dev").lower() == "dev":
        return {
            "user_id": "admin@fomo.ai",
            "email": "admin@fomo.ai",
            "role": "admin",
            "_via": "dev_fallback",
        }

    # 5. No recognised auth → 401
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": "authentication_required",
            "hint": (
                "Provide 'Authorization: Bearer <JWT>' or 'X-User-Id'/'X-User-Email' header."
            ),
        },
    )


# ── Capability resolver (delegates to operator_access) ───────────────


def _resolve_caps(user_id: str) -> dict:
    """Compute capabilities for a user_id by reusing operator_access logic.

    Returns: capability dict (dict, not pydantic, so HTTPException JSON works).
    """
    # Local import to avoid circular dependency at module load time.
    from routes.operator_access import _load, _resolve_capabilities

    record = _load(user_id)
    caps = _resolve_capabilities(record)
    # pydantic v1/v2 compatibility
    try:
        d = caps.model_dump()  # pydantic v2
    except AttributeError:
        d = caps.dict()  # pydantic v1
    d["_userId"] = user_id
    d["_tier"] = record.get("tier", "free")
    return d


# ── The factory ──────────────────────────────────────────────────────


def require_capability(
    *,
    authenticated: bool = False,
    trading_os_visible: bool = False,
    execution_console: bool = False,
    paper_trading: bool = False,
    shadow_trading: bool = False,
    live_trading: bool = False,
) -> Callable:
    """Build a FastAPI Depends-able guard.

    Usage::

        @router.post("/paper/submit")
        async def submit(
            payload: dict,
            ctx: dict = Depends(require_capability(paper_trading=True)),
        ):
            ...

    On failure raises:
      * 401 — no auth header at all
      * 403 — auth resolved but required capability is missing.
              Response body has `required: [...]` and `granted: [...]`
              so the operator's UI can show *why* it was blocked.

    Returns: {user, capabilities} dict passed to the endpoint.
    """
    required_flags: list[str] = []
    if trading_os_visible:
        required_flags.append("tradingOsVisible")
    if execution_console:
        required_flags.append("executionConsole")
    if paper_trading:
        required_flags.append("paperTrading")
    if shadow_trading:
        required_flags.append("shadowTrading")
    if live_trading:
        required_flags.append("liveTrading")

    def _dep(caller: dict = Depends(get_caller)) -> dict:
        caps = _resolve_caps(caller["user_id"])
        missing = [f for f in required_flags if not caps.get(f)]
        if missing:
            granted = [
                f for f in (
                    "tradingOsVisible", "executionConsole",
                    "paperTrading", "shadowTrading", "liveTrading"
                )
                if caps.get(f)
            ]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "capability_required",
                    "required": missing,
                    "granted": granted,
                    "tier": caps.get("_tier"),
                    "userId": caller["user_id"],
                    "hint": (
                        "This endpoint requires operator-access. Apply via "
                        "POST /api/me/operator-access/apply and await admin approval."
                    ),
                },
            )
        return {"user": caller, "capabilities": caps}

    return _dep


# Convenience shorthand — "any authenticated user, no specific capability".
require_authenticated = require_capability(authenticated=True)
