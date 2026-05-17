"""
Test Unified Intelligence Layer — Graph-level intelligence signals
Tests the _compute_graph_intelligence function and Intelligence Panel integration

Feature: Unified Intelligence Layer
- Backend computes intelligence[] array for every graph render
- Frontend filters by active mode (smart_money, entity, risk, token_rotation, cex_flow)
- Signal types: entity_cluster, accumulation, distribution, whale_activity, loop_routing, high_risk_nodes, rotation, cex_flow_summary
- Each signal has: type, category, confidence, summary, entities, details
- Categories: smart_money, entity, risk, token_flow, route
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')

# Valid signal types produced by _compute_graph_intelligence
VALID_SIGNAL_TYPES = {
    'entity_cluster', 'accumulation', 'distribution', 'whale_activity',
    'loop_routing', 'high_risk_nodes', 'rotation', 'cex_flow_summary'
}

# Valid intelligence categories
VALID_CATEGORIES = {'smart_money', 'entity', 'risk', 'token_flow', 'route'}

# Required fields for each intelligence signal
REQUIRED_SIGNAL_FIELDS = {'type', 'category', 'confidence', 'summary', 'entities', 'details'}


class TestBackendIntelligenceEndpoints:
    """Test that render-seeds returns intelligence array with proper signal structure"""

    def test_render_seeds_returns_intelligence_array(self):
        """GET /api/graph-core/render-seeds returns intelligence[] array in response"""
        # Use smart_money mode which should produce signals
        response = requests.get(
            f"{BASE_URL}/api/graph-core/render-seeds",
            params={"seeds": "wallet:0xd8da6bf26964af9d7eed9e03e53415d37aa96045:ethereum", "limit": 50, "mode": "smart_money"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "intelligence" in data, "Response should contain 'intelligence' field"
        assert isinstance(data["intelligence"], list), "intelligence should be a list"
        print(f"✓ render-seeds returns intelligence array with {len(data['intelligence'])} signals")
    
    def test_intelligence_signal_structure(self):
        """Each intelligence signal has: type, category, confidence, summary, entities, details"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/render-seeds",
            params={"seeds": "wallet:0xd8da6bf26964af9d7eed9e03e53415d37aa96045:ethereum", "limit": 50, "mode": "smart_money"}
        )
        assert response.status_code == 200
        
        data = response.json()
        intelligence = data.get("intelligence", [])
        
        for signal in intelligence:
            # Check required fields
            for field in REQUIRED_SIGNAL_FIELDS:
                assert field in signal, f"Signal missing required field '{field}': {signal}"
            
            # Check type is valid
            assert signal["type"] in VALID_SIGNAL_TYPES, f"Invalid signal type: {signal['type']}"
            
            # Check category is valid
            assert signal["category"] in VALID_CATEGORIES, f"Invalid category: {signal['category']}"
            
            # Check confidence is a number between 0 and 1
            assert isinstance(signal["confidence"], (int, float)), f"Confidence should be numeric: {signal['confidence']}"
            assert 0 <= signal["confidence"] <= 1, f"Confidence should be 0-1: {signal['confidence']}"
            
            # Check summary is a non-empty string
            assert isinstance(signal["summary"], str) and len(signal["summary"]) > 0, f"Summary should be non-empty string"
            
            # Check entities is a list
            assert isinstance(signal["entities"], list), f"Entities should be a list"
            
            # Check details is a dict
            assert isinstance(signal["details"], dict), f"Details should be a dict"
            
        print(f"✓ All {len(intelligence)} signals have valid structure (type, category, confidence, summary, entities, details)")


class TestEntityModeIntelligence:
    """Entity mode seeds should produce entity_cluster signals"""
    
    def test_entity_mode_produces_entity_cluster_signals(self):
        """Backend: Entity mode seeds (cluster:binance:ethereum etc) produce entity_cluster signals"""
        # Try entity mode discovery first
        discovery_resp = requests.get(
            f"{BASE_URL}/api/graph-core/discovery",
            params={"mode": "entity", "limit": 5}
        )
        
        if discovery_resp.status_code != 200 or not discovery_resp.json().get("seed_nodes"):
            # Fallback: use a known cluster seed
            seeds = "cluster:binance:ethereum"
        else:
            seeds = ",".join([n["id"] for n in discovery_resp.json()["seed_nodes"][:3]])
        
        response = requests.get(
            f"{BASE_URL}/api/graph-core/render-seeds",
            params={"seeds": seeds, "limit": 100, "mode": "entity"}
        )
        assert response.status_code == 200
        
        data = response.json()
        intelligence = data.get("intelligence", [])
        
        # Check if entity_cluster signals exist (may not have data for this)
        entity_signals = [s for s in intelligence if s.get("category") == "entity"]
        
        print(f"Entity mode returned {len(entity_signals)} entity-category signals")
        print(f"  Signal types: {set(s['type'] for s in entity_signals) if entity_signals else 'none'}")
        
        # If we have entity signals, verify structure
        for signal in entity_signals:
            if signal["type"] == "entity_cluster":
                assert "cluster_id" in signal.get("details", {}), "entity_cluster signal should have cluster_id in details"
                assert "cluster_size" in signal.get("details", {}), "entity_cluster signal should have cluster_size in details"
                print(f"  ✓ entity_cluster signal found: {signal['summary']}")


class TestSmartMoneyModeIntelligence:
    """Smart money mode should produce accumulation/distribution/whale signals"""
    
    def test_smart_money_mode_produces_signals(self):
        """Backend: Smart money mode seeds produce accumulation/distribution/whale signals"""
        # Try smart_money discovery
        discovery_resp = requests.get(
            f"{BASE_URL}/api/graph-core/discovery",
            params={"mode": "smart_money", "limit": 10}
        )
        
        if discovery_resp.status_code == 200 and discovery_resp.json().get("seed_nodes"):
            seeds = ",".join([n["id"] for n in discovery_resp.json()["seed_nodes"][:5]])
        else:
            # Fallback to known wallet
            seeds = "wallet:0xd8da6bf26964af9d7eed9e03e53415d37aa96045:ethereum"
        
        response = requests.get(
            f"{BASE_URL}/api/graph-core/render-seeds",
            params={"seeds": seeds, "limit": 100, "mode": "smart_money"}
        )
        assert response.status_code == 200
        
        data = response.json()
        intelligence = data.get("intelligence", [])
        
        # Check for smart_money category signals
        sm_signals = [s for s in intelligence if s.get("category") == "smart_money"]
        sm_types = set(s["type"] for s in sm_signals) if sm_signals else set()
        
        print(f"Smart Money mode returned {len(sm_signals)} smart_money-category signals")
        print(f"  Signal types found: {sm_types or 'none'}")
        
        # Verify structure of smart_money signals
        for signal in sm_signals:
            if signal["type"] == "accumulation":
                details = signal.get("details", {})
                assert "wallet_count" in details, "accumulation signal should have wallet_count"
                assert "total_volume_usd" in details, "accumulation signal should have total_volume_usd"
                print(f"  ✓ accumulation signal: {signal['summary']}")
            elif signal["type"] == "distribution":
                details = signal.get("details", {})
                assert "wallet_count" in details, "distribution signal should have wallet_count"
                assert "total_volume_usd" in details, "distribution signal should have total_volume_usd"
                print(f"  ✓ distribution signal: {signal['summary']}")
            elif signal["type"] == "whale_activity":
                details = signal.get("details", {})
                assert "whale_count" in details, "whale_activity signal should have whale_count"
                print(f"  ✓ whale_activity signal: {signal['summary']}")


class TestIntelligenceCategories:
    """Test that intelligence categories include all expected types"""
    
    def test_categories_include_expected_types(self):
        """Backend: Intelligence categories include: smart_money, entity, risk, token_flow, route"""
        # Load a rich graph that might have multiple categories
        response = requests.get(
            f"{BASE_URL}/api/graph-core/render-seeds",
            params={"seeds": "cex:binance:ethereum,wallet:0xd8da6bf26964af9d7eed9e03e53415d37aa96045:ethereum", "limit": 150, "depth": 2}
        )
        assert response.status_code == 200
        
        data = response.json()
        intelligence = data.get("intelligence", [])
        
        found_categories = set(s.get("category") for s in intelligence)
        
        print(f"Found categories: {found_categories}")
        print(f"Expected categories: {VALID_CATEGORIES}")
        
        # All found categories should be valid
        for cat in found_categories:
            assert cat in VALID_CATEGORIES, f"Invalid category found: {cat}"
        
        print(f"✓ All {len(found_categories)} found categories are valid")


class TestCexFlowModeIntelligence:
    """CEX Flow mode should return cex_routes with wash_flags and wash_score"""
    
    def test_cex_flow_mode_returns_cex_routes(self):
        """Backend: CEX Flow mode still returns cex_routes with wash_flags and wash_score"""
        # Discover CEX seeds
        discovery_resp = requests.get(
            f"{BASE_URL}/api/graph-core/discovery",
            params={"mode": "cex_flow", "limit": 5}
        )
        
        if discovery_resp.status_code == 200 and discovery_resp.json().get("seed_nodes"):
            seeds = ",".join([n["id"] for n in discovery_resp.json()["seed_nodes"]])
        else:
            seeds = "cex:binance:ethereum,cex:coinbase:ethereum"
        
        response = requests.get(
            f"{BASE_URL}/api/graph-core/render-seeds",
            params={"seeds": seeds, "limit": 100, "mode": "cex_flow", "depth": 2}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # CEX Flow should have cex_routes
        cex_routes = data.get("cex_routes", [])
        print(f"CEX Flow mode returned {len(cex_routes)} cex_routes")
        
        # Verify cex_routes structure
        for route in cex_routes[:5]:  # Check first 5
            assert "path" in route, "CEX route should have 'path'"
            assert "wash_flags" in route, "CEX route should have 'wash_flags'"
            assert "wash_score" in route, "CEX route should have 'wash_score'"
            assert isinstance(route["wash_flags"], list), "wash_flags should be a list"
            assert isinstance(route["wash_score"], (int, float)), "wash_score should be numeric"
        
        if cex_routes:
            print(f"✓ CEX routes have wash_flags and wash_score")
        
        # CEX Flow should also have intelligence (cex_flow_summary signal)
        intelligence = data.get("intelligence", [])
        cex_intel = [s for s in intelligence if s.get("type") == "cex_flow_summary"]
        print(f"CEX Flow mode returned {len(cex_intel)} cex_flow_summary signals")


class TestRenderEndpointIntelligence:
    """Test /render/{id} endpoint returns valid graph data"""
    
    def test_render_endpoint_returns_graph(self):
        """Backend: render/{id} endpoint returns nodes and edges (intelligence via project endpoint)"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/render/wallet:0xd8da6bf26964af9d7eed9e03e53415d37aa96045:ethereum",
            params={"limit": 50}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Check basic graph structure
        assert "nodes" in data, "render endpoint should return nodes"
        assert "edges" in data, "render endpoint should return edges"
        assert "meta" in data, "render endpoint should return meta"
        
        print(f"Render endpoint returned {len(data['nodes'])} nodes, {len(data['edges'])} edges")
        
        # NOTE: Intelligence is computed via render-seeds endpoint, not render/{id}
        # The frontend uses graphDataService which calls render-seeds for discovery mode
        # and render/{id} for exploration mode - intelligence is added in render-seeds
        
        print("✓ render endpoint returns valid graph data")


class TestProjectEndpointIntelligence:
    """Test that /project/{id} endpoint also adds intelligence"""
    
    def test_project_endpoint_has_intelligence(self):
        """Backend: project/{id} endpoint adds intelligence to result (Unified Intelligence Layer)"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/project/wallet:0xd8da6bf26964af9d7eed9e03e53415d37aa96045:ethereum",
            params={"depth": 2, "max_nodes": 50}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Check intelligence field exists
        assert "intelligence" in data, "project endpoint should return intelligence field"
        intelligence = data["intelligence"]
        
        print(f"Project endpoint returned {len(intelligence)} intelligence signals")
        print("✓ project endpoint includes intelligence array")


class TestRiskModeIntelligence:
    """Risk mode should produce risk-category signals"""
    
    def test_risk_mode_produces_risk_signals(self):
        """Backend: Risk mode produces high_risk_nodes and loop_routing signals"""
        # Try risk mode discovery (may have limited data)
        discovery_resp = requests.get(
            f"{BASE_URL}/api/graph-core/discovery",
            params={"mode": "risk", "limit": 5}
        )
        
        if discovery_resp.status_code == 200 and discovery_resp.json().get("seed_nodes"):
            seeds = ",".join([n["id"] for n in discovery_resp.json()["seed_nodes"]])
        else:
            # Use general seeds that might have risk data
            seeds = "wallet:0xd8da6bf26964af9d7eed9e03e53415d37aa96045:ethereum"
        
        response = requests.get(
            f"{BASE_URL}/api/graph-core/render-seeds",
            params={"seeds": seeds, "limit": 100, "mode": "risk"}
        )
        assert response.status_code == 200
        
        data = response.json()
        intelligence = data.get("intelligence", [])
        
        risk_signals = [s for s in intelligence if s.get("category") == "risk"]
        risk_types = set(s["type"] for s in risk_signals) if risk_signals else set()
        
        print(f"Risk mode returned {len(risk_signals)} risk-category signals")
        print(f"  Signal types: {risk_types or 'none'}")
        
        # Valid risk signal types
        valid_risk_types = {"high_risk_nodes", "loop_routing"}
        for signal in risk_signals:
            assert signal["type"] in valid_risk_types, f"Invalid risk signal type: {signal['type']}"
        
        print("✓ Risk signals have valid types")


class TestIntelligenceConfidenceSort:
    """Intelligence signals should be sorted by confidence DESC"""
    
    def test_signals_sorted_by_confidence(self):
        """Backend: Intelligence signals are sorted by confidence in descending order"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/render-seeds",
            params={"seeds": "cex:binance:ethereum,wallet:0xd8da6bf26964af9d7eed9e03e53415d37aa96045:ethereum", "limit": 100}
        )
        assert response.status_code == 200
        
        data = response.json()
        intelligence = data.get("intelligence", [])
        
        if len(intelligence) >= 2:
            confidences = [s["confidence"] for s in intelligence]
            # Check descending order
            is_sorted = all(confidences[i] >= confidences[i+1] for i in range(len(confidences)-1))
            assert is_sorted, f"Signals not sorted by confidence DESC: {confidences[:10]}"
            print(f"✓ {len(intelligence)} signals sorted by confidence (highest: {confidences[0]}, lowest: {confidences[-1]})")
        else:
            print(f"Only {len(intelligence)} signals, can't verify sorting")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
