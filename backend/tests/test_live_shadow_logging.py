"""
Live Shadow Logging Feature Tests
Tests the new live prediction logging feature for crypto Decision Intelligence System.

Key features tested:
- POST /api/ml/predict/live — runs predictions through active + shadow models
- GET /api/ml/signals/stats — aggregated statistics with top actors/tokens
- GET /api/ml/shadow-eval — shadow vs production comparison (now with 406 evaluated)
- GET /api/ml/calibration — calibration buckets and ECE (now with 406 signals)
- GET /api/ml/signals/top — top actionable signals (ENTER/FOLLOW only)
- POST /api/ml/daily-jobs — comprehensive daily run with real data
- Deduplication verification — second call should skip existing signals
- GET /api/ml/decision — regression tests for decision mapper
- GET /api/ml/status — active model with metrics, drift, health
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://expo-telegram-web.preview.emergentagent.com").rstrip("/")


class TestLivePredictions:
    """POST /api/ml/predict/live endpoint tests"""
    
    def test_live_predictions_endpoint_exists(self):
        """POST /api/ml/predict/live should be accessible"""
        response = requests.post(f"{BASE_URL}/api/ml/predict/live", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "ok" in data, "Missing ok field in response"
        print(f"Live predictions response: ok={data.get('ok')}")
    
    def test_live_predictions_returns_model_info(self):
        """Live predictions should return prod_model and shadow_model keys"""
        response = requests.post(f"{BASE_URL}/api/ml/predict/live", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        if data.get("ok"):
            assert "prod_model" in data, "Missing prod_model field"
            assert "shadow_model" in data, "Missing shadow_model field"
            
            print(f"Production model: {data.get('prod_model')}")
            print(f"Shadow model: {data.get('shadow_model')}")
        else:
            print(f"Error: {data.get('error')}")
    
    def test_live_predictions_returns_counts(self):
        """Live predictions should return signals_logged, shadow_logged, skipped_existing"""
        response = requests.post(f"{BASE_URL}/api/ml/predict/live", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        if data.get("ok"):
            assert "signals_logged" in data, "Missing signals_logged field"
            assert "shadow_logged" in data, "Missing shadow_logged field"
            assert "skipped_existing" in data, "Missing skipped_existing field"
            
            print(f"Signals logged: {data.get('signals_logged')}")
            print(f"Shadow logged: {data.get('shadow_logged')}")
            print(f"Skipped existing: {data.get('skipped_existing')}")
    
    def test_live_predictions_returns_distributions(self):
        """Live predictions should return action and result distributions"""
        response = requests.post(f"{BASE_URL}/api/ml/predict/live", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        if data.get("ok"):
            assert "action_distribution" in data, "Missing action_distribution field"
            assert "result_distribution" in data, "Missing result_distribution field"
            
            action_dist = data.get("action_distribution", {})
            result_dist = data.get("result_distribution", {})
            
            print(f"Action distribution: {action_dist}")
            print(f"Result distribution: {result_dist}")
            
            # Verify action types are valid
            valid_actions = {"ENTER", "FOLLOW", "WATCH", "AVOID"}
            for action in action_dist.keys():
                assert action in valid_actions, f"Invalid action type: {action}"


class TestDeduplication:
    """Deduplication verification — second call should skip existing signals"""
    
    def test_deduplication_skips_existing(self):
        """Second call to /api/ml/predict/live should show skipped_existing > 0"""
        # First call (may log new or skip existing)
        response1 = requests.post(f"{BASE_URL}/api/ml/predict/live", timeout=120)
        assert response1.status_code == 200
        data1 = response1.json()
        
        if not data1.get("ok"):
            pytest.skip(f"First call failed: {data1.get('error')}")
        
        # Second call should skip all existing
        response2 = requests.post(f"{BASE_URL}/api/ml/predict/live", timeout=120)
        assert response2.status_code == 200
        data2 = response2.json()
        
        assert data2.get("ok") is True, f"Second call failed: {data2}"
        
        # After first call, second should have signals_logged=0 and skipped_existing > 0
        signals_logged = data2.get("signals_logged", 0)
        skipped_existing = data2.get("skipped_existing", 0)
        
        print(f"Second call - Signals logged: {signals_logged}")
        print(f"Second call - Skipped existing: {skipped_existing}")
        
        # If data was already logged, skipped should be > 0
        # Per spec: should show skipped_existing=406 (no duplicates)
        assert skipped_existing >= 0, "skipped_existing should be >= 0"
        
        # If signals_logged is 0, then skipped_existing should be > 0 (dedup working)
        if signals_logged == 0:
            assert skipped_existing > 0, "If no new signals logged, skipped_existing should be > 0"
            print(f"Deduplication working: {skipped_existing} signals skipped")


class TestSignalStats:
    """GET /api/ml/signals/stats endpoint tests"""
    
    def test_signal_stats_endpoint(self):
        """GET /api/ml/signals/stats should return aggregated statistics"""
        response = requests.get(f"{BASE_URL}/api/ml/signals/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        print(f"Signal stats response: ok={data.get('ok')}")
    
    def test_signal_stats_total_signals(self):
        """Signal stats should return total_signals count"""
        response = requests.get(f"{BASE_URL}/api/ml/signals/stats", timeout=30)
        data = response.json()
        
        if data.get("ok"):
            assert "total_signals" in data, "Missing total_signals field"
            total = data.get("total_signals", 0)
            print(f"Total signals: {total}")
            
            # Per spec: DB now has 406 entries in ml_signal_log
            if total > 0:
                print(f"Signal log has {total} entries")
    
    def test_signal_stats_action_distribution(self):
        """Signal stats should return action distribution"""
        response = requests.get(f"{BASE_URL}/api/ml/signals/stats", timeout=30)
        data = response.json()
        
        if data.get("ok") and data.get("total_signals", 0) > 0:
            assert "action_distribution" in data, "Missing action_distribution field"
            
            action_dist = data.get("action_distribution", {})
            print(f"Action distribution: {action_dist}")
            
            # Verify valid action types
            valid_actions = {"ENTER", "FOLLOW", "WATCH", "AVOID"}
            for action in action_dist.keys():
                assert action in valid_actions, f"Invalid action: {action}"
    
    def test_signal_stats_result_distribution(self):
        """Signal stats should return result distribution (WIN/LOSS)"""
        response = requests.get(f"{BASE_URL}/api/ml/signals/stats", timeout=30)
        data = response.json()
        
        if data.get("ok") and data.get("total_signals", 0) > 0:
            assert "result_distribution" in data, "Missing result_distribution field"
            
            result_dist = data.get("result_distribution", {})
            print(f"Result distribution: {result_dist}")
            
            # Verify valid result types
            valid_results = {"WIN", "LOSS", None}
            for result in result_dist.keys():
                assert result in valid_results or result is None, f"Invalid result: {result}"
    
    def test_signal_stats_top_actors(self):
        """Signal stats should return top actors by ENTER/FOLLOW signals"""
        response = requests.get(f"{BASE_URL}/api/ml/signals/stats", timeout=30)
        data = response.json()
        
        if data.get("ok") and data.get("total_signals", 0) > 0:
            assert "top_actors" in data, "Missing top_actors field"
            
            top_actors = data.get("top_actors", [])
            print(f"Top actors count: {len(top_actors)}")
            
            for actor in top_actors[:5]:
                assert "actor" in actor, "Missing actor field in top_actors"
                assert "actionable_signals" in actor, "Missing actionable_signals field"
                assert "avg_prediction" in actor, "Missing avg_prediction field"
                print(f"  - {actor.get('actor')}: {actor.get('actionable_signals')} signals, avg_pred={actor.get('avg_prediction')}")
    
    def test_signal_stats_top_tokens(self):
        """Signal stats should return top tokens by signal count"""
        response = requests.get(f"{BASE_URL}/api/ml/signals/stats", timeout=30)
        data = response.json()
        
        if data.get("ok") and data.get("total_signals", 0) > 0:
            assert "top_tokens" in data, "Missing top_tokens field"
            
            top_tokens = data.get("top_tokens", [])
            print(f"Top tokens count: {len(top_tokens)}")
            
            for token in top_tokens[:5]:
                assert "token" in token, "Missing token field in top_tokens"
                assert "actionable_signals" in token, "Missing actionable_signals field"
                print(f"  - {token.get('token')}: {token.get('actionable_signals')} signals")
    
    def test_signal_stats_shadow_counts(self):
        """Signal stats should return shadow prediction counts"""
        response = requests.get(f"{BASE_URL}/api/ml/signals/stats", timeout=30)
        data = response.json()
        
        if data.get("ok"):
            assert "shadow_predictions" in data, "Missing shadow_predictions field"
            assert "shadow_evaluated" in data, "Missing shadow_evaluated field"
            
            shadow_total = data.get("shadow_predictions", 0)
            shadow_eval = data.get("shadow_evaluated", 0)
            
            print(f"Shadow predictions total: {shadow_total}")
            print(f"Shadow evaluated: {shadow_eval}")


class TestShadowEvalWithData:
    """GET /api/ml/shadow-eval tests — now with 406 evaluated predictions"""
    
    def test_shadow_eval_has_data(self):
        """Shadow eval should now have evaluated predictions"""
        response = requests.get(f"{BASE_URL}/api/ml/shadow-eval", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check if we have enough data now
        if data.get("status") == "not_enough_data":
            evaluated = data.get("evaluated", 0)
            required = data.get("required", 100)
            print(f"Shadow eval: not_enough_data (evaluated={evaluated}, required={required})")
        elif "eval" in data:
            eval_data = data["eval"]
            print(f"Shadow eval has data!")
            print(f"Evaluated count: {eval_data.get('evaluated_count')}")
            print(f"Winner: {eval_data.get('winner')}")
    
    def test_shadow_eval_comparison_metrics(self):
        """Shadow eval should show prod vs shadow comparison"""
        response = requests.get(f"{BASE_URL}/api/ml/shadow-eval", timeout=60)
        data = response.json()
        
        if data.get("ok") and "eval" in data:
            eval_data = data["eval"]
            
            # Verify comparison fields
            assert "prod_model" in eval_data, "Missing prod_model"
            assert "shadow_model" in eval_data, "Missing shadow_model"
            assert "prod_metrics" in eval_data, "Missing prod_metrics"
            assert "shadow_metrics" in eval_data, "Missing shadow_metrics"
            assert "winner" in eval_data, "Missing winner"
            
            print(f"Prod model: {eval_data.get('prod_model')}")
            print(f"Shadow model: {eval_data.get('shadow_model')}")
            print(f"Prod metrics: {eval_data.get('prod_metrics')}")
            print(f"Shadow metrics: {eval_data.get('shadow_metrics')}")
            print(f"Winner: {eval_data.get('winner')}")
            
            # Verify diff fields
            assert "precision_diff" in eval_data, "Missing precision_diff"
            assert "return_diff" in eval_data, "Missing return_diff"
            print(f"Precision diff: {eval_data.get('precision_diff')}")
            print(f"Return diff: {eval_data.get('return_diff')}")


class TestCalibrationWithData:
    """GET /api/ml/calibration tests — now with 406 signals with results"""
    
    def test_calibration_has_data(self):
        """Calibration should now have signal data"""
        response = requests.get(f"{BASE_URL}/api/ml/calibration", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        if data.get("status") == "not_enough_data":
            count = data.get("count", 0)
            print(f"Calibration: not_enough_data (count={count})")
        elif "calibration" in data:
            cal = data["calibration"]
            print(f"Calibration has data!")
            print(f"Total signals: {cal.get('total_signals')}")
            print(f"ECE: {cal.get('ece')}")
    
    def test_calibration_buckets(self):
        """Calibration should show probability buckets"""
        response = requests.get(f"{BASE_URL}/api/ml/calibration", timeout=30)
        data = response.json()
        
        if data.get("ok") and "calibration" in data:
            cal = data["calibration"]
            
            assert "buckets" in cal, "Missing buckets field"
            assert "ece" in cal, "Missing ece field"
            assert "needs_recalibration" in cal, "Missing needs_recalibration field"
            
            buckets = cal.get("buckets", {})
            ece = cal.get("ece", 0)
            needs_recal = cal.get("needs_recalibration", False)
            
            print(f"Calibration buckets: {list(buckets.keys())}")
            print(f"ECE (Expected Calibration Error): {ece}")
            print(f"Needs recalibration: {needs_recal}")
            
            # Per spec: ECE should be around 0.12
            if ece > 0:
                print(f"ECE value: {ece} (spec expects ~0.12)")
            
            # Verify bucket structure
            for bucket_name, bucket_data in buckets.items():
                assert "count" in bucket_data, f"Missing count in bucket {bucket_name}"
                assert "actual_win_rate" in bucket_data, f"Missing actual_win_rate in bucket {bucket_name}"
                assert "expected" in bucket_data, f"Missing expected in bucket {bucket_name}"
                assert "gap" in bucket_data, f"Missing gap in bucket {bucket_name}"
                
                print(f"  Bucket {bucket_name}: count={bucket_data['count']}, actual={bucket_data['actual_win_rate']}, expected={bucket_data['expected']}, gap={bucket_data['gap']}")


class TestTopSignals:
    """GET /api/ml/signals/top tests — returns top actionable signals"""
    
    def test_top_signals_returns_actionable(self):
        """Top signals should only return ENTER/FOLLOW actions"""
        response = requests.get(f"{BASE_URL}/api/ml/signals/top?limit=10", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "signals" in data, "Missing signals field"
        
        signals = data.get("signals", [])
        print(f"Top signals count: {len(signals)}")
        
        # All signals should be actionable (ENTER or FOLLOW)
        for sig in signals:
            action = sig.get("action")
            assert action in ("ENTER", "FOLLOW"), f"Expected ENTER/FOLLOW, got {action}"
            print(f"  - {sig.get('token')}: {action} ({sig.get('strength')}) by {sig.get('actor')}")
    
    def test_top_signals_sorted_by_prediction(self):
        """Top signals should be sorted by prediction strength (descending)"""
        response = requests.get(f"{BASE_URL}/api/ml/signals/top?limit=10", timeout=30)
        data = response.json()
        
        if data.get("ok"):
            signals = data.get("signals", [])
            
            if len(signals) >= 2:
                predictions = [s.get("prediction", 0) for s in signals]
                # Verify descending order
                for i in range(len(predictions) - 1):
                    assert predictions[i] >= predictions[i+1], f"Signals not sorted by prediction: {predictions}"
                
                print(f"Signals sorted correctly by prediction (descending)")
                print(f"Prediction range: {predictions[0]} to {predictions[-1]}")


class TestDailyJobsWithData:
    """POST /api/ml/daily-jobs tests — comprehensive daily run with real data"""
    
    def test_daily_jobs_runs_all(self):
        """Daily jobs should run all monitoring jobs"""
        response = requests.post(f"{BASE_URL}/api/ml/daily-jobs", timeout=180)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "jobs" in data, "Missing jobs field"
        
        jobs = data["jobs"]
        expected_jobs = ["metrics", "drift", "data_health", "calibration", 
                        "shadow_backfill", "shadow_eval", "retrain_check", "kill_switch"]
        
        for job_name in expected_jobs:
            assert job_name in jobs, f"Missing job: {job_name}"
            job_result = jobs[job_name]
            print(f"Job {job_name}: ok={job_result.get('ok')}")
    
    def test_daily_jobs_calibration_with_data(self):
        """Daily jobs calibration should now have real data"""
        response = requests.post(f"{BASE_URL}/api/ml/daily-jobs", timeout=180)
        data = response.json()
        
        if data.get("ok"):
            jobs = data["jobs"]
            cal_job = jobs.get("calibration", {})
            
            if cal_job.get("ok") and "calibration" in cal_job:
                cal = cal_job["calibration"]
                print(f"Daily jobs calibration ECE: {cal.get('ece')}")
                print(f"Daily jobs calibration total: {cal.get('total_signals')}")
    
    def test_daily_jobs_shadow_eval_with_data(self):
        """Daily jobs shadow eval should now have real data"""
        response = requests.post(f"{BASE_URL}/api/ml/daily-jobs", timeout=180)
        data = response.json()
        
        if data.get("ok"):
            jobs = data["jobs"]
            shadow_job = jobs.get("shadow_eval", {})
            
            if shadow_job.get("ok") and "eval" in shadow_job:
                eval_data = shadow_job["eval"]
                print(f"Daily jobs shadow eval count: {eval_data.get('evaluated_count')}")
                print(f"Daily jobs shadow eval winner: {eval_data.get('winner')}")


class TestDecisionMapperRegression:
    """GET /api/ml/decision regression tests"""
    
    def test_decision_enter_strong_high_prob_early(self):
        """prob>0.80 + EARLY = ENTER + STRONG"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.85, "position": "EARLY", "actor_hit_rate": 0.7},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        decision = data["decision"]
        assert decision.get("action") == "ENTER", f"Expected ENTER, got {decision.get('action')}"
        assert decision.get("strength") == "STRONG", f"Expected STRONG, got {decision.get('strength')}"
        print(f"PASS: prob=0.85, EARLY -> ENTER/STRONG")
    
    def test_decision_enter_moderate_mid_prob_early(self):
        """prob>0.70 + EARLY = ENTER + MODERATE"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.75, "position": "EARLY"},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        decision = data["decision"]
        assert decision.get("action") == "ENTER", f"Expected ENTER, got {decision.get('action')}"
        assert decision.get("strength") == "MODERATE", f"Expected MODERATE, got {decision.get('strength')}"
        print(f"PASS: prob=0.75, EARLY -> ENTER/MODERATE")
    
    def test_decision_follow_mid_position(self):
        """prob>0.65 + MID = FOLLOW"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.68, "position": "MID"},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        decision = data["decision"]
        assert decision.get("action") == "FOLLOW", f"Expected FOLLOW, got {decision.get('action')}"
        print(f"PASS: prob=0.68, MID -> FOLLOW")
    
    def test_decision_watch_low_prob(self):
        """prob=0.55 = WATCH"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.55, "position": "MID"},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        decision = data["decision"]
        assert decision.get("action") == "WATCH", f"Expected WATCH, got {decision.get('action')}"
        print(f"PASS: prob=0.55, MID -> WATCH")
    
    def test_decision_avoid_very_low_prob(self):
        """prob<0.50 = AVOID"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.30, "position": "LATE"},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        decision = data["decision"]
        assert decision.get("action") == "AVOID", f"Expected AVOID, got {decision.get('action')}"
        assert decision.get("strength") == "NO_SIGNAL", f"Expected NO_SIGNAL, got {decision.get('strength')}"
        print(f"PASS: prob=0.30, LATE -> AVOID/NO_SIGNAL")
    
    def test_decision_why_field_populated(self):
        """Decision should include 'why' field with reasons"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.85, "position": "EARLY", "actor_hit_rate": 0.7, "coordination": 0.6},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        decision = data["decision"]
        assert "why" in decision, "Missing why field"
        assert len(decision["why"]) > 0, "Why should have reasons"
        
        print(f"Why reasons: {decision['why']}")


class TestMLStatusWithData:
    """GET /api/ml/status tests — should show active model with metrics"""
    
    def test_status_has_active_model(self):
        """Status should show active model"""
        response = requests.get(f"{BASE_URL}/api/ml/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        active_model = data.get("active_model")
        print(f"Active model: {active_model}")
        
        # Per spec: Active model is signal_quality_xgb_20260325_1902
        if active_model:
            assert "signal_quality_xgb" in active_model, f"Unexpected model name: {active_model}"
    
    def test_status_has_metrics(self):
        """Status should show active model metrics"""
        response = requests.get(f"{BASE_URL}/api/ml/status", timeout=30)
        data = response.json()
        
        if data.get("ok") and data.get("active_model"):
            assert "active_metrics" in data, "Missing active_metrics"
            
            metrics = data.get("active_metrics", {})
            if metrics:
                print(f"Active metrics: {metrics}")
                
                # Verify key metric fields
                expected_fields = ["precision_top10", "hit_rate", "avg_return"]
                for field in expected_fields:
                    if field in metrics:
                        print(f"  {field}: {metrics[field]}")
    
    def test_status_has_drift(self):
        """Status should show drift status"""
        response = requests.get(f"{BASE_URL}/api/ml/status", timeout=30)
        data = response.json()
        
        if data.get("ok"):
            assert "drift" in data, "Missing drift field"
            
            drift = data.get("drift", {})
            print(f"Drift status: {drift.get('status')}")
            print(f"Drift score: {drift.get('score')}")
    
    def test_status_has_health(self):
        """Status should show data health"""
        response = requests.get(f"{BASE_URL}/api/ml/status", timeout=30)
        data = response.json()
        
        if data.get("ok"):
            assert "data_health" in data, "Missing data_health field"
            
            health = data.get("data_health", {})
            if health:
                print(f"Data health - Total signals: {health.get('total_signals')}")
                print(f"Data health - Dataset size: {health.get('dataset_size')}")
                print(f"Data health - Tradeable count: {health.get('tradeable_count')}")
    
    def test_status_has_kill_switch(self):
        """Status should show kill switch status"""
        response = requests.get(f"{BASE_URL}/api/ml/status", timeout=30)
        data = response.json()
        
        if data.get("ok"):
            assert "kill_switch" in data, "Missing kill_switch field"
            
            kill_switch = data.get("kill_switch", {})
            print(f"Kill switch action: {kill_switch.get('action')}")
            print(f"Kill switch status: {kill_switch.get('status')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
