"""
Wash / Fake Routing Detection Integration Tests
================================================
Tests the new P1 feature: Wash detection integrated into CEX Flow mode.

Tested endpoints:
1. GET /api/graph-core/wash/alerts - returns wash alerts from DB
2. POST /api/graph-core/wash/scan - triggers wash detection and returns results
3. GET /api/graph-core/render-seeds?mode=cex_flow&depth=2 - returns cex_routes with wash analysis
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestWashAlerts:
    """Test GET /api/graph-core/wash/alerts endpoint"""
    
    def test_wash_alerts_endpoint_returns_200(self):
        """Verify wash/alerts endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/graph-core/wash/alerts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /wash/alerts returns 200")
    
    def test_wash_alerts_response_structure(self):
        """Verify wash/alerts returns expected data structure"""
        response = requests.get(f"{BASE_URL}/api/graph-core/wash/alerts")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "alerts" in data, "Response missing 'alerts' field"
        assert "total" in data, "Response missing 'total' field"
        assert "returned" in data, "Response missing 'returned' field"
        assert "stats" in data, "Response missing 'stats' field"
        
        assert isinstance(data["alerts"], list), "alerts should be a list"
        assert isinstance(data["total"], int), "total should be int"
        print(f"PASS: wash/alerts structure OK - {data['total']} total alerts")
    
    def test_wash_alerts_with_pattern_filter(self):
        """Test filtering wash alerts by pattern type"""
        response = requests.get(f"{BASE_URL}/api/graph-core/wash/alerts?pattern_type=cyclical_flow")
        assert response.status_code == 200
        data = response.json()
        
        # If alerts returned, they should all match the filter
        for alert in data.get("alerts", []):
            assert alert.get("pattern_type") == "cyclical_flow", f"Got unexpected pattern: {alert.get('pattern_type')}"
        print(f"PASS: Pattern filter works - {len(data.get('alerts', []))} cyclical_flow alerts")
    
    def test_wash_alerts_with_min_confidence(self):
        """Test filtering wash alerts by minimum confidence"""
        response = requests.get(f"{BASE_URL}/api/graph-core/wash/alerts?min_confidence=0.5")
        assert response.status_code == 200
        data = response.json()
        
        for alert in data.get("alerts", []):
            confidence = alert.get("confidence", 0)
            assert confidence >= 0.5, f"Alert confidence {confidence} is below min 0.5"
        print(f"PASS: Min confidence filter works - {len(data.get('alerts', []))} alerts with confidence >= 0.5")


class TestWashScan:
    """Test POST /api/graph-core/wash/scan endpoint"""
    
    def test_wash_scan_endpoint_returns_200(self):
        """Verify wash/scan endpoint triggers detection and returns OK"""
        response = requests.post(f"{BASE_URL}/api/graph-core/wash/scan")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /wash/scan returns 200")
    
    def test_wash_scan_response_structure(self):
        """Verify wash/scan returns expected result structure"""
        response = requests.post(f"{BASE_URL}/api/graph-core/wash/scan")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "status" in data, "Response missing 'status' field"
        assert data["status"] == "completed", f"Expected status=completed, got {data['status']}"
        assert "alerts_found" in data, "Response missing 'alerts_found' field"
        assert "by_type" in data, "Response missing 'by_type' field"
        
        assert isinstance(data["alerts_found"], int), "alerts_found should be int"
        assert isinstance(data["by_type"], dict), "by_type should be dict"
        
        print(f"PASS: wash/scan completed - {data['alerts_found']} alerts found")
        print(f"      By type: {data['by_type']}")


class TestCexFlowWithWashAnalysis:
    """Test CEX Flow mode render-seeds endpoint returns wash analysis"""
    
    def test_discovery_endpoint_returns_seeds(self):
        """Verify discovery endpoint returns CEX flow seeds"""
        response = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=cex_flow&limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert "seed_nodes" in data, "Response missing 'seed_nodes'"
        seeds = data.get("seed_nodes", [])
        assert len(seeds) > 0, "No seed nodes returned for CEX flow discovery"
        
        print(f"PASS: Discovery found {len(seeds)} seeds for CEX flow mode")
        return [s.get("id") for s in seeds]
    
    def test_render_seeds_cex_flow_returns_cex_routes(self):
        """Verify render-seeds with mode=cex_flow returns cex_routes array"""
        # First get seeds
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=cex_flow&limit=5")
        assert disc_resp.status_code == 200
        seeds = disc_resp.json().get("seed_nodes", [])
        
        if not seeds:
            pytest.skip("No seeds available for CEX flow")
        
        seed_ids = ",".join([s.get("id") for s in seeds[:3]])
        
        # Render seeds with cex_flow mode and depth=2
        response = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&mode=cex_flow&depth=2&limit=100")
        assert response.status_code == 200
        data = response.json()
        
        assert "nodes" in data, "Response missing 'nodes'"
        assert "edges" in data, "Response missing 'edges'"
        assert "cex_routes" in data, "Response missing 'cex_routes' - this is the key field for CEX flow"
        
        print(f"PASS: render-seeds cex_flow returns {len(data['nodes'])} nodes, {len(data['edges'])} edges, {len(data.get('cex_routes', []))} cex_routes")
    
    def test_cex_routes_have_wash_fields(self):
        """Verify each route in cex_routes has wash_flags and wash_score"""
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=cex_flow&limit=5")
        assert disc_resp.status_code == 200
        seeds = disc_resp.json().get("seed_nodes", [])
        
        if not seeds:
            pytest.skip("No seeds available for CEX flow")
        
        seed_ids = ",".join([s.get("id") for s in seeds[:3]])
        
        response = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&mode=cex_flow&depth=2&limit=100")
        assert response.status_code == 200
        data = response.json()
        
        cex_routes = data.get("cex_routes", [])
        if not cex_routes:
            pytest.skip("No CEX routes found in response")
        
        for i, route in enumerate(cex_routes):
            assert "wash_flags" in route, f"Route {i} missing 'wash_flags' field"
            assert "wash_score" in route, f"Route {i} missing 'wash_score' field"
            
            # Validate types
            assert isinstance(route["wash_flags"], list), f"Route {i} wash_flags should be list"
            assert isinstance(route["wash_score"], (int, float)), f"Route {i} wash_score should be number"
            
            # wash_score should be 0-1
            score = route["wash_score"]
            assert 0 <= score <= 1, f"Route {i} wash_score {score} outside [0,1] range"
        
        # Count routes with wash signals
        flagged_count = sum(1 for r in cex_routes if r.get("wash_score", 0) > 0)
        print(f"PASS: All {len(cex_routes)} routes have wash_flags and wash_score fields")
        print(f"      {flagged_count}/{len(cex_routes)} routes have wash_score > 0")
    
    def test_cex_routes_wash_flags_structure(self):
        """Verify wash_flags array has correct structure when present"""
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=cex_flow&limit=5")
        assert disc_resp.status_code == 200
        seeds = disc_resp.json().get("seed_nodes", [])
        
        if not seeds:
            pytest.skip("No seeds available for CEX flow")
        
        seed_ids = ",".join([s.get("id") for s in seeds[:3]])
        
        response = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&mode=cex_flow&depth=2&limit=100")
        assert response.status_code == 200
        cex_routes = response.json().get("cex_routes", [])
        
        # Find a route with wash flags
        routes_with_flags = [r for r in cex_routes if r.get("wash_flags")]
        if not routes_with_flags:
            print("WARN: No routes with wash_flags found - this may be OK if no patterns detected")
            return
        
        # Validate flag structure
        valid_types = {"bidirectional", "pass_through", "shared_intermediates", "circular", "volume_symmetric"}
        valid_severities = {"high", "medium", "low"}
        
        for route in routes_with_flags:
            for flag in route["wash_flags"]:
                assert "type" in flag, f"Flag missing 'type' field"
                assert "label" in flag, f"Flag missing 'label' field"
                assert "description" in flag, f"Flag missing 'description' field"
                assert "severity" in flag, f"Flag missing 'severity' field"
                
                assert flag["type"] in valid_types, f"Invalid flag type: {flag['type']}"
                assert flag["severity"] in valid_severities, f"Invalid severity: {flag['severity']}"
        
        flag_types = set()
        for r in routes_with_flags:
            for f in r["wash_flags"]:
                flag_types.add(f["type"])
        
        print(f"PASS: {len(routes_with_flags)} routes have wash flags")
        print(f"      Detected pattern types: {flag_types}")
    
    def test_cex_routes_db_wash_alerts_enrichment(self):
        """Verify routes are enriched with db_wash_alerts when matching alerts exist"""
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=cex_flow&limit=5")
        assert disc_resp.status_code == 200
        seeds = disc_resp.json().get("seed_nodes", [])
        
        if not seeds:
            pytest.skip("No seeds available for CEX flow")
        
        seed_ids = ",".join([s.get("id") for s in seeds[:3]])
        
        response = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&mode=cex_flow&depth=2&limit=100")
        assert response.status_code == 200
        cex_routes = response.json().get("cex_routes", [])
        
        # Check if any routes have db_wash_alerts
        routes_with_db_alerts = [r for r in cex_routes if r.get("db_wash_alerts")]
        
        if routes_with_db_alerts:
            # Validate structure
            for route in routes_with_db_alerts:
                for alert in route["db_wash_alerts"]:
                    assert "alert_id" in alert, "DB alert missing 'alert_id'"
                    assert "pattern_type" in alert, "DB alert missing 'pattern_type'"
            print(f"PASS: {len(routes_with_db_alerts)} routes enriched with db_wash_alerts")
        else:
            print("INFO: No routes have db_wash_alerts - this is OK if no DB alerts match route nodes")


class TestCexFlowRouteStructure:
    """Verify complete CEX route data structure"""
    
    def test_cex_route_required_fields(self):
        """Verify each CEX route has all required fields"""
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=cex_flow&limit=5")
        assert disc_resp.status_code == 200
        seeds = disc_resp.json().get("seed_nodes", [])
        
        if not seeds:
            pytest.skip("No seeds available for CEX flow")
        
        seed_ids = ",".join([s.get("id") for s in seeds[:3]])
        
        response = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&mode=cex_flow&depth=2&limit=100")
        assert response.status_code == 200
        cex_routes = response.json().get("cex_routes", [])
        
        if not cex_routes:
            pytest.skip("No CEX routes returned")
        
        required_fields = {"from_cex", "to_cex", "path", "hops", "wash_flags", "wash_score"}
        
        for i, route in enumerate(cex_routes):
            missing = required_fields - set(route.keys())
            assert not missing, f"Route {i} missing fields: {missing}"
            
            # Validate types
            assert isinstance(route["from_cex"], str), f"Route {i} from_cex should be string"
            assert isinstance(route["to_cex"], str), f"Route {i} to_cex should be string"
            assert isinstance(route["path"], list), f"Route {i} path should be list"
            assert isinstance(route["hops"], int), f"Route {i} hops should be int"
            assert len(route["path"]) >= 2, f"Route {i} path should have at least 2 nodes"
            
            # Validate path consistency
            assert route["path"][0] == route["from_cex"], f"Route {i} path start should match from_cex"
            assert route["path"][-1] == route["to_cex"], f"Route {i} path end should match to_cex"
            assert route["hops"] == len(route["path"]) - 2, f"Route {i} hops calculation mismatch"
        
        print(f"PASS: All {len(cex_routes)} routes have valid structure")


class TestEntitySpecificCexFlow:
    """Test CEX Flow with specific entity (entity-centered exploration)"""
    
    def test_render_entity_cex_flow(self):
        """Test render endpoint for specific CEX entity with cex_flow mode"""
        # Use a known CEX node
        cex_id = "cex:0x21a31ee1afc51d94c2efccaa2092ad1028285549:ethereum"
        
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{cex_id}?mode=cex_flow&depth=2&limit=150")
        assert response.status_code == 200
        data = response.json()
        
        assert "nodes" in data
        assert "edges" in data
        
        # cex_routes should be present when mode=cex_flow
        if "cex_routes" in data:
            cex_routes = data["cex_routes"]
            print(f"PASS: Entity CEX flow render - {len(data['nodes'])} nodes, {len(cex_routes)} routes")
            
            # Verify wash fields present
            if cex_routes:
                for route in cex_routes:
                    assert "wash_flags" in route
                    assert "wash_score" in route
                print(f"      All {len(cex_routes)} routes have wash analysis fields")
        else:
            print(f"INFO: No cex_routes for this entity - {len(data['nodes'])} nodes returned")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
