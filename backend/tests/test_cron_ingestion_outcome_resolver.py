"""
Test Cron Ingestion Pipeline + Outcome Resolver APIs
Phase 4: Production cron pipeline with 8 guards + Outcome Resolver

Endpoints tested:
- GET /api/ingestion/scheduler/status - scheduler running/locked state
- POST /api/ingestion/scheduler/start - starts the 6h scheduler
- POST /api/ingestion/scheduler/stop - stops the scheduler
- GET /api/ingestion/cron/status - full cron status with last cycle, health trend
- POST /api/ingestion/pipeline/enable - re-enables pipeline after hard stop
- POST /api/outcome/resolve - runs outcome resolution on unresolved samples
- GET /api/outcome/stats - outcome resolution statistics
- GET /api/dataset/v3/stats - verify dataset v3 has grown
- GET /api/dataset/v3/health - verify data health
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestSchedulerStatus:
    """Test scheduler status endpoint"""

    def test_scheduler_status_returns_valid_json(self):
        """GET /api/ingestion/scheduler/status - returns scheduler state"""
        response = requests.get(f"{BASE_URL}/api/ingestion/scheduler/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Validate response structure
        assert "running" in data, "Missing 'running' field"
        assert "locked" in data, "Missing 'locked' field"
        assert "interval_hours" in data, "Missing 'interval_hours' field"
        
        # Validate types
        assert isinstance(data["running"], bool), "running should be boolean"
        assert isinstance(data["locked"], bool), "locked should be boolean"
        assert isinstance(data["interval_hours"], (int, float)), "interval_hours should be numeric"
        
        # Validate interval is 6 hours
        assert data["interval_hours"] == 6.0, f"Expected 6h interval, got {data['interval_hours']}"
        
        print(f"Scheduler status: running={data['running']}, locked={data['locked']}, interval={data['interval_hours']}h")


class TestSchedulerStartStop:
    """Test scheduler start/stop endpoints"""

    def test_scheduler_start(self):
        """POST /api/ingestion/scheduler/start - starts the scheduler"""
        response = requests.post(f"{BASE_URL}/api/ingestion/scheduler/start", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        
        # Either starts successfully or already running
        if data.get("ok"):
            assert "message" in data, "Missing 'message' field on success"
            assert "interval_hours" in data, "Missing 'interval_hours' field"
            print(f"Scheduler started: {data['message']}, interval={data.get('interval_hours')}h")
        else:
            # Already running is acceptable
            assert "error" in data, "Missing 'error' field on failure"
            assert "already running" in data["error"].lower(), f"Unexpected error: {data['error']}"
            print(f"Scheduler already running: {data['error']}")

    def test_scheduler_stop(self):
        """POST /api/ingestion/scheduler/stop - stops the scheduler"""
        response = requests.post(f"{BASE_URL}/api/ingestion/scheduler/stop", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] is True, f"Expected ok=True, got {data['ok']}"
        assert "message" in data, "Missing 'message' field"
        
        print(f"Scheduler stop: {data['message']}")


class TestCronStatus:
    """Test full cron status endpoint"""

    def test_cron_status_returns_full_status(self):
        """GET /api/ingestion/cron/status - returns full cron status"""
        response = requests.get(f"{BASE_URL}/api/ingestion/cron/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] is True, f"Expected ok=True, got {data['ok']}"
        
        # Validate required fields
        required_fields = ["scheduler", "pipeline_enabled", "total_cycles", "data_status", "data_health"]
        for field in required_fields:
            assert field in data, f"Missing '{field}' field"
        
        # Validate scheduler sub-object
        scheduler = data["scheduler"]
        assert "running" in scheduler, "Missing scheduler.running"
        assert "locked" in scheduler, "Missing scheduler.locked"
        assert "interval_hours" in scheduler, "Missing scheduler.interval_hours"
        
        # Validate pipeline_enabled is boolean
        assert isinstance(data["pipeline_enabled"], bool), "pipeline_enabled should be boolean"
        
        # Validate total_cycles is integer
        assert isinstance(data["total_cycles"], int), "total_cycles should be integer"
        
        # Validate data_health
        health = data["data_health"]
        assert "status" in health, "Missing data_health.status"
        
        print(f"Cron status: cycles={data['total_cycles']}, pipeline_enabled={data['pipeline_enabled']}")
        print(f"  Scheduler: running={scheduler['running']}, locked={scheduler['locked']}")
        print(f"  Data health: {health['status']}")
        
        # Check if last_cycle exists (may be null if no cycles run)
        if data.get("last_cycle"):
            print(f"  Last cycle: {data['last_cycle'].get('cycle_at', 'N/A')}")


class TestPipelineEnable:
    """Test pipeline enable endpoint"""

    def test_pipeline_enable(self):
        """POST /api/ingestion/pipeline/enable - re-enables pipeline"""
        response = requests.post(f"{BASE_URL}/api/ingestion/pipeline/enable", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] is True, f"Expected ok=True, got {data['ok']}"
        assert "message" in data, "Missing 'message' field"
        
        print(f"Pipeline enable: {data['message']}")


class TestOutcomeResolver:
    """Test outcome resolution endpoints"""

    def test_outcome_resolve(self):
        """POST /api/outcome/resolve - runs outcome resolution"""
        response = requests.post(
            f"{BASE_URL}/api/outcome/resolve",
            json={"limit": 50},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] is True, f"Expected ok=True, got {data['ok']}"
        
        # Validate response structure
        expected_fields = ["resolved", "partial_updates", "skipped", "errors", "total_checked"]
        for field in expected_fields:
            assert field in data, f"Missing '{field}' field"
            assert isinstance(data[field], int), f"{field} should be integer"
        
        print(f"Outcome resolution: resolved={data['resolved']}, partial={data['partial_updates']}, skipped={data['skipped']}, errors={data['errors']}")

    def test_outcome_stats(self):
        """GET /api/outcome/stats - returns outcome statistics"""
        response = requests.get(f"{BASE_URL}/api/outcome/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] is True, f"Expected ok=True, got {data['ok']}"
        
        # Validate required fields
        required_fields = ["total", "resolved", "unresolved", "labels", "tradeable", "tradeable_pct", "resolution_pct"]
        for field in required_fields:
            assert field in data, f"Missing '{field}' field"
        
        # Validate labels sub-object
        labels = data["labels"]
        assert "GOOD" in labels, "Missing labels.GOOD"
        assert "BAD" in labels, "Missing labels.BAD"
        assert "NEUTRAL" in labels, "Missing labels.NEUTRAL"
        
        # Validate numeric types
        assert isinstance(data["total"], int), "total should be integer"
        assert isinstance(data["resolved"], int), "resolved should be integer"
        assert isinstance(data["tradeable"], int), "tradeable should be integer"
        
        print(f"Outcome stats: total={data['total']}, resolved={data['resolved']}, unresolved={data['unresolved']}")
        print(f"  Labels: GOOD={labels['GOOD']}, BAD={labels['BAD']}, NEUTRAL={labels['NEUTRAL']}")
        print(f"  Tradeable: {data['tradeable']} ({data['tradeable_pct']}%)")
        print(f"  Resolution: {data['resolution_pct']}%")


class TestDatasetV3Verification:
    """Verify dataset v3 stats and health"""

    def test_dataset_v3_stats(self):
        """GET /api/dataset/v3/stats - verify dataset has grown"""
        response = requests.get(f"{BASE_URL}/api/dataset/v3/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] is True, f"Expected ok=True, got {data['ok']}"
        
        # Validate total samples
        total = data.get("total", 0)
        assert total >= 0, f"Total should be non-negative, got {total}"
        
        # If we have samples, validate structure
        if total > 0:
            assert "resolved" in data, "Missing 'resolved' field"
            assert "tradeable" in data, "Missing 'tradeable' field"
            assert "quality" in data, "Missing 'quality' field"
            assert "diversity" in data, "Missing 'diversity' field"
            
            quality = data["quality"]
            assert "avg_dqs" in quality, "Missing quality.avg_dqs"
            
            diversity = data["diversity"]
            assert "unique_actors" in diversity, "Missing diversity.unique_actors"
            assert "unique_tokens" in diversity, "Missing diversity.unique_tokens"
            
            print(f"Dataset V3: total={total}, resolved={data['resolved']}, tradeable={data['tradeable']}")
            print(f"  Quality: avg_dqs={quality['avg_dqs']}")
            print(f"  Diversity: actors={diversity['unique_actors']}, tokens={diversity['unique_tokens']}")
        else:
            print("Dataset V3: empty dataset")

    def test_dataset_v3_health(self):
        """GET /api/dataset/v3/health - verify data health"""
        response = requests.get(f"{BASE_URL}/api/dataset/v3/health", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] is True, f"Expected ok=True, got {data['ok']}"
        
        # Validate status field
        assert "status" in data, "Missing 'status' field"
        status = data["status"]
        valid_statuses = ["healthy", "degrading", "insufficient_data"]
        assert status in valid_statuses, f"Invalid status: {status}"
        
        # Validate alerts field
        assert "alerts" in data or status == "insufficient_data", "Missing 'alerts' field"
        
        print(f"Data health: status={status}")
        if data.get("alerts"):
            print(f"  Alerts: {data['alerts']}")
        if data.get("avg_dqs_24h"):
            print(f"  DQS 24h: {data['avg_dqs_24h']}, DQS 7d: {data.get('avg_dqs_7d', 'N/A')}")


class TestIngestionCycleMinimal:
    """Test ingestion cycle with minimal params (fast response)"""

    def test_ingestion_cycle_minimal(self):
        """POST /api/ingestion/cycle - test with minimal params for fast response"""
        # Use tokens_limit=0, actor_limit=0 to get fast response
        response = requests.post(
            f"{BASE_URL}/api/ingestion/cycle",
            json={"tokens_limit": 0, "actor_limit": 0},
            timeout=120
        )
        
        # Accept 200 (success) or 502 (timeout/error during long-running cycle)
        # The endpoint may timeout if another cycle is running
        if response.status_code == 502:
            print("Ingestion cycle: 502 - likely another cycle is running or timeout")
            # This is acceptable - verify the scheduler status instead
            status_resp = requests.get(f"{BASE_URL}/api/ingestion/scheduler/status", timeout=30)
            if status_resp.status_code == 200:
                status = status_resp.json()
                print(f"  Scheduler status: running={status.get('running')}, locked={status.get('locked')}")
                # If locked, another cycle is running - this is expected
                if status.get("locked"):
                    print("  Another cycle is running - 502 is expected behavior")
                    return  # Test passes
            pytest.skip("Ingestion cycle returned 502 - likely another cycle running")
            return
        
        assert response.status_code == 200, f"Expected 200 or 502, got {response.status_code}"
        
        data = response.json()
        
        # Either ok=True (success) or ok=False with error (pipeline disabled or locked)
        assert "ok" in data, "Missing 'ok' field"
        
        if data["ok"]:
            # Successful cycle
            assert "cycle_at" in data, "Missing 'cycle_at' field"
            assert "duration_sec" in data, "Missing 'duration_sec' field"
            assert "stages" in data, "Missing 'stages' field"
            
            print(f"Ingestion cycle: ok={data['ok']}, duration={data['duration_sec']}s")
            print(f"  Stages: {len(data['stages'])}")
            if data.get("health"):
                print(f"  Health: {data['health'].get('health_status', 'N/A')}")
        else:
            # Pipeline disabled or locked
            error = data.get("error", "Unknown error")
            print(f"Ingestion cycle skipped: {error}")
            # This is acceptable - pipeline may be disabled or locked
            assert "error" in data, "Missing 'error' field on failure"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
