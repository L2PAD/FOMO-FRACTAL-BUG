"""
Snapshot & Alerts API Tests
============================
Tests for FOMO AI Product Signals & Sharing features:
- Part A: Snapshot creation and retrieval
- Part B: Alert settings and statistics
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSnapshotAPIs:
    """Snapshot endpoints for share links"""
    
    def test_create_snapshot_btcusdt(self):
        """POST /api/v10/snapshot/create - creates immutable snapshot"""
        response = requests.post(
            f"{BASE_URL}/api/v10/snapshot/create",
            json={"symbol": "BTCUSDT"},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["ok"] == True
        assert "snapshot" in data
        assert "shareUrl" in data
        
        # Verify snapshot fields
        snapshot = data["snapshot"]
        assert "snapshotId" in snapshot
        assert snapshot["symbol"] == "BTCUSDT"
        assert "action" in snapshot
        assert "confidence" in snapshot
        assert "timestamp" in snapshot
        assert "explainability" in snapshot
        assert "createdAt" in snapshot
        assert "expiresAt" in snapshot
        
        # Verify explainability structure
        explain = snapshot["explainability"]
        assert "verdict" in explain
        assert "appliedRules" in explain
        assert "riskFlags" in explain
        assert "drivers" in explain
        
        # Store snapshotId for next test
        TestSnapshotAPIs.created_snapshot_id = snapshot["snapshotId"]
        print(f"Created snapshot: {snapshot['snapshotId']}")
    
    def test_create_snapshot_missing_symbol(self):
        """POST /api/v10/snapshot/create - requires symbol"""
        response = requests.post(
            f"{BASE_URL}/api/v10/snapshot/create",
            json={},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] == False
        assert "error" in data
    
    def test_get_public_snapshot(self):
        """GET /api/public/snapshot/:id - retrieves snapshot without auth"""
        # Use the created snapshot ID or a known test ID
        snapshot_id = getattr(TestSnapshotAPIs, 'created_snapshot_id', 'GG5ZkoM85l')
        
        response = requests.get(f"{BASE_URL}/api/public/snapshot/{snapshot_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert "snapshot" in data
        
        snapshot = data["snapshot"]
        assert snapshot["snapshotId"] == snapshot_id
        assert "symbol" in snapshot
        assert "action" in snapshot
        assert "confidence" in snapshot
    
    def test_get_nonexistent_snapshot(self):
        """GET /api/public/snapshot/:id - returns 404 for missing snapshot"""
        response = requests.get(f"{BASE_URL}/api/public/snapshot/nonexistent123xyz")
        
        assert response.status_code == 404
        data = response.json()
        assert data["ok"] == False
        assert data["error"] == "Snapshot not found"
    
    def test_get_recent_snapshots(self):
        """GET /api/v10/snapshot/recent/:symbol - returns recent snapshots"""
        response = requests.get(f"{BASE_URL}/api/v10/snapshot/recent/BTCUSDT?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert "snapshots" in data
        assert isinstance(data["snapshots"], list)
        
        # Verify snapshots have correct structure
        if len(data["snapshots"]) > 0:
            snapshot = data["snapshots"][0]
            assert "snapshotId" in snapshot
            assert snapshot["symbol"] == "BTCUSDT"
            print(f"Found {len(data['snapshots'])} recent snapshots for BTCUSDT")
    
    def test_get_snapshot_stats(self):
        """GET /api/v10/snapshot/stats - returns snapshot statistics"""
        response = requests.get(f"{BASE_URL}/api/v10/snapshot/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert "stats" in data
        
        stats = data["stats"]
        assert "total" in stats
        assert "recentCount" in stats
        assert "byAction" in stats
        print(f"Snapshot stats: total={stats['total']}, recent={stats['recentCount']}")


class TestAlertAPIs:
    """Alert settings and statistics endpoints"""
    
    def test_get_alert_settings(self):
        """GET /api/v10/alerts/settings - returns alert settings"""
        response = requests.get(f"{BASE_URL}/api/v10/alerts/settings")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert "settings" in data
        
        settings = data["settings"]
        assert "enabled" in settings
        assert "telegram" in settings
        assert "discord" in settings
        assert "decisionConfidenceThreshold" in settings
        assert "cooldownPerAssetMs" in settings
        assert "channels" in settings
        
        # Verify channels structure
        channels = settings["channels"]
        assert "decisions" in channels
        assert "riskWarnings" in channels
        assert "systemAlerts" in channels
        
        print(f"Alert settings: enabled={settings['enabled']}, threshold={settings['decisionConfidenceThreshold']}")
    
    def test_update_alert_settings(self):
        """PATCH /api/v10/alerts/settings - updates settings"""
        # Update confidence threshold
        response = requests.patch(
            f"{BASE_URL}/api/v10/alerts/settings",
            json={"decisionConfidenceThreshold": 0.75},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert data["message"] == "Settings updated"
        
        # Verify update was applied
        verify_response = requests.get(f"{BASE_URL}/api/v10/alerts/settings")
        verify_data = verify_response.json()
        assert verify_data["settings"]["decisionConfidenceThreshold"] == 0.75
        
        # Reset to original
        requests.patch(
            f"{BASE_URL}/api/v10/alerts/settings",
            json={"decisionConfidenceThreshold": 0.65},
            headers={"Content-Type": "application/json"}
        )
        print("Settings update and verify successful")
    
    def test_update_alert_channels(self):
        """PATCH /api/v10/alerts/settings - updates channel settings"""
        response = requests.patch(
            f"{BASE_URL}/api/v10/alerts/settings",
            json={
                "channels": {
                    "decisions": True,
                    "riskWarnings": True,
                    "systemAlerts": False
                }
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
        # Verify and reset
        verify = requests.get(f"{BASE_URL}/api/v10/alerts/settings").json()
        assert verify["settings"]["channels"]["systemAlerts"] == False
        
        # Reset
        requests.patch(
            f"{BASE_URL}/api/v10/alerts/settings",
            json={"channels": {"decisions": True, "riskWarnings": True, "systemAlerts": True}},
            headers={"Content-Type": "application/json"}
        )
    
    def test_get_alert_stats(self):
        """GET /api/v10/alerts/stats - returns alert statistics"""
        response = requests.get(f"{BASE_URL}/api/v10/alerts/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert "stats" in data
        
        stats = data["stats"]
        assert "total" in stats
        assert "sent" in stats
        assert "failed" in stats
        assert "byType" in stats
        
        print(f"Alert stats: total={stats['total']}, sent={stats['sent']}, failed={stats['failed']}")
    
    def test_get_alert_history(self):
        """GET /api/v10/alerts/history - returns alert history"""
        response = requests.get(f"{BASE_URL}/api/v10/alerts/history?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        
        print(f"Alert history: {len(data['alerts'])} alerts found")
    
    def test_test_telegram_not_configured(self):
        """POST /api/v10/alerts/test/telegram - returns error when not configured"""
        response = requests.post(f"{BASE_URL}/api/v10/alerts/test/telegram")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should fail since Telegram not configured in test env
        if not data["ok"]:
            assert "error" in data
            print(f"Telegram test (expected fail): {data.get('error')}")
        else:
            print("Telegram test sent successfully (configured)")
    
    def test_test_invalid_channel(self):
        """POST /api/v10/alerts/test/:channel - rejects invalid channel"""
        response = requests.post(f"{BASE_URL}/api/v10/alerts/test/invalid")
        
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] == False
        assert "error" in data


class TestHealthCheck:
    """Basic health and service verification"""
    
    def test_health_endpoint(self):
        """GET /api/health - service is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
