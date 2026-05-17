"""
Admin Billing API Tests — Sprint 1 Billing Operating System

Tests for:
- GET /api/admin/billing/overview — KPIs, charts, recent_payments, at_risk
- GET /api/admin/billing/subscribers — List users with subscription data
- GET /api/admin/billing/subscribers/{user_id} — Detailed user info
- GET /api/admin/billing/payments — Payment transactions list
- GET /api/admin/billing/subscriptions — Subscriptions list
- GET /api/admin/billing/events — Billing events log
- POST /api/admin/billing/access/{user_id}/grant — Grant access
- POST /api/admin/billing/access/{user_id}/revoke — Revoke access
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestAdminBillingOverview:
    """Test GET /api/admin/billing/overview endpoint"""
    
    def test_overview_returns_200(self):
        """Overview endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Overview endpoint returns 200")
    
    def test_overview_has_kpis(self):
        """Overview should contain KPIs object with required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        data = response.json()
        
        assert "ok" in data and data["ok"] == True
        assert "kpis" in data, "Response missing 'kpis' field"
        
        kpis = data["kpis"]
        required_kpi_fields = [
            "total_users", "active_subscribers", "free_users", "past_due",
            "canceled", "mrr", "arr_run_rate", "revenue_30d", 
            "failed_payments_7d", "conversion_rate"
        ]
        for field in required_kpi_fields:
            assert field in kpis, f"KPIs missing '{field}' field"
        
        print(f"✓ KPIs present: total_users={kpis['total_users']}, active_subscribers={kpis['active_subscribers']}, mrr=${kpis['mrr']}")
    
    def test_overview_has_charts(self):
        """Overview should contain charts object with required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        data = response.json()
        
        assert "charts" in data, "Response missing 'charts' field"
        charts = data["charts"]
        
        assert "revenue_daily" in charts, "Charts missing 'revenue_daily'"
        assert "plan_distribution" in charts, "Charts missing 'plan_distribution'"
        assert "payment_methods" in charts, "Charts missing 'payment_methods'"
        
        # revenue_daily should be a list of 30 days
        assert isinstance(charts["revenue_daily"], list)
        assert len(charts["revenue_daily"]) == 30, f"Expected 30 days, got {len(charts['revenue_daily'])}"
        
        print(f"✓ Charts present: revenue_daily ({len(charts['revenue_daily'])} days), plan_distribution, payment_methods")
    
    def test_overview_has_recent_payments(self):
        """Overview should contain recent_payments list"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        data = response.json()
        
        assert "recent_payments" in data, "Response missing 'recent_payments' field"
        assert isinstance(data["recent_payments"], list)
        print(f"✓ Recent payments: {len(data['recent_payments'])} items")
    
    def test_overview_has_at_risk(self):
        """Overview should contain at_risk list"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        data = response.json()
        
        assert "at_risk" in data, "Response missing 'at_risk' field"
        assert isinstance(data["at_risk"], list)
        print(f"✓ At-risk subscriptions: {len(data['at_risk'])} items")


class TestAdminBillingSubscribers:
    """Test GET /api/admin/billing/subscribers endpoint"""
    
    def test_subscribers_returns_200(self):
        """Subscribers endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Subscribers endpoint returns 200")
    
    def test_subscribers_has_list(self):
        """Subscribers should return list with total count"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers")
        data = response.json()
        
        assert "ok" in data and data["ok"] == True
        assert "total" in data, "Response missing 'total' field"
        assert "subscribers" in data, "Response missing 'subscribers' field"
        assert isinstance(data["subscribers"], list)
        
        print(f"✓ Subscribers: {data['total']} total, {len(data['subscribers'])} returned")
    
    def test_subscribers_filter_active(self):
        """Subscribers should support status=active filter"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers?status=active")
        assert response.status_code == 200
        data = response.json()
        assert "subscribers" in data
        print(f"✓ Active filter: {len(data['subscribers'])} subscribers")
    
    def test_subscribers_filter_free(self):
        """Subscribers should support status=free filter"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers?status=free")
        assert response.status_code == 200
        data = response.json()
        assert "subscribers" in data
        print(f"✓ Free filter: {len(data['subscribers'])} subscribers")
    
    def test_subscribers_search(self):
        """Subscribers should support search parameter"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers?search=test")
        assert response.status_code == 200
        data = response.json()
        assert "subscribers" in data
        print(f"✓ Search 'test': {len(data['subscribers'])} results")
    
    def test_subscriber_has_required_fields(self):
        """Each subscriber should have required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers?limit=5")
        data = response.json()
        
        if len(data["subscribers"]) > 0:
            sub = data["subscribers"][0]
            required_fields = ["user_id", "email", "plan_status"]
            for field in required_fields:
                assert field in sub, f"Subscriber missing '{field}' field"
            print(f"✓ Subscriber fields present: user_id, email, plan_status")
        else:
            print("⚠ No subscribers to validate fields")


class TestAdminBillingSubscriberDetail:
    """Test GET /api/admin/billing/subscribers/{user_id} endpoint"""
    
    @pytest.fixture
    def user_id(self):
        """Get a user_id from subscribers list"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers?limit=1")
        data = response.json()
        if data.get("subscribers") and len(data["subscribers"]) > 0:
            return data["subscribers"][0]["user_id"]
        pytest.skip("No users available for detail test")
    
    def test_subscriber_detail_returns_200(self, user_id):
        """Subscriber detail should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers/{user_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Subscriber detail for {user_id} returns 200")
    
    def test_subscriber_detail_has_user(self, user_id):
        """Subscriber detail should contain user object"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers/{user_id}")
        data = response.json()
        
        assert "ok" in data and data["ok"] == True
        assert "user" in data, "Response missing 'user' field"
        assert data["user"]["user_id"] == user_id
        print(f"✓ User data present for {user_id}")
    
    def test_subscriber_detail_has_payments(self, user_id):
        """Subscriber detail should contain payments list"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers/{user_id}")
        data = response.json()
        
        assert "payments" in data, "Response missing 'payments' field"
        assert isinstance(data["payments"], list)
        print(f"✓ Payments list: {len(data['payments'])} items")
    
    def test_subscriber_detail_has_events(self, user_id):
        """Subscriber detail should contain events list"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers/{user_id}")
        data = response.json()
        
        assert "events" in data, "Response missing 'events' field"
        assert isinstance(data["events"], list)
        print(f"✓ Events list: {len(data['events'])} items")
    
    def test_subscriber_detail_has_access(self, user_id):
        """Subscriber detail should contain access object"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers/{user_id}")
        data = response.json()
        
        assert "access" in data, "Response missing 'access' field"
        access = data["access"]
        assert "has_access" in access
        assert "plan_status" in access
        print(f"✓ Access state: has_access={access['has_access']}, plan_status={access['plan_status']}")
    
    def test_subscriber_detail_404_for_invalid_user(self):
        """Subscriber detail should return 404 for invalid user_id"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers/invalid_user_id_12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Returns 404 for invalid user_id")


class TestAdminBillingPayments:
    """Test GET /api/admin/billing/payments endpoint"""
    
    def test_payments_returns_200(self):
        """Payments endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/payments")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Payments endpoint returns 200")
    
    def test_payments_has_list(self):
        """Payments should return list with total count"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/payments")
        data = response.json()
        
        assert "ok" in data and data["ok"] == True
        assert "total" in data, "Response missing 'total' field"
        assert "payments" in data, "Response missing 'payments' field"
        assert isinstance(data["payments"], list)
        
        print(f"✓ Payments: {data['total']} total, {len(data['payments'])} returned")
    
    def test_payments_filter_paid(self):
        """Payments should support status=paid filter"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/payments?status=paid")
        assert response.status_code == 200
        data = response.json()
        assert "payments" in data
        print(f"✓ Paid filter: {len(data['payments'])} payments")
    
    def test_payments_filter_failed(self):
        """Payments should support status=failed filter"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/payments?status=failed")
        assert response.status_code == 200
        data = response.json()
        assert "payments" in data
        print(f"✓ Failed filter: {len(data['payments'])} payments")
    
    def test_payments_filter_method_card(self):
        """Payments should support method=card filter"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/payments?method=card")
        assert response.status_code == 200
        data = response.json()
        assert "payments" in data
        print(f"✓ Card method filter: {len(data['payments'])} payments")
    
    def test_payments_filter_method_crypto(self):
        """Payments should support method=crypto filter"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/payments?method=crypto")
        assert response.status_code == 200
        data = response.json()
        assert "payments" in data
        print(f"✓ Crypto method filter: {len(data['payments'])} payments")


class TestAdminBillingSubscriptions:
    """Test GET /api/admin/billing/subscriptions endpoint"""
    
    def test_subscriptions_returns_200(self):
        """Subscriptions endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscriptions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Subscriptions endpoint returns 200")
    
    def test_subscriptions_has_list(self):
        """Subscriptions should return list with total count"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscriptions")
        data = response.json()
        
        assert "ok" in data and data["ok"] == True
        assert "total" in data, "Response missing 'total' field"
        assert "subscriptions" in data, "Response missing 'subscriptions' field"
        assert isinstance(data["subscriptions"], list)
        
        print(f"✓ Subscriptions: {data['total']} total, {len(data['subscriptions'])} returned")
    
    def test_subscriptions_filter_active(self):
        """Subscriptions should support status=active filter"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscriptions?status=active")
        assert response.status_code == 200
        data = response.json()
        assert "subscriptions" in data
        print(f"✓ Active filter: {len(data['subscriptions'])} subscriptions")
    
    def test_subscriptions_filter_canceled(self):
        """Subscriptions should support status=canceled filter"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscriptions?status=canceled")
        assert response.status_code == 200
        data = response.json()
        assert "subscriptions" in data
        print(f"✓ Canceled filter: {len(data['subscriptions'])} subscriptions")


class TestAdminBillingEvents:
    """Test GET /api/admin/billing/events endpoint"""
    
    def test_events_returns_200(self):
        """Events endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/events")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Events endpoint returns 200")
    
    def test_events_has_list(self):
        """Events should return list with total count"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/events")
        data = response.json()
        
        assert "ok" in data and data["ok"] == True
        assert "total" in data, "Response missing 'total' field"
        assert "events" in data, "Response missing 'events' field"
        assert isinstance(data["events"], list)
        
        print(f"✓ Events: {data['total']} total, {len(data['events'])} returned")


class TestAdminBillingAccessControl:
    """Test POST /api/admin/billing/access/{user_id}/grant and /revoke endpoints"""
    
    @pytest.fixture
    def user_id(self):
        """Get a user_id from subscribers list"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers?limit=1")
        data = response.json()
        if data.get("subscribers") and len(data["subscribers"]) > 0:
            return data["subscribers"][0]["user_id"]
        pytest.skip("No users available for access control test")
    
    def test_grant_access_returns_200(self, user_id):
        """Grant access should return 200 OK"""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/access/{user_id}/grant",
            json={"reason": "TEST_grant_access", "days": 7}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Grant access for {user_id} returns 200")
    
    def test_grant_access_updates_user(self, user_id):
        """Grant access should update user's plan_status"""
        # Grant access
        requests.post(
            f"{BASE_URL}/api/admin/billing/access/{user_id}/grant",
            json={"reason": "TEST_grant_verify", "days": 7}
        )
        
        # Verify via subscriber detail
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers/{user_id}")
        data = response.json()
        
        assert data["access"]["has_access"] == True
        assert data["access"]["override_status"] == "granted"
        print(f"✓ User {user_id} access granted and verified")
    
    def test_grant_access_logs_event(self, user_id):
        """Grant access should log billing_event"""
        # Grant access
        requests.post(
            f"{BASE_URL}/api/admin/billing/access/{user_id}/grant",
            json={"reason": "TEST_event_log", "days": 7}
        )
        
        # Check events
        response = requests.get(f"{BASE_URL}/api/admin/billing/events?limit=5")
        data = response.json()
        
        # Find the grant event
        grant_events = [e for e in data["events"] if e.get("type") == "access_granted" and e.get("user_id") == user_id]
        assert len(grant_events) > 0, "Grant event not found in billing_events"
        print(f"✓ Grant event logged for {user_id}")
    
    def test_revoke_access_returns_200(self, user_id):
        """Revoke access should return 200 OK"""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/access/{user_id}/revoke",
            json={"reason": "TEST_revoke_access"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Revoke access for {user_id} returns 200")
    
    def test_revoke_access_updates_user(self, user_id):
        """Revoke access should update user's plan_status"""
        # Revoke access
        requests.post(
            f"{BASE_URL}/api/admin/billing/access/{user_id}/revoke",
            json={"reason": "TEST_revoke_verify"}
        )
        
        # Verify via subscriber detail
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers/{user_id}")
        data = response.json()
        
        assert data["access"]["has_access"] == False
        assert data["access"]["override_status"] == "revoked"
        print(f"✓ User {user_id} access revoked and verified")
    
    def test_revoke_access_logs_event(self, user_id):
        """Revoke access should log billing_event"""
        # Revoke access
        requests.post(
            f"{BASE_URL}/api/admin/billing/access/{user_id}/revoke",
            json={"reason": "TEST_revoke_event_log"}
        )
        
        # Check events
        response = requests.get(f"{BASE_URL}/api/admin/billing/events?limit=5")
        data = response.json()
        
        # Find the revoke event
        revoke_events = [e for e in data["events"] if e.get("type") == "access_revoked" and e.get("user_id") == user_id]
        assert len(revoke_events) > 0, "Revoke event not found in billing_events"
        print(f"✓ Revoke event logged for {user_id}")
    
    def test_grant_access_404_for_invalid_user(self):
        """Grant access should return 404 for invalid user_id"""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/access/invalid_user_id_12345/grant",
            json={"reason": "TEST_invalid", "days": 7}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Grant returns 404 for invalid user_id")
    
    def test_revoke_access_404_for_invalid_user(self):
        """Revoke access should return 404 for invalid user_id"""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/access/invalid_user_id_12345/revoke",
            json={"reason": "TEST_invalid"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Revoke returns 404 for invalid user_id")


class TestBillingWebhookLogging:
    """Test POST /api/billing/webhook logs events to billing_events"""
    
    def test_webhook_returns_200(self):
        """Webhook endpoint should return 200 OK"""
        response = requests.post(
            f"{BASE_URL}/api/billing/webhook",
            json={"type": "test.event", "data": {"object": {}}}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Webhook endpoint returns 200")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
