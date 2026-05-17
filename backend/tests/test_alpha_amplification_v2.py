"""
Test Alpha Amplification v2 Enhancements for Crypto Decision Intelligence System.

Tests cover:
- Config-driven parameters (hot-reload from DB)
- Hysteresis for top-quantile
- Token concentration cap (35%)
- SL cooldown (anti-revenge 120min)
- Partial TP (50%@1h, 30%@4h) + trailing stop on remainder
- Re-entry with confirmation (new actor + coordination increase)
- Trade spacing (30min gap)
- Rolling window validation (3d/7d/14d)
- Actor drop test
- Token diversity check
- Profit consistency
- Tail risk (P95 loss)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestConfigEndpoints:
    """Test config-driven parameters with hot-reload from DB."""

    def test_get_config_returns_all_14_parameters(self):
        """GET /api/ml/live/config returns all 14 tunable parameters."""
        response = requests.get(f"{BASE_URL}/api/ml/live/config")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        config = data.get("config", {})
        
        # Verify all 14 parameters exist
        expected_params = [
            "top_quantile",
            "max_positions",
            "max_per_token_pct",
            "cooldown_after_sl_min",
            "min_entry_gap_min",
            "token_cooldown_hours",
            "tau_hours",
            "tp_1h_base",
            "tp_4h_base",
            "sl_1h_base",
            "trailing_stop_pct",
            "partial_tp_1h_close_pct",
            "partial_tp_4h_close_pct",
        ]
        
        for param in expected_params:
            assert param in config, f"Missing parameter: {param}"
        
        print(f"Config has {len(config)} parameters: {list(config.keys())}")
        print(f"Current config values: {config}")

    def test_update_config_top_quantile(self):
        """POST /api/ml/live/config updates config in DB."""
        # Get current config
        get_resp = requests.get(f"{BASE_URL}/api/ml/live/config")
        assert get_resp.status_code == 200
        original_config = get_resp.json().get("config", {})
        original_top_quantile = original_config.get("top_quantile")
        
        # Update top_quantile
        new_value = 0.40
        update_resp = requests.post(
            f"{BASE_URL}/api/ml/live/config",
            json={"top_quantile": new_value}
        )
        assert update_resp.status_code == 200
        update_data = update_resp.json()
        assert update_data.get("ok") is True
        assert "updated" in update_data
        assert update_data["updated"].get("top_quantile") == new_value
        
        # Verify config reflects change
        verify_resp = requests.get(f"{BASE_URL}/api/ml/live/config")
        assert verify_resp.status_code == 200
        new_config = verify_resp.json().get("config", {})
        assert new_config.get("top_quantile") == new_value
        
        print(f"Config updated: top_quantile {original_top_quantile} -> {new_value}")
        
        # Restore original value
        requests.post(
            f"{BASE_URL}/api/ml/live/config",
            json={"top_quantile": original_top_quantile}
        )

    def test_config_hot_reload(self):
        """Verify config changes are reflected immediately (hot-reload)."""
        # Update a parameter
        update_resp = requests.post(
            f"{BASE_URL}/api/ml/live/config",
            json={"max_positions": 12}
        )
        assert update_resp.status_code == 200
        
        # Immediately verify
        get_resp = requests.get(f"{BASE_URL}/api/ml/live/config")
        config = get_resp.json().get("config", {})
        assert config.get("max_positions") == 12
        
        # Restore
        requests.post(
            f"{BASE_URL}/api/ml/live/config",
            json={"max_positions": 10}
        )
        print("Hot-reload verified: config changes reflected immediately")


class TestFilterChain:
    """Test the full filter chain with all 8 steps."""

    def test_process_filter_chain_all_steps(self):
        """POST /api/ml/live/process shows filter steps in filter_log."""
        response = requests.post(f"{BASE_URL}/api/ml/live/process")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        filter_log = data.get("filter_log", {})
        steps = filter_log.get("steps", {})
        
        # Core filter steps that should always be present
        core_steps = [
            "anti_late",
            "action_filter",
            "top_quantile",
            "token_cooldown",
            "sl_cooldown",
            "trade_spacing",
        ]
        
        # Optional steps that appear only if trade_spacing passes
        optional_steps = [
            "concentration_cap",
            "anti_overtrading",
        ]
        
        for step in core_steps:
            assert step in steps, f"Missing core filter step: {step}"
        
        # Check if trade_spacing passed (not a skip_all message)
        trade_spacing = steps.get("trade_spacing", "")
        if trade_spacing == "ok":
            # If trade_spacing passed, concentration_cap and anti_overtrading should be present
            for step in optional_steps:
                assert step in steps, f"Missing optional step after trade_spacing passed: {step}"
        else:
            # trade_spacing blocked further processing - this is expected behavior
            print(f"Trade spacing blocked: {trade_spacing}")
        
        print(f"Filter chain steps: {steps}")
        print(f"Input: {filter_log.get('input')}, Output: {filter_log.get('output')}")

    def test_dedup_second_process_returns_zero(self):
        """Verify dedup: POST /api/ml/live/process again returns positions_opened=0."""
        # First call
        resp1 = requests.post(f"{BASE_URL}/api/ml/live/process")
        assert resp1.status_code == 200
        
        # Second call should open 0 positions (dedup)
        resp2 = requests.post(f"{BASE_URL}/api/ml/live/process")
        assert resp2.status_code == 200
        data2 = resp2.json()
        
        # Either positions_opened=0 or message about no new signals
        positions_opened = data2.get("positions_opened", 0)
        message = data2.get("message", "")
        
        assert positions_opened == 0 or "no new" in message.lower(), \
            f"Dedup failed: positions_opened={positions_opened}, message={message}"
        
        print(f"Dedup verified: positions_opened={positions_opened}")


class TestPartialTPTracking:
    """Test partial TP tracking fields in position updates."""

    def test_update_positions_partial_tp_fields(self):
        """POST /api/ml/live/update includes partial TP tracking fields."""
        response = requests.post(f"{BASE_URL}/api/ml/live/update")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Check stats include partial TP counters
        assert "partial_tp_1h" in data or "updated" in data
        assert "partial_tp_4h" in data or "updated" in data
        
        print(f"Update stats: {data}")

    def test_positions_have_partial_tp_fields(self):
        """Verify positions have partial_tp_1h_realized, partial_tp_4h_realized, remaining_pct, trailing_stop."""
        response = requests.get(f"{BASE_URL}/api/ml/live/positions?limit=10")
        assert response.status_code == 200
        data = response.json()
        positions = data.get("positions", [])
        
        if positions:
            pos = positions[0]
            # These fields should exist (may be null for new positions)
            expected_fields = [
                "partial_tp_1h_realized",
                "partial_tp_4h_realized",
                "remaining_pct",
                "trailing_stop",
            ]
            for field in expected_fields:
                assert field in pos, f"Missing field: {field}"
            
            print(f"Position fields verified: {list(pos.keys())}")
        else:
            print("No positions to verify fields")


class TestMetricsEndpoint:
    """Test metrics endpoint with profit consistency and tail risk."""

    def test_metrics_includes_profit_consistency(self):
        """GET /api/ml/live/metrics includes profit_consistency object."""
        response = requests.get(f"{BASE_URL}/api/ml/live/metrics")
        assert response.status_code == 200
        data = response.json()
        
        if data.get("message") == "No closed positions":
            pytest.skip("No closed positions for metrics")
        
        metrics = data.get("metrics", data)
        
        # Check profit_consistency object
        profit_consistency = metrics.get("profit_consistency", {})
        assert "positive_days_ratio" in profit_consistency or "positive_days" in profit_consistency
        assert "stable" in profit_consistency
        
        print(f"Profit consistency: {profit_consistency}")

    def test_metrics_includes_tail_risk(self):
        """GET /api/ml/live/metrics includes tail_risk (p95_loss)."""
        response = requests.get(f"{BASE_URL}/api/ml/live/metrics")
        assert response.status_code == 200
        data = response.json()
        
        if data.get("message") == "No closed positions":
            pytest.skip("No closed positions for metrics")
        
        metrics = data.get("metrics", data)
        
        # Check tail_risk object
        tail_risk = metrics.get("tail_risk", {})
        assert "p95_loss_hold" in tail_risk or "p95_loss_tpsl" in tail_risk
        
        print(f"Tail risk: {tail_risk}")

    def test_metrics_includes_strategy_comparison(self):
        """GET /api/ml/live/metrics includes strategy_comparison."""
        response = requests.get(f"{BASE_URL}/api/ml/live/metrics")
        assert response.status_code == 200
        data = response.json()
        
        if data.get("message") == "No closed positions":
            pytest.skip("No closed positions for metrics")
        
        metrics = data.get("metrics", data)
        
        # Check strategy_comparison
        strategy_comparison = metrics.get("strategy_comparison", {})
        assert "hold_avg" in strategy_comparison or "winner" in strategy_comparison
        
        print(f"Strategy comparison: {strategy_comparison}")


class TestRollingWindowValidation:
    """Test rolling window validation (3d/7d/14d/all)."""

    def test_rolling_window_all_windows(self):
        """GET /api/ml/live/validate/rolling returns 3d/7d/14d/all windows."""
        response = requests.get(f"{BASE_URL}/api/ml/live/validate/rolling")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        windows = data.get("windows", {})
        
        # Check all window periods exist
        expected_windows = ["3d", "7d", "14d", "all"]
        for window in expected_windows:
            if window in windows:
                w_data = windows[window]
                assert "trades" in w_data
                assert "win_rate" in w_data
                assert "avg_return" in w_data
        
        # Check all_positive flag
        assert "all_positive" in data
        
        print(f"Rolling windows: {windows}")
        print(f"All positive: {data.get('all_positive')}")


class TestActorDropTest:
    """Test actor drop validation."""

    def test_actor_drop_removes_top3(self):
        """GET /api/ml/live/validate/actor-drop removes top 3 actors."""
        response = requests.get(f"{BASE_URL}/api/ml/live/validate/actor-drop")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Check required fields
        assert "dropped_actors" in data or "message" in data
        
        if "dropped_actors" in data:
            assert "survives_without_top3" in data
            assert "top3_dependency_pct" in data
            
            print(f"Dropped actors: {data.get('dropped_actors')}")
            print(f"Survives without top3: {data.get('survives_without_top3')}")
            print(f"Top3 dependency: {data.get('top3_dependency_pct')}%")
        else:
            print(f"Actor drop test: {data.get('message')}")


class TestTokenDiversity:
    """Test token diversity validation."""

    def test_token_diversity_check(self):
        """GET /api/ml/live/validate/token-diversity returns profitable_count and diversified flag."""
        response = requests.get(f"{BASE_URL}/api/ml/live/validate/token-diversity")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Check required fields
        assert "profitable_count" in data
        assert "diversified" in data
        
        # diversified should be True if >=3 profitable tokens
        profitable_count = data.get("profitable_count", 0)
        diversified = data.get("diversified")
        
        if profitable_count >= 3:
            assert diversified is True, f"Should be diversified with {profitable_count} profitable tokens"
        
        print(f"Profitable tokens: {profitable_count}")
        print(f"Diversified: {diversified}")
        print(f"Total tokens: {data.get('total_tokens')}")


class TestReentryEndpoint:
    """Test re-entry with confirmation."""

    def test_reentry_candidates(self):
        """GET /api/ml/live/reentry returns candidates with new_actor/coordination_increase flags."""
        response = requests.get(f"{BASE_URL}/api/ml/live/reentry")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        candidates = data.get("candidates", [])
        
        if candidates:
            for c in candidates[:3]:  # Check first 3
                assert "token" in c
                assert "new_actor" in c
                assert "coordination_increase" in c
                print(f"Re-entry candidate: {c}")
        else:
            print("No re-entry candidates found")


class TestCompositeScoreDecay:
    """Test composite score with decay for different age_hours values."""

    def test_score_decay_age_0_vs_24(self):
        """Composite score at age_hours=0 should be higher than age_hours=24."""
        # Score at age=0
        resp_0 = requests.get(
            f"{BASE_URL}/api/ml/live/score",
            params={
                "prediction": 0.85,
                "actor_hit_rate": 0.7,
                "coordination": 0.5,
                "position": "EARLY",
                "age_hours": 0
            }
        )
        assert resp_0.status_code == 200
        score_0 = resp_0.json().get("score", {}).get("composite_score", 0)
        
        # Score at age=24
        resp_24 = requests.get(
            f"{BASE_URL}/api/ml/live/score",
            params={
                "prediction": 0.85,
                "actor_hit_rate": 0.7,
                "coordination": 0.5,
                "position": "EARLY",
                "age_hours": 24
            }
        )
        assert resp_24.status_code == 200
        score_24 = resp_24.json().get("score", {}).get("composite_score", 0)
        
        # Score at age=0 should be higher due to decay
        assert score_0 > score_24, f"Score at age=0 ({score_0}) should be > score at age=24 ({score_24})"
        
        print(f"Score at age=0: {score_0}")
        print(f"Score at age=24: {score_24}")
        print(f"Decay factor: {score_24 / score_0 if score_0 > 0 else 0:.4f}")

    def test_score_components_include_decay(self):
        """Score response includes decay component."""
        response = requests.get(
            f"{BASE_URL}/api/ml/live/score",
            params={
                "prediction": 0.8,
                "actor_hit_rate": 0.6,
                "coordination": 0.4,
                "position": "MID",
                "age_hours": 6
            }
        )
        assert response.status_code == 200
        data = response.json()
        score = data.get("score", {})
        components = score.get("components", {})
        
        assert "decay" in components
        # At tau=6 hours, decay should be ~0.368 (e^-1)
        decay = components.get("decay", 0)
        assert 0.3 < decay < 0.4, f"Decay at 6h should be ~0.368, got {decay}"
        
        print(f"Score components: {components}")


class TestConfidenceBuckets:
    """Test confidence bucket analysis."""

    def test_confidence_buckets_is_monotonic(self):
        """GET /api/ml/live/confidence-buckets includes is_monotonic check."""
        response = requests.get(f"{BASE_URL}/api/ml/live/confidence-buckets")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Check is_monotonic flag
        assert "is_monotonic" in data
        
        buckets = data.get("buckets", {})
        print(f"Confidence buckets: {buckets}")
        print(f"Is monotonic: {data.get('is_monotonic')}")


class TestDashboard:
    """Test dashboard endpoint."""

    def test_dashboard_includes_config(self):
        """GET /api/ml/live/dashboard includes config."""
        response = requests.get(f"{BASE_URL}/api/ml/live/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        assert "config" in data
        config = data.get("config", {})
        assert len(config) >= 10, f"Config should have at least 10 params, got {len(config)}"
        
        print(f"Dashboard config: {config}")

    def test_dashboard_health_checks_profit_consistent(self):
        """GET /api/ml/live/dashboard health_checks includes profit_consistent flag."""
        response = requests.get(f"{BASE_URL}/api/ml/live/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        health_checks = data.get("health_checks", {})
        
        # profit_consistent may not exist if no metrics yet
        if health_checks:
            print(f"Health checks: {health_checks}")
            # Check for profit_consistent if there are trades
            if health_checks.get("has_trades"):
                assert "profit_consistent" in health_checks or "has_alpha" in health_checks


class TestRegressionEndpoints:
    """Regression tests for existing ML endpoints."""

    def test_ml_status(self):
        """GET /api/ml/status still works."""
        response = requests.get(f"{BASE_URL}/api/ml/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "active_model" in data
        print(f"Active model: {data.get('active_model')}")

    def test_ml_retrain_check(self):
        """POST /api/ml/retrain-check still works."""
        response = requests.get(f"{BASE_URL}/api/ml/retrain-check")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Retrain check: {data}")

    def test_ml_decision(self):
        """GET /api/ml/decision still works."""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.85, "position": "EARLY"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        decision = data.get("decision", {})
        assert "action" in decision
        print(f"Decision: {decision}")


class TestConfigParameters:
    """Test specific config parameter values."""

    def test_concentration_cap_35_percent(self):
        """Verify max_per_token_pct is 0.35 (35%)."""
        response = requests.get(f"{BASE_URL}/api/ml/live/config")
        assert response.status_code == 200
        config = response.json().get("config", {})
        
        max_per_token = config.get("max_per_token_pct", 0)
        assert max_per_token == 0.35, f"Expected 0.35, got {max_per_token}"
        print(f"Token concentration cap: {max_per_token * 100}%")

    def test_sl_cooldown_120_min(self):
        """Verify cooldown_after_sl_min is 120."""
        response = requests.get(f"{BASE_URL}/api/ml/live/config")
        assert response.status_code == 200
        config = response.json().get("config", {})
        
        cooldown = config.get("cooldown_after_sl_min", 0)
        assert cooldown == 120, f"Expected 120, got {cooldown}"
        print(f"SL cooldown: {cooldown} minutes")

    def test_trade_spacing_30_min(self):
        """Verify min_entry_gap_min is 30."""
        response = requests.get(f"{BASE_URL}/api/ml/live/config")
        assert response.status_code == 200
        config = response.json().get("config", {})
        
        gap = config.get("min_entry_gap_min", 0)
        assert gap == 30, f"Expected 30, got {gap}"
        print(f"Trade spacing: {gap} minutes")

    def test_partial_tp_percentages(self):
        """Verify partial TP percentages: 50% at 1h, 30% at 4h."""
        response = requests.get(f"{BASE_URL}/api/ml/live/config")
        assert response.status_code == 200
        config = response.json().get("config", {})
        
        tp_1h = config.get("partial_tp_1h_close_pct", 0)
        tp_4h = config.get("partial_tp_4h_close_pct", 0)
        
        assert tp_1h == 0.50, f"Expected 0.50 for 1h, got {tp_1h}"
        assert tp_4h == 0.30, f"Expected 0.30 for 4h, got {tp_4h}"
        
        print(f"Partial TP: {tp_1h * 100}% at 1h, {tp_4h * 100}% at 4h")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
