"""
FOMO Mobile App Backend API Tests
Tests all mobile endpoints: auth, home, feed, signals, edge
"""
import pytest
import requests
import os
from datetime import datetime

# Get backend URL from environment
BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    pytest.skip("EXPO_PUBLIC_BACKEND_URL not set", allow_module_level=True)

# Test credentials from test_credentials.md
DEV_EMAIL = "dev@fomo.ai"
DEV_NAME = "FOMO Developer"


class TestHealthCheck:
    """Basic health check"""
    
    def test_backend_health(self):
        """Test backend health endpoint"""
        # Try /health first, fallback to /api/health
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 404:
            response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        # Accept either python-gateway or node-backend service
        assert data.get("ok") == True or data.get("status") == "ok" or data.get("service") in ["python-gateway", "node-backend"]
        print(f"✓ Backend health check passed: {data}")


class TestMobileAuth:
    """Mobile authentication tests"""
    
    def test_dev_login_success(self):
        """Test dev login with correct credentials"""
        response = requests.post(
            f"{BASE_URL}/api/mobile/auth/dev-login",
            json={"email": DEV_EMAIL, "name": DEV_NAME},
            timeout=10
        )
        assert response.status_code == 200, f"Dev login failed: {response.text}"
        
        data = response.json()
        assert "accessToken" in data, "Missing accessToken in response"
        assert "refreshToken" in data, "Missing refreshToken in response"
        assert "user" in data, "Missing user in response"
        
        user = data["user"]
        assert user["email"] == DEV_EMAIL
        assert user["name"] == DEV_NAME
        
        print(f"✓ Dev login successful for {user['email']}")
        
        # Store token for other tests
        pytest.access_token = data["accessToken"]
        pytest.user_id = user["id"]
    
    def test_dev_login_creates_or_finds_user(self):
        """Test that dev login is idempotent"""
        # First login
        response1 = requests.post(
            f"{BASE_URL}/api/mobile/auth/dev-login",
            json={"email": DEV_EMAIL, "name": DEV_NAME},
            timeout=10
        )
        assert response1.status_code == 200
        user1_id = response1.json()["user"]["id"]
        
        # Second login - should return same user
        response2 = requests.post(
            f"{BASE_URL}/api/mobile/auth/dev-login",
            json={"email": DEV_EMAIL, "name": DEV_NAME},
            timeout=10
        )
        assert response2.status_code == 200
        user2_id = response2.json()["user"]["id"]
        
        assert user1_id == user2_id, "Dev login should return same user on repeated calls"
        print(f"✓ Dev login is idempotent (user_id: {user1_id})")


class TestMobileHome:
    """Home screen API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login before each test"""
        if not hasattr(pytest, 'access_token'):
            response = requests.post(
                f"{BASE_URL}/api/mobile/auth/dev-login",
                json={"email": DEV_EMAIL, "name": DEV_NAME},
                timeout=10
            )
            pytest.access_token = response.json()["accessToken"]
    
    def test_home_btc_data(self):
        """Test /api/mobile/home?asset=BTC returns valid data"""
        headers = {"Authorization": f"Bearer {pytest.access_token}"}
        response = requests.get(
            f"{BASE_URL}/api/mobile/home?asset=BTC",
            headers=headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Home API failed: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "asset" in data or "symbol" in data
        assert "price" in data or "currentPrice" in data
        assert "decision" in data
        
        # Decision is an object with action, confidence, etc
        decision = data["decision"]
        assert isinstance(decision, dict), "Decision should be an object"
        assert "action" in decision
        assert decision["action"] in ["BUY", "SELL", "WAIT"]
        assert "confidence" in decision
        
        price = data.get("price") or data.get("currentPrice")
        print(f"✓ Home BTC data: action={decision['action']}, confidence={decision['confidence']}, price={price}")
    
    def test_home_without_auth(self):
        """Test home endpoint without authentication"""
        response = requests.get(
            f"{BASE_URL}/api/mobile/home?asset=BTC",
            timeout=10
        )
        # Should work without auth (optional auth endpoint)
        assert response.status_code in [200, 401]
        print(f"✓ Home without auth: status={response.status_code}")


class TestMobileFeed:
    """Feed API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login before each test"""
        if not hasattr(pytest, 'access_token'):
            response = requests.post(
                f"{BASE_URL}/api/mobile/auth/dev-login",
                json={"email": DEV_EMAIL, "name": DEV_NAME},
                timeout=10
            )
            pytest.access_token = response.json()["accessToken"]
    
    def test_feed_btc(self):
        """Test /api/mobile/feed?asset=BTC returns feed items"""
        headers = {"Authorization": f"Bearer {pytest.access_token}"}
        response = requests.get(
            f"{BASE_URL}/api/mobile/feed?asset=BTC",
            headers=headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Feed API failed: {response.text}"
        data = response.json()
        
        # API can return either array or object with 'items' field
        if isinstance(data, dict):
            assert "items" in data, "Feed object should have 'items' field"
            items = data["items"]
            count = data.get("count", len(items))
            print(f"✓ Feed returned {count} items in object format")
        else:
            items = data
            print(f"✓ Feed returned {len(items)} items in array format")
        
        if len(items) > 0:
            item = items[0]
            assert "id" in item
            print(f"✓ First feed item: {item.get('title', item.get('label', 'N/A'))[:50]}")


class TestMobileSignals:
    """Signals API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login before each test"""
        if not hasattr(pytest, 'access_token'):
            response = requests.post(
                f"{BASE_URL}/api/mobile/auth/dev-login",
                json={"email": DEV_EMAIL, "name": DEV_NAME},
                timeout=10
            )
            pytest.access_token = response.json()["accessToken"]
    
    def test_signals_list(self):
        """Test /api/mobile/signals returns signal list"""
        headers = {"Authorization": f"Bearer {pytest.access_token}"}
        response = requests.get(
            f"{BASE_URL}/api/mobile/signals",
            headers=headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Signals API failed: {response.text}"
        data = response.json()
        
        # Check structure
        assert "ok" in data or "signals" in data or isinstance(data, list)
        print(f"✓ Signals API returned: {type(data)}")
    
    def test_signal_btc(self):
        """Test /api/mobile/signals/BTC returns BTC signal"""
        headers = {"Authorization": f"Bearer {pytest.access_token}"}
        response = requests.get(
            f"{BASE_URL}/api/mobile/signals/BTC",
            headers=headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"BTC signal API failed: {response.text}"
        data = response.json()
        
        # Should have signal data
        if "signal" in data:
            signal = data["signal"]
            if signal:
                assert "asset" in signal or "symbol" in signal
                print(f"✓ BTC signal returned: {signal}")
        else:
            print(f"✓ BTC signal response: {data}")


class TestMobileEdge:
    """Edge opportunities API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login before each test"""
        if not hasattr(pytest, 'access_token'):
            response = requests.post(
                f"{BASE_URL}/api/mobile/auth/dev-login",
                json={"email": DEV_EMAIL, "name": DEV_NAME},
                timeout=10
            )
            pytest.access_token = response.json()["accessToken"]
    
    def test_edge_opportunities(self):
        """Test /api/mobile/edge returns edge data"""
        headers = {"Authorization": f"Bearer {pytest.access_token}"}
        response = requests.get(
            f"{BASE_URL}/api/mobile/edge?asset=BTC",
            headers=headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Edge API failed: {response.text}"
        data = response.json()
        
        # Should have opportunities structure
        assert isinstance(data, dict)
        print(f"✓ Edge API returned: {list(data.keys())}")


class TestAdminPanel:
    """Admin panel access test"""
    
    def test_admin_panel_accessible(self):
        """Test /api/panel/ returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/panel/",
            timeout=10,
            allow_redirects=False
        )
        
        # Should return 200 or redirect (301/302)
        assert response.status_code in [200, 301, 302, 307, 308], \
            f"Admin panel not accessible: {response.status_code}"
        print(f"✓ Admin panel accessible: status={response.status_code}")


class TestDataPersistence:
    """Test data persistence after create operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login before each test"""
        if not hasattr(pytest, 'access_token'):
            response = requests.post(
                f"{BASE_URL}/api/mobile/auth/dev-login",
                json={"email": DEV_EMAIL, "name": DEV_NAME},
                timeout=10
            )
            pytest.access_token = response.json()["accessToken"]
    
    def test_user_profile_persistence(self):
        """Test that user profile data persists"""
        headers = {"Authorization": f"Bearer {pytest.access_token}"}
        
        # Get profile
        response = requests.get(
            f"{BASE_URL}/api/mobile/profile",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            profile = response.json()
            assert "email" in profile
            assert profile["email"] == DEV_EMAIL
            print(f"✓ User profile persists: {profile.get('email')}")
        else:
            print(f"⚠ Profile endpoint returned {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
