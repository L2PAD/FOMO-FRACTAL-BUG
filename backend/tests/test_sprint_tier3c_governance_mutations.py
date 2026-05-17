"""Phase 3C acceptance — governance mutations and their invariants.

User-stated acceptance criteria:
  1. tier change works AND does not affect admin-granted live/console
  2. trader → pro removes tier-derived paper but preserves explicit grants
  3. revoke paperTrading overrides trader tier
  4. grant live requires exact typed confirmation
  5. wrong typed confirmation fails
  6. audit row appears immediately after every mutation
  7. no optimistic state: UI changes only after refetch  (this is FE
     responsibility — exercised by the manual screenshot tests; here
     we assert that backend responses ARE authoritative and contain
     the resolved capabilities for each mutation, so FE has truth to
     render)
  8. backend regression stays green (covered by existing suites)
"""
import os
import pytest
import requests
import jwt as _jwt
from pathlib import Path
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


def _seed(uid, *, tier, oa=None):
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
    r = requests.get(f"{BASE_URL}/api/me/capabilities", headers={"X-User-Id": uid}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ── 1. tier change does not erase admin-granted live/console ─────────


class TestTierChangePreservesAdminGrants:
    USER = "tier3c_tier_change_preserves"

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_tier_downgrade_keeps_explicit_admin_grants(self):
        _wipe(self.USER)
        # trader + admin grants for live + console
        _seed(self.USER, tier="trader", oa={
            "enabled": True, "status": "approved", "mode": "live",
            "consoleAccess": True,
            "capabilityOverrides": {},
            "liveAuthority": {
                "granted": True, "grantedAt": "2026-01-01T00:00:00+00:00",
                "grantedBy": "test", "reason": "test", "expiresAt": None,
            },
        })
        before = _caps(self.USER)["capabilities"]
        assert before["liveTrading"] is True
        assert before["executionConsole"] is True

        # Downgrade via admin endpoint
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/set-tier",
            json={"userId": self.USER, "tier": "free"},
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200, r.text

        after = _caps(self.USER)["capabilities"]
        assert after["tier"] == "free"
        # Admin grants survive — billing decoupled from operational trust
        assert after["liveTrading"] is True
        assert after["executionConsole"] is True


# ── 2. trader → pro strips paper tier default, keeps grants ──────────


class TestTraderToProRemovesPaperDefault:
    USER = "tier3c_trader_to_pro"

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_paper_falls_back_to_not_granted_on_pro(self):
        _wipe(self.USER)
        # Seed without an admin grant so the only source for paperTrading
        # is the trader tier_default. After downgrade to pro (no tier
        # default for paper) it must fall to not_granted.
        _seed(self.USER, tier="trader", oa={
            "enabled": False, "status": "none", "mode": "none",
            "consoleAccess": False,
            "capabilityOverrides": {},
            "liveAuthority": {"granted": False},
        })
        before = _caps(self.USER)["capabilities"]
        assert before["paperTrading"] is True
        assert before["sources"]["paperTrading"] == "tier_default"

        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/set-tier",
            json={"userId": self.USER, "tier": "pro"},
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200, r.text
        after = _caps(self.USER)["capabilities"]
        # paper no longer tier-default for pro, no admin grant set → False
        assert after["paperTrading"] is False
        assert after["sources"]["paperTrading"] == "not_granted"


# ── 3. revoke override beats trader tier default ─────────────────────


class TestOverrideBeatsTierDefault:
    USER = "tier3c_override_beats_tier"

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_revoke_override_strips_tier_paper(self):
        _wipe(self.USER)
        _seed(self.USER, tier="trader")
        assert _caps(self.USER)["capabilities"]["paperTrading"] is True

        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/override-capability",
            json={"userId": self.USER, "capability": "paperTrading",
                  "value": "revoked", "reason": "violation handling"},
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200, r.text
        after = _caps(self.USER)["capabilities"]
        assert after["paperTrading"] is False
        assert after["structured"]["paperTrading"]["override"] == "manual"
        assert after["structured"]["paperTrading"]["source"] == "admin_revoke"


# ── 4 & 5. typed confirmation validation ─────────────────────────────


class TestTypedConfirmationFlow:
    USER = "tier3c_typed_confirm"

    def setup_method(self, _):
        _wipe(self.USER)
        _seed(self.USER, tier="pro")

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_wrong_phrase_rejected(self):
        for phrase in ["grant live trading", "GRANT LIVE", "GRANT LIVE TRADING NOW", " GRANT LIVE TRADING"]:
            r = requests.post(
                f"{BASE_URL}/api/admin/operator-access/grant-live-authority",
                json={"userId": self.USER, "typedConfirmation": phrase, "reason": "x"},
                headers=_admin_headers(), timeout=15,
            )
            # Trailing/leading whitespace is stripped, so " GRANT LIVE TRADING" actually passes
            if phrase.strip() == "GRANT LIVE TRADING":
                assert r.status_code == 200, f"{phrase!r} should pass (post-strip)"
            else:
                assert r.status_code == 400, f"{phrase!r} should be rejected"
                assert r.json()["detail"]["error"] == "TYPED_CONFIRMATION_MISMATCH"

    def test_correct_phrase_with_reason_succeeds(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/grant-live-authority",
            json={
                "userId": self.USER,
                "typedConfirmation": "GRANT LIVE TRADING",
                "reason": "Production rollout — Q2 cohort",
            },
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200, r.text
        caps = _caps(self.USER)["capabilities"]
        assert caps["liveTrading"] is True


# ── 6. audit row appears immediately after every mutation ────────────


class TestAuditAppearsImmediately:
    USER = "tier3c_audit_immediate"

    def setup_method(self, _):
        _wipe(self.USER)
        _seed(self.USER, tier="pro")

    def teardown_method(self, _):
        _wipe(self.USER)

    def _timeline(self):
        return requests.get(
            f"{BASE_URL}/api/admin/operator-access/audit-timeline",
            params={"userId": self.USER, "limit": 50},
            headers=_admin_headers(), timeout=15,
        ).json()["rows"]

    def test_every_mutation_emits_audit_row(self):
        # Empty initial
        assert len(self._timeline()) == 0

        # 1. set-tier
        r = requests.post(f"{BASE_URL}/api/admin/operator-access/set-tier",
                          json={"userId": self.USER, "tier": "trader"},
                          headers=_admin_headers(), timeout=15)
        assert r.status_code == 200
        tl = self._timeline()
        assert tl[0]["action"] == "set-tier"
        assert tl[0]["severity"] == "info"

        # 2. override-capability
        r = requests.post(f"{BASE_URL}/api/admin/operator-access/override-capability",
                          json={"userId": self.USER, "capability": "executionConsole",
                                "value": "granted", "reason": "test"},
                          headers=_admin_headers(), timeout=15)
        assert r.status_code == 200
        tl = self._timeline()
        assert tl[0]["action"] == "override-capability"
        assert tl[0]["severity"] == "elevated"
        assert tl[0]["reason"] == "test"

        # 3. grant-live-authority
        r = requests.post(f"{BASE_URL}/api/admin/operator-access/grant-live-authority",
                          json={"userId": self.USER, "typedConfirmation": "GRANT LIVE TRADING",
                                "reason": "ops ack"},
                          headers=_admin_headers(), timeout=15)
        assert r.status_code == 200
        tl = self._timeline()
        assert tl[0]["action"] == "grant-live-authority"
        assert tl[0]["severity"] == "critical"

        # 4. revoke-live-authority
        r = requests.post(f"{BASE_URL}/api/admin/operator-access/revoke-live-authority",
                          json={"userId": self.USER, "reason": "rollback"},
                          headers=_admin_headers(), timeout=15)
        assert r.status_code == 200
        tl = self._timeline()
        assert tl[0]["action"] == "revoke-live-authority"
        assert tl[0]["severity"] == "critical"

        # 5. set-console-access (toggle off)
        r = requests.post(f"{BASE_URL}/api/admin/operator-access/set-console-access",
                          json={"userId": self.USER, "consoleAccess": False},
                          headers=_admin_headers(), timeout=15)
        assert r.status_code == 200
        tl = self._timeline()
        assert tl[0]["action"] == "set-console-access"
        assert tl[0]["severity"] == "elevated"

        # Final: 5 audit rows in correct reverse-chronological order
        actions = [r["action"] for r in tl[:5]]
        assert actions == [
            "set-console-access",
            "revoke-live-authority",
            "grant-live-authority",
            "override-capability",
            "set-tier",
        ]


# ── 7. backend mutations return authoritative capabilities ──────────


class TestMutationResponseIsAuthoritative:
    USER = "tier3c_auth_response"

    def setup_method(self, _):
        _wipe(self.USER)
        _seed(self.USER, tier="pro")

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_override_response_includes_resolved_capabilities(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/override-capability",
            json={"userId": self.USER, "capability": "executionConsole",
                  "value": "granted", "reason": "test"},
            headers=_admin_headers(), timeout=15,
        )
        body = r.json()
        assert "capabilities" in body
        caps = body["capabilities"]
        assert caps["executionConsole"] is True
        assert caps["sources"]["executionConsole"] == "admin_grant"
        assert caps["structured"]["executionConsole"]["override"] == "manual"

    def test_live_grant_response_includes_capabilities(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/grant-live-authority",
            json={"userId": self.USER, "typedConfirmation": "GRANT LIVE TRADING",
                  "reason": "test"},
            headers=_admin_headers(), timeout=15,
        )
        body = r.json()
        assert body["capabilities"]["liveTrading"] is True
