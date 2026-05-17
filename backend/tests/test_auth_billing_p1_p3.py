"""
P1-P3 Auth & Billing API Tests
Tests for:
- Auth endpoints (session, me, logout)
- Billing endpoints (checkout, status, portal, webhook)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthEndpoints:
    """Auth API tests - unauthenticated flows"""
    
    def test_auth_me_returns_401_when_not_authenticated(self):
        """GET /api/auth/me should return 401 when not authenticated"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data
        print(f"✓ GET /api/auth/me returns 401 when not authenticated")
    
    def test_auth_logout_returns_ok(self):
        """POST /api/auth/logout should return ok:true"""
        response = requests.post(f"{BASE_URL}/api/auth/logout")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        print(f"✓ POST /api/auth/logout returns ok:true")
    
    def test_auth_session_requires_session_id(self):
        """POST /api/auth/session should require session_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/session",
            json={},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ POST /api/auth/session requires session_id")


class TestBillingEndpoints:
    """Billing API tests - unauthenticated flows"""
    
    def test_billing_status_returns_401_when_not_authenticated(self):
        """GET /api/billing/status should return 401 when not authenticated"""
        response = requests.get(f"{BASE_URL}/api/billing/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ GET /api/billing/status returns 401 when not authenticated")
    
    def test_billing_create_checkout_returns_401_when_not_authenticated(self):
        """POST /api/billing/create-checkout should return 401 when not authenticated"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={"origin_url": "https://example.com"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ POST /api/billing/create-checkout returns 401 when not authenticated")
    
    def test_billing_portal_returns_401_when_not_authenticated(self):
        """POST /api/billing/portal should return 401 when not authenticated"""
        response = requests.post(
            f"{BASE_URL}/api/billing/portal",
            json={"origin_url": "https://example.com"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ POST /api/billing/portal returns 401 when not authenticated")
    
    def test_billing_webhook_accepts_post(self):
        """POST /api/billing/webhook should accept POST requests"""
        # Webhook should accept POST even without valid signature (returns ok in dev mode)
        response = requests.post(
            f"{BASE_URL}/api/billing/webhook",
            json={"type": "test", "data": {}},
            headers={"Content-Type": "application/json"}
        )
        # Should return 200 (dev mode parses raw JSON)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ POST /api/billing/webhook accepts POST requests")


class TestHealthEndpoint:
    """Health check endpoint"""
    
    def test_health_endpoint(self):
        """GET /api/health or /health should return ok"""
        # Try /api/health first (backend API)
        response = requests.get(f"{BASE_URL}/api/exchange/health")
        assert response.status_code in [200, 503], f"Expected 200 or 503, got {response.status_code}"
        data = response.json()
        assert "status" in data, f"Expected status in response, got {data}"
        print(f"✓ GET /api/exchange/health returns status: {data.get('status')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
