"""
B4 Parser UI Backend Tests
Tests for Twitter Parser Runtime Layer APIs used by the Parser UI
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestParserRuntimeSearch:
    """Tests for POST /api/v4/twitter/runtime/search"""
    
    def test_search_with_keyword(self):
        """Test keyword search returns tweets"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "BTC", "limit": 10},
            headers={"Content-Type": "application/json"}
        )
        
        # May fail due to 5% mock failure rate, retry once
        if response.status_code != 200:
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/search",
                json={"keyword": "BTC", "limit": 10},
                headers={"Content-Type": "application/json"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        assert isinstance(data["data"], list)
        
        # Verify tweet structure
        if len(data["data"]) > 0:
            tweet = data["data"][0]
            assert "id" in tweet
            assert "text" in tweet
            assert "author" in tweet
            assert "likes" in tweet or "engagement" in tweet
            assert "createdAt" in tweet or "timestamp" in tweet
    
    def test_search_with_sol_keyword(self):
        """Test SOL keyword search (default in UI)"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "SOL", "limit": 20},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/search",
                json={"keyword": "SOL", "limit": 20},
                headers={"Content-Type": "application/json"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert len(data.get("data", [])) <= 20
    
    def test_search_returns_meta_info(self):
        """Test search returns meta information"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "ETH", "limit": 5},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/search",
                json={"keyword": "ETH", "limit": 5},
                headers={"Content-Type": "application/json"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "meta" in data
        meta = data["meta"]
        assert "instanceId" in meta
        assert "taskId" in meta
        assert "duration" in meta
    
    def test_search_missing_keyword_returns_400(self):
        """Test missing keyword returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"limit": 10},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
    
    def test_search_empty_keyword_returns_400(self):
        """Test empty keyword returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "", "limit": 10},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400


class TestParserAccountTweets:
    """Tests for POST /api/v4/twitter/runtime/account/tweets"""
    
    def test_account_tweets_with_username(self):
        """Test fetching tweets by username"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
            json={"username": "elonmusk", "limit": 10},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
                json={"username": "elonmusk", "limit": 10},
                headers={"Content-Type": "application/json"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        
        # Verify all tweets have correct author
        for tweet in data.get("data", []):
            assert tweet.get("author", {}).get("username") == "elonmusk"
    
    def test_account_tweets_missing_username_returns_400(self):
        """Test missing username returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/account/tweets",
            json={"limit": 10},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400


class TestExecutionStatus:
    """Tests for execution status endpoints"""
    
    def test_detailed_status(self):
        """Test GET /api/v4/twitter/execution/detailed-status"""
        response = requests.get(
            f"{BASE_URL}/api/v4/twitter/execution/detailed-status",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        
        # Verify status structure
        status = data.get("data", {})
        assert "worker" in status
        assert "capacity" in status
        assert "runtime" in status
        
        # Verify worker info
        worker = status["worker"]
        assert "running" in worker
        assert "currentTasks" in worker
        
        # Verify capacity info
        capacity = status["capacity"]
        assert "totalCapacity" in capacity
        assert "availableThisHour" in capacity
    
    def test_basic_status(self):
        """Test GET /api/v4/twitter/execution/status"""
        response = requests.get(
            f"{BASE_URL}/api/v4/twitter/execution/status",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True


class TestTweetDataStructure:
    """Tests to verify tweet data structure matches UI expectations"""
    
    def test_tweet_has_engagement_fields(self):
        """Test tweets have engagement fields (likes, reposts, replies, views)"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "crypto", "limit": 5},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/search",
                json={"keyword": "crypto", "limit": 5},
                headers={"Content-Type": "application/json"}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data.get("data", [])) > 0:
            tweet = data["data"][0]
            # Check for flat engagement fields (API format)
            assert "likes" in tweet, "Tweet should have 'likes' field"
            assert "reposts" in tweet, "Tweet should have 'reposts' field"
            assert "replies" in tweet, "Tweet should have 'replies' field"
            assert "views" in tweet, "Tweet should have 'views' field"
            
            # Verify they are numbers
            assert isinstance(tweet["likes"], (int, float))
            assert isinstance(tweet["reposts"], (int, float))
    
    def test_tweet_has_author_info(self):
        """Test tweets have author information"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "defi", "limit": 5},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/search",
                json={"keyword": "defi", "limit": 5},
                headers={"Content-Type": "application/json"}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data.get("data", [])) > 0:
            tweet = data["data"][0]
            assert "author" in tweet
            author = tweet["author"]
            assert "username" in author
            assert "displayName" in author
            assert "verified" in author
    
    def test_tweet_has_timestamp(self):
        """Test tweets have timestamp (createdAt)"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "nft", "limit": 5},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/search",
                json={"keyword": "nft", "limit": 5},
                headers={"Content-Type": "application/json"}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data.get("data", [])) > 0:
            tweet = data["data"][0]
            assert "createdAt" in tweet, "Tweet should have 'createdAt' field"
            assert isinstance(tweet["createdAt"], (int, float))
    
    def test_mock_tweets_have_mock_prefix(self):
        """Test mock tweets have 'mock-' prefix in ID"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/runtime/search",
            json={"keyword": "memecoin", "limit": 5},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/runtime/search",
                json={"keyword": "memecoin", "limit": 5},
                headers={"Content-Type": "application/json"}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data.get("data", [])) > 0:
            tweet = data["data"][0]
            assert tweet["id"].startswith("mock-"), "Mock tweets should have 'mock-' prefix"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
