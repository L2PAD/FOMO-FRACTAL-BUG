"""
Test Suite for Admin Consent Policy Management System
Tests all CRUD operations and admin actions for consent policies.

Endpoints tested:
- GET /api/v4/admin/twitter/consent-policies - list all policies
- GET /api/v4/admin/twitter/consent-policies/:id - get single policy
- POST /api/v4/admin/twitter/consent-policies - create draft
- PUT /api/v4/admin/twitter/consent-policies/:id - update draft
- DELETE /api/v4/admin/twitter/consent-policies/:id - delete draft
- POST /api/v4/admin/twitter/consent-policies/:id/publish - publish draft
- POST /api/v4/admin/twitter/consent-policies/force-reconsent - force re-consent
- GET /api/v4/admin/twitter/consent-policies/stats - consent statistics
- GET /api/v4/admin/twitter/consent-policies/logs - consent audit log
"""

import pytest
import requests
import os
import time
import random
import string

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

def random_version():
    """Generate random version string for testing"""
    return f"99.{random.randint(1, 99)}.{random.randint(1, 99)}"

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def test_policy_data():
    """Generate unique test policy data"""
    version = random_version()
    return {
        "version": version,
        "title": f"TEST Policy v{version}",
        "contentMarkdown": f"# Test Policy v{version}\n\nThis is a test policy created for automated testing.\n\n## Section 1\nTest content here."
    }


class TestConsentPoliciesListAndStats:
    """Test listing policies and statistics endpoints"""
    
    def test_list_policies_returns_200(self, api_client):
        """GET /api/v4/admin/twitter/consent-policies returns 200"""
        response = api_client.get(f"{BASE_URL}/api/v4/admin/twitter/consent-policies")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        assert isinstance(data["data"], list)
        print(f"✓ List policies returned {len(data['data'])} policies")
    
    def test_list_policies_data_structure(self, api_client):
        """Verify policy list data structure"""
        response = api_client.get(f"{BASE_URL}/api/v4/admin/twitter/consent-policies")
        data = response.json()
        
        if len(data["data"]) > 0:
            policy = data["data"][0]
            # Check required fields
            assert "id" in policy
            assert "slug" in policy
            assert "version" in policy
            assert "title" in policy
            assert "isActive" in policy
            assert "createdAt" in policy
            assert "contentPreview" in policy
            assert "stats" in policy
            assert "activeConsents" in policy["stats"]
            print(f"✓ Policy data structure is correct")
        else:
            print("⚠ No policies to verify structure")
    
    def test_get_stats_returns_200(self, api_client):
        """GET /api/v4/admin/twitter/consent-policies/stats returns 200"""
        response = api_client.get(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        print(f"✓ Stats endpoint returned successfully")
    
    def test_stats_data_structure(self, api_client):
        """Verify stats data structure when active policy exists"""
        response = api_client.get(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/stats")
        data = response.json()
        
        if data["data"].get("hasActivePolicy"):
            stats_data = data["data"]
            assert "activePolicy" in stats_data
            assert "version" in stats_data["activePolicy"]
            assert "title" in stats_data["activePolicy"]
            
            assert "stats" in stats_data
            stats = stats_data["stats"]
            assert "totalActiveConsents" in stats
            assert "consentsForCurrentVersion" in stats
            assert "outdatedConsents" in stats
            assert "revokedConsents" in stats
            assert "recentConsents7d" in stats
            print(f"✓ Stats structure verified - Active version: v{stats_data['activePolicy']['version']}")
        else:
            print("⚠ No active policy - stats structure minimal")
    
    def test_get_logs_returns_200(self, api_client):
        """GET /api/v4/admin/twitter/consent-policies/logs returns 200"""
        response = api_client.get(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/logs")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        assert isinstance(data["data"], list)
        print(f"✓ Logs endpoint returned {len(data['data'])} entries")
    
    def test_logs_with_limit_param(self, api_client):
        """Test logs endpoint with limit parameter"""
        response = api_client.get(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/logs?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["data"]) <= 5
        print(f"✓ Logs limit parameter works correctly")
    
    def test_logs_with_include_revoked(self, api_client):
        """Test logs endpoint with includeRevoked parameter"""
        response = api_client.get(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/logs?includeRevoked=true")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Logs includeRevoked parameter works")


class TestConsentPolicyCRUD:
    """Test Create, Read, Update, Delete operations for policies"""
    
    def test_create_policy_draft(self, api_client, test_policy_data):
        """POST /api/v4/admin/twitter/consent-policies creates draft"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/admin/twitter/consent-policies",
            json=test_policy_data
        )
        assert response.status_code == 201
        
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        assert data["data"]["version"] == test_policy_data["version"]
        assert data["data"]["title"] == test_policy_data["title"]
        assert data["data"]["isActive"] == False  # Should be draft
        
        # Store ID for later tests
        test_policy_data["id"] = data["data"]["id"]
        print(f"✓ Created draft policy v{test_policy_data['version']} with ID: {data['data']['id']}")
    
    def test_create_policy_missing_fields(self, api_client):
        """POST with missing fields returns 400"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/admin/twitter/consent-policies",
            json={"title": "Missing version and content"}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("ok") == False
        assert data.get("error") == "MISSING_FIELDS"
        print(f"✓ Missing fields validation works")
    
    def test_create_duplicate_version(self, api_client, test_policy_data):
        """POST with existing version returns 409"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/admin/twitter/consent-policies",
            json=test_policy_data
        )
        assert response.status_code == 409
        
        data = response.json()
        assert data.get("ok") == False
        assert data.get("error") == "VERSION_EXISTS"
        print(f"✓ Duplicate version validation works")
    
    def test_get_single_policy(self, api_client, test_policy_data):
        """GET /api/v4/admin/twitter/consent-policies/:id returns policy"""
        policy_id = test_policy_data.get("id")
        if not policy_id:
            pytest.skip("No policy ID from create test")
        
        response = api_client.get(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/{policy_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert data["data"]["id"] == policy_id
        assert data["data"]["version"] == test_policy_data["version"]
        assert "contentMarkdown" in data["data"]  # Full content
        assert "stats" in data["data"]
        print(f"✓ Get single policy works - full content length: {len(data['data']['contentMarkdown'])}")
    
    def test_get_nonexistent_policy(self, api_client):
        """GET with invalid ID returns 404"""
        response = api_client.get(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/000000000000000000000000")
        assert response.status_code == 404
        
        data = response.json()
        assert data.get("ok") == False
        assert data.get("error") == "POLICY_NOT_FOUND"
        print(f"✓ 404 for nonexistent policy works")
    
    def test_update_draft_policy(self, api_client, test_policy_data):
        """PUT /api/v4/admin/twitter/consent-policies/:id updates draft"""
        policy_id = test_policy_data.get("id")
        if not policy_id:
            pytest.skip("No policy ID from create test")
        
        new_title = f"UPDATED {test_policy_data['title']}"
        response = api_client.put(
            f"{BASE_URL}/api/v4/admin/twitter/consent-policies/{policy_id}",
            json={"title": new_title}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert data["data"]["title"] == new_title
        print(f"✓ Update draft policy works - new title: {new_title}")
    
    def test_update_nonexistent_policy(self, api_client):
        """PUT with invalid ID returns 404"""
        response = api_client.put(
            f"{BASE_URL}/api/v4/admin/twitter/consent-policies/000000000000000000000000",
            json={"title": "Test"}
        )
        assert response.status_code == 404
        print(f"✓ 404 for updating nonexistent policy works")


class TestConsentPolicyPublish:
    """Test publishing and force re-consent operations"""
    
    def test_publish_draft_policy(self, api_client, test_policy_data):
        """POST /api/v4/admin/twitter/consent-policies/:id/publish publishes draft"""
        policy_id = test_policy_data.get("id")
        if not policy_id:
            pytest.skip("No policy ID from create test")
        
        response = api_client.post(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/{policy_id}/publish")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert data["data"]["isActive"] == True
        assert "affectedUsersCount" in data["data"]
        print(f"✓ Published policy v{data['data']['version']} - affected users: {data['data']['affectedUsersCount']}")
        
        # Mark as published for cleanup
        test_policy_data["published"] = True
    
    def test_publish_already_active(self, api_client, test_policy_data):
        """POST publish on already active policy returns 400"""
        policy_id = test_policy_data.get("id")
        if not policy_id or not test_policy_data.get("published"):
            pytest.skip("No published policy to test")
        
        response = api_client.post(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/{policy_id}/publish")
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("error") == "ALREADY_ACTIVE"
        print(f"✓ Cannot publish already active policy")
    
    def test_cannot_edit_active_policy(self, api_client, test_policy_data):
        """PUT on active policy returns 400"""
        policy_id = test_policy_data.get("id")
        if not policy_id or not test_policy_data.get("published"):
            pytest.skip("No published policy to test")
        
        response = api_client.put(
            f"{BASE_URL}/api/v4/admin/twitter/consent-policies/{policy_id}",
            json={"title": "Should fail"}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("error") == "CANNOT_EDIT_ACTIVE"
        print(f"✓ Cannot edit active policy")
    
    def test_cannot_delete_active_policy(self, api_client, test_policy_data):
        """DELETE on active policy returns 400"""
        policy_id = test_policy_data.get("id")
        if not policy_id or not test_policy_data.get("published"):
            pytest.skip("No published policy to test")
        
        response = api_client.delete(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/{policy_id}")
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("error") == "CANNOT_DELETE_ACTIVE"
        print(f"✓ Cannot delete active policy")
    
    def test_force_reconsent(self, api_client):
        """POST /api/v4/admin/twitter/consent-policies/force-reconsent works"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/admin/twitter/consent-policies/force-reconsent",
            json={"reason": "Automated test - force re-consent"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert "revokedCount" in data["data"]
        assert "activeVersion" in data["data"]
        print(f"✓ Force re-consent worked - revoked {data['data']['revokedCount']} consents")


class TestConsentPolicyCleanup:
    """Cleanup test data - restore original active policy"""
    
    def test_restore_original_active_policy(self, api_client):
        """Restore v1.0.0 as active policy if it was deactivated"""
        # Get all policies
        response = api_client.get(f"{BASE_URL}/api/v4/admin/twitter/consent-policies")
        data = response.json()
        
        # Find v1.0.0 policy
        v1_policy = None
        for p in data["data"]:
            if p["version"] == "1.0.0":
                v1_policy = p
                break
        
        if v1_policy and not v1_policy["isActive"]:
            # Re-publish v1.0.0
            response = api_client.post(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/{v1_policy['id']}/publish")
            if response.status_code == 200:
                print(f"✓ Restored v1.0.0 as active policy")
            else:
                print(f"⚠ Could not restore v1.0.0: {response.json()}")
        elif v1_policy and v1_policy["isActive"]:
            print(f"✓ v1.0.0 is already active")
        else:
            print(f"⚠ v1.0.0 policy not found")
    
    def test_delete_test_policies(self, api_client):
        """Delete all TEST_ prefixed policies"""
        response = api_client.get(f"{BASE_URL}/api/v4/admin/twitter/consent-policies")
        data = response.json()
        
        deleted = 0
        for p in data["data"]:
            if p["version"].startswith("99.") and not p["isActive"]:
                del_response = api_client.delete(f"{BASE_URL}/api/v4/admin/twitter/consent-policies/{p['id']}")
                if del_response.status_code == 200:
                    deleted += 1
        
        print(f"✓ Cleaned up {deleted} test policies")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
