"""
User Account Profile API Tests
Tests for: GET/PUT /api/user/profile, POST /api/user/avatar, GET /api/user/avatar/{user_id},
POST /api/user/2fa/setup, POST /api/user/2fa/verify, POST /api/user/2fa/disable
"""
import pytest
import requests
import os
import uuid
import pyotp
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test session token for authenticated requests (created directly in MongoDB)
TEST_USER_ID = f"test_user_{uuid.uuid4().hex[:8]}"
TEST_SESSION_TOKEN = f"sess_test_{uuid.uuid4().hex}"


@pytest.fixture(scope="module")
def mongo_client():
    """Get MongoDB client for test setup"""
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017")
    return client["intelligence_engine"]


@pytest.fixture(scope="module")
def test_user(mongo_client):
    """Create a test user and session in MongoDB for authenticated tests"""
    db = mongo_client
    
    # Create test user
    user_data = {
        "user_id": TEST_USER_ID,
        "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
        "name": "Test User",
        "picture": "",
        "plan_status": "free",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db["users"].insert_one(user_data)
    
    # Create session
    session_data = {
        "user_id": TEST_USER_ID,
        "session_token": TEST_SESSION_TOKEN,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db["user_sessions"].insert_one(session_data)
    
    yield {"user": user_data, "session_token": TEST_SESSION_TOKEN}
    
    # Cleanup
    db["users"].delete_one({"user_id": TEST_USER_ID})
    db["user_sessions"].delete_one({"session_token": TEST_SESSION_TOKEN})


class TestUserProfileUnauthenticated:
    """Tests for unauthenticated access to user profile endpoints"""
    
    def test_get_profile_returns_401_when_not_authenticated(self):
        """GET /api/user/profile returns 401 when not authenticated"""
        response = requests.get(f"{BASE_URL}/api/user/profile")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Not authenticated" in data["detail"]
        print("PASS: GET /api/user/profile returns 401 when not authenticated")
    
    def test_put_profile_returns_401_when_not_authenticated(self):
        """PUT /api/user/profile returns 401 when not authenticated"""
        response = requests.put(
            f"{BASE_URL}/api/user/profile",
            json={"nickname": "TestNick"}
        )
        assert response.status_code == 401
        print("PASS: PUT /api/user/profile returns 401 when not authenticated")
    
    def test_post_avatar_returns_401_when_not_authenticated(self):
        """POST /api/user/avatar returns 401 when not authenticated"""
        # Create a simple test image
        files = {'file': ('test.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, 'image/png')}
        response = requests.post(f"{BASE_URL}/api/user/avatar", files=files)
        assert response.status_code == 401
        print("PASS: POST /api/user/avatar returns 401 when not authenticated")
    
    def test_get_avatar_returns_404_when_no_avatar(self):
        """GET /api/user/avatar/{user_id} returns 404 when no avatar exists"""
        response = requests.get(f"{BASE_URL}/api/user/avatar/nonexistent_user_123")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "No avatar" in data["detail"]
        print("PASS: GET /api/user/avatar/{user_id} returns 404 when no avatar")
    
    def test_2fa_setup_returns_401_when_not_authenticated(self):
        """POST /api/user/2fa/setup returns 401 when not authenticated"""
        response = requests.post(f"{BASE_URL}/api/user/2fa/setup")
        assert response.status_code == 401
        print("PASS: POST /api/user/2fa/setup returns 401 when not authenticated")
    
    def test_2fa_verify_returns_401_when_not_authenticated(self):
        """POST /api/user/2fa/verify returns 401 when not authenticated"""
        response = requests.post(
            f"{BASE_URL}/api/user/2fa/verify",
            json={"code": "123456"}
        )
        assert response.status_code == 401
        print("PASS: POST /api/user/2fa/verify returns 401 when not authenticated")
    
    def test_2fa_disable_returns_401_when_not_authenticated(self):
        """POST /api/user/2fa/disable returns 401 when not authenticated"""
        response = requests.post(
            f"{BASE_URL}/api/user/2fa/disable",
            json={"code": "123456"}
        )
        assert response.status_code == 401
        print("PASS: POST /api/user/2fa/disable returns 401 when not authenticated")


class TestUserProfileAuthenticated:
    """Tests for authenticated access to user profile endpoints"""
    
    def test_get_profile_returns_user_data(self, test_user):
        """GET /api/user/profile returns user profile when authenticated"""
        headers = {"Authorization": f"Bearer {test_user['session_token']}"}
        response = requests.get(f"{BASE_URL}/api/user/profile", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "profile" in data
        profile = data["profile"]
        assert "user_id" in profile
        assert "email" in profile
        assert "totp_enabled" in profile
        assert profile["totp_enabled"] is False  # Initially disabled
        print("PASS: GET /api/user/profile returns user data when authenticated")
    
    def test_put_profile_updates_nickname(self, test_user):
        """PUT /api/user/profile updates nickname"""
        headers = {
            "Authorization": f"Bearer {test_user['session_token']}",
            "Content-Type": "application/json"
        }
        new_nickname = f"TestNick_{uuid.uuid4().hex[:4]}"
        response = requests.put(
            f"{BASE_URL}/api/user/profile",
            headers=headers,
            json={"nickname": new_nickname}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("nickname") == new_nickname
        print(f"PASS: PUT /api/user/profile updates nickname to '{new_nickname}'")
    
    def test_put_profile_rejects_empty_nickname(self, test_user):
        """PUT /api/user/profile rejects empty nickname"""
        headers = {
            "Authorization": f"Bearer {test_user['session_token']}",
            "Content-Type": "application/json"
        }
        response = requests.put(
            f"{BASE_URL}/api/user/profile",
            headers=headers,
            json={"nickname": ""}
        )
        assert response.status_code == 400
        print("PASS: PUT /api/user/profile rejects empty nickname")
    
    def test_put_profile_rejects_long_nickname(self, test_user):
        """PUT /api/user/profile rejects nickname > 50 chars"""
        headers = {
            "Authorization": f"Bearer {test_user['session_token']}",
            "Content-Type": "application/json"
        }
        long_nickname = "A" * 51
        response = requests.put(
            f"{BASE_URL}/api/user/profile",
            headers=headers,
            json={"nickname": long_nickname}
        )
        assert response.status_code == 400
        print("PASS: PUT /api/user/profile rejects nickname > 50 chars")


class TestUser2FA:
    """Tests for 2FA (TOTP) endpoints"""
    
    def test_2fa_setup_generates_secret_and_qr(self, test_user, mongo_client):
        """POST /api/user/2fa/setup generates TOTP secret and QR code"""
        # First ensure 2FA is not enabled
        mongo_client["users"].update_one(
            {"user_id": TEST_USER_ID},
            {"$unset": {"totp_enabled": "", "totp_secret": "", "totp_secret_pending": ""}}
        )
        
        headers = {"Authorization": f"Bearer {test_user['session_token']}"}
        response = requests.post(f"{BASE_URL}/api/user/2fa/setup", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "secret" in data
        assert "qr_code" in data
        assert "provisioning_uri" in data
        assert data["qr_code"].startswith("data:image/png;base64,")
        assert len(data["secret"]) == 32  # Base32 secret
        print("PASS: POST /api/user/2fa/setup generates TOTP secret and QR code")
        return data["secret"]
    
    def test_2fa_verify_enables_2fa_with_valid_code(self, test_user, mongo_client):
        """POST /api/user/2fa/verify enables 2FA with valid TOTP code"""
        # First setup 2FA
        mongo_client["users"].update_one(
            {"user_id": TEST_USER_ID},
            {"$unset": {"totp_enabled": "", "totp_secret": "", "totp_secret_pending": ""}}
        )
        
        headers = {"Authorization": f"Bearer {test_user['session_token']}"}
        setup_response = requests.post(f"{BASE_URL}/api/user/2fa/setup", headers=headers)
        assert setup_response.status_code == 200
        secret = setup_response.json()["secret"]
        
        # Generate valid TOTP code
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        
        # Verify with valid code
        headers["Content-Type"] = "application/json"
        response = requests.post(
            f"{BASE_URL}/api/user/2fa/verify",
            headers=headers,
            json={"code": valid_code}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "2FA enabled" in data.get("message", "")
        print("PASS: POST /api/user/2fa/verify enables 2FA with valid code")
    
    def test_2fa_verify_rejects_invalid_code(self, test_user, mongo_client):
        """POST /api/user/2fa/verify rejects invalid TOTP code"""
        # First setup 2FA
        mongo_client["users"].update_one(
            {"user_id": TEST_USER_ID},
            {"$unset": {"totp_enabled": "", "totp_secret": "", "totp_secret_pending": ""}}
        )
        
        headers = {"Authorization": f"Bearer {test_user['session_token']}"}
        setup_response = requests.post(f"{BASE_URL}/api/user/2fa/setup", headers=headers)
        assert setup_response.status_code == 200
        
        # Try to verify with invalid code
        headers["Content-Type"] = "application/json"
        response = requests.post(
            f"{BASE_URL}/api/user/2fa/verify",
            headers=headers,
            json={"code": "000000"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "Invalid code" in data.get("detail", "")
        print("PASS: POST /api/user/2fa/verify rejects invalid code")
    
    def test_2fa_disable_with_valid_code(self, test_user, mongo_client):
        """POST /api/user/2fa/disable disables 2FA with valid code"""
        # First enable 2FA
        mongo_client["users"].update_one(
            {"user_id": TEST_USER_ID},
            {"$unset": {"totp_enabled": "", "totp_secret": "", "totp_secret_pending": ""}}
        )
        
        headers = {"Authorization": f"Bearer {test_user['session_token']}"}
        setup_response = requests.post(f"{BASE_URL}/api/user/2fa/setup", headers=headers)
        secret = setup_response.json()["secret"]
        
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        
        headers["Content-Type"] = "application/json"
        # Enable 2FA first
        requests.post(
            f"{BASE_URL}/api/user/2fa/verify",
            headers=headers,
            json={"code": valid_code}
        )
        
        # Now disable with a new valid code
        import time
        time.sleep(1)  # Wait for new TOTP window
        new_code = totp.now()
        
        response = requests.post(
            f"{BASE_URL}/api/user/2fa/disable",
            headers=headers,
            json={"code": new_code}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "2FA disabled" in data.get("message", "")
        print("PASS: POST /api/user/2fa/disable disables 2FA with valid code")
    
    def test_2fa_setup_fails_when_already_enabled(self, test_user, mongo_client):
        """POST /api/user/2fa/setup returns 400 when 2FA is already enabled"""
        # Enable 2FA first
        secret = pyotp.random_base32()
        mongo_client["users"].update_one(
            {"user_id": TEST_USER_ID},
            {"$set": {"totp_enabled": True, "totp_secret": secret}}
        )
        
        headers = {"Authorization": f"Bearer {test_user['session_token']}"}
        response = requests.post(f"{BASE_URL}/api/user/2fa/setup", headers=headers)
        assert response.status_code == 400
        data = response.json()
        assert "already enabled" in data.get("detail", "").lower()
        print("PASS: POST /api/user/2fa/setup returns 400 when 2FA already enabled")
        
        # Cleanup
        mongo_client["users"].update_one(
            {"user_id": TEST_USER_ID},
            {"$unset": {"totp_enabled": "", "totp_secret": ""}}
        )
    
    def test_2fa_disable_fails_when_not_enabled(self, test_user, mongo_client):
        """POST /api/user/2fa/disable returns 400 when 2FA is not enabled"""
        # Ensure 2FA is not enabled
        mongo_client["users"].update_one(
            {"user_id": TEST_USER_ID},
            {"$unset": {"totp_enabled": "", "totp_secret": "", "totp_secret_pending": ""}}
        )
        
        headers = {
            "Authorization": f"Bearer {test_user['session_token']}",
            "Content-Type": "application/json"
        }
        response = requests.post(
            f"{BASE_URL}/api/user/2fa/disable",
            headers=headers,
            json={"code": "123456"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "not enabled" in data.get("detail", "").lower()
        print("PASS: POST /api/user/2fa/disable returns 400 when 2FA not enabled")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
