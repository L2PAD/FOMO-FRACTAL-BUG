"""
MLOps Pipeline API Tests
Tests all 15+ MLOps endpoints for the crypto Decision Intelligence System.

Endpoints tested:
- GET /api/ml/status — ML system status
- POST /api/ml/retrain — Retrain model
- GET /api/ml/metrics/daily — Daily metrics history
- POST /api/ml/metrics/compute — Compute daily metrics
- GET /api/ml/drift — Drift detection
- GET /api/ml/health — Data health
- GET /api/ml/shadow-eval — Shadow evaluation
- POST /api/ml/promote/{model_key} — Promote model
- POST /api/ml/rollback — Rollback model
- GET /api/ml/kill-switch — Kill switch check
- GET /api/ml/retrain-check — Retrain trigger check
- GET /api/ml/calibration — Calibration check
- POST /api/ml/daily-jobs — Run daily jobs
- GET /api/ml/models — List models
- GET /api/ml/signals/top — Top signals
- GET /api/ml/decision — Decision mapper
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://expo-telegram-web.preview.emergentagent.com").rstrip("/")


class TestMLOpsStatus:
    """ML Status endpoint tests"""
    
    def test_ml_status_returns_ok(self):
        """GET /api/ml/status should return ok=True with active model info"""
        response = requests.get(f"{BASE_URL}/api/ml/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify structure
        assert "active_model" in data, "Missing active_model field"
        assert "active_metrics" in data, "Missing active_metrics field"
        assert "model_counts" in data, "Missing model_counts field"
        assert "drift" in data, "Missing drift field"
        assert "data_health" in data, "Missing data_health field"
        assert "kill_switch" in data, "Missing kill_switch field"
        
        print(f"Active model: {data.get('active_model')}")
        print(f"Model counts: {data.get('model_counts')}")
        print(f"Drift status: {data.get('drift')}")


class TestMLOpsMetrics:
    """Daily metrics endpoints tests"""
    
    def test_daily_metrics_history(self):
        """GET /api/ml/metrics/daily should return metrics history"""
        response = requests.get(f"{BASE_URL}/api/ml/metrics/daily?days=30", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "metrics" in data, "Missing metrics field"
        assert "count" in data, "Missing count field"
        
        print(f"Metrics count: {data.get('count')}")
        if data.get("metrics"):
            print(f"Latest metric date: {data['metrics'][0].get('date')}")
    
    def test_compute_daily_metrics(self):
        """POST /api/ml/metrics/compute should compute and return metrics"""
        response = requests.post(f"{BASE_URL}/api/ml/metrics/compute", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Should have metrics or message
        if "metrics" in data:
            metrics = data["metrics"]
            assert "date" in metrics, "Missing date in metrics"
            assert "n_signals" in metrics, "Missing n_signals in metrics"
            print(f"Computed metrics for date: {metrics.get('date')}")
            print(f"Total signals: {metrics.get('n_signals')}")
        else:
            print(f"Message: {data.get('message')}")


class TestMLOpsDrift:
    """Drift detection endpoint tests"""
    
    def test_drift_detection(self):
        """GET /api/ml/drift should compute and return drift analysis"""
        response = requests.get(f"{BASE_URL}/api/ml/drift", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Should have drift data or message
        if "drift" in data:
            drift = data["drift"]
            assert "overall_status" in drift, "Missing overall_status in drift"
            assert "overall_drift_score" in drift, "Missing overall_drift_score in drift"
            assert "feature_drift" in drift, "Missing feature_drift in drift"
            
            print(f"Overall drift status: {drift.get('overall_status')}")
            print(f"Overall drift score: {drift.get('overall_drift_score')}")
            print(f"Feature drift: {drift.get('feature_drift')}")
        else:
            print(f"Message: {data.get('message')}")


class TestMLOpsHealth:
    """Data health endpoint tests"""
    
    def test_data_health(self):
        """GET /api/ml/health should return data pipeline health"""
        response = requests.get(f"{BASE_URL}/api/ml/health", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        if "health" in data:
            health = data["health"]
            assert "total_signals" in health, "Missing total_signals in health"
            assert "dataset_size" in health, "Missing dataset_size in health"
            assert "tradeable_count" in health, "Missing tradeable_count in health"
            
            print(f"Total signals: {health.get('total_signals')}")
            print(f"Dataset size: {health.get('dataset_size')}")
            print(f"Tradeable count: {health.get('tradeable_count')}")


class TestMLOpsShadowEval:
    """Shadow evaluation endpoint tests"""
    
    def test_shadow_eval(self):
        """GET /api/ml/shadow-eval should return shadow evaluation or not_enough_data"""
        response = requests.get(f"{BASE_URL}/api/ml/shadow-eval", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Expected: not_enough_data since shadow_predictions is empty
        if data.get("status") == "not_enough_data":
            print(f"Shadow eval status: not_enough_data (expected)")
            print(f"Evaluated: {data.get('evaluated')}, Required: {data.get('required')}")
        elif "eval" in data:
            eval_data = data["eval"]
            print(f"Shadow eval winner: {eval_data.get('winner')}")
            print(f"Evaluated count: {eval_data.get('evaluated_count')}")


class TestMLOpsKillSwitch:
    """Kill switch endpoint tests"""
    
    def test_kill_switch_check(self):
        """GET /api/ml/kill-switch should check if model needs to be killed"""
        response = requests.get(f"{BASE_URL}/api/ml/kill-switch", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "action" in data, "Missing action field"
        
        action = data.get("action")
        print(f"Kill switch action: {action}")
        
        if action == "none":
            assert "model" in data or "reason" in data, "Missing model or reason field"
            print(f"Model: {data.get('model')}, Status: {data.get('status')}")
        elif action == "rollback_needed":
            assert "reasons" in data, "Missing reasons field"
            print(f"Rollback reasons: {data.get('reasons')}")


class TestMLOpsRetrainCheck:
    """Retrain trigger check endpoint tests"""
    
    def test_retrain_check(self):
        """GET /api/ml/retrain-check should check if retrain is needed"""
        response = requests.get(f"{BASE_URL}/api/ml/retrain-check", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "should_retrain" in data, "Missing should_retrain field"
        assert "triggers" in data, "Missing triggers field"
        assert "details" in data, "Missing details field"
        
        print(f"Should retrain: {data.get('should_retrain')}")
        print(f"Active triggers: {data.get('active_triggers')}")
        print(f"Details: {data.get('details')}")


class TestMLOpsCalibration:
    """Calibration endpoint tests"""
    
    def test_calibration_check(self):
        """GET /api/ml/calibration should return calibration data or not_enough_data"""
        response = requests.get(f"{BASE_URL}/api/ml/calibration", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Expected: not_enough_data since signal_log is empty
        if data.get("status") == "not_enough_data":
            print(f"Calibration status: not_enough_data (expected)")
            print(f"Count: {data.get('count')}")
        elif "calibration" in data:
            cal = data["calibration"]
            print(f"ECE: {cal.get('ece')}")
            print(f"Needs recalibration: {cal.get('needs_recalibration')}")


class TestMLOpsModels:
    """Models listing endpoint tests"""
    
    def test_list_all_models(self):
        """GET /api/ml/models should list all registered models"""
        response = requests.get(f"{BASE_URL}/api/ml/models", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "models" in data, "Missing models field"
        assert "count" in data, "Missing count field"
        
        print(f"Total models: {data.get('count')}")
        for model in data.get("models", [])[:5]:
            print(f"  - {model.get('model_key')}: {model.get('status')}")
    
    def test_list_active_models(self):
        """GET /api/ml/models?status=active should list only active models"""
        response = requests.get(f"{BASE_URL}/api/ml/models?status=active", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # All returned models should be active
        for model in data.get("models", []):
            assert model.get("status") == "active", f"Expected active status, got {model.get('status')}"
        
        print(f"Active models: {data.get('count')}")


class TestMLOpsSignals:
    """Top signals endpoint tests"""
    
    def test_top_signals(self):
        """GET /api/ml/signals/top should return top actionable signals"""
        response = requests.get(f"{BASE_URL}/api/ml/signals/top?limit=10", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "signals" in data, "Missing signals field"
        
        signals = data.get("signals", [])
        print(f"Top signals count: {len(signals)}")
        
        # Signals should be actionable (ENTER or FOLLOW)
        for sig in signals[:3]:
            action = sig.get("action")
            assert action in ("ENTER", "FOLLOW"), f"Expected ENTER/FOLLOW, got {action}"
            print(f"  - {sig.get('token')}: {action} ({sig.get('strength')})")


class TestMLOpsDecisionMapper:
    """Decision mapper endpoint tests - CRITICAL for user-facing decisions"""
    
    def test_decision_enter_strong(self):
        """prob>0.80 + EARLY should return ENTER + STRONG"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.85, "position": "EARLY", "actor_hit_rate": 0.7, "coordination": 0.6},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "decision" in data, "Missing decision field"
        
        decision = data["decision"]
        assert decision.get("action") == "ENTER", f"Expected ENTER, got {decision.get('action')}"
        assert decision.get("strength") == "STRONG", f"Expected STRONG, got {decision.get('strength')}"
        assert "why" in decision, "Missing why field"
        assert len(decision["why"]) > 0, "Why should have reasons"
        
        print(f"Decision: {decision.get('action')} ({decision.get('strength')})")
        print(f"Why: {decision.get('why')}")
    
    def test_decision_enter_moderate(self):
        """prob>0.70 + EARLY should return ENTER + MODERATE"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.75, "position": "EARLY"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        decision = data["decision"]
        assert decision.get("action") == "ENTER", f"Expected ENTER, got {decision.get('action')}"
        assert decision.get("strength") == "MODERATE", f"Expected MODERATE, got {decision.get('strength')}"
        
        print(f"Decision: {decision.get('action')} ({decision.get('strength')})")
    
    def test_decision_follow(self):
        """prob>0.65 + MID should return FOLLOW"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.68, "position": "MID"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        decision = data["decision"]
        assert decision.get("action") == "FOLLOW", f"Expected FOLLOW, got {decision.get('action')}"
        
        print(f"Decision: {decision.get('action')} ({decision.get('strength')})")
    
    def test_decision_watch(self):
        """prob=0.55 + MID should return WATCH"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.55, "position": "MID"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        decision = data["decision"]
        assert decision.get("action") == "WATCH", f"Expected WATCH, got {decision.get('action')}"
        
        print(f"Decision: {decision.get('action')} ({decision.get('strength')})")
    
    def test_decision_avoid(self):
        """prob=0.30 + LATE should return AVOID"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.30, "position": "LATE"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        decision = data["decision"]
        assert decision.get("action") == "AVOID", f"Expected AVOID, got {decision.get('action')}"
        assert decision.get("strength") == "NO_SIGNAL", f"Expected NO_SIGNAL, got {decision.get('strength')}"
        
        print(f"Decision: {decision.get('action')} ({decision.get('strength')})")
    
    def test_decision_never_exposes_probability(self):
        """Decision response should NEVER contain raw probability"""
        response = requests.get(
            f"{BASE_URL}/api/ml/decision",
            params={"probability": 0.85, "position": "EARLY"},
            timeout=30
        )
        data = response.json()
        decision = data["decision"]
        
        # Verify no probability in response
        assert "probability" not in decision, "Decision should NOT expose raw probability"
        assert "prob" not in decision, "Decision should NOT expose raw probability"
        
        print("Verified: No raw probability exposed in decision response")


class TestMLOpsRetrain:
    """Retrain endpoint tests"""
    
    def test_retrain_job(self):
        """POST /api/ml/retrain should train a new candidate model"""
        response = requests.post(f"{BASE_URL}/api/ml/retrain", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        if data.get("ok"):
            assert "model_key" in data, "Missing model_key field"
            assert "stage" in data, "Missing stage field"
            assert data.get("stage") == "candidate", f"Expected candidate stage, got {data.get('stage')}"
            assert "metrics" in data, "Missing metrics field"
            
            metrics = data["metrics"]
            assert "precision_top10" in metrics, "Missing precision_top10 in metrics"
            assert "hit_rate" in metrics, "Missing hit_rate in metrics"
            assert "avg_return" in metrics, "Missing avg_return in metrics"
            
            print(f"Retrained model: {data.get('model_key')}")
            print(f"Stage: {data.get('stage')}")
            print(f"Metrics: {metrics}")
        else:
            # May fail if not enough samples
            print(f"Retrain skipped: {data.get('error')}")
            assert "error" in data, "Missing error field"


class TestMLOpsPromotion:
    """Model promotion endpoint tests"""
    
    def test_promote_nonexistent_model(self):
        """POST /api/ml/promote/{model_key} with invalid key should fail"""
        response = requests.post(f"{BASE_URL}/api/ml/promote/nonexistent_model_xyz", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is False, f"Expected ok=False for nonexistent model"
        assert "error" in data, "Missing error field"
        
        print(f"Expected error: {data.get('error')}")
    
    def test_promote_requires_validation(self):
        """Promotion should validate candidate meets criteria"""
        # First get list of models to find a candidate
        models_resp = requests.get(f"{BASE_URL}/api/ml/models?status=candidate", timeout=30)
        models_data = models_resp.json()
        
        if models_data.get("count", 0) > 0:
            candidate = models_data["models"][0]
            model_key = candidate.get("model_key")
            
            response = requests.post(f"{BASE_URL}/api/ml/promote/{model_key}", timeout=30)
            data = response.json()
            
            # May succeed or fail based on validation
            print(f"Promotion result for {model_key}: ok={data.get('ok')}")
            if not data.get("ok"):
                print(f"Validation checks: {data.get('checks')}")
        else:
            print("No candidate models to test promotion")


class TestMLOpsRollback:
    """Rollback endpoint tests"""
    
    def test_rollback_model(self):
        """POST /api/ml/rollback should rollback active model"""
        # First check if there's an active model
        status_resp = requests.get(f"{BASE_URL}/api/ml/status", timeout=30)
        status_data = status_resp.json()
        
        if status_data.get("active_model"):
            response = requests.post(f"{BASE_URL}/api/ml/rollback", timeout=30)
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            print(f"Rollback result: ok={data.get('ok')}")
            
            if data.get("ok"):
                print(f"Rolled back: {data.get('rolled_back')}")
                print(f"Restored: {data.get('restored')}")
            else:
                print(f"Rollback error: {data.get('error')}")
        else:
            print("No active model to rollback")


class TestMLOpsDailyJobs:
    """Daily jobs endpoint tests"""
    
    def test_run_daily_jobs(self):
        """POST /api/ml/daily-jobs should run all monitoring jobs"""
        response = requests.post(f"{BASE_URL}/api/ml/daily-jobs", timeout=180)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "jobs" in data, "Missing jobs field"
        
        jobs = data["jobs"]
        expected_jobs = ["metrics", "drift", "data_health", "calibration", "shadow_backfill", 
                        "shadow_eval", "retrain_check", "kill_switch"]
        
        for job_name in expected_jobs:
            assert job_name in jobs, f"Missing job: {job_name}"
            print(f"Job {job_name}: ok={jobs[job_name].get('ok')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
