"""
Phase C: Frontend Integration of Actor Intelligence Layer into Entity Terminal
Tests for:
- GET /api/entities/v2/{slug}/intelligence endpoint
- All intelligence fields: pressure, strategy, conviction, regime, playbook
- Cluster roles, token dependency, quick tags, highlights, summary
- Backward compatibility with existing entity endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test entities with varying data
TEST_ENTITIES = ['binance', 'coinbase', 'uniswap', 'okx', 'kraken']


class TestIntelligenceEndpoint:
    """Test the unified /intelligence endpoint returns all required fields"""
    
    def test_intelligence_returns_200_for_binance(self):
        """Binance has the richest data, should return 200"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True
        print("✅ Intelligence endpoint returns 200 for binance")
    
    def test_intelligence_returns_404_for_nonexistent(self):
        """Non-existent entity should return 404"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent-entity-xyz/intelligence")
        assert response.status_code == 404
        print("✅ Intelligence endpoint returns 404 for non-existent entity")
    
    def test_intelligence_has_all_required_fields(self):
        """Verify all required fields are present in response"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            'slug', 'name', 'pressure', 'pressure_detail', 
            'strategy', 'strategy_detail', 'conviction', 'conviction_detail',
            'regime', 'regime_detail', 'playbook', 'playbook_detail',
            'cluster_roles', 'token_dependency', 'quick_tags', 'highlights',
            'summary', 'computed_at'
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"✅ All {len(required_fields)} required fields present")


class TestPressureField:
    """Test pressure field and pressure_detail structure"""
    
    def test_pressure_is_valid_string(self):
        """Pressure should be bullish/bearish/neutral"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        pressure = data.get("pressure")
        assert pressure in ["bullish", "bearish", "neutral"], f"Invalid pressure: {pressure}"
        print(f"✅ Pressure value is valid: {pressure}")
    
    def test_pressure_detail_structure(self):
        """Pressure detail should have score, inflow_ratio, net_flow_usd, drivers"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        pd = data.get("pressure_detail", {})
        assert "score" in pd, "pressure_detail missing score"
        assert "inflow_ratio" in pd, "pressure_detail missing inflow_ratio"
        assert "net_flow_usd" in pd, "pressure_detail missing net_flow_usd"
        assert "drivers" in pd, "pressure_detail missing drivers"
        assert isinstance(pd["drivers"], list), "drivers should be a list"
        
        print(f"✅ Pressure detail structure valid - score: {pd['score']}")


class TestStrategyField:
    """Test strategy field and strategy_detail structure"""
    
    def test_strategy_is_string(self):
        """Strategy should be a non-empty string"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        strategy = data.get("strategy")
        assert isinstance(strategy, str), f"Strategy should be string, got {type(strategy)}"
        assert len(strategy) > 0, "Strategy should not be empty"
        print(f"✅ Strategy is valid string: {strategy}")
    
    def test_strategy_detail_structure(self):
        """Strategy detail should have strategy, confidence, drivers"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        sd = data.get("strategy_detail", {})
        assert "strategy" in sd, "strategy_detail missing strategy"
        assert "confidence" in sd, "strategy_detail missing confidence"
        assert "drivers" in sd, "strategy_detail missing drivers"
        assert 0 <= sd["confidence"] <= 1, f"Confidence should be 0-1, got {sd['confidence']}"
        
        print(f"✅ Strategy detail valid - confidence: {sd['confidence']}")


class TestConvictionField:
    """Test conviction field and conviction_detail structure"""
    
    def test_conviction_is_valid_string(self):
        """Conviction should be low/moderate/high/extreme"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        conviction = data.get("conviction")
        valid = ["low", "moderate", "high", "extreme"]
        assert conviction in valid, f"Invalid conviction: {conviction}"
        print(f"✅ Conviction value is valid: {conviction}")
    
    def test_conviction_detail_structure(self):
        """Conviction detail should have conviction, score (0-100), drivers"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        cd = data.get("conviction_detail", {})
        assert "conviction" in cd, "conviction_detail missing conviction"
        assert "score" in cd, "conviction_detail missing score"
        assert "drivers" in cd, "conviction_detail missing drivers"
        assert 0 <= cd["score"] <= 100, f"Score should be 0-100, got {cd['score']}"
        
        print(f"✅ Conviction detail valid - score: {cd['score']}")


class TestRegimeField:
    """Test regime field and regime_detail structure"""
    
    def test_regime_is_valid_string(self):
        """Regime should be accumulation/distribution/liquidity/dormant/rotation"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        regime = data.get("regime")
        valid = ["accumulation", "distribution", "liquidity", "dormant", "rotation"]
        assert regime in valid, f"Invalid regime: {regime}"
        print(f"✅ Regime value is valid: {regime}")
    
    def test_regime_detail_has_drivers(self):
        """Regime detail should have regime and drivers"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        rd = data.get("regime_detail", {})
        assert "regime" in rd, "regime_detail missing regime"
        assert "drivers" in rd, "regime_detail missing drivers"
        
        print(f"✅ Regime detail valid with drivers")


class TestPlaybookField:
    """Test playbook field and playbook_detail structure"""
    
    def test_playbook_is_string(self):
        """Playbook should be a non-empty string"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        playbook = data.get("playbook")
        assert isinstance(playbook, str), f"Playbook should be string"
        assert len(playbook) > 0, "Playbook should not be empty"
        print(f"✅ Playbook is valid: {playbook}")
    
    def test_playbook_detail_structure(self):
        """Playbook detail should have playbook, strategy, regime, pressure"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        pbd = data.get("playbook_detail", {})
        assert "playbook" in pbd, "playbook_detail missing playbook"
        assert "strategy" in pbd, "playbook_detail missing strategy"
        assert "regime" in pbd, "playbook_detail missing regime"
        assert "pressure" in pbd, "playbook_detail missing pressure"
        
        print(f"✅ Playbook detail structure valid")


class TestClusterRoles:
    """Test cluster_roles array structure"""
    
    def test_cluster_roles_is_array(self):
        """Cluster roles should be an array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        cr = data.get("cluster_roles")
        assert isinstance(cr, list), "cluster_roles should be a list"
        print(f"✅ Cluster roles is array with {len(cr)} items")
    
    def test_cluster_role_structure(self):
        """Each cluster role should have required fields"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        cr = data.get("cluster_roles", [])
        if len(cr) > 0:
            role = cr[0]
            expected_fields = ['cluster_id', 'tier', 'size', 'cluster_role', 
                              'flow_weight', 'token_profile', 'confidence']
            for field in expected_fields:
                assert field in role, f"Cluster role missing {field}"
            print(f"✅ Cluster role structure valid with all fields")
        else:
            print("⚠️ No cluster roles to test (empty array)")


class TestTokenDependency:
    """Test token_dependency object structure"""
    
    def test_token_dependency_is_object(self):
        """Token dependency should be an object"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        td = data.get("token_dependency")
        assert isinstance(td, dict), "token_dependency should be a dict"
        print(f"✅ Token dependency is object")
    
    def test_token_dependency_fields(self):
        """Token dependency should have stablecoin, eth, top_token dependencies"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        td = data.get("token_dependency", {})
        assert "stablecoin_dependency" in td, "Missing stablecoin_dependency"
        assert "eth_dependency" in td, "Missing eth_dependency"
        assert "top_token_dependency" in td, "Missing top_token_dependency"
        
        # All should be 0-1 range
        assert 0 <= td["stablecoin_dependency"] <= 1, "stablecoin_dependency out of range"
        assert 0 <= td["eth_dependency"] <= 1, "eth_dependency out of range"
        assert 0 <= td["top_token_dependency"] <= 1, "top_token_dependency out of range"
        
        print(f"✅ Token dependency fields valid - stablecoin: {td['stablecoin_dependency']:.2%}")


class TestQuickTagsAndHighlights:
    """Test quick_tags and highlights arrays"""
    
    def test_quick_tags_is_array_of_strings(self):
        """Quick tags should be array of strings"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        tags = data.get("quick_tags")
        assert isinstance(tags, list), "quick_tags should be a list"
        for tag in tags:
            assert isinstance(tag, str), f"Tag should be string, got {type(tag)}"
        
        print(f"✅ Quick tags valid: {tags[:3]}...")
    
    def test_highlights_is_array_of_strings(self):
        """Highlights should be array of strings"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        highlights = data.get("highlights")
        assert isinstance(highlights, list), "highlights should be a list"
        for h in highlights:
            assert isinstance(h, str), f"Highlight should be string, got {type(h)}"
        
        print(f"✅ Highlights valid: {len(highlights)} items")


class TestSummary:
    """Test summary field"""
    
    def test_summary_is_nonempty_string(self):
        """Summary should be a non-empty string"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        data = response.json()
        
        summary = data.get("summary")
        assert isinstance(summary, str), "summary should be a string"
        assert len(summary) > 0, "summary should not be empty"
        
        print(f"✅ Summary valid: {summary[:80]}...")


class TestAllEntitiesReturn200:
    """Test all test entities return 200 from intelligence endpoint"""
    
    @pytest.mark.parametrize("entity_slug", TEST_ENTITIES)
    def test_entity_intelligence_returns_200(self, entity_slug):
        """Each entity should return valid intelligence data"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/{entity_slug}/intelligence")
        assert response.status_code == 200, f"{entity_slug} returned {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True
        assert data.get("slug") == entity_slug
        assert "pressure" in data
        assert "strategy" in data
        assert "summary" in data
        
        print(f"✅ {entity_slug}: pressure={data['pressure']}, strategy={data['strategy']}")


class TestExistingEndpointsRegression:
    """Ensure existing entity endpoints still work"""
    
    def test_entity_list_endpoint(self):
        """GET /api/entities/v2/list should return entities"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/list?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "entities" in data
        print(f"✅ List endpoint works: {len(data['entities'])} entities")
    
    def test_entity_detail_endpoint(self):
        """GET /api/entities/v2/{slug} should return entity detail"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "entity" in data
        print("✅ Entity detail endpoint works")
    
    def test_entity_impact_endpoint(self):
        """GET /api/entities/v2/{slug}/impact should work"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/impact")
        assert response.status_code == 200
        data = response.json()
        assert "impact_score" in data
        print("✅ Impact endpoint works")
    
    def test_entity_timeline_endpoint(self):
        """GET /api/entities/v2/{slug}/timeline should work"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/timeline")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        print("✅ Timeline endpoint works")
    
    def test_entity_interactions_endpoint(self):
        """GET /api/entities/v2/{slug}/interactions should work"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        print("✅ Interactions endpoint works")
    
    def test_entity_behaviour_endpoint(self):
        """GET /api/entities/v2/{slug}/behaviour should work"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour")
        assert response.status_code == 200
        data = response.json()
        assert "behaviour_type" in data
        print("✅ Behaviour endpoint works")
    
    def test_entity_holdings_endpoint(self):
        """GET /api/entities/v2/{slug}/holdings should work"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/holdings")
        assert response.status_code == 200
        print("✅ Holdings endpoint works")
    
    def test_entity_flows_endpoint(self):
        """GET /api/entities/v2/{slug}/flows should work"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/flows")
        assert response.status_code == 200
        print("✅ Flows endpoint works")
    
    def test_entity_clusters_endpoint(self):
        """GET /api/entities/v2/{slug}/clusters should work"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        assert response.status_code == 200
        print("✅ Clusters endpoint works")
    
    def test_entity_similar_endpoint(self):
        """GET /api/entities/v2/{slug}/similar should work"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        assert response.status_code == 200
        print("✅ Similar endpoint works")
    
    def test_entity_chains_endpoint(self):
        """GET /api/entities/v2/{slug}/chains should work"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        assert response.status_code == 200
        print("✅ Chains endpoint works")
    
    def test_discovery_endpoint(self):
        """GET /api/entities/v2/discovery should work"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/discovery")
        assert response.status_code == 200
        print("✅ Discovery endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
