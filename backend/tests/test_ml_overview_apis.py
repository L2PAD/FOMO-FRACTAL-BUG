"""
ML Overview APIs Test Suite
Tests for ML Overview page backend endpoints:
- /api/v4/admin/runtime/system-metrics
- /api/v4/admin/runtime/overview
- /api/v4/admin/runtime/kill-switch
- /api/v4/admin/runtime/soft-stop
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSystemMetricsEndpoint:
    """Tests for /api/v4/admin/runtime/system-metrics endpoint"""
    
    def test_system_metrics_returns_200(self):
        """System metrics endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/system-metrics")
        assert response.status_code == 200
        print(f"✓ system-metrics returns 200")
    
    def test_system_metrics_response_structure(self):
        """System metrics should return valid JSON with required fields"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/system-metrics")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True, "Response should have ok=true"
        
        # Check top-level fields
        response_data = data.get('data', {})
        assert 'system' in response_data, "Should have 'system' field"
        assert 'memory' in response_data, "Should have 'memory' field"
        assert 'process' in response_data, "Should have 'process' field"
        assert 'dataFreshness' in response_data, "Should have 'dataFreshness' field"
        assert 'services' in response_data, "Should have 'services' field"
        print(f"✓ system-metrics has all required top-level fields")
    
    def test_system_metrics_system_fields(self):
        """System section should have CPU and uptime info"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/system-metrics")
        data = response.json()
        
        system = data['data']['system']
        assert 'cpuCount' in system, "System should have cpuCount"
        assert 'loadAvg1m' in system, "System should have loadAvg1m"
        assert 'uptimeHours' in system, "System should have uptimeHours"
        assert 'platform' in system, "System should have platform"
        print(f"✓ system-metrics.system has CPU and uptime fields")
    
    def test_system_metrics_process_fields(self):
        """Process section should have Node version"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/system-metrics")
        data = response.json()
        
        process = data['data']['process']
        assert 'nodeVersion' in process, "Process should have nodeVersion"
        assert 'memoryMB' in process, "Process should have memoryMB"
        assert 'heapTotalMB' in process, "Process should have heapTotalMB"
        print(f"✓ system-metrics.process has Node version")
    
    def test_system_metrics_data_freshness(self):
        """Data freshness should have 6 data sources"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/system-metrics")
        data = response.json()
        
        freshness = data['data']['dataFreshness']
        expected_sources = ['sentiment', 'twitter', 'exchange', 'predictions', 'onchain', 'signals']
        
        for source in expected_sources:
            assert source in freshness, f"DataFreshness should have '{source}'"
            src_data = freshness[source]
            assert 'label' in src_data, f"{source} should have 'label'"
            assert 'status' in src_data, f"{source} should have 'status'"
        
        print(f"✓ system-metrics.dataFreshness has all 6 data sources")
    
    def test_system_metrics_services(self):
        """Services should show MongoDB and API Server status"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/system-metrics")
        data = response.json()
        
        services = data['data']['services']
        
        # MongoDB
        assert 'mongodb' in services, "Services should have 'mongodb'"
        mongodb = services['mongodb']
        assert 'status' in mongodb, "MongoDB should have status"
        assert 'label' in mongodb, "MongoDB should have label"
        
        # API Server
        assert 'fastify' in services, "Services should have 'fastify'"
        fastify = services['fastify']
        assert 'status' in fastify, "Fastify should have status"
        assert 'label' in fastify, "Fastify should have label"
        
        print(f"✓ system-metrics.services has MongoDB and API Server")


class TestOverviewEndpoint:
    """Tests for /api/v4/admin/runtime/overview endpoint"""
    
    def test_overview_returns_200(self):
        """Overview endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/overview")
        assert response.status_code == 200
        print(f"✓ overview returns 200")
    
    def test_overview_response_structure(self):
        """Overview should return valid JSON with required fields"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/overview")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True, "Response should have ok=true"
        
        response_data = data.get('data', {})
        assert 'health' in response_data, "Should have 'health' field"
        assert 'ram' in response_data, "Should have 'ram' field"
        assert 'modules' in response_data, "Should have 'modules' field"
        assert 'killSwitch' in response_data, "Should have 'killSwitch' field"
        print(f"✓ overview has all required top-level fields")
    
    def test_overview_health_status(self):
        """Health should have status and reasons"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/overview")
        data = response.json()
        
        health = data['data']['health']
        assert 'status' in health, "Health should have status"
        assert health['status'] in ['OK', 'DEGRADED', 'CRITICAL'], "Status should be valid"
        assert 'reasons' in health, "Health should have reasons"
        assert isinstance(health['reasons'], list), "Reasons should be a list"
        print(f"✓ overview.health has valid status: {health['status']}")
    
    def test_overview_modules(self):
        """Modules should have sentiment, twitter, automation"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/overview")
        data = response.json()
        
        modules = data['data']['modules']
        
        # Sentiment
        assert 'sentiment' in modules, "Should have 'sentiment' module"
        sentiment = modules['sentiment']
        assert 'enabled' in sentiment
        assert 'mode' in sentiment
        assert 'status' in sentiment
        
        # Twitter
        assert 'twitter' in modules, "Should have 'twitter' module"
        twitter = modules['twitter']
        assert 'parserEnabled' in twitter
        assert 'sentimentEnabled' in twitter
        assert 'status' in twitter
        
        # Automation
        assert 'automation' in modules, "Should have 'automation' module"
        automation = modules['automation']
        assert 'enabled' in automation
        assert 'running' in automation
        assert 'status' in automation
        
        print(f"✓ overview.modules has sentiment, twitter, automation")
    
    def test_overview_kill_switch(self):
        """KillSwitch should have global and softStop flags"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/overview")
        data = response.json()
        
        kill_switch = data['data']['killSwitch']
        assert 'global' in kill_switch, "KillSwitch should have 'global'"
        assert 'softStop' in kill_switch, "KillSwitch should have 'softStop'"
        assert isinstance(kill_switch['global'], bool), "global should be boolean"
        assert isinstance(kill_switch['softStop'], bool), "softStop should be boolean"
        print(f"✓ overview.killSwitch has global and softStop flags")


class TestKillSwitchEndpoint:
    """Tests for /api/v4/admin/runtime/kill-switch endpoint"""
    
    def test_kill_switch_activate_deactivate(self):
        """Kill switch should activate and deactivate"""
        # Activate
        response = requests.post(
            f"{BASE_URL}/api/v4/admin/runtime/kill-switch",
            json={"activate": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'KILL SWITCH ACTIVATED' in data.get('message', '').upper()
        print(f"✓ kill-switch activated")
        
        # Verify via overview
        overview_response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/overview")
        overview_data = overview_response.json()
        assert overview_data['data']['killSwitch']['global'] == True
        print(f"✓ kill-switch state verified via overview")
        
        # Deactivate
        response = requests.post(
            f"{BASE_URL}/api/v4/admin/runtime/kill-switch",
            json={"activate": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"✓ kill-switch deactivated")
        
        # Verify via overview
        overview_response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/overview")
        overview_data = overview_response.json()
        assert overview_data['data']['killSwitch']['global'] == False
        print(f"✓ kill-switch deactivation verified")


class TestSoftStopEndpoint:
    """Tests for /api/v4/admin/runtime/soft-stop endpoint"""
    
    def test_soft_stop_activate_deactivate(self):
        """Soft stop should activate and deactivate"""
        # Activate
        response = requests.post(
            f"{BASE_URL}/api/v4/admin/runtime/soft-stop",
            json={"activate": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"✓ soft-stop activated")
        
        # Verify via overview
        overview_response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/overview")
        overview_data = overview_response.json()
        assert overview_data['data']['killSwitch']['softStop'] == True
        print(f"✓ soft-stop state verified via overview")
        
        # Deactivate
        response = requests.post(
            f"{BASE_URL}/api/v4/admin/runtime/soft-stop",
            json={"activate": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"✓ soft-stop deactivated")
        
        # Verify via overview
        overview_response = requests.get(f"{BASE_URL}/api/v4/admin/runtime/overview")
        overview_data = overview_response.json()
        assert overview_data['data']['killSwitch']['softStop'] == False
        print(f"✓ soft-stop deactivation verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
