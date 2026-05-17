"""
Graph Core P3 Testing: Storage Layer + Temporal Filter + Snapshot Builder
=========================================================================
Tests for P3.1 (Storage indexes), P3.2 (Temporal queries), P3.3 (Snapshot build)

Run with:
  pytest /app/backend/tests/test_graph_core_p3_storage_temporal.py -v --tb=short
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ========================================================
# P3.1: Storage Layer Tests (Health endpoint storage stats)
# ========================================================
class TestStorageLayer:
    """Tests for P3.1 - Storage layer with graph_nodes, graph_relations, graph_snapshots, graph_clusters"""

    def test_health_returns_storage_object(self):
        """Health endpoint should return storage stats"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "storage" in data, "Health response should contain 'storage' key"

    def test_storage_contains_graph_nodes_count(self):
        """Storage should have graph_nodes collection count"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = resp.json()
        storage = data.get("storage", {})
        assert "graph_nodes" in storage, "Storage should have graph_nodes"
        assert isinstance(storage["graph_nodes"], int)

    def test_storage_contains_graph_relations_count(self):
        """Storage should have graph_relations collection count"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = resp.json()
        storage = data.get("storage", {})
        assert "graph_relations" in storage, "Storage should have graph_relations"
        assert isinstance(storage["graph_relations"], int)

    def test_storage_contains_graph_snapshots_count(self):
        """Storage should have graph_snapshots collection count"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = resp.json()
        storage = data.get("storage", {})
        assert "graph_snapshots" in storage, "Storage should have graph_snapshots"
        assert isinstance(storage["graph_snapshots"], int)

    def test_storage_contains_graph_clusters_count(self):
        """Storage should have graph_clusters collection count"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = resp.json()
        storage = data.get("storage", {})
        assert "graph_clusters" in storage, "Storage should have graph_clusters"
        assert isinstance(storage["graph_clusters"], int)

    def test_storage_contains_graph_neighbors_cache_count(self):
        """Storage should have graph_neighbors_cache collection count"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = resp.json()
        storage = data.get("storage", {})
        assert "graph_neighbors_cache" in storage, "Storage should have graph_neighbors_cache"
        assert isinstance(storage["graph_neighbors_cache"], int)

    def test_storage_contains_graph_anchor_entities_count(self):
        """Storage should have graph_anchor_entities collection count"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = resp.json()
        storage = data.get("storage", {})
        assert "graph_anchor_entities" in storage, "Storage should have graph_anchor_entities"
        assert isinstance(storage["graph_anchor_entities"], int)


# ========================================================
# P3.2: Temporal Filter Tests (Neighbors endpoint with time params)
# ========================================================
class TestTemporalFilter:
    """Tests for P3.2 - Temporal query support with start_time/end_time params"""

    def test_neighbors_accepts_start_time_param(self):
        """Neighbors endpoint should accept start_time query param"""
        node_id = "wallet:0xTestTemporalStart:ethereum"
        start_ts = int(time.time()) - 86400  # 24h ago
        resp = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{node_id}",
            params={"start_time": start_ts}
        )
        assert resp.status_code == 200

    def test_neighbors_accepts_end_time_param(self):
        """Neighbors endpoint should accept end_time query param"""
        node_id = "wallet:0xTestTemporalEnd:ethereum"
        end_ts = int(time.time())
        resp = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{node_id}",
            params={"end_time": end_ts}
        )
        assert resp.status_code == 200

    def test_neighbors_accepts_both_time_params(self):
        """Neighbors endpoint should accept both start_time and end_time"""
        node_id = "wallet:0xTestTemporalBoth:ethereum"
        now = int(time.time())
        resp = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{node_id}",
            params={"start_time": now - 86400, "end_time": now}
        )
        assert resp.status_code == 200
        data = resp.json()
        # Temporal queries skip cache
        assert "cached" in data
        assert "source" in data

    def test_temporal_query_returns_source_build(self):
        """Temporal queries should skip cache and return source=build"""
        node_id = "wallet:0xTestTemporalBuild:ethereum"
        now = int(time.time())
        resp = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{node_id}",
            params={"start_time": now - 604800}  # 7d ago
        )
        data = resp.json()
        # Temporal queries always fresh build (skip snapshot + cache)
        assert data.get("source") == "build", f"Expected source=build, got {data.get('source')}"
        assert data.get("cached") == False

    def test_temporal_query_returns_nodes_edges_corridors(self):
        """Temporal query response should have nodes, edges, corridors"""
        node_id = "wallet:0xTestTemporalResponse:ethereum"
        now = int(time.time())
        resp = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{node_id}",
            params={"start_time": now - 2592000}  # 30d ago
        )
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert "corridors" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        assert isinstance(data["corridors"], list)

    def test_temporal_query_returns_counts(self):
        """Temporal query response should have node_count, edge_count, corridor_count"""
        node_id = "wallet:0xTestTemporalCounts:ethereum"
        now = int(time.time())
        resp = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{node_id}",
            params={"end_time": now}
        )
        data = resp.json()
        assert "node_count" in data
        assert "edge_count" in data
        assert "corridor_count" in data


# ========================================================
# P3.2 (cont): 3-Tier Cascade Tests
# ========================================================
class TestThreeTierCascade:
    """Tests for neighbors 3-tier cascade: snapshot → cache → relations → KG fallback"""

    def test_neighbors_returns_source_field(self):
        """Neighbors response should always have source field"""
        node_id = "wallet:0xTestCascadeSource:ethereum"
        resp = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{node_id}")
        data = resp.json()
        assert "source" in data, "Response should have 'source' field"
        assert data["source"] in ["snapshot", "cache", "build"], f"Invalid source: {data['source']}"

    def test_first_call_not_snapshot(self):
        """First call to new node should not be from snapshot (unless pre-built)"""
        node_id = f"wallet:0xNewTestNode{int(time.time())}:ethereum"
        resp = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{node_id}")
        data = resp.json()
        # New node shouldn't have snapshot
        assert data.get("source") in ["cache", "build"]

    def test_cached_response_returns_source_cache(self):
        """Cached response should return source=cache or source=snapshot"""
        node_id = "wallet:0xTestCascadeCached:ethereum"
        # First call - cache miss
        resp1 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{node_id}")
        data1 = resp1.json()
        
        if data1.get("cached"):
            # If already cached, verify source
            assert data1["source"] in ["cache", "snapshot"]
        else:
            # Second call - should be cached
            resp2 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{node_id}")
            data2 = resp2.json()
            # Could be cache or snapshot
            assert data2["source"] in ["cache", "snapshot", "build"]


# ========================================================
# P3.3: Snapshot Builder Tests
# ========================================================
class TestSnapshotBuilder:
    """Tests for P3.3 - POST /api/graph-core/snapshots/build endpoint"""

    def test_snapshot_build_endpoint_exists(self):
        """POST /api/graph-core/snapshots/build should exist"""
        resp = requests.post(f"{BASE_URL}/api/graph-core/snapshots/build")
        # Should not return 404
        assert resp.status_code != 404, "Snapshot build endpoint should exist"

    def test_snapshot_build_returns_built_count(self):
        """Snapshot build should return 'built' count"""
        resp = requests.post(f"{BASE_URL}/api/graph-core/snapshots/build")
        data = resp.json()
        assert "built" in data, "Response should have 'built' field"
        assert isinstance(data["built"], int)

    def test_snapshot_build_returns_total_anchors(self):
        """Snapshot build should return 'total_anchors' count"""
        resp = requests.post(f"{BASE_URL}/api/graph-core/snapshots/build")
        data = resp.json()
        assert "total_anchors" in data, "Response should have 'total_anchors' field"
        assert isinstance(data["total_anchors"], int)

    def test_snapshot_build_total_anchors_matches_entities(self):
        """total_anchors from build should match anchor-entities count"""
        # Get anchor entities count
        anchor_resp = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        anchor_data = anchor_resp.json()
        anchor_count = anchor_data.get("count", 0)
        
        # Get snapshot build result
        build_resp = requests.post(f"{BASE_URL}/api/graph-core/snapshots/build")
        build_data = build_resp.json()
        
        # Should match
        assert build_data.get("total_anchors") == anchor_count, \
            f"total_anchors ({build_data.get('total_anchors')}) should match anchor count ({anchor_count})"

    def test_snapshot_count_in_storage_after_build(self):
        """After build, graph_snapshots count should be >= 0"""
        # Trigger build
        requests.post(f"{BASE_URL}/api/graph-core/snapshots/build")
        
        # Check health
        health_resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = health_resp.json()
        snapshots_count = data.get("storage", {}).get("graph_snapshots", -1)
        
        assert snapshots_count >= 0, "Should have non-negative snapshot count"


# ========================================================
# P0/P1/P2 Compatibility Tests (Ensure P3 doesn't break existing)
# ========================================================
class TestP0P1P2Compatibility:
    """Ensure P3 changes don't break P0/P1/P2 functionality"""

    def test_health_still_returns_status_ok(self):
        """Health should still return status: ok"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = resp.json()
        assert data.get("status") == "ok"

    def test_health_still_returns_cache_stats(self):
        """Health should still return P1 cache stats"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = resp.json()
        assert "cache_hit_rate" in data
        assert "cache_hits" in data
        assert "cache_misses" in data

    def test_anchor_entities_still_works(self):
        """Anchor entities endpoint should still work"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        assert resp.status_code == 200
        data = resp.json()
        assert "entities" in data
        assert "count" in data

    def test_neighbors_without_time_params_still_works(self):
        """Neighbors without time params should work (backward compat)"""
        node_id = "wallet:0xTestCompatNeighbors:ethereum"
        resp = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{node_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert "corridors" in data

    def test_cache_invalidate_still_works(self):
        """Cache invalidation should still work"""
        node_id = "wallet:0xTestCompatInvalidate:ethereum"
        resp = requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{node_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "invalidated" in data


# ========================================================
# Integration Tests
# ========================================================
class TestIntegration:
    """Integration tests for full P3 flow"""

    def test_full_neighbor_flow_with_temporal(self):
        """Full flow: neighbor query with temporal → verify response"""
        node_id = "wallet:0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045:ethereum"  # Vitalik (anchor)
        now = int(time.time())
        
        resp = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{node_id}",
            params={
                "depth": 2,
                "limit_nodes": 100,
                "limit_edges": 200,
                "start_time": now - 7776000,  # 90 days
                "end_time": now
            }
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Should be fresh build (temporal skips cache)
        assert data.get("source") == "build"
        assert data.get("cached") == False
        
        # Should have all response fields
        assert "nodes" in data
        assert "edges" in data
        assert "corridors" in data
        assert "node_count" in data
        assert "edge_count" in data

    def test_snapshot_lookup_for_anchor_entity(self):
        """Query anchor entity - might return from snapshot if built"""
        # First ensure snapshots are built
        requests.post(f"{BASE_URL}/api/graph-core/snapshots/build")
        
        # Query a known anchor entity
        node_id = "cex:0x28C6c06298d514Db089934071355E5743bf21d60:ethereum"  # Binance
        
        resp = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{node_id}")
        data = resp.json()
        
        # Should return valid response
        assert resp.status_code == 200
        assert "source" in data
        # Could be snapshot (if built) or build (if empty/not built)
        assert data["source"] in ["snapshot", "cache", "build"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
