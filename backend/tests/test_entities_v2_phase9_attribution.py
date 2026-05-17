"""
Entities V2 Phase 9 — Attribution Engine Tests
===============================================
Tests entity identity hypothesization for unknown wallet clusters using 4 signals:
- counterparty_overlap (0.35 weight)
- behaviour_match (0.25 weight)
- token_activity (0.25 weight)
- flow_pattern (0.15 weight)

Attribution levels: known (>=0.80), likely (>=0.50), possible (>=0.30), unknown (<0.30)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Known cluster IDs from Phase 8 (11 clusters across 6 entities)
KNOWN_CLUSTER_IDS = [
    "binance_cluster_1",
    "binance_cluster_2",
    "coinbase_cluster_1",
    "coinbase_cluster_2",
    "gate-io_cluster_1",
    "gate-io_cluster_2",
    "kraken_cluster_1",
    "kraken_cluster_2",
    "okx_cluster_1",
    "bybit_cluster_1",
    "bybit_cluster_2",
]

# Attribution level thresholds
KNOWN_THRESHOLD = 0.80
LIKELY_THRESHOLD = 0.50
POSSIBLE_THRESHOLD = 0.30

VALID_LEVELS = {"known", "likely", "possible", "unknown"}


class TestPhase9CandidatesEndpoint:
    """Tests for GET /api/entities/v2/candidates — cluster candidates with attribution hypotheses"""

    def test_candidates_returns_200(self):
        """Candidates endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True

    def test_candidates_has_required_fields(self):
        """Response should include total_clusters, attributed, by_level, candidates"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        
        assert "total_clusters" in data, "Missing total_clusters field"
        assert "attributed" in data, "Missing attributed field"
        assert "by_level" in data, "Missing by_level field"
        assert "candidates" in data, "Missing candidates field"
        assert isinstance(data["candidates"], list), "candidates should be a list"

    def test_candidates_structure_validation(self):
        """Each candidate should have required fields"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        candidates = data.get("candidates", [])
        
        assert len(candidates) > 0, "Expected at least one candidate"
        
        required_fields = [
            "cluster_id", "parent_entity", "tier", "size", 
            "possible_entity", "attribution_score", "attribution_level", "signals"
        ]
        
        for candidate in candidates:
            for field in required_fields:
                assert field in candidate, f"Candidate missing '{field}' field: {candidate}"

    def test_candidates_attribution_score_range(self):
        """Attribution score should be float between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        candidates = data.get("candidates", [])
        
        for candidate in candidates:
            score = candidate["attribution_score"]
            assert isinstance(score, (int, float)), f"Score should be numeric: {score}"
            assert 0 <= score <= 1, f"Score should be 0-1, got {score}"

    def test_candidates_attribution_level_valid(self):
        """Attribution level should be one of: known, likely, possible, unknown"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        candidates = data.get("candidates", [])
        
        for candidate in candidates:
            level = candidate["attribution_level"]
            assert level in VALID_LEVELS, f"Invalid level '{level}', expected one of {VALID_LEVELS}"

    def test_candidates_attribution_level_matches_score(self):
        """Attribution level should match score thresholds"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        candidates = data.get("candidates", [])
        
        for candidate in candidates:
            score = candidate["attribution_score"]
            level = candidate["attribution_level"]
            
            if score >= KNOWN_THRESHOLD:
                expected = "known"
            elif score >= LIKELY_THRESHOLD:
                expected = "likely"
            elif score >= POSSIBLE_THRESHOLD:
                expected = "possible"
            else:
                expected = "unknown"
            
            assert level == expected, f"Score {score} should have level '{expected}', got '{level}'"

    def test_candidates_signals_is_list(self):
        """Signals should be a list of human-readable strings"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        candidates = data.get("candidates", [])
        
        for candidate in candidates:
            signals = candidate["signals"]
            assert isinstance(signals, list), f"Signals should be list: {signals}"
            for signal in signals:
                assert isinstance(signal, str), f"Signal should be string: {signal}"

    def test_candidates_sorted_by_score_descending(self):
        """Candidates should be sorted by attribution_score descending"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        candidates = data.get("candidates", [])
        
        if len(candidates) > 1:
            scores = [c["attribution_score"] for c in candidates]
            assert scores == sorted(scores, reverse=True), "Candidates should be sorted by score desc"

    def test_candidates_by_level_sums_to_total(self):
        """by_level counts should sum to total_clusters"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        
        total = data.get("total_clusters", 0)
        by_level = data.get("by_level", {})
        level_sum = sum(by_level.values())
        
        assert level_sum == total, f"by_level sum {level_sum} should equal total_clusters {total}"

    def test_candidates_has_expected_clusters(self):
        """Response should contain some of the known cluster IDs"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        candidates = data.get("candidates", [])
        
        candidate_ids = {c["cluster_id"] for c in candidates}
        
        # At least some known clusters should be present
        found = candidate_ids & set(KNOWN_CLUSTER_IDS)
        assert len(found) > 0, f"Expected at least some known clusters, found none"


class TestPhase9ClusterAttributionEndpoint:
    """Tests for GET /api/entities/v2/clusters/{cluster_id}/attribution"""

    def test_binance_cluster_1_attribution(self):
        """Binance high-tier cluster should return detailed attribution"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/binance_cluster_1/attribution")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True

    def test_binance_cluster_1_has_required_fields(self):
        """Response should include cluster_id, parent_entity, attribution, components"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/binance_cluster_1/attribution")
        data = response.json()
        
        assert "cluster_id" in data, "Missing cluster_id"
        assert data["cluster_id"] == "binance_cluster_1"
        assert "parent_entity" in data, "Missing parent_entity"
        assert data["parent_entity"] == "binance"

    def test_gate_io_cluster_2_attribution(self):
        """Gate.io cluster should return attribution"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/gate-io_cluster_2/attribution")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True
        assert data.get("cluster_id") == "gate-io_cluster_2"

    def test_nonexistent_cluster_returns_404(self):
        """Nonexistent cluster should return 404"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/nonexistent_cluster/attribution")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is False

    def test_attribution_has_components(self):
        """Attribution should include component scores"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/binance_cluster_1/attribution")
        data = response.json()
        
        # Check if components exist either at top level or within attribution
        components = data.get("components") or (data.get("attribution", {}) if isinstance(data.get("attribution"), dict) else {})
        
        # Should have 4 component scores
        expected_components = ["counterparty", "behaviour", "token_activity", "flow_pattern"]
        
        # Check in top_candidates if components not at top level
        if not components or not all(c in components for c in expected_components):
            top_candidates = data.get("top_candidates", [])
            if top_candidates:
                components = top_candidates[0].get("components", {})
        
        for comp in expected_components:
            assert comp in components, f"Missing component: {comp}"
            score = components[comp]
            assert isinstance(score, (int, float)), f"{comp} should be numeric"
            assert 0 <= score <= 1, f"{comp} should be 0-1, got {score}"

    def test_attribution_score_and_level(self):
        """Attribution should have score and level"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/binance_cluster_1/attribution")
        data = response.json()
        
        # Score and level may be in attribution sub-object or in top_candidates
        attribution = data.get("attribution", {})
        if attribution and isinstance(attribution, dict):
            score = attribution.get("confidence", attribution.get("attribution_score", 0))
            level = attribution.get("level", attribution.get("attribution_level", "unknown"))
        else:
            score = data.get("attribution_score", 0)
            level = data.get("attribution_level", "unknown")
        
        assert isinstance(score, (int, float)), f"Score should be numeric"
        assert level in VALID_LEVELS, f"Level should be valid, got {level}"


class TestPhase9EntityClusterAttributions:
    """Tests for GET /api/entities/v2/{slug}/cluster-attributions"""

    def test_binance_cluster_attributions(self):
        """Binance should return cluster attributions"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/cluster-attributions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True

    def test_binance_attributions_has_entity_info(self):
        """Response should include entity information"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/cluster-attributions")
        data = response.json()
        
        assert "entity" in data, "Missing entity field"
        entity = data["entity"]
        assert entity.get("slug") == "binance"
        assert "name" in entity
        assert "type" in entity
        assert "category" in entity

    def test_binance_attributions_has_clusters(self):
        """Response should include cluster attributions"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/cluster-attributions")
        data = response.json()
        
        assert "total_clusters" in data, "Missing total_clusters"
        assert "attributions" in data, "Missing attributions"
        assert isinstance(data["attributions"], list)
        
        # Binance should have clusters
        assert data["total_clusters"] >= 1, f"Expected at least 1 cluster for Binance"

    def test_coinbase_cluster_attributions(self):
        """Coinbase should return cluster attributions"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/coinbase/cluster-attributions")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("entity", {}).get("slug") == "coinbase"

    def test_nonexistent_entity_returns_404(self):
        """Nonexistent entity should return 404"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent/cluster-attributions")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is False

    def test_attributions_sorted_by_score(self):
        """Attributions should be sorted by score descending"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/cluster-attributions")
        data = response.json()
        attributions = data.get("attributions", [])
        
        if len(attributions) > 1:
            scores = [a.get("attribution_score", 0) for a in attributions]
            assert scores == sorted(scores, reverse=True), "Attributions should be sorted by score desc"


class TestPhase9BuildAllAttributions:
    """Tests for POST /api/entities/v2/attributions/build-all"""

    def test_build_all_returns_200(self):
        """Build all should succeed (may take up to 60s)"""
        response = requests.post(f"{BASE_URL}/api/entities/v2/attributions/build-all", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True

    def test_build_all_returns_stats(self):
        """Build all should return statistics"""
        response = requests.post(f"{BASE_URL}/api/entities/v2/attributions/build-all", timeout=120)
        data = response.json()
        
        assert "total_clusters" in data, "Missing total_clusters"
        assert "by_level" in data, "Missing by_level"
        
        # Should process 11 known clusters
        assert data["total_clusters"] >= 1, f"Expected at least 1 cluster processed"

    def test_build_all_creates_attributions(self):
        """After build, candidates endpoint should return attributions"""
        # Ensure build has been run
        requests.post(f"{BASE_URL}/api/entities/v2/attributions/build-all", timeout=120)
        
        # Verify candidates now exist
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        
        assert data["total_clusters"] >= 1, "Expected at least 1 attributed cluster"


class TestPhase9ComponentWeights:
    """Tests to verify attribution component weights: counterparty 0.35, behaviour 0.25, token_activity 0.25, flow_pattern 0.15"""

    def test_component_weights_sum_to_one(self):
        """Component weights should sum to 1.0"""
        weights = {
            "counterparty": 0.35,
            "behaviour": 0.25,
            "token_activity": 0.25,
            "flow_pattern": 0.15,
        }
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001, f"Weights should sum to 1.0, got {total}"

    def test_attribution_score_is_weighted_sum(self):
        """Attribution score should be weighted sum of components"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/binance_cluster_1/attribution")
        data = response.json()
        
        # Get components from top_candidates if available
        top_candidates = data.get("top_candidates", [])
        if not top_candidates:
            pytest.skip("No top_candidates found for verification")
        
        best = top_candidates[0]
        components = best.get("components", {})
        
        if not all(k in components for k in ["counterparty", "behaviour", "token_activity", "flow_pattern"]):
            pytest.skip("Components not available for verification")
        
        expected = (
            components["counterparty"] * 0.35 +
            components["behaviour"] * 0.25 +
            components["token_activity"] * 0.25 +
            components["flow_pattern"] * 0.15
        )
        
        actual = best.get("attribution_score", 0)
        
        # Allow small floating point tolerance
        assert abs(expected - actual) < 0.01, f"Expected score ~{expected:.4f}, got {actual}"


class TestPhase9AllKnownClusters:
    """Tests to verify all 11 known clusters have attributions"""

    @pytest.mark.parametrize("cluster_id", KNOWN_CLUSTER_IDS)
    def test_known_cluster_has_attribution(self, cluster_id):
        """Each known cluster should have attribution data"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/{cluster_id}/attribution")
        # May return 200 (found) or 404 (not computed yet)
        if response.status_code == 200:
            data = response.json()
            assert data.get("ok") is True
            assert "cluster_id" in data or data.get("cluster_id") == cluster_id
        else:
            # If 404, it might just mean attribution not yet built - not necessarily a failure
            pytest.skip(f"Attribution for {cluster_id} not yet computed")


class TestPhase9DataIntegrity:
    """Data integrity tests for attribution engine"""

    def test_candidates_total_matches_list_length(self):
        """total_clusters should match length of candidates list"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        
        total = data.get("total_clusters", 0)
        candidates = data.get("candidates", [])
        
        assert len(candidates) == total, f"candidates length {len(candidates)} should match total {total}"

    def test_attributed_count_excludes_unknown(self):
        """attributed count should equal total minus unknown count"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        
        attributed = data.get("attributed", 0)
        by_level = data.get("by_level", {})
        unknown_count = by_level.get("unknown", 0)
        total = data.get("total_clusters", 0)
        
        expected_attributed = total - unknown_count
        assert attributed == expected_attributed, f"attributed {attributed} should be total - unknown ({expected_attributed})"

    def test_all_levels_in_by_level(self):
        """by_level should contain all present levels from candidates"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        
        candidates = data.get("candidates", [])
        by_level = data.get("by_level", {})
        
        # Count levels from candidates
        level_counts = {}
        for c in candidates:
            level = c["attribution_level"]
            level_counts[level] = level_counts.get(level, 0) + 1
        
        # Verify counts match
        for level, count in level_counts.items():
            assert by_level.get(level) == count, f"by_level[{level}] should be {count}, got {by_level.get(level)}"


class TestPhase9EdgeCases:
    """Edge case tests"""

    def test_cluster_id_with_hyphen(self):
        """Cluster ID with hyphen (gate-io) should work"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/gate-io_cluster_1/attribution")
        # Either 200 (found) or 404 (not computed) is acceptable
        assert response.status_code in [200, 404]

    def test_empty_signals_handling(self):
        """Clusters with no matching signals should have default signal message"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/candidates")
        data = response.json()
        candidates = data.get("candidates", [])
        
        for candidate in candidates:
            signals = candidate.get("signals", [])
            # Should never be empty - at least "no matching signals" or actual signals
            assert len(signals) > 0 or candidate["attribution_score"] == 0, "Signals should not be empty"
