"""
Sprint T1 — Native Trading Runtime tests.
Replaces retired Trading Terminal side-car. Validates verdict fusion,
paper-trading flow, and honest-404 on legacy /api/terminal/* paths.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or \
           os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"

API = f"{BASE_URL}/api"
TIMEOUT = 30


@pytest.fixture(scope="module")
def s():
    # TIER-2: dev_user is seeded approved+paper by conftest, which is
    # exactly the principal these legacy T1 trading/paper assertions
    # were written for.
    sess = requests.Session()
    sess.headers.update({"X-User-Id": "dev_user"})
    return sess


# ── Runtime status ───────────────────────────────────────────────────
class TestRuntimeStatus:
    def test_status(self, s):
        r = s.get(f"{API}/trading/runtime/status", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["source"] == "trading_runtime_v1"
        assert d["mode"] == "paper"
        assert d["sidecar"] is None
        assert "account" in d and d["account"]["accountId"] == "default-paper-account"
        # Balance should be >= 0 (may have been altered by prior tests). Initial value config 10000.
        assert d["config"]["startingBalanceUsd"] == 10000.0


# ── Verdict ──────────────────────────────────────────────────────────
class TestVerdict:
    @pytest.mark.parametrize("sym", ["BTC", "ETH", "SOL"])
    def test_verdict_structure(self, s, sym):
        r = s.get(f"{API}/trading/verdict/{sym}", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["symbol"] == sym
        assert d["action"] in ("WAIT", "LONG", "SHORT")
        for k in ("confidence", "alignment", "reasons", "blockedBy",
                  "moduleConfidence", "currentPrice", "asOf"):
            assert k in d, f"missing {k}"
        al = d["alignment"]
        for k in ("ta", "sentiment", "fractal", "longVotes",
                  "shortVotes", "waitVotes", "score"):
            assert k in al, f"alignment missing {k}"
        mc = d["moduleConfidence"]
        for k in ("ta", "sentiment", "fractal"):
            assert k in mc
        if d["action"] == "WAIT":
            # entry/stop/target may be null when WAIT
            pass
        else:
            assert d["entry"] and d["stop"] and d["target"]

    def test_verdict_integrates_cognition(self, s):
        # Verify underlying cognition endpoints respond, then trading verdict reads them
        for path in ("/ta/basic/BTC", "/sentiment/runtime/BTC", "/fractal/runtime/BTC"):
            rr = s.get(f"{API}{path}", timeout=TIMEOUT)
            assert rr.status_code == 200, f"{path} -> {rr.status_code}"
        v = s.get(f"{API}/trading/verdict/BTC", timeout=TIMEOUT).json()
        assert v["currentPrice"] is None or v["currentPrice"] > 0


# ── Opportunities ────────────────────────────────────────────────────
class TestOpportunities:
    def test_scan(self, s):
        r = s.get(f"{API}/trading/opportunities?symbols=BTC,ETH,SOL", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert set(d["counts"].keys()) == {"WAIT", "LONG", "SHORT"}
        total = sum(d["counts"].values())
        assert total == 3
        assert set(d["opportunities"].keys()) == {"WAIT", "LONG", "SHORT"}


# ── Paper account ────────────────────────────────────────────────────
class TestPaperAccount:
    def test_account(self, s):
        r = s.get(f"{API}/trading/paper/account", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["accountId"] == "default-paper-account"
        assert "balanceUsd" in d
        assert "equityUsd" in d


# ── Paper submit / positions / close ─────────────────────────────────
class TestPaperFlow:
    """End-to-end paper trade flow. Uses unique account to avoid collisions."""

    ACCOUNT = "TEST_t1_paper_acct"
    SYMBOL = "BTC"
    position_id = None
    order_id = None

    def _cleanup(self, s):
        # Close any open BTC position on the test account
        try:
            poss = s.get(
                f"{API}/trading/paper/positions",
                params={"accountId": self.ACCOUNT, "status": "OPEN"},
                timeout=TIMEOUT,
            ).json().get("positions", [])
            for p in poss:
                s.post(
                    f"{API}/trading/paper/close",
                    json={"positionId": p["positionId"],
                          "accountId": self.ACCOUNT,
                          "reason": "cleanup"},
                    timeout=TIMEOUT,
                )
        except Exception:
            pass

    def test_01_submit_override_long(self, s):
        self._cleanup(s)
        payload = {
            "symbol": self.SYMBOL,
            "action": "LONG",
            "sizeUsd": 1500,
            "accountId": self.ACCOUNT,
        }
        r = s.post(f"{API}/trading/paper/submit", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True, d
        assert d["side"] == "LONG"
        assert d["sizeUsd"] == 1500
        assert d["entry"] and d["stop"] and d["target"], "levels must be derived"
        # Stop < entry < target for LONG
        assert d["stop"] < d["entry"] < d["target"]
        TestPaperFlow.position_id = d["positionId"]
        TestPaperFlow.order_id = d["orderId"]

    def test_02_duplicate_position_blocked(self, s):
        payload = {
            "symbol": self.SYMBOL,
            "action": "LONG",
            "sizeUsd": 1500,
            "accountId": self.ACCOUNT,
        }
        r = s.post(f"{API}/trading/paper/submit", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is False
        assert d.get("error") == "position_already_open"

    def test_03_open_positions_listed(self, s):
        r = s.get(
            f"{API}/trading/paper/positions",
            params={"accountId": self.ACCOUNT, "status": "OPEN"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True and d["count"] >= 1
        p = next((x for x in d["positions"]
                  if x["positionId"] == TestPaperFlow.position_id), None)
        assert p is not None
        assert "unrealizedPnlUsd" in p
        assert "unrealizedPnlPct" in p
        assert "currentPrice" in p

    def test_04_orders_listed(self, s):
        r = s.get(
            f"{API}/trading/paper/orders",
            params={"accountId": self.ACCOUNT},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        order = next((o for o in d["orders"]
                      if o["orderId"] == TestPaperFlow.order_id), None)
        assert order is not None
        assert "verdict" in order, "order must include verdict snapshot"

    def test_05_evaluate_hits_noop(self, s):
        r = s.post(
            f"{API}/trading/paper/evaluate-hits",
            json={"accountId": self.ACCOUNT},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert isinstance(d.get("closed"), list)

    def test_06_close_position(self, s):
        r = s.post(
            f"{API}/trading/paper/close",
            json={"positionId": TestPaperFlow.position_id,
                  "accountId": self.ACCOUNT},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert "pnlUsd" in d and "pnlPct" in d
        assert d.get("reason") == "manual"

    def test_07_account_updated_after_close(self, s):
        r = s.get(
            f"{API}/trading/paper/account",
            params={"accountId": self.ACCOUNT},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        d = r.json()
        assert d.get("totalTrades", 0) >= 1
        assert (d.get("wins", 0) + d.get("losses", 0)) >= 1

    def test_08_closed_position_listed(self, s):
        r = s.get(
            f"{API}/trading/paper/positions",
            params={"accountId": self.ACCOUNT, "status": "CLOSED"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        d = r.json()
        p = next((x for x in d["positions"]
                  if x["positionId"] == TestPaperFlow.position_id), None)
        assert p is not None
        assert p["closePrice"] is not None
        assert p["closeReason"] == "manual"

    def test_09_events_ledger(self, s):
        r = s.get(f"{API}/trading/paper/events", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        types = {e.get("type") for e in d.get("events", [])}
        assert "ORDER_FILLED" in types
        assert "POSITION_CLOSED" in types


# ── Legacy terminal honest-404 ──────────────────────────────────────
class TestLegacyTerminal404:
    @pytest.mark.parametrize("p", [
        "/terminal/health",
        "/terminal/status",
        "/terminal-app/health",
        "/terminal-app/something",
    ])
    def test_legacy_404(self, s, p):
        r = s.get(f"{API}{p}", timeout=TIMEOUT)
        # Honest 404 expected (not 200, not 502).
        assert r.status_code == 404, f"{p} -> {r.status_code} ({r.text[:100]})"


# ── Cognition endpoints still alive ─────────────────────────────────
class TestCognitionSurfaces:
    @pytest.mark.parametrize("p", [
        "/ta/basic/BTC",
        "/sentiment/runtime/BTC",
        "/fractal/runtime/BTC",
        "/miniapp/lite",
        "/panel/admin",
    ])
    def test_alive(self, s, p):
        r = s.get(f"{API}{p}", timeout=TIMEOUT)
        assert r.status_code == 200, f"{p} -> {r.status_code}"


# ── Expo web bundle (T2 frontend wiring regression) ─────────────────
class TestExpoWebBundle:
    def test_root_serves(self, s):
        r = s.get(f"{BASE_URL}/", timeout=TIMEOUT)
        assert r.status_code == 200, f"GET / -> {r.status_code}"
        # Expo web shell should reference a bundle or root div
        body = r.text.lower()
        assert ("expo" in body) or ("root" in body) or ("<script" in body), \
            "Expo web shell did not render expected markers"
