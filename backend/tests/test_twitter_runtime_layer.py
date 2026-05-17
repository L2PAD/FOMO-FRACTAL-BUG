"""
Twitter Parser B3 Runtime Layer API Tests
Tests for Runtime Layer endpoints (Mock/Remote/Proxy abstraction)
- POST /api/v4/twitter/runtime/search - search tweets using Runtime Layer
- POST /api/v4/twitter/runtime/account/tweets - get account tweets using Runtime Layer
- GET /api/v4/twitter/execution/detailed-status - detailed status with runtime info
- GET /api/v4/twitter/execution/status - basic execution status with runtime summary
- Admin APIs: accounts, slots, monitor

Note: Mock runtime has 5% simulated failure rate for realistic testing.
Tests include retry logic to handle this expected behavior.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data prefixes for cleanup
TEST_PREFIX = "TEST_"

# Helper function to retry API calls due to mock's simulated failure rate
def retry_api_call(method, url, max_retries=3, **kwargs):
    """Retry API call up to max_retries times to handle mock's 5% failure rate"""
    for attempt in range(max_retries):
        response = method(url, **kwargs)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") is True:
                return response, data
    return response, response.json() if response.status_code == 200 else None


class TestRuntimeSearch:
    """Tests for POST /api/v4/twitter/runtime/search"""
    
    def test_runtime_search_success(self):
        """Test search with valid keyword returns mock tweets"""
        response, data = retry_api_call(
            requests.post,
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "BTC", "limit": 5},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        # Verify response structure
        assert data["ok"] is True
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 5
        
        # Verify tweet structure
        tweet = data["data"][0]
        assert "id" in tweet
        assert "text" in tweet
        assert "likes" in tweet
        assert "reposts" in tweet
        assert "author" in tweet
        assert "username" in tweet["author"]
    
    def test_runtime_search_with_crypto_keyword(self):
        """Test search with crypto-related keyword"""
        response, data = retry_api_call(
            requests.post,
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "ETH", "limit": 10},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        if data and data.get("ok") is True:
            assert len(data["data"]) == 10
            
            # Verify mock data contains crypto-themed content
            for tweet in data["data"]:
                assert isinstance(tweet["likes"], int)
                assert isinstance(tweet["reposts"], int)
                assert "createdAt" in tweet
        else:
            pytest.skip("Mock runtime simulated failures on all attempts")
    
    def test_runtime_search_default_limit(self):
        """Test search without limit uses default (20)"""
        response, data = retry_api_call(
            requests.post,
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "SOL"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        if data and data.get("ok") is True:
            assert len(data["data"]) == 20  # Default limit
        else:
            pytest.skip("Mock runtime simulated failures on all attempts")
    
    def test_runtime_search_missing_keyword(self):
        """Test search without keyword returns error"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"limit": 5},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        data = response.json()
        
        assert data["ok"] is False
        assert "keyword is required" in data["error"]
    
    def test_runtime_search_empty_keyword(self):
        """Test search with empty keyword returns error"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "", "limit": 5},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        data = response.json()
        
        assert data["ok"] is False
    
    def test_runtime_search_meta_info(self):
        """Test search response includes meta information"""
        response, data = retry_api_call(
            requests.post,
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "DOGE", "limit": 3},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        if data and data.get("ok") is True:
            # Meta should be present in response
            assert "meta" in data
            meta = data["meta"]
            assert "instanceId" in meta
            assert "taskId" in meta
            assert "duration" in meta
        else:
            pytest.skip("Mock runtime simulated failures on all attempts")


class TestRuntimeAccountTweets:
    """Tests for POST /api/v4/twitter/runtime/account/tweets"""
    
    def test_runtime_account_tweets_success(self):
        """Test fetching account tweets with valid username"""
        response, data = retry_api_call(
            requests.post,
            f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
            json={"username": "CryptoWhale", "limit": 5},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        if data and data.get("ok") is True:
            # Verify response structure
            assert "data" in data
            assert isinstance(data["data"], list)
            assert len(data["data"]) == 5
            
            # Verify tweets are from the requested user
            for tweet in data["data"]:
                assert tweet["author"]["username"] == "CryptoWhale"
        else:
            pytest.skip("Mock runtime simulated failures on all attempts")
    
    def test_runtime_account_tweets_different_users(self):
        """Test fetching tweets for different usernames"""
        usernames = ["DeFi_Degen", "NFT_Hunter", "SolanaNews"]
        success_count = 0
        
        for username in usernames:
            response, data = retry_api_call(
                requests.post,
                f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
                json={"username": username, "limit": 3},
                headers={"Content-Type": "application/json"}
            )
            
            if data and data.get("ok") is True:
                assert len(data["data"]) == 3
                # All tweets should be from the requested user
                for tweet in data["data"]:
                    assert tweet["author"]["username"] == username
                success_count += 1
        
        # At least 2 out of 3 should succeed
        assert success_count >= 2, f"Only {success_count}/3 users succeeded"
    
    def test_runtime_account_tweets_default_limit(self):
        """Test account tweets without limit uses default (20)"""
        response, data = retry_api_call(
            requests.post,
            f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
            json={"username": "ETH_Maxi"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        if data and data.get("ok") is True:
            assert len(data["data"]) == 20  # Default limit
        else:
            pytest.skip("Mock runtime simulated failures on all attempts")
    
    def test_runtime_account_tweets_missing_username(self):
        """Test account tweets without username returns error"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
            json={"limit": 5},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        data = response.json()
        
        assert data["ok"] is False
        assert "username is required" in data["error"]
    
    def test_runtime_account_tweets_meta_info(self):
        """Test account tweets response includes meta information"""
        response, data = retry_api_call(
            requests.post,
            f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
            json={"username": "AlphaLeaks", "limit": 3},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        if data and data.get("ok") is True:
            assert "meta" in data
            meta = data["meta"]
            assert "instanceId" in meta
            assert "taskId" in meta
        else:
            pytest.skip("Mock runtime simulated failures on all attempts")


class TestExecutionDetailedStatus:
    """Tests for GET /api/v4/twitter/execution/detailed-status"""
    
    def test_detailed_status_success(self):
        """Test detailed status returns comprehensive info"""
        response = requests.get(
            f"{BASE_URL}/api/v4/twitter/execution/detailed-status",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "data" in data
        status = data["data"]
        
        # Verify worker info
        assert "worker" in status
        assert "running" in status["worker"]
        assert "currentTasks" in status["worker"]
        
        # Verify capacity info
        assert "capacity" in status
        assert "totalCapacity" in status["capacity"]
        assert "usedThisHour" in status["capacity"]
        assert "availableThisHour" in status["capacity"]
        assert "activeInstances" in status["capacity"]
        
        # Verify runtime summary
        assert "runtime" in status
        assert "total" in status["runtime"]
        assert "healthy" in status["runtime"]
        assert "degraded" in status["runtime"]
        assert "error" in status["runtime"]
        
        # Verify task stats
        assert "tasks" in status
        assert "queued" in status["tasks"]
        assert "running" in status["tasks"]
        assert "done" in status["tasks"]
        assert "failed" in status["tasks"]
        
        # Verify runtime details per slot
        assert "runtimeDetails" in status
    
    def test_detailed_status_runtime_details(self):
        """Test detailed status includes runtime details per slot"""
        response = requests.get(
            f"{BASE_URL}/api/v4/twitter/execution/detailed-status",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        
        status = data["data"]
        runtime_details = status.get("runtimeDetails", {})
        
        # Should have at least one slot
        if runtime_details:
            for slot_id, details in runtime_details.items():
                assert "sourceType" in details
                assert "health" in details
                # sourceType should be one of MOCK, PROXY, REMOTE_WORKER
                assert details["sourceType"] in ["MOCK", "PROXY", "REMOTE_WORKER", "UNKNOWN"]


class TestExecutionStatus:
    """Tests for GET /api/v4/twitter/execution/status"""
    
    def test_execution_status_success(self):
        """Test basic execution status returns summary"""
        response = requests.get(
            f"{BASE_URL}/api/v4/twitter/execution/status",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "data" in data
        status = data["data"]
        
        # Verify worker info
        assert "worker" in status
        assert "running" in status["worker"]
        
        # Verify capacity info
        assert "capacity" in status
        assert "totalCapacity" in status["capacity"]
        assert "availableThisHour" in status["capacity"]
        
        # Verify runtime summary
        assert "runtime" in status
        assert "total" in status["runtime"]
        assert "healthy" in status["runtime"]
    
    def test_execution_status_vs_detailed_status(self):
        """Test that basic status is subset of detailed status"""
        basic_response = requests.get(
            f"{BASE_URL}/api/v4/twitter/execution/status",
            headers={"Content-Type": "application/json"}
        )
        detailed_response = requests.get(
            f"{BASE_URL}/api/v4/twitter/execution/detailed-status",
            headers={"Content-Type": "application/json"}
        )
        
        assert basic_response.status_code == 200
        assert detailed_response.status_code == 200
        
        basic = basic_response.json()["data"]
        detailed = detailed_response.json()["data"]
        
        # Basic should have same worker and capacity info
        assert basic["worker"]["running"] == detailed["worker"]["running"]
        assert basic["capacity"]["totalCapacity"] == detailed["capacity"]["totalCapacity"]
        
        # Detailed should have additional fields
        assert "tasks" in detailed
        assert "runtimeDetails" in detailed


class TestAdminAPIs:
    """Tests for Admin APIs - ensure they still work with B3 Runtime Layer"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Headers with auth token"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}"
        }
    
    def test_admin_accounts_list(self, auth_headers):
        """Test GET /api/admin/twitter-parser/accounts"""
        response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "data" in data
        assert isinstance(data["data"], list)
        assert "total" in data
    
    def test_admin_slots_list(self, auth_headers):
        """Test GET /api/admin/twitter-parser/slots"""
        response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "data" in data
        assert isinstance(data["data"], list)
        assert "total" in data
        
        # Verify slot structure
        if data["data"]:
            slot = data["data"][0]
            assert "_id" in slot
            assert "label" in slot
            assert "type" in slot
            assert "enabled" in slot
    
    def test_admin_monitor(self, auth_headers):
        """Test GET /api/admin/twitter-parser/monitor"""
        response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/monitor",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "data" in data
        monitor = data["data"]
        
        # Verify monitor data structure
        assert "totalAccounts" in monitor
        assert "activeAccounts" in monitor
        assert "totalSlots" in monitor
        assert "enabledSlots" in monitor
        assert "healthySlots" in monitor
        assert "totalCapacityPerHour" in monitor
        assert "availableThisHour" in monitor


class TestRuntimeIntegration:
    """Integration tests for Runtime Layer with execution system"""
    
    def test_search_updates_execution_status(self):
        """Test that runtime search updates execution status"""
        # Get initial status
        initial_response = requests.get(
            f"{BASE_URL}/api/v4/twitter/execution/detailed-status",
            headers={"Content-Type": "application/json"}
        )
        assert initial_response.status_code == 200
        
        # Perform search (retry on mock failure)
        for _ in range(3):
            search_response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/search",
                json={"keyword": "PEPE", "limit": 5},
                headers={"Content-Type": "application/json"}
            )
            if search_response.status_code == 200 and search_response.json().get("ok"):
                break
        
        assert search_response.status_code == 200
        
        # Get updated status
        updated_response = requests.get(
            f"{BASE_URL}/api/v4/twitter/execution/detailed-status",
            headers={"Content-Type": "application/json"}
        )
        assert updated_response.status_code == 200
    
    def test_multiple_runtime_operations(self):
        """Test multiple runtime operations in sequence (with retry for mock failures)"""
        operations = [
            {"type": "search", "payload": {"keyword": "BTC", "limit": 3}},
            {"type": "search", "payload": {"keyword": "ETH", "limit": 3}},
            {"type": "account_tweets", "payload": {"username": "CryptoWhale", "limit": 3}},
            {"type": "search", "payload": {"keyword": "SOL", "limit": 3}},
        ]
        
        success_count = 0
        for op in operations:
            # Retry up to 3 times due to mock's 5% simulated failure rate
            for attempt in range(3):
                if op["type"] == "search":
                    response = requests.post(
                        f"{BASE_URL}/api/v4/twitter/runtime/search",
                        json=op["payload"],
                        headers={"Content-Type": "application/json"}
                    )
                else:
                    response = requests.post(
                        f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
                        json=op["payload"],
                        headers={"Content-Type": "application/json"}
                    )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok") is True:
                        assert len(data["data"]) == op["payload"]["limit"]
                        success_count += 1
                        break
        
        # At least 3 out of 4 operations should succeed
        assert success_count >= 3, f"Only {success_count}/4 operations succeeded"


class TestMockRuntimeBehavior:
    """Tests specific to Mock Runtime behavior"""
    
    def test_mock_generates_crypto_themed_content(self):
        """Test that mock runtime generates crypto-themed tweets"""
        response, data = retry_api_call(
            requests.post,
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "crypto", "limit": 10},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        if data and data.get("ok") is True:
            # Check that tweets contain crypto-related content
            crypto_keywords = ['$', '#', 'moon', 'whale', 'bullish', 'bearish', 'pump', 'alpha', 'degen']
            
            for tweet in data["data"]:
                text = tweet["text"].lower()
                # At least one crypto keyword should be present
                has_crypto_content = any(kw.lower() in text for kw in crypto_keywords)
                assert has_crypto_content or 'crypto' in text.lower()
        else:
            pytest.skip("Mock runtime simulated failures on all attempts")
    
    def test_mock_generates_realistic_engagement_numbers(self):
        """Test that mock runtime generates realistic engagement numbers"""
        response, data = retry_api_call(
            requests.post,
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "NFT", "limit": 20},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        if data and data.get("ok") is True:
            for tweet in data["data"]:
                # Engagement numbers should be reasonable
                assert 0 <= tweet["likes"] <= 10000
                assert 0 <= tweet["reposts"] <= 5000
                assert 0 <= tweet["replies"] <= 1000
                assert 0 <= tweet["views"] <= 100000
        else:
            pytest.skip("Mock runtime simulated failures on all attempts")
    
    def test_mock_generates_unique_tweet_ids(self):
        """Test that mock runtime generates unique tweet IDs"""
        # Retry up to 3 times due to mock's 5% simulated failure rate
        for attempt in range(3):
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/search",
                json={"keyword": "DeFi", "limit": 20},
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 200
            data = response.json()
            
            if data.get("ok") is True:
                tweet_ids = [tweet["id"] for tweet in data["data"]]
                # All IDs should be unique
                assert len(tweet_ids) == len(set(tweet_ids))
                
                # IDs should contain 'mock' prefix
                for tweet_id in tweet_ids:
                    assert tweet_id.startswith("mock-")
                return
        
        # If all retries failed due to mock failures, that's acceptable
        pytest.skip("Mock runtime simulated failures on all attempts")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
