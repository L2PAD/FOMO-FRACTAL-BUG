"""
A.3 - Admin Control Plane for Twitter Integration Tests

Tests for:
- A.3.0: Admin Gate with requireAdmin middleware
- A.3.1: Admin Overview & Users List
- A.3.2: User Detail & Admin Actions (disable/enable/cooldown/invalidate)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAdminGate:
    """A.3.0 - Admin Gate middleware tests"""
    
    def test_admin_access_allowed_for_dev_user(self):
        """dev-user is admin by default (ADMIN_USER_IDS env)"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/overview")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
    
    def test_admin_access_denied_for_non_admin(self):
        """Non-admin user should get 403"""
        response = requests.get(
            f"{BASE_URL}/api/v4/admin/twitter/overview",
            headers={"x-user-id": "non-admin-user"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'ADMIN_ONLY'
        assert 'Administrator access required' in data['message']
    
    def test_admin_access_denied_for_random_user(self):
        """Random user ID should get 403"""
        response = requests.get(
            f"{BASE_URL}/api/v4/admin/twitter/users",
            headers={"x-user-id": "random-user-123"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'ADMIN_ONLY'


class TestAdminOverview:
    """A.3.1 - Admin Overview endpoint tests"""
    
    def test_overview_returns_system_totals(self):
        """GET /api/v4/admin/twitter/overview returns system totals"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/overview")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] == True
        assert 'data' in data
        
        overview = data['data']
        assert 'totalUsers' in overview
        assert 'activeUsers' in overview
        assert 'totalAccounts' in overview
        assert 'totalSessions' in overview
        assert 'abortsLast24h' in overview
        
        # Validate totalSessions structure
        sessions = overview['totalSessions']
        assert 'ok' in sessions
        assert 'stale' in sessions
        assert 'invalid' in sessions
        
        # Values should be non-negative integers
        assert isinstance(overview['totalUsers'], int)
        assert overview['totalUsers'] >= 0
        assert isinstance(overview['activeUsers'], int)
        assert overview['activeUsers'] >= 0


class TestAdminUsersList:
    """A.3.1 - Admin Users List endpoint tests"""
    
    def test_users_list_returns_paginated_data(self):
        """GET /api/v4/admin/twitter/users returns paginated users"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] == True
        assert 'data' in data
        
        result = data['data']
        assert 'users' in result
        assert 'total' in result
        assert 'page' in result
        assert 'pages' in result
        
        assert isinstance(result['users'], list)
        assert result['page'] >= 1
    
    def test_users_list_contains_dev_user(self):
        """Users list should contain dev-user with test data"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users")
        data = response.json()
        
        users = data['data']['users']
        dev_user = next((u for u in users if u['userId'] == 'dev-user'), None)
        
        assert dev_user is not None, "dev-user should be in users list"
        assert 'accounts' in dev_user
        assert 'sessions' in dev_user
        assert 'riskAvg' in dev_user
        assert 'health' in dev_user
        assert 'telegramConnected' in dev_user
    
    def test_users_list_user_structure(self):
        """Each user should have proper structure"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users")
        data = response.json()
        
        if data['data']['users']:
            user = data['data']['users'][0]
            
            # Required fields
            assert 'userId' in user
            assert 'accounts' in user
            assert 'sessions' in user
            assert 'riskAvg' in user
            assert 'health' in user
            assert 'telegramConnected' in user
            assert 'tasksLast24h' in user
            assert 'abortsLast24h' in user
            
            # Sessions structure
            assert 'ok' in user['sessions']
            assert 'stale' in user['sessions']
            assert 'invalid' in user['sessions']
            
            # Health should be valid enum
            assert user['health'] in ['HEALTHY', 'WARNING', 'DEGRADED', 'BLOCKED']
    
    def test_users_list_pagination(self):
        """Pagination parameters should work"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users?page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert data['data']['page'] == 1
    
    def test_users_list_search_filter(self):
        """Search filter should work"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users?search=dev")
        assert response.status_code == 200
        data = response.json()
        
        # Should find dev-user
        users = data['data']['users']
        assert any(u['userId'] == 'dev-user' for u in users)
    
    def test_users_list_status_filter(self):
        """Status filter should work"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users?status=DEGRADED")
        assert response.status_code == 200
        data = response.json()
        
        # All returned users should have DEGRADED status
        for user in data['data']['users']:
            assert user['health'] == 'DEGRADED'


class TestAdminUserDetail:
    """A.3.2 - Admin User Detail endpoint tests"""
    
    def test_user_detail_returns_data(self):
        """GET /api/v4/admin/twitter/users/:userId returns user detail"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] == True
        assert 'data' in data
        
        detail = data['data']
        assert 'user' in detail
        assert 'accounts' in detail
        assert 'sessions' in detail
        assert 'stats' in detail
    
    def test_user_detail_user_info(self):
        """User info should have proper structure"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user")
        data = response.json()
        
        user = data['data']['user']
        assert user['userId'] == 'dev-user'
        assert 'createdAt' in user
        assert 'telegramConnected' in user
    
    def test_user_detail_accounts_structure(self):
        """Accounts should have proper structure"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user")
        data = response.json()
        
        accounts = data['data']['accounts']
        assert isinstance(accounts, list)
        
        if accounts:
            account = accounts[0]
            assert 'accountId' in account
            assert 'username' in account
            assert 'enabled' in account
            assert 'sessionsCount' in account
            assert 'riskAvg' in account
    
    def test_user_detail_sessions_structure(self):
        """Sessions should have proper structure"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user")
        data = response.json()
        
        sessions = data['data']['sessions']
        assert isinstance(sessions, list)
        
        if sessions:
            session = sessions[0]
            assert 'sessionId' in session
            assert 'accountId' in session
            assert 'status' in session
            assert 'riskScore' in session
            assert 'isActive' in session
    
    def test_user_detail_stats_structure(self):
        """Stats should have proper structure"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user")
        data = response.json()
        
        stats = data['data']['stats']
        assert 'tasks24h' in stats
        assert 'tasks7d' in stats
        assert 'aborts24h' in stats
        assert 'aborts7d' in stats
        assert 'tweetsFetched24h' in stats
        assert 'tweetsFetched7d' in stats
        assert 'avgRuntime' in stats
        assert 'cooldownCount' in stats
    
    def test_user_detail_not_found(self):
        """Non-existent user should return 404"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/nonexistent-user-xyz")
        assert response.status_code == 404
        data = response.json()
        
        assert data['ok'] == False
        assert data['error'] == 'USER_NOT_FOUND'


class TestAdminUserTasks:
    """A.3.2 - Admin User Tasks endpoint tests"""
    
    def test_user_tasks_returns_list(self):
        """GET /api/v4/admin/twitter/users/:userId/tasks returns tasks"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/tasks")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] == True
        assert isinstance(data['data'], list)
    
    def test_user_tasks_structure(self):
        """Tasks should have proper structure"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/tasks")
        data = response.json()
        
        if data['data']:
            task = data['data'][0]
            assert 'taskId' in task
            assert 'status' in task
            assert 'type' in task
            assert 'fetched' in task
            assert 'createdAt' in task


class TestAdminUserActions:
    """A.3.2 - Admin User Actions (audit log) endpoint tests"""
    
    def test_user_actions_returns_list(self):
        """GET /api/v4/admin/twitter/users/:userId/actions returns action history"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/actions")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] == True
        assert isinstance(data['data'], list)
    
    def test_user_actions_structure(self):
        """Actions should have proper structure"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/actions")
        data = response.json()
        
        if data['data']:
            action = data['data'][0]
            assert 'id' in action
            assert 'adminId' in action
            assert 'action' in action
            assert 'target' in action
            assert 'createdAt' in action


class TestAdminActionsDisableEnable:
    """A.3.2 - Admin Actions: Disable/Enable user parsing"""
    
    def test_disable_user_parsing(self):
        """POST /api/v4/admin/twitter/users/:userId/disable disables parsing"""
        response = requests.post(
            f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/disable",
            json={"reason": "Test disable from pytest"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] == True
        assert data['success'] == True
        assert 'disabled' in data['message'].lower()
        assert 'affected' in data
    
    def test_enable_user_parsing(self):
        """POST /api/v4/admin/twitter/users/:userId/enable enables parsing"""
        response = requests.post(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/enable")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] == True
        assert data['success'] == True
        assert 'enabled' in data['message'].lower() or 'reactivated' in data['message'].lower()
        assert 'affected' in data
    
    def test_disable_enable_logged_in_actions(self):
        """Disable/Enable actions should be logged"""
        # First disable
        requests.post(
            f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/disable",
            json={"reason": "Test for action log"}
        )
        
        # Then enable
        requests.post(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/enable")
        
        # Check action log
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/actions")
        data = response.json()
        
        actions = data['data']
        action_types = [a['action'] for a in actions[:5]]
        
        assert 'USER_DISABLE' in action_types or 'USER_ENABLE' in action_types


class TestAdminActionsCooldown:
    """A.3.2 - Admin Actions: Force cooldown"""
    
    def test_force_cooldown(self):
        """POST /api/v4/admin/twitter/users/:userId/cooldown forces cooldown"""
        response = requests.post(
            f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/cooldown",
            json={"reason": "Test cooldown from pytest"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] == True
        assert data['success'] == True
        assert 'cooldown' in data['message'].lower()
        assert 'affected' in data


class TestAdminActionsInvalidateSessions:
    """A.3.2 - Admin Actions: Invalidate sessions"""
    
    def test_invalidate_all_sessions(self):
        """POST /api/v4/admin/twitter/users/:userId/invalidate-sessions invalidates all"""
        response = requests.post(
            f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/invalidate-sessions",
            json={"reason": "Test invalidate from pytest"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] == True
        assert data['success'] == True
        assert 'invalidated' in data['message'].lower()
        assert 'affected' in data
    
    def test_sessions_marked_invalid_after_action(self):
        """After invalidate, sessions should be INVALID"""
        # First invalidate
        requests.post(
            f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/invalidate-sessions",
            json={"reason": "Test verify invalidation"}
        )
        
        # Check user detail
        response = requests.get(f"{BASE_URL}/api/v4/admin/twitter/users/dev-user")
        data = response.json()
        
        sessions = data['data']['sessions']
        for session in sessions:
            assert session['status'] == 'INVALID'
            assert session['isActive'] == False


class TestAdminActionsNonAdminDenied:
    """A.3.2 - Admin Actions should be denied for non-admins"""
    
    def test_disable_denied_for_non_admin(self):
        """Non-admin cannot disable users"""
        response = requests.post(
            f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/disable",
            headers={"x-user-id": "non-admin-user"},
            json={"reason": "Should fail"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'ADMIN_ONLY'
    
    def test_enable_denied_for_non_admin(self):
        """Non-admin cannot enable users"""
        response = requests.post(
            f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/enable",
            headers={"x-user-id": "non-admin-user"}
        )
        assert response.status_code == 403
    
    def test_cooldown_denied_for_non_admin(self):
        """Non-admin cannot force cooldown"""
        response = requests.post(
            f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/cooldown",
            headers={"x-user-id": "non-admin-user"}
        )
        assert response.status_code == 403
    
    def test_invalidate_denied_for_non_admin(self):
        """Non-admin cannot invalidate sessions"""
        response = requests.post(
            f"{BASE_URL}/api/v4/admin/twitter/users/dev-user/invalidate-sessions",
            headers={"x-user-id": "non-admin-user"}
        )
        assert response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
