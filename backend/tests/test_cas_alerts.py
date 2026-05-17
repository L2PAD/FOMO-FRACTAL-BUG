"""
CAS (Coordinated Activity Score) + Alerts System Tests
=======================================================
Tests for P1 features:
- GET /api/connections/overview/cas - CAS calculation endpoint
- GET /api/connections/overview/alerts - Fetch alerts
- POST /api/connections/overview/alerts/evaluate - Generate alerts
- POST /api/connections/overview/alerts/read - Mark alerts as read
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCASEndpoint:
    """P1: CAS (Coordinated Activity Score) endpoint tests"""
    
    def test_cas_endpoint_returns_200(self):
        """Test CAS endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/cas")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ CAS endpoint returns 200")
    
    def test_cas_response_structure(self):
        """Test CAS response has required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/cas")
        data = response.json()
        
        # Verify ok field
        assert data.get('ok') == True, "Response should have ok: true"
        print("✓ CAS response has ok: true")
        
        # Verify CAS score
        assert 'cas' in data, "Response should have 'cas' field"
        assert isinstance(data['cas'], (int, float)), "CAS should be numeric"
        assert 0 <= data['cas'] <= 100, f"CAS should be 0-100, got {data['cas']}"
        print(f"✓ CAS score: {data['cas']}")
        
        # Verify label
        assert 'label' in data, "Response should have 'label' field"
        assert data['label'] in ['Organic', 'Watch', 'Coordinated', 'Possible Pump'], f"Invalid label: {data['label']}"
        print(f"✓ CAS label: {data['label']}")
        
        # Verify severity
        assert 'severity' in data, "Response should have 'severity' field"
        assert data['severity'] in ['low', 'medium', 'high', 'critical'], f"Invalid severity: {data['severity']}"
        print(f"✓ CAS severity: {data['severity']}")
    
    def test_cas_components(self):
        """Test CAS components are present"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/cas")
        data = response.json()
        
        assert 'components' in data, "Response should have 'components' field"
        components = data['components']
        
        required_components = ['clusterDensity', 'mentionVelocity', 'farmOverlap', 'botProbability']
        for comp in required_components:
            assert comp in components, f"Missing component: {comp}"
            assert isinstance(components[comp], (int, float)), f"{comp} should be numeric"
        
        print(f"✓ CAS components: clusterDensity={components['clusterDensity']}, mentionVelocity={components['mentionVelocity']}, farmOverlap={components['farmOverlap']}, botProbability={components['botProbability']}")
    
    def test_cas_context(self):
        """Test CAS context is present"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/cas")
        data = response.json()
        
        assert 'context' in data, "Response should have 'context' field"
        context = data['context']
        
        required_context = ['pumpTokens', 'momentumTokens', 'totalClusters', 'lowCredClusters', 'topPumpTokens']
        for ctx in required_context:
            assert ctx in context, f"Missing context: {ctx}"
        
        assert isinstance(context['topPumpTokens'], list), "topPumpTokens should be a list"
        print(f"✓ CAS context: {context['pumpTokens']} pump tokens, {context['totalClusters']} clusters")


class TestAlertsEndpoints:
    """P1: Alerts system endpoint tests"""
    
    def test_alerts_list_returns_200(self):
        """Test alerts list endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/alerts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Alerts list endpoint returns 200")
    
    def test_alerts_response_structure(self):
        """Test alerts response has required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/alerts")
        data = response.json()
        
        assert data.get('ok') == True, "Response should have ok: true"
        assert 'alerts' in data, "Response should have 'alerts' field"
        assert 'unreadCount' in data, "Response should have 'unreadCount' field"
        assert isinstance(data['alerts'], list), "'alerts' should be a list"
        assert isinstance(data['unreadCount'], int), "'unreadCount' should be integer"
        print(f"✓ Alerts response: {len(data['alerts'])} alerts, {data['unreadCount']} unread")
    
    def test_alert_item_structure(self):
        """Test individual alert has required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/alerts")
        data = response.json()
        
        if len(data['alerts']) > 0:
            alert = data['alerts'][0]
            required_fields = ['id', 'type', 'severity', 'title', 'message', 'read', 'createdAt']
            for field in required_fields:
                assert field in alert, f"Alert missing field: {field}"
            
            assert alert['severity'] in ['low', 'medium', 'high', 'critical', 'info'], f"Invalid severity: {alert['severity']}"
            print(f"✓ Alert structure valid: {alert['type']} - {alert['title']}")
        else:
            print("⚠ No alerts to verify structure (this is OK)")
    
    def test_alerts_limit_param(self):
        """Test alerts limit parameter"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/alerts?limit=5")
        data = response.json()
        
        assert len(data['alerts']) <= 5, f"Expected at most 5 alerts, got {len(data['alerts'])}"
        print(f"✓ Alerts limit param works: returned {len(data['alerts'])} alerts")
    
    def test_alerts_evaluate_returns_200(self):
        """Test alerts evaluate endpoint returns 200"""
        response = requests.post(f"{BASE_URL}/api/connections/overview/alerts/evaluate")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Alerts evaluate endpoint returns 200")
    
    def test_alerts_evaluate_response_structure(self):
        """Test evaluate response has required fields"""
        response = requests.post(f"{BASE_URL}/api/connections/overview/alerts/evaluate")
        data = response.json()
        
        assert data.get('ok') == True, "Response should have ok: true"
        assert 'generated' in data, "Response should have 'generated' field"
        assert 'alerts' in data, "Response should have 'alerts' field"
        print(f"✓ Evaluate response: generated {data['generated']} alerts")
    
    def test_alerts_read_returns_200(self):
        """Test mark alerts as read endpoint returns 200"""
        response = requests.post(
            f"{BASE_URL}/api/connections/overview/alerts/read",
            headers={'Content-Type': 'application/json'},
            json={}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Mark all read endpoint returns 200")
    
    def test_alerts_read_response_structure(self):
        """Test mark read response"""
        response = requests.post(
            f"{BASE_URL}/api/connections/overview/alerts/read",
            headers={'Content-Type': 'application/json'},
            json={}
        )
        data = response.json()
        
        assert data.get('ok') == True, "Response should have ok: true"
        print("✓ Mark all read response valid")


class TestIntegrationStatus:
    """P0: Integration status API test (used by parser wrapper)"""
    
    def test_integration_status_returns_200(self):
        """Test integration status endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/integration/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Integration status endpoint returns 200")
    
    def test_integration_status_structure(self):
        """Test integration status response structure"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/integration/status")
        data = response.json()
        
        assert data.get('ok') == True, "Response should have ok: true"
        assert 'data' in data, "Response should have 'data' field"
        
        status_data = data['data']
        assert 'state' in status_data, "Status should have 'state' field"
        assert 'sessions' in status_data, "Status should have 'sessions' field"
        
        sessions = status_data['sessions']
        assert 'ok' in sessions, "Sessions should have 'ok' count"
        assert 'stale' in sessions, "Sessions should have 'stale' count"
        
        print(f"✓ Integration status: state={status_data['state']}, sessions.ok={sessions['ok']}, sessions.stale={sessions['stale']}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
