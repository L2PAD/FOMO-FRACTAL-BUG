"""
Bot Detection Interpretability Layer Tests
Tests for: clickable @handles, actor modal data, human-readable names,
interpretation blocks, howToUse, metricExplanations
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestIntelligenceEndpoint:
    """Tests for /api/connections/network/intelligence endpoint"""
    
    def test_intelligence_returns_200(self):
        """Intelligence endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        assert response.status_code == 200
        print("PASS: Intelligence endpoint returns 200")
    
    def test_intelligence_has_howToUse(self):
        """Primary cluster should have howToUse field"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        primary = data.get("primary", {})
        assert "howToUse" in primary, "Primary cluster missing howToUse field"
        assert isinstance(primary["howToUse"], list), "howToUse should be a list"
        assert len(primary["howToUse"]) > 0, "howToUse should not be empty"
        print(f"PASS: howToUse found with {len(primary['howToUse'])} items")
    
    def test_intelligence_has_metricExplanations(self):
        """Primary cluster should have metricExplanations field"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        primary = data.get("primary", {})
        assert "metricExplanations" in primary, "Primary cluster missing metricExplanations"
        explanations = primary["metricExplanations"]
        assert "botScore" in explanations, "Missing botScore explanation"
        assert "density" in explanations, "Missing density explanation"
        assert "confidence" in explanations, "Missing confidence explanation"
        print("PASS: metricExplanations found with botScore, density, confidence")
    
    def test_cluster_names_human_readable(self):
        """Cluster names should be human-readable (no 'Ring')"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        clusters = data.get("clusters", [])
        
        for cluster in clusters:
            name = cluster.get("name", "")
            assert "Ring" not in name, f"Cluster name contains 'Ring': {name}"
            # Should contain descriptive words
            assert any(word in name for word in ["Coordinated", "Cross-Asset", "Cluster", "Activity", "Coordination"]), \
                f"Cluster name not human-readable: {name}"
        
        print(f"PASS: All {len(clusters)} cluster names are human-readable")
    
    def test_clusters_have_interpretation(self):
        """All clusters should have interpretation field"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        clusters = data.get("clusters", [])
        
        for cluster in clusters:
            assert "interpretation" in cluster, f"Cluster {cluster.get('farmId')} missing interpretation"
            assert isinstance(cluster["interpretation"], list), "interpretation should be a list"
            assert len(cluster["interpretation"]) > 0, "interpretation should not be empty"
        
        print(f"PASS: All {len(clusters)} clusters have interpretation")
    
    def test_clusters_have_action(self):
        """All clusters should have action field"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        clusters = data.get("clusters", [])
        
        for cluster in clusters:
            assert "action" in cluster, f"Cluster {cluster.get('farmId')} missing action"
            assert len(cluster["action"]) > 0, "action should not be empty"
        
        print(f"PASS: All {len(clusters)} clusters have action")
    
    def test_signals_have_detail_with_handles(self):
        """Signals should have detail field with @handles"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        signals = data.get("signals", [])
        
        signals_with_handles = 0
        for signal in signals:
            detail = signal.get("detail", "")
            if "@" in detail:
                signals_with_handles += 1
        
        assert signals_with_handles > 0, "No signals have @handles in detail"
        print(f"PASS: {signals_with_handles}/{len(signals)} signals have @handles in detail")


class TestActorEndpoint:
    """Tests for /api/connections/network/actor/{id} endpoint"""
    
    def test_actor_returns_200(self):
        """Actor endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/connections/network/actor/forex17227271")
        assert response.status_code == 200
        print("PASS: Actor endpoint returns 200")
    
    def test_actor_has_audience_quality(self):
        """Actor should have audienceQuality with required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/network/actor/forex17227271")
        data = response.json()
        aq = data.get("data", {}).get("audienceQuality", {})
        
        assert "pctBot" in aq, "Missing pctBot"
        assert "pctHuman" in aq, "Missing pctHuman"
        assert "aqi" in aq, "Missing aqi"
        assert "pctSuspicious" in aq, "Missing pctSuspicious"
        
        print(f"PASS: audienceQuality has pctBot={aq['pctBot']}, pctHuman={aq['pctHuman']}, aqi={aq['aqi']}")
    
    def test_actor_has_engagement(self):
        """Actor should have engagement data"""
        response = requests.get(f"{BASE_URL}/api/connections/network/actor/forex17227271")
        data = response.json()
        aq = data.get("data", {}).get("audienceQuality", {})
        engagement = aq.get("engagement", {})
        
        # Engagement may be None for some actors, but if present should have fields
        if engagement:
            assert "avgLikes" in engagement or "zeroEngagementRatio" in engagement, \
                "Engagement missing expected fields"
            print(f"PASS: engagement data found")
        else:
            print("INFO: No engagement data for this actor")
    
    def test_actor_has_connections(self):
        """Actor should have connections list"""
        response = requests.get(f"{BASE_URL}/api/connections/network/actor/forex17227271")
        data = response.json()
        actor_data = data.get("data", {})
        
        assert "connections" in actor_data, "Missing connections"
        assert "totalConnections" in actor_data, "Missing totalConnections"
        
        connections = actor_data["connections"]
        total = actor_data["totalConnections"]
        
        assert isinstance(connections, list), "connections should be a list"
        assert total == len(connections), "totalConnections should match connections length"
        
        print(f"PASS: Actor has {total} connections")
    
    def test_actor_has_farms(self):
        """Actor should have farms (cluster membership)"""
        response = requests.get(f"{BASE_URL}/api/connections/network/actor/forex17227271")
        data = response.json()
        farms = data.get("data", {}).get("farms", [])
        
        assert isinstance(farms, list), "farms should be a list"
        
        if farms:
            farm = farms[0]
            assert "farmId" in farm, "Farm missing farmId"
            assert "name" in farm, "Farm missing name"
            assert "riskLevel" in farm, "Farm missing riskLevel"
            print(f"PASS: Actor is in farm '{farm['name']}' with risk {farm['riskLevel']}")
        else:
            print("INFO: Actor not in any farm")
    
    def test_actor_unknown_returns_default(self):
        """Unknown actor should return default values"""
        response = requests.get(f"{BASE_URL}/api/connections/network/actor/unknown_actor_xyz")
        assert response.status_code == 200
        
        data = response.json()
        aq = data.get("data", {}).get("audienceQuality", {})
        
        # Should have default values
        assert aq.get("pctHuman") == 50, "Default pctHuman should be 50"
        assert aq.get("level") == "UNKNOWN", "Default level should be UNKNOWN"
        
        print("PASS: Unknown actor returns default values")


class TestFarmGraphEndpoint:
    """Tests for /api/connections/network/farm-graph endpoint"""
    
    def test_farm_graph_returns_200(self):
        """Farm graph endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/connections/network/farm-graph?minScore=0.1&limit=50")
        assert response.status_code == 200
        print("PASS: Farm graph endpoint returns 200")
    
    def test_farm_graph_nodes_have_required_fields(self):
        """Nodes should have required fields for modal display"""
        response = requests.get(f"{BASE_URL}/api/connections/network/farm-graph?minScore=0.1&limit=50")
        data = response.json()
        nodes = data.get("nodes", [])
        
        assert len(nodes) > 0, "No nodes returned"
        
        for node in nodes[:5]:  # Check first 5
            assert "id" in node, "Node missing id"
            assert "pctBot" in node, "Node missing pctBot"
            assert "audienceQuality" in node, "Node missing audienceQuality"
            assert "level" in node, "Node missing level"
        
        print(f"PASS: {len(nodes)} nodes have required fields")
    
    def test_farm_graph_edges_have_required_fields(self):
        """Edges should have required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/network/farm-graph?minScore=0.1&limit=50")
        data = response.json()
        edges = data.get("edges", [])
        
        assert len(edges) > 0, "No edges returned"
        
        for edge in edges[:5]:  # Check first 5
            assert "a" in edge, "Edge missing a"
            assert "b" in edge, "Edge missing b"
            assert "edgeScore" in edge or "overlapScore" in edge, "Edge missing score"
            assert "sharedTokens" in edge, "Edge missing sharedTokens"
        
        print(f"PASS: {len(edges)} edges have required fields")


class TestBotFarmsEndpoint:
    """Tests for /api/connections/bot-farms endpoint"""
    
    def test_bot_farms_returns_200(self):
        """Bot farms endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/connections/bot-farms")
        assert response.status_code == 200
        print("PASS: Bot farms endpoint returns 200")
    
    def test_bot_farms_names_human_readable(self):
        """Farm names should be human-readable"""
        response = requests.get(f"{BASE_URL}/api/connections/bot-farms")
        data = response.json()
        farms = data.get("data", [])
        
        for farm in farms:
            name = farm.get("name", "")
            assert "Ring" not in name, f"Farm name contains 'Ring': {name}"
        
        print(f"PASS: All {len(farms)} farm names are human-readable")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
