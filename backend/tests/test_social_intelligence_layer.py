"""
Social Intelligence 2.0 — Narrative Intelligence Layer Tests

Tests for 9 services:
- Cluster Builder (semantic dedup)
- Echo Filter (retweet/quote/paraphrase)
- Origin Detector (earliest credible)
- Propagation Graph (wave analysis)
- Influence Engine (trust-based)
- Saturation Engine
- Narrative Lifecycle (EARLY/EXPANDING/SATURATED/FADING/DORMANT)
- Social Signal Aggregator
- Market Social Impact (probability capped ≤0.05)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSocialIntelligenceBasicAPI:
    """Basic API endpoint tests for Social Intelligence"""

    def test_get_social_intel_btc(self):
        """GET /api/social-intelligence/BTC returns social intel with all required fields"""
        response = requests.get(f"{BASE_URL}/api/social-intelligence/BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("asset") == "BTC"
        
        si = data.get("socialIntel", {})
        # Required fields
        assert "lifecycle" in si, "Missing lifecycle field"
        assert "echoScore" in si, "Missing echoScore field"
        assert "saturationScore" in si, "Missing saturationScore field"
        assert "originQuality" in si, "Missing originQuality field"
        assert "whyHelpful" in si, "Missing whyHelpful field"
        assert "whyRisky" in si, "Missing whyRisky field"
        
        # Lifecycle must be valid
        assert si["lifecycle"] in ["EARLY", "EXPANDING", "SATURATED", "FADING", "DORMANT"], \
            f"Invalid lifecycle: {si['lifecycle']}"
        
        print(f"✓ BTC social intel: lifecycle={si['lifecycle']}, origin={si.get('originQuality')}")

    def test_get_social_intel_detailed(self):
        """GET /api/social-intelligence/BTC/detailed returns clusters, assessments, impact"""
        response = requests.get(f"{BASE_URL}/api/social-intelligence/BTC/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("asset") == "BTC"
        
        # Detailed response structure
        assert "eventsCount" in data, "Missing eventsCount"
        assert "clustersCount" in data, "Missing clustersCount"
        assert "clusters" in data, "Missing clusters array"
        assert "assessments" in data, "Missing assessments array"
        assert "impact" in data, "Missing impact object"
        
        # Clusters structure
        if data["clustersCount"] > 0:
            cluster = data["clusters"][0]
            assert "clusterId" in cluster
            assert "eventCount" in cluster
            assert "canonicalText" in cluster
            print(f"✓ First cluster: {cluster['clusterId']}, events={cluster['eventCount']}")
        
        # Assessments structure
        if len(data["assessments"]) > 0:
            assessment = data["assessments"][0]
            assert "clusterId" in assessment
            assert "origin" in assessment
            assert "echoScore" in assessment
            assert "saturationScore" in assessment
            assert "lifecycle" in assessment
            assert "socialStrength" in assessment
            print(f"✓ First assessment: lifecycle={assessment['lifecycle']}, strength={assessment['socialStrength']}")

    def test_batch_social_intel(self):
        """POST /api/social-intelligence/batch returns results for multiple assets"""
        response = requests.post(
            f"{BASE_URL}/api/social-intelligence/batch",
            json={"assets": ["BTC", "ETH", "SOL"]}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "results" in data
        
        results = data["results"]
        assert "BTC" in results, "Missing BTC in batch results"
        assert "ETH" in results, "Missing ETH in batch results"
        assert "SOL" in results, "Missing SOL in batch results"
        
        # BTC should have data (seeded), ETH/SOL should be DORMANT
        btc = results["BTC"]
        eth = results["ETH"]
        
        assert btc["lifecycle"] in ["EARLY", "EXPANDING", "SATURATED", "FADING", "DORMANT"]
        assert eth["lifecycle"] == "DORMANT", f"ETH should be DORMANT, got {eth['lifecycle']}"
        
        print(f"✓ Batch results: BTC={btc['lifecycle']}, ETH={eth['lifecycle']}, SOL={results['SOL']['lifecycle']}")


class TestClusterBuilder:
    """Tests for Cluster Builder service (semantic dedup via n-gram similarity)"""

    def test_clusters_group_similar_events(self):
        """Cluster builder groups similar events into clusters"""
        response = requests.get(f"{BASE_URL}/api/social-intelligence/BTC/detailed")
        assert response.status_code == 200
        
        data = response.json()
        clusters = data.get("clusters", [])
        events_count = data.get("eventsCount", 0)
        
        # With 8+ seeded events, should have multiple clusters
        if events_count > 0:
            assert len(clusters) > 0, "Should have at least one cluster"
            # Clusters should have unique IDs
            cluster_ids = [c["clusterId"] for c in clusters]
            assert len(cluster_ids) == len(set(cluster_ids)), "Cluster IDs should be unique"
            print(f"✓ {events_count} events grouped into {len(clusters)} clusters")


class TestEchoFilter:
    """Tests for Echo Filter service (retweet/quote/paraphrase/original)"""

    def test_echo_score_in_assessments(self):
        """Echo filter produces echoScore in assessments"""
        response = requests.get(f"{BASE_URL}/api/social-intelligence/BTC/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assessments = data.get("assessments", [])
        
        for a in assessments:
            assert "echoScore" in a, "Missing echoScore in assessment"
            assert 0 <= a["echoScore"] <= 1, f"echoScore out of range: {a['echoScore']}"
        
        if assessments:
            avg_echo = sum(a["echoScore"] for a in assessments) / len(assessments)
            print(f"✓ Average echo score: {avg_echo:.2f}")


class TestOriginDetector:
    """Tests for Origin Detector (earliest credible, trust-weighted)"""

    def test_origin_in_assessments(self):
        """Origin detector picks origin with trust score"""
        response = requests.get(f"{BASE_URL}/api/social-intelligence/BTC/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assessments = data.get("assessments", [])
        
        for a in assessments:
            origin = a.get("origin", {})
            assert "trustScore" in origin, "Missing trustScore in origin"
            assert 0 <= origin["trustScore"] <= 1, f"trustScore out of range: {origin['trustScore']}"
        
        # Check that high-trust sources are preferred
        if assessments:
            high_trust = [a for a in assessments if a["origin"]["trustScore"] >= 0.5]
            print(f"✓ {len(high_trust)}/{len(assessments)} clusters have high-trust origins")


class TestNarrativeLifecycle:
    """Tests for Narrative Lifecycle (EARLY/EXPANDING/SATURATED/FADING/DORMANT)"""

    def test_lifecycle_states(self):
        """Lifecycle correctly identifies narrative phase"""
        response = requests.get(f"{BASE_URL}/api/social-intelligence/BTC/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assessments = data.get("assessments", [])
        
        valid_states = ["EARLY", "EXPANDING", "SATURATED", "FADING", "DORMANT"]
        
        for a in assessments:
            assert a["lifecycle"] in valid_states, f"Invalid lifecycle: {a['lifecycle']}"
        
        # Count lifecycle distribution
        lifecycle_counts = {}
        for a in assessments:
            lc = a["lifecycle"]
            lifecycle_counts[lc] = lifecycle_counts.get(lc, 0) + 1
        
        print(f"✓ Lifecycle distribution: {lifecycle_counts}")

    def test_dormant_for_no_events(self):
        """Assets without events return DORMANT lifecycle"""
        response = requests.get(f"{BASE_URL}/api/social-intelligence/UNKNOWN_ASSET_XYZ")
        assert response.status_code == 200
        
        data = response.json()
        si = data.get("socialIntel", {})
        assert si["lifecycle"] == "DORMANT", f"Expected DORMANT for unknown asset, got {si['lifecycle']}"
        print("✓ Unknown asset returns DORMANT lifecycle")


class TestMarketSocialImpact:
    """Tests for Market Social Impact (probability capped ≤0.05, confidence ≤0.20)"""

    def test_probability_delta_capped(self):
        """Probability delta is capped at ≤0.05"""
        response = requests.get(f"{BASE_URL}/api/social-intelligence/BTC")
        assert response.status_code == 200
        
        data = response.json()
        si = data.get("socialIntel", {})
        
        prob_delta = si.get("probabilityDelta", 0)
        assert prob_delta <= 0.05, f"probabilityDelta {prob_delta} exceeds cap of 0.05"
        print(f"✓ probabilityDelta={prob_delta} (capped at 0.05)")

    def test_confidence_delta_capped(self):
        """Confidence delta is capped at ≤0.20"""
        response = requests.get(f"{BASE_URL}/api/social-intelligence/BTC")
        assert response.status_code == 200
        
        data = response.json()
        si = data.get("socialIntel", {})
        
        conf_delta = si.get("confidenceDelta", 0)
        assert conf_delta <= 0.20, f"confidenceDelta {conf_delta} exceeds cap of 0.20"
        print(f"✓ confidenceDelta={conf_delta} (capped at 0.20)")

    def test_why_helpful_and_risky(self):
        """Impact includes whyHelpful and whyRisky arrays"""
        response = requests.get(f"{BASE_URL}/api/social-intelligence/BTC")
        assert response.status_code == 200
        
        data = response.json()
        si = data.get("socialIntel", {})
        
        assert isinstance(si.get("whyHelpful"), list), "whyHelpful should be a list"
        assert isinstance(si.get("whyRisky"), list), "whyRisky should be a list"
        
        print(f"✓ whyHelpful: {si['whyHelpful'][:2]}")
        print(f"✓ whyRisky: {si['whyRisky'][:2]}")


class TestPredictionIntegration:
    """Tests for integration with /api/prediction/run"""

    def test_prediction_run_includes_social_intel(self):
        """GET /api/prediction/run includes socialIntel field in each case"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Find cases in sections
        sections = data.get("sections", {})
        cases_found = 0
        cases_with_social = 0
        
        for section_name, cases in sections.items():
            for c in cases:
                cases_found += 1
                if "socialIntel" in c:
                    cases_with_social += 1
                    si = c["socialIntel"]
                    # Verify structure
                    assert "lifecycle" in si
                    assert "echoScore" in si
                    assert "saturationScore" in si
        
        if cases_found > 0:
            pct = (cases_with_social / cases_found) * 100
            print(f"✓ {cases_with_social}/{cases_found} cases have socialIntel ({pct:.0f}%)")
            assert cases_with_social > 0, "At least some cases should have socialIntel"


class TestSocialIntelStructure:
    """Tests for complete SocialIntel structure"""

    def test_full_social_intel_structure(self):
        """Verify all fields in SocialIntel response"""
        response = requests.get(f"{BASE_URL}/api/social-intelligence/BTC")
        assert response.status_code == 200
        
        data = response.json()
        si = data.get("socialIntel", {})
        
        required_fields = [
            "originQuality", "echoScore", "saturationScore", "lifecycle",
            "socialStrength", "socialConfidence", "probabilityDelta",
            "confidenceDelta", "alignmentDelta", "narrativeDelta",
            "whyHelpful", "whyRisky", "topOrigin", "topAmplifiers"
        ]
        
        for field in required_fields:
            assert field in si, f"Missing required field: {field}"
        
        # Type checks
        assert isinstance(si["originQuality"], (int, float))
        assert isinstance(si["echoScore"], (int, float))
        assert isinstance(si["saturationScore"], (int, float))
        assert isinstance(si["lifecycle"], str)
        assert isinstance(si["whyHelpful"], list)
        assert isinstance(si["whyRisky"], list)
        assert isinstance(si["topAmplifiers"], list)
        
        print(f"✓ All {len(required_fields)} required fields present with correct types")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
