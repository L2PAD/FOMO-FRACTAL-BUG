"""
Decision Intelligence System - Phase 3 Tests
Dataset V3 with DQS (Data Quality Score), dedup, outcome resolution,
production feature extraction (32 alpha features with NO label leakage),
data health monitoring, and cron ingestion pipeline.

Key tests:
1. POST /api/dataset/v3/build - builds dataset v3 from enriched events
2. GET /api/dataset/v3/stats - returns full stats (quality, distribution, diversity)
3. GET /api/dataset/v3/health - anti-degradation monitoring
4. GET /api/dataset/v3/features/sample - returns 32-feature vector with NO label leakage
5. GET /api/ingestion/cron/status - cron status
6. GET /api/ml/data/real-vs-synthetic - regression check
7. GET /api/sentiment/stats - regression check
8. GET /api/enrichment/stats - regression check
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Label leakage features that MUST NOT appear in feature vector
LABEL_LEAKAGE_FEATURES = [
    "f_ret_1h", "f_ret_4h", "f_ret_24h",
    "pnl_1h", "pnl_4h", "pnl_24h",
    "ret_1h", "ret_4h", "ret_24h",
]

# Expected 32 alpha features (NO label leakage)
EXPECTED_FEATURES = [
    # Sentiment (7)
    "f_intent_bullish", "f_intent_bearish", "f_intent_hype", "f_intent_warning",
    "f_sent_conf", "f_bullish_conf", "f_bearish_conf",
    # Actor (7)
    "f_actor_score", "f_actor_hit", "f_actor_early", "f_actor_consistency",
    "f_actor_hot", "f_actor_role_driver", "f_actor_role_amplifier",
    # Price context (5) - NO ret leakage
    "f_volatility", "f_momentum", "f_regime_trending", "f_regime_overheated", "f_regime_range",
    # Signal (4)
    "f_mentions", "f_unique_actors", "f_coordination", "f_cluster_size",
    # Timing (3)
    "f_early", "f_mid", "f_late",
    # Alpha composites (6)
    "f_actor_weighted_signal", "f_momentum_alignment", "f_signal_strength",
    "f_early_bullish", "f_alpha_1", "f_alpha_2", "f_alpha_3", "f_alpha_4",
]


class TestDatasetV3Build:
    """Test POST /api/dataset/v3/build endpoint"""

    def test_build_dataset_v3(self):
        """Build dataset v3 from enriched events"""
        response = requests.post(
            f"{BASE_URL}/api/dataset/v3/build",
            json={"limit": 100},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check response structure - may have "message" if no new events
        assert "processed" in data, "Missing 'processed' field"
        
        # If there are new events, check for duplicates/errors fields
        if data.get("processed", 0) > 0 or "duplicates" in data:
            assert "duplicates" in data, "Missing 'duplicates' field"
            assert "errors" in data, "Missing 'errors' field"
            print(f"Dataset V3 build: processed={data.get('processed')}, duplicates={data.get('duplicates')}, errors={data.get('errors')}")
        else:
            # No new events case
            print(f"Dataset V3 build: {data.get('message', 'no new events')}")


class TestDatasetV3Stats:
    """Test GET /api/dataset/v3/stats endpoint"""

    def test_get_stats(self):
        """Get dataset v3 statistics"""
        response = requests.get(f"{BASE_URL}/api/dataset/v3/stats", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check total count
        total = data.get("total", 0)
        print(f"Dataset V3 total samples: {total}")
        
        if total == 0:
            pytest.skip("Empty dataset - skipping detailed stats check")
        
        # Check quality stats
        quality = data.get("quality", {})
        assert "avg_dqs" in quality, "Missing avg_dqs in quality"
        assert "high" in quality, "Missing high count in quality"
        assert "medium" in quality, "Missing medium count in quality"
        assert "low" in quality, "Missing low count in quality"
        print(f"Quality: avg_dqs={quality.get('avg_dqs')}, high={quality.get('high')}, medium={quality.get('medium')}, low={quality.get('low')}")
        
        # Check distribution stats
        distribution = data.get("distribution", {})
        assert "by_intent" in distribution, "Missing by_intent in distribution"
        assert "by_position" in distribution, "Missing by_position in distribution"
        assert "by_role" in distribution, "Missing by_role in distribution"
        assert "by_regime" in distribution, "Missing by_regime in distribution"
        print(f"Distribution: by_intent={distribution.get('by_intent')}, by_position={distribution.get('by_position')}")
        
        # Check diversity stats
        diversity = data.get("diversity", {})
        assert "actor_gini" in diversity, "Missing actor_gini in diversity"
        assert "token_gini" in diversity, "Missing token_gini in diversity"
        print(f"Diversity: actor_gini={diversity.get('actor_gini')}, token_gini={diversity.get('token_gini')}")


class TestDatasetV3Health:
    """Test GET /api/dataset/v3/health endpoint"""

    def test_get_health(self):
        """Get dataset v3 health (anti-degradation monitoring)"""
        response = requests.get(f"{BASE_URL}/api/dataset/v3/health", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check health status
        status = data.get("status")
        assert status in ["healthy", "degrading", "insufficient_data"], f"Unexpected status: {status}"
        print(f"Data health status: {status}")
        
        # Check alerts
        alerts = data.get("alerts", [])
        print(f"Health alerts: {alerts}")
        
        # Check DQS trends
        avg_dqs_24h = data.get("avg_dqs_24h", 0)
        avg_dqs_7d = data.get("avg_dqs_7d", 0)
        print(f"DQS trends: 24h={avg_dqs_24h}, 7d={avg_dqs_7d}")


class TestDatasetV3FeaturesSample:
    """Test GET /api/dataset/v3/features/sample endpoint - CRITICAL: NO LABEL LEAKAGE"""

    def test_features_sample_structure(self):
        """Get sample feature vector and verify structure"""
        response = requests.get(f"{BASE_URL}/api/dataset/v3/features/sample", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        if data.get("ok") is False:
            # May have no resolved samples
            print(f"No resolved samples: {data.get('error')}")
            pytest.skip("No resolved samples in dataset")
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        features = data.get("features", {})
        dqs = data.get("dqs", 0)
        
        print(f"Sample DQS: {dqs}")
        print(f"Feature count: {len(features)}")

    def test_no_label_leakage(self):
        """CRITICAL: Verify NO label leakage features in feature vector"""
        response = requests.get(f"{BASE_URL}/api/dataset/v3/features/sample", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        if data.get("ok") is False:
            pytest.skip("No resolved samples in dataset")
        
        features = data.get("features", {})
        feature_names = list(features.keys())
        
        # Check for label leakage
        leakage_found = []
        for leak_feature in LABEL_LEAKAGE_FEATURES:
            if leak_feature in feature_names:
                leakage_found.append(leak_feature)
            # Also check with f_ prefix
            if f"f_{leak_feature}" in feature_names:
                leakage_found.append(f"f_{leak_feature}")
        
        assert len(leakage_found) == 0, f"LABEL LEAKAGE DETECTED! Found: {leakage_found}"
        print("NO LABEL LEAKAGE - feature vector is clean")

    def test_expected_feature_count(self):
        """Verify feature count (34 alpha features as per implementation)"""
        response = requests.get(f"{BASE_URL}/api/dataset/v3/features/sample", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        if data.get("ok") is False:
            pytest.skip("No resolved samples in dataset")
        
        features = data.get("features", {})
        feature_count = len(features)
        
        # Implementation has 34 features:
        # Sentiment: 7, Actor: 7, Price context: 5, Signal: 4, Timing: 3, Alpha composites: 8
        assert feature_count == 34, f"Expected 34 features, got {feature_count}. Features: {list(features.keys())}"
        print(f"Verified: exactly 34 features present")

    def test_alpha_features_present(self):
        """Verify composite alpha features are present"""
        response = requests.get(f"{BASE_URL}/api/dataset/v3/features/sample", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        if data.get("ok") is False:
            pytest.skip("No resolved samples in dataset")
        
        features = data.get("features", {})
        
        # Check for key alpha features
        alpha_features = ["f_alpha_1", "f_early_bullish", "f_actor_weighted_signal"]
        for af in alpha_features:
            assert af in features, f"Missing alpha feature: {af}"
        
        print(f"Alpha features present: {alpha_features}")
        print(f"All features: {list(features.keys())}")


class TestCronIngestionStatus:
    """Test GET /api/ingestion/cron/status endpoint"""

    def test_cron_status(self):
        """Get cron ingestion status"""
        response = requests.get(f"{BASE_URL}/api/ingestion/cron/status", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check response structure
        assert "total_cycles" in data, "Missing total_cycles"
        assert "data_status" in data, "Missing data_status"
        assert "data_health" in data, "Missing data_health"
        
        print(f"Cron status: total_cycles={data.get('total_cycles')}")
        print(f"Data status: {data.get('data_status')}")
        print(f"Data health: {data.get('data_health', {}).get('status')}")


class TestRegressionChecks:
    """Regression tests for existing endpoints"""

    def test_real_vs_synthetic(self):
        """Regression: GET /api/ml/data/real-vs-synthetic still works"""
        response = requests.get(f"{BASE_URL}/api/ml/data/real-vs-synthetic", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        print(f"Real-vs-synthetic: {data.get('summary', 'no summary')}")

    def test_sentiment_stats(self):
        """Regression: GET /api/sentiment/stats still works"""
        response = requests.get(f"{BASE_URL}/api/sentiment/stats", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        total = data.get("total", 0)
        print(f"Sentiment stats: total={total}")

    def test_enrichment_stats(self):
        """Regression: GET /api/enrichment/stats still works"""
        response = requests.get(f"{BASE_URL}/api/enrichment/stats", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        total = data.get("total", 0)
        print(f"Enrichment stats: total={total}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
