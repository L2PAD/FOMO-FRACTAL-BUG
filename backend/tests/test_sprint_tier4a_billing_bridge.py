"""TIER-4A — Billing Model + Entitlement Bridge tests.

Architectural invariants verified:
  * Product catalog is explicit & multi-product aware
  * Invoice records explicit purchase intent + frozen productSnapshot
  * Payment NEVER grants liveAuthority / consoleAccess / overrides
  * Billing audit is append-only with locked severity vocab
  * Refund triggers downgrade event (tier→free) but keeps governance grants
  * Cross-system audit: every entitlement activation writes BOTH a
    billing_audit row AND an operator_access_audit row (set-tier)
"""
import os
from pathlib import Path

import pytest
import requests
import jwt as _jwt
from pymongo import MongoClient


BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://merge-verify-4.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _admin_headers():
    secret = os.environ.get("ADMIN_JWT_SECRET") or os.environ.get("JWT_ACCESS_SECRET")
    if not secret:
        env = Path(__file__).resolve().parents[1] / ".env"
        for line in env.read_text().splitlines():
            if line.startswith("ADMIN_JWT_SECRET=") or line.startswith("JWT_ACCESS_SECRET="):
                secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    token = _jwt.encode({"role": "admin", "sub": "test_admin"}, secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _wipe(uid):
    _db().operator_access.delete_many({"userId": uid})
    _db().operator_access_audit.delete_many({"userId": uid})
    _db().billing_invoices.delete_many({"userId": uid})
    _db().billing_audit.delete_many({"userId": uid})


def _seed(uid, *, tier="free", oa=None):
    _db().operator_access.update_one(
        {"userId": uid},
        {"$set": {"userId": uid, "tier": tier, "operatorAccess": oa or {
            "enabled": False, "status": "none", "mode": "none",
            "consoleAccess": False, "capabilityOverrides": {},
            "liveAuthority": {"granted": False},
        }}},
        upsert=True,
    )


def _caps(uid):
    r = requests.get(f"{BASE_URL}/api/me/capabilities",
                     headers={"X-User-Id": uid}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _billing_timeline(uid):
    r = requests.get(f"{BASE_URL}/api/billing/audit-timeline",
                     params={"userId": uid},
                     headers=_admin_headers(), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def _create_invoice(uid, product_code):
    r = requests.post(f"{BASE_URL}/api/billing/invoices",
                      json={"userId": uid, "productCode": product_code},
                      headers=_admin_headers(), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["invoice"]


def _confirm(invoice_id, ref=None):
    return requests.post(f"{BASE_URL}/api/billing/invoices/confirm",
                         json={"invoiceId": invoice_id, "paymentReference": ref},
                         headers=_admin_headers(), timeout=15)


# ── Product catalog ──────────────────────────────────────────────────


class TestProductCatalog:
    def test_catalog_lists_pro_and_trader(self):
        r = requests.get(f"{BASE_URL}/api/billing/products", timeout=15)
        assert r.status_code == 200
        body = r.json()
        codes = {p["code"] for p in body["products"]}
        assert codes == {"PRO", "TRADER"}

    def test_each_product_declares_does_not_grant(self):
        r = requests.get(f"{BASE_URL}/api/billing/products", timeout=15).json()
        for p in r["products"]:
            # Critical: every product MUST declare it does not grant live or console.
            assert "liveTrading" in p["doesNotGrant"]
            assert "executionConsole" in p["doesNotGrant"]


# ── Invoice creation ─────────────────────────────────────────────────


class TestInvoiceCreation:
    USER = "tier4a_invoice_create"

    def setup_method(self, _):
        _wipe(self.USER); _seed(self.USER, tier="free")

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_create_invoice_records_frozen_snapshot(self):
        inv = _create_invoice(self.USER, "TRADER")
        assert inv["status"] == "pending"
        assert inv["productCode"] == "TRADER"
        assert inv["productSnapshot"]["tier"] == "trader"
        assert inv["productSnapshot"]["title"] == "TRADER — Execution Workspace"
        assert "doesNotGrant" in inv["productSnapshot"]

    def test_create_invoice_emits_audit_row(self):
        _create_invoice(self.USER, "TRADER")
        tl = _billing_timeline(self.USER)
        assert tl[0]["action"] == "invoice_created"
        assert tl[0]["severity"] == "info"

    def test_unknown_product_rejected(self):
        r = requests.post(f"{BASE_URL}/api/billing/invoices",
                          json={"userId": self.USER, "productCode": "ENTERPRISE"},
                          headers=_admin_headers(), timeout=15)
        # Pydantic validates Literal first → 422
        assert r.status_code in (404, 422)


# ── Entitlement activation: TRADER ───────────────────────────────────


class TestTraderPurchaseFlow:
    USER = "tier4a_trader_purchase"

    def setup_method(self, _):
        _wipe(self.USER); _seed(self.USER, tier="free")

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_paid_trader_invoice_activates_trader_tier(self):
        inv = _create_invoice(self.USER, "TRADER")
        r = _confirm(inv["invoiceId"], "btc-tx-abc")
        assert r.status_code == 200, r.text
        caps = _caps(self.USER)["capabilities"]
        assert caps["tier"] == "trader"
        # Tier default unlocks paper workspace
        assert caps["paperTrading"] is True
        assert caps["tradingOsVisible"] is True
        assert caps["sources"]["paperTrading"] == "tier_default"

    def test_paid_trader_invoice_does_NOT_grant_live_authority(self):
        """The critical TIER-4 invariant: payment NEVER grants live."""
        inv = _create_invoice(self.USER, "TRADER")
        _confirm(inv["invoiceId"])
        caps = _caps(self.USER)["capabilities"]
        assert caps["liveTrading"] is False
        op = _db().operator_access.find_one({"userId": self.USER}, {"_id": 0})
        assert (op.get("operatorAccess") or {}).get("liveAuthority", {}).get("granted") in (False, None)

    def test_paid_trader_invoice_does_NOT_grant_console_access(self):
        inv = _create_invoice(self.USER, "TRADER")
        _confirm(inv["invoiceId"])
        caps = _caps(self.USER)["capabilities"]
        assert caps["executionConsole"] is False
        op = _db().operator_access.find_one({"userId": self.USER}, {"_id": 0})
        assert (op.get("operatorAccess") or {}).get("consoleAccess") in (False, None)

    def test_paid_trader_invoice_does_NOT_inject_overrides(self):
        inv = _create_invoice(self.USER, "TRADER")
        _confirm(inv["invoiceId"])
        op = _db().operator_access.find_one({"userId": self.USER}, {"_id": 0})
        assert (op.get("operatorAccess") or {}).get("capabilityOverrides") in ({}, None)

    def test_confirmation_writes_three_audit_rows(self):
        """Cross-system audit: invoice_paid + entitlement_activated +
        operator_access_audit set-tier — three append-only rows."""
        inv = _create_invoice(self.USER, "TRADER")
        _confirm(inv["invoiceId"])
        billing = _billing_timeline(self.USER)
        actions = [r["action"] for r in billing]
        assert "invoice_paid" in actions
        assert "entitlement_activated" in actions

        # Cross-link: operator_access audit must have a set-tier row with actor=billing_system
        r = requests.get(f"{BASE_URL}/api/admin/operator-access/audit-timeline",
                         params={"userId": self.USER},
                         headers=_admin_headers(), timeout=15)
        op_tl = r.json()["rows"]
        assert any(row["action"] == "set-tier" and row["actor"] == "billing_system" for row in op_tl)


# ── Operational grants survive billing events ────────────────────────


class TestOperationalGrantsSurviveBilling:
    USER = "tier4a_op_grants_survive"

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_purchase_does_not_erase_existing_live_authority(self):
        """If admin has already granted live authority to a free user
        (edge case but architecturally valid), buying a TRADER plan must
        NOT erase that grant. Billing is orthogonal to governance."""
        _wipe(self.USER)
        _seed(self.USER, tier="free", oa={
            "enabled": True, "status": "approved", "mode": "live",
            "consoleAccess": True,
            "capabilityOverrides": {},
            "liveAuthority": {
                "granted": True,
                "grantedAt": "2026-01-01T00:00:00+00:00",
                "grantedBy": "admin",
                "reason": "pre-billing operational grant",
                "expiresAt": None,
            },
        })
        before = _caps(self.USER)["capabilities"]
        assert before["liveTrading"] is True
        assert before["executionConsole"] is True

        inv = _create_invoice(self.USER, "TRADER")
        _confirm(inv["invoiceId"])

        after = _caps(self.USER)["capabilities"]
        assert after["tier"] == "trader"
        # Operational grants survive billing intervention
        assert after["liveTrading"] is True
        assert after["executionConsole"] is True


# ── Refund / downgrade ───────────────────────────────────────────────


class TestRefundFlow:
    USER = "tier4a_refund"

    def setup_method(self, _):
        _wipe(self.USER); _seed(self.USER, tier="free")

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_refund_downgrades_to_free(self):
        inv = _create_invoice(self.USER, "TRADER")
        _confirm(inv["invoiceId"])
        assert _caps(self.USER)["capabilities"]["tier"] == "trader"

        r = requests.post(f"{BASE_URL}/api/billing/invoices/refund",
                          json={"invoiceId": inv["invoiceId"], "reason": "customer dispute"},
                          headers=_admin_headers(), timeout=15)
        assert r.status_code == 200, r.text
        after = _caps(self.USER)["capabilities"]
        assert after["tier"] == "free"
        assert after["paperTrading"] is False  # tier_default gone

    def test_refund_emits_refund_and_downgrade_audit_rows(self):
        inv = _create_invoice(self.USER, "TRADER")
        _confirm(inv["invoiceId"])
        requests.post(f"{BASE_URL}/api/billing/invoices/refund",
                      json={"invoiceId": inv["invoiceId"], "reason": "test refund"},
                      headers=_admin_headers(), timeout=15)
        tl = _billing_timeline(self.USER)
        actions = [r["action"] for r in tl]
        assert "refund" in actions
        assert "downgrade" in actions
        # Both elevated severity
        for r in tl:
            if r["action"] in ("refund", "downgrade"):
                assert r["severity"] == "elevated"

    def test_refund_requires_reason(self):
        inv = _create_invoice(self.USER, "TRADER")
        _confirm(inv["invoiceId"])
        r = requests.post(f"{BASE_URL}/api/billing/invoices/refund",
                          json={"invoiceId": inv["invoiceId"], "reason": "   "},
                          headers=_admin_headers(), timeout=15)
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "REASON_REQUIRED"

    def test_refund_keeps_admin_granted_live_authority(self):
        """Refund downgrades tier but DOES NOT revoke admin-installed
        operational governance grants."""
        _wipe(self.USER)
        _seed(self.USER, tier="free", oa={
            "enabled": True, "status": "approved", "mode": "live",
            "consoleAccess": True,
            "capabilityOverrides": {},
            "liveAuthority": {
                "granted": True, "grantedAt": "2026-01-01T00:00:00+00:00",
                "grantedBy": "admin", "reason": "ops", "expiresAt": None,
            },
        })
        inv = _create_invoice(self.USER, "TRADER")
        _confirm(inv["invoiceId"])
        requests.post(f"{BASE_URL}/api/billing/invoices/refund",
                      json={"invoiceId": inv["invoiceId"], "reason": "refund"},
                      headers=_admin_headers(), timeout=15)
        after = _caps(self.USER)["capabilities"]
        assert after["tier"] == "free"
        # Live authority NOT touched by refund
        assert after["liveTrading"] is True


# ── Invoice failure ──────────────────────────────────────────────────


class TestFailedInvoice:
    USER = "tier4a_failed_invoice"

    def setup_method(self, _):
        _wipe(self.USER); _seed(self.USER, tier="free")

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_failed_invoice_does_not_change_tier(self):
        inv = _create_invoice(self.USER, "TRADER")
        r = requests.post(f"{BASE_URL}/api/billing/invoices/fail",
                          json={"invoiceId": inv["invoiceId"], "paymentReference": "declined"},
                          headers=_admin_headers(), timeout=15)
        assert r.status_code == 200
        caps = _caps(self.USER)["capabilities"]
        assert caps["tier"] == "free"
        assert caps["paperTrading"] is False
        tl = _billing_timeline(self.USER)
        assert any(r["action"] == "invoice_failed" and r["severity"] == "elevated" for r in tl)


# ── Audit immutability ───────────────────────────────────────────────


class TestBillingAuditAppendOnly:
    def test_no_billing_audit_mutation_endpoints(self):
        for path in (
            "/api/billing/audit-timeline/clear",
            "/api/billing/audit/delete",
            "/api/billing/audit/update",
        ):
            r = requests.post(f"{BASE_URL}{path}", json={},
                              headers=_admin_headers(), timeout=10)
            assert r.status_code in (404, 405)


# ── State transitions are enforced ───────────────────────────────────


class TestInvoiceStateTransitions:
    USER = "tier4a_state_transitions"

    def setup_method(self, _):
        _wipe(self.USER); _seed(self.USER, tier="free")

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_cannot_confirm_already_paid(self):
        inv = _create_invoice(self.USER, "PRO")
        _confirm(inv["invoiceId"])
        r = _confirm(inv["invoiceId"])
        assert r.status_code == 409
        assert r.json()["detail"]["error"] == "INVOICE_NOT_PENDING"

    def test_cannot_refund_unpaid(self):
        inv = _create_invoice(self.USER, "PRO")
        r = requests.post(f"{BASE_URL}/api/billing/invoices/refund",
                          json={"invoiceId": inv["invoiceId"], "reason": "test"},
                          headers=_admin_headers(), timeout=15)
        assert r.status_code == 409
        assert r.json()["detail"]["error"] == "INVOICE_NOT_PAID"

    def test_cannot_confirm_failed(self):
        inv = _create_invoice(self.USER, "PRO")
        requests.post(f"{BASE_URL}/api/billing/invoices/fail",
                      json={"invoiceId": inv["invoiceId"]},
                      headers=_admin_headers(), timeout=15)
        r = _confirm(inv["invoiceId"])
        assert r.status_code == 409
