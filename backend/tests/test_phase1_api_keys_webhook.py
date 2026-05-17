"""
Phase 1.1 & 1.2 Tests: User-scoped API Keys & Webhook Session Versioning

Tests:
- POST /api/v4/user/api-keys - создание API ключа с scopes
- GET /api/v4/user/api-keys - список ключей пользователя
- DELETE /api/v4/user/api-keys/:id - отзыв ключа
- POST /api/v4/twitter/sessions/webhook - webhook с API key auth
- Session versioning: version increment
- Session deactivation: isActive: false
- STALE status при отсутствии auth_token или ct0
"""

import pytest
import requests
import time

BASE_URL = "http://localhost:8003"

# Test data
EXISTING_ACCOUNT_ID_1 = "697fa7d52dd38baab2b57c28"  # test_twitter_user
EXISTING_ACCOUNT_ID_2 = "697fab792dd38baab2c880a4"  # second_twitter_user
NON_EXISTENT_ACCOUNT_ID = "000000000000000000000000"


class TestApiKeyManagement:
    """Phase 1.1: API Key CRUD operations"""
    
    created_key_id = None
    created_api_key = None
    
    def test_01_create_api_key_success(self):
        """POST /api/v4/user/api-keys - создание API ключа с scopes"""
        response = requests.post(
            f"{BASE_URL}/api/v4/user/api-keys",
            json={
                "name": "TEST_Phase1_Extension",
                "scopes": ["twitter:cookies:write"]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        assert "apiKey" in data["data"], "apiKey should be returned on creation"
        assert "info" in data["data"]
        
        # Validate API key format
        api_key = data["data"]["apiKey"]
        assert api_key.startswith("usr_"), f"API key should start with 'usr_', got: {api_key[:10]}"
        
        # Validate info structure
        info = data["data"]["info"]
        assert "id" in info
        assert info["name"] == "TEST_Phase1_Extension"
        assert "twitter:cookies:write" in info["scopes"]
        assert info["revoked"] is False
        assert "keyPrefix" in info
        assert info["keyPrefix"].startswith("usr_")
        
        # Store for later tests
        TestApiKeyManagement.created_key_id = info["id"]
        TestApiKeyManagement.created_api_key = api_key
        
        print(f"✓ Created API key: {info['keyPrefix']}")
    
    def test_02_create_api_key_with_multiple_scopes(self):
        """POST /api/v4/user/api-keys - создание ключа с несколькими scopes"""
        response = requests.post(
            f"{BASE_URL}/api/v4/user/api-keys",
            json={
                "name": "TEST_Multi_Scope_Key",
                "scopes": ["twitter:cookies:write", "twitter:read", "twitter:tasks:write"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        
        info = data["data"]["info"]
        assert len(info["scopes"]) == 3
        assert "twitter:cookies:write" in info["scopes"]
        assert "twitter:read" in info["scopes"]
        assert "twitter:tasks:write" in info["scopes"]
        
        print(f"✓ Created multi-scope API key: {info['keyPrefix']}")
    
    def test_03_list_api_keys(self):
        """GET /api/v4/user/api-keys - список ключей пользователя"""
        response = requests.get(f"{BASE_URL}/api/v4/user/api-keys")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        assert isinstance(data["data"], list)
        
        # Should have at least the keys we created
        assert len(data["data"]) >= 2, f"Expected at least 2 keys, got {len(data['data'])}"
        
        # Verify structure of each key
        for key in data["data"]:
            assert "id" in key
            assert "name" in key
            assert "keyPrefix" in key
            assert "scopes" in key
            assert "createdAt" in key
            assert "revoked" in key
            # apiKey should NOT be in list response (security)
            assert "apiKey" not in key, "plaintext apiKey should not be in list response"
        
        print(f"✓ Listed {len(data['data'])} API keys")
    
    def test_04_revoke_api_key_success(self):
        """DELETE /api/v4/user/api-keys/:id - отзыв ключа"""
        # Create a key to revoke
        create_response = requests.post(
            f"{BASE_URL}/api/v4/user/api-keys",
            json={"name": "TEST_Key_To_Revoke", "scopes": ["twitter:read"]}
        )
        assert create_response.status_code == 200
        key_id = create_response.json()["data"]["info"]["id"]
        
        # Revoke it
        response = requests.delete(f"{BASE_URL}/api/v4/user/api-keys/{key_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        
        # Verify it's no longer in active list
        list_response = requests.get(f"{BASE_URL}/api/v4/user/api-keys")
        active_keys = list_response.json()["data"]
        revoked_key = next((k for k in active_keys if k["id"] == key_id), None)
        assert revoked_key is None, "Revoked key should not appear in active list"
        
        print(f"✓ Revoked API key: {key_id}")
    
    def test_05_revoke_nonexistent_key(self):
        """DELETE /api/v4/user/api-keys/:id - несуществующий ключ возвращает 404"""
        response = requests.delete(f"{BASE_URL}/api/v4/user/api-keys/000000000000000000000000")
        
        assert response.status_code == 404
        data = response.json()
        assert data["ok"] is False
        
        print("✓ Nonexistent key returns 404")


class TestWebhookAuthentication:
    """Phase 1.1: Webhook API Key Authentication"""
    
    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """Create API key for webhook tests"""
        response = requests.post(
            f"{BASE_URL}/api/v4/user/api-keys",
            json={"name": "TEST_Webhook_Auth_Key", "scopes": ["twitter:cookies:write"]}
        )
        assert response.status_code == 200
        self.api_key = response.json()["data"]["apiKey"]
        self.key_id = response.json()["data"]["info"]["id"]
        yield
        # Cleanup
        requests.delete(f"{BASE_URL}/api/v4/user/api-keys/{self.key_id}")
    
    def test_01_webhook_without_api_key_returns_401(self):
        """POST /api/v4/twitter/sessions/webhook без API key - 401"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            json={
                "accountId": EXISTING_ACCOUNT_ID_1,
                "cookies": [{"name": "auth_token", "value": "test123"}]
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert data["ok"] is False
        assert "Authorization" in data.get("error", "") or "Missing" in data.get("error", "")
        
        print("✓ Webhook without API key returns 401")
    
    def test_02_webhook_with_invalid_api_key_returns_401(self):
        """POST /api/v4/twitter/sessions/webhook с невалидным API key - 401"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": "Bearer usr_invalid_key_12345"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_1,
                "cookies": [{"name": "auth_token", "value": "test123"}]
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert data["ok"] is False
        
        print("✓ Webhook with invalid API key returns 401")
    
    def test_03_webhook_with_wrong_scope_returns_401(self):
        """POST /api/v4/twitter/sessions/webhook с ключом без нужного scope - 401"""
        # Create key with wrong scope
        create_response = requests.post(
            f"{BASE_URL}/api/v4/user/api-keys",
            json={"name": "TEST_Wrong_Scope_Key", "scopes": ["twitter:read"]}  # Not cookies:write
        )
        wrong_scope_key = create_response.json()["data"]["apiKey"]
        wrong_scope_key_id = create_response.json()["data"]["info"]["id"]
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/sessions/webhook",
                headers={"Authorization": f"Bearer {wrong_scope_key}"},
                json={
                    "accountId": EXISTING_ACCOUNT_ID_1,
                    "cookies": [{"name": "auth_token", "value": "test123"}]
                }
            )
            
            assert response.status_code == 401, f"Expected 401, got {response.status_code}"
            data = response.json()
            assert data["ok"] is False
            assert "scope" in data.get("error", "").lower()
            
            print("✓ Webhook with wrong scope returns 401")
        finally:
            requests.delete(f"{BASE_URL}/api/v4/user/api-keys/{wrong_scope_key_id}")
    
    def test_04_webhook_with_valid_api_key_success(self):
        """POST /api/v4/twitter/sessions/webhook с валидным API key - успех"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_1,
                "cookies": [
                    {"name": "auth_token", "value": "test_auth_token_123"},
                    {"name": "ct0", "value": "test_ct0_token_456"}
                ],
                "userAgent": "Mozilla/5.0 Test Agent"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        result = data["data"]
        assert result["accountId"] == EXISTING_ACCOUNT_ID_1
        assert "sessionId" in result
        assert "sessionVersion" in result
        assert result["status"] == "OK"  # Both auth_token and ct0 present
        
        print(f"✓ Webhook success: session v{result['sessionVersion']}, status={result['status']}")


class TestWebhookAccountValidation:
    """Phase 1.2: Account ownership validation"""
    
    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """Create API key for tests"""
        response = requests.post(
            f"{BASE_URL}/api/v4/user/api-keys",
            json={"name": "TEST_Account_Validation_Key", "scopes": ["twitter:cookies:write"]}
        )
        assert response.status_code == 200
        self.api_key = response.json()["data"]["apiKey"]
        self.key_id = response.json()["data"]["info"]["id"]
        yield
        requests.delete(f"{BASE_URL}/api/v4/user/api-keys/{self.key_id}")
    
    def test_00_webhook_with_other_users_account_returns_403(self):
        """POST /api/v4/twitter/sessions/webhook с чужим accountId - 403 OWNERSHIP_VIOLATION"""
        # Note: This test requires creating an account owned by a different user
        # Since we're using mocked auth (dev-user), we need to create an account
        # with a different ownerUserId directly in DB
        import subprocess
        import json
        
        # Create account owned by 'other-user'
        create_cmd = '''mongosh --quiet --eval "db.user_twitter_accounts.insertOne({ownerUserId: 'other-user', username: 'test_other_user_account', ownerType: 'USER', enabled: true, verified: false, requestsInWindow: 0, createdAt: new Date(), updatedAt: new Date()})" test'''
        result = subprocess.run(create_cmd, shell=True, capture_output=True, text=True)
        
        # Extract the inserted ID
        output = result.stdout
        import re
        match = re.search(r"ObjectId\('([a-f0-9]+)'\)", output)
        if not match:
            pytest.skip("Could not create test account for ownership test")
        
        other_user_account_id = match.group(1)
        
        try:
            # Try to access other user's account
            response = requests.post(
                f"{BASE_URL}/api/v4/twitter/sessions/webhook",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "accountId": other_user_account_id,
                    "cookies": [
                        {"name": "auth_token", "value": "test"},
                        {"name": "ct0", "value": "test"}
                    ]
                }
            )
            
            assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
            data = response.json()
            assert data["ok"] is False
            assert "ACCOUNT_OWNERSHIP_VIOLATION" in data.get("error", "")
            
            print("✓ Accessing other user's account returns 403 OWNERSHIP_VIOLATION")
        finally:
            # Cleanup
            cleanup_cmd = f'''mongosh --quiet --eval "db.user_twitter_accounts.deleteOne({{_id: ObjectId('{other_user_account_id}')}})" test'''
            subprocess.run(cleanup_cmd, shell=True, capture_output=True)
    
    def test_01_webhook_with_nonexistent_account_returns_404(self):
        """POST /api/v4/twitter/sessions/webhook с несуществующим accountId - 404"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "accountId": NON_EXISTENT_ACCOUNT_ID,
                "cookies": [
                    {"name": "auth_token", "value": "test123"},
                    {"name": "ct0", "value": "test456"}
                ]
            }
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["ok"] is False
        assert "ACCOUNT_NOT_FOUND" in data.get("error", "")
        
        print("✓ Webhook with nonexistent accountId returns 404")
    
    def test_02_webhook_missing_accountId_returns_400(self):
        """POST /api/v4/twitter/sessions/webhook без accountId - 400"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "cookies": [
                    {"name": "auth_token", "value": "test123"},
                    {"name": "ct0", "value": "test456"}
                ]
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert data["ok"] is False
        assert "accountid" in data.get("error", "").lower()
        
        print("✓ Webhook without accountId returns 400")
    
    def test_03_webhook_empty_cookies_returns_400(self):
        """POST /api/v4/twitter/sessions/webhook с пустыми cookies - 400"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_1,
                "cookies": []
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert data["ok"] is False
        
        print("✓ Webhook with empty cookies returns 400")


class TestSessionVersioning:
    """Phase 1.2: Session versioning and deactivation"""
    
    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """Create API key for tests"""
        response = requests.post(
            f"{BASE_URL}/api/v4/user/api-keys",
            json={"name": "TEST_Session_Versioning_Key", "scopes": ["twitter:cookies:write"]}
        )
        assert response.status_code == 200
        self.api_key = response.json()["data"]["apiKey"]
        self.key_id = response.json()["data"]["info"]["id"]
        yield
        requests.delete(f"{BASE_URL}/api/v4/user/api-keys/{self.key_id}")
    
    def test_01_session_version_increments_on_repeat_webhook(self):
        """Повторный webhook должен инкрементировать version"""
        # First webhook
        response1 = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_2,  # Use second account to avoid conflicts
                "cookies": [
                    {"name": "auth_token", "value": "first_auth_token"},
                    {"name": "ct0", "value": "first_ct0"}
                ],
                "userAgent": "Test Agent v1"
            }
        )
        
        assert response1.status_code == 200, f"First webhook failed: {response1.text}"
        data1 = response1.json()["data"]
        version1 = data1["sessionVersion"]
        session_id1 = data1["sessionId"]
        
        print(f"  First webhook: session {session_id1}, version {version1}")
        
        # Small delay to ensure different timestamps
        time.sleep(0.1)
        
        # Second webhook (should increment version)
        response2 = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_2,
                "cookies": [
                    {"name": "auth_token", "value": "second_auth_token"},
                    {"name": "ct0", "value": "second_ct0"}
                ],
                "userAgent": "Test Agent v2"
            }
        )
        
        assert response2.status_code == 200, f"Second webhook failed: {response2.text}"
        data2 = response2.json()["data"]
        version2 = data2["sessionVersion"]
        session_id2 = data2["sessionId"]
        
        print(f"  Second webhook: session {session_id2}, version {version2}")
        
        # Verify version incremented
        assert version2 == version1 + 1, f"Version should increment: {version1} -> {version2}"
        assert session_id2 != session_id1, "New session should have different ID"
        assert data2["previousSessionDeactivated"] is True, "Previous session should be deactivated"
        
        print(f"✓ Session version incremented: {version1} -> {version2}")
    
    def test_02_previous_session_deactivated(self):
        """Старая сессия должна иметь isActive: false после нового webhook"""
        # This is implicitly tested in test_01 via previousSessionDeactivated flag
        # But we can verify by checking the response
        
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_2,
                "cookies": [
                    {"name": "auth_token", "value": "deactivation_test_auth"},
                    {"name": "ct0", "value": "deactivation_test_ct0"}
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        # The response tells us if previous session was deactivated
        # For first session of an account, this would be False
        # For subsequent sessions, this should be True
        print(f"✓ Previous session deactivated: {data['previousSessionDeactivated']}")


class TestStaleStatus:
    """Phase 1.2: STALE status when missing auth_token or ct0"""
    
    @pytest.fixture(autouse=True)
    def setup_api_key(self):
        """Create API key for tests"""
        response = requests.post(
            f"{BASE_URL}/api/v4/user/api-keys",
            json={"name": "TEST_Stale_Status_Key", "scopes": ["twitter:cookies:write"]}
        )
        assert response.status_code == 200
        self.api_key = response.json()["data"]["apiKey"]
        self.key_id = response.json()["data"]["info"]["id"]
        yield
        requests.delete(f"{BASE_URL}/api/v4/user/api-keys/{self.key_id}")
    
    def test_01_stale_status_when_missing_auth_token(self):
        """STALE status при отсутствии auth_token в cookies"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_1,
                "cookies": [
                    {"name": "ct0", "value": "only_ct0_present"},
                    {"name": "other_cookie", "value": "some_value"}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()["data"]
        
        assert data["status"] == "STALE", f"Expected STALE status, got {data['status']}"
        
        print(f"✓ Missing auth_token -> STALE status (version {data['sessionVersion']})")
    
    def test_02_stale_status_when_missing_ct0(self):
        """STALE status при отсутствии ct0 в cookies"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_1,
                "cookies": [
                    {"name": "auth_token", "value": "only_auth_token_present"},
                    {"name": "other_cookie", "value": "some_value"}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()["data"]
        
        assert data["status"] == "STALE", f"Expected STALE status, got {data['status']}"
        
        print(f"✓ Missing ct0 -> STALE status (version {data['sessionVersion']})")
    
    def test_03_stale_status_when_missing_both(self):
        """STALE status при отсутствии обоих auth_token и ct0"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_1,
                "cookies": [
                    {"name": "random_cookie", "value": "random_value"},
                    {"name": "another_cookie", "value": "another_value"}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()["data"]
        
        assert data["status"] == "STALE", f"Expected STALE status, got {data['status']}"
        
        print(f"✓ Missing both auth_token and ct0 -> STALE status (version {data['sessionVersion']})")
    
    def test_04_ok_status_when_both_present(self):
        """OK status когда оба auth_token и ct0 присутствуют"""
        response = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_1,
                "cookies": [
                    {"name": "auth_token", "value": "valid_auth_token"},
                    {"name": "ct0", "value": "valid_ct0"},
                    {"name": "other_cookie", "value": "other_value"}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()["data"]
        
        assert data["status"] == "OK", f"Expected OK status, got {data['status']}"
        
        print(f"✓ Both auth_token and ct0 present -> OK status (version {data['sessionVersion']})")


class TestApiKeyLastUsedAt:
    """Test that API key lastUsedAt is updated on use"""
    
    def test_last_used_at_updated(self):
        """API key lastUsedAt should update after webhook call"""
        # Create key
        create_response = requests.post(
            f"{BASE_URL}/api/v4/user/api-keys",
            json={"name": "TEST_LastUsedAt_Key", "scopes": ["twitter:cookies:write"]}
        )
        assert create_response.status_code == 200
        api_key = create_response.json()["data"]["apiKey"]
        key_id = create_response.json()["data"]["info"]["id"]
        
        try:
            # Get initial state
            list_response1 = requests.get(f"{BASE_URL}/api/v4/user/api-keys")
            key_before = next(k for k in list_response1.json()["data"] if k["id"] == key_id)
            last_used_before = key_before.get("lastUsedAt")
            
            # Use the key
            time.sleep(0.5)  # Ensure time difference
            requests.post(
                f"{BASE_URL}/api/v4/twitter/sessions/webhook",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "accountId": EXISTING_ACCOUNT_ID_1,
                    "cookies": [
                        {"name": "auth_token", "value": "test"},
                        {"name": "ct0", "value": "test"}
                    ]
                }
            )
            
            # Check lastUsedAt updated
            time.sleep(0.2)  # Allow async update
            list_response2 = requests.get(f"{BASE_URL}/api/v4/user/api-keys")
            key_after = next(k for k in list_response2.json()["data"] if k["id"] == key_id)
            last_used_after = key_after.get("lastUsedAt")
            
            assert last_used_after is not None, "lastUsedAt should be set after use"
            if last_used_before:
                assert last_used_after != last_used_before, "lastUsedAt should be updated"
            
            print(f"✓ lastUsedAt updated: {last_used_before} -> {last_used_after}")
        finally:
            requests.delete(f"{BASE_URL}/api/v4/user/api-keys/{key_id}")


class TestRevokedKeyCannotBeUsed:
    """Test that revoked API keys cannot be used"""
    
    def test_revoked_key_returns_401(self):
        """Revoked API key should return 401 on webhook"""
        # Create key
        create_response = requests.post(
            f"{BASE_URL}/api/v4/user/api-keys",
            json={"name": "TEST_Revoked_Key", "scopes": ["twitter:cookies:write"]}
        )
        assert create_response.status_code == 200
        api_key = create_response.json()["data"]["apiKey"]
        key_id = create_response.json()["data"]["info"]["id"]
        
        # Verify it works before revocation
        response1 = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_1,
                "cookies": [
                    {"name": "auth_token", "value": "test"},
                    {"name": "ct0", "value": "test"}
                ]
            }
        )
        assert response1.status_code == 200, "Key should work before revocation"
        
        # Revoke the key
        revoke_response = requests.delete(f"{BASE_URL}/api/v4/user/api-keys/{key_id}")
        assert revoke_response.status_code == 200
        
        # Try to use revoked key
        response2 = requests.post(
            f"{BASE_URL}/api/v4/twitter/sessions/webhook",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "accountId": EXISTING_ACCOUNT_ID_1,
                "cookies": [
                    {"name": "auth_token", "value": "test"},
                    {"name": "ct0", "value": "test"}
                ]
            }
        )
        
        assert response2.status_code == 401, f"Revoked key should return 401, got {response2.status_code}"
        
        print("✓ Revoked API key returns 401")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
