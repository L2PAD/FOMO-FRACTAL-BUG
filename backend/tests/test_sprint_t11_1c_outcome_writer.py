"""
T11.1c — Paper Outcome Writer (forward-only spine completion).

Acceptance criteria (from user spec):

  * new submit → order has lineage
  * new submit → ORDER_FILLED has lineage
  * new submit → POSITION_OPENED event exists
  * close → paper_outcomes row exists
  * close twice → no duplicate outcome
  * attribution summary layer counts start increasing for new closed trades
  * pre-T11.1c positions do not break summary
  * no retroactive fabrication

These tests are unit-level (no HTTP); they hit the trading_runtime
service directly and verify Mongo state after each action.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta

import pytest
from pymongo import MongoClient

from services import trading_runtime as TR
from routes import attribution as ATTR


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

_db = MongoClient(MONGO_URL)[DB_NAME]
_orders = _db["paper_orders_v2"]
_positions = _db["paper_positions_v2"]
_events = _db["paper_events_v2"]
_outcomes = _db["paper_outcomes"]


# ──────────────────────────────────────────────────────────────────────
# Synthetic helpers — bypass live market price fetching so tests are
# deterministic regardless of external feed availability.
# ──────────────────────────────────────────────────────────────────────


def _fake_verdict(symbol: str = "BTC", action: str = "LONG") -> dict:
    """Build a verdict-like dict ready for submit_paper_order."""
    return {
        "symbol": symbol,
        "action": action,
        "entry": 100.0,
        "stop": 95.0,
        "target": 115.0,
        "rr": 3.0,
        "risk": "N/A",
        "sizeUsd": 200.0,
        "confidence": 0.5,
        "alignment": {"score": 0.5, "ta": action, "sentiment": action, "fractal": action},
        "currentPrice": 100.0,
        "support": 90.0,
        "resistance": 120.0,
        "moduleConfidence": {"ta": 0.5, "sentiment": 0.5, "fractal": 0.5},
        "asOf": datetime.now(timezone.utc).isoformat(),
        "source": "trading_runtime_test",
        "reasons": ["test"],
        "blockedBy": [],
        # T11.1b spine fields — required by the writer.
        "lineageId": f"lin_test{int(datetime.now().timestamp()*1000)%10_000_000:07d}",
        "pipelineVersion": ATTR.ATTRIBUTION_PIPELINE_VERSION,
        "rawVerdictSnapshot": {
            "lineageId": "placeholder",  # build_verdict normally fills this
            "action": action,
            "confidence": 0.5,
            "entry": 100.0,
            "stop": 95.0,
            "target": 115.0,
            "rr": 3.0,
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "modelVersion": "trading_runtime_test",
            "marketContext": {
                "currentPrice": 100.0,
                "support": 90.0,
                "resistance": 120.0,
            },
            "reasons": ["test"],
            "blockedBy": [],
            "rawRisk": "N/A",
            "rawSizeUsd": 200.0,
        },
    }


@pytest.fixture(autouse=True)
def _isolate_test_account(monkeypatch):
    """Each test runs against a unique throwaway accountId so we don't
    pollute the dev DB.  We also stub _fetch_ta / _current_price and
    build_verdict so submit_paper_order is deterministic without an
    external price feed."""
    account = f"t11_1c_test_acct_{datetime.now().timestamp():.0f}"
    monkeypatch.setattr(TR, "DEFAULT_ACCOUNT_ID", account)
    # Stub price machinery so close path doesn't need a feed.
    monkeypatch.setattr(TR, "_current_price", lambda sym, ta: 105.0)
    monkeypatch.setattr(TR, "_fetch_ta", lambda sym: {"price": 105.0})
    # Stub build_verdict — submit_paper_order calls it internally.  We
    # return a verdict shape that already has the T11.1b spine fields,
    # but we still let trading_runtime decorate it.  IMPORTANT: the
    # returned verdict will be MUTATED in place by the pipeline (its
    # rawVerdictSnapshot becomes the real one) — that's expected.
    def _stub_build_verdict(symbol: str):
        return _fake_verdict(symbol=symbol)
    monkeypatch.setattr(TR, "build_verdict", _stub_build_verdict)
    # Bypass portfolio-gate / sizing forced-zero so the order can fill.
    yield account
    # Cleanup: remove anything we created in this test.
    _orders.delete_many({"accountId": account})
    _positions.delete_many({"accountId": account})
    _outcomes.delete_many({"accountId": account})


# ──────────────────────────────────────────────────────────────────────
# Submit-path tests (T11.1c acceptance items 1-3)
# ──────────────────────────────────────────────────────────────────────


def _submit_for_test(account: str, symbol: str = "BTC", action: str = "LONG") -> tuple[dict, dict]:
    """Helper — capture the verdict that the stub will return AND the
    submit result.  We pre-build the verdict so the test can assert
    against the same lineageId the writer persisted."""
    return TR.submit_paper_order(symbol=symbol, account_id=account, override_action=action, override_size_usd=200.0)


class TestSubmitPathCarriesLineage:
    def test_new_submit_order_has_lineage(self, _isolate_test_account):
        r = _submit_for_test(_isolate_test_account, "BTC", "LONG")
        assert r["ok"] is True, r
        order = _orders.find_one({"orderId": r["orderId"]}, {"_id": 0})
        assert order is not None
        assert order["lineageId"] is not None
        assert order["lineageId"].startswith("lin_")
        assert order["pipelineVersion"] == ATTR.ATTRIBUTION_PIPELINE_VERSION
        # Full verdictSnapshot persisted (NOT the stripped subset).
        assert "verdictSnapshot" in order
        assert order["verdictSnapshot"].get("rawVerdictSnapshot") is not None

    def test_new_submit_order_filled_event_has_lineage(self, _isolate_test_account):
        r = _submit_for_test(_isolate_test_account, "BTC", "LONG")
        assert r["ok"]
        evt = _events.find_one({"type": "ORDER_FILLED", "positionId": r["positionId"]}, {"_id": 0})
        assert evt is not None, "ORDER_FILLED event missing"
        assert evt["lineageId"] is not None
        assert evt["pipelineVersion"] == ATTR.ATTRIBUTION_PIPELINE_VERSION

    def test_new_submit_creates_position_opened_event(self, _isolate_test_account):
        r = _submit_for_test(_isolate_test_account, "BTC", "LONG")
        assert r["ok"]
        evt = _events.find_one({"type": "POSITION_OPENED", "positionId": r["positionId"]}, {"_id": 0})
        assert evt is not None, "POSITION_OPENED event missing"
        assert evt["lineageId"] is not None
        assert evt["pipelineVersion"] == ATTR.ATTRIBUTION_PIPELINE_VERSION
        # The event MUST carry rawVerdictSnapshot — this is what the
        # attribution drilldowns will read when reconstructing lifecycle.
        assert evt.get("rawVerdictSnapshot") is not None
        # And the lineageId on the event MATCHES the lineageId on the position row.
        pos = _positions.find_one({"positionId": r["positionId"]}, {"_id": 0})
        assert pos["lineageId"] == evt["lineageId"]


# ──────────────────────────────────────────────────────────────────────
# Close-path tests (T11.1c acceptance items 4-5)
# ──────────────────────────────────────────────────────────────────────


class TestCloseWritesPaperOutcome:
    def test_close_creates_paper_outcome_row(self, _isolate_test_account):
        r = _submit_for_test(_isolate_test_account, "BTC", "LONG")
        assert r["ok"]
        close = TR.close_paper_position(r["positionId"], account_id=_isolate_test_account, reason="t11_1c_test")
        assert close["ok"], close
        outcome = _outcomes.find_one({"positionId": r["positionId"]}, {"_id": 0})
        assert outcome is not None, "paper_outcomes row missing after close"
        assert outcome["lineageId"] is not None
        assert outcome["lineageId"].startswith("lin_")
        assert outcome["pipelineVersion"] == ATTR.ATTRIBUTION_PIPELINE_VERSION
        assert outcome["outcome"] in ("win", "loss")
        assert outcome["closeReason"] == "t11_1c_test"
        # Full snapshots present (no on-the-fly reconstruction)
        assert outcome["verdictSnapshot"] is not None
        assert outcome["rawVerdictSnapshot"] is not None
        # Outcome has its own id (separate from positionId)
        assert outcome["outcomeId"].startswith("out_")

    def test_close_twice_does_not_duplicate_outcome(self, _isolate_test_account):
        r = _submit_for_test(_isolate_test_account, "BTC", "LONG")
        assert r["ok"]
        TR.close_paper_position(r["positionId"], account_id=_isolate_test_account, reason="first")
        closed = _positions.find_one({"positionId": r["positionId"]}, {"_id": 0})
        # Call writer again directly (this is the helper that both
        # manual and auto close paths converge on).
        oid2 = TR._write_paper_outcome_t11_1c(
            closed_pos=closed,
            close_price=closed["closePrice"],
            pnl_usd=closed["realizedPnlUsd"],
            pnl_pct=closed["realizedPnlPct"],
            reason="second",
            detection_mode="manual",
        )
        cnt = _outcomes.count_documents({"positionId": r["positionId"]})
        assert cnt == 1, f"expected 1 outcome row, found {cnt} (idempotency broken)"
        existing = _outcomes.find_one({"positionId": r["positionId"]}, {"_id": 0})
        if oid2 is not None:
            assert oid2 == existing["outcomeId"]


# ──────────────────────────────────────────────────────────────────────
# Attribution-integration tests (acceptance item 6 + edge cases)
# ──────────────────────────────────────────────────────────────────────


class TestAttributionSummaryConsumesOutcomes:
    def test_attribution_layer_counts_increase_after_close(self, _isolate_test_account):
        """The 'gated' layer aggregate is computed from paper_outcomes.
        After a close with full lineage, paper_outcomes count MUST
        increase by exactly 1."""
        before = _outcomes.count_documents({})
        r = _submit_for_test(_isolate_test_account, "BTC", "LONG")
        assert r["ok"]
        TR.close_paper_position(r["positionId"], account_id=_isolate_test_account, reason="agg_test")
        after = _outcomes.count_documents({})
        assert after == before + 1, (
            f"paper_outcomes must grow by exactly 1 — was {before}, now {after}"
        )


class TestForwardOnlyInvariant:
    def test_pre_t11_1c_position_does_not_write_outcome(self, _isolate_test_account):
        """A position without lineageId (pre-T11.1c) MUST NOT generate
        a paper_outcomes row on close — no retroactive fabrication."""
        # Manually craft a pre-T11.1c-shaped closed position (no lineageId).
        legacy_pos = {
            "positionId": "pos_legacy_t11_1c_test",
            "orderId": "ord_legacy_t11_1c",
            "accountId": _isolate_test_account,
            "symbol": "BTC",
            "side": "LONG",
            "entryPrice": 100.0,
            "stopPrice": 95.0,
            "targetPrice": 110.0,
            "sizeUsd": 100.0,
            "status": "CLOSED",
            "openedAt": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "closedAt": datetime.now(timezone.utc).isoformat(),
            "closePrice": 105.0,
            "realizedPnlUsd": 5.0,
            "realizedPnlPct": 5.0,
            # NO lineageId, NO pipelineVersion, NO verdictSnapshot
        }
        out_id = TR._write_paper_outcome_t11_1c(
            closed_pos=legacy_pos,
            close_price=105.0,
            pnl_usd=5.0,
            pnl_pct=5.0,
            reason="legacy_close",
            detection_mode="manual",
        )
        assert out_id is None, (
            "writer must SKIP pre-T11.1c positions (forward-only invariant)"
        )
        cnt = _outcomes.count_documents({"positionId": "pos_legacy_t11_1c_test"})
        assert cnt == 0, "no paper_outcomes row should be created for pre-T11.1c position"

    def test_no_retroactive_backfill_on_new_close(self, _isolate_test_account):
        """Closing one new position must NOT cause anything to be
        written for OTHER pre-existing positions.  Tests that the
        outcome writer is positionId-scoped."""
        # Snapshot paper_outcomes IDs BEFORE.
        before_ids = {o["outcomeId"] for o in _outcomes.find({}, {"outcomeId": 1, "_id": 0}) if o.get("outcomeId")}
        r = _submit_for_test(_isolate_test_account, "BTC", "LONG")
        TR.close_paper_position(r["positionId"], account_id=_isolate_test_account, reason="scoped_test")
        after_ids = {o["outcomeId"] for o in _outcomes.find({}, {"outcomeId": 1, "_id": 0}) if o.get("outcomeId")}
        new_ids = after_ids - before_ids
        # At most ONE new outcome row was written; never any others.
        assert len(new_ids) == 1, (
            f"expected exactly 1 new outcome row, got {len(new_ids)} — "
            f"writer may be writing for other positions"
        )


class TestAttributionEndpointHandlesMixedAvailability:
    def test_summary_does_not_crash_with_outcomes_present(self):
        """After T11.1c, paper_outcomes may have rows AND legacy
        paper_positions may exist without lineage.  Attribution summary
        must STILL handle both gracefully (no 500)."""
        # We don't need to hit HTTP — just call the route fn body.
        # In practice that means asserting the aggregate code path
        # works on any subset.
        outcomes_present = list(_outcomes.find({}, {"_id": 0}).limit(5))
        from routes.attribution import _aggregate_outcomes
        agg = _aggregate_outcomes(outcomes_present)
        # Must produce a dict with all expected keys regardless of
        # whether outcomes carry rawVerdictSnapshot or not.
        for key in ("tradeCount", "winCount", "lossCount", "hitRatePct",
                    "meanReturnPct", "cumulativePnlUsd", "cumulativePnlPct",
                    "maxDrawdownPct", "sharpeLike", "meanBarsHeld"):
            assert key in agg, f"missing aggregate key: {key}"
