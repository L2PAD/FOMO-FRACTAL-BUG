"""
Phase 3: ML Training Sandbox API Tests

Tests for the isolated ML training sandbox infrastructure:
- GET /api/ml/sandbox/status - Sandbox status with gates info
- GET /api/ml/sandbox/runs - List of training runs
- GET /api/ml/sandbox/models - List of trained models
- POST /api/ml/sandbox/train - Start training (blocked due to insufficient data)
- POST /api/ml/train - Legacy endpoint disabled with redirect message
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSandboxStatus:
    """Test GET /api/ml/sandbox/status endpoint"""
    
    def test_sandbox_status_returns_ok(self):
        """Verify sandbox status endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/status")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
    def test_sandbox_status_has_sandbox_info(self):
        """Verify sandbox info contains required fields"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/status")
        data = response.json()
        
        sandbox = data['data']['sandbox']
        assert sandbox['enabled'] == True
        assert sandbox['isolated'] == True
        assert sandbox['engineConnected'] == False  # CRITICAL: Must be false
        assert sandbox['productionAccess'] == False  # CRITICAL: Must be false
        
    def test_sandbox_status_has_gates_info(self):
        """Verify gates info is present"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/status")
        data = response.json()
        
        gates = data['data']['gates']
        assert 'allowed' in gates
        assert 'reasons' in gates
        # Gates should be blocked due to insufficient data
        assert gates['allowed'] == False
        assert len(gates['reasons']) > 0
        assert any('DATASET_TOO_SMALL' in r for r in gates['reasons'])
        
    def test_sandbox_status_has_stats(self):
        """Verify stats info is present"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/status")
        data = response.json()
        
        stats = data['data']['stats']
        assert 'totalRuns' in stats
        assert 'successfulRuns' in stats
        assert isinstance(stats['totalRuns'], int)
        assert isinstance(stats['successfulRuns'], int)


class TestSandboxRuns:
    """Test GET /api/ml/sandbox/runs endpoint"""
    
    def test_sandbox_runs_returns_ok(self):
        """Verify runs endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/runs")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
    def test_sandbox_runs_returns_list(self):
        """Verify runs endpoint returns a list"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/runs")
        data = response.json()
        assert isinstance(data['data'], list)
        
    def test_sandbox_runs_with_limit(self):
        """Verify runs endpoint respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/runs?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data['data']) <= 5


class TestSandboxModels:
    """Test GET /api/ml/sandbox/models endpoint"""
    
    def test_sandbox_models_returns_ok(self):
        """Verify models endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/models")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
    def test_sandbox_models_has_warning(self):
        """Verify models endpoint includes sandbox warning"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/models")
        data = response.json()
        assert 'warning' in data['data']
        assert 'SANDBOX ONLY' in data['data']['warning']
        
    def test_sandbox_models_returns_list(self):
        """Verify models endpoint returns a list"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/models")
        data = response.json()
        assert isinstance(data['data']['models'], list)


class TestSandboxTrain:
    """Test POST /api/ml/sandbox/train endpoint"""
    
    def test_sandbox_train_blocked_insufficient_data(self):
        """Verify training is blocked due to insufficient data"""
        response = requests.post(
            f"{BASE_URL}/api/ml/sandbox/train",
            json={"modelType": "confidence_calibrator", "horizon": "7d"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Training should be blocked
        assert data['ok'] == False
        assert data['error'] == 'TRAINING_BLOCKED'
        
    def test_sandbox_train_returns_block_reasons(self):
        """Verify blocked training returns reasons"""
        response = requests.post(
            f"{BASE_URL}/api/ml/sandbox/train",
            json={"modelType": "confidence_calibrator", "horizon": "7d"}
        )
        data = response.json()
        
        assert 'data' in data
        assert 'blockReasons' in data['data']
        assert len(data['data']['blockReasons']) > 0
        assert any('DATASET_TOO_SMALL' in r for r in data['data']['blockReasons'])
        
    def test_sandbox_train_creates_blocked_run(self):
        """Verify blocked training creates a run record"""
        response = requests.post(
            f"{BASE_URL}/api/ml/sandbox/train",
            json={"modelType": "outcome_model", "horizon": "30d"}
        )
        data = response.json()
        
        assert 'data' in data
        assert 'runId' in data['data']
        assert data['data']['runId'].startswith('blocked_')
        
        # Verify run appears in runs list
        runs_response = requests.get(f"{BASE_URL}/api/ml/sandbox/runs")
        runs_data = runs_response.json()
        run_ids = [r['runId'] for r in runs_data['data']]
        assert data['data']['runId'] in run_ids


class TestLegacyTrainEndpoint:
    """Test POST /api/ml/train legacy endpoint is disabled"""
    
    def test_legacy_train_disabled(self):
        """Verify legacy train endpoint returns ENDPOINT_DISABLED"""
        response = requests.post(
            f"{BASE_URL}/api/ml/train",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] == False
        assert data['error'] == 'ENDPOINT_DISABLED'
        
    def test_legacy_train_has_redirect(self):
        """Verify legacy train endpoint provides redirect info"""
        response = requests.post(
            f"{BASE_URL}/api/ml/train",
            json={}
        )
        data = response.json()
        
        assert 'redirect' in data
        assert data['redirect'] == '/api/ml/sandbox/train'
        
    def test_legacy_train_has_message(self):
        """Verify legacy train endpoint has helpful message"""
        response = requests.post(
            f"{BASE_URL}/api/ml/train",
            json={}
        )
        data = response.json()
        
        assert 'message' in data
        assert 'sandbox' in data['message'].lower()


class TestSandboxRunDetails:
    """Test GET /api/ml/sandbox/runs/:runId endpoint"""
    
    def test_get_run_details(self):
        """Verify can get details of a specific run"""
        # First get list of runs
        runs_response = requests.get(f"{BASE_URL}/api/ml/sandbox/runs")
        runs_data = runs_response.json()
        
        if len(runs_data['data']) > 0:
            run_id = runs_data['data'][0]['runId']
            
            # Get run details
            response = requests.get(f"{BASE_URL}/api/ml/sandbox/runs/{run_id}")
            assert response.status_code == 200
            data = response.json()
            
            assert data['ok'] == True
            assert data['data']['runId'] == run_id
            assert 'status' in data['data']
            assert 'modelType' in data['data']
            assert 'horizon' in data['data']
        else:
            pytest.skip("No runs available to test")
            
    def test_get_nonexistent_run(self):
        """Verify 404 for nonexistent run"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/runs/nonexistent_run_id")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] == False
        assert data['error'] == 'NOT_FOUND'


class TestSandboxMetrics:
    """Test GET /api/ml/sandbox/metrics/:runId endpoint"""
    
    def test_get_metrics_for_run(self):
        """Verify can get metrics for a specific run"""
        # First get list of runs
        runs_response = requests.get(f"{BASE_URL}/api/ml/sandbox/runs")
        runs_data = runs_response.json()
        
        if len(runs_data['data']) > 0:
            run_id = runs_data['data'][0]['runId']
            
            # Get metrics
            response = requests.get(f"{BASE_URL}/api/ml/sandbox/metrics/{run_id}")
            assert response.status_code == 200
            data = response.json()
            
            assert data['ok'] == True
            assert data['data']['runId'] == run_id
            assert 'status' in data['data']
            assert 'metrics' in data['data']
            assert 'datasetStats' in data['data']
        else:
            pytest.skip("No runs available to test")


class TestSandboxIsolation:
    """Test sandbox isolation guarantees"""
    
    def test_engine_never_connected(self):
        """Verify engineConnected is always false"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/status")
        data = response.json()
        
        # This is a CRITICAL safety check
        assert data['data']['sandbox']['engineConnected'] == False
        
    def test_production_access_never_allowed(self):
        """Verify productionAccess is always false"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/status")
        data = response.json()
        
        # This is a CRITICAL safety check
        assert data['data']['sandbox']['productionAccess'] == False
        
    def test_models_not_connected_to_engine(self):
        """Verify models show NOT connected to engine"""
        response = requests.get(f"{BASE_URL}/api/ml/sandbox/models")
        data = response.json()
        
        for model in data['data']['models']:
            assert model.get('connectedToEngine') == False
            assert model.get('productionReady') == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
