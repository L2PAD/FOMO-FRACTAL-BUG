"""
ML Risk Overlay V1 Tests - Phase B: ML Risk Overlay
Tests for /api/ml-risk/* endpoints:
- POST /api/ml-risk/build-dataset: builds 432 samples from exchange_forecasts
- POST /api/ml-risk/train: trains LogisticRegression, returns metrics with roc_auc, top_features
- GET /api/ml-risk/status: returns model_trained=true, dataset_size=432, shadow_scored=433
- POST /api/ml-risk/shadow-score: scores forecasts and writes audit.ml to exchange_forecasts
- GET /api/ml-risk/shadow-stats: returns risk buckets (low/med/high) with error_rate, model_validation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')


class TestMlRiskStatus:
    """Tests for GET /api/ml-risk/status endpoint"""

    def test_status_returns_200(self):
        """GET /api/ml-risk/status returns 200"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/ml-risk/status returns 200")

    def test_status_has_model_trained(self):
        """status has model_trained field"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/status")
        data = response.json()
        assert "model_trained" in data, "Missing model_trained field"
        assert data["model_trained"] is True, f"Expected model_trained=True, got {data['model_trained']}"
        print(f"✓ model_trained = {data['model_trained']}")

    def test_status_has_dataset_size(self):
        """status has dataset_size = 432"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/status")
        data = response.json()
        assert "dataset_size" in data, "Missing dataset_size field"
        assert data["dataset_size"] == 432, f"Expected dataset_size=432, got {data['dataset_size']}"
        print(f"✓ dataset_size = {data['dataset_size']}")

    def test_status_has_shadow_scored(self):
        """status has shadow_scored = 433"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/status")
        data = response.json()
        assert "shadow_scored" in data, "Missing shadow_scored field"
        assert data["shadow_scored"] == 433, f"Expected shadow_scored=433, got {data['shadow_scored']}"
        print(f"✓ shadow_scored = {data['shadow_scored']}")

    def test_status_has_metrics(self):
        """status has metrics object"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/status")
        data = response.json()
        assert "metrics" in data, "Missing metrics field"
        assert data["metrics"] is not None, "metrics should not be None"
        print("✓ metrics object present")

    def test_metrics_has_roc_auc(self):
        """metrics has roc_auc field"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/status")
        data = response.json()
        metrics = data.get("metrics", {})
        assert "roc_auc" in metrics, "Missing roc_auc in metrics"
        assert 0.5 < metrics["roc_auc"] < 1.0, f"roc_auc should be between 0.5 and 1.0, got {metrics['roc_auc']}"
        print(f"✓ roc_auc = {metrics['roc_auc']:.4f}")

    def test_metrics_has_top_features(self):
        """metrics has top_features list"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/status")
        data = response.json()
        metrics = data.get("metrics", {})
        assert "top_features" in metrics, "Missing top_features in metrics"
        assert isinstance(metrics["top_features"], list), "top_features should be a list"
        assert len(metrics["top_features"]) > 0, "top_features should not be empty"
        print(f"✓ top_features has {len(metrics['top_features'])} features")

    def test_metrics_has_classification_report(self):
        """metrics has classification_report"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/status")
        data = response.json()
        metrics = data.get("metrics", {})
        assert "classification_report" in metrics, "Missing classification_report in metrics"
        print("✓ classification_report present")

    def test_metrics_has_train_test_sizes(self):
        """metrics has train_size and test_size"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/status")
        data = response.json()
        metrics = data.get("metrics", {})
        assert "train_size" in metrics, "Missing train_size"
        assert "test_size" in metrics, "Missing test_size"
        assert metrics["train_size"] > 0, "train_size should be > 0"
        assert metrics["test_size"] > 0, "test_size should be > 0"
        print(f"✓ train_size={metrics['train_size']}, test_size={metrics['test_size']}")


class TestMlRiskShadowStats:
    """Tests for GET /api/ml-risk/shadow-stats endpoint"""

    def test_shadow_stats_returns_200(self):
        """GET /api/ml-risk/shadow-stats returns 200"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/ml-risk/shadow-stats returns 200")

    def test_shadow_stats_has_total(self):
        """shadow-stats has total count"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        assert "total" in data, "Missing total field"
        assert data["total"] > 0, f"Expected total > 0, got {data['total']}"
        print(f"✓ total = {data['total']}")

    def test_shadow_stats_has_bucket_low(self):
        """shadow-stats has bucket_low with error_rate"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        assert "bucket_low" in data, "Missing bucket_low"
        bucket = data["bucket_low"]
        assert "count" in bucket, "Missing count in bucket_low"
        assert "error_rate" in bucket, "Missing error_rate in bucket_low"
        assert "avg_conf_before" in bucket, "Missing avg_conf_before in bucket_low"
        assert "avg_conf_after" in bucket, "Missing avg_conf_after in bucket_low"
        print(f"✓ bucket_low: count={bucket['count']}, error_rate={bucket['error_rate']}%")

    def test_shadow_stats_has_bucket_medium(self):
        """shadow-stats has bucket_medium with error_rate"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        assert "bucket_medium" in data, "Missing bucket_medium"
        bucket = data["bucket_medium"]
        assert "count" in bucket, "Missing count in bucket_medium"
        assert "error_rate" in bucket, "Missing error_rate in bucket_medium"
        print(f"✓ bucket_medium: count={bucket['count']}, error_rate={bucket['error_rate']}%")

    def test_shadow_stats_has_bucket_high(self):
        """shadow-stats has bucket_high with error_rate"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        assert "bucket_high" in data, "Missing bucket_high"
        bucket = data["bucket_high"]
        assert "count" in bucket, "Missing count in bucket_high"
        assert "error_rate" in bucket, "Missing error_rate in bucket_high"
        print(f"✓ bucket_high: count={bucket['count']}, error_rate={bucket['error_rate']}%")

    def test_shadow_stats_has_model_validation(self):
        """shadow-stats has model_validation with verdict"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        assert "model_validation" in data, "Missing model_validation"
        mv = data["model_validation"]
        assert "verdict" in mv, "Missing verdict in model_validation"
        assert "high_worse_than_low" in mv, "Missing high_worse_than_low"
        assert "high_error_rate" in mv, "Missing high_error_rate"
        assert "low_error_rate" in mv, "Missing low_error_rate"
        print(f"✓ model_validation: verdict={mv['verdict']}, high_worse_than_low={mv['high_worse_than_low']}")

    def test_model_validation_verdict_is_useful(self):
        """model_validation verdict is USEFUL (high_error_rate > low_error_rate)"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        mv = data.get("model_validation", {})
        assert mv.get("verdict") == "USEFUL", f"Expected verdict=USEFUL, got {mv.get('verdict')}"
        assert mv.get("high_worse_than_low") is True, "high_worse_than_low should be True"
        print(f"✓ Model is USEFUL: high_error_rate ({mv['high_error_rate']}%) > low_error_rate ({mv['low_error_rate']}%)")

    def test_shadow_stats_has_risk_percentiles(self):
        """shadow-stats has risk_percentiles"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        assert "risk_percentiles" in data, "Missing risk_percentiles"
        pctl = data["risk_percentiles"]
        assert "p50" in pctl, "Missing p50"
        assert "p75" in pctl, "Missing p75"
        assert "p90" in pctl, "Missing p90"
        assert "p95" in pctl, "Missing p95"
        print(f"✓ risk_percentiles: p50={pctl['p50']}, p75={pctl['p75']}, p90={pctl['p90']}, p95={pctl['p95']}")


class TestMlRiskBuildDataset:
    """Tests for POST /api/ml-risk/build-dataset endpoint"""

    def test_build_dataset_returns_200(self):
        """POST /api/ml-risk/build-dataset returns 200"""
        response = requests.post(f"{BASE_URL}/api/ml-risk/build-dataset?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/ml-risk/build-dataset returns 200")

    def test_build_dataset_has_valid_rows(self):
        """build-dataset returns valid_rows count"""
        response = requests.post(f"{BASE_URL}/api/ml-risk/build-dataset?limit=10")
        data = response.json()
        assert "valid_rows" in data, "Missing valid_rows"
        assert data["valid_rows"] >= 0, "valid_rows should be >= 0"
        print(f"✓ valid_rows = {data['valid_rows']}")

    def test_build_dataset_has_target_distribution(self):
        """build-dataset returns target_distribution"""
        response = requests.post(f"{BASE_URL}/api/ml-risk/build-dataset?limit=10")
        data = response.json()
        assert "target_distribution" in data, "Missing target_distribution"
        td = data["target_distribution"]
        assert "error" in td, "Missing error count"
        assert "correct" in td, "Missing correct count"
        print(f"✓ target_distribution: error={td['error']}, correct={td['correct']}")


class TestMlRiskTrain:
    """Tests for POST /api/ml-risk/train endpoint"""

    def test_train_returns_200(self):
        """POST /api/ml-risk/train returns 200"""
        response = requests.post(f"{BASE_URL}/api/ml-risk/train")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/ml-risk/train returns 200")

    def test_train_returns_metrics(self):
        """train returns metrics with roc_auc"""
        response = requests.post(f"{BASE_URL}/api/ml-risk/train")
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data.get('ok')}"
        assert "metrics" in data, "Missing metrics"
        metrics = data["metrics"]
        assert "roc_auc" in metrics, "Missing roc_auc in metrics"
        print(f"✓ train returned roc_auc = {metrics['roc_auc']:.4f}")


class TestMlRiskShadowScore:
    """Tests for POST /api/ml-risk/shadow-score endpoint"""

    def test_shadow_score_returns_200(self):
        """POST /api/ml-risk/shadow-score returns 200"""
        response = requests.post(f"{BASE_URL}/api/ml-risk/shadow-score?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/ml-risk/shadow-score returns 200")

    def test_shadow_score_has_scored_count(self):
        """shadow-score returns scored count"""
        response = requests.post(f"{BASE_URL}/api/ml-risk/shadow-score?limit=5")
        data = response.json()
        assert "scored" in data, "Missing scored field"
        assert "total_checked" in data, "Missing total_checked field"
        print(f"✓ shadow-score: scored={data['scored']}, total_checked={data['total_checked']}")


class TestMlRiskIntegration:
    """Integration tests for ML Risk Overlay V1"""

    def test_full_flow_status_to_shadow_stats(self):
        """Full flow: status shows model trained, shadow-stats shows buckets"""
        # 1. Check status
        status_resp = requests.get(f"{BASE_URL}/api/ml-risk/status")
        assert status_resp.status_code == 200
        status = status_resp.json()
        assert status["model_trained"] is True, "Model should be trained"
        assert status["dataset_size"] == 432, f"Expected 432 samples, got {status['dataset_size']}"
        
        # 2. Check shadow stats
        shadow_resp = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        assert shadow_resp.status_code == 200
        shadow = shadow_resp.json()
        assert shadow["total"] == 433, f"Expected 433 shadow scored, got {shadow['total']}"
        
        # 3. Verify model validation
        mv = shadow["model_validation"]
        assert mv["verdict"] == "USEFUL", f"Expected USEFUL, got {mv['verdict']}"
        assert mv["high_error_rate"] > mv["low_error_rate"], "High risk should have higher error rate"
        
        print("✓ Full integration flow verified:")
        print(f"  - Model trained: {status['model_trained']}")
        print(f"  - Dataset size: {status['dataset_size']}")
        print(f"  - Shadow scored: {status['shadow_scored']}")
        print(f"  - ROC AUC: {status['metrics']['roc_auc']:.4f}")
        print(f"  - Verdict: {mv['verdict']}")
        print(f"  - High error rate: {mv['high_error_rate']}%")
        print(f"  - Low error rate: {mv['low_error_rate']}%")

    def test_risk_buckets_distribution(self):
        """Risk buckets have expected distribution"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        
        low = data["bucket_low"]
        med = data["bucket_medium"]
        high = data["bucket_high"]
        
        total = low["count"] + med["count"] + high["count"]
        assert total == data["total"], f"Bucket counts should sum to total: {total} != {data['total']}"
        
        # Verify error rates increase with risk
        assert high["error_rate"] > med["error_rate"], "High risk should have higher error rate than medium"
        assert med["error_rate"] > low["error_rate"], "Medium risk should have higher error rate than low"
        
        print("✓ Risk bucket distribution verified:")
        print(f"  - Low: {low['count']} ({low['error_rate']}% error)")
        print(f"  - Medium: {med['count']} ({med['error_rate']}% error)")
        print(f"  - High: {high['count']} ({high['error_rate']}% error)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
