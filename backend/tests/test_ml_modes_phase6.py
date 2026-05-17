"""
Phase 6: ML Modes + Kill Switch API Tests
Tests for mode switching (OFF/ADVISOR/ASSIST) and kill switch functionality
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestModeState:
    """GET /api/ml/mode/state - Get current ML mode state"""
    
    def test_get_mode_state_success(self):
        """Test getting current mode state"""
        response = requests.get(f"{BASE_URL}/api/ml/mode/state")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'mode' in data
        assert data['mode'] in ['OFF', 'ADVISOR', 'ASSIST']
        assert 'killSwitch' in data
        assert data['killSwitch']['status'] in ['ARMED', 'TRIGGERED']
        assert 'modeChangedAt' in data
        assert 'modeChangedBy' in data


class TestModeSet:
    """POST /api/ml/mode/set - Set ML mode"""
    
    def test_set_mode_off(self):
        """Test setting mode to OFF"""
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/set",
            json={"mode": "OFF", "triggeredBy": "test"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert data.get('mode') == 'OFF'
    
    def test_set_mode_advisor(self):
        """Test setting mode to ADVISOR"""
        # First reset kill switch to ensure ADVISOR can be set
        requests.post(f"{BASE_URL}/api/ml/mode/reset", json={"triggeredBy": "test"})
        
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/set",
            json={"mode": "ADVISOR", "triggeredBy": "test"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert data.get('mode') == 'ADVISOR'
    
    def test_set_mode_invalid(self):
        """Test setting invalid mode returns error"""
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/set",
            json={"mode": "INVALID_MODE", "triggeredBy": "test"}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert data.get('success') == False
        assert 'error' in data
    
    def test_set_mode_assist_blocked_by_gates(self):
        """Test ASSIST mode blocked when gates fail"""
        # First trigger kill switch to make gates fail
        requests.post(f"{BASE_URL}/api/ml/mode/kill", json={"reason": "test"})
        
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/set",
            json={"mode": "ASSIST", "triggeredBy": "test"}
        )
        
        data = response.json()
        # Should be blocked
        assert data.get('blocked') == True or data.get('success') == False
        
        # Cleanup - reset kill switch
        requests.post(f"{BASE_URL}/api/ml/mode/reset", json={"triggeredBy": "test"})


class TestKillSwitch:
    """POST /api/ml/mode/kill - Trigger kill switch"""
    
    def test_trigger_kill_switch(self):
        """Test manual kill switch trigger"""
        # First reset to ensure clean state
        requests.post(f"{BASE_URL}/api/ml/mode/reset", json={"triggeredBy": "test"})
        
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/kill",
            json={"reason": "Test trigger", "triggeredBy": "test"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'reason' in data
        
        # Verify state changed
        state_response = requests.get(f"{BASE_URL}/api/ml/mode/state")
        state_data = state_response.json()
        assert state_data['killSwitch']['status'] == 'TRIGGERED'
        assert state_data['mode'] == 'OFF'
    
    def test_kill_switch_idempotent(self):
        """Test kill switch is idempotent (multiple triggers don't break)"""
        # Trigger multiple times
        for i in range(3):
            response = requests.post(
                f"{BASE_URL}/api/ml/mode/kill",
                json={"reason": f"Test trigger {i}", "triggeredBy": "test"}
            )
            assert response.status_code == 200
        
        # State should still be consistent
        state_response = requests.get(f"{BASE_URL}/api/ml/mode/state")
        state_data = state_response.json()
        assert state_data['killSwitch']['status'] == 'TRIGGERED'
        assert state_data['mode'] == 'OFF'


class TestKillSwitchReset:
    """POST /api/ml/mode/reset - Reset kill switch"""
    
    def test_reset_kill_switch(self):
        """Test resetting kill switch"""
        # First trigger it
        requests.post(f"{BASE_URL}/api/ml/mode/kill", json={"reason": "test"})
        
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/reset",
            json={"triggeredBy": "test"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        
        # Verify state changed
        state_response = requests.get(f"{BASE_URL}/api/ml/mode/state")
        state_data = state_response.json()
        assert state_data['killSwitch']['status'] == 'ARMED'


class TestHealthCheck:
    """POST /api/ml/mode/health-check - Health check with metrics"""
    
    def test_health_check_normal(self):
        """Test health check with normal metrics"""
        # Reset first
        requests.post(f"{BASE_URL}/api/ml/mode/reset", json={"triggeredBy": "test"})
        
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/health-check",
            json={"flipRate": 0.03, "ece": 0.08}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert data.get('healthy') == True
        assert data.get('killTriggered') == False
        assert data.get('triggers') == []
    
    def test_health_check_flip_rate_exceeded(self):
        """Test health check triggers kill switch when flip rate > 7%"""
        # Reset first
        requests.post(f"{BASE_URL}/api/ml/mode/reset", json={"triggeredBy": "test"})
        requests.post(f"{BASE_URL}/api/ml/mode/set", json={"mode": "ADVISOR"})
        
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/health-check",
            json={"flipRate": 0.12, "ece": 0.05}  # 12% > 7% threshold
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('healthy') == False
        assert data.get('killTriggered') == True
        assert len(data.get('triggers', [])) > 0
        
        # Verify mode is OFF
        state_response = requests.get(f"{BASE_URL}/api/ml/mode/state")
        state_data = state_response.json()
        assert state_data['mode'] == 'OFF'
    
    def test_health_check_ece_exceeded(self):
        """Test health check triggers kill switch when ECE > 0.15"""
        # Reset first
        requests.post(f"{BASE_URL}/api/ml/mode/reset", json={"triggeredBy": "test"})
        requests.post(f"{BASE_URL}/api/ml/mode/set", json={"mode": "ADVISOR"})
        
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/health-check",
            json={"flipRate": 0.01, "ece": 0.25}  # 0.25 > 0.15 threshold
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('healthy') == False
        assert data.get('killTriggered') == True


class TestModeAudit:
    """GET /api/ml/mode/audit - Get mode audit history"""
    
    def test_get_audit_history(self):
        """Test getting audit history"""
        response = requests.get(f"{BASE_URL}/api/ml/mode/audit?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'count' in data
        assert 'audits' in data
        assert isinstance(data['audits'], list)
        
        # Check audit structure if there are entries
        if len(data['audits']) > 0:
            audit = data['audits'][0]
            assert 'action' in audit
            assert 'timestamp' in audit


class TestAttackTests:
    """POST /api/ml/mode/attack-tests - Run Phase 6 attack tests"""
    
    def test_run_attack_tests(self):
        """Test running all Phase 6 attack tests"""
        response = requests.post(f"{BASE_URL}/api/ml/mode/attack-tests", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'totalTests' in data
        assert 'passed' in data
        assert 'failed' in data
        assert 'results' in data
        
        # Should have 7 tests
        assert data['totalTests'] == 7
        
        # All tests should pass
        assert data['passed'] == 7
        assert data['failed'] == 0
        
        # Check individual test results
        results = data['results']
        assert len(results) == 7
        
        for test in results:
            assert 'id' in test
            assert 'name' in test
            assert 'passed' in test
            assert 'category' in test
            assert test['passed'] == True, f"Test {test['id']} failed: {test.get('actual')}"
    
    def test_attack_test_f1_force_assist_gates_fail(self):
        """Verify F1 test: Force ASSIST with gates FAIL"""
        response = requests.post(f"{BASE_URL}/api/ml/mode/attack-tests", json={})
        data = response.json()
        
        f1_test = next((t for t in data['results'] if t['id'] == 'F1'), None)
        assert f1_test is not None
        assert f1_test['passed'] == True
        assert f1_test['category'] == 'SAFETY'
    
    def test_attack_test_f2_flip_spike(self):
        """Verify F2 test: Flip spike auto OFF"""
        response = requests.post(f"{BASE_URL}/api/ml/mode/attack-tests", json={})
        data = response.json()
        
        f2_test = next((t for t in data['results'] if t['id'] == 'F2'), None)
        assert f2_test is not None
        assert f2_test['passed'] == True
        assert f2_test['category'] == 'AUTO_SAFETY'
    
    def test_attack_test_f3_ece_threshold(self):
        """Verify F3 test: ECE threshold"""
        response = requests.post(f"{BASE_URL}/api/ml/mode/attack-tests", json={})
        data = response.json()
        
        f3_test = next((t for t in data['results'] if t['id'] == 'F3'), None)
        assert f3_test is not None
        assert f3_test['passed'] == True
        assert f3_test['category'] == 'AUTO_SAFETY'
    
    def test_attack_test_f4_bucket_crossing(self):
        """Verify F4 test: Bucket crossing blocked by architecture"""
        response = requests.post(f"{BASE_URL}/api/ml/mode/attack-tests", json={})
        data = response.json()
        
        f4_test = next((t for t in data['results'] if t['id'] == 'F4'), None)
        assert f4_test is not None
        assert f4_test['passed'] == True
        assert f4_test['category'] == 'ARCHITECTURE'
    
    def test_attack_test_f5_kill_switch_idempotent(self):
        """Verify F5 test: Kill switch idempotent"""
        response = requests.post(f"{BASE_URL}/api/ml/mode/attack-tests", json={})
        data = response.json()
        
        f5_test = next((t for t in data['results'] if t['id'] == 'F5'), None)
        assert f5_test is not None
        assert f5_test['passed'] == True
        assert f5_test['category'] == 'IDEMPOTENCY'
    
    def test_attack_test_f6_manual_off(self):
        """Verify F6 test: Manual OFF immediate"""
        response = requests.post(f"{BASE_URL}/api/ml/mode/attack-tests", json={})
        data = response.json()
        
        f6_test = next((t for t in data['results'] if t['id'] == 'F6'), None)
        assert f6_test is not None
        assert f6_test['passed'] == True
        assert f6_test['category'] == 'CONTROL'
    
    def test_attack_test_f7_calibration_map_missing(self):
        """Verify F7 test: Calibration map missing fallback"""
        response = requests.post(f"{BASE_URL}/api/ml/mode/attack-tests", json={})
        data = response.json()
        
        f7_test = next((t for t in data['results'] if t['id'] == 'F7'), None)
        assert f7_test is not None
        assert f7_test['passed'] == True
        assert f7_test['category'] == 'FALLBACK'


class TestKillSwitchEvents:
    """GET /api/ml/mode/kill-events - Get kill switch events"""
    
    def test_get_kill_events(self):
        """Test getting kill switch events"""
        response = requests.get(f"{BASE_URL}/api/ml/mode/kill-events?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'count' in data
        assert 'events' in data
        assert isinstance(data['events'], list)


class TestSafetyInvariants:
    """Test safety invariants for Phase 6"""
    
    def test_kill_switch_blocks_advisor_mode(self):
        """When kill switch is triggered, ADVISOR mode should be blocked"""
        # Trigger kill switch
        requests.post(f"{BASE_URL}/api/ml/mode/kill", json={"reason": "test"})
        
        # Try to set ADVISOR
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/set",
            json={"mode": "ADVISOR", "triggeredBy": "test"}
        )
        
        data = response.json()
        assert data.get('blocked') == True or data.get('success') == False
        
        # Cleanup
        requests.post(f"{BASE_URL}/api/ml/mode/reset", json={"triggeredBy": "test"})
    
    def test_kill_switch_blocks_assist_mode(self):
        """When kill switch is triggered, ASSIST mode should be blocked"""
        # Trigger kill switch
        requests.post(f"{BASE_URL}/api/ml/mode/kill", json={"reason": "test"})
        
        # Try to set ASSIST
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/set",
            json={"mode": "ASSIST", "triggeredBy": "test"}
        )
        
        data = response.json()
        assert data.get('blocked') == True or data.get('success') == False
        
        # Cleanup
        requests.post(f"{BASE_URL}/api/ml/mode/reset", json={"triggeredBy": "test"})
    
    def test_off_mode_always_allowed(self):
        """OFF mode should always be allowed, even with kill switch triggered"""
        # Trigger kill switch
        requests.post(f"{BASE_URL}/api/ml/mode/kill", json={"reason": "test"})
        
        # Set OFF should work
        response = requests.post(
            f"{BASE_URL}/api/ml/mode/set",
            json={"mode": "OFF", "triggeredBy": "test"}
        )
        
        data = response.json()
        assert data.get('success') == True
        assert data.get('mode') == 'OFF'
        
        # Cleanup
        requests.post(f"{BASE_URL}/api/ml/mode/reset", json={"triggeredBy": "test"})


# Cleanup fixture to reset state after all tests
@pytest.fixture(scope="module", autouse=True)
def cleanup_after_tests():
    """Reset state after all tests complete"""
    yield
    # Reset to clean state
    requests.post(f"{BASE_URL}/api/ml/mode/reset", json={"triggeredBy": "test_cleanup"})
    requests.post(f"{BASE_URL}/api/ml/mode/set", json={"mode": "OFF", "triggeredBy": "test_cleanup"})
