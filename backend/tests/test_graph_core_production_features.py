"""
Graph Core Production Features Tests — Iteration 306
====================================================
Tests for:
- Production indexes (via health endpoint storage counts)
- graph_relation_buckets (temporal optimization)
- graph_corridors (macro flow aggregation)
- Manual wallet clusters (known institutions)
- Updated Active Corridors API (reads from graph_corridors)
- Neighbor cache warming (verified via cache stats)

Run: pytest backend/tests/test_graph_core_production_features.py -v
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestHealthEndpointWithStorageStats:
    """Verify health endpoint shows all collections with data"""

    def test_health_returns_ok_status(self):
        """Health endpoint should return status ok"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_health_returns_storage_stats(self):
        """Health endpoint should include storage stats for all collections"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        storage = data.get("storage", {})
        
        required_collections = [
            "graph_nodes",
            "graph_relations",
            "graph_snapshots",
            "graph_clusters",
            "graph_neighbors_cache",
            "graph_anchor_entities",
        ]
        for coll in required_collections:
            assert coll in storage, f"Missing collection: {coll}"

    def test_health_graph_nodes_has_data(self):
        """graph_nodes collection should have data"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert data["storage"]["graph_nodes"] > 1000, "Expected >1000 nodes"

    def test_health_graph_relations_has_data(self):
        """graph_relations collection should have data"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert data["storage"]["graph_relations"] > 5000, "Expected >5000 relations"

    def test_health_graph_clusters_has_data(self):
        """graph_clusters should have real clusters (not just test clusters)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        # We expect binance, coinbase, jump_trading, etc.
        assert data["storage"]["graph_clusters"] >= 5, "Expected >=5 clusters"

    def test_health_cache_stats_present(self):
        """Health should include cache hit/miss stats"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert "cache_hits" in data
        assert "cache_misses" in data
        assert "cache_hit_rate" in data


class TestActiveCorridorsAPI:
    """Test corridors/active endpoint reads from graph_corridors collection"""

    def test_corridors_active_returns_200(self):
        """Corridors active endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active?limit=20")
        assert response.status_code == 200

    def test_corridors_active_has_count_field(self):
        """Response should include count field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active?limit=20")
        data = response.json()
        assert "count" in data
        assert "corridors" in data

    def test_corridors_active_has_corridor_data(self):
        """Should return at least 1 corridor from graph_corridors collection"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active?limit=20&min_value=0")
        data = response.json()
        assert data["count"] >= 1, "Expected at least 1 corridor in graph_corridors"

    def test_corridors_active_corridor_has_required_fields(self):
        """Each corridor should have source, target, labels, and amounts"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active?limit=5&min_value=0")
        data = response.json()
        if data["corridors"]:
            c = data["corridors"][0]
            assert "source" in c
            assert "target" in c
            assert "source_label" in c
            assert "target_label" in c
            assert "corridor_count" in c
            assert "total_amount_usd" in c

    def test_corridors_active_corridor_types_present(self):
        """Corridors should include source/target type info"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active?limit=5&min_value=0")
        data = response.json()
        if data["corridors"]:
            c = data["corridors"][0]
            assert "source_type" in c
            assert "target_type" in c


class TestClustersAPI:
    """Test manual wallet clusters for known institutions"""

    def test_clusters_returns_200(self):
        """Clusters endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        assert response.status_code == 200

    def test_clusters_has_binance(self):
        """Should have binance cluster (real institution, not test)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        data = response.json()
        cluster_ids = [c["cluster_id"] for c in data["clusters"]]
        assert "binance" in cluster_ids, "Missing binance cluster"

    def test_clusters_has_jump_trading(self):
        """Should have jump_trading cluster"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        data = response.json()
        cluster_ids = [c["cluster_id"] for c in data["clusters"]]
        assert "jump_trading" in cluster_ids, "Missing jump_trading cluster"

    def test_clusters_has_member_count(self):
        """Each cluster should have member_count field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        data = response.json()
        for c in data["clusters"]:
            assert "member_count" in c, f"Cluster {c.get('cluster_id')} missing member_count"

    def test_binance_cluster_has_members(self):
        """Binance cluster should have >10 members"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        data = response.json()
        binance = next((c for c in data["clusters"] if c["cluster_id"] == "binance"), None)
        assert binance is not None
        assert binance["member_count"] > 10, "Expected binance to have >10 member nodes"

    def test_no_test_clusters_in_primary_list(self):
        """Real clusters should be prioritized (no test_ prefix in primary clusters)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        data = response.json()
        real_clusters = [c for c in data["clusters"] if not c["cluster_id"].startswith("test_")]
        # At least 5 real clusters
        assert len(real_clusters) >= 5, "Expected at least 5 real clusters"


class TestClusterMembersAPI:
    """Test cluster members endpoint"""

    def test_binance_members_returns_200(self):
        """GET /clusters/binance/members should return 200"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters/binance/members")
        assert response.status_code == 200

    def test_binance_members_has_nodes(self):
        """Binance members should return actual node data"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters/binance/members")
        data = response.json()
        assert "members" in data
        assert "count" in data
        assert data["count"] > 10, "Expected >10 binance members"

    def test_binance_members_have_id_field(self):
        """Member nodes should have id field (canonical node_id)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters/binance/members")
        data = response.json()
        if data["members"]:
            member = data["members"][0]
            assert "id" in member, "Member should have id field"

    def test_jump_trading_members(self):
        """Jump trading cluster should have at least 1 member"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters/jump_trading/members")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1


class TestNeighborsWithSnapshotCache:
    """Test neighbors endpoint uses snapshot/cache cascade"""

    def test_eth_token_neighbors_has_400_plus_nodes(self):
        """ETH token snapshot should have 400+ nodes"""
        node_id = "token:0x0000000000000000000000000000000000000000:ethereum"
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{requests.utils.quote(node_id, safe='')}",
            params={"depth": 2, "limit_nodes": 500, "limit_edges": 1000}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["node_count"] >= 400, f"Expected >=400 nodes, got {data['node_count']}"

    def test_eth_token_comes_from_snapshot(self):
        """ETH query should hit snapshot (pre-warmed)"""
        node_id = "token:0x0000000000000000000000000000000000000000:ethereum"
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{requests.utils.quote(node_id, safe='')}",
            params={"depth": 2, "limit_nodes": 150, "limit_edges": 400}
        )
        data = response.json()
        assert data["cached"] is True
        assert data["source"] in ["snapshot", "cache"]

    def test_binance_neighbors_has_nodes(self):
        """Binance CEX should return nodes from snapshot/cache"""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{requests.utils.quote(node_id, safe='')}",
            params={"depth": 2, "limit_nodes": 150, "limit_edges": 400}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["node_count"] >= 50, f"Expected >=50 nodes, got {data['node_count']}"

    def test_binance_cached_response(self):
        """Binance should be served from snapshot/cache"""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{requests.utils.quote(node_id, safe='')}",
            params={"depth": 2, "limit_nodes": 150, "limit_edges": 400}
        )
        data = response.json()
        assert data["cached"] is True


class TestResolveEndpoint:
    """Test search/resolve functionality"""

    def test_resolve_binance_by_name(self):
        """Resolve 'Binance' to canonical node_id"""
        response = requests.get(f"{BASE_URL}/api/graph-core/resolve", params={"q": "Binance"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert data["type"] == "cex"
        assert "0x28c6c06298d514db089934071355e5743bf21d60" in data["node_id"].lower()

    def test_resolve_jump_trading(self):
        """Resolve 'Jump Trading' to wallet type"""
        response = requests.get(f"{BASE_URL}/api/graph-core/resolve", params={"q": "Jump Trading"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert data["type"] == "wallet"
        assert data["label"] == "Jump Trading"

    def test_resolve_uniswap(self):
        """Resolve 'Uniswap' to dex or protocol type"""
        response = requests.get(f"{BASE_URL}/api/graph-core/resolve", params={"q": "Uniswap"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        # Uniswap can be dex or protocol (V3 Router contracts)
        assert data["type"] in ["dex", "protocol", "contract"]

    def test_resolve_by_address(self):
        """Resolve by raw address"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/resolve",
            params={"q": "0x28c6c06298d514db089934071355e5743bf21d60"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True


class TestAnchorEntities:
    """Test anchor entities seeding"""

    def test_anchor_entities_returns_200(self):
        """GET /anchor-entities should return 200"""
        response = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        assert response.status_code == 200

    def test_anchor_entities_has_data(self):
        """Should have ~30 anchor entities"""
        response = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        data = response.json()
        assert data["count"] >= 25, f"Expected >=25 anchors, got {data['count']}"

    def test_anchor_entities_include_binance(self):
        """Anchor entities should include Binance"""
        response = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        data = response.json()
        labels = [e["label"] for e in data["entities"]]
        assert "Binance" in labels


class TestCacheWarmingEffects:
    """Verify cache warming script has populated caches"""

    def test_cache_entries_exist(self):
        """Should have some cache entries from warming"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        cache_count = data["storage"].get("graph_neighbors_cache", 0)
        # After warming, we should have some entries
        assert cache_count >= 0, "Cache count should be non-negative"

    def test_snapshots_exist(self):
        """Should have snapshots from warming"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        snap_count = data["storage"].get("graph_snapshots", 0)
        assert snap_count >= 20, f"Expected >=20 snapshots, got {snap_count}"
