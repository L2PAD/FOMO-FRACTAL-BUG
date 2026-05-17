"""
Stripe Crypto Billing Integration Tests
Tests for new crypto (USDC) payment endpoints alongside existing card payment.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBillingEndpointsExist:
    """Verify billing endpoints exist and return correct status codes without auth."""
    
    def test_create_checkout_returns_401_without_auth(self):
        """POST /api/billing/create-checkout should return 401 without auth (route exists)."""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={"origin_url": "https://example.com"},
            headers={"Content-Type": "application/json"}
        )
        # 401 = route exists but needs auth, 404 = route doesn't exist
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"PASS: POST /api/billing/create-checkout returns 401 (route exists, needs auth)")
    
    def test_create_crypto_checkout_returns_401_without_auth(self):
        """POST /api/billing/create-crypto-checkout should return 401 without auth (route exists)."""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-crypto-checkout",
            json={"origin_url": "https://example.com"},
            headers={"Content-Type": "application/json"}
        )
        # 401 = route exists but needs auth, 404 = route doesn't exist
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"PASS: POST /api/billing/create-crypto-checkout returns 401 (route exists, needs auth)")
    
    def test_crypto_checkout_status_returns_401_without_auth(self):
        """GET /api/billing/crypto-checkout-status/{session_id} should return 401 without auth."""
        response = requests.get(
            f"{BASE_URL}/api/billing/crypto-checkout-status/test_session_123",
            headers={"Content-Type": "application/json"}
        )
        # 401 = route exists but needs auth, 404 = route doesn't exist
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"PASS: GET /api/billing/crypto-checkout-status returns 401 (route exists, needs auth)")
    
    def test_crypto_webhook_returns_200_without_auth(self):
        """POST /api/billing/webhook/crypto should return 200 without auth (webhook endpoint)."""
        response = requests.post(
            f"{BASE_URL}/api/billing/webhook/crypto",
            json={},
            headers={"Content-Type": "application/json"}
        )
        # Webhook endpoints should accept requests without auth
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=True, got {data}"
        print(f"PASS: POST /api/billing/webhook/crypto returns 200 (webhook endpoint)")
    
    def test_billing_status_returns_401_without_auth(self):
        """GET /api/billing/status should return 401 without auth."""
        response = requests.get(
            f"{BASE_URL}/api/billing/status",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"PASS: GET /api/billing/status returns 401 (route exists, needs auth)")
    
    def test_checkout_status_returns_401_without_auth(self):
        """GET /api/billing/checkout-status/{session_id} should return 401 without auth."""
        response = requests.get(
            f"{BASE_URL}/api/billing/checkout-status/test_session_123",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"PASS: GET /api/billing/checkout-status returns 401 (route exists, needs auth)")
    
    def test_portal_returns_401_without_auth(self):
        """POST /api/billing/portal should return 401 without auth."""
        response = requests.post(
            f"{BASE_URL}/api/billing/portal",
            json={"origin_url": "https://example.com"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"PASS: POST /api/billing/portal returns 401 (route exists, needs auth)")
    
    def test_regular_webhook_returns_200_without_auth(self):
        """POST /api/billing/webhook should return 200 without auth (webhook endpoint)."""
        response = requests.post(
            f"{BASE_URL}/api/billing/webhook",
            json={},
            headers={"Content-Type": "application/json"}
        )
        # Webhook endpoints should accept requests without auth
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=True, got {data}"
        print(f"PASS: POST /api/billing/webhook returns 200 (webhook endpoint)")


class TestHealthAndBasicEndpoints:
    """Verify basic health and API endpoints."""
    
    def test_health_endpoint(self):
        """GET /api/health should return 200."""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=True, got {data}"
        print(f"PASS: GET /api/health returns 200 OK")
    
    def test_auth_me_returns_401_or_200(self):
        """GET /api/auth/me should return 401 without auth or 200 with user info."""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        # 401 = not authenticated (correct), 200 = authenticated
        assert response.status_code in [200, 401], f"Expected 200 or 401, got {response.status_code}"
        print(f"PASS: GET /api/auth/me returns {response.status_code} (route exists)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
