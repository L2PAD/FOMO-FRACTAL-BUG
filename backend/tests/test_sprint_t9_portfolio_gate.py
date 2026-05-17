"""Sprint T9 — Portfolio Exposure Control + Drawdown Circuit Breaker tests.

Validates that the gate sits AFTER adaptive sizing and BEFORE submit,
and that any one rule can block while leaving cognition/calibration
untouched.

Contract:
  * verdict has portfolioGate block (always)
  * permission ∈ {'allowed','blocked'}
  * any rule blocking → action='WAIT', sizeUsd=None, blockedBy includes rule,
    actionBeforePortfolioGate preserves what cognition wanted
  * cognition/calibration/sizing blocks are NOT mutated by the gate
  * existing closes are unaffected (we don't test paper/close here — gate
    is only on the OPEN/deployment path)
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
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
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


# ── Unit tests on apply_portfolio_gate ────────────────────────────────


def _make_verdict(action="LONG", symbol="BTC", final=500.0):
    return {
        "symbol": symbol, "action": action, "confidence": 0.7,
        "risk": "MED", "alignment": {"score": 0.5}, "reasons": [],
        "blockedBy": [],
        "entry": 100.0, "stop": 95.0, "target": 110.0, "rr": 2.0,
        "sizeUsd": final if action in ("LONG", "SHORT") else None,
        "sizing": {"final": final, "forcedZeroReason": None},
        "calibration": {"sample": 10, "winRate": 0.55, "recent30d": {"sample": 6}},
    }


def _acct(equity=10_000.0):
    return {
        "accountId": "TEST_T9_acct",
        "balanceUsd": equity,
        "equityUsd": equity,
        "startingBalanceUsd": equity,
    }


class TestGateAllowsCleanState:
    def test_empty_book_allows(self):
        from services import portfolio_gate as g
        v = g.apply_portfolio_gate(_make_verdict(), _acct(), [])
        gate = v["portfolioGate"]
        assert gate["permission"] == "allowed"
        assert gate["finalPermission"] == "allowed"
        assert gate["blockReason"] is None
        # Cognition / sizing NOT mutated
        assert v["action"] == "LONG"
        assert v["sizeUsd"] == 500.0
        assert "calibration" in v and v["calibration"]["sample"] == 10

    def test_gate_block_present_for_wait_verdict_without_blocking(self):
        """WAIT verdict already has size 0 → gate observes book but never blocks."""
        from services import portfolio_gate as g
        v = _make_verdict(action="WAIT", final=0)
        v["sizeUsd"] = None
        out = g.apply_portfolio_gate(v, _acct(), [])
        assert out["portfolioGate"]["permission"] == "allowed"
        assert out["action"] == "WAIT"


class TestExposureCaps:
    def test_max_open_positions_blocks(self):
        from services import portfolio_gate as g
        open_pos = [
            {"symbol": "ETH", "side": "LONG", "sizeUsd": 50.0}
            for _ in range(5)
        ]
        v = g.apply_portfolio_gate(_make_verdict(), _acct(), open_pos)
        assert v["portfolioGate"]["blockReason"] == "max_open_positions"
        assert v["action"] == "WAIT"
        assert v["sizeUsd"] is None
        assert "max_open_positions" in (v.get("blockedBy") or [])
        assert v.get("actionBeforePortfolioGate") == "LONG"

    def test_max_total_notional_blocks(self):
        from services import portfolio_gate as g
        # 3 positions × $10k = $30k notional; equity $10k → ratio 3.0
        # Adding $500 → 3.05 > 3.0 cap
        open_pos = [
            {"symbol": "ETH", "side": "LONG", "sizeUsd": 10_000.0},
            {"symbol": "SOL", "side": "LONG", "sizeUsd": 10_000.0},
            {"symbol": "DOGE", "side": "LONG", "sizeUsd": 10_000.0},
        ]
        v = g.apply_portfolio_gate(_make_verdict(symbol="ADA"), _acct(), open_pos)
        assert v["portfolioGate"]["blockReason"] == "max_total_notional"
        assert v["action"] == "WAIT"

    def test_max_per_symbol_blocks(self):
        from services import portfolio_gate as g
        # BTC already $15k against $10k equity → ratio 1.5
        # Adding $500 → 1.55 > 1.5 cap
        open_pos = [{"symbol": "BTC", "side": "LONG", "sizeUsd": 15_000.0}]
        v = g.apply_portfolio_gate(_make_verdict(symbol="BTC"), _acct(), open_pos)
        assert v["portfolioGate"]["blockReason"] == "max_per_symbol_exposure"

    def test_max_same_side_blocks(self):
        from services import portfolio_gate as g
        # 3 short positions on different symbols, total $25k → same-side ratio 2.5
        # Adding short → exceeds
        open_pos = [
            {"symbol": "DOGE", "side": "SHORT", "sizeUsd": 8_500.0},
            {"symbol": "ADA",  "side": "SHORT", "sizeUsd": 8_500.0},
            {"symbol": "XRP",  "side": "SHORT", "sizeUsd": 8_500.0},
        ]
        v = g.apply_portfolio_gate(
            _make_verdict(action="SHORT", symbol="LINK"), _acct(), open_pos
        )
        assert v["portfolioGate"]["blockReason"] == "max_same_side_exposure"

    def test_caps_report_progress_when_allowed(self):
        from services import portfolio_gate as g
        open_pos = [{"symbol": "ETH", "side": "LONG", "sizeUsd": 1_000.0}]
        v = g.apply_portfolio_gate(_make_verdict(), _acct(), open_pos)
        caps = v["portfolioGate"]["caps"]
        assert caps["openPositions"]["current"] == 1
        assert caps["openPositions"]["prospective"] == 2
        assert caps["totalNotional"]["currentUsd"] == 1000.0
        assert caps["sameSide"]["side"] == "LONG"


class TestCorrelationGuard:
    def test_majors_cluster_same_side_blocks(self):
        from services import portfolio_gate as g
        # 2 majors already LONG, each $9k → cluster 18k vs $10k equity → 1.8
        # Adding BTC LONG $500 → 1.85 still below cap 2.0
        # Adding BTC LONG $3000 → 2.1 > 2.0 → block
        open_pos = [
            {"symbol": "ETH", "side": "LONG", "sizeUsd": 9_000.0},
            {"symbol": "SOL", "side": "LONG", "sizeUsd": 9_000.0},
        ]
        v = _make_verdict(symbol="BTC", final=3_000.0)
        out = g.apply_portfolio_gate(v, _acct(), open_pos)
        assert out["portfolioGate"]["blockReason"] == "max_correlated_exposure"
        cor = out["portfolioGate"]["correlation"]
        assert cor["cluster"] == "majors_l1"
        assert cor["sameSideCountInCluster"] == 2
        assert "BTC" in cor["clusterMembers"]

    def test_correlation_irrelevant_for_non_cluster_symbol(self):
        from services import portfolio_gate as g
        # DOGE is NOT in any cluster — even with majors LONG, no cluster gate
        open_pos = [
            {"symbol": "BTC", "side": "LONG", "sizeUsd": 9_000.0},
            {"symbol": "ETH", "side": "LONG", "sizeUsd": 9_000.0},
        ]
        v = g.apply_portfolio_gate(_make_verdict(symbol="DOGE"), _acct(), open_pos)
        gate = v["portfolioGate"]
        # DOGE has no cluster → correlation.cluster is None
        assert gate["correlation"]["cluster"] is None

    def test_correlation_opposite_sides_dont_aggregate(self):
        from services import portfolio_gate as g
        # ETH SHORT does NOT count toward LONG cluster exposure
        open_pos = [
            {"symbol": "ETH", "side": "SHORT", "sizeUsd": 9_000.0},
            {"symbol": "SOL", "side": "SHORT", "sizeUsd": 9_000.0},
        ]
        v = g.apply_portfolio_gate(
            _make_verdict(symbol="BTC", action="LONG"), _acct(), open_pos
        )
        cor = v["portfolioGate"]["correlation"]
        assert cor["sameSideCountInCluster"] == 0  # no LONG in cluster
        assert v["portfolioGate"]["permission"] == "allowed"


class TestDrawdownBreaker:
    def test_breaker_blocks_when_daily_drawdown_exceeded(self, db):
        from services import portfolio_gate as g
        acct = _acct()
        # Seed 1 CLOSED position with -$600 PnL today → -6% of $10k baseline
        midnight = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        # Insert a fake closed loss for the test account
        pid = f"T9_DD_{uuid.uuid4().hex[:8]}"
        db.paper_positions_v2.delete_many({"accountId": acct["accountId"]})
        db.paper_positions_v2.insert_one({
            "positionId": pid, "orderId": f"ord_{pid}",
            "accountId": acct["accountId"], "symbol": "BTC", "side": "LONG",
            "entryPrice": 100, "stopPrice": 95, "targetPrice": 110,
            "sizeUsd": 5000, "status": "CLOSED",
            "openedAt": midnight, "closedAt": datetime.now(timezone.utc).isoformat(),
            "closePrice": 88, "realizedPnlUsd": -600.0, "realizedPnlPct": -12,
            "closeReason": "stop",
        })
        try:
            v = g.apply_portfolio_gate(_make_verdict(), acct, [])
            assert v["portfolioGate"]["drawdown"]["breakerActive"] is True
            assert v["portfolioGate"]["drawdown"]["drawdownPct"] <= -5.0
            assert v["portfolioGate"]["blockReason"] == "daily_drawdown_circuit_breaker"
            assert v["action"] == "WAIT"
            assert "daily_drawdown_circuit_breaker" in (v.get("blockedBy") or [])
        finally:
            db.paper_positions_v2.delete_many({"accountId": acct["accountId"]})

    def test_breaker_not_engaged_for_small_drawdown(self, db):
        from services import portfolio_gate as g
        acct = _acct()
        midnight = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        pid = f"T9_DD2_{uuid.uuid4().hex[:8]}"
        db.paper_positions_v2.delete_many({"accountId": acct["accountId"]})
        db.paper_positions_v2.insert_one({
            "positionId": pid, "orderId": f"ord_{pid}",
            "accountId": acct["accountId"], "symbol": "BTC", "side": "LONG",
            "entryPrice": 100, "stopPrice": 95, "targetPrice": 110,
            "sizeUsd": 5000, "status": "CLOSED",
            "openedAt": midnight, "closedAt": datetime.now(timezone.utc).isoformat(),
            "closePrice": 98, "realizedPnlUsd": -200.0, "realizedPnlPct": -4,
            "closeReason": "manual",
        })
        try:
            v = g.apply_portfolio_gate(_make_verdict(), acct, [])
            assert v["portfolioGate"]["drawdown"]["breakerActive"] is False
            assert v["portfolioGate"]["permission"] == "allowed"
        finally:
            db.paper_positions_v2.delete_many({"accountId": acct["accountId"]})


class TestLossStreakCooldown:
    def test_three_consecutive_losses_triggers_cooldown(self, db):
        from services import portfolio_gate as g
        acct = _acct()
        db.paper_positions_v2.delete_many({"accountId": acct["accountId"]})
        # Insert 3 LOSSES, most-recent within cooldown window
        now = datetime.now(timezone.utc)
        for i in range(3):
            ts = (now - timedelta(minutes=i * 30)).isoformat()
            db.paper_positions_v2.insert_one({
                "positionId": f"T9_LS_{uuid.uuid4().hex[:8]}",
                "orderId": f"ord_{i}",
                "accountId": acct["accountId"], "symbol": "ETH", "side": "LONG",
                "entryPrice": 100, "stopPrice": 95, "targetPrice": 110,
                "sizeUsd": 100, "status": "CLOSED",
                "openedAt": ts, "closedAt": ts,
                "closePrice": 95, "realizedPnlUsd": -5.0, "realizedPnlPct": -5.0,
                "closeReason": "stop",
            })
        try:
            v = g.apply_portfolio_gate(_make_verdict(), acct, [])
            cd = v["portfolioGate"]["cooldown"]
            assert cd["recentLossStreak"] == 3
            assert cd["cooldownActive"] is True
            assert cd["cooldownUntil"] is not None
            assert v["portfolioGate"]["blockReason"] == "loss_streak_cooldown"
            assert v["action"] == "WAIT"
        finally:
            db.paper_positions_v2.delete_many({"accountId": acct["accountId"]})

    def test_win_resets_streak(self, db):
        from services import portfolio_gate as g
        acct = _acct()
        db.paper_positions_v2.delete_many({"accountId": acct["accountId"]})
        # 2 losses then 1 win (most recent) → streak=0
        now = datetime.now(timezone.utc)
        db.paper_positions_v2.insert_one({  # oldest loss
            "positionId": f"T9_W1_{uuid.uuid4().hex[:8]}",
            "orderId": "ord_a",
            "accountId": acct["accountId"], "symbol": "ETH", "side": "LONG",
            "entryPrice": 100, "stopPrice": 95, "targetPrice": 110,
            "sizeUsd": 100, "status": "CLOSED",
            "openedAt": (now - timedelta(hours=3)).isoformat(),
            "closedAt": (now - timedelta(hours=3)).isoformat(),
            "closePrice": 95, "realizedPnlUsd": -5.0, "realizedPnlPct": -5.0,
            "closeReason": "stop",
        })
        db.paper_positions_v2.insert_one({  # newer win
            "positionId": f"T9_W2_{uuid.uuid4().hex[:8]}",
            "orderId": "ord_b",
            "accountId": acct["accountId"], "symbol": "ETH", "side": "LONG",
            "entryPrice": 100, "stopPrice": 95, "targetPrice": 110,
            "sizeUsd": 100, "status": "CLOSED",
            "openedAt": (now - timedelta(hours=1)).isoformat(),
            "closedAt": (now - timedelta(hours=1)).isoformat(),
            "closePrice": 110, "realizedPnlUsd": 10.0, "realizedPnlPct": 10.0,
            "closeReason": "target",
        })
        try:
            v = g.apply_portfolio_gate(_make_verdict(), acct, [])
            assert v["portfolioGate"]["cooldown"]["recentLossStreak"] == 0
            assert v["portfolioGate"]["cooldown"]["cooldownActive"] is False
        finally:
            db.paper_positions_v2.delete_many({"accountId": acct["accountId"]})


class TestPipelineOrdering:
    def test_gate_does_not_mutate_cognition_or_calibration(self):
        from services import portfolio_gate as g
        v = _make_verdict()
        v["calibration"]["recent30d"]["winRate"] = 0.62
        # Force a block via max_open_positions
        open_pos = [
            {"symbol": "ETH", "side": "LONG", "sizeUsd": 50.0} for _ in range(6)
        ]
        out = g.apply_portfolio_gate(v, _acct(), open_pos)
        # Cognition + calibration intact
        assert out["calibration"]["sample"] == 10
        assert out["calibration"]["winRate"] == 0.55
        assert out["calibration"]["recent30d"]["winRate"] == 0.62
        # Sizing is preserved as data, even if action flipped
        assert out["sizing"]["final"] == 500.0
        # But final deployment forbidden
        assert out["action"] == "WAIT"
        assert out["sizeUsd"] is None


# ── Integration: live /api/trading/verdict/{symbol} response shape ────


class TestVerdictExposesGate:
    def test_verdict_contains_portfolio_gate(self, s):
        r = s.get(f"{BASE_URL}/api/trading/verdict/BTC", timeout=20).json()
        assert "portfolioGate" in r, list(r.keys())
        gate = r["portfolioGate"]
        for k in (
            "permission", "blockReason", "reasons",
            "caps", "correlation", "drawdown", "cooldown",
            "thresholds", "finalPermission", "version",
        ):
            assert k in gate, f"missing {k}"
        assert gate["version"].startswith("t9.")
        assert gate["permission"] in ("allowed", "blocked")
        assert gate["finalPermission"] in ("allowed", "blocked")

    def test_caps_block_has_all_4_subblocks(self, s):
        r = s.get(f"{BASE_URL}/api/trading/verdict/BTC", timeout=20).json()
        caps = r["portfolioGate"]["caps"]
        assert set(caps.keys()) >= {"openPositions", "totalNotional", "perSymbol", "sameSide"}


# ── Regression: T1-T8 endpoints unchanged ─────────────────────────────


class TestRegression:
    @pytest.mark.parametrize("path", [
        "/api/trading/runtime/status",
        "/api/trading/verdict/BTC",
        "/api/trading/opportunities?symbols=BTC,ETH,SOL",
        "/api/trading/paper/account",
        "/api/trading/paper/positions?status=OPEN",
        "/api/trading/paper/orders?limit=10",
        "/api/trading/paper/events?limit=10",
        "/api/trading/paper/scheduler/status",
        "/api/trading/intelligence/calibration?symbol=BTC",
    ])
    def test_endpoint_ok(self, s, path):
        r = s.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"
