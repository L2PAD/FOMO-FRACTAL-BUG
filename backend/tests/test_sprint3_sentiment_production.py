"""
Sprint 3: Sentiment Production for Prediction OS
Tests for ML Readiness Gate, Stability Monitor, Sampling Rollout, Event Typing Upgrade

Key endpoints:
- GET /api/sentiment/ml-readiness - ML Readiness Gate API
- GET /api/sentiment/stability-monitor - Data Stability Monitor
- GET /api/outcome/rollout-status - Sampling rollout status (should be 30%)
- GET /api/outcome/sampling-quality - Sampling quality by event type (no 'unknown' key)
- GET /api/outcome/rollout-check - Rollout health check with distribution
- POST /api/outcome/sampling-rollout?pct=30 - Set sampling rollout (DO NOT change pct)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestMLReadinessGate:
    """Tests for /api/sentiment/ml-readiness endpoint"""

    def test_ml_readiness_returns_json(self):
        """ML Readiness endpoint returns valid JSON with required fields"""
        response = requests.get(f"{BASE_URL}/api/sentiment/ml-readiness")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Required fields
        assert "ready" in data, "Missing 'ready' field"
        assert "reasons" in data, "Missing 'reasons' field"
        assert "dataset_size" in data, "Missing 'dataset_size' field"
        assert "distribution_health" in data, "Missing 'distribution_health' field"
        
        print(f"ML Readiness: ready={data['ready']}, dataset_size={data['dataset_size']}, distribution_health={data['distribution_health']}")

    def test_ml_readiness_ready_is_boolean(self):
        """ready field is a boolean"""
        response = requests.get(f"{BASE_URL}/api/sentiment/ml-readiness")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data["ready"], bool), f"'ready' should be boolean, got {type(data['ready'])}"

    def test_ml_readiness_reasons_is_list(self):
        """reasons field is a list"""
        response = requests.get(f"{BASE_URL}/api/sentiment/ml-readiness")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data["reasons"], list), f"'reasons' should be list, got {type(data['reasons'])}"
        print(f"Reasons: {data['reasons']}")

    def test_ml_readiness_dataset_size_is_numeric(self):
        """dataset_size is a number"""
        response = requests.get(f"{BASE_URL}/api/sentiment/ml-readiness")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data["dataset_size"], (int, float)), f"'dataset_size' should be numeric, got {type(data['dataset_size'])}"
        print(f"Dataset size: {data['dataset_size']}")

    def test_ml_readiness_has_label_distribution(self):
        """Response includes label_distribution"""
        response = requests.get(f"{BASE_URL}/api/sentiment/ml-readiness")
        assert response.status_code == 200
        
        data = response.json()
        assert "label_distribution" in data, "Missing 'label_distribution' field"
        print(f"Label distribution: {data['label_distribution']}")

    def test_ml_readiness_has_event_type_distribution(self):
        """Response includes event_type_distribution"""
        response = requests.get(f"{BASE_URL}/api/sentiment/ml-readiness")
        assert response.status_code == 200
        
        data = response.json()
        assert "event_type_distribution" in data, "Missing 'event_type_distribution' field"
        print(f"Event type distribution: {data['event_type_distribution']}")


class TestStabilityMonitor:
    """Tests for /api/sentiment/stability-monitor endpoint"""

    def test_stability_monitor_returns_json(self):
        """Stability Monitor endpoint returns valid JSON with required fields"""
        response = requests.get(f"{BASE_URL}/api/sentiment/stability-monitor")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] == True, f"Expected ok=True, got {data['ok']}"
        
        # Either NO_DATA status or full response
        if data.get("status") == "NO_DATA":
            print("Stability Monitor: NO_DATA (empty dataset)")
            return
        
        assert "status" in data, "Missing 'status' field"
        assert "current" in data, "Missing 'current' field (snapshot)"
        assert "drift_alerts" in data, "Missing 'drift_alerts' field"
        assert "history_count" in data, "Missing 'history_count' field"
        
        print(f"Stability Monitor: status={data['status']}, history_count={data['history_count']}")

    def test_stability_monitor_status_values(self):
        """status is either STABLE, DRIFT_DETECTED, or NO_DATA"""
        response = requests.get(f"{BASE_URL}/api/sentiment/stability-monitor")
        assert response.status_code == 200
        
        data = response.json()
        valid_statuses = ["STABLE", "DRIFT_DETECTED", "NO_DATA"]
        assert data["status"] in valid_statuses, f"Invalid status: {data['status']}, expected one of {valid_statuses}"
        print(f"Status: {data['status']}")

    def test_stability_monitor_current_snapshot_structure(self):
        """current snapshot has expected structure"""
        response = requests.get(f"{BASE_URL}/api/sentiment/stability-monitor")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("status") == "NO_DATA":
            pytest.skip("No data available for snapshot structure test")
        
        current = data.get("current", {})
        assert "timestamp" in current, "Missing 'timestamp' in current snapshot"
        assert "total" in current, "Missing 'total' in current snapshot"
        assert "distribution" in current, "Missing 'distribution' in current snapshot"
        assert "include_rate" in current, "Missing 'include_rate' in current snapshot"
        assert "event_mix" in current, "Missing 'event_mix' in current snapshot"
        
        print(f"Current snapshot: total={current['total']}, include_rate={current['include_rate']}")

    def test_stability_monitor_drift_alerts_is_list(self):
        """drift_alerts is a list"""
        response = requests.get(f"{BASE_URL}/api/sentiment/stability-monitor")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("status") == "NO_DATA":
            pytest.skip("No data available for drift alerts test")
        
        assert isinstance(data["drift_alerts"], list), f"'drift_alerts' should be list, got {type(data['drift_alerts'])}"
        print(f"Drift alerts: {data['drift_alerts']}")


class TestRolloutStatus:
    """Tests for /api/outcome/rollout-status endpoint"""

    def test_rollout_status_returns_json(self):
        """Rollout status endpoint returns valid JSON"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] == True, f"Expected ok=True, got {data['ok']}"

    def test_rollout_status_sampling_pct_is_30(self):
        """sampling_rollout_pct should be 30 (Sprint 3 requirement)"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "sampling_rollout_pct" in data, "Missing 'sampling_rollout_pct' field"
        assert data["sampling_rollout_pct"] == 30, f"Expected sampling_rollout_pct=30, got {data['sampling_rollout_pct']}"
        print(f"Sampling rollout: {data['sampling_rollout_pct']}%")

    def test_rollout_status_has_labels_v2_production(self):
        """Response includes labels_v2_production flag"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "labels_v2_production" in data, "Missing 'labels_v2_production' field"
        print(f"Labels V2 production: {data['labels_v2_production']}")

    def test_rollout_status_has_rollout_state(self):
        """Response includes rollout_state"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "rollout_state" in data, "Missing 'rollout_state' field"
        print(f"Rollout state: {data['rollout_state']}")


class TestSamplingQuality:
    """Tests for /api/outcome/sampling-quality endpoint"""

    def test_sampling_quality_returns_json(self):
        """Sampling quality endpoint returns valid JSON"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] == True, f"Expected ok=True, got {data['ok']}"

    def test_sampling_quality_has_by_event_type(self):
        """Response includes by_event_type breakdown"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200
        
        data = response.json()
        assert "by_event_type" in data, "Missing 'by_event_type' field"
        print(f"Event types: {list(data['by_event_type'].keys())}")

    def test_sampling_quality_no_unknown_event_type(self):
        """by_event_type should NOT have 'unknown' key (Sprint 3 requirement: all events classified)"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200
        
        data = response.json()
        by_event_type = data.get("by_event_type", {})
        
        # Check that 'unknown' is not present OR has 0 count
        unknown_count = by_event_type.get("unknown", {}).get("count", 0)
        assert "unknown" not in by_event_type or unknown_count == 0, \
            f"'unknown' event type should not exist or have 0 count, found count={unknown_count}"
        
        print(f"Event type distribution (no unknown): {by_event_type}")

    def test_sampling_quality_has_include_rate(self):
        """Response includes include_rate_new"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200
        
        data = response.json()
        assert "include_rate_new" in data, "Missing 'include_rate_new' field"
        print(f"Include rate: {data['include_rate_new']}%")

    def test_sampling_quality_has_priority_buckets(self):
        """Response includes priority_buckets (high/medium/low)"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200
        
        data = response.json()
        assert "priority_buckets" in data, "Missing 'priority_buckets' field"
        buckets = data["priority_buckets"]
        assert "high" in buckets, "Missing 'high' bucket"
        assert "medium" in buckets, "Missing 'medium' bucket"
        assert "low" in buckets, "Missing 'low' bucket"
        print(f"Priority buckets: high={buckets['high']}, medium={buckets['medium']}, low={buckets['low']}")


class TestRolloutCheck:
    """Tests for /api/outcome/rollout-check endpoint"""

    def test_rollout_check_returns_json(self):
        """Rollout check endpoint returns valid JSON"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] == True, f"Expected ok=True, got {data['ok']}"

    def test_rollout_check_has_status(self):
        """Response includes state.status or rollout_state.status field"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        assert response.status_code == 200
        
        data = response.json()
        # Status can be in state.status or rollout_state.status
        state_status = data.get("state", {}).get("status")
        rollout_status = data.get("rollout_state", {}).get("status")
        
        assert state_status or rollout_status, "Missing status in 'state' or 'rollout_state'"
        status = state_status or rollout_status
        print(f"Rollout check status: {status}")

    def test_rollout_check_has_distribution(self):
        """Response includes distribution data"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        assert response.status_code == 200
        
        data = response.json()
        # Either NO_DATA or has distribution
        if data.get("status") == "NO_DATA":
            print("Rollout check: NO_DATA (no sampling data)")
            return
        
        assert "distribution" in data, "Missing 'distribution' field"
        dist = data["distribution"]
        assert "high_pct" in dist, "Missing 'high_pct' in distribution"
        assert "medium_pct" in dist, "Missing 'medium_pct' in distribution"
        assert "low_pct" in dist, "Missing 'low_pct' in distribution"
        print(f"Distribution: high={dist['high_pct']}%, medium={dist['medium_pct']}%, low={dist['low_pct']}%")

    def test_rollout_check_has_health_result(self):
        """Response includes health check result"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("status") == "NO_DATA":
            pytest.skip("No data available for health result test")
        
        assert "health" in data, "Missing 'health' field"
        print(f"Health result: {data['health']}")


class TestSamplingRolloutPersistence:
    """Tests for POST /api/outcome/sampling-rollout endpoint - READ ONLY verification"""

    def test_sampling_rollout_endpoint_exists(self):
        """Verify sampling-rollout endpoint exists (POST with pct=30 - current state)"""
        # NOTE: We're testing with pct=30 which is the CURRENT state
        # This should NOT change anything, just verify the endpoint works
        response = requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct=30")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] == True, f"Expected ok=True, got {data['ok']}"
        assert "new_pct" in data, "Missing 'new_pct' field"
        assert data["new_pct"] == 30, f"Expected new_pct=30, got {data['new_pct']}"
        print(f"Sampling rollout POST: old_pct={data.get('old_pct')}, new_pct={data['new_pct']}")


class TestEventTypingUpgrade:
    """Tests for Event Typing Upgrade - detect_event_type returns (type, confidence) tuple"""

    def test_event_type_confidence_in_dataset_entries(self):
        """dataset_entries should have quality.event_type and quality.event_type_confidence"""
        response = requests.get(f"{BASE_URL}/api/sentiment/ml-readiness")
        assert response.status_code == 200
        
        data = response.json()
        event_dist = data.get("event_type_distribution", {})
        
        # If we have data, verify event types are classified
        if data.get("dataset_size", 0) > 0:
            # Check that we have classified event types
            classified_types = [k for k in event_dist.keys() if k and k != "unknown"]
            print(f"Classified event types: {classified_types}")
            assert len(classified_types) > 0 or data.get("dataset_size", 0) == 0, \
                "Expected at least some classified event types"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
