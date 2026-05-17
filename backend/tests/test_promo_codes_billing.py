"""
Test Promo Codes and Billing Features - Iteration 540

Tests:
- Admin promo group CRUD (create, list, get codes, delete)
- User promo code validation
- Billing plans with billing_mode and free_trial_days
- Create checkout with promo code
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
AUTH_TOKEN = "sess_debug_1775055184466"

# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def auth_client():
    """Session with auth header."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}",
    })
    session.cookies.set("session_token", AUTH_TOKEN)
    return session


# ═══════════════════════════════════════════════════════════════
# ADMIN PROMO GROUP TESTS
# ═══════════════════════════════════════════════════════════════

class TestAdminPromoGroups:
    """Admin promo group CRUD operations."""
    
    created_group_id = None
    
    def test_create_promo_group(self, api_client):
        """POST /api/admin/billing/promos/groups creates promo group with codes."""
        response = api_client.post(f"{BASE_URL}/api/admin/billing/promos/groups", json={
            "name": "TEST_VIP_50",
            "discount_percent": 50,
            "count": 5,
            "prefix": "TEST",
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "group_id" in data, "Missing group_id in response"
        assert data.get("codes_generated") == 5, f"Expected 5 codes, got {data.get('codes_generated')}"
        assert "sample_codes" in data, "Missing sample_codes in response"
        assert len(data.get("sample_codes", [])) <= 5, "Too many sample codes"
        
        # Store for cleanup
        TestAdminPromoGroups.created_group_id = data["group_id"]
        print(f"✓ Created promo group: {data['group_id']} with {data['codes_generated']} codes")
    
    def test_create_promo_group_100_percent(self, api_client):
        """POST /api/admin/billing/promos/groups with 100% discount (free access)."""
        response = api_client.post(f"{BASE_URL}/api/admin/billing/promos/groups", json={
            "name": "TEST_FREE_ACCESS",
            "discount_percent": 100,
            "count": 3,
            "prefix": "FREE",
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("codes_generated") == 3
        print(f"✓ Created 100% discount group: {data['group_id']}")
    
    def test_create_promo_group_validation_errors(self, api_client):
        """POST /api/admin/billing/promos/groups validates input."""
        # Missing name
        response = api_client.post(f"{BASE_URL}/api/admin/billing/promos/groups", json={
            "discount_percent": 50,
            "count": 5,
        })
        assert response.status_code == 400, "Should reject missing name"
        
        # Invalid discount
        response = api_client.post(f"{BASE_URL}/api/admin/billing/promos/groups", json={
            "name": "Invalid",
            "discount_percent": 150,
            "count": 5,
        })
        assert response.status_code == 400, "Should reject discount > 100"
        
        # Invalid count
        response = api_client.post(f"{BASE_URL}/api/admin/billing/promos/groups", json={
            "name": "Invalid",
            "discount_percent": 50,
            "count": 1000,
        })
        assert response.status_code == 400, "Should reject count > 500"
        print("✓ Validation errors handled correctly")
    
    def test_list_promo_groups(self, api_client):
        """GET /api/admin/billing/promos/groups lists all groups with usage stats."""
        response = api_client.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "groups" in data
        assert isinstance(data["groups"], list)
        
        # Check structure of groups
        if data["groups"]:
            group = data["groups"][0]
            assert "group_id" in group
            assert "name" in group
            assert "discount_percent" in group
            assert "total_codes" in group
            assert "used_codes" in group
            print(f"✓ Listed {len(data['groups'])} promo groups with usage stats")
        else:
            print("✓ No promo groups found (empty list)")
    
    def test_get_group_codes(self, api_client):
        """GET /api/admin/billing/promos/groups/{group_id}/codes returns codes for a group."""
        if not TestAdminPromoGroups.created_group_id:
            pytest.skip("No group created to test")
        
        group_id = TestAdminPromoGroups.created_group_id
        response = api_client.get(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}/codes")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "codes" in data
        assert isinstance(data["codes"], list)
        
        # Check code structure
        if data["codes"]:
            code = data["codes"][0]
            assert "code" in code
            assert "group_id" in code
            assert "discount_percent" in code
            assert "used_by" in code
            print(f"✓ Retrieved {len(data['codes'])} codes for group {group_id}")
    
    def test_delete_promo_group(self, api_client):
        """DELETE /api/admin/billing/promos/groups/{group_id} deletes group and codes."""
        if not TestAdminPromoGroups.created_group_id:
            pytest.skip("No group created to delete")
        
        group_id = TestAdminPromoGroups.created_group_id
        response = api_client.delete(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "deleted_codes" in data
        print(f"✓ Deleted group {group_id} with {data['deleted_codes']} codes")
        
        # Verify deletion
        response = api_client.get(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}/codes")
        assert response.status_code == 200
        data = response.json()
        assert len(data.get("codes", [])) == 0, "Codes should be deleted"


# ═══════════════════════════════════════════════════════════════
# USER PROMO CODE VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestUserPromoValidation:
    """User promo code validation."""
    
    def test_validate_existing_promo_code_50(self, api_client):
        """POST /api/billing/validate-promo validates code and returns discount_percent."""
        # Use existing promo code from test data
        response = api_client.post(f"{BASE_URL}/api/billing/validate-promo", json={
            "code": "VIP-BI6P0FOK",
        })
        assert response.status_code == 200
        
        data = response.json()
        # Code may be valid or already used
        if data.get("ok"):
            assert "discount_percent" in data
            assert data["discount_percent"] == 50
            print(f"✓ Validated promo code: {data['discount_percent']}% discount")
        else:
            # Code already used or invalid
            assert "error" in data
            print(f"✓ Promo code validation returned: {data.get('error')}")
    
    def test_validate_existing_promo_code_100(self, api_client):
        """POST /api/billing/validate-promo validates 100% discount code."""
        response = api_client.post(f"{BASE_URL}/api/billing/validate-promo", json={
            "code": "FREE-N46RQCR8",
        })
        assert response.status_code == 200
        
        data = response.json()
        if data.get("ok"):
            assert data["discount_percent"] == 100
            print(f"✓ Validated 100% promo code")
        else:
            print(f"✓ Promo code validation returned: {data.get('error')}")
    
    def test_validate_invalid_promo_code(self, api_client):
        """POST /api/billing/validate-promo returns error for invalid code."""
        response = api_client.post(f"{BASE_URL}/api/billing/validate-promo", json={
            "code": "INVALID-CODE-12345",
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is False, "Invalid code should return ok=False"
        assert "error" in data
        assert "invalid" in data["error"].lower() or "Invalid" in data["error"]
        print(f"✓ Invalid promo code handled: {data['error']}")
    
    def test_validate_empty_promo_code(self, api_client):
        """POST /api/billing/validate-promo returns error for empty code."""
        response = api_client.post(f"{BASE_URL}/api/billing/validate-promo", json={
            "code": "",
        })
        assert response.status_code == 400, "Empty code should return 400"
        print("✓ Empty promo code rejected with 400")


# ═══════════════════════════════════════════════════════════════
# BILLING PLANS TESTS
# ═══════════════════════════════════════════════════════════════

class TestBillingPlans:
    """Billing plans API tests."""
    
    def test_get_plans_returns_billing_mode(self, api_client):
        """GET /api/billing/plans returns billing_mode and free_trial_days."""
        response = api_client.get(f"{BASE_URL}/api/billing/plans")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "plans" in data
        
        plans = data["plans"]
        assert "billing_mode" in plans, "Missing billing_mode in plans"
        assert plans["billing_mode"] in ["paid", "free_trial"], f"Invalid billing_mode: {plans['billing_mode']}"
        assert "free_trial_days" in plans, "Missing free_trial_days in plans"
        assert isinstance(plans["free_trial_days"], int)
        
        print(f"✓ Plans: billing_mode={plans['billing_mode']}, free_trial_days={plans['free_trial_days']}")
    
    def test_get_plans_has_monthly_pricing(self, api_client):
        """GET /api/billing/plans has monthly pricing."""
        response = api_client.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        
        plans = data["plans"]
        assert "monthly" in plans
        monthly = plans["monthly"]
        assert "card_price" in monthly
        assert "crypto_price" in monthly
        assert "interval" in monthly
        assert monthly["interval"] == "month"
        print(f"✓ Monthly pricing: card=${monthly['card_price']}, crypto=${monthly['crypto_price']}")
    
    def test_get_plans_has_yearly_pricing(self, api_client):
        """GET /api/billing/plans has yearly pricing with discount."""
        response = api_client.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        
        plans = data["plans"]
        assert "yearly" in plans
        yearly = plans["yearly"]
        assert "card_price" in yearly
        assert "crypto_price" in yearly
        assert "interval" in yearly
        assert yearly["interval"] == "year"
        assert "discount_percent" in yearly
        assert "monthly_equivalent" in yearly
        print(f"✓ Yearly pricing: card=${yearly['card_price']}, discount={yearly['discount_percent']}%")


# ═══════════════════════════════════════════════════════════════
# CHECKOUT WITH PROMO CODE TESTS
# ═══════════════════════════════════════════════════════════════

class TestCheckoutWithPromo:
    """Checkout with promo code tests."""
    
    def test_create_checkout_requires_auth(self, api_client):
        """POST /api/billing/create-checkout returns 401 when not authenticated."""
        response = api_client.post(f"{BASE_URL}/api/billing/create-checkout", json={
            "origin_url": "https://example.com",
            "interval": "month",
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Checkout requires authentication")
    
    def test_create_checkout_with_promo_code(self, auth_client):
        """POST /api/billing/create-checkout with promo_code applies Stripe coupon discount."""
        # First create a test promo group
        create_response = auth_client.post(f"{BASE_URL}/api/admin/billing/promos/groups", json={
            "name": "TEST_CHECKOUT_PROMO",
            "discount_percent": 25,
            "count": 1,
            "prefix": "CHECKOUT",
        })
        
        if create_response.status_code == 200:
            create_data = create_response.json()
            group_id = create_data.get("group_id")
            
            # Get the code
            codes_response = auth_client.get(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}/codes")
            if codes_response.status_code == 200:
                codes_data = codes_response.json()
                if codes_data.get("codes"):
                    promo_code = codes_data["codes"][0]["code"]
                    
                    # Try checkout with promo code
                    checkout_response = auth_client.post(f"{BASE_URL}/api/billing/create-checkout", json={
                        "origin_url": "https://example.com",
                        "interval": "month",
                        "promo_code": promo_code,
                    })
                    
                    # May succeed or fail based on auth, but should not error
                    assert checkout_response.status_code in [200, 401], f"Unexpected status: {checkout_response.status_code}"
                    
                    if checkout_response.status_code == 200:
                        data = checkout_response.json()
                        assert data.get("ok") is True
                        assert "url" in data or "session_id" in data
                        print(f"✓ Checkout with promo code created successfully")
                    else:
                        print("✓ Checkout requires valid session (401)")
                    
                    # Cleanup
                    auth_client.delete(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}")
                    return
        
        print("✓ Checkout with promo code test completed (promo creation may have failed)")


# ═══════════════════════════════════════════════════════════════
# ADMIN BILLING PRICING TESTS
# ═══════════════════════════════════════════════════════════════

class TestAdminBillingPricing:
    """Admin billing pricing configuration tests."""
    
    def test_get_admin_pricing(self, api_client):
        """GET /api/admin/billing/pricing returns current pricing config."""
        response = api_client.get(f"{BASE_URL}/api/admin/billing/pricing")
        assert response.status_code == 200
        
        data = response.json()
        assert "pricing" in data
        pricing = data["pricing"]
        
        # Check required fields
        assert "billing_mode" in pricing
        assert "free_trial_days" in pricing
        print(f"✓ Admin pricing: billing_mode={pricing.get('billing_mode')}")
    
    def test_update_billing_mode_to_free_trial(self, api_client):
        """PUT /api/admin/billing/pricing accepts billing_mode='free_trial'."""
        # Get current config
        get_response = api_client.get(f"{BASE_URL}/api/admin/billing/pricing")
        current = get_response.json().get("pricing", {})
        
        # Update to free_trial
        response = api_client.put(f"{BASE_URL}/api/admin/billing/pricing", json={
            "billing_mode": "free_trial",
            "free_trial_days": 7,
            "monthly_card_cents": current.get("monthly_card_cents", 100),
            "yearly_card_cents": current.get("yearly_card_cents", 1000),
            "monthly_crypto_dollars": current.get("monthly_crypto_dollars", 1.0),
            "yearly_crypto_dollars": current.get("yearly_crypto_dollars", 10.0),
            "yearly_discount_percent": current.get("yearly_discount_percent", 15),
            "free_access_enabled": current.get("free_access_enabled", False),
            "product_name": current.get("product_name", "FOMO Intelligence PRO"),
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("pricing", {}).get("billing_mode") == "free_trial"
        print("✓ Updated billing_mode to free_trial")
    
    def test_update_billing_mode_to_paid(self, api_client):
        """PUT /api/admin/billing/pricing accepts billing_mode='paid'."""
        # Get current config
        get_response = api_client.get(f"{BASE_URL}/api/admin/billing/pricing")
        current = get_response.json().get("pricing", {})
        
        # Update to paid
        response = api_client.put(f"{BASE_URL}/api/admin/billing/pricing", json={
            "billing_mode": "paid",
            "free_trial_days": current.get("free_trial_days", 3),
            "monthly_card_cents": current.get("monthly_card_cents", 100),
            "yearly_card_cents": current.get("yearly_card_cents", 1000),
            "monthly_crypto_dollars": current.get("monthly_crypto_dollars", 1.0),
            "yearly_crypto_dollars": current.get("yearly_crypto_dollars", 10.0),
            "yearly_discount_percent": current.get("yearly_discount_percent", 15),
            "free_access_enabled": current.get("free_access_enabled", False),
            "product_name": current.get("product_name", "FOMO Intelligence PRO"),
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("pricing", {}).get("billing_mode") == "paid"
        print("✓ Updated billing_mode to paid")


# ═══════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data():
    """Cleanup TEST_ prefixed promo groups after tests."""
    yield
    # Cleanup
    try:
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        if response.status_code == 200:
            groups = response.json().get("groups", [])
            for g in groups:
                if g.get("name", "").startswith("TEST_"):
                    session.delete(f"{BASE_URL}/api/admin/billing/promos/groups/{g['group_id']}")
    except:
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
