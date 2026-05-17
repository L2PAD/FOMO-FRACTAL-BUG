"""
T11.2B — Attribution drilldown endpoints.

Four new READ-ONLY derivation endpoints:
  * /api/admin/attribution/assets
  * /api/admin/attribution/gate-rule-breakdown
  * /api/admin/attribution/confidence-distribution
  * /api/admin/attribution/exposure-histograms

Acceptance criteria (per user spec):
  * attribution endpoints remain read-only (byte-identical Mongo counts before/after reads)
  * drilldowns work honestly with sparse data (no NaN, no fabricated rows)
  * pre-T11.1c partial lineage does not break the UI (returns 'unknown' bucket)
  * pipelineVersion present on every response
  * no retrospective recompute (counterfactuals frozen at decision time)
  * no operational CTA in any payload (no 'recommended', 'optimal',
    'should')
"""
from __future__ import annotations

import os
from pathlib import Path

import jwt as _jwt
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

import server  # noqa: F401  (registers all routes including attribution)
from routes import attribution as ATTR


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(server.app)


@pytest.fixture(scope="module")
def admin_token() -> str:
    """Build a self-signed admin JWT using the same secret the
    backend reads from .env — matches the pattern used by
    test_sprint_t11_1_attribution.py."""
    secret = os.environ.get("ADMIN_JWT_SECRET") or os.environ.get("JWT_ACCESS_SECRET")
    if not secret:
        env = Path(__file__).resolve().parents[1] / ".env"
        for line in env.read_text().splitlines():
            if line.startswith("ADMIN_JWT_SECRET=") or line.startswith("JWT_ACCESS_SECRET="):
                secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return _jwt.encode({"role": "admin", "sub": "test_admin"}, secret, algorithm="HS256")


def _hdr(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


WINDOWS = ["7d", "30d", "90d", "all"]
BANNED_CTA_WORDS = [
    "recommend",
    "optimal",
    "should be",
    "needs to be",
    "increase the",
    "decrease the",
    "tighten",
    "loosen",
    "better",
    "worse",
    "alpha",
    "edge",
]


# ──────────────────────────────────────────────────────────────────────
# Auth + window guard
# ──────────────────────────────────────────────────────────────────────


class TestAuthAndWindow:
    @pytest.mark.parametrize("path", [
        "/api/admin/attribution/assets",
        "/api/admin/attribution/gate-rule-breakdown",
        "/api/admin/attribution/confidence-distribution",
        "/api/admin/attribution/exposure-histograms",
    ])
    def test_endpoints_require_admin(self, client: TestClient, path: str):
        r = client.get(path)
        assert r.status_code == 401
        assert r.json()["detail"]["error"] == "ADMIN_REQUIRED"

    @pytest.mark.parametrize("path", [
        "/api/admin/attribution/assets",
        "/api/admin/attribution/gate-rule-breakdown",
        "/api/admin/attribution/confidence-distribution",
        "/api/admin/attribution/exposure-histograms",
    ])
    def test_endpoints_reject_unknown_window(self, client: TestClient, admin_token: str, path: str):
        r = client.get(f"{path}?window=60d", headers=_hdr(admin_token))
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "INVALID_WINDOW"

    @pytest.mark.parametrize("path", [
        "/api/admin/attribution/assets",
        "/api/admin/attribution/gate-rule-breakdown",
        "/api/admin/attribution/confidence-distribution",
        "/api/admin/attribution/exposure-histograms",
    ])
    @pytest.mark.parametrize("w", WINDOWS)
    def test_endpoints_accept_all_canonical_windows(
        self, client: TestClient, admin_token: str, path: str, w: str
    ):
        r = client.get(f"{path}?window={w}", headers=_hdr(admin_token))
        assert r.status_code == 200, r.text


# ──────────────────────────────────────────────────────────────────────
# Read-only invariant (load-bearing)
# ──────────────────────────────────────────────────────────────────────


class TestReadOnlyInvariant:
    def test_drilldown_endpoints_do_not_mutate_sources(self, client: TestClient, admin_token: str):
        db = MongoClient(MONGO_URL)[DB_NAME]
        before = {
            "paper_outcomes":   db.paper_outcomes.count_documents({}),
            "gate_decisions":   db.gate_decisions.count_documents({}),
            "paper_orders_v2":  db.paper_orders_v2.count_documents({}),
            "paper_positions_v2": db.paper_positions_v2.count_documents({}),
            "paper_events_v2":  db.paper_events_v2.count_documents({}),
        }
        for path in [
            "/api/admin/attribution/assets",
            "/api/admin/attribution/gate-rule-breakdown",
            "/api/admin/attribution/confidence-distribution",
            "/api/admin/attribution/exposure-histograms",
        ]:
            for w in WINDOWS:
                r = client.get(f"{path}?window={w}", headers=_hdr(admin_token))
                assert r.status_code == 200, f"{path}?window={w} → {r.status_code} {r.text}"
        after = {
            "paper_outcomes":   db.paper_outcomes.count_documents({}),
            "gate_decisions":   db.gate_decisions.count_documents({}),
            "paper_orders_v2":  db.paper_orders_v2.count_documents({}),
            "paper_positions_v2": db.paper_positions_v2.count_documents({}),
            "paper_events_v2":  db.paper_events_v2.count_documents({}),
        }
        assert before == after, f"sources mutated: {before} → {after}"


# ──────────────────────────────────────────────────────────────────────
# /assets — per-asset drilldown
# ──────────────────────────────────────────────────────────────────────


class TestAssetsEndpoint:
    def test_returns_pipeline_version(self, client: TestClient, admin_token: str):
        r = client.get("/api/admin/attribution/assets?window=30d", headers=_hdr(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["pipelineVersion"] == ATTR.ATTRIBUTION_PIPELINE_VERSION
        assert body["ok"] is True
        assert "rows" in body
        assert isinstance(body["rows"], list)
        assert "framingNote" in body
        # Framing note must avoid leaderboard / CTA language.
        note = body["framingNote"].lower()
        assert "leaderboard" in note or "investigative" in note
        for banned in BANNED_CTA_WORDS:
            assert banned not in note, f"framing leaked CTA word: {banned}"

    def test_rows_have_required_shape(self, client: TestClient, admin_token: str):
        r = client.get("/api/admin/attribution/assets?window=all", headers=_hdr(admin_token))
        body = r.json()
        for row in body["rows"]:
            assert "symbol" in row
            assert "outcomes" in row
            assert "gateBlocks" in row
            assert "lineage" in row
            # outcomes carries the standard aggregate shape.
            for k in ("tradeCount", "winCount", "lossCount", "hitRatePct",
                      "meanReturnPct", "cumulativePnlUsd", "maxDrawdownPct"):
                assert k in row["outcomes"], f"missing {k} in outcomes for {row['symbol']}"
            # lineage shape
            for k in ("outcomesInWindow", "rawSamples", "lineageCompletePct"):
                assert k in row["lineage"]
            # lineageCompletePct in [0, 100]
            lc = row["lineage"]["lineageCompletePct"]
            assert 0.0 <= lc <= 100.0


# ──────────────────────────────────────────────────────────────────────
# /gate-rule-breakdown
# ──────────────────────────────────────────────────────────────────────


class TestGateRuleBreakdown:
    def test_returns_all_canonical_rules(self, client: TestClient, admin_token: str):
        r = client.get("/api/admin/attribution/gate-rule-breakdown?window=all", headers=_hdr(admin_token))
        assert r.status_code == 200
        body = r.json()
        labels = [row["rule"] for row in body["rules"]]
        expected = {"drawdownBreaker", "cooldown", "correlationCluster", "sameSideExposure", "exposureCap"}
        assert set(labels) == expected, f"rules: {labels}"
        assert body["pipelineVersion"] == ATTR.ATTRIBUTION_PIPELINE_VERSION
        assert "framingNote" in body
        # Framing must not contain adjudication words.
        note = body["framingNote"].lower()
        for banned in BANNED_CTA_WORDS:
            assert banned not in note, f"framing leaked CTA word: {banned}"

    def test_each_rule_has_required_shape(self, client: TestClient, admin_token: str):
        r = client.get("/api/admin/attribution/gate-rule-breakdown?window=all", headers=_hdr(admin_token))
        for rule in r.json()["rules"]:
            assert "rule" in rule
            assert "count" in rule
            assert "preventedNotionalUsd" in rule
            assert "topSymbols" in rule
            assert "recentExamples" in rule
            assert isinstance(rule["topSymbols"], list)
            assert isinstance(rule["recentExamples"], list)
            assert len(rule["topSymbols"]) <= 5
            assert len(rule["recentExamples"]) <= 3

    def test_no_would_have_been_profitable_field(self, client: TestClient, admin_token: str):
        """Critical invariant — endpoint MUST NOT return any field
        that scores blocked decisions against later market prices."""
        r = client.get("/api/admin/attribution/gate-rule-breakdown?window=all", headers=_hdr(admin_token))
        body = r.json()
        forbidden = {"wouldHaveProfited", "missedPnl", "missedReturn",
                     "shouldRelax", "ruleAccuracy", "ruleEfficiency"}
        for rule in body["rules"]:
            for f in forbidden:
                assert f not in rule, f"rule {rule['rule']} leaked adjudication field: {f}"


# ──────────────────────────────────────────────────────────────────────
# /confidence-distribution
# ──────────────────────────────────────────────────────────────────────


class TestConfidenceDistribution:
    def test_returns_canonical_buckets(self, client: TestClient, admin_token: str):
        r = client.get("/api/admin/attribution/confidence-distribution?window=all", headers=_hdr(admin_token))
        assert r.status_code == 200
        body = r.json()
        buckets = {b["bucket"] for b in body["buckets"]}
        assert buckets == {"low", "mid", "high", "unknown"}
        assert body["pipelineVersion"] == ATTR.ATTRIBUTION_PIPELINE_VERSION

    def test_share_percentages_sum_to_100_when_any_outcomes(self, client: TestClient, admin_token: str):
        r = client.get("/api/admin/attribution/confidence-distribution?window=all", headers=_hdr(admin_token))
        body = r.json()
        total = body["totalOutcomes"]
        if total == 0:
            # All shares should be 0 in empty state.
            for b in body["buckets"]:
                assert b["sharePct"] == 0.0
                assert b["tradeCount"] == 0
        else:
            share_sum = sum(b["sharePct"] for b in body["buckets"])
            # Allow small float rounding (≤0.2pp).
            assert abs(share_sum - 100.0) <= 0.2, f"share sum drift: {share_sum}"

    def test_framing_is_epistemic_not_optimisation(self, client: TestClient, admin_token: str):
        r = client.get("/api/admin/attribution/confidence-distribution?window=all", headers=_hdr(admin_token))
        note = r.json()["framingNote"].lower()
        assert "epistemic" in note or "calibration" in note
        for banned in BANNED_CTA_WORDS:
            assert banned not in note, f"framing leaked CTA word: {banned}"


# ──────────────────────────────────────────────────────────────────────
# /exposure-histograms
# ──────────────────────────────────────────────────────────────────────


class TestExposureHistograms:
    def test_returns_canonical_bands(self, client: TestClient, admin_token: str):
        r = client.get("/api/admin/attribution/exposure-histograms?window=all", headers=_hdr(admin_token))
        assert r.status_code == 200
        body = r.json()
        labels = {b["band"] for b in body["bands"]}
        assert labels == {"0-100", "100-250", "250-500", "500-1000", "1000+", "unknown"}
        assert body["pipelineVersion"] == ATTR.ATTRIBUTION_PIPELINE_VERSION

    def test_each_band_has_canonical_shape(self, client: TestClient, admin_token: str):
        r = client.get("/api/admin/attribution/exposure-histograms?window=all", headers=_hdr(admin_token))
        for band in r.json()["bands"]:
            for k in ("band", "tradeCount", "winCount", "lossCount", "hitRatePct",
                      "meanReturnPct", "cumulativePnlUsd", "meanSizeUsd"):
                assert k in band, f"missing {k} in band {band.get('band')}"

    def test_no_recommended_size_field(self, client: TestClient, admin_token: str):
        r = client.get("/api/admin/attribution/exposure-histograms?window=all", headers=_hdr(admin_token))
        body = r.json()
        forbidden = {"recommendedBand", "optimalSizeUsd", "shouldSize", "bestBand"}
        for f in forbidden:
            assert f not in body, f"top-level leaked CTA field: {f}"
            for band in body["bands"]:
                assert f not in band, f"band leaked CTA field: {f}"

    def test_framing_is_observational(self, client: TestClient, admin_token: str):
        r = client.get("/api/admin/attribution/exposure-histograms?window=all", headers=_hdr(admin_token))
        note = r.json()["framingNote"].lower()
        assert "observation" in note or "downstream effect" in note
        for banned in BANNED_CTA_WORDS:
            assert banned not in note, f"framing leaked CTA word: {banned}"


# ──────────────────────────────────────────────────────────────────────
# Sparse-data graceful handling
# ──────────────────────────────────────────────────────────────────────


class TestSparseAndEmptyData:
    def test_assets_endpoint_returns_n_zero_on_short_window_no_data(self, client: TestClient, admin_token: str):
        """7d window may legitimately be empty — endpoint MUST NOT
        return 5xx or NaN."""
        r = client.get("/api/admin/attribution/assets?window=7d", headers=_hdr(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert "rows" in body
        # n must match rows length
        assert body["n"] == len(body["rows"])

    def test_all_endpoints_no_NaN_or_inf_in_response(self, client: TestClient, admin_token: str):
        """No metric may serialise as NaN / Infinity — pytest will see
        json.loads succeed but we explicitly check for the string
        forms just in case."""
        for path in [
            "/api/admin/attribution/assets?window=30d",
            "/api/admin/attribution/gate-rule-breakdown?window=30d",
            "/api/admin/attribution/confidence-distribution?window=30d",
            "/api/admin/attribution/exposure-histograms?window=30d",
        ]:
            r = client.get(path, headers=_hdr(admin_token))
            txt = r.text.lower()
            assert "nan" not in txt
            assert "infinity" not in txt
            assert "\"inf\"" not in txt
