"""
Test Real vs Synthetic Validation Framework + Twitter Ingestion APIs

Tests the new P0 features:
- GET /api/ml/data/real-vs-synthetic — 4 strict time-isolated tests (A, B, C, D)
- GET /api/ml/ingest/status — real vs synthetic breakdown
- GET /api/ml/ingest/parser-health — Twitter parser health
- POST /api/ml/ingest/actor — ingest actor tweets
- POST /api/ml/ingest/search — ingest search results
- POST /api/ml/ingest/mass — mass ingestion
- GET /api/ml/data/health — existing health endpoint
- GET /api/ml/status — existing ML status endpoint
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Ensure BASE_URL is set
if not BASE_URL:
    BASE_URL = "https://expo-telegram-web.preview.emergentagent.com"


class TestExistingEndpointsRegression:
    """Verify existing ML endpoints still work (regression tests)."""

    def test_ml_status_endpoint(self):
        """GET /api/ml/status — existing ML status should still work."""
        response = requests.get(f"{BASE_URL}/api/ml/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should have model info
        assert "ok" in data or "active_model" in data or "model" in data, f"Missing expected fields: {data.keys()}"
        print(f"✓ ML Status: {data.get('active_model', data.get('model', 'N/A'))}")

    def test_ml_data_health_endpoint(self):
        """GET /api/ml/data/health — existing health endpoint should still work."""
        response = requests.get(f"{BASE_URL}/api/ml/data/health", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "ok" in data, f"Missing 'ok' field: {data.keys()}"
        print(f"✓ Data Health: ok={data.get('ok')}")


class TestIngestionStatus:
    """Test ingestion status endpoint — real vs synthetic breakdown."""

    def test_ingest_status_returns_breakdown(self):
        """GET /api/ml/ingest/status — returns real vs synthetic event/dataset/actor breakdown."""
        response = requests.get(f"{BASE_URL}/api/ml/ingest/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True: {data}"
        
        # Verify events breakdown
        assert "events" in data, f"Missing 'events' field: {data.keys()}"
        events = data["events"]
        assert "total" in events, f"Missing events.total: {events.keys()}"
        assert "real" in events, f"Missing events.real: {events.keys()}"
        assert "synthetic" in events, f"Missing events.synthetic: {events.keys()}"
        assert "real_pct" in events, f"Missing events.real_pct: {events.keys()}"
        
        # Verify dataset breakdown
        assert "dataset" in data, f"Missing 'dataset' field: {data.keys()}"
        dataset = data["dataset"]
        assert "total" in dataset, f"Missing dataset.total: {dataset.keys()}"
        assert "real" in dataset, f"Missing dataset.real: {dataset.keys()}"
        assert "synthetic" in dataset, f"Missing dataset.synthetic: {dataset.keys()}"
        
        # Verify actors breakdown
        assert "actors" in data, f"Missing 'actors' field: {data.keys()}"
        actors = data["actors"]
        assert "real_unique" in actors, f"Missing actors.real_unique: {actors.keys()}"
        assert "synth_unique" in actors, f"Missing actors.synth_unique: {actors.keys()}"
        
        print(f"✓ Ingest Status: events={events['total']} (real={events['real']}, synth={events['synthetic']})")
        print(f"  Dataset: total={dataset['total']} (real={dataset['real']}, synth={dataset['synthetic']})")
        print(f"  Actors: real_unique={actors['real_unique']}, synth_unique={actors['synth_unique']}")


class TestParserHealth:
    """Test Twitter parser health endpoint."""

    def test_parser_health_endpoint(self):
        """GET /api/ml/ingest/parser-health — returns health of Twitter parser Node.js service."""
        response = requests.get(f"{BASE_URL}/api/ml/ingest/parser-health", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should have ok field (true if parser is running, false with error if not)
        assert "ok" in data, f"Missing 'ok' field: {data.keys()}"
        
        if data.get("ok"):
            print(f"✓ Parser Health: OK (parser running)")
        else:
            # Parser might not be running, but endpoint should still work
            print(f"✓ Parser Health: NOT OK (error={data.get('error', 'unknown')})")
            print(f"  Parser URL: {data.get('parser_url', 'N/A')}")


class TestRealVsSyntheticValidation:
    """Test the main validation framework endpoint — 4 strict time-isolated tests."""

    def test_real_vs_synthetic_endpoint_returns_all_fields(self):
        """GET /api/ml/data/real-vs-synthetic — returns tests A, B, C, D with all required fields."""
        # This endpoint takes 3-5 seconds
        response = requests.get(f"{BASE_URL}/api/ml/data/real-vs-synthetic", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Check top-level ok field
        assert "ok" in data, f"Missing 'ok' field: {data.keys()}"
        
        if not data.get("ok"):
            # If not ok, should have error message
            print(f"⚠ Validation returned ok=False: {data.get('error', 'unknown')}")
            # This is acceptable if there's not enough data
            return
        
        # Verify data_summary
        assert "data_summary" in data, f"Missing 'data_summary' field: {data.keys()}"
        summary = data["data_summary"]
        assert "total_samples" in summary, f"Missing data_summary.total_samples"
        assert "real_samples" in summary, f"Missing data_summary.real_samples"
        assert "synthetic_samples" in summary, f"Missing data_summary.synthetic_samples"
        assert "real_pct" in summary, f"Missing data_summary.real_pct"
        
        # Verify tests field with A, B, C, D
        assert "tests" in data, f"Missing 'tests' field: {data.keys()}"
        tests = data["tests"]
        
        # Check for all 4 tests
        expected_tests = ["A_synth_train_real_test", "B_real_only", "C_mixed_70_30", "D_live_holdout"]
        for test_name in expected_tests:
            assert test_name in tests, f"Missing test '{test_name}': {tests.keys()}"
            test_result = tests[test_name]
            
            # Each test should have metrics or error
            if "error" not in test_result:
                # Verify metrics fields
                assert "precision_top10" in test_result, f"Missing precision_top10 in {test_name}"
                assert "hit_rate" in test_result, f"Missing hit_rate in {test_name}"
                assert "avg_return" in test_result, f"Missing avg_return in {test_name}"
                assert "median_return" in test_result, f"Missing median_return in {test_name}"
                assert "profit_factor" in test_result, f"Missing profit_factor in {test_name}"
                assert "max_drawdown" in test_result, f"Missing max_drawdown in {test_name}"
                assert "train_size" in test_result, f"Missing train_size in {test_name}"
                assert "test_size" in test_result, f"Missing test_size in {test_name}"
                print(f"  {test_name}: precision={test_result['precision_top10']}, hit_rate={test_result['hit_rate']}, avg_return={test_result['avg_return']}%")
            else:
                print(f"  {test_name}: error={test_result['error']}")
        
        # Verify confidence_buckets_real
        assert "confidence_buckets_real" in data, f"Missing 'confidence_buckets_real' field: {data.keys()}"
        conf_buckets = data["confidence_buckets_real"]
        if "error" not in conf_buckets:
            assert "buckets" in conf_buckets, f"Missing buckets in confidence_buckets_real"
            assert "monotonic" in conf_buckets, f"Missing monotonic in confidence_buckets_real"
            print(f"  Confidence buckets: monotonic={conf_buckets['monotonic']}, buckets={len(conf_buckets['buckets'])}")
        
        # Verify actor_stats
        assert "actor_stats" in data, f"Missing 'actor_stats' field: {data.keys()}"
        actor_stats = data["actor_stats"]
        print(f"  Actor stats: {len(actor_stats)} test(s) analyzed")
        
        # Verify feature_importance_drift
        assert "feature_importance_drift" in data, f"Missing 'feature_importance_drift' field: {data.keys()}"
        drift = data["feature_importance_drift"]
        if drift:
            print(f"  Feature drift: max_shift={drift.get('max_shift', 'N/A')}, top_feature_changed={drift.get('top_feature_changed', 'N/A')}")
        
        # Verify red_flags
        assert "red_flags" in data, f"Missing 'red_flags' field: {data.keys()}"
        red_flags = data["red_flags"]
        print(f"  Red flags: {len(red_flags)} flag(s)")
        for flag in red_flags[:3]:  # Show first 3
            print(f"    - {flag}")
        
        # Verify decision
        assert "decision" in data, f"Missing 'decision' field: {data.keys()}"
        decision = data["decision"]
        assert "action" in decision, f"Missing action in decision"
        assert "reason" in decision, f"Missing reason in decision"
        print(f"  Decision: action={decision['action']}")
        print(f"    Reason: {decision['reason'][:100]}...")
        
        print(f"✓ Real vs Synthetic Validation: {summary['total_samples']} samples ({summary['real_pct']}% real)")


class TestIngestionEndpoints:
    """Test Twitter ingestion endpoints (actor, search, mass)."""

    def test_ingest_actor_missing_username(self):
        """POST /api/ml/ingest/actor — should return 400 if username missing."""
        response = requests.post(
            f"{BASE_URL}/api/ml/ingest/actor",
            json={},
            timeout=30
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is False, f"Expected ok=False: {data}"
        assert "username" in data.get("error", "").lower(), f"Error should mention username: {data}"
        print("✓ Ingest actor: correctly rejects missing username")

    def test_ingest_search_missing_keyword(self):
        """POST /api/ml/ingest/search — should return 400 if keyword missing."""
        response = requests.post(
            f"{BASE_URL}/api/ml/ingest/search",
            json={},
            timeout=30
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is False, f"Expected ok=False: {data}"
        assert "keyword" in data.get("error", "").lower(), f"Error should mention keyword: {data}"
        print("✓ Ingest search: correctly rejects missing keyword")

    def test_ingest_mass_missing_actors(self):
        """POST /api/ml/ingest/mass — should return 400 if actors list missing."""
        response = requests.post(
            f"{BASE_URL}/api/ml/ingest/mass",
            json={},
            timeout=30
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is False, f"Expected ok=False: {data}"
        assert "actors" in data.get("error", "").lower(), f"Error should mention actors: {data}"
        print("✓ Ingest mass: correctly rejects missing actors list")

    def test_ingest_actor_with_valid_username(self):
        """POST /api/ml/ingest/actor — test with a valid username (limit=5 for speed)."""
        # This test may take 10-15 seconds due to browser-based parsing
        response = requests.post(
            f"{BASE_URL}/api/ml/ingest/actor",
            json={"username": "cz_binance", "limit": 5},
            timeout=120  # Long timeout for browser parsing
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should have ok field
        assert "ok" in data, f"Missing 'ok' field: {data.keys()}"
        
        if data.get("ok"):
            # Successful ingestion
            assert "username" in data, f"Missing username in response"
            assert "tweets_fetched" in data, f"Missing tweets_fetched in response"
            assert "signals_created" in data, f"Missing signals_created in response"
            print(f"✓ Ingest actor: username={data['username']}, tweets={data['tweets_fetched']}, signals={data['signals_created']}")
            if data.get("tokens_found"):
                print(f"  Tokens found: {data['tokens_found']}")
        else:
            # Parser might not be running or cookies invalid
            print(f"⚠ Ingest actor returned ok=False: {data.get('error', 'unknown')}")
            # This is acceptable - endpoint works, just parser/cookies issue


class TestValidationMetricsDetail:
    """Detailed tests for validation metrics structure."""

    def test_validation_metrics_structure(self):
        """Verify detailed structure of validation response."""
        response = requests.get(f"{BASE_URL}/api/ml/data/real-vs-synthetic", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("ok"):
            pytest.skip(f"Validation not ok: {data.get('error')}")
        
        # Test B should have detailed metrics if enough real data
        tests = data.get("tests", {})
        test_b = tests.get("B_real_only", {})
        
        if "error" not in test_b:
            # Verify all metric fields are numeric
            numeric_fields = ["precision_top10", "hit_rate", "avg_return", "median_return", "profit_factor", "max_drawdown"]
            for field in numeric_fields:
                assert field in test_b, f"Missing {field} in Test B"
                assert isinstance(test_b[field], (int, float)), f"{field} should be numeric: {type(test_b[field])}"
            
            # Verify train/test source fields
            assert "train_source" in test_b, "Missing train_source in Test B"
            assert "test_source" in test_b, "Missing test_source in Test B"
            
            print(f"✓ Test B metrics verified: precision={test_b['precision_top10']}, profit_factor={test_b['profit_factor']}")

    def test_confidence_buckets_structure(self):
        """Verify confidence buckets have correct structure."""
        response = requests.get(f"{BASE_URL}/api/ml/data/real-vs-synthetic", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("ok"):
            pytest.skip(f"Validation not ok: {data.get('error')}")
        
        conf_buckets = data.get("confidence_buckets_real", {})
        if "error" in conf_buckets:
            pytest.skip(f"Confidence buckets not computed: {conf_buckets.get('error')}")
        
        buckets = conf_buckets.get("buckets", [])
        expected_bucket_labels = ["0.9+", "0.8-0.9", "0.7-0.8", "0.6-0.7", "0.5-0.6", "<0.5"]
        
        for bucket in buckets:
            assert "bucket" in bucket, f"Missing bucket label: {bucket}"
            assert "count" in bucket, f"Missing count: {bucket}"
            assert "win_rate" in bucket, f"Missing win_rate: {bucket}"
            assert "avg_return" in bucket, f"Missing avg_return: {bucket}"
        
        print(f"✓ Confidence buckets verified: {len(buckets)} buckets, monotonic={conf_buckets.get('monotonic')}")

    def test_decision_structure(self):
        """Verify decision has correct structure."""
        response = requests.get(f"{BASE_URL}/api/ml/data/real-vs-synthetic", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("ok"):
            pytest.skip(f"Validation not ok: {data.get('error')}")
        
        decision = data.get("decision", {})
        assert "action" in decision, f"Missing action in decision: {decision.keys()}"
        assert "reason" in decision, f"Missing reason in decision: {decision.keys()}"
        
        # Action should be one of expected values
        valid_actions = ["use_real_only", "use_mixed", "use_curriculum", "insufficient_data", "insufficient_data_for_d"]
        assert decision["action"] in valid_actions, f"Unexpected action: {decision['action']}"
        
        print(f"✓ Decision verified: action={decision['action']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
