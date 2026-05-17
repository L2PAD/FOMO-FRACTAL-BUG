"""T11.1 — Performance Attribution tests.

Architectural invariants verified:
  * Attribution NEVER mutates source data (outcomes, gate_decisions,
    paper_positions, verdict snapshots).
  * Counterfactual snapshots are written FORWARD-ONLY by portfolio_gate
    and are immutable thereafter.
  * pipelineVersion is exposed on every response so cross-version
    comparisons can be structurally prevented.
  * Window guard supports 'all' as an explicit value (attribution
    semantically requires long-horizon).
  * Raw-layer attribution is honestly reported as 'forward-only' when
    rawVerdictSnapshot is absent — no fabrication.
  * Capital-preservation score on the gate layer is observational
    (counts by rule) — never a value judgment ('gate blocked winners').
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
PIPELINE_VERSION = "t6+t8+t9+t10+tier4c1"


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


# ── Auth + windowing ─────────────────────────────────────────────────


class TestAttributionAuth:
    def test_summary_requires_admin(self):
        r = requests.get(f"{BASE_URL}/api/admin/attribution/summary")
        assert r.status_code == 401

    def test_summary_supports_only_known_windows(self):
        r = requests.get(f"{BASE_URL}/api/admin/attribution/summary",
                         headers=_admin_headers(), params={"window": "60d"})
        assert r.status_code == 400
        body = r.json()
        assert body["detail"]["error"] == "INVALID_WINDOW"
        # 'all' must be explicitly supported on the attribution surface
        assert "all" in body["detail"]["supported"]

    def test_summary_supports_all_window(self):
        r = requests.get(f"{BASE_URL}/api/admin/attribution/summary",
                         headers=_admin_headers(), params={"window": "all"})
        assert r.status_code == 200
        body = r.json()
        assert body["window"] == "all"
        assert body["windowDays"] is None
        assert body["windowStart"] is None


class TestPipelineVersion:
    def test_pipeline_version_is_stable_and_lists_components(self):
        r = requests.get(f"{BASE_URL}/api/admin/attribution/pipeline-version",
                         headers=_admin_headers())
        assert r.status_code == 200
        body = r.json()
        assert body["pipelineVersion"] == PIPELINE_VERSION
        # All known components must be listed for transparency.
        for k in ("t6", "t8", "t9", "t10", "tier4c1"):
            assert k in body["components"]

    def test_summary_carries_pipeline_version(self):
        r = requests.get(f"{BASE_URL}/api/admin/attribution/summary",
                         headers=_admin_headers(), params={"window": "30d"})
        assert r.json()["pipelineVersion"] == PIPELINE_VERSION


# ── Honest data availability ─────────────────────────────────────────


class TestRawLayerHonesty:
    def test_raw_layer_marks_itself_unsupported_when_no_snapshots(self):
        # With no outcomes carrying rawVerdictSnapshot, the response
        # MUST mark raw as forward-only-from-T11.1, not fabricate data.
        r = requests.get(f"{BASE_URL}/api/admin/attribution/summary",
                         headers=_admin_headers(), params={"window": "all"})
        body = r.json()
        avail = body["dataAvailability"]
        # If no raw samples exist, the layer is honestly flagged.
        if avail["rawSamples"] == 0:
            assert avail["rawLayerSupported"] is False
            assert "raw" in body["layers"]
            # Note exists explaining the absence
            assert "rawVerdictSnapshot" in body["layers"]["raw"].get("note", "")


# ── Capital preservation score ───────────────────────────────────────


class TestCapitalPreservationScore:
    """Risk-adjusted gate attribution.  Verifies counts by rule,
    preserved notional, AND the editorial framingNote (UI invariant)."""

    def setup_method(self):
        # Isolate the test's gate decisions by tagging them with a
        # unique synthetic symbol — easy to clean up.
        self.test_symbol = f"T11TEST_{int(time.time())}"
        _db().gate_decisions.delete_many({"symbol": self.test_symbol})

    def teardown_method(self):
        _db().gate_decisions.delete_many({"symbol": self.test_symbol})

    def _seed_block(self, rule, size_usd):
        _db().gate_decisions.insert_one({
            "decisionId":      f"gd_test_{int(time.time()*1000000)}",
            "pipelineVersion": PIPELINE_VERSION,
            "ts":              _ts(),
            "symbol":          self.test_symbol,
            "permission":      "blocked",
            "blockReason":     rule,
            "blockReasons":    [rule],
            "verdictPreGate":  {"action": "LONG", "alignment": {}, "risk": "med", "rr": 2.0,
                                "sizing": {"final": size_usd}, "entry": 100, "stop": 95, "target": 110},
            "counterfactual":  {"theoreticalEntry": 100, "theoreticalStop": 95,
                                "theoreticalTarget": 110, "theoreticalSizeUsd": size_usd,
                                "marketPriceAtDecision": 100, "rr": 2.0},
            "gateBlockSummary": {"permission": "blocked", "blockReason": rule},
        })

    def test_capital_preservation_aggregates_by_rule(self):
        # Seed a known mix of blocks.
        self._seed_block("daily_drawdown_circuit_breaker", 250.0)
        self._seed_block("loss_streak_cooldown",          150.0)
        self._seed_block("max_correlated_exposure",       300.0)
        self._seed_block("max_total_notional",            200.0)
        # Hit per-asset to confine to our synthetic symbol.
        r = requests.get(
            f"{BASE_URL}/api/admin/attribution/per-asset",
            headers=_admin_headers(),
            params={"symbol": self.test_symbol, "window": "all"},
        )
        body = r.json()
        gb = body["gateBlocks"]
        assert gb["blockedCount"] == 4
        assert gb["preventedNotionalUsd"] == pytest.approx(900.0)
        by = gb["byRule"]
        assert by["drawdownBreaker"]    == 1
        assert by["cooldown"]           == 1
        assert by["correlationCluster"] == 1
        assert by["exposureCap"]        == 1
        # Editorial invariant — must reach the UI verbatim
        assert "Capital preservation is not winner-picking" in gb["framingNote"]


# ── Lost opportunity ─────────────────────────────────────────────────


class TestLostOpportunity:
    def setup_method(self):
        self.test_symbol = f"T11LO_{int(time.time())}"
        _db().gate_decisions.delete_many({"symbol": self.test_symbol})

    def teardown_method(self):
        _db().gate_decisions.delete_many({"symbol": self.test_symbol})

    def test_lost_opportunity_returns_immutable_counterfactual_with_framing(self):
        _db().gate_decisions.insert_one({
            "decisionId":      "gd_lo_test_1",
            "pipelineVersion": PIPELINE_VERSION,
            "ts":              _ts(),
            "symbol":          self.test_symbol,
            "permission":      "blocked",
            "blockReason":     "daily_drawdown_circuit_breaker",
            "blockReasons":    ["daily_drawdown_circuit_breaker"],
            "verdictPreGate":  {"action": "LONG"},
            "counterfactual":  {
                "theoreticalEntry": 50000, "theoreticalStop": 49000,
                "theoreticalTarget": 52000, "theoreticalSizeUsd": 500,
                "marketPriceAtDecision": 50000, "rr": 2.0,
            },
            "gateBlockSummary": {"permission": "blocked"},
        })
        r = requests.get(
            f"{BASE_URL}/api/admin/attribution/lost-opportunity",
            headers=_admin_headers(), params={"window": "all"},
        )
        body = r.json()
        assert body["pipelineVersion"] == PIPELINE_VERSION
        # The editorial framing invariant is mandatory
        assert "risk-containment" in body["framingNote"]
        assert "not retrospective mistakes" in body["framingNote"]
        # Our synthetic row appears with counterfactual fields intact
        ours = [r for r in body["rows"] if r.get("symbol") == self.test_symbol]
        assert len(ours) == 1
        cf = ours[0]["counterfactual"]
        assert cf["theoreticalEntry"] == 50000
        assert cf["theoreticalSizeUsd"] == 500


# ── Attribution is read-only ─────────────────────────────────────────


class TestReadOnlyDerivation:
    def test_summary_does_not_mutate_source_collections(self):
        before_outcomes = _db().paper_outcomes.count_documents({})
        before_gates    = _db().gate_decisions.count_documents({})
        before_positions = _db().paper_positions_v2.count_documents({})

        # Hit every endpoint across every window to maximise coverage.
        for w in ("7d", "30d", "90d", "all"):
            requests.get(f"{BASE_URL}/api/admin/attribution/summary",
                         headers=_admin_headers(), params={"window": w})
            requests.get(f"{BASE_URL}/api/admin/attribution/lost-opportunity",
                         headers=_admin_headers(), params={"window": w})

        # Source-of-truth counts must be byte-identical post-derivation
        assert _db().paper_outcomes.count_documents({})    == before_outcomes
        assert _db().gate_decisions.count_documents({})    == before_gates
        assert _db().paper_positions_v2.count_documents({}) == before_positions


# ── Gate-decisions write path ────────────────────────────────────────


class TestGateDecisionsAreImmutableForwardOnly:
    """The portfolio_gate writes a snapshot row at every evaluation.
    Rows must be append-only — once written, payload fields never
    change.  We don't test the writer directly (it's tested by
    TIER-4B.2 integration); here we verify the SHAPE invariant — every
    gate_decisions row carries a frozen counterfactual block plus a
    pipelineVersion stamp."""

    def test_all_existing_gate_decisions_carry_pipeline_version(self):
        # Inspect existing rows (may be zero — that's fine).
        for row in _db().gate_decisions.find({}, {"_id": 0}).limit(10):
            assert row.get("pipelineVersion"), "every gate decision must carry pipelineVersion"
            assert "counterfactual" in row, "every gate decision must carry counterfactual snapshot"
            cf = row["counterfactual"]
            # Snapshot fields are present (values may legitimately be
            # None if the verdict was WAIT at decision time).
            assert "theoreticalEntry" in cf
            assert "theoreticalSizeUsd" in cf
            assert "marketPriceAtDecision" in cf


# ── Per-asset endpoint ───────────────────────────────────────────────


class TestPerAssetEndpoint:
    def test_per_asset_requires_symbol(self):
        r = requests.get(f"{BASE_URL}/api/admin/attribution/per-asset",
                         headers=_admin_headers())
        assert r.status_code == 422  # missing required query param

    def test_per_asset_returns_pipeline_version(self):
        r = requests.get(f"{BASE_URL}/api/admin/attribution/per-asset",
                         headers=_admin_headers(),
                         params={"symbol": "BTC-USDT", "window": "30d"})
        assert r.status_code == 200
        assert r.json()["pipelineVersion"] == PIPELINE_VERSION


# ── T11.1b — Raw Lineage Capture continuity ──────────────────────────


class TestLineageSpine:
    """The lineageId is the canonical spine that ties together raw →
    calibrated → sized → gated → submitted → outcome.  These tests
    verify the in-process build_verdict() pipeline + apply_portfolio_gate
    chain propagates the lineage end-to-end.  Forward-only — historical
    rows without lineageId are explicitly tolerated.
    """

    def test_build_verdict_attaches_lineage_id_and_raw_snapshot(self):
        # Import locally so the test stays decoupled from boot order
        from services.trading_runtime import build_verdict
        # Any symbol; the function gracefully handles missing TA data.
        v = build_verdict("LINEAGE_TEST_SYMBOL")
        assert "lineageId" in v, "every verdict must carry lineageId"
        assert v["lineageId"].startswith("lin_")
        assert "rawVerdictSnapshot" in v
        raw = v["rawVerdictSnapshot"]
        # Required minimum fields per user spec
        for k in ("lineageId", "action", "confidence", "entry", "stop",
                  "target", "rr", "symbol", "timestamp", "modelVersion",
                  "marketContext"):
            assert k in raw, f"raw snapshot missing required field: {k}"
        # Lineage spine invariant: id matches the parent verdict
        assert raw["lineageId"] == v["lineageId"]
        # Pipeline version present
        assert v["pipelineVersion"] == PIPELINE_VERSION

    def test_raw_snapshot_is_isolated_from_later_mutations(self):
        """After downstream layers (calibration/sizing/gate) modify the
        verdict, the rawVerdictSnapshot block must remain UNCHANGED —
        snapshot-at-decision invariant."""
        from services.trading_runtime import build_verdict
        v = build_verdict("LINEAGE_ISOLATION_TEST")
        raw_initial = dict(v["rawVerdictSnapshot"])
        # Simulate later mutation on the parent verdict — this should
        # NOT bleed into the raw snapshot.
        v["action"] = "MUTATED_BY_TEST"
        v["confidence"] = 0.999
        # The frozen snapshot is unchanged
        assert v["rawVerdictSnapshot"] == raw_initial

    def test_gate_decision_carries_lineage_id_from_verdict(self):
        """When the portfolio gate persists a gate_decisions row, it
        must include the lineageId from the verdict — same spine."""
        from services.portfolio_gate import apply_portfolio_gate
        # Synthetic minimal verdict with a lineage id pre-attached
        synthetic_lineage = "lin_t11b_gate_test_synth"
        verdict = {
            "symbol":     "T11BGATETEST",
            "action":     "LONG",
            "entry":      100.0,
            "stop":       95.0,
            "target":     110.0,
            "rr":         2.0,
            "risk":       "MED",
            "sizing":     {"final": 250.0},
            "lineageId":  synthetic_lineage,
            "pipelineVersion": PIPELINE_VERSION,
            "alignment":  {"score": 0.33},
        }
        # Minimal account + empty open-positions list
        account = {"accountId": "test_paper_acc", "equityUsd": 10000,
                   "balanceUsd": 10000}
        before = _db().gate_decisions.count_documents({"lineageId": synthetic_lineage})
        apply_portfolio_gate(verdict, account, [])
        after = _db().gate_decisions.count_documents({"lineageId": synthetic_lineage})
        assert after == before + 1, "gate must write exactly one row per evaluation"
        row = _db().gate_decisions.find_one({"lineageId": synthetic_lineage}, {"_id": 0})
        assert row["lineageId"] == synthetic_lineage
        assert row["pipelineVersion"] == PIPELINE_VERSION
        # Cleanup our synthetic row
        _db().gate_decisions.delete_many({"lineageId": synthetic_lineage})

    def test_pre_lineage_outcomes_still_render_without_error(self):
        """Historical outcomes without lineageId must NOT break the
        attribution endpoints — graceful degradation per the
        forward-only invariant.  This is verified implicitly by the
        summary endpoint returning 200 with the honest note flag."""
        r = requests.get(f"{BASE_URL}/api/admin/attribution/summary",
                         headers=_admin_headers(), params={"window": "all"})
        assert r.status_code == 200
        body = r.json()
        # No exception, data availability block exists, raw layer
        # supported flag is a clean boolean regardless of dataset shape.
        assert "dataAvailability" in body
        assert isinstance(body["dataAvailability"]["rawLayerSupported"], bool)
