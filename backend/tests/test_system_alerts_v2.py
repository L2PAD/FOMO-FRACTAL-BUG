"""
System Alerts V2 - Backend API Tests
Tests for Alerts V2 = System & Intelligence Notifications Layer

Endpoints tested:
- GET /api/system-alerts - List alerts with filters
- GET /api/system-alerts/summary - Stats for dashboard
- POST /api/system-alerts/:alertId/ack - Acknowledge alert
- POST /api/system-alerts/test - Create test alerts
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSystemAlertsAPI:
    """System Alerts V2 API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_alert_ids = []
        yield
        # Cleanup: acknowledge any test alerts created
        for alert_id in self.created_alert_ids:
            try:
                self.session.post(f"{BASE_URL}/api/system-alerts/{alert_id}/ack", json={})
            except:
                pass
    
    # ==================== GET /api/system-alerts ====================
    
    def test_get_alerts_returns_list(self):
        """GET /api/system-alerts returns list of alerts"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "count" in data
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
    
    def test_get_alerts_structure(self):
        """GET /api/system-alerts returns alerts with correct structure"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts")
        
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            alert = data["alerts"][0]
            # Verify required fields
            assert "alertId" in alert
            assert "type" in alert
            assert "category" in alert
            assert "severity" in alert
            assert "title" in alert
            assert "message" in alert
            assert "status" in alert
            assert "createdAt" in alert
            # Verify _id is excluded
            assert "_id" not in alert
    
    def test_get_alerts_filter_by_status_open(self):
        """GET /api/system-alerts?status=OPEN filters correctly"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts", params={"status": "OPEN"})
        
        assert response.status_code == 200
        data = response.json()
        
        for alert in data["alerts"]:
            assert alert["status"] == "OPEN"
    
    def test_get_alerts_filter_by_status_acked(self):
        """GET /api/system-alerts?status=ACKED filters correctly"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts", params={"status": "ACKED"})
        
        assert response.status_code == 200
        data = response.json()
        
        for alert in data["alerts"]:
            assert alert["status"] == "ACKED"
    
    def test_get_alerts_filter_by_status_resolved(self):
        """GET /api/system-alerts?status=RESOLVED filters correctly"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts", params={"status": "RESOLVED"})
        
        assert response.status_code == 200
        data = response.json()
        
        for alert in data["alerts"]:
            assert alert["status"] == "RESOLVED"
    
    def test_get_alerts_filter_by_category_ml(self):
        """GET /api/system-alerts?category=ML filters correctly"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts", params={"category": "ML"})
        
        assert response.status_code == 200
        data = response.json()
        
        for alert in data["alerts"]:
            assert alert["category"] == "ML"
    
    def test_get_alerts_filter_by_category_system(self):
        """GET /api/system-alerts?category=SYSTEM filters correctly"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts", params={"category": "SYSTEM"})
        
        assert response.status_code == 200
        data = response.json()
        
        for alert in data["alerts"]:
            assert alert["category"] == "SYSTEM"
    
    def test_get_alerts_filter_by_severity_critical(self):
        """GET /api/system-alerts?severity=CRITICAL filters correctly"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts", params={"severity": "CRITICAL"})
        
        assert response.status_code == 200
        data = response.json()
        
        for alert in data["alerts"]:
            assert alert["severity"] == "CRITICAL"
    
    def test_get_alerts_filter_by_severity_high(self):
        """GET /api/system-alerts?severity=HIGH filters correctly"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts", params={"severity": "HIGH"})
        
        assert response.status_code == 200
        data = response.json()
        
        for alert in data["alerts"]:
            assert alert["severity"] == "HIGH"
    
    def test_get_alerts_pagination_limit(self):
        """GET /api/system-alerts?limit=2 respects limit"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts", params={"limit": 2})
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["alerts"]) <= 2
    
    # ==================== GET /api/system-alerts/summary ====================
    
    def test_get_summary_returns_stats(self):
        """GET /api/system-alerts/summary returns dashboard stats"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "total" in data
        assert "active" in data
        assert "critical" in data
        assert "resolved24h" in data
        assert "byCategory" in data
        assert "bySeverity" in data
    
    def test_get_summary_category_breakdown(self):
        """GET /api/system-alerts/summary has correct category breakdown"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        by_category = data["byCategory"]
        assert "SYSTEM" in by_category
        assert "ML" in by_category
        assert "MARKET" in by_category
        
        # All values should be non-negative integers
        assert isinstance(by_category["SYSTEM"], int) and by_category["SYSTEM"] >= 0
        assert isinstance(by_category["ML"], int) and by_category["ML"] >= 0
        assert isinstance(by_category["MARKET"], int) and by_category["MARKET"] >= 0
    
    def test_get_summary_severity_breakdown(self):
        """GET /api/system-alerts/summary has correct severity breakdown"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        by_severity = data["bySeverity"]
        assert "INFO" in by_severity
        assert "LOW" in by_severity
        assert "MEDIUM" in by_severity
        assert "HIGH" in by_severity
        assert "CRITICAL" in by_severity
    
    def test_get_summary_counts_are_consistent(self):
        """GET /api/system-alerts/summary counts are logically consistent"""
        response = self.session.get(f"{BASE_URL}/api/system-alerts/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        # Active should be <= total
        assert data["active"] <= data["total"]
        # Critical should be <= active
        assert data["critical"] <= data["active"]
    
    # ==================== POST /api/system-alerts/test ====================
    
    def test_create_test_alert_ml_mode_change(self):
        """POST /api/system-alerts/test creates ML_MODE_CHANGE alert"""
        response = self.session.post(
            f"{BASE_URL}/api/system-alerts/test",
            json={"type": "ML_MODE_CHANGE"}
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "Test alert created"
        assert "alert" in data
        assert data["alert"]["type"] == "ML_MODE_CHANGE"
        assert data["alert"]["severity"] == "MEDIUM"
        
        self.created_alert_ids.append(data["alert"]["alertId"])
    
    def test_create_test_alert_ml_kill_switch(self):
        """POST /api/system-alerts/test creates ML_KILL_SWITCH alert"""
        response = self.session.post(
            f"{BASE_URL}/api/system-alerts/test",
            json={"type": "ML_KILL_SWITCH"}
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert data["alert"]["type"] == "ML_KILL_SWITCH"
        assert data["alert"]["severity"] == "CRITICAL"
        
        self.created_alert_ids.append(data["alert"]["alertId"])
    
    def test_create_test_alert_rpc_degraded(self):
        """POST /api/system-alerts/test creates RPC_DEGRADED alert"""
        response = self.session.post(
            f"{BASE_URL}/api/system-alerts/test",
            json={"type": "RPC_DEGRADED"}
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert data["alert"]["type"] == "RPC_DEGRADED"
        assert data["alert"]["severity"] == "HIGH"
        
        self.created_alert_ids.append(data["alert"]["alertId"])
    
    def test_create_test_alert_bridge_spike(self):
        """POST /api/system-alerts/test creates BRIDGE_ACTIVITY_SPIKE alert"""
        response = self.session.post(
            f"{BASE_URL}/api/system-alerts/test",
            json={"type": "BRIDGE_ACTIVITY_SPIKE"}
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert data["alert"]["type"] == "BRIDGE_ACTIVITY_SPIKE"
        
        self.created_alert_ids.append(data["alert"]["alertId"])
    
    def test_create_test_alert_ml_drift_high(self):
        """POST /api/system-alerts/test creates ML_DRIFT_HIGH alert"""
        response = self.session.post(
            f"{BASE_URL}/api/system-alerts/test",
            json={"type": "ML_DRIFT_HIGH"}
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert data["alert"]["type"] == "ML_DRIFT_HIGH"
        assert data["alert"]["severity"] == "HIGH"
        
        self.created_alert_ids.append(data["alert"]["alertId"])
    
    # ==================== POST /api/system-alerts/:alertId/ack ====================
    
    def test_acknowledge_alert_success(self):
        """POST /api/system-alerts/:alertId/ack acknowledges alert"""
        # First create a test alert
        create_response = self.session.post(
            f"{BASE_URL}/api/system-alerts/test",
            json={"type": "ML_MODE_CHANGE"}
        )
        assert create_response.status_code == 201
        alert_id = create_response.json()["alert"]["alertId"]
        
        # Acknowledge it
        ack_response = self.session.post(
            f"{BASE_URL}/api/system-alerts/{alert_id}/ack",
            json={}
        )
        
        assert ack_response.status_code == 200
        data = ack_response.json()
        
        assert data["success"] is True
        assert data["message"] == "Alert acknowledged"
        assert data["alertId"] == alert_id
        
        # Verify status changed
        get_response = self.session.get(
            f"{BASE_URL}/api/system-alerts",
            params={"status": "ACKED"}
        )
        acked_alerts = get_response.json()["alerts"]
        acked_ids = [a["alertId"] for a in acked_alerts]
        assert alert_id in acked_ids
    
    def test_acknowledge_alert_not_found(self):
        """POST /api/system-alerts/:alertId/ack returns 404 for invalid alertId"""
        response = self.session.post(
            f"{BASE_URL}/api/system-alerts/invalid_alert_id_12345/ack",
            json={}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert "not found" in data["error"].lower() or "already" in data["error"].lower()
    
    def test_acknowledge_already_acked_alert(self):
        """POST /api/system-alerts/:alertId/ack returns 404 for already acked alert"""
        # Create and ack an alert
        create_response = self.session.post(
            f"{BASE_URL}/api/system-alerts/test",
            json={"type": "ML_MODE_CHANGE"}
        )
        alert_id = create_response.json()["alert"]["alertId"]
        
        # First ack
        self.session.post(f"{BASE_URL}/api/system-alerts/{alert_id}/ack", json={})
        
        # Second ack should fail
        response = self.session.post(
            f"{BASE_URL}/api/system-alerts/{alert_id}/ack",
            json={}
        )
        
        assert response.status_code == 404
    
    # ==================== Integration Tests ====================
    
    def test_create_alert_and_verify_in_list(self):
        """Create alert and verify it appears in list"""
        # Create alert
        create_response = self.session.post(
            f"{BASE_URL}/api/system-alerts/test",
            json={"type": "ML_MODE_CHANGE"}
        )
        assert create_response.status_code == 201
        alert_id = create_response.json()["alert"]["alertId"]
        self.created_alert_ids.append(alert_id)
        
        # Verify in list
        list_response = self.session.get(f"{BASE_URL}/api/system-alerts")
        alerts = list_response.json()["alerts"]
        alert_ids = [a["alertId"] for a in alerts]
        
        assert alert_id in alert_ids
    
    def test_create_alert_updates_summary(self):
        """Create alert and verify summary counts update"""
        # Get initial summary
        initial_summary = self.session.get(f"{BASE_URL}/api/system-alerts/summary").json()
        initial_total = initial_summary["total"]
        
        # Create alert
        create_response = self.session.post(
            f"{BASE_URL}/api/system-alerts/test",
            json={"type": "ML_MODE_CHANGE"}
        )
        assert create_response.status_code == 201
        self.created_alert_ids.append(create_response.json()["alert"]["alertId"])
        
        # Get updated summary
        updated_summary = self.session.get(f"{BASE_URL}/api/system-alerts/summary").json()
        
        assert updated_summary["total"] == initial_total + 1
    
    def test_acknowledge_alert_updates_summary(self):
        """Acknowledge alert and verify active count decreases"""
        # Create alert
        create_response = self.session.post(
            f"{BASE_URL}/api/system-alerts/test",
            json={"type": "ML_MODE_CHANGE"}
        )
        alert_id = create_response.json()["alert"]["alertId"]
        
        # Get summary before ack
        before_summary = self.session.get(f"{BASE_URL}/api/system-alerts/summary").json()
        before_active = before_summary["active"]
        
        # Acknowledge
        self.session.post(f"{BASE_URL}/api/system-alerts/{alert_id}/ack", json={})
        
        # Get summary after ack
        after_summary = self.session.get(f"{BASE_URL}/api/system-alerts/summary").json()
        
        assert after_summary["active"] == before_active - 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
