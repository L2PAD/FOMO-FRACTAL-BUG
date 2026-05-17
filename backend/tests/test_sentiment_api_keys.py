"""
Sentiment API v1 - API Key Management Tests
============================================
Tests for the Admin Sentiment API page features:
- API key CRUD operations (create, list, revoke, delete)
- Public endpoints (health, metrics, capabilities, config)
- API key authentication for protected endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')
API_PREFIX = f"{BASE_URL}/api/v1/sentiment"


class TestPublicEndpoints:
    """Test public endpoints that don't require API key authentication"""
    
    def test_health_endpoint(self):
        """GET /api/v1/sentiment/health returns READY status"""
        response = requests.get(f"{API_PREFIX}/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "data" in data
        assert data["data"]["status"] == "READY"
        assert "uptime" in data["data"]
        assert "cache" in data["data"]
        print(f"✓ Health endpoint: status={data['data']['status']}")
    
    def test_capabilities_endpoint(self):
        """GET /api/v1/sentiment/capabilities returns engine capabilities"""
        response = requests.get(f"{API_PREFIX}/capabilities")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "data" in data
        assert "supportedSources" in data["data"]
        assert "lexiconStats" in data["data"]
        print(f"✓ Capabilities endpoint: sources={len(data['data']['supportedSources'])}")
    
    def test_metrics_endpoint(self):
        """GET /api/v1/sentiment/metrics returns usage metrics"""
        response = requests.get(f"{API_PREFIX}/metrics")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "data" in data
        assert "requests" in data["data"]
        assert "cache" in data["data"]
        assert "latency" in data["data"]
        assert "labels" in data["data"]
        print(f"✓ Metrics endpoint: total requests={data['data']['requests']['total']}")
    
    def test_config_endpoint(self):
        """GET /api/v1/sentiment/config returns server configuration"""
        response = requests.get(f"{API_PREFIX}/config")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "data" in data
        assert "mode" in data["data"]
        assert "url" in data["data"]
        print(f"✓ Config endpoint: mode={data['data']['mode']}, url={data['data']['url']}")


class TestApiKeyManagement:
    """Test API key CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Store created key prefixes for cleanup"""
        self.created_key_prefixes = []
        yield
        # Cleanup: Delete test keys
        for prefix in self.created_key_prefixes:
            try:
                requests.delete(f"{API_PREFIX}/keys", json={"prefix": prefix, "permanent": True})
            except:
                pass
    
    def test_list_keys(self):
        """GET /api/v1/sentiment/keys returns list of API keys"""
        response = requests.get(f"{API_PREFIX}/keys")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "data" in data
        assert isinstance(data["data"], list)
        print(f"✓ List keys: {len(data['data'])} keys found")
        
        # Verify key structure (if keys exist)
        if len(data["data"]) > 0:
            key = data["data"][0]
            assert "prefix" in key
            assert "name" in key
            assert "active" in key
            assert "requests" in key
            print(f"  First key: name={key['name']}, active={key['active']}")
    
    def test_create_key(self):
        """POST /api/v1/sentiment/keys creates a new API key"""
        key_name = "TEST-pytest-key"
        response = requests.post(
            f"{API_PREFIX}/keys",
            json={"name": key_name}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "data" in data
        assert "key" in data["data"]  # Full key shown only on creation
        assert "prefix" in data["data"]
        assert "name" in data["data"]
        assert data["data"]["name"] == key_name
        
        # Store for cleanup
        self.created_key_prefixes.append(data["data"]["prefix"])
        print(f"✓ Created key: name={key_name}, prefix={data['data']['prefix']}")
        
        # Verify key appears in list
        list_response = requests.get(f"{API_PREFIX}/keys")
        list_data = list_response.json()
        key_found = any(k["name"] == key_name for k in list_data["data"])
        assert key_found, f"Key {key_name} not found in list after creation"
        print(f"✓ Key verified in list")
    
    def test_create_key_invalid_name(self):
        """POST /api/v1/sentiment/keys with invalid name returns 400"""
        response = requests.post(
            f"{API_PREFIX}/keys",
            json={"name": "a"}  # Too short (min 2 chars)
        )
        assert response.status_code == 400
        
        data = response.json()
        assert data["ok"] == False
        print(f"✓ Invalid name rejected: {data.get('error', data.get('message'))}")
    
    def test_revoke_key(self):
        """DELETE /api/v1/sentiment/keys revokes a key (sets active=false)"""
        # First create a key
        key_name = "TEST-revoke-key"
        create_response = requests.post(
            f"{API_PREFIX}/keys",
            json={"name": key_name}
        )
        assert create_response.status_code == 200
        prefix = create_response.json()["data"]["prefix"]
        self.created_key_prefixes.append(prefix)
        
        # Revoke the key
        revoke_response = requests.delete(
            f"{API_PREFIX}/keys",
            json={"prefix": prefix}  # No permanent flag = revoke only
        )
        assert revoke_response.status_code == 200
        print(f"✓ Key revoked: prefix={prefix}")
        
        # Verify key is now inactive
        list_response = requests.get(f"{API_PREFIX}/keys")
        list_data = list_response.json()
        revoked_key = next((k for k in list_data["data"] if k["prefix"] == prefix), None)
        assert revoked_key is not None, "Key not found in list"
        assert revoked_key["active"] == False, "Key should be inactive after revoke"
        print(f"✓ Key verified as revoked (active=false)")
    
    def test_delete_key_permanently(self):
        """DELETE /api/v1/sentiment/keys with permanent=true deletes key"""
        # First create a key
        key_name = "TEST-delete-key"
        create_response = requests.post(
            f"{API_PREFIX}/keys",
            json={"name": key_name}
        )
        assert create_response.status_code == 200
        prefix = create_response.json()["data"]["prefix"]
        
        # Delete the key permanently
        delete_response = requests.delete(
            f"{API_PREFIX}/keys",
            json={"prefix": prefix, "permanent": True}
        )
        assert delete_response.status_code == 200
        print(f"✓ Key permanently deleted: prefix={prefix}")
        
        # Verify key is no longer in list
        list_response = requests.get(f"{API_PREFIX}/keys")
        list_data = list_response.json()
        key_found = any(k["prefix"] == prefix for k in list_data["data"])
        assert not key_found, "Key should not be in list after permanent deletion"
        print(f"✓ Key verified as deleted from list")


class TestApiKeyAuthentication:
    """Test that protected endpoints require valid API key"""
    
    def test_analyze_without_key_returns_401(self):
        """POST /api/v1/sentiment/analyze without API key returns 401"""
        response = requests.post(
            f"{API_PREFIX}/analyze",
            json={"text": "Test text", "source": "twitter"}
        )
        assert response.status_code == 401
        
        data = response.json()
        assert data["ok"] == False
        assert data["error"] == "UNAUTHORIZED"
        print(f"✓ Analyze without key: 401 Unauthorized")
    
    def test_analyze_with_valid_key(self):
        """POST /api/v1/sentiment/analyze with valid API key works"""
        # First create a key
        create_response = requests.post(
            f"{API_PREFIX}/keys",
            json={"name": "TEST-auth-key"}
        )
        assert create_response.status_code == 200
        api_key = create_response.json()["data"]["key"]
        prefix = create_response.json()["data"]["prefix"]
        
        try:
            # Use the key to analyze
            response = requests.post(
                f"{API_PREFIX}/analyze",
                headers={"X-API-Key": api_key},
                json={"text": "Bitcoin is very bullish today!", "source": "twitter"}
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["ok"] == True
            assert "data" in data
            assert "label" in data["data"]
            assert "score" in data["data"]
            print(f"✓ Analyze with key: label={data['data']['label']}, score={data['data']['score']}")
        finally:
            # Cleanup
            requests.delete(f"{API_PREFIX}/keys", json={"prefix": prefix, "permanent": True})
    
    def test_analyze_with_revoked_key_returns_403(self):
        """POST /api/v1/sentiment/analyze with revoked key returns 403"""
        # Create a key
        create_response = requests.post(
            f"{API_PREFIX}/keys",
            json={"name": "TEST-revoked-auth-key"}
        )
        assert create_response.status_code == 200
        api_key = create_response.json()["data"]["key"]
        prefix = create_response.json()["data"]["prefix"]
        
        try:
            # Revoke the key
            requests.delete(f"{API_PREFIX}/keys", json={"prefix": prefix})
            
            # Try to use revoked key
            response = requests.post(
                f"{API_PREFIX}/analyze",
                headers={"X-API-Key": api_key},
                json={"text": "Test text", "source": "twitter"}
            )
            assert response.status_code == 403
            
            data = response.json()
            assert data["ok"] == False
            assert data["error"] == "FORBIDDEN"
            print(f"✓ Revoked key rejected: 403 Forbidden")
        finally:
            # Cleanup
            requests.delete(f"{API_PREFIX}/keys", json={"prefix": prefix, "permanent": True})


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
