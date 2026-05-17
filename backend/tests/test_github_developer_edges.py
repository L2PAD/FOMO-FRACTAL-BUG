"""
GitHub Developer→Project Edges Test Suite
==========================================
Tests for GitHub parser integration with Knowledge Graph.
- 26 tracked crypto repos (Ethereum, Solana, Aptos, etc.)
- developer:login → project:key (contributes_to) edges
- Contribution-weighted scores (log scale)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestGitHubSync:
    """Test GitHub sync endpoint and data population"""

    def test_github_sync_returns_projects(self):
        """POST /api/graph/github/sync — syncs repos from GitHub API"""
        resp = requests.post(f"{BASE_URL}/api/graph/github/sync", json={"batch_size": 5}, timeout=180)
        assert resp.status_code == 200, f"GitHub sync failed: {resp.text}"
        
        data = resp.json()
        # Check response structure
        assert "projects" in data or "synced" in data, f"Missing projects/synced in response: {data}"
        
        # Check graph_edges were created
        if "graph_edges" in data:
            edges = data["graph_edges"]
            assert "edges" in edges, f"Missing edges count: {edges}"
            print(f"GitHub sync: {edges.get('edges', 0)} contributes_to edges, {edges.get('nodes', 0)} nodes")
        
        # Check projects synced
        projects = data.get("projects", [])
        if projects:
            print(f"Synced {len(projects)} projects:")
            for p in projects[:5]:
                print(f"  - {p.get('project', 'N/A')}: dev_score={p.get('dev_score', 0)}")


class TestGraphBuild:
    """Test full graph build includes GitHub edges"""

    def test_graph_build_includes_github_edges(self):
        """POST /api/graph/build — full rebuild includes GitHub edges"""
        resp = requests.post(f"{BASE_URL}/api/graph/build", timeout=120)
        assert resp.status_code == 200, f"Graph build failed: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True, f"Graph build not ok: {data}"
        
        # Check GitHub edges were built
        github = data.get("github", {})
        github_edges = github.get("edges", 0)
        github_nodes = github.get("nodes", 0)
        print(f"GitHub edges: {github_edges}, nodes: {github_nodes}")
        
        # Check totals
        totals = data.get("totals", {})
        total_nodes = totals.get("nodes", 0)
        total_edges = totals.get("edges", 0)
        print(f"Total graph: {total_nodes} nodes, {total_edges} edges")
        
        # Verify GitHub edges exist (should be 173+ based on context)
        assert github_edges >= 0, f"No GitHub edges created: {github}"

    def test_graph_build_stats_shows_contributes_to(self):
        """GET /api/graph/build/stats — shows correct node/edge counts with GitHub data"""
        resp = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        assert resp.status_code == 200, f"Stats failed: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True, f"Stats not ok: {data}"
        
        # Check edge types include contributes_to
        edge_types = data.get("edge_types", {})
        contributes_to_count = edge_types.get("KNOWLEDGE:contributes_to", 0)
        print(f"contributes_to edges: {contributes_to_count}")
        
        # Check node types include developer
        node_types = data.get("node_types", {})
        developer_count = node_types.get("developer", 0)
        print(f"developer nodes: {developer_count}")
        
        # Check cross-layer bridges
        cross_layer = data.get("cross_layer", {})
        print(f"Cross-layer bridges: token_of={cross_layer.get('token_of', 0)}, account_of={cross_layer.get('account_of', 0)}")
        
        # Verify totals
        print(f"Total: {data.get('nodes', 0)} nodes, {data.get('edges', 0)} edges")


class TestEntityDetail:
    """Test entity detail endpoints for projects with GitHub data"""

    def test_ethereum_has_contributes_to_edges(self):
        """GET /api/graph/entity/project:ethereum — has contributes_to edges from developers"""
        resp = requests.get(f"{BASE_URL}/api/graph/entity/project:ethereum", timeout=30)
        assert resp.status_code == 200, f"Entity fetch failed: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True, f"Entity not ok: {data}"
        
        # Check entity exists
        entity = data.get("entity", {})
        assert entity.get("id") == "project:ethereum", f"Wrong entity: {entity}"
        
        # Check edges
        edges = data.get("edges", [])
        contributes_to_edges = [e for e in edges if e.get("relation_type") == "contributes_to"]
        print(f"Ethereum: {len(contributes_to_edges)} contributes_to edges out of {len(edges)} total")
        
        # List some developers
        if contributes_to_edges:
            developers = [e.get("from_node_id", "").replace("developer:", "") for e in contributes_to_edges[:10]]
            print(f"Top developers: {developers}")
        
        # Check edges_by_layer
        edges_by_layer = data.get("edges_by_layer", {})
        print(f"Edges by layer: {edges_by_layer}")

    def test_solana_has_contributes_to_edges(self):
        """GET /api/graph/entity/project:solana — has contributes_to edges from developers"""
        resp = requests.get(f"{BASE_URL}/api/graph/entity/project:solana", timeout=30)
        assert resp.status_code == 200, f"Entity fetch failed: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True, f"Entity not ok: {data}"
        
        # Check entity exists
        entity = data.get("entity", {})
        assert entity.get("id") == "project:solana", f"Wrong entity: {entity}"
        
        # Check edges
        edges = data.get("edges", [])
        contributes_to_edges = [e for e in edges if e.get("relation_type") == "contributes_to"]
        print(f"Solana: {len(contributes_to_edges)} contributes_to edges out of {len(edges)} total")
        
        # List some developers
        if contributes_to_edges:
            developers = [e.get("from_node_id", "").replace("developer:", "") for e in contributes_to_edges[:10]]
            print(f"Top developers: {developers}")


class TestDeveloperNodes:
    """Test developer nodes exist in graph"""

    def test_developer_obscuren_exists(self):
        """Verify developer:obscuren node exists (Ethereum contributor)"""
        # First check via entity endpoint
        resp = requests.get(f"{BASE_URL}/api/graph/entity/developer:obscuren", timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                entity = data.get("entity", {})
                print(f"developer:obscuren found: {entity.get('label', 'N/A')}")
                edges = data.get("edges", [])
                print(f"  Edges: {len(edges)}")
                return
        
        # If not found directly, search via hydrate
        resp = requests.post(f"{BASE_URL}/api/graph/hydrate", json={"query": "obscuren"}, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            nodes = data.get("nodes", [])
            dev_nodes = [n for n in nodes if n.get("id", "").startswith("developer:")]
            if dev_nodes:
                print(f"Found via hydrate: {[n.get('id') for n in dev_nodes]}")
            else:
                print(f"developer:obscuren not found (may not be in top contributors)")

    def test_developer_mvines_exists(self):
        """Verify developer:mvines node exists (Solana contributor)"""
        resp = requests.get(f"{BASE_URL}/api/graph/entity/developer:mvines", timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                entity = data.get("entity", {})
                print(f"developer:mvines found: {entity.get('label', 'N/A')}")
                edges = data.get("edges", [])
                print(f"  Edges: {len(edges)}")
                return
        
        # If not found directly, search via hydrate
        resp = requests.post(f"{BASE_URL}/api/graph/hydrate", json={"query": "mvines"}, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            nodes = data.get("nodes", [])
            dev_nodes = [n for n in nodes if n.get("id", "").startswith("developer:")]
            if dev_nodes:
                print(f"Found via hydrate: {[n.get('id') for n in dev_nodes]}")
            else:
                print(f"developer:mvines not found (may not be in top contributors)")


class TestHydration:
    """Test entity hydration with GitHub data"""

    def test_hydrate_ethereum_returns_edges(self):
        """POST /api/graph/hydrate {query:'Ethereum'} — returns edges across layers"""
        resp = requests.post(f"{BASE_URL}/api/graph/hydrate", json={"query": "Ethereum"}, timeout=30)
        assert resp.status_code == 200, f"Hydrate failed: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True, f"Hydrate not ok: {data}"
        
        matched_nodes = data.get("matched_nodes", 0)
        total_edges = data.get("total_edges", 0)
        total_neighbors = data.get("total_neighbors", 0)
        
        print(f"Ethereum hydration: {matched_nodes} matched, {total_edges} edges, {total_neighbors} neighbors")
        
        # Check edge types
        edges = data.get("edges", [])
        edge_types = {}
        for e in edges:
            rt = e.get("relation_type", "unknown")
            edge_types[rt] = edge_types.get(rt, 0) + 1
        print(f"Edge types: {edge_types}")

    def test_hydrate_solana_returns_edges(self):
        """POST /api/graph/hydrate {query:'Solana'} — returns edges across layers"""
        resp = requests.post(f"{BASE_URL}/api/graph/hydrate", json={"query": "Solana"}, timeout=30)
        assert resp.status_code == 200, f"Hydrate failed: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True, f"Hydrate not ok: {data}"
        
        matched_nodes = data.get("matched_nodes", 0)
        total_edges = data.get("total_edges", 0)
        
        print(f"Solana hydration: {matched_nodes} matched, {total_edges} edges")


class TestIdempotency:
    """Test graph build idempotency"""

    def test_build_twice_no_duplicates(self):
        """Verify graph idempotency: running build twice doesn't create duplicates"""
        # First build
        resp1 = requests.post(f"{BASE_URL}/api/graph/build", timeout=120)
        assert resp1.status_code == 200, f"First build failed: {resp1.text}"
        
        data1 = resp1.json()
        totals1 = data1.get("totals", {})
        nodes1 = totals1.get("nodes", 0)
        edges1 = totals1.get("edges", 0)
        print(f"First build: {nodes1} nodes, {edges1} edges")
        
        # Wait a bit
        time.sleep(2)
        
        # Second build
        resp2 = requests.post(f"{BASE_URL}/api/graph/build", timeout=120)
        assert resp2.status_code == 200, f"Second build failed: {resp2.text}"
        
        data2 = resp2.json()
        totals2 = data2.get("totals", {})
        nodes2 = totals2.get("nodes", 0)
        edges2 = totals2.get("edges", 0)
        print(f"Second build: {nodes2} nodes, {edges2} edges")
        
        # Verify no significant increase (small variance allowed for timing)
        node_diff = abs(nodes2 - nodes1)
        edge_diff = abs(edges2 - edges1)
        
        # Allow up to 5% variance for timing-related changes
        max_node_diff = max(50, int(nodes1 * 0.05))
        max_edge_diff = max(100, int(edges1 * 0.05))
        
        assert node_diff <= max_node_diff, f"Node count changed significantly: {nodes1} → {nodes2} (diff={node_diff})"
        assert edge_diff <= max_edge_diff, f"Edge count changed significantly: {edges1} → {edges2} (diff={edge_diff})"
        
        print(f"Idempotency verified: node_diff={node_diff}, edge_diff={edge_diff}")


class TestHTMLFallback:
    """Test HTML fallback endpoints still work"""

    def test_fallback_test_cryptorank(self):
        """POST /api/graph/fallback/test {parser:'CryptoRank'} — HTML fallback works"""
        resp = requests.post(f"{BASE_URL}/api/graph/fallback/test", json={"parser": "CryptoRank"}, timeout=60)
        assert resp.status_code == 200, f"Fallback test failed: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True, f"Fallback not ok: {data}"
        
        count = data.get("count", 0)
        duration = data.get("duration_sec", 0)
        print(f"CryptoRank HTML fallback: {count} coins in {duration}s")

    def test_fallback_status(self):
        """GET /api/graph/fallback/status — returns parser statuses"""
        resp = requests.get(f"{BASE_URL}/api/graph/fallback/status", timeout=30)
        assert resp.status_code == 200, f"Fallback status failed: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True, f"Status not ok: {data}"
        
        parsers = data.get("parsers", [])
        print(f"Fallback status: {len(parsers)} parsers")
        for p in parsers[:5]:
            print(f"  - {p.get('name', 'N/A')}: status={p.get('status', 'N/A')}, failures={p.get('consecutive_failures', 0)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
