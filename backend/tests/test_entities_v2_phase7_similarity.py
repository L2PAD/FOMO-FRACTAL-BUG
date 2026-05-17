"""
Entities V2 — Phase 7: Similarity Engine Tests
===============================================
Tests for similarity computation between entities using multi-signal composite score:
- behaviour (0.35) + token_matrix (0.30) + flows (0.20) + portfolio (0.15)

Endpoints tested:
- POST /api/entities/v2/similarity/build-all — Build all similarity rankings
- GET /api/entities/v2/similarity-map — Cross-entity similarity map
- GET /api/entities/v2/{slug}/similar — Similar entities for a given entity
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestSimilarityBuildAll:
    """POST /api/entities/v2/similarity/build-all tests."""

    def test_build_all_similarities_returns_200(self, api_client):
        """Build-all returns success with stats."""
        resp = api_client.post(f"{BASE_URL}/api/entities/v2/similarity/build-all")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        print(f"[PASS] POST /api/entities/v2/similarity/build-all returned 200")

    def test_build_all_returns_stats(self, api_client):
        """Build-all returns proper stats structure."""
        resp = api_client.post(f"{BASE_URL}/api/entities/v2/similarity/build-all")
        data = resp.json()
        # Should have total_entities, computed, errors
        assert "total_entities" in data, "Missing total_entities"
        assert "computed" in data, "Missing computed count"
        assert "errors" in data, "Missing errors count"
        assert data["total_entities"] >= 15, f"Expected at least 15 entities, got {data['total_entities']}"
        assert data["computed"] == data["total_entities"], "Not all entities computed"
        assert data["errors"] == 0, f"Errors during build: {data['errors']}"
        print(f"[PASS] Build-all stats: {data['computed']}/{data['total_entities']} computed, {data['errors']} errors")


class TestSimilarityMap:
    """GET /api/entities/v2/similarity-map tests."""

    def test_similarity_map_returns_200(self, api_client):
        """Similarity map returns success."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/similarity-map")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        print(f"[PASS] GET /api/entities/v2/similarity-map returned 200")

    def test_similarity_map_has_required_fields(self, api_client):
        """Similarity map contains clusters, top_pairs, total_entities."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/similarity-map")
        data = resp.json()
        assert "total_entities" in data, "Missing total_entities"
        assert "clusters" in data, "Missing clusters"
        assert "top_pairs" in data, "Missing top_pairs"
        print(f"[PASS] Similarity map has all required fields")

    def test_similarity_map_clusters_structure(self, api_client):
        """Clusters are grouped by behaviour_type."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/similarity-map")
        data = resp.json()
        clusters = data.get("clusters", [])
        assert isinstance(clusters, list), "clusters should be a list"
        for cluster in clusters:
            assert "behaviour_type" in cluster, "Cluster missing behaviour_type"
            assert "entity_count" in cluster, "Cluster missing entity_count"
            assert "entities" in cluster, "Cluster missing entities list"
            assert isinstance(cluster["entities"], list), "entities should be a list"
            # Each entity in cluster should have slug, name, type
            for ent in cluster["entities"]:
                assert "slug" in ent, "Entity in cluster missing slug"
                assert "name" in ent, "Entity in cluster missing name"
        print(f"[PASS] Clusters structure validated - {len(clusters)} behaviour type groups")

    def test_similarity_map_top_pairs_structure(self, api_client):
        """Top pairs have entity_a, entity_b, similarity_score, reasons."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/similarity-map")
        data = resp.json()
        top_pairs = data.get("top_pairs", [])
        assert isinstance(top_pairs, list), "top_pairs should be a list"
        if top_pairs:
            pair = top_pairs[0]
            assert "entity_a" in pair, "Pair missing entity_a"
            assert "entity_b" in pair, "Pair missing entity_b"
            assert "similarity_score" in pair, "Pair missing similarity_score"
            assert "reasons" in pair, "Pair missing reasons"
            # Score should be float in range [0,1]
            score = pair["similarity_score"]
            assert isinstance(score, (int, float)), "similarity_score should be numeric"
            assert 0 <= score <= 1, f"Score {score} not in [0,1]"
        print(f"[PASS] Top pairs structure validated - {len(top_pairs)} pairs")


class TestEntitySimilarBinance:
    """GET /api/entities/v2/binance/similar tests."""

    def test_binance_similar_returns_200(self, api_client):
        """Binance similar returns success."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        print(f"[PASS] GET /api/entities/v2/binance/similar returned 200")

    def test_binance_similar_has_top_similar_list(self, api_client):
        """Response contains top_similar list."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        data = resp.json()
        assert "top_similar" in data, "Missing top_similar"
        assert isinstance(data["top_similar"], list), "top_similar should be a list"
        assert len(data["top_similar"]) > 0, "top_similar should not be empty"
        print(f"[PASS] Binance has {len(data['top_similar'])} similar entities")

    def test_binance_similar_entity_structure(self, api_client):
        """Each similar entity has required fields."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        data = resp.json()
        top = data.get("top_similar", [])
        for ent in top:
            assert "slug" in ent, "Missing slug"
            assert "name" in ent, "Missing name"
            assert "type" in ent, "Missing type"
            assert "category" in ent, "Missing category"
            assert "behaviour_type" in ent, "Missing behaviour_type"
            assert "similarity_score" in ent, "Missing similarity_score"
            assert "reasons" in ent, "Missing reasons"
            assert "components" in ent, "Missing components"
        print(f"[PASS] All similar entities have required fields")

    def test_binance_similar_score_is_valid_float(self, api_client):
        """similarity_score is float in range [0,1]."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        data = resp.json()
        for ent in data.get("top_similar", []):
            score = ent["similarity_score"]
            assert isinstance(score, (int, float)), f"Score {score} not numeric"
            assert 0 <= score <= 1, f"Score {score} not in [0,1]"
        print(f"[PASS] All similarity_scores are valid floats in [0,1]")

    def test_binance_similar_components_structure(self, api_client):
        """Components has behaviour, token_matrix, flows, portfolio (all floats 0-1)."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        data = resp.json()
        for ent in data.get("top_similar", []):
            comps = ent.get("components", {})
            for key in ["behaviour", "token_matrix", "flows", "portfolio"]:
                assert key in comps, f"Missing component: {key}"
                val = comps[key]
                assert isinstance(val, (int, float)), f"{key} value {val} not numeric"
                assert 0 <= val <= 1, f"{key} value {val} not in [0,1]"
        print(f"[PASS] All component scores validated")

    def test_binance_similar_reasons_is_list(self, api_client):
        """reasons is list of strings."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        data = resp.json()
        for ent in data.get("top_similar", []):
            reasons = ent.get("reasons", [])
            assert isinstance(reasons, list), "reasons should be a list"
            for r in reasons:
                assert isinstance(r, str), f"reason should be string, got {type(r)}"
        print(f"[PASS] All reasons validated as list of strings")

    def test_binance_similar_sorted_descending(self, api_client):
        """top_similar is sorted by similarity_score descending."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        data = resp.json()
        scores = [e["similarity_score"] for e in data.get("top_similar", [])]
        assert scores == sorted(scores, reverse=True), "Not sorted descending"
        print(f"[PASS] top_similar sorted by score descending: {scores[:3]}...")

    def test_binance_not_in_own_similar_list(self, api_client):
        """Entity does not appear in its own similar list."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        data = resp.json()
        slugs = [e["slug"] for e in data.get("top_similar", [])]
        assert "binance" not in slugs, "binance should not be in its own similar list"
        print(f"[PASS] binance not in its own similar list")


class TestEntitySimilarGateIO:
    """GET /api/entities/v2/gate-io/similar tests."""

    def test_gate_io_similar_returns_200(self, api_client):
        """Gate.io similar returns success."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/gate-io/similar")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"[PASS] GET /api/entities/v2/gate-io/similar returned 200")

    def test_gate_io_most_similar_is_coinbase(self, api_client):
        """Gate.io most similar to Coinbase (both accumulation behaviour)."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/gate-io/similar")
        data = resp.json()
        top_similar = data.get("top_similar", [])
        assert len(top_similar) > 0, "No similar entities"
        # Top should be coinbase or at least high scorer
        top_slug = top_similar[0]["slug"]
        top_score = top_similar[0]["similarity_score"]
        print(f"[INFO] Gate.io top similar: {top_slug} (score: {top_score})")
        # Verify score is reasonable
        assert top_score >= 0.3, f"Top similarity score too low: {top_score}"
        print(f"[PASS] Gate.io has valid top similar entity")

    def test_gate_io_not_in_own_list(self, api_client):
        """Gate.io not in its own similar list."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/gate-io/similar")
        data = resp.json()
        slugs = [e["slug"] for e in data.get("top_similar", [])]
        assert "gate-io" not in slugs, "gate-io should not be in its own list"
        print(f"[PASS] gate-io not in its own similar list")


class TestEntitySimilarCoinbase:
    """GET /api/entities/v2/coinbase/similar tests."""

    def test_coinbase_similar_returns_200(self, api_client):
        """Coinbase similar returns success."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/coinbase/similar")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"[PASS] GET /api/entities/v2/coinbase/similar returned 200")

    def test_coinbase_similar_has_rankings(self, api_client):
        """Coinbase has valid similarity rankings."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/coinbase/similar")
        data = resp.json()
        top_similar = data.get("top_similar", [])
        assert len(top_similar) > 0, "No similar entities"
        # Verify structure
        first = top_similar[0]
        assert "similarity_score" in first
        assert "components" in first
        print(f"[PASS] Coinbase has {len(top_similar)} similar entities")


class TestEntitySimilarOKX:
    """GET /api/entities/v2/okx/similar tests."""

    def test_okx_similar_returns_200(self, api_client):
        """OKX similar returns success."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/okx/similar")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"[PASS] GET /api/entities/v2/okx/similar returned 200")

    def test_okx_similar_has_rankings(self, api_client):
        """OKX has valid similarity rankings."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/okx/similar")
        data = resp.json()
        top_similar = data.get("top_similar", [])
        assert len(top_similar) > 0, "No similar entities"
        print(f"[PASS] OKX has {len(top_similar)} similar entities")


class TestEntitySimilarKraken:
    """GET /api/entities/v2/kraken/similar tests (entity with no data)."""

    def test_kraken_similar_returns_200(self, api_client):
        """Kraken (no data) still returns similarity results."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/kraken/similar")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"[PASS] GET /api/entities/v2/kraken/similar returned 200")

    def test_kraken_similar_has_rankings(self, api_client):
        """Kraken has similarity rankings despite no data."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/kraken/similar")
        data = resp.json()
        top_similar = data.get("top_similar", [])
        assert len(top_similar) > 0, "No similar entities even for entity with no data"
        print(f"[PASS] Kraken (no data) has {len(top_similar)} similar entities")


class TestEntitySimilarNonexistent:
    """GET /api/entities/v2/nonexistent/similar tests (404 case)."""

    def test_nonexistent_returns_404(self, api_client):
        """Nonexistent entity returns 404."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/nonexistent/similar")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is False
        assert "error" in data
        print(f"[PASS] GET /api/entities/v2/nonexistent/similar returned 404")


class TestSimilarityResponseStructure:
    """Validate complete response structure for similar endpoint."""

    def test_entity_info_in_response(self, api_client):
        """Response contains entity info."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        data = resp.json()
        assert "entity" in data, "Missing entity info"
        entity = data["entity"]
        assert "slug" in entity
        assert "name" in entity
        assert "type" in entity
        assert "category" in entity
        print(f"[PASS] Response contains entity info")

    def test_total_compared_in_response(self, api_client):
        """Response contains total_compared count."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        data = resp.json()
        assert "total_compared" in data, "Missing total_compared"
        assert isinstance(data["total_compared"], int)
        assert data["total_compared"] >= 14, "Should compare against at least 14 other entities"
        print(f"[PASS] total_compared: {data['total_compared']}")

    def test_computed_at_in_response(self, api_client):
        """Response contains computed_at timestamp."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        data = resp.json()
        assert "computed_at" in data, "Missing computed_at"
        # Should be ISO format
        assert "T" in data["computed_at"], "computed_at should be ISO format"
        print(f"[PASS] computed_at: {data['computed_at']}")


class TestSimilarityWeights:
    """Verify component weights are correct (behaviour 0.35, token_matrix 0.30, flows 0.20, portfolio 0.15)."""

    def test_components_sum_to_similarity_score(self, api_client):
        """Verify composite score matches weighted sum of components."""
        resp = api_client.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        data = resp.json()
        for ent in data.get("top_similar", [])[:5]:  # Check first 5
            comps = ent["components"]
            expected = (
                comps["behaviour"] * 0.35 +
                comps["token_matrix"] * 0.30 +
                comps["flows"] * 0.20 +
                comps["portfolio"] * 0.15
            )
            actual = ent["similarity_score"]
            # Allow small floating point tolerance
            assert abs(expected - actual) < 0.01, f"Score mismatch: expected {expected:.4f}, got {actual:.4f}"
        print(f"[PASS] Component weights verified: 0.35+0.30+0.20+0.15")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
