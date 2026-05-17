"""TIER-4B.2 — Billing Reconciliation Integrity tests.

Architectural invariants verified:
  * Findings are IMMUTABLE — no field rewrites, no auto-close.
  * Snapshot-at-detection is mandatory.
  * Dedup key prevents the same anomaly band from being re-recorded.
  * Severity escalation produces a NEW finding, not a mutation.
  * Acknowledgement / mark_resolved_later are SECONDARY ATTESTATIONS
    in a separate append-only collection.
  * Reconciliation NEVER mutates billing_invoices, billing_audit,
    operator_access, or operator_access_audit.
  * Six detectors: stuck_pending, entitlement_mismatch,
    tier_without_billing_trail, failed_activation,
    refunded_but_not_downgraded, orphan_audit_row.
"""
import os
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

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


def _wipe_findings_for(uids):
    _db().billing_reconciliation_findings.delete_many({"userId": {"$in": uids}})
    _db().billing_reconciliation_findings.delete_many({"invoiceId": {"$ne": None, "$in":
        [d["invoiceId"] for d in _db().billing_invoices.find({"userId": {"$in": uids}}, {"invoiceId": 1, "_id": 0})]
    }})


def _ts(dt=None):
    return (dt or datetime.now(timezone.utc)).isoformat()


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate(request):
    """Clean any reconciliation collections + per-test users prior to test."""
    db = _db()
    # We don't wipe global findings/attestations between tests because
    # other tests' data shouldn't interfere; instead each test scopes to
    # its own userId prefix and asserts on its slice.
    yield
    # No global cleanup; specific tests handle their own teardown.


class TestScanInfrastructure:
    def test_scan_requires_admin(self):
        r = requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan")
        assert r.status_code == 401

    def test_findings_requires_admin(self):
        r = requests.get(f"{BASE_URL}/api/admin/billing/reconciliation/findings")
        assert r.status_code == 401

    def test_scan_returns_scan_metadata(self):
        r = requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan", headers=_admin_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        scan = body["scan"]
        assert scan["scanId"].startswith("scn_")
        assert "findingsProduced" in scan
        # all 6 detectors reported
        expected = {"stuck_pending", "entitlement_mismatch", "tier_without_billing_trail",
                    "failed_activation", "refunded_but_not_downgraded", "orphan_audit_row"}
        assert expected.issubset(set(scan["findingsProduced"].keys()))
        assert isinstance(scan["durationMs"], int)


class TestStuckPendingDetector:
    UID = "tier4b2_stuck_user"

    def setup_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def teardown_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def _seed_pending_invoice(self, age_hours):
        created = datetime.now(timezone.utc) - timedelta(hours=age_hours)
        inv_id = f"inv_stuck_{int(age_hours)}_{int(time.time())}"
        _db().billing_invoices.insert_one({
            "invoiceId": inv_id,
            "userId": self.UID,
            "productCode": "PRO",
            "productSnapshot": {"tier": "pro", "code": "PRO", "priceUsd": 49.0,
                               "grants": ["analyticsPro"], "doesNotGrant": ["liveTrading", "executionConsole"],
                               "type": "intelligence", "title": "PRO", "subtitle": ""},
            "priceUsd": 49.0,
            "status": "pending",
            "paymentReference": None,
            "createdAt": _ts(created),
            "updatedAt": _ts(created),
            "paidAt": None, "failedAt": None, "refundedAt": None,
        })
        return inv_id

    def test_stuck_under_24h_produces_no_finding(self):
        inv_id = self._seed_pending_invoice(age_hours=5)
        requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan", headers=_admin_headers())
        rows = list(_db().billing_reconciliation_findings.find({"invoiceId": inv_id}))
        assert rows == []

    def test_stuck_over_24h_produces_elevated_only(self):
        inv_id = self._seed_pending_invoice(age_hours=25)
        requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan", headers=_admin_headers())
        rows = list(_db().billing_reconciliation_findings.find({"invoiceId": inv_id}))
        sev = sorted(r["severity"] for r in rows)
        assert sev == ["elevated"]
        assert rows[0]["evidence"]["ageHours"] >= 24
        assert rows[0]["evidence"]["invoiceSnapshot"]["invoiceId"] == inv_id

    def test_stuck_over_72h_produces_both_bands_with_escalation_link(self):
        inv_id = self._seed_pending_invoice(age_hours=80)
        requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan", headers=_admin_headers())
        rows = list(_db().billing_reconciliation_findings.find({"invoiceId": inv_id}))
        sev = sorted(r["severity"] for r in rows)
        assert sev == ["critical", "elevated"]
        critical = next(r for r in rows if r["severity"] == "critical")
        elevated = next(r for r in rows if r["severity"] == "elevated")
        # critical points back to elevated as the parent (escalation chain)
        assert critical["parentFindingId"] == elevated["findingId"]

    def test_rescan_is_idempotent_no_duplicate_findings(self):
        inv_id = self._seed_pending_invoice(age_hours=25)
        for _ in range(3):
            requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan", headers=_admin_headers())
        rows = list(_db().billing_reconciliation_findings.find({"invoiceId": inv_id}))
        # exactly one elevated, even after 3 scans (dedup key enforced)
        assert len([r for r in rows if r["severity"] == "elevated"]) == 1


class TestEntitlementMismatchDetector:
    UID = "tier4b2_mismatch_user"

    def setup_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def teardown_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def test_paid_invoice_with_wrong_tier_produces_finding(self):
        inv_id = f"inv_mismatch_{int(time.time())}"
        _db().billing_invoices.insert_one({
            "invoiceId": inv_id,
            "userId": self.UID,
            "productCode": "TRADER",
            "productSnapshot": {"tier": "trader", "code": "TRADER", "priceUsd": 99.0,
                               "grants": [], "doesNotGrant": [],
                               "type": "execution_workspace", "title": "", "subtitle": ""},
            "priceUsd": 99.0,
            "status": "paid",
            "paymentReference": None,
            "createdAt": _ts(), "updatedAt": _ts(),
            "paidAt": _ts(), "failedAt": None, "refundedAt": None,
        })
        # user.tier is "free" — clear mismatch with expected "trader"
        _db().operator_access.insert_one({
            "userId": self.UID, "tier": "free",
            "createdAt": _ts(), "updatedAt": _ts(),
        })

        requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan", headers=_admin_headers())

        rows = list(_db().billing_reconciliation_findings.find({
            "userId": self.UID, "findingType": "entitlement_mismatch",
        }))
        assert len(rows) == 1
        f = rows[0]
        assert f["evidence"]["expectedTier"] == "trader"
        assert f["evidence"]["actualTier"] == "free"
        assert f["severity"] == "elevated"


class TestFailedActivationDetector:
    UID = "tier4b2_failedactiv_user"

    def setup_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def teardown_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def test_paid_invoice_with_no_entitlement_activated_is_critical(self):
        inv_id = f"inv_failactiv_{int(time.time())}"
        _db().billing_invoices.insert_one({
            "invoiceId": inv_id, "userId": self.UID, "productCode": "PRO",
            "productSnapshot": {"tier": "pro", "code": "PRO", "priceUsd": 49.0,
                               "grants": [], "doesNotGrant": [],
                               "type": "intelligence", "title": "", "subtitle": ""},
            "priceUsd": 49.0, "status": "paid",
            "paymentReference": None,
            "createdAt": _ts(), "updatedAt": _ts(),
            "paidAt": _ts(), "failedAt": None, "refundedAt": None,
        })
        # invoice_paid event written, but entitlement_activated MISSING
        _db().billing_audit.insert_one({
            "userId": self.UID, "action": "invoice_paid", "actor": "admin",
            "invoiceId": inv_id, "before": {}, "after": {},
            "ts": _ts(), "severity": "info",
        })

        requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan", headers=_admin_headers())

        rows = list(_db().billing_reconciliation_findings.find({
            "userId": self.UID, "findingType": "failed_activation",
        }))
        assert len(rows) == 1
        assert rows[0]["severity"] == "critical"


class TestRefundedNotDowngradedDetector:
    UID = "tier4b2_refund_orphan_user"

    def setup_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def teardown_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def test_refund_without_downgrade_is_critical(self):
        inv_id = f"inv_reforph_{int(time.time())}"
        _db().billing_invoices.insert_one({
            "invoiceId": inv_id, "userId": self.UID, "productCode": "PRO",
            "productSnapshot": {"tier": "pro", "code": "PRO", "priceUsd": 49.0,
                               "grants": [], "doesNotGrant": [],
                               "type": "intelligence", "title": "", "subtitle": ""},
            "priceUsd": 49.0, "status": "refunded",
            "paymentReference": None,
            "createdAt": _ts(), "updatedAt": _ts(),
            "paidAt": _ts(), "failedAt": None, "refundedAt": _ts(),
        })
        # Refund event present, but downgrade event INTENTIONALLY missing.
        _db().billing_audit.insert_one({
            "userId": self.UID, "action": "refund", "actor": "admin",
            "invoiceId": inv_id, "before": {"status": "paid"}, "after": {"status": "refunded"},
            "ts": _ts(), "severity": "elevated",
        })

        requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan", headers=_admin_headers())

        rows = list(_db().billing_reconciliation_findings.find({
            "userId": self.UID, "findingType": "refunded_but_not_downgraded",
        }))
        assert len(rows) == 1
        assert rows[0]["severity"] == "critical"


class TestAttestationOverlay:
    """Attestations are append-only attestation EVENTS; the finding
    itself never mutates.  Effective status is computed at read time."""

    UID = "tier4b2_attest_user"

    def setup_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})
        _db().billing_reconciliation_attestations.delete_many({})

    def teardown_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})
        _db().billing_reconciliation_attestations.delete_many({})

    def _seed_one_finding(self):
        # easy way to produce a deterministic finding: tier_without_billing_trail
        _db().operator_access.insert_one({
            "userId": self.UID, "tier": "trader",
            "createdAt": _ts(), "updatedAt": _ts(),
        })
        requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan", headers=_admin_headers())
        row = _db().billing_reconciliation_findings.find_one({"userId": self.UID})
        assert row is not None
        return row["findingId"]

    def test_default_status_is_open(self):
        fid = self._seed_one_finding()
        r = requests.get(f"{BASE_URL}/api/admin/billing/reconciliation/findings/{fid}",
                         headers=_admin_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["finding"]["status"] == "open"
        assert body["attestations"] == []

    def test_acknowledge_creates_attestation_without_mutating_finding(self):
        fid = self._seed_one_finding()
        original = dict(_db().billing_reconciliation_findings.find_one({"findingId": fid}))
        r = requests.post(
            f"{BASE_URL}/api/admin/billing/reconciliation/findings/{fid}/attest",
            headers=_admin_headers(),
            json={"action": "acknowledge", "reason": "operator reviewed"},
        )
        assert r.status_code == 200, r.text
        # finding row UNCHANGED
        after = dict(_db().billing_reconciliation_findings.find_one({"findingId": fid}))
        for k in ("severity", "findingType", "detectedAt", "dedupKey",
                  "evidence", "scanId", "parentFindingId"):
            assert original[k] == after[k]
        # status overlay flips
        detail = requests.get(f"{BASE_URL}/api/admin/billing/reconciliation/findings/{fid}",
                              headers=_admin_headers()).json()
        assert detail["finding"]["status"] == "acknowledged"
        assert len(detail["attestations"]) == 1
        assert detail["attestations"][0]["action"] == "acknowledge"
        assert detail["attestations"][0]["reason"] == "operator reviewed"

    def test_multiple_attestations_use_latest_for_overlay(self):
        fid = self._seed_one_finding()
        requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/findings/{fid}/attest",
                      headers=_admin_headers(), json={"action": "acknowledge"})
        time.sleep(0.05)
        requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/findings/{fid}/attest",
                      headers=_admin_headers(),
                      json={"action": "mark_resolved_later", "note": "issue auto-cleared after admin action"})
        detail = requests.get(f"{BASE_URL}/api/admin/billing/reconciliation/findings/{fid}",
                              headers=_admin_headers()).json()
        # most recent wins
        assert detail["finding"]["status"] == "resolved_later"
        # both records survive in the attestations timeline
        assert len(detail["attestations"]) == 2
        actions = [a["action"] for a in detail["attestations"]]
        assert "acknowledge" in actions and "mark_resolved_later" in actions

    def test_attestation_for_unknown_finding_returns_404(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/billing/reconciliation/findings/fnd_does_not_exist/attest",
            headers=_admin_headers(), json={"action": "acknowledge"},
        )
        assert r.status_code == 404


class TestReconciliationNoSideEffects:
    """Reconciliation observation MUST NOT touch the underlying ledger."""

    UID = "tier4b2_no_side_effects_user"

    def setup_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def teardown_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def test_scan_does_not_mutate_invoices_or_audit_or_operator_access(self):
        # Seed a paid invoice + matching audit + user tier=free (mismatch).
        inv_id = f"inv_noeffect_{int(time.time())}"
        inv_doc = {
            "invoiceId": inv_id, "userId": self.UID, "productCode": "PRO",
            "productSnapshot": {"tier": "pro", "code": "PRO", "priceUsd": 49.0,
                               "grants": [], "doesNotGrant": [],
                               "type": "intelligence", "title": "", "subtitle": ""},
            "priceUsd": 49.0, "status": "paid",
            "paymentReference": None,
            "createdAt": _ts(), "updatedAt": _ts(),
            "paidAt": _ts(), "failedAt": None, "refundedAt": None,
        }
        _db().billing_invoices.insert_one(dict(inv_doc))
        audit_doc = {
            "userId": self.UID, "action": "invoice_paid", "actor": "admin",
            "invoiceId": inv_id, "before": {}, "after": {},
            "ts": _ts(), "severity": "info",
        }
        _db().billing_audit.insert_one(dict(audit_doc))
        oa_doc = {"userId": self.UID, "tier": "free", "createdAt": _ts(), "updatedAt": _ts()}
        _db().operator_access.insert_one(dict(oa_doc))

        # Capture pre-scan state
        before_invoice = _db().billing_invoices.find_one({"invoiceId": inv_id}, {"_id": 0})
        before_audit_count = _db().billing_audit.count_documents({"userId": self.UID})
        before_oa = _db().operator_access.find_one({"userId": self.UID}, {"_id": 0})

        requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan", headers=_admin_headers())

        # Post-scan: every underlying record byte-identical
        after_invoice = _db().billing_invoices.find_one({"invoiceId": inv_id}, {"_id": 0})
        after_audit_count = _db().billing_audit.count_documents({"userId": self.UID})
        after_oa = _db().operator_access.find_one({"userId": self.UID}, {"_id": 0})
        assert before_invoice == after_invoice
        assert before_audit_count == after_audit_count
        assert before_oa == after_oa


class TestSummaryAndListing:
    """Summary endpoint aggregates findings; listing supports filters."""

    UID = "tier4b2_summary_user"

    def setup_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def teardown_method(self):
        _wipe(self.UID)
        _db().billing_reconciliation_findings.delete_many({"userId": self.UID})

    def test_summary_shape(self):
        r = requests.get(f"{BASE_URL}/api/admin/billing/reconciliation/summary",
                         headers=_admin_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert {"totalFindings", "bySeverity", "byCategory", "byStatus", "lastScan"} <= set(body.keys())
        assert set(body["bySeverity"].keys()) == {"info", "elevated", "critical"}
        assert set(body["byStatus"].keys()) == {"open", "acknowledged", "resolved_later"}

    def test_findings_filter_by_severity(self):
        _db().operator_access.insert_one({
            "userId": self.UID, "tier": "pro",
            "createdAt": _ts(), "updatedAt": _ts(),
        })
        requests.post(f"{BASE_URL}/api/admin/billing/reconciliation/scan", headers=_admin_headers())
        r = requests.get(f"{BASE_URL}/api/admin/billing/reconciliation/findings",
                         params={"severity": "info", "userId": self.UID},
                         headers=_admin_headers())
        assert r.status_code == 200
        rows = r.json()["rows"]
        assert all(row["severity"] == "info" for row in rows)
        assert any(row["userId"] == self.UID for row in rows)
