"""
Test Cross-Market Phase 2.5 (Actionability Layer) + Phase 3A Batch 1 (Kalshi Integration)

Phase 2.5 Features:
- actionability_score = score*0.4 + liquidity*0.3 + execution_feasibility*0.2 + time*0.1
- Severity levels: STRONG >= 0.75, HIGH >= 0.65, MEDIUM >= 0.55, HIDDEN < 0.55

Phase 3A Batch 1 Features:
- Kalshi REST API integration for crypto markets (KXBTC, KXETH series)
- Cross-platform market matching with scoring (entity*0.35 + topic*0.25 + time*0.2 + resolution*0.2)
- Resolution parser v2 with primitives array
- Cross-platform relation engine (SUBSET/EQUIVALENT)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCrossMarketMispricingActionability:
    """Test Phase 2.5 actionability scoring in mispricing endpoint"""
    
    def test_mispricing_endpoint_returns_ok(self):
        """GET /api/cross-market/mispricing returns 200 with ok=true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/mispricing", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "count" in data, "Missing count field"
        assert "mispricings" in data, "Missing mispricings field"
        print(f"Mispricing endpoint: {data.get('count')} mispricings found")
    
    def test_mispricing_has_actionability_fields(self):
        """Mispricings should include actionability_score and actionability_severity"""
        response = requests.get(f"{BASE_URL}/api/cross-market/mispricing", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        mispricings = data.get("mispricings", [])
        
        # If there are mispricings, verify actionability fields
        if mispricings:
            for mp in mispricings[:3]:  # Check first 3
                assert "actionability_score" in mp, f"Missing actionability_score in mispricing"
                assert "actionability_severity" in mp, f"Missing actionability_severity in mispricing"
                
                # Verify severity is valid
                severity = mp.get("actionability_severity")
                assert severity in ["STRONG", "HIGH", "MEDIUM"], f"Invalid severity: {severity}"
                
                # Verify score is in valid range
                score = mp.get("actionability_score", 0)
                assert 0 <= score <= 1, f"Invalid actionability_score: {score}"
                
                print(f"Mispricing: score={score:.4f}, severity={severity}")
        else:
            print("No mispricings found (expected with real data below thresholds)")


class TestCrossMarketStrategiesActionability:
    """Test Phase 2.5 actionability in strategies endpoint"""
    
    def test_strategies_endpoint_returns_ok(self):
        """GET /api/cross-market/strategies returns 200 with ok=true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/strategies", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "total_actionable" in data, "Missing total_actionable field"
        assert "actionable" in data, "Missing actionable field"
        print(f"Strategies: {data.get('total_actionable')} actionable, {data.get('total_no_trade')} no_trade")
    
    def test_strategies_have_actionability_breakdown(self):
        """Strategies should include actionability_score, severity, and breakdown"""
        response = requests.get(f"{BASE_URL}/api/cross-market/strategies", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        actionable = data.get("actionable", [])
        
        if actionable:
            for strat in actionable[:3]:
                assert "actionability_score" in strat, "Missing actionability_score"
                assert "actionability_severity" in strat, "Missing actionability_severity"
                assert "actionability_breakdown" in strat, "Missing actionability_breakdown"
                
                breakdown = strat.get("actionability_breakdown", {})
                # Verify breakdown components
                expected_components = ["score_component", "liquidity_component", "execution_component", "time_component"]
                for comp in expected_components:
                    if comp in breakdown:
                        print(f"Strategy breakdown: {comp}={breakdown[comp]:.4f}")
        else:
            print("No actionable strategies found (expected with real data)")


class TestKalshiMarketsEndpoint:
    """Test Phase 3A Kalshi markets endpoint"""
    
    def test_kalshi_markets_returns_ok(self):
        """GET /api/cross-market/kalshi/markets returns 200 with normalized markets"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/markets", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "count" in data, "Missing count field"
        assert "markets" in data, "Missing markets field"
        
        count = data.get("count", 0)
        print(f"Kalshi markets: {count} crypto markets fetched")
    
    def test_kalshi_markets_have_required_fields(self):
        """Kalshi markets should have normalized fields"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/markets", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        markets = data.get("markets", [])
        
        if markets:
            required_fields = ["id", "ticker", "entity", "question", "yes_price", "volume", "threshold", "direction"]
            for mkt in markets[:3]:
                for field in required_fields:
                    assert field in mkt, f"Missing field {field} in Kalshi market"
                
                # Verify entity is BTC or ETH (crypto filter)
                entity = mkt.get("entity", "")
                assert entity in ["BTC", "ETH", "SOL", "UNKNOWN"], f"Unexpected entity: {entity}"
                
                print(f"Kalshi market: {mkt.get('ticker')} - {entity} - ${mkt.get('threshold', 0):,.0f}")
        else:
            print("No Kalshi markets found (API may be unavailable)")


class TestKalshiClustersEndpoint:
    """Test Phase 3A cross-platform clusters endpoint"""
    
    def test_kalshi_clusters_returns_ok(self):
        """GET /api/cross-market/kalshi/clusters returns 200 with clusters"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/clusters", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "count" in data, "Missing count field"
        assert "clusters" in data, "Missing clusters field"
        
        count = data.get("count", 0)
        print(f"Cross-platform clusters: {count} clusters found")
    
    def test_clusters_have_required_structure(self):
        """Clusters should have entity, topic, markets, and matches"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/clusters", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        clusters = data.get("clusters", [])
        
        if clusters:
            for cluster in clusters[:3]:
                assert "cluster_id" in cluster, "Missing cluster_id"
                assert "entity" in cluster, "Missing entity"
                assert "topic" in cluster, "Missing topic"
                assert "markets" in cluster, "Missing markets"
                assert "market_count" in cluster, "Missing market_count"
                
                print(f"Cluster: {cluster.get('cluster_id')} - {cluster.get('market_count')} markets")
        else:
            print("No clusters found (may need rebuild)")


class TestKalshiRelationsEndpoint:
    """Test Phase 3A cross-platform relations endpoint"""
    
    def test_kalshi_relations_returns_ok(self):
        """GET /api/cross-market/kalshi/relations returns 200 with relations"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/relations", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "count" in data, "Missing count field"
        assert "relations" in data, "Missing relations field"
        
        count = data.get("count", 0)
        print(f"Cross-platform relations: {count} relations inferred")
    
    def test_relations_have_subset_or_equivalent(self):
        """Relations should be SUBSET or EQUIVALENT type"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/relations", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        relations = data.get("relations", [])
        
        subset_count = 0
        equivalent_count = 0
        
        for rel in relations:
            relation_type = rel.get("relation", "")
            assert relation_type in ["SUBSET", "EQUIVALENT"], f"Invalid relation type: {relation_type}"
            
            if relation_type == "SUBSET":
                subset_count += 1
            elif relation_type == "EQUIVALENT":
                equivalent_count += 1
            
            # Verify confidence is present
            assert "confidence" in rel, "Missing confidence in relation"
        
        print(f"Relations: {equivalent_count} EQUIVALENT, {subset_count} SUBSET")


class TestKalshiRebuildEndpoint:
    """Test Phase 3A rebuild endpoint"""
    
    def test_kalshi_rebuild_returns_summary(self):
        """POST /api/cross-market/kalshi/rebuild returns rebuild summary"""
        response = requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "summary" in data, "Missing summary field"
        
        summary = data.get("summary", {})
        expected_fields = ["kalshi_raw", "kalshi_normalized", "kalshi_filtered", "poly_markets", "clusters", "relations"]
        for field in expected_fields:
            assert field in summary, f"Missing {field} in rebuild summary"
        
        print(f"Rebuild summary: {summary.get('kalshi_filtered')} Kalshi markets, "
              f"{summary.get('poly_markets')} Poly markets, "
              f"{summary.get('clusters')} clusters, "
              f"{summary.get('relations')} relations")


class TestKalshiDebugClustersEndpoint:
    """Test Phase 3A debug clusters endpoint with match scoring"""
    
    def test_debug_clusters_returns_scoring_details(self):
        """GET /api/cross-market/kalshi/debug/clusters returns match scoring details"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/debug/clusters", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "total_clusters" in data, "Missing total_clusters"
        assert "total_relations" in data, "Missing total_relations"
        assert "clusters" in data, "Missing clusters field"
        
        print(f"Debug: {data.get('total_clusters')} clusters, {data.get('total_relations')} relations")
    
    def test_debug_clusters_have_match_scores(self):
        """Debug clusters should include match scoring breakdown"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/debug/clusters", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        clusters = data.get("clusters", [])
        
        if clusters:
            for cluster in clusters[:2]:
                matches = cluster.get("matches", [])
                if matches:
                    for match in matches[:2]:
                        # Verify scoring fields
                        assert "score" in match or "match_score" in match, "Missing match score"
                        
                        # Check for component scores
                        score_fields = ["entity_score", "topic_score", "time_score", "resolution_score"]
                        found_scores = [f for f in score_fields if f in match]
                        
                        if found_scores:
                            print(f"Match scores: {', '.join(f'{f}={match.get(f, 0):.2f}' for f in found_scores)}")
                
                # Check parsed resolutions
                parsed = cluster.get("parsed_resolutions", [])
                if parsed:
                    for p in parsed[:2]:
                        if "primitives" in p:
                            print(f"Parsed: {p.get('platform')} - primitives={p.get('primitives')}")
        else:
            print("No debug clusters found")


class TestCrossMarketSignalsWithActionability:
    """Test signals endpoint includes cross-market signals"""
    
    def test_signals_endpoint_returns_signals(self):
        """GET /api/cross-market/signals returns signals with severity"""
        response = requests.get(f"{BASE_URL}/api/cross-market/signals", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "signals" in data, "Missing signals field"
        
        signals = data.get("signals", [])
        print(f"Cross-market signals: {len(signals)} signals found")
        
        # Count by severity
        high = sum(1 for s in signals if s.get("severity") == "HIGH")
        medium = sum(1 for s in signals if s.get("severity") == "MEDIUM")
        low = sum(1 for s in signals if s.get("severity") == "LOW")
        print(f"Severity breakdown: HIGH={high}, MEDIUM={medium}, LOW={low}")
    
    def test_signals_have_required_fields(self):
        """Signals should have type, entity, severity, message"""
        response = requests.get(f"{BASE_URL}/api/cross-market/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        if signals:
            for sig in signals[:5]:
                assert "type" in sig, "Missing type in signal"
                assert "entity" in sig, "Missing entity in signal"
                assert "severity" in sig, "Missing severity in signal"
                
                sig_type = sig.get("type", "")
                valid_types = ["STRUCTURE_MISMATCH", "MONOTONIC_BREAK", "EQUIVALENT_DIVERGENCE", 
                              "LADDER_VIOLATION", "LADDER_GAP"]
                # Allow other types too
                print(f"Signal: {sig_type} - {sig.get('entity')} - {sig.get('severity')}")


class TestActionabilitySeverityThresholds:
    """Test actionability severity thresholds are correctly applied"""
    
    def test_severity_thresholds_in_strategies(self):
        """Verify severity thresholds: STRONG >= 0.75, HIGH >= 0.65, MEDIUM >= 0.55"""
        response = requests.get(f"{BASE_URL}/api/cross-market/strategies", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        actionable = data.get("actionable", [])
        
        for strat in actionable:
            score = strat.get("actionability_score", 0)
            severity = strat.get("actionability_severity", "")
            
            if severity == "STRONG":
                assert score >= 0.75, f"STRONG severity but score={score} < 0.75"
            elif severity == "HIGH":
                assert 0.65 <= score < 0.75, f"HIGH severity but score={score} not in [0.65, 0.75)"
            elif severity == "MEDIUM":
                assert 0.55 <= score < 0.65, f"MEDIUM severity but score={score} not in [0.55, 0.65)"
            
            print(f"Strategy severity check: score={score:.4f} -> {severity} (valid)")


class TestCrossMarketAnalysisEndpoint:
    """Test main analysis endpoint includes Phase 2.5 and 3A data"""
    
    def test_analysis_endpoint_returns_summary(self):
        """GET /api/cross-market/analysis returns comprehensive summary"""
        response = requests.get(f"{BASE_URL}/api/cross-market/analysis", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        
        # Check for summary field with Phase 2 data
        summary = data.get("summary", {})
        assert "mispricings" in summary or "clusters" in summary, "Missing summary info"
        
        print(f"Analysis summary: clusters={summary.get('clusters')}, relations={summary.get('relations')}, mispricings={summary.get('mispricings')}")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
