"""
Phase 5: Auto-Calibration API Tests
Tests for ML calibration endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')


class TestCalibrationActiveStatus:
    """Tests for GET /api/ml/calibration/active"""
    
    def test_get_active_calibration_status(self):
        """Test getting active calibration status"""
        response = requests.get(f"{BASE_URL}/api/ml/calibration/active")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'status' in data
        assert 'window' in data
        # Status should be ACTIVE or DISABLED
        assert data['status'] in ['ACTIVE', 'DISABLED']
    
    def test_get_active_calibration_with_window_param(self):
        """Test getting active calibration with specific window"""
        response = requests.get(f"{BASE_URL}/api/ml/calibration/active", params={'window': '14d'})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True


class TestCalibrationRuns:
    """Tests for GET /api/ml/calibration/runs"""
    
    def test_get_calibration_runs(self):
        """Test getting calibration run history"""
        response = requests.get(f"{BASE_URL}/api/ml/calibration/runs")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'runs' in data
        assert 'count' in data
        assert isinstance(data['runs'], list)
    
    def test_get_calibration_runs_with_limit(self):
        """Test getting calibration runs with limit"""
        response = requests.get(f"{BASE_URL}/api/ml/calibration/runs", params={'limit': 5})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert len(data['runs']) <= 5
    
    def test_calibration_run_structure(self):
        """Test that calibration runs have correct structure"""
        response = requests.get(f"{BASE_URL}/api/ml/calibration/runs", params={'limit': 1})
        assert response.status_code == 200
        
        data = response.json()
        if data['count'] > 0:
            run = data['runs'][0]
            # Check required fields
            assert 'runId' in run
            assert 'window' in run
            assert 'status' in run
            assert 'createdAt' in run
            # Check nested structures
            assert 'sampleRange' in run or 'inputMetrics' in run
            assert 'outputMetrics' in run


class TestCalibrationBuild:
    """Tests for POST /api/ml/calibration/build"""
    
    def test_build_calibration_map(self):
        """Test building a calibration map"""
        payload = {
            'window': '7d',
            'scope': 'global',
            'limit': 1000,
            'realOnly': True
        }
        response = requests.post(f"{BASE_URL}/api/ml/calibration/build", json=payload)
        # May return 200, 400, or 520 (server error for insufficient samples)
        assert response.status_code in [200, 400, 520]
        
        data = response.json()
        # May fail due to insufficient samples, but should return proper response
        assert 'success' in data
        if not data['success']:
            # Expected error for insufficient samples
            assert 'error' in data
            assert 'samples' in data['error'].lower() or 'insufficient' in data['error'].lower()
    
    def test_build_calibration_with_different_windows(self):
        """Test building calibration with different window values"""
        for window in ['7d', '14d', '30d']:
            payload = {'window': window, 'scope': 'global', 'limit': 100}
            response = requests.post(f"{BASE_URL}/api/ml/calibration/build", json=payload)
            # May return 200, 400, or 520 (server error for insufficient samples)
            assert response.status_code in [200, 400, 520]
            data = response.json()
            assert 'success' in data


class TestCalibrationSimulate:
    """Tests for POST /api/ml/calibration/simulate"""
    
    def test_simulate_calibration_with_invalid_runid(self):
        """Test simulation with invalid run ID"""
        payload = {'runId': 'invalid-run-id-12345'}
        response = requests.post(f"{BASE_URL}/api/ml/calibration/simulate", json=payload)
        # Should return 200 with error, 500, or 520 (server error)
        assert response.status_code in [200, 500, 520]
        
        data = response.json()
        # Either success false or error message
        assert 'success' in data or 'error' in data


class TestCalibrationAttackTests:
    """Tests for POST /api/ml/calibration/attack-tests"""
    
    def test_run_attack_tests(self):
        """Test running attack tests"""
        response = requests.post(f"{BASE_URL}/api/ml/calibration/attack-tests")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'totalTests' in data
        assert 'passed' in data
        assert 'failed' in data
        assert 'results' in data
        
        # Verify all 5 tests are present
        assert data['totalTests'] == 5
        assert len(data['results']) == 5
    
    def test_attack_tests_all_pass(self):
        """Test that all attack tests pass"""
        response = requests.post(f"{BASE_URL}/api/ml/calibration/attack-tests")
        assert response.status_code == 200
        
        data = response.json()
        assert data['passed'] == 5
        assert data['failed'] == 0
    
    def test_attack_test_structure(self):
        """Test attack test result structure"""
        response = requests.post(f"{BASE_URL}/api/ml/calibration/attack-tests")
        assert response.status_code == 200
        
        data = response.json()
        for test in data['results']:
            assert 'id' in test
            assert 'name' in test
            assert 'category' in test
            assert 'passed' in test
            assert 'details' in test
            assert 'expected' in test
            assert 'actual' in test
    
    def test_attack_test_categories(self):
        """Test that attack tests cover all categories"""
        response = requests.post(f"{BASE_URL}/api/ml/calibration/attack-tests")
        assert response.status_code == 200
        
        data = response.json()
        categories = {test['category'] for test in data['results']}
        expected_categories = {'DATA', 'CALIBRATION', 'CHEATING', 'TEMPORAL', 'SYSTEM'}
        assert categories == expected_categories


class TestCalibrationDisable:
    """Tests for POST /api/ml/calibration/disable"""
    
    def test_disable_calibration(self):
        """Test disabling calibration"""
        payload = {'window': '7d', 'reason': 'Test disable'}
        response = requests.post(f"{BASE_URL}/api/ml/calibration/disable", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        
        # Verify calibration is disabled
        status_response = requests.get(f"{BASE_URL}/api/ml/calibration/active", params={'window': '7d'})
        status_data = status_response.json()
        assert status_data['status'] == 'DISABLED'


class TestCalibrationTemporalSimulation:
    """Tests for POST /api/ml/calibration/simulate-temporal"""
    
    def test_temporal_simulation(self):
        """Test temporal simulation endpoint"""
        payload = {
            'window': '7d',
            'hoursToSimulate': 96,
            'scenario': 'stable'
        }
        response = requests.post(f"{BASE_URL}/api/ml/calibration/simulate-temporal", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'result' in data
        assert 'recommendation' in data['result']


class TestHealthEndpoint:
    """Tests for system health"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
