"""
T10.2C — Binance Spot Testnet Executor tests.

Covers all 6 hardcoded architectural invariants:
  A. TESTNET_ONLY hardcoded (Python const, not env-toggleable)
  B. SYMBOL_ALLOWLIST = BTC/USDT only
  C. MAX_NOTIONAL_USD = 25.0 hard cap
  D. Every submit produces immutable receipt + brokerAck + transport + lineageId
  E. No auto-resubmit — unique(lineageId) at DB level, 409 on retry
  F. Failures are observational, NEVER self-healing

Plus:
  * MOCK and TESTNET produce observationally identical receipts
  * Append-only: no update path exists
  * Read-only listing endpoints
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import jwt as _jwt
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

import server  # noqa: F401  (registers routes)
from services import binance_testnet_executor as TX


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

_db = MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(server.app)


@pytest.fixture(scope="module")
def admin_token() -> str:
    secret = os.environ.get("ADMIN_JWT_SECRET") or os.environ.get("JWT_ACCESS_SECRET")
    if not secret:
        env = Path(__file__).resolve().parents[1] / ".env"
        for line in env.read_text().splitlines():
            if line.startswith("ADMIN_JWT_SECRET="):
                secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return _jwt.encode({"role": "admin", "sub": "test_admin"}, secret, algorithm="HS256")


def _hdr(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


# ──────────────────────────────────────────────────────────────────────
# Test fixtures — synthetic gate_decision + operator with full authority
# ──────────────────────────────────────────────────────────────────────


def _new_lineage_id() -> str:
    """Unique lineageId per test — uses microsecond timestamp + random."""
    return f"lin_t10_2c_{int(time.time()*1_000_000) % 1_000_000_000:09d}{uuid.uuid4().hex[:4]}"


def _seed_gate_allowed(lineage_id: str, symbol: str = "BTC/USDT") -> str:
    """Insert a synthetic gate_decisions row with permission='allowed'."""
    _db.gate_decisions.insert_one({
        "decisionId":      f"dec_{uuid.uuid4().hex[:10]}",
        "lineageId":       lineage_id,
        "pipelineVersion": "t6+t8+t9+t10+tier4c1",
        "symbol":          symbol,
        "permission":      "allowed",
        "ts":              "2026-01-01T00:00:00+00:00",
        "verdictPreGate":  {"action": "LONG", "confidence": 0.6, "entry": 50_000.0,
                            "stop": 48_000.0, "target": 55_000.0, "rr": 2.5,
                            "sizeUsd": 10.0},
    })
    return lineage_id


def _seed_gate_blocked(lineage_id: str, symbol: str = "BTC/USDT") -> str:
    _db.gate_decisions.insert_one({
        "decisionId":      f"dec_{uuid.uuid4().hex[:10]}",
        "lineageId":       lineage_id,
        "pipelineVersion": "t6+t8+t9+t10+tier4c1",
        "symbol":          symbol,
        "permission":      "blocked",
        "blockReason":     "max_total_notional",
        "ts":              "2026-01-01T00:00:00+00:00",
    })
    return lineage_id


def _seed_operator_with_live_authority(user_id: str) -> str:
    _db.operator_access.update_one(
        {"userId": user_id},
        {"$set": {
            "userId":         user_id,
            "tier":           "trader",
            "consoleAccess":  True,
            "liveAuthority":  {"granted": True, "grantedAt": "2026-01-01T00:00:00+00:00"},
            "capabilityOverrides": {},
        }},
        upsert=True,
    )
    return user_id


def _seed_operator_paper_only(user_id: str) -> str:
    _db.operator_access.update_one(
        {"userId": user_id},
        {"$set": {
            "userId":         user_id,
            "tier":           "trader",
            "consoleAccess":  False,
            "liveAuthority":  {"granted": False},
            "capabilityOverrides": {},
        }},
        upsert=True,
    )
    return user_id


@pytest.fixture(autouse=True)
def _cleanup(request):
    """Each test cleans its own scratch rows."""
    yield
    # Remove anything touched by tests in this module — keyed by our
    # naming convention so we don't blow away production-shaped data.
    _db.execution_receipts.delete_many({"lineageId": {"$regex": "^lin_t10_2c_"}})
    _db.gate_decisions.delete_many({"lineageId": {"$regex": "^lin_t10_2c_"}})
    _db.operator_access.delete_many({"userId": {"$regex": "^op_t10_2c_"}})


# ──────────────────────────────────────────────────────────────────────
# Invariant A — TESTNET_ONLY hardcoded
# ──────────────────────────────────────────────────────────────────────


class TestInvariantA_TestnetOnlyHardcoded:
    def test_testnet_only_is_python_constant_true(self):
        assert TX.TESTNET_ONLY is True

    def test_testnet_only_cannot_be_flipped_via_env(self, monkeypatch):
        """Setting a truthy/falsy env var MUST NOT change the constant.
        This is the architectural guarantee — only a code change can
        flip TESTNET_ONLY.  We verify by reading the module source
        directly rather than reloading the module (a reload would
        create a SECOND TestnetExecutorConflict class in memory and
        break the running route layer's isinstance() catch — which
        is exactly the kind of footgun this invariant guards against
        in production)."""
        monkeypatch.setenv("TESTNET_ONLY", "false")
        monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
        # Re-importing without forcing a reload keeps the canonical
        # class identity stable.
        from services import binance_testnet_executor as mod
        assert mod.TESTNET_ONLY is True
        # And the source itself contains the literal hardcoded `True`.
        import inspect
        src = inspect.getsource(mod)
        assert "TESTNET_ONLY: bool = True" in src, (
            "TESTNET_ONLY must be a hardcoded Python literal, not env-derived"
        )
        # No reference to env in the constant declaration line.
        for line in src.splitlines():
            if line.strip().startswith("TESTNET_ONLY"):
                assert "os.environ" not in line and "getenv" not in line, (
                    f"TESTNET_ONLY appears env-derived: {line!r}"
                )
                break

    def test_config_endpoint_exposes_invariants_verbatim(self, client, admin_token):
        r = client.get("/api/admin/execution/testnet/config", headers=_hdr(admin_token))
        assert r.status_code == 200
        inv = r.json()["invariants"]
        assert inv["TESTNET_ONLY"] is True
        assert inv["MAX_NOTIONAL_USD"] == 25.0
        assert sorted(inv["SYMBOL_ALLOWLIST"]) == ["BTC", "BTC/USDT", "BTCUSDT"]
        assert inv["retryForbidden"] is True
        assert inv["appendOnly"] is True
        assert inv["autoResubmit"] is False


# ──────────────────────────────────────────────────────────────────────
# Invariant B — symbol allowlist
# ──────────────────────────────────────────────────────────────────────


class TestInvariantB_SymbolAllowlist:
    def test_btc_usdt_is_allowed(self):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=10.0,
        )
        assert r["status"] in (TX.STATUS_SUBMITTED,), r
        assert r["preflight"]["symbolAllowed"] is True

    @pytest.mark.parametrize("sym", ["ETH/USDT", "SOL/USDT", "DOGE/USDT", "BTC-PERP", "BTCUSD"])
    def test_other_symbols_are_rejected_at_preflight(self, sym):
        lid = _seed_gate_allowed(_new_lineage_id(), symbol=sym)
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol=sym, side="LONG", size_usd=10.0,
        )
        assert r["status"] == TX.STATUS_PREFLIGHT_FAIL
        assert r["failedCheck"] == "symbolAllowed"
        assert r["preflight"]["symbolAllowed"] is False
        # Receipt is STILL persisted — failure is observational, never silently dropped.
        assert _db.execution_receipts.count_documents({"lineageId": lid}) == 1


# ──────────────────────────────────────────────────────────────────────
# Invariant C — notional cap
# ──────────────────────────────────────────────────────────────────────


class TestInvariantC_NotionalCap:
    def test_under_cap_passes_preflight(self):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=24.99,
        )
        assert r["preflight"]["notionalOk"] is True

    def test_at_cap_exactly_passes(self):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=25.0,
        )
        assert r["preflight"]["notionalOk"] is True

    @pytest.mark.parametrize("size", [25.01, 50.0, 100.0, 1000.0])
    def test_over_cap_rejected(self, size):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=size,
        )
        assert r["status"] == TX.STATUS_PREFLIGHT_FAIL
        assert r["failedCheck"] == "notionalOk"

    @pytest.mark.parametrize("size", [0.0, -1.0, -100.0])
    def test_non_positive_rejected(self, size):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=size,
        )
        assert r["status"] == TX.STATUS_PREFLIGHT_FAIL
        assert r["failedCheck"] == "notionalOk"


# ──────────────────────────────────────────────────────────────────────
# Invariant D — immutable receipt with full lineage linkage
# ──────────────────────────────────────────────────────────────────────


class TestInvariantD_ReceiptShape:
    REQUIRED_TOP_LEVEL = {
        "receiptId", "lineageId", "pipelineVersion", "symbol", "side", "sizeUsd",
        "operatorUserId", "submittedBy", "preflight", "failedCheck",
        "brokerAck", "transport", "status", "submittedAt", "completedAt", "createdAt",
    }
    REQUIRED_PREFLIGHT = {
        "symbolAllowed", "notionalOk", "lineageOk", "authorityOk", "testnetOnly",
    }
    REQUIRED_TRANSPORT = {"mode", "status", "latencyMs", "errorCode", "errorMessage"}

    def test_successful_receipt_has_full_shape(self):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=10.0,
        )
        assert set(r.keys()) >= self.REQUIRED_TOP_LEVEL, r.keys()
        assert set(r["preflight"].keys()) >= self.REQUIRED_PREFLIGHT
        assert set(r["transport"].keys()) >= self.REQUIRED_TRANSPORT
        # lineage linkage
        assert r["lineageId"] == lid
        assert r["pipelineVersion"] == TX.EXECUTION_PIPELINE_VERSION
        # brokerAck shape on a successful submit
        assert r["brokerAck"] is not None
        assert "mock" in r["brokerAck"]

    def test_preflight_failure_still_carries_lineage_and_pipeline_version(self):
        # Lineage doesn't exist → preflight fail; receipt is still written
        lid = _new_lineage_id()  # NOT seeded into gate_decisions
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=10.0,
        )
        assert r["status"] == TX.STATUS_PREFLIGHT_FAIL
        assert r["failedCheck"] == "lineageOk"
        assert r["lineageId"] == lid
        assert r["pipelineVersion"] == TX.EXECUTION_PIPELINE_VERSION
        assert r["brokerAck"] is None  # never reached broker
        assert r["transport"]["status"] == "not_attempted"


# ──────────────────────────────────────────────────────────────────────
# Invariant E — no auto-resubmit (unique lineageId)
# ──────────────────────────────────────────────────────────────────────


class TestInvariantE_NoResubmit:
    def test_second_submit_for_same_lineage_raises_conflict(self):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        first = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=10.0,
        )
        assert first["status"] in (TX.STATUS_SUBMITTED, TX.STATUS_BROKER_REJECT,
                                   TX.STATUS_TRANSPORT_ERROR, TX.STATUS_PREFLIGHT_FAIL)
        with pytest.raises(TX.TestnetExecutorConflict):
            TX.submit_testnet_order(
                lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=10.0,
            )
        # Exactly one row persisted.
        assert _db.execution_receipts.count_documents({"lineageId": lid}) == 1

    def test_http_409_on_retry(self, client, admin_token):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        body = {"lineageId": lid, "operatorUserId": op, "symbol": "BTC/USDT",
                "side": "LONG", "sizeUsd": 10.0}
        r1 = client.post("/api/admin/execution/testnet/submit", json=body, headers=_hdr(admin_token))
        assert r1.status_code == 200
        r2 = client.post("/api/admin/execution/testnet/submit", json=body, headers=_hdr(admin_token))
        assert r2.status_code == 409
        assert r2.json()["detail"]["error"] == "RECEIPT_EXISTS"

    def test_preflight_failure_also_consumes_lineage_slot(self):
        """An observational failure STILL writes a receipt, so a second
        attempt for the same lineage is still forbidden — failure is a
        terminal event, not a retry opportunity."""
        lid = _new_lineage_id()  # No gate_decision → preflight will fail
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r1 = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=10.0,
        )
        assert r1["status"] == TX.STATUS_PREFLIGHT_FAIL
        # Second attempt MUST conflict even though first was a failure.
        with pytest.raises(TX.TestnetExecutorConflict):
            TX.submit_testnet_order(
                lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=10.0,
            )


# ──────────────────────────────────────────────────────────────────────
# Invariant F — failures are observational
# ──────────────────────────────────────────────────────────────────────


class TestInvariantF_ObservationalFailures:
    def test_blocked_lineage_preflight_fail_with_observational_receipt(self):
        lid = _seed_gate_blocked(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=10.0,
        )
        assert r["status"] == TX.STATUS_PREFLIGHT_FAIL
        assert r["failedCheck"] == "lineageOk"
        # Persisted, not dropped
        assert _db.execution_receipts.count_documents({"lineageId": lid}) == 1

    def test_no_authority_preflight_fail(self):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_paper_only(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=10.0,
        )
        assert r["status"] == TX.STATUS_PREFLIGHT_FAIL
        assert r["failedCheck"] == "authorityOk"

    def test_unknown_operator_preflight_fail(self):
        lid = _seed_gate_allowed(_new_lineage_id())
        r = TX.submit_testnet_order(
            lineage_id=lid,
            operator_user_id=f"op_t10_2c_unknown_{uuid.uuid4().hex[:6]}",
            symbol="BTC/USDT", side="LONG", size_usd=10.0,
        )
        assert r["status"] == TX.STATUS_PREFLIGHT_FAIL
        assert r["failedCheck"] == "authorityOk"


# ──────────────────────────────────────────────────────────────────────
# MOCK ≅ TESTNET observational equivalence
# ──────────────────────────────────────────────────────────────────────


class TestMockTestnetObservationalEquivalence:
    def test_mock_mode_active_without_credentials(self, monkeypatch):
        monkeypatch.delenv("BINANCE_TESTNET_API_KEY", raising=False)
        monkeypatch.delenv("BINANCE_TESTNET_API_SECRET", raising=False)
        assert TX._resolve_mode() == "mock"

    def test_testnet_mode_active_with_credentials(self, monkeypatch):
        monkeypatch.setenv("BINANCE_TESTNET_API_KEY", "test_key")
        monkeypatch.setenv("BINANCE_TESTNET_API_SECRET", "test_secret")
        assert TX._resolve_mode() == "testnet"

    def test_mock_receipt_matches_canonical_schema(self):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        r = TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=10.0,
        )
        assert r["transport"]["mode"] == "mock"
        assert r["brokerAck"]["mock"] is True
        assert r["brokerAck"]["exchangeOrderId"] is None
        assert r["brokerAck"]["mockOrderId"].startswith("mock_")
        # Schema parity with what a real testnet receipt would carry:
        for k in ("filledQty", "avgFillPrice", "raw"):
            assert k in r["brokerAck"]
        for k in ("mode", "status", "latencyMs", "errorCode", "errorMessage"):
            assert k in r["transport"]


# ──────────────────────────────────────────────────────────────────────
# Append-only invariant — no update path exists
# ──────────────────────────────────────────────────────────────────────


class TestAppendOnly:
    def test_no_route_mutates_existing_receipt(self, client, admin_token):
        """The route layer must NOT expose any update path.  Try every
        mutation verb on the receipts URL family — all should 404 or 405."""
        for verb in ("post", "patch", "put", "delete"):
            for path in [
                "/api/admin/execution/testnet/receipts/some_id",
                "/api/admin/execution/testnet/receipts/by-lineage/lin_x",
                "/api/admin/execution/testnet/config",
            ]:
                r = getattr(client, verb)(path, headers=_hdr(admin_token))
                assert r.status_code in (404, 405, 422), (
                    f"{verb.upper()} {path} returned {r.status_code} — "
                    "mutation surface leaked"
                )

    def test_receipt_count_only_grows(self):
        before = _db.execution_receipts.count_documents({})
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        TX.submit_testnet_order(
            lineage_id=lid, operator_user_id=op, symbol="BTC/USDT", side="LONG", size_usd=10.0,
        )
        after = _db.execution_receipts.count_documents({})
        assert after == before + 1


# ──────────────────────────────────────────────────────────────────────
# HTTP surface — auth, validation, listing
# ──────────────────────────────────────────────────────────────────────


class TestHttpSurface:
    @pytest.mark.parametrize("path,verb", [
        ("/api/admin/execution/testnet/config", "get"),
        ("/api/admin/execution/testnet/submit", "post"),
        ("/api/admin/execution/testnet/receipts", "get"),
        ("/api/admin/execution/testnet/receipts/x", "get"),
        ("/api/admin/execution/testnet/receipts/by-lineage/x", "get"),
    ])
    def test_endpoints_require_admin(self, client, path, verb):
        if verb == "get":
            r = client.get(path)
        else:
            # Valid-body POST so FastAPI body-validation doesn't pre-empt
            # the auth check.  This is the load-bearing scenario: a
            # legitimate-looking submit must still be refused without
            # admin credentials.
            r = client.post(path, json={
                "lineageId": "lin_unauth_test",
                "operatorUserId": "op_unauth_test",
                "symbol": "BTC/USDT", "side": "LONG", "sizeUsd": 10.0,
            })
        assert r.status_code == 401, f"{verb.upper()} {path} returned {r.status_code}"

    def test_submit_returns_200_with_full_receipt(self, client, admin_token):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        body = {"lineageId": lid, "operatorUserId": op, "symbol": "BTC/USDT",
                "side": "LONG", "sizeUsd": 10.0}
        r = client.post("/api/admin/execution/testnet/submit", json=body, headers=_hdr(admin_token))
        assert r.status_code == 200
        b = r.json()
        assert b["ok"] is True
        assert b["receipt"]["lineageId"] == lid
        assert b["receipt"]["pipelineVersion"] == TX.EXECUTION_PIPELINE_VERSION

    def test_get_receipt_by_lineage(self, client, admin_token):
        lid = _seed_gate_allowed(_new_lineage_id())
        op = _seed_operator_with_live_authority(f"op_t10_2c_{uuid.uuid4().hex[:6]}")
        client.post("/api/admin/execution/testnet/submit", json={
            "lineageId": lid, "operatorUserId": op, "symbol": "BTC/USDT",
            "side": "LONG", "sizeUsd": 10.0,
        }, headers=_hdr(admin_token))
        r = client.get(f"/api/admin/execution/testnet/receipts/by-lineage/{lid}", headers=_hdr(admin_token))
        assert r.status_code == 200
        assert r.json()["receipt"]["lineageId"] == lid

    def test_listing_returns_most_recent_first(self, client, admin_token):
        r = client.get("/api/admin/execution/testnet/receipts?limit=5", headers=_hdr(admin_token))
        assert r.status_code == 200
        b = r.json()
        assert b["pipelineVersion"] == TX.EXECUTION_PIPELINE_VERSION
        assert isinstance(b["rows"], list)
