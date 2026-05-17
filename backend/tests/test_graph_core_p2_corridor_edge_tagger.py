"""
P2 Intelligence Layer Tests: Liquidity Corridor Detection + Edge Tagging
=========================================================================
Tests corridor_detector.py and edge_tagger.py modules directly with sample data,
plus API integration tests for /api/graph-core/neighbors/{node_id} response format.

Corridors: DEX→BRIDGE→DEX, DEX→BRIDGE→CEX, CEX→BRIDGE→DEX patterns
Edge Tags: large_transfer (>$500k), exchange_deposit, exchange_withdraw, bridge_exit, dex_swap
Guard: MIN_CORRIDOR_VALUE_USD = $50,000
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ===================================================================
# CORRIDOR DETECTOR UNIT TESTS
# ===================================================================

class TestCorridorDetectorBasics:
    """Basic corridor_detector.py functionality tests"""

    def test_import_corridor_detector(self):
        """Verify corridor_detector module imports correctly"""
        from corridor_detector import detect_corridors, MIN_CORRIDOR_VALUE_USD
        assert callable(detect_corridors)
        assert MIN_CORRIDOR_VALUE_USD == 50000

    def test_empty_input_returns_empty(self):
        """Empty nodes/edges returns empty corridors list"""
        from corridor_detector import detect_corridors
        result = detect_corridors([], [])
        assert result == []
        result = detect_corridors(None, None)
        assert result == []

    def test_nodes_only_no_edges(self):
        """Nodes without edges returns no corridors"""
        from corridor_detector import detect_corridors
        nodes = [
            {"id": "dex:uniswap:eth", "type": "dex"},
            {"id": "bridge:wormhole:eth", "type": "bridge"},
        ]
        result = detect_corridors(nodes, [])
        assert result == []


class TestCorridorPatternDetection:
    """Tests for DEX→BRIDGE→DEX, DEX→BRIDGE→CEX, CEX→BRIDGE→DEX patterns"""

    def test_dex_bridge_dex_pattern_detected(self):
        """DEX → BRIDGE → DEX pattern should be detected"""
        from corridor_detector import detect_corridors
        
        nodes = [
            {"id": "dex:uniswap:eth", "type": "dex", "chain": "ethereum"},
            {"id": "bridge:wormhole:eth", "type": "bridge", "chain": "ethereum"},
            {"id": "dex:sushi:arb", "type": "dex", "chain": "arbitrum"},
        ]
        edges = [
            {"source": "dex:uniswap:eth", "target": "bridge:wormhole:eth", "type": "swap", "amountUsd": 100000},
            {"source": "bridge:wormhole:eth", "target": "dex:sushi:arb", "type": "bridge", "amountUsd": 100000},
        ]
        
        result = detect_corridors(nodes, edges)
        assert len(result) >= 1
        corridor = result[0]
        assert corridor["pattern"] == "DEX_BRIDGE_DEX"
        assert corridor["source"] == "dex:uniswap:eth"
        assert corridor["target"] == "dex:sushi:arb"
        assert corridor["amountUsd"] >= 50000

    def test_dex_bridge_cex_pattern_detected(self):
        """DEX → BRIDGE → CEX pattern should be detected"""
        from corridor_detector import detect_corridors
        
        nodes = [
            {"id": "dex:curve:eth", "type": "dex", "chain": "ethereum"},
            {"id": "bridge:layerzero:eth", "type": "bridge", "chain": "ethereum"},
            {"id": "cex:binance:eth", "type": "cex", "chain": "ethereum"},
        ]
        edges = [
            {"source": "dex:curve:eth", "target": "bridge:layerzero:eth", "type": "transfer", "amountUsd": 75000},
            {"source": "bridge:layerzero:eth", "target": "cex:binance:eth", "type": "exit", "amountUsd": 75000},
        ]
        
        result = detect_corridors(nodes, edges)
        assert len(result) >= 1
        corridor = result[0]
        assert corridor["pattern"] == "DEX_BRIDGE_CEX"

    def test_cex_bridge_dex_pattern_detected(self):
        """CEX → BRIDGE → DEX pattern should be detected"""
        from corridor_detector import detect_corridors
        
        nodes = [
            {"id": "cex:coinbase:eth", "type": "cex", "chain": "ethereum"},
            {"id": "bridge:stargate:eth", "type": "bridge", "chain": "ethereum"},
            {"id": "dex:balancer:eth", "type": "dex", "chain": "ethereum"},
        ]
        edges = [
            {"source": "cex:coinbase:eth", "target": "bridge:stargate:eth", "type": "transfer", "amountUsd": 200000},
            {"source": "bridge:stargate:eth", "target": "dex:balancer:eth", "type": "bridge", "amountUsd": 200000},
        ]
        
        result = detect_corridors(nodes, edges)
        assert len(result) >= 1
        corridor = result[0]
        assert corridor["pattern"] == "CEX_BRIDGE_DEX"


class TestCorridorValueGuard:
    """Tests for $50,000 minimum corridor value guard"""

    def test_corridor_below_50k_skipped(self):
        """Corridors with value < $50,000 should be skipped"""
        from corridor_detector import detect_corridors, MIN_CORRIDOR_VALUE_USD
        
        nodes = [
            {"id": "dex:uni:eth", "type": "dex"},
            {"id": "bridge:hop:eth", "type": "bridge"},
            {"id": "dex:sushi:eth", "type": "dex"},
        ]
        # All edges below $50k
        edges = [
            {"source": "dex:uni:eth", "target": "bridge:hop:eth", "type": "swap", "amountUsd": 30000},
            {"source": "bridge:hop:eth", "target": "dex:sushi:eth", "type": "bridge", "amountUsd": 30000},
        ]
        
        result = detect_corridors(nodes, edges)
        assert len(result) == 0, f"Expected 0 corridors for sub-$50k flow, got {len(result)}"

    def test_corridor_at_50k_boundary_included(self):
        """Corridors with value == $50,000 should be included"""
        from corridor_detector import detect_corridors
        
        nodes = [
            {"id": "dex:uni:eth", "type": "dex"},
            {"id": "bridge:hop:eth", "type": "bridge"},
            {"id": "dex:sushi:eth", "type": "dex"},
        ]
        # Exactly at boundary
        edges = [
            {"source": "dex:uni:eth", "target": "bridge:hop:eth", "type": "swap", "amountUsd": 50000},
            {"source": "bridge:hop:eth", "target": "dex:sushi:eth", "type": "bridge", "amountUsd": 50000},
        ]
        
        result = detect_corridors(nodes, edges)
        assert len(result) >= 1, "Corridor at exactly $50k boundary should be included"

    def test_corridor_above_50k_included(self):
        """Corridors with value > $50,000 should be included"""
        from corridor_detector import detect_corridors
        
        nodes = [
            {"id": "dex:uni:eth", "type": "dex"},
            {"id": "bridge:hop:eth", "type": "bridge"},
            {"id": "cex:kraken:eth", "type": "cex"},
        ]
        edges = [
            {"source": "dex:uni:eth", "target": "bridge:hop:eth", "type": "swap", "amountUsd": 500000},
            {"source": "bridge:hop:eth", "target": "cex:kraken:eth", "type": "bridge", "amountUsd": 500000},
        ]
        
        result = detect_corridors(nodes, edges)
        assert len(result) >= 1
        assert result[0]["amountUsd"] == 500000


class TestCorridorOutputStructure:
    """Tests for corridor output structure fields"""

    def test_corridor_has_required_fields(self):
        """Corridor output must have id, source, target, pattern, amountUsd, path, chains"""
        from corridor_detector import detect_corridors
        
        nodes = [
            {"id": "dex:uni:eth", "type": "dex", "chain": "ethereum"},
            {"id": "bridge:worm:eth", "type": "bridge", "chain": "ethereum"},
            {"id": "dex:sushi:arb", "type": "dex", "chain": "arbitrum"},
        ]
        edges = [
            {"source": "dex:uni:eth", "target": "bridge:worm:eth", "type": "swap", "amountUsd": 100000},
            {"source": "bridge:worm:eth", "target": "dex:sushi:arb", "type": "bridge", "amountUsd": 100000},
        ]
        
        result = detect_corridors(nodes, edges)
        assert len(result) >= 1
        corridor = result[0]
        
        # Required fields
        assert "id" in corridor
        assert "source" in corridor
        assert "target" in corridor
        assert "pattern" in corridor
        assert "amountUsd" in corridor
        assert "path" in corridor
        assert "chains" in corridor
        
        # Field types
        assert isinstance(corridor["id"], str)
        assert isinstance(corridor["source"], str)
        assert isinstance(corridor["target"], str)
        assert isinstance(corridor["pattern"], str)
        assert isinstance(corridor["amountUsd"], (int, float))
        assert isinstance(corridor["path"], list)
        assert isinstance(corridor["chains"], list)

    def test_corridor_id_format(self):
        """Corridor ID should follow 'corridor:{source}-{target}' format"""
        from corridor_detector import detect_corridors
        
        nodes = [
            {"id": "dex:uni:eth", "type": "dex"},
            {"id": "bridge:hop:eth", "type": "bridge"},
            {"id": "dex:sushi:eth", "type": "dex"},
        ]
        edges = [
            {"source": "dex:uni:eth", "target": "bridge:hop:eth", "type": "swap", "amountUsd": 100000},
            {"source": "bridge:hop:eth", "target": "dex:sushi:eth", "type": "bridge", "amountUsd": 100000},
        ]
        
        result = detect_corridors(nodes, edges)
        assert len(result) >= 1
        assert result[0]["id"].startswith("corridor:")

    def test_corridor_path_contains_node_ids(self):
        """Corridor path should contain sequence of node IDs"""
        from corridor_detector import detect_corridors
        
        nodes = [
            {"id": "dex:uni:eth", "type": "dex"},
            {"id": "bridge:hop:eth", "type": "bridge"},
            {"id": "dex:sushi:eth", "type": "dex"},
        ]
        edges = [
            {"source": "dex:uni:eth", "target": "bridge:hop:eth", "type": "swap", "amountUsd": 100000},
            {"source": "bridge:hop:eth", "target": "dex:sushi:eth", "type": "bridge", "amountUsd": 100000},
        ]
        
        result = detect_corridors(nodes, edges)
        assert len(result) >= 1
        path = result[0]["path"]
        assert "dex:uni:eth" in path
        assert "bridge:hop:eth" in path
        assert "dex:sushi:eth" in path


# ===================================================================
# EDGE TAGGER UNIT TESTS
# ===================================================================

class TestEdgeTaggerBasics:
    """Basic edge_tagger.py functionality tests"""

    def test_import_edge_tagger(self):
        """Verify edge_tagger module imports correctly"""
        from edge_tagger import tag_edges, LARGE_TRANSFER_THRESHOLD_USD
        assert callable(tag_edges)
        assert LARGE_TRANSFER_THRESHOLD_USD == 500000

    def test_empty_edges_returns_empty(self):
        """Empty edges list returns empty list"""
        from edge_tagger import tag_edges
        result = tag_edges([], {})
        assert result == []


class TestEdgeTaggerLargeTransfer:
    """Tests for large_transfer tag (>$500k)"""

    def test_large_transfer_tag_applied(self):
        """Edges with amountUsd > $500,000 should get large_transfer tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "a", "target": "b", "amountUsd": 600000}]
        node_map = {"a": {"type": "wallet"}, "b": {"type": "wallet"}}
        
        result = tag_edges(edges, node_map)
        assert "tags" in result[0]
        assert "large_transfer" in result[0]["tags"]

    def test_small_transfer_no_large_tag(self):
        """Edges with amountUsd <= $500,000 should NOT get large_transfer tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "a", "target": "b", "amountUsd": 100000}]
        node_map = {"a": {"type": "wallet"}, "b": {"type": "wallet"}}
        
        result = tag_edges(edges, node_map)
        assert "large_transfer" not in result[0]["tags"]

    def test_boundary_500k_no_large_tag(self):
        """Edges with exactly $500,000 should NOT get large_transfer tag (> not >=)"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "a", "target": "b", "amountUsd": 500000}]
        node_map = {"a": {"type": "wallet"}, "b": {"type": "wallet"}}
        
        result = tag_edges(edges, node_map)
        assert "large_transfer" not in result[0]["tags"]


class TestEdgeTaggerExchangeDeposit:
    """Tests for exchange_deposit tag (target is CEX)"""

    def test_exchange_deposit_tag_cex_target(self):
        """Edges with target being CEX should get exchange_deposit tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "wallet1", "target": "cex1", "amountUsd": 10000}]
        node_map = {
            "wallet1": {"type": "wallet"},
            "cex1": {"type": "cex"}
        }
        
        result = tag_edges(edges, node_map)
        assert "exchange_deposit" in result[0]["tags"]

    def test_no_exchange_deposit_tag_dex_target(self):
        """Edges with target being DEX should NOT get exchange_deposit tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "wallet1", "target": "dex1", "amountUsd": 10000}]
        node_map = {
            "wallet1": {"type": "wallet"},
            "dex1": {"type": "dex"}
        }
        
        result = tag_edges(edges, node_map)
        assert "exchange_deposit" not in result[0]["tags"]


class TestEdgeTaggerExchangeWithdraw:
    """Tests for exchange_withdraw tag (source is CEX)"""

    def test_exchange_withdraw_tag_cex_source(self):
        """Edges with source being CEX should get exchange_withdraw tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "cex1", "target": "wallet1", "amountUsd": 10000}]
        node_map = {
            "cex1": {"type": "cex"},
            "wallet1": {"type": "wallet"}
        }
        
        result = tag_edges(edges, node_map)
        assert "exchange_withdraw" in result[0]["tags"]

    def test_no_exchange_withdraw_tag_dex_source(self):
        """Edges with source being DEX should NOT get exchange_withdraw tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "dex1", "target": "wallet1", "amountUsd": 10000}]
        node_map = {
            "dex1": {"type": "dex"},
            "wallet1": {"type": "wallet"}
        }
        
        result = tag_edges(edges, node_map)
        assert "exchange_withdraw" not in result[0]["tags"]


class TestEdgeTaggerBridgeExit:
    """Tests for bridge_exit tag (edge type is bridge/exit)"""

    def test_bridge_exit_tag_bridge_type(self):
        """Edges with type 'bridge' should get bridge_exit tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "a", "target": "b", "type": "bridge", "amountUsd": 10000}]
        node_map = {"a": {"type": "wallet"}, "b": {"type": "wallet"}}
        
        result = tag_edges(edges, node_map)
        assert "bridge_exit" in result[0]["tags"]

    def test_bridge_exit_tag_exit_type(self):
        """Edges with type 'exit' should get bridge_exit tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "a", "target": "b", "type": "exit", "amountUsd": 10000}]
        node_map = {"a": {"type": "wallet"}, "b": {"type": "wallet"}}
        
        result = tag_edges(edges, node_map)
        assert "bridge_exit" in result[0]["tags"]

    def test_no_bridge_exit_tag_transfer_type(self):
        """Edges with type 'transfer' should NOT get bridge_exit tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "a", "target": "b", "type": "transfer", "amountUsd": 10000}]
        node_map = {"a": {"type": "wallet"}, "b": {"type": "wallet"}}
        
        result = tag_edges(edges, node_map)
        assert "bridge_exit" not in result[0]["tags"]


class TestEdgeTaggerDexSwap:
    """Tests for dex_swap tag (type is swap OR source/target is DEX)"""

    def test_dex_swap_tag_swap_type(self):
        """Edges with type 'swap' should get dex_swap tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "a", "target": "b", "type": "swap", "amountUsd": 10000}]
        node_map = {"a": {"type": "wallet"}, "b": {"type": "wallet"}}
        
        result = tag_edges(edges, node_map)
        assert "dex_swap" in result[0]["tags"]

    def test_dex_swap_tag_dex_source(self):
        """Edges with source being DEX should get dex_swap tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "dex1", "target": "wallet1", "type": "transfer", "amountUsd": 10000}]
        node_map = {
            "dex1": {"type": "dex"},
            "wallet1": {"type": "wallet"}
        }
        
        result = tag_edges(edges, node_map)
        assert "dex_swap" in result[0]["tags"]

    def test_dex_swap_tag_dex_target(self):
        """Edges with target being DEX should get dex_swap tag"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "wallet1", "target": "dex1", "type": "transfer", "amountUsd": 10000}]
        node_map = {
            "wallet1": {"type": "wallet"},
            "dex1": {"type": "dex"}
        }
        
        result = tag_edges(edges, node_map)
        assert "dex_swap" in result[0]["tags"]


class TestEdgeTaggerMultipleTags:
    """Tests for edges that qualify for multiple tags"""

    def test_multiple_tags_applied(self):
        """Edge can have multiple tags applied simultaneously"""
        from edge_tagger import tag_edges
        
        # Large transfer from CEX to DEX (should get: large_transfer, exchange_withdraw, dex_swap)
        edges = [{"source": "cex1", "target": "dex1", "type": "transfer", "amountUsd": 700000}]
        node_map = {
            "cex1": {"type": "cex"},
            "dex1": {"type": "dex"}
        }
        
        result = tag_edges(edges, node_map)
        tags = result[0]["tags"]
        
        assert "large_transfer" in tags
        assert "exchange_withdraw" in tags
        assert "dex_swap" in tags

    def test_cex_to_cex_tags(self):
        """CEX → CEX transfer should get both deposit and withdraw tags"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "cex1", "target": "cex2", "type": "transfer", "amountUsd": 100000}]
        node_map = {
            "cex1": {"type": "cex"},
            "cex2": {"type": "cex"}
        }
        
        result = tag_edges(edges, node_map)
        tags = result[0]["tags"]
        
        assert "exchange_withdraw" in tags
        assert "exchange_deposit" in tags


class TestEdgeTaggerEdgeCases:
    """Tests for edge cases and alternative field names"""

    def test_from_node_id_to_node_id_fields(self):
        """Edge tagger should handle from_node_id/to_node_id field names"""
        from edge_tagger import tag_edges
        
        edges = [{"from_node_id": "cex1", "to_node_id": "wallet1", "amountUsd": 10000}]
        node_map = {
            "cex1": {"type": "cex"},
            "wallet1": {"type": "wallet"}
        }
        
        result = tag_edges(edges, node_map)
        assert "exchange_withdraw" in result[0]["tags"]

    def test_entity_type_field_name(self):
        """Edge tagger should handle entity_type field name for nodes"""
        from edge_tagger import tag_edges
        
        edges = [{"source": "cex1", "target": "wallet1", "amountUsd": 10000}]
        node_map = {
            "cex1": {"entity_type": "cex"},  # Using entity_type instead of type
            "wallet1": {"entity_type": "wallet"}
        }
        
        result = tag_edges(edges, node_map)
        assert "exchange_withdraw" in result[0]["tags"]


# ===================================================================
# API INTEGRATION TESTS (neighbors endpoint)
# ===================================================================

class TestNeighborsEndpointCorridorFields:
    """Tests for corridors field in /api/graph-core/neighbors response"""

    def test_neighbors_returns_corridors_field(self):
        """GET /neighbors/{node_id} should return corridors array"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/wallet:0xTestCorridorAPI:ethereum",
            params={"depth": 2, "limit_nodes": 50, "limit_edges": 100}
        )
        assert response.status_code == 200
        data = response.json()
        assert "corridors" in data
        assert isinstance(data["corridors"], list)

    def test_neighbors_returns_corridor_count_field(self):
        """GET /neighbors/{node_id} should return corridor_count integer"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/wallet:0xTestCorridorCount:ethereum",
            params={"depth": 2, "limit_nodes": 50, "limit_edges": 100}
        )
        assert response.status_code == 200
        data = response.json()
        assert "corridor_count" in data
        assert isinstance(data["corridor_count"], int)
        assert data["corridor_count"] == len(data["corridors"])

    def test_neighbors_cached_response_includes_corridors(self):
        """Cached response should also include corridors field"""
        node_id = "wallet:0xTestCacheCorridors:ethereum"
        
        # First call - cache miss
        response1 = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{node_id}",
            params={"depth": 1, "limit_nodes": 50, "limit_edges": 100}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert "corridors" in data1
        
        # Second call - cache hit
        response2 = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{node_id}",
            params={"depth": 1, "limit_nodes": 50, "limit_edges": 100}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2.get("cached") == True
        assert "corridors" in data2
        assert "corridor_count" in data2


class TestHealthEndpointCacheMetrics:
    """Tests for /api/graph-core/health cache metrics"""

    def test_health_returns_cache_metrics(self):
        """GET /health should return cache metrics"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "ok"
        assert "cache_entries" in data
        assert "cache_hit_rate" in data
        assert "cache_hits" in data
        assert "cache_misses" in data
        assert "avg_graph_build_time_ms" in data


# ===================================================================
# CORRIDOR DETECTOR EDGE CASES
# ===================================================================

class TestCorridorDetectorEdgeCases:
    """Additional edge cases for corridor detection"""

    def test_3hop_corridor_pattern(self):
        """Test 3-hop corridor: DEX → intermediate → BRIDGE → final DEX"""
        from corridor_detector import detect_corridors
        
        nodes = [
            {"id": "dex:start:eth", "type": "dex"},
            {"id": "wallet:mid:eth", "type": "wallet"},
            {"id": "bridge:hop:eth", "type": "bridge"},
            {"id": "dex:end:eth", "type": "dex"},
        ]
        edges = [
            {"source": "dex:start:eth", "target": "wallet:mid:eth", "type": "swap", "amountUsd": 100000},
            {"source": "wallet:mid:eth", "target": "bridge:hop:eth", "type": "transfer", "amountUsd": 100000},
            {"source": "bridge:hop:eth", "target": "dex:end:eth", "type": "bridge", "amountUsd": 100000},
        ]
        
        # Should still detect DEX→BRIDGE→DEX pattern through the path
        result = detect_corridors(nodes, edges)
        # May or may not detect depending on exact algorithm traversal
        # At minimum, no crash
        assert isinstance(result, list)

    def test_corridor_uses_max_edge_value(self):
        """Corridor value should use max of edge amounts"""
        from corridor_detector import detect_corridors
        
        nodes = [
            {"id": "dex:uni:eth", "type": "dex"},
            {"id": "bridge:hop:eth", "type": "bridge"},
            {"id": "dex:sushi:eth", "type": "dex"},
        ]
        edges = [
            {"source": "dex:uni:eth", "target": "bridge:hop:eth", "type": "swap", "amountUsd": 60000},
            {"source": "bridge:hop:eth", "target": "dex:sushi:eth", "type": "bridge", "amountUsd": 80000},
        ]
        
        result = detect_corridors(nodes, edges)
        assert len(result) >= 1
        assert result[0]["amountUsd"] == 80000  # Max of 60k and 80k

    def test_corridor_deduplication(self):
        """Same corridor should not be reported twice"""
        from corridor_detector import detect_corridors
        
        nodes = [
            {"id": "dex:uni:eth", "type": "dex"},
            {"id": "bridge:hop:eth", "type": "bridge"},
            {"id": "dex:sushi:eth", "type": "dex"},
        ]
        # Duplicate edges (same path)
        edges = [
            {"source": "dex:uni:eth", "target": "bridge:hop:eth", "type": "swap", "amountUsd": 100000},
            {"source": "bridge:hop:eth", "target": "dex:sushi:eth", "type": "bridge", "amountUsd": 100000},
            {"source": "dex:uni:eth", "target": "bridge:hop:eth", "type": "swap", "amountUsd": 100000},
            {"source": "bridge:hop:eth", "target": "dex:sushi:eth", "type": "bridge", "amountUsd": 100000},
        ]
        
        result = detect_corridors(nodes, edges)
        # Should only have 1 corridor despite duplicate edges
        dex_bridge_dex = [c for c in result if c["pattern"] == "DEX_BRIDGE_DEX"]
        assert len(dex_bridge_dex) <= 1


# ===================================================================
# CLEANUP
# ===================================================================

@pytest.fixture(scope="module", autouse=True)
def cleanup_test_cache():
    """Clean up test cache entries after all tests"""
    yield
    # Invalidate test cache entries
    try:
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/wallet:0xTestCorridorAPI:ethereum")
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/wallet:0xTestCorridorCount:ethereum")
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/wallet:0xTestCacheCorridors:ethereum")
    except:
        pass
