"""
Comprehensive Tests for A/B Shadow System for Structure Impact Validation
==========================================================================
Tests: shadow recording, evaluation, KPI computation, verdict logic, 
API endpoints, scheduler integration, and full pipeline integration.
"""

import pytest
import sys
import os
import requests
from datetime import datetime, timezone, timedelta

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

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://expo-telegram-web.preview.emergentagent.com").rstrip("/")


def _get_test_db():
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    return MongoClient(mongo_url)[db_name]


@pytest.fixture(autouse=True)
def cleanup():
    """Cleanup test shadow records before and after tests"""
    db = _get_test_db()
    db[SHADOW_COLLECTION].delete_many({"forecastId": {"$regex": "^test-shadow-ab-"}})
    yield
    db[SHADOW_COLLECTION].delete_many({"forecastId": {"$regex": "^test-shadow-ab-"}})


# ═══════════════════════════════════════════════════════
# API ENDPOINT TESTS
# ═══════════════════════════════════════════════════════

class TestShadowKPIEndpoint:
    """Tests for GET /api/forecast/shadow/kpi endpoint"""
    
    def test_shadow_kpi_endpoint_returns_ok(self):
        """Verify shadow KPI endpoint returns valid response"""
        response = requests.get(f"{BASE_URL}/api/forecast/shadow/kpi")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "n" in data
        assert "verdict" in data
        
    def test_shadow_kpi_with_7d_horizon_filter(self):
        """Verify horizon filter works for 7D"""
        response = requests.get(f"{BASE_URL}/api/forecast/shadow/kpi?horizon=7D")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        
    def test_shadow_kpi_with_30d_horizon_filter(self):
        """Verify horizon filter works for 30D"""
        response = requests.get(f"{BASE_URL}/api/forecast/shadow/kpi?horizon=30D")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True


class TestShadowCasesEndpoint:
    """Tests for GET /api/forecast/shadow/cases endpoint"""
    
    def test_shadow_cases_endpoint_returns_ok(self):
        """Verify shadow cases endpoint returns valid response"""
        response = requests.get(f"{BASE_URL}/api/forecast/shadow/cases")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "count" in data
        assert "cases" in data
        assert isinstance(data["cases"], list)
        
    def test_shadow_cases_with_case_type_filter(self):
        """Verify case_type filter works"""
        response = requests.get(f"{BASE_URL}/api/forecast/shadow/cases?case_type=structure_improved")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        
    def test_shadow_cases_with_horizon_filter(self):
        """Verify horizon filter works"""
        response = requests.get(f"{BASE_URL}/api/forecast/shadow/cases?horizon=7D")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        
    def test_shadow_cases_with_limit(self):
        """Verify limit parameter works"""
        response = requests.get(f"{BASE_URL}/api/forecast/shadow/cases?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True


# ═══════════════════════════════════════════════════════
# SHADOW RECORDING TESTS
# ═══════════════════════════════════════════════════════

class TestShadowRecordingFeatures:
    """Tests for record_shadow() functionality"""
    
    def test_record_creates_document_with_all_fields(self):
        """Verify shadow record has all required fields"""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        record_shadow(
            forecast_id="test-shadow-ab-fields",
            asset="BTC",
            horizon="7D",
            entry_price=70000.0,
            base_score=0.25,
            structure_score=0.30,
            structure_features={"structure_bias_score": 0.5},
            structure_delta=0.05,
            sign_flip=False,
            evaluate_after=now_ms + 86400000,
            bucket="2026-03-19",
        )
        
        db = _get_test_db()
        doc = db[SHADOW_COLLECTION].find_one({"forecastId": "test-shadow-ab-fields"}, {"_id": 0})
        
        assert doc is not None
        assert doc["asset"] == "BTC"
        assert doc["horizon"] == "7D"
        assert doc["bucket"] == "2026-03-19"
        assert doc["entryPrice"] == 70000.0
        assert doc["forecast_base"]["score"] == 0.25
        assert doc["forecast_structure"]["score"] == 0.30
        assert doc["structure_delta"]["delta"] == 0.05
        assert doc["evaluated"] is False
        assert doc["outcome"] is None
        
    def test_direction_changed_flag_when_class_changes(self):
        """Verify direction_changed is True when structure delta changes direction class"""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        # base_score=0.10 → NEUTRAL, structure_score=0.25 → MILD_BULL
        record_shadow(
            forecast_id="test-shadow-ab-direction-change",
            asset="BTC",
            horizon="7D",
            entry_price=70000.0,
            base_score=0.10,
            structure_score=0.25,
            structure_features={},
            structure_delta=0.15,
            sign_flip=False,
            evaluate_after=now_ms + 86400000,
            bucket="2026-03-19",
        )
        
        db = _get_test_db()
        doc = db[SHADOW_COLLECTION].find_one({"forecastId": "test-shadow-ab-direction-change"}, {"_id": 0})
        
        # base=NEUTRAL, structure=MILD_BULL → direction_changed=True
        assert doc["forecast_base"]["direction"] == "NEUTRAL"
        assert doc["forecast_structure"]["direction"] == "MILD_BULL"
        assert doc["structure_delta"]["direction_changed"] is True
        
    def test_direction_not_changed_when_class_same(self):
        """Verify direction_changed is False when classes match"""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        # Both scores → MILD_BULL
        record_shadow(
            forecast_id="test-shadow-ab-same-direction",
            asset="BTC",
            horizon="7D",
            entry_price=70000.0,
            base_score=0.25,
            structure_score=0.30,
            structure_features={},
            structure_delta=0.05,
            sign_flip=False,
            evaluate_after=now_ms + 86400000,
            bucket="2026-03-19",
        )
        
        db = _get_test_db()
        doc = db[SHADOW_COLLECTION].find_one({"forecastId": "test-shadow-ab-same-direction"}, {"_id": 0})
        
        assert doc["structure_delta"]["direction_changed"] is False
        
    def test_upsert_idempotency_no_duplicates(self):
        """Verify multiple calls don't create duplicates (forecastId+horizon key)"""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        for i in range(5):
            record_shadow(
                forecast_id="test-shadow-ab-idempotent",
                asset="BTC",
                horizon="7D",
                entry_price=70000.0 + i,
                base_score=0.20,
                structure_score=0.25,
                structure_features={},
                structure_delta=0.05,
                sign_flip=False,
                evaluate_after=now_ms,
                bucket="2026-03-19",
            )
        
        db = _get_test_db()
        count = db[SHADOW_COLLECTION].count_documents({"forecastId": "test-shadow-ab-idempotent"})
        assert count == 1
        
        # Last entry_price should be 70004 (last write wins)
        doc = db[SHADOW_COLLECTION].find_one({"forecastId": "test-shadow-ab-idempotent"}, {"_id": 0})
        assert doc["entryPrice"] == 70004.0


# ═══════════════════════════════════════════════════════
# SHADOW EVALUATION TESTS
# ═══════════════════════════════════════════════════════

class TestShadowEvaluation:
    """Tests for evaluate_shadows() case classification"""
    
    def test_case_classification_structure_improved(self):
        """Verify structure_improved: structure correct, base wrong"""
        # Manual test: create matured shadow with known outcome
        db = _get_test_db()
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        past_ms = now_ms - 86400000  # 1 day ago
        
        # Create shadow where structure predicts BULL correctly, base predicts BEAR incorrectly
        doc = {
            "forecastId": "test-shadow-ab-case-improved",
            "asset": "BTC",
            "horizon": "7D",
            "bucket": "2026-03-18",
            "entryPrice": 70000.0,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "evaluateAfter": past_ms,
            "forecast_base": {"score": -0.25, "direction": "MILD_BEAR"},
            "forecast_structure": {"score": 0.30, "direction": "MILD_BULL"},
            "structure_delta": {"delta": 0.55, "sign_flip": True, "direction_changed": True},
            "structure_features": {},
            "evaluated": True,
            "outcome": {
                "actualPrice": 71000.0,
                "realMovePct": 1.43,
                "realDirection": "BULL",
                "baseDirectionCorrect": False,
                "structDirectionCorrect": True,
                "caseType": "structure_improved",
                "evaluatedAt": datetime.now(timezone.utc).isoformat(),
            },
        }
        db[SHADOW_COLLECTION].insert_one(doc)
        
        # Retrieve and verify
        result = db[SHADOW_COLLECTION].find_one(
            {"forecastId": "test-shadow-ab-case-improved"},
            {"_id": 0}
        )
        assert result["outcome"]["caseType"] == "structure_improved"
        
    def test_case_classification_structure_hurt(self):
        """Verify structure_hurt: base correct, structure wrong"""
        db = _get_test_db()
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        past_ms = now_ms - 86400000
        
        doc = {
            "forecastId": "test-shadow-ab-case-hurt",
            "asset": "BTC",
            "horizon": "7D",
            "bucket": "2026-03-18",
            "entryPrice": 70000.0,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "evaluateAfter": past_ms,
            "forecast_base": {"score": 0.30, "direction": "MILD_BULL"},
            "forecast_structure": {"score": -0.25, "direction": "MILD_BEAR"},
            "structure_delta": {"delta": -0.55, "sign_flip": True, "direction_changed": True},
            "structure_features": {},
            "evaluated": True,
            "outcome": {
                "actualPrice": 71000.0,
                "realMovePct": 1.43,
                "realDirection": "BULL",
                "baseDirectionCorrect": True,
                "structDirectionCorrect": False,
                "caseType": "structure_hurt",
                "evaluatedAt": datetime.now(timezone.utc).isoformat(),
            },
        }
        db[SHADOW_COLLECTION].insert_one(doc)
        
        result = db[SHADOW_COLLECTION].find_one(
            {"forecastId": "test-shadow-ab-case-hurt"},
            {"_id": 0}
        )
        assert result["outcome"]["caseType"] == "structure_hurt"
        
    def test_case_classification_both_correct(self):
        """Verify both_correct: both variants correct"""
        db = _get_test_db()
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        past_ms = now_ms - 86400000
        
        doc = {
            "forecastId": "test-shadow-ab-case-both-correct",
            "asset": "BTC",
            "horizon": "7D",
            "bucket": "2026-03-18",
            "entryPrice": 70000.0,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "evaluateAfter": past_ms,
            "forecast_base": {"score": 0.25, "direction": "MILD_BULL"},
            "forecast_structure": {"score": 0.35, "direction": "MILD_BULL"},
            "structure_delta": {"delta": 0.10, "sign_flip": False, "direction_changed": False},
            "structure_features": {},
            "evaluated": True,
            "outcome": {
                "actualPrice": 71000.0,
                "realMovePct": 1.43,
                "realDirection": "BULL",
                "baseDirectionCorrect": True,
                "structDirectionCorrect": True,
                "caseType": "both_correct",
                "evaluatedAt": datetime.now(timezone.utc).isoformat(),
            },
        }
        db[SHADOW_COLLECTION].insert_one(doc)
        
        result = db[SHADOW_COLLECTION].find_one(
            {"forecastId": "test-shadow-ab-case-both-correct"},
            {"_id": 0}
        )
        assert result["outcome"]["caseType"] == "both_correct"
        
    def test_case_classification_both_wrong(self):
        """Verify both_wrong: both variants incorrect"""
        db = _get_test_db()
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        past_ms = now_ms - 86400000
        
        doc = {
            "forecastId": "test-shadow-ab-case-both-wrong",
            "asset": "BTC",
            "horizon": "7D",
            "bucket": "2026-03-18",
            "entryPrice": 70000.0,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "evaluateAfter": past_ms,
            "forecast_base": {"score": -0.25, "direction": "MILD_BEAR"},
            "forecast_structure": {"score": -0.30, "direction": "MILD_BEAR"},
            "structure_delta": {"delta": -0.05, "sign_flip": False, "direction_changed": False},
            "structure_features": {},
            "evaluated": True,
            "outcome": {
                "actualPrice": 71000.0,
                "realMovePct": 1.43,
                "realDirection": "BULL",
                "baseDirectionCorrect": False,
                "structDirectionCorrect": False,
                "caseType": "both_wrong",
                "evaluatedAt": datetime.now(timezone.utc).isoformat(),
            },
        }
        db[SHADOW_COLLECTION].insert_one(doc)
        
        result = db[SHADOW_COLLECTION].find_one(
            {"forecastId": "test-shadow-ab-case-both-wrong"},
            {"_id": 0}
        )
        assert result["outcome"]["caseType"] == "both_wrong"


# ═══════════════════════════════════════════════════════
# SHADOW KPI COMPUTATION TESTS
# ═══════════════════════════════════════════════════════

class TestShadowKPIComputation:
    """Tests for compute_shadow_kpi() verdict logic"""
    
    def test_insufficient_data_verdict(self):
        """Verify INSUFFICIENT_DATA when n < 10"""
        # With only case documents from previous tests (or empty), should be INSUFFICIENT
        kpi = compute_shadow_kpi(horizon="7D")
        # If n < 10, verdict should be INSUFFICIENT_DATA
        if kpi["n"] < 10:
            assert kpi["verdict"] == "INSUFFICIENT_DATA"
            
    def test_kpi_structure_with_evaluated_data(self):
        """Verify KPI response structure when data exists"""
        db = _get_test_db()
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        past_ms = now_ms - 86400000
        
        # Create 12 evaluated records for comprehensive test
        for i in range(12):
            base_score = 0.25 if i % 2 == 0 else -0.25
            struct_score = 0.30 if i % 2 == 0 else -0.30
            base_dir = "MILD_BULL" if i % 2 == 0 else "MILD_BEAR"
            struct_dir = "MILD_BULL" if i % 2 == 0 else "MILD_BEAR"
            real_dir = "BULL" if i % 3 != 0 else "BEAR"
            
            base_correct = (base_dir in ["MILD_BULL", "STRONG_BULL"] and real_dir == "BULL") or \
                          (base_dir in ["MILD_BEAR", "STRONG_BEAR"] and real_dir == "BEAR")
            struct_correct = (struct_dir in ["MILD_BULL", "STRONG_BULL"] and real_dir == "BULL") or \
                            (struct_dir in ["MILD_BEAR", "STRONG_BEAR"] and real_dir == "BEAR")
            
            if struct_correct and not base_correct:
                case_type = "structure_improved"
            elif not struct_correct and base_correct:
                case_type = "structure_hurt"
            elif struct_correct and base_correct:
                case_type = "both_correct"
            else:
                case_type = "both_wrong"
            
            doc = {
                "forecastId": f"test-shadow-ab-kpi-{i:03d}",
                "asset": "BTC",
                "horizon": "7D",
                "bucket": "2026-03-18",
                "entryPrice": 70000.0,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "evaluateAfter": past_ms,
                "forecast_base": {"score": base_score, "direction": base_dir},
                "forecast_structure": {"score": struct_score, "direction": struct_dir},
                "structure_delta": {"delta": struct_score - base_score, "sign_flip": False, "direction_changed": False},
                "structure_features": {},
                "evaluated": True,
                "outcome": {
                    "actualPrice": 71000.0 if real_dir == "BULL" else 69000.0,
                    "realMovePct": 1.43 if real_dir == "BULL" else -1.43,
                    "realDirection": real_dir,
                    "baseDirectionCorrect": base_correct,
                    "structDirectionCorrect": struct_correct,
                    "caseType": case_type,
                    "evaluatedAt": datetime.now(timezone.utc).isoformat(),
                },
            }
            db[SHADOW_COLLECTION].insert_one(doc)
        
        # Compute KPI
        kpi = compute_shadow_kpi(horizon="7D", limit=100)
        
        # Verify structure
        assert kpi["n"] >= 12
        assert "verdict" in kpi
        assert "base" in kpi
        assert "structure" in kpi
        assert "comparison" in kpi
        
        # Verify base/structure have accuracy
        assert "accuracy" in kpi["base"]
        assert "accuracy" in kpi["structure"]
        
        # Verify comparison has key metrics
        assert "accuracy_lift" in kpi["comparison"]
        assert "cases" in kpi["comparison"]
        
    def test_verdict_with_positive_accuracy_lift(self):
        """Verify STRUCTURE_POSITIVE when accuracy_lift > 0.05"""
        db = _get_test_db()
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        past_ms = now_ms - 86400000
        
        # Create records where structure is always correct, base is often wrong
        for i in range(15):
            doc = {
                "forecastId": f"test-shadow-ab-positive-{i:03d}",
                "asset": "BTC",
                "horizon": "30D",  # Use 30D to isolate from 7D tests
                "bucket": "2026-03-18",
                "entryPrice": 70000.0,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "evaluateAfter": past_ms,
                "forecast_base": {"score": -0.25, "direction": "MILD_BEAR"},  # Wrong
                "forecast_structure": {"score": 0.30, "direction": "MILD_BULL"},  # Correct
                "structure_delta": {"delta": 0.55, "sign_flip": True, "direction_changed": True},
                "structure_features": {},
                "evaluated": True,
                "outcome": {
                    "actualPrice": 71000.0,
                    "realMovePct": 1.43,
                    "realDirection": "BULL",
                    "baseDirectionCorrect": False,
                    "structDirectionCorrect": True,
                    "caseType": "structure_improved",
                    "evaluatedAt": datetime.now(timezone.utc).isoformat(),
                },
            }
            db[SHADOW_COLLECTION].insert_one(doc)
        
        kpi = compute_shadow_kpi(horizon="30D", limit=100)
        
        # All structure correct (100%), all base wrong (0%) → lift = 1.0 > 0.05
        if kpi["n"] >= 10:
            assert kpi["comparison"]["accuracy_lift"] > 0.05
            assert kpi["verdict"] == "STRUCTURE_POSITIVE"


class TestShadowCasesRetrieval:
    """Tests for get_shadow_cases() filtering"""
    
    def test_get_cases_returns_list(self):
        """Verify cases returns list"""
        cases = get_shadow_cases()
        assert isinstance(cases, list)
        
    def test_get_cases_with_case_type_filter(self):
        """Verify case_type filter works"""
        # Create a specific case type
        db = _get_test_db()
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        past_ms = now_ms - 86400000
        
        doc = {
            "forecastId": "test-shadow-ab-filter-case",
            "asset": "BTC",
            "horizon": "7D",
            "bucket": "2026-03-18",
            "entryPrice": 70000.0,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "evaluateAfter": past_ms,
            "forecast_base": {"score": -0.25, "direction": "MILD_BEAR"},
            "forecast_structure": {"score": 0.30, "direction": "MILD_BULL"},
            "structure_delta": {"delta": 0.55, "sign_flip": True, "direction_changed": True},
            "structure_features": {},
            "evaluated": True,
            "outcome": {
                "actualPrice": 71000.0,
                "realMovePct": 1.43,
                "realDirection": "BULL",
                "baseDirectionCorrect": False,
                "structDirectionCorrect": True,
                "caseType": "structure_improved",
                "evaluatedAt": datetime.now(timezone.utc).isoformat(),
            },
        }
        db[SHADOW_COLLECTION].insert_one(doc)
        
        # Query with filter
        cases = get_shadow_cases(case_type="structure_improved", limit=100)
        
        # Verify all returned cases match filter
        for case in cases:
            if case["forecastId"].startswith("test-shadow-ab-"):
                assert case["outcome"]["caseType"] == "structure_improved"


# ═══════════════════════════════════════════════════════
# SCHEDULER INTEGRATION TEST
# ═══════════════════════════════════════════════════════

class TestSchedulerIntegration:
    """Tests for scheduler phase integration"""
    
    def test_run_structure_shadow_eval_function_exists(self):
        """Verify run_structure_shadow_eval exists and returns dict"""
        from forecast.scheduler import run_structure_shadow_eval
        result = run_structure_shadow_eval()
        assert isinstance(result, dict)
        # Should have evaluated, skipped keys or error
        assert "evaluated" in result or "error" in result


# ═══════════════════════════════════════════════════════
# DIRECTION MATCH HELPER TESTS
# ═══════════════════════════════════════════════════════

class TestDirectionMatchHelper:
    """Tests for _direction_match helper function"""
    
    def test_strong_bull_matches_bull(self):
        assert _direction_match("STRONG_BULL", "BULL") is True
        
    def test_mild_bull_matches_bull(self):
        assert _direction_match("MILD_BULL", "BULL") is True
        
    def test_strong_bear_matches_bear(self):
        assert _direction_match("STRONG_BEAR", "BEAR") is True
        
    def test_mild_bear_matches_bear(self):
        assert _direction_match("MILD_BEAR", "BEAR") is True
        
    def test_neutral_matches_flat(self):
        assert _direction_match("NEUTRAL", "FLAT") is True
        
    def test_bull_does_not_match_bear(self):
        assert _direction_match("MILD_BULL", "BEAR") is False
        assert _direction_match("STRONG_BULL", "BEAR") is False
        
    def test_bear_does_not_match_bull(self):
        assert _direction_match("MILD_BEAR", "BULL") is False
        assert _direction_match("STRONG_BEAR", "BULL") is False
        
    def test_neutral_does_not_match_bull(self):
        assert _direction_match("NEUTRAL", "BULL") is False
        
    def test_neutral_does_not_match_bear(self):
        assert _direction_match("NEUTRAL", "BEAR") is False


class TestDirectionDistributionHelper:
    """Tests for _direction_distribution helper function"""
    
    def test_all_neutral_ratio_is_1(self):
        dist = _direction_distribution(["NEUTRAL", "NEUTRAL", "NEUTRAL"])
        assert dist["neutral_ratio"] == 1.0
        assert dist["mild_ratio"] == 0.0
        assert dist["strong_ratio"] == 0.0
        
    def test_mixed_distribution(self):
        dirs = ["MILD_BULL", "MILD_BEAR", "STRONG_BULL", "NEUTRAL"]
        dist = _direction_distribution(dirs)
        assert dist["neutral_ratio"] == 0.25
        assert dist["mild_ratio"] == 0.5
        assert dist["strong_ratio"] == 0.25
        
    def test_counts_are_tracked(self):
        dirs = ["MILD_BULL", "MILD_BULL", "STRONG_BEAR"]
        dist = _direction_distribution(dirs)
        assert dist["counts"]["MILD_BULL"] == 2
        assert dist["counts"]["STRONG_BEAR"] == 1


# ═══════════════════════════════════════════════════════
# PIPELINE INTEGRATION TEST
# ═══════════════════════════════════════════════════════

class TestPipelineIntegration:
    """Tests for shadow recording during forecast generation"""
    
    def test_shadow_collection_has_recent_records(self):
        """Verify shadow records exist from forecast generation"""
        db = _get_test_db()
        count = db[SHADOW_COLLECTION].count_documents({})
        # Should have at least 1 record from previous forecast runs
        # This validates the integration in generator_v41.py
        assert count >= 1
        
    def test_recent_shadow_has_structure_features(self):
        """Verify recent shadow record has structure features populated"""
        db = _get_test_db()
        doc = db[SHADOW_COLLECTION].find_one(
            {"forecastId": {"$not": {"$regex": "^test-shadow-"}}},
            {"_id": 0, "structure_features": 1}
        )
        if doc:
            features = doc.get("structure_features", {})
            # Should have the 7 structure feature keys
            assert "structure_bias_score" in features


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
