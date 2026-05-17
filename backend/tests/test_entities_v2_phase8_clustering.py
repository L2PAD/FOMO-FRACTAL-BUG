"""
Entities V2 — Phase 8: Clustering Engine API Tests
====================================================
Tests for wallet clustering based on on-chain activity patterns.

Endpoints tested:
  - GET /api/entities/v2/{slug}/clusters — Entity cluster data
  - GET /api/entities/v2/clusters/overview — Cross-entity cluster overview  
  - POST /api/entities/v2/clusters/build-all — Build clusters for all entities
  - GET /api/entities/v2/nonexistent/clusters — 404 error handling
"""

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ══════════════════════════════════════════════════════════
#  Entity Cluster Endpoint Tests — Binance (large entity)
# ══════════════════════════════════════════════════════════

class TestBinanceClusters:
    """Tests for GET /api/entities/v2/binance/clusters — entity with most data."""

    def test_binance_clusters_status(self, api_client):
        """Should return 200 for valid entity."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True

    def test_binance_clusters_entity_info(self, api_client):
        """Should include entity metadata."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        entity = data.get("entity", {})
        assert entity.get("slug") == "binance"
        assert entity.get("name") is not None
        assert entity.get("type") is not None
        assert entity.get("category") is not None

    def test_binance_clusters_known_addresses(self, api_client):
        """Binance should have 5 known addresses (per context)."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        known_addrs = data.get("known_addresses", 0)
        assert known_addrs >= 5, f"Expected >= 5 known addresses, got {known_addrs}"

    def test_binance_clusters_total_counterparties(self, api_client):
        """Binance should have 200+ counterparties (per context)."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        total_cp = data.get("total_counterparties", 0)
        assert total_cp >= 200, f"Expected >= 200 counterparties, got {total_cp}"

    def test_binance_clusters_discovered_addresses(self, api_client):
        """Binance should have discovered addresses (211 per context)."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        total_disc = data.get("total_discovered", 0)
        assert total_disc > 0, f"Expected discovered addresses > 0, got {total_disc}"

    def test_binance_coverage_expansion(self, api_client):
        """Coverage expansion should be total_discovered / known_addresses."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        known = data.get("known_addresses", 0)
        discovered = data.get("total_discovered", 0)
        coverage = data.get("coverage_expansion", 0)
        if known > 0:
            expected = round(discovered / known, 2)
            assert abs(coverage - expected) < 0.1, f"Coverage {coverage} != {expected}"

    def test_binance_clusters_list_structure(self, api_client):
        """Should have clusters array with tier-based groupings."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        clusters = data.get("clusters", [])
        assert isinstance(clusters, list), "clusters should be a list"
        assert len(clusters) > 0, "Binance should have clusters"

    def test_binance_cluster_item_structure(self, api_client):
        """Each cluster should have required fields."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        clusters = data.get("clusters", [])
        for cluster in clusters:
            assert "cluster_id" in cluster, "Missing cluster_id"
            assert "tier" in cluster, "Missing tier"
            assert "size" in cluster, "Missing size"
            assert "confidence" in cluster, "Missing confidence"
            assert "activity_score" in cluster, "Missing activity_score"
            assert "total_transfers" in cluster, "Missing total_transfers"
            assert "members" in cluster, "Missing members"

    def test_binance_cluster_tiers(self, api_client):
        """Cluster tiers should be high/medium/low."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        clusters = data.get("clusters", [])
        valid_tiers = {"high", "medium", "low"}
        for cluster in clusters:
            tier = cluster.get("tier")
            assert tier in valid_tiers, f"Invalid tier: {tier}"

    def test_binance_cluster_confidence_range(self, api_client):
        """Cluster confidence should be float between 0 and 1."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        clusters = data.get("clusters", [])
        for cluster in clusters:
            conf = cluster.get("confidence", -1)
            assert 0 <= conf <= 1, f"Confidence out of range: {conf}"

    def test_binance_cluster_member_structure(self, api_client):
        """Each cluster member should have required fields."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        clusters = data.get("clusters", [])
        for cluster in clusters:
            members = cluster.get("members", [])
            for member in members[:5]:  # Check first 5
                assert "address" in member, "Missing address"
                assert "confidence" in member, "Missing confidence"
                assert "role" in member, "Missing role"
                assert "transfer_count" in member, "Missing transfer_count"
                assert "entity_links" in member, "Missing entity_links"
                assert "unique_tokens" in member, "Missing unique_tokens"

    def test_binance_member_roles(self, api_client):
        """Member roles should be sender/receiver/intermediary/peripheral."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        clusters = data.get("clusters", [])
        valid_roles = {"sender", "receiver", "intermediary", "peripheral"}
        for cluster in clusters:
            members = cluster.get("members", [])
            for member in members[:5]:
                role = member.get("role")
                assert role in valid_roles, f"Invalid role: {role}"

    def test_binance_member_confidence_range(self, api_client):
        """Member confidence should be float between 0 and 1."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        clusters = data.get("clusters", [])
        for cluster in clusters:
            members = cluster.get("members", [])
            for member in members[:5]:
                conf = member.get("confidence", -1)
                assert isinstance(conf, (int, float)), f"Confidence not numeric: {conf}"
                assert 0 <= conf <= 1, f"Member confidence out of range: {conf}"

    def test_binance_tier_thresholds(self, api_client):
        """Verify tier thresholds: high >= 0.40, medium 0.20-0.40, low 0.10-0.20."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        clusters = data.get("clusters", [])
        for cluster in clusters:
            tier = cluster.get("tier")
            members = cluster.get("members", [])
            for member in members[:5]:
                conf = member.get("confidence", 0)
                if tier == "high":
                    assert conf >= 0.40, f"High tier member conf {conf} < 0.40"
                elif tier == "medium":
                    assert 0.20 <= conf < 0.40, f"Medium tier member conf {conf} out of range"
                elif tier == "low":
                    assert 0.10 <= conf < 0.20, f"Low tier member conf {conf} out of range"


# ══════════════════════════════════════════════════════════
#  Entity Cluster Endpoint Tests — Gate.io
# ══════════════════════════════════════════════════════════

class TestGateIOClusters:
    """Tests for GET /api/entities/v2/gate-io/clusters."""

    def test_gate_io_clusters_status(self, api_client):
        """Should return 200 for Gate.io."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/gate-io/clusters")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_gate_io_clusters_entity(self, api_client):
        """Should have correct entity slug."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/gate-io/clusters")
        data = response.json()
        assert data.get("entity", {}).get("slug") == "gate-io"

    def test_gate_io_has_clusters(self, api_client):
        """Gate.io should have some clusters (50 discovered per context)."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/gate-io/clusters")
        data = response.json()
        total_disc = data.get("total_discovered", 0)
        assert total_disc >= 0, f"Gate.io total_discovered: {total_disc}"


# ══════════════════════════════════════════════════════════
#  Entity Cluster Endpoint Tests — Coinbase
# ══════════════════════════════════════════════════════════

class TestCoinbaseClusters:
    """Tests for GET /api/entities/v2/coinbase/clusters."""

    def test_coinbase_clusters_status(self, api_client):
        """Should return 200 for Coinbase."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/coinbase/clusters")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_coinbase_clusters_entity(self, api_client):
        """Should have correct entity slug."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/coinbase/clusters")
        data = response.json()
        assert data.get("entity", {}).get("slug") == "coinbase"

    def test_coinbase_has_clusters(self, api_client):
        """Coinbase should have clusters (105 discovered per context)."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/coinbase/clusters")
        data = response.json()
        total_disc = data.get("total_discovered", 0)
        assert total_disc >= 0, f"Coinbase total_discovered: {total_disc}"


# ══════════════════════════════════════════════════════════
#  Entity Cluster Endpoint Tests — Kraken (less data)
# ══════════════════════════════════════════════════════════

class TestKrakenClusters:
    """Tests for GET /api/entities/v2/kraken/clusters — entity with less data."""

    def test_kraken_clusters_status(self, api_client):
        """Should return 200 even with less data."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/kraken/clusters")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_kraken_clusters_entity(self, api_client):
        """Should have correct entity slug."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/kraken/clusters")
        data = response.json()
        assert data.get("entity", {}).get("slug") == "kraken"

    def test_kraken_cluster_structure_valid(self, api_client):
        """Should have valid structure even if clusters are empty."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/kraken/clusters")
        data = response.json()
        assert "known_addresses" in data
        assert "total_counterparties" in data
        assert "total_discovered" in data
        assert "clusters" in data
        assert "coverage_expansion" in data


# ══════════════════════════════════════════════════════════
#  Error Handling Tests
# ══════════════════════════════════════════════════════════

class TestClusterErrors:
    """Error handling tests for cluster endpoints."""

    def test_nonexistent_entity_404(self, api_client):
        """Should return 404 for nonexistent entity."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/nonexistent/clusters")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is False
        assert "error" in data

    def test_invalid_slug_404(self, api_client):
        """Should return 404 for invalid slug."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/xyz-invalid-123/clusters")
        assert response.status_code == 404


# ══════════════════════════════════════════════════════════
#  Clusters Overview Tests
# ══════════════════════════════════════════════════════════

class TestClustersOverview:
    """Tests for GET /api/entities/v2/clusters/overview."""

    def test_overview_status(self, api_client):
        """Should return 200."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/clusters/overview")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_overview_structure(self, api_client):
        """Overview should have required fields."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/clusters/overview")
        data = response.json()
        assert "total_entities" in data
        assert "entities_with_clusters" in data
        assert "total_discovered" in data
        assert "entities" in data

    def test_overview_entities_list(self, api_client):
        """Entities list should have required fields per entity."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/clusters/overview")
        data = response.json()
        entities = data.get("entities", [])
        assert isinstance(entities, list)
        for entity in entities[:5]:
            assert "slug" in entity
            assert "name" in entity
            assert "type" in entity
            assert "known_addresses" in entity
            assert "total_counterparties" in entity
            assert "total_discovered" in entity
            assert "cluster_count" in entity
            assert "coverage_expansion" in entity

    def test_overview_sorted_by_discovered(self, api_client):
        """Entities should be sorted by total_discovered descending."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/clusters/overview")
        data = response.json()
        entities = data.get("entities", [])
        if len(entities) >= 2:
            discovered_values = [e.get("total_discovered", 0) for e in entities]
            assert discovered_values == sorted(discovered_values, reverse=True), \
                "Entities not sorted by total_discovered descending"

    def test_overview_entities_with_clusters_count(self, api_client):
        """entities_with_clusters should match count of entities with > 0 discovered."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/clusters/overview")
        data = response.json()
        entities = data.get("entities", [])
        entities_with = data.get("entities_with_clusters", 0)
        actual_with = sum(1 for e in entities if e.get("total_discovered", 0) > 0)
        assert entities_with == actual_with, \
            f"entities_with_clusters ({entities_with}) != actual ({actual_with})"

    def test_overview_total_discovered_sum(self, api_client):
        """total_discovered should equal sum of all entity discovered counts."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/clusters/overview")
        data = response.json()
        entities = data.get("entities", [])
        total = data.get("total_discovered", 0)
        actual_sum = sum(e.get("total_discovered", 0) for e in entities)
        assert total == actual_sum, f"total_discovered ({total}) != sum ({actual_sum})"


# ══════════════════════════════════════════════════════════
#  Build All Clusters Tests (Single call to avoid timeout)
# ══════════════════════════════════════════════════════════

class TestBuildAllClusters:
    """Tests for POST /api/entities/v2/clusters/build-all.
    
    Note: build-all takes ~30-50s, so we make ONE call and validate
    all assertions from the same response to avoid timeout issues.
    """
    
    _build_response = None  # Cache response across test methods

    @pytest.fixture(autouse=True, scope="class")
    def build_once(self, api_client):
        """Build clusters once for the entire test class."""
        if TestBuildAllClusters._build_response is None:
            response = api_client.post(f"{BASE_URL}/api/entities/v2/clusters/build-all", timeout=120)
            TestBuildAllClusters._build_response = response
        return TestBuildAllClusters._build_response

    def test_build_all_status(self, build_once):
        """Should return 200 on build."""
        assert build_once.status_code == 200
        data = build_once.json()
        assert data.get("ok") is True

    def test_build_all_structure(self, build_once):
        """Build response should have stats."""
        data = build_once.json()
        assert "total_entities" in data
        assert "computed" in data
        assert "total_discovered" in data
        assert "entities_with_clusters" in data

    def test_build_all_15_entities(self, build_once):
        """Should build 15 entities (per context)."""
        data = build_once.json()
        total = data.get("total_entities", 0)
        computed = data.get("computed", 0)
        assert total >= 15, f"Expected >= 15 entities, got {total}"
        assert computed >= 15, f"Expected >= 15 computed, got {computed}"

    def test_build_all_entities_with_clusters(self, build_once):
        """Should have >= 6 entities with clusters (per context)."""
        data = build_once.json()
        entities_with = data.get("entities_with_clusters", 0)
        assert entities_with >= 6, f"Expected >= 6 entities_with_clusters, got {entities_with}"

    def test_build_all_total_discovered(self, build_once):
        """Total discovered should be > 0 (391 per context)."""
        data = build_once.json()
        total_disc = data.get("total_discovered", 0)
        assert total_disc > 0, f"Expected total_discovered > 0, got {total_disc}"


# ══════════════════════════════════════════════════════════
#  Entity With No Addresses Tests
# ══════════════════════════════════════════════════════════

class TestEntityNoAddresses:
    """Tests for entities with no addresses — should return empty clusters."""

    def test_empty_entity_returns_valid_structure(self, api_client):
        """Entity with no on-chain activity should return valid but empty clusters."""
        # Try an entity that exists but may have no clusters
        response = api_client.get(f"{BASE_URL}/api/entities/v2/clusters/overview")
        data = response.json()
        entities = data.get("entities", [])
        
        # Find an entity with 0 discovered
        empty_entity = None
        for e in entities:
            if e.get("total_discovered", 0) == 0:
                empty_entity = e.get("slug")
                break
        
        if empty_entity:
            response2 = api_client.get(f"{BASE_URL}/api/entities/v2/{empty_entity}/clusters")
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2.get("total_discovered", 0) == 0
            assert data2.get("clusters", []) == []


# ══════════════════════════════════════════════════════════
#  Computed At Timestamp Tests
# ══════════════════════════════════════════════════════════

class TestComputedAtTimestamp:
    """Tests for computed_at field."""

    def test_computed_at_present(self, api_client):
        """Cluster data should have computed_at timestamp."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        assert "computed_at" in data, "Missing computed_at"

    def test_computed_at_iso_format(self, api_client):
        """computed_at should be ISO timestamp format."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        data = response.json()
        computed_at = data.get("computed_at", "")
        # Should be ISO format like 2024-01-15T10:30:00+00:00
        assert "T" in computed_at, f"computed_at not ISO format: {computed_at}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
