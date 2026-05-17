"""
FOMO Mobile App Backend API Tests
Tests: Health, Dev Login, Home, Feed Intelligence, Signals
"""
import pytest
import requests
import os

# Get backend URL from environment
BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')

if not BASE_URL:
    pytest.skip("EXPO_PUBLIC_BACKEND_URL not set", allow_module_level=True)


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def auth_token(api_client):
    """Get auth token via dev-login for authenticated tests"""
    response = api_client.post(f"{BASE_URL}/api/mobile/auth/dev-login", json={
        "email": "dev@fomo.ai",
        "name": "FOMO Developer"
    })
    if response.status_code != 200:
        pytest.skip(f"Dev login failed: {response.status_code}")
    
    data = response.json()
    return data.get('accessToken')


class TestHealth:
    """Health check endpoint"""
    
    def test_health_endpoint(self, api_client):
        """GET /api/health should return 200 with status ok"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('status') == 'ok', f"Expected status=ok, got {data.get('status')}"
        assert 'service' in data, "Response should contain 'service' field"
        print(f"✓ Health check passed: {data}")


class TestAuth:
    """Authentication endpoints"""
    
    def test_dev_login_success(self, api_client):
        """POST /api/mobile/auth/dev-login should return tokens and user"""
        response = api_client.post(f"{BASE_URL}/api/mobile/auth/dev-login", json={
            "email": "dev@fomo.ai",
            "name": "FOMO Developer"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'accessToken' in data, "Response should contain accessToken"
        assert 'refreshToken' in data, "Response should contain refreshToken"
        assert 'user' in data, "Response should contain user object"
        
        user = data['user']
        assert user.get('email') == 'dev@fomo.ai', f"Expected email=dev@fomo.ai, got {user.get('email')}"
        assert user.get('name') == 'FOMO Developer', f"Expected name=FOMO Developer, got {user.get('name')}"
        assert 'plan' in user, "User should have plan field"
        
        print(f"✓ Dev login successful: user={user.get('email')}, plan={user.get('plan')}")


class TestHome:
    """Home screen endpoint (requires auth)"""
    
    def test_home_endpoint_with_auth(self, api_client, auth_token):
        """GET /api/mobile/home?asset=BTC should return home data"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = api_client.get(f"{BASE_URL}/api/mobile/home?asset=BTC", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'asset' in data, "Response should contain asset field"
        assert 'price' in data, "Response should contain price field"
        assert 'decision' in data, "Response should contain decision field"
        
        print(f"✓ Home endpoint passed: asset={data.get('asset')}, price={data.get('price')}, decision={data.get('decision')}")
    
    def test_home_endpoint_without_auth(self, api_client):
        """GET /api/mobile/home without auth should still work (optional auth)"""
        response = api_client.get(f"{BASE_URL}/api/mobile/home?asset=BTC")
        # Home endpoint uses optional auth, so it should work without token
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'asset' in data, "Response should contain asset field"
        print(f"✓ Home endpoint (no auth) passed: asset={data.get('asset')}")


class TestFeed:
    """Feed intelligence endpoint"""
    
    def test_feed_intelligence_endpoint(self, api_client):
        """GET /api/mobile/feed/intelligence?asset=BTC should return intelligence data"""
        response = api_client.get(f"{BASE_URL}/api/mobile/feed/intelligence?asset=BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'ok' in data, "Response should contain 'ok' field"
        # Feed intelligence may return empty data on fresh deployment
        print(f"✓ Feed intelligence endpoint passed: ok={data.get('ok')}")


class TestSignals:
    """Signals endpoint"""
    
    def test_signals_endpoint(self, api_client):
        """GET /api/mobile/signals?horizon=swing should return signals"""
        response = api_client.get(f"{BASE_URL}/api/mobile/signals?horizon=swing")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'ok' in data, "Response should contain 'ok' field"
        assert data.get('ok') == True, f"Expected ok=true, got {data.get('ok')}"
        assert 'signals' in data, "Response should contain 'signals' field"
        assert isinstance(data.get('signals'), list), "Signals should be a list"
        
        print(f"✓ Signals endpoint passed: ok={data.get('ok')}, count={len(data.get('signals', []))}")
    
    def test_signals_btc_specific(self, api_client):
        """GET /api/mobile/signals/BTC should return BTC signal"""
        response = api_client.get(f"{BASE_URL}/api/mobile/signals/BTC?horizon=swing")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'ok' in data, "Response should contain 'ok' field"
        assert 'signal' in data, "Response should contain 'signal' field"
        
        print(f"✓ BTC signal endpoint passed: ok={data.get('ok')}")


class TestMarketState:
    """Market state endpoint"""
    
    def test_market_state_endpoint(self, api_client):
        """GET /api/mobile/market-state should return market state"""
        response = api_client.get(f"{BASE_URL}/api/mobile/market-state")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'ok' in data, "Response should contain 'ok' field"
        
        print(f"✓ Market state endpoint passed: ok={data.get('ok')}")
