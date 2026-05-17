"""
Z1 + Y2 - Bybit USDT Perp Provider + Admin Exchange Control Tests
=================================================================

Tests for:
- Z1: Bybit USDT Perpetual provider registration and connectivity
- Y2: Admin Exchange Control API operations

Provider Priority: Bybit (100) > Binance (90) > Mock (1)
Expected: Bybit and Binance return HTTP errors due to regional blocks
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestProviderList:
    """Test provider listing with 3 providers including Bybit"""
    
    def test_list_providers_returns_three_providers(self):
        """Should return 3 providers: BYBIT_USDTPERP, BINANCE_USDM, MOCK"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/admin/providers")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert len(data['providers']) == 3
        
        provider_ids = [p['id'] for p in data['providers']]
        assert 'BYBIT_USDTPERP' in provider_ids
        assert 'BINANCE_USDM' in provider_ids
        assert 'MOCK' in provider_ids
    
    def test_provider_priority_order(self):
        """Bybit priority 100 > Binance 90 > Mock 1"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/admin/providers")
        assert response.status_code == 200
        
        data = response.json()
        providers = {p['id']: p for p in data['providers']}
        
        assert providers['BYBIT_USDTPERP']['priority'] == 100
        assert providers['BINANCE_USDM']['priority'] == 90
        assert providers['MOCK']['priority'] == 1
    
    def test_all_providers_enabled(self):
        """All 3 providers should be enabled by default"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/admin/providers")
        assert response.status_code == 200
        
        data = response.json()
        for provider in data['providers']:
            assert provider['enabled'] is True
    
    def test_providers_have_health_status(self):
        """All providers should have health status"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/admin/providers")
        assert response.status_code == 200
        
        data = response.json()
        for provider in data['providers']:
            assert 'health' in provider
            assert 'status' in provider['health']
            assert provider['health']['status'] in ['UP', 'DEGRADED', 'DOWN']


class TestBybitProvider:
    """Tests specific to BYBIT_USDTPERP provider"""
    
    def test_get_bybit_provider_details(self):
        """Get BYBIT_USDTPERP provider details"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/admin/providers/BYBIT_USDTPERP")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['provider']['id'] == 'BYBIT_USDTPERP'
        assert data['provider']['priority'] == 100
        assert data['provider']['enabled'] is True
    
    def test_bybit_connectivity_returns_403(self):
        """Bybit test should return 403 due to regional restriction"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/admin/providers/BYBIT_USDTPERP/test",
            json={'symbol': 'BTCUSDT'}
        )
        assert response.status_code == 200  # API returns 200, ok: false in body
        
        data = response.json()
        assert data['ok'] is False
        assert 'BYBIT_USDTPERP' in data.get('providerId', '')
        assert 'latencyMs' in data
        # Error should indicate HTTP 403
        assert '403' in data.get('error', '')
    
    def test_bybit_reset_circuit_breaker(self):
        """Reset Bybit circuit breaker"""
        response = requests.post(f"{BASE_URL}/api/v10/exchange/admin/providers/BYBIT_USDTPERP/reset")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True


class TestMockProvider:
    """Tests for MOCK provider (always available fallback)"""
    
    def test_mock_connectivity_succeeds(self):
        """MOCK provider should always succeed"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/admin/providers/MOCK/test",
            json={'symbol': 'BTCUSDT'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['providerId'] == 'MOCK'
        assert 'sample' in data
        assert 'mid' in data['sample']
        assert data['sample']['mid'] > 0
    
    def test_mock_has_lowest_priority(self):
        """MOCK should have priority 1 (lowest)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/admin/providers/MOCK")
        assert response.status_code == 200
        
        data = response.json()
        assert data['provider']['priority'] == 1


class TestBinanceProvider:
    """Tests for BINANCE_USDM provider"""
    
    def test_binance_connectivity_returns_451(self):
        """Binance test should return 451 due to regional restriction"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/admin/providers/BINANCE_USDM/test",
            json={'symbol': 'BTCUSDT'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is False
        assert '451' in data.get('error', '')


class TestProviderPatching:
    """Test provider configuration updates"""
    
    def test_patch_bybit_priority(self):
        """Change Bybit priority and verify"""
        original = requests.get(f"{BASE_URL}/api/v10/exchange/admin/providers/BYBIT_USDTPERP").json()
        original_priority = original['provider']['priority']
        
        # Update priority
        response = requests.patch(
            f"{BASE_URL}/api/v10/exchange/admin/providers/BYBIT_USDTPERP",
            json={'priority': 95}
        )
        assert response.status_code == 200
        
        # Verify update
        updated = requests.get(f"{BASE_URL}/api/v10/exchange/admin/providers/BYBIT_USDTPERP").json()
        assert updated['provider']['priority'] == 95
        
        # Restore original
        requests.patch(
            f"{BASE_URL}/api/v10/exchange/admin/providers/BYBIT_USDTPERP",
            json={'priority': original_priority}
        )
    
    def test_disable_enable_bybit(self):
        """Disable and re-enable Bybit provider"""
        # Disable
        response = requests.patch(
            f"{BASE_URL}/api/v10/exchange/admin/providers/BYBIT_USDTPERP",
            json={'enabled': False}
        )
        assert response.status_code == 200
        
        # Verify disabled
        check = requests.get(f"{BASE_URL}/api/v10/exchange/admin/providers/BYBIT_USDTPERP").json()
        assert check['provider']['enabled'] is False
        
        # Re-enable
        response = requests.patch(
            f"{BASE_URL}/api/v10/exchange/admin/providers/BYBIT_USDTPERP",
            json={'enabled': True}
        )
        assert response.status_code == 200
        
        # Verify enabled
        check = requests.get(f"{BASE_URL}/api/v10/exchange/admin/providers/BYBIT_USDTPERP").json()
        assert check['provider']['enabled'] is True


class TestJobsAPI:
    """Test job listing and operations"""
    
    def test_list_jobs_returns_six_jobs(self):
        """Should return 6 jobs"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/admin/jobs")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert len(data['jobs']) == 6
    
    def test_job_ids_are_correct(self):
        """All expected job IDs present"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/admin/jobs")
        data = response.json()
        
        job_ids = [j['id'] for j in data['jobs']]
        expected_ids = ['exchangeTick', 'whaleIngest', 'indicatorCalculation', 
                       'regimeDetection', 'patternDetection', 'observationPersist']
        
        for expected in expected_ids:
            assert expected in job_ids
    
    def test_job_start_stop_cycle(self):
        """Start and stop a job"""
        job_id = 'exchangeTick'
        
        # Get initial state
        initial = requests.get(f"{BASE_URL}/api/v10/exchange/admin/jobs/{job_id}").json()
        
        if not initial['job']['running']:
            # Start job
            start_response = requests.post(f"{BASE_URL}/api/v10/exchange/admin/jobs/{job_id}/start")
            assert start_response.status_code == 200
            
            # Verify running
            running = requests.get(f"{BASE_URL}/api/v10/exchange/admin/jobs/{job_id}").json()
            assert running['job']['running'] is True
            
            # Stop job
            stop_response = requests.post(f"{BASE_URL}/api/v10/exchange/admin/jobs/{job_id}/stop")
            assert stop_response.status_code == 200
            
            # Verify stopped
            stopped = requests.get(f"{BASE_URL}/api/v10/exchange/admin/jobs/{job_id}").json()
            assert stopped['job']['running'] is False
    
    def test_job_run_once(self):
        """Run job once for diagnostic"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/admin/jobs/exchangeTick/run-once",
            json={'symbol': 'BTCUSDT'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True


class TestHealthOverview:
    """Test health overview endpoint with 3 providers"""
    
    def test_health_shows_three_providers(self):
        """Health should show 3 providers total"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/admin/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['providers']['total'] == 3
    
    def test_health_has_jobs_stats(self):
        """Health includes job statistics"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/admin/health")
        data = response.json()
        
        assert 'jobs' in data
        assert data['jobs']['total'] == 6
    
    def test_health_has_data_status(self):
        """Health includes data mode"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/admin/health")
        data = response.json()
        
        assert 'dataStatus' in data
        assert 'mode' in data['dataStatus']
        assert data['dataStatus']['mode'] in ['LIVE', 'MOCK', 'MIXED']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
