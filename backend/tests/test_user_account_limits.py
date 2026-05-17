"""
Test User Account/Keyword Limits Feature
- GET /api/user/extension-status - returns hasExtension, sessions, limits
- GET /api/user/my-accounts - returns user's tracked account IDs
- POST /api/user/my-accounts - adds account to tracked list
- DELETE /api/user/my-accounts?id=xxx - removes account from tracked list
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestExtensionStatus:
    """Test /api/user/extension-status endpoint"""
    
    def test_extension_status_returns_ok(self):
        """Extension status API should return ok:true with hasExtension, sessions, limits"""
        response = requests.get(f"{BASE_URL}/api/user/extension-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        
        # Verify hasExtension field exists
        assert "hasExtension" in data, f"Missing hasExtension field: {data}"
        assert isinstance(data["hasExtension"], bool), f"hasExtension should be bool: {data}"
        
        # Verify sessions field exists with ok, stale, total
        assert "sessions" in data, f"Missing sessions field: {data}"
        sessions = data["sessions"]
        assert "ok" in sessions, f"Missing sessions.ok: {sessions}"
        assert "stale" in sessions, f"Missing sessions.stale: {sessions}"
        assert "total" in sessions, f"Missing sessions.total: {sessions}"
        
        # Verify limits field exists with accounts, keywords
        assert "limits" in data, f"Missing limits field: {data}"
        limits = data["limits"]
        assert "accounts" in limits, f"Missing limits.accounts: {limits}"
        assert "keywords" in limits, f"Missing limits.keywords: {limits}"
        
        print(f"Extension status: hasExtension={data['hasExtension']}, sessions={sessions}, limits={limits}")
    
    def test_extension_status_limits_based_on_sessions(self):
        """Limits should be 30/30 with extension (ok sessions > 0), 2/2 without"""
        response = requests.get(f"{BASE_URL}/api/user/extension-status")
        data = response.json()
        
        has_extension = data.get("hasExtension", False)
        limits = data.get("limits", {})
        
        if has_extension:
            assert limits.get("accounts") == 30, f"With extension, accounts limit should be 30: {limits}"
            assert limits.get("keywords") == 30, f"With extension, keywords limit should be 30: {limits}"
        else:
            assert limits.get("accounts") == 2, f"Without extension, accounts limit should be 2: {limits}"
            assert limits.get("keywords") == 2, f"Without extension, keywords limit should be 2: {limits}"
        
        print(f"Limits verified: hasExtension={has_extension}, limits={limits}")


class TestMyAccounts:
    """Test /api/user/my-accounts CRUD endpoints"""
    
    def test_get_my_accounts_returns_ok(self):
        """GET /api/user/my-accounts should return ok:true with accounts array"""
        response = requests.get(f"{BASE_URL}/api/user/my-accounts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "accounts" in data, f"Missing accounts field: {data}"
        assert isinstance(data["accounts"], list), f"accounts should be list: {data}"
        
        print(f"My accounts: {data['accounts']}")
    
    def test_add_account_to_tracked_list(self):
        """POST /api/user/my-accounts should add account to tracked list"""
        test_account_id = "twitter:TEST_account_123"
        
        # Add account
        response = requests.post(
            f"{BASE_URL}/api/user/my-accounts",
            json={"accountId": test_account_id},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "accounts" in data, f"Missing accounts field: {data}"
        assert test_account_id in data["accounts"], f"Account not added: {data}"
        
        print(f"Added account {test_account_id}, accounts now: {data['accounts']}")
        
        # Verify with GET
        get_response = requests.get(f"{BASE_URL}/api/user/my-accounts")
        get_data = get_response.json()
        assert test_account_id in get_data.get("accounts", []), f"Account not persisted: {get_data}"
        
        print(f"Verified account persisted via GET: {get_data['accounts']}")
    
    def test_add_duplicate_account_returns_already_added(self):
        """Adding same account twice should return 'Already added' message"""
        test_account_id = "twitter:TEST_duplicate_456"
        
        # Add first time
        requests.post(
            f"{BASE_URL}/api/user/my-accounts",
            json={"accountId": test_account_id},
            headers={"Content-Type": "application/json"}
        )
        
        # Add second time
        response = requests.post(
            f"{BASE_URL}/api/user/my-accounts",
            json={"accountId": test_account_id},
            headers={"Content-Type": "application/json"}
        )
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert data.get("message") == "Already added", f"Expected 'Already added' message: {data}"
        
        print(f"Duplicate add handled correctly: {data}")
    
    def test_add_account_without_id_returns_400(self):
        """POST without accountId should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/user/my-accounts",
            json={},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == False, f"Expected ok:false, got {data}"
        assert "accountId required" in data.get("error", ""), f"Expected error message: {data}"
        
        print(f"Empty accountId handled correctly: {data}")
    
    def test_delete_account_from_tracked_list(self):
        """DELETE /api/user/my-accounts?id=xxx should remove account"""
        test_account_id = "twitter:TEST_delete_789"
        
        # First add the account
        requests.post(
            f"{BASE_URL}/api/user/my-accounts",
            json={"accountId": test_account_id},
            headers={"Content-Type": "application/json"}
        )
        
        # Verify it's added
        get_response = requests.get(f"{BASE_URL}/api/user/my-accounts")
        assert test_account_id in get_response.json().get("accounts", [])
        
        # Delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/user/my-accounts?id={test_account_id}"
        )
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        
        data = delete_response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert test_account_id not in data.get("accounts", []), f"Account not removed: {data}"
        
        print(f"Deleted account {test_account_id}, accounts now: {data['accounts']}")
        
        # Verify with GET
        verify_response = requests.get(f"{BASE_URL}/api/user/my-accounts")
        verify_data = verify_response.json()
        assert test_account_id not in verify_data.get("accounts", []), f"Account still exists: {verify_data}"
        
        print(f"Verified account removed via GET: {verify_data['accounts']}")
    
    def test_delete_account_without_id_returns_400(self):
        """DELETE without id query param should return 400"""
        response = requests.delete(f"{BASE_URL}/api/user/my-accounts")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == False, f"Expected ok:false, got {data}"
        assert "id query param required" in data.get("error", ""), f"Expected error message: {data}"
        
        print(f"Empty id handled correctly: {data}")


class TestSentimentAccountsAPI:
    """Test /api/v4/sentiment/accounts endpoint for sidebar data"""
    
    def test_sentiment_accounts_returns_data(self):
        """GET /api/v4/sentiment/accounts should return accounts for sidebar"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/accounts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "data" in data, f"Missing data field: {data}"
        
        accounts = data.get("data", [])
        assert isinstance(accounts, list), f"data should be list: {data}"
        
        if len(accounts) > 0:
            # Verify account structure
            account = accounts[0]
            assert "id" in account, f"Account missing id: {account}"
            assert "username" in account, f"Account missing username: {account}"
            print(f"Found {len(accounts)} accounts, first: {account.get('username')}")
        else:
            print("No accounts found (may be expected)")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_accounts(self):
        """Remove TEST_ prefixed accounts"""
        # Get current accounts
        response = requests.get(f"{BASE_URL}/api/user/my-accounts")
        accounts = response.json().get("accounts", [])
        
        # Delete TEST_ accounts
        for acc_id in accounts:
            if "TEST_" in acc_id:
                requests.delete(f"{BASE_URL}/api/user/my-accounts?id={acc_id}")
                print(f"Cleaned up: {acc_id}")
        
        # Verify cleanup
        final_response = requests.get(f"{BASE_URL}/api/user/my-accounts")
        final_accounts = final_response.json().get("accounts", [])
        test_accounts = [a for a in final_accounts if "TEST_" in a]
        assert len(test_accounts) == 0, f"Test accounts not cleaned up: {test_accounts}"
        
        print(f"Cleanup complete, remaining accounts: {final_accounts}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
