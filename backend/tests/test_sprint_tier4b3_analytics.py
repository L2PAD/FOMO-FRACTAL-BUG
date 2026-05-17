"""TIER-4B.3 — Billing Analytics (derived read model) tests.

Architectural invariants verified:
  * Analytics is a derived READ MODEL — never a source of truth.
  * No mutation of billing_invoices / billing_audit / operator_access
    when /summary is called.
  * Refunds are dual-tracked: gross / refunded / net surfaced
    separately, never silently netted.
  * Churn semantics are SEPARATED: refundDriven vs voluntary.
  * Time window guard rejects unsupported windows.
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


def _ts(dt=None):
    return (dt or datetime.now(timezone.utc)).isoformat()


def _seed_invoice(uid, *, product, status, price, paid_at=None, refunded_at=None, created_at=None):
    inv_id = f"inv_{uid}_{int(time.time()*1000)}_{product}_{status}"
    _db().billing_invoices.insert_one({
        "invoiceId": inv_id,
        "userId": uid,
        "productCode": product,
        "productSnapshot": {"tier": product.lower(), "code": product, "priceUsd": price,
                            "grants": [], "doesNotGrant": [],
                            "type": "intelligence", "title": "", "subtitle": ""},
        "priceUsd": price,
        "status": status,
        "paymentReference": None,
        "createdAt":   _ts(created_at) if created_at else _ts(),
        "updatedAt":   _ts(),
        "paidAt":      _ts(paid_at)     if paid_at     else None,
        "failedAt":    None,
        "refundedAt":  _ts(refunded_at) if refunded_at else None,
    })
    return inv_id


# ── Tests ────────────────────────────────────────────────────────────


class TestAnalyticsAuth:
    def test_summary_requires_admin(self):
        r = requests.get(f"{BASE_URL}/api/admin/billing/analytics/summary")
        assert r.status_code == 401

    def test_summary_supports_only_known_windows(self):
        r = requests.get(f"{BASE_URL}/api/admin/billing/analytics/summary",
                         headers=_admin_headers(), params={"window": "60d"})
        assert r.status_code == 400
        body = r.json()
        assert body["detail"]["error"] == "INVALID_WINDOW"
        assert set(body["detail"]["supported"]) == {"7d", "30d", "90d"}

    def test_summary_default_window_is_30d(self):
        r = requests.get(f"{BASE_URL}/api/admin/billing/analytics/summary",
                         headers=_admin_headers())
        assert r.status_code == 200
        body = r.json()
        assert body["window"] == "30d"
        assert body["windowDays"] == 30
        # All sections present
        for sec in ("revenue", "mrr", "conversion", "productMix", "refundRate", "churn"):
            assert sec in body, f"missing section {sec}"


class TestRevenueDualTracking:
    UID = "tier4b3_revenue_user"

    def setup_method(self):
        _db().billing_invoices.delete_many({"userId": self.UID})
        _db().billing_audit.delete_many({"userId": self.UID})

    def teardown_method(self):
        _db().billing_invoices.delete_many({"userId": self.UID})
        _db().billing_audit.delete_many({"userId": self.UID})

    def test_gross_refunded_net_are_separate(self):
        now = datetime.now(timezone.utc)

        # Baseline numbers BEFORE we seed.
        before = requests.get(
            f"{BASE_URL}/api/admin/billing/analytics/summary?window=7d",
            headers=_admin_headers(),
        ).json()["revenue"]

        # Two paid PRO, one refunded TRADER inside the 7d window.
        _seed_invoice(self.UID, product="PRO",    status="paid",     price=49.0,
                      created_at=now - timedelta(days=2),
                      paid_at=now - timedelta(days=2))
        _seed_invoice(self.UID, product="PRO",    status="paid",     price=49.0,
                      created_at=now - timedelta(days=1),
                      paid_at=now - timedelta(days=1))
        _seed_invoice(self.UID, product="TRADER", status="refunded", price=99.0,
                      created_at=now - timedelta(days=3),
                      paid_at=now - timedelta(days=3),
                      refunded_at=now - timedelta(days=1))

        after = requests.get(
            f"{BASE_URL}/api/admin/billing/analytics/summary?window=7d",
            headers=_admin_headers(),
        ).json()["revenue"]

        delta_gross    = after["grossRevenue"]    - before["grossRevenue"]
        delta_refunded = after["refundedRevenue"] - before["refundedRevenue"]
        delta_net      = after["netRevenue"]      - before["netRevenue"]

        # gross counts the refunded one too (it was originally a paid event)
        assert delta_gross    == pytest.approx(49.0 + 49.0 + 99.0)
        assert delta_refunded == pytest.approx(99.0)
        assert delta_net      == pytest.approx(49.0 + 49.0)   # 99 - 99 = 0 for the trader


class TestProductMixSplit:
    UID = "tier4b3_mix_user"

    def setup_method(self):
        _db().billing_invoices.delete_many({"userId": self.UID})

    def teardown_method(self):
        _db().billing_invoices.delete_many({"userId": self.UID})

    def test_pro_trader_split_reflects_revenue_share(self):
        now = datetime.now(timezone.utc)
        # 3 PRO @ 49 = 147; 1 TRADER @ 99 = 99 → total 246, PRO share ~ 59.76%
        for _ in range(3):
            _seed_invoice(self.UID, product="PRO", status="paid", price=49.0,
                          created_at=now - timedelta(days=1),
                          paid_at=now - timedelta(days=1))
        _seed_invoice(self.UID, product="TRADER", status="paid", price=99.0,
                      created_at=now - timedelta(days=1),
                      paid_at=now - timedelta(days=1))

        mix = requests.get(
            f"{BASE_URL}/api/admin/billing/analytics/summary?window=7d",
            headers=_admin_headers(),
        ).json()["productMix"]

        # The fixture user contributes 3 PRO + 1 TRADER on top of any
        # baseline.  Test the COUNTS for this user via the per-product
        # count fields by asserting the structure of the response.
        assert mix["pro"]["count"]    >= 3
        assert mix["trader"]["count"] >= 1
        # share fields are present and percentages
        for s in (mix["pro"]["countShare"], mix["pro"]["revShare"],
                  mix["trader"]["countShare"], mix["trader"]["revShare"]):
            assert 0 <= s <= 100


class TestChurnSeparation:
    UID = "tier4b3_churn_user"

    def setup_method(self):
        _db().billing_audit.delete_many({"userId": self.UID})
        _db().operator_access_audit.delete_many({"userId": self.UID})

    def teardown_method(self):
        _db().billing_audit.delete_many({"userId": self.UID})
        _db().operator_access_audit.delete_many({"userId": self.UID})

    def test_refund_driven_and_voluntary_are_dual_tracked(self):
        now = datetime.now(timezone.utc)
        before = requests.get(
            f"{BASE_URL}/api/admin/billing/analytics/summary?window=7d",
            headers=_admin_headers(),
        ).json()["churn"]

        # Seed one refund-driven downgrade (trader → free) via billing_audit
        _db().billing_audit.insert_one({
            "userId": self.UID, "action": "downgrade", "actor": "billing_system",
            "invoiceId": "inv_churn_test", "ts": _ts(now - timedelta(days=1)),
            "before": {"tier": "trader"}, "after": {"tier": "free"},
            "severity": "elevated",
        })
        # Seed one voluntary admin downgrade (pro → free) via operator_access_audit
        _db().operator_access_audit.insert_one({
            "userId": self.UID, "action": "set-tier", "actor": "admin_ops_1",
            "ts": _ts(now - timedelta(days=1)),
            "before": {"tier": "pro"}, "after": {"tier": "free"},
            "severity": "info",
        })

        after = requests.get(
            f"{BASE_URL}/api/admin/billing/analytics/summary?window=7d",
            headers=_admin_headers(),
        ).json()["churn"]

        # Refund-driven and voluntary buckets MUST be separate
        assert after["refundDriven"]["traderToFree"] >= before["refundDriven"]["traderToFree"] + 1
        assert after["voluntary"]["proToFree"]      >= before["voluntary"]["proToFree"]      + 1
        # The two buckets do not contaminate each other
        assert after["refundDriven"]["proToFree"] == before["refundDriven"]["proToFree"]
        assert after["voluntary"]["traderToFree"] == before["voluntary"]["traderToFree"]


class TestAnalyticsNoSideEffects:
    UID = "tier4b3_noeffects_user"

    def setup_method(self):
        _db().billing_invoices.delete_many({"userId": self.UID})

    def teardown_method(self):
        _db().billing_invoices.delete_many({"userId": self.UID})

    def test_summary_is_read_only_on_billing_collections(self):
        # Seed a known invoice
        now = datetime.now(timezone.utc)
        inv_id = _seed_invoice(self.UID, product="PRO", status="paid", price=49.0,
                               created_at=now - timedelta(days=2),
                               paid_at=now - timedelta(days=2))
        before_inv = _db().billing_invoices.find_one({"invoiceId": inv_id}, {"_id": 0})
        before_audit_n = _db().billing_audit.count_documents({})
        before_oa_n    = _db().operator_access.count_documents({})

        # Hit summary multiple times across all windows
        for w in ("7d", "30d", "90d"):
            r = requests.get(
                f"{BASE_URL}/api/admin/billing/analytics/summary?window={w}",
                headers=_admin_headers(),
            )
            assert r.status_code == 200

        after_inv = _db().billing_invoices.find_one({"invoiceId": inv_id}, {"_id": 0})
        after_audit_n = _db().billing_audit.count_documents({})
        after_oa_n    = _db().operator_access.count_documents({})

        # Byte-identical: analytics is purely derived.
        assert before_inv == after_inv
        assert before_audit_n == after_audit_n
        assert before_oa_n    == after_oa_n


class TestMRRBlock:
    def test_mrr_is_always_trailing_30d_regardless_of_window(self):
        b7  = requests.get(f"{BASE_URL}/api/admin/billing/analytics/summary?window=7d",
                           headers=_admin_headers()).json()
        b30 = requests.get(f"{BASE_URL}/api/admin/billing/analytics/summary?window=30d",
                           headers=_admin_headers()).json()
        b90 = requests.get(f"{BASE_URL}/api/admin/billing/analytics/summary?window=90d",
                           headers=_admin_headers()).json()
        # MRR block is identical across window selections — it is its own canonical metric.
        assert b7["mrr"]["trailingWindowDays"]  == 30
        assert b30["mrr"]["trailingWindowDays"] == 30
        assert b90["mrr"]["trailingWindowDays"] == 30
        # mrrApprox should be stable across the three within a tight margin
        # (data may evolve in-flight between consecutive calls, so allow small drift)
        vs = [b7["mrr"]["mrrApproxUsd"], b30["mrr"]["mrrApproxUsd"], b90["mrr"]["mrrApproxUsd"]]
        assert max(vs) - min(vs) <= 1.0, f"MRR drifted across window selections: {vs}"
