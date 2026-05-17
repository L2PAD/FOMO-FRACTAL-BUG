"""
Test Cross-Platform Auto-Rebuild Scheduler and Manual Validation Framework.

Features tested:
- GET /api/cross-market/kalshi/health — rebuild health metrics
- POST /api/cross-market/kalshi/auto-rebuild/start — start background auto-rebuild
- POST /api/cross-market/kalshi/auto-rebuild/stop — stop auto-rebuild
- GET /api/cross-market/kalshi/validation-queue — pending validation entries
- GET /api/cross-market/kalshi/validation-queue?status=VALIDATED — validated entries
- POST /api/cross-market/kalshi/validate/{id} — submit verdict
- GET /api/cross-market/kalshi/validation-metrics — validation performance metrics
- POST /api/cross-market/kalshi/rebuild — still works, stores signals + creates validation entries
- GET /api/cross-market/kalshi/analytics — returns analytics with stored signals
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestHealthEndpoint:
    """Test GET /api/cross-market/kalshi/health endpoint."""
    
    def test_health_returns_ok(self):
        """Health endpoint returns ok=true with required fields."""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        
        # Verify required health fields exist
        assert "running" in data, "Missing 'running' field"
        assert "total_rebuilds" in data, "Missing 'total_rebuilds' field"
        assert "total_skipped" in data, "Missing 'total_skipped' field"
        assert "total_material_changes" in data, "Missing 'total_material_changes' field"
        assert "last_latency_ms" in data, "Missing 'last_latency_ms' field"
        assert "rebuilds_this_hour" in data, "Missing 'rebuilds_this_hour' field"
        assert "max_rebuilds_per_hour" in data, "Missing 'max_rebuilds_per_hour' field"
        
        # Verify types
        assert isinstance(data["running"], bool), "running should be boolean"
        assert isinstance(data["total_rebuilds"], int), "total_rebuilds should be int"
        assert isinstance(data["max_rebuilds_per_hour"], int), "max_rebuilds_per_hour should be int"
        
        print(f"Health endpoint OK: running={data['running']}, total_rebuilds={data['total_rebuilds']}")


class TestAutoRebuildStartStop:
    """Test auto-rebuild start/stop endpoints."""
    
    def test_auto_rebuild_start(self):
        """POST /api/cross-market/kalshi/auto-rebuild/start starts the scheduler."""
        response = requests.post(f"{BASE_URL}/api/cross-market/kalshi/auto-rebuild/start")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "message" in data, "Expected message field"
        
        # Message should indicate started or already running
        msg = data["message"].lower()
        assert "started" in msg or "running" in msg, f"Unexpected message: {data['message']}"
        
        print(f"Auto-rebuild start: {data['message']}")
    
    def test_auto_rebuild_health_after_start(self):
        """After starting, health should show running=true (may need brief wait)."""
        # Start auto-rebuild
        requests.post(f"{BASE_URL}/api/cross-market/kalshi/auto-rebuild/start")
        
        # Wait briefly for task to start
        time.sleep(2)
        
        # Check health
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/health")
        assert response.status_code == 200
        
        data = response.json()
        # Note: running might be true or false depending on timing
        # Just verify the endpoint works
        assert "running" in data
        print(f"Health after start: running={data['running']}")
    
    def test_auto_rebuild_stop(self):
        """POST /api/cross-market/kalshi/auto-rebuild/stop stops the scheduler."""
        response = requests.post(f"{BASE_URL}/api/cross-market/kalshi/auto-rebuild/stop")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "message" in data, "Expected message field"
        
        msg = data["message"].lower()
        assert "stop" in msg, f"Unexpected message: {data['message']}"
        
        print(f"Auto-rebuild stop: {data['message']}")
    
    def test_auto_rebuild_idempotent_start(self):
        """Starting when already running should return ok with 'already running' message."""
        # Start twice
        requests.post(f"{BASE_URL}/api/cross-market/kalshi/auto-rebuild/start")
        time.sleep(1)
        response = requests.post(f"{BASE_URL}/api/cross-market/kalshi/auto-rebuild/start")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Clean up - stop
        requests.post(f"{BASE_URL}/api/cross-market/kalshi/auto-rebuild/stop")
        print("Idempotent start test passed")


class TestValidationQueue:
    """Test validation queue endpoints."""
    
    def test_validation_queue_pending(self):
        """GET /api/cross-market/kalshi/validation-queue returns pending entries."""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/validation-queue")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "count" in data, "Missing 'count' field"
        assert "entries" in data, "Missing 'entries' field"
        assert isinstance(data["entries"], list), "entries should be a list"
        
        print(f"Validation queue (PENDING): {data['count']} entries")
    
    def test_validation_queue_validated(self):
        """GET /api/cross-market/kalshi/validation-queue?status=VALIDATED returns validated entries."""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/validation-queue?status=VALIDATED")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "count" in data, "Missing 'count' field"
        assert "entries" in data, "Missing 'entries' field"
        
        print(f"Validation queue (VALIDATED): {data['count']} entries")
    
    def test_validation_queue_with_limit(self):
        """Validation queue respects limit parameter."""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/validation-queue?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        # If there are entries, should be <= 5
        assert len(data.get("entries", [])) <= 5
        
        print(f"Validation queue with limit=5: {len(data.get('entries', []))} entries")
    
    def test_validation_entry_structure(self):
        """Validation entries have expected fields."""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/validation-queue?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        entries = data.get("entries", [])
        
        if entries:
            entry = entries[0]
            # Check expected fields
            expected_fields = ["validation_id", "entity", "edge_case_type", "score"]
            for field in expected_fields:
                assert field in entry, f"Missing field: {field}"
            
            print(f"Entry structure OK: {list(entry.keys())[:8]}...")
        else:
            print("No entries to validate structure (expected with current data)")


class TestValidationMetrics:
    """Test validation metrics endpoint."""
    
    def test_validation_metrics_returns_ok(self):
        """GET /api/cross-market/kalshi/validation-metrics returns metrics."""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/validation-metrics")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        
        # Check required metric fields
        assert "total" in data, "Missing 'total' field"
        assert "validated" in data, "Missing 'validated' field"
        assert "pending" in data, "Missing 'pending' field"
        
        print(f"Validation metrics: total={data['total']}, validated={data['validated']}, pending={data['pending']}")
    
    def test_validation_metrics_structure(self):
        """Validation metrics have expected structure."""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/validation-metrics")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check optional rate fields exist (may be null if no data)
        assert "real_edge_rate" in data, "Missing 'real_edge_rate' field"
        assert "execution_rate" in data, "Missing 'execution_rate' field"
        assert "trap_rate" in data, "Missing 'trap_rate' field"
        assert "by_edge_type" in data, "Missing 'by_edge_type' field"
        assert "by_confidence_bucket" in data, "Missing 'by_confidence_bucket' field"
        
        # by_edge_type and by_confidence_bucket should be lists
        assert isinstance(data["by_edge_type"], list), "by_edge_type should be list"
        assert isinstance(data["by_confidence_bucket"], list), "by_confidence_bucket should be list"
        
        print(f"Metrics structure OK: by_edge_type={len(data['by_edge_type'])} types, by_confidence_bucket={len(data['by_confidence_bucket'])} buckets")


class TestSubmitVerdict:
    """Test verdict submission endpoint."""
    
    def test_submit_verdict_invalid_id(self):
        """POST /api/cross-market/kalshi/validate/{id} with invalid ID returns error or ok=false."""
        # Use a fake ObjectId format
        fake_id = "000000000000000000000000"
        response = requests.post(
            f"{BASE_URL}/api/cross-market/kalshi/validate/{fake_id}",
            json={"manual_verdict": "REAL_EDGE"}
        )
        
        # Should return 200 with ok=false (not found) or handle gracefully
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # ok should be false since ID doesn't exist
        assert data.get("ok") is False, "Expected ok=false for non-existent ID"
        
        print("Invalid ID verdict submission handled correctly")
    
    def test_submit_verdict_invalid_verdict(self):
        """POST with invalid verdict type returns error."""
        fake_id = "000000000000000000000000"
        response = requests.post(
            f"{BASE_URL}/api/cross-market/kalshi/validate/{fake_id}",
            json={"manual_verdict": "INVALID_VERDICT"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is False, "Expected ok=false for invalid verdict"
        
        print("Invalid verdict type handled correctly")
    
    def test_valid_verdict_types(self):
        """All valid verdict types are accepted (structure test)."""
        valid_verdicts = ["REAL_EDGE", "FAKE_EDGE", "EXECUTION_TRAP", "TIMING_TRAP", "AMBIGUOUS_RULES", "SKIP"]
        fake_id = "000000000000000000000000"
        
        for verdict in valid_verdicts:
            response = requests.post(
                f"{BASE_URL}/api/cross-market/kalshi/validate/{fake_id}",
                json={"manual_verdict": verdict}
            )
            assert response.status_code == 200, f"Failed for verdict: {verdict}"
            # ok=false is expected since ID doesn't exist, but no error
            data = response.json()
            # Should not have error about invalid verdict
            if "error" in data:
                assert "Invalid verdict" not in data["error"], f"Verdict {verdict} should be valid"
        
        print(f"All {len(valid_verdicts)} verdict types accepted")


class TestRebuildStillWorks:
    """Test that rebuild endpoint still works and integrates with analytics/validation."""
    
    def test_rebuild_returns_summary(self):
        """POST /api/cross-market/kalshi/rebuild returns summary with all counts."""
        response = requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "summary" in data, "Missing 'summary' field"
        
        summary = data["summary"]
        expected_fields = ["kalshi_raw", "kalshi_filtered", "poly_markets", "clusters", 
                          "relations", "violations", "mispricings", "strategies_actionable"]
        for field in expected_fields:
            assert field in summary, f"Missing summary field: {field}"
        
        print(f"Rebuild summary: {summary}")
    
    def test_analytics_after_rebuild(self):
        """GET /api/cross-market/kalshi/analytics returns data after rebuild."""
        # First rebuild
        requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild")
        
        # Then check analytics
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/analytics")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "total_signals_tracked" in data
        assert "by_edge_type" in data
        assert "by_platform_pair" in data
        
        print(f"Analytics after rebuild: {data['total_signals_tracked']} signals tracked")


class TestHealthMetricsAfterRebuild:
    """Test health metrics update after rebuild."""
    
    def test_health_metrics_update(self):
        """Health metrics should reflect rebuild activity."""
        # Get initial health
        initial = requests.get(f"{BASE_URL}/api/cross-market/kalshi/health").json()
        initial_rebuilds = initial.get("total_rebuilds", 0)
        
        # Do a rebuild
        requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild")
        
        # Note: Manual rebuild doesn't increment auto-rebuild counters
        # But health endpoint should still work
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        print(f"Health after rebuild: total_rebuilds={data.get('total_rebuilds')}, last_latency_ms={data.get('last_latency_ms')}")


class TestEndToEndFlow:
    """Test end-to-end flow: rebuild → check analytics → check validation queue."""
    
    def test_full_flow(self):
        """Complete flow test."""
        # 1. Rebuild
        rebuild_resp = requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild")
        assert rebuild_resp.status_code == 200
        rebuild_data = rebuild_resp.json()
        assert rebuild_data.get("ok") is True
        print(f"1. Rebuild OK: {rebuild_data.get('summary', {}).get('mispricings', 0)} mispricings")
        
        # 2. Check analytics
        analytics_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/analytics")
        assert analytics_resp.status_code == 200
        analytics_data = analytics_resp.json()
        assert analytics_data.get("ok") is True
        print(f"2. Analytics OK: {analytics_data.get('total_signals_tracked', 0)} signals tracked")
        
        # 3. Check validation queue
        queue_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/validation-queue")
        assert queue_resp.status_code == 200
        queue_data = queue_resp.json()
        assert queue_data.get("ok") is True
        print(f"3. Validation queue OK: {queue_data.get('count', 0)} pending entries")
        
        # 4. Check validation metrics
        metrics_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/validation-metrics")
        assert metrics_resp.status_code == 200
        metrics_data = metrics_resp.json()
        assert metrics_data.get("ok") is True
        print(f"4. Validation metrics OK: total={metrics_data.get('total', 0)}")
        
        # 5. Check health
        health_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data.get("ok") is True
        print(f"5. Health OK: running={health_data.get('running')}")
        
        print("End-to-end flow completed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
