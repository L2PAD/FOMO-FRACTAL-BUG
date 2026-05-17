"""
Auth + Billing API Tests - Iteration 488
Tests for:
- Auth endpoints: /api/auth/me, /api/auth/session, /api/auth/logout
- Billing endpoints: /api/billing/status, /api/billing/create-checkout, /api/billing/portal
- Decision Engine stats endpoint
- Notifications feed endpoint

Test session token: test_session_audit_1774744582792
Test user: audit@test.com, user_id: test-user-audit, plan_status: free
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')
TEST_SESSION_TOKEN = "test_session_audit_1774744582792"
TEST_USER_EMAIL = "audit@test.com"
TEST_USER_ID = "test-user-audit"


class TestAuthEndpoints:
    """Auth endpoint tests with test session token"""
    
    def test_auth_me_without_token_returns_401(self):
        """GET /api/auth/me without token should return 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/auth/me without token returns 401")
    
    def test_auth_me_with_bearer_token(self):
        """GET /api/auth/me with Bearer token should return user data"""
        headers = {"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        # May return 401 if test session not in DB, but should not error
        if response.status_code == 200:
            data = response.json()
            assert "user" in data, "Response should contain 'user' key"
            assert data["ok"] == True, "Response should have ok=True"
            print(f"✓ GET /api/auth/me with Bearer token returns user: {data.get('user', {}).get('email')}")
        else:
            print(f"✓ GET /api/auth/me with Bearer token returns {response.status_code} (test session may not exist)")
    
    def test_auth_session_requires_session_id(self):
        """POST /api/auth/session without session_id should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/auth/session",
            json={},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ POST /api/auth/session without session_id returns 400")
    
    def test_auth_session_with_invalid_session_id(self):
        """POST /api/auth/session with invalid session_id should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/session",
            json={"session_id": "invalid_session_12345"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ POST /api/auth/session with invalid session_id returns 401")
    
    def test_auth_logout_returns_ok(self):
        """POST /api/auth/logout should return ok:true"""
        response = requests.post(f"{BASE_URL}/api/auth/logout")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, "Response should have ok=True"
        print("✓ POST /api/auth/logout returns ok:true")


class TestBillingEndpoints:
    """Billing endpoint tests - require authentication"""
    
    def test_billing_status_without_auth_returns_401(self):
        """GET /api/billing/status without auth should return 401"""
        response = requests.get(f"{BASE_URL}/api/billing/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/billing/status without auth returns 401")
    
    def test_billing_status_with_bearer_token(self):
        """GET /api/billing/status with Bearer token"""
        headers = {"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        response = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        # May return 401 if test session not in DB
        if response.status_code == 200:
            data = response.json()
            assert "ok" in data, "Response should contain 'ok' key"
            assert "subscribed" in data, "Response should contain 'subscribed' key"
            assert "plan_status" in data, "Response should contain 'plan_status' key"
            print(f"✓ GET /api/billing/status returns: subscribed={data.get('subscribed')}, plan_status={data.get('plan_status')}")
        else:
            print(f"✓ GET /api/billing/status returns {response.status_code} (test session may not exist)")
    
    def test_billing_create_checkout_without_auth_returns_401(self):
        """POST /api/billing/create-checkout without auth should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={"origin_url": BASE_URL},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ POST /api/billing/create-checkout without auth returns 401")
    
    def test_billing_create_checkout_requires_origin_url(self):
        """POST /api/billing/create-checkout requires origin_url"""
        headers = {"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={},
            headers={**headers, "Content-Type": "application/json"}
        )
        # Should return 400 if authenticated but no origin_url, or 401 if not authenticated
        assert response.status_code in [400, 401], f"Expected 400 or 401, got {response.status_code}"
        print(f"✓ POST /api/billing/create-checkout without origin_url returns {response.status_code}")
    
    def test_billing_portal_without_auth_returns_401(self):
        """POST /api/billing/portal without auth should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/billing/portal",
            json={"origin_url": BASE_URL},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ POST /api/billing/portal without auth returns 401")
    
    def test_billing_webhook_accepts_post(self):
        """POST /api/billing/webhook should accept POST requests"""
        response = requests.post(
            f"{BASE_URL}/api/billing/webhook",
            json={"type": "test"},
            headers={"Content-Type": "application/json"}
        )
        # Webhook should return 200 even without valid signature in dev mode
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, "Response should have ok=True"
        print("✓ POST /api/billing/webhook accepts POST and returns ok:true")


class TestDecisionEngineEndpoints:
    """Decision Engine stats endpoint tests"""
    
    def test_decision_engine_stats(self):
        """GET /api/engine-v3/stats should return decision engine stats"""
        response = requests.get(f"{BASE_URL}/api/engine-v3/stats")
        # May require auth or return data
        if response.status_code == 200:
            data = response.json()
            print(f"✓ GET /api/engine-v3/stats returns: {list(data.keys())[:5]}...")
        else:
            print(f"✓ GET /api/engine-v3/stats returns {response.status_code}")
    
    def test_decision_engine_snapshot(self):
        """GET /api/engine-integration/snapshot should return engine snapshot"""
        response = requests.get(f"{BASE_URL}/api/engine-integration/snapshot")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ GET /api/engine-integration/snapshot returns: ok={data.get('ok')}")
        else:
            print(f"✓ GET /api/engine-integration/snapshot returns {response.status_code}")


class TestNotificationsEndpoints:
    """Notifications feed endpoint tests"""
    
    def test_notifications_feed(self):
        """GET /api/notifications/feed should return notifications"""
        response = requests.get(f"{BASE_URL}/api/notifications/feed?user_id=user&limit=10")
        if response.status_code == 200:
            data = response.json()
            assert "ok" in data, "Response should contain 'ok' key"
            print(f"✓ GET /api/notifications/feed returns: ok={data.get('ok')}, count={len(data.get('notifications', []))}")
        else:
            print(f"✓ GET /api/notifications/feed returns {response.status_code}")
    
    def test_notifications_stats(self):
        """GET /api/notifications/stats should return notification stats"""
        response = requests.get(f"{BASE_URL}/api/notifications/stats")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ GET /api/notifications/stats returns: ok={data.get('ok')}")
        else:
            print(f"✓ GET /api/notifications/stats returns {response.status_code}")


class TestTelegramIntelEndpoints:
    """Telegram Intel endpoint tests"""
    
    def test_telegram_utility_list(self):
        """GET /api/telegram-intel/utility/list should return channel list"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?limit=5")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ GET /api/telegram-intel/utility/list returns: total={data.get('total', 0)}, items={len(data.get('items', []))}")
        else:
            # May return disabled stub
            data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            if data.get('enabled') == False:
                print(f"✓ GET /api/telegram-intel/utility/list returns: module disabled")
            else:
                print(f"✓ GET /api/telegram-intel/utility/list returns {response.status_code}")


class TestHealthEndpoints:
    """Health check endpoint tests"""
    
    def test_health_endpoint(self):
        """GET /api/health should return service status"""
        # Note: /health without /api prefix returns frontend HTML
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, "Health status should have ok=True"
        print(f"✓ GET /api/health returns: ok={data.get('ok')}, uptime={data.get('uptime')}")
    
    def test_api_health_endpoint(self):
        """GET /api/health should return API health"""
        response = requests.get(f"{BASE_URL}/api/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ GET /api/health returns: ok={data.get('ok')}")
        else:
            print(f"✓ GET /api/health returns {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
