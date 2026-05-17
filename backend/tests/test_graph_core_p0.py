"""
Graph Core P0 Test Suite - Anchor Entities, Health, Node Label Resolver
Tests the Graph Anchor Entities seed, health endpoint, and anchor-entities retrieval.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')

class TestGraphCoreHealth:
    """Test /api/graph-core/health endpoint - key metrics for monitoring graph size and performance"""

    def test_health_endpoint_returns_ok(self):
        """Health endpoint returns status ok"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_endpoint_returns_node_count(self):
        """Health endpoint returns node_count field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        assert "node_count" in data
        assert isinstance(data["node_count"], int)
        assert data["node_count"] >= 0

    def test_health_endpoint_returns_edge_count(self):
        """Health endpoint returns edge_count field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        assert "edge_count" in data
        assert isinstance(data["edge_count"], int)

    def test_health_endpoint_returns_cache_entries(self):
        """Health endpoint returns cache_entries field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        assert "cache_entries" in data
        assert isinstance(data["cache_entries"], int)

    def test_health_endpoint_returns_query_latency(self):
        """Health endpoint returns query_latency_ms field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        assert "query_latency_ms" in data
        assert isinstance(data["query_latency_ms"], (int, float))
        assert data["query_latency_ms"] >= 0


class TestGraphCoreSeedAnchors:
    """Test /api/graph-core/seed-anchors endpoint - seeds ~30 anchor entities"""

    def test_seed_anchors_endpoint_works(self):
        """Seed-anchors endpoint returns status ok"""
        response = requests.post(f"{BASE_URL}/api/graph-core/seed-anchors")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_seed_anchors_returns_seeded_count(self):
        """Seed-anchors returns seeded count"""
        response = requests.post(f"{BASE_URL}/api/graph-core/seed-anchors")
        assert response.status_code == 200
        data = response.json()
        assert "seeded" in data
        assert isinstance(data["seeded"], int)
        # The endpoint processes 30 entities
        assert data["seeded"] >= 0

    def test_seed_anchors_returns_total_count(self):
        """Seed-anchors returns total count after seeding"""
        response = requests.post(f"{BASE_URL}/api/graph-core/seed-anchors")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert isinstance(data["total"], int)
        # Should have ~29 unique entities (30 entries but Uniswap DEX and UNI token share same address)
        assert data["total"] >= 29


class TestGraphCoreAnchorEntities:
    """Test /api/graph-core/anchor-entities endpoint - retrieves all seeded entities"""

    def test_anchor_entities_endpoint_works(self):
        """Anchor-entities endpoint returns entities list"""
        response = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        assert response.status_code == 200
        data = response.json()
        assert "entities" in data
        assert isinstance(data["entities"], list)

    def test_anchor_entities_returns_count(self):
        """Anchor-entities returns count field matching entities length"""
        response = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] == len(data["entities"])

    def test_anchor_entities_count_is_around_29(self):
        """Anchor-entities count should be ~29 after seeding"""
        # First seed to ensure data exists
        requests.post(f"{BASE_URL}/api/graph-core/seed-anchors")
        
        response = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        assert response.status_code == 200
        data = response.json()
        # Should have ~29 unique entities (30 entries but Uniswap/UNI share address)
        assert data["count"] >= 29

    def test_anchor_entities_have_required_fields(self):
        """Each anchor entity has required fields: type, label, chain, address"""
        response = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        assert response.status_code == 200
        data = response.json()
        
        if len(data["entities"]) > 0:
            entity = data["entities"][0]
            assert "type" in entity
            assert "label" in entity
            assert "chain" in entity
            assert "address" in entity

    def test_anchor_entities_include_known_entities(self):
        """Anchor entities include known entities like Binance, Uniswap, Vitalik"""
        response = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        assert response.status_code == 200
        data = response.json()
        
        labels = [e["label"] for e in data["entities"]]
        
        # Check for key known entities
        assert "Binance" in labels, "Binance should be in anchor entities"
        assert "Vitalik" in labels, "Vitalik should be in anchor entities"
        # Note: Uniswap/UNI share address, so last upsert wins (UNI token)
        # Either Uniswap or UNI should be present
        assert "UNI" in labels or "Uniswap" in labels, "UNI or Uniswap should be in anchor entities"

    def test_anchor_entities_have_diverse_types(self):
        """Anchor entities include diverse types: dex, cex, token, bridge, wallet, contract"""
        response = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        assert response.status_code == 200
        data = response.json()
        
        types = set(e["type"] for e in data["entities"])
        
        expected_types = {"dex", "cex", "token", "bridge", "wallet", "contract"}
        for expected_type in expected_types:
            assert expected_type in types, f"Type '{expected_type}' should be in anchor entities"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
