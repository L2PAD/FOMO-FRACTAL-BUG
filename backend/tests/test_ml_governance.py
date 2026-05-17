"""
ML Governance API Tests
Tests for human-in-the-loop approval workflow endpoints:
- GET /api/admin/ml/approvals/candidates
- GET /api/admin/ml/approvals/active-models
- GET /api/admin/ml/approvals/history
- POST /api/admin/ml/approvals/approve
- POST /api/admin/ml/approvals/reject
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://expo-telegram-web.preview.emergentagent.com"


class TestAdminAuth:
    """Admin authentication tests"""
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "token" in data
        assert data.get("role") == "ADMIN"
        assert data.get("username") == "admin"
    
    def test_admin_login_invalid_credentials(self):
        """Test admin login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [401, 400]


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/admin/auth/login",
        json={"username": "admin", "password": "admin12345"},
        headers={"Content-Type": "application/json"}
    )
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture
def auth_headers(admin_token):
    """Headers with admin token"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_token}"
    }


class TestMlGovernanceCandidates:
    """Tests for GET /api/admin/ml/approvals/candidates"""
    
    def test_get_candidates_success(self, auth_headers):
        """Test fetching promotion candidates"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/candidates",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        assert "items" in data["data"]
        assert "count" in data["data"]
        assert isinstance(data["data"]["items"], list)
    
    def test_get_candidates_with_task_filter(self, auth_headers):
        """Test fetching candidates with task filter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/candidates?task=market",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_get_candidates_with_network_filter(self, auth_headers):
        """Test fetching candidates with network filter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/candidates?network=ethereum",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_get_candidates_with_both_filters(self, auth_headers):
        """Test fetching candidates with both task and network filters"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/candidates?task=market&network=ethereum",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True


class TestMlGovernanceActiveModels:
    """Tests for GET /api/admin/ml/approvals/active-models"""
    
    def test_get_active_models_success(self, auth_headers):
        """Test fetching active models"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/active-models",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        assert "items" in data["data"]
        assert "count" in data["data"]
        assert isinstance(data["data"]["items"], list)
    
    def test_active_model_has_expected_fields(self, auth_headers):
        """Test that active models have expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/active-models",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["data"]["count"] > 0:
            model = data["data"]["items"][0]
            assert "modelId" in model
            assert "task" in model
            assert "network" in model
            assert "version" in model
            assert "metrics" in model
    
    def test_active_model_market_ethereum_exists(self, auth_headers):
        """Test that market/ethereum active model exists"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/active-models",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find market/ethereum model
        market_eth_models = [
            m for m in data["data"]["items"]
            if m.get("task") == "market" and m.get("network") == "ethereum"
        ]
        assert len(market_eth_models) >= 1, "Expected at least one market/ethereum active model"
        
        model = market_eth_models[0]
        assert "market_v2.0_1769680469" in model.get("version", "")


class TestMlGovernanceHistory:
    """Tests for GET /api/admin/ml/approvals/history"""
    
    def test_get_history_success(self, auth_headers):
        """Test fetching approval history"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/history",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        assert "items" in data["data"]
        assert "count" in data["data"]
        assert isinstance(data["data"]["items"], list)
    
    def test_get_history_with_task_filter(self, auth_headers):
        """Test fetching history with task filter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/history?task=market",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_get_history_with_limit(self, auth_headers):
        """Test fetching history with limit"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/history?limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True


class TestMlGovernanceApprove:
    """Tests for POST /api/admin/ml/approvals/approve"""
    
    def test_approve_missing_model_id(self, auth_headers):
        """Test approve without modelId returns error"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ml/approvals/approve",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") == False
        assert data.get("error") == "MODEL_ID_REQUIRED"
    
    def test_approve_invalid_model_id(self, auth_headers):
        """Test approve with invalid modelId format"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ml/approvals/approve",
            json={"modelId": "invalid123", "note": "test"},
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") == False
    
    def test_approve_nonexistent_model(self, auth_headers):
        """Test approve with valid ObjectId but non-existent model"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ml/approvals/approve",
            json={"modelId": "000000000000000000000000", "note": "test"},
            headers=auth_headers
        )
        assert response.status_code == 404
        data = response.json()
        assert data.get("ok") == False
        assert data.get("error") == "MODEL_NOT_FOUND"
    
    def test_approve_active_model_fails(self, auth_headers):
        """Test approve on active model fails (not pending)"""
        # First get active model ID
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/active-models",
            headers=auth_headers
        )
        data = response.json()
        
        if data["data"]["count"] > 0:
            model_id = data["data"]["items"][0]["modelId"]
            
            # Try to approve active model
            response = requests.post(
                f"{BASE_URL}/api/admin/ml/approvals/approve",
                json={"modelId": model_id, "note": "test approval"},
                headers=auth_headers
            )
            assert response.status_code == 400
            data = response.json()
            assert data.get("ok") == False
            assert data.get("error") == "MODEL_NOT_PENDING"


class TestMlGovernanceReject:
    """Tests for POST /api/admin/ml/approvals/reject"""
    
    def test_reject_missing_model_id(self, auth_headers):
        """Test reject without modelId returns error"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ml/approvals/reject",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") == False
        assert data.get("error") == "MODEL_ID_REQUIRED"
    
    def test_reject_invalid_model_id(self, auth_headers):
        """Test reject with invalid modelId format"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ml/approvals/reject",
            json={"modelId": "invalid123", "note": "test"},
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") == False
    
    def test_reject_nonexistent_model(self, auth_headers):
        """Test reject with valid ObjectId but non-existent model"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ml/approvals/reject",
            json={"modelId": "000000000000000000000000", "note": "test"},
            headers=auth_headers
        )
        assert response.status_code == 404
        data = response.json()
        assert data.get("ok") == False
        assert data.get("error") == "MODEL_NOT_FOUND"


class TestMlGovernanceCanPromote:
    """Tests for GET /api/admin/ml/approvals/can-promote/:modelId"""
    
    def test_can_promote_invalid_model_id(self, auth_headers):
        """Test can-promote with invalid modelId"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/can-promote/invalid123",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("canPromote") == False
        assert data.get("reason") == "MODEL_NOT_FOUND"
    
    def test_can_promote_nonexistent_model(self, auth_headers):
        """Test can-promote with non-existent model"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/can-promote/000000000000000000000000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("canPromote") == False
        assert data.get("reason") == "MODEL_NOT_FOUND"


class TestMlGovernanceRollbackTargets:
    """Tests for GET /api/admin/ml/approvals/rollback-targets/:task"""
    
    def test_get_rollback_targets_market(self, auth_headers):
        """Test fetching rollback targets for market task"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/rollback-targets/market",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        assert "items" in data["data"]
    
    def test_get_rollback_targets_actor(self, auth_headers):
        """Test fetching rollback targets for actor task"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ml/approvals/rollback-targets/actor",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
