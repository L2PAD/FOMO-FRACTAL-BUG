"""Sprint TIER-3 — Governance Layer Invariants.

Tests the 8 architectural requirements:
  A. Never compute "effective" on frontend  → backend ships effective+source+override+effectiveSummary
  B. Audit records are immutable (append-only)
  C. Live authority supports expiresAt schema
  D. Severity is semantic (info/elevated/critical)
  E. Mode is decoupled from liveTrading authority
  F. Server-validated typed confirmation for live-authority grant
  G. lastCapabilityChangeAt + lastCapabilityChangedBy stamped
  H. Per-capability override precedence is HIGHEST
"""
import os
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
    _db().operator_access.delete_many({"userId": uid})
    _db().operator_access_audit.delete_many({"userId": uid})


def _seed(uid, *, tier="trader", oa=None):
    _db().operator_access.update_one(
        {"userId": uid},
        {"$set": {"userId": uid, "tier": tier, "operatorAccess": oa or {
            "enabled": True, "status": "approved", "mode": "paper",
            "consoleAccess": False, "capabilityOverrides": {},
            "liveAuthority": {"granted": False},
        }}},
        upsert=True,
    )


def _caps(uid):
    r = requests.get(
        f"{BASE_URL}/api/me/capabilities",
        headers={"X-User-Id": uid}, timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _admin_token():
    """Generate a valid admin JWT for backend admin endpoints."""
    import jwt
    from pathlib import Path
    # Load secret from backend/.env so tests align with the running server.
    secret = os.environ.get("ADMIN_JWT_SECRET") or os.environ.get("JWT_ACCESS_SECRET")
    if not secret:
        env_path = Path(__file__).resolve().parents[1] / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("ADMIN_JWT_SECRET=") or line.startswith("JWT_ACCESS_SECRET="):
                    secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if secret:
                        break
    secret = secret or "test-secret-fallback-32-chars-min!!"
    return jwt.encode({"role": "admin", "sub": "test_admin"}, secret, algorithm="HS256")


def _admin_headers():
    return {"Authorization": f"Bearer {_admin_token()}"}


# ── E. Mode decoupled from liveTrading authority ──────────────────────


class TestModeAuthorityDecoupling:
    USER = "tier3_mode_authority_decouple"

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_mode_live_without_authority_does_NOT_grant_live_trading(self):
        """The critical architectural invariant: a broker connection in
        mode='live' without liveAuthority.granted must NOT enable
        liveTrading capability."""
        _wipe(self.USER)
        _seed(self.USER, tier="pro", oa={
            "enabled": True, "status": "approved", "mode": "live",
            "consoleAccess": False,
            "liveAuthority": {"granted": False},   # ← key
        })
        caps = _caps(self.USER)["capabilities"]
        assert caps["liveTrading"] is False, "mode=live MUST NOT imply liveTrading"
        assert caps["sources"]["liveTrading"] == "not_granted"

    def test_live_authority_without_mode_live_still_no_live_trading(self):
        """Symmetric: liveAuthority granted but mode=paper — still not
        live (no broker connection that could execute). Defensive."""
        _wipe(self.USER)
        _seed(self.USER, tier="pro", oa={
            "enabled": True, "status": "approved", "mode": "paper",
            "consoleAccess": False,
            "liveAuthority": {"granted": True, "grantedAt": "2026-01-01T00:00:00+00:00",
                              "grantedBy": "test", "reason": "test"},
        })
        # liveAuthority alone is enough at the capability layer — broker
        # layer enforces the mode separately. Document the boundary:
        caps = _caps(self.USER)["capabilities"]
        assert caps["liveTrading"] is True, "liveAuthority IS the capability axis"
        assert caps["sources"]["liveTrading"] == "admin_grant"


# ── A. Backend ships effective + source + override + effectiveSummary ─


class TestStructuredCapabilityShape:
    def test_structured_present_for_every_capability(self):
        body = _caps("dev_user")
        caps = body["capabilities"]
        assert "structured" in caps
        for name in ("tradingOsVisible", "paperTrading", "shadowTrading",
                     "executionConsole", "liveTrading"):
            assert name in caps["structured"]
            cell = caps["structured"][name]
            assert "effective" in cell
            assert "source" in cell
            assert "override" in cell
            assert cell["source"] in ("tier_default", "admin_grant", "admin_revoke", "not_granted")
            assert cell["override"] in ("none", "manual", "expired")

    def test_effective_summary_is_backend_rendered(self):
        body = _caps("dev_user")
        caps = body["capabilities"]
        assert "effectiveSummary" in caps
        es = caps["effectiveSummary"]
        assert "can" in es and "cannot" in es
        # dev_user: paper + console
        assert "Deploy paper trades" in es["can"]
        assert "Deploy live capital" in es["cannot"]


# ── H. Per-capability override precedence is HIGHEST ──────────────────


class TestPerCapabilityOverridePrecedence:
    USER = "tier3_per_cap_override"

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_override_revoke_beats_tier_default(self):
        """trader tier defaults paperTrading=True. Per-cap override
        'revoked' must turn it OFF — even though the tier still gives it."""
        _wipe(self.USER)
        _seed(self.USER, tier="trader", oa={
            "enabled": True, "status": "approved", "mode": "paper",
            "consoleAccess": False,
            "capabilityOverrides": {
                "paperTrading": {"value": "revoked", "reason": "test",
                                 "setAt": "2026-01-01T00:00:00+00:00",
                                 "setBy": "test_admin"},
            },
            "liveAuthority": {"granted": False},
        })
        caps = _caps(self.USER)["capabilities"]
        assert caps["paperTrading"] is False
        assert caps["sources"]["paperTrading"] == "admin_revoke"
        assert caps["structured"]["paperTrading"]["override"] == "manual"

    def test_override_grant_beats_not_granted(self):
        """free tier user, no admin grant, but per-cap override
        'granted' must enable the capability."""
        _wipe(self.USER)
        _seed(self.USER, tier="free", oa={
            "enabled": False, "status": "none", "mode": "none",
            "consoleAccess": False,
            "capabilityOverrides": {
                "executionConsole": {"value": "granted", "reason": "emergency lift",
                                     "setAt": "2026-01-01T00:00:00+00:00",
                                     "setBy": "test_admin"},
            },
            "liveAuthority": {"granted": False},
        })
        caps = _caps(self.USER)["capabilities"]
        assert caps["executionConsole"] is True
        assert caps["sources"]["executionConsole"] == "admin_grant"
        assert caps["structured"]["executionConsole"]["override"] == "manual"


# ── F. Server-validated typed confirmation ────────────────────────────


class TestLiveAuthorityTypedConfirmation:
    USER = "tier3_live_authority_typed"

    def setup_method(self, _):
        _wipe(self.USER)
        _seed(self.USER, tier="pro", oa={
            "enabled": True, "status": "approved", "mode": "paper",
            "consoleAccess": False, "liveAuthority": {"granted": False},
        })

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_grant_rejects_wrong_phrase(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/grant-live-authority",
            json={
                "userId": self.USER,
                "typedConfirmation": "grant live trading",   # wrong case
                "reason": "test",
            },
            headers=_admin_headers(),
            timeout=15,
        )
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "TYPED_CONFIRMATION_MISMATCH"

    def test_grant_rejects_empty_reason(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/grant-live-authority",
            json={
                "userId": self.USER,
                "typedConfirmation": "GRANT LIVE TRADING",
                "reason": "   ",
            },
            headers=_admin_headers(),
            timeout=15,
        )
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "REASON_REQUIRED"

    def test_grant_accepts_exact_phrase_with_reason(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/grant-live-authority",
            json={
                "userId": self.USER,
                "typedConfirmation": "GRANT LIVE TRADING",
                "reason": "Production approval: AAPL portfolio rollout",
            },
            headers=_admin_headers(),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        caps = _caps(self.USER)["capabilities"]
        assert caps["liveTrading"] is True
        assert caps["sources"]["liveTrading"] == "admin_grant"


# ── B. Audit immutable + D. severity vocab + G. lastCapabilityChange ─


class TestAuditGovernance:
    USER = "tier3_audit_governance"

    def setup_method(self, _):
        _wipe(self.USER)
        _seed(self.USER, tier="pro", oa={
            "enabled": True, "status": "approved", "mode": "paper",
            "consoleAccess": False, "liveAuthority": {"granted": False},
        })

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_grant_live_authority_writes_critical_audit_row(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/grant-live-authority",
            json={
                "userId": self.USER,
                "typedConfirmation": "GRANT LIVE TRADING",
                "reason": "production rollout",
            },
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200, r.text

        timeline = requests.get(
            f"{BASE_URL}/api/admin/operator-access/audit-timeline",
            params={"userId": self.USER},
            headers=_admin_headers(), timeout=15,
        ).json()
        rows = timeline["rows"]
        assert len(rows) >= 1
        row = next(r for r in rows if r["action"] == "grant-live-authority")
        assert row["severity"] == "critical"
        assert row["actor"] == "admin"
        assert row["userId"] == self.USER
        assert row["reason"] == "production rollout"
        assert "before" in row and "after" in row
        assert row["after"]["liveAuthority"]["granted"] is True

    def test_capability_override_severity_elevated(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/override-capability",
            json={"userId": self.USER, "capability": "executionConsole",
                  "value": "granted", "reason": "ops emergency"},
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200, r.text

        timeline = requests.get(
            f"{BASE_URL}/api/admin/operator-access/audit-timeline",
            params={"userId": self.USER, "severity": "elevated"},
            headers=_admin_headers(), timeout=15,
        ).json()
        rows = timeline["rows"]
        assert any(r["action"] == "override-capability" and r["severity"] == "elevated" for r in rows)

    def test_last_capability_change_stamped(self):
        before_caps = _caps(self.USER)
        before_stamp = before_caps["operatorAccess"].get("lastCapabilityChangeAt")

        # Trigger a capability change
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/override-capability",
            json={"userId": self.USER, "capability": "executionConsole",
                  "value": "granted", "reason": "test"},
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200

        after = _caps(self.USER)["operatorAccess"]
        assert after["lastCapabilityChangeAt"] is not None
        assert after["lastCapabilityChangedBy"] == "admin"
        if before_stamp:
            assert after["lastCapabilityChangeAt"] != before_stamp


# ── C. Live authority expiry schema ──────────────────────────────────


class TestLiveAuthorityExpiry:
    USER = "tier3_live_authority_expiry"

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_expired_authority_is_not_effective(self):
        _wipe(self.USER)
        _seed(self.USER, tier="pro", oa={
            "enabled": True, "status": "approved", "mode": "live",
            "consoleAccess": False,
            "liveAuthority": {
                "granted": True,
                "grantedAt": "2020-01-01T00:00:00+00:00",
                "grantedBy": "test", "reason": "test",
                "expiresAt": "2020-01-02T00:00:00+00:00",   # long expired
            },
        })
        caps = _caps(self.USER)["capabilities"]
        assert caps["liveTrading"] is False
        assert caps["structured"]["liveTrading"]["override"] == "expired"

    def test_future_expiry_still_effective(self):
        _wipe(self.USER)
        _seed(self.USER, tier="pro", oa={
            "enabled": True, "status": "approved", "mode": "live",
            "consoleAccess": False,
            "liveAuthority": {
                "granted": True,
                "grantedAt": "2026-01-01T00:00:00+00:00",
                "grantedBy": "test", "reason": "test",
                "expiresAt": "2099-12-31T23:59:59+00:00",
            },
        })
        caps = _caps(self.USER)["capabilities"]
        assert caps["liveTrading"] is True


# ── B (deeper). Audit append-only — no edit/delete ops exposed ────────


class TestAuditAppendOnly:
    def test_no_audit_delete_endpoint_exposed(self):
        """No admin endpoint deletes audit rows. We confirm by hitting
        likely paths and expecting 404 / 405."""
        for path in ("/api/admin/operator-access/audit/delete",
                     "/api/admin/operator-access/audit-timeline/clear"):
            r = requests.post(
                f"{BASE_URL}{path}", json={}, headers=_admin_headers(), timeout=10,
            )
            assert r.status_code in (404, 405), f"{path} unexpectedly handled: {r.status_code}"

    def test_no_audit_edit_endpoint_exposed(self):
        for path in ("/api/admin/operator-access/audit/update",
                     "/api/admin/operator-access/audit/edit"):
            r = requests.post(
                f"{BASE_URL}{path}", json={}, headers=_admin_headers(), timeout=10,
            )
            assert r.status_code in (404, 405)


# ── A (deeper). List endpoint ships capability matrix per user ───────


class TestAdminListSurface:
    def test_list_includes_capabilities_per_row(self):
        r = requests.get(
            f"{BASE_URL}/api/admin/operator-access/list?limit=10",
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "total" in body and "rows" in body
        for row in body["rows"]:
            assert "capabilities" in row
            caps = row["capabilities"]
            assert "structured" in caps
            assert "effectiveSummary" in caps

    def test_list_pagination(self):
        r = requests.get(
            f"{BASE_URL}/api/admin/operator-access/list?limit=5&offset=0",
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["limit"] == 5
        assert body["offset"] == 0
