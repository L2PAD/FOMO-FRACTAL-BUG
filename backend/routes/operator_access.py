"""
Operator Access — capability topology + entitlement layer.

NOT a billing system.  NOT RBAC.  NOT a permission engine.
NOT a tier-upgrade flow.  NOT "Pro vs Premium".

This module installs the *semantic gate* between:

    PUBLIC INTELLIGENCE SURFACE  (Home / Feed / Signals / Edge)
        — analytics consumer surface, free + pro tiers —

    RESTRICTED OPERATIONAL ENVIRONMENT  (Trading OS subsystem)
        — Command / Market / Execution / Portfolio / Attribution —
        — access granted, not upgrade —

Wire it now so that when STAGE A bring-up exposes real operator
cognition (suppression graph, parallel universes, execution reasoning,
risk envelope, attribution) it CANNOT leak into the public surface
without an explicit `operatorAccess.enabled=true && status='approved'`
gate.

UI / API language:
    operatorAccess.enabled              boolean
    operatorAccess.status               'none'|'invited'|'pending_review'
                                       |'approved'|'revoked'
    operatorAccess.mode                 'none'|'paper'|'shadow'|'live'

Forbidden language (do not introduce):
    VIP / Elite / Premium Trader / Alpha Club / Inner Circle / Unlock

Endpoints:
    GET   /api/me/capabilities                     — capability map for current user
    POST  /api/me/operator-access/apply            — user submits application
    POST  /api/me/operator-access/risk-ack         — user acknowledges risk
    GET   /api/admin/operator-access/list          — admin lists all access records
    POST  /api/admin/operator-access/grant         — admin approves a user
    POST  /api/admin/operator-access/revoke        — admin revokes access
    POST  /api/admin/operator-access/set-mode      — admin sets paper/shadow/live
    GET   /api/admin/operator-access/audit         — admin reads audit log

Stub-friendly: when auth sidecar is absent, falls back to `dev_user`.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal, List

from fastapi import APIRouter, HTTPException, Request, Header, Body
from pydantic import BaseModel, Field
from pymongo import MongoClient


router = APIRouter(prefix="/api", tags=["operator-access"])

# ─── Mongo wiring ──────────────────────────────────────────────────────
_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "test_database")]
_coll = _db.operator_access
_audit = _db.operator_access_audit
_coll.create_index("userId", unique=True)
_audit.create_index([("userId", 1), ("ts", -1)])

AccessStatus = Literal["none", "invited", "pending_review", "approved", "revoked"]
AccessMode = Literal["none", "paper", "shadow", "live"]
Tier = Literal["free", "pro", "trader"]


# ─── Capability source vocabulary ──────────────────────────────────────
# Every capability bool is paired with a `source` string in
# Capabilities.sources so the operator UI / debug shell can answer the
# question "*why* did this user get this capability?".  Adding a 5th
# source class later is fine — keep the vocabulary closed.
CapabilitySource = Literal[
    "tier_default",     # auto-granted by the tier (trader → paper, etc.)
    "admin_grant",      # explicit admin operator_access grant (mode + consoleAccess)
    "admin_revoke",     # explicit revoke (status='revoked') — overrides tier defaults
    "not_granted",      # neither tier nor admin granted it
]


# Tier → default capabilities (the ONLY place this matrix lives).
#
# Invariants enforced here AT THE TYPE LEVEL:
#   * liveTrading is NEVER a tier default — only admin-granted via mode='live'
#   * executionConsole is NEVER a tier default — only admin-granted via consoleAccess=True
#   * shadowTrading is NEVER a tier default — only admin-granted via mode='shadow'
#
# This is the architectural separation between
#   tier         = commercial product
#   liveTrading  = operational approval
# we never mix billing and operational trust.
_TIER_DEFAULTS: dict[str, set[str]] = {
    "free":   set(),
    "pro":    set(),
    "trader": {"tradingOsVisible", "paperTrading"},  # paper execution workspace
}


# ─── Schemas ───────────────────────────────────────────────────────────
class OperatorAccess(BaseModel):
    enabled: bool = False
    status: AccessStatus = "none"
    mode: AccessMode = "none"
    # Explicit admin-installed scheduler/runtime console access.
    # Customer tiers (free/pro/trader) NEVER auto-grant this — it's the
    # boundary between "customer surface" and "operator surface".
    consoleAccess: bool = False
    riskAcknowledgedAt: Optional[str] = None
    termsAcceptedAt: Optional[str] = None
    appliedAt: Optional[str] = None
    approvedAt: Optional[str] = None
    approvedBy: Optional[str] = None
    maxCapitalExposureUsd: Optional[float] = None
    allowedExchanges: List[str] = Field(default_factory=list)


class CapabilityOverride(BaseModel):
    """Per-capability admin override.

    Two-tier vocabulary:
      'granted'  → admin explicitly turned this capability ON for the
                   user, regardless of tier defaults or mode.
      'revoked'  → admin explicitly turned this capability OFF for the
                   user, regardless of tier defaults / admin grants.

    Both forms are immutable audit-tracked.  The absence of an entry
    means "fall through to the standard derivation chain"."""
    value: Literal["granted", "revoked"]
    reason: Optional[str] = None
    setAt: str
    setBy: str


class LiveAuthority(BaseModel):
    """Operational live-trading authority — DISTINCT from broker mode.

    This is the architectural separation invariant: `mode == 'live'`
    describes the *broker connection*, while `liveAuthority.granted`
    describes whether the operator has been entrusted with live-capital
    deployment authority.  Reaching the live broker requires BOTH."""
    granted: bool = False
    grantedAt: Optional[str] = None
    grantedBy: Optional[str] = None
    reason: Optional[str] = None
    expiresAt: Optional[str] = None  # schema-ready for time-bounded grants


class OperatorAccess(BaseModel):
    enabled: bool = False
    status: AccessStatus = "none"
    mode: AccessMode = "none"                    # broker connection mode ONLY
    consoleAccess: bool = False
    # ── TIER-3 governance ─────────────────────────────────────────────
    # Per-capability admin override map.  Keys ⊂ {tradingOsVisible,
    # paperTrading, shadowTrading, liveTrading, executionConsole}.
    capabilityOverrides: dict = Field(default_factory=dict)
    # Operational live-trading authority — admin governance decision,
    # NOT a billing tier upgrade and NOT derived from `mode`.
    liveAuthority: LiveAuthority = Field(default_factory=LiveAuthority)
    # Last write touching capability surface (for operator review UX)
    lastCapabilityChangeAt: Optional[str] = None
    lastCapabilityChangedBy: Optional[str] = None
    # ── Legacy / observability fields ─────────────────────────────────
    riskAcknowledgedAt: Optional[str] = None
    termsAcceptedAt: Optional[str] = None
    appliedAt: Optional[str] = None
    approvedAt: Optional[str] = None
    approvedBy: Optional[str] = None
    maxCapitalExposureUsd: Optional[float] = None
    allowedExchanges: List[str] = Field(default_factory=list)


# ── Structured capability cell ────────────────────────────────────────
class CapabilityCell(BaseModel):
    """A single capability with full provenance for the admin UI.

    The admin SPA renders the TIER-3 capability table directly from
    this — *no derivation happens on the frontend*."""
    effective: bool
    source: CapabilitySource
    override: Literal["none", "manual", "expired"] = "none"


class EffectiveSummary(BaseModel):
    """Backend-rendered Can/Cannot prose lines for the operator review
    panel.  The admin SPA does NOT compute these itself."""
    can: List[str] = Field(default_factory=list)
    cannot: List[str] = Field(default_factory=list)


class Capabilities(BaseModel):
    """Resolved capability map.

    Derivation precedence (HIGH → LOW):
      1. per-capability override (capabilityOverrides[name])
      2. status == 'revoked'                   → all OFF (admin_revoke)
      3. capability-specific admin grant       (mode / consoleAccess / liveAuthority)
      4. tier defaults                         (_TIER_DEFAULTS[tier])
      5. not_granted                           → default deny

    Architectural invariant — `mode` is NEVER coupled to `liveTrading`:
      liveTrading.effective requires operatorAccess.liveAuthority.granted
      AND (no expiry or not expired) AND (no revoke override).
    A broker connection in mode='live' without live authority means the
    broker can read live market data but the operator has NO authority
    to deploy capital.
    """
    tier: Tier = "free"
    analyticsBasic: bool = True
    analyticsPro: bool = False
    # Legacy bool fields — kept for backward compat with all existing
    # FastAPI Depends(require_capability(...)) guards and frontend
    # consumers that read caps.paperTrading as a bool.
    tradingOsVisible: bool = False
    executionConsole: bool = False
    paperTrading: bool = False
    shadowTrading: bool = False
    liveTrading: bool = False
    # TIER-3 structured surface (admin SPA reads this; frontend trader
    # code keeps reading the bool fields above).
    structured: dict = Field(default_factory=dict)   # name → CapabilityCell
    effectiveSummary: EffectiveSummary = Field(default_factory=EffectiveSummary)
    # Legacy field kept for transitional compat — same data as
    # structured[name].source.  New code should read `structured`.
    sources: dict = Field(default_factory=dict)


class MeCapabilitiesResponse(BaseModel):
    userId: str
    tier: Tier
    operatorAccess: OperatorAccess
    capabilities: Capabilities


class ApplyBody(BaseModel):
    termsAccepted: bool = False
    note: Optional[str] = None


class RiskAckBody(BaseModel):
    acknowledged: bool


class GrantBody(BaseModel):
    userId: str
    mode: AccessMode = "paper"
    consoleAccess: Optional[bool] = None
    maxCapitalExposureUsd: Optional[float] = None
    allowedExchanges: List[str] = Field(default_factory=list)


class SetModeBody(BaseModel):
    userId: str
    mode: AccessMode


class SetTierBody(BaseModel):
    userId: str
    tier: Tier


class SetConsoleAccessBody(BaseModel):
    userId: str
    consoleAccess: bool


class RevokeBody(BaseModel):
    userId: str
    reason: Optional[str] = None


# ─── TIER-3 admin governance bodies ────────────────────────────────────


_CAP_NAMES = ("tradingOsVisible", "paperTrading", "shadowTrading",
              "executionConsole", "liveTrading")
CapName = Literal["tradingOsVisible", "paperTrading", "shadowTrading",
                  "executionConsole", "liveTrading"]


class OverrideCapabilityBody(BaseModel):
    """Granular per-capability override (TIER-3).  Either grants the
    capability irrespective of tier/admin defaults, or revokes it even
    if the tier default would otherwise enable it."""
    userId: str
    capability: CapName
    value: Literal["granted", "revoked", "clear"]   # 'clear' removes the override
    reason: Optional[str] = None


class GrantLiveAuthorityBody(BaseModel):
    """Live-capital deployment authority grant.

    The architectural separation invariant: this is the operational
    decision distinct from `mode='live'` (the broker connection mode).
    Requires server-validated typed confirmation and a mandatory reason."""
    userId: str
    typedConfirmation: str  # MUST equal exactly "GRANT LIVE TRADING"
    reason: str             # mandatory governance justification
    expiresAt: Optional[str] = None  # optional ISO timestamp


class RevokeLiveAuthorityBody(BaseModel):
    userId: str
    reason: str             # mandatory


LIVE_AUTHORITY_PHRASE = "GRANT LIVE TRADING"


# ─── Helpers ───────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_user_id(
    x_user_id: Optional[str], x_user_email: Optional[str]
) -> str:
    """Until the auth sidecar lands, fall back to dev_user.  When auth
    arrives this resolver is the one place to swap to JWT subject."""
    raw = (x_user_id or x_user_email or "dev_user").strip().lower()
    return raw or "dev_user"


def _is_admin(request: Request) -> bool:
    auth = request.headers.get("authorization", "") or request.headers.get(
        "Authorization", ""
    )
    if not auth.lower().startswith("bearer "):
        return False
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return False
    try:
        import jwt as _jwt
        secret = (
            os.environ.get("ADMIN_JWT_SECRET", "")
            or os.environ.get("JWT_ACCESS_SECRET", "")
        )
        payload = _jwt.decode(token, secret, algorithms=["HS256"])
        # Accept both FOMO admin JWT (role="ADMIN"/"SUPERADMIN" uppercase)
        # and operator-auth JWT (role="admin"/"superadmin" lowercase).
        # Casing is normalized — role taxonomy is the source of truth.
        role = (payload.get("role") or "").strip().lower()
        return role in ("superadmin", "admin")
    except Exception:
        return False


def _require_admin(request: Request) -> None:
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})


# ─── Admin auth exchange ───────────────────────────────────────────────


class AdminLoginBody(BaseModel):
    secret: str


@router.post("/admin/operator-auth/login")
def admin_auth_login(body: AdminLoginBody):
    """[LEGACY_ORPHAN_ADMIN_AUTH]

    Operator-secret login for the legacy orphan Expo admin at /admin/*.

    ⚠️ This is NOT the canonical FOMO admin auth endpoint.

    Canonical FOMO Intelligence Terminal admin auth:
        POST /api/admin/auth/login   (routes/admin_auth.py)
        body: {username, password}
        backed by `admin_users` Mongo collection (pbkdf2-hashed)
        used by /api/panel/admin/ React SPA and by 8 test suites

    This endpoint exists only for backward compatibility during the
    admin reintegration migration (TIER-REINTEGRATE.0 hotfix,
    2026-05-14).  Previously it was registered at the canonical path
    /api/admin/auth/login and inadvertently shadowed the FOMO admin
    login form (FastAPI router resolution order — operator_access is
    included before admin_auth, so the earlier registration won).
    Renaming this endpoint to /api/admin/operator-auth/login restores
    the canonical FOMO admin auth route.

    DO NOT add new callers.  Once /app/frontend/src/admin/auth/
    AdminAuthContext.tsx is quarantined (TIER-REINTEGRATE.6), this
    endpoint will have zero callers and can be removed in a future
    sprint.

    Exchanges the admin shared-secret for a short-lived role=admin JWT.
    The shared secret is read from ADMIN_JWT_SECRET (preferred) or
    JWT_ACCESS_SECRET (fallback) in backend/.env. Constant-time compare
    avoids leaking the prefix through timing differences.
    """
    import hmac
    import jwt as _jwt
    expected = (
        os.environ.get("ADMIN_JWT_SECRET", "")
        or os.environ.get("JWT_ACCESS_SECRET", "")
    )
    if not expected:
        raise HTTPException(status_code=500, detail={"error": "ADMIN_SECRET_NOT_CONFIGURED"})
    presented = (body.secret or "").strip()
    if not hmac.compare_digest(expected, presented):
        raise HTTPException(status_code=401, detail={"error": "INVALID_SECRET"})

    # 8h JWT, locked to role=admin. exp/iat use UTC epoch seconds.
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=8)
    payload = {
        "role": "admin",
        "sub": "admin_console",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = _jwt.encode(payload, expected, algorithm="HS256")
    return {
        "ok": True,
        "token": token,
        "expiresAt": exp.isoformat(),
    }


def _load(user_id: str) -> dict:
    """Load or seed the operator_access record for a user.

    Seed policy (dev-time only, until auth sidecar lands):
        dev_user → tier=pro, operatorAccess approved+paper+consoleAccess
                   (so the Trade tab renders the cognition layer in dev
                    AND the operator scheduler/console is unlocked for
                    development; consoleAccess is the boundary between
                    customer surface and operator surface)
        anyone else → tier=free, operatorAccess none
    """
    doc = _coll.find_one({"userId": user_id}, {"_id": 0})
    if doc:
        return doc

    is_dev = user_id in ("dev_user", "dev@fomo.ai")
    seed = {
        "userId": user_id,
        "tier": "pro" if is_dev else "free",
        "operatorAccess": {
            "enabled": is_dev,
            "status": "approved" if is_dev else "none",
            "mode": "paper" if is_dev else "none",
            "consoleAccess": is_dev,                # dev shell gets operator console
            "riskAcknowledgedAt": _now() if is_dev else None,
            "termsAcceptedAt": _now() if is_dev else None,
            "appliedAt": _now() if is_dev else None,
            "approvedAt": _now() if is_dev else None,
            "approvedBy": "seed" if is_dev else None,
            "maxCapitalExposureUsd": None,
            "allowedExchanges": [],
        },
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    _coll.insert_one(seed)
    return {k: v for k, v in seed.items() if k != "_id"}


def _is_expired(expires_at: Optional[str]) -> bool:
    """Check if a liveAuthority expiry timestamp has passed."""
    if not expires_at:
        return False
    try:
        return datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < datetime.now(timezone.utc)
    except Exception:
        return False


# Human-readable phrases for the backend-rendered Can/Cannot panel.
_CAP_PROSE = {
    "tradingOsVisible":  "View Trading OS",
    "paperTrading":      "Deploy paper trades",
    "shadowTrading":     "Run shadow simulations",
    "executionConsole":  "Access execution scheduler & operator console",
    "liveTrading":       "Deploy live capital",
}

_CAP_ORDER = ["tradingOsVisible", "paperTrading", "shadowTrading",
              "executionConsole", "liveTrading"]


def _resolve_capabilities(record: dict) -> Capabilities:
    """Single source of truth for capability derivation.

    Precedence (HIGH → LOW):
      1. per-capability override               (capabilityOverrides[name])
      2. status == 'revoked'                   (admin_revoke)
      3. capability-specific admin grant       (mode / consoleAccess / liveAuthority)
      4. tier defaults                         (_TIER_DEFAULTS[tier])
      5. not_granted

    Architectural invariants:
      * `mode` is NEVER coupled to `liveTrading`. `mode == 'live'` is
        the broker connection mode; `liveTrading` requires an explicit
        liveAuthority grant.
      * `executionConsole` requires the explicit `consoleAccess` flag.
      * tier defaults NEVER include liveTrading / executionConsole /
        shadowTrading.
    """
    # Backward-compat: legacy users may have tier=None or missing.
    raw_tier = record.get("tier")
    tier: Tier = raw_tier if raw_tier in ("free", "pro", "trader") else "free"

    oa = record.get("operatorAccess") or {}
    enabled = bool(oa.get("enabled"))
    status = oa.get("status") or "none"
    mode = oa.get("mode") or "none"
    console_access = bool(oa.get("consoleAccess"))
    cap_overrides = oa.get("capabilityOverrides") or {}
    live_auth = oa.get("liveAuthority") or {}
    live_authority_granted = (
        bool(live_auth.get("granted"))
        and not _is_expired(live_auth.get("expiresAt"))
    )
    approved = enabled and status == "approved"
    revoked = status == "revoked"
    tier_defaults = _TIER_DEFAULTS.get(tier, set())

    structured: dict = {}
    sources: dict = {}

    def _resolve_one(name: str, admin_granted: bool) -> bool:
        # 1. per-capability override (HIGHEST precedence)
        override_entry = cap_overrides.get(name)
        if override_entry:
            ov_value = (
                override_entry.get("value")
                if isinstance(override_entry, dict)
                else override_entry
            )
            if ov_value == "revoked":
                structured[name] = {"effective": False, "source": "admin_revoke", "override": "manual"}
                sources[name] = "admin_revoke"
                return False
            if ov_value == "granted":
                structured[name] = {"effective": True, "source": "admin_grant", "override": "manual"}
                sources[name] = "admin_grant"
                return True
        # 2. blanket admin revoke (status=revoked)
        if revoked:
            structured[name] = {"effective": False, "source": "admin_revoke", "override": "none"}
            sources[name] = "admin_revoke"
            return False
        # 3. explicit admin grant
        if admin_granted:
            structured[name] = {"effective": True, "source": "admin_grant", "override": "none"}
            sources[name] = "admin_grant"
            return True
        # 3b. live-authority expired but grant still in record → mark as expired
        if name == "liveTrading" and bool(live_auth.get("granted")) and _is_expired(live_auth.get("expiresAt")):
            structured[name] = {"effective": False, "source": "not_granted", "override": "expired"}
            sources[name] = "not_granted"
            return False
        # 4. tier default
        if name in tier_defaults:
            structured[name] = {"effective": True, "source": "tier_default", "override": "none"}
            sources[name] = "tier_default"
            return True
        # 5. default deny
        structured[name] = {"effective": False, "source": "not_granted", "override": "none"}
        sources[name] = "not_granted"
        return False

    trading_os_visible = _resolve_one("tradingOsVisible", enabled and not revoked)
    paper_trading = _resolve_one("paperTrading", approved and mode == "paper")
    shadow_trading = _resolve_one("shadowTrading", approved and mode == "shadow")
    execution_console = _resolve_one("executionConsole", approved and console_access)
    # Critical separation: liveTrading depends on liveAuthority, NOT on mode.
    live_trading = _resolve_one("liveTrading", approved and live_authority_granted)

    # Backend-rendered Can/Cannot summary
    effective_map = {
        "tradingOsVisible": trading_os_visible,
        "paperTrading": paper_trading,
        "shadowTrading": shadow_trading,
        "executionConsole": execution_console,
        "liveTrading": live_trading,
    }
    can: list = []
    cannot: list = []
    for k in _CAP_ORDER:
        phrase = _CAP_PROSE[k]
        (can if effective_map[k] else cannot).append(phrase)

    return Capabilities(
        tier=tier,
        analyticsBasic=True,
        analyticsPro=tier in ("pro", "trader"),
        tradingOsVisible=trading_os_visible,
        executionConsole=execution_console,
        paperTrading=paper_trading,
        shadowTrading=shadow_trading,
        liveTrading=live_trading,
        structured=structured,
        sources=sources,
        effectiveSummary=EffectiveSummary(can=can, cannot=cannot),
    )


_AUDIT_SEVERITY = {
    "apply":                       "info",
    "risk-ack":                    "info",
    "set-tier":                    "info",
    "set-mode":                    "info",
    "grant":                       "elevated",
    "revoke":                      "elevated",
    "set-console-access":          "elevated",
    "override-capability":         "elevated",
    "grant-live-authority":        "critical",
    "revoke-live-authority":       "critical",
}


def _audit_write(
    user_id: str,
    action: str,
    actor: str,
    before: dict,
    after: dict,
    note: str = "",
    reason: Optional[str] = None,
) -> None:
    """Append-only audit row. TIER-3 invariant: never edit, never delete.

    `severity` is semantic (info / elevated / critical) — drives alert
    routing and is locked in code, not pulled from the request.
    `before` / `after` are JSON-stable copies; the admin SPA renders
    them side-by-side without inferring anything."""
    _audit.insert_one({
        "userId": user_id,             # target
        "action": action,
        "severity": _AUDIT_SEVERITY.get(action, "info"),
        "actor": actor,
        "before": before,
        "after": after,
        "note": note,
        "reason": reason,
        "ts": _now(),
    })


def _stamp_capability_change(record: dict, actor: str) -> None:
    """Record who/when last touched the capability surface of this user."""
    oa = record.get("operatorAccess") or {}
    oa["lastCapabilityChangeAt"] = _now()
    oa["lastCapabilityChangedBy"] = actor
    record["operatorAccess"] = oa


def _update(
    user_id: str,
    mutator,
    actor: str,
    action: str,
    note: str = "",
    reason: Optional[str] = None,
    touches_capability: bool = True,
) -> dict:
    """Apply mutator(record) → record, write audit, persist.

    `touches_capability=True` stamps lastCapabilityChangeAt+By on the
    record (default; only `apply`/`risk-ack` set False so user-side
    flow doesn't pollute the operator-review surface)."""
    before = _load(user_id)
    after = mutator({**before, "operatorAccess": dict(before.get("operatorAccess") or {})})
    if touches_capability:
        _stamp_capability_change(after, actor)
    after["updatedAt"] = _now()
    _coll.update_one({"userId": user_id}, {"$set": after}, upsert=True)
    persisted = _coll.find_one({"userId": user_id}, {"_id": 0})
    _audit_write(
        user_id, action, actor,
        before=before.get("operatorAccess") or {},
        after=persisted.get("operatorAccess") or {},
        note=note,
        reason=reason,
    )
    return persisted


# ─── /api/me/capabilities ──────────────────────────────────────────────
@router.get("/me/capabilities", response_model=MeCapabilitiesResponse)
def me_capabilities(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
):
    user_id = _resolve_user_id(x_user_id, x_user_email)
    record = _load(user_id)
    raw_tier = record.get("tier")
    normalized_tier = raw_tier if raw_tier in ("free", "pro", "trader") else "free"
    return MeCapabilitiesResponse(
        userId=user_id,
        tier=normalized_tier,
        operatorAccess=OperatorAccess(**(record.get("operatorAccess") or {})),
        capabilities=_resolve_capabilities(record),
    )


# ─── /api/me/operator-access/apply ─────────────────────────────────────
@router.post("/me/operator-access/apply")
def operator_apply(
    body: ApplyBody,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
):
    user_id = _resolve_user_id(x_user_id, x_user_email)
    if not body.termsAccepted:
        raise HTTPException(status_code=400, detail={"error": "TERMS_REQUIRED"})

    def _mut(rec: dict) -> dict:
        oa = rec["operatorAccess"]
        # Only allow apply from 'none' or 'revoked' state.
        if oa.get("status") in ("approved", "pending_review"):
            raise HTTPException(status_code=409, detail={"error": "ALREADY_" + oa["status"].upper()})
        oa["enabled"] = True
        oa["status"] = "pending_review"
        oa["appliedAt"] = _now()
        oa["termsAcceptedAt"] = _now()
        rec["operatorAccess"] = oa
        return rec

    persisted = _update(user_id, _mut, actor="self", action="apply", note=body.note or "", touches_capability=False)
    return {
        "ok": True,
        "operatorAccess": persisted.get("operatorAccess"),
        "message": "Application submitted. Operator access is granted manually after review.",
    }


@router.post("/me/operator-access/risk-ack")
def operator_risk_ack(
    body: RiskAckBody,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
):
    user_id = _resolve_user_id(x_user_id, x_user_email)
    if not body.acknowledged:
        raise HTTPException(status_code=400, detail={"error": "ACK_REQUIRED"})

    def _mut(rec: dict) -> dict:
        rec["operatorAccess"]["riskAcknowledgedAt"] = _now()
        return rec

    persisted = _update(user_id, _mut, actor="self", action="risk-ack", touches_capability=False)
    return {"ok": True, "operatorAccess": persisted.get("operatorAccess")}


# ─── /api/admin/operator-access/* ──────────────────────────────────────
@router.get("/admin/operator-access/list")
def admin_list(
    request: Request,
    limit: int = 200,
    offset: int = 0,
    tier: Optional[str] = None,
    status: Optional[str] = None,
    mode: Optional[str] = None,
    hasOverrides: Optional[bool] = None,
    q: Optional[str] = None,
):
    """TIER-3 admin list with filters + pagination.

    Each row includes the resolved `capabilities` block (effective +
    sources + structured + effectiveSummary) so the admin SPA renders
    truth without re-deriving anything client-side."""
    _require_admin(request)

    query: dict = {}
    if tier:
        query["tier"] = tier
    if status:
        query["operatorAccess.status"] = status
    if mode:
        query["operatorAccess.mode"] = mode
    if q:
        # Best-effort substring match on userId
        query["userId"] = {"$regex": q.lower(), "$options": "i"}

    total = _coll.count_documents(query)
    cursor = _coll.find(query, {"_id": 0}).sort("updatedAt", -1).skip(int(offset)).limit(int(limit))
    rows = []
    for r in cursor:
        if hasOverrides is True and not (r.get("operatorAccess") or {}).get("capabilityOverrides"):
            continue
        if hasOverrides is False and (r.get("operatorAccess") or {}).get("capabilityOverrides"):
            continue
        caps = _resolve_capabilities(r).dict()
        rows.append({
            "userId": r.get("userId"),
            "tier": r.get("tier") or "free",
            "operatorAccess": r.get("operatorAccess") or {},
            "capabilities": caps,
            "updatedAt": r.get("updatedAt"),
        })
    return {"ok": True, "total": total, "n": len(rows), "offset": offset, "limit": limit, "rows": rows}


@router.post("/admin/operator-access/grant")
def admin_grant(request: Request, body: GrantBody):
    _require_admin(request)
    actor = "admin"

    def _mut(rec: dict) -> dict:
        oa = rec["operatorAccess"]
        oa["enabled"] = True
        oa["status"] = "approved"
        oa["mode"] = body.mode
        oa["approvedAt"] = _now()
        oa["approvedBy"] = actor
        if body.consoleAccess is not None:
            oa["consoleAccess"] = bool(body.consoleAccess)
        if body.maxCapitalExposureUsd is not None:
            oa["maxCapitalExposureUsd"] = float(body.maxCapitalExposureUsd)
        if body.allowedExchanges:
            oa["allowedExchanges"] = list(body.allowedExchanges)
        rec["operatorAccess"] = oa
        return rec

    persisted = _update(body.userId, _mut, actor=actor, action="grant")
    return {"ok": True, "operatorAccess": persisted.get("operatorAccess")}


@router.post("/admin/operator-access/set-tier")
def admin_set_tier(request: Request, body: SetTierBody):
    """Set a user's commercial tier.

    NOTE: this is commercial product positioning ONLY. It does not grant
    or revoke `liveTrading` or `executionConsole` — those remain admin
    operational decisions decoupled from billing. Setting tier=trader
    will, however, auto-derive `paperTrading` + `tradingOsVisible` as
    tier defaults at capability-resolution time (unless an explicit
    revoke is in place)."""
    _require_admin(request)

    def _mut(rec: dict) -> dict:
        rec["tier"] = body.tier
        return rec

    persisted = _update(body.userId, _mut, actor="admin", action="set-tier", note=body.tier)
    return {
        "ok": True,
        "tier": persisted.get("tier"),
        "operatorAccess": persisted.get("operatorAccess"),
    }


@router.post("/admin/operator-access/set-console-access")
def admin_set_console_access(request: Request, body: SetConsoleAccessBody):
    """Toggle the operator scheduler/console flag on an existing access record.

    Customer tiers (free/pro/trader) NEVER auto-grant consoleAccess —
    this is the boundary between customer surface and operator surface."""
    _require_admin(request)

    def _mut(rec: dict) -> dict:
        oa = rec["operatorAccess"]
        if oa.get("status") != "approved":
            raise HTTPException(status_code=409, detail={"error": "NOT_APPROVED"})
        oa["consoleAccess"] = bool(body.consoleAccess)
        rec["operatorAccess"] = oa
        return rec

    persisted = _update(
        body.userId, _mut, actor="admin", action="set-console-access",
        note=str(body.consoleAccess),
    )
    return {"ok": True, "operatorAccess": persisted.get("operatorAccess")}


@router.post("/admin/operator-access/set-mode")
def admin_set_mode(request: Request, body: SetModeBody):
    _require_admin(request)

    def _mut(rec: dict) -> dict:
        if (rec["operatorAccess"].get("status") != "approved"):
            raise HTTPException(status_code=409, detail={"error": "NOT_APPROVED"})
        rec["operatorAccess"]["mode"] = body.mode
        return rec

    persisted = _update(body.userId, _mut, actor="admin", action="set-mode", note=body.mode)
    return {"ok": True, "operatorAccess": persisted.get("operatorAccess")}


@router.post("/admin/operator-access/revoke")
def admin_revoke(request: Request, body: RevokeBody):
    _require_admin(request)

    def _mut(rec: dict) -> dict:
        oa = rec["operatorAccess"]
        oa["enabled"] = False
        oa["status"] = "revoked"
        oa["mode"] = "none"
        rec["operatorAccess"] = oa
        return rec

    persisted = _update(body.userId, _mut, actor="admin", action="revoke", note=body.reason or "")
    return {"ok": True, "operatorAccess": persisted.get("operatorAccess")}


@router.get("/admin/operator-access/audit")
def admin_audit(request: Request, userId: Optional[str] = None, limit: int = 200):
    _require_admin(request)
    q = {"userId": userId.lower()} if userId else {}
    rows = list(_audit.find(q, {"_id": 0}).sort("ts", -1).limit(int(limit)))
    return {"ok": True, "n": len(rows), "rows": rows}


# ─── TIER-3 admin governance endpoints ─────────────────────────────────


@router.post("/admin/operator-access/override-capability")
def admin_override_capability(request: Request, body: OverrideCapabilityBody):
    """Set / clear a per-capability admin override.

    Precedence model:
      override=granted  → effective ON  regardless of tier/admin defaults
      override=revoked  → effective OFF regardless of tier/admin defaults
      override=clear    → remove the override (capability falls through
                          to the standard derivation chain)

    The override is the HIGHEST-precedence layer in the resolver, so
    even an explicit blanket revoke (status='revoked') is overridden.
    """
    _require_admin(request)
    cap = body.capability
    if cap == "liveTrading" and body.value == "granted":
        # liveTrading override→granted is allowed but should normally
        # go through grant-live-authority for the typed-confirmation +
        # audit-reason workflow. We still permit it for emergency
        # operational lifts, but stamp a flag in the audit row.
        pass

    def _mut(rec: dict) -> dict:
        oa = rec["operatorAccess"]
        overrides = dict(oa.get("capabilityOverrides") or {})
        if body.value == "clear":
            overrides.pop(cap, None)
        else:
            overrides[cap] = {
                "value": body.value,
                "reason": body.reason,
                "setAt": _now(),
                "setBy": "admin",
            }
        oa["capabilityOverrides"] = overrides
        rec["operatorAccess"] = oa
        return rec

    persisted = _update(
        body.userId, _mut,
        actor="admin",
        action="override-capability",
        note=f"{cap}={body.value}",
        reason=body.reason,
    )
    return {
        "ok": True,
        "operatorAccess": persisted.get("operatorAccess"),
        "capabilities": _resolve_capabilities(persisted).dict(),
    }


@router.post("/admin/operator-access/grant-live-authority")
def admin_grant_live_authority(request: Request, body: GrantLiveAuthorityBody):
    """Grant live-capital deployment authority.

    TIER-3 highest-friction action.  Server-side validation:
      * typedConfirmation MUST equal `LIVE_AUTHORITY_PHRASE` exactly
        (case-sensitive, whitespace-trimmed)
      * reason is mandatory and non-empty after strip()

    Frontend ALSO requires typed confirmation, but backend never trusts
    the client — both layers validate independently."""
    _require_admin(request)
    if (body.typedConfirmation or "").strip() != LIVE_AUTHORITY_PHRASE:
        raise HTTPException(
            status_code=400,
            detail={"error": "TYPED_CONFIRMATION_MISMATCH", "expected": LIVE_AUTHORITY_PHRASE},
        )
    if not (body.reason or "").strip():
        raise HTTPException(status_code=400, detail={"error": "REASON_REQUIRED"})

    def _mut(rec: dict) -> dict:
        oa = rec["operatorAccess"]
        if oa.get("status") != "approved":
            raise HTTPException(status_code=409, detail={"error": "NOT_APPROVED"})
        oa["liveAuthority"] = {
            "granted": True,
            "grantedAt": _now(),
            "grantedBy": "admin",
            "reason": body.reason.strip(),
            "expiresAt": body.expiresAt,
        }
        rec["operatorAccess"] = oa
        return rec

    persisted = _update(
        body.userId, _mut,
        actor="admin",
        action="grant-live-authority",
        note=f"expires={body.expiresAt or 'never'}",
        reason=body.reason.strip(),
    )
    return {
        "ok": True,
        "operatorAccess": persisted.get("operatorAccess"),
        "capabilities": _resolve_capabilities(persisted).dict(),
    }


@router.post("/admin/operator-access/revoke-live-authority")
def admin_revoke_live_authority(request: Request, body: RevokeLiveAuthorityBody):
    """Revoke live-capital deployment authority."""
    _require_admin(request)
    if not (body.reason or "").strip():
        raise HTTPException(status_code=400, detail={"error": "REASON_REQUIRED"})

    def _mut(rec: dict) -> dict:
        oa = rec["operatorAccess"]
        oa["liveAuthority"] = {
            "granted": False,
            "grantedAt": None,
            "grantedBy": None,
            "reason": None,
            "expiresAt": None,
        }
        rec["operatorAccess"] = oa
        return rec

    persisted = _update(
        body.userId, _mut,
        actor="admin",
        action="revoke-live-authority",
        reason=body.reason.strip(),
    )
    return {
        "ok": True,
        "operatorAccess": persisted.get("operatorAccess"),
        "capabilities": _resolve_capabilities(persisted).dict(),
    }


@router.get("/admin/operator-access/audit-timeline")
def admin_audit_timeline(
    request: Request,
    userId: str,
    limit: int = 200,
    severity: Optional[str] = None,
):
    """Per-user append-only audit timeline.  Severity vocab:
    info / elevated / critical.  Records are immutable — no edit/delete."""
    _require_admin(request)
    q: dict = {"userId": userId.lower()}
    if severity:
        q["severity"] = severity
    rows = list(_audit.find(q, {"_id": 0}).sort("ts", -1).limit(int(limit)))
    return {"ok": True, "userId": userId.lower(), "n": len(rows), "rows": rows}
