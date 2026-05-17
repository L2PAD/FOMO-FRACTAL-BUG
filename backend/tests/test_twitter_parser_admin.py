"""
Twitter Parser Admin API Tests
Tests for Twitter accounts and egress slots CRUD operations
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data prefixes for cleanup
TEST_PREFIX = "TEST_"


class TestAdminAuth:
    """Admin authentication tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert "token" in data
        return data["token"]
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "token" in data
        assert data["role"] == "ADMIN"
        assert data["username"] == "admin"
    
    def test_admin_login_invalid_credentials(self):
        """Test admin login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401
        data = response.json()
        assert data["ok"] is False
        assert data["error"] == "INVALID_CREDENTIALS"
    
    def test_admin_login_missing_fields(self):
        """Test admin login with missing fields"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] is False


class TestTwitterAccounts:
    """Twitter accounts CRUD tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Headers with auth token"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}"
        }
    
    def test_list_accounts(self, auth_headers):
        """Test listing all Twitter accounts"""
        response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        assert isinstance(data["data"], list)
        assert "total" in data
    
    def test_create_account(self, auth_headers):
        """Test creating a new Twitter account"""
        payload = {
            "label": f"{TEST_PREFIX}Account_Create_Test",
            "notes": "Test account for pytest"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        assert data["data"]["label"] == payload["label"]
        assert data["data"]["notes"] == payload["notes"]
        assert data["data"]["status"] == "ACTIVE"
        
        # Store ID for cleanup
        account_id = data["data"]["_id"]
        
        # Verify by GET
        get_response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["data"]["label"] == payload["label"]
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}",
            headers=auth_headers
        )
    
    def test_create_account_missing_label(self, auth_headers):
        """Test creating account without required label"""
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json={"notes": "Missing label"},
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] is False
        assert "Label is required" in data.get("error", "")
    
    def test_update_account(self, auth_headers):
        """Test updating a Twitter account"""
        # Create account first
        create_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json={"label": f"{TEST_PREFIX}Account_Update_Test"},
            headers=auth_headers
        )
        assert create_response.status_code == 201
        account_id = create_response.json()["data"]["_id"]
        
        # Update account
        update_payload = {
            "label": f"{TEST_PREFIX}Account_Updated",
            "notes": "Updated notes"
        }
        update_response = requests.patch(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}",
            json=update_payload,
            headers=auth_headers
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["ok"] is True
        assert data["data"]["label"] == update_payload["label"]
        assert data["data"]["notes"] == update_payload["notes"]
        
        # Verify by GET
        get_response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["data"]["label"] == update_payload["label"]
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}",
            headers=auth_headers
        )
    
    def test_enable_disable_account(self, auth_headers):
        """Test enabling and disabling an account"""
        # Create account
        create_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json={"label": f"{TEST_PREFIX}Account_Toggle_Test"},
            headers=auth_headers
        )
        assert create_response.status_code == 201, f"Create failed: {create_response.text}"
        account_id = create_response.json()["data"]["_id"]
        
        # Headers without Content-Type for empty POST
        post_headers = {"Authorization": auth_headers["Authorization"]}
        
        try:
            # Disable account
            disable_response = requests.post(
                f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}/disable",
                headers=post_headers
            )
            assert disable_response.status_code == 200, f"Disable failed: {disable_response.text}"
            assert disable_response.json()["data"]["status"] == "DISABLED"
            
            # Enable account
            enable_response = requests.post(
                f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}/enable",
                headers=post_headers
            )
            assert enable_response.status_code == 200, f"Enable failed: {enable_response.text}"
            assert enable_response.json()["data"]["status"] == "ACTIVE"
        finally:
            # Cleanup
            requests.delete(
                f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}",
                headers=auth_headers
            )
    
    def test_delete_account(self, auth_headers):
        """Test deleting a Twitter account"""
        # Create account
        create_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json={"label": f"{TEST_PREFIX}Account_Delete_Test"},
            headers=auth_headers
        )
        assert create_response.status_code == 201
        account_id = create_response.json()["data"]["_id"]
        
        # Delete account
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["ok"] is True
        
        # Verify deletion
        get_response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404
    
    def test_get_nonexistent_account(self, auth_headers):
        """Test getting a non-existent account"""
        response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/000000000000000000000000",
            headers=auth_headers
        )
        assert response.status_code == 404
        data = response.json()
        assert data["ok"] is False


class TestEgressSlots:
    """Egress slots CRUD tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Headers with auth token"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}"
        }
    
    def test_list_slots(self, auth_headers):
        """Test listing all egress slots"""
        response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        assert isinstance(data["data"], list)
        assert "total" in data
    
    def test_create_proxy_slot(self, auth_headers):
        """Test creating a PROXY type slot"""
        payload = {
            "label": f"{TEST_PREFIX}Proxy_Slot_Test",
            "type": "PROXY",
            "proxy": {
                "url": "http://test:pass@proxy.test.com:8080",
                "region": "US"
            },
            "limits": {"requestsPerHour": 100}
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ok"] is True
        assert data["data"]["label"] == payload["label"]
        assert data["data"]["type"] == "PROXY"
        assert data["data"]["enabled"] is True
        
        slot_id = data["data"]["_id"]
        
        # Verify by GET
        get_response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["data"]["label"] == payload["label"]
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            headers=auth_headers
        )
    
    def test_create_worker_slot(self, auth_headers):
        """Test creating a REMOTE_WORKER type slot"""
        payload = {
            "label": f"{TEST_PREFIX}Worker_Slot_Test",
            "type": "REMOTE_WORKER",
            "worker": {
                "baseUrl": "https://parser-test.up.railway.app",
                "region": "EU"
            },
            "limits": {"requestsPerHour": 150}
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ok"] is True
        assert data["data"]["type"] == "REMOTE_WORKER"
        
        slot_id = data["data"]["_id"]
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            headers=auth_headers
        )
    
    def test_create_slot_missing_label(self, auth_headers):
        """Test creating slot without required label"""
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={"type": "PROXY"},
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] is False
    
    def test_create_slot_invalid_type(self, auth_headers):
        """Test creating slot with invalid type"""
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={"label": "Test", "type": "INVALID"},
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] is False
    
    def test_create_worker_slot_missing_url(self, auth_headers):
        """Test creating REMOTE_WORKER slot without baseUrl"""
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "label": f"{TEST_PREFIX}Worker_No_URL",
                "type": "REMOTE_WORKER"
            },
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] is False
        # Check for baseurl in error message (case insensitive)
        assert "baseurl" in data.get("error", "").lower()
    
    def test_update_slot(self, auth_headers):
        """Test updating an egress slot"""
        # Create slot
        create_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "label": f"{TEST_PREFIX}Slot_Update_Test",
                "type": "PROXY"
            },
            headers=auth_headers
        )
        assert create_response.status_code == 201
        slot_id = create_response.json()["data"]["_id"]
        
        # Update slot
        update_payload = {
            "label": f"{TEST_PREFIX}Slot_Updated",
            "limits": {"requestsPerHour": 300}
        }
        update_response = requests.patch(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            json=update_payload,
            headers=auth_headers
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["ok"] is True
        assert data["data"]["label"] == update_payload["label"]
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            headers=auth_headers
        )
    
    def test_enable_disable_slot(self, auth_headers):
        """Test enabling and disabling a slot"""
        # Create slot
        create_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "label": f"{TEST_PREFIX}Slot_Toggle_Test",
                "type": "PROXY"
            },
            headers=auth_headers
        )
        assert create_response.status_code == 201, f"Create failed: {create_response.text}"
        slot_id = create_response.json()["data"]["_id"]
        
        # Headers without Content-Type for empty POST
        post_headers = {"Authorization": auth_headers["Authorization"]}
        
        try:
            # Disable slot
            disable_response = requests.post(
                f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}/disable",
                headers=post_headers
            )
            assert disable_response.status_code == 200, f"Disable failed: {disable_response.text}"
            assert disable_response.json()["data"]["enabled"] is False
            
            # Enable slot
            enable_response = requests.post(
                f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}/enable",
                headers=post_headers
            )
            assert enable_response.status_code == 200, f"Enable failed: {enable_response.text}"
            assert enable_response.json()["data"]["enabled"] is True
        finally:
            # Cleanup
            requests.delete(
                f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
                headers=auth_headers
            )
    
    def test_bind_unbind_account(self, auth_headers):
        """Test binding and unbinding account to slot"""
        # Create test account for this test
        account_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json={"label": f"{TEST_PREFIX}Account_For_Bind_Test"},
            headers=auth_headers
        )
        assert account_response.status_code == 201, f"Account create failed: {account_response.text}"
        test_account = account_response.json()["data"]
        
        # Create slot
        create_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "label": f"{TEST_PREFIX}Slot_Bind_Test",
                "type": "PROXY"
            },
            headers=auth_headers
        )
        assert create_response.status_code == 201, f"Slot create failed: {create_response.text}"
        slot_id = create_response.json()["data"]["_id"]
        
        # Headers without Content-Type for empty POST
        post_headers = {"Authorization": auth_headers["Authorization"]}
        
        try:
            # Bind account
            bind_response = requests.post(
                f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}/bind-account",
                json={"accountId": test_account["_id"]},
                headers=auth_headers
            )
            assert bind_response.status_code == 200, f"Bind failed: {bind_response.text}"
            data = bind_response.json()
            assert data["ok"] is True
            assert data["data"]["accountId"] == test_account["_id"]
            assert data["data"]["accountLabel"] == test_account["label"]
            
            # Unbind account (no body needed)
            unbind_response = requests.post(
                f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}/unbind-account",
                headers=post_headers
            )
            assert unbind_response.status_code == 200, f"Unbind failed: {unbind_response.text}"
            unbind_data = unbind_response.json()
            assert unbind_data["ok"] is True
            assert unbind_data["data"].get("accountId") is None
        finally:
            # Cleanup
            requests.delete(
                f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
                headers=auth_headers
            )
            requests.delete(
                f"{BASE_URL}/api/admin/twitter-parser/accounts/{test_account['_id']}",
                headers=auth_headers
            )
    
    def test_bind_missing_account_id(self, auth_headers):
        """Test binding without accountId"""
        # Create slot
        create_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "label": f"{TEST_PREFIX}Slot_Bind_NoID",
                "type": "PROXY"
            },
            headers=auth_headers
        )
        assert create_response.status_code == 201
        slot_id = create_response.json()["data"]["_id"]
        
        # Try to bind without accountId
        bind_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}/bind-account",
            json={},
            headers=auth_headers
        )
        assert bind_response.status_code == 400
        assert bind_response.json()["ok"] is False
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            headers=auth_headers
        )
    
    def test_reset_usage_window(self, auth_headers):
        """Test resetting slot usage window"""
        # Create slot
        create_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "label": f"{TEST_PREFIX}Slot_Reset_Test",
                "type": "PROXY"
            },
            headers=auth_headers
        )
        assert create_response.status_code == 201, f"Create failed: {create_response.text}"
        slot_id = create_response.json()["data"]["_id"]
        
        # Headers without Content-Type for empty POST
        post_headers = {"Authorization": auth_headers["Authorization"]}
        
        try:
            # Reset window
            reset_response = requests.post(
                f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}/reset-window",
                headers=post_headers
            )
            assert reset_response.status_code == 200, f"Reset failed: {reset_response.text}"
            data = reset_response.json()
            assert data["ok"] is True
            assert "Usage window reset" in data.get("message", "")
        finally:
            # Cleanup
            requests.delete(
                f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
                headers=auth_headers
            )
    
    def test_delete_slot(self, auth_headers):
        """Test deleting an egress slot"""
        # Create slot
        create_response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "label": f"{TEST_PREFIX}Slot_Delete_Test",
                "type": "PROXY"
            },
            headers=auth_headers
        )
        assert create_response.status_code == 201
        slot_id = create_response.json()["data"]["_id"]
        
        # Delete slot
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["ok"] is True
        
        # Verify deletion
        get_response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404


class TestParserMonitor:
    """Parser monitor endpoint tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Headers with auth token"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}"
        }
    
    def test_get_monitor_stats(self, auth_headers):
        """Test getting parser monitor statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/twitter-parser/monitor",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        # Verify all expected fields
        monitor_data = data["data"]
        expected_fields = [
            "totalAccounts",
            "activeAccounts",
            "totalSlots",
            "enabledSlots",
            "healthySlots",
            "degradedSlots",
            "errorSlots",
            "totalCapacityPerHour",
            "usedThisHour",
            "availableThisHour"
        ]
        for field in expected_fields:
            assert field in monitor_data, f"Missing field: {field}"
            assert isinstance(monitor_data[field], int), f"Field {field} should be int"


# Cleanup fixture to remove any leftover test data
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Cleanup any TEST_ prefixed data after all tests"""
    yield
    
    # Get token
    response = requests.post(
        f"{BASE_URL}/api/admin/auth/login",
        json={"username": "admin", "password": "admin12345"},
        headers={"Content-Type": "application/json"}
    )
    if response.status_code != 200:
        return
    
    token = response.json()["token"]
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # Cleanup accounts
    accounts_response = requests.get(
        f"{BASE_URL}/api/admin/twitter-parser/accounts",
        headers=headers
    )
    if accounts_response.status_code == 200:
        for account in accounts_response.json().get("data", []):
            if account.get("label", "").startswith(TEST_PREFIX):
                requests.delete(
                    f"{BASE_URL}/api/admin/twitter-parser/accounts/{account['_id']}",
                    headers=headers
                )
    
    # Cleanup slots
    slots_response = requests.get(
        f"{BASE_URL}/api/admin/twitter-parser/slots",
        headers=headers
    )
    if slots_response.status_code == 200:
        for slot in slots_response.json().get("data", []):
            if slot.get("label", "").startswith(TEST_PREFIX):
                requests.delete(
                    f"{BASE_URL}/api/admin/twitter-parser/slots/{slot['_id']}",
                    headers=headers
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
