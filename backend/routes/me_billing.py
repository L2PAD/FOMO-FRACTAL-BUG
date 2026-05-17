"""
TIER-4C.1 — Public Entitlement Surface (customer-facing self-serve)

Architectural invariants:

  * Entitlement state lives ONLY in the backend (operator_access +
    capability resolver).  Frontend NEVER derives capability meaning —
    it renders what these endpoints return verbatim.

  * Self-serve creates INVOICE INTENTS only.  Activation, refund,
    capability overrides, live-authority and console-access remain
    admin-only actions.  Buying TRADER NEVER grants live trading —
    that semantic boundary is enforced both in product catalog
    (doesNotGrant) and in the activation pipeline.

  * No optimistic UI on the backend side either — invoices return
    status=pending until an operator confirms.  Customers cannot
    cancel/refund their own invoices (refund is operator action).

  * The customer endpoint cannot specify another user's userId.  The
    target is always the authenticated caller (X-User-Id header).

  * One-time invoice issuance model.  No subscription language.

This module is the public-facing complement to the admin-facing
billing_products.py — they share the product catalog (single source
of truth) but expose different surfaces.
"""
from __future__ import annotations

import os
import uuid
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient

from routes.operator_access import (
    _coll as _operator_coll,
    _now as _ts,
    _load as _operator_load,
    _resolve_capabilities,
    _resolve_user_id,
)
from routes.billing_products import (
    PRODUCT_CATALOG,
    _audit_billing,
)

load_dotenv()

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "test_database")]
_invoices = _db.billing_invoices


router = APIRouter(prefix="/api/me/billing", tags=["me-billing"])


# ── Schemas ──────────────────────────────────────────────────────────


class CreateMyInvoiceBody(BaseModel):
    productCode: Literal["PRO", "TRADER"]


# ── Helpers ──────────────────────────────────────────────────────────


def _find_product(code: str) -> dict:
    for p in PRODUCT_CATALOG:
        if p["code"] == code:
            return p
    raise HTTPException(status_code=400, detail={"error": "UNKNOWN_PRODUCT_CODE"})


def _new_invoice_id() -> str:
    return f"inv_{uuid.uuid4().hex[:18]}"


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/products")
def list_products_public():
    """Public read-only catalog — same source as the admin endpoint.
    Returns each product with the explicit `grants` and `doesNotGrant`
    lists so the paywall UI can render the disclaimer block.

    The architectural invariant `paid TRADER ≠ live trading` is
    PRE-STAMPED into every TRADER product entry's `doesNotGrant`
    (['liveTrading', 'executionConsole']) — the UI surfaces these
    verbatim.  Frontend never adds, removes, or interprets these.
    """
    return {"ok": True, "products": PRODUCT_CATALOG}


@router.get("/entitlement")
def get_my_entitlement(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
):
    """Current effective entitlement state for the calling customer.

    Backend-authoritative.  Returns:
      * userId, tier, capabilities (resolved via _resolve_capabilities)
      * pendingInvoices — invoices the customer initiated but which
        have not yet been confirmed
      * paidInvoices — short list of recent paid invoices (so the user
        can see their commercial history without contacting support)

    The frontend renders this directly — never derives capability
    meaning on its own side."""
    user_id = _resolve_user_id(x_user_id, x_user_email)
    record = _operator_load(user_id)
    raw_tier = record.get("tier")
    tier = raw_tier if raw_tier in ("free", "pro", "trader") else "free"

    pending = list(_invoices.find(
        {"userId": user_id, "status": "pending"},
        {"_id": 0},
    ).sort("createdAt", -1).limit(20))
    paid = list(_invoices.find(
        {"userId": user_id, "status": {"$in": ["paid", "refunded"]}},
        {"_id": 0},
    ).sort("createdAt", -1).limit(20))

    return {
        "ok":             True,
        "userId":         user_id,
        "tier":           tier,
        "capabilities":   _resolve_capabilities(record),
        "operatorAccess": record.get("operatorAccess") or {},
        "pendingInvoices": pending,
        "paidInvoices":   paid,
    }


@router.post("/invoices")
def create_my_invoice(
    body: CreateMyInvoiceBody,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
):
    """Self-serve invoice creation.

    The customer initiates the COMMERCIAL INTENT.  Activation still
    requires an operator to confirm — backend NEVER auto-activates a
    self-serve invoice.  This keeps the architectural separation
    between commercial demand and operational entitlement clean.

    Idempotency guard: if the customer already has a `pending` invoice
    for the same productCode, return that existing one instead of
    creating a duplicate — prevents accidental double-clicks from
    spawning multiple commercial intents.
    """
    user_id = _resolve_user_id(x_user_id, x_user_email)
    product = _find_product(body.productCode)

    existing_pending = _invoices.find_one(
        {"userId": user_id, "productCode": body.productCode, "status": "pending"},
        {"_id": 0},
    )
    if existing_pending:
        return {
            "ok": True,
            "invoice": existing_pending,
            "deduplicated": True,
            "note": "An equivalent pending invoice already exists for this product. "
                    "Wait for it to be confirmed instead of creating a duplicate.",
        }

    invoice_id = _new_invoice_id()
    invoice = {
        "invoiceId":      invoice_id,
        "userId":         user_id,
        "productCode":    body.productCode,
        # Frozen product snapshot — receipt remains accurate even if the
        # catalog evolves later.  This is the single immutable record
        # of what was offered at purchase time.
        "productSnapshot": product,
        "priceUsd":       product["priceUsd"],
        "status":         "pending",
        "paymentReference": None,
        "createdAt":      _ts(),
        "updatedAt":      _ts(),
        "paidAt":         None,
        "failedAt":       None,
        "refundedAt":     None,
        # Provenance: marks this row as customer-initiated vs
        # admin-issued.  Used by reconciliation later if we want to
        # split funnels.
        "initiatedBy":    "customer",
    }
    _invoices.insert_one(invoice)
    invoice.pop("_id", None)

    _audit_billing(
        user_id=user_id,
        action="invoice_created",
        actor="customer",
        invoice_id=invoice_id,
        before={"status": None},
        after={"status": "pending", "productCode": body.productCode},
    )

    return {
        "ok": True,
        "invoice": invoice,
        "deduplicated": False,
        # Payment instructions are a stub at this stage — no real
        # provider is wired in TIER-4C.1.  See user spec: "payment
        # provider = simulated/manual confirmation".  An operator
        # confirms the invoice via /admin/billing once payment is
        # observed out-of-band.
        "paymentInstructions": {
            "method":   "manual",
            "status":   "awaiting_operator_confirmation",
            "message":  "Your purchase intent has been recorded. "
                        "An operator will confirm activation manually. "
                        "Tier entitlement will be granted on confirmation.",
        },
    }


@router.get("/invoices")
def list_my_invoices(
    status: Optional[str] = None,
    limit: int = 50,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
):
    """List the calling customer's own invoices.  Cannot see other
    users' invoices — userId filter is NOT exposed."""
    user_id = _resolve_user_id(x_user_id, x_user_email)
    q: dict = {"userId": user_id}
    if status:
        q["status"] = status
    rows = list(_invoices.find(q, {"_id": 0}).sort("createdAt", -1).limit(int(limit)))
    return {"ok": True, "n": len(rows), "rows": rows}
