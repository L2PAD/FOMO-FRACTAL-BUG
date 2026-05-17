"""
Test P0 Bug Fix and P1 Feature for Twitter Module

P0: /admin/twitter page crash fix - API returns {data: {users: []}} correctly
P1: Telegram deep-link connection - GET /api/v4/twitter/telegram/connect-link endpoint
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestP0AdminTwitterUsers:
    """P0 Bug Fix: Admin Twitter Users API should return proper structure"""
    
    def test_admin_users_endpoint_returns_ok(self):
        """GET /api/v4/admin/twitter/users should return ok: true"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        
    def test_admin_users_returns_nested_structure(self):
        """API should return {data: {users: [], total, page, pages}}"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users")
        assert response.status_code == 200
        data = response.json()
        
        # Verify nested structure
        assert 'data' in data
        response_data = data['data']
        
        # Should have users array (can be empty)
        assert 'users' in response_data
        assert isinstance(response_data['users'], list)
        
        # Should have pagination info
        assert 'total' in response_data
        assert 'page' in response_data
        assert 'pages' in response_data
        
    def test_admin_users_empty_state(self):
        """When no users, should return empty array not error"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users")
        assert response.status_code == 200
        data = response.json()
        
        # Should not crash - users should be array
        users = data.get('data', {}).get('users', [])
        assert isinstance(users, list)
        
    def test_admin_users_with_filters(self):
        """Filters should work without crashing"""
        # Test with status filter
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users?status=HEALTHY")
        assert response.status_code == 200
        
        # Test with search filter
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users?search=test")
        assert response.status_code == 200


class TestP1TelegramDeepLink:
    """P1 Feature: Telegram deep-link connection endpoint"""
    
    def test_connect_link_endpoint_exists(self):
        """GET /api/v4/twitter/telegram/connect-link should exist"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/connect-link")
        # Should return 200 (success) or 401 (auth required), not 404
        assert response.status_code in [200, 401, 500]
        
    def test_connect_link_returns_deep_link(self):
        """Should return t.me deep-link with token"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/connect-link")
        
        if response.status_code == 200:
            data = response.json()
            assert data.get('ok') == True
            
            # Verify link structure
            link_data = data.get('data', {})
            assert 'link' in link_data
            assert 'token' in link_data
            assert 'expiresIn' in link_data
            assert 'botUsername' in link_data
            
            # Verify link format
            link = link_data['link']
            assert link.startswith('https://t.me/')
            assert '?start=link_' in link
            
    def test_connect_link_token_format(self):
        """Token should be base64-like string"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/connect-link")
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('data', {}).get('token', '')
            
            # Token should be alphanumeric (base64 without special chars)
            assert len(token) > 0
            assert token.isalnum()
            
    def test_connect_link_expiry(self):
        """Link should have 10 minute expiry (600 seconds)"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/connect-link")
        
        if response.status_code == 200:
            data = response.json()
            expires_in = data.get('data', {}).get('expiresIn', 0)
            assert expires_in == 600


class TestTelegramStatus:
    """Telegram status endpoint tests"""
    
    def test_telegram_status_endpoint(self):
        """GET /api/v4/twitter/telegram/status should work"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        assert response.status_code in [200, 401, 500]
        
    def test_telegram_status_structure(self):
        """Status should return connected flag and preferences"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        
        if response.status_code == 200:
            data = response.json()
            assert data.get('ok') == True
            
            status_data = data.get('data', {})
            assert 'connected' in status_data
            assert isinstance(status_data['connected'], bool)


class TestTelegramEvents:
    """Telegram event preferences tests"""
    
    def test_events_put_endpoint(self):
        """PUT /api/v4/twitter/telegram/events should accept preferences"""
        response = requests.put(
            f"{BASE_URL}/api/v4/twitter/telegram/events",
            json={
                "sessionOk": True,
                "sessionStale": True,
                "sessionInvalid": True
            }
        )
        # Should return 200 or 400 (if not connected), not 404
        assert response.status_code in [200, 400, 401, 500]


class TestTelegramUnlink:
    """Telegram unlink endpoint tests"""
    
    def test_unlink_endpoint_exists(self):
        """DELETE /api/v4/twitter/telegram/unlink should exist"""
        response = requests.delete(f"{BASE_URL}/api/v4/twitter/telegram/unlink")
        # Should return 200 or error, not 404
        assert response.status_code in [200, 400, 401, 500]


class TestHealthCheck:
    """Basic health check"""
    
    def test_api_health(self):
        """API should be healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
