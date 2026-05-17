"""
v4.1 Forecast Generator Tests
==============================
Tests for Exchange Forecast v4.1 Emergency Recovery features:
- 5-state direction classification (STRONG_BULL/MILD_BULL/NEUTRAL/MILD_BEAR/STRONG_BEAR)
- Legacy direction mapping (MILD_BEAR→SHORT, STRONG_BULL→LONG)
- Blended baselines (recent + long-term)
- Soft degradation (never forces NEUTRAL)
- Calibrated confidence (confidenceDirection, confidenceTarget)
- Audit payload with full traceability
- Configurable thresholds and suppression caps
"""

import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestV41ConfigConstants:
    """Test v4.1 configuration constants in v41_config.py"""
    
    def test_direction_thresholds_defined(self):
        """Verify direction thresholds are configured correctly"""
        from forecast.v41_config import DIRECTION_THRESHOLDS
        
        assert "strong_bull" in DIRECTION_THRESHOLDS
        assert "mild_bull" in DIRECTION_THRESHOLDS
        assert "mild_bear" in DIRECTION_THRESHOLDS
        assert "strong_bear" in DIRECTION_THRESHOLDS
        
        # Verify thresholds are symmetric and ordered
        assert DIRECTION_THRESHOLDS["strong_bull"] == 0.65
        assert DIRECTION_THRESHOLDS["mild_bull"] == 0.20
        assert DIRECTION_THRESHOLDS["mild_bear"] == -0.20
        assert DIRECTION_THRESHOLDS["strong_bear"] == -0.65
    
    def test_direction_classes_defined(self):
        """Verify all 5 direction classes are defined"""
        from forecast.v41_config import DIRECTION_CLASSES
        
        assert len(DIRECTION_CLASSES) == 5
        assert "STRONG_BULL" in DIRECTION_CLASSES
        assert "MILD_BULL" in DIRECTION_CLASSES
        assert "NEUTRAL" in DIRECTION_CLASSES
        assert "MILD_BEAR" in DIRECTION_CLASSES
        assert "STRONG_BEAR" in DIRECTION_CLASSES
    
    def test_regime_shrinkage_transition(self):
        """Verify TRANSITION shrinkage is 0.82 (not 0.6 as in v4.0)"""
        from forecast.v41_config import REGIME_SHRINKAGE
        
        assert REGIME_SHRINKAGE["TRANSITION"] == 0.82
        assert REGIME_SHRINKAGE["TREND"] == 1.00
        assert REGIME_SHRINKAGE["RANGE"] == 0.85
        assert REGIME_SHRINKAGE["RISK_OFF"] == 0.80
    
    def test_suppression_caps_enforced(self):
        """Verify suppression caps are configured correctly"""
        from forecast.v41_config import MAX_SCORE_REDUCTION, MAX_MOVE_REDUCTION, MAX_CONFIDENCE_REDUCTION
        
        assert MAX_SCORE_REDUCTION == 0.25
        assert MAX_MOVE_REDUCTION == 0.30
        assert MAX_CONFIDENCE_REDUCTION == 0.35
    
    def test_calibration_bins_present(self):
        """Verify calibration bins exist for all horizons"""
        from forecast.v41_config import CALIBRATION_BINS
        
        assert "7D" in CALIBRATION_BINS
        assert "30D" in CALIBRATION_BINS
        assert "24H" in CALIBRATION_BINS
        
        for horizon in ["7D", "30D", "24H"]:
            assert "direction" in CALIBRATION_BINS[horizon]
            assert "target" in CALIBRATION_BINS[horizon]
            # Verify bins are non-empty
            assert len(CALIBRATION_BINS[horizon]["direction"]) > 0
            assert len(CALIBRATION_BINS[horizon]["target"]) > 0
    
    def test_calibration_bins_monotonic(self):
        """Verify calibration bins are monotonically ordered"""
        from forecast.v41_config import CALIBRATION_BINS
        
        for horizon, bin_types in CALIBRATION_BINS.items():
            for bin_type, bins in bin_types.items():
                prev_high = 0.0
                for low, high, cal in bins:
                    assert low >= prev_high, f"{horizon}/{bin_type}: bins not monotonic at {low}"
                    assert low < high, f"{horizon}/{bin_type}: invalid range [{low}, {high})"
                    prev_high = high


class TestV41DirectionClassifier:
    """Test 5-state direction classifier function"""
    
    def test_classify_strong_bull(self):
        """Score >= 0.65 → STRONG_BULL"""
        from forecast.v41_config import classify_direction
        
        assert classify_direction(0.65) == "STRONG_BULL"
        assert classify_direction(0.80) == "STRONG_BULL"
        assert classify_direction(1.00) == "STRONG_BULL"
    
    def test_classify_mild_bull(self):
        """Score in [0.20, 0.65) → MILD_BULL"""
        from forecast.v41_config import classify_direction
        
        assert classify_direction(0.20) == "MILD_BULL"
        assert classify_direction(0.40) == "MILD_BULL"
        assert classify_direction(0.64) == "MILD_BULL"
    
    def test_classify_neutral(self):
        """Score in (-0.20, 0.20) → NEUTRAL"""
        from forecast.v41_config import classify_direction
        
        assert classify_direction(0.0) == "NEUTRAL"
        assert classify_direction(0.19) == "NEUTRAL"
        assert classify_direction(-0.19) == "NEUTRAL"
    
    def test_classify_mild_bear(self):
        """Score in (-0.65, -0.20] → MILD_BEAR"""
        from forecast.v41_config import classify_direction
        
        assert classify_direction(-0.20) == "MILD_BEAR"
        assert classify_direction(-0.40) == "MILD_BEAR"
        assert classify_direction(-0.64) == "MILD_BEAR"
    
    def test_classify_strong_bear(self):
        """Score <= -0.65 → STRONG_BEAR"""
        from forecast.v41_config import classify_direction
        
        assert classify_direction(-0.65) == "STRONG_BEAR"
        assert classify_direction(-0.80) == "STRONG_BEAR"
        assert classify_direction(-1.00) == "STRONG_BEAR"


class TestV41CalibrateConfidence:
    """Test confidence calibration function"""
    
    def test_calibrate_direction_7d(self):
        """Verify calibration returns correct bucket value for 7D direction"""
        from forecast.v41_config import calibrate_confidence
        
        # Raw 0.0-0.10 → 0.45
        assert calibrate_confidence(0.05, "7D", "direction") == 0.45
        # Raw 0.30-0.40 → 0.62
        assert calibrate_confidence(0.35, "7D", "direction") == 0.62
    
    def test_calibrate_target_30d(self):
        """Verify calibration returns correct bucket value for 30D target"""
        from forecast.v41_config import calibrate_confidence
        
        # Raw 0.0-0.10 → 0.22
        assert calibrate_confidence(0.05, "30D", "target") == 0.22
    
    def test_calibrate_fallback(self):
        """Verify fallback for unknown horizon"""
        from forecast.v41_config import calibrate_confidence
        
        result = calibrate_confidence(0.5, "UNKNOWN", "direction")
        assert 0.10 <= result <= 0.85


class TestV41LegacyDirectionMapping:
    """Test mapping from 5-state to legacy 3-state direction"""
    
    def test_strong_bull_to_long(self):
        """STRONG_BULL → LONG"""
        from forecast.generator_v41 import _to_legacy_direction
        assert _to_legacy_direction("STRONG_BULL") == "LONG"
    
    def test_mild_bull_to_long(self):
        """MILD_BULL → LONG"""
        from forecast.generator_v41 import _to_legacy_direction
        assert _to_legacy_direction("MILD_BULL") == "LONG"
    
    def test_neutral_to_neutral(self):
        """NEUTRAL → NEUTRAL"""
        from forecast.generator_v41 import _to_legacy_direction
        assert _to_legacy_direction("NEUTRAL") == "NEUTRAL"
    
    def test_mild_bear_to_short(self):
        """MILD_BEAR → SHORT"""
        from forecast.generator_v41 import _to_legacy_direction
        assert _to_legacy_direction("MILD_BEAR") == "SHORT"
    
    def test_strong_bear_to_short(self):
        """STRONG_BEAR → SHORT"""
        from forecast.generator_v41 import _to_legacy_direction
        assert _to_legacy_direction("STRONG_BEAR") == "SHORT"


class TestV41KPIEndpoint:
    """Test KPI endpoint for recovery metrics"""
    
    def test_kpi_endpoint_returns_ok(self):
        """GET /api/forecast/kpi returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/forecast/kpi", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_kpi_has_current_metrics(self):
        """KPI response has current metrics for all horizons"""
        response = requests.get(f"{BASE_URL}/api/forecast/kpi", timeout=30)
        data = response.json()
        
        assert "current" in data
        current = data["current"]
        
        for horizon in ["7D", "30D", "24H"]:
            assert horizon in current, f"Missing horizon {horizon} in current metrics"
            metrics = current[horizon]
            assert "total" in metrics
            assert "evaluated" in metrics
            assert "neutralRatio" in metrics
            assert "directionDistribution" in metrics
    
    def test_kpi_has_legacy_baseline(self):
        """KPI response has legacy baseline for comparison"""
        response = requests.get(f"{BASE_URL}/api/forecast/kpi", timeout=30)
        data = response.json()
        
        assert "legacy" in data
        legacy = data["legacy"]
        
        for horizon in ["7D", "30D"]:
            assert horizon in legacy, f"Missing horizon {horizon} in legacy baseline"
    
    def test_kpi_shows_v41_model_version(self):
        """KPI shows v4.1.0 in model versions breakdown"""
        response = requests.get(f"{BASE_URL}/api/forecast/kpi", timeout=30)
        data = response.json()
        
        found_v41 = False
        for horizon, metrics in data.get("current", {}).items():
            if "v4.1.0" in metrics.get("modelVersions", {}):
                found_v41 = True
                break
        
        assert found_v41, "v4.1.0 not found in any horizon's modelVersions"
    
    def test_kpi_shows_directional_recovery(self):
        """30D horizon shows MILD_BEAR in direction distribution (directional recovery)"""
        response = requests.get(f"{BASE_URL}/api/forecast/kpi", timeout=30)
        data = response.json()
        
        dist_30d = data.get("current", {}).get("30D", {}).get("directionDistribution", {})
        
        # Check if MILD_BEAR appears (proof of directional call)
        has_mild_bear = "MILD_BEAR" in dist_30d
        assert has_mild_bear, f"MILD_BEAR not found in 30D distribution: {dist_30d}"


class TestV41ForecastInDatabase:
    """Test v4.1 forecasts stored in database have correct structure"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database connection"""
        from pymongo import MongoClient
        import os
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
        db_name = os.environ.get("DB_NAME", "intelligence_engine")
        self.db = MongoClient(mongo_url)[db_name]
        self.col = self.db["exchange_forecasts"]
    
    def test_v41_forecasts_exist(self):
        """v4.1.0 forecasts exist in database"""
        count = self.col.count_documents({"modelVersion": "v4.1.0"})
        assert count >= 1, "No v4.1.0 forecasts found in database"
    
    def test_v41_has_direction_class_field(self):
        """v4.1 forecasts have directionClass field (5-state)"""
        doc = self.col.find_one({"modelVersion": "v4.1.0"}, {"_id": 0})
        assert doc is not None, "No v4.1.0 forecast found"
        assert "directionClass" in doc, "directionClass field missing"
        assert doc["directionClass"] in ["STRONG_BULL", "MILD_BULL", "NEUTRAL", "MILD_BEAR", "STRONG_BEAR"]
    
    def test_v41_30d_has_mild_bear(self):
        """30D v4.1 forecast has directionClass=MILD_BEAR (proving directional recovery)"""
        doc = self.col.find_one({"modelVersion": "v4.1.0", "horizon": "30D"}, {"_id": 0})
        assert doc is not None, "No 30D v4.1.0 forecast found"
        assert doc.get("directionClass") == "MILD_BEAR", f"30D directionClass is {doc.get('directionClass')}, expected MILD_BEAR"
    
    def test_v41_maps_direction_correctly(self):
        """directionClass maps to legacy direction correctly"""
        doc = self.col.find_one({"modelVersion": "v4.1.0", "horizon": "30D"}, {"_id": 0})
        assert doc is not None
        
        dc = doc.get("directionClass")
        legacy = doc.get("direction")
        
        if dc in ("STRONG_BULL", "MILD_BULL"):
            assert legacy == "LONG", f"Expected LONG for {dc}, got {legacy}"
        elif dc in ("STRONG_BEAR", "MILD_BEAR"):
            assert legacy == "SHORT", f"Expected SHORT for {dc}, got {legacy}"
        else:
            assert legacy == "NEUTRAL", f"Expected NEUTRAL for {dc}, got {legacy}"
    
    def test_v41_has_confidence_direction(self):
        """v4.1 forecasts have confidenceDirection field"""
        doc = self.col.find_one({"modelVersion": "v4.1.0"}, {"_id": 0})
        assert doc is not None
        assert "confidenceDirection" in doc, "confidenceDirection field missing"
        assert isinstance(doc["confidenceDirection"], (int, float))
        assert 0 <= doc["confidenceDirection"] <= 1
    
    def test_v41_has_confidence_target(self):
        """v4.1 forecasts have confidenceTarget field"""
        doc = self.col.find_one({"modelVersion": "v4.1.0"}, {"_id": 0})
        assert doc is not None
        assert "confidenceTarget" in doc, "confidenceTarget field missing"
        assert isinstance(doc["confidenceTarget"], (int, float))
        assert 0 <= doc["confidenceTarget"] <= 1
    
    def test_v41_has_degraded_flag(self):
        """v4.1 forecasts have degraded field"""
        doc = self.col.find_one({"modelVersion": "v4.1.0"}, {"_id": 0})
        assert doc is not None
        assert "degraded" in doc, "degraded field missing"
        assert isinstance(doc["degraded"], bool)
    
    def test_v41_soft_degradation_does_not_force_neutral(self):
        """Soft degradation applies but does NOT force NEUTRAL"""
        # 30D is degraded but still has MILD_BEAR direction
        doc = self.col.find_one({"modelVersion": "v4.1.0", "horizon": "30D"}, {"_id": 0})
        assert doc is not None
        
        degraded = doc.get("degraded", False)
        direction_class = doc.get("directionClass")
        
        # If degraded, direction should still be MILD_BEAR (not forced to NEUTRAL)
        if degraded:
            assert direction_class == "MILD_BEAR", f"Degraded forecast was forced to {direction_class}, should be MILD_BEAR"


class TestV41AuditPayload:
    """Test v4.1 audit payload structure and contents"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database connection"""
        from pymongo import MongoClient
        import os
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
        db_name = os.environ.get("DB_NAME", "intelligence_engine")
        self.db = MongoClient(mongo_url)[db_name]
        self.col = self.db["exchange_forecasts"]
    
    def test_v41_has_audit_field(self):
        """v4.1 forecasts have audit field"""
        doc = self.col.find_one({"modelVersion": "v4.1.0"}, {"_id": 0})
        assert doc is not None
        assert "audit" in doc, "audit field missing"
        assert isinstance(doc["audit"], dict)
    
    def test_audit_has_version(self):
        """Audit payload includes version marker"""
        doc = self.col.find_one({"modelVersion": "v4.1.0"}, {"_id": 0})
        audit = doc.get("audit", {})
        assert audit.get("v") == "4.1"
    
    def test_audit_has_score_raw_and_final(self):
        """Audit payload includes scoreRaw and scoreFinal"""
        doc = self.col.find_one({"modelVersion": "v4.1.0"}, {"_id": 0})
        audit = doc.get("audit", {})
        
        assert "scoreRaw" in audit, "scoreRaw missing from audit"
        assert "scoreFinal" in audit, "scoreFinal missing from audit"
        assert isinstance(audit["scoreRaw"], (int, float))
        assert isinstance(audit["scoreFinal"], (int, float))
    
    def test_audit_has_regime(self):
        """Audit payload includes regime"""
        doc = self.col.find_one({"modelVersion": "v4.1.0"}, {"_id": 0})
        audit = doc.get("audit", {})
        
        assert "regime" in audit, "regime missing from audit"
        assert audit["regime"] in ["TREND", "RANGE", "RISK_OFF", "TRANSITION"]
    
    def test_audit_has_penalties(self):
        """Audit payload includes penalties array"""
        doc = self.col.find_one({"modelVersion": "v4.1.0"}, {"_id": 0})
        audit = doc.get("audit", {})
        
        assert "penalties" in audit, "penalties missing from audit"
        assert isinstance(audit["penalties"], list)
    
    def test_audit_has_baseline_source(self):
        """Audit payload includes baselineSource"""
        doc = self.col.find_one({"modelVersion": "v4.1.0"}, {"_id": 0})
        audit = doc.get("audit", {})
        
        assert "baselineSource" in audit, "baselineSource missing from audit"
        assert audit["baselineSource"] in ["blended", "long_only", "fallback", "unknown"]
    
    def test_audit_has_recent_samples(self):
        """Audit payload includes recentSamples count"""
        doc = self.col.find_one({"modelVersion": "v4.1.0"}, {"_id": 0})
        audit = doc.get("audit", {})
        
        assert "recentSamples" in audit, "recentSamples missing from audit"
        assert isinstance(audit["recentSamples"], int)
    
    def test_audit_blended_baseline_for_30d(self):
        """30D forecast uses blended baseline with recentSamples > 0"""
        doc = self.col.find_one({"modelVersion": "v4.1.0", "horizon": "30D"}, {"_id": 0})
        audit = doc.get("audit", {})
        
        baseline_source = audit.get("baselineSource")
        recent_samples = audit.get("recentSamples", 0)
        
        assert baseline_source == "blended", f"30D baselineSource is {baseline_source}, expected 'blended'"
        assert recent_samples > 0, f"30D recentSamples is {recent_samples}, expected > 0"


class TestV41Evaluator:
    """Test evaluator handles both legacy and 5-state directions"""
    
    def test_evaluator_handles_bullish_classes(self):
        """Evaluator recognizes STRONG_BULL and MILD_BULL as bullish"""
        from forecast.evaluator import BULLISH_CLASSES
        
        assert "LONG" in BULLISH_CLASSES
        assert "STRONG_BULL" in BULLISH_CLASSES
        assert "MILD_BULL" in BULLISH_CLASSES
    
    def test_evaluator_handles_bearish_classes(self):
        """Evaluator recognizes STRONG_BEAR and MILD_BEAR as bearish"""
        from forecast.evaluator import BEARISH_CLASSES
        
        assert "SHORT" in BEARISH_CLASSES
        assert "STRONG_BEAR" in BEARISH_CLASSES
        assert "MILD_BEAR" in BEARISH_CLASSES


class TestV41SchedulerIntegration:
    """Test scheduler imports generator_v41 correctly"""
    
    def test_scheduler_uses_v41_generator(self):
        """Scheduler imports generate_forecast from generator_v41"""
        from forecast.scheduler import generate_forecast
        from forecast.generator_v41 import generate_forecast as v41_generate
        
        # Both should reference the same function
        assert generate_forecast.__module__ == "forecast.generator_v41"


class TestV41ForecastHealthEndpoint:
    """Test forecast health endpoint works"""
    
    def test_health_endpoint_returns_ok(self):
        """GET /api/forecast/health returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/forecast/health", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_health_has_horizon_stats(self):
        """Health endpoint shows stats per horizon"""
        response = requests.get(f"{BASE_URL}/api/forecast/health", timeout=30)
        data = response.json()
        
        assert "horizons" in data
        for horizon in ["24H", "7D", "30D"]:
            assert horizon in data["horizons"]


class TestV41AdminStatusEndpoint:
    """Test admin status endpoint"""
    
    def test_admin_status_returns_ok(self):
        """GET /api/forecast/admin/status returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/forecast/admin/status", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_admin_status_shows_last_run(self):
        """Admin status shows last run info"""
        response = requests.get(f"{BASE_URL}/api/forecast/admin/status", timeout=30)
        data = response.json()
        
        assert "lastRun" in data
        last_run = data["lastRun"]
        if last_run:
            assert "runId" in last_run
            assert "ts" in last_run


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
