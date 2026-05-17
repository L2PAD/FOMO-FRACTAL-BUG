"""TIER-4C.1 — Public Entitlement Surface tests.

Architectural invariants verified:
  * Self-serve POST /me/billing/invoices creates an invoice for the
    AUTHENTICATED caller only — userId in body would be ignored even
    if supplied (the schema rejects it; we verify there is no escape
    hatch).
  * Idempotency guard returns the existing pending invoice instead
    of creating a duplicate on repeated calls (prevents accidental
    multi-click spam).
  * Self-serve never activates — tier stays at free until an operator
    confirms.  Live authority / console access / capability
    overrides remain untouched throughout the customer flow.
  * Product catalog always carries doesNotGrant including
    'liveTrading' and 'executionConsole' — the boundary that
    'TRADER ≠ live trading' is enforced at the data layer, not just
    in the UI copy.
  * Customer can only see their own invoices.
"""
import os
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient


BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://merge-verify-4.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _wipe(uid):
    _db().billing_invoices.delete_many({"userId": uid})
    _db().billing_audit.delete_many({"userId": uid})
    _db().operator_access.delete_many({"userId": uid})


def _hdr(uid):
    return {"X-User-Id": uid}


# ── Catalog ──────────────────────────────────────────────────────────


class TestPublicCatalog:
    def test_products_endpoint_returns_catalog(self):
        r = requests.get(f"{BASE_URL}/api/me/billing/products")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        codes = {p["code"] for p in body["products"]}
        assert codes == {"PRO", "TRADER"}

    def test_trader_product_explicitly_does_not_grant_live(self):
        r = requests.get(f"{BASE_URL}/api/me/billing/products")
        products = {p["code"]: p for p in r.json()["products"]}
        trader = products["TRADER"]
        # The architectural boundary — pre-stamped into the catalog.
        assert "liveTrading"      in trader["doesNotGrant"]
        assert "executionConsole" in trader["doesNotGrant"]
        # And NOT in grants
        assert "liveTrading"      not in trader["grants"]
        assert "executionConsole" not in trader["grants"]

    def test_pro_product_does_not_grant_any_execution(self):
        r = requests.get(f"{BASE_URL}/api/me/billing/products")
        products = {p["code"]: p for p in r.json()["products"]}
        pro = products["PRO"]
        for forbidden in ("paperTrading", "liveTrading", "executionConsole"):
            assert forbidden in pro["doesNotGrant"]
            assert forbidden not in pro["grants"]


# ── Entitlement ──────────────────────────────────────────────────────


class TestMyEntitlement:
    UID = "tier4c1_entitlement_user"

    def setup_method(self):  _wipe(self.UID)
    def teardown_method(self): _wipe(self.UID)

    def test_default_free_tier_has_no_execution_capabilities(self):
        r = requests.get(f"{BASE_URL}/api/me/billing/entitlement", headers=_hdr(self.UID))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tier"] == "free"
        caps = body["capabilities"]
        for forbidden in ("paperTrading", "executionConsole", "liveTrading"):
            assert caps[forbidden] is False, f"free tier must not have {forbidden}"

    def test_entitlement_shows_my_pending_invoices(self):
        # create then read back
        cr = requests.post(
            f"{BASE_URL}/api/me/billing/invoices",
            headers=_hdr(self.UID),
            json={"productCode": "PRO"},
        )
        assert cr.status_code == 200
        ent = requests.get(f"{BASE_URL}/api/me/billing/entitlement",
                           headers=_hdr(self.UID)).json()
        assert len(ent["pendingInvoices"]) == 1
        assert ent["pendingInvoices"][0]["productCode"] == "PRO"
        assert ent["pendingInvoices"][0]["status"] == "pending"
        # Tier did NOT activate — self-serve cannot activate
        assert ent["tier"] == "free"


# ── Self-serve invoice creation ──────────────────────────────────────


class TestSelfServeInvoiceCreation:
    UID = "tier4c1_selfserve_user"

    def setup_method(self):  _wipe(self.UID)
    def teardown_method(self): _wipe(self.UID)

    def test_self_serve_create_pending(self):
        r = requests.post(
            f"{BASE_URL}/api/me/billing/invoices",
            headers=_hdr(self.UID),
            json={"productCode": "TRADER"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        inv = body["invoice"]
        assert inv["userId"] == self.UID
        assert inv["status"] == "pending"
        assert inv["productCode"] == "TRADER"
        assert inv["initiatedBy"] == "customer"
        # Payment instructions are a stub
        assert body["paymentInstructions"]["status"] == "awaiting_operator_confirmation"

    def test_self_serve_idempotent_returns_existing_pending(self):
        r1 = requests.post(f"{BASE_URL}/api/me/billing/invoices",
                           headers=_hdr(self.UID), json={"productCode": "PRO"})
        first_id = r1.json()["invoice"]["invoiceId"]
        # Repeat — must return the SAME invoice, marked deduplicated
        r2 = requests.post(f"{BASE_URL}/api/me/billing/invoices",
                           headers=_hdr(self.UID), json={"productCode": "PRO"})
        assert r2.json()["invoice"]["invoiceId"] == first_id
        assert r2.json()["deduplicated"] is True
        # Mongo confirms only one row exists
        assert _db().billing_invoices.count_documents({
            "userId": self.UID, "productCode": "PRO", "status": "pending",
        }) == 1

    def test_self_serve_creating_trader_does_not_grant_live_authority(self):
        """The load-bearing architectural invariant of TIER-4C.
        Confirms the full chain: customer creates TRADER invoice →
        backend NEVER touches liveAuthority / consoleAccess /
        capabilityOverrides.  Even if the invoice later activates
        (which requires admin confirm), the activation pathway is
        already tested in TIER-4A — here we verify the customer-facing
        creation step itself is inert with respect to governance.
        """
        before = _db().operator_access.find_one({"userId": self.UID}, {"_id": 0})

        requests.post(f"{BASE_URL}/api/me/billing/invoices",
                      headers=_hdr(self.UID), json={"productCode": "TRADER"})

        after = _db().operator_access.find_one({"userId": self.UID}, {"_id": 0})
        # If the user didn't exist before, they still don't have
        # liveAuthority granted.  If they did exist, no field moved.
        if after is not None:
            oa = after.get("operatorAccess") or {}
            assert (oa.get("liveAuthority") or {}).get("granted") is not True
            assert bool(oa.get("consoleAccess")) is False
            assert (oa.get("capabilityOverrides") or {}) == {}
        # operator_access should not have been silently created either —
        # the customer endpoint must NOT touch governance docs
        assert before == after

    def test_self_serve_rejects_unknown_product(self):
        r = requests.post(f"{BASE_URL}/api/me/billing/invoices",
                          headers=_hdr(self.UID), json={"productCode": "MEGA"})
        # pydantic rejects with 422 since literal type mismatch
        assert r.status_code == 422


# ── Cross-user isolation ─────────────────────────────────────────────


class TestCustomerIsolation:
    UID_A = "tier4c1_isolation_a"
    UID_B = "tier4c1_isolation_b"

    def setup_method(self):
        _wipe(self.UID_A)
        _wipe(self.UID_B)

    def teardown_method(self):
        _wipe(self.UID_A)
        _wipe(self.UID_B)

    def test_customer_cannot_see_other_users_invoices(self):
        # User A creates an invoice
        requests.post(f"{BASE_URL}/api/me/billing/invoices",
                      headers=_hdr(self.UID_A), json={"productCode": "PRO"})
        # User B asks for invoices — must NOT see A's
        r = requests.get(f"{BASE_URL}/api/me/billing/invoices",
                         headers=_hdr(self.UID_B))
        body = r.json()
        for inv in body["rows"]:
            assert inv["userId"] == self.UID_B

    def test_customer_endpoint_userid_is_derived_from_header_not_body(self):
        """Customer cannot pose as another user by stuffing a userId
        in the body — the body schema does not accept it.  The header
        is the only source of identity for /me/* endpoints."""
        # Send an arbitrary 'userId' field — schema rejects extras OR
        # ignores them depending on pydantic config.  Either way, the
        # resulting invoice MUST be scoped to UID_A (the header user).
        r = requests.post(
            f"{BASE_URL}/api/me/billing/invoices",
            headers=_hdr(self.UID_A),
            json={"productCode": "PRO", "userId": self.UID_B, "targetUserId": self.UID_B},
        )
        assert r.status_code in (200, 422)
        if r.status_code == 200:
            inv = r.json()["invoice"]
            assert inv["userId"] == self.UID_A, "header identity must win"
            assert inv["userId"] != self.UID_B


# ── Admin operations remain admin-only ───────────────────────────────


class TestAdminOnlyMutationsStillProtected:
    UID = "tier4c1_admin_guard_user"

    def setup_method(self):  _wipe(self.UID)
    def teardown_method(self): _wipe(self.UID)

    def test_customer_cannot_hit_admin_confirm_or_refund(self):
        # Create a pending invoice via self-serve
        cr = requests.post(f"{BASE_URL}/api/me/billing/invoices",
                           headers=_hdr(self.UID), json={"productCode": "PRO"})
        inv_id = cr.json()["invoice"]["invoiceId"]

        # Hitting admin confirm WITHOUT an admin JWT must fail
        r = requests.post(f"{BASE_URL}/api/billing/invoices/confirm",
                          json={"invoiceId": inv_id})
        assert r.status_code == 401

        # Refund equally guarded
        r = requests.post(f"{BASE_URL}/api/billing/invoices/refund",
                          json={"invoiceId": inv_id, "reason": "x"})
        assert r.status_code == 401
