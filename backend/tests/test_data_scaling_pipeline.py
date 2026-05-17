"""
Data Scaling Pipeline Tests — Actor Discovery, Signal Expansion, Smart Dedup, Relative Labeling, Gini Monitoring

Goal: scale from 406→1500+ samples, 20→100+ actors, 3→20+ tokens
Key: reduce top3_dep from 194% to <80%

Tests:
- POST /api/ml/data/scale — full pipeline
- GET /api/ml/data/discover/token-first — actor discovery
- GET /api/ml/data/discover/comention — co-mention graph
- POST /api/ml/data/expand — signal expansion
- POST /api/ml/data/dedup — smart dedup v2
- POST /api/ml/data/build-dataset — relative BTC labeling
- GET /api/ml/data/health — Gini coefficients
- GET /api/ml/data/sanity-check — pre-retrain checks
- Regression: GET /api/ml/live/dashboard, GET /api/ml/decision, GET /api/ml/status
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDataScalingDiscovery:
    """Actor discovery endpoints tests"""
    
    def test_discover_token_first(self):
        """GET /api/ml/data/discover/token-first — lists current actors and token coverage"""
        response = requests.get(f"{BASE_URL}/api/ml/data/discover/token-first", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify structure
        assert "current_actors" in data, "Missing current_actors count"
        assert "actors" in data, "Missing actors list"
        assert "token_coverage" in data, "Missing token_coverage"
        
        # Verify data quality (based on context: 104 actors expected)
        assert data["current_actors"] >= 50, f"Expected >=50 actors, got {data['current_actors']}"
        assert isinstance(data["actors"], list), "actors should be a list"
        assert isinstance(data["token_coverage"], dict), "token_coverage should be a dict"
        
        print(f"✓ Token-first discovery: {data['current_actors']} actors, {len(data['token_coverage'])} tokens")
        print(f"  Top tokens by coverage: {dict(list(data['token_coverage'].items())[:5])}")
    
    def test_discover_comention(self):
        """GET /api/ml/data/discover/comention — co-mention graph with shared tokens"""
        response = requests.get(f"{BASE_URL}/api/ml/data/discover/comention", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify structure
        assert "actor_count" in data, "Missing actor_count"
        assert "comention_pairs" in data, "Missing comention_pairs"
        assert "highly_connected" in data, "Missing highly_connected"
        
        # Verify co-mention pairs structure
        if data["comention_pairs"]:
            pair = data["comention_pairs"][0]
            assert "actor_a" in pair, "Missing actor_a in pair"
            assert "actor_b" in pair, "Missing actor_b in pair"
            assert "shared_tokens" in pair, "Missing shared_tokens in pair"
            assert "overlap" in pair, "Missing overlap in pair"
            # Pairs should have 3+ shared tokens
            assert pair["overlap"] >= 3, f"Expected overlap >= 3, got {pair['overlap']}"
        
        print(f"✓ Co-mention discovery: {data['actor_count']} actors")
        print(f"  Co-mention pairs: {len(data['comention_pairs'])}")
        print(f"  Highly connected actors (8+ tokens): {len(data['highly_connected'])}")
        if data["comention_pairs"]:
            top_pair = data["comention_pairs"][0]
            print(f"  Top pair: {top_pair['actor_a']} ↔ {top_pair['actor_b']} ({top_pair['overlap']} shared tokens)")


class TestDataScalingExpansion:
    """Signal expansion and dedup tests"""
    
    def test_expand_signals(self):
        """POST /api/ml/data/expand — generates expanded signals with new actors/tokens"""
        # Use small target for testing to avoid long runtime
        payload = {"target_signals": 100, "time_window_days": 7}
        response = requests.post(f"{BASE_URL}/api/ml/data/expand", json=payload, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify structure
        assert "generated" in data, "Missing generated count"
        assert "new_actors_added" in data, "Missing new_actors_added"
        assert "new_tokens_added" in data, "Missing new_tokens_added"
        assert "total_actors_now" in data, "Missing total_actors_now"
        assert "total_tokens_now" in data, "Missing total_tokens_now"
        assert "token_distribution" in data, "Missing token_distribution"
        assert "actor_distribution_top10" in data, "Missing actor_distribution_top10"
        
        # Verify expansion happened
        assert data["generated"] >= 0, f"Expected generated >= 0, got {data['generated']}"
        
        print(f"✓ Signal expansion: {data['generated']} signals generated")
        print(f"  New actors: {data['new_actors_added']}, New tokens: {data['new_tokens_added']}")
        print(f"  Total actors now: {data['total_actors_now']}, Total tokens now: {data['total_tokens_now']}")
        print(f"  Token distribution (top 5): {dict(list(data['token_distribution'].items())[:5])}")
    
    def test_dedup_signals(self):
        """POST /api/ml/data/dedup — smart dedup v2 with text hash"""
        response = requests.post(f"{BASE_URL}/api/ml/data/dedup", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify structure
        assert "total_checked" in data, "Missing total_checked"
        assert "duplicates_found" in data, "Missing duplicates_found"
        assert "deleted" in data, "Missing deleted"
        assert "remaining" in data, "Missing remaining"
        assert "dedup_pct" in data, "Missing dedup_pct"
        
        # Verify dedup percentage is reasonable (sanity check: <15%)
        assert data["dedup_pct"] < 15, f"Dedup percentage too high: {data['dedup_pct']}% (expected <15%)"
        
        print(f"✓ Smart dedup v2: {data['total_checked']} checked, {data['duplicates_found']} duplicates")
        print(f"  Deleted: {data['deleted']}, Remaining: {data['remaining']}")
        print(f"  Dedup percentage: {data['dedup_pct']}%")


class TestDataScalingDataset:
    """Dataset building and labeling tests"""
    
    def test_build_dataset(self):
        """POST /api/ml/data/build-dataset — relative BTC labeling + class balancing"""
        response = requests.post(f"{BASE_URL}/api/ml/data/build-dataset", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify structure
        assert "total_events" in data, "Missing total_events"
        assert "valid_samples" in data, "Missing valid_samples"
        assert "tradeable" in data, "Missing tradeable count"
        assert "noise" in data, "Missing noise count"
        assert "balanced_total" in data, "Missing balanced_total"
        assert "tradeable_ratio" in data, "Missing tradeable_ratio"
        assert "unique_actors" in data, "Missing unique_actors"
        assert "unique_tokens" in data, "Missing unique_tokens"
        
        # Verify tradeable_ratio is in expected range (10-30%)
        ratio = data["tradeable_ratio"]
        assert 0.10 <= ratio <= 0.30, f"Tradeable ratio {ratio} not in expected range 0.10-0.30"
        
        print(f"✓ Dataset built: {data['balanced_total']} samples")
        print(f"  Tradeable: {data['tradeable']}, Noise: {data['noise']}")
        print(f"  Tradeable ratio: {ratio:.2%}")
        print(f"  Unique actors: {data['unique_actors']}, Unique tokens: {data['unique_tokens']}")


class TestDataScalingHealth:
    """Data health and Gini coefficient tests"""
    
    def test_data_health_v2(self):
        """GET /api/ml/data/health — Gini coefficients for actor/token concentration"""
        response = requests.get(f"{BASE_URL}/api/ml/data/health", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify structure
        assert "events" in data, "Missing events section"
        assert "dataset" in data, "Missing dataset section"
        assert "concentration" in data, "Missing concentration section"
        
        # Verify events section
        events = data["events"]
        assert "total" in events, "Missing events.total"
        assert "original" in events, "Missing events.original"
        assert "expanded" in events, "Missing events.expanded"
        assert "unique_actors" in events, "Missing events.unique_actors"
        assert "unique_tokens" in events, "Missing events.unique_tokens"
        
        # Verify dataset section
        dataset = data["dataset"]
        assert "total" in dataset, "Missing dataset.total"
        assert "tradeable" in dataset, "Missing dataset.tradeable"
        assert "tradeable_ratio" in dataset, "Missing dataset.tradeable_ratio"
        
        # Verify concentration section (Gini coefficients)
        conc = data["concentration"]
        assert "actor_gini_events" in conc, "Missing actor_gini_events"
        assert "token_gini_events" in conc, "Missing token_gini_events"
        assert "actor_gini_ok" in conc, "Missing actor_gini_ok"
        assert "token_gini_ok" in conc, "Missing token_gini_ok"
        
        # Verify Gini < 0.5 for both actors and tokens
        actor_gini = conc["actor_gini_events"]
        token_gini = conc["token_gini_events"]
        assert actor_gini < 0.5, f"Actor Gini {actor_gini} >= 0.5 (too concentrated)"
        assert token_gini < 0.5, f"Token Gini {token_gini} >= 0.5 (too concentrated)"
        assert conc["actor_gini_ok"] is True, "actor_gini_ok should be True"
        assert conc["token_gini_ok"] is True, "token_gini_ok should be True"
        
        print(f"✓ Data health v2:")
        print(f"  Events: {events['total']} total ({events['original']} original, {events['expanded']} expanded)")
        print(f"  Actors: {events['unique_actors']}, Tokens: {events['unique_tokens']}")
        print(f"  Dataset: {dataset['total']} samples, tradeable_ratio: {dataset['tradeable_ratio']:.2%}")
        print(f"  Gini coefficients: actor={actor_gini:.4f}, token={token_gini:.4f}")
        print(f"  Gini OK: actor={conc['actor_gini_ok']}, token={conc['token_gini_ok']}")


class TestDataScalingSanityCheck:
    """Pre-retrain sanity checks"""
    
    def test_sanity_check(self):
        """GET /api/ml/data/sanity-check — pre-retrain checks"""
        response = requests.get(f"{BASE_URL}/api/ml/data/sanity-check", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify structure
        assert "ready_for_retrain" in data, "Missing ready_for_retrain"
        assert "checks" in data, "Missing checks"
        assert "recommendation" in data, "Missing recommendation"
        
        checks = data["checks"]
        
        # Verify all required checks are present
        required_checks = ["dataset_size", "unique_actors", "unique_tokens", "tradeable_ratio", "duplicates_pct"]
        for check_name in required_checks:
            assert check_name in checks, f"Missing check: {check_name}"
            check = checks[check_name]
            assert "value" in check, f"Missing value in {check_name}"
            assert "pass" in check, f"Missing pass in {check_name}"
        
        # Verify individual checks
        # dataset_size >= 500
        ds_check = checks["dataset_size"]
        assert ds_check["value"] >= 500, f"Dataset size {ds_check['value']} < 500"
        assert ds_check["pass"] is True, f"dataset_size check failed: {ds_check}"
        
        # unique_actors >= 50
        actors_check = checks["unique_actors"]
        assert actors_check["value"] >= 50, f"Unique actors {actors_check['value']} < 50"
        assert actors_check["pass"] is True, f"unique_actors check failed: {actors_check}"
        
        # unique_tokens >= 15
        tokens_check = checks["unique_tokens"]
        assert tokens_check["value"] >= 15, f"Unique tokens {tokens_check['value']} < 15"
        assert tokens_check["pass"] is True, f"unique_tokens check failed: {tokens_check}"
        
        # tradeable_ratio 0.10-0.30
        ratio_check = checks["tradeable_ratio"]
        ratio = ratio_check["value"]
        assert 0.10 <= ratio <= 0.30, f"Tradeable ratio {ratio} not in 0.10-0.30"
        assert ratio_check["pass"] is True, f"tradeable_ratio check failed: {ratio_check}"
        
        # duplicates_pct < 15%
        dup_check = checks["duplicates_pct"]
        assert dup_check["value"] < 15, f"Duplicates {dup_check['value']}% >= 15%"
        assert dup_check["pass"] is True, f"duplicates_pct check failed: {dup_check}"
        
        # All checks should pass
        assert data["ready_for_retrain"] is True, f"Not ready for retrain: {data['recommendation']}"
        
        print(f"✓ Sanity check: ready_for_retrain={data['ready_for_retrain']}")
        for name, check in checks.items():
            status = "✓" if check["pass"] else "✗"
            print(f"  {status} {name}: {check['value']} (required: {check.get('required', check.get('max', 'N/A'))})")


class TestDataScalingFullPipeline:
    """Full scaling pipeline test"""
    
    def test_full_scale_pipeline(self):
        """POST /api/ml/data/scale — full pipeline (discover → expand → dedup → label → health → sanity)"""
        # Use small target for testing
        payload = {"target_signals": 50, "time_window_days": 7}
        response = requests.post(f"{BASE_URL}/api/ml/data/scale", json=payload, timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify all pipeline steps are present
        required_steps = ["discovery", "expansion", "dedup", "dataset", "health", "sanity"]
        for step in required_steps:
            assert step in data, f"Missing pipeline step: {step}"
            assert data[step].get("ok") is True, f"Pipeline step {step} failed: {data[step]}"
        
        # Verify discovery
        discovery = data["discovery"]
        assert "current_actors" in discovery, "Missing current_actors in discovery"
        
        # Verify expansion
        expansion = data["expansion"]
        assert "generated" in expansion, "Missing generated in expansion"
        
        # Verify dedup
        dedup = data["dedup"]
        assert "remaining" in dedup, "Missing remaining in dedup"
        
        # Verify dataset
        dataset = data["dataset"]
        assert "balanced_total" in dataset, "Missing balanced_total in dataset"
        
        # Verify health
        health = data["health"]
        assert "concentration" in health, "Missing concentration in health"
        
        # Verify sanity
        sanity = data["sanity"]
        assert "ready_for_retrain" in sanity, "Missing ready_for_retrain in sanity"
        
        print(f"✓ Full scaling pipeline completed:")
        print(f"  Discovery: {discovery['current_actors']} actors")
        print(f"  Expansion: {expansion['generated']} signals generated")
        print(f"  Dedup: {dedup['remaining']} remaining after dedup")
        print(f"  Dataset: {dataset['balanced_total']} samples")
        print(f"  Health: actor_gini={health['concentration']['actor_gini_events']}, token_gini={health['concentration']['token_gini_events']}")
        print(f"  Sanity: ready_for_retrain={sanity['ready_for_retrain']}")


class TestRegressionMLEndpoints:
    """Regression tests for existing ML endpoints"""
    
    def test_ml_status(self):
        """GET /api/ml/status — active model should be signal_quality_xgb_20260325_2231"""
        response = requests.get(f"{BASE_URL}/api/ml/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify active model
        assert "active_model" in data, "Missing active_model"
        model_key = data["active_model"]
        assert model_key is not None, "No active model"
        
        # Model should be the retrained one
        assert "signal_quality_xgb" in model_key, f"Unexpected model: {model_key}"
        
        print(f"✓ ML Status: active_model={model_key}")
        if "active_metrics" in data:
            metrics = data["active_metrics"]
            print(f"  Metrics: precision@10%={metrics.get('precision_top10')}, hit_rate={metrics.get('hit_rate')}")
    
    def test_ml_decision(self):
        """GET /api/ml/decision — decision mapping still works"""
        params = {"probability": 0.85, "position": "EARLY", "actor_hit_rate": 0.7, "coordination": 0.5}
        response = requests.get(f"{BASE_URL}/api/ml/decision", params=params, timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "decision" in data, "Missing decision"
        
        decision = data["decision"]
        assert "action" in decision, "Missing action in decision"
        assert decision["action"] in ["ENTER", "FOLLOW", "WATCH", "AVOID"], f"Invalid action: {decision['action']}"
        
        print(f"✓ ML Decision: action={decision['action']} for prob=0.85, EARLY")
    
    def test_live_dashboard(self):
        """GET /api/ml/live/dashboard — dashboard still works"""
        response = requests.get(f"{BASE_URL}/api/ml/live/dashboard", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify structure
        assert "config" in data, "Missing config"
        assert "health_checks" in data, "Missing health_checks"
        
        print(f"✓ Live Dashboard: health_checks present")
        if "positions" in data:
            print(f"  Positions: {data.get('positions', {}).get('total', 'N/A')}")


class TestRetrainOnExpandedData:
    """Test retrain on expanded dataset"""
    
    def test_retrain_trigger(self):
        """POST /api/ml/retrain — retrain on expanded dataset"""
        response = requests.post(f"{BASE_URL}/api/ml/retrain", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify retrain result
        assert "model_key" in data or "candidate" in data, "Missing model_key or candidate"
        
        print(f"✓ Retrain triggered successfully")
        if "model_key" in data:
            print(f"  New model: {data['model_key']}")
        if "metrics" in data:
            print(f"  Metrics: {data['metrics']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
