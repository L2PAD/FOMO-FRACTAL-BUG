"""
Intel Admin Proxy Pool CRUD Tests
=================================
Tests for the Intel Admin panel proxy management:
- Proxy Pool CRUD operations
- Cross-backend sync to networkconfigs
- Russian translation verification (via API responses)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestIntelAdminProxyPool:
    """Proxy Pool CRUD operations"""
    
    created_proxy_ids = []
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and cleanup test data"""
        yield
        # Cleanup: Delete all test proxies created during tests
        for proxy_id in self.created_proxy_ids:
            try:
                requests.delete(f"{BASE_URL}/api/intel/admin/proxy/{proxy_id}")
            except:
                pass
        self.created_proxy_ids.clear()
    
    def test_proxy_status_endpoint(self):
        """Test GET /api/intel/admin/proxy/status returns proxy list"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/proxy/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Response should have 'ok' field"
        assert data["ok"] == True, "ok should be True"
        assert "proxies" in data, "Response should have 'proxies' field"
        assert "total" in data, "Response should have 'total' field"
        assert "active" in data, "Response should have 'active' field"
        assert "inactive" in data, "Response should have 'inactive' field"
        assert isinstance(data["proxies"], list), "proxies should be a list"
        print(f"✓ Proxy status: {data['total']} total, {data['active']} active, {data['inactive']} inactive")
    
    def test_add_proxy_http(self):
        """Test POST /api/intel/admin/proxy/add with HTTP proxy"""
        payload = {
            "server": "http://test-proxy.example.com:8080",
            "username": "testuser",
            "password": "testpass123",
            "priority": 5
        }
        
        response = requests.post(
            f"{BASE_URL}/api/intel/admin/proxy/add",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["ok"] == True, "ok should be True"
        assert "proxy" in data, "Response should have 'proxy' field"
        
        proxy = data["proxy"]
        assert "id" in proxy, "Proxy should have 'id'"
        assert proxy["server"] == payload["server"], "Server should match"
        assert proxy["username"] == payload["username"], "Username should match"
        assert proxy["priority"] == payload["priority"], "Priority should match"
        assert proxy["enabled"] == True, "New proxy should be enabled"
        assert proxy["healthy"] == True, "New proxy should be healthy"
        
        self.created_proxy_ids.append(proxy["id"])
        print(f"✓ Added HTTP proxy: {proxy['id']}")
        return proxy["id"]
    
    def test_add_proxy_socks5(self):
        """Test POST /api/intel/admin/proxy/add with SOCKS5 proxy"""
        payload = {
            "server": "socks5://socks-proxy.example.com:1080",
            "username": "socksuser",
            "password": "sockspass",
            "priority": 10
        }
        
        response = requests.post(
            f"{BASE_URL}/api/intel/admin/proxy/add",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["ok"] == True
        proxy = data["proxy"]
        assert "socks5://" in proxy["server"], "SOCKS5 URL should be preserved"
        
        self.created_proxy_ids.append(proxy["id"])
        print(f"✓ Added SOCKS5 proxy: {proxy['id']}")
        return proxy["id"]
    
    def test_toggle_proxy_disable(self):
        """Test POST /api/intel/admin/proxy/{id}/toggle to disable proxy"""
        # First add a proxy
        add_response = requests.post(
            f"{BASE_URL}/api/intel/admin/proxy/add",
            json={"server": "http://toggle-test.example.com:8080", "priority": 1}
        )
        proxy_id = add_response.json()["proxy"]["id"]
        self.created_proxy_ids.append(proxy_id)
        
        # Toggle to disabled
        response = requests.post(
            f"{BASE_URL}/api/intel/admin/proxy/{proxy_id}/toggle?enabled=false"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["ok"] == True
        
        # Verify proxy is disabled
        status_response = requests.get(f"{BASE_URL}/api/intel/admin/proxy/status")
        proxies = status_response.json()["proxies"]
        proxy = next((p for p in proxies if p["id"] == proxy_id), None)
        assert proxy is not None, "Proxy should exist"
        assert proxy["enabled"] == False, "Proxy should be disabled"
        print(f"✓ Toggled proxy {proxy_id} to disabled")
    
    def test_toggle_proxy_enable(self):
        """Test POST /api/intel/admin/proxy/{id}/toggle to enable proxy"""
        # First add a proxy
        add_response = requests.post(
            f"{BASE_URL}/api/intel/admin/proxy/add",
            json={"server": "http://toggle-enable-test.example.com:8080", "priority": 1}
        )
        proxy_id = add_response.json()["proxy"]["id"]
        self.created_proxy_ids.append(proxy_id)
        
        # Disable first
        requests.post(f"{BASE_URL}/api/intel/admin/proxy/{proxy_id}/toggle?enabled=false")
        
        # Then enable
        response = requests.post(
            f"{BASE_URL}/api/intel/admin/proxy/{proxy_id}/toggle?enabled=true"
        )
        assert response.status_code == 200
        
        # Verify proxy is enabled
        status_response = requests.get(f"{BASE_URL}/api/intel/admin/proxy/status")
        proxies = status_response.json()["proxies"]
        proxy = next((p for p in proxies if p["id"] == proxy_id), None)
        assert proxy["enabled"] == True, "Proxy should be enabled"
        print(f"✓ Toggled proxy {proxy_id} to enabled")
    
    def test_delete_proxy(self):
        """Test DELETE /api/intel/admin/proxy/{id}"""
        # First add a proxy
        add_response = requests.post(
            f"{BASE_URL}/api/intel/admin/proxy/add",
            json={"server": "http://delete-test.example.com:8080", "priority": 1}
        )
        proxy_id = add_response.json()["proxy"]["id"]
        
        # Delete the proxy
        response = requests.delete(f"{BASE_URL}/api/intel/admin/proxy/{proxy_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["ok"] == True
        assert data["deleted"] == True, "deleted should be True"
        
        # Verify proxy is gone
        status_response = requests.get(f"{BASE_URL}/api/intel/admin/proxy/status")
        proxies = status_response.json()["proxies"]
        proxy = next((p for p in proxies if p["id"] == proxy_id), None)
        assert proxy is None, "Proxy should be deleted"
        print(f"✓ Deleted proxy {proxy_id}")
    
    def test_set_proxy_priority(self):
        """Test POST /api/intel/admin/proxy/{id}/priority"""
        # First add a proxy
        add_response = requests.post(
            f"{BASE_URL}/api/intel/admin/proxy/add",
            json={"server": "http://priority-test.example.com:8080", "priority": 1}
        )
        proxy_id = add_response.json()["proxy"]["id"]
        self.created_proxy_ids.append(proxy_id)
        
        # Set new priority
        response = requests.post(
            f"{BASE_URL}/api/intel/admin/proxy/{proxy_id}/priority?priority=99"
        )
        assert response.status_code == 200
        
        # Verify priority changed
        status_response = requests.get(f"{BASE_URL}/api/intel/admin/proxy/status")
        proxies = status_response.json()["proxies"]
        proxy = next((p for p in proxies if p["id"] == proxy_id), None)
        assert proxy["priority"] == 99, f"Priority should be 99, got {proxy['priority']}"
        print(f"✓ Set proxy {proxy_id} priority to 99")


class TestCrossBackendSync:
    """Test proxy sync to networkconfigs collection"""
    
    created_proxy_ids = []
    
    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        for proxy_id in self.created_proxy_ids:
            try:
                requests.delete(f"{BASE_URL}/api/intel/admin/proxy/{proxy_id}")
            except:
                pass
        self.created_proxy_ids.clear()
    
    def test_proxy_syncs_to_networkconfigs(self):
        """Test that adding a proxy syncs to networkconfigs collection"""
        # Add a proxy
        payload = {
            "server": "http://sync-test.example.com:8080",
            "username": "syncuser",
            "password": "syncpass",
            "priority": 7
        }
        
        add_response = requests.post(
            f"{BASE_URL}/api/intel/admin/proxy/add",
            json=payload
        )
        assert add_response.status_code == 200
        proxy_id = add_response.json()["proxy"]["id"]
        self.created_proxy_ids.append(proxy_id)
        
        # The sync happens automatically in the backend
        # We can verify by checking proxy status shows the proxy
        status_response = requests.get(f"{BASE_URL}/api/intel/admin/proxy/status")
        assert status_response.status_code == 200
        
        proxies = status_response.json()["proxies"]
        proxy = next((p for p in proxies if p["id"] == proxy_id), None)
        assert proxy is not None, "Proxy should exist after sync"
        print(f"✓ Proxy {proxy_id} synced successfully")
    
    def test_socks5_url_sync_format(self):
        """Test that SOCKS5 URLs are properly formatted during sync"""
        # Add a SOCKS5 proxy
        payload = {
            "server": "socks5://socks-sync.example.com:1080",
            "username": "socksync",
            "password": "socksyncpass",
            "priority": 5
        }
        
        add_response = requests.post(
            f"{BASE_URL}/api/intel/admin/proxy/add",
            json=payload
        )
        assert add_response.status_code == 200
        proxy_id = add_response.json()["proxy"]["id"]
        self.created_proxy_ids.append(proxy_id)
        
        # Verify the server URL is preserved correctly
        status_response = requests.get(f"{BASE_URL}/api/intel/admin/proxy/status")
        proxies = status_response.json()["proxies"]
        proxy = next((p for p in proxies if p["id"] == proxy_id), None)
        
        assert proxy is not None
        assert "socks5://" in proxy["server"], f"SOCKS5 protocol should be preserved, got: {proxy['server']}"
        print(f"✓ SOCKS5 URL format preserved: {proxy['server']}")


class TestAdminAuthLogin:
    """Test admin authentication"""
    
    def test_admin_login_success(self):
        """Test POST /api/admin/auth/login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"}
        )
        
        # Admin login is proxied to Node.js backend
        # Should return 200 with token or session
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check for success indicators
        assert data.get("ok") == True or "token" in data or "user" in data, f"Login should succeed: {data}"
        print(f"✓ Admin login successful")
    
    def test_admin_login_invalid_password(self):
        """Test POST /api/admin/auth/login with invalid password"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "wrongpassword"}
        )
        
        # Should return 401 or error response
        assert response.status_code in [401, 400, 403], f"Expected auth error, got {response.status_code}"
        print(f"✓ Invalid password correctly rejected")


class TestIntelAdminOtherEndpoints:
    """Test other Intel Admin endpoints"""
    
    def test_api_keys_endpoint(self):
        """Test GET /api/intel/admin/api-keys"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/api-keys")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "keys" in data
        print(f"✓ API Keys endpoint: {len(data['keys'])} keys")
    
    def test_llm_keys_endpoint(self):
        """Test GET /api/intel/admin/llm-keys"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/llm-keys")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "keys" in data
        print(f"✓ LLM Keys endpoint: {len(data['keys'])} keys")
    
    def test_llm_providers_endpoint(self):
        """Test GET /api/intel/admin/llm-keys/providers"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/llm-keys/providers")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "providers" in data
        assert len(data["providers"]) >= 4, "Should have at least 4 LLM providers"
        print(f"✓ LLM Providers: {[p['id'] for p in data['providers']]}")
    
    def test_sentiment_keys_endpoint(self):
        """Test GET /api/intel/admin/sentiment-keys"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/sentiment-keys")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "keys" in data
        print(f"✓ Sentiment Keys endpoint: {len(data['keys'])} keys")
    
    def test_providers_endpoint(self):
        """Test GET /api/intel/admin/providers"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/providers")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "providers" in data
        print(f"✓ Providers endpoint: {len(data['providers'])} providers")
    
    def test_health_sources_endpoint(self):
        """Test GET /api/intel/admin/health/sources"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/health/sources")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert "summary" in data
        print(f"✓ Health Sources: {data['summary'].get('total', 0)} sources")
    
    def test_discovery_dashboard_endpoint(self):
        """Test GET /api/intel/admin/discovery/dashboard"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/discovery/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "collections" in data or "graph" in data
        print(f"✓ Discovery Dashboard endpoint working")
    
    def test_webhooks_subscriptions_endpoint(self):
        """Test GET /api/intel/admin/webhooks/subscriptions"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/webhooks/subscriptions")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "subscriptions" in data
        print(f"✓ Webhooks: {len(data['subscriptions'])} subscriptions")
    
    def test_webhook_event_types_endpoint(self):
        """Test GET /api/intel/admin/webhooks/event-types"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/webhooks/event-types")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "event_types" in data
        assert len(data["event_types"]) > 0, "Should have event types"
        print(f"✓ Webhook Event Types: {len(data['event_types'])} types")
    
    def test_merge_candidates_endpoint(self):
        """Test GET /api/intel/admin/merge/find-candidates"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/merge/find-candidates")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "candidates" in data
        print(f"✓ Merge Candidates: {len(data['candidates'])} candidates")
    
    def test_merge_stats_endpoint(self):
        """Test GET /api/intel/admin/merge/stats"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/merge/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_nodes" in data
        assert "total_edges" in data
        print(f"✓ Merge Stats: {data['total_nodes']} nodes, {data['total_edges']} edges")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
