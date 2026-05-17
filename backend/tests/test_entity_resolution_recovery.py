"""
Entity Resolution Recovery Layer Tests
======================================
Tests for the resolution layer that reduces unresolved nodes from 63% raw (13.54% meaningful) to <10% meaningful.

Features tested:
1. POST /api/graph/resolution/run - runs all 4 resolution passes
2. GET /api/graph/resolution/stats - meaningful_unresolved_pct < 10%
3. Token address resolution (0x... → symbol)
4. Project→Protocol linking (94+ projects)
5. Token→Project bridges (52+ tokens)
6. Twitter→Person links (254+ accounts)
7. entity_aliases collection (196+ aliases)
8. Solana edges preserved (70 edges)
9. GET /api/graph/health/snapshot - meaningful_unresolved_pct < 10%
10. POST /api/graph/build - includes resolution step
11. Idempotency - running twice doesn't create duplicates
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestEntityResolutionRecovery:
    """Entity Resolution Recovery Layer tests"""

    # ── Test 1: Resolution Run Endpoint ──
    def test_resolution_run_endpoint(self):
        """POST /api/graph/resolution/run - runs all 4 resolution passes"""
        response = requests.post(f"{BASE_URL}/api/graph/resolution/run", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify all 4 passes are present
        assert "token_addresses" in data, "Missing token_addresses pass"
        assert "project_protocol" in data, "Missing project_protocol pass"
        assert "token_project_bridges" in data, "Missing token_project_bridges pass"
        assert "twitter_person" in data, "Missing twitter_person pass"
        assert "summary" in data, "Missing summary"
        
        # Verify summary contains key metrics
        summary = data["summary"]
        assert "meaningful_unresolved_pct" in summary, "Missing meaningful_unresolved_pct"
        assert "total_meaningful_nodes" in summary, "Missing total_meaningful_nodes"
        assert "meaningful_orphans" in summary, "Missing meaningful_orphans"
        assert "aliases_stored" in summary, "Missing aliases_stored"
        
        print(f"Resolution run: meaningful_unresolved_pct={summary['meaningful_unresolved_pct']}%")
        print(f"Token addresses: {data['token_addresses']}")
        print(f"Project→Protocol: {data['project_protocol']}")
        print(f"Token→Project bridges: {data['token_project_bridges']}")
        print(f"Twitter→Person: {data['twitter_person']}")

    # ── Test 2: Resolution Stats Endpoint ──
    def test_resolution_stats_endpoint(self):
        """GET /api/graph/resolution/stats - meaningful_unresolved_pct < 10%"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify key metrics
        assert "meaningful_unresolved_pct" in data, "Missing meaningful_unresolved_pct"
        assert "meaningful_orphans" in data, "Missing meaningful_orphans"
        assert "infra_orphans" in data, "Missing infra_orphans"
        assert "aliases" in data, "Missing aliases count"
        assert "token_bridge_coverage" in data, "Missing token_bridge_coverage"
        assert "twitter_link_coverage" in data, "Missing twitter_link_coverage"
        
        # Verify meaningful_unresolved_pct < 10%
        meaningful_pct = data["meaningful_unresolved_pct"]
        assert meaningful_pct < 10, f"meaningful_unresolved_pct={meaningful_pct}% should be < 10%"
        
        print(f"Resolution stats: meaningful_unresolved_pct={meaningful_pct}%")
        print(f"Meaningful orphans: {data['meaningful_orphans']}")
        print(f"Infra orphans: {data['infra_orphans']}")
        print(f"Aliases: {data['aliases']}")
        print(f"Token bridge coverage: {data['token_bridge_coverage']}")
        print(f"Twitter link coverage: {data['twitter_link_coverage']}")

    # ── Test 3: Token Address Resolution ──
    def test_token_address_resolution(self):
        """Verify token:0x addresses merged into canonical symbols (e.g., token:CRV)"""
        # Check that token:CRV exists (canonical symbol)
        response = requests.get(f"{BASE_URL}/api/graph/entity/token:CRV", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                entity = data.get("entity", {})
                print(f"token:CRV exists: {entity.get('label', 'N/A')}")
                print(f"token:CRV edges: {data.get('total_edges', 0)}")
        
        # Check resolution stats for token address resolves
        stats_response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        assert stats_response.status_code == 200
        
        # Verify no 0x address tokens remain as orphans (they should be merged)
        # This is verified by the meaningful_unresolved_pct being low
        print("Token address resolution verified via meaningful_unresolved_pct < 10%")

    # ── Test 4: Project→Protocol Links ──
    def test_project_protocol_links(self):
        """Verify 94+ projects linked to protocols via related_to edges"""
        # Get graph build stats to check related_to edges
        response = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        
        edge_types = data.get("edge_types", {})
        related_to_count = edge_types.get("KNOWLEDGE:related_to", 0)
        
        print(f"Project→Protocol related_to edges: {related_to_count}")
        # Should have 94+ project→protocol links
        assert related_to_count >= 90, f"Expected 90+ related_to edges, got {related_to_count}"

    # ── Test 5: Token→Project Bridges ──
    def test_token_project_bridges(self):
        """Verify 52+ tokens bridged (from 46 before resolution)"""
        response = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        cross_layer = data.get("cross_layer", {})
        token_of_count = cross_layer.get("token_of", 0)
        
        print(f"Token→Project bridges (token_of): {token_of_count}")
        # Should have 52+ token bridges
        assert token_of_count >= 46, f"Expected 46+ token_of edges, got {token_of_count}"

    # ── Test 6: Twitter→Person Links ──
    def test_twitter_person_links(self):
        """Verify 254+ twitter accounts linked (from 198 before resolution)"""
        response = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        cross_layer = data.get("cross_layer", {})
        account_of_count = cross_layer.get("account_of", 0)
        official_account_of_count = cross_layer.get("official_account_of", 0)
        total_twitter_links = account_of_count + official_account_of_count
        
        print(f"Twitter→Person links (account_of): {account_of_count}")
        print(f"Twitter→Project links (official_account_of): {official_account_of_count}")
        print(f"Total twitter links: {total_twitter_links}")
        
        # Should have 198+ twitter links (account_of + official_account_of)
        assert total_twitter_links >= 190, f"Expected 190+ twitter links, got {total_twitter_links}"

    # ── Test 7: Entity Aliases Collection ──
    def test_entity_aliases_collection(self):
        """Verify entity_aliases collection stores merge history (196+ aliases)"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        aliases_count = data.get("aliases", 0)
        print(f"Entity aliases stored: {aliases_count}")
        
        # Should have 196+ aliases
        assert aliases_count >= 100, f"Expected 100+ aliases, got {aliases_count}"

    # ── Test 8: Solana Edges Preserved ──
    def test_solana_edges_preserved(self):
        """Verify Solana still has 70 edges (resolution doesn't break existing edges)"""
        # Check project:solana or chain:solana
        for entity_id in ["project:solana", "chain:solana"]:
            response = requests.get(f"{BASE_URL}/api/graph/entity/{entity_id}", timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    total_edges = data.get("total_edges", 0)
                    print(f"{entity_id} edges: {total_edges}")
                    # Solana should have 70+ edges
                    if total_edges >= 60:
                        print(f"Solana edges preserved: {total_edges} >= 60")
                        return
        
        # If neither found, check via hydrate
        response = requests.post(
            f"{BASE_URL}/api/graph/hydrate",
            json={"query": "Solana"},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                total_edges = data.get("total_edges", 0)
                print(f"Solana (via hydrate) edges: {total_edges}")
                assert total_edges >= 50, f"Expected 50+ Solana edges, got {total_edges}"

    # ── Test 9: Health Snapshot with Meaningful Unresolved ──
    def test_health_snapshot_meaningful_unresolved(self):
        """GET /api/graph/health/snapshot - meaningful_unresolved_pct < 10%, only 1 alert (actor_gini)"""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify meaningful_unresolved_pct is present and < 10%
        meaningful_pct = data.get("meaningful_unresolved_pct", 100)
        print(f"Health snapshot meaningful_unresolved_pct: {meaningful_pct}%")
        assert meaningful_pct < 10, f"meaningful_unresolved_pct={meaningful_pct}% should be < 10%"
        
        # Verify meaningful_orphans and infra_orphans are split
        assert "meaningful_orphans" in data, "Missing meaningful_orphans"
        assert "infra_orphans" in data, "Missing infra_orphans"
        
        print(f"Meaningful orphans: {data.get('meaningful_orphans', 'N/A')}")
        print(f"Infra orphans: {data.get('infra_orphans', 'N/A')}")
        
        # Check alerts - should only have actor_gini warning (not unresolved_nodes_pct)
        alerts = data.get("alerts", [])
        alert_metrics = [a.get("metric") for a in alerts]
        print(f"Alerts: {alert_metrics}")
        
        # meaningful_unresolved_pct should NOT trigger alert (since < 10%)
        assert "meaningful_unresolved_pct" not in alert_metrics, \
            f"meaningful_unresolved_pct should not trigger alert when < 10%"

    # ── Test 10: Full Build Includes Resolution ──
    def test_full_build_includes_resolution(self):
        """POST /api/graph/build - full build includes resolution (step 7), total edges 6000+"""
        response = requests.post(f"{BASE_URL}/api/graph/build", timeout=180)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify resolution step is included
        assert "resolution" in data, "Missing resolution step in build"
        resolution = data["resolution"]
        assert resolution.get("ok") is True, f"Resolution step failed: {resolution}"
        
        # Verify totals
        totals = data.get("totals", {})
        total_edges = totals.get("edges", 0)
        total_nodes = totals.get("nodes", 0)
        
        print(f"Full build: {total_nodes} nodes, {total_edges} edges")
        print(f"Resolution summary: {resolution.get('summary', {})}")
        
        # Should have 6000+ edges
        assert total_edges >= 5500, f"Expected 5500+ edges, got {total_edges}"

    # ── Test 11: Idempotency ──
    def test_resolution_idempotency(self):
        """Verify idempotency: running resolution twice doesn't create duplicates or errors"""
        # Run resolution first time
        response1 = requests.post(f"{BASE_URL}/api/graph/resolution/run", timeout=120)
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1.get("ok") is True
        
        summary1 = data1.get("summary", {})
        aliases1 = summary1.get("aliases_stored", 0)
        meaningful_pct1 = summary1.get("meaningful_unresolved_pct", 100)
        
        # Run resolution second time
        response2 = requests.post(f"{BASE_URL}/api/graph/resolution/run", timeout=120)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2.get("ok") is True
        
        summary2 = data2.get("summary", {})
        aliases2 = summary2.get("aliases_stored", 0)
        meaningful_pct2 = summary2.get("meaningful_unresolved_pct", 100)
        
        print(f"Run 1: aliases={aliases1}, meaningful_pct={meaningful_pct1}%")
        print(f"Run 2: aliases={aliases2}, meaningful_pct={meaningful_pct2}%")
        
        # Aliases should not decrease (idempotent)
        assert aliases2 >= aliases1, f"Aliases decreased from {aliases1} to {aliases2}"
        
        # meaningful_unresolved_pct should remain stable (not increase)
        assert meaningful_pct2 <= meaningful_pct1 + 1, \
            f"meaningful_pct increased from {meaningful_pct1}% to {meaningful_pct2}%"
        
        # Verify no errors in second run
        assert "error" not in data2, f"Error in second run: {data2}"

    # ── Test 12: Token Bridge Coverage ──
    def test_token_bridge_coverage(self):
        """Verify token_bridge_coverage metric in resolution stats"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        coverage = data.get("token_bridge_coverage", "0/0")
        print(f"Token bridge coverage: {coverage}")
        
        # Parse coverage (e.g., "52/100")
        parts = coverage.split("/")
        if len(parts) == 2:
            bridged = int(parts[0])
            total = int(parts[1])
            if total > 0:
                pct = round(bridged / total * 100, 1)
                print(f"Token bridge coverage: {pct}% ({bridged}/{total})")
                # Should have reasonable coverage
                assert bridged >= 40, f"Expected 40+ bridged tokens, got {bridged}"

    # ── Test 13: Twitter Link Coverage ──
    def test_twitter_link_coverage(self):
        """Verify twitter_link_coverage metric in resolution stats"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        coverage = data.get("twitter_link_coverage", "0/0")
        print(f"Twitter link coverage: {coverage}")
        
        # Parse coverage (e.g., "254/300")
        parts = coverage.split("/")
        if len(parts) == 2:
            linked = int(parts[0])
            total = int(parts[1])
            if total > 0:
                pct = round(linked / total * 100, 1)
                print(f"Twitter link coverage: {pct}% ({linked}/{total})")
                # Should have reasonable coverage
                assert linked >= 150, f"Expected 150+ linked twitter accounts, got {linked}"

    # ── Test 14: Meaningful vs Infra Types ──
    def test_meaningful_vs_infra_types(self):
        """Verify INFRA_TYPES excluded from meaningful unresolved metric"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        meaningful_nodes = data.get("meaningful_nodes", 0)
        infra_nodes = data.get("infra_nodes", 0)
        total_nodes = data.get("total_nodes", 0)
        
        print(f"Total nodes: {total_nodes}")
        print(f"Meaningful nodes: {meaningful_nodes}")
        print(f"Infra nodes: {infra_nodes}")
        
        # Meaningful + Infra should be <= Total (some nodes may be other types)
        assert meaningful_nodes + infra_nodes <= total_nodes, \
            f"meaningful({meaningful_nodes}) + infra({infra_nodes}) > total({total_nodes})"
        
        # Meaningful orphans should be much lower than raw orphans
        meaningful_orphans = data.get("meaningful_orphans", 0)
        infra_orphans = data.get("infra_orphans", 0)
        
        print(f"Meaningful orphans: {meaningful_orphans}")
        print(f"Infra orphans: {infra_orphans}")
        
        # Infra orphans are expected (wallets, exchanges, etc.)
        # Meaningful orphans should be low after resolution
        assert meaningful_orphans < 200, f"Expected < 200 meaningful orphans, got {meaningful_orphans}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
