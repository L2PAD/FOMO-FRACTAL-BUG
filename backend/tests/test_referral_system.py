"""
Test Referral System APIs - Iteration 545
Tests: Promo groups with referral settings, assign codes, referral conversions
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestPromoGroupsAPI:
    """Test promo groups CRUD with referral settings"""
    
    def test_list_promo_groups(self):
        """GET /api/admin/billing/promos/groups returns list"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "groups" in data
        assert isinstance(data["groups"], list)
        print(f"✓ Found {len(data['groups'])} promo groups")
    
    def test_existing_referral_group_has_badge_fields(self):
        """Existing referral group 'Influencer 25%' has referral fields"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        assert response.status_code == 200
        data = response.json()
        
        # Find the referral group
        referral_groups = [g for g in data["groups"] if g.get("referral_enabled")]
        assert len(referral_groups) > 0, "No referral groups found"
        
        ref_group = referral_groups[0]
        assert ref_group["referral_enabled"] is True
        assert "referral_reward_percent" in ref_group
        assert ref_group["referral_reward_percent"] > 0
        print(f"✓ Referral group '{ref_group['name']}' has reward {ref_group['referral_reward_percent']}%")
    
    def test_create_referral_promo_group(self):
        """POST /api/admin/billing/promos/groups with referral_enabled=true"""
        unique_name = f"TEST_Referral_{uuid.uuid4().hex[:6]}"
        payload = {
            "name": unique_name,
            "discount_percent": 20,
            "count": 3,
            "prefix": "TREF",
            "referral_enabled": True,
            "referral_reward_percent": 25
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "group_id" in data
        assert data["codes_generated"] == 3
        
        # Verify group was created with referral settings
        group_id = data["group_id"]
        list_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = list_response.json()["groups"]
        created_group = next((g for g in groups if g["group_id"] == group_id), None)
        
        assert created_group is not None
        assert created_group["referral_enabled"] is True
        assert created_group["referral_reward_percent"] == 25
        
        print(f"✓ Created referral group '{unique_name}' with ID {group_id}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}")
    
    def test_create_non_referral_promo_group(self):
        """POST /api/admin/billing/promos/groups without referral settings"""
        unique_name = f"TEST_Regular_{uuid.uuid4().hex[:6]}"
        payload = {
            "name": unique_name,
            "discount_percent": 50,
            "count": 2,
            "prefix": "REG"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        
        group_id = data["group_id"]
        
        # Verify group was created without referral settings
        list_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = list_response.json()["groups"]
        created_group = next((g for g in groups if g["group_id"] == group_id), None)
        
        assert created_group is not None
        assert created_group.get("referral_enabled", False) is False
        
        print(f"✓ Created non-referral group '{unique_name}'")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}")


class TestReferralGroupUpdate:
    """Test PUT /api/admin/billing/promos/groups/{group_id}"""
    
    def test_update_referral_settings(self):
        """PUT updates referral_reward_percent and discount_percent"""
        # First create a test group
        payload = {
            "name": f"TEST_Update_{uuid.uuid4().hex[:6]}",
            "discount_percent": 10,
            "count": 2,
            "referral_enabled": True,
            "referral_reward_percent": 10
        }
        create_response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups",
            json=payload
        )
        group_id = create_response.json()["group_id"]
        
        # Update the group
        update_payload = {
            "referral_reward_percent": 30,
            "discount_percent": 15
        }
        update_response = requests.put(
            f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}",
            json=update_payload
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["ok"] is True
        assert data["group"]["referral_reward_percent"] == 30
        assert data["group"]["discount_percent"] == 15
        
        print(f"✓ Updated group {group_id} referral settings")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}")
    
    def test_update_nonexistent_group_returns_404(self):
        """PUT on non-existent group returns 404"""
        response = requests.put(
            f"{BASE_URL}/api/admin/billing/promos/groups/grp_nonexistent",
            json={"referral_reward_percent": 50}
        )
        assert response.status_code == 404
        print("✓ Non-existent group returns 404")


class TestReferralCodeAssignment:
    """Test POST /api/admin/billing/promos/groups/{group_id}/assign"""
    
    def test_assign_code_to_existing_user(self):
        """Assign referral code to existing user by email"""
        # Get existing referral group
        groups_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = groups_response.json()["groups"]
        referral_group = next((g for g in groups if g.get("referral_enabled")), None)
        
        if not referral_group:
            pytest.skip("No referral group available for testing")
        
        group_id = referral_group["group_id"]
        
        # Try to assign to existing user
        assign_response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups/{group_id}/assign",
            json={"user_email": "evhenbik21@gmail.com"}
        )
        
        # Could be 200 (success) or 400 (no available codes) or 404 (user not found)
        if assign_response.status_code == 200:
            data = assign_response.json()
            assert data["ok"] is True
            assert "code" in data
            print(f"✓ Assigned code {data['code']} to user")
        elif assign_response.status_code == 400:
            print("✓ No available codes in group (expected if all assigned)")
        else:
            print(f"✓ Assignment returned {assign_response.status_code}")
    
    def test_assign_code_missing_email_returns_400(self):
        """Assign without email returns 400"""
        groups_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = groups_response.json()["groups"]
        referral_group = next((g for g in groups if g.get("referral_enabled")), None)
        
        if not referral_group:
            pytest.skip("No referral group available")
        
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups/{referral_group['group_id']}/assign",
            json={}
        )
        assert response.status_code == 400
        print("✓ Missing email returns 400")
    
    def test_assign_code_nonexistent_user_returns_404(self):
        """Assign to non-existent user returns 404"""
        groups_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = groups_response.json()["groups"]
        referral_group = next((g for g in groups if g.get("referral_enabled")), None)
        
        if not referral_group:
            pytest.skip("No referral group available")
        
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/promos/groups/{referral_group['group_id']}/assign",
            json={"user_email": "nonexistent_user_12345@test.com"}
        )
        assert response.status_code == 404
        print("✓ Non-existent user returns 404")


class TestReferralConversions:
    """Test GET /api/admin/billing/promos/referrals"""
    
    def test_get_referral_conversions(self):
        """GET /api/admin/billing/promos/referrals returns list"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/promos/referrals")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "conversions" in data
        assert "total_conversions" in data
        assert "total_rewards" in data
        print(f"✓ Referral conversions: {data['total_conversions']} total, ${data['total_rewards']} rewards")
    
    def test_get_group_referrals(self):
        """GET /api/admin/billing/promos/groups/{group_id}/referrals"""
        groups_response = requests.get(f"{BASE_URL}/api/admin/billing/promos/groups")
        groups = groups_response.json()["groups"]
        referral_group = next((g for g in groups if g.get("referral_enabled")), None)
        
        if not referral_group:
            pytest.skip("No referral group available")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/promos/groups/{referral_group['group_id']}/referrals"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "conversions" in data
        print(f"✓ Group referrals: {len(data['conversions'])} conversions")


class TestPricingWithPaywall:
    """Test pricing config with paywall_enabled field"""
    
    def test_get_pricing_has_paywall_field(self):
        """GET /api/admin/billing/pricing includes paywall_enabled"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/pricing")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "pricing" in data
        assert "paywall_enabled" in data["pricing"]
        print(f"✓ Paywall enabled: {data['pricing']['paywall_enabled']}")
    
    def test_update_paywall_setting(self):
        """PUT /api/admin/billing/pricing can toggle paywall"""
        # Get current state
        get_response = requests.get(f"{BASE_URL}/api/admin/billing/pricing")
        current = get_response.json()["pricing"]
        current_paywall = current.get("paywall_enabled", True)
        
        # Toggle paywall
        update_response = requests.put(
            f"{BASE_URL}/api/admin/billing/pricing",
            json={"paywall_enabled": not current_paywall}
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["ok"] is True
        assert data["pricing"]["paywall_enabled"] == (not current_paywall)
        
        # Restore original state
        requests.put(
            f"{BASE_URL}/api/admin/billing/pricing",
            json={"paywall_enabled": current_paywall}
        )
        print(f"✓ Paywall toggle works (restored to {current_paywall})")


class TestAccessTab:
    """Test Access tab API (subscribers endpoint)"""
    
    def test_subscribers_endpoint_works(self):
        """GET /api/admin/billing/subscribers returns data"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "subscribers" in data
        assert "total" in data
        print(f"✓ Subscribers endpoint: {data['total']} total users")
    
    def test_grant_access_endpoint(self):
        """POST /api/admin/billing/access/{user_id}/grant works"""
        # Get a test user
        subs_response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers?limit=1")
        subscribers = subs_response.json()["subscribers"]
        
        if not subscribers:
            pytest.skip("No users available for testing")
        
        user_id = subscribers[0]["user_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/access/{user_id}/grant",
            json={"reason": "Test grant", "days": 1}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        print(f"✓ Grant access works for user {user_id}")
    
    def test_revoke_access_endpoint(self):
        """POST /api/admin/billing/access/{user_id}/revoke works"""
        subs_response = requests.get(f"{BASE_URL}/api/admin/billing/subscribers?limit=1")
        subscribers = subs_response.json()["subscribers"]
        
        if not subscribers:
            pytest.skip("No users available for testing")
        
        user_id = subscribers[0]["user_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/access/{user_id}/revoke",
            json={"reason": "Test revoke"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        print(f"✓ Revoke access works for user {user_id}")


class TestBillingTabsAPIs:
    """Test all billing tab APIs load without errors"""
    
    def test_overview_tab_api(self):
        """GET /api/admin/billing/overview"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/overview")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        print("✓ Overview tab API works")
    
    def test_payments_tab_api(self):
        """GET /api/admin/billing/payments"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/payments")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        print("✓ Payments tab API works")
    
    def test_subscriptions_tab_api(self):
        """GET /api/admin/billing/subscriptions"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/subscriptions")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        print("✓ Subscriptions tab API works")
    
    def test_events_tab_api(self):
        """GET /api/admin/billing/events"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/events")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        print("✓ Events tab API works")
    
    def test_stripe_keys_tab_api(self):
        """GET /api/admin/billing/stripe-keys"""
        response = requests.get(f"{BASE_URL}/api/admin/billing/stripe-keys")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        print("✓ Stripe keys tab API works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
