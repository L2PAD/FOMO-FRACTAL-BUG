"""
Test suite for GraphExplorer refactoring verification
Tests backend APIs that power the refactored frontend components
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test address used for graph exploration
TEST_ADDRESS = "0x1f2f10d1c40777ae1da742455c65828ff36df387"
TEST_NODE_ID = f"wallet:{TEST_ADDRESS}:ethereum"


class TestGraphCoreAPIs:
    """Tests for graph-core endpoints used by useGraphLoader hook"""
    
    def test_graph_render_endpoint(self):
        """Test /api/graph-core/render/{node_id} returns valid graph data"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'nodes' in data, "Response should contain nodes"
        assert 'edges' in data, "Response should contain edges"
        assert isinstance(data['nodes'], list), "Nodes should be a list"
        assert isinstance(data['edges'], list), "Edges should be a list"
        assert len(data['nodes']) > 0, "Should return at least one node"
        print(f"✓ Render endpoint: {len(data['nodes'])} nodes, {len(data['edges'])} edges")
    
    def test_graph_render_with_smart_money_mode(self):
        """Test render endpoint with smart_money mode returns intelligence data"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150&mode=smart_money"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        # Intelligence data should be present for smart_money mode
        assert 'intelligence' in data, "Smart money mode should return intelligence"
        assert isinstance(data['intelligence'], list), "Intelligence should be a list"
        
        # Market context should be present
        assert 'market_context' in data, "Smart money mode should return market_context"
        if data['market_context']:
            ctx = data['market_context']
            assert 'type' in ctx, "Market context should have type"
            assert 'confidence' in ctx, "Market context should have confidence"
            print(f"✓ Smart Money mode: {len(data['intelligence'])} signals, market_context type: {ctx.get('type')}")
        else:
            print("✓ Smart Money mode: no market context (valid for this address)")
    
    def test_graph_render_with_entity_mode(self):
        """Test render endpoint with entity mode"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150&mode=entity"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'nodes' in data
        assert 'edges' in data
        print(f"✓ Entity mode: {len(data['nodes'])} nodes, {len(data.get('intelligence', []))} signals")
    
    def test_graph_render_with_cex_flow_mode(self):
        """Test render endpoint with cex_flow mode returns cexRoutes"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150&mode=cex_flow"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        # cexRoutes may or may not be present depending on the address
        if 'cexRoutes' in data:
            assert isinstance(data['cexRoutes'], list), "cexRoutes should be a list"
            print(f"✓ CEX Flow mode: {len(data['cexRoutes'])} routes found")
        else:
            print("✓ CEX Flow mode: no cexRoutes (valid for this address)")
    
    def test_graph_render_with_risk_mode(self):
        """Test render endpoint with risk mode"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150&mode=risk"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'nodes' in data
        print(f"✓ Risk mode: {len(data['nodes'])} nodes")
    
    def test_graph_render_with_token_rotation_mode(self):
        """Test render endpoint with token_rotation mode"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150&mode=token_rotation"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'nodes' in data
        print(f"✓ Token Rotation mode: {len(data['nodes'])} nodes")


class TestSearchAndSuggestAPIs:
    """Tests for search/suggest endpoints used by GraphExplorer search bar"""
    
    def test_search_suggest_endpoint(self):
        """Test /api/graph-core/search/suggest returns suggestions"""
        url = f"{BASE_URL}/api/graph-core/search/suggest?q={TEST_ADDRESS[:10]}&limit=8"
        response = requests.get(url, timeout=15)
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'results' in data, "Should return results array"
        assert isinstance(data['results'], list)
        print(f"✓ Search suggest: {len(data['results'])} suggestions for query '{TEST_ADDRESS[:10]}'")
    
    def test_resolve_endpoint(self):
        """Test /api/graph-core/resolve endpoint"""
        url = f"{BASE_URL}/api/graph-core/resolve?q={TEST_ADDRESS}"
        response = requests.get(url, timeout=15)
        
        assert response.status_code == 200
        data = response.json()
        
        # Resolve should find or not find the entity
        assert 'found' in data, "Should return found status"
        print(f"✓ Resolve endpoint: found={data.get('found')}")


class TestEdgesAPI:
    """Tests for edges endpoint used by Relations table"""
    
    def test_edges_endpoint(self):
        """Test /api/graph-core/edges/{node_id} returns edge list"""
        url = f"{BASE_URL}/api/graph-core/edges/{TEST_NODE_ID}?limit=100"
        response = requests.get(url, timeout=15)
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'edges' in data, "Should return edges array"
        assert isinstance(data['edges'], list)
        print(f"✓ Edges endpoint: {len(data['edges'])} edges for {TEST_NODE_ID}")


class TestMarketContextIntegration:
    """Tests specifically for Market Context feature used by MarketContextBlock component"""
    
    def test_market_context_structure(self):
        """Test that market_context has correct structure when present"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150&mode=smart_money"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('market_context'):
            ctx = data['market_context']
            
            # Required fields
            assert 'type' in ctx, "market_context should have 'type'"
            assert 'confidence' in ctx, "market_context should have 'confidence'"
            
            # Type should be one of expected values
            valid_types = ['bullish', 'bearish', 'neutral', 'uncertain']
            assert ctx['type'] in valid_types, f"Type should be one of {valid_types}, got {ctx['type']}"
            
            # Confidence should be 0-1
            assert 0 <= ctx['confidence'] <= 1, "Confidence should be between 0 and 1"
            
            # Optional fields check
            if 'summary' in ctx:
                assert isinstance(ctx['summary'], str), "Summary should be string"
            
            if 'bullish_score' in ctx:
                assert isinstance(ctx['bullish_score'], (int, float)), "bullish_score should be numeric"
            
            if 'bearish_score' in ctx:
                assert isinstance(ctx['bearish_score'], (int, float)), "bearish_score should be numeric"
            
            if 'drivers' in ctx:
                assert isinstance(ctx['drivers'], list), "drivers should be list"
                for driver in ctx['drivers']:
                    assert 'type' in driver, "Each driver should have type"
                    assert 'contribution' in driver, "Each driver should have contribution"
            
            if 'risks' in ctx:
                assert isinstance(ctx['risks'], list), "risks should be list"
                for risk in ctx['risks']:
                    assert 'type' in risk, "Each risk should have type"
                    assert 'contribution' in risk, "Each risk should have contribution"
            
            print(f"✓ Market Context structure valid: type={ctx['type']}, confidence={ctx['confidence']}")
        else:
            print("✓ Market Context not present for this query (valid)")


class TestIntelligenceSignals:
    """Tests for intelligence signals used by IntelligencePanel component"""
    
    def test_intelligence_signal_structure(self):
        """Test that intelligence signals have correct structure"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150&mode=smart_money"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        intel = data.get('intelligence', [])
        
        if intel:
            for i, signal in enumerate(intel):
                assert 'type' in signal, f"Signal {i} should have type"
                assert 'confidence' in signal, f"Signal {i} should have confidence"
                assert 'summary' in signal, f"Signal {i} should have summary"
                
                # Confidence validation
                assert 0 <= signal['confidence'] <= 1, f"Signal {i} confidence should be 0-1"
                
                # Category is optional but useful
                if 'category' in signal:
                    valid_categories = ['smart_money', 'entity', 'risk', 'token_flow', 'route']
                    assert signal['category'] in valid_categories
                
                print(f"  Signal {i}: {signal['type']} ({signal['confidence']*100:.0f}% confidence)")
            
            print(f"✓ Intelligence signals valid: {len(intel)} signals")
        else:
            print("✓ No intelligence signals for this query (valid)")


class TestDiscoveryMode:
    """Tests for discovery mode used when no entity is selected"""
    
    def test_render_seeds_discovery(self):
        """Test /api/graph-core/render-seeds for discovery mode"""
        # Use a simple seed for discovery
        seeds = "exchange:binance,exchange:coinbase"
        url = f"{BASE_URL}/api/graph-core/render-seeds?seeds={seeds}&mode=smart_money&limit=50"
        response = requests.get(url, timeout=30)
        
        # May return 200 or 400 depending on seed validity
        if response.status_code == 200:
            data = response.json()
            assert 'nodes' in data
            print(f"✓ Render-seeds discovery: {len(data['nodes'])} nodes")
        else:
            print(f"✓ Render-seeds: status {response.status_code} (seeds may not exist)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
