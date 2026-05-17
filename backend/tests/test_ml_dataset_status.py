"""
ML Dataset Status Tests - Block 5.A.1
======================================
Tests for:
1. GET /api/ml-overlay/dataset-status endpoint
2. ML dataset section in Intelligence Console aggregator
3. sizeFactor floor validation (max 0.3)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestMLDatasetStatusEndpoint:
    """Tests for /api/ml-overlay/dataset-status endpoint"""
    
    def test_dataset_status_returns_ok(self):
        """Endpoint returns ok=true with data object"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/dataset-status?asset=BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
        print(f"PASS: /api/ml-overlay/dataset-status returns ok=true")
    
    def test_dataset_status_has_usable_for_ml(self):
        """Response has usable_for_ml count"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/dataset-status?asset=BTC")
        data = response.json()["data"]
        assert "usable_for_ml" in data
        assert isinstance(data["usable_for_ml"], int)
        print(f"PASS: usable_for_ml = {data['usable_for_ml']}")
    
    def test_dataset_status_has_progress_pct(self):
        """Response has progress_pct"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/dataset-status?asset=BTC")
        data = response.json()["data"]
        assert "progress_pct" in data
        assert 0 <= data["progress_pct"] <= 100
        print(f"PASS: progress_pct = {data['progress_pct']}")
    
    def test_dataset_status_has_quality_metrics(self):
        """Response has quality object with required fields"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/dataset-status?asset=BTC")
        data = response.json()["data"]
        assert "quality" in data
        quality = data["quality"]
        assert "entropy_variance" in quality
        assert "uncertainty_variance" in quality
        assert "regime_diversity" in quality
        print(f"PASS: quality metrics present - entropy_var={quality['entropy_variance']}, uncertainty_var={quality['uncertainty_variance']}, regime_div={quality['regime_diversity']}")
    
    def test_dataset_status_has_readiness(self):
        """Response has readiness object with status and blockers"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/dataset-status?asset=BTC")
        data = response.json()["data"]
        assert "readiness" in data
        readiness = data["readiness"]
        assert "ready" in readiness
        assert "status" in readiness
        assert "blockers" in readiness
        print(f"PASS: readiness - ready={readiness['ready']}, status={readiness['status']}, blockers_count={len(readiness['blockers'])}")
    
    def test_dataset_status_blocked_with_no_usable_data(self):
        """Status should be BLOCKED when no usable data (expected behavior)"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/dataset-status?asset=BTC")
        data = response.json()["data"]
        
        # Currently expected to have 0 usable (all forecasts are v4.0.0-bootstrap without audit)
        if data["usable_for_ml"] == 0:
            assert data["readiness"]["status"] == "BLOCKED"
            assert len(data["readiness"]["blockers"]) > 0
            print(f"PASS: Status BLOCKED with blockers when usable_for_ml=0")
        else:
            # If there's usable data, status could be READY
            print(f"INFO: usable_for_ml > 0, status={data['readiness']['status']}")
    
    def test_dataset_status_quality_reports_no_usable_data(self):
        """Quality reason should be 'no_usable_data' when 0 usable rows"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/dataset-status?asset=BTC")
        data = response.json()["data"]
        
        if data["usable_for_ml"] == 0:
            assert data["quality"].get("reason") == "no_usable_data"
            print(f"PASS: quality.reason = 'no_usable_data'")
        else:
            print(f"INFO: usable_for_ml > 0, quality has real metrics")
    
    def test_dataset_status_has_thresholds(self):
        """Response has minimum and ideal thresholds"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/dataset-status?asset=BTC")
        data = response.json()["data"]
        assert "minimum_threshold" in data
        assert "ideal_threshold" in data
        assert data["minimum_threshold"] == 100
        assert data["ideal_threshold"] == 200
        print(f"PASS: thresholds - minimum={data['minimum_threshold']}, ideal={data['ideal_threshold']}")
    
    def test_dataset_status_has_breakdown(self):
        """Response has full breakdown (total_evaluated, v4_total, with_full_audit, etc.)"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/dataset-status?asset=BTC")
        data = response.json()["data"]
        assert "total_evaluated" in data
        assert "v4_total" in data
        assert "with_full_audit" in data
        assert "with_outcome" in data
        assert "days_covered" in data
        print(f"PASS: breakdown - total_evaluated={data['total_evaluated']}, v4_total={data['v4_total']}, with_full_audit={data['with_full_audit']}")


class TestIntelligenceConsoleMLDataset:
    """Tests for ML dataset section in Intelligence Console aggregator"""
    
    def test_console_includes_ml_dataset_section(self):
        """Console aggregator includes ml_dataset section"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/console?range=all")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "ml_dataset" in data["data"]
        print(f"PASS: /api/admin/intelligence/console includes ml_dataset section")
    
    def test_console_ml_dataset_has_expected_fields(self):
        """ml_dataset in console has the same fields as dedicated endpoint"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/console?range=all")
        data = response.json()["data"]["ml_dataset"]
        
        # Check key fields
        assert "usable_for_ml" in data
        assert "progress_pct" in data
        assert "quality" in data
        assert "readiness" in data
        print(f"PASS: ml_dataset has usable_for_ml, progress_pct, quality, readiness")
    
    def test_console_still_has_6_original_sections(self):
        """Console still includes all 6 original sections"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/console?range=all")
        data = response.json()["data"]
        
        original_sections = ["overview", "phases", "regimes", "scenarios", "drift", "tactical"]
        for section in original_sections:
            assert section in data, f"Missing section: {section}"
        print(f"PASS: All 6 original sections present: {original_sections}")


class TestSizeFactorFloor:
    """Tests for sizeFactor floor at max 0.3"""
    
    def test_drift_adjustments_defensive_respects_floor(self):
        """Defensive mode with high drift still respects 0.3 floor"""
        import sys
        sys.path.insert(0, "/app/backend")
        from drift.drift_execution_hook import compute_drift_adjustments
        
        result = compute_drift_adjustments(0.95, 0.5)
        assert result["size_mult"] >= 0.3
        assert result["mode"] == "defensive"
        print(f"PASS: drift=0.95, cat=0.5 => size_mult={result['size_mult']} >= 0.3")
    
    def test_drift_adjustments_extreme_values_respect_floor(self):
        """Extreme values (1.0, 1.0) still respect 0.3 floor"""
        import sys
        sys.path.insert(0, "/app/backend")
        from drift.drift_execution_hook import compute_drift_adjustments
        
        result = compute_drift_adjustments(1.0, 1.0)
        assert result["size_mult"] >= 0.3
        print(f"PASS: drift=1.0, cat=1.0 => size_mult={result['size_mult']} >= 0.3")
    
    def test_drift_adjustments_normal_mode_no_reduction(self):
        """Low drift returns size_mult=1.0"""
        import sys
        sys.path.insert(0, "/app/backend")
        from drift.drift_execution_hook import compute_drift_adjustments
        
        result = compute_drift_adjustments(0.2, 0.1)
        assert result["size_mult"] == 1.0
        assert result["mode"] == "normal"
        print(f"PASS: drift=0.2, cat=0.1 => size_mult={result['size_mult']}, mode=normal")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
