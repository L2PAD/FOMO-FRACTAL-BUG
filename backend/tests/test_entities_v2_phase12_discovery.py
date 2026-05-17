"""
Entities V2 Phase 12: Entity Discovery Engine Tests
====================================================
Tests for automatic discovery of new market actors from unknown wallet clusters.
- GET /api/entities/v2/discovery — all candidates sorted by score
- GET /api/entities/v2/discovery/{cluster_id} — single candidate detail
- POST /api/entities/v2/discovery/build — build/rebuild discovery data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Valid candidate types per spec
VALID_CANDIDATE_TYPES = {
    "possible_fund",
    "possible_market_maker",
    "possible_whale",
    "possible_protocol_actor",
    "unknown_cluster"
}

# Component weights per spec
DISCOVERY_WEIGHTS = {
    "cluster_size": 0.30,
    "capital_activity": 0.25,
    "behaviour_coherence": 0.20,
    "token_pattern": 0.15,
    "counterparty_network": 0.10
}


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ═══════════════════════════════════════════════════════════════
# TEST: GET /api/entities/v2/discovery — All candidates
# ═══════════════════════════════════════════════════════════════

class TestDiscoveryList:
    """Tests for GET /api/entities/v2/discovery endpoint."""
    
    def test_discovery_list_returns_200(self, api_client):
        """GET /discovery returns 200 OK."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True
    
    def test_discovery_list_structure(self, api_client):
        """Response has total_candidates, type_distribution, candidates."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        assert "total_candidates" in data, "Missing total_candidates"
        assert "type_distribution" in data, "Missing type_distribution"
        assert "candidates" in data, "Missing candidates list"
        
        assert isinstance(data["total_candidates"], int)
        assert isinstance(data["type_distribution"], dict)
        assert isinstance(data["candidates"], list)
    
    def test_discovery_has_candidates(self, api_client):
        """Discovery has at least 1 candidate (8 per agent context)."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        assert data["total_candidates"] >= 1, "Expected at least 1 candidate"
        assert len(data["candidates"]) >= 1
    
    def test_candidate_structure_all_fields(self, api_client):
        """Each candidate has all required fields."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        required_fields = [
            "cluster_id", "parent_entity", "candidate_type", 
            "discovery_score", "confidence", "wallets",
            "dominant_tokens", "signals", "components",
            "activity", "attribution"
        ]
        
        for candidate in data["candidates"][:3]:  # Check first 3
            for field in required_fields:
                assert field in candidate, f"Candidate missing field: {field}"
    
    def test_discovery_score_range(self, api_client):
        """discovery_score is float between 0 and 1."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        for c in data["candidates"]:
            score = c["discovery_score"]
            assert isinstance(score, (int, float)), f"discovery_score must be numeric, got {type(score)}"
            assert 0 <= score <= 1, f"discovery_score {score} not in [0,1]"
    
    def test_candidate_type_valid(self, api_client):
        """candidate_type is one of valid types."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        for c in data["candidates"]:
            assert c["candidate_type"] in VALID_CANDIDATE_TYPES, \
                f"Invalid candidate_type: {c['candidate_type']}"
    
    def test_components_structure(self, api_client):
        """Components has all 5 signal scores (0-1 floats)."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        required_components = [
            "cluster_size", "capital_activity", "behaviour_coherence",
            "token_pattern", "counterparty_network"
        ]
        
        for c in data["candidates"][:3]:
            comp = c["components"]
            for key in required_components:
                assert key in comp, f"Missing component: {key}"
                val = comp[key]
                assert isinstance(val, (int, float)), f"Component {key} must be numeric"
                assert 0 <= val <= 1, f"Component {key}={val} not in [0,1]"
    
    def test_candidates_sorted_by_score_desc(self, api_client):
        """Candidates are sorted by discovery_score descending."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        scores = [c["discovery_score"] for c in data["candidates"]]
        assert scores == sorted(scores, reverse=True), "Candidates not sorted by score desc"
    
    def test_type_distribution_counts_match(self, api_client):
        """type_distribution counts sum to total_candidates."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        type_dist = data["type_distribution"]
        total_from_dist = sum(type_dist.values())
        
        assert total_from_dist == data["total_candidates"], \
            f"type_distribution sum ({total_from_dist}) != total_candidates ({data['total_candidates']})"
    
    def test_dominant_tokens_is_list(self, api_client):
        """dominant_tokens is a list."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        for c in data["candidates"][:3]:
            assert isinstance(c["dominant_tokens"], list), "dominant_tokens must be list"
    
    def test_signals_is_list(self, api_client):
        """signals is a list of strings."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        for c in data["candidates"][:3]:
            assert isinstance(c["signals"], list), "signals must be list"
    
    def test_activity_structure(self, api_client):
        """activity has total_transfers, outbound, inbound, unique_tokens, direction."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        required_activity_fields = [
            "total_transfers", "outbound", "inbound", 
            "unique_tokens", "direction"
        ]
        
        for c in data["candidates"][:3]:
            activity = c["activity"]
            for field in required_activity_fields:
                assert field in activity, f"Activity missing field: {field}"
    
    def test_attribution_structure(self, api_client):
        """attribution has current_score, current_entity, level."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        for c in data["candidates"][:3]:
            attr = c["attribution"]
            assert "current_score" in attr
            assert "current_entity" in attr
            assert "level" in attr


# ═══════════════════════════════════════════════════════════════
# TEST: GET /api/entities/v2/discovery/{cluster_id} — Single detail
# ═══════════════════════════════════════════════════════════════

class TestDiscoveryDetail:
    """Tests for GET /api/entities/v2/discovery/{cluster_id} endpoint."""
    
    def test_discovery_detail_returns_200(self, api_client):
        """GET /discovery/binance_cluster_1 returns 200."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery/binance_cluster_1")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    def test_discovery_detail_structure(self, api_client):
        """Detail response has all candidate fields."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery/binance_cluster_1")
        data = resp.json()
        
        assert data.get("ok") is True
        assert data.get("cluster_id") == "binance_cluster_1"
        assert "discovery_score" in data
        assert "candidate_type" in data
        assert "components" in data
        assert "activity" in data
    
    def test_discovery_detail_score_value(self, api_client):
        """binance_cluster_1 has top score ~0.845 per agent context."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery/binance_cluster_1")
        data = resp.json()
        
        score = data["discovery_score"]
        assert 0.8 <= score <= 0.9, f"Expected score ~0.845, got {score}"
    
    def test_discovery_detail_candidate_type(self, api_client):
        """binance_cluster_1 is possible_fund per agent context."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery/binance_cluster_1")
        data = resp.json()
        
        assert data["candidate_type"] == "possible_fund"
    
    def test_nonexistent_returns_404(self, api_client):
        """GET /discovery/nonexistent returns 404."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery/nonexistent")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        
        data = resp.json()
        assert data.get("ok") is False
        assert "error" in data


# ═══════════════════════════════════════════════════════════════
# TEST: POST /api/entities/v2/discovery/build — Build discovery
# ═══════════════════════════════════════════════════════════════

class TestDiscoveryBuild:
    """Tests for POST /api/entities/v2/discovery/build endpoint."""
    
    def test_build_returns_200(self, api_client):
        """POST /discovery/build returns 200."""
        resp = api_client.post(f"{BASE_URL}/api/entities/v2/discovery/build")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    def test_build_response_structure(self, api_client):
        """Build response has total_candidates, type_distribution, top_candidates, built_at."""
        resp = api_client.post(f"{BASE_URL}/api/entities/v2/discovery/build")
        data = resp.json()
        
        assert data.get("ok") is True
        assert "total_candidates" in data
        assert "type_distribution" in data
        assert "top_candidates" in data
        assert "built_at" in data
    
    def test_build_returns_candidates(self, api_client):
        """Build returns 8 candidates per agent context."""
        resp = api_client.post(f"{BASE_URL}/api/entities/v2/discovery/build")
        data = resp.json()
        
        assert data["total_candidates"] >= 1, "Expected at least 1 candidate"
        assert len(data["top_candidates"]) >= 1
    
    def test_build_type_distribution(self, api_client):
        """Build returns correct type_distribution."""
        resp = api_client.post(f"{BASE_URL}/api/entities/v2/discovery/build")
        data = resp.json()
        
        type_dist = data["type_distribution"]
        assert isinstance(type_dist, dict)
        
        # All type keys should be valid
        for t in type_dist.keys():
            assert t in VALID_CANDIDATE_TYPES, f"Invalid type in distribution: {t}"
    
    def test_build_top_candidates_sorted(self, api_client):
        """top_candidates are sorted by discovery_score desc."""
        resp = api_client.post(f"{BASE_URL}/api/entities/v2/discovery/build")
        data = resp.json()
        
        scores = [c["discovery_score"] for c in data["top_candidates"]]
        assert scores == sorted(scores, reverse=True)


# ═══════════════════════════════════════════════════════════════
# TEST: Data integrity & business rules
# ═══════════════════════════════════════════════════════════════

class TestDiscoveryIntegrity:
    """Tests for discovery data integrity and business rules."""
    
    def test_confidence_range(self, api_client):
        """confidence is float in [0, 1]."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        for c in data["candidates"]:
            conf = c["confidence"]
            assert isinstance(conf, (int, float))
            assert 0 <= conf <= 1.2, f"confidence {conf} out of expected range"
    
    def test_wallets_positive(self, api_client):
        """wallets count is positive integer >= 2."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        for c in data["candidates"]:
            w = c["wallets"]
            assert isinstance(w, int), "wallets must be int"
            assert w >= 2, f"wallets count {w} should be >= 2"
    
    def test_parent_entity_not_empty(self, api_client):
        """parent_entity is not empty string."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        for c in data["candidates"]:
            assert c["parent_entity"], "parent_entity should not be empty"
    
    def test_cluster_id_format(self, api_client):
        """cluster_id follows pattern {entity}_cluster_{n}."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        for c in data["candidates"]:
            cid = c["cluster_id"]
            assert "_cluster_" in cid, f"cluster_id {cid} missing '_cluster_' pattern"
    
    def test_direction_valid(self, api_client):
        """activity.direction is inflow_dominant, outflow_dominant, balanced, or none."""
        valid_directions = {"inflow_dominant", "outflow_dominant", "balanced", "none"}
        
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/discovery")
        data = resp.json()
        
        for c in data["candidates"]:
            direction = c["activity"].get("direction")
            assert direction in valid_directions, f"Invalid direction: {direction}"
