"""
Stripe Billing Integration Tests - Iteration 490
Tests the Stripe payment integration fix (api_base for Emergent proxy)

Endpoints tested:
- POST /api/billing/create-checkout - Create Stripe checkout session
- GET /api/billing/status - Get subscription status
- GET /api/billing/checkout-status/{session_id} - Check checkout session status
- POST /api/billing/portal - Create Stripe customer portal session
- POST /api/billing/webhook - Handle Stripe webhooks
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_SESSION_TOKEN = "sess_d82481030085456c92079883a6df3c62"


class TestBillingEndpointsAuth:
    """Test billing endpoints require authentication"""

    def test_billing_status_requires_auth(self):
        """GET /api/billing/status should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/billing/status")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        data = response.json()
        assert "detail" in data or "error" in data
        print("✓ /api/billing/status returns 401 without auth")

    def test_create_checkout_requires_auth(self):
        """POST /api/billing/create-checkout should return 401 without auth"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={"origin_url": "https://example.com"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /api/billing/create-checkout returns 401 without auth")

    def test_portal_requires_auth(self):
        """POST /api/billing/portal should return 401 without auth"""
        response = requests.post(
            f"{BASE_URL}/api/billing/portal",
            json={"origin_url": "https://example.com"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /api/billing/portal returns 401 without auth")


class TestBillingStatus:
    """Test billing status endpoint"""

    def test_billing_status_returns_subscription_info(self):
        """GET /api/billing/status should return subscription status"""
        response = requests.get(
            f"{BASE_URL}/api/billing/status",
            cookies={"session_token": TEST_SESSION_TOKEN}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert data.get("ok") is True, "Response should have ok: true"
        assert "subscribed" in data, "Response should have 'subscribed' field"
        assert "plan_status" in data, "Response should have 'plan_status' field"
        assert data["plan_status"] in ["free", "active", "canceled", "trialing"], \
            f"Invalid plan_status: {data['plan_status']}"
        
        print(f"✓ /api/billing/status returns: subscribed={data['subscribed']}, plan_status={data['plan_status']}")


class TestCreateCheckout:
    """Test checkout session creation"""

    def test_create_checkout_requires_origin_url(self):
        """POST /api/billing/create-checkout should require origin_url"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={},
            cookies={"session_token": TEST_SESSION_TOKEN},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ /api/billing/create-checkout requires origin_url")

    def test_create_checkout_returns_stripe_url(self):
        """POST /api/billing/create-checkout should return Stripe checkout URL"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={"origin_url": "https://expo-telegram-web.preview.emergentagent.com"},
            cookies={"session_token": TEST_SESSION_TOKEN},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert data.get("ok") is True, "Response should have ok: true"
        assert "url" in data, "Response should have 'url' field"
        assert "session_id" in data, "Response should have 'session_id' field"
        
        # Verify URL is a valid Stripe checkout URL
        assert data["url"].startswith("https://checkout.stripe.com/"), \
            f"URL should be Stripe checkout URL, got: {data['url'][:50]}..."
        
        # Verify session_id format
        assert data["session_id"].startswith("cs_test_"), \
            f"Session ID should start with cs_test_, got: {data['session_id'][:20]}..."
        
        print(f"✓ /api/billing/create-checkout returns valid Stripe URL")
        print(f"  Session ID: {data['session_id'][:30]}...")
        
        # Store session_id for checkout-status test
        return data["session_id"]


class TestCheckoutStatus:
    """Test checkout status endpoint"""

    @pytest.fixture
    def checkout_session_id(self):
        """Create a checkout session and return its ID"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={"origin_url": "https://expo-telegram-web.preview.emergentagent.com"},
            cookies={"session_token": TEST_SESSION_TOKEN},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            return response.json().get("session_id")
        pytest.skip("Could not create checkout session")

    def test_checkout_status_returns_session_info(self, checkout_session_id):
        """GET /api/billing/checkout-status/{session_id} should return session status"""
        response = requests.get(
            f"{BASE_URL}/api/billing/checkout-status/{checkout_session_id}",
            cookies={"session_token": TEST_SESSION_TOKEN}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert data.get("ok") is True, "Response should have ok: true"
        assert "status" in data, "Response should have 'status' field"
        assert "payment_status" in data, "Response should have 'payment_status' field"
        
        # Verify status values
        assert data["status"] in ["open", "complete", "expired"], \
            f"Invalid status: {data['status']}"
        assert data["payment_status"] in ["unpaid", "paid", "no_payment_required"], \
            f"Invalid payment_status: {data['payment_status']}"
        
        print(f"✓ /api/billing/checkout-status returns: status={data['status']}, payment_status={data['payment_status']}")


class TestPortal:
    """Test Stripe customer portal"""

    def test_portal_returns_stripe_url(self):
        """POST /api/billing/portal should return Stripe portal URL"""
        response = requests.post(
            f"{BASE_URL}/api/billing/portal",
            json={"origin_url": "https://expo-telegram-web.preview.emergentagent.com"},
            cookies={"session_token": TEST_SESSION_TOKEN},
            headers={"Content-Type": "application/json"}
        )
        
        # Portal may return 400 if user has no stripe_customer_id, or 200 with URL
        if response.status_code == 400:
            data = response.json()
            assert "No billing account" in str(data) or "detail" in data
            print("✓ /api/billing/portal returns 400 for user without billing account (expected)")
        else:
            assert response.status_code == 200, f"Expected 200 or 400, got {response.status_code}"
            data = response.json()
            assert data.get("ok") is True
            assert "url" in data
            assert "stripe.com" in data["url"] or "billing.stripe.com" in data["url"]
            print(f"✓ /api/billing/portal returns valid Stripe portal URL")


class TestWebhook:
    """Test Stripe webhook endpoint"""

    def test_webhook_accepts_events(self):
        """POST /api/billing/webhook should accept webhook events"""
        response = requests.post(
            f"{BASE_URL}/api/billing/webhook",
            json={"type": "test.event", "data": {"object": {}}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True
        print("✓ /api/billing/webhook accepts events and returns ok: true")

    def test_webhook_handles_checkout_completed(self):
        """POST /api/billing/webhook should handle checkout.session.completed"""
        response = requests.post(
            f"{BASE_URL}/api/billing/webhook",
            json={
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "metadata": {"user_id": "test_user"},
                        "subscription": None
                    }
                }
            },
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True
        print("✓ /api/billing/webhook handles checkout.session.completed")


class TestStripeApiBaseConfiguration:
    """Test that Stripe API base is correctly configured for Emergent proxy"""

    def test_checkout_uses_emergent_proxy(self):
        """Verify checkout session creation works (implies api_base is correct)"""
        # If api_base wasn't set correctly, Stripe would reject the sk_test_emergent key
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={"origin_url": "https://expo-telegram-web.preview.emergentagent.com"},
            cookies={"session_token": TEST_SESSION_TOKEN},
            headers={"Content-Type": "application/json"}
        )
        
        # If we get a 200 with valid Stripe URL, the api_base fix is working
        assert response.status_code == 200, \
            f"Checkout failed - api_base may not be configured correctly. Status: {response.status_code}, Response: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("url", "").startswith("https://checkout.stripe.com/")
        
        print("✓ Stripe API base correctly configured for Emergent proxy (checkout works)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
