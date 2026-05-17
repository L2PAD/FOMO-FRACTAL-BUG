"""
Entities V2 — Foundation Module Tests
======================================
Tests for new entity registry with proper types, attribution, and real addresses.
15 entities (6 exchanges, 3 funds, 2 market makers, 3 protocols, 1 whale) with 27 addresses.

Endpoints:
- POST /api/entities/v2/seed
- GET /api/entities/v2/list
- GET /api/entities/v2/{slug}
- GET /api/entities/v2/search
- GET /api/entities/v2/resolve
- GET /api/entities/v2/summary
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


@pytest.fixture(scope="session", autouse=True)
def seed_entities(api_client):
    """Seed entities before running tests. Must run first."""
    response = api_client.post(f"{BASE_URL}/api/entities/v2/seed")
    assert response.status_code == 200, f"Seed failed: {response.text}"
    data = response.json()
    assert data.get("ok") is True
    print(f"Seed result: seeded={data.get('seeded')}, updated={data.get('updated')}, total={data.get('total_entities')}")
    return data


# ═══════════════════════════════════════════════════════════════
# SEED ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════

class TestSeedEndpoint:
    """POST /api/entities/v2/seed tests"""

    def test_seed_returns_ok_true(self, api_client):
        """Seed endpoint returns ok=true with counts."""
        response = api_client.post(f"{BASE_URL}/api/entities/v2/seed")
        assert response.status_code == 200
        data = response.json()
        
        # ok=true
        assert data.get("ok") is True
        
        # Has required count fields
        assert "seeded" in data
        assert "updated" in data
        assert "total_entities" in data
        assert "total_addresses" in data
        
        # Counts are integers
        assert isinstance(data["seeded"], int)
        assert isinstance(data["updated"], int)
        assert isinstance(data["total_entities"], int)
        assert isinstance(data["total_addresses"], int)
        
        # Expected totals from seed.py
        assert data["total_entities"] == 15, f"Expected 15 entities, got {data['total_entities']}"
        assert data["total_addresses"] == 27, f"Expected 27 addresses, got {data['total_addresses']}"

    def test_seed_is_idempotent(self, api_client):
        """Calling seed multiple times doesn't create duplicates."""
        # Call seed twice
        response1 = api_client.post(f"{BASE_URL}/api/entities/v2/seed")
        response2 = api_client.post(f"{BASE_URL}/api/entities/v2/seed")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Second call should have 0 seeded (all updates)
        data2 = response2.json()
        assert data2["seeded"] == 0, "Idempotent seed should not create new entities"
        assert data2["updated"] == 15, "All entities should be updated"


# ═══════════════════════════════════════════════════════════════
# LIST ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════

class TestListEndpoint:
    """GET /api/entities/v2/list tests"""

    def test_list_returns_15_entities(self, api_client):
        """List returns all 15 entities with pagination."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "entities" in data
        assert "pagination" in data
        
        # Should have 15 entities total
        assert data["pagination"]["total"] == 15
        assert len(data["entities"]) == 15

    def test_entity_has_required_fields(self, api_client):
        """Each entity has name, slug, type, category, confidence, addresses_count, primary_addresses."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list")
        data = response.json()
        
        for entity in data["entities"]:
            assert "name" in entity, f"Missing name: {entity}"
            assert "slug" in entity, f"Missing slug: {entity}"
            assert "type" in entity, f"Missing type: {entity}"
            assert "category" in entity, f"Missing category: {entity}"
            assert "confidence" in entity, f"Missing confidence: {entity}"
            assert "addresses_count" in entity, f"Missing addresses_count: {entity}"
            assert "primary_addresses" in entity, f"Missing primary_addresses: {entity}"

    def test_entity_types_valid(self, api_client):
        """Entity types are valid (exchange, fund, market_maker, protocol, whale)."""
        valid_types = ["exchange", "fund", "market_maker", "protocol", "whale", "dao", "bridge", "unknown_cluster"]
        
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list")
        data = response.json()
        
        for entity in data["entities"]:
            assert entity["type"] in valid_types, f"Invalid type {entity['type']} for {entity['name']}"

    def test_entity_categories_valid(self, api_client):
        """Entity categories are valid (CEX, VC, MM, DEX, DeFi, Institution, Unknown)."""
        valid_categories = ["CEX", "DEX", "VC", "MM", "Institution", "DeFi", "Foundation", "Treasury", "Bridge", "Unknown"]
        
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list")
        data = response.json()
        
        for entity in data["entities"]:
            assert entity["category"] in valid_categories, f"Invalid category {entity['category']} for {entity['name']}"

    def test_list_filter_by_type_exchange(self, api_client):
        """Filter by type=exchange returns 6 exchanges."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list?type=exchange")
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["total"] == 6, f"Expected 6 exchanges, got {data['pagination']['total']}"
        for entity in data["entities"]:
            assert entity["type"] == "exchange"

    def test_list_filter_by_type_fund(self, api_client):
        """Filter by type=fund returns 3 funds."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list?type=fund")
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["total"] == 3, f"Expected 3 funds, got {data['pagination']['total']}"
        for entity in data["entities"]:
            assert entity["type"] == "fund"

    def test_list_filter_by_type_market_maker(self, api_client):
        """Filter by type=market_maker returns 2 market makers."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list?type=market_maker")
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["total"] == 2, f"Expected 2 market makers, got {data['pagination']['total']}"
        for entity in data["entities"]:
            assert entity["type"] == "market_maker"

    def test_list_filter_by_type_protocol(self, api_client):
        """Filter by type=protocol returns 3 protocols."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list?type=protocol")
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["total"] == 3, f"Expected 3 protocols, got {data['pagination']['total']}"
        for entity in data["entities"]:
            assert entity["type"] == "protocol"

    def test_list_filter_by_type_whale(self, api_client):
        """Filter by type=whale returns 1 whale."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list?type=whale")
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["total"] == 1, f"Expected 1 whale, got {data['pagination']['total']}"
        for entity in data["entities"]:
            assert entity["type"] == "whale"

    def test_list_filter_by_category_cex(self, api_client):
        """Filter by category=CEX returns 6 CEX exchanges."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list?category=CEX")
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["total"] == 6, f"Expected 6 CEX, got {data['pagination']['total']}"
        for entity in data["entities"]:
            assert entity["category"] == "CEX"

    def test_list_filter_by_category_vc(self, api_client):
        """Filter by category=VC returns 2 VC funds."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list?category=VC")
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["total"] == 2, f"Expected 2 VC, got {data['pagination']['total']}"
        for entity in data["entities"]:
            assert entity["category"] == "VC"

    def test_list_filter_by_category_mm(self, api_client):
        """Filter by category=MM returns 2 market makers."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list?category=MM")
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["total"] == 2, f"Expected 2 MM, got {data['pagination']['total']}"
        for entity in data["entities"]:
            assert entity["category"] == "MM"

    def test_list_search_jump(self, api_client):
        """Search for 'jump' returns Jump Trading."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list?search=jump")
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["total"] >= 1, "Expected at least 1 result for 'jump'"
        # Find Jump Trading
        names = [e["name"] for e in data["entities"]]
        assert "Jump Trading" in names, f"Expected 'Jump Trading' in results: {names}"

    def test_pagination_structure(self, api_client):
        """Pagination has total, page, limit, total_pages."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/list?page=1&limit=5")
        assert response.status_code == 200
        data = response.json()
        
        pagination = data["pagination"]
        assert "total" in pagination
        assert "page" in pagination
        assert "limit" in pagination
        assert "total_pages" in pagination
        
        assert pagination["page"] == 1
        assert pagination["limit"] == 5
        assert pagination["total_pages"] == 3  # ceil(15/5)


# ═══════════════════════════════════════════════════════════════
# ENTITY DETAIL TESTS
# ═══════════════════════════════════════════════════════════════

class TestEntityDetailEndpoint:
    """GET /api/entities/v2/{slug} tests"""

    def test_binance_has_5_addresses(self, api_client):
        """Binance entity has 5 addresses."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        entity = data["entity"]
        
        assert entity["name"] == "Binance"
        assert entity["addresses_count"] == 5, f"Expected 5 addresses, got {entity['addresses_count']}"
        assert len(entity["addresses"]) == 5

    def test_binance_has_attribution_summary(self, api_client):
        """Binance entity has attribution_summary."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance")
        data = response.json()
        entity = data["entity"]
        
        assert "attribution_summary" in entity
        summary = entity["attribution_summary"]
        
        assert "total_addresses" in summary
        assert "sources" in summary
        assert "avg_confidence" in summary
        assert "chains" in summary
        
        assert summary["total_addresses"] == 5
        assert "ethereum" in summary["chains"]

    def test_binance_addresses_confidence_and_source(self, api_client):
        """Binance addresses have confidence >= 90, source in (verified, tagged)."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance")
        data = response.json()
        entity = data["entity"]
        
        valid_sources = ["verified", "tagged"]
        for addr in entity["addresses"]:
            assert addr["confidence"] >= 90, f"Address {addr['address']} has low confidence: {addr['confidence']}"
            assert addr["source"] in valid_sources, f"Address {addr['address']} has invalid source: {addr['source']}"

    def test_address_has_required_fields(self, api_client):
        """Addresses have: address, chain, role, confidence, source, entity_slug."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/binance")
        data = response.json()
        entity = data["entity"]
        
        for addr in entity["addresses"]:
            assert "address" in addr, f"Missing address field: {addr}"
            assert "chain" in addr, f"Missing chain field: {addr}"
            assert "role" in addr, f"Missing role field: {addr}"
            assert "confidence" in addr, f"Missing confidence field: {addr}"
            assert "source" in addr, f"Missing source field: {addr}"
            assert "entity_slug" in addr, f"Missing entity_slug field: {addr}"

    def test_nonexistent_entity_returns_404(self, api_client):
        """Nonexistent entity returns 404."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert data.get("ok") is False
        assert "error" in data


# ═══════════════════════════════════════════════════════════════
# RESOLVE ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════

class TestResolveEndpoint:
    """GET /api/entities/v2/resolve tests"""

    def test_resolve_binance_address(self, api_client):
        """Resolve Binance hot wallet address to Binance."""
        address = "0x28c6c06298d514db089934071355e5743bf21d60"
        response = api_client.get(f"{BASE_URL}/api/entities/v2/resolve?address={address}")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("found") is True
        
        entity = data["entity"]
        assert entity["entity_slug"] == "binance"
        assert entity["entity_name"] == "Binance"

    def test_resolve_unknown_address(self, api_client):
        """Resolve unknown address returns found=false."""
        address = "0x0000000000000000000000000000000000000000"
        response = api_client.get(f"{BASE_URL}/api/entities/v2/resolve?address={address}")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("found") is False
        assert data.get("entity") is None

    def test_resolve_case_insensitive(self, api_client):
        """Resolve is case-insensitive for addresses."""
        address_lower = "0x28c6c06298d514db089934071355e5743bf21d60"
        address_upper = "0x28C6C06298D514DB089934071355E5743BF21D60"
        
        response1 = api_client.get(f"{BASE_URL}/api/entities/v2/resolve?address={address_lower}")
        response2 = api_client.get(f"{BASE_URL}/api/entities/v2/resolve?address={address_upper}")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        assert data1.get("found") is True
        assert data2.get("found") is True
        assert data1["entity"]["entity_slug"] == data2["entity"]["entity_slug"]


# ═══════════════════════════════════════════════════════════════
# SEARCH ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════

class TestSearchEndpoint:
    """GET /api/entities/v2/search tests"""

    def test_search_wintermute(self, api_client):
        """Search for 'winter' returns Wintermute."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/search?q=winter")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "results" in data
        
        names = [r["name"] for r in data["results"]]
        assert "Wintermute" in names, f"Expected 'Wintermute' in results: {names}"

    def test_search_uniswap(self, api_client):
        """Search for 'uni' returns Uniswap Protocol."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/search?q=uni")
        assert response.status_code == 200
        data = response.json()
        
        names = [r["name"] for r in data["results"]]
        assert "Uniswap Protocol" in names, f"Expected 'Uniswap Protocol' in results: {names}"

    def test_search_empty_query(self, api_client):
        """Empty search query returns empty results."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/search?q=")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        # Empty query should return empty or all results
        assert "results" in data

    def test_search_result_fields(self, api_client):
        """Search results have name, slug, type, category, confidence."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/search?q=binance")
        assert response.status_code == 200
        data = response.json()
        
        for result in data["results"]:
            assert "name" in result
            assert "slug" in result
            assert "type" in result
            assert "category" in result
            assert "confidence" in result


# ═══════════════════════════════════════════════════════════════
# SUMMARY ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════

class TestSummaryEndpoint:
    """GET /api/entities/v2/summary tests"""

    def test_summary_has_by_type_and_by_category(self, api_client):
        """Summary has by_type and by_category breakdowns."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/summary")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "by_type" in data
        assert "by_category" in data
        assert "total_entities" in data
        assert "total_addresses" in data

    def test_summary_by_type_counts(self, api_client):
        """Summary by_type has correct counts."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/summary")
        data = response.json()
        
        by_type = data["by_type"]
        assert by_type.get("exchange") == 6, f"Expected 6 exchanges, got {by_type.get('exchange')}"
        assert by_type.get("fund") == 3, f"Expected 3 funds, got {by_type.get('fund')}"
        assert by_type.get("market_maker") == 2, f"Expected 2 market makers, got {by_type.get('market_maker')}"
        assert by_type.get("protocol") == 3, f"Expected 3 protocols, got {by_type.get('protocol')}"
        assert by_type.get("whale") == 1, f"Expected 1 whale, got {by_type.get('whale')}"

    def test_summary_by_category_counts(self, api_client):
        """Summary by_category has correct counts."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/summary")
        data = response.json()
        
        by_category = data["by_category"]
        assert by_category.get("CEX") == 6, f"Expected 6 CEX, got {by_category.get('CEX')}"
        assert by_category.get("VC") == 2, f"Expected 2 VC, got {by_category.get('VC')}"
        assert by_category.get("MM") == 2, f"Expected 2 MM, got {by_category.get('MM')}"
        assert by_category.get("Institution") == 1, f"Expected 1 Institution, got {by_category.get('Institution')}"
        assert by_category.get("DEX") == 1, f"Expected 1 DEX, got {by_category.get('DEX')}"
        assert by_category.get("DeFi") == 2, f"Expected 2 DeFi, got {by_category.get('DeFi')}"
        assert by_category.get("Unknown") == 1, f"Expected 1 Unknown, got {by_category.get('Unknown')}"

    def test_summary_totals(self, api_client):
        """Summary totals are correct."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/summary")
        data = response.json()
        
        assert data["total_entities"] == 15, f"Expected 15 entities, got {data['total_entities']}"
        assert data["total_addresses"] == 27, f"Expected 27 addresses, got {data['total_addresses']}"


# ═══════════════════════════════════════════════════════════════
# REGRESSION TESTS
# ═══════════════════════════════════════════════════════════════

class TestRegressionEndpoints:
    """Regression tests for existing endpoints."""

    def test_engine_v3_context_still_works(self, api_client):
        """GET /api/engine/v3/context still works (200)."""
        response = api_client.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        assert response.status_code == 200, f"Engine V3 context failed: {response.status_code} {response.text[:200]}"
        data = response.json()
        assert data.get("ok") is True

    def test_cex_context_still_works(self, api_client):
        """GET /api/onchain/cex/context still works (200)."""
        response = api_client.get(f"{BASE_URL}/api/onchain/cex/context", timeout=30)
        assert response.status_code == 200, f"CEX context failed: {response.status_code} {response.text[:200]}"
        data = response.json()
        assert data.get("ok") is True


# ═══════════════════════════════════════════════════════════════
# ADDITIONAL ENTITY VALIDATION
# ═══════════════════════════════════════════════════════════════

class TestEntityValidation:
    """Additional validation tests for specific entities."""

    def test_coinbase_entity(self, api_client):
        """Coinbase entity has 4 addresses."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/coinbase")
        assert response.status_code == 200
        data = response.json()
        entity = data["entity"]
        
        assert entity["name"] == "Coinbase"
        assert entity["type"] == "exchange"
        assert entity["category"] == "CEX"
        assert entity["addresses_count"] == 4

    def test_kraken_entity(self, api_client):
        """Kraken entity has 2 addresses."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/kraken")
        assert response.status_code == 200
        data = response.json()
        entity = data["entity"]
        
        assert entity["name"] == "Kraken"
        assert entity["addresses_count"] == 2

    def test_a16z_entity(self, api_client):
        """a16z entity is a VC fund."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/a16z")
        assert response.status_code == 200
        data = response.json()
        entity = data["entity"]
        
        assert entity["name"] == "a16z Crypto"
        assert entity["type"] == "fund"
        assert entity["category"] == "VC"

    def test_wintermute_entity(self, api_client):
        """Wintermute is a market maker."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/wintermute")
        assert response.status_code == 200
        data = response.json()
        entity = data["entity"]
        
        assert entity["name"] == "Wintermute"
        assert entity["type"] == "market_maker"
        assert entity["category"] == "MM"

    def test_uniswap_entity(self, api_client):
        """Uniswap is a DEX protocol."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/uniswap")
        assert response.status_code == 200
        data = response.json()
        entity = data["entity"]
        
        assert entity["name"] == "Uniswap Protocol"
        assert entity["type"] == "protocol"
        assert entity["category"] == "DEX"

    def test_whale_alpha_entity(self, api_client):
        """Whale alpha cluster exists."""
        response = api_client.get(f"{BASE_URL}/api/entities/v2/whale-alpha")
        assert response.status_code == 200
        data = response.json()
        entity = data["entity"]
        
        assert entity["name"] == "Whale Cluster Alpha"
        assert entity["type"] == "whale"
        assert entity["category"] == "Unknown"
