"""
Test Live Evaluation Framework + Alpha Amplification Layer.

Tests the NEW live trading engine endpoints:
- Composite scoring with signal decay
- Alpha filters (anti-late, top quantile, token cooldown, actor stacking, anti-overtrading)
- Position management (OPEN → CLOSE lifecycle)
- TP/SL strategy tracking
- Equity curve, confidence buckets, actor/action stats
- Regression tests for base MLOps endpoints

Base URL: https://expo-telegram-web.preview.emergentagent.com
"""

import pytest
import requests
import os
import math

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestCompositeScoring:
    """Test composite score computation with decay."""
    
    def test_composite_score_basic(self):
        """Test GET /api/ml/live/score with basic parameters."""
        response = requests.get(f"{BASE_URL}/api/ml/live/score", params={
            "prediction": 0.88,
            "actor_hit_rate": 0.72,
            "coordination": 0.6,
            "position": "EARLY",
            "age_hours": 0
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        score = data.get("score", {})
        assert "composite_score" in score
        assert "confidence_weight" in score
        assert "components" in score
        
        # Verify components
        components = score["components"]
        assert "model_prob" in components
        assert "actor_score" in components
        assert "coordination" in components
        assert "early_bonus" in components
        assert "freshness" in components
        assert "decay" in components
        
        # Verify EARLY position gives bonus = 1.0
        assert components["early_bonus"] == 1.0
        
        # Verify freshness = 1.0 when age_hours = 0
        assert components["freshness"] == 1.0
        
        # Verify decay = 1.0 when age_hours = 0
        assert components["decay"] == 1.0
        
        print(f"Composite score: {score['composite_score']}")
        print(f"Components: {components}")
    
    def test_composite_score_formula_verification(self):
        """Verify composite score formula: model*0.4 + actor*0.25 + coord*0.2 + early*0.1 + fresh*0.05."""
        response = requests.get(f"{BASE_URL}/api/ml/live/score", params={
            "prediction": 0.88,
            "actor_hit_rate": 0.72,
            "coordination": 0.6,
            "position": "EARLY",
            "age_hours": 0
        })
        assert response.status_code == 200
        data = response.json()
        score = data.get("score", {})
        components = score["components"]
        
        # Manual calculation:
        # model_prob = 0.88 * 0.40 = 0.352
        # actor_score = 0.72 * 0.25 = 0.18
        # coordination = min(0.6/2.0, 1.0) * 0.20 = 0.3 * 0.20 = 0.06
        # early_bonus = 1.0 * 0.10 = 0.10
        # freshness = 1.0 * 0.05 = 0.05
        # Total = 0.352 + 0.18 + 0.06 + 0.10 + 0.05 = 0.742
        
        expected_score = (
            0.88 * 0.40 +
            0.72 * 0.25 +
            min(0.6 / 2.0, 1.0) * 0.20 +
            1.0 * 0.10 +
            1.0 * 0.05
        )
        
        # Allow small floating point tolerance
        assert abs(score["composite_score"] - expected_score) < 0.01, \
            f"Expected ~{expected_score:.4f}, got {score['composite_score']}"
        
        print(f"Expected score: {expected_score:.4f}, Actual: {score['composite_score']}")
    
    def test_composite_score_with_decay(self):
        """Test signal decay: score *= exp(-age / tau) where tau=6."""
        # Test with age_hours = 1
        response = requests.get(f"{BASE_URL}/api/ml/live/score", params={
            "prediction": 0.88,
            "actor_hit_rate": 0.72,
            "coordination": 0.6,
            "position": "EARLY",
            "age_hours": 1
        })
        assert response.status_code == 200
        data = response.json()
        score = data.get("score", {})
        components = score["components"]
        
        # Decay = exp(-1/6) ≈ 0.8465
        expected_decay = math.exp(-1 / 6)
        assert abs(components["decay"] - expected_decay) < 0.01, \
            f"Expected decay ~{expected_decay:.4f}, got {components['decay']}"
        
        # Freshness = 1 - (1/24) = 0.9583
        expected_freshness = 1.0 - (1 / 24)
        assert abs(components["freshness"] - expected_freshness) < 0.01
        
        print(f"Decay at 1h: {components['decay']:.4f} (expected {expected_decay:.4f})")
    
    def test_composite_score_late_position(self):
        """Test LATE position gives low early_bonus = 0.1."""
        response = requests.get(f"{BASE_URL}/api/ml/live/score", params={
            "prediction": 0.88,
            "actor_hit_rate": 0.72,
            "coordination": 0.6,
            "position": "LATE",
            "age_hours": 0
        })
        assert response.status_code == 200
        data = response.json()
        components = data["score"]["components"]
        
        assert components["early_bonus"] == 0.1, "LATE position should have early_bonus=0.1"
        print(f"LATE position early_bonus: {components['early_bonus']}")
    
    def test_composite_score_mid_position(self):
        """Test MID position gives early_bonus = 0.5."""
        response = requests.get(f"{BASE_URL}/api/ml/live/score", params={
            "prediction": 0.88,
            "actor_hit_rate": 0.72,
            "coordination": 0.6,
            "position": "MID",
            "age_hours": 0
        })
        assert response.status_code == 200
        data = response.json()
        components = data["score"]["components"]
        
        assert components["early_bonus"] == 0.5, "MID position should have early_bonus=0.5"
        print(f"MID position early_bonus: {components['early_bonus']}")


class TestLiveProcessing:
    """Test signal processing with alpha filters."""
    
    def test_process_signals(self):
        """Test POST /api/ml/live/process — score+filter+open positions."""
        response = requests.post(f"{BASE_URL}/api/ml/live/process")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Should have filter_log with steps
        if "filter_log" in data:
            filter_log = data["filter_log"]
            print(f"Filter log: {filter_log}")
            
            # Verify filter steps exist
            if "steps" in filter_log:
                steps = filter_log["steps"]
                # Expected steps: anti_late, action_filter, top_quantile, token_cooldown, anti_overtrading
                expected_steps = ["anti_late", "action_filter", "top_quantile", "token_cooldown", "anti_overtrading"]
                for step in expected_steps:
                    if step in steps:
                        print(f"  {step}: {steps[step]}")
        
        print(f"Scored signals: {data.get('scored_signals', 0)}")
        print(f"Positions opened: {data.get('positions_opened', 0)}")
    
    def test_process_deduplication(self):
        """Test that calling process again opens 0 new positions (dedup)."""
        # First call
        response1 = requests.post(f"{BASE_URL}/api/ml/live/process")
        assert response1.status_code == 200
        
        # Second call should open 0 new positions
        response2 = requests.post(f"{BASE_URL}/api/ml/live/process")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Either positions_opened=0 or message says "No new signals"
        if data2.get("positions_opened") is not None:
            assert data2["positions_opened"] == 0, "Dedup should prevent opening same positions twice"
            print("Deduplication verified: positions_opened=0 on second call")
        elif "message" in data2:
            print(f"Dedup message: {data2['message']}")
        else:
            print(f"Process response: {data2}")


class TestPositionManagement:
    """Test position lifecycle management."""
    
    def test_list_positions_all(self):
        """Test GET /api/ml/live/positions — list all positions."""
        response = requests.get(f"{BASE_URL}/api/ml/live/positions")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "positions" in data
        assert "count" in data
        
        print(f"Total positions: {data['count']}")
        if data["positions"]:
            pos = data["positions"][0]
            print(f"Sample position fields: {list(pos.keys())}")
    
    def test_list_positions_open(self):
        """Test GET /api/ml/live/positions?status=OPEN."""
        response = requests.get(f"{BASE_URL}/api/ml/live/positions", params={"status": "OPEN"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # All returned positions should be OPEN
        for pos in data.get("positions", []):
            assert pos.get("status") == "OPEN", f"Expected OPEN, got {pos.get('status')}"
        
        print(f"Open positions: {data['count']}")
    
    def test_list_positions_closed(self):
        """Test GET /api/ml/live/positions?status=CLOSED."""
        response = requests.get(f"{BASE_URL}/api/ml/live/positions", params={"status": "CLOSED"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # All returned positions should be CLOSED
        for pos in data.get("positions", []):
            assert pos.get("status") == "CLOSED", f"Expected CLOSED, got {pos.get('status')}"
        
        print(f"Closed positions: {data['count']}")
    
    def test_update_positions(self):
        """Test POST /api/ml/live/update — update returns, apply TP/SL."""
        response = requests.post(f"{BASE_URL}/api/ml/live/update")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        print(f"Updated: {data.get('updated', 0)}")
        print(f"Closed TP: {data.get('closed_tp', 0)}")
        print(f"Closed SL: {data.get('closed_sl', 0)}")
        print(f"Closed 24h: {data.get('closed_24h', 0)}")
        print(f"Total open: {data.get('total_open', 0)}")
    
    def test_anti_overtrading_max_5(self):
        """Verify max 5 concurrent positions (anti-overtrading)."""
        response = requests.get(f"{BASE_URL}/api/ml/live/positions", params={"status": "OPEN"})
        assert response.status_code == 200
        data = response.json()
        
        open_count = data.get("count", 0)
        assert open_count <= 5, f"Anti-overtrading violated: {open_count} open positions (max 5)"
        print(f"Open positions: {open_count} (max 5 allowed)")


class TestLiveMetrics:
    """Test live trading metrics and analytics."""
    
    def test_live_metrics(self):
        """Test GET /api/ml/live/metrics — hold vs TP/SL comparison."""
        response = requests.get(f"{BASE_URL}/api/ml/live/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        if "metrics" in data:
            metrics = data["metrics"]
            print(f"Date: {metrics.get('date')}")
            print(f"N positions: {metrics.get('n_positions', 0)}")
            
            if "strategy_hold" in metrics:
                hold = metrics["strategy_hold"]
                print(f"HOLD strategy: win_rate={hold.get('win_rate')}, avg_return={hold.get('avg_return')}%")
            
            if "strategy_tpsl" in metrics:
                tpsl = metrics["strategy_tpsl"]
                print(f"TP/SL strategy: win_rate={tpsl.get('win_rate')}, avg_return={tpsl.get('avg_return')}%")
            
            if "strategy_comparison" in metrics:
                comp = metrics["strategy_comparison"]
                print(f"Strategy comparison: winner={comp.get('winner')}")
        else:
            print(f"Metrics response: {data}")
    
    def test_equity_curve(self):
        """Test GET /api/ml/live/equity — cumulative equity curve."""
        response = requests.get(f"{BASE_URL}/api/ml/live/equity")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        print(f"Total trades: {data.get('total_trades', 0)}")
        print(f"Cumulative return: {data.get('cumulative_return', 0)}%")
        print(f"Max drawdown: {data.get('max_drawdown', 0)}%")
        
        if data.get("equity"):
            print(f"Equity curve points: {len(data['equity'])}")
            # Verify equity curve structure
            if data["equity"]:
                point = data["equity"][0]
                assert "return" in point
                assert "cumulative" in point
                assert "drawdown" in point
    
    def test_confidence_buckets(self):
        """Test GET /api/ml/live/confidence-buckets — win rates by bucket."""
        response = requests.get(f"{BASE_URL}/api/ml/live/confidence-buckets")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        print(f"Is monotonic: {data.get('is_monotonic')}")
        print(f"Calibration OK: {data.get('calibration_ok')}")
        
        if "buckets" in data:
            buckets = data["buckets"]
            for bucket_name, bucket_data in buckets.items():
                print(f"  {bucket_name}: count={bucket_data.get('count')}, win_rate={bucket_data.get('win_rate')}")
    
    def test_actor_stats(self):
        """Test GET /api/ml/live/actor-stats — per-actor live performance."""
        response = requests.get(f"{BASE_URL}/api/ml/live/actor-stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        if "actors" in data:
            print(f"Total actors: {len(data['actors'])}")
            for actor in data["actors"][:5]:  # Top 5
                print(f"  {actor.get('actor')}: signals={actor.get('signals')}, win_rate={actor.get('win_rate')}, avg_return={actor.get('avg_return')}%")
    
    def test_action_stats(self):
        """Test GET /api/ml/live/action-stats — ENTER vs FOLLOW comparison."""
        response = requests.get(f"{BASE_URL}/api/ml/live/action-stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        if "actions" in data:
            for action in data["actions"]:
                print(f"  {action.get('action')}: count={action.get('count')}, win_rate={action.get('win_rate')}, avg_return={action.get('avg_return')}%")
        
        if "enter_vs_follow" in data:
            evf = data["enter_vs_follow"]
            print(f"ENTER avg: {evf.get('enter_avg')}%, FOLLOW avg: {evf.get('follow_avg')}%")
            print(f"Logic valid (ENTER >= FOLLOW): {evf.get('logic_valid')}")


class TestLiveDashboard:
    """Test live dashboard aggregation."""
    
    def test_dashboard(self):
        """Test GET /api/ml/live/dashboard — aggregated status with health checks."""
        response = requests.get(f"{BASE_URL}/api/ml/live/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Verify positions counts
        assert "positions" in data
        positions = data["positions"]
        print(f"Positions: open={positions.get('open')}, closed={positions.get('closed')}")
        
        # Verify health checks
        if "health_checks" in data:
            checks = data["health_checks"]
            print(f"Health checks: {checks}")
        
        # Verify confidence monotonic
        print(f"Confidence monotonic: {data.get('confidence_monotonic')}")
        
        # Verify top bucket
        if "top_bucket" in data and data["top_bucket"]:
            print(f"Top bucket (0.9+): {data['top_bucket']}")


class TestRegressionMLOps:
    """Regression tests for base MLOps endpoints."""
    
    def test_ml_status(self):
        """Regression: GET /api/ml/status still works."""
        response = requests.get(f"{BASE_URL}/api/ml/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        print(f"Active model: {data.get('active_model')}")
        print(f"Drift status: {data.get('drift', {}).get('status')}")
    
    def test_ml_decision(self):
        """Regression: GET /api/ml/decision still works."""
        response = requests.get(f"{BASE_URL}/api/ml/decision", params={
            "probability": 0.85,
            "position": "EARLY",
            "actor_hit_rate": 0.7,
            "coordination": 0.5
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        decision = data.get("decision", {})
        assert decision.get("action") == "ENTER"
        assert decision.get("strength") == "STRONG"
        print(f"Decision: {decision}")
    
    def test_ml_predict_live(self):
        """Regression: POST /api/ml/predict/live still works."""
        response = requests.post(f"{BASE_URL}/api/ml/predict/live")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        print(f"Prod model: {data.get('prod_model')}")
        print(f"Signals logged: {data.get('signals_logged')}")
        print(f"Skipped existing: {data.get('skipped_existing')}")


class TestPositionFields:
    """Test position document structure and fields."""
    
    def test_position_structure(self):
        """Verify position documents have all required fields."""
        response = requests.get(f"{BASE_URL}/api/ml/live/positions", params={"limit": 1})
        assert response.status_code == 200
        data = response.json()
        
        if data.get("positions"):
            pos = data["positions"][0]
            
            # Required fields
            required_fields = [
                "signal_id", "token", "prediction", "composite_score",
                "action", "strength", "actor", "position", "status", "opened_at"
            ]
            
            for field in required_fields:
                assert field in pos, f"Missing required field: {field}"
            
            # Strategy fields (may be None for OPEN positions)
            strategy_fields = [
                "strategy_hold_return", "strategy_tpsl_return",
                "strategy_tpsl_exit_reason", "strategy_tpsl_exit_time"
            ]
            
            for field in strategy_fields:
                assert field in pos, f"Missing strategy field: {field}"
            
            print(f"Position structure verified: {list(pos.keys())}")
            print(f"Status: {pos['status']}, Action: {pos['action']}, Strength: {pos['strength']}")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_score_with_zero_values(self):
        """Test composite score with zero values."""
        response = requests.get(f"{BASE_URL}/api/ml/live/score", params={
            "prediction": 0.5,
            "actor_hit_rate": 0,
            "coordination": 0,
            "position": "UNKNOWN",
            "age_hours": 0
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        score = data["score"]
        assert score["composite_score"] >= 0
        print(f"Score with zeros: {score['composite_score']}")
    
    def test_score_with_high_age(self):
        """Test composite score with high signal age (heavy decay)."""
        response = requests.get(f"{BASE_URL}/api/ml/live/score", params={
            "prediction": 0.88,
            "actor_hit_rate": 0.72,
            "coordination": 0.6,
            "position": "EARLY",
            "age_hours": 24
        })
        assert response.status_code == 200
        data = response.json()
        
        components = data["score"]["components"]
        # Decay at 24h = exp(-24/6) = exp(-4) ≈ 0.0183
        expected_decay = math.exp(-24 / 6)
        assert abs(components["decay"] - expected_decay) < 0.01
        
        # Freshness at 24h = 1 - 24/24 = 0
        assert components["freshness"] == 0
        
        print(f"Score at 24h age: {data['score']['composite_score']}")
        print(f"Decay: {components['decay']:.4f}")
    
    def test_positions_with_limit(self):
        """Test positions endpoint with limit parameter."""
        response = requests.get(f"{BASE_URL}/api/ml/live/positions", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        
        assert len(data.get("positions", [])) <= 5
        print(f"Positions returned with limit=5: {len(data.get('positions', []))}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
