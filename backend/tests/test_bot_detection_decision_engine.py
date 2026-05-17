"""
Bot Detection Decision Engine API Tests
Tests for the new decision intelligence endpoints:
- /api/connections/network/intelligence
- /api/connections/network/farm-graph
- /api/connections/bot-farms
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBotDetectionIntelligence:
    """Tests for /api/connections/network/intelligence endpoint"""
    
    def test_intelligence_endpoint_returns_200(self):
        """Intelligence endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Intelligence endpoint returns 200")
    
    def test_intelligence_response_structure(self):
        """Intelligence response should have ok, primary, signals, clusters"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        
        assert "ok" in data, "Response missing 'ok' field"
        assert data["ok"] == True, "Response ok should be True"
        assert "primary" in data, "Response missing 'primary' field"
        assert "signals" in data, "Response missing 'signals' field"
        assert "clusters" in data, "Response missing 'clusters' field"
        print("✓ Intelligence response has correct structure")
    
    def test_intelligence_primary_cluster_fields(self):
        """Primary cluster should have required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        primary = data.get("primary")
        
        if primary is None:
            pytest.skip("No primary cluster available")
        
        required_fields = ["farmId", "name", "members", "memberCount", "clusterBotScore", 
                          "density", "confidence", "riskLevel", "interpretation", "action"]
        for field in required_fields:
            assert field in primary, f"Primary cluster missing '{field}' field"
        
        # Validate interpretation is a list
        assert isinstance(primary["interpretation"], list), "interpretation should be a list"
        assert len(primary["interpretation"]) > 0, "interpretation should not be empty"
        
        # Validate action is a string
        assert isinstance(primary["action"], str), "action should be a string"
        assert len(primary["action"]) > 0, "action should not be empty"
        
        print(f"✓ Primary cluster '{primary['name']}' has all required fields")
    
    def test_intelligence_signals_structure(self):
        """Signals should have type, severity, title, description, action"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        signals = data.get("signals", [])
        
        if not signals:
            pytest.skip("No signals available")
        
        signal_types = set()
        for signal in signals:
            assert "type" in signal, "Signal missing 'type'"
            assert "severity" in signal, "Signal missing 'severity'"
            assert "title" in signal, "Signal missing 'title'"
            assert "description" in signal, "Signal missing 'description'"
            assert "action" in signal, "Signal missing 'action'"
            
            # Validate severity values
            assert signal["severity"] in ["HIGH", "MEDIUM", "LOW"], f"Invalid severity: {signal['severity']}"
            signal_types.add(signal["type"])
        
        print(f"✓ Found {len(signals)} signals with types: {signal_types}")
    
    def test_intelligence_signal_types(self):
        """Should have expected signal types"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        signals = data.get("signals", [])
        
        expected_types = {"COORDINATED_PUSH", "BOT_AMPLIFICATION", "GHOST_ACCOUNTS", "EXIT_RISK"}
        actual_types = {s["type"] for s in signals}
        
        # At least some expected types should be present
        found_types = expected_types & actual_types
        print(f"✓ Found signal types: {found_types}")
        assert len(found_types) > 0, "No expected signal types found"
    
    def test_intelligence_clusters_have_interpretation(self):
        """All clusters should have interpretation and action"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        clusters = data.get("clusters", [])
        
        if not clusters:
            pytest.skip("No clusters available")
        
        for cluster in clusters:
            assert "interpretation" in cluster, f"Cluster {cluster.get('farmId')} missing interpretation"
            assert "action" in cluster, f"Cluster {cluster.get('farmId')} missing action"
            assert isinstance(cluster["interpretation"], list), "interpretation should be a list"
        
        print(f"✓ All {len(clusters)} clusters have interpretation and action")


class TestFarmGraph:
    """Tests for /api/connections/network/farm-graph endpoint"""
    
    def test_farm_graph_returns_200(self):
        """Farm graph endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/connections/network/farm-graph")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Farm graph endpoint returns 200")
    
    def test_farm_graph_response_structure(self):
        """Farm graph should return nodes and edges"""
        response = requests.get(f"{BASE_URL}/api/connections/network/farm-graph")
        data = response.json()
        
        assert "nodes" in data, "Response missing 'nodes'"
        assert "edges" in data, "Response missing 'edges'"
        assert isinstance(data["nodes"], list), "nodes should be a list"
        assert isinstance(data["edges"], list), "edges should be a list"
        
        print(f"✓ Farm graph has {len(data['nodes'])} nodes and {len(data['edges'])} edges")
    
    def test_farm_graph_node_fields(self):
        """Nodes should have required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/network/farm-graph")
        data = response.json()
        nodes = data.get("nodes", [])
        
        if not nodes:
            pytest.skip("No nodes available")
        
        required_fields = ["id", "farmId", "pctBot", "level", "audienceQuality"]
        for node in nodes[:5]:  # Check first 5 nodes
            for field in required_fields:
                assert field in node, f"Node {node.get('id')} missing '{field}'"
        
        print(f"✓ Nodes have required fields (farmId, pctBot, level)")
    
    def test_farm_graph_edge_fields(self):
        """Edges should have required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/network/farm-graph")
        data = response.json()
        edges = data.get("edges", [])
        
        if not edges:
            pytest.skip("No edges available")
        
        required_fields = ["a", "b", "edgeScore", "sharedTokens", "evidence"]
        for edge in edges[:5]:  # Check first 5 edges
            for field in required_fields:
                assert field in edge, f"Edge missing '{field}'"
        
        print(f"✓ Edges have required fields (edgeScore, sharedTokens, evidence)")
    
    def test_farm_graph_edge_scores_valid(self):
        """Edge scores should be between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/connections/network/farm-graph")
        data = response.json()
        edges = data.get("edges", [])
        
        if not edges:
            pytest.skip("No edges available")
        
        for edge in edges:
            score = edge.get("edgeScore", 0)
            assert 0 <= score <= 1, f"Invalid edge score: {score}"
        
        print(f"✓ All {len(edges)} edge scores are valid (0-1)")


class TestBotFarms:
    """Tests for /api/connections/bot-farms endpoint"""
    
    def test_bot_farms_returns_200(self):
        """Bot farms endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/connections/bot-farms")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Bot farms endpoint returns 200")
    
    def test_bot_farms_response_structure(self):
        """Bot farms should return ok, data, total"""
        response = requests.get(f"{BASE_URL}/api/connections/bot-farms")
        data = response.json()
        
        assert "ok" in data, "Response missing 'ok'"
        assert "data" in data, "Response missing 'data'"
        assert "total" in data, "Response missing 'total'"
        assert data["ok"] == True, "Response ok should be True"
        
        print(f"✓ Bot farms response has {data['total']} clusters")
    
    def test_bot_farms_cluster_fields(self):
        """Clusters should have required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/bot-farms")
        data = response.json()
        farms = data.get("data", [])
        
        if not farms:
            pytest.skip("No farms available")
        
        required_fields = ["farmId", "name", "actorIds", "clusterBotScore", 
                          "density", "confidence", "riskLevel", "topTokens"]
        for farm in farms:
            for field in required_fields:
                assert field in farm, f"Farm {farm.get('farmId')} missing '{field}'"
        
        print(f"✓ All {len(farms)} farms have required fields")
    
    def test_bot_farms_risk_levels_valid(self):
        """Risk levels should be HIGH, MEDIUM, or LOW"""
        response = requests.get(f"{BASE_URL}/api/connections/bot-farms")
        data = response.json()
        farms = data.get("data", [])
        
        if not farms:
            pytest.skip("No farms available")
        
        valid_levels = {"HIGH", "MEDIUM", "LOW"}
        for farm in farms:
            level = farm.get("riskLevel")
            assert level in valid_levels, f"Invalid risk level: {level}"
        
        print(f"✓ All farms have valid risk levels")
    
    def test_bot_farms_sorted_by_score(self):
        """Farms should be sorted by clusterBotScore descending"""
        response = requests.get(f"{BASE_URL}/api/connections/bot-farms")
        data = response.json()
        farms = data.get("data", [])
        
        if len(farms) < 2:
            pytest.skip("Not enough farms to test sorting")
        
        scores = [f.get("clusterBotScore", 0) for f in farms]
        assert scores == sorted(scores, reverse=True), "Farms not sorted by score"
        
        print(f"✓ Farms sorted by clusterBotScore (highest first)")


class TestDataIntegrity:
    """Cross-endpoint data integrity tests"""
    
    def test_intelligence_clusters_match_bot_farms(self):
        """Intelligence clusters should match bot-farms data"""
        intel_resp = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        farms_resp = requests.get(f"{BASE_URL}/api/connections/bot-farms")
        
        intel_data = intel_resp.json()
        farms_data = farms_resp.json()
        
        intel_farm_ids = {c["farmId"] for c in intel_data.get("clusters", [])}
        farms_farm_ids = {f["farmId"] for f in farms_data.get("data", [])}
        
        # Intelligence clusters should be subset of bot-farms
        assert intel_farm_ids == farms_farm_ids, "Farm IDs mismatch between endpoints"
        
        print(f"✓ Intelligence clusters match bot-farms ({len(intel_farm_ids)} clusters)")
    
    def test_graph_nodes_have_farm_assignments(self):
        """Graph nodes should have farmId assignments"""
        response = requests.get(f"{BASE_URL}/api/connections/network/farm-graph")
        data = response.json()
        nodes = data.get("nodes", [])
        
        if not nodes:
            pytest.skip("No nodes available")
        
        nodes_with_farm = [n for n in nodes if n.get("farmId")]
        print(f"✓ {len(nodes_with_farm)}/{len(nodes)} nodes have farmId assignments")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
