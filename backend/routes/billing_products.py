"""
TIER-4A — Commercial-to-Operational Bridge

Architectural invariants enforced here:

  * Payment NEVER grants operational danger.
        Buying TRADER lifts `tier` and (via tier_default) auto-grants the
        paper workspace.  It NEVER touches:
          - liveAuthority.granted   (only via grant-live-authority typed flow)
          - consoleAccess           (only via admin set-console-access)
          - capabilityOverrides     (only via admin override-capability)
        These remain admin governance actions, not billing outcomes.

  * Multi-product aware.
        The product catalog is explicit — not implied by `plan == 'pro'`.
        Each product has a `code`, a `type` (intelligence vs
        execution_workspace) and the `tier` it activates.

  * Purchase intent is explicit.
        Every invoice records: productCode, targetUserId, priceUsd, and
        a frozen `productSnapshot` so historical receipts remain
        accurate even after the catalog evolves.

  * Append-only billing audit.
        Vocabulary: invoice_created · invoice_paid · invoice_failed ·
        entitlement_activated · entitlement_failed · refund · downgrade.
        Rows are never edited or deleted.

This module is *backend-only* in Phase 4A.  Billing admin UI (4B) and
client paywall (4C) consume these endpoints later.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo import MongoClient

# Reuse the operator_access machinery for tier mutation + audit cross-link.
from routes.operator_access import (
    _coll as _operator_coll,
    _audit as _operator_audit,
    _audit_write as _operator_audit_write,
    _is_admin as _is_operator_admin,
    _now as _ts,
)

load_dotenv()

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "test_database")]
_invoices = _db.billing_invoices
_audit = _db.billing_audit
_invoices.create_index("userId")
_invoices.create_index("invoiceId", unique=True)
_audit.create_index([("userId", 1), ("ts", -1)])


# ── Product catalog ──────────────────────────────────────────────────
# The single source of truth for what is sellable.  Each entry maps a
# commercial product code to (a) the analytical depth it adds via tier,
# (b) the *intent* it announces to the entitlement layer, and (c) a
# stable display label / price.

PRODUCT_CATALOG: list[dict] = [
    {
        "code": "PRO",
        "type": "intelligence",
        "title": "PRO — Intelligence",
        "subtitle": "Pro-level cognition + verdict transparency",
        "tier": "pro",
        "priceUsd": 49.0,
        "grants": ["analyticsPro"],
        "doesNotGrant": ["paperTrading", "liveTrading", "executionConsole"],
    },
    {
        "code": "TRADER",
        "type": "execution_workspace",
        "title": "TRADER — Execution Workspace",
        "subtitle": "Paper-mode execution + Trading OS surface",
        "tier": "trader",
        "priceUsd": 99.0,
        "grants": ["analyticsPro", "tradingOsVisible", "paperTrading"],
        "doesNotGrant": ["liveTrading", "executionConsole"],
    },
]
_PRODUCT_BY_CODE = {p["code"]: p for p in PRODUCT_CATALOG}

ProductCode = Literal["PRO", "TRADER"]
InvoiceStatus = Literal["pending", "paid", "failed", "refunded"]

# Locked-vocabulary billing event types.  Severity is mirrored from the
# operator_access audit conventions so an admin reviewing one timeline
# sees the same colour semantics.
_BILLING_SEVERITY = {
    "invoice_created":        "info",
    "invoice_paid":           "info",
    "invoice_failed":         "elevated",
    "entitlement_activated":  "info",
    "entitlement_failed":     "elevated",
    "refund":                 "elevated",
    "downgrade":              "elevated",
}


# ── Schemas ──────────────────────────────────────────────────────────


class CreateInvoiceBody(BaseModel):
    userId: str
    productCode: ProductCode
    priceUsdOverride: Optional[float] = None  # for promo / discount injection


class ConfirmInvoiceBody(BaseModel):
    invoiceId: str
    paymentReference: Optional[str] = None    # external txn id / hash


class RefundInvoiceBody(BaseModel):
    invoiceId: str
    reason: str


# ── Helpers ──────────────────────────────────────────────────────────


def _audit_billing(
    user_id: str,
    action: str,
    actor: str,
    before: dict,
    after: dict,
    invoice_id: Optional[str] = None,
    reason: Optional[str] = None,
    note: str = "",
) -> None:
    """Append-only billing event. Never edited, never deleted."""
    _audit.insert_one({
        "userId": user_id,
        "action": action,
        "severity": _BILLING_SEVERITY.get(action, "info"),
        "actor": actor,
        "before": before,
        "after": after,
        "invoiceId": invoice_id,
        "reason": reason,
        "note": note,
        "ts": _ts(),
    })


def _set_tier_safely(user_id: str, new_tier: str, actor: str, reason: str) -> dict:
    """Move a user's commercial tier without touching ANY operational
    governance fields.  This is the invariant guard at code level —
    we only ever update the `tier` key.  liveAuthority, consoleAccess
    and capabilityOverrides remain whatever an admin previously set."""
    before = _operator_coll.find_one({"userId": user_id}, {"_id": 0}) or {}
    before_oa = dict(before.get("operatorAccess") or {})
    _operator_coll.update_one(
        {"userId": user_id},
        {"$set": {"tier": new_tier, "updatedAt": _ts()}, "$setOnInsert": {"userId": user_id, "createdAt": _ts()}},
        upsert=True,
    )
    after = _operator_coll.find_one({"userId": user_id}, {"_id": 0}) or {}
    after_oa = dict(after.get("operatorAccess") or {})
    # Cross-write into operator_access_audit so the operator review UI
    # also shows the tier change with a clear actor ("billing_system").
    _operator_audit_write(
        user_id=user_id,
        action="set-tier",
        actor="billing_system",
        before=before_oa,
        after=after_oa,
        note=new_tier,
        reason=reason,
    )
    return after


# ── Router ───────────────────────────────────────────────────────────


router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/products")
def list_products():
    """Public product catalog.  Frontend paywall + admin billing UI both
    read this — no derivation anywhere else."""
    return {"ok": True, "products": PRODUCT_CATALOG}


@router.post("/invoices")
def create_invoice(body: CreateInvoiceBody, request: Request):
    """Create a purchase-intent invoice.  Admin or self.

    Records a frozen `productSnapshot` so historical receipts stay
    accurate even if the live catalog later evolves."""
    product = _PRODUCT_BY_CODE.get(body.productCode)
    if not product:
        raise HTTPException(status_code=404, detail={"error": "UNKNOWN_PRODUCT_CODE"})
    actor = "admin" if _is_operator_admin(request) else "self"
    # Self-creation is allowed but the targetUserId must equal the caller.
    if actor == "self":
        caller = (request.headers.get("X-User-Id") or "").lower()
        if not caller or caller != body.userId.lower():
            raise HTTPException(status_code=403, detail={"error": "TARGET_MISMATCH"})

    invoice_id = f"inv_{uuid.uuid4().hex[:18]}"
    price = float(body.priceUsdOverride if body.priceUsdOverride is not None else product["priceUsd"])
    doc = {
        "invoiceId": invoice_id,
        "userId": body.userId.lower(),
        "productCode": body.productCode,
        "productSnapshot": product,          # frozen
        "priceUsd": price,
        "status": "pending",
        "paymentReference": None,
        "createdAt": _ts(),
        "updatedAt": _ts(),
        "paidAt": None,
        "failedAt": None,
        "refundedAt": None,
    }
    _invoices.insert_one(doc)
    doc.pop("_id", None)

    _audit_billing(
        user_id=body.userId.lower(),
        action="invoice_created",
        actor=actor,
        before={},
        after={"invoiceId": invoice_id, "productCode": body.productCode, "priceUsd": price},
        invoice_id=invoice_id,
    )
    return {"ok": True, "invoice": doc}


@router.post("/invoices/confirm")
def confirm_invoice(body: ConfirmInvoiceBody, request: Request):
    """Mark an invoice paid and run entitlement activation.

    Phase 4A intentionally uses an admin-driven confirm endpoint instead
    of wiring real payment-provider webhooks.  This keeps the test loop
    fast and surfaces the invariants clearly.  TIER-4 later phases will
    front this with NOWPayments/Stripe webhook handlers that call the
    same function internally.

    Entitlement contract:
      * tier moves to product.tier (PRO → pro, TRADER → trader)
      * NOTHING ELSE in operator_access is touched
      * three audit rows are written:
          1. billing_audit:        invoice_paid
          2. billing_audit:        entitlement_activated (or _failed)
          3. operator_access_audit: set-tier (actor=billing_system)
    """
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})

    inv = _invoices.find_one({"invoiceId": body.invoiceId}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail={"error": "INVOICE_NOT_FOUND"})
    if inv["status"] != "pending":
        raise HTTPException(status_code=409, detail={"error": "INVOICE_NOT_PENDING", "status": inv["status"]})

    user_id = inv["userId"]
    snapshot = inv["productSnapshot"]
    target_tier = snapshot["tier"]

    # 1. mark invoice paid
    _invoices.update_one(
        {"invoiceId": body.invoiceId},
        {"$set": {
            "status": "paid",
            "paymentReference": body.paymentReference,
            "paidAt": _ts(),
            "updatedAt": _ts(),
        }},
    )
    _audit_billing(
        user_id=user_id,
        action="invoice_paid",
        actor="admin",
        before={"status": "pending"},
        after={"status": "paid", "paymentReference": body.paymentReference},
        invoice_id=body.invoiceId,
    )

    # 2. apply entitlement (tier-only)
    try:
        before_op = _operator_coll.find_one({"userId": user_id}, {"_id": 0}) or {}
        before_tier = before_op.get("tier", "free")
        _set_tier_safely(
            user_id=user_id,
            new_tier=target_tier,
            actor="billing_system",
            reason=f"entitlement from invoice {body.invoiceId} (product={inv['productCode']})",
        )
        _audit_billing(
            user_id=user_id,
            action="entitlement_activated",
            actor="billing_system",
            before={"tier": before_tier},
            after={"tier": target_tier, "productCode": inv["productCode"]},
            invoice_id=body.invoiceId,
        )
    except Exception as e:
        _audit_billing(
            user_id=user_id,
            action="entitlement_failed",
            actor="billing_system",
            before={},
            after={"error": str(e)},
            invoice_id=body.invoiceId,
            reason=str(e),
        )
        raise HTTPException(status_code=500, detail={"error": "ENTITLEMENT_FAILED", "message": str(e)})

    fresh = _invoices.find_one({"invoiceId": body.invoiceId}, {"_id": 0})
    return {"ok": True, "invoice": fresh}


@router.post("/invoices/refund")
def refund_invoice(body: RefundInvoiceBody, request: Request):
    """Admin-initiated refund.  Always emits a `downgrade` event so the
    operator review surface can show entitlement removal — and we move
    the tier back to `free` because the customer no longer paid for the
    plan.  Operational governance grants (liveAuthority, consoleAccess,
    capabilityOverrides) are NEVER touched here — admin must revoke
    those separately if appropriate."""
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    if not (body.reason or "").strip():
        raise HTTPException(status_code=400, detail={"error": "REASON_REQUIRED"})

    inv = _invoices.find_one({"invoiceId": body.invoiceId}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail={"error": "INVOICE_NOT_FOUND"})
    if inv["status"] != "paid":
        raise HTTPException(status_code=409, detail={"error": "INVOICE_NOT_PAID", "status": inv["status"]})

    user_id = inv["userId"]
    _invoices.update_one(
        {"invoiceId": body.invoiceId},
        {"$set": {"status": "refunded", "refundedAt": _ts(), "updatedAt": _ts()}},
    )
    _audit_billing(
        user_id=user_id,
        action="refund",
        actor="admin",
        before={"status": "paid"},
        after={"status": "refunded"},
        invoice_id=body.invoiceId,
        reason=body.reason.strip(),
    )

    # Downgrade tier → free.  We intentionally do not touch any other
    # operator_access field.  Operational caps that this user might still
    # hold (admin-granted live, console etc.) survive the refund — that
    # is correct: refund is a billing event, not a governance event.
    before_op = _operator_coll.find_one({"userId": user_id}, {"_id": 0}) or {}
    before_tier = before_op.get("tier", "free")
    _set_tier_safely(
        user_id=user_id,
        new_tier="free",
        actor="billing_system",
        reason=f"downgrade from refund of {body.invoiceId}",
    )
    _audit_billing(
        user_id=user_id,
        action="downgrade",
        actor="billing_system",
        before={"tier": before_tier},
        after={"tier": "free"},
        invoice_id=body.invoiceId,
        reason=body.reason.strip(),
    )

    fresh = _invoices.find_one({"invoiceId": body.invoiceId}, {"_id": 0})
    return {"ok": True, "invoice": fresh}


@router.post("/invoices/fail")
def fail_invoice(body: ConfirmInvoiceBody, request: Request):
    """Mark a pending invoice as failed (e.g. provider declined).
    Emits invoice_failed.  No entitlement is granted."""
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})

    inv = _invoices.find_one({"invoiceId": body.invoiceId}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail={"error": "INVOICE_NOT_FOUND"})
    if inv["status"] != "pending":
        raise HTTPException(status_code=409, detail={"error": "INVOICE_NOT_PENDING", "status": inv["status"]})

    _invoices.update_one(
        {"invoiceId": body.invoiceId},
        {"$set": {"status": "failed", "failedAt": _ts(), "updatedAt": _ts()}},
    )
    _audit_billing(
        user_id=inv["userId"],
        action="invoice_failed",
        actor="admin",
        before={"status": "pending"},
        after={"status": "failed"},
        invoice_id=body.invoiceId,
        reason=body.paymentReference,
    )
    return {"ok": True, "invoice": _invoices.find_one({"invoiceId": body.invoiceId}, {"_id": 0})}


@router.get("/invoices")
def list_invoices(request: Request, userId: Optional[str] = None, limit: int = 50, status: Optional[str] = None):
    """List invoices. Admin sees all; otherwise filtered to caller."""
    is_admin = _is_operator_admin(request)
    caller = (request.headers.get("X-User-Id") or "").lower()
    q: dict = {}
    if not is_admin:
        if not caller:
            raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED"})
        q["userId"] = caller
    elif userId:
        q["userId"] = userId.lower()
    if status:
        q["status"] = status
    rows = list(_invoices.find(q, {"_id": 0}).sort("createdAt", -1).limit(int(limit)))
    return {"ok": True, "n": len(rows), "rows": rows}


@router.get("/audit-timeline")
def audit_timeline(request: Request, userId: str, limit: int = 100):
    """Per-user immutable billing event stream."""
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    rows = list(_audit.find({"userId": userId.lower()}, {"_id": 0}).sort("ts", -1).limit(int(limit)))
    return {"ok": True, "userId": userId.lower(), "n": len(rows), "rows": rows}
