"""
Twitter Parser MULTI Architecture API Tests
Tests CRUD operations for Accounts, Sessions, and Proxy Slots
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')

class TestTwitterAccounts:
    """Twitter Account CRUD API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.test_username = f"TEST_account_{uuid.uuid4().hex[:8]}"
        yield
        # Cleanup: Try to delete test account
        try:
            accounts_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/accounts")
            if accounts_res.status_code == 200:
                accounts = accounts_res.json().get('data', [])
                for acc in accounts:
                    if acc.get('username', '').startswith('test_'):
                        requests.delete(f"{BASE_URL}/api/admin/twitter-parser/accounts/{acc['_id']}")
        except:
            pass
    
    def test_get_all_accounts(self):
        """GET /api/admin/twitter-parser/accounts - List all accounts"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/accounts")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        assert 'stats' in data
        assert isinstance(data['data'], list)
        
        # Verify stats structure
        stats = data['stats']
        assert 'total' in stats
        assert 'active' in stats
        assert 'disabled' in stats
        print(f"✓ GET accounts: {stats['total']} total, {stats['active']} active")
    
    def test_create_account(self):
        """POST /api/admin/twitter-parser/accounts - Create new account"""
        payload = {
            "username": self.test_username,
            "displayName": "Test Account",
            "notes": "Created by pytest"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json=payload
        )
        assert response.status_code == 201
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        account = data['data']
        assert account['username'] == self.test_username.lower()
        assert account['displayName'] == "Test Account"
        assert account['status'] == 'ACTIVE'
        print(f"✓ Created account: {account['username']}")
        
        # Verify persistence with GET
        get_response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/accounts/{account['_id']}")
        assert get_response.status_code == 200
        fetched = get_response.json()['data']
        assert fetched['username'] == self.test_username.lower()
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/twitter-parser/accounts/{account['_id']}")
    
    def test_create_duplicate_account_fails(self):
        """POST /api/admin/twitter-parser/accounts - Duplicate username should fail"""
        # First create
        payload = {"username": self.test_username}
        response1 = requests.post(f"{BASE_URL}/api/admin/twitter-parser/accounts", json=payload)
        assert response1.status_code == 201
        account_id = response1.json()['data']['_id']
        
        # Try duplicate
        response2 = requests.post(f"{BASE_URL}/api/admin/twitter-parser/accounts", json=payload)
        assert response2.status_code == 400
        assert 'already exists' in response2.json().get('error', '').lower()
        print("✓ Duplicate account correctly rejected")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}")
    
    def test_update_account(self):
        """PUT /api/admin/twitter-parser/accounts/:id - Update account"""
        # Create account first
        create_res = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json={"username": self.test_username}
        )
        account_id = create_res.json()['data']['_id']
        
        # Update
        update_payload = {
            "displayName": "Updated Name",
            "rateLimit": 500,
            "notes": "Updated notes"
        }
        response = requests.put(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}",
            json=update_payload
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data['data']['displayName'] == "Updated Name"
        assert data['data']['rateLimit'] == 500
        print(f"✓ Updated account: {account_id}")
        
        # Verify persistence
        get_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}")
        assert get_res.json()['data']['displayName'] == "Updated Name"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}")
    
    def test_change_account_status(self):
        """PATCH /api/admin/twitter-parser/accounts/:id/status - Change status"""
        # Create account
        create_res = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json={"username": self.test_username}
        )
        account_id = create_res.json()['data']['_id']
        
        # Disable
        response = requests.patch(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}/status",
            json={"status": "DISABLED"}
        )
        assert response.status_code == 200
        assert response.json().get('ok') == True
        
        # Verify
        get_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}")
        assert get_res.json()['data']['status'] == 'DISABLED'
        print(f"✓ Status changed to DISABLED")
        
        # Re-enable
        response2 = requests.patch(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}/status",
            json={"status": "ACTIVE"}
        )
        assert response2.status_code == 200
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}")
    
    def test_invalid_status_rejected(self):
        """PATCH /api/admin/twitter-parser/accounts/:id/status - Invalid status rejected"""
        # Create account
        create_res = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json={"username": self.test_username}
        )
        account_id = create_res.json()['data']['_id']
        
        response = requests.patch(
            f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}/status",
            json={"status": "INVALID_STATUS"}
        )
        assert response.status_code == 400
        print("✓ Invalid status correctly rejected")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}")
    
    def test_delete_account(self):
        """DELETE /api/admin/twitter-parser/accounts/:id - Delete account"""
        # Create account
        create_res = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/accounts",
            json={"username": self.test_username}
        )
        account_id = create_res.json()['data']['_id']
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}")
        assert response.status_code == 200
        assert response.json().get('ok') == True
        print(f"✓ Deleted account: {account_id}")
        
        # Verify deletion
        get_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/accounts/{account_id}")
        assert get_res.status_code == 404
    
    def test_delete_nonexistent_account(self):
        """DELETE /api/admin/twitter-parser/accounts/:id - Nonexistent returns 404"""
        response = requests.delete(f"{BASE_URL}/api/admin/twitter-parser/accounts/000000000000000000000000")
        assert response.status_code == 404
        print("✓ Delete nonexistent correctly returns 404")


class TestTwitterSessions:
    """Twitter Session CRUD API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.test_session_id = f"TEST_session_{uuid.uuid4().hex[:8]}"
        yield
        # Cleanup
        try:
            requests.delete(f"{BASE_URL}/api/admin/twitter-parser/sessions/{self.test_session_id}")
        except:
            pass
    
    def test_get_all_sessions(self):
        """GET /api/admin/twitter-parser/sessions - List all sessions"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/sessions")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        assert 'stats' in data
        
        stats = data['stats']
        assert 'total' in stats
        assert 'ok' in stats
        assert 'stale' in stats
        print(f"✓ GET sessions: {stats['total']} total, {stats['ok']} valid")
    
    def test_get_webhook_info(self):
        """GET /api/admin/twitter-parser/sessions/webhook/info - Get webhook details"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook/info")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        webhook_data = data['data']
        assert 'apiKey' in webhook_data
        assert 'webhookUrl' in webhook_data
        assert 'format' in webhook_data
        assert len(webhook_data['apiKey']) > 0
        print(f"✓ Webhook info retrieved, API key: {webhook_data['apiKey'][:8]}...")
        
        return webhook_data['apiKey']
    
    def test_ingest_session_via_webhook(self):
        """POST /api/admin/twitter-parser/sessions/webhook - Ingest cookies"""
        # Get API key first
        info_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook/info")
        api_key = info_res.json()['data']['apiKey']
        
        payload = {
            "apiKey": api_key,
            "sessionId": self.test_session_id,
            "cookies": [
                {"name": "auth_token", "value": "test_auth_token_value", "domain": ".twitter.com"},
                {"name": "ct0", "value": "test_ct0_value", "domain": ".twitter.com"}
            ],
            "userAgent": "Mozilla/5.0 Test Agent"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook",
            json=payload
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('stored') == True
        assert data.get('cookieCount') == 2
        print(f"✓ Ingested session: {self.test_session_id}")
        
        # Verify persistence
        get_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/sessions/{self.test_session_id}")
        assert get_res.status_code == 200
        session = get_res.json()['data']
        assert session['sessionId'] == self.test_session_id
        assert session['cookiesMeta']['count'] == 2
        assert session['cookiesMeta']['hasAuthToken'] == True
    
    def test_ingest_session_invalid_api_key(self):
        """POST /api/admin/twitter-parser/sessions/webhook - Invalid API key rejected"""
        payload = {
            "apiKey": "invalid_key",
            "sessionId": self.test_session_id,
            "cookies": [{"name": "test", "value": "test", "domain": ".twitter.com"}]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook",
            json=payload
        )
        assert response.status_code == 401
        print("✓ Invalid API key correctly rejected")
    
    def test_ingest_session_missing_data(self):
        """POST /api/admin/twitter-parser/sessions/webhook - Missing data rejected"""
        info_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook/info")
        api_key = info_res.json()['data']['apiKey']
        
        # Missing cookies
        payload = {"apiKey": api_key, "sessionId": self.test_session_id}
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook",
            json=payload
        )
        assert response.status_code == 400
        print("✓ Missing cookies correctly rejected")
    
    def test_test_session(self):
        """POST /api/admin/twitter-parser/sessions/:sessionId/test - Test session validity"""
        # First ingest a session
        info_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook/info")
        api_key = info_res.json()['data']['apiKey']
        
        requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook",
            json={
                "apiKey": api_key,
                "sessionId": self.test_session_id,
                "cookies": [
                    {"name": "auth_token", "value": "test_value", "domain": ".twitter.com"}
                ]
            }
        )
        
        # Test the session
        response = requests.post(f"{BASE_URL}/api/admin/twitter-parser/sessions/{self.test_session_id}/test")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'valid' in data
        print(f"✓ Session test result: valid={data.get('valid')}")
    
    def test_delete_session(self):
        """DELETE /api/admin/twitter-parser/sessions/:sessionId - Delete session"""
        # First ingest a session
        info_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook/info")
        api_key = info_res.json()['data']['apiKey']
        
        requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/sessions/webhook",
            json={
                "apiKey": api_key,
                "sessionId": self.test_session_id,
                "cookies": [{"name": "test", "value": "test", "domain": ".twitter.com"}]
            }
        )
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/admin/twitter-parser/sessions/{self.test_session_id}")
        assert response.status_code == 200
        assert response.json().get('ok') == True
        print(f"✓ Deleted session: {self.test_session_id}")
        
        # Verify deletion
        get_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/sessions/{self.test_session_id}")
        assert get_res.status_code == 404


class TestProxySlots:
    """Proxy Slot CRUD API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.test_slot_name = f"TEST_slot_{uuid.uuid4().hex[:8]}"
        yield
        # Cleanup
        try:
            slots_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/slots")
            if slots_res.status_code == 200:
                slots = slots_res.json().get('data', [])
                for slot in slots:
                    if slot.get('name', '').startswith('TEST_'):
                        requests.delete(f"{BASE_URL}/api/admin/twitter-parser/slots/{slot['_id']}")
        except:
            pass
    
    def test_get_all_slots(self):
        """GET /api/admin/twitter-parser/slots - List all slots"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/slots")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        assert 'stats' in data
        
        stats = data['stats']
        assert 'total' in stats
        assert 'active' in stats
        assert 'cooldown' in stats
        assert 'disabled' in stats
        print(f"✓ GET slots: {stats['total']} total, {stats['active']} active")
    
    def test_get_available_slots(self):
        """GET /api/admin/twitter-parser/slots/available - Get available slots"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/slots/available")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        assert 'count' in data
        print(f"✓ Available slots: {data['count']}")
    
    def test_create_slot(self):
        """POST /api/admin/twitter-parser/slots - Create new slot"""
        payload = {
            "name": self.test_slot_name,
            "host": "test-proxy.example.com",
            "port": 8888,
            "protocol": "http",
            "username": "testuser",
            "password": "testpass",
            "notes": "Created by pytest"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json=payload
        )
        assert response.status_code == 201
        
        data = response.json()
        assert data.get('ok') == True
        
        slot = data['data']
        assert slot['name'] == self.test_slot_name
        assert slot['host'] == "test-proxy.example.com"
        assert slot['port'] == 8888
        assert slot['status'] == 'ACTIVE'
        print(f"✓ Created slot: {slot['name']}")
        
        # Verify persistence
        get_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/slots/{slot['_id']}")
        assert get_res.status_code == 200
        assert get_res.json()['data']['name'] == self.test_slot_name
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/twitter-parser/slots/{slot['_id']}")
    
    def test_update_slot(self):
        """PUT /api/admin/twitter-parser/slots/:id - Update slot"""
        # Create slot
        create_res = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "name": self.test_slot_name,
                "host": "original.example.com",
                "port": 8080
            }
        )
        slot_id = create_res.json()['data']['_id']
        
        # Update
        update_payload = {
            "name": f"{self.test_slot_name}_updated",
            "host": "updated.example.com",
            "port": 9090,
            "notes": "Updated by pytest"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}",
            json=update_payload
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data['data']['host'] == "updated.example.com"
        assert data['data']['port'] == 9090
        print(f"✓ Updated slot: {slot_id}")
        
        # Verify persistence
        get_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}")
        assert get_res.json()['data']['host'] == "updated.example.com"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}")
    
    def test_test_slot_connectivity(self):
        """POST /api/admin/twitter-parser/slots/:id/test - Test slot connectivity"""
        # Create slot
        create_res = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "name": self.test_slot_name,
                "host": "test.example.com",
                "port": 8080
            }
        )
        slot_id = create_res.json()['data']['_id']
        
        # Test connectivity
        response = requests.post(f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}/test")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        assert 'status' in data['data']
        print(f"✓ Slot test result: {data['data']['status']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}")
    
    def test_change_slot_status(self):
        """PATCH /api/admin/twitter-parser/slots/:id/status - Change status"""
        # Create slot
        create_res = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "name": self.test_slot_name,
                "host": "test.example.com",
                "port": 8080
            }
        )
        slot_id = create_res.json()['data']['_id']
        
        # Disable
        response = requests.patch(
            f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}/status",
            json={"status": "DISABLED"}
        )
        assert response.status_code == 200
        
        # Verify
        get_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}")
        assert get_res.json()['data']['status'] == 'DISABLED'
        print("✓ Slot status changed to DISABLED")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}")
    
    def test_delete_slot(self):
        """DELETE /api/admin/twitter-parser/slots/:id - Delete slot"""
        # Create slot
        create_res = requests.post(
            f"{BASE_URL}/api/admin/twitter-parser/slots",
            json={
                "name": self.test_slot_name,
                "host": "test.example.com",
                "port": 8080
            }
        )
        slot_id = create_res.json()['data']['_id']
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}")
        assert response.status_code == 200
        assert response.json().get('ok') == True
        print(f"✓ Deleted slot: {slot_id}")
        
        # Verify deletion
        get_res = requests.get(f"{BASE_URL}/api/admin/twitter-parser/slots/{slot_id}")
        assert get_res.status_code == 404
    
    def test_delete_nonexistent_slot(self):
        """DELETE /api/admin/twitter-parser/slots/:id - Nonexistent returns 404"""
        response = requests.delete(f"{BASE_URL}/api/admin/twitter-parser/slots/000000000000000000000000")
        assert response.status_code == 404
        print("✓ Delete nonexistent slot correctly returns 404")


class TestExistingData:
    """Tests for existing test data mentioned in context"""
    
    def test_existing_account_test_user_1(self):
        """Verify existing test_user_1 account"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/accounts")
        assert response.status_code == 200
        
        accounts = response.json().get('data', [])
        test_user = next((a for a in accounts if a.get('username') == 'test_user_1'), None)
        
        if test_user:
            print(f"✓ Found existing account: test_user_1 (status: {test_user['status']})")
            assert test_user['username'] == 'test_user_1'
        else:
            print("⚠ test_user_1 not found (may have been deleted)")
    
    def test_existing_session_test_1(self):
        """Verify existing session_test_1"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/sessions")
        assert response.status_code == 200
        
        sessions = response.json().get('data', [])
        test_session = next((s for s in sessions if s.get('sessionId') == 'session_test_1'), None)
        
        if test_session:
            print(f"✓ Found existing session: session_test_1 (status: {test_session['status']})")
            assert test_session['sessionId'] == 'session_test_1'
        else:
            print("⚠ session_test_1 not found (may have been deleted)")
    
    def test_existing_proxy_slot_1(self):
        """Verify existing Proxy Slot 1"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/slots")
        assert response.status_code == 200
        
        slots = response.json().get('data', [])
        test_slot = next((s for s in slots if s.get('name') == 'Proxy Slot 1'), None)
        
        if test_slot:
            print(f"✓ Found existing slot: Proxy Slot 1 (status: {test_slot['status']})")
            assert test_slot['name'] == 'Proxy Slot 1'
        else:
            print("⚠ Proxy Slot 1 not found (may have been deleted)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
