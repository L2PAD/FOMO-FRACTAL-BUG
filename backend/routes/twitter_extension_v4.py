"""
Twitter Extension API (v4) — endpoints used by the FOMO X Connect Chrome extension.

These were previously legacy_compat stubs. This module provides real, simple
implementations backed by MongoDB so the extension can:
  • list available accounts (GET /api/v4/twitter/accounts)
  • run a preflight check on cookies   (POST /api/v4/twitter/preflight-check/extension)
  • send ingested timeline/profile data (POST /api/v4/twitter/ingest)
  • register a session via webhook      (POST /api/v4/twitter/sessions/webhook)
  • expose status                       (GET  /api/v4/twitter/integration/status)

Authentication: the extension passes "Authorization: Bearer <API_KEY>".
We accept any key whose value matches `TWITTER_EXTENSION_API_KEY` (env) OR a
DB-stored issued key in collection `twitter_extension_keys`. If no key is
configured the endpoints accept any bearer (dev/admin friendly).
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Header, HTTPException, Query

from ml_ops import get_db

router = APIRouter(tags=["twitter-extension-v4"])


# ──────────────────────────── Helpers ────────────────────────────


def _now():
    return datetime.now(timezone.utc)


def _utc_iso():
    return _now().isoformat()


def _db():
    return get_db()


def _safe(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def _verify_api_key(authorization: Optional[str]) -> dict:
    """
    Accepts:
      - any bearer in dev (no key configured)
      - bearer matching env TWITTER_EXTENSION_API_KEY
      - bearer found in twitter_extension_keys collection
    Returns issuer info; raises 401 otherwise.
    """
    env_key = os.environ.get("TWITTER_EXTENSION_API_KEY", "").strip()
    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization.split(" ", 1)[1].strip()

    if not env_key and not bearer:
        # No key configured and none provided → permissive dev mode
        return {"mode": "permissive", "key": None}

    if env_key and bearer == env_key:
        return {"mode": "env", "key_id": "env"}

    if bearer:
        # Check DB
        try:
            doc = await _db().twitter_extension_keys.find_one({"key": bearer})
            if doc:
                return {"mode": "db", "key_id": doc.get("id"), "issued_to": doc.get("label")}
        except Exception:
            pass

    if env_key:
        # Key configured but provided doesn't match
        raise HTTPException(status_code=401, detail={"ok": False, "error": "API_KEY_INVALID"})

    # No env key, bearer was provided but not in DB — accept (permissive)
    return {"mode": "permissive", "key": bearer[:6] + "..."}


# ──────────────────────────── Default accounts ─────────────────────────
# Intentionally empty.
# The canonical source of accounts is the `twitter_parser_accounts` collection
# (written by /api/admin/twitter-parser/accounts). We DO NOT seed test accounts.


async def _list_accounts_canonical(include_legacy: bool) -> list[dict]:
    """
    Aggregate accounts from the canonical admin collection
    `twitter_parser_accounts` (and a fallback `twitter_accounts` for backward
    compatibility). Returns the EXACT shape the FOMO X Connect popup expects:
      { id, username, sessionStatus, tier, ... }
    """
    db = _db()
    out: list[dict] = []
    seen_usernames: set[str] = set()

    # 1) Primary: admin-managed accounts
    async for a in db.twitter_parser_accounts.find({}, {"_id": 0}):
        username = (a.get("handle") or a.get("username") or "").strip().lstrip("@")
        if not username:
            continue
        seen_usernames.add(username.lower())
        # Map status to extension's expected vocabulary
        raw_status = (a.get("status") or "ACTIVE").upper()
        if raw_status in ("ACTIVE", "OK", "READY", "SYNCED"):
            sess_status = "active"
        elif raw_status in ("DEGRADED", "STALE", "WARN", "WARNING"):
            sess_status = "degraded"
        elif raw_status in ("INACTIVE", "DISABLED", "ERROR", "FAIL", "FAILED"):
            sess_status = "inactive"
        else:
            sess_status = "pending"
        out.append(
            {
                "id": a.get("id") or username,
                "username": username,
                "handle": username,            # alias for forward-compat
                "name": a.get("displayName") or username,
                "sessionStatus": sess_status,
                "status": sess_status,
                "tier": (a.get("tier") or "C").upper(),
                "legacy": False,
                "weight": a.get("weight"),
                "category": a.get("category"),
                "slotType": a.get("slotType"),
                "lastSyncAt": _safe(a.get("lastFetchAt") or a.get("lastSyncAt")),
            }
        )

    # 2) Optional legacy table — only if extension explicitly asks for it
    if include_legacy:
        async for a in db.twitter_accounts.find({}, {"_id": 0}):
            username = (a.get("handle") or a.get("username") or a.get("name") or "").strip().lstrip("@")
            if not username or username.lower() in seen_usernames:
                continue
            out.append(
                {
                    "id": a.get("id") or username,
                    "username": username,
                    "handle": username,
                    "name": a.get("name") or username,
                    "sessionStatus": (a.get("status") or "pending").lower(),
                    "status": (a.get("status") or "pending").lower(),
                    "tier": (a.get("tier") or "C").upper(),
                    "legacy": True,
                    "lastSyncAt": _safe(a.get("lastSyncAt")),
                }
            )

    tier_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    out.sort(key=lambda x: (tier_order.get(x["tier"], 9), x["username"]))
    return out


# ──────────────────────────── Endpoints ────────────────────────────


@router.get("/api/v4/twitter/accounts")
async def v4_twitter_accounts(
    includeLegacy: bool = Query(default=False),
    authorization: Optional[str] = Header(default=None),
):
    """Return the list of Twitter accounts the extension can sync into.

    Source of truth: `twitter_parser_accounts` (admin-managed).
    """
    await _verify_api_key(authorization)
    accounts = await _list_accounts_canonical(include_legacy=includeLegacy)

    return {
        "ok": True,
        "data": {"accounts": accounts},
        "count": len(accounts),
        "asOf": _utc_iso(),
    }


@router.post("/api/v4/twitter/preflight-check/extension")
async def v4_twitter_preflight(
    payload: dict = Body(...),
    authorization: Optional[str] = Header(default=None),
):
    """Validate cookies + account before a sync."""
    await _verify_api_key(authorization)

    cookies = payload.get("cookies") or []
    account_id = payload.get("accountId")

    if not cookies or not isinstance(cookies, list):
        return {
            "ok": False,
            "state": "NO_COOKIES",
            "fixHint": "Open x.com and log in first",
        }

    names = {c.get("name") for c in cookies if isinstance(c, dict)}
    has_auth = "auth_token" in names and any(
        c.get("name") == "auth_token" and len(str(c.get("value") or "")) > 5
        for c in cookies
    )
    has_ct0 = "ct0" in names and any(
        c.get("name") == "ct0" and len(str(c.get("value") or "")) > 5
        for c in cookies
    )

    if not has_auth or not has_ct0:
        missing = []
        if not has_auth:
            missing.append("auth_token")
        if not has_ct0:
            missing.append("ct0")
        return {
            "ok": False,
            "state": "MISSING_COOKIES",
            "missing": missing,
            "fixHint": "Re-login to x.com to refresh session cookies",
        }

    # Optional: validate account exists in EITHER admin or legacy collection
    if account_id:
        db = _db()
        acc = await db.twitter_parser_accounts.find_one(
            {"$or": [{"handle": account_id}, {"username": account_id}, {"id": account_id}]}
        )
        if not acc:
            acc = await db.twitter_accounts.find_one({"id": account_id})
        if not acc:
            return {
                "ok": False,
                "state": "ACCOUNT_NOT_FOUND",
                "fixHint": "Re-select an account in the dashboard",
            }

    return {
        "ok": True,
        "state": "READY",
        "cookieCount": len(cookies),
        "accountId": account_id,
        "asOf": _utc_iso(),
    }


@router.post("/api/v4/twitter/sessions/webhook")
async def v4_twitter_session_webhook(
    payload: dict = Body(...),
    authorization: Optional[str] = Header(default=None),
):
    """Receive a Twitter session from the extension (sync)."""
    await _verify_api_key(authorization)
    db = _db()

    account_id = payload.get("accountId")
    cookies = payload.get("cookies") or []
    user_agent = payload.get("userAgent")
    quality = payload.get("qualityReport")

    if not cookies:
        return {"ok": False, "error": "NO_COOKIES"}
    if not account_id:
        return {"ok": False, "error": "NO_ACCOUNT_ID"}

    sess_id = hashlib.md5(f"twitter_session:{account_id}".encode()).hexdigest()
    doc = {
        "id": sess_id,
        "accountId": account_id,
        "cookies": cookies,
        "cookieCount": len(cookies),
        "userAgent": user_agent,
        "qualityReport": quality,
        "source": payload.get("source") or "extension",
        "updatedAt": _now(),
    }
    await db.twitter_session.update_one(
        {"id": sess_id},
        {"$set": doc, "$setOnInsert": {"createdAt": _now()}},
        upsert=True,
    )
    # Update lastFetchAt on whichever collection holds the account
    await db.twitter_parser_accounts.update_one(
        {"$or": [{"handle": account_id}, {"username": account_id}, {"id": account_id}]},
        {"$set": {"lastFetchAt": _now(), "status": "ACTIVE"}},
    )
    await db.twitter_accounts.update_one(
        {"id": account_id},
        {"$set": {"lastSyncAt": _now(), "status": "active"}},
    )
    return {
        "ok": True,
        "sessionId": sess_id,
        "accountId": account_id,
        "cookieCount": len(cookies),
        "asOf": _utc_iso(),
    }


@router.post("/api/v4/twitter/ingest")
async def v4_twitter_ingest(
    payload: dict = Body(...),
    authorization: Optional[str] = Header(default=None),
):
    """Receive scraped Twitter data (tweets, profile, search...) from extension."""
    await _verify_api_key(authorization)
    db = _db()

    type_ = payload.get("type") or "UNKNOWN"
    data = payload.get("data") or {}
    params = payload.get("params") or {}
    source = payload.get("source") or "browser-extension"
    ts = payload.get("timestamp") or int(_now().timestamp() * 1000)

    rec = {
        "id": hashlib.md5(f"{type_}:{ts}:{repr(params)[:200]}".encode()).hexdigest(),
        "type": type_,
        "params": params,
        "data": data,
        "source": source,
        "ingestedAt": _now(),
        "ts": ts,
    }
    await db.twitter_ingested_raw.update_one(
        {"id": rec["id"]}, {"$set": rec}, upsert=True
    )
    return {"ok": True, "id": rec["id"], "type": type_, "asOf": _utc_iso()}


@router.get("/api/v4/twitter/integration/status")
async def v4_twitter_integration_status(
    authorization: Optional[str] = Header(default=None),
):
    """Reports overall extension integration health."""
    await _verify_api_key(authorization)
    db = _db()
    accounts_total = await db.twitter_parser_accounts.count_documents({})
    sessions_total = await db.twitter_session.count_documents({})
    last_session = await db.twitter_session.find_one(
        {}, sort=[("updatedAt", -1)], projection={"_id": 0, "updatedAt": 1, "accountId": 1}
    )
    last_ingest = await db.twitter_ingested_raw.find_one(
        {}, sort=[("ingestedAt", -1)], projection={"_id": 0, "ingestedAt": 1, "type": 1}
    )

    return {
        "ok": True,
        "extensionConnected": sessions_total > 0,
        "accounts": accounts_total,
        "sessions": sessions_total,
        "lastSession": {
            "accountId": last_session.get("accountId") if last_session else None,
            "at": _safe(last_session.get("updatedAt")) if last_session else None,
        },
        "lastIngest": {
            "type": last_ingest.get("type") if last_ingest else None,
            "at": _safe(last_ingest.get("ingestedAt")) if last_ingest else None,
        },
        "asOf": _utc_iso(),
    }


# ──────────────────────────── Extension ZIP builder ─────────────────


@router.get("/api/admin/twitter-extension/zip-info")
async def twitter_extension_zip_info():
    """Diagnostic: where the extension zip lives, whether it exists, its size and mtime."""
    from pathlib import Path

    src_dir = Path("/app/backend/admin_build/fomo_extension_v1.3.0")
    zip_path = Path("/app/backend/static/fomo_extension_v1.3.0.zip")

    return {
        "ok": True,
        "sourceDir": str(src_dir),
        "sourceExists": src_dir.exists(),
        "zipPath": str(zip_path),
        "zipExists": zip_path.exists(),
        "zipSize": zip_path.stat().st_size if zip_path.exists() else 0,
        "zipMtime": (
            datetime.fromtimestamp(zip_path.stat().st_mtime, tz=timezone.utc).isoformat()
            if zip_path.exists()
            else None
        ),
        "downloadUrl": "/api/download/fomo-extension",
    }
