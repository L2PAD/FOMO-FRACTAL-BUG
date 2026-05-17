"""
FOMO-AI v4.0 Twitter Parser System Tests
Tests Admin UI APIs and User Parser APIs
Includes retry logic for mock runtime's intentional 5% failure rate
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


def retry_request(func, max_retries=3, delay=1):
    """Retry a request function with exponential backoff for mock runtime failures"""
    last_error = None
    for attempt in range(max_retries):
        try:
            result = func()
            if result.get("ok") == True:
                return result
            # Check if it's a mock simulated error (expected behavior)
            if "Mock simulated error" in str(result.get("error", "")):
                time.sleep(delay * (attempt + 1))
                continue
            return result
        except Exception as e:
            last_error = e
            time.sleep(delay * (attempt + 1))
    return {"ok": False, "error": str(last_error) if last_error else "Max retries exceeded"}


class TestAdminAuth:
    """Admin authentication tests"""
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "token" in data
        assert data.get("role") == "ADMIN"
        assert data.get("username") == "admin"
    
    def test_admin_login_invalid_credentials(self):
        """Test admin login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [401, 400]
        data = response.json()
        assert data.get("ok") == False


class TestAdminTwitterParserAccounts:
    """Admin Twitter Parser Accounts API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"},
            headers={"Content-Type": "application/json"}
        )
        return response.json().get("token")
    
    def test_get_accounts(self, auth_token):
        """Test getting Twitter accounts list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        assert isinstance(data["data"], list)
    
    def test_create_and_delete_account(self, auth_token):
        """Test creating and deleting a Twitter account"""
        # Create account
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json={"label": "TEST_Account_CRUD", "notes": "Test account for CRUD testing"},
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert data.get("ok") == True
        
        account_id = data.get("data", {}).get("_id")
        assert account_id is not None
        
        # Verify account exists
        get_response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        accounts = get_response.json().get("data", [])
        account_labels = [a.get("label") for a in accounts]
        assert "TEST_Account_CRUD" in account_labels
        
        # Delete account
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert delete_response.status_code == 200


class TestAdminTwitterParserSlots:
    """Admin Twitter Parser Slots API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"},
            headers={"Content-Type": "application/json"}
        )
        return response.json().get("token")
    
    def test_get_slots(self, auth_token):
        """Test getting egress slots list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        assert isinstance(data["data"], list)
    
    def test_create_proxy_slot(self, auth_token):
        """Test creating a PROXY type egress slot"""
        # Note: Type must be PROXY or REMOTE_WORKER, not MOCK
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "label": "TEST_Proxy_Slot",
                "type": "PROXY",
                "enabled": True,
                "proxyUrl": "http://test:test@proxy.example.com:8080",
                "limits": {"requestsPerHour": 100}
            },
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert data.get("ok") == True
        
        # Cleanup - delete the test slot
        slot_id = data.get("data", {}).get("_id")
        if slot_id:
            requests.delete(
                f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )


class TestAdminTwitterParserMonitor:
    """Admin Twitter Parser Monitor API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"},
            headers={"Content-Type": "application/json"}
        )
        return response.json().get("token")
    
    def test_get_monitor(self, auth_token):
        """Test getting parser monitor data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/monitor",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        
        # Verify monitor data structure
        monitor = data["data"]
        assert "totalAccounts" in monitor
        assert "activeAccounts" in monitor
        assert "totalSlots" in monitor
        assert "enabledSlots" in monitor


class TestTwitterRuntimeSearch:
    """Twitter Runtime Search API tests (User-facing)
    Note: Mock runtime has intentional 5% failure rate for realistic testing
    """
    
    def test_keyword_search_with_retry(self):
        """Test keyword search via runtime API with retry for mock failures"""
        def make_request():
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/search",
                json={"keyword": "BTC", "limit": 10},
                headers={"Content-Type": "application/json"}
            )
            return response.json()
        
        data = retry_request(make_request, max_retries=3)
        assert data.get("ok") == True, f"Failed after retries: {data.get('error')}"
        assert "data" in data
        assert isinstance(data["data"], list)
        
        # Verify tweet structure
        if len(data["data"]) > 0:
            tweet = data["data"][0]
            assert "id" in tweet
            assert "text" in tweet
            assert "author" in tweet
            assert "createdAt" in tweet or "timestamp" in tweet
    
    def test_keyword_search_validation(self):
        """Test keyword search with missing keyword"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"limit": 10},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
    
    def test_account_tweets_with_retry(self):
        """Test fetching tweets for a specific account with retry"""
        def make_request():
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
                json={"username": "elonmusk", "limit": 10},
                headers={"Content-Type": "application/json"}
            )
            return response.json()
        
        data = retry_request(make_request, max_retries=3)
        assert data.get("ok") == True, f"Failed after retries: {data.get('error')}"
        assert "data" in data
        assert isinstance(data["data"], list)
        
        # Verify all tweets have the correct author
        for tweet in data["data"]:
            assert tweet.get("author", {}).get("username") == "elonmusk"
    
    def test_account_tweets_validation(self):
        """Test account tweets with missing username"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
            json={"limit": 10},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400


class TestHealthEndpoint:
    """Health check endpoint tests"""
    
    def test_health_check(self):
        """Test health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
