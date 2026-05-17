"""
P1 Capital Influence + P2 Smart Wallet Engine API Tests
========================================================
Tests for:
- POST /api/graph-core/context/build -> capital_influence in details
- GET /api/graph-core/smart-wallets -> wallets with smart_wallet_score, profitability, etc.
- GET /api/graph-core/top-clusters -> clusters with cluster_id, cluster_score, wallet_count
- GET /api/graph-core/top-routes -> routes with path, importance
- GET /api/graph-core/project/{node_id} -> nodes with capitalInfluenceScore field
- GET /api/graph-core/edges/{node_id} -> edges with source_label/target_label
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test node ID for Binance (CEX anchor)
BINANCE_NODE_ID = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"


class TestP1CapitalInfluenceRefactor:
    """P1: Verify capital_influence_score is renamed and present in APIs"""

    def test_context_build_returns_capital_influence(self):
        """POST /api/graph-core/context/build should return 'capital_influence' in details (not 'influence')"""
        response = requests.post(f"{BASE_URL}/api/graph-core/context/build", timeout=60)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "status" in data, "Response should have 'status' field"
        assert "details" in data, "Response should have 'details' field"
        
        details = data["details"]
        # Check that capital_influence is present (P1 refactor renamed influence_score to capital_influence_score)
        assert "capital_influence" in details, f"Expected 'capital_influence' in details, got: {list(details.keys())}"
        
        # Verify capital_influence has scored count
        capital_influence = details["capital_influence"]
        assert "scored" in capital_influence, f"capital_influence should have 'scored' field, got: {capital_influence}"
        print(f"PASS: context/build returned capital_influence with {capital_influence.get('scored', 0)} scored nodes")


class TestP2SmartWalletEngine:
    """P2: Smart Wallet Engine - 3 new endpoints + leaderboard data"""

    def test_smart_wallets_endpoint(self):
        """GET /api/graph-core/smart-wallets returns wallets array with required fields"""
        response = requests.get(f"{BASE_URL}/api/graph-core/smart-wallets?limit=50", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "wallets" in data, f"Response should have 'wallets' field, got: {list(data.keys())}"
        assert "total" in data, f"Response should have 'total' field"
        
        wallets = data["wallets"]
        print(f"smart-wallets returned {len(wallets)} wallets (total: {data.get('total', 0)})")
        
        # If wallets exist, verify required fields per wallet
        if wallets:
            w = wallets[0]
            required_fields = [
                "smart_wallet_score",
                "profitability",
                "early_entry_score",
                "alpha_score",
                "capital_size",
                "capital_influence_score",  # P1 refactor: renamed from influence_score
            ]
            for field in required_fields:
                assert field in w, f"Wallet missing required field '{field}', got: {list(w.keys())}"
            
            # Verify score is numeric and reasonable
            assert isinstance(w["smart_wallet_score"], (int, float)), "smart_wallet_score should be numeric"
            assert 0 <= w["smart_wallet_score"] <= 1, f"smart_wallet_score should be 0-1, got {w['smart_wallet_score']}"
            
            print(f"PASS: Top wallet score={w['smart_wallet_score']:.4f}, profitability={w.get('profitability', 0):.4f}")
        else:
            print("PASS: smart-wallets endpoint returned empty array (no data yet)")

    def test_top_clusters_endpoint(self):
        """GET /api/graph-core/top-clusters returns clusters array with required fields"""
        response = requests.get(f"{BASE_URL}/api/graph-core/top-clusters?limit=20", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "clusters" in data, f"Response should have 'clusters' field, got: {list(data.keys())}"
        assert "total" in data, f"Response should have 'total' field"
        
        clusters = data["clusters"]
        print(f"top-clusters returned {len(clusters)} clusters (total: {data.get('total', 0)})")
        
        # If clusters exist, verify required fields
        if clusters:
            c = clusters[0]
            required_fields = ["cluster_id", "cluster_score", "wallet_count"]
            for field in required_fields:
                assert field in c, f"Cluster missing required field '{field}', got: {list(c.keys())}"
            
            assert isinstance(c["cluster_score"], (int, float)), "cluster_score should be numeric"
            print(f"PASS: Top cluster_id={c['cluster_id']}, score={c['cluster_score']}, wallets={c['wallet_count']}")
        else:
            print("PASS: top-clusters endpoint returned empty array (no cluster data yet)")

    def test_top_routes_endpoint(self):
        """GET /api/graph-core/top-routes returns routes array with path, importance"""
        response = requests.get(f"{BASE_URL}/api/graph-core/top-routes?limit=20", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "routes" in data, f"Response should have 'routes' field, got: {list(data.keys())}"
        assert "total" in data, f"Response should have 'total' field"
        
        routes = data["routes"]
        print(f"top-routes returned {len(routes)} routes (total: {data.get('total', 0)})")
        
        # If routes exist, verify required fields
        if routes:
            r = routes[0]
            required_fields = ["path", "importance"]
            for field in required_fields:
                assert field in r, f"Route missing required field '{field}', got: {list(r.keys())}"
            
            assert isinstance(r["importance"], (int, float)), "importance should be numeric"
            print(f"PASS: Top route importance={r['importance']}, path={r.get('path', [])}")
        else:
            print("PASS: top-routes endpoint returned empty array (no route data yet)")


class TestGraphProjectionCapitalInfluence:
    """Test that projection layer includes capitalInfluenceScore in nodes"""

    def test_project_endpoint_includes_capital_influence_score(self):
        """GET /api/graph-core/project/{node_id} nodes have capitalInfluenceScore field"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/project/{BINANCE_NODE_ID}?depth=2&max_nodes=50&max_edges=100",
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "nodes" in data, f"Response should have 'nodes' field"
        assert "edges" in data, f"Response should have 'edges' field"
        
        nodes = data["nodes"]
        print(f"project endpoint returned {len(nodes)} nodes, {len(data.get('edges', []))} edges")
        
        # Verify nodes have capitalInfluenceScore field
        if nodes:
            # Find node with capitalInfluenceScore > 0 if any
            nodes_with_influence = [n for n in nodes if n.get("capitalInfluenceScore", 0) > 0]
            print(f"Nodes with capitalInfluenceScore > 0: {len(nodes_with_influence)} out of {len(nodes)}")
            
            # Verify field exists in node schema
            n = nodes[0]
            assert "capitalInfluenceScore" in n, f"Node missing 'capitalInfluenceScore' field, got: {list(n.keys())}"
            print(f"PASS: First node has capitalInfluenceScore={n.get('capitalInfluenceScore', 0)}")
        else:
            print("project endpoint returned no nodes")


class TestEdgesWithLabels:
    """Test that edges endpoint returns source_label/target_label"""

    def test_edges_endpoint_includes_labels(self):
        """GET /api/graph-core/edges/{node_id} returns edges with source_label/target_label"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/edges/{BINANCE_NODE_ID}?limit=50",
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "edges" in data, f"Response should have 'edges' field"
        assert "total" in data, f"Response should have 'total' field"
        assert "node_id" in data, f"Response should have 'node_id' field"
        
        edges = data["edges"]
        print(f"edges endpoint returned {len(edges)} edges (total: {data.get('total', 0)})")
        
        # Verify edges have label fields
        if edges:
            e = edges[0]
            # Required fields per API contract
            required_fields = ["source", "target", "source_label", "target_label", "type"]
            for field in required_fields:
                assert field in e, f"Edge missing required field '{field}', got: {list(e.keys())}"
            
            print(f"PASS: Edge source={e['source'][:30]}..., source_label='{e['source_label']}'")
            print(f"      Edge target={e['target'][:30]}..., target_label='{e['target_label']}'")
        else:
            print("edges endpoint returned no edges (node may have no relations)")


class TestHealthAndIntegration:
    """Basic health and integration checks"""

    def test_graph_health(self):
        """GET /api/graph-core/health should return OK"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health", timeout=10)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "status" in data, f"Health response should have 'status'"
        assert data["status"] == "ok", f"Expected status 'ok', got '{data.get('status')}'"
        print(f"PASS: Health OK, storage stats: {data.get('storage', {})}")

    def test_anchor_entities_seeded(self):
        """GET /api/graph-core/anchor-entities should return seeded anchors"""
        response = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities", timeout=10)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "entities" in data, f"Response should have 'entities' field"
        assert "count" in data, f"Response should have 'count' field"
        
        entities = data["entities"]
        print(f"PASS: anchor-entities returned {len(entities)} entities")
        
        # Verify Binance is in anchors
        binance_anchors = [e for e in entities if "binance" in e.get("label", "").lower()]
        assert len(binance_anchors) > 0, "Binance should be in anchor entities"
        print(f"  Found Binance anchors: {[e['label'] for e in binance_anchors]}")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
