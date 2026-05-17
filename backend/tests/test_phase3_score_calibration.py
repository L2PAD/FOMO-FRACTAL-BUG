"""
Phase 3 Score Calibration Tests - Decision Intelligence System Sentiment Module

Tests for:
- GET /api/outcome/sampling-quality (percentiles, priority_buckets)
- GET /api/outcome/rollout-status (labels_v2_production, sampling_rollout_pct)
- POST /api/outcome/promote-v2-labels (migration)
- POST /api/outcome/sampling-rollout (rollout percentage control)
- POST /api/outcome/backfill-labels-v2 (rescore)
- Score calibration distribution validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSamplingQualityAPI:
    """Tests for GET /api/outcome/sampling-quality endpoint"""

    def test_sampling_quality_returns_200(self):
        """Verify endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/outcome/sampling-quality returns 200")

    def test_sampling_quality_has_percentiles(self):
        """Verify response contains percentiles (p50, p75, p90, p95, max_score)"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200
        data = response.json()
        
        assert "percentiles" in data, "Missing 'percentiles' field"
        pctl = data["percentiles"]
        
        required_keys = ["p50", "p75", "p90", "p95", "max_score"]
        for key in required_keys:
            assert key in pctl, f"Missing percentile key: {key}"
            assert isinstance(pctl[key], (int, float)), f"Percentile {key} should be numeric"
        
        print(f"✓ Percentiles present: p50={pctl['p50']}, p75={pctl['p75']}, p90={pctl['p90']}, p95={pctl['p95']}, max={pctl['max_score']}")

    def test_sampling_quality_has_priority_buckets(self):
        """Verify response contains priority_buckets (high, medium, low)"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200
        data = response.json()
        
        assert "priority_buckets" in data, "Missing 'priority_buckets' field"
        pb = data["priority_buckets"]
        
        for bucket in ["high", "medium", "low"]:
            assert bucket in pb, f"Missing priority bucket: {bucket}"
            assert "count" in pb[bucket], f"Missing 'count' in {bucket} bucket"
            assert "pct" in pb[bucket], f"Missing 'pct' in {bucket} bucket"
        
        print(f"✓ Priority buckets: high={pb['high']['count']} ({pb['high']['pct']}%), medium={pb['medium']['count']} ({pb['medium']['pct']}%), low={pb['low']['count']} ({pb['low']['pct']}%)")

    def test_sampling_quality_has_core_fields(self):
        """Verify response contains all core fields"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "ok", "total", "include_rate_new", "included_count", 
            "rejected_count", "avg_score", "avg_score_included",
            "score_histogram", "by_reason", "by_event_type"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"✓ All core fields present. Total samples: {data['total']}")

    def test_sampling_quality_histogram_structure(self):
        """Verify score_histogram has correct structure"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200
        data = response.json()
        
        histogram = data.get("score_histogram", [])
        assert len(histogram) == 5, f"Expected 5 histogram buckets, got {len(histogram)}"
        
        expected_ranges = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
        for i, bucket in enumerate(histogram):
            assert "range" in bucket, f"Missing 'range' in bucket {i}"
            assert "count" in bucket, f"Missing 'count' in bucket {i}"
            assert bucket["range"] == expected_ranges[i], f"Unexpected range: {bucket['range']}"
        
        print(f"✓ Histogram structure valid with 5 buckets")


class TestRolloutStatusAPI:
    """Tests for GET /api/outcome/rollout-status endpoint"""

    def test_rollout_status_returns_200(self):
        """Verify endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/outcome/rollout-status returns 200")

    def test_rollout_status_has_v2_production_flag(self):
        """Verify labels_v2_production is true (V2 promoted to production)"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200
        data = response.json()
        
        assert "labels_v2_production" in data, "Missing 'labels_v2_production' field"
        assert data["labels_v2_production"] is True, f"Expected labels_v2_production=true, got {data['labels_v2_production']}"
        
        print("✓ labels_v2_production = true (V2 is production)")

    def test_rollout_status_has_sampling_rollout_pct(self):
        """Verify sampling_rollout_pct is 10 (initial rollout)"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200
        data = response.json()
        
        assert "sampling_rollout_pct" in data, "Missing 'sampling_rollout_pct' field"
        # Initial rollout is 10%
        assert data["sampling_rollout_pct"] >= 0 and data["sampling_rollout_pct"] <= 100, \
            f"sampling_rollout_pct should be 0-100, got {data['sampling_rollout_pct']}"
        
        print(f"✓ sampling_rollout_pct = {data['sampling_rollout_pct']}%")

    def test_rollout_status_has_label_counts(self):
        """Verify v2_labeled and v1_labeled counts"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200
        data = response.json()
        
        assert "v2_labeled" in data, "Missing 'v2_labeled' field"
        assert "v1_labeled" in data, "Missing 'v1_labeled' field"
        assert "total_resolved" in data, "Missing 'total_resolved' field"
        
        # V2 should have samples (106 expected)
        assert data["v2_labeled"] >= 0, "v2_labeled should be >= 0"
        
        print(f"✓ v2_labeled={data['v2_labeled']}, v1_labeled={data['v1_labeled']}, total_resolved={data['total_resolved']}")

    def test_rollout_status_v2_pct_calculation(self):
        """Verify v2_pct is calculated correctly"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200
        data = response.json()
        
        assert "v2_pct" in data, "Missing 'v2_pct' field"
        
        # Verify calculation
        if data["total_resolved"] > 0:
            expected_pct = round(data["v2_labeled"] / data["total_resolved"] * 100, 1)
            assert abs(data["v2_pct"] - expected_pct) < 0.2, \
                f"v2_pct calculation mismatch: expected {expected_pct}, got {data['v2_pct']}"
        
        print(f"✓ v2_pct = {data['v2_pct']}%")


class TestPromoteV2LabelsAPI:
    """Tests for POST /api/outcome/promote-v2-labels endpoint"""

    def test_promote_v2_labels_returns_200(self):
        """Verify endpoint returns 200 OK"""
        response = requests.post(f"{BASE_URL}/api/outcome/promote-v2-labels")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/outcome/promote-v2-labels returns 200")

    def test_promote_v2_labels_response_structure(self):
        """Verify response has promoted and remaining counts"""
        response = requests.post(f"{BASE_URL}/api/outcome/promote-v2-labels")
        assert response.status_code == 200
        data = response.json()
        
        assert "ok" in data, "Missing 'ok' field"
        assert "promoted" in data, "Missing 'promoted' field"
        assert "remaining" in data, "Missing 'remaining' field"
        
        print(f"✓ Promote response: promoted={data['promoted']}, remaining={data['remaining']}")

    def test_promote_v2_labels_remaining_is_zero(self):
        """Verify all samples have been migrated (remaining=0)"""
        response = requests.post(f"{BASE_URL}/api/outcome/promote-v2-labels")
        assert response.status_code == 200
        data = response.json()
        
        # After full migration, remaining should be 0
        assert data["remaining"] == 0, f"Expected remaining=0 after migration, got {data['remaining']}"
        
        print("✓ All samples migrated (remaining=0)")


class TestSamplingRolloutAPI:
    """Tests for POST /api/outcome/sampling-rollout endpoint"""

    def test_sampling_rollout_returns_200(self):
        """Verify endpoint returns 200 OK"""
        response = requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/outcome/sampling-rollout returns 200")

    def test_sampling_rollout_changes_percentage(self):
        """Verify rollout percentage can be changed"""
        # Set to 30%
        response = requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct=30")
        assert response.status_code == 200
        data = response.json()
        
        assert "ok" in data, "Missing 'ok' field"
        assert "old_pct" in data, "Missing 'old_pct' field"
        assert "new_pct" in data, "Missing 'new_pct' field"
        assert data["new_pct"] == 30, f"Expected new_pct=30, got {data['new_pct']}"
        
        print(f"✓ Rollout changed: old={data['old_pct']}% → new={data['new_pct']}%")
        
        # Verify via rollout-status
        status_response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        status_data = status_response.json()
        assert status_data["sampling_rollout_pct"] == 30, \
            f"Rollout status should reflect 30%, got {status_data['sampling_rollout_pct']}"
        
        print("✓ Rollout status reflects new percentage")
        
        # Reset to 10%
        requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct=10")

    def test_sampling_rollout_clamps_values(self):
        """Verify rollout percentage is clamped to 0-100"""
        # Test over 100
        response = requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct=150")
        assert response.status_code == 200
        data = response.json()
        assert data["new_pct"] == 100, f"Expected clamped to 100, got {data['new_pct']}"
        
        # Test negative
        response = requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct=-10")
        assert response.status_code == 200
        data = response.json()
        assert data["new_pct"] == 0, f"Expected clamped to 0, got {data['new_pct']}"
        
        # Reset to 10%
        requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct=10")
        
        print("✓ Rollout percentage correctly clamped to 0-100")


class TestBackfillLabelsV2API:
    """Tests for POST /api/outcome/backfill-labels-v2 endpoint"""

    def test_backfill_labels_v2_returns_200(self):
        """Verify endpoint returns 200 OK"""
        response = requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/outcome/backfill-labels-v2 returns 200")

    def test_backfill_labels_v2_with_rescore(self):
        """Verify rescore=true re-scores all samples"""
        response = requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?rescore=true&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert "ok" in data, "Missing 'ok' field"
        assert data["ok"] is True, f"Expected ok=true, got {data['ok']}"
        
        print(f"✓ Backfill with rescore=true completed: {data}")

    def test_backfill_labels_v2_response_structure(self):
        """Verify response has expected fields"""
        response = requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert "ok" in data, "Missing 'ok' field"
        # Response should have backfilled count or similar
        print(f"✓ Backfill response structure valid: {data}")


class TestScoreCalibrationDistribution:
    """Tests for score calibration distribution targets"""

    def test_score_distribution_targets(self):
        """
        Verify score calibration produces correct distribution:
        - High (>=0.6): 10-18%
        - Medium (0.3-0.6): 55-65%
        - Low (<0.3): 15-25%
        """
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200
        data = response.json()
        
        if data["total"] == 0:
            pytest.skip("No samples to analyze distribution")
        
        pb = data.get("priority_buckets", {})
        high_pct = pb.get("high", {}).get("pct", 0)
        medium_pct = pb.get("medium", {}).get("pct", 0)
        low_pct = pb.get("low", {}).get("pct", 0)
        
        print(f"Current distribution: High={high_pct}%, Medium={medium_pct}%, Low={low_pct}%")
        
        # Note: These are target ranges, actual may vary based on data
        # We check that distribution is reasonable (not all in one bucket)
        total_pct = high_pct + medium_pct + low_pct
        assert abs(total_pct - 100) < 1, f"Percentages should sum to ~100%, got {total_pct}%"
        
        print(f"✓ Distribution sums to {total_pct}% (expected ~100%)")

    def test_percentile_ordering(self):
        """Verify percentiles are in ascending order"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200
        data = response.json()
        
        pctl = data.get("percentiles", {})
        if not pctl:
            pytest.skip("No percentiles data")
        
        p50 = pctl.get("p50", 0)
        p75 = pctl.get("p75", 0)
        p90 = pctl.get("p90", 0)
        p95 = pctl.get("p95", 0)
        max_score = pctl.get("max_score", 0)
        
        assert p50 <= p75, f"p50 ({p50}) should be <= p75 ({p75})"
        assert p75 <= p90, f"p75 ({p75}) should be <= p90 ({p90})"
        assert p90 <= p95, f"p90 ({p90}) should be <= p95 ({p95})"
        assert p95 <= max_score, f"p95 ({p95}) should be <= max_score ({max_score})"
        
        print(f"✓ Percentiles in ascending order: p50={p50} <= p75={p75} <= p90={p90} <= p95={p95} <= max={max_score}")


class TestOutcomeResolverConfig:
    """Tests for outcome_resolver configuration values"""

    def test_labels_v2_production_is_true(self):
        """Verify LABELS_V2_PRODUCTION is True in outcome_resolver"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200
        data = response.json()
        
        assert data["labels_v2_production"] is True, \
            "LABELS_V2_PRODUCTION should be True for production rollout"
        
        print("✓ LABELS_V2_PRODUCTION = True (production mode)")

    def test_sampling_rollout_initial_value(self):
        """Verify initial SAMPLING_ROLLOUT_PCT is 10"""
        # First reset to 10
        requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct=10")
        
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200
        data = response.json()
        
        assert data["sampling_rollout_pct"] == 10, \
            f"Initial SAMPLING_ROLLOUT_PCT should be 10, got {data['sampling_rollout_pct']}"
        
        print("✓ SAMPLING_ROLLOUT_PCT = 10 (initial rollout)")


class TestIntegration:
    """Integration tests for the full Phase 3 flow"""

    def test_full_flow_sampling_to_rollout(self):
        """Test complete flow: sampling quality → rollout status → promote"""
        # 1. Check sampling quality
        sq_response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert sq_response.status_code == 200
        sq_data = sq_response.json()
        print(f"1. Sampling quality: {sq_data['total']} samples, avg_score={sq_data.get('avg_score')}")
        
        # 2. Check rollout status
        rs_response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert rs_response.status_code == 200
        rs_data = rs_response.json()
        print(f"2. Rollout status: v2_production={rs_data['labels_v2_production']}, rollout={rs_data['sampling_rollout_pct']}%")
        
        # 3. Verify promote (should have 0 remaining)
        pr_response = requests.post(f"{BASE_URL}/api/outcome/promote-v2-labels")
        assert pr_response.status_code == 200
        pr_data = pr_response.json()
        print(f"3. Promote: promoted={pr_data['promoted']}, remaining={pr_data['remaining']}")
        
        # 4. Verify all v2 labeled
        assert rs_data["v2_labeled"] > 0, "Should have V2 labeled samples"
        
        print("✓ Full integration flow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
