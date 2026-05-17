"""
FOMO AI Alerts API Tests (v10)
Tests for:
- GET /api/v10/fomo-alerts/config - returns alert config with masked tokens
- PATCH /api/v10/fomo-alerts/config - updates config
- GET /api/v10/fomo-alerts/stats - returns stats with hourlyRemaining
- GET /api/v10/fomo-alerts/logs - returns alert logs
- POST /api/v10/fomo-alerts/test/user - sends test user alert
- POST /api/v10/fomo-alerts/test/admin - sends test admin alert
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFomoAlertsConfig:
    """FOMO Alerts config endpoint tests"""
    
    def test_get_config_returns_ok(self):
        """GET /api/v10/fomo-alerts/config returns ok and config object"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/config")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok=true"
        assert 'config' in data, "Expected config in response"
    
    def test_get_config_has_user_section(self):
        """Config should have user section with required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/config")
        
        assert response.status_code == 200
        data = response.json()
        config = data.get('config', {})
        
        assert 'user' in config, "Expected user section in config"
        user = config['user']
        
        # Check required user fields
        assert 'enabled' in user, "Expected enabled in user config"
        assert 'decisionChanged' in user, "Expected decisionChanged toggle"
        assert 'highConfidence' in user, "Expected highConfidence toggle"
        assert 'riskIncreased' in user, "Expected riskIncreased toggle"
        assert 'confidenceThreshold' in user, "Expected confidenceThreshold"
    
    def test_get_config_has_admin_section(self):
        """Config should have admin section with required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/config")
        
        assert response.status_code == 200
        data = response.json()
        config = data.get('config', {})
        
        assert 'admin' in config, "Expected admin section in config"
        admin = config['admin']
        
        # Check required admin fields
        assert 'enabled' in admin, "Expected enabled in admin config"
        assert 'mlPromoted' in admin, "Expected mlPromoted toggle"
        assert 'mlRollback' in admin, "Expected mlRollback toggle"
        assert 'providerDown' in admin, "Expected providerDown toggle"
    
    def test_get_config_has_global_section(self):
        """Config should have global section with safety guards"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/config")
        
        assert response.status_code == 200
        data = response.json()
        config = data.get('config', {})
        
        assert 'global' in config, "Expected global section in config"
        global_cfg = config['global']
        
        # Check safety guards
        assert 'requireLiveData' in global_cfg, "Expected requireLiveData"
        assert 'noUserAlertsOnAvoid' in global_cfg, "Expected noUserAlertsOnAvoid"
        assert 'maxAlertsPerHour' in global_cfg, "Expected maxAlertsPerHour"
        assert 'dedupeWindowMs' in global_cfg, "Expected dedupeWindowMs"
    
    def test_get_config_masks_tokens(self):
        """Bot tokens should be masked in response"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/config")
        
        assert response.status_code == 200
        data = response.json()
        config = data.get('config', {})
        
        # Tokens should be masked or undefined
        user_token = config.get('user', {}).get('botToken')
        admin_token = config.get('admin', {}).get('botToken')
        
        # Token should be masked with *** or be undefined
        if user_token:
            assert '***' in str(user_token), "User token should be masked"
        if admin_token:
            assert '***' in str(admin_token), "Admin token should be masked"
    
    def test_patch_config_updates_global_enabled(self):
        """PATCH /api/v10/fomo-alerts/config updates enabled flag"""
        # Get current config
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/config")
        assert response.status_code == 200
        initial_config = response.json().get('config', {})
        initial_enabled = initial_config.get('enabled', True)
        
        # Update to opposite value
        new_enabled = not initial_enabled
        update_response = requests.patch(
            f"{BASE_URL}/api/v10/fomo-alerts/config",
            json={'enabled': new_enabled},
            headers={'Content-Type': 'application/json'}
        )
        
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}"
        update_data = update_response.json()
        assert update_data.get('ok') == True
        
        # Verify change persisted
        verify_response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/config")
        assert verify_response.status_code == 200
        verify_config = verify_response.json().get('config', {})
        assert verify_config.get('enabled') == new_enabled, "Config update should persist"
        
        # Restore original value
        requests.patch(
            f"{BASE_URL}/api/v10/fomo-alerts/config",
            json={'enabled': initial_enabled},
            headers={'Content-Type': 'application/json'}
        )
    
    def test_patch_config_updates_user_threshold(self):
        """PATCH config updates user confidence threshold"""
        # Get current threshold
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/config")
        assert response.status_code == 200
        initial_threshold = response.json().get('config', {}).get('user', {}).get('confidenceThreshold', 0.65)
        
        # Update threshold
        new_threshold = 0.75 if initial_threshold < 0.75 else 0.55
        update_response = requests.patch(
            f"{BASE_URL}/api/v10/fomo-alerts/config",
            json={'user': {'confidenceThreshold': new_threshold}},
            headers={'Content-Type': 'application/json'}
        )
        
        assert update_response.status_code == 200
        
        # Verify change
        verify_response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/config")
        verify_threshold = verify_response.json().get('config', {}).get('user', {}).get('confidenceThreshold')
        assert verify_threshold == new_threshold, f"Expected {new_threshold}, got {verify_threshold}"
        
        # Restore
        requests.patch(
            f"{BASE_URL}/api/v10/fomo-alerts/config",
            json={'user': {'confidenceThreshold': initial_threshold}},
            headers={'Content-Type': 'application/json'}
        )


class TestFomoAlertsStats:
    """FOMO Alerts stats endpoint tests"""
    
    def test_get_stats_returns_ok(self):
        """GET /api/v10/fomo-alerts/stats returns ok and stats object"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok=true"
        assert 'stats' in data, "Expected stats in response"
    
    def test_get_stats_has_counts(self):
        """Stats should have total, sent, skipped, failed counts"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/stats")
        
        assert response.status_code == 200
        stats = response.json().get('stats', {})
        
        assert 'total' in stats, "Expected total count"
        assert 'sent' in stats, "Expected sent count"
        assert 'skipped' in stats, "Expected skipped count"
        assert 'failed' in stats, "Expected failed count"
    
    def test_get_stats_has_hourly_remaining(self):
        """Stats should have hourlyRemaining field"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/stats")
        
        assert response.status_code == 200
        stats = response.json().get('stats', {})
        
        assert 'hourlyRemaining' in stats, "Expected hourlyRemaining"
        assert isinstance(stats['hourlyRemaining'], (int, float)), "hourlyRemaining should be numeric"
        assert stats['hourlyRemaining'] >= 0, "hourlyRemaining should be >= 0"
    
    def test_get_stats_has_byevent_byestatus(self):
        """Stats should have byEvent and byStatus breakdowns"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/stats")
        
        assert response.status_code == 200
        stats = response.json().get('stats', {})
        
        assert 'byEvent' in stats, "Expected byEvent breakdown"
        assert 'byStatus' in stats, "Expected byStatus breakdown"


class TestFomoAlertsLogs:
    """FOMO Alerts logs endpoint tests"""
    
    def test_get_logs_returns_ok(self):
        """GET /api/v10/fomo-alerts/logs returns ok and logs array"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/logs")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok=true"
        assert 'logs' in data, "Expected logs in response"
        assert isinstance(data['logs'], list), "Logs should be an array"
    
    def test_get_logs_with_limit(self):
        """GET logs with limit parameter"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/logs?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        
        logs = data.get('logs', [])
        assert len(logs) <= 10, "Should respect limit parameter"


class TestFomoAlertsTest:
    """FOMO Alerts test endpoints"""
    
    def test_user_alert_without_token(self):
        """POST /api/v10/fomo-alerts/test/user returns error without bot token"""
        response = requests.post(f"{BASE_URL}/api/v10/fomo-alerts/test/user")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Without token configured, should return ok=false with USER_BOT_NOT_CONFIGURED
        # OR ok=true if token is configured
        if not data.get('ok'):
            assert 'USER_BOT_NOT_CONFIGURED' in str(data.get('error', '')), \
                f"Expected USER_BOT_NOT_CONFIGURED error, got {data}"
    
    def test_admin_alert_without_token(self):
        """POST /api/v10/fomo-alerts/test/admin returns error without bot token"""
        response = requests.post(f"{BASE_URL}/api/v10/fomo-alerts/test/admin")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Without token configured, should return ok=false with ADMIN_BOT_NOT_CONFIGURED
        # OR ok=true if token is configured
        if not data.get('ok'):
            assert 'ADMIN_BOT_NOT_CONFIGURED' in str(data.get('error', '')), \
                f"Expected ADMIN_BOT_NOT_CONFIGURED error, got {data}"
    
    def test_invalid_scope_returns_400(self):
        """POST /api/v10/fomo-alerts/test/invalid returns 400"""
        response = requests.post(f"{BASE_URL}/api/v10/fomo-alerts/test/invalid")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"


class TestFomoAlertsPreview:
    """FOMO Alerts preview endpoint tests"""
    
    def test_preview_decision_changed(self):
        """POST /api/v10/fomo-alerts/preview generates message preview"""
        payload = {
            'event': 'DECISION_CHANGED',
            'payload': {
                'symbol': 'BTCUSDT',
                'previousAction': 'AVOID',
                'newAction': 'BUY',
                'previousConfidence': 0.45,
                'newConfidence': 0.72,
                'reasons': ['Test reason 1', 'Test reason 2'],
                'timestamp': 1704067200000
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v10/fomo-alerts/preview",
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok=true"
        assert 'preview' in data, "Expected preview in response"
        
        preview = data['preview']
        assert 'text' in preview, "Expected text in preview"
        assert 'title' in preview, "Expected title in preview"
        assert 'BTCUSDT' in preview['text'], "Message should contain symbol"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
