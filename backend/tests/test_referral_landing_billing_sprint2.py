"""
Test Suite: Referral Landing Page + Sprint 2 Billing Admin Extensions
Iteration 548

Tests:
1. /ref/{valid_code} - Referral landing page validation
2. /ref/{invalid_code} - Invalid code handling
3. POST /api/billing/apply-referral - 401 for unauthenticated
4. POST /api/billing/validate-promo - Validates existing code
5. POST /api/admin/billing/refund - Process refund
6. GET /api/admin/billing/refunds - List all refunds
7. GET /api/admin/billing/overview - subscriber_growth chart (30 entries)
8. GET /api/admin/billing/overview - total_refunds and total_refunded in KPIs
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')

# Known valid referral code from the test data
VALID_REFERRAL_CODE = "REF-8SOXY4YI"
INVALID_REFERRAL_CODE = "INVALID-CODE-XYZ"


class TestReferralLandingValidation:
    """Tests for referral code validation endpoint"""
    
    def test_validate_promo_valid_code(self):
        """POST /api/billing/validate-promo validates existing code REF-8SOXY4YI"""
        response = requests.post(
            f"{BASE_URL}/api/billing/validate-promo",
            json={"code": VALID_REFERRAL_CODE},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=True, got {data}"
        assert "discount_percent" in data, f"Missing discount_percent in response: {data}"
        assert data.get("discount_percent") == 25, f"Expected 25% discount, got {data.get('discount_percent')}"
        print(f"✓ Valid code {VALID_REFERRAL_CODE} returns 25% discount from {data.get('group_name', 'unknown')} program")
    
    def test_validate_promo_invalid_code(self):
        """POST /api/billing/validate-promo returns ok=false for invalid code"""
        response = requests.post(
            f"{BASE_URL}/api/billing/validate-promo",
            json={"code": INVALID_REFERRAL_CODE},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") == False, f"Expected ok=False for invalid code, got {data}"
        print(f"✓ Invalid code {INVALID_REFERRAL_CODE} returns ok=false")
    
    def test_validate_promo_empty_code(self):
        """POST /api/billing/validate-promo handles empty code"""
        response = requests.post(
            f"{BASE_URL}/api/billing/validate-promo",
            json={"code": ""},
            headers={"Content-Type": "application/json"}
        )
        # Should return 200 with ok=false or 400
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            assert data.get("ok") == False, f"Expected ok=False for empty code"
        print(f"✓ Empty code handled correctly (status {response.status_code})")


class TestApplyReferralAuth:
    """Tests for apply-referral endpoint authentication"""
    
    def test_apply_referral_unauthenticated_returns_401(self):
        """POST /api/billing/apply-referral returns 401 for unauthenticated"""
        response = requests.post(
            f"{BASE_URL}/api/billing/apply-referral",
            json={"code": VALID_REFERRAL_CODE},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/billing/apply-referral returns 401 for unauthenticated")


class TestAdminRefundManagement:
    """Tests for admin refund management endpoints"""
    
    def test_process_refund_requires_user_id(self):
        """POST /api/admin/billing/refund requires user_id"""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/refund",
            json={"amount": 10.00, "reason": "Test refund"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400 for missing user_id, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/admin/billing/refund returns 400 when user_id missing")
    
    def test_process_refund_invalid_user_returns_404(self):
        """POST /api/admin/billing/refund returns 404 for non-existent user"""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/refund",
            json={"user_id": "nonexistent-user-id-xyz", "amount": 10.00, "reason": "Test refund"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 404, f"Expected 404 for non-existent user, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/admin/billing/refund returns 404 for non-existent user")
    
    def test_list_refunds(self):
        """GET /api/admin/billing/refunds lists all refunds"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/refunds")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=True, got {data}"
        assert "refunds" in data, f"Missing 'refunds' key in response: {data}"
        assert isinstance(data["refunds"], list), f"Expected refunds to be a list"
        print(f"✓ GET /api/admin/billing/refunds returns {len(data['refunds'])} refunds")


class TestBillingOverviewExtensions:
    """Tests for billing overview KPIs and charts"""
    
    def test_overview_has_subscriber_growth_chart(self):
        """GET /api/admin/billing/overview includes subscriber_growth chart with 30 entries"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=True, got {data}"
        
        # Check charts exist
        assert "charts" in data, f"Missing 'charts' key in response"
        charts = data["charts"]
        
        # Check subscriber_growth chart
        assert "subscriber_growth" in charts, f"Missing 'subscriber_growth' in charts: {charts.keys()}"
        subscriber_growth = charts["subscriber_growth"]
        assert isinstance(subscriber_growth, list), f"Expected subscriber_growth to be a list"
        assert len(subscriber_growth) == 30, f"Expected 30 entries in subscriber_growth, got {len(subscriber_growth)}"
        
        # Verify structure of each entry
        if subscriber_growth:
            entry = subscriber_growth[0]
            assert "date" in entry, f"Missing 'date' in subscriber_growth entry: {entry}"
            assert "subscribers" in entry, f"Missing 'subscribers' in subscriber_growth entry: {entry}"
        
        print(f"✓ GET /api/admin/billing/overview includes subscriber_growth chart with {len(subscriber_growth)} entries")
    
    def test_overview_has_revenue_daily_chart(self):
        """GET /api/admin/billing/overview includes revenue_daily chart with 30 entries"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        assert response.status_code == 200
        data = response.json()
        
        charts = data.get("charts", {})
        assert "revenue_daily" in charts, f"Missing 'revenue_daily' in charts"
        revenue_daily = charts["revenue_daily"]
        assert len(revenue_daily) == 30, f"Expected 30 entries in revenue_daily, got {len(revenue_daily)}"
        
        print(f"✓ GET /api/admin/billing/overview includes revenue_daily chart with {len(revenue_daily)} entries")
    
    def test_overview_kpis_include_refund_data(self):
        """GET /api/admin/billing/overview includes total_refunds and total_refunded in KPIs"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check KPIs exist
        assert "kpis" in data, f"Missing 'kpis' key in response"
        kpis = data["kpis"]
        
        # Check refund KPIs
        assert "total_refunds" in kpis, f"Missing 'total_refunds' in KPIs: {kpis.keys()}"
        assert "total_refunded" in kpis, f"Missing 'total_refunded' in KPIs: {kpis.keys()}"
        
        # Verify they are numeric
        assert isinstance(kpis["total_refunds"], (int, float)), f"total_refunds should be numeric"
        assert isinstance(kpis["total_refunded"], (int, float)), f"total_refunded should be numeric"
        
        print(f"✓ KPIs include total_refunds={kpis['total_refunds']}, total_refunded=${kpis['total_refunded']}")
    
    def test_overview_kpis_complete(self):
        """GET /api/admin/billing/overview includes all expected KPIs"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        assert response.status_code == 200
        data = response.json()
        kpis = data.get("kpis", {})
        
        expected_kpis = [
            "total_users", "active_subscribers", "free_users", "past_due", "canceled",
            "mrr", "arr_run_rate", "revenue_30d", "failed_payments_7d",
            "total_refunds", "total_refunded"
        ]
        
        for kpi in expected_kpis:
            assert kpi in kpis, f"Missing KPI '{kpi}' in response: {kpis.keys()}"
        
        print(f"✓ All {len(expected_kpis)} expected KPIs present in overview")


class TestReferralLandingPageFrontend:
    """Tests for referral landing page frontend routes"""
    
    def test_referral_landing_page_valid_code_loads(self):
        """GET /ref/{valid_code} returns 200 (page loads)"""
        response = requests.get(f"{BASE_URL}/ref/{VALID_REFERRAL_CODE}")
        # Frontend routes return 200 with HTML
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /ref/{VALID_REFERRAL_CODE} returns 200 (page loads)")
    
    def test_referral_landing_page_invalid_code_loads(self):
        """GET /ref/{invalid_code} returns 200 (page loads, shows error)"""
        response = requests.get(f"{BASE_URL}/ref/{INVALID_REFERRAL_CODE}")
        # Frontend routes return 200 with HTML (error shown in UI)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /ref/{INVALID_REFERRAL_CODE} returns 200 (page loads)")


class TestBillingPlansAPI:
    """Tests for billing plans public API"""
    
    def test_plans_api_returns_pricing(self):
        """GET /api/billing/plans returns pricing info"""
        response = requests.get(f"{BASE_URL}/api/billing/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=True, got {data}"
        assert "plans" in data, f"Missing 'plans' key in response"
        
        plans = data["plans"]
        assert "monthly" in plans, f"Missing 'monthly' in plans"
        assert "yearly" in plans, f"Missing 'yearly' in plans"
        
        print(f"✓ GET /api/billing/plans returns pricing info")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
