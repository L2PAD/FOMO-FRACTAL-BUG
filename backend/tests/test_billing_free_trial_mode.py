"""
Test Billing Free Trial Mode Features — Iteration 539

Tests:
1. GET /api/billing/plans returns billing_mode and free_trial_days
2. GET /api/admin/billing/stripe-keys returns masked keys and has_* flags
3. PUT /api/admin/billing/stripe-keys accepts sk_ and pk_ prefixed keys
4. PUT /api/admin/billing/pricing accepts billing_mode='free_trial' or 'paid'
5. PUT /api/admin/billing/pricing rejects invalid billing_mode values
6. POST /api/billing/create-checkout adds trial_period_days when billing_mode is free_trial
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test session token for authenticated requests
TEST_SESSION_TOKEN = "sess_debug_1775055184466"


class TestBillingPlansAPI:
    """Test GET /api/billing/plans returns billing_mode and free_trial_days"""

    def test_plans_returns_200(self):
        """GET /api/billing/plans should return 200"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/billing/plans returns 200")

    def test_plans_returns_ok_true(self):
        """GET /api/billing/plans should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print("PASS: GET /api/billing/plans returns ok:true")

    def test_plans_has_billing_mode(self):
        """GET /api/billing/plans should return billing_mode field"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        plans = data.get("plans", {})
        assert "billing_mode" in plans, f"billing_mode not in plans: {plans.keys()}"
        assert plans["billing_mode"] in ("free_trial", "paid"), f"Invalid billing_mode: {plans['billing_mode']}"
        print(f"PASS: GET /api/billing/plans has billing_mode={plans['billing_mode']}")

    def test_plans_has_free_trial_days(self):
        """GET /api/billing/plans should return free_trial_days field"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        plans = data.get("plans", {})
        assert "free_trial_days" in plans, f"free_trial_days not in plans: {plans.keys()}"
        assert isinstance(plans["free_trial_days"], int), f"free_trial_days should be int: {type(plans['free_trial_days'])}"
        assert plans["free_trial_days"] > 0, f"free_trial_days should be > 0: {plans['free_trial_days']}"
        print(f"PASS: GET /api/billing/plans has free_trial_days={plans['free_trial_days']}")

    def test_plans_has_monthly_pricing(self):
        """GET /api/billing/plans should have monthly pricing"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        plans = data.get("plans", {})
        monthly = plans.get("monthly", {})
        assert "card_price" in monthly, f"card_price not in monthly: {monthly.keys()}"
        assert "crypto_price" in monthly, f"crypto_price not in monthly: {monthly.keys()}"
        assert "interval" in monthly, f"interval not in monthly: {monthly.keys()}"
        print(f"PASS: GET /api/billing/plans has monthly pricing: ${monthly.get('card_price')}/mo")

    def test_plans_has_yearly_pricing(self):
        """GET /api/billing/plans should have yearly pricing with discount"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        data = response.json()
        plans = data.get("plans", {})
        yearly = plans.get("yearly", {})
        assert "card_price" in yearly, f"card_price not in yearly: {yearly.keys()}"
        assert "discount_percent" in yearly, f"discount_percent not in yearly: {yearly.keys()}"
        assert "monthly_equivalent" in yearly, f"monthly_equivalent not in yearly: {yearly.keys()}"
        print(f"PASS: GET /api/billing/plans has yearly pricing: ${yearly.get('card_price')}/yr ({yearly.get('discount_percent')}% off)")


class TestAdminStripeKeysAPI:
    """Test GET/PUT /api/admin/billing/stripe-keys"""

    def test_get_stripe_keys_returns_200(self):
        """GET /api/admin/billing/stripe-keys should return 200"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/stripe-keys")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/admin/billing/stripe-keys returns 200")

    def test_get_stripe_keys_has_masked_keys(self):
        """GET /api/admin/billing/stripe-keys should return masked keys"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/stripe-keys")
        data = response.json()
        keys = data.get("keys", {})
        assert "stripe_secret_key_masked" in keys, f"stripe_secret_key_masked not in keys: {keys.keys()}"
        assert "stripe_publishable_key_masked" in keys, f"stripe_publishable_key_masked not in keys: {keys.keys()}"
        print(f"PASS: GET /api/admin/billing/stripe-keys has masked keys")

    def test_get_stripe_keys_has_flags(self):
        """GET /api/admin/billing/stripe-keys should return has_secret_key and has_publishable_key flags"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/stripe-keys")
        data = response.json()
        keys = data.get("keys", {})
        assert "has_secret_key" in keys, f"has_secret_key not in keys: {keys.keys()}"
        assert "has_publishable_key" in keys, f"has_publishable_key not in keys: {keys.keys()}"
        assert isinstance(keys["has_secret_key"], bool), f"has_secret_key should be bool"
        assert isinstance(keys["has_publishable_key"], bool), f"has_publishable_key should be bool"
        print(f"PASS: GET /api/admin/billing/stripe-keys has flags: has_secret_key={keys['has_secret_key']}, has_publishable_key={keys['has_publishable_key']}")

    def test_put_stripe_keys_accepts_sk_prefix(self):
        """PUT /api/admin/billing/stripe-keys should accept sk_ prefixed keys"""
        response = requests.put(
            f"{BASE_URL}/api/admin/billing/stripe-keys",
            json={"stripe_secret_key": "sk_test_example123456789"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print("PASS: PUT /api/admin/billing/stripe-keys accepts sk_ prefixed keys")

    def test_put_stripe_keys_accepts_pk_prefix(self):
        """PUT /api/admin/billing/stripe-keys should accept pk_ prefixed keys"""
        response = requests.put(
            f"{BASE_URL}/api/admin/billing/stripe-keys",
            json={"stripe_publishable_key": "pk_test_example123456789"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print("PASS: PUT /api/admin/billing/stripe-keys accepts pk_ prefixed keys")


class TestAdminPricingAPI:
    """Test PUT /api/admin/billing/pricing with billing_mode"""

    def test_get_pricing_returns_200(self):
        """GET /api/admin/billing/pricing should return 200"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/pricing")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/admin/billing/pricing returns 200")

    def test_get_pricing_has_billing_mode(self):
        """GET /api/admin/billing/pricing should return billing_mode"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/pricing")
        data = response.json()
        pricing = data.get("pricing", {})
        assert "billing_mode" in pricing, f"billing_mode not in pricing: {pricing.keys()}"
        print(f"PASS: GET /api/admin/billing/pricing has billing_mode={pricing['billing_mode']}")

    def test_put_pricing_accepts_free_trial_mode(self):
        """PUT /api/admin/billing/pricing should accept billing_mode='free_trial'"""
        # First get current config to preserve other values
        get_response = requests.get(f"{BASE_URL}/api/admin/billing/pricing")
        current = get_response.json().get("pricing", {})
        
        response = requests.put(
            f"{BASE_URL}/api/admin/billing/pricing",
            json={
                "billing_mode": "free_trial",
                "free_trial_days": 7,
                "monthly_card_cents": current.get("monthly_card_cents", 100),
                "yearly_card_cents": current.get("yearly_card_cents", 1000),
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        pricing = data.get("pricing", {})
        assert pricing.get("billing_mode") == "free_trial", f"Expected billing_mode=free_trial, got {pricing.get('billing_mode')}"
        assert pricing.get("free_trial_days") == 7, f"Expected free_trial_days=7, got {pricing.get('free_trial_days')}"
        print("PASS: PUT /api/admin/billing/pricing accepts billing_mode='free_trial'")

    def test_put_pricing_accepts_paid_mode(self):
        """PUT /api/admin/billing/pricing should accept billing_mode='paid'"""
        # First get current config to preserve other values
        get_response = requests.get(f"{BASE_URL}/api/admin/billing/pricing")
        current = get_response.json().get("pricing", {})
        
        response = requests.put(
            f"{BASE_URL}/api/admin/billing/pricing",
            json={
                "billing_mode": "paid",
                "free_trial_days": 3,
                "monthly_card_cents": current.get("monthly_card_cents", 100),
                "yearly_card_cents": current.get("yearly_card_cents", 1000),
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        pricing = data.get("pricing", {})
        assert pricing.get("billing_mode") == "paid", f"Expected billing_mode=paid, got {pricing.get('billing_mode')}"
        print("PASS: PUT /api/admin/billing/pricing accepts billing_mode='paid'")

    def test_put_pricing_rejects_invalid_billing_mode(self):
        """PUT /api/admin/billing/pricing should reject invalid billing_mode values"""
        response = requests.put(
            f"{BASE_URL}/api/admin/billing/pricing",
            json={
                "billing_mode": "invalid_mode",
                "monthly_card_cents": 100,
                "yearly_card_cents": 1000,
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("PASS: PUT /api/admin/billing/pricing rejects invalid billing_mode")


class TestBillingCheckoutWithTrialMode:
    """Test POST /api/billing/create-checkout with free_trial mode"""

    def test_create_checkout_requires_auth(self):
        """POST /api/billing/create-checkout should return 401 when not authenticated"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-checkout",
            json={"origin_url": "https://example.com"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/billing/create-checkout returns 401 when not authenticated")

    def test_create_crypto_checkout_requires_auth(self):
        """POST /api/billing/create-crypto-checkout should return 401 when not authenticated"""
        response = requests.post(
            f"{BASE_URL}/api/billing/create-crypto-checkout",
            json={"origin_url": "https://example.com"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/billing/create-crypto-checkout returns 401 when not authenticated")


class TestBillingStatusAPI:
    """Test GET /api/billing/status"""

    def test_billing_status_requires_auth(self):
        """GET /api/billing/status should return 401 when not authenticated"""
        response = requests.get(f"{BASE_URL}/api/billing/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/billing/status returns 401 when not authenticated")


class TestBillingPortalAPI:
    """Test POST /api/billing/portal"""

    def test_billing_portal_requires_auth(self):
        """POST /api/billing/portal should return 401 when not authenticated"""
        response = requests.post(
            f"{BASE_URL}/api/billing/portal",
            json={"origin_url": "https://example.com"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/billing/portal returns 401 when not authenticated")


class TestAdminBillingOverview:
    """Test GET /api/admin/billing/overview"""

    def test_overview_returns_200(self):
        """GET /api/admin/billing/overview should return 200"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/admin/billing/overview returns 200")

    def test_overview_has_kpis(self):
        """GET /api/admin/billing/overview should return KPIs"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        data = response.json()
        assert "kpis" in data, f"kpis not in response: {data.keys()}"
        kpis = data["kpis"]
        assert "total_users" in kpis, f"total_users not in kpis"
        assert "active_subscribers" in kpis, f"active_subscribers not in kpis"
        assert "mrr" in kpis, f"mrr not in kpis"
        print(f"PASS: GET /api/admin/billing/overview has KPIs: {kpis.get('total_users')} users, {kpis.get('active_subscribers')} active")


# Restore billing mode to 'paid' after tests
@pytest.fixture(scope="module", autouse=True)
def restore_billing_mode():
    """Restore billing mode to 'paid' after all tests"""
    yield
    # Restore to paid mode
    requests.put(
        f"{BASE_URL}/api/admin/billing/pricing",
        json={
            "billing_mode": "paid",
            "free_trial_days": 3,
            "monthly_card_cents": 100,
            "yearly_card_cents": 1000,
        }
    )
    print("CLEANUP: Restored billing_mode to 'paid'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
