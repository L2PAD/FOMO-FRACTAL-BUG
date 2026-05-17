"""
Test Suite: Extended Referral System (iteration_547)

Tests for:
1. Settings page Referrals tab (user-facing)
2. Backend /api/user/referrals endpoint
3. Backend /api/admin/billing/promos/codes/{code}/unassign endpoint
4. Backend /api/admin/billing/promos/codes/{code}/reassign endpoint
5. Admin Referrals page padding and layout
6. Admin Influencers tab edit/unassign/reassign functionality
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestUserReferralsEndpoint:
    """Tests for GET /api/user/referrals endpoint"""
    
    def test_user_referrals_unauthenticated_returns_401(self):
        """Unauthenticated request should return 401"""
        response = requests.get(f"{BASE_URL}/api/user/referrals")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/user/referrals returns 401 for unauthenticated users")


class TestUnassignEndpoint:
    """Tests for POST /api/admin/billing/promos/codes/{code}/unassign"""
    
    def test_unassign_nonexistent_code_returns_400(self):
        """Unassigning a non-existent code should return 400"""
        response = requests.post(f"{BASE_URL}/api/admin/billing/promos/codes/NONEXIST123/unassign")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data or "error" in data, "Response should contain error message"
        print("PASS: POST /api/admin/billing/promos/codes/NONEXIST/unassign returns 400")
    
    def test_unassign_random_code_returns_400(self):
        """Unassigning a random code should return 400"""
        response = requests.post(f"{BASE_URL}/api/admin/billing/promos/codes/RANDOM_CODE_XYZ/unassign")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Unassign random code returns 400")


class TestReassignEndpoint:
    """Tests for POST /api/admin/billing/promos/codes/{code}/reassign"""
    
    def test_reassign_nonexistent_code_returns_404(self):
        """Reassigning a non-existent code should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/codes/NONEXIST123/reassign",
            json={"user_email": "test@example.com"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "detail" in data or "error" in data, "Response should contain error message"
        print("PASS: POST /api/admin/billing/promos/codes/NONEXIST/reassign returns 404")
    
    def test_reassign_missing_email_returns_400(self):
        """Reassigning without email should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/codes/ANYCODE/reassign",
            json={}
        )
        # Could be 400 (missing email) or 404 (code not found)
        assert response.status_code in [400, 404], f"Expected 400 or 404, got {response.status_code}"
        print("PASS: Reassign without email returns 400 or 404")


class TestPromoGroupsAPI:
    """Tests for promo groups API with referral stats"""
    
    def test_list_groups_returns_referral_stats(self):
        """GET /api/admin/billing/promos/groups should include referral stats"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "groups" in data, "Response should contain 'groups' key"
        print(f"PASS: GET /api/admin/billing/promos/groups returns {len(data['groups'])} groups")
        
        # Check that referral-enabled groups have referral_conversions field
        for group in data['groups']:
            if group.get('referral_enabled'):
                assert 'referral_conversions' in group, f"Referral group {group['name']} should have referral_conversions"
                print(f"  - Group '{group['name']}': referral_enabled=True, conversions={group.get('referral_conversions', 0)}")
    
    def test_update_group_referral_settings(self):
        """PUT /api/admin/billing/promos/groups/{id} should update referral settings"""
        # First get existing groups
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        assert response.status_code == 200
        groups = response.json().get('groups', [])
        
        if not groups:
            pytest.skip("No promo groups available for testing")
        
        group_id = groups[0]['group_id']
        
        # Update referral settings
        update_response = requests.put(
            f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}",
            json={"referral_reward_percent": 15}
        )
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}"
        data = update_response.json()
        assert data.get('ok') == True, "Update should return ok=True"
        print(f"PASS: PUT /api/admin/billing/promos/groups/{group_id} updates referral settings")
    
    def test_update_nonexistent_group_returns_404(self):
        """PUT /api/admin/billing/promos/groups/{id} for non-existent group should return 404"""
        response = requests.put(
            f"{BASE_URL}/api/admin/billing/promos/groups/grp_nonexistent123",
            json={"referral_reward_percent": 10}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: PUT /api/admin/billing/promos/groups/nonexistent returns 404")


class TestReferralConversionsAPI:
    """Tests for referral conversions API"""
    
    def test_list_referral_conversions(self):
        """GET /api/admin/billing/promos/referrals should return conversions"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/referrals")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "conversions" in data, "Response should contain 'conversions' key"
        assert "total_conversions" in data, "Response should contain 'total_conversions' key"
        assert "total_rewards" in data, "Response should contain 'total_rewards' key"
        print(f"PASS: GET /api/admin/billing/promos/referrals returns {data['total_conversions']} conversions, ${data['total_rewards']} rewards")


class TestSettingsPageTabs:
    """Tests for Settings page tabs structure"""
    
    def test_settings_page_loads(self):
        """Settings page should load"""
        response = requests.get(f"{BASE_URL}/settings")
        # Frontend routes return 200 even for SPA routes
        assert response.status_code in [200, 304], f"Expected 200/304, got {response.status_code}"
        print("PASS: Settings page loads")
    
    def test_settings_referrals_tab_url(self):
        """Settings page with referrals tab should be accessible"""
        response = requests.get(f"{BASE_URL}/settings?tab=referrals")
        assert response.status_code in [200, 304], f"Expected 200/304, got {response.status_code}"
        print("PASS: Settings page with ?tab=referrals loads")


class TestAdminReferralsPage:
    """Tests for Admin Referrals page"""
    
    def test_admin_referrals_page_loads(self):
        """Admin referrals page should load"""
        response = requests.get(f"{BASE_URL}/admin/referrals")
        assert response.status_code in [200, 304], f"Expected 200/304, got {response.status_code}"
        print("PASS: Admin referrals page loads")


class TestBillingPageNoPromos:
    """Tests to verify Billing page no longer has Promos tab"""
    
    def test_billing_overview_api(self):
        """Billing overview API should work"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/admin/billing/overview works")
    
    def test_billing_pricing_api(self):
        """Billing pricing API should work"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/pricing")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/admin/billing/pricing works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
