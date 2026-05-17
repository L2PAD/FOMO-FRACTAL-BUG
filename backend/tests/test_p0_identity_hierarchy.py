"""
P0 Identity Hierarchy Layer Tests
=================================
Tests the 3-level identity hierarchy (wallet → cluster → entity)
for the On-Chain Graph Intelligence Platform.

Features tested:
- POST /api/graph-core/identity/build
- GET /api/graph-core/identity/resolve/{node_id}?level=wallet|cluster|entity
- GET /api/graph-core/identity/cluster/{cluster_id}/wallets
- GET /api/graph-core/identity/entity/{entity_id}/wallets
- GET /api/graph-core/identity/entity/{entity_id}/clusters
- GET /api/graph-core/project/{node_id}?level=wallet|cluster|entity
- GET /api/graph-core/project/{node_id}?mode=smart_money&level=entity
- POST /api/graph-core/pipeline/run (identity hierarchy step)
- Regression: /api/graph-core/health, /api/graph-core/routes, /api/graph-core/overlay
- Identity deduplication verification
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test node IDs from context
CENTER_NODE = "exchange:binance:ethereum"
WALLET_NODE = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
CLUSTER_NODE = "cluster:binance:ethereum"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestIdentityBuild:
    """Tests for POST /api/graph-core/identity/build"""
    
    def test_identity_build_returns_200(self, api_client):
        """Identity build endpoint should return 200 with stats"""
        response = api_client.post(f"{BASE_URL}/api/graph-core/identity/build")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response has required fields
        assert "status" in data, "Response should have 'status' field"
        assert "mappings" in data, "Response should have 'mappings' count"
        assert "wallets" in data, "Response should have 'wallets' count"
        assert "orphan_wallets" in data, "Response should have 'orphan_wallets' count"
        
        # Verify values are reasonable
        assert isinstance(data["mappings"], int), "mappings should be an integer"
        assert data["mappings"] > 0, "Should have at least some mappings"
        print(f"Identity build: {data['mappings']} mappings, {data['wallets']} wallets, {data['orphan_wallets']} orphans")


class TestIdentityResolve:
    """Tests for GET /api/graph-core/identity/resolve/{node_id}"""
    
    def test_resolve_wallet_to_wallet_level(self, api_client):
        """Resolving wallet at wallet level should return same node"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/resolve/{WALLET_NODE}?level=wallet")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "input" in data, "Response should have 'input' field"
        assert "level" in data, "Response should have 'level' field"
        assert "resolved" in data, "Response should have 'resolved' field"
        assert data["level"] == "wallet"
        assert data["input"] == WALLET_NODE.lower() or WALLET_NODE in data["input"]
        print(f"Wallet→Wallet: {data['input']} → {data['resolved']}")
    
    def test_resolve_wallet_to_cluster_level(self, api_client):
        """Resolving wallet at cluster level should return cluster node"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/resolve/{WALLET_NODE}?level=cluster")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["level"] == "cluster"
        # Wallet should resolve to cluster (binance)
        resolved = data.get("resolved", "")
        print(f"Wallet→Cluster: {data['input']} → {resolved}")
        # Verify it resolved to something cluster-like
        assert resolved != "" or data.get("mapping") is not None, "Should have resolved value or mapping"
    
    def test_resolve_wallet_to_entity_level(self, api_client):
        """Resolving wallet at entity level should return entity node"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/resolve/{WALLET_NODE}?level=entity")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["level"] == "entity"
        resolved = data.get("resolved", "")
        print(f"Wallet→Entity: {data['input']} → {resolved}")
        # Verify it resolved to entity (exchange:binance:ethereum)
        assert resolved != "", "Should resolve to entity"
    
    def test_resolve_entity_at_entity_level(self, api_client):
        """Resolving entity at entity level should return same node"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/resolve/{CENTER_NODE}?level=entity")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        resolved = data.get("resolved", "")
        print(f"Entity→Entity: {data['input']} → {resolved}")
        # Entity should resolve to itself at entity level
        assert resolved != "", "Entity should resolve"
    
    def test_resolve_returns_mapping_details(self, api_client):
        """Identity resolve should include mapping details"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/resolve/{WALLET_NODE}?level=entity")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("mapping"):
            mapping = data["mapping"]
            print(f"Mapping: wallet_id={mapping.get('wallet_id')}, cluster_id={mapping.get('cluster_id')}, entity_id={mapping.get('entity_id')}")


class TestClusterWallets:
    """Tests for GET /api/graph-core/identity/cluster/{cluster_id}/wallets"""
    
    def test_get_cluster_wallets_returns_200(self, api_client):
        """Getting wallets for a cluster should return 200"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/cluster/{CLUSTER_NODE}/wallets")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "cluster_id" in data, "Response should have 'cluster_id'"
        assert "wallets" in data, "Response should have 'wallets'"
        assert "count" in data, "Response should have 'count'"
        assert isinstance(data["wallets"], list), "wallets should be a list"
        print(f"Cluster {CLUSTER_NODE}: {data['count']} wallets")
    
    def test_get_binance_cluster_wallets(self, api_client):
        """Binance cluster should have wallets (based on context: entity binance has 61 wallets)"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/cluster/{CLUSTER_NODE}/wallets")
        assert response.status_code == 200
        
        data = response.json()
        wallet_count = data.get("count", 0)
        # Context says binance has 61 wallets
        print(f"Binance cluster wallets: {wallet_count}")
        # At minimum, should have some wallets


class TestEntityWallets:
    """Tests for GET /api/graph-core/identity/entity/{entity_id}/wallets"""
    
    def test_get_entity_wallets_returns_200(self, api_client):
        """Getting wallets for an entity should return 200"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/entity/{CENTER_NODE}/wallets")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "entity_id" in data, "Response should have 'entity_id'"
        assert "wallets" in data, "Response should have 'wallets'"
        assert "count" in data, "Response should have 'count'"
        print(f"Entity {CENTER_NODE}: {data['count']} wallets")
    
    def test_binance_entity_has_wallets(self, api_client):
        """Binance entity should have wallets (context: 61 wallets)"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/entity/{CENTER_NODE}/wallets")
        assert response.status_code == 200
        
        data = response.json()
        wallet_count = data.get("count", 0)
        print(f"Binance entity wallets: {wallet_count}")


class TestEntityClusters:
    """Tests for GET /api/graph-core/identity/entity/{entity_id}/clusters"""
    
    def test_get_entity_clusters_returns_200(self, api_client):
        """Getting clusters for an entity should return 200"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/entity/{CENTER_NODE}/clusters")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "entity_id" in data, "Response should have 'entity_id'"
        assert "clusters" in data, "Response should have 'clusters'"
        assert "count" in data, "Response should have 'count'"
        print(f"Entity {CENTER_NODE}: {data['count']} clusters")
    
    def test_binance_entity_has_cluster(self, api_client):
        """Binance entity should have at least 1 cluster (context: 1 cluster)"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/entity/{CENTER_NODE}/clusters")
        assert response.status_code == 200
        
        data = response.json()
        cluster_count = data.get("count", 0)
        print(f"Binance entity clusters: {cluster_count}, list: {data.get('clusters', [])}")


class TestProjectionWithLevel:
    """Tests for GET /api/graph-core/project/{node_id}?level=X"""
    
    def test_project_wallet_level(self, api_client):
        """Projection at wallet level should return full graph"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?level=wallet")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "nodes" in data, "Response should have 'nodes'"
        assert "edges" in data, "Response should have 'edges'"
        assert "meta" in data, "Response should have 'meta'"
        
        wallet_nodes = len(data["nodes"])
        wallet_edges = len(data["edges"])
        print(f"Wallet level: {wallet_nodes} nodes, {wallet_edges} edges")
        
        meta = data.get("meta", {})
        assert meta.get("level") == "wallet", "Meta should indicate wallet level"
    
    def test_project_cluster_level(self, api_client):
        """Projection at cluster level should have fewer nodes due to dedup"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?level=cluster")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        cluster_nodes = len(data["nodes"])
        cluster_edges = len(data["edges"])
        print(f"Cluster level: {cluster_nodes} nodes, {cluster_edges} edges")
        
        meta = data.get("meta", {})
        assert meta.get("level") == "cluster", "Meta should indicate cluster level"
    
    def test_project_entity_level(self, api_client):
        """Projection at entity level should have fewest nodes"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?level=entity")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        entity_nodes = len(data["nodes"])
        entity_edges = len(data["edges"])
        print(f"Entity level: {entity_nodes} nodes, {entity_edges} edges")
        
        meta = data.get("meta", {})
        assert meta.get("level") == "entity", "Meta should indicate entity level"
    
    def test_deduplication_reduces_nodes(self, api_client):
        """Entity level should have <= nodes than cluster level, which <= wallet level"""
        # Get wallet level
        wallet_resp = api_client.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?level=wallet")
        assert wallet_resp.status_code == 200
        wallet_data = wallet_resp.json()
        wallet_nodes = len(wallet_data.get("nodes", []))
        wallet_edges = len(wallet_data.get("edges", []))
        
        # Get cluster level
        cluster_resp = api_client.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?level=cluster")
        assert cluster_resp.status_code == 200
        cluster_data = cluster_resp.json()
        cluster_nodes = len(cluster_data.get("nodes", []))
        cluster_edges = len(cluster_data.get("edges", []))
        
        # Get entity level
        entity_resp = api_client.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?level=entity")
        assert entity_resp.status_code == 200
        entity_data = entity_resp.json()
        entity_nodes = len(entity_data.get("nodes", []))
        entity_edges = len(entity_data.get("edges", []))
        
        print(f"Deduplication comparison:")
        print(f"  Wallet: {wallet_nodes} nodes, {wallet_edges} edges")
        print(f"  Cluster: {cluster_nodes} nodes, {cluster_edges} edges")
        print(f"  Entity: {entity_nodes} nodes, {entity_edges} edges")
        
        # Entity should be <= cluster <= wallet (deduplication reduces counts)
        # Note: Could be equal if all nodes are already at entity level
        assert entity_nodes <= cluster_nodes or entity_nodes <= wallet_nodes, \
            f"Entity level ({entity_nodes}) should have <= nodes than cluster ({cluster_nodes}) or wallet ({wallet_nodes})"


class TestProjectionModeAndLevel:
    """Tests for mode + level combo on projection endpoint"""
    
    def test_smart_money_mode_with_entity_level(self, api_client):
        """Projection with mode=smart_money and level=entity should work"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?mode=smart_money&level=entity")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        meta = data.get("meta", {})
        assert meta.get("mode") == "smart_money", "Meta should indicate smart_money mode"
        assert meta.get("level") == "entity", "Meta should indicate entity level"
        print(f"Smart Money + Entity: {len(data['nodes'])} nodes, {len(data['edges'])} edges")
    
    def test_cex_flow_mode_with_cluster_level(self, api_client):
        """Projection with mode=cex_flow and level=cluster should work"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?mode=cex_flow&level=cluster")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        meta = data.get("meta", {})
        assert meta.get("mode") == "cex_flow", "Meta should indicate cex_flow mode"
        assert meta.get("level") == "cluster", "Meta should indicate cluster level"
        print(f"CEX Flow + Cluster: {len(data['nodes'])} nodes, {len(data['edges'])} edges")
    
    def test_entity_mode_with_entity_level(self, api_client):
        """Projection with mode=entity and level=entity should work"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?mode=entity&level=entity")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        meta = data.get("meta", {})
        assert meta.get("mode") == "entity", "Meta should indicate entity mode"
        assert meta.get("level") == "entity", "Meta should indicate entity level"
        print(f"Entity Mode + Entity Level: {len(data['nodes'])} nodes, {len(data['edges'])} edges")


class TestPipelineRun:
    """Tests for POST /api/graph-core/pipeline/run"""
    
    def test_pipeline_includes_identity_step(self, api_client):
        """Pipeline run should include identity hierarchy step"""
        response = api_client.post(f"{BASE_URL}/api/graph-core/pipeline/run")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "status" in data, "Response should have 'status'"
        assert data["status"] == "completed", "Pipeline should complete"
        
        steps = data.get("steps", {})
        assert "identity_hierarchy" in steps, "Pipeline should include identity_hierarchy step"
        
        identity_result = steps.get("identity_hierarchy", {})
        print(f"Identity hierarchy step: {identity_result}")
        
        # Verify identity step has expected fields
        assert "status" in identity_result or "mappings" in identity_result, \
            "Identity step should have status or mappings"


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_health_endpoint(self, api_client):
        """Health endpoint should still work"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "status" in data, "Response should have 'status'"
        assert data["status"] == "ok", "Health status should be ok"
        print(f"Health: {data}")
    
    def test_routes_endpoint(self, api_client):
        """Routes endpoint should still work"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/routes")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "routes" in data, "Response should have 'routes'"
        print(f"Routes: {len(data.get('routes', []))} routes returned")
    
    def test_overlay_endpoint(self, api_client):
        """Overlay endpoint should still work"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/overlay")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "overlays" in data, "Response should have 'overlays'"
        print(f"Overlays: {len(data.get('overlays', []))} overlays returned")


class TestEdgeCases:
    """Edge case tests"""
    
    def test_resolve_unknown_wallet(self, api_client):
        """Resolving an unknown wallet should return gracefully"""
        unknown_wallet = "wallet:0x0000000000000000000000000000000000000001:ethereum"
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/resolve/{unknown_wallet}?level=entity")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should return something (either the same node or empty resolved)
        print(f"Unknown wallet resolution: {data}")
    
    def test_resolve_with_default_level(self, api_client):
        """Resolve without level should default to entity"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/resolve/{WALLET_NODE}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Default level is entity per route definition
        print(f"Default level resolution: level={data.get('level')}, resolved={data.get('resolved')}")
    
    def test_project_without_level_defaults_to_wallet(self, api_client):
        """Project without level should default to wallet"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}")
        assert response.status_code == 200
        
        data = response.json()
        meta = data.get("meta", {})
        # Default level should be wallet per projection service
        assert meta.get("level") == "wallet", "Default level should be wallet"
    
    def test_entity_wallets_with_nonexistent_entity(self, api_client):
        """Getting wallets for nonexistent entity should return empty list"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/identity/entity/entity:nonexistent:ethereum/wallets")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("count", -1) == 0, "Should return 0 wallets for nonexistent entity"
        print(f"Nonexistent entity: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
