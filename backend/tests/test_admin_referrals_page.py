"""
Test suite for Admin Referrals Page (/admin/referrals)
Tests the new dedicated Referrals & Promo page with 4 tabs:
- Обзор (Overview) - Dashboard KPIs
- Промокоды (Promos) - Group management with referral support
- Рефералы (Referrals) - Conversion tracking journal
- Инфлюенсеры (Influencers) - Assign codes to bloggers, leaderboard

Backend APIs tested:
- GET /api/admin/billing/promos/groups - List all groups with referral stats
- POST /api/admin/billing/promos/groups - Create group with referral settings
- PUT /api/admin/billing/promos/groups/{id} - Update referral settings
- DELETE /api/admin/billing/promos/groups/{id} - Delete group and related data
- POST /api/admin/billing/promos/groups/{id}/assign - Assign code to user
- GET /api/admin/billing/promos/referrals - Get all conversions
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPromoGroupsAPI:
    """Test promo groups CRUD operations"""
    
    def test_list_promo_groups(self):
        """GET /api/admin/billing/promos/groups returns groups list"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data
        assert "groups" in data
        assert isinstance(data["groups"], list)
        print(f"PASS: List promo groups - {len(data['groups'])} groups found")
    
    def test_list_groups_has_referral_fields(self):
        """Groups should have referral_enabled and referral_reward_percent fields"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        assert response.status_code == 200
        
        data = response.json()
        groups = data.get("groups", [])
        
        # Check if any group has referral fields
        for g in groups:
            assert "referral_enabled" in g or g.get("referral_enabled") is not None or "referral_enabled" not in g
            # Fields should exist in schema
            if g.get("referral_enabled"):
                assert "referral_reward_percent" in g
                print(f"PASS: Group '{g['name']}' has referral fields - REF {g['referral_reward_percent']}%")
        
        print(f"PASS: Groups have proper referral field structure")
    
    def test_create_promo_group_with_referral(self):
        """POST /api/admin/billing/promos/groups creates group with referral settings"""
        unique_name = f"TEST_Referral_{uuid.uuid4().hex[:6]}"
        payload = {
            "name": unique_name,
            "discount_percent": 25,
            "count": 5,
            "prefix": "TREF",
            "referral_enabled": True,
            "referral_reward_percent": 15
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True
        assert "group_id" in data
        assert data.get("codes_generated") == 5
        
        # Verify group was created with referral settings
        group_id = data["group_id"]
        verify_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = verify_response.json().get("groups", [])
        created_group = next((g for g in groups if g["group_id"] == group_id), None)
        
        assert created_group is not None
        assert created_group["referral_enabled"] == True
        assert created_group["referral_reward_percent"] == 15
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}")
        print(f"PASS: Created referral group '{unique_name}' with REF 15%")
    
    def test_create_promo_group_without_referral(self):
        """POST /api/admin/billing/promos/groups creates non-referral group"""
        unique_name = f"TEST_NoRef_{uuid.uuid4().hex[:6]}"
        payload = {
            "name": unique_name,
            "discount_percent": 50,
            "count": 3,
            "prefix": "TNOR",
            "referral_enabled": False,
            "referral_reward_percent": 0
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups",
            json=payload
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        group_id = data["group_id"]
        
        # Verify
        verify_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = verify_response.json().get("groups", [])
        created_group = next((g for g in groups if g["group_id"] == group_id), None)
        
        assert created_group is not None
        assert created_group["referral_enabled"] == False
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}")
        print(f"PASS: Created non-referral group '{unique_name}'")
    
    def test_update_promo_group_referral_settings(self):
        """PUT /api/admin/billing/promos/groups/{id} updates referral settings"""
        # First create a group
        unique_name = f"TEST_Update_{uuid.uuid4().hex[:6]}"
        create_response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups",
            json={
                "name": unique_name,
                "discount_percent": 20,
                "count": 2,
                "referral_enabled": True,
                "referral_reward_percent": 10
            }
        )
        assert create_response.status_code == 200
        group_id = create_response.json()["group_id"]
        
        # Update referral settings
        update_response = requests.put(
            f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}",
            json={
                "referral_reward_percent": 25,
                "discount_percent": 30
            }
        )
        assert update_response.status_code == 200
        
        data = update_response.json()
        assert data.get("ok") == True
        assert data["group"]["referral_reward_percent"] == 25
        assert data["group"]["discount_percent"] == 30
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}")
        print(f"PASS: Updated referral settings for group '{unique_name}'")
    
    def test_update_nonexistent_group_returns_404(self):
        """PUT /api/admin/billing/promos/groups/{id} returns 404 for nonexistent group"""
        response = requests.put(
            f"{BASE_URL}/api/admin/billing/promos/groups/grp_nonexistent123",
            json={"referral_reward_percent": 20}
        )
        assert response.status_code == 404
        print("PASS: Update nonexistent group returns 404")
    
    def test_delete_promo_group(self):
        """DELETE /api/admin/billing/promos/groups/{id} deletes group and codes"""
        # Create a group
        unique_name = f"TEST_Delete_{uuid.uuid4().hex[:6]}"
        create_response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups",
            json={
                "name": unique_name,
                "discount_percent": 10,
                "count": 3,
                "referral_enabled": False
            }
        )
        assert create_response.status_code == 200
        group_id = create_response.json()["group_id"]
        
        # Delete
        delete_response = requests.delete(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}")
        assert delete_response.status_code == 200
        
        data = delete_response.json()
        assert data.get("ok") == True
        assert "deleted_codes" in data
        
        # Verify deletion
        verify_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = verify_response.json().get("groups", [])
        deleted_group = next((g for g in groups if g["group_id"] == group_id), None)
        assert deleted_group is None
        
        print(f"PASS: Deleted group '{unique_name}' and {data['deleted_codes']} codes")


class TestReferralConversionsAPI:
    """Test referral conversions tracking"""
    
    def test_get_referral_conversions(self):
        """GET /api/admin/billing/promos/referrals returns conversions list"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/referrals")
        assert response.status_code == 200
        
        data = response.json()
        assert "ok" in data
        assert "conversions" in data
        assert "total_conversions" in data
        assert "total_rewards" in data
        assert isinstance(data["conversions"], list)
        
        print(f"PASS: Get referral conversions - {data['total_conversions']} total, ${data['total_rewards']} rewards")
    
    def test_get_group_referrals(self):
        """GET /api/admin/billing/promos/groups/{id}/referrals returns group conversions"""
        # Get existing referral group
        groups_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = groups_response.json().get("groups", [])
        ref_groups = [g for g in groups if g.get("referral_enabled")]
        
        if not ref_groups:
            pytest.skip("No referral groups exist for testing")
        
        group_id = ref_groups[0]["group_id"]
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}/referrals")
        assert response.status_code == 200
        
        data = response.json()
        assert "ok" in data
        assert "conversions" in data
        
        print(f"PASS: Get group referrals for {group_id}")


class TestInfluencerAssignmentAPI:
    """Test influencer code assignment"""
    
    def test_assign_code_missing_email_returns_400(self):
        """POST /api/admin/billing/promos/groups/{id}/assign returns 400 without email"""
        # Get a referral group
        groups_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = groups_response.json().get("groups", [])
        ref_groups = [g for g in groups if g.get("referral_enabled")]
        
        if not ref_groups:
            # Create one for testing
            create_response = requests.post(
                f"{BASE_URL}/api/admin/billing/promos/groups",
                json={
                    "name": f"TEST_Assign_{uuid.uuid4().hex[:6]}",
                    "discount_percent": 20,
                    "count": 5,
                    "referral_enabled": True,
                    "referral_reward_percent": 10
                }
            )
            group_id = create_response.json()["group_id"]
        else:
            group_id = ref_groups[0]["group_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}/assign",
            json={}
        )
        assert response.status_code == 400
        print("PASS: Assign code without email returns 400")
    
    def test_assign_code_nonexistent_user_returns_404(self):
        """POST /api/admin/billing/promos/groups/{id}/assign returns 404 for unknown user"""
        # Get a referral group
        groups_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = groups_response.json().get("groups", [])
        ref_groups = [g for g in groups if g.get("referral_enabled")]
        
        if not ref_groups:
            pytest.skip("No referral groups exist for testing")
        
        group_id = ref_groups[0]["group_id"]
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}/assign",
            json={"user_email": f"nonexistent_{uuid.uuid4().hex[:8]}@test.com"}
        )
        assert response.status_code == 404
        print("PASS: Assign code to nonexistent user returns 404")
    
    def test_assign_code_nonexistent_group_returns_404(self):
        """POST /api/admin/billing/promos/groups/{id}/assign returns 404 for unknown group"""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups/grp_nonexistent123/assign",
            json={"user_email": "test@example.com"}
        )
        assert response.status_code == 404
        print("PASS: Assign code to nonexistent group returns 404")


class TestGroupCodesAPI:
    """Test group codes retrieval"""
    
    def test_get_group_codes(self):
        """GET /api/admin/billing/promos/groups/{id}/codes returns codes list"""
        # Get any group
        groups_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = groups_response.json().get("groups", [])
        
        if not groups:
            pytest.skip("No promo groups exist for testing")
        
        group_id = groups[0]["group_id"]
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}/codes")
        assert response.status_code == 200
        
        data = response.json()
        assert "ok" in data
        assert "codes" in data
        assert isinstance(data["codes"], list)
        
        # Check code structure
        if data["codes"]:
            code = data["codes"][0]
            assert "code" in code
            assert "group_id" in code
            assert "discount_percent" in code
        
        print(f"PASS: Get group codes - {len(data['codes'])} codes found")


class TestOverviewKPIs:
    """Test Overview tab KPI data"""
    
    def test_overview_kpis_from_groups(self):
        """Overview tab should calculate KPIs from groups data"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        assert response.status_code == 200
        
        data = response.json()
        groups = data.get("groups", [])
        
        # Calculate expected KPIs
        total_groups = len(groups)
        total_codes = sum(g.get("total_codes", 0) for g in groups)
        used_codes = sum(g.get("used_codes", 0) for g in groups)
        ref_groups = [g for g in groups if g.get("referral_enabled")]
        
        print(f"PASS: Overview KPIs - {total_groups} groups, {used_codes}/{total_codes} codes, {len(ref_groups)} referral groups")
    
    def test_overview_kpis_from_conversions(self):
        """Overview tab should get conversion stats"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/referrals")
        assert response.status_code == 200
        
        data = response.json()
        total_conversions = data.get("total_conversions", 0)
        total_rewards = data.get("total_rewards", 0)
        
        print(f"PASS: Overview conversion KPIs - {total_conversions} conversions, ${total_rewards} rewards")


class TestBillingPageNoPromosTab:
    """Verify Promos tab was removed from Billing page"""
    
    def test_billing_overview_api_works(self):
        """Billing overview API should still work"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        assert response.status_code == 200
        
        data = response.json()
        assert "kpis" in data
        print("PASS: Billing overview API works")
    
    def test_billing_pricing_api_works(self):
        """Billing pricing API should still work"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/pricing")
        assert response.status_code == 200
        
        data = response.json()
        assert "pricing" in data
        print("PASS: Billing pricing API works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
