"""
Admin UI Enhancements Backend Tests
====================================
Tests for:
1. System Resources Monitor API (/api/admin/resources)
2. ML Data Accumulation API (/api/admin/data-accumulation)
3. Twitter Standby Monitor API (/api/v4/admin/system/standby)
4. Scheduler Status API (/api/v4/admin/system/scheduler/status)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSystemResourcesAPI:
    """Tests for /api/admin/resources endpoint - System resource monitoring"""
    
    def test_resources_endpoint_returns_200(self):
        """Verify resources endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/admin/resources")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Resources endpoint returns 200")
    
    def test_resources_response_structure(self):
        """Verify resources response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/admin/resources")
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=True"
        assert "data" in data, "Response should have 'data' field"
        
        res_data = data["data"]
        assert "health" in res_data, "Should have health status"
        assert "cpu" in res_data, "Should have CPU data"
        assert "memory" in res_data, "Should have memory data"
        assert "timestamp" in res_data, "Should have timestamp"
        print("✓ Resources response has correct structure")
    
    def test_resources_cpu_data(self):
        """Verify CPU data contains required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/resources")
        cpu = response.json()["data"]["cpu"]
        
        assert "percent" in cpu, "CPU should have percent"
        assert "cores" in cpu, "CPU should have cores count"
        assert "loadAvg" in cpu, "CPU should have loadAvg array"
        assert "loadPercent" in cpu, "CPU should have loadPercent"
        
        assert isinstance(cpu["loadAvg"], list), "loadAvg should be a list"
        assert len(cpu["loadAvg"]) == 3, "loadAvg should have 3 values (1m, 5m, 15m)"
        print(f"✓ CPU data valid: {cpu['loadPercent']}% load, {cpu['cores']} cores")
    
    def test_resources_memory_data(self):
        """Verify memory data contains required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/resources")
        mem = response.json()["data"]["memory"]
        
        assert "percent" in mem, "Memory should have percent"
        assert "usedMB" in mem, "Memory should have usedMB"
        assert "totalMB" in mem, "Memory should have totalMB"
        assert "availableMB" in mem, "Memory should have availableMB"
        
        assert mem["usedMB"] > 0, "Used memory should be positive"
        assert mem["totalMB"] > mem["usedMB"], "Total should be > used"
        print(f"✓ Memory data valid: {mem['percent']}% used ({mem['usedMB']}MB / {mem['totalMB']}MB)")
    
    def test_resources_health_status(self):
        """Verify health status is one of expected values"""
        response = requests.get(f"{BASE_URL}/api/admin/resources")
        health = response.json()["data"]["health"]
        
        valid_statuses = ["OK", "WARNING", "CRITICAL"]
        assert health in valid_statuses, f"Health should be one of {valid_statuses}, got {health}"
        print(f"✓ Health status valid: {health}")


class TestDataAccumulationAPI:
    """Tests for /api/admin/data-accumulation endpoint - ML readiness tracking"""
    
    def test_data_accumulation_endpoint_returns_200(self):
        """Verify data-accumulation endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/admin/data-accumulation")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Data accumulation endpoint returns 200")
    
    def test_data_accumulation_response_structure(self):
        """Verify data-accumulation response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/admin/data-accumulation")
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=True"
        assert "data" in data, "Response should have 'data' field"
        
        acc_data = data["data"]
        assert "collections" in acc_data, "Should have collections"
        assert "mlReadiness" in acc_data, "Should have mlReadiness"
        assert "timestamp" in acc_data, "Should have timestamp"
        print("✓ Data accumulation response has correct structure")
    
    def test_ml_readiness_fields(self):
        """Verify ML readiness contains required fields with 150 threshold"""
        response = requests.get(f"{BASE_URL}/api/admin/data-accumulation")
        ml = response.json()["data"]["mlReadiness"]
        
        assert "status" in ml, "Should have status"
        assert "dirSamples" in ml, "Should have dirSamples count"
        assert "shadowDecisions" in ml, "Should have shadowDecisions count"
        assert "minThreshold" in ml, "Should have minThreshold"
        assert "goodThreshold" in ml, "Should have goodThreshold"
        assert "progress" in ml, "Should have progress percentage"
        
        # Verify 150 sample threshold as per requirements
        assert ml["minThreshold"] == 150, f"Min threshold should be 150, got {ml['minThreshold']}"
        assert ml["goodThreshold"] == 500, f"Good threshold should be 500, got {ml['goodThreshold']}"
        print(f"✓ ML readiness valid: {ml['status']} ({ml['dirSamples']} samples, {ml['progress']}% progress)")
    
    def test_ml_readiness_status_values(self):
        """Verify ML readiness status is one of expected values"""
        response = requests.get(f"{BASE_URL}/api/admin/data-accumulation")
        status = response.json()["data"]["mlReadiness"]["status"]
        
        valid_statuses = ["NOT_READY", "MINIMUM_MET", "READY"]
        assert status in valid_statuses, f"Status should be one of {valid_statuses}, got {status}"
        print(f"✓ ML readiness status valid: {status}")
    
    def test_collections_have_russian_labels(self):
        """Verify collections have Russian labels"""
        response = requests.get(f"{BASE_URL}/api/admin/data-accumulation")
        collections = response.json()["data"]["collections"]
        
        # Check that at least some collections have Russian labels
        russian_labels_found = 0
        for col_name, col_data in collections.items():
            label = col_data.get("label", "")
            # Check for Cyrillic characters
            if any('\u0400' <= c <= '\u04FF' for c in label):
                russian_labels_found += 1
        
        assert russian_labels_found > 0, "Should have Russian labels in collections"
        print(f"✓ Found {russian_labels_found} collections with Russian labels")


class TestTwitterStandbyAPI:
    """Tests for /api/v4/admin/system/standby endpoint - Twitter standby monitor"""
    
    def test_standby_endpoint_returns_200(self):
        """Verify standby endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/system/standby")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Standby endpoint returns 200")
    
    def test_standby_response_structure(self):
        """Verify standby response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/system/standby")
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=True"
        assert "data" in data, "Response should have 'data' field"
        
        standby = data["data"]
        assert "state" in standby, "Should have state"
        assert "totalSessions" in standby, "Should have totalSessions"
        assert "okSessions" in standby, "Should have okSessions"
        print("✓ Standby response has correct structure")
    
    def test_standby_state_values(self):
        """Verify standby state is ACTIVE or STANDBY"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/system/standby")
        state = response.json()["data"]["state"]
        
        valid_states = ["ACTIVE", "STANDBY", "UNKNOWN"]
        assert state in valid_states, f"State should be one of {valid_states}, got {state}"
        print(f"✓ Standby state valid: {state}")
    
    def test_standby_session_counts(self):
        """Verify session counts are present and valid"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/system/standby")
        data = response.json()["data"]
        
        assert "totalSessions" in data, "Should have totalSessions"
        assert "okSessions" in data, "Should have okSessions"
        assert "staleSessions" in data, "Should have staleSessions"
        assert "expiredSessions" in data, "Should have expiredSessions"
        
        total = data["totalSessions"]
        ok = data["okSessions"]
        stale = data["staleSessions"]
        expired = data["expiredSessions"]
        
        assert total >= 0, "Total sessions should be >= 0"
        assert ok >= 0, "OK sessions should be >= 0"
        assert ok <= total, "OK sessions should be <= total"
        print(f"✓ Session counts valid: {ok}/{total} OK, {stale} stale, {expired} expired")


class TestSchedulerStatusAPI:
    """Tests for /api/v4/admin/system/scheduler/status endpoint"""
    
    def test_scheduler_endpoint_returns_200(self):
        """Verify scheduler status endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/system/scheduler/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Scheduler status endpoint returns 200")
    
    def test_scheduler_response_structure(self):
        """Verify scheduler response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/system/scheduler/status")
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=True"
        assert "data" in data, "Response should have 'data' field"
        
        scheduler = data["data"]
        assert "enabled" in scheduler, "Should have enabled flag"
        assert "intervalMinutes" in scheduler, "Should have intervalMinutes"
        print(f"✓ Scheduler response valid: enabled={scheduler.get('enabled')}, interval={scheduler.get('intervalMinutes')}min")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
