"""
Tests for Structure A/B Shadow System
=======================================
Tests shadow recording, evaluation, KPI computation, and case analysis.
"""

import pytest
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from forecast.structure.shadow import (
    record_shadow,
    evaluate_shadows,
    compute_shadow_kpi,
    get_shadow_cases,
    _direction_match,
    _direction_distribution,
    SHADOW_COLLECTION,
)
from forecast.v41_config import classify_direction


# ═══════════════════════════════════════════════════════
# HELPER: DB cleanup
# ═══════════════════════════════════════════════════════

def _get_test_db():
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    return MongoClient(mongo_url)[db_name]


@pytest.fixture(autouse=True)
def cleanup():
    db = _get_test_db()
    db[SHADOW_COLLECTION].delete_many({"forecastId": {"$regex": "^test-shadow-"}})
    yield
    db[SHADOW_COLLECTION].delete_many({"forecastId": {"$regex": "^test-shadow-"}})


# ═══════════════════════════════════════════════════════
# UNIT TESTS: direction matching
# ═══════════════════════════════════════════════════════

class TestDirectionMatch:
    def test_bull_match(self):
        assert _direction_match("MILD_BULL", "BULL") is True
        assert _direction_match("STRONG_BULL", "BULL") is True

    def test_bull_mismatch(self):
        assert _direction_match("MILD_BEAR", "BULL") is False
        assert _direction_match("NEUTRAL", "BULL") is False

    def test_bear_match(self):
        assert _direction_match("MILD_BEAR", "BEAR") is True
        assert _direction_match("STRONG_BEAR", "BEAR") is True

    def test_bear_mismatch(self):
        assert _direction_match("MILD_BULL", "BEAR") is False

    def test_flat_match(self):
        assert _direction_match("NEUTRAL", "FLAT") is True

    def test_flat_mismatch(self):
        assert _direction_match("MILD_BULL", "FLAT") is False


class TestDirectionDistribution:
    def test_all_neutral(self):
        dist = _direction_distribution(["NEUTRAL", "NEUTRAL", "NEUTRAL"])
        assert dist["neutral_ratio"] == 1.0
        assert dist["mild_ratio"] == 0.0

    def test_mixed(self):
        dirs = ["MILD_BULL", "MILD_BEAR", "NEUTRAL", "STRONG_BULL"]
        dist = _direction_distribution(dirs)
        assert dist["neutral_ratio"] == 0.25
        assert dist["mild_ratio"] == 0.5
        assert dist["strong_ratio"] == 0.25


# ═══════════════════════════════════════════════════════
# INTEGRATION TESTS: record + KPI
# ═══════════════════════════════════════════════════════

class TestShadowRecording:
    def test_record_creates_document(self):
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        record_shadow(
            forecast_id="test-shadow-001",
            asset="BTC",
            horizon="7D",
            entry_price=70000.0,
            base_score=0.25,
            structure_score=0.30,
            structure_features={"structure_bias_score": 0.7},
            structure_delta=0.05,
            sign_flip=False,
            evaluate_after=now_ms + 86400000,
            bucket="2026-03-19",
        )

        db = _get_test_db()
        doc = db[SHADOW_COLLECTION].find_one(
            {"forecastId": "test-shadow-001"},
            {"_id": 0},
        )
        assert doc is not None
        assert doc["asset"] == "BTC"
        assert doc["horizon"] == "7D"
        assert doc["forecast_base"]["score"] == 0.25
        assert doc["forecast_base"]["direction"] == "MILD_BULL"
        assert doc["forecast_structure"]["score"] == 0.30
        assert doc["structure_delta"]["delta"] == 0.05
        assert doc["evaluated"] is False

    def test_direction_change_tracked(self):
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        record_shadow(
            forecast_id="test-shadow-002",
            asset="BTC",
            horizon="7D",
            entry_price=70000.0,
            base_score=0.18,
            structure_score=0.22,
            structure_features={},
            structure_delta=0.04,
            sign_flip=False,
            evaluate_after=now_ms + 86400000,
            bucket="2026-03-19",
        )

        db = _get_test_db()
        doc = db[SHADOW_COLLECTION].find_one(
            {"forecastId": "test-shadow-002"},
            {"_id": 0},
        )
        # base_score=0.18 → NEUTRAL, structure_score=0.22 → MILD_BULL
        assert doc["forecast_base"]["direction"] == "NEUTRAL"
        assert doc["forecast_structure"]["direction"] == "MILD_BULL"
        assert doc["structure_delta"]["direction_changed"] is True

    def test_upsert_idempotent(self):
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        for _ in range(3):
            record_shadow(
                forecast_id="test-shadow-003",
                asset="BTC",
                horizon="7D",
                entry_price=70000.0,
                base_score=0.3,
                structure_score=0.35,
                structure_features={},
                structure_delta=0.05,
                sign_flip=False,
                evaluate_after=now_ms,
                bucket="2026-03-19",
            )

        db = _get_test_db()
        count = db[SHADOW_COLLECTION].count_documents({"forecastId": "test-shadow-003"})
        assert count == 1


class TestShadowKPIEmpty:
    def test_empty_returns_insufficient(self):
        kpi = compute_shadow_kpi(horizon="7D")
        assert kpi["n"] == 0
        assert kpi["verdict"] == "INSUFFICIENT_DATA"


class TestShadowCases:
    def test_empty_returns_list(self):
        cases = get_shadow_cases(horizon="7D")
        assert isinstance(cases, list)
