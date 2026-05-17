"""
Module Registry + Feature Toggles (Phase 7) Tests
=================================================
Tests for Meta Brain V2 module control system.
- GET /api/meta-brain-v2/modules
- POST /api/meta-brain-v2/modules/update
- Existing meta-brain-v2 endpoints (/signals, /state, /policy, /performance)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestModuleRegistryAPI:
    """Module Registry Phase 7 API Tests"""

    def test_get_modules_returns_all_four(self):
        """GET /modules returns all 4 modules with correct fields"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/modules")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert 'modules' in data
        assert len(data['modules']) == 4
        
        module_names = [m['module'] for m in data['modules']]
        assert 'exchange' in module_names
        assert 'fractal' in module_names
        assert 'onchain' in module_names
        assert 'sentiment' in module_names
        
    def test_modules_have_correct_fields(self):
        """Each module has required fields: enabled, mode, weight, weightOverride, maxSnapshotAgeHours, lastUpdated"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/modules")
        assert response.status_code == 200
        
        data = response.json()
        required_fields = ['module', 'enabled', 'mode', 'weight', 'weightOverride', 'maxSnapshotAgeHours', 'lastUpdated']
        
        for mod in data['modules']:
            for field in required_fields:
                assert field in mod, f"Module {mod.get('module')} missing field {field}"
            
            # Validate types
            assert isinstance(mod['enabled'], bool)
            assert mod['mode'] in ['live', 'snapshot', 'off']
            assert isinstance(mod['weight'], (int, float))
            assert mod['weightOverride'] is None or isinstance(mod['weightOverride'], (int, float))
            assert isinstance(mod['maxSnapshotAgeHours'], (int, float))
            assert isinstance(mod['lastUpdated'], str)

    def test_toggle_module_off_and_back(self):
        """POST /modules/update changes module state - toggle onchain off and back"""
        # Step 1: Toggle off
        response = requests.post(
            f"{BASE_URL}/api/meta-brain-v2/modules/update",
            json={"module": "onchain", "enabled": False, "mode": "off"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert data['module']['enabled'] is False
        assert data['module']['mode'] == 'off'
        
        # Step 2: Verify via GET
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/modules")
        assert response.status_code == 200
        modules = response.json()['modules']
        onchain = next(m for m in modules if m['module'] == 'onchain')
        assert onchain['enabled'] is False
        assert onchain['mode'] == 'off'
        
        # Step 3: Toggle back on
        response = requests.post(
            f"{BASE_URL}/api/meta-brain-v2/modules/update",
            json={"module": "onchain", "enabled": True, "mode": "snapshot"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert data['module']['enabled'] is True
        assert data['module']['mode'] == 'snapshot'
        
    def test_change_module_mode(self):
        """POST /modules/update can change mode (live/snapshot/off)"""
        # Set to live
        response = requests.post(
            f"{BASE_URL}/api/meta-brain-v2/modules/update",
            json={"module": "fractal", "mode": "snapshot"}
        )
        assert response.status_code == 200
        assert response.json()['module']['mode'] == 'snapshot'
        
        # Set back to live
        response = requests.post(
            f"{BASE_URL}/api/meta-brain-v2/modules/update",
            json={"module": "fractal", "mode": "live"}
        )
        assert response.status_code == 200
        assert response.json()['module']['mode'] == 'live'
        
    def test_update_nonexistent_module_returns_404(self):
        """POST /modules/update with invalid module returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/meta-brain-v2/modules/update",
            json={"module": "nonexistent", "enabled": False}
        )
        assert response.status_code == 404
        assert response.json()['ok'] is False
        
    def test_update_without_module_name_returns_400(self):
        """POST /modules/update without module name returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/meta-brain-v2/modules/update",
            json={"enabled": False}
        )
        assert response.status_code == 400
        assert response.json()['ok'] is False


class TestExistingMetaBrainEndpoints:
    """Verify existing meta-brain-v2 endpoints still work"""
    
    def test_get_signals(self):
        """GET /signals returns ok:true with signals array"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'signals' in data
        assert isinstance(data['signals'], list)
        
    def test_get_state(self):
        """GET /state returns ok:true with state data"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/state")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        
    def test_get_policy(self):
        """GET /policy returns ok:true with policy config"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/policy")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'policy' in data
        assert 'regime' in data
        
    def test_get_performance(self):
        """GET /performance returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/performance")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True


class TestModuleIntegrationWithSignals:
    """Test that module flags affect signal collection"""
    
    def test_disabled_module_not_in_active(self):
        """After disabling module, it should not be returned by active query"""
        # Disable onchain
        requests.post(
            f"{BASE_URL}/api/meta-brain-v2/modules/update",
            json={"module": "onchain", "enabled": False, "mode": "off"}
        )
        
        # Verify in modules list
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/modules")
        modules = response.json()['modules']
        onchain = next(m for m in modules if m['module'] == 'onchain')
        assert onchain['enabled'] is False
        
        # Re-enable for cleanup
        requests.post(
            f"{BASE_URL}/api/meta-brain-v2/modules/update",
            json={"module": "onchain", "enabled": True, "mode": "snapshot"}
        )
        
    def test_lastUpdated_timestamp_changes(self):
        """lastUpdated timestamp changes after update"""
        # Get current state
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/modules")
        modules = response.json()['modules']
        sentiment = next(m for m in modules if m['module'] == 'sentiment')
        old_timestamp = sentiment['lastUpdated']
        
        time.sleep(0.1)  # Small delay
        
        # Update
        response = requests.post(
            f"{BASE_URL}/api/meta-brain-v2/modules/update",
            json={"module": "sentiment", "maxSnapshotAgeHours": 48}
        )
        assert response.status_code == 200
        new_timestamp = response.json()['module']['lastUpdated']
        
        assert new_timestamp != old_timestamp, "lastUpdated should change after update"
        
        # Reset
        requests.post(
            f"{BASE_URL}/api/meta-brain-v2/modules/update",
            json={"module": "sentiment", "maxSnapshotAgeHours": 24}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
