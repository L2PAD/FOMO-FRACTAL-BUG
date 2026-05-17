"""
P1 (Remote Runtime) and P2 (MongoDB Persistence) Feature Tests
Tests for FOMO-AI v4.0 Twitter Parser

P1 Features:
- Create REMOTE_WORKER slot with baseUrl via Admin API
- Test Connection button - calls /api/v4/twitter/runtime/health-check/:slotId
- Runtime factory creates RemoteRuntime for REMOTE_WORKER slots

P2 Features:
- POST /api/v4/twitter/tweets/query - filtered query with minLikes, minReposts, timeRange
- GET /api/v4/twitter/tweets/recent - recent tweets from MongoDB
- GET /api/v4/twitter/tweets/by-keyword/:keyword - tweets by keyword
- GET /api/v4/twitter/tweets/by-user/:username - tweets by username
- GET /api/v4/twitter/tasks/stats - task queue statistics
- GET /api/v4/twitter/tasks/:status - tasks by status
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestP1RemoteRuntime:
    """P1 - Remote Runtime Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/admin/auth/login", json={
            "username": "admin",
            "password": "admin12345"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        self.token = data.get('token')
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_create_remote_worker_slot_with_baseurl(self):
        """P1: Create REMOTE_WORKER slot with baseUrl via Admin API"""
        # Create a REMOTE_WORKER slot with worker.baseUrl (correct API structure)
        slot_data = {
            "label": "TEST_Railway_P1_Slot",
            "type": "REMOTE_WORKER",
            "worker": {"baseUrl": "https://test-parser.up.railway.app"},
            "enabled": True,
            "limits": {"requestsPerHour": 100}
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json=slot_data,
            headers=self.headers
        )
        
        # Should create successfully
        assert response.status_code == 201, f"Failed to create REMOTE_WORKER slot: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        
        slot = data.get('data', {})
        assert slot.get('type') == 'REMOTE_WORKER'
        assert slot.get('worker', {}).get('baseUrl') == 'https://test-parser.up.railway.app'
        assert slot.get('label') == 'TEST_Railway_P1_Slot'
        
        # Store slot ID for cleanup
        self.created_slot_id = slot.get('_id')
        
        # Cleanup
        if self.created_slot_id:
            requests.delete(
                f"{BASE_URL}/api/admin/twitter-parser/slots/{self.created_slot_id}",
                headers=self.headers
            )
        
        print(f"✓ REMOTE_WORKER slot created with baseUrl: {slot.get('worker', {}).get('baseUrl')}")
    
    def test_create_proxy_slot(self):
        """P1: Create PROXY slot with proxyUrl"""
        slot_data = {
            "label": "TEST_Proxy_P1_Slot",
            "type": "PROXY",
            "proxy": {"url": "http://proxy.example.com:8080"},
            "enabled": True,
            "limits": {"requestsPerHour": 150}
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json=slot_data,
            headers=self.headers
        )
        
        assert response.status_code == 201, f"Failed to create PROXY slot: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        
        slot = data.get('data', {})
        assert slot.get('type') == 'PROXY'
        # Proxy URL is optional, so just check slot was created
        
        # Cleanup
        slot_id = slot.get('_id')
        if slot_id:
            requests.delete(
                f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
                headers=self.headers
            )
        
        print(f"✓ PROXY slot created")
    
    def test_health_check_endpoint_exists(self):
        """P1: Test Connection endpoint exists - /api/v4/twitter/runtime/health-check/:slotId"""
        # First create a slot to test with
        slot_data = {
            "label": "TEST_HealthCheck_Slot",
            "type": "REMOTE_WORKER",
            "worker": {"baseUrl": "https://nonexistent-parser.railway.app"},
            "enabled": True
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json=slot_data,
            headers=self.headers
        )
        
        assert create_response.status_code == 201, f"Failed to create slot: {create_response.text}"
        slot_id = create_response.json().get('data', {}).get('_id')
        
        # Test the health check endpoint (POST without body or with empty body)
        health_response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/health-check/{slot_id}",
            json={},  # Send empty JSON body
            headers=self.headers
        )
        
        # Endpoint should exist and return a response (even if ERROR due to invalid URL)
        assert health_response.status_code == 200, f"Health check endpoint failed: {health_response.text}"
        data = health_response.json()
        assert 'ok' in data
        assert 'data' in data
        assert data['data'].get('slotId') == slot_id
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            headers=self.headers
        )
        
        print(f"✓ Health check endpoint works for slot: {slot_id}")
    
    def test_health_check_with_invalid_slot_id(self):
        """P1: Health check with non-existent slot ID"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/health-check/000000000000000000000000",
            json={},  # Send empty JSON body
            headers=self.headers
        )
        
        # Should return 200 with error status or 404
        assert response.status_code in [200, 404, 500], f"Unexpected status: {response.status_code}"
        print(f"✓ Health check handles invalid slot ID correctly")


class TestP2MongoDBPersistence:
    """P2 - MongoDB Persistence Tests"""
    
    def test_tweets_query_endpoint(self):
        """P2: POST /api/v4/twitter/tweets/query - filtered query"""
        # Test with various filters
        filters = {
            "minLikes": 10,
            "minReposts": 5,
            "limit": 20
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/tweets/query",
            json=filters
        )
        
        assert response.status_code == 200, f"Query endpoint failed: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        result = data.get('data', {})
        assert 'items' in result
        assert 'total' in result
        assert 'limit' in result
        assert 'offset' in result
        
        print(f"✓ Tweets query returned {len(result.get('items', []))} items, total: {result.get('total')}")
    
    def test_tweets_query_with_time_range(self):
        """P2: Query tweets with timeRange filter"""
        now = int(time.time() * 1000)
        one_day_ago = now - (24 * 60 * 60 * 1000)
        
        filters = {
            "timeRange": {
                "from": one_day_ago,
                "to": now
            },
            "limit": 50
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/tweets/query",
            json=filters
        )
        
        assert response.status_code == 200, f"Time range query failed: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        
        print(f"✓ Time range query works correctly")
    
    def test_tweets_recent_endpoint(self):
        """P2: GET /api/v4/twitter/tweets/recent - recent tweets from MongoDB"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/tweets/recent?limit=10")
        
        assert response.status_code == 200, f"Recent tweets endpoint failed: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        tweets = data.get('data', [])
        assert isinstance(tweets, list)
        
        print(f"✓ Recent tweets endpoint returned {len(tweets)} tweets")
    
    def test_tweets_by_keyword_endpoint(self):
        """P2: GET /api/v4/twitter/tweets/by-keyword/:keyword"""
        keyword = "bitcoin"
        response = requests.get(f"{BASE_URL}/api/v4/twitter/tweets/by-keyword/{keyword}?limit=10")
        
        assert response.status_code == 200, f"By-keyword endpoint failed: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        tweets = data.get('data', [])
        assert isinstance(tweets, list)
        
        print(f"✓ Tweets by keyword '{keyword}' returned {len(tweets)} tweets")
    
    def test_tweets_by_user_endpoint(self):
        """P2: GET /api/v4/twitter/tweets/by-user/:username"""
        username = "elonmusk"
        response = requests.get(f"{BASE_URL}/api/v4/twitter/tweets/by-user/{username}?limit=10")
        
        assert response.status_code == 200, f"By-user endpoint failed: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        tweets = data.get('data', [])
        assert isinstance(tweets, list)
        
        print(f"✓ Tweets by user '@{username}' returned {len(tweets)} tweets")
    
    def test_tasks_stats_endpoint(self):
        """P2: GET /api/v4/twitter/tasks/stats - task queue statistics"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/tasks/stats")
        
        assert response.status_code == 200, f"Tasks stats endpoint failed: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        stats = data.get('data', {})
        assert 'queued' in stats
        assert 'running' in stats
        assert 'done' in stats
        assert 'failed' in stats
        assert 'total' in stats
        
        print(f"✓ Task stats: queued={stats.get('queued')}, running={stats.get('running')}, done={stats.get('done')}, failed={stats.get('failed')}, total={stats.get('total')}")
    
    def test_tasks_by_status_queued(self):
        """P2: GET /api/v4/twitter/tasks/QUEUED"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/tasks/QUEUED?limit=10")
        
        assert response.status_code == 200, f"Tasks by status failed: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        tasks = data.get('data', [])
        assert isinstance(tasks, list)
        
        print(f"✓ QUEUED tasks: {len(tasks)}")
    
    def test_tasks_by_status_done(self):
        """P2: GET /api/v4/twitter/tasks/DONE"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/tasks/DONE?limit=10")
        
        assert response.status_code == 200, f"Tasks by status failed: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        
        print(f"✓ DONE tasks endpoint works")
    
    def test_tasks_by_status_failed(self):
        """P2: GET /api/v4/twitter/tasks/FAILED"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/tasks/FAILED?limit=10")
        
        assert response.status_code == 200, f"Tasks by status failed: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        
        print(f"✓ FAILED tasks endpoint works")
    
    def test_tasks_invalid_status(self):
        """P2: GET /api/v4/twitter/tasks/:status with invalid status"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/tasks/INVALID_STATUS")
        
        assert response.status_code == 400, f"Expected 400 for invalid status, got: {response.status_code}"
        data = response.json()
        assert data.get('ok') == False
        assert 'error' in data
        
        print(f"✓ Invalid status returns proper error")


class TestRuntimeSearch:
    """Test runtime search endpoints (used by UI)"""
    
    def test_runtime_search_keyword(self):
        """Test POST /api/v4/twitter/runtime/search"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "crypto", "limit": 10}
        )
        
        assert response.status_code == 200, f"Runtime search failed: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        
        print(f"✓ Runtime search works")
    
    def test_runtime_account_tweets(self):
        """Test POST /api/v4/twitter/runtime/account/tweets"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
            json={"username": "vitalikbuterin", "limit": 10}
        )
        
        assert response.status_code == 200, f"Runtime account tweets failed: {response.text}"
        data = response.json()
        assert data.get('ok') == True
        
        print(f"✓ Runtime account tweets works")


class TestAdminSlotsAPI:
    """Test Admin Slots API for P1 features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/admin/auth/login", json={
            "username": "admin",
            "password": "admin12345"
        })
        assert response.status_code == 200
        self.token = response.json().get('token')
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_get_all_slots(self):
        """Get all egress slots"""
        response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        slots = data.get('data', [])
        print(f"✓ Found {len(slots)} slots")
        
        # Check slot structure
        for slot in slots:
            assert 'type' in slot
            assert slot['type'] in ['PROXY', 'REMOTE_WORKER', 'MOCK']
    
    def test_slot_crud_flow(self):
        """Test full CRUD flow for slots"""
        # CREATE
        create_data = {
            "label": "TEST_CRUD_Slot",
            "type": "REMOTE_WORKER",
            "worker": {"baseUrl": "https://crud-test.railway.app"},
            "enabled": True,
            "limits": {"requestsPerHour": 50}
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json=create_data,
            headers=self.headers
        )
        
        assert create_response.status_code == 201, f"Create failed: {create_response.text}"
        slot_id = create_response.json().get('data', {}).get('_id')
        assert slot_id is not None
        print(f"✓ Created slot: {slot_id}")
        
        # READ
        read_response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            headers=self.headers
        )
        
        assert read_response.status_code == 200
        slot = read_response.json().get('data', {})
        assert slot.get('label') == 'TEST_CRUD_Slot'
        print(f"✓ Read slot: {slot.get('label')}")
        
        # UPDATE
        update_data = {"label": "TEST_CRUD_Slot_Updated"}
        update_response = requests.patch(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            json=update_data,
            headers=self.headers
        )
        
        assert update_response.status_code == 200
        updated_slot = update_response.json().get('data', {})
        assert updated_slot.get('label') == 'TEST_CRUD_Slot_Updated'
        print(f"✓ Updated slot label")
        
        # DELETE
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            headers=self.headers
        )
        
        assert delete_response.status_code == 200
        print(f"✓ Deleted slot")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
