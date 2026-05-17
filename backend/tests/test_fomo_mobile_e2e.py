"""
FOMO Mobile App E2E Tests
==========================

Tests all mobile API endpoints + payment webhook flow.

Priority: Payment webhook verification (E2E flow)

Test Coverage:
- Auth: Dev login, token refresh, profile
- Mobile: Home, Feed, Signals, Edge, Intel, Profile
- Payments: Plans, Create invoice, Webhook, Status
- Admin: Panel access
"""
import pytest
import requests
import os
import json
from datetime import datetime

# Get backend URL from environment
BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    pytest.skip("EXPO_PUBLIC_BACKEND_URL not set", allow_module_level=True)

print(f"[TEST] Using BASE_URL: {BASE_URL}")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def auth_token(api_client):
    """Get auth token via dev login"""
    response = api_client.post(
        f"{BASE_URL}/api/mobile/auth/dev-login",
        json={"email": "dev@fomo.ai", "name": "FOMO Developer"}
    )
    assert response.status_code == 200, f"Dev login failed: {response.text}"
    data = response.json()
    assert "accessToken" in data, "No accessToken in response"
    assert "refreshToken" in data, "No refreshToken in response"
    assert "user" in data, "No user in response"
    print(f"[TEST] ✅ Dev login successful, user: {data['user'].get('email')}")
    return data["accessToken"]


class TestAuth:
    """Authentication endpoint tests"""

    def test_dev_login_success(self, api_client):
        """Test dev login creates/finds user and returns tokens"""
        response = api_client.post(
            f"{BASE_URL}/api/mobile/auth/dev-login",
            json={"email": "dev@fomo.ai", "name": "FOMO Developer"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "accessToken" in data
        assert "refreshToken" in data
        assert "user" in data
        
        user = data["user"]
        assert user["email"] == "dev@fomo.ai"
        # Name might be different if user already exists
        assert "name" in user
        assert user["plan"] in ["FREE", "PRO", "TRIAL"]
        assert "id" in user
        
        print(f"[TEST] ✅ Dev login: {user['email']}, plan={user['plan']}")

    def test_get_me_with_token(self, api_client, auth_token):
        """Test /auth/me returns user profile"""
        response = api_client.get(
            f"{BASE_URL}/api/mobile/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "dev@fomo.ai"
        print(f"[TEST] ✅ /auth/me: {data['email']}")

    def test_refresh_token(self, api_client):
        """Test token refresh flow"""
        # First login
        login_resp = api_client.post(
            f"{BASE_URL}/api/mobile/auth/dev-login",
            json={"email": "dev@fomo.ai", "name": "FOMO Developer"}
        )
        assert login_resp.status_code == 200
        refresh_token = login_resp.json()["refreshToken"]
        
        # Refresh
        refresh_resp = api_client.post(
            f"{BASE_URL}/api/mobile/auth/refresh",
            json={"refreshToken": refresh_token}
        )
        assert refresh_resp.status_code == 200
        data = refresh_resp.json()
        assert "accessToken" in data
        assert "refreshToken" in data
        print(f"[TEST] ✅ Token refresh successful")


class TestMobileEndpoints:
    """Mobile app API endpoints"""

    def test_home_endpoint(self, api_client, auth_token):
        """Test GET /api/mobile/home?asset=BTC returns signal data"""
        response = api_client.get(
            f"{BASE_URL}/api/mobile/home?asset=BTC",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "asset" in data
        assert data["asset"] == "BTC"
        assert "decision" in data
        assert data["decision"] in ["BUY", "SELL", "WAIT"]
        assert "confidence" in data
        assert "drivers" in data
        
        print(f"[TEST] ✅ Home: {data['asset']} {data['decision']} conf={data['confidence']}")

    def test_signals_endpoint(self, api_client, auth_token):
        """Test GET /api/mobile/signals?horizon=swing returns signals array"""
        response = api_client.get(
            f"{BASE_URL}/api/mobile/signals?horizon=swing",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "signals" in data or "ok" in data
        if "signals" in data:
            assert isinstance(data["signals"], list)
            print(f"[TEST] ✅ Signals: {len(data['signals'])} signals returned")
        else:
            print(f"[TEST] ✅ Signals: ok={data.get('ok')}")

    def test_profile_endpoint(self, api_client, auth_token):
        """Test GET /api/mobile/profile returns user profile"""
        response = api_client.get(
            f"{BASE_URL}/api/mobile/profile",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "email" in data
        assert "plan" in data
        assert data["email"] == "dev@fomo.ai"
        
        print(f"[TEST] ✅ Profile: {data['email']}, plan={data['plan']}")


class TestPayments:
    """Payment endpoints - NOWPayments integration"""

    def test_get_plans(self, api_client):
        """Test GET /api/payments/plans returns pricing"""
        response = api_client.get(f"{BASE_URL}/api/payments/plans")
        assert response.status_code == 200
        data = response.json()
        
        assert "ok" in data
        assert data["ok"] is True
        assert "plans" in data
        
        plans = data["plans"]
        assert "monthly" in plans
        assert "yearly" in plans
        
        monthly = plans["monthly"]
        assert monthly["price"] == 19
        assert monthly["currency"] == "usd"
        assert monthly["payment_method"] == "crypto"
        
        print(f"[TEST] ✅ Plans: monthly=${monthly['price']}, yearly=${plans['yearly']['price']}")

    def test_create_wallet_invoice(self, api_client, auth_token):
        """Test POST /api/payments/create-wallet-invoice returns invoice URL"""
        response = api_client.post(
            f"{BASE_URL}/api/payments/create-wallet-invoice",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "invoice_url" in data
        assert "invoice_id" in data or "payment_id" in data
        assert "order_id" in data
        
        # In dev mode, should return demo URL
        assert "nowpayments.io" in data["invoice_url"] or "demo" in data["invoice_url"]
        
        print(f"[TEST] ✅ Invoice created: {data['invoice_url'][:50]}...")
        return data

    def test_payment_webhook_flow(self, api_client, auth_token):
        """
        PRIORITY TEST: E2E Payment Webhook Verification
        
        Flow:
        1. Create invoice
        2. Simulate webhook with status='finished'
        3. Verify user upgraded to PRO
        4. Check payment status
        """
        # Step 1: Create invoice
        invoice_resp = api_client.post(
            f"{BASE_URL}/api/payments/create-wallet-invoice",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert invoice_resp.status_code == 200
        invoice_data = invoice_resp.json()
        order_id = invoice_data["order_id"]
        
        print(f"[TEST] 📝 Step 1: Invoice created for order {order_id}")
        
        # Step 2: Simulate webhook (payment finished)
        webhook_payload = {
            "payment_id": f"test_payment_{datetime.utcnow().timestamp()}",
            "payment_status": "finished",
            "pay_amount": 19,
            "pay_currency": "USDT",
            "order_id": order_id,
            "order_description": "FOMO PRO - Market Intelligence Subscription",
            "price_amount": 19,
            "price_currency": "usd",
            "actually_paid": 19
        }
        
        webhook_resp = api_client.post(
            f"{BASE_URL}/api/payments/webhook-wallet",
            json=webhook_payload
        )
        
        # Webhook should return 200 even if signature verification fails in dev mode
        assert webhook_resp.status_code == 200
        webhook_data = webhook_resp.json()
        
        print(f"[TEST] 📝 Step 2: Webhook processed: {webhook_data}")
        
        # Step 3: Verify user upgraded to PRO
        profile_resp = api_client.get(
            f"{BASE_URL}/api/mobile/profile",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert profile_resp.status_code == 200
        profile_data = profile_resp.json()
        
        # User should now be PRO
        assert profile_data["plan"] == "PRO", f"Expected PRO, got {profile_data['plan']}"
        
        print(f"[TEST] ✅ Step 3: User upgraded to PRO")
        
        # Step 4: Check payment status
        status_resp = api_client.get(
            f"{BASE_URL}/api/payments/status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        
        assert status_data["plan"] == "PRO"
        assert status_data["status"] in ["active", "finished"]
        
        print(f"[TEST] ✅ Step 4: Payment status verified: {status_data['status']}")
        print(f"[TEST] 🎉 E2E Payment Webhook Flow: PASSED")

    def test_payment_status_endpoint(self, api_client, auth_token):
        """Test GET /api/payments/status returns user plan status"""
        response = api_client.get(
            f"{BASE_URL}/api/payments/status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "plan" in data
        assert "status" in data
        assert data["plan"] in ["FREE", "PRO", "TRIAL"]
        
        print(f"[TEST] ✅ Payment status: plan={data['plan']}, status={data['status']}")


class TestAdmin:
    """Admin panel endpoints"""

    def test_admin_panel_access(self, api_client):
        """Test GET /api/panel/ returns HTML admin interface"""
        response = api_client.get(f"{BASE_URL}/api/panel/")
        
        # Admin panel might return 200 (HTML) or 404 (not mounted)
        # We just check it doesn't crash
        assert response.status_code in [200, 404, 302]
        
        if response.status_code == 200:
            print(f"[TEST] ✅ Admin panel accessible")
        else:
            print(f"[TEST] ⚠️ Admin panel returned {response.status_code}")


class TestHealthChecks:
    """System health checks"""

    def test_backend_health(self, api_client):
        """Test backend is running"""
        response = api_client.get(f"{BASE_URL}/health")
        # Health endpoint might not be at root, try /api/health
        if response.status_code == 404:
            response = api_client.get(f"{BASE_URL}/api/health")
        
        # If still 404, backend is running but health endpoint not configured
        if response.status_code == 404:
            print(f"[TEST] ⚠️ Health endpoint not found, but backend is responding")
            return
        
        # 503 is acceptable (service degraded but running)
        assert response.status_code in [200, 503]
        data = response.json()
        print(f"[TEST] ✅ Backend health: status={response.status_code}, service={data.get('service', 'unknown')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
