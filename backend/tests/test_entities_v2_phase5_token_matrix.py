"""
Entities V2 Phase 5: Token Flow Matrix — Comprehensive API Tests
=================================================================
Tests for:
- GET /api/entities/v2/{slug}/token-matrix — Entity token matrix with role classification
- GET /api/entities/v2/token-matrix/overview — Cross-entity token analysis
- POST /api/entities/v2/token-matrix/build-all — Rebuild all matrices

Token role classification:
- liquidity_token: High share, balanced flow (bi-directional)
- accumulation_token: Net inflow dominant
- distribution_token: Net outflow dominant
- neutral_token: No priced volume

Entities with flow data: binance ($4.65M), gate-io ($1.38M), coinbase ($292K), okx ($511)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Valid token roles
VALID_ROLES = {"liquidity_token", "accumulation_token", "distribution_token", "neutral_token"}
# Valid token classes
VALID_CLASSES = {"stablecoin", "major", "altcoin"}


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ==============================================================================
#  Phase 5 — Entity Token Matrix Tests
# ==============================================================================

class TestEntityTokenMatrix:
    """GET /api/entities/v2/{slug}/token-matrix — Entity-specific token matrix"""

    def test_binance_token_matrix_returns_200(self, api_client):
        """Binance should return full token matrix with dominant_asset, tokens, role_breakdown"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data.get("ok") is True

    def test_binance_entity_info_present(self, api_client):
        """Entity block has slug, name, type, category"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        entity = data.get("entity", {})
        assert entity.get("slug") == "binance"
        assert entity.get("name") == "Binance"
        assert entity.get("type") == "exchange"
        assert entity.get("category") == "CEX"

    def test_binance_dominant_asset_structure(self, api_client):
        """dominant_asset has symbol, flow_share, role, volume_usd"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        dominant = data.get("dominant_asset", {})
        assert "symbol" in dominant, "dominant_asset missing symbol"
        assert "flow_share" in dominant, "dominant_asset missing flow_share"
        assert "role" in dominant, "dominant_asset missing role"
        assert "volume_usd" in dominant, "dominant_asset missing volume_usd"
        # Validate types
        assert isinstance(dominant["flow_share"], (int, float))
        assert isinstance(dominant["volume_usd"], (int, float))
        assert dominant["role"] in VALID_ROLES or dominant["role"] is None

    def test_binance_dominant_is_usdt(self, api_client):
        """Binance dominant asset should be USDT (highest volume)"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        dominant = data.get("dominant_asset", {})
        assert dominant.get("symbol") == "USDT", f"Expected USDT, got {dominant.get('symbol')}"
        assert dominant["volume_usd"] > 3_000_000, "USDT volume should be > $3M for Binance"

    def test_binance_role_breakdown_structure(self, api_client):
        """role_breakdown has count, volume_usd, tokens list per role"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        role_breakdown = data.get("role_breakdown", {})
        
        # Should have at least some roles
        assert len(role_breakdown) > 0, "role_breakdown should not be empty for Binance"
        
        for role_name, role_data in role_breakdown.items():
            assert role_name in VALID_ROLES, f"Invalid role: {role_name}"
            assert "count" in role_data, f"Role {role_name} missing count"
            assert "volume_usd" in role_data, f"Role {role_name} missing volume_usd"
            assert "tokens" in role_data, f"Role {role_name} missing tokens list"
            assert isinstance(role_data["count"], int)
            assert isinstance(role_data["volume_usd"], (int, float))
            assert isinstance(role_data["tokens"], list)

    def test_binance_class_breakdown_structure(self, api_client):
        """class_breakdown has stablecoin/major/altcoin with count, volume_usd, share"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        class_breakdown = data.get("class_breakdown", {})
        
        # Should have all 3 class keys
        for cls in ["stablecoin", "major", "altcoin"]:
            assert cls in class_breakdown, f"class_breakdown missing {cls}"
            cls_data = class_breakdown[cls]
            assert "count" in cls_data, f"Class {cls} missing count"
            assert "volume_usd" in cls_data, f"Class {cls} missing volume_usd"
            assert "share" in cls_data, f"Class {cls} missing share"
            assert isinstance(cls_data["count"], int)
            assert isinstance(cls_data["share"], (int, float))
            assert 0 <= cls_data["share"] <= 1, f"Class {cls} share out of range [0,1]"

    def test_binance_stablecoin_dependency_range(self, api_client):
        """stablecoin_dependency should be between 0 and 1"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        stab_dep = data.get("stablecoin_dependency", -1)
        assert 0 <= stab_dep <= 1, f"stablecoin_dependency out of range: {stab_dep}"

    def test_binance_top3_concentration_range(self, api_client):
        """top3_concentration should be between 0 and 1"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        top3 = data.get("top3_concentration", -1)
        assert 0 <= top3 <= 1, f"top3_concentration out of range: {top3}"

    def test_binance_tokens_list_structure(self, api_client):
        """tokens list has all required fields per token entry"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        tokens = data.get("tokens", [])
        
        assert len(tokens) > 0, "tokens list should not be empty for Binance"
        
        required_fields = [
            "token_address", "symbol", "token_class", "role",
            "inflow_usd", "outflow_usd", "net_flow_usd", "flow_volume_usd",
            "flow_share", "transfer_count", "activity_score"
        ]
        
        for idx, token in enumerate(tokens[:5]):  # Check first 5 tokens
            for field in required_fields:
                assert field in token, f"Token {idx} missing field: {field}"

    def test_binance_token_roles_valid(self, api_client):
        """All token roles should be valid role types"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        tokens = data.get("tokens", [])
        
        for token in tokens:
            assert token["role"] in VALID_ROLES, f"Invalid role for {token['symbol']}: {token['role']}"

    def test_binance_token_classes_valid(self, api_client):
        """All token classes should be stablecoin, major, or altcoin"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        tokens = data.get("tokens", [])
        
        for token in tokens:
            assert token["token_class"] in VALID_CLASSES, f"Invalid class for {token['symbol']}: {token['token_class']}"

    def test_binance_activity_scores_in_range(self, api_client):
        """activity_score should be 0-100"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        tokens = data.get("tokens", [])
        
        for token in tokens:
            score = token.get("activity_score", -1)
            assert 0 <= score <= 100, f"activity_score out of range for {token['symbol']}: {score}"

    def test_binance_flow_share_sum_reasonable(self, api_client):
        """flow_share values should sum to approximately 1.0 for priced tokens"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        tokens = data.get("tokens", [])
        
        priced_shares = [t["flow_share"] for t in tokens if t["flow_volume_usd"] > 0]
        total_share = sum(priced_shares)
        
        # Should be close to 1.0 (allowing small floating point tolerance)
        assert 0.99 <= total_share <= 1.01, f"Flow shares sum to {total_share}, expected ~1.0"

    def test_gate_io_token_matrix_returns_200(self, api_client):
        """Gate.io should return valid token matrix"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/gate-io/token-matrix")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert data.get("entity", {}).get("slug") == "gate-io"
        assert data.get("total_tokens", 0) > 0

    def test_gate_io_dominant_asset_structure(self, api_client):
        """Gate.io dominant_asset should have valid structure"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/gate-io/token-matrix")
        data = r.json()
        dominant = data.get("dominant_asset", {})
        assert dominant.get("symbol") == "USDT", f"Gate.io dominant should be USDT, got {dominant.get('symbol')}"
        assert dominant.get("role") in VALID_ROLES

    def test_coinbase_token_matrix_returns_200(self, api_client):
        """Coinbase should return valid token matrix"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/coinbase/token-matrix")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert data.get("entity", {}).get("slug") == "coinbase"

    def test_coinbase_dominant_is_usdc(self, api_client):
        """Coinbase dominant asset should be USDC"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/coinbase/token-matrix")
        data = r.json()
        dominant = data.get("dominant_asset", {})
        assert dominant.get("symbol") == "USDC", f"Coinbase dominant should be USDC, got {dominant.get('symbol')}"

    def test_okx_token_matrix_returns_200(self, api_client):
        """OKX should return valid token matrix"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/okx/token-matrix")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert data.get("entity", {}).get("slug") == "okx"

    def test_okx_minimal_data(self, api_client):
        """OKX has minimal flow data (1 token, ~$511)"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/okx/token-matrix")
        data = r.json()
        assert data.get("total_tokens") == 1, f"OKX should have 1 token, got {data.get('total_tokens')}"
        assert data.get("dominant_asset", {}).get("symbol") == "UNI"

    def test_nonexistent_entity_returns_404(self, api_client):
        """Nonexistent entity should return 404"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/nonexistent/token-matrix")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"
        data = r.json()
        assert data.get("ok") is False
        assert "error" in data

    def test_kraken_empty_matrix(self, api_client):
        """Kraken (no priced flows) should return empty matrix structure"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/kraken/token-matrix")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        
        # Empty/zero value checks
        assert data.get("priced_tokens", -1) == 0, "Kraken should have 0 priced tokens"
        assert data.get("total_flow_volume_usd", -1) == 0, "Kraken should have 0 flow volume"
        assert data.get("stablecoin_dependency", -1) == 0, "Kraken stablecoin_dependency should be 0"


# ==============================================================================
#  Phase 5 — Token Matrix Overview Tests
# ==============================================================================

class TestTokenMatrixOverview:
    """GET /api/entities/v2/token-matrix/overview — Cross-entity token analysis"""

    def test_overview_returns_200(self, api_client):
        """Overview endpoint should return 200"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/token-matrix/overview")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True

    def test_overview_has_aggregate_fields(self, api_client):
        """Overview should have total_unique_tokens, tokens_with_volume, total_volume_usd"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/token-matrix/overview")
        data = r.json()
        
        assert "total_unique_tokens" in data, "Missing total_unique_tokens"
        assert "tokens_with_volume" in data, "Missing tokens_with_volume"
        assert "total_volume_usd" in data, "Missing total_volume_usd"
        assert "top_tokens" in data, "Missing top_tokens"

    def test_overview_top_tokens_structure(self, api_client):
        """top_tokens has required fields per entry"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/token-matrix/overview")
        data = r.json()
        top_tokens = data.get("top_tokens", [])
        
        assert len(top_tokens) > 0, "top_tokens should not be empty"
        
        required_fields = [
            "token_address", "symbol", "token_class",
            "total_volume_usd", "total_transfers", "entity_count", "dominant_role"
        ]
        
        for token in top_tokens[:5]:
            for field in required_fields:
                assert field in token, f"top_token missing field: {field}"

    def test_overview_dominant_role_valid(self, api_client):
        """All top_tokens dominant_role should be valid"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/token-matrix/overview")
        data = r.json()
        
        for token in data.get("top_tokens", []):
            assert token.get("dominant_role") in VALID_ROLES, f"Invalid dominant_role: {token.get('dominant_role')}"

    def test_overview_usdt_is_top(self, api_client):
        """USDT should be the top token by volume"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/token-matrix/overview")
        data = r.json()
        top_tokens = data.get("top_tokens", [])
        
        assert len(top_tokens) > 0
        top_token = top_tokens[0]
        assert top_token.get("symbol") == "USDT", f"Expected USDT as top token, got {top_token.get('symbol')}"

    def test_overview_entities_array_present(self, api_client):
        """Top tokens should have entities array with slug, role, volume_usd"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/token-matrix/overview")
        data = r.json()
        top_tokens = data.get("top_tokens", [])
        
        for token in top_tokens[:3]:
            entities = token.get("entities", [])
            if token.get("total_volume_usd", 0) > 0:
                assert len(entities) > 0, f"Token {token.get('symbol')} with volume should have entities"
                for ent in entities:
                    assert "slug" in ent
                    assert "role" in ent
                    assert "volume_usd" in ent

    def test_overview_total_volume_consistency(self, api_client):
        """Total volume should be approximately sum of binance + gate-io + coinbase + okx"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/token-matrix/overview")
        data = r.json()
        
        total_vol = data.get("total_volume_usd", 0)
        # Known approx: binance $4.65M + gate-io $1.38M + coinbase $292K + okx $511 ≈ $6.3M
        assert total_vol > 6_000_000, f"Total volume {total_vol} should be > $6M"
        assert total_vol < 10_000_000, f"Total volume {total_vol} unexpectedly high"


# ==============================================================================
#  Phase 5 — Build All Token Matrices Tests
# ==============================================================================

class TestBuildAllTokenMatrices:
    """POST /api/entities/v2/token-matrix/build-all — Rebuild matrices"""

    @pytest.mark.skip(reason="Build-all is a long-running operation (30+ seconds)")
    def test_build_all_returns_stats(self, api_client):
        """Build-all should return stats with computed/with_tokens/errors"""
        r = api_client.post(f"{BASE_URL}/api/entities/v2/token-matrix/build-all")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        
        assert "total_entities" in data
        assert "computed" in data
        assert "with_tokens" in data
        assert "errors" in data

    def test_build_all_endpoint_exists(self, api_client):
        """Build-all endpoint should be accessible (quick check, no actual build)"""
        # Just verify the endpoint exists and doesn't 404
        r = api_client.options(f"{BASE_URL}/api/entities/v2/token-matrix/build-all")
        # OPTIONS may return 405 or 200 depending on CORS config, but not 404
        assert r.status_code != 404, "Build-all endpoint should exist"


# ==============================================================================
#  Token Role Classification Logic Tests
# ==============================================================================

class TestTokenRoleClassificationLogic:
    """Validate token role classification based on flow patterns"""

    def test_liquidity_token_classification(self, api_client):
        """USDT on Binance should be liquidity_token (high share, balanced flow)"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        tokens = data.get("tokens", [])
        
        usdt = next((t for t in tokens if t["symbol"] == "USDT"), None)
        assert usdt is not None, "USDT not found in Binance tokens"
        assert usdt["role"] == "liquidity_token", f"USDT should be liquidity_token, got {usdt['role']}"
        assert usdt["flow_share"] >= 0.15, "USDT should have high flow share for liquidity classification"

    def test_accumulation_token_classification(self, api_client):
        """DAI on Binance should be accumulation_token (net inflow)"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        tokens = data.get("tokens", [])
        
        dai = next((t for t in tokens if t["symbol"] == "DAI"), None)
        assert dai is not None, "DAI not found in Binance tokens"
        # DAI has inflow=40417, outflow=0 → net inflow → accumulation
        assert dai["role"] == "accumulation_token", f"DAI should be accumulation_token, got {dai['role']}"
        assert dai["inflow_usd"] > dai["outflow_usd"], "DAI should have positive net flow"

    def test_distribution_token_classification(self, api_client):
        """WBTC on Binance should be distribution_token (net outflow)"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        tokens = data.get("tokens", [])
        
        wbtc = next((t for t in tokens if t["symbol"] == "WBTC"), None)
        assert wbtc is not None, "WBTC not found in Binance tokens"
        # WBTC has inflow=0, outflow=260K → net outflow → distribution
        assert wbtc["role"] == "distribution_token", f"WBTC should be distribution_token, got {wbtc['role']}"
        assert wbtc["outflow_usd"] > wbtc["inflow_usd"], "WBTC should have negative net flow"

    def test_neutral_token_classification(self, api_client):
        """Tokens with 0 volume should be neutral_token"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/binance/token-matrix")
        data = r.json()
        tokens = data.get("tokens", [])
        
        neutral_tokens = [t for t in tokens if t["flow_volume_usd"] == 0]
        for t in neutral_tokens:
            assert t["role"] == "neutral_token", f"Token {t['symbol']} with 0 volume should be neutral_token"


# ==============================================================================
#  Phase 1-4 Regression Tests
# ==============================================================================

class TestPhase1to4Regression:
    """Ensure previous phases still work"""

    def test_phase1_list_entities(self, api_client):
        """Phase 1: List entities should work"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/list")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        # Check pagination.total instead of top-level total
        pagination = data.get("pagination", {})
        assert pagination.get("total", 0) >= 10

    def test_phase2_address_index_status(self, api_client):
        """Phase 2: Address index status should work"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/address-index/status")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        # Check indexed field instead of total_addresses_indexed
        assert data.get("indexed", 0) > 0

    def test_phase3_holdings_overview(self, api_client):
        """Phase 3: Holdings overview should work"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/holdings/overview")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert data.get("entities_with_holdings", 0) >= 4

    def test_phase4_flows_overview(self, api_client):
        """Phase 4: Flows overview should work"""
        r = api_client.get(f"{BASE_URL}/api/entities/v2/flows/overview")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert data.get("entities_with_flows", 0) >= 4
