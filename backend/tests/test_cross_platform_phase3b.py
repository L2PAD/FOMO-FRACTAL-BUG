"""
Phase 3B Cross-Platform (Poly ↔ Kalshi) API Tests

Tests:
- GET /api/cross-market/kalshi/signals — cross-platform signals with strategy objects
- GET /api/cross-market/kalshi/strategies — actionable + no_trade strategies
- GET /api/cross-market/kalshi/mispricings — scored mispricings with edge_case_type
- POST /api/cross-market/kalshi/rebuild — triggers full pipeline rebuild
- GET /api/cross-market/kalshi/debug/clusters — debug view with scoring details
- GET /api/cross-market/kalshi/markets — normalized Kalshi markets
- GET /api/cross-market/kalshi/clusters — matched clusters
- GET /api/cross-market/kalshi/relations — inferred SUBSET/EQUIVALENT relations
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCrossPlatformPhase3BRebuild:
    """Test POST /api/cross-market/kalshi/rebuild endpoint"""
    
    def test_rebuild_returns_ok(self):
        """Rebuild should return ok=true with summary"""
        response = requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "summary" in data
        
    def test_rebuild_summary_has_required_fields(self):
        """Rebuild summary should have all Phase 3B fields"""
        response = requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild")
        assert response.status_code == 200
        data = response.json()
        summary = data.get("summary", {})
        
        # Phase 3A fields
        assert "kalshi_raw" in summary
        assert "kalshi_normalized" in summary
        assert "kalshi_filtered" in summary
        assert "poly_markets" in summary
        assert "clusters" in summary
        assert "relations" in summary
        
        # Phase 3B fields
        assert "violations" in summary
        assert "mispricings" in summary
        assert "strategies_actionable" in summary
        
    def test_rebuild_populates_cache(self):
        """After rebuild, other endpoints should return data"""
        # First rebuild
        rebuild_resp = requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild")
        assert rebuild_resp.status_code == 200
        
        # Check markets endpoint
        markets_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/markets")
        assert markets_resp.status_code == 200
        markets_data = markets_resp.json()
        assert markets_data.get("ok") is True
        assert "count" in markets_data
        assert "markets" in markets_data


class TestCrossPlatformMarkets:
    """Test GET /api/cross-market/kalshi/markets endpoint"""
    
    def test_markets_returns_ok(self):
        """Markets endpoint should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/markets")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
    def test_markets_has_required_fields(self):
        """Each market should have required fields"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/markets")
        assert response.status_code == 200
        data = response.json()
        
        if data.get("count", 0) > 0:
            market = data["markets"][0]
            assert "id" in market
            assert "ticker" in market
            assert "entity" in market
            assert "question" in market
            assert "yes_price" in market
            assert "volume" in market
            assert "threshold" in market
            assert "direction" in market
            assert "close_time" in market


class TestCrossPlatformClusters:
    """Test GET /api/cross-market/kalshi/clusters endpoint"""
    
    def test_clusters_returns_ok(self):
        """Clusters endpoint should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/clusters")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
    def test_clusters_has_required_fields(self):
        """Each cluster should have required fields"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/clusters")
        assert response.status_code == 200
        data = response.json()
        
        if data.get("count", 0) > 0:
            cluster = data["clusters"][0]
            assert "cluster_id" in cluster
            assert "entity" in cluster
            assert "topic" in cluster
            assert "market_count" in cluster
            assert "match_count" in cluster
            assert "markets" in cluster


class TestCrossPlatformRelations:
    """Test GET /api/cross-market/kalshi/relations endpoint"""
    
    def test_relations_returns_ok(self):
        """Relations endpoint should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/relations")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
    def test_relations_has_required_fields(self):
        """Each relation should have required fields"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/relations")
        assert response.status_code == 200
        data = response.json()
        
        if data.get("count", 0) > 0:
            relation = data["relations"][0]
            assert "relation" in relation
            assert relation["relation"] in ["SUBSET", "EQUIVALENT"]
            assert "confidence" in relation
            assert "poly_market_id" in relation
            assert "kalshi_market_id" in relation
            assert "poly_price" in relation
            assert "kalshi_price" in relation
            assert "explanation" in relation
            assert "cluster_id" in relation
            assert "entity" in relation


class TestCrossPlatformMispricings:
    """Test GET /api/cross-market/kalshi/mispricings endpoint"""
    
    def test_mispricings_returns_ok(self):
        """Mispricings endpoint should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/mispricings")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "count" in data
        assert "mispricings" in data
        
    def test_mispricings_structure_if_present(self):
        """If mispricings exist, they should have Phase 3B fields"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/mispricings")
        assert response.status_code == 200
        data = response.json()
        
        # Mispricings may be empty due to hard filters
        if data.get("count", 0) > 0:
            m = data["mispricings"][0]
            # Core fields
            assert "cluster_id" in m
            assert "entity" in m
            assert "constraint_type" in m
            assert "gap" in m
            assert "gap_pct" in m
            
            # Phase 3B scoring fields
            assert "score" in m
            assert "actionability_score" in m
            assert "severity" in m
            assert "actionable" in m
            
            # Edge case classification
            assert "edge_case_type" in m
            assert "edge_multiplier" in m
            
            # Components breakdown
            assert "components" in m


class TestCrossPlatformStrategies:
    """Test GET /api/cross-market/kalshi/strategies endpoint"""
    
    def test_strategies_returns_ok(self):
        """Strategies endpoint should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/strategies")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
    def test_strategies_has_required_fields(self):
        """Strategies response should have actionable and no_trade arrays"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/strategies")
        assert response.status_code == 200
        data = response.json()
        
        assert "total_actionable" in data
        assert "total_no_trade" in data
        assert "actionable" in data
        assert "no_trade" in data
        assert isinstance(data["actionable"], list)
        assert isinstance(data["no_trade"], list)
        
    def test_strategy_structure_if_present(self):
        """If strategies exist, they should have required fields"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/strategies")
        assert response.status_code == 200
        data = response.json()
        
        all_strategies = data.get("actionable", []) + data.get("no_trade", [])
        if len(all_strategies) > 0:
            s = all_strategies[0]
            assert "strategy_type" in s
            assert s["strategy_type"] in ["LOGICAL_ARBITRAGE", "RELATIVE_VALUE", "NO_TRADE"]
            assert "cluster_id" in s
            assert "entity" in s
            assert "edge_case_type" in s
            assert "legs" in s
            assert "edge" in s
            assert "edge_pct" in s
            assert "score" in s
            assert "actionability_score" in s
            assert "severity" in s
            assert "actionable" in s
            assert "reasoning" in s
            assert "risks" in s


class TestCrossPlatformSignals:
    """Test GET /api/cross-market/kalshi/signals endpoint"""
    
    def test_signals_returns_ok(self):
        """Signals endpoint should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/signals")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "count" in data
        assert "signals" in data
        
    def test_signals_structure_if_present(self):
        """If signals exist, they should have combined mispricing + strategy data"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/signals")
        assert response.status_code == 200
        data = response.json()
        
        if data.get("count", 0) > 0:
            sig = data["signals"][0]
            # Mispricing fields
            assert "cluster_id" in sig
            assert "entity" in sig
            assert "constraint_type" in sig
            assert "edge_case_type" in sig
            assert "gap" in sig
            assert "gap_pct" in sig
            assert "score" in sig
            assert "actionability_score" in sig
            assert "severity" in sig
            assert "actionable" in sig
            assert "poly_price" in sig
            assert "kalshi_price" in sig
            assert "explanation" in sig
            
            # Strategy field (may be None)
            assert "strategy" in sig


class TestCrossPlatformDebugClusters:
    """Test GET /api/cross-market/kalshi/debug/clusters endpoint"""
    
    def test_debug_clusters_returns_ok(self):
        """Debug clusters endpoint should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/debug/clusters")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
    def test_debug_clusters_has_required_fields(self):
        """Debug response should have totals and clusters array"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/debug/clusters")
        assert response.status_code == 200
        data = response.json()
        
        assert "total_clusters" in data
        assert "total_relations" in data
        assert "clusters" in data
        
    def test_debug_cluster_has_scoring_details(self):
        """Each debug cluster should have match scoring details"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/debug/clusters")
        assert response.status_code == 200
        data = response.json()
        
        if len(data.get("clusters", [])) > 0:
            cluster = data["clusters"][0]
            assert "cluster_id" in cluster
            assert "entity" in cluster
            assert "topic" in cluster
            assert "markets" in cluster
            assert "matches" in cluster
            assert "parsed_resolutions" in cluster
            assert "relations" in cluster
            
            # Check match scoring details
            if len(cluster.get("matches", [])) > 0:
                match = cluster["matches"][0]
                assert "poly" in match
                assert "kalshi" in match
                assert "score" in match
                assert "entity_score" in match
                assert "topic_score" in match
                assert "time_score" in match
                assert "resolution_score" in match


class TestCrossPlatformPipelineIntegration:
    """Integration tests for the full Phase 3B pipeline"""
    
    def test_pipeline_flow_rebuild_to_signals(self):
        """Test full pipeline: rebuild → relations → mispricings → strategies → signals"""
        # Step 1: Rebuild
        rebuild_resp = requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild")
        assert rebuild_resp.status_code == 200
        rebuild_data = rebuild_resp.json()
        summary = rebuild_data.get("summary", {})
        
        # Step 2: Check relations count matches
        relations_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/relations")
        assert relations_resp.status_code == 200
        relations_data = relations_resp.json()
        assert relations_data.get("count") == summary.get("relations")
        
        # Step 3: Check mispricings count matches
        mispricings_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/mispricings")
        assert mispricings_resp.status_code == 200
        mispricings_data = mispricings_resp.json()
        assert mispricings_data.get("count") == summary.get("mispricings")
        
        # Step 4: Check strategies count matches
        strategies_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/strategies")
        assert strategies_resp.status_code == 200
        strategies_data = strategies_resp.json()
        assert strategies_data.get("total_actionable") == summary.get("strategies_actionable")
        
        # Step 5: Check signals count matches mispricings
        signals_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/signals")
        assert signals_resp.status_code == 200
        signals_data = signals_resp.json()
        assert signals_data.get("count") == mispricings_data.get("count")
        
    def test_constraint_types_are_valid(self):
        """All constraint types should be SUBSET or EQUIVALENT"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/relations")
        assert response.status_code == 200
        data = response.json()
        
        for rel in data.get("relations", []):
            assert rel.get("relation") in ["SUBSET", "EQUIVALENT"]
            
    def test_severity_levels_are_valid(self):
        """All severity levels should be STRONG, HIGH, or MEDIUM"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/mispricings")
        assert response.status_code == 200
        data = response.json()
        
        for m in data.get("mispricings", []):
            assert m.get("severity") in ["STRONG", "HIGH", "MEDIUM"]
            
    def test_edge_case_types_are_valid(self):
        """All edge case types should be from the defined set"""
        valid_types = [
            "SOFT_HARD_TRIGGER",
            "THRESHOLD_EQUIVALENT",
            "APPROVAL_CHAIN",
            "LISTING_STAGE",
            "TIME_WINDOW_MISMATCH",
            "LADDER_SHAPE_MISMATCH",
            "NARRATIVE_DIVERGENCE",
            "UNKNOWN",
        ]
        
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/mispricings")
        assert response.status_code == 200
        data = response.json()
        
        for m in data.get("mispricings", []):
            assert m.get("edge_case_type") in valid_types


class TestCrossPlatformHardFilters:
    """Test that hard filters are working correctly"""
    
    def test_violations_vs_mispricings(self):
        """Violations count should be >= mispricings count (hard filters reduce)"""
        rebuild_resp = requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild")
        assert rebuild_resp.status_code == 200
        summary = rebuild_resp.json().get("summary", {})
        
        violations = summary.get("violations", 0)
        mispricings = summary.get("mispricings", 0)
        
        # Hard filters should reduce violations to mispricings
        assert violations >= mispricings
        
    def test_actionable_strategies_match_actionable_mispricings(self):
        """Actionable strategies count should match actionable mispricings"""
        # Get mispricings
        mispricings_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/mispricings")
        assert mispricings_resp.status_code == 200
        mispricings = mispricings_resp.json().get("mispricings", [])
        actionable_mispricings = [m for m in mispricings if m.get("actionable")]
        
        # Get strategies
        strategies_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/strategies")
        assert strategies_resp.status_code == 200
        strategies_data = strategies_resp.json()
        
        # Actionable strategies should match actionable mispricings
        assert strategies_data.get("total_actionable") == len(actionable_mispricings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
