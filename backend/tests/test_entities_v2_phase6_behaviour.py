"""
Entities V2 — Phase 6: Behaviour Engine Tests
==============================================
Tests for behaviour classification endpoints.

Behaviour types: accumulation, distribution, market_making, liquidity_provision, treasury, mixed
Source data: entity_flows_v2, entity_token_matrix_v2, entity_holdings_v2
Output: entity_behaviour_v2 collection

Endpoints:
- POST /api/entities/v2/behaviour/build-all — Build all behaviours
- GET /api/entities/v2/behaviour/overview — Type distribution
- GET /api/entities/v2/{slug}/behaviour — Single entity behaviour
"""

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8001"

VALID_BEHAVIOUR_TYPES = {"accumulation", "distribution", "market_making", "liquidity_provision", "treasury", "mixed"}


class TestEntityBehaviourEndpoint:
    """Test GET /api/entities/v2/{slug}/behaviour endpoint"""

    def test_binance_behaviour(self):
        """Binance should have liquidity_provision behaviour with high confidence"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour", timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        # Check behaviour_type
        behaviour_type = data.get("behaviour_type")
        assert behaviour_type in VALID_BEHAVIOUR_TYPES, f"Invalid behaviour_type: {behaviour_type}"
        assert behaviour_type == "liquidity_provision", f"Expected liquidity_provision for Binance, got {behaviour_type}"
        
        # Check confidence (0-1)
        confidence = data.get("confidence")
        assert isinstance(confidence, (int, float)), "confidence must be a number"
        assert 0 <= confidence <= 1, f"confidence {confidence} not in range [0,1]"
        assert confidence >= 0.80, f"Binance confidence should be >= 0.80, got {confidence}"
        
        # Check drivers (list of strings)
        drivers = data.get("drivers")
        assert isinstance(drivers, list), "drivers must be a list"
        assert len(drivers) >= 1, "drivers should have at least one explanation"
        for d in drivers:
            assert isinstance(d, str), f"Each driver must be a string, got {type(d)}"
            assert len(d) > 3, f"Driver too short to be meaningful: '{d}'"
        
        # Check signals object structure
        signals = data.get("signals")
        assert isinstance(signals, dict), "signals must be a dict"
        assert "flow" in signals, "signals.flow missing"
        assert "token_matrix" in signals, "signals.token_matrix missing"
        assert "holdings" in signals, "signals.holdings missing"

    def test_binance_signals_flow_structure(self):
        """Validate signals.flow structure for Binance"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour", timeout=30)
        assert resp.status_code == 200
        
        flow = resp.json().get("signals", {}).get("flow", {})
        
        # Required fields
        assert "has_data" in flow, "signals.flow.has_data missing"
        assert "direction" in flow, "signals.flow.direction missing"
        assert "net_flow_bias" in flow, "signals.flow.net_flow_bias missing"
        assert "velocity_usd" in flow, "signals.flow.velocity_usd missing"
        assert "inflow_usd" in flow, "signals.flow.inflow_usd missing"
        assert "outflow_usd" in flow, "signals.flow.outflow_usd missing"
        assert "net_flow_usd" in flow, "signals.flow.net_flow_usd missing"
        
        # Type checks
        assert isinstance(flow["has_data"], bool), "has_data must be boolean"
        assert isinstance(flow["net_flow_bias"], (int, float)), "net_flow_bias must be number"
        assert isinstance(flow["velocity_usd"], (int, float)), "velocity_usd must be number"

    def test_binance_signals_token_matrix_structure(self):
        """Validate signals.token_matrix structure for Binance"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour", timeout=30)
        assert resp.status_code == 200
        
        matrix = resp.json().get("signals", {}).get("token_matrix", {})
        
        # Required fields
        assert "has_data" in matrix, "signals.token_matrix.has_data missing"
        assert "stablecoin_dependency" in matrix, "signals.token_matrix.stablecoin_dependency missing"
        assert "top3_concentration" in matrix, "signals.token_matrix.top3_concentration missing"
        assert "role_shares" in matrix, "signals.token_matrix.role_shares missing"
        assert "priced_tokens" in matrix, "signals.token_matrix.priced_tokens missing"
        
        # Type checks
        assert isinstance(matrix["has_data"], bool), "has_data must be boolean"
        assert isinstance(matrix["role_shares"], dict), "role_shares must be dict"

    def test_binance_signals_holdings_structure(self):
        """Validate signals.holdings structure for Binance"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour", timeout=30)
        assert resp.status_code == 200
        
        holdings = resp.json().get("signals", {}).get("holdings", {})
        
        # Required fields
        assert "has_data" in holdings, "signals.holdings.has_data missing"
        assert "total_value_usd" in holdings, "signals.holdings.total_value_usd missing"
        assert "stablecoin_share" in holdings, "signals.holdings.stablecoin_share missing"
        assert "concentration" in holdings, "signals.holdings.concentration missing"
        
        # Type checks
        assert isinstance(holdings["has_data"], bool), "has_data must be boolean"
        assert isinstance(holdings["total_value_usd"], (int, float)), "total_value_usd must be number"

    def test_gate_io_behaviour_accumulation(self):
        """Gate.io should have accumulation behaviour"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/gate-io/behaviour", timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("ok") is True
        
        behaviour_type = data.get("behaviour_type")
        assert behaviour_type in VALID_BEHAVIOUR_TYPES, f"Invalid behaviour_type: {behaviour_type}"
        assert behaviour_type == "accumulation", f"Expected accumulation for Gate.io, got {behaviour_type}"
        
        # Check confidence
        confidence = data.get("confidence")
        assert 0 <= confidence <= 1, f"confidence {confidence} not in range [0,1]"
        
        # Drivers should exist
        drivers = data.get("drivers")
        assert isinstance(drivers, list) and len(drivers) >= 1

    def test_coinbase_behaviour_accumulation(self):
        """Coinbase should have accumulation behaviour"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/coinbase/behaviour", timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("ok") is True
        
        behaviour_type = data.get("behaviour_type")
        assert behaviour_type in VALID_BEHAVIOUR_TYPES, f"Invalid behaviour_type: {behaviour_type}"
        assert behaviour_type == "accumulation", f"Expected accumulation for Coinbase, got {behaviour_type}"

    def test_okx_behaviour_accumulation(self):
        """OKX should have accumulation behaviour"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/okx/behaviour", timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("ok") is True
        
        behaviour_type = data.get("behaviour_type")
        assert behaviour_type in VALID_BEHAVIOUR_TYPES, f"Invalid behaviour_type: {behaviour_type}"
        assert behaviour_type == "accumulation", f"Expected accumulation for OKX, got {behaviour_type}"

    def test_kraken_behaviour_mixed_insufficient_data(self):
        """Kraken should return mixed with insufficient data (no flow data)"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/kraken/behaviour", timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("ok") is True
        
        behaviour_type = data.get("behaviour_type")
        assert behaviour_type in VALID_BEHAVIOUR_TYPES, f"Invalid behaviour_type: {behaviour_type}"
        assert behaviour_type == "mixed", f"Expected mixed for Kraken, got {behaviour_type}"
        
        # Confidence should be low or zero for insufficient data
        confidence = data.get("confidence")
        assert confidence <= 0.5, f"Expected low confidence for Kraken (insufficient data), got {confidence}"
        
        # Drivers should mention insufficient data
        drivers = data.get("drivers", [])
        assert any("insufficient" in d.lower() or "no" in d.lower() or "weak" in d.lower() for d in drivers), \
            f"Drivers should mention data insufficiency: {drivers}"

    def test_nonexistent_entity_404(self):
        """Nonexistent entity should return 404"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent/behaviour", timeout=30)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        
        data = resp.json()
        assert data.get("ok") is False
        assert "error" in data

    def test_entity_field_in_response(self):
        """Response should include entity details"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour", timeout=30)
        assert resp.status_code == 200
        
        entity = resp.json().get("entity", {})
        assert "slug" in entity, "entity.slug missing"
        assert "name" in entity, "entity.name missing"
        assert "type" in entity, "entity.type missing"
        assert "category" in entity, "entity.category missing"
        assert entity["slug"] == "binance"


class TestBehaviourOverview:
    """Test GET /api/entities/v2/behaviour/overview endpoint"""

    def test_overview_returns_valid_response(self):
        """Overview should return type distribution and entities list"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/behaviour/overview", timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("ok") is True
        
        # Check type_distribution
        type_dist = data.get("type_distribution")
        assert isinstance(type_dist, dict), "type_distribution must be a dict"
        
        # All keys should be valid behaviour types
        for key in type_dist.keys():
            assert key in VALID_BEHAVIOUR_TYPES, f"Invalid behaviour type in distribution: {key}"

    def test_overview_entities_list(self):
        """Overview should include entities list sorted by confidence"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/behaviour/overview", timeout=30)
        assert resp.status_code == 200
        
        entities = resp.json().get("entities", [])
        assert isinstance(entities, list), "entities must be a list"
        assert len(entities) > 0, "Should have at least one entity"
        
        # Check each entity has required fields
        for ent in entities:
            assert "slug" in ent, f"Entity missing slug: {ent}"
            assert "name" in ent, f"Entity missing name: {ent}"
            assert "behaviour_type" in ent, f"Entity missing behaviour_type: {ent}"
            assert "confidence" in ent, f"Entity missing confidence: {ent}"
            assert "drivers" in ent, f"Entity missing drivers: {ent}"

    def test_overview_sorted_by_confidence_descending(self):
        """Entities in overview should be sorted by confidence descending"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/behaviour/overview", timeout=30)
        assert resp.status_code == 200
        
        entities = resp.json().get("entities", [])
        if len(entities) >= 2:
            confidences = [e["confidence"] for e in entities]
            assert confidences == sorted(confidences, reverse=True), \
                f"Entities not sorted by confidence descending: {confidences}"

    def test_overview_total_entities_count(self):
        """Overview should report correct total entities count"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/behaviour/overview", timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        total = data.get("total_entities", 0)
        entities_len = len(data.get("entities", []))
        
        assert total == entities_len, f"total_entities {total} != len(entities) {entities_len}"


class TestBuildAllBehaviours:
    """Test POST /api/entities/v2/behaviour/build-all endpoint"""

    def test_build_all_returns_stats(self):
        """Build-all should return stats with by_type breakdown"""
        resp = requests.post(f"{BASE_URL}/api/entities/v2/behaviour/build-all", timeout=60)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("ok") is True
        
        # Check required stats fields
        assert "total_entities" in data, "missing total_entities"
        assert "computed" in data, "missing computed"
        assert "by_type" in data, "missing by_type"
        
        # All types in by_type should be valid
        by_type = data.get("by_type", {})
        for key in by_type.keys():
            assert key in VALID_BEHAVIOUR_TYPES, f"Invalid type in by_type: {key}"
        
        # Computed count should match sum of by_type counts
        type_sum = sum(by_type.values())
        computed = data.get("computed", 0)
        assert computed == type_sum, f"computed {computed} != sum of by_type {type_sum}"

    def test_build_all_15_entities(self):
        """Build-all should process all 15 entities"""
        resp = requests.post(f"{BASE_URL}/api/entities/v2/behaviour/build-all", timeout=60)
        assert resp.status_code == 200
        
        data = resp.json()
        total = data.get("total_entities", 0)
        computed = data.get("computed", 0)
        
        assert total == 15, f"Expected 15 total entities, got {total}"
        assert computed == 15, f"Expected 15 computed, got {computed}"


class TestBehaviourDataValidation:
    """Additional data validation tests"""

    def test_drivers_are_meaningful(self):
        """Drivers should be real explanations not generic strings"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour", timeout=30)
        assert resp.status_code == 200
        
        drivers = resp.json().get("drivers", [])
        
        # Drivers should be more than just placeholders
        for d in drivers:
            assert d not in ["driver1", "driver2", "unknown", "test"], \
                f"Driver appears to be placeholder: {d}"
            # Should be descriptive
            assert len(d) > 5, f"Driver too short: '{d}'"

    def test_confidence_range_all_entities(self):
        """All entities should have confidence in [0,1] range"""
        slugs = ["binance", "gate-io", "coinbase", "okx", "kraken", "bybit", "kucoin"]
        
        for slug in slugs:
            resp = requests.get(f"{BASE_URL}/api/entities/v2/{slug}/behaviour", timeout=30)
            if resp.status_code == 200:
                confidence = resp.json().get("confidence")
                assert 0 <= confidence <= 1, f"{slug} confidence {confidence} not in [0,1]"

    def test_behaviour_type_consistency_with_overview(self):
        """Individual entity behaviour type should match overview"""
        overview_resp = requests.get(f"{BASE_URL}/api/entities/v2/behaviour/overview", timeout=30)
        assert overview_resp.status_code == 200
        
        entities = overview_resp.json().get("entities", [])
        overview_map = {e["slug"]: e["behaviour_type"] for e in entities}
        
        # Check at least one entity
        if "binance" in overview_map:
            binance_resp = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour", timeout=30)
            assert binance_resp.status_code == 200
            binance_type = binance_resp.json().get("behaviour_type")
            assert binance_type == overview_map["binance"], \
                f"Binance type mismatch: individual={binance_type}, overview={overview_map['binance']}"


class TestResponseStructureComplete:
    """Test complete response structure"""

    def test_full_response_structure(self):
        """Test complete response has all required fields"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour", timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        
        # Top-level required fields
        required_top = ["ok", "entity", "behaviour_type", "confidence", "drivers", "signals", "computed_at"]
        for field in required_top:
            assert field in data, f"Missing top-level field: {field}"
        
        # Entity fields
        entity = data["entity"]
        for f in ["slug", "name", "type", "category"]:
            assert f in entity, f"Missing entity.{f}"
        
        # Signals sub-objects
        signals = data["signals"]
        for sig in ["flow", "token_matrix", "holdings"]:
            assert sig in signals, f"Missing signals.{sig}"

    def test_computed_at_is_iso_timestamp(self):
        """computed_at should be ISO format timestamp"""
        resp = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour", timeout=30)
        assert resp.status_code == 200
        
        computed_at = resp.json().get("computed_at", "")
        assert computed_at, "computed_at is empty"
        # Should contain date-time separators
        assert "T" in computed_at or "-" in computed_at, f"computed_at not ISO format: {computed_at}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
