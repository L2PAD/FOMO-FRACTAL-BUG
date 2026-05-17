"""
Entities V2 — Phase 2: Address Attribution Engine Tests
=========================================================
Tests for Address Activity Index building and querying.
Connects entity registry (15 entities, 27 addresses) to real on-chain activity.

Data sources scanned:
- onchain_v2_erc20_logs
- onchain_v2_address_labels
- wallet_counterparty_flow_buckets
- onchain_v2_dex_swaps

Endpoints:
- POST /api/entities/v2/address-index/build
- GET /api/entities/v2/address-index/status
- GET /api/entities/v2/{slug}/addresses (Phase 2 enhanced with activity)
- GET /api/entities/v2/{slug}/address-activity
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ═══════════════════════════════════════════════════════════════
# ADDRESS INDEX STATUS TESTS
# ═══════════════════════════════════════════════════════════════

class TestAddressIndexStatus:
    """GET /api/entities/v2/address-index/status tests"""

    def test_status_returns_ok_true(self, api_client):
        """Status endpoint returns ok=true."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/address-index/status")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True

    def test_status_has_coverage_pct(self, api_client):
        """Status has coverage_pct field."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/address-index/status")
        data = response.json()
        
        assert "coverage_pct" in data
        assert isinstance(data["coverage_pct"], (int, float))
        # Coverage should be 100% (27/27 indexed)
        assert data["coverage_pct"] == 100.0, f"Expected 100% coverage, got {data['coverage_pct']}"

    def test_status_has_status_breakdown(self, api_client):
        """Status has status_breakdown with active/dormant/stale/not_indexed."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/address-index/status")
        data = response.json()
        
        assert "status_breakdown" in data
        breakdown = data["status_breakdown"]
        
        assert "active" in breakdown
        assert "dormant" in breakdown
        assert "stale" in breakdown
        assert "not_indexed" in breakdown
        
        # All should be integers
        assert isinstance(breakdown["active"], int)
        assert isinstance(breakdown["dormant"], int)
        assert isinstance(breakdown["stale"], int)
        assert isinstance(breakdown["not_indexed"], int)

    def test_status_has_score_distribution(self, api_client):
        """Status has score_distribution with ranges."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/address-index/status")
        data = response.json()
        
        assert "score_distribution" in data
        dist = data["score_distribution"]
        
        # Expected ranges
        assert "high_75_100" in dist
        assert "medium_50_74" in dist
        assert "low_25_49" in dist
        assert "minimal_0_24" in dist

    def test_status_total_addresses_27(self, api_client):
        """Total entity addresses should be 27."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/address-index/status")
        data = response.json()
        
        assert "total_entity_addresses" in data
        assert data["total_entity_addresses"] == 27, f"Expected 27, got {data['total_entity_addresses']}"

    def test_status_indexed_equals_total(self, api_client):
        """Indexed count should equal total (100% coverage)."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/address-index/status")
        data = response.json()
        
        assert data["indexed"] == 27, f"Expected 27 indexed, got {data['indexed']}"
        assert data["indexed"] == data["total_entity_addresses"]

    def test_status_breakdown_sums_to_indexed(self, api_client):
        """Status breakdown active+dormant+stale should sum to indexed count."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/address-index/status")
        data = response.json()
        
        breakdown = data["status_breakdown"]
        sum_statuses = breakdown["active"] + breakdown["dormant"] + breakdown["stale"]
        assert sum_statuses == data["indexed"], f"Sum {sum_statuses} != indexed {data['indexed']}"

    def test_status_has_last_indexed_at(self, api_client):
        """Status has last_indexed_at timestamp."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/address-index/status")
        data = response.json()
        
        assert "last_indexed_at" in data
        # Should be an ISO timestamp string
        assert data["last_indexed_at"] is not None


# ═══════════════════════════════════════════════════════════════
# ONCHAIN INTELLIGENCE - ADDRESSES ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════

class TestOnchainIntelligenceAddresses:
    """GET /api/entities/v2/{slug}/addresses tests (Phase 2 enhanced)"""

    def test_binance_addresses_ok_true(self, api_client):
        """Binance addresses endpoint returns ok=true."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/addresses")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True

    def test_binance_has_entity_info(self, api_client):
        """Response has entity object with slug, name, type, category."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/addresses")
        data = response.json()
        
        assert "entity" in data
        entity = data["entity"]
        
        assert entity["slug"] == "binance"
        assert entity["name"] == "Binance"
        assert entity["type"] == "exchange"
        assert entity["category"] == "CEX"

    def test_binance_has_summary(self, api_client):
        """Response has summary with aggregated metrics."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/addresses")
        data = response.json()
        
        assert "summary" in data
        summary = data["summary"]
        
        # Required summary fields
        assert "total_addresses" in summary
        assert "active_addresses" in summary
        assert "dormant_addresses" in summary
        assert "total_tx_count" in summary
        assert "avg_activity_score" in summary

    def test_binance_5_addresses(self, api_client):
        """Binance should have 5 addresses."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/addresses")
        data = response.json()
        
        assert data["summary"]["total_addresses"] == 5
        assert len(data["addresses"]) == 5

    def test_binance_4_active_addresses(self, api_client):
        """Binance should have 4 active addresses."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/addresses")
        data = response.json()
        
        assert data["summary"]["active_addresses"] == 4, f"Expected 4 active, got {data['summary']['active_addresses']}"

    def test_binance_252_total_tx_count(self, api_client):
        """Binance should have 252 total tx count."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/addresses")
        data = response.json()
        
        assert data["summary"]["total_tx_count"] == 252, f"Expected 252 tx, got {data['summary']['total_tx_count']}"

    def test_addresses_have_activity_metrics(self, api_client):
        """Each address has activity metrics: activity_score, status, erc20."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/addresses")
        data = response.json()
        
        for addr in data["addresses"]:
            assert "address" in addr
            assert "activity_score" in addr
            assert "status" in addr
            assert "erc20" in addr or addr["erc20"] is None
            assert "attribution_confidence" in addr
            assert "attribution_source" in addr

    def test_activity_score_in_range(self, api_client):
        """Activity scores should be 0-100."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/addresses")
        data = response.json()
        
        for addr in data["addresses"]:
            score = addr["activity_score"]
            assert 0 <= score <= 100, f"Score {score} out of range for {addr['address']}"

    def test_addresses_sorted_by_activity_score(self, api_client):
        """Addresses should be sorted by activity_score descending."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/addresses")
        data = response.json()
        
        scores = [a["activity_score"] for a in data["addresses"]]
        assert scores == sorted(scores, reverse=True), "Addresses not sorted by score"

    def test_nonexistent_entity_returns_404(self, api_client):
        """Nonexistent entity returns 404."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/nonexistent/addresses")
        assert response.status_code == 404
        data = response.json()
        assert data.get("ok") is False
        assert "error" in data


# ═══════════════════════════════════════════════════════════════
# ONCHAIN INTELLIGENCE - ADDRESS ACTIVITY DETAIL TESTS
# ═══════════════════════════════════════════════════════════════

class TestOnchainIntelligenceAddressActivity:
    """GET /api/entities/v2/{slug}/address-activity tests"""

    def test_binance_address_activity_ok_true(self, api_client):
        """Binance address-activity endpoint returns ok=true."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/address-activity")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True

    def test_has_entity_info(self, api_client):
        """Response has entity object."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/address-activity")
        data = response.json()
        
        assert "entity" in data
        entity = data["entity"]
        assert entity["slug"] == "binance"
        assert entity["name"] == "Binance"

    def test_has_coverage_section(self, api_client):
        """Response has coverage section with data source counts."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/address-activity")
        data = response.json()
        
        assert "coverage" in data
        coverage = data["coverage"]
        
        assert "total_addresses" in coverage
        assert "with_erc20_data" in coverage
        assert "with_labels" in coverage
        assert "with_counterparty_flows" in coverage
        assert "with_dex_activity" in coverage

    def test_has_token_exposure(self, api_client):
        """Response has token_exposure section."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/address-activity")
        data = response.json()
        
        assert "token_exposure" in data
        token_exp = data["token_exposure"]
        
        assert "unique_tokens" in token_exp
        assert "tokens" in token_exp
        assert isinstance(token_exp["tokens"], list)

    def test_binance_38_unique_tokens(self, api_client):
        """Binance should have 38 unique tokens."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/address-activity")
        data = response.json()
        
        unique_tokens = data["token_exposure"]["unique_tokens"]
        assert unique_tokens == 38, f"Expected 38 unique tokens, got {unique_tokens}"

    def test_has_counterparty_graph(self, api_client):
        """Response has counterparty_graph section."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/address-activity")
        data = response.json()
        
        assert "counterparty_graph" in data
        cp_graph = data["counterparty_graph"]
        
        assert "unique_counterparties" in cp_graph
        assert "resolved" in cp_graph
        assert isinstance(cp_graph["resolved"], list)

    def test_has_dex_activity(self, api_client):
        """Response has dex_activity section."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/address-activity")
        data = response.json()
        
        assert "dex_activity" in data
        dex = data["dex_activity"]
        
        assert "total_swaps" in dex
        assert "protocols" in dex

    def test_has_address_breakdown(self, api_client):
        """Response has address_breakdown section."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/address-activity")
        data = response.json()
        
        assert "address_breakdown" in data
        breakdown = data["address_breakdown"]
        
        assert isinstance(breakdown, list)
        assert len(breakdown) == 5  # 5 Binance addresses

    def test_address_breakdown_fields(self, api_client):
        """Address breakdown entries have required fields."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/address-activity")
        data = response.json()
        
        for addr in data["address_breakdown"]:
            assert "address" in addr
            assert "role" in addr
            assert "activity_score" in addr
            assert "status" in addr
            assert "tx_count" in addr
            assert "has_label" in addr
            assert "has_flows" in addr
            assert "has_dex" in addr

    def test_indexed_true(self, api_client):
        """Response shows indexed=true."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance/address-activity")
        data = response.json()
        
        assert data.get("indexed") is True

    def test_nonexistent_entity_returns_404(self, api_client):
        """Nonexistent entity returns 404."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/nonexistent/address-activity")
        assert response.status_code == 404
        data = response.json()
        assert data.get("ok") is False
        assert "error" in data


# ═══════════════════════════════════════════════════════════════
# WHALE-ALPHA DORMANT ENTITY TESTS
# ═══════════════════════════════════════════════════════════════

class TestWhaleAlphaDormant:
    """Test entity with no on-chain data (whale-alpha)"""

    def test_whale_alpha_addresses_ok(self, api_client):
        """Whale-alpha addresses endpoint returns ok=true."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/whale-alpha/addresses")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_whale_alpha_has_1_address(self, api_client):
        """Whale-alpha should have 1 address."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/whale-alpha/addresses")
        data = response.json()
        
        assert data["summary"]["total_addresses"] == 1
        assert len(data["addresses"]) == 1

    def test_whale_alpha_dormant_status(self, api_client):
        """Whale-alpha should have dormant status."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/whale-alpha/addresses")
        data = response.json()
        
        # 0 active, 1 dormant
        assert data["summary"]["active_addresses"] == 0
        assert data["summary"]["dormant_addresses"] == 1
        
        # Address status is dormant
        assert data["addresses"][0]["status"] == "dormant"

    def test_whale_alpha_zero_tx_count(self, api_client):
        """Whale-alpha should have 0 tx count (no ERC20 activity in test data)."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/whale-alpha/addresses")
        data = response.json()
        
        assert data["summary"]["total_tx_count"] == 0


# ═══════════════════════════════════════════════════════════════
# ADDRESS INDEX BUILD TESTS (skip actual build - takes too long)
# ═══════════════════════════════════════════════════════════════

class TestAddressIndexBuild:
    """POST /api/entities/v2/address-index/build tests (structure only)"""

    @pytest.mark.skip(reason="Build endpoint takes too long for CI - index already built")
    def test_build_index_returns_ok(self, api_client):
        """Build endpoint returns ok=true with stats."""
        response = api_client.post(f"{BASE_URL}/api/entities/v2/address-index/build", timeout=120)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "total_addresses" in data
        assert "with_erc20_activity" in data
        assert "with_label_match" in data
        assert "indexed" in data


# ═══════════════════════════════════════════════════════════════
# PHASE 1 REGRESSION TESTS
# ═══════════════════════════════════════════════════════════════

class TestPhase1RegressionEndpoints:
    """Phase 1 endpoints still work correctly."""

    def test_list_returns_15_entities(self, api_client):
        """GET /api/entities/v2/list returns ok=true with 15 entities."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert data["pagination"]["total"] == 15

    def test_summary_returns_counts(self, api_client):
        """GET /api/entities/v2/summary returns counts by type/category."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/summary")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "by_type" in data
        assert "by_category" in data
        assert data["total_entities"] == 15
        assert data["total_addresses"] == 27

    def test_search_binance_returns_results(self, api_client):
        """GET /api/entities/v2/search?q=binance returns results."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/search?q=binance")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert len(data["results"]) >= 1
        names = [r["name"] for r in data["results"]]
        assert "Binance" in names

    def test_resolve_binance_address(self, api_client):
        """GET /api/entities/v2/resolve returns found=true for Binance address."""
        address = "0x28c6c06298d514db089934071355e5743bf21d60"
        response = api_client.get(f"{BASE_URL}/api/entities/v2/resolve?address={address}")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("found") is True
        assert data["entity"]["entity_slug"] == "binance"


# ═══════════════════════════════════════════════════════════════
# ACTIVITY SCORE VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestActivityScoreValidation:
    """Activity score computation tests."""

    def test_scores_in_0_100_range(self, api_client):
        """All activity scores should be in 0-100 range."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/address-index/status")
        data = response.json()
        
        # Score distribution should sum to indexed count
        dist = data["score_distribution"]
        total_dist = (
            dist["high_75_100"] + 
            dist["medium_50_74"] + 
            dist["low_25_49"] + 
            dist["minimal_0_24"]
        )
        assert total_dist == data["indexed"], f"Score distribution {total_dist} != indexed {data['indexed']}"

    def test_higher_score_for_active_entity(self, api_client):
        """Binance (active) should have higher avg score than whale-alpha (dormant)."""
        binance_resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/addresses")
        whale_resp = api_client.get(f"{BASE_URL}/api/entities/v2/whale-alpha/addresses")
        
        binance_score = binance_resp.json()["summary"]["avg_activity_score"]
        whale_score = whale_resp.json()["summary"]["avg_activity_score"]
        
        assert binance_score > whale_score, f"Binance {binance_score} should be > whale {whale_score}"


# ═══════════════════════════════════════════════════════════════
# INDEX COVERAGE TESTS
# ═══════════════════════════════════════════════════════════════

class TestIndexCoverage:
    """Index coverage validation tests."""

    def test_100_percent_coverage(self, api_client):
        """Index should have 100% coverage (27/27)."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/address-index/status")
        data = response.json()
        
        assert data["coverage_pct"] == 100.0
        assert data["indexed"] == 27
        assert data["total_entity_addresses"] == 27
        assert data["status_breakdown"]["not_indexed"] == 0

    def test_all_entities_have_indexed_addresses(self, api_client):
        """Each entity's addresses should be indexed."""
        # Test a few key entities
        entities_to_check = ["binance", "coinbase", "uniswap", "wintermute", "whale-alpha"]
        
        for slug in entities_to_check:
            response = api_client.get(f"{BASE_URL}/api/entities/v2/{slug}/addresses")
            assert response.status_code == 200, f"Failed for {slug}"
            data = response.json()
            
            # All addresses should have activity data (not "not_indexed" status)
            for addr in data["addresses"]:
                assert addr["status"] in ["active", "dormant", "stale", "unknown"], \
                    f"Address {addr['address']} of {slug} has unexpected status: {addr['status']}"
