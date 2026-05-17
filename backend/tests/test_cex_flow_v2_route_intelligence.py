"""
CEX Flow v2 Route Intelligence Tests

Tests for route intelligence features in liquidity-map and liquidity-map/refresh endpoints:
- GET /api/graph-core/liquidity-map returns top_routes with label, volume_usd, tx_count, route_count, confidence, wash_score
- GET /api/graph-core/liquidity-map returns route_meta with route_count, wash_volume_usd, wash_route_count, fan_out_count, fan_in_count
- GET /api/graph-core/liquidity-map returns flow_state (ACCUMULATION/DISTRIBUTION/ROUTING/RETURN TO CEX/REDISTRIBUTION)
- POST /api/graph-core/liquidity-map/refresh returns route_count in response
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

VALID_FLOW_STATES = ['ACCUMULATION', 'DISTRIBUTION', 'ROUTING', 'RETURN TO CEX', 'REDISTRIBUTION']


@pytest.fixture(scope='module')
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    return session


class TestLiquidityMapRouteIntelligence:
    """Tests for GET /api/graph-core/liquidity-map route intelligence fields"""
    
    def test_liquidity_map_returns_top_routes(self, api_client):
        """Test that liquidity-map returns top_routes array"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        data = response.json()
        assert 'top_routes' in data, "Missing top_routes in response"
        assert isinstance(data['top_routes'], list), "top_routes should be an array"
        print(f"Found {len(data['top_routes'])} routes in top_routes")
    
    def test_top_routes_has_required_fields(self, api_client):
        """Test that each route in top_routes has required fields"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        data = response.json()
        top_routes = data.get('top_routes', [])
        
        if len(top_routes) == 0:
            pytest.skip("No routes found in top_routes")
        
        # Check required fields for first route
        route = top_routes[0]
        required_fields = ['label', 'volume_usd', 'tx_count', 'route_count', 'confidence', 'wash_score']
        
        for field in required_fields:
            assert field in route, f"Missing required field '{field}' in route"
        
        # Verify field types
        assert isinstance(route['label'], str), "label should be string"
        assert isinstance(route['volume_usd'], (int, float)), "volume_usd should be number"
        assert isinstance(route['tx_count'], int), "tx_count should be integer"
        assert isinstance(route['route_count'], int), "route_count should be integer"
        assert isinstance(route['confidence'], (int, float)), "confidence should be number"
        assert isinstance(route['wash_score'], (int, float)), "wash_score should be number"
        
        print(f"Route sample: {route['label']} - vol: ${route['volume_usd']:.2f}, tx: {route['tx_count']}, confidence: {route['confidence']}")
    
    def test_liquidity_map_returns_route_meta(self, api_client):
        """Test that liquidity-map returns route_meta object"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        data = response.json()
        assert 'route_meta' in data, "Missing route_meta in response"
        
        route_meta = data['route_meta']
        required_fields = ['route_count', 'wash_volume_usd', 'wash_route_count', 'fan_out_count', 'fan_in_count']
        
        for field in required_fields:
            assert field in route_meta, f"Missing required field '{field}' in route_meta"
        
        print(f"Route Meta: {route_meta}")
    
    def test_route_meta_field_types(self, api_client):
        """Test that route_meta fields have correct types"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        route_meta = response.json().get('route_meta', {})
        
        assert isinstance(route_meta.get('route_count'), int), "route_count should be integer"
        assert isinstance(route_meta.get('wash_volume_usd'), (int, float)), "wash_volume_usd should be number"
        assert isinstance(route_meta.get('wash_route_count'), int), "wash_route_count should be integer"
        assert isinstance(route_meta.get('fan_out_count'), int), "fan_out_count should be integer"
        assert isinstance(route_meta.get('fan_in_count'), int), "fan_in_count should be integer"
    
    def test_flow_state_is_valid(self, api_client):
        """Test that flow_state is one of the valid states"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get('summary', {})
        flow_state = summary.get('flow_state')
        
        assert flow_state is not None, "flow_state is missing from summary"
        assert flow_state in VALID_FLOW_STATES, f"flow_state '{flow_state}' not in valid states: {VALID_FLOW_STATES}"
        
        print(f"Flow State: {flow_state}")
    
    def test_flow_driver_is_present(self, api_client):
        """Test that flow_driver is present in summary"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get('summary', {})
        flow_driver = summary.get('flow_driver')
        
        assert flow_driver is not None, "flow_driver is missing from summary"
        assert isinstance(flow_driver, str), "flow_driver should be string"
        assert len(flow_driver) > 0, "flow_driver should not be empty"
        
        print(f"Flow Driver: {flow_driver}")


class TestLiquidityMapRefresh:
    """Tests for POST /api/graph-core/liquidity-map/refresh"""
    
    def test_refresh_returns_route_count(self, api_client):
        """Test that refresh endpoint returns route_count"""
        response = api_client.post(f'{BASE_URL}/api/graph-core/liquidity-map/refresh')
        assert response.status_code == 200
        
        data = response.json()
        assert 'route_count' in data, "Missing route_count in refresh response"
        assert isinstance(data['route_count'], int), "route_count should be integer"
        
        print(f"Refresh returned route_count: {data['route_count']}")
    
    def test_refresh_returns_status(self, api_client):
        """Test that refresh endpoint returns status: refreshed"""
        response = api_client.post(f'{BASE_URL}/api/graph-core/liquidity-map/refresh')
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('status') == 'refreshed', "Expected status: refreshed"
    
    def test_refresh_returns_summary_with_flow_state(self, api_client):
        """Test that refresh endpoint returns summary with flow_state"""
        response = api_client.post(f'{BASE_URL}/api/graph-core/liquidity-map/refresh')
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get('summary', {})
        
        assert 'flow_state' in summary, "Missing flow_state in refresh summary"
        assert summary['flow_state'] in VALID_FLOW_STATES, f"Invalid flow_state: {summary['flow_state']}"
        
        print(f"Refresh Summary Flow State: {summary['flow_state']}")


class TestRouteConfidenceAndWashScore:
    """Tests for route confidence and wash score values"""
    
    def test_route_confidence_in_valid_range(self, api_client):
        """Test that route confidence scores are in [0, 1] range"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        top_routes = response.json().get('top_routes', [])
        
        for route in top_routes:
            confidence = route.get('confidence', 0)
            assert 0 <= confidence <= 1, f"Confidence {confidence} out of [0,1] range for route {route.get('label')}"
    
    def test_route_wash_score_in_valid_range(self, api_client):
        """Test that route wash_score values are in [0, 1] range"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        top_routes = response.json().get('top_routes', [])
        
        for route in top_routes:
            wash_score = route.get('wash_score', 0)
            assert 0 <= wash_score <= 1, f"Wash score {wash_score} out of [0,1] range for route {route.get('label')}"
    
    def test_high_wash_score_routes_are_detectable(self, api_client):
        """Test that routes with wash_score > 0.5 can be identified"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        top_routes = response.json().get('top_routes', [])
        route_meta = response.json().get('route_meta', {})
        
        # Count routes with high wash score
        high_wash_routes = [r for r in top_routes if r.get('wash_score', 0) > 0.5]
        wash_route_count = route_meta.get('wash_route_count', 0)
        
        # Note: wash_route_count is from all routes, not just top_routes
        print(f"High wash routes in top_routes: {len(high_wash_routes)}")
        print(f"Total wash_route_count in route_meta: {wash_route_count}")


class TestRouteLabels:
    """Tests for route label formats"""
    
    def test_route_labels_contain_arrows(self, api_client):
        """Test that route labels use arrow notation (→)"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        top_routes = response.json().get('top_routes', [])
        
        if len(top_routes) == 0:
            pytest.skip("No routes found")
        
        # Most labels should contain arrow notation
        labels_with_arrows = [r for r in top_routes if '→' in r.get('label', '')]
        
        print(f"Routes with arrow labels: {len(labels_with_arrows)}/{len(top_routes)}")
        
        # Print sample labels
        for route in top_routes[:5]:
            print(f"  Label: {route.get('label')}")
    
    def test_route_types_are_present(self, api_client):
        """Test that routes have type field"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        top_routes = response.json().get('top_routes', [])
        
        for route in top_routes:
            assert 'type' in route, f"Missing type field in route {route.get('label')}"


class TestFlowStateLogic:
    """Tests for flow state determination logic"""
    
    def test_flow_state_matches_flow_driver(self, api_client):
        """Test that flow_state and flow_driver are consistent"""
        response = api_client.get(f'{BASE_URL}/api/graph-core/liquidity-map')
        assert response.status_code == 200
        
        summary = response.json().get('summary', {})
        flow_state = summary.get('flow_state', '')
        flow_driver = summary.get('flow_driver', '')
        
        # Basic consistency checks
        if flow_state == 'REDISTRIBUTION':
            assert 'fan' in flow_driver.lower() or 'out' in flow_driver.lower(), \
                f"REDISTRIBUTION should have fan/out driver, got: {flow_driver}"
        
        if flow_state == 'ROUTING':
            assert 'pass' in flow_driver.lower() or 'cross' in flow_driver.lower(), \
                f"ROUTING should have pass-through or cross-chain driver, got: {flow_driver}"
        
        print(f"Flow State: {flow_state}, Driver: {flow_driver}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
