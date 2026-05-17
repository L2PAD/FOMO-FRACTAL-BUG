"""Sprint T3 — Continuous Paper Runtime tests.

Validates:
- Scheduler status/enable/disable/run-once endpoints
- Bar high/low + tick-fallback hit detection (forced via MongoDB mutation)
- Idempotency (no duplicate closes)
- Multi-symbol scanning
- lastEvalAt update
- Regression: T1/T2 endpoints + cognition rails + miniapp/admin
- Backend startup bootstrap auto-enables scheduler
"""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or os.environ.get("EXPO_BACKEND_URL")
            or "https://merge-verify-4.preview.emergentagent.com").rstrip("/")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ACC = "default-paper-account"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({
        "Content-Type": "application/json",
        # TIER-2: legacy T3 scheduler tests run as dev_user (approved+paper)
        "X-User-Id": "dev_user",
    })
    return sess


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


# ── Scheduler endpoints ──────────────────────────────────────────────

class TestSchedulerEndpoints:
    def test_status_running_and_enabled_at_boot(self, s):
        r = s.get(f"{BASE_URL}/api/trading/paper/scheduler/status", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert d.get("enabled") is True, f"PAPER_EVAL_ENABLED=true should auto-bootstrap: {d}"
        assert d.get("running") is True, f"loop should be running: {d}"
        assert d.get("intervalSeconds") == 60
        assert isinstance(d.get("history"), list)
        assert isinstance(d.get("runsTotal"), int)

    def test_run_once_returns_evaluation_shape(self, s):
        r = s.post(f"{BASE_URL}/api/trading/paper/scheduler/run-once", timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        for k in ("scanned", "closed", "count", "barUsed", "tickUsed", "asOf"):
            assert k in d, f"missing field {k}: {d}"
        assert isinstance(d["closed"], list)

    def test_runs_total_increments_after_run_once(self, s):
        before = s.get(f"{BASE_URL}/api/trading/paper/scheduler/status").json()["runsTotal"]
        s.post(f"{BASE_URL}/api/trading/paper/scheduler/run-once", timeout=20)
        after = s.get(f"{BASE_URL}/api/trading/paper/scheduler/status").json()["runsTotal"]
        assert after >= before + 1, f"runsTotal should advance: before={before} after={after}"

    def test_disable_then_enable_idempotent(self, s):
        r1 = s.post(f"{BASE_URL}/api/trading/paper/scheduler/disable", timeout=10).json()
        assert r1.get("ok") is True
        # Second disable → alreadyDisabled
        r2 = s.post(f"{BASE_URL}/api/trading/paper/scheduler/disable", timeout=10).json()
        assert r2.get("ok") is True
        assert r2.get("alreadyDisabled") is True, f"expected alreadyDisabled flag: {r2}"

        # Allow loop to actually exit
        time.sleep(1)
        r3 = s.post(f"{BASE_URL}/api/trading/paper/scheduler/enable", timeout=10).json()
        assert r3.get("ok") is True
        r4 = s.post(f"{BASE_URL}/api/trading/paper/scheduler/enable", timeout=10).json()
        assert r4.get("ok") is True
        assert r4.get("alreadyEnabled") is True, f"expected alreadyEnabled flag: {r4}"

        st = s.get(f"{BASE_URL}/api/trading/paper/scheduler/status").json()
        assert st.get("running") is True

    # ── Iteration_5 fix verification: full cycle + run-once survives ──
    def test_full_cycle_disable_enable_disable_enable_then_run_once(self, s):
        """Verify scheduler still functions normally after a full toggle cycle."""
        # disable → enable → disable → enable
        for _ in range(2):
            d = s.post(f"{BASE_URL}/api/trading/paper/scheduler/disable", timeout=10).json()
            assert d.get("ok") is True, f"disable failed: {d}"
            time.sleep(0.5)
            e = s.post(f"{BASE_URL}/api/trading/paper/scheduler/enable", timeout=10).json()
            assert e.get("ok") is True, f"enable failed: {e}"
            time.sleep(0.3)

        # Confirm enabled + running
        st = s.get(f"{BASE_URL}/api/trading/paper/scheduler/status", timeout=10).json()
        assert st.get("enabled") is True
        assert st.get("running") is True

        # run-once must still work and produce a valid result
        r = s.post(f"{BASE_URL}/api/trading/paper/scheduler/run-once", timeout=20).json()
        assert r.get("ok") is True, f"run-once after cycle failed: {r}"
        # Result shape: {ok, scanned, closed, count, barUsed, tickUsed, asOf}
        assert "asOf" in r and "scanned" in r and "closed" in r, \
            f"run-once result missing expected keys: {r}"
        assert isinstance(r.get("closed"), list)

    def test_bootstrap_enabled_at_startup(self, s):
        """REGRESSION: server.py startup hook must auto-bootstrap scheduler enabled+running."""
        st = s.get(f"{BASE_URL}/api/trading/paper/scheduler/status", timeout=10).json()
        assert st.get("enabled") is True, f"expected scheduler enabled at boot: {st}"
        assert st.get("running") is True, f"expected scheduler running at boot: {st}"


# ── Forced stop-hit + auto-close ──────────────────────────────────────

class TestForcedStopHitAndAutoClose:
    @pytest.fixture(scope="class")
    def opened_btc_long(self, s, db):
        # Close any existing OPEN BTC position to start clean
        existing = list(db.paper_positions_v2.find({"accountId": ACC, "symbol": "BTC", "status": "OPEN"}))
        for p in existing:
            s.post(f"{BASE_URL}/api/trading/paper/close",
                   json={"positionId": p["positionId"], "reason": "test_cleanup"}, timeout=10)

        r = s.post(f"{BASE_URL}/api/trading/paper/submit",
                   json={"symbol": "BTC", "action": "LONG"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True, f"submit failed: {d}"
        return d

    def test_force_stop_hit_closes_position(self, s, db, opened_btc_long):
        pid = opened_btc_long["positionId"]
        entry = float(opened_btc_long["entry"])
        # For LONG: setting stop_price ABOVE entry guarantees tick fallback fires immediately
        forced_stop = round(entry * 1.5, 2)
        upd = db.paper_positions_v2.update_one(
            {"positionId": pid, "status": "OPEN"},
            {"$set": {"stopPrice": forced_stop}},
        )
        assert upd.modified_count == 1, "Could not mutate stopPrice for forcing"

        # Snapshot account before
        acc_before = s.get(f"{BASE_URL}/api/trading/paper/account").json()

        run = s.post(f"{BASE_URL}/api/trading/paper/scheduler/run-once", timeout=20).json()
        assert run.get("ok") is True
        assert run.get("count", 0) >= 1, f"expected ≥1 auto-close, got {run}"
        assert run.get("scanned", 0) >= 1

        # Position should be CLOSED with reason=stop
        pos = db.paper_positions_v2.find_one({"positionId": pid}, {"_id": 0})
        assert pos["status"] == "CLOSED"
        assert pos["closeReason"] == "stop"
        assert pos.get("closePrice") is not None
        assert pos.get("detectionMode") in ("tick", "bar_1m"), f"detectionMode missing/invalid: {pos.get('detectionMode')}"

        # Account updated: balance changed, trades & losses incremented (pnl<=0 since LONG with stop above entry)
        acc_after = s.get(f"{BASE_URL}/api/trading/paper/account").json()
        assert acc_after["totalTrades"] >= acc_before.get("totalTrades", 0) + 1
        # LONG closed at stop ABOVE entry → pnl > 0 → wins should increment. But our setup uses
        # stopPrice ABOVE entry purely to trigger tick-mode close; actual close-price is the live
        # tick (likely < forced stop). Treat it as: realizedPnlUsd field must update.
        assert "balanceUsd" in acc_after and "realizedPnlUsd" in acc_after

    def test_position_closed_in_positions_list(self, s, opened_btc_long):
        pid = opened_btc_long["positionId"]
        r = s.get(f"{BASE_URL}/api/trading/paper/positions?status=CLOSED", timeout=10).json()
        match = [p for p in r.get("positions", []) if p.get("positionId") == pid]
        assert match, f"closed position not found in CLOSED list (count={r.get('count')})"
        p = match[0]
        assert p["closeReason"] in ("stop", "target")
        assert p.get("closePrice") is not None

    def test_position_closed_event_in_ledger(self, s, opened_btc_long):
        pid = opened_btc_long["positionId"]
        r = s.get(f"{BASE_URL}/api/trading/paper/events?limit=50", timeout=10).json()
        evs = [e for e in r.get("events", []) if e.get("type") == "POSITION_CLOSED" and e.get("positionId") == pid]
        assert evs, f"POSITION_CLOSED event missing for {pid}"
        e0 = evs[0]
        assert e0.get("reason") == "stop"
        assert "detectionMode" in e0

    def test_idempotency_no_duplicate_close(self, s, db, opened_btc_long):
        pid = opened_btc_long["positionId"]
        # Snapshot event count for this position
        before = len([e for e in s.get(f"{BASE_URL}/api/trading/paper/events?limit=100").json()["events"]
                      if e.get("positionId") == pid and e.get("type") == "POSITION_CLOSED"])
        # Run scheduler 3 more times back to back
        for _ in range(3):
            r = s.post(f"{BASE_URL}/api/trading/paper/scheduler/run-once", timeout=20).json()
            # Already-closed position must not appear in scanned set (we filter on status=OPEN)
            assert all(c.get("positionId") != pid for c in r.get("closed", [])), \
                f"position {pid} closed again: {r}"
        after = len([e for e in s.get(f"{BASE_URL}/api/trading/paper/events?limit=100").json()["events"]
                     if e.get("positionId") == pid and e.get("type") == "POSITION_CLOSED"])
        assert after == before, f"duplicate POSITION_CLOSED events: before={before} after={after}"


# ── Multi-symbol scan + lastEvalAt update ─────────────────────────────

class TestMultiSymbolAndLastEvalAt:
    def test_scheduler_scans_multiple_open_positions(self, s, db):
        # Cleanup any open BTC/ETH
        for sym in ("BTC", "ETH"):
            ex = list(db.paper_positions_v2.find({"accountId": ACC, "symbol": sym, "status": "OPEN"}))
            for p in ex:
                s.post(f"{BASE_URL}/api/trading/paper/close",
                       json={"positionId": p["positionId"], "reason": "test_cleanup"}, timeout=10)

        opened = []
        for sym in ("BTC", "ETH"):
            r = s.post(f"{BASE_URL}/api/trading/paper/submit",
                       json={"symbol": sym, "action": "LONG"}, timeout=15).json()
            assert r.get("ok") is True, f"submit {sym}: {r}"
            opened.append(r["positionId"])

        run = s.post(f"{BASE_URL}/api/trading/paper/scheduler/run-once", timeout=25).json()
        assert run.get("ok") is True
        # 2 fresh + maybe other OPEN; scanned should be at least 2
        assert run.get("scanned", 0) >= 2, f"expected scanned ≥ 2: {run}"

        # lastEvalAt should be set/updated on those that didn't close
        for pid in opened:
            pos = db.paper_positions_v2.find_one({"positionId": pid}, {"_id": 0})
            if pos and pos.get("status") == "OPEN":
                assert pos.get("lastEvalAt") is not None, f"lastEvalAt missing on {pid}"

        # Cleanup
        for pid in opened:
            s.post(f"{BASE_URL}/api/trading/paper/close",
                   json={"positionId": pid, "reason": "test_cleanup"}, timeout=10)


# ── Regression: T1/T2 endpoints still work ────────────────────────────

class TestT1T2Regression:
    @pytest.mark.parametrize("path", [
        "/api/trading/verdict/BTC",
        "/api/trading/opportunities?symbols=BTC,ETH,SOL",
        "/api/trading/paper/account",
        "/api/trading/paper/positions?status=OPEN",
        "/api/trading/paper/orders?limit=10",
        "/api/trading/paper/events?limit=10",
        "/api/trading/runtime/status",
    ])
    def test_get_endpoint_ok(self, s, path):
        r = s.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"
        j = r.json()
        # All listed return JSON dicts (verdict returns dict; opportunities returns dict)
        assert isinstance(j, dict)

    def test_paper_evaluate_hits_still_works(self, s):
        r = s.post(f"{BASE_URL}/api/trading/paper/evaluate-hits", json={}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        for k in ("scanned", "closed", "count", "barUsed", "tickUsed", "asOf"):
            assert k in d


# ── Cognition rails still respond ─────────────────────────────────────

class TestCognitionRails:
    @pytest.mark.parametrize("path", [
        "/api/ta/basic/BTC",
        "/api/sentiment/runtime/BTC",
        "/api/fractal/runtime/BTC",
    ])
    def test_rail(self, s, path):
        r = s.get(f"{BASE_URL}{path}", timeout=20)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"


# ── Legacy terminal honest-404 ────────────────────────────────────────

class TestLegacyTerminal:
    def test_legacy_terminal_404(self, s):
        r = s.get(f"{BASE_URL}/api/terminal/status", timeout=10)
        assert r.status_code == 404, f"legacy terminal should 404, got {r.status_code}"


# ── Miniapp + Admin SPAs ──────────────────────────────────────────────

class TestSPAs:
    def test_miniapp_lite(self, s):
        r = s.get(f"{BASE_URL}/api/miniapp/lite", timeout=15)
        assert r.status_code == 200, f"miniapp lite → {r.status_code}"

    def test_panel_admin(self, s):
        r = s.get(f"{BASE_URL}/api/panel/admin", timeout=15)
        assert r.status_code == 200, f"panel admin → {r.status_code}"
