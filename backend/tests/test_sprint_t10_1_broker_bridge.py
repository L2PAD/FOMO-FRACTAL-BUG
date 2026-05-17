"""Sprint T10.1 — Broker Readiness Bridge tests.

Validates the safe-mode pre-live execution layer.

Acceptance:
  * No real orders are possible by default (BROKER_LIVE_MODE absent → refused)
  * broker config missing → honest degraded status (configured=False, connected=False)
  * preflight validates symbol/min size/side/notional purely (no broker call)
  * live submit refused with EXACT gate reasons in the response
  * audit row written to broker_audit_v1 for every submit attempt
  * even when (hypothetically) all gates pass, T10.1 safe-mode trip still refuses
"""
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or os.environ.get("EXPO_BACKEND_URL")
            or "https://merge-verify-4.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json", "X-User-Id": "dev_user"})
    return sess


@pytest.fixture(scope="module")
def s_live():
    """live_test_operator (mode=live, seeded by conftest) — required for
    /api/broker/live/submit which is guarded by liveTrading capability.
    Exchange is still in safe mode, so all submits are honest-refused
    with full gate transparency. We test the *audit* + *gate transparency*
    contract, not real execution."""
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json", "X-User-Id": "live_test_operator"})
    return sess


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


# ── Status / read-only ───────────────────────────────────────────────


class TestBrokerStatus:
    def test_status_default_safe_mode(self, s):
        r = s.get(f"{BASE_URL}/api/broker/status", timeout=15).json()
        assert r["ok"] is True
        assert r["adapter"] == "noop"
        assert r["configured"] is False
        assert r["connected"] is False
        assert r["liveSubmitEnabled"] is False
        assert r["version"].startswith(("t10_1.", "t10_2b."))
        assert r["mode"] in ("off", "shadow", "live")
        # config block is honest about credentials
        for k in ("liveMode", "provider", "apiKeySet", "apiSecretSet", "riskAckSigned"):
            assert k in r["config"]

    def test_balances_honest_when_unconfigured(self, s):
        r = s.get(f"{BASE_URL}/api/broker/balances", timeout=15).json()
        assert r["ok"] is True
        assert r["connected"] is False
        assert r["balances"] == []
        assert "noop" in r["note"].lower() or "no broker" in r["note"].lower()

    def test_markets_returns_curated_list(self, s):
        r = s.get(f"{BASE_URL}/api/broker/markets", timeout=15).json()
        assert r["ok"] is True
        assert r["count"] >= 3
        symbols = {m["symbol"] for m in r["markets"]}
        assert symbols >= {"BTC", "ETH", "SOL"}
        for m in r["markets"]:
            for k in ("pair", "minNotionalUsd", "minQty", "tickSize", "tradable"):
                assert k in m
            # T10.1: nothing is tradable
            assert m["tradable"] is False


# ── Preflight ────────────────────────────────────────────────────────


class TestPreflight:
    def test_preflight_valid_passes(self, s):
        r = s.post(
            f"{BASE_URL}/api/broker/preflight",
            json={"symbol": "BTC", "action": "LONG", "sizeUsd": 100.0},
            timeout=15,
        ).json()
        assert r["ok"] is True
        assert r["marketSupported"] is True
        assert r["sideOk"] is True
        assert r["sizeOk"] is True
        assert r["minNotionalOk"] is True
        assert r["refusedReasons"] == []

    def test_preflight_rejects_unknown_symbol(self, s):
        r = s.post(
            f"{BASE_URL}/api/broker/preflight",
            json={"symbol": "FAKE", "action": "LONG", "sizeUsd": 100},
            timeout=15,
        ).json()
        assert r["ok"] is False
        assert r["marketSupported"] is False
        assert any("market_supported" in x for x in r["refusedReasons"])

    def test_preflight_rejects_below_min_notional(self, s):
        r = s.post(
            f"{BASE_URL}/api/broker/preflight",
            json={"symbol": "BTC", "action": "LONG", "sizeUsd": 1.0},
            timeout=15,
        ).json()
        assert r["ok"] is False
        assert r["minNotionalOk"] is False
        assert any("min_notional" in x for x in r["refusedReasons"])

    def test_preflight_rejects_invalid_side(self, s):
        r = s.post(
            f"{BASE_URL}/api/broker/preflight",
            json={"symbol": "BTC", "action": "BUY", "sizeUsd": 100},
            timeout=15,
        ).json()
        assert r["ok"] is False
        assert any("side_valid" in x for x in r["refusedReasons"])

    def test_preflight_rejects_zero_size(self, s):
        r = s.post(
            f"{BASE_URL}/api/broker/preflight",
            json={"symbol": "BTC", "action": "LONG", "sizeUsd": 0},
            timeout=15,
        ).json()
        assert r["ok"] is False
        assert any("size_positive" in x for x in r["refusedReasons"])

    def test_preflight_missing_symbol_400(self, s):
        r = s.post(f"{BASE_URL}/api/broker/preflight", json={}, timeout=15)
        assert r.status_code == 400


# ── Live submit (T10.1 invariant: ALWAYS refused) ────────────────────


class TestLiveSubmitRefused:
    def test_submit_refused_in_safe_mode(self, s_live):
        r = s_live.post(
            f"{BASE_URL}/api/broker/live/submit",
            json={"symbol": "BTC", "action": "LONG", "sizeUsd": 500},
            timeout=20,
        ).json()
        assert r["ok"] is False
        assert r["finalStatus"] in ("refused", "refused_t10_1_safe_mode")
        # No broker order id ever in T10.1
        # (key may be absent — accept both)
        assert r.get("brokerOrderId") is None
        # Audit id written
        assert isinstance(r.get("auditId"), str) and r["auditId"].startswith("baud_")

    def test_refused_reasons_mention_disabled_live_mode(self, s_live):
        r = s_live.post(
            f"{BASE_URL}/api/broker/live/submit",
            json={"symbol": "BTC", "action": "LONG", "sizeUsd": 500},
            timeout=20,
        ).json()
        joined = " ".join(r["refusedReasons"])
        # At least one of these is always present in default safe mode
        assert any(x in joined for x in (
            "live_mode_enabled",
            "broker_configured",
            "broker_connected",
            "user_risk_ack_signed",
        )), f"reasons must reference disabled live mode: {joined}"

    def test_gate_checks_list_complete(self, s_live):
        r = s_live.post(
            f"{BASE_URL}/api/broker/live/submit",
            json={"symbol": "BTC", "action": "LONG", "sizeUsd": 500},
            timeout=20,
        ).json()
        check_names = {c["name"] for c in r["gateChecks"]}
        required = {
            "live_mode_enabled", "broker_configured", "broker_connected",
            "user_risk_ack_signed", "paper_scheduler_healthy",
            "verdict_directional", "portfolio_gate_allowed",
            "drawdown_breaker_off", "calibration_sample_sufficient",
            "sizing_final_positive", "preflight_passed",
        }
        assert required.issubset(check_names), \
            f"missing gate checks: {required - check_names}"

    def test_snapshots_present_in_response(self, s_live):
        r = s_live.post(
            f"{BASE_URL}/api/broker/live/submit",
            json={"symbol": "BTC", "action": "LONG", "sizeUsd": 500},
            timeout=20,
        ).json()
        for k in ("verdictSnapshot", "sizingSnapshot", "gateSnapshot", "preflight"):
            assert k in r, f"missing snapshot {k}"

    def test_submit_unknown_symbol_still_refuses(self, s_live):
        r = s_live.post(
            f"{BASE_URL}/api/broker/live/submit",
            json={"symbol": "FAKE", "action": "LONG", "sizeUsd": 500},
            timeout=20,
        ).json()
        assert r["ok"] is False
        # preflight must have failed
        assert any("preflight_passed" in x or "market_supported" in x
                   for x in r["refusedReasons"])

    def test_submit_missing_symbol_400(self, s_live):
        r = s_live.post(f"{BASE_URL}/api/broker/live/submit", json={}, timeout=15)
        assert r.status_code == 400


# ── Audit ────────────────────────────────────────────────────────────


class TestAudit:
    def test_audit_row_written_per_attempt(self, s_live, db):
        # Snapshot pre-count
        before = db.broker_audit_v1.count_documents({})
        r = s_live.post(
            f"{BASE_URL}/api/broker/live/submit",
            json={"symbol": "BTC", "action": "LONG", "sizeUsd": 500},
            timeout=20,
        ).json()
        audit_id = r["auditId"]
        after = db.broker_audit_v1.count_documents({})
        assert after >= before + 1
        # Confirm shape
        row = db.broker_audit_v1.find_one({"auditId": audit_id}, {"_id": 0})
        assert row is not None
        assert row["finalStatus"] in ("refused", "refused_t10_1_safe_mode")
        assert row["symbol"] == "BTC"
        for k in ("verdictSnapshot", "sizingSnapshot", "gateSnapshot",
                  "preflight", "gateChecks", "refusedReasons", "attemptAt"):
            assert k in row

    def test_audit_endpoint_lists_attempts(self, s_live):
        r = s_live.get(f"{BASE_URL}/api/broker/audit?limit=10", timeout=15).json()
        assert r["ok"] is True
        assert "audit" in r
        assert isinstance(r["audit"], list)
        # Most recent first
        if len(r["audit"]) >= 2:
            t0 = r["audit"][0]["attemptAt"]
            t1 = r["audit"][1]["attemptAt"]
            assert t0 >= t1


# ── Regression: T4/T6/T8/T9 endpoints + trading endpoints still healthy ─


class TestRegression:
    @pytest.mark.parametrize("path", [
        "/api/trading/runtime/status",
        "/api/trading/verdict/BTC",
        "/api/trading/opportunities?symbols=BTC,ETH,SOL",
        "/api/trading/paper/account",
        "/api/trading/paper/positions?status=OPEN",
        "/api/trading/paper/scheduler/status",
        "/api/trading/intelligence/calibration?symbol=BTC",
        "/api/broker/status",
        "/api/broker/markets",
        "/api/broker/balances",
    ])
    def test_endpoint_ok(self, s, path):
        r = s.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"
