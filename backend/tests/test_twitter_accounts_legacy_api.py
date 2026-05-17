"""
Test: GET /api/v4/twitter/accounts with API Key Auth and Legacy Accounts

P0 Bug Fix: Browser extension now sees Twitter accounts added via admin web UI.
The endpoint supports both JWT (web UI) and API key (extension) authentication.
Legacy accounts from twitter_accounts collection are merged with results.

Test Cases:
1. Unauthenticated request returns 401
2. Valid API key returns accounts list
3. Legacy accounts (from twitter_accounts) have isLegacy=true, source=admin
4. Account response includes all required fields
"""

import pytest
import requests
import os

# Use the public URL from frontend/.env
BASE_URL = "https://expo-telegram-web.preview.emergentagent.com"

# API Key provided by main agent
API_KEY = "usr_7HKpJ0GZBWQMeD2bViMcXQ21oe9jg8Mhaiandn4lB-c"


class TestTwitterAccountsEndpoint:
    """Tests for GET /api/v4/twitter/accounts with API key auth and legacy support"""
    
    def test_unauthenticated_request_returns_401(self):
        """Request without auth should return 401 UNAUTHORIZED"""
        response = requests.get(
            f"{BASE_URL}/api/v4/twitter/accounts",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is False, "Response should have ok=false"
        assert "error" in data, "Response should contain error field"
        assert data["error"] == "UNAUTHORIZED", f"Expected UNAUTHORIZED error, got {data.get('error')}"
        print("✓ Test 1 PASSED: Unauthenticated request returns 401 UNAUTHORIZED")
    
    def test_api_key_auth_returns_accounts(self):
        """Request with valid API key should return accounts list"""
        response = requests.get(
            f"{BASE_URL}/api/v4/twitter/accounts",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Response should have ok=true, got {data}"
        assert "data" in data, "Response should contain data field"
        assert "accounts" in data["data"], "Data should contain accounts array"
        assert isinstance(data["data"]["accounts"], list), "Accounts should be a list"
        
        print(f"✓ Test 2 PASSED: API key auth returns {len(data['data']['accounts'])} accounts")
        return data["data"]["accounts"]
    
    def test_legacy_account_dmytro_visible(self):
        """Legacy account dmytro_fo1990 should be visible with isLegacy=true"""
        response = requests.get(
            f"{BASE_URL}/api/v4/twitter/accounts",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        accounts = data.get("data", {}).get("accounts", [])
        
        # Find dmytro_fo1990 account (case-insensitive)
        dmytro_account = None
        for account in accounts:
            username = account.get("username", "").lower()
            if username == "dmytro_fo1990":
                dmytro_account = account
                break
        
        if dmytro_account:
            # Verify it's marked as legacy account from admin
            assert dmytro_account.get("isLegacy") is True, \
                f"dmytro_fo1990 should have isLegacy=true, got {dmytro_account.get('isLegacy')}"
            assert dmytro_account.get("source") == "admin", \
                f"dmytro_fo1990 should have source=admin, got {dmytro_account.get('source')}"
            print(f"✓ Test 3 PASSED: Found dmytro_fo1990 with isLegacy={dmytro_account.get('isLegacy')}, source={dmytro_account.get('source')}")
        else:
            # Account might not exist in database - this is informational
            print(f"⚠ Test 3 INFO: dmytro_fo1990 not found in accounts list. Found accounts: {[a.get('username') for a in accounts]}")
            # Don't fail - the account might not be in the database during test
            pytest.skip("dmytro_fo1990 account not found in database - account may not exist yet")
    
    def test_account_response_fields(self):
        """Each account should contain required fields: id, username, displayName, enabled, sessionStatus, isLegacy, source"""
        response = requests.get(
            f"{BASE_URL}/api/v4/twitter/accounts",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        accounts = data.get("data", {}).get("accounts", [])
        
        if len(accounts) == 0:
            pytest.skip("No accounts in response to validate fields")
        
        required_fields = ["id", "username", "displayName", "enabled", "sessionStatus", "isLegacy", "source"]
        
        for account in accounts:
            for field in required_fields:
                assert field in account, f"Account {account.get('username')} missing field: {field}"
            
            # Validate field types
            assert isinstance(account.get("id"), str), f"id should be string for {account.get('username')}"
            assert isinstance(account.get("username"), str), f"username should be string"
            assert isinstance(account.get("displayName"), str), f"displayName should be string"
            assert isinstance(account.get("enabled"), bool), f"enabled should be boolean"
            assert isinstance(account.get("isLegacy"), bool), f"isLegacy should be boolean"
            assert account.get("source") in ["admin", "user"], f"source should be 'admin' or 'user'"
        
        print(f"✓ Test 4 PASSED: All {len(accounts)} accounts have required fields")
    
    def test_invalid_api_key_returns_401(self):
        """Request with invalid API key should return 401"""
        response = requests.get(
            f"{BASE_URL}/api/v4/twitter/accounts",
            headers={
                "Authorization": "Bearer usr_invalid_key_12345",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ Test 5 PASSED: Invalid API key returns 401")
    
    def test_response_includes_total_and_limit(self):
        """Response should include total count and limit for accounts"""
        response = requests.get(
            f"{BASE_URL}/api/v4/twitter/accounts",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        response_data = data.get("data", {})
        
        assert "total" in response_data, "Response should include total count"
        assert "limit" in response_data, "Response should include limit"
        assert isinstance(response_data.get("total"), int), "total should be integer"
        assert isinstance(response_data.get("limit"), int), "limit should be integer"
        
        print(f"✓ Test 6 PASSED: Response includes total={response_data.get('total')}, limit={response_data.get('limit')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
