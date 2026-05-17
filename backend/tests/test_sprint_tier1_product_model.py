"""Sprint TIER-1 — Product Model Cleanup tests.

Invariants:
  1. Deterministic derivation with precedence
        explicit revoke > explicit grant > tier_default > not_granted
  2. LIVE_OPERATOR is not a tier (no Tier literal contains 'live' or
     'live_operator').  Tier is commercial; liveTrading is operational.
  3. tier=trader auto-grants tradingOsVisible + paperTrading
     (NEVER executionConsole, NEVER liveTrading)
  4. Capability response carries a `sources` map for debug traceability.
  5. Downgrade trader → pro removes tier defaults but does NOT erase
     explicit admin grants that happen to coincide.
  6. Admin revoke wins over tier defaults (trader + revoke → all off).
  7. Backward compat: legacy users missing/null tier resolve to 'free'.
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


def _wipe(user_id: str) -> None:
    """Erase any operator_access record so we can re-test the seed path."""
    _db().operator_access.delete_many({"userId": user_id})


def _seed(user_id: str, *, tier: str, oa: dict | None = None) -> None:
    """Write a deterministic operator_access record for the test."""
    _db().operator_access.update_one(
        {"userId": user_id},
        {"$set": {
            "userId": user_id,
            "tier": tier,
            "operatorAccess": oa or {
                "enabled": False, "status": "none", "mode": "none",
                "consoleAccess": False,
            },
        }},
        upsert=True,
    )


def _capabilities(user_id: str) -> dict:
    r = requests.get(
        f"{BASE_URL}/api/me/capabilities",
        headers={"X-User-Id": user_id},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ── Invariant 2: Tier vocabulary is closed and excludes live ─────────


class TestTierVocabulary:
    def test_tier_enum_exact_membership(self):
        """No 'live_operator' / 'live' / 'enterprise' in the tier set."""
        from routes import operator_access as oa
        # Pydantic Literal exposed at module level
        # Tier = Literal["free", "pro", "trader"]
        # We inspect _TIER_DEFAULTS keys for the canonical set.
        assert set(oa._TIER_DEFAULTS.keys()) == {"free", "pro", "trader"}

    def test_no_tier_default_grants_live_or_console(self):
        from routes import operator_access as oa
        # CRITICAL: these caps must NEVER appear in any tier's default set.
        FORBIDDEN = {"liveTrading", "shadowTrading", "executionConsole"}
        for tier, defaults in oa._TIER_DEFAULTS.items():
            leak = defaults & FORBIDDEN
            assert not leak, f"tier '{tier}' leaks operational capabilities: {leak}"


# ── Invariant 3: trader tier defaults ────────────────────────────────


class TestTraderTierDefaults:
    USER = "tier1_trader_user_a"

    def setup_method(self, _):
        _wipe(self.USER)
        _seed(self.USER, tier="trader")

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_trader_gets_paper_and_visibility(self):
        body = _capabilities(self.USER)
        caps = body["capabilities"]
        assert caps["tier"] == "trader"
        assert caps["tradingOsVisible"] is True
        assert caps["paperTrading"] is True

    def test_trader_does_not_get_live_or_console(self):
        caps = _capabilities(self.USER)["capabilities"]
        assert caps["liveTrading"] is False
        assert caps["executionConsole"] is False
        assert caps["shadowTrading"] is False

    def test_trader_inherits_pro_analytics(self):
        caps = _capabilities(self.USER)["capabilities"]
        assert caps["analyticsBasic"] is True
        assert caps["analyticsPro"] is True

    def test_trader_paper_source_is_tier_default(self):
        caps = _capabilities(self.USER)["capabilities"]
        src = caps["sources"]
        assert src["paperTrading"] == "tier_default"
        assert src["tradingOsVisible"] == "tier_default"
        assert src["liveTrading"] == "not_granted"
        assert src["executionConsole"] == "not_granted"


# ── Invariant 1: precedence — explicit admin grant beats tier default ─


class TestExplicitAdminGrantSourceTagging:
    USER = "tier1_trader_with_live_grant"

    def setup_method(self, _):
        _wipe(self.USER)
        # trader tier (would default to paper) PLUS explicit liveAuthority
        # grant. After TIER-3 invariant E (mode != authority), live trading
        # requires liveAuthority.granted=True regardless of broker mode.
        _seed(self.USER, tier="trader", oa={
            "enabled": True, "status": "approved", "mode": "live",
            "consoleAccess": False,
            "liveAuthority": {
                "granted": True,
                "grantedAt": "2026-01-01T00:00:00+00:00",
                "grantedBy": "test_admin",
                "reason": "test fixture",
                "expiresAt": None,
            },
        })

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_live_is_admin_granted(self):
        caps = _capabilities(self.USER)["capabilities"]
        assert caps["liveTrading"] is True
        assert caps["sources"]["liveTrading"] == "admin_grant"

    def test_paper_falls_back_to_tier_default(self):
        # mode=live means admin did NOT grant paper. But trader tier
        # default DOES grant paper. So result is still True with
        # source=tier_default.
        caps = _capabilities(self.USER)["capabilities"]
        assert caps["paperTrading"] is True
        assert caps["sources"]["paperTrading"] == "tier_default"

    def test_console_still_off_without_explicit_flag(self):
        caps = _capabilities(self.USER)["capabilities"]
        assert caps["executionConsole"] is False
        assert caps["sources"]["executionConsole"] == "not_granted"


# ── Invariant 6: admin revoke wins over tier default ─────────────────


class TestAdminRevokeWinsOverTierDefault:
    USER = "tier1_trader_revoked"

    def setup_method(self, _):
        _wipe(self.USER)
        _seed(self.USER, tier="trader", oa={
            "enabled": False, "status": "revoked", "mode": "none",
            "consoleAccess": False,
        })

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_revoke_zeroes_everything(self):
        caps = _capabilities(self.USER)["capabilities"]
        for k in ("tradingOsVisible", "paperTrading", "shadowTrading",
                  "liveTrading", "executionConsole"):
            assert caps[k] is False, f"{k} should be revoked, got {caps[k]}"
            assert caps["sources"][k] == "admin_revoke", \
                f"{k} source should be admin_revoke, got {caps['sources'][k]}"

    def test_revoked_trader_keeps_pro_analytics(self):
        # Analytics is tier-derived; trader still gets pro analytics
        # since 'analyticsPro' is not an operator capability — it's
        # product positioning. Revoke does NOT downgrade billing.
        caps = _capabilities(self.USER)["capabilities"]
        assert caps["analyticsPro"] is True


# ── Invariant 5: downgrade trader → pro ──────────────────────────────


class TestTierDowngradeBehaviour:
    USER = "tier1_downgrade_user"

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_downgrade_removes_paper_default(self):
        # Start as trader → has paper via tier_default
        _wipe(self.USER)
        _seed(self.USER, tier="trader")
        before = _capabilities(self.USER)["capabilities"]
        assert before["paperTrading"] is True
        assert before["sources"]["paperTrading"] == "tier_default"

        # Downgrade to pro (no operator_access changes)
        _db().operator_access.update_one(
            {"userId": self.USER}, {"$set": {"tier": "pro"}}
        )

        after = _capabilities(self.USER)["capabilities"]
        assert after["tier"] == "pro"
        assert after["paperTrading"] is False
        assert after["sources"]["paperTrading"] == "not_granted"

    def test_downgrade_preserves_explicit_admin_grant(self):
        """If admin previously granted live authority explicitly, a tier
        downgrade must NOT silently delete that operational grant.

        This protects the architectural separation: tier downgrades are
        billing operations, not operational revocations."""
        _wipe(self.USER)
        _seed(self.USER, tier="trader", oa={
            "enabled": True, "status": "approved", "mode": "live",
            "consoleAccess": True,
            "liveAuthority": {
                "granted": True,
                "grantedAt": "2026-01-01T00:00:00+00:00",
                "grantedBy": "test_admin",
                "reason": "test fixture",
                "expiresAt": None,
            },
        })
        before = _capabilities(self.USER)["capabilities"]
        assert before["liveTrading"] is True
        assert before["executionConsole"] is True

        # Tier downgrade — billing-driven, not operator-driven
        _db().operator_access.update_one(
            {"userId": self.USER}, {"$set": {"tier": "free"}}
        )

        after = _capabilities(self.USER)["capabilities"]
        assert after["tier"] == "free"
        # Operational grants survive
        assert after["liveTrading"] is True
        assert after["sources"]["liveTrading"] == "admin_grant"
        assert after["executionConsole"] is True
        assert after["sources"]["executionConsole"] == "admin_grant"
        # Paper falls back: no tier default + no explicit paper grant
        # (mode=live, not paper)
        assert after["paperTrading"] is False


# ── Invariant 7: backward compat ─────────────────────────────────────


class TestBackwardCompat:
    USER = "tier1_legacy_user_no_tier"

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_missing_tier_resolves_to_free(self):
        _wipe(self.USER)
        # Legacy doc: no tier field at all
        _db().operator_access.update_one(
            {"userId": self.USER},
            {"$set": {
                "userId": self.USER,
                "operatorAccess": {"enabled": False, "status": "none", "mode": "none"},
            }},
            upsert=True,
        )
        body = _capabilities(self.USER)
        assert body["capabilities"]["tier"] == "free"
        # Free → no tier defaults
        caps = body["capabilities"]
        for k in ("paperTrading", "liveTrading", "executionConsole",
                  "shadowTrading", "tradingOsVisible"):
            assert caps[k] is False

    def test_null_tier_resolves_to_free(self):
        _wipe(self.USER)
        _db().operator_access.update_one(
            {"userId": self.USER},
            {"$set": {
                "userId": self.USER,
                "tier": None,
                "operatorAccess": {"enabled": False, "status": "none", "mode": "none"},
            }},
            upsert=True,
        )
        body = _capabilities(self.USER)
        assert body["capabilities"]["tier"] == "free"

    def test_garbage_tier_falls_back_to_free(self):
        _wipe(self.USER)
        _db().operator_access.update_one(
            {"userId": self.USER},
            {"$set": {
                "userId": self.USER,
                "tier": "enterprise_legacy_typo",
                "operatorAccess": {"enabled": False, "status": "none", "mode": "none"},
            }},
            upsert=True,
        )
        body = _capabilities(self.USER)
        assert body["capabilities"]["tier"] == "free"


# ── Invariant 4: capability response shape contract ──────────────────


class TestCapabilityShapeContract:
    def test_response_has_sources_block(self):
        body = _capabilities("dev_user")
        caps = body["capabilities"]
        assert "sources" in caps
        # Every capability must have a source
        for k in ("tradingOsVisible", "executionConsole", "paperTrading",
                  "shadowTrading", "liveTrading"):
            assert k in caps["sources"], f"missing source for {k}"
            assert caps["sources"][k] in (
                "tier_default", "admin_grant", "admin_revoke", "not_granted"
            ), f"unknown source value for {k}: {caps['sources'][k]}"


# ── End-to-end: trader actually unlocks paper endpoints ──────────────


class TestTraderTierEndToEnd:
    """Trader principal sent via X-User-Id should NOT be blocked from
    paper-trading endpoints by TIER-2 backend enforcement."""

    USER = "tier1_e2e_trader_user"

    def setup_method(self, _):
        _wipe(self.USER)
        _seed(self.USER, tier="trader")

    def teardown_method(self, _):
        _wipe(self.USER)

    def test_paper_account_200(self):
        r = requests.get(
            f"{BASE_URL}/api/trading/paper/account",
            headers={"X-User-Id": self.USER},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:200]

    def test_live_submit_403_with_live_required(self):
        r = requests.post(
            f"{BASE_URL}/api/broker/live/submit",
            json={"symbol": "BTC", "action": "LONG", "sizeUsd": 500},
            headers={"X-User-Id": self.USER, "Content-Type": "application/json"},
            timeout=15,
        )
        assert r.status_code == 403, r.text[:200]
        detail = (r.json().get("detail") or r.json())
        assert "liveTrading" in detail.get("required", [])

    def test_scheduler_status_403(self):
        """Trader must NOT have executionConsole — scheduler endpoint
        is operator surface, not customer surface."""
        r = requests.get(
            f"{BASE_URL}/api/trading/paper/scheduler/status",
            headers={"X-User-Id": self.USER},
            timeout=15,
        )
        assert r.status_code == 403, r.text[:200]
        detail = (r.json().get("detail") or r.json())
        assert "executionConsole" in detail.get("required", [])
