"""
Test Flow State Simplification (Final UI Polish)
=================================================
Tests that flow_state is one of only 3 values: ACCUMULATION, DISTRIBUTION, ROUTING
and that no arrows (↑↓↔↩⇉) are present in flow_state values.
"""

import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Valid flow states - ONLY these 3 values allowed
VALID_FLOW_STATES = {'ACCUMULATION', 'DISTRIBUTION', 'ROUTING'}

# Arrow characters that should NOT be present
ARROW_CHARS = re.compile(r'[↑↓↔↩⇉]')

# Node ring colors mapping
RING_COLORS = {
    'ACCUMULATION': '#22c55e',  # Green
    'DISTRIBUTION': '#EF4444',  # Red (case-insensitive)
    'ROUTING': '#EAB308',       # Yellow
}


class TestFlowStateSimplification:
    """Test flow_state returns only 3 valid values without arrows"""
    
    def test_global_liquidity_map_flow_state(self):
        """Test global liquidity map returns valid flow_state"""
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        summary = data.get('summary', {})
        flow_state = summary.get('flow_state')
        
        print(f"Global flow_state: {flow_state}")
        
        # Validate flow_state is one of 3 valid values
        assert flow_state in VALID_FLOW_STATES, f"Invalid flow_state: '{flow_state}'. Must be one of {VALID_FLOW_STATES}"
        
        # Validate no arrows in flow_state
        assert not ARROW_CHARS.search(str(flow_state)), f"flow_state contains arrows: '{flow_state}'"
        
        print(f"✓ Global flow_state '{flow_state}' is valid")
    
    def test_global_liquidity_map_flow_driver(self):
        """Test global liquidity map returns flow_driver"""
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map")
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get('summary', {})
        flow_driver = summary.get('flow_driver')
        
        print(f"Global flow_driver: {flow_driver}")
        
        # flow_driver should be present (can be None but key should exist)
        assert 'flow_driver' in summary, "flow_driver key missing from summary"
        
        # If flow_driver has value, validate no arrows
        if flow_driver:
            assert not ARROW_CHARS.search(str(flow_driver)), f"flow_driver contains arrows: '{flow_driver}'"
        
        print(f"✓ Global flow_driver '{flow_driver}' is valid")
    
    def test_entity_liquidity_map_flow_state_binance(self):
        """Test entity-specific liquidity map for Binance returns valid flow_state"""
        # Binance main wallet
        entity_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map?entity={entity_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        summary = data.get('summary', {})
        flow_state = summary.get('flow_state')
        flow_driver = summary.get('flow_driver')
        
        print(f"Binance entity flow_state: {flow_state}")
        print(f"Binance entity flow_driver: {flow_driver}")
        
        # Validate flow_state is one of 3 valid values
        assert flow_state in VALID_FLOW_STATES, f"Invalid flow_state: '{flow_state}'. Must be one of {VALID_FLOW_STATES}"
        
        # Validate no arrows
        assert not ARROW_CHARS.search(str(flow_state)), f"flow_state contains arrows: '{flow_state}'"
        
        if flow_driver:
            assert not ARROW_CHARS.search(str(flow_driver)), f"flow_driver contains arrows: '{flow_driver}'"
        
        print(f"✓ Binance entity flow_state '{flow_state}' with driver '{flow_driver}' is valid")
    
    def test_entity_liquidity_map_flow_state_coinbase(self):
        """Test entity-specific liquidity map for Coinbase returns valid flow_state"""
        # Coinbase main wallet
        entity_id = "cex:0x71660c4005ba85c37ccec55d0c4493e66fe775d3:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map?entity={entity_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        summary = data.get('summary', {})
        flow_state = summary.get('flow_state')
        
        print(f"Coinbase entity flow_state: {flow_state}")
        
        # Validate flow_state is one of 3 valid values
        assert flow_state in VALID_FLOW_STATES, f"Invalid flow_state: '{flow_state}'. Must be one of {VALID_FLOW_STATES}"
        
        # Validate no arrows
        assert not ARROW_CHARS.search(str(flow_state)), f"flow_state contains arrows: '{flow_state}'"
        
        print(f"✓ Coinbase entity flow_state '{flow_state}' is valid")
    
    def test_no_neutral_or_legacy_states_global(self):
        """Verify NEUTRAL, RETURN TO CEX, REDISTRIBUTION are NOT returned"""
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map")
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get('summary', {})
        flow_state = summary.get('flow_state', '')
        
        # These legacy states should NOT appear
        legacy_states = ['NEUTRAL', 'RETURN TO CEX', 'REDISTRIBUTION']
        for legacy in legacy_states:
            assert flow_state.upper() != legacy.upper(), f"Legacy flow_state '{legacy}' should not be returned"
        
        print(f"✓ No legacy states detected in global response")
    
    def test_no_neutral_or_legacy_states_entity(self):
        """Verify NEUTRAL, RETURN TO CEX, REDISTRIBUTION are NOT returned for entity"""
        entity_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map?entity={entity_id}")
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get('summary', {})
        flow_state = summary.get('flow_state', '')
        
        # These legacy states should NOT appear
        legacy_states = ['NEUTRAL', 'RETURN TO CEX', 'REDISTRIBUTION']
        for legacy in legacy_states:
            assert flow_state.upper() != legacy.upper(), f"Legacy flow_state '{legacy}' should not be returned"
        
        print(f"✓ No legacy states detected in entity response")


class TestNodeRingColors:
    """Test node ring colors are correct for each flow_state"""
    
    def test_render_endpoint_returns_ring_colors(self):
        """Test /render endpoint includes ringColor in nodes"""
        # Use Binance node
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=1&limit=50")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        nodes = data.get('nodes', [])
        
        assert len(nodes) > 0, "No nodes returned"
        
        # Check that nodes have ringColor and flow_state
        nodes_with_ring = [n for n in nodes if n.get('ringColor') or n.get('ring_color')]
        print(f"Nodes with ring colors: {len(nodes_with_ring)} / {len(nodes)}")
        
        # At least some nodes should have ring colors
        assert len(nodes_with_ring) > 0, "No nodes have ring colors"
        
        print(f"✓ Render endpoint returns nodes with ring colors")
    
    def test_ring_color_matches_flow_state(self):
        """Test that ring_color matches flow_state (Green=ACCUMULATION, Red=DISTRIBUTION, Yellow=ROUTING)"""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=1&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        nodes = data.get('nodes', [])
        
        validated_count = 0
        for node in nodes:
            ring_color = node.get('ringColor') or node.get('ring_color')
            flow_state = node.get('flow_state')
            
            if ring_color and flow_state:
                validated_count += 1
                
                # Normalize color for comparison (case-insensitive)
                ring_color_lower = ring_color.lower()
                
                if flow_state == 'ACCUMULATION':
                    expected = RING_COLORS['ACCUMULATION'].lower()
                    assert ring_color_lower == expected, f"ACCUMULATION node has wrong color: {ring_color}, expected {expected}"
                elif flow_state == 'DISTRIBUTION':
                    expected = RING_COLORS['DISTRIBUTION'].lower()
                    assert ring_color_lower == expected, f"DISTRIBUTION node has wrong color: {ring_color}, expected {expected}"
                elif flow_state == 'ROUTING':
                    expected = RING_COLORS['ROUTING'].lower()
                    assert ring_color_lower == expected, f"ROUTING node has wrong color: {ring_color}, expected {expected}"
        
        assert validated_count > 0, "No nodes with both ring_color and flow_state to validate"
        print(f"✓ Validated ring colors for {validated_count} nodes")
    
    def test_accumulation_nodes_have_green_ring(self):
        """Test ACCUMULATION nodes specifically have green (#22c55e) ring"""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=100")
        assert response.status_code == 200
        
        data = response.json()
        nodes = data.get('nodes', [])
        
        accumulation_nodes = [n for n in nodes if n.get('flow_state') == 'ACCUMULATION']
        
        for node in accumulation_nodes:
            ring_color = node.get('ringColor') or node.get('ring_color')
            if ring_color:
                assert ring_color.lower() == '#22c55e', f"ACCUMULATION node {node.get('id', 'unknown')} has wrong color: {ring_color}"
        
        print(f"✓ Found {len(accumulation_nodes)} ACCUMULATION nodes with correct green ring")
    
    def test_distribution_nodes_have_red_ring(self):
        """Test DISTRIBUTION nodes specifically have red (#EF4444) ring"""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=100")
        assert response.status_code == 200
        
        data = response.json()
        nodes = data.get('nodes', [])
        
        distribution_nodes = [n for n in nodes if n.get('flow_state') == 'DISTRIBUTION']
        
        for node in distribution_nodes:
            ring_color = node.get('ringColor') or node.get('ring_color')
            if ring_color:
                assert ring_color.lower() == '#ef4444', f"DISTRIBUTION node {node.get('id', 'unknown')} has wrong color: {ring_color}"
        
        print(f"✓ Found {len(distribution_nodes)} DISTRIBUTION nodes with correct red ring")
    
    def test_routing_nodes_have_yellow_ring(self):
        """Test ROUTING nodes specifically have yellow (#EAB308) ring"""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=100")
        assert response.status_code == 200
        
        data = response.json()
        nodes = data.get('nodes', [])
        
        routing_nodes = [n for n in nodes if n.get('flow_state') == 'ROUTING']
        
        for node in routing_nodes:
            ring_color = node.get('ringColor') or node.get('ring_color')
            if ring_color:
                assert ring_color.lower() == '#eab308', f"ROUTING node {node.get('id', 'unknown')} has wrong color: {ring_color}"
        
        print(f"✓ Found {len(routing_nodes)} ROUTING nodes with correct yellow ring")


class TestRouteIntelligenceFlowState:
    """Test route_intelligence_service flow_state logic"""
    
    def test_route_flow_state_in_global_response(self):
        """Test route_flow_state is included in global liquidity map"""
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check route_flow_state at top level
        route_flow_state = data.get('route_flow_state')
        route_flow_driver = data.get('route_flow_driver')
        
        print(f"route_flow_state: {route_flow_state}")
        print(f"route_flow_driver: {route_flow_driver}")
        
        # If present, validate it's one of 3 valid values
        if route_flow_state:
            assert route_flow_state in VALID_FLOW_STATES, f"Invalid route_flow_state: '{route_flow_state}'"
            assert not ARROW_CHARS.search(str(route_flow_state)), f"route_flow_state contains arrows: '{route_flow_state}'"
        
        print(f"✓ route_flow_state validation passed")
    
    def test_top_routes_labels_no_arrows(self):
        """Test top_routes labels don't contain arrows"""
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map")
        assert response.status_code == 200
        
        data = response.json()
        top_routes = data.get('top_routes', [])
        
        for route in top_routes:
            label = route.get('label', '')
            # Route labels can have → for direction, but not the special arrows ↑↓↔↩⇉
            assert not ARROW_CHARS.search(str(label)), f"Route label contains forbidden arrows: '{label}'"
        
        print(f"✓ Validated {len(top_routes)} route labels - no forbidden arrows")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
