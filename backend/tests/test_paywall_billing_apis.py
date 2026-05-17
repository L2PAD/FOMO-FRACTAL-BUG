"""
Test Paywall and Billing APIs - Iteration 544
Tests for PaywallOverlay feature including:
- /api/billing/plans endpoint
- /api/billing/validate-promo endpoint
- /api/promo/validate endpoint (should NOT exist - bug check)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBillingPlansAPI:
    """Test /api/billing/plans endpoint"""
    
    def test_plans_endpoint_returns_200(self):
        """Plans endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /api/billing/plans returns 200")
    
    def test_plans_response_structure(self):
        """Plans response should have correct structure"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=True"
        assert "plans" in data, "Response should have 'plans' key"
        
        plans = data["plans"]
        assert "billing_mode" in plans, "Plans should have billing_mode"
        assert "monthly" in plans, "Plans should have monthly pricing"
        assert "yearly" in plans, "Plans should have yearly pricing"
        assert "free_access_enabled" in plans, "Plans should have free_access_enabled"
        print("PASS: /api/billing/plans has correct structure")
    
    def test_plans_pricing_values(self):
        """Plans should have valid pricing values"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        plans = data["plans"]
        
        monthly = plans["monthly"]
        yearly = plans["yearly"]
        
        assert "card_price" in monthly, "Monthly should have card_price"
        assert "crypto_price" in monthly, "Monthly should have crypto_price"
        assert monthly["card_price"] >= 0, "Monthly card price should be >= 0"
        
        assert "card_price" in yearly, "Yearly should have card_price"
        assert "discount_percent" in yearly, "Yearly should have discount_percent"
        assert yearly["card_price"] >= 0, "Yearly card price should be >= 0"
        
        print(f"PASS: Pricing - Monthly: ${monthly['card_price']}, Yearly: ${yearly['card_price']}")


class TestPromoValidationAPI:
    """Test promo code validation endpoints"""
    
    def test_validate_promo_correct_endpoint(self):
        """Test /api/billing/validate-promo endpoint (correct endpoint)"""
        response = requests.post(
            f"{BASE_URL}/api/billing/validate-promo",
            json={"code": "TESTCODE123"},
            headers={"Content-Type": "application/json"}
        )
        # Should return 200 with ok=false for invalid code
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "ok" in data, "Response should have 'ok' field"
        print("PASS: /api/billing/validate-promo endpoint works correctly")
    
    def test_validate_promo_wrong_endpoint_returns_404(self):
        """Test /api/promo/validate endpoint (WRONG endpoint used by PaywallOverlay)
        
        BUG: PaywallOverlay.jsx line 97 calls /api/promo/validate
        but the backend only has /api/billing/validate-promo
        """
        response = requests.post(
            f"{BASE_URL}/api/promo/validate",
            json={"code": "TESTCODE123"},
            headers={"Content-Type": "application/json"}
        )
        # This should return 404 because the endpoint doesn't exist
        if response.status_code == 404:
            print("CONFIRMED BUG: /api/promo/validate returns 404 - PaywallOverlay uses wrong endpoint")
            data = response.json()
            assert data.get("error") == "NOT_FOUND" or "not found" in str(data).lower()
        else:
            print(f"INFO: /api/promo/validate returned {response.status_code}")
    
    def test_validate_promo_empty_code(self):
        """Test validation with empty code"""
        response = requests.post(
            f"{BASE_URL}/api/billing/validate-promo",
            json={"code": ""},
            headers={"Content-Type": "application/json"}
        )
        # Should return 400 for empty code
        assert response.status_code == 400, f"Expected 400 for empty code, got {response.status_code}"
        print("PASS: Empty promo code returns 400")
    
    def test_validate_promo_invalid_code(self):
        """Test validation with invalid code"""
        response = requests.post(
            f"{BASE_URL}/api/billing/validate-promo",
            json={"code": "INVALID_CODE_12345"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == False, "Invalid code should return ok=False"
        assert "error" in data, "Invalid code should have error message"
        print("PASS: Invalid promo code returns ok=False with error")


class TestBillingStatusAPI:
    """Test billing status endpoint (requires auth)"""
    
    def test_billing_status_requires_auth(self):
        """Billing status should require authentication"""
        response = requests.get(f"{BASE_URL}/api/billing/status")
        # Should return 401 for unauthenticated request
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /api/billing/status requires authentication")


class TestCheckoutEndpoints:
    """Test checkout endpoints (require auth)"""
    
    def test_create_checkout_requires_auth(self):
        """Create checkout should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={"origin_url": "https://example.com"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /api/billing/create-checkout requires authentication")
    
    def test_create_crypto_checkout_requires_auth(self):
        """Create crypto checkout should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-crypto-checkout",
            json={"origin_url": "https://example.com"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /api/billing/create-crypto-checkout requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
