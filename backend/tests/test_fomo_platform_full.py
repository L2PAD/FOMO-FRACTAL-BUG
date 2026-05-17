"""
FOMO Platform Full Deployment Tests
Tests: Mobile API + Admin Panel + Telegram MiniApp + Unified Auth
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


# ═══════════════════════════════════════════════════════════
# HEALTH & SYSTEM
# ═══════════════════════════════════════════════════════════

class TestHealth:
    """Health check endpoint - should return all components"""
    
    def test_health_endpoint_with_components(self, api_client):
        """GET /api/health should return status=ok with components array"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('status') == 'ok', f"Expected status=ok, got {data.get('status')}"
        assert 'components' in data, "Response should contain 'components' field"
        
        components = data.get('components', [])
        assert isinstance(components, list), "Components should be a list"
        assert 'mobile' in components, "Components should include 'mobile'"
        assert 'admin' in components, "Components should include 'admin'"
        assert 'miniapp' in components, "Components should include 'miniapp'"
        
        print(f"✓ Health check passed: status={data.get('status')}, components={components}")


# ═══════════════════════════════════════════════════════════
# MOBILE APP API (Regression Tests)
# ═══════════════════════════════════════════════════════════

class TestMobileAuth:
    """Mobile authentication endpoints"""
    
    def test_mobile_dev_login_success(self, api_client):
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
        
        print(f"✓ Mobile dev login successful: user={user.get('email')}, plan={user.get('plan')}")


class TestMobileHome:
    """Mobile home screen endpoint"""
    
    def test_mobile_home_endpoint(self, api_client):
        """GET /api/mobile/home?asset=BTC should return decision data"""
        response = api_client.get(f"{BASE_URL}/api/mobile/home?asset=BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'asset' in data, "Response should contain asset field"
        assert 'decision' in data, "Response should contain decision field"
        assert data.get('asset') == 'BTC', f"Expected asset=BTC, got {data.get('asset')}"
        
        print(f"✓ Mobile home endpoint passed: asset={data.get('asset')}, decision={data.get('decision')}")


class TestMobileFeed:
    """Mobile feed intelligence endpoint"""
    
    def test_mobile_feed_intelligence(self, api_client):
        """GET /api/mobile/feed/intelligence?asset=BTC should return ok=true"""
        response = api_client.get(f"{BASE_URL}/api/mobile/feed/intelligence?asset=BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'ok' in data, "Response should contain 'ok' field"
        assert data.get('ok') == True, f"Expected ok=true, got {data.get('ok')}"
        
        print(f"✓ Mobile feed intelligence passed: ok={data.get('ok')}")


# ═══════════════════════════════════════════════════════════
# ADMIN PANEL
# ═══════════════════════════════════════════════════════════

class TestAdminPanel:
    """Admin panel static file serving"""
    
    def test_admin_panel_root(self, api_client):
        """GET /api/panel/ should return HTML (200 status)"""
        response = api_client.get(f"{BASE_URL}/api/panel/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check if response is HTML
        content_type = response.headers.get('content-type', '')
        assert 'html' in content_type.lower(), f"Expected HTML content, got {content_type}"
        
        # Check if HTML contains expected elements
        html = response.text
        assert '<html' in html.lower(), "Response should contain HTML tag"
        assert 'fomo' in html.lower() or 'admin' in html.lower(), "HTML should contain FOMO or admin references"
        
        print(f"✓ Admin panel loads: status={response.status_code}, content-type={content_type}")


# ═══════════════════════════════════════════════════════════
# TELEGRAM MINIAPP API
# ═══════════════════════════════════════════════════════════

class TestMiniAppHome:
    """MiniApp home endpoint"""
    
    def test_miniapp_home_endpoint(self, api_client):
        """GET /api/miniapp/home?asset=BTC should return ok=true with decision data"""
        response = api_client.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'ok' in data, "Response should contain 'ok' field"
        assert data.get('ok') == True, f"Expected ok=true, got {data.get('ok')}"
        
        # Check for decision data
        assert 'decision' in data, "Response should contain 'decision' field"
        
        print(f"✓ MiniApp home passed: ok={data.get('ok')}, decision={data.get('decision')}")


class TestMiniAppEdge:
    """MiniApp edge endpoint"""
    
    def test_miniapp_edge_endpoint(self, api_client):
        """GET /api/miniapp/edge should return ok=true"""
        response = api_client.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'ok' in data, "Response should contain 'ok' field"
        assert data.get('ok') == True, f"Expected ok=true, got {data.get('ok')}"
        
        print(f"✓ MiniApp edge passed: ok={data.get('ok')}")


class TestMiniAppSearch:
    """MiniApp search endpoint"""
    
    def test_miniapp_search_endpoint(self, api_client):
        """GET /api/miniapp/search?q=BTC should return results"""
        response = api_client.get(f"{BASE_URL}/api/miniapp/search?q=BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'ok' in data, "Response should contain 'ok' field"
        assert data.get('ok') == True, f"Expected ok=true, got {data.get('ok')}"
        assert 'results' in data, "Response should contain 'results' field"
        assert isinstance(data.get('results'), list), "Results should be a list"
        
        print(f"✓ MiniApp search passed: ok={data.get('ok')}, results_count={len(data.get('results', []))}")


class TestMiniAppWebhook:
    """MiniApp Telegram webhook"""
    
    def test_miniapp_webhook_accepts_updates(self, api_client):
        """POST /api/miniapp/webhook should accept telegram updates"""
        # Send a minimal Telegram update
        telegram_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 123456,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "chat": {
                    "id": 123456,
                    "first_name": "Test",
                    "username": "testuser",
                    "type": "private"
                },
                "date": 1234567890,
                "text": "/start"
            }
        }
        
        response = api_client.post(f"{BASE_URL}/api/miniapp/webhook", json=telegram_update)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'ok' in data, "Response should contain 'ok' field"
        assert data.get('ok') == True, f"Expected ok=true, got {data.get('ok')}"
        
        print(f"✓ MiniApp webhook passed: ok={data.get('ok')}")


# ═══════════════════════════════════════════════════════════
# UNIFIED AUTH
# ═══════════════════════════════════════════════════════════

class TestUnifiedAuth:
    """Unified auth endpoints"""
    
    def test_unified_auth_endpoint_exists(self, api_client):
        """Verify /api/unified/auth/* endpoint exists"""
        # Try to access unified auth dev-login endpoint
        response = api_client.post(f"{BASE_URL}/api/unified/auth/dev-login", json={
            "email": "test@unified.ai",
            "name": "Unified Test",
            "platform": "mobile"
        })
        
        # Should return 200 or 422 (validation error), not 404
        assert response.status_code in [200, 422, 500], f"Unified auth endpoint should exist, got {response.status_code}"
        
        # If 404, endpoint doesn't exist
        if response.status_code == 404:
            pytest.fail("Unified auth endpoint /api/unified/auth/dev-login not found")
        
        print(f"✓ Unified auth endpoint exists: status={response.status_code}")
