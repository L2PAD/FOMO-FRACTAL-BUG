"""
Info CMS Routes — admin-controlled content for the /info landing page.

Stores three content groups in a single Mongo document
(info_cms_config._id == "main"):

  * app_links     — Android / iOS / Telegram distribution URLs + status.
  * legal_pages   — HTML content for Terms / Privacy / Cookies pages.
                    Rich-editor output (sanitized on save).
  * social_links  — Twitter / Discord / Telegram / LinkedIn footer links.

Admin endpoints require Bearer JWT (see admin_auth.get_admin).
Public endpoints feed the /info inject scripts (apps + socials) and
the /legal/<page> SPA routes.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient

from routes.admin_auth import get_admin

load_dotenv()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────────────────────
_MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME = os.getenv("DB_NAME", "test_database")
_client = MongoClient(_MONGO_URL)
_db = _client[_DB_NAME]
_col = _db["info_cms_config"]

_DOC_ID = "main"
_ALLOWED_LEGAL = ("terms", "privacy", "cookies")
_ALLOWED_STATUS = ("soon", "live")
_ALLOWED_SOCIALS = ("twitter", "discord", "telegram", "linkedin")

_DEFAULT_CONFIG: Dict[str, Any] = {
    "_id": _DOC_ID,
    "app_links": {
        "android": {"url": "", "status": "soon"},
        "ios": {"url": "", "status": "soon"},
        "telegram": {"url": "https://t.me/FOMO_mini_bot/app", "status": "live"},
    },
    "legal_pages": {
        "terms": "",
        "privacy": "",
        "cookies": "",
    },
    "social_links": {
        "twitter": "",
        "discord": "",
        "telegram": "",
        "linkedin": "",
    },
    "updated_at": None,
    "updated_by": None,
}


def _ensure_seed() -> None:
    if _col.count_documents({"_id": _DOC_ID}) == 0:
        _col.insert_one({**_DEFAULT_CONFIG})
        logger.info("[InfoCMS] Seeded default config")


_ensure_seed()


# ─────────────────────────────────────────────────────────────
# HTML sanitizer — conservative allow-list for legal pages.
# Rich editor emits basic HTML (p/b/i/u/strong/em/ul/ol/li/a/h1-3/br/hr/
# blockquote). We strip scripts, event handlers, and non-http links.
# ─────────────────────────────────────────────────────────────
_TAG_ALLOWLIST = {
    "p", "br", "hr", "b", "i", "u", "strong", "em", "s", "strike",
    "a", "ul", "ol", "li", "h1", "h2", "h3", "h4", "blockquote",
    "code", "pre", "span", "div",
}
_ATTR_ALLOWLIST = {
    "a": {"href", "title", "target", "rel"},
    # everything else: no attrs
}
_SCRIPT_RE = re.compile(r"<\s*script[\s\S]*?</\s*script\s*>", re.IGNORECASE)
_STYLE_RE = re.compile(r"<\s*style[\s\S]*?</\s*style\s*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<\s*(/?)\s*([a-zA-Z0-9]+)([^>]*)>")
_ATTR_RE = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*\"([^\"]*)\"")
_EVENT_ATTR_RE = re.compile(r"^on", re.IGNORECASE)
_SAFE_URL_RE = re.compile(r"^(https?:|mailto:|tel:|/)", re.IGNORECASE)


def _sanitize_html(raw: str) -> str:
    if not raw:
        return ""
    s = _SCRIPT_RE.sub("", raw)
    s = _STYLE_RE.sub("", s)

    def _tag_sub(m: "re.Match[str]") -> str:
        closing = m.group(1) or ""
        name = (m.group(2) or "").lower()
        attrs_str = m.group(3) or ""
        if name not in _TAG_ALLOWLIST:
            return ""
        if closing:
            return f"</{name}>"
        allowed_attrs = _ATTR_ALLOWLIST.get(name, set())
        kept: list[str] = []
        for am in _ATTR_RE.finditer(attrs_str):
            attr = am.group(1).lower()
            val = am.group(2)
            if _EVENT_ATTR_RE.match(attr):
                continue
            if attr not in allowed_attrs:
                continue
            if attr == "href" and not _SAFE_URL_RE.match(val):
                continue
            kept.append(f'{attr}="{val}"')
        # force rel=noopener on external anchors
        if name == "a":
            if not any(k.startswith("rel=") for k in kept):
                kept.append('rel="noopener noreferrer"')
            if not any(k.startswith("target=") for k in kept):
                kept.append('target="_blank"')
        return f"<{name}{(' ' + ' '.join(kept)) if kept else ''}>"

    return _TAG_RE.sub(_tag_sub, s)


# ─────────────────────────────────────────────────────────────
# URL validator — permissive but blocks javascript: / data: schemes
# ─────────────────────────────────────────────────────────────
def _clean_url(url: Any) -> str:
    if not url:
        return ""
    u = str(url).strip()
    if not u:
        return ""
    if not _SAFE_URL_RE.match(u) and not u.startswith("http"):
        # Allow bare domain-ish (e.g. twitter.com/fomo) by prefixing https://
        if re.match(r"^[A-Za-z0-9][A-Za-z0-9.\-]+\.[A-Za-z]{2,}(/.*)?$", u):
            u = "https://" + u
        else:
            return ""
    return u


# ─────────────────────────────────────────────────────────────
# Fetch full config (with defaults filled in)
# ─────────────────────────────────────────────────────────────
def _get_config() -> Dict[str, Any]:
    doc = _col.find_one({"_id": _DOC_ID}) or {}
    merged: Dict[str, Any] = {**_DEFAULT_CONFIG, **doc}
    # Deep-merge nested sections
    for key in ("app_links", "legal_pages", "social_links"):
        merged[key] = {**_DEFAULT_CONFIG[key], **(doc.get(key) or {})}
    return merged


# ─────────────────────────────────────────────────────────────
# Pydantic payloads
# ─────────────────────────────────────────────────────────────
class AppLink(BaseModel):
    url: str = ""
    status: str = "soon"


class AppLinksPayload(BaseModel):
    android: Optional[AppLink] = None
    ios: Optional[AppLink] = None
    telegram: Optional[AppLink] = None


class LegalPayload(BaseModel):
    content: str = Field(default="", max_length=200_000)


class SocialLinksPayload(BaseModel):
    twitter: Optional[str] = None
    discord: Optional[str] = None
    telegram: Optional[str] = None
    linkedin: Optional[str] = None


class FullUpdatePayload(BaseModel):
    app_links: Optional[AppLinksPayload] = None
    legal_pages: Optional[Dict[str, str]] = None
    social_links: Optional[SocialLinksPayload] = None


# ─────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────
router = APIRouter(tags=["info-cms"])


# ----- Admin endpoints ---------------------------------------------------
@router.get("/api/admin/info-cms")
async def admin_get_info_cms(admin: dict = Depends(get_admin)):
    cfg = _get_config()
    cfg.pop("_id", None)
    return cfg


@router.put("/api/admin/info-cms")
async def admin_update_info_cms(payload: FullUpdatePayload, admin: dict = Depends(get_admin)):
    update: Dict[str, Any] = {}
    if payload.app_links:
        current = _get_config().get("app_links", {})
        for key in ("android", "ios", "telegram"):
            link: Optional[AppLink] = getattr(payload.app_links, key)
            if link is None:
                continue
            status = link.status if link.status in _ALLOWED_STATUS else "soon"
            current[key] = {"url": _clean_url(link.url), "status": status}
        update["app_links"] = current

    if payload.legal_pages is not None:
        current = _get_config().get("legal_pages", {})
        for page in _ALLOWED_LEGAL:
            if page in payload.legal_pages:
                current[page] = _sanitize_html(payload.legal_pages[page] or "")
        update["legal_pages"] = current

    if payload.social_links:
        current = _get_config().get("social_links", {})
        for key in _ALLOWED_SOCIALS:
            val = getattr(payload.social_links, key, None)
            if val is not None:
                current[key] = _clean_url(val)
        update["social_links"] = current

    if not update:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    update["updated_at"] = datetime.utcnow().isoformat()
    update["updated_by"] = admin.get("username") or admin.get("sub")
    _col.update_one({"_id": _DOC_ID}, {"$set": update}, upsert=True)

    fresh = _get_config()
    fresh.pop("_id", None)
    return {"ok": True, "config": fresh}


# ----- Public endpoints --------------------------------------------------
@router.get("/api/info-cms/public")
async def public_get_info_cms():
    """
    Public snapshot used by /info inject scripts.
    Returns app_links + social_links (no legal bodies).
    """
    cfg = _get_config()
    return {
        "app_links": cfg.get("app_links", {}),
        "social_links": cfg.get("social_links", {}),
    }


@router.get("/api/info-cms/legal/{page}")
async def public_get_legal(page: str):
    if page not in _ALLOWED_LEGAL:
        raise HTTPException(status_code=404, detail="Unknown legal page")
    cfg = _get_config()
    content = (cfg.get("legal_pages") or {}).get(page, "")
    return {"page": page, "content": content, "updated_at": cfg.get("updated_at")}
