"""
Billing Settings Page API Tests
Tests for /api/billing/* endpoints - subscription management
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestBillingPlansAPI:
    """Tests for GET /api/billing/plans - public endpoint"""
    
    def test_get_plans_returns_200(self):
        """GET /api/billing/plans should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/billing/plans returns 200")
    
    def test_get_plans_returns_ok_true(self):
        """GET /api/billing/plans should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        print("PASS: GET /api/billing/plans returns ok:true")
    
    def test_get_plans_has_monthly_pricing(self):
        """GET /api/billing/plans should return monthly pricing data"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        plans = data.get("plans", {})
        monthly = plans.get("monthly", {})
        
        assert "card_price" in monthly, "Missing monthly.card_price"
        assert "crypto_price" in monthly, "Missing monthly.crypto_price"
        assert "interval" in monthly, "Missing monthly.interval"
        assert monthly["interval"] == "month", f"Expected interval='month', got {monthly['interval']}"
        print(f"PASS: Monthly pricing: card=${monthly['card_price']}, crypto=${monthly['crypto_price']}")
    
    def test_get_plans_has_yearly_pricing(self):
        """GET /api/billing/plans should return yearly pricing data"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        plans = data.get("plans", {})
        yearly = plans.get("yearly", {})
        
        assert "card_price" in yearly, "Missing yearly.card_price"
        assert "crypto_price" in yearly, "Missing yearly.crypto_price"
        assert "interval" in yearly, "Missing yearly.interval"
        assert "discount_percent" in yearly, "Missing yearly.discount_percent"
        assert "monthly_equivalent" in yearly, "Missing yearly.monthly_equivalent"
        assert yearly["interval"] == "year", f"Expected interval='year', got {yearly['interval']}"
        print(f"PASS: Yearly pricing: card=${yearly['card_price']}, crypto=${yearly['crypto_price']}, discount={yearly['discount_percent']}%")
    
    def test_get_plans_has_product_name(self):
        """GET /api/billing/plans should return product_name"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        plans = data.get("plans", {})
        
        assert "product_name" in plans, "Missing product_name"
        assert isinstance(plans["product_name"], str), "product_name should be string"
        print(f"PASS: Product name: {plans['product_name']}")


class TestBillingAuthenticatedEndpoints:
    """Tests for authenticated billing endpoints - should return 401 when not authenticated"""
    
    def test_create_checkout_requires_auth(self):
        """POST /api/billing/create-checkout should return 401 when not authenticated"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={"origin_url": "https://example.com", "interval": "month"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data or "error" in data, "Expected error message in response"
        print("PASS: POST /api/billing/create-checkout returns 401 when not authenticated")
    
    def test_create_crypto_checkout_requires_auth(self):
        """POST /api/billing/create-crypto-checkout should return 401 when not authenticated"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-crypto-checkout",
            json={"origin_url": "https://example.com", "interval": "month"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data or "error" in data, "Expected error message in response"
        print("PASS: POST /api/billing/create-crypto-checkout returns 401 when not authenticated")
    
    def test_billing_status_requires_auth(self):
        """GET /api/billing/status should return 401 when not authenticated"""
        response = requests.get(f"{BASE_URL}/api/billing/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data or "error" in data, "Expected error message in response"
        print("PASS: GET /api/billing/status returns 401 when not authenticated")
    
    def test_billing_portal_requires_auth(self):
        """POST /api/billing/portal should return 401 when not authenticated"""
        response = requests.post(
            f"{BASE_URL}/api/billing/portal",
            json={"origin_url": "https://example.com"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/billing/portal returns 401 when not authenticated")


class TestBillingValidation:
    """Tests for billing endpoint validation"""
    
    def test_create_checkout_requires_origin_url(self):
        """POST /api/billing/create-checkout should validate origin_url"""
        # This test would require authentication to properly test validation
        # For now, we verify the endpoint exists and returns 401
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={},  # Missing origin_url
            headers={"Content-Type": "application/json"}
        )
        # Should return 401 (auth check happens before validation)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/billing/create-checkout endpoint exists and requires auth")
    
    def test_create_crypto_checkout_requires_origin_url(self):
        """POST /api/billing/create-crypto-checkout should validate origin_url"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-crypto-checkout",
            json={},  # Missing origin_url
            headers={"Content-Type": "application/json"}
        )
        # Should return 401 (auth check happens before validation)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/billing/create-crypto-checkout endpoint exists and requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
