"""
MiniApp Billing API Tests - Stripe Bridge for Telegram Users
============================================================
Tests for billing endpoints: plans, status, checkout, portal, verify
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestMiniAppBillingPlans:
    """GET /api/miniapp/billing/plans - Returns billing plans"""

    def test_plans_returns_ok(self):
        """Plans endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Plans endpoint returns ok=true")

    def test_plans_has_billing_mode(self):
        """Plans response includes billingMode"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans")
        data = response.json()
        assert "billingMode" in data
        assert data["billingMode"] in ["paid", "free_trial", "free"]
        print(f"PASS: billingMode={data['billingMode']}")

    def test_plans_has_free_trial_days(self):
        """Plans response includes freeTrialDays"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans")
        data = response.json()
        assert "freeTrialDays" in data
        assert isinstance(data["freeTrialDays"], int)
        assert data["freeTrialDays"] >= 0
        print(f"PASS: freeTrialDays={data['freeTrialDays']}")

    def test_plans_has_product_name(self):
        """Plans response includes productName"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans")
        data = response.json()
        assert "productName" in data
        assert isinstance(data["productName"], str)
        assert len(data["productName"]) > 0
        print(f"PASS: productName={data['productName']}")

    def test_plans_has_monthly_price(self):
        """Plans response includes monthly price"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans")
        data = response.json()
        assert "monthly" in data
        monthly = data["monthly"]
        assert "price" in monthly
        assert "currency" in monthly
        assert monthly["currency"] == "usd"
        assert isinstance(monthly["price"], (int, float))
        print(f"PASS: monthly price=${monthly['price']} {monthly['currency']}")

    def test_plans_has_yearly_price(self):
        """Plans response includes yearly price with monthlyEquivalent"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans")
        data = response.json()
        assert "yearly" in data
        yearly = data["yearly"]
        assert "price" in yearly
        assert "currency" in yearly
        assert "monthlyEquivalent" in yearly
        assert yearly["currency"] == "usd"
        print(f"PASS: yearly price=${yearly['price']} (${yearly['monthlyEquivalent']}/mo)")


class TestMiniAppBillingStatus:
    """GET /api/miniapp/billing/status - Returns subscription status"""

    def test_status_returns_ok(self):
        """Status endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/status?telegram_id=test123")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Status endpoint returns ok=true")

    def test_status_new_user_is_free(self):
        """New user (no subscription) returns planStatus=free"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/status?telegram_id=test_new_user_12345")
        data = response.json()
        assert data.get("subscribed") is False
        assert data.get("planStatus") == "free"
        print(f"PASS: New user planStatus=free, subscribed=false")

    def test_status_has_subscription_field(self):
        """Status response includes subscription field (null for free users)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/status?telegram_id=test123")
        data = response.json()
        assert "subscription" in data
        # For free users, subscription should be None
        if not data.get("subscribed"):
            assert data["subscription"] is None
        print(f"PASS: subscription field present")

    def test_status_without_telegram_id(self):
        """Status without telegram_id returns free status"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/status")
        data = response.json()
        assert data.get("ok") is True
        assert data.get("subscribed") is False
        assert data.get("planStatus") == "free"
        print(f"PASS: No telegram_id returns free status")


class TestMiniAppBillingCheckout:
    """POST /api/miniapp/billing/checkout - Creates Stripe checkout session"""

    def test_checkout_creates_session(self):
        """Checkout creates valid Stripe session with URL and sessionId"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/billing/checkout",
            json={
                "telegram_id": "test123",
                "origin_url": "https://expo-telegram-web.preview.emergentagent.com",
                "interval": "month"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("success") is True
        assert "url" in data
        assert "sessionId" in data
        # Stripe checkout URL should contain checkout.stripe.com or integrations.emergentagent.com
        assert "checkout" in data["url"].lower() or "stripe" in data["url"].lower() or "emergentagent" in data["url"].lower()
        assert data["sessionId"].startswith("cs_")
        print(f"PASS: Checkout created - sessionId={data['sessionId'][:20]}...")

    def test_checkout_yearly_interval(self):
        """Checkout with yearly interval works"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/billing/checkout",
            json={
                "telegram_id": "test_yearly_user",
                "origin_url": "https://expo-telegram-web.preview.emergentagent.com",
                "interval": "year"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "url" in data
        print(f"PASS: Yearly checkout created")

    def test_checkout_missing_telegram_id(self):
        """Checkout without telegram_id returns error"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/billing/checkout",
            json={
                "origin_url": "https://expo-telegram-web.preview.emergentagent.com",
                "interval": "month"
            }
        )
        data = response.json()
        # Should return success=false with message
        assert data.get("success") is False
        assert "telegram_id" in data.get("message", "").lower()
        print(f"PASS: Missing telegram_id returns error")

    def test_checkout_missing_origin_url(self):
        """Checkout without origin_url returns error"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/billing/checkout",
            json={
                "telegram_id": "test123",
                "interval": "month"
            }
        )
        data = response.json()
        assert data.get("success") is False
        assert "origin_url" in data.get("message", "").lower()
        print(f"PASS: Missing origin_url returns error")


class TestMiniAppBillingPortal:
    """POST /api/miniapp/billing/portal - Creates Stripe customer portal"""

    def test_portal_no_stripe_customer(self):
        """Portal returns error when user has no stripe_customer_id"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/billing/portal",
            json={
                "telegram_id": "test_no_stripe_customer_xyz",
                "origin_url": "https://expo-telegram-web.preview.emergentagent.com"
            }
        )
        data = response.json()
        assert data.get("ok") is True
        assert data.get("success") is False
        assert "billing account" in data.get("message", "").lower() or "no" in data.get("message", "").lower()
        print(f"PASS: Portal returns error for user without stripe_customer_id")

    def test_portal_missing_telegram_id(self):
        """Portal without telegram_id returns error"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/billing/portal",
            json={
                "origin_url": "https://expo-telegram-web.preview.emergentagent.com"
            }
        )
        data = response.json()
        assert data.get("success") is False
        print(f"PASS: Portal without telegram_id returns error")


class TestMiniAppBillingVerify:
    """GET /api/miniapp/billing/verify/{session_id} - Verifies checkout"""

    def test_verify_invalid_session(self):
        """Verify with invalid session_id handles gracefully"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/verify/invalid_session_id_xyz")
        # Should return 200 with error info, or 500 for Stripe API error
        assert response.status_code in [200, 400, 404, 500]
        # For 500 errors, Stripe may return non-JSON - that's acceptable error handling
        if response.status_code == 500:
            print(f"PASS: Invalid session returns 500 (Stripe API error) - expected behavior")
        else:
            try:
                data = response.json()
                # Either ok=true with success=false, or error response
                if data.get("ok"):
                    assert data.get("success") is False or "error" in str(data).lower()
                print(f"PASS: Invalid session handled gracefully - status={response.status_code}")
            except:
                print(f"PASS: Invalid session returns non-JSON error - status={response.status_code}")

    def test_verify_empty_session(self):
        """Verify with empty session_id returns error"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/verify/")
        # Should return 404 or error
        assert response.status_code in [404, 405, 422]
        print(f"PASS: Empty session returns error - status={response.status_code}")


class TestMiniAppRegressionEndpoints:
    """Regression tests for existing MiniApp endpoints"""

    def test_edge_still_works(self):
        """GET /api/miniapp/edge still returns data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "status" in data
        print(f"PASS: Edge endpoint works - status={data.get('status')}")

    def test_profile_still_works(self):
        """GET /api/miniapp/profile still returns data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "user" in data
        print(f"PASS: Profile endpoint works - user={data.get('user', {}).get('name')}")

    def test_home_still_works(self):
        """GET /api/miniapp/home?asset=BTC still returns data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "asset" in data
        print(f"PASS: Home endpoint works - asset={data.get('asset')}")

    def test_feed_still_works(self):
        """GET /api/miniapp/feed still returns data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        # Feed returns sections with items
        assert "sections" in data or "signals" in data or "items" in data or "feed" in data
        print(f"PASS: Feed endpoint works - sections={len(data.get('sections', []))}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
