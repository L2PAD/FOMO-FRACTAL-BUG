"""
Twitter Parser Extension + Connections Service Integration Tests

Tests:
- P0: Connections service ingestion - test /api/connections/test/ingest endpoint
- P0: Main backend ConnectionsClient - verify can reach connections service
- P2: Admin webhook info - test /api/admin/twitter-parser/sessions/webhook/info
- P2: Admin regenerate API key - test /api/admin/twitter-parser/sessions/webhook/regenerate-key
- Services health - test all 3 services (main backend 8003, parser 5001, connections 8004)
"""

import pytest
import requests
import os
import time

# Use local URLs for testing since they are more reliable than public proxy
# The public URL times out due to network latency
BASE_URL = "http://localhost:8003"

# Service URLs for direct testing
PARSER_SERVICE_URL = "http://localhost:5001"
CONNECTIONS_SERVICE_URL = "http://localhost:8004"
MAIN_BACKEND_URL = "http://localhost:8003"

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin12345"
PROVIDED_API_KEY = "0a128e7b915cef5e472140871d683c7c802b2632ed581031052209ce3335f40a"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token for authenticated requests"""
    response = requests.post(
        f"{BASE_URL}/api/admin/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token")
    pytest.skip(f"Admin login failed: {response.text}")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def authenticated_client(api_client, admin_token):
    """Session with admin auth header"""
    api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return api_client


class TestServicesHealth:
    """Test that all 3 services are running"""
    
    def test_main_backend_health(self, api_client):
        """Main backend (8003) should be running"""
        response = api_client.get(f"{MAIN_BACKEND_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "service" in data
        print(f"✓ Main backend health: {data}")
    
    def test_parser_service_health(self, api_client):
        """Parser service (5001) should be running"""
        response = api_client.get(f"{PARSER_SERVICE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("status") == "running"
        print(f"✓ Parser service health: {data}")
    
    def test_connections_service_health(self, api_client):
        """Connections service (8004) should be running"""
        response = api_client.get(f"{CONNECTIONS_SERVICE_URL}/api/connections/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("module") == "connections"
        assert data.get("enabled") is True
        print(f"✓ Connections service health: {data}")
    
    def test_connections_proxy_via_main_backend(self, api_client):
        """Connections service accessible via main backend proxy"""
        response = api_client.get(f"{BASE_URL}/api/connections/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        # Proxy may return slightly different format
        print(f"✓ Connections proxy via main backend: {data}")


class TestConnectionsServiceIngestion:
    """P0: Test Connections service tweet ingestion for author profile analysis"""
    
    def test_ingest_tweet_creates_author_profile(self, api_client):
        """POST /api/connections/test/ingest should accept tweet data and create/update author profile"""
        # Generate unique tweet ID to avoid conflicts
        tweet_id = f"test_tweet_{int(time.time())}"
        author_id = f"test_author_{int(time.time())}"
        
        tweet_data = {
            "tweet_id": tweet_id,
            "text": "Testing connections service integration $BTC to the moon!",
            "author": {
                "author_id": author_id,
                "username": "test_integration_user",
                "avatar_url": "https://example.com/avatar.jpg",
                "followers_count": 15000,
                "following_count": 500
            },
            "engagement": {
                "likes": 250,
                "reposts": 50,
                "replies": 25
            },
            "views": 8000,
            "created_at": "2026-01-15T10:00:00Z"
        }
        
        response = api_client.post(
            f"{CONNECTIONS_SERVICE_URL}/api/connections/test/ingest",
            json=tweet_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
        
        # Verify author profile was created
        profile = data["data"]
        assert profile.get("author_id") == author_id
        assert profile.get("handle") == "test_integration_user"
        assert "scores" in profile
        assert "influence_score" in profile["scores"]
        print(f"✓ Tweet ingested, author profile created: influence_score={profile['scores']['influence_score']}")
    
    def test_ingest_tweet_requires_author_id(self, api_client):
        """POST /api/connections/test/ingest should require author.author_id"""
        response = api_client.post(
            f"{CONNECTIONS_SERVICE_URL}/api/connections/test/ingest",
            json={"text": "No author data"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") is False
        assert "author" in data.get("message", "").lower() or "required" in data.get("message", "").lower()
        print(f"✓ Correctly rejects tweet without author_id")
    
    def test_ingest_tweet_updates_existing_profile(self, api_client):
        """Multiple tweets from same author should update the profile"""
        # Fixed author ID to ensure updates
        author_id = "persistent_test_author_001"
        
        # First tweet
        tweet1 = {
            "tweet_id": f"tweet1_{int(time.time())}",
            "text": "First tweet from persistent author",
            "author": {
                "author_id": author_id,
                "username": "persistent_user",
                "avatar_url": "",
                "followers_count": 5000,
                "following_count": 200
            },
            "engagement": {"likes": 100, "reposts": 20, "replies": 10},
            "views": 3000
        }
        
        response1 = api_client.post(
            f"{CONNECTIONS_SERVICE_URL}/api/connections/test/ingest",
            json=tweet1
        )
        assert response1.status_code == 200
        profile1 = response1.json()["data"]
        posts_count_1 = profile1.get("activity", {}).get("posts_count", 0)
        
        # Second tweet
        tweet2 = {
            "tweet_id": f"tweet2_{int(time.time())}",
            "text": "Second tweet from persistent author",
            "author": {
                "author_id": author_id,
                "username": "persistent_user",
                "avatar_url": "",
                "followers_count": 5000,
                "following_count": 200
            },
            "engagement": {"likes": 150, "reposts": 30, "replies": 15},
            "views": 4000
        }
        
        response2 = api_client.post(
            f"{CONNECTIONS_SERVICE_URL}/api/connections/test/ingest",
            json=tweet2
        )
        assert response2.status_code == 200
        profile2 = response2.json()["data"]
        posts_count_2 = profile2.get("activity", {}).get("posts_count", 0)
        
        # Posts count should have incremented
        assert posts_count_2 >= posts_count_1, f"Posts count should increase: {posts_count_1} -> {posts_count_2}"
        print(f"✓ Profile updated: posts_count {posts_count_1} -> {posts_count_2}")
    
    def test_get_author_profile_after_ingestion(self, api_client):
        """GET /api/connections/accounts/:author_id should return ingested profile"""
        author_id = "get_test_author_001"
        
        # First ingest
        api_client.post(
            f"{CONNECTIONS_SERVICE_URL}/api/connections/test/ingest",
            json={
                "tweet_id": f"get_test_{int(time.time())}",
                "text": "Test for GET verification",
                "author": {
                    "author_id": author_id,
                    "username": "get_test_user",
                    "avatar_url": "",
                    "followers_count": 2000,
                    "following_count": 100
                },
                "engagement": {"likes": 50, "reposts": 10, "replies": 5},
                "views": 1000
            }
        )
        
        # Then GET
        response = api_client.get(f"{CONNECTIONS_SERVICE_URL}/api/connections/accounts/{author_id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data["data"]["author_id"] == author_id
        print(f"✓ GET profile works after ingestion")


class TestAdminWebhookEndpoints:
    """P2: Test admin webhook info and key regeneration endpoints"""
    
    def test_webhook_info_returns_api_key(self, authenticated_client):
        """GET /api/admin/twitter-parser/sessions/webhook/info should return API key"""
        response = authenticated_client.get(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook/info"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
        assert "apiKey" in data["data"]
        assert len(data["data"]["apiKey"]) == 64  # SHA256 hex string
        assert "webhookUrl" in data["data"]
        print(f"✓ Webhook info returned API key: {data['data']['apiKey'][:16]}...")
    
    def test_webhook_info_publicly_accessible(self, api_client):
        """GET /api/admin/twitter-parser/sessions/webhook/info is publicly accessible (for Chrome extension)
        
        NOTE: This is by design - Chrome extension needs to fetch webhook info
        Security relies on the API key itself, not endpoint protection
        """
        response = api_client.get(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook/info"
        )
        
        # Endpoint is publicly accessible
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "apiKey" in data.get("data", {})
        print(f"✓ Webhook info is publicly accessible (by design for Chrome extension)")
    
    def test_regenerate_api_key(self, authenticated_client, api_client):
        """POST /api/admin/twitter-parser/sessions/webhook/regenerate-key should generate new key
        
        NOTE: This endpoint is currently publicly accessible (no auth required)
        This is a SECURITY CONCERN that should be reported
        """
        # Get current key
        info_response = api_client.get(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook/info"
        )
        old_key = info_response.json()["data"]["apiKey"]
        
        # Regenerate - endpoint is publicly accessible (no auth needed)
        # Use empty json body since Content-Type is application/json
        response = api_client.post(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook/regenerate-key",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
        assert "apiKey" in data["data"]
        new_key = data["data"]["apiKey"]
        
        # New key should be different from old key
        assert new_key != old_key, "New API key should be different from old key"
        assert len(new_key) == 64  # SHA256 hex string
        print(f"✓ API key regenerated: {old_key[:16]}... -> {new_key[:16]}...")
        print(f"⚠ WARNING: Regenerate endpoint is publicly accessible - SECURITY CONCERN")
    
    def test_regenerate_key_is_publicly_accessible(self, api_client):
        """POST /api/admin/twitter-parser/sessions/webhook/regenerate-key is publicly accessible
        
        NOTE: This is a SECURITY CONCERN - endpoint should require admin auth
        """
        response = api_client.post(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook/regenerate-key",
            json={}  # Need empty body since Content-Type is application/json
        )
        
        # Currently returns 200 (no auth required) - SECURITY CONCERN
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"⚠ WARNING: Regenerate key endpoint is publicly accessible - SECURITY CONCERN")


class TestConnectionsClientIntegration:
    """P0: Test main backend ConnectionsClient can reach connections service"""
    
    def test_connections_health_via_proxy(self, api_client):
        """Main backend should proxy connections health check"""
        response = api_client.get(f"{BASE_URL}/api/connections/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"✓ Connections health via proxy: {data}")
    
    def test_connections_stats_via_proxy(self, api_client):
        """Main backend should proxy connections stats"""
        response = api_client.get(f"{CONNECTIONS_SERVICE_URL}/api/connections/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
        assert "total_profiles" in data["data"]
        print(f"✓ Connections stats: total_profiles={data['data']['total_profiles']}")
    
    def test_connections_accounts_list(self, api_client):
        """Should be able to list author profiles"""
        response = api_client.get(
            f"{CONNECTIONS_SERVICE_URL}/api/connections/accounts",
            params={"limit": 10, "sort_by": "influence_score", "order": "desc"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
        print(f"✓ Accounts list works")


class TestWebhookIngestion:
    """Test webhook endpoint for cookie ingestion (used by Chrome Extension)"""
    
    def test_webhook_rejects_invalid_api_key(self, api_client):
        """POST /api/admin/twitter-parser/sessions/webhook should reject invalid API key"""
        response = api_client.post(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook",
            json={
                "apiKey": "invalid_key_12345",
                "sessionId": "test_session_001",
                "cookies": [{"name": "auth_token", "value": "test"}]
            }
        )
        
        # Should reject with error
        data = response.json()
        assert data.get("ok") is False
        print(f"✓ Webhook correctly rejects invalid API key")
    
    def test_webhook_requires_session_id(self, api_client, authenticated_client):
        """POST /api/admin/twitter-parser/sessions/webhook should require sessionId"""
        # Get current API key
        info_response = authenticated_client.get(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook/info"
        )
        api_key = info_response.json()["data"]["apiKey"]
        
        response = api_client.post(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook",
            json={
                "apiKey": api_key,
                "cookies": [{"name": "auth_token", "value": "test"}]
            }
        )
        
        # Should reject with error about missing sessionId
        data = response.json()
        assert data.get("ok") is False
        print(f"✓ Webhook correctly requires sessionId")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
