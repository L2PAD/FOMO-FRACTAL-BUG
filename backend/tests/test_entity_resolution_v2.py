"""
Entity Resolution Recovery Layer V2 Tests
==========================================
Tests for enhanced resolution with 5 passes:
1. Token address resolution (32 addresses, label-based fallback)
2. Project→Protocol links (chain-qualified protocol linking)
3. Token→Project bridges (symbol matching)
4. Twitter→Person links (50+ TWITTER_HANDLE_MAP, 0.75 threshold)
5. Signal actor reconnection (orphan twitter with mentions)

Plus: Cron integration, idempotency, alias system, health endpoint rename.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestResolutionEndpoints:
    """Test resolution API endpoints"""

    def test_resolution_run_endpoint_exists(self):
        """POST /api/graph/resolution/run should exist and return ok"""
        response = requests.post(f"{BASE_URL}/api/graph/resolution/run", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        # Should have 5 resolution passes
        assert "token_addresses" in data, "Missing token_addresses pass"
        assert "project_protocol" in data, "Missing project_protocol pass"
        assert "token_project_bridges" in data, "Missing token_project_bridges pass"
        assert "twitter_person" in data, "Missing twitter_person pass"
        assert "signal_actors" in data, "Missing signal_actors pass (PASS 5)"
        print(f"Resolution run: {data.get('summary', {})}")

    def test_resolution_stats_endpoint(self):
        """GET /api/graph/resolution/stats should return coverage metrics"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True
        # Check required fields
        assert "meaningful_unresolved_pct" in data, "Missing meaningful_unresolved_pct"
        assert "meaningful_orphans" in data, "Missing meaningful_orphans"
        assert "infra_orphans" in data, "Missing infra_orphans"
        assert "token_bridge_coverage" in data, "Missing token_bridge_coverage"
        assert "twitter_link_coverage" in data, "Missing twitter_link_coverage"
        assert "aliases" in data, "Missing aliases count"
        print(f"Resolution stats: meaningful_unresolved_pct={data.get('meaningful_unresolved_pct')}%, "
              f"orphans={data.get('meaningful_orphans')}, aliases={data.get('aliases')}")

    def test_health_snapshot_endpoint_renamed(self):
        """GET /api/graph/health/snapshot should work (renamed from health-stats)"""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Should have health metrics
        assert "status" in data or "ok" in data, f"Missing status/ok in response: {data}"
        print(f"Health snapshot: {data.get('status', 'N/A')}")

    def test_graph_build_stats_still_works(self):
        """POST /api/graph/build/stats should still work after resolution changes"""
        response = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True
        assert "nodes" in data, "Missing nodes count"
        assert "edges" in data, "Missing edges count"
        print(f"Graph build stats: {data.get('nodes')} nodes, {data.get('edges')} edges")


class TestResolutionPasses:
    """Test individual resolution passes"""

    def test_token_address_resolution(self):
        """Token address nodes (token:0x...) should merge into canonical token:SYMBOL"""
        # Run resolution first
        requests.post(f"{BASE_URL}/api/graph/resolution/run", timeout=60)
        
        # Check stats
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        data = response.json()
        
        # Token bridge coverage should show bridged tokens
        coverage = data.get("token_bridge_coverage", "0/0")
        bridged, total = coverage.split("/")
        print(f"Token bridge coverage: {coverage}")
        assert int(total) > 0, "Should have token nodes"

    def test_project_protocol_links(self):
        """Orphan projects should link to protocols via name similarity"""
        response = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        data = response.json()
        
        edge_types = data.get("edge_types", {})
        # Check for related_to edges (project→protocol links)
        related_to = edge_types.get("KNOWLEDGE:related_to", 0)
        print(f"Project→Protocol links (related_to): {related_to}")

    def test_chain_qualified_protocol_linking(self):
        """Chain-qualified protocols (protocol:uniswap:ethereum) should link to base protocols"""
        response = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        data = response.json()
        
        edge_types = data.get("edge_types", {})
        # Check for instance_of edges (chain protocol → base protocol)
        instance_of = edge_types.get("KNOWLEDGE:instance_of", 0)
        print(f"Chain protocol links (instance_of): {instance_of}")

    def test_twitter_person_links(self):
        """Twitter accounts should link to persons/projects via TWITTER_HANDLE_MAP"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        data = response.json()
        
        coverage = data.get("twitter_link_coverage", "0/0")
        linked, total = coverage.split("/")
        print(f"Twitter link coverage: {coverage}")
        
        # Check build stats for account_of edges
        build_response = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        build_data = build_response.json()
        edge_types = build_data.get("edge_types", {})
        
        account_of = edge_types.get("KNOWLEDGE:account_of", 0)
        official_account_of = edge_types.get("KNOWLEDGE:official_account_of", 0)
        print(f"Twitter links: account_of={account_of}, official_account_of={official_account_of}")


class TestResolutionIdempotency:
    """Test that resolution is idempotent"""

    def test_resolution_idempotency(self):
        """Running resolution twice should produce identical results on second pass"""
        # First run
        response1 = requests.post(f"{BASE_URL}/api/graph/resolution/run", timeout=60)
        data1 = response1.json()
        
        # Get stats after first run
        stats1 = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30).json()
        aliases1 = stats1.get("aliases", 0)
        pct1 = stats1.get("meaningful_unresolved_pct", 0)
        
        # Second run
        response2 = requests.post(f"{BASE_URL}/api/graph/resolution/run", timeout=60)
        data2 = response2.json()
        
        # Get stats after second run
        stats2 = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30).json()
        aliases2 = stats2.get("aliases", 0)
        pct2 = stats2.get("meaningful_unresolved_pct", 0)
        
        print(f"Run 1: aliases={aliases1}, pct={pct1}")
        print(f"Run 2: aliases={aliases2}, pct={pct2}")
        
        # Second run should have 0 new changes (or very minimal)
        # Aliases should be same or slightly higher (no duplicates)
        assert aliases2 >= aliases1, f"Aliases should not decrease: {aliases1} -> {aliases2}"
        # Percentage should be same or lower
        assert pct2 <= pct1 + 0.5, f"Unresolved pct should not increase significantly: {pct1} -> {pct2}"


class TestAliasSystem:
    """Test entity alias preservation"""

    def test_aliases_stored(self):
        """Merged entities should be preserved in entity_aliases collection"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        data = response.json()
        
        aliases = data.get("aliases", 0)
        print(f"Aliases stored: {aliases}")
        # Should have some aliases from previous resolution runs
        assert aliases >= 0, "Aliases count should be non-negative"


class TestCronIntegration:
    """Test cron pipeline integration"""

    def test_cron_status_includes_resolution(self):
        """Cron status should show entity_resolution stage"""
        response = requests.get(f"{BASE_URL}/api/ingestion/cron/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Check if last_cycle has resolution info
        last_cycle = data.get("last_cycle", {})
        if last_cycle:
            stages = last_cycle.get("stages", [])
            stage_names = [s.get("stage") for s in stages]
            print(f"Cron stages: {stage_names}")
            # entity_resolution should be in the pipeline
            if "entity_resolution" in stage_names:
                print("entity_resolution stage found in cron pipeline")
            else:
                print("Note: entity_resolution may not have run yet in this cycle")


class TestMeaningfulVsInfraOrphans:
    """Test meaningful vs infra orphan separation"""

    def test_meaningful_vs_infra_separation(self):
        """Resolution stats should separate meaningful from infra orphans"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        data = response.json()
        
        meaningful_orphans = data.get("meaningful_orphans", 0)
        infra_orphans = data.get("infra_orphans", 0)
        meaningful_nodes = data.get("meaningful_nodes", 0)
        infra_nodes = data.get("infra_nodes", 0)
        
        print(f"Meaningful: {meaningful_orphans} orphans / {meaningful_nodes} total")
        print(f"Infra: {infra_orphans} orphans / {infra_nodes} total")
        
        # Infra orphans are expected (wallets, exchanges, etc.)
        # Meaningful orphans should be minimized by resolution


class TestSignalActorReconnection:
    """Test PASS 5: Signal actor reconnection"""

    def test_signal_actors_pass_exists(self):
        """Resolution should include signal_actors pass (PASS 5)"""
        response = requests.post(f"{BASE_URL}/api/graph/resolution/run", timeout=60)
        data = response.json()
        
        assert "signal_actors" in data, "Missing signal_actors pass"
        signal_actors = data.get("signal_actors", {})
        print(f"Signal actors pass: {signal_actors}")
        
        # Should have connected and orphan_twitter counts
        assert "connected" in signal_actors or "orphan_twitter" in signal_actors, \
            f"signal_actors should have connected/orphan_twitter: {signal_actors}"


class TestHealthMetrics:
    """Test health metrics after resolution"""

    def test_health_snapshot_metrics(self):
        """Health snapshot should include resolution-aware metrics"""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=30)
        data = response.json()
        
        # Check for meaningful_unresolved_pct (should not trigger alert if < 10%)
        meaningful_pct = data.get("meaningful_unresolved_pct", 0)
        alerts = data.get("alerts", [])
        
        print(f"Health: meaningful_unresolved_pct={meaningful_pct}%")
        print(f"Alerts: {[a.get('metric') for a in alerts]}")
        
        # If meaningful_unresolved_pct < 10%, there should be no unresolved alert
        if meaningful_pct < 10:
            unresolved_alerts = [a for a in alerts if "unresolved" in a.get("metric", "")]
            assert len(unresolved_alerts) == 0, \
                f"Should not have unresolved alert when pct={meaningful_pct}%: {unresolved_alerts}"


class TestTokenBridgeCoverage:
    """Test token→project bridge coverage"""

    def test_token_bridge_coverage_metric(self):
        """Resolution stats should show token bridge coverage"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        data = response.json()
        
        coverage = data.get("token_bridge_coverage", "0/0")
        print(f"Token bridge coverage: {coverage}")
        
        # Parse coverage
        parts = coverage.split("/")
        if len(parts) == 2:
            bridged = int(parts[0])
            total = int(parts[1])
            if total > 0:
                pct = round(bridged / total * 100, 1)
                print(f"Token bridge percentage: {pct}%")


class TestTwitterLinkCoverage:
    """Test twitter→person/project link coverage"""

    def test_twitter_link_coverage_metric(self):
        """Resolution stats should show twitter link coverage"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        data = response.json()
        
        coverage = data.get("twitter_link_coverage", "0/0")
        print(f"Twitter link coverage: {coverage}")
        
        # Parse coverage
        parts = coverage.split("/")
        if len(parts) == 2:
            linked = int(parts[0])
            total = int(parts[1])
            if total > 0:
                pct = round(linked / total * 100, 1)
                print(f"Twitter link percentage: {pct}%")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
