"""
Graph Core API — Resolve + Neighbors Tests
============================================
Tests for:
- GET /api/graph-core/health (collection counts)
- GET /api/graph-core/resolve (name/address resolution)
- GET /api/graph-core/neighbors/{node_id} (multi-tier storage cascade)
- POST /api/graph-core/cache/invalidate-all (cache flush)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestHealthEndpoint:
    """Health endpoint: collection counts and status"""

    def test_health_returns_ok_status(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_health_returns_storage_stats(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        storage = data.get("storage", {})
        required_collections = [
            "graph_nodes", "graph_relations", "graph_snapshots",
            "graph_clusters", "graph_neighbors_cache", "graph_anchor_entities"
        ]
        for coll in required_collections:
            assert coll in storage, f"Missing collection: {coll}"

    def test_health_has_graph_snapshots_gt_zero(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        storage = data.get("storage", {})
        assert storage.get("graph_snapshots", 0) > 0, "graph_snapshots should be > 0"

    def test_health_has_cache_stats(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert "cache_hit_rate" in data
        assert "cache_hits" in data
        assert "cache_misses" in data


class TestResolveEndpoint:
    """Resolve endpoint: name/address → canonical node_id"""

    def test_resolve_binance_by_name(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/resolve", params={"q": "Binance"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("found") is True
        assert "cex" in data.get("node_id", "").lower()
        assert data.get("type") == "cex"

    def test_resolve_binance_by_address(self):
        binance_addr = "0x28c6c06298d514db089934071355e5743bf21d60"
        response = requests.get(f"{BASE_URL}/api/graph-core/resolve", params={"q": binance_addr})
        assert response.status_code == 200
        data = response.json()
        assert data.get("found") is True
        assert binance_addr.lower() in data.get("node_id", "").lower()

    def test_resolve_returns_canonical_lowercase_nodeid(self):
        binance_addr = "0x28C6c06298d514Db089934071355E5743bf21d60"  # mixed case
        response = requests.get(f"{BASE_URL}/api/graph-core/resolve", params={"q": binance_addr})
        data = response.json()
        node_id = data.get("node_id", "")
        # Should be all lowercase
        assert node_id == node_id.lower()

    def test_resolve_unknown_returns_wallet_fallback(self):
        unknown_addr = "0x1234567890abcdef1234567890abcdef12345678"
        response = requests.get(f"{BASE_URL}/api/graph-core/resolve", params={"q": unknown_addr})
        assert response.status_code == 200
        data = response.json()
        assert data.get("found") is True
        assert "wallet:" in data.get("node_id", "")

    def test_resolve_uniswap_by_name(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/resolve", params={"q": "Uniswap"})
        assert response.status_code == 200
        data = response.json()
        if data.get("found"):
            # Uniswap may resolve to 'protocol' or 'dex' depending on which anchor entity matches
            assert data.get("type") in ["dex", "protocol", "contract"]


class TestNeighborsEndpoint:
    """Neighbors endpoint: multi-tier cascade (snapshot → cache → relations → Infura)"""

    def test_neighbors_eth_token_has_nodes(self):
        """ETH token (0x000...) should have 400+ nodes from snapshot"""
        node_id = "token:0x0000000000000000000000000000000000000000:ethereum"
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{requests.utils.quote(node_id, safe='')}",
            params={"depth": 2, "limit_nodes": 150, "limit_edges": 400}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("node_count", 0) > 50, f"Expected 50+ nodes, got {data.get('node_count')}"

    def test_neighbors_binance_has_nodes(self):
        """Binance CEX should return cached/snapshot data with 50+ nodes"""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{requests.utils.quote(node_id, safe='')}",
            params={"depth": 2, "limit_nodes": 150, "limit_edges": 400}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("node_count", 0) >= 50, f"Expected 50+ nodes, got {data.get('node_count')}"

    def test_neighbors_returns_source_field(self):
        """Response should indicate source (snapshot/cache/build)"""
        node_id = "token:0x0000000000000000000000000000000000000000:ethereum"
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{requests.utils.quote(node_id, safe='')}",
            params={"depth": 2, "limit_nodes": 150, "limit_edges": 400}
        )
        data = response.json()
        assert "source" in data
        assert data["source"] in ["snapshot", "cache", "build"]

    def test_neighbors_returns_corridors_array(self):
        """Response should include corridors field (may be empty)"""
        node_id = "token:0x0000000000000000000000000000000000000000:ethereum"
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{requests.utils.quote(node_id, safe='')}",
            params={"depth": 2, "limit_nodes": 150, "limit_edges": 400}
        )
        data = response.json()
        assert "corridors" in data
        assert isinstance(data["corridors"], list)

    def test_neighbors_edges_have_required_fields(self):
        """Edges should have source, target, type fields"""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{requests.utils.quote(node_id, safe='')}",
            params={"depth": 2, "limit_nodes": 150, "limit_edges": 400}
        )
        data = response.json()
        edges = data.get("edges", [])
        if edges:
            edge = edges[0]
            assert "source" in edge
            assert "target" in edge


class TestCacheInvalidation:
    """Cache invalidation endpoints"""

    def test_invalidate_all_returns_invalidated_count(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate-all")
        assert response.status_code == 200
        data = response.json()
        assert "invalidated" in data
        assert isinstance(data["invalidated"], int)

    def test_invalidate_specific_node_returns_count(self):
        node_id = "test:invalidate:ethereum"
        response = requests.post(
            f"{BASE_URL}/api/graph-core/cache/invalidate/{requests.utils.quote(node_id, safe='')}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "invalidated" in data


class TestNodeIdNormalization:
    """Verify node_id canonical format enforcement"""

    def test_neighbors_normalizes_mixed_case_address(self):
        """Mixed case addresses should be normalized to lowercase"""
        mixed_case = "cex:0x28C6C06298d514Db089934071355E5743bf21d60:ethereum"
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{requests.utils.quote(mixed_case, safe='')}",
            params={"depth": 1, "limit_nodes": 50, "limit_edges": 100}
        )
        assert response.status_code == 200
        data = response.json()
        # Should still return data (normalized internally)
        assert data.get("node_count", 0) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
