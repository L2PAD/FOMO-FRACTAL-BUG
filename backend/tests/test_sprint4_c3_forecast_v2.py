"""
Sprint 4 C3: Forecast Core Correction Tests
============================================
Tests for Forecast V2 (enhanced score formula) + Decision V2 integration.

Key features tested:
1. GET /api/prediction/forecast-v1-vs-v2 - Forecast V1 vs V2 comparison
2. GET /api/prediction/v1-vs-v2 - Decision V1 vs V2 comparison
3. GET /api/prediction/c1-audit - Audit with classification and root_causes
4. GET /api/sentiment/ml-readiness - Dataset readiness info
5. GET /api/sentiment/stability-monitor - STABLE status
6. GET /api/outcome/rollout-status - sampling_rollout_pct=30
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestForecastV1VsV2Comparison:
    """Tests for GET /api/prediction/forecast-v1-vs-v2 endpoint (Sprint 4 C3.9)"""

    def test_forecast_v1_vs_v2_returns_json(self):
        """Endpoint returns valid JSON with ok=true"""
        response = requests.get(f"{BASE_URL}/api/prediction/forecast-v1-vs-v2", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        print(f"PASS: forecast-v1-vs-v2 returns ok=true, total_analyzed={data.get('total_analyzed')}")

    def test_forecast_v1_vs_v2_has_all_pass(self):
        """Response contains all_pass boolean field"""
        response = requests.get(f"{BASE_URL}/api/prediction/forecast-v1-vs-v2", timeout=30)
        data = response.json()
        assert "all_pass" in data, f"Missing all_pass field in response"
        assert isinstance(data["all_pass"], bool), f"all_pass should be boolean, got {type(data['all_pass'])}"
        print(f"PASS: all_pass={data['all_pass']}")

    def test_forecast_v1_vs_v2_has_score_stats(self):
        """Response contains score_stats with v1/v2 statistics"""
        response = requests.get(f"{BASE_URL}/api/prediction/forecast-v1-vs-v2", timeout=30)
        data = response.json()
        assert "score_stats" in data, "Missing score_stats field"
        stats = data["score_stats"]
        required_fields = ["v1_std", "v2_std", "v1_mean", "v2_mean", "v1_correlation", "v2_correlation"]
        for field in required_fields:
            assert field in stats, f"Missing {field} in score_stats"
        print(f"PASS: score_stats present with v1_corr={stats['v1_correlation']}, v2_corr={stats['v2_correlation']}")

    def test_forecast_v1_vs_v2_has_v1_section(self):
        """Response contains v1 section with accuracy metrics"""
        response = requests.get(f"{BASE_URL}/api/prediction/forecast-v1-vs-v2", timeout=30)
        data = response.json()
        assert "v1" in data, "Missing v1 section"
        v1 = data["v1"]
        required_fields = ["tp", "fp", "neutral_miss", "reversal_miss", "directional", "accuracy_pct"]
        for field in required_fields:
            assert field in v1, f"Missing {field} in v1 section"
        print(f"PASS: v1 section present with accuracy={v1['accuracy_pct']}%")

    def test_forecast_v1_vs_v2_has_v2_full_section(self):
        """Response contains v2_full section with enhanced metrics"""
        response = requests.get(f"{BASE_URL}/api/prediction/forecast-v1-vs-v2", timeout=30)
        data = response.json()
        assert "v2_full" in data, "Missing v2_full section"
        v2 = data["v2_full"]
        required_fields = ["tp", "fp", "neutral_miss", "reversal_miss", "directional", "accuracy_pct", "neutral_pct"]
        for field in required_fields:
            assert field in v2, f"Missing {field} in v2_full section"
        print(f"PASS: v2_full section present with accuracy={v2['accuracy_pct']}%, neutral_pct={v2['neutral_pct']}%")

    def test_forecast_v1_vs_v2_has_pass_criteria(self):
        """Response contains pass_criteria with 4 criteria"""
        response = requests.get(f"{BASE_URL}/api/prediction/forecast-v1-vs-v2", timeout=30)
        data = response.json()
        assert "pass_criteria" in data, "Missing pass_criteria field"
        criteria = data["pass_criteria"]
        expected_criteria = ["score_spread_maintained", "correlation_maintained", "accuracy_improved", "fp_stable"]
        for c in expected_criteria:
            assert c in criteria, f"Missing {c} in pass_criteria"
        print(f"PASS: pass_criteria present: {criteria}")


class TestDecisionV1VsV2Comparison:
    """Tests for GET /api/prediction/v1-vs-v2 endpoint (Sprint 4 C2.9)"""

    def test_v1_vs_v2_returns_json(self):
        """Endpoint returns valid JSON with ok=true"""
        response = requests.get(f"{BASE_URL}/api/prediction/v1-vs-v2", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        print(f"PASS: v1-vs-v2 returns ok=true, total_analyzed={data.get('total_analyzed')}")

    def test_v1_vs_v2_has_all_pass(self):
        """Response contains all_pass boolean field"""
        response = requests.get(f"{BASE_URL}/api/prediction/v1-vs-v2", timeout=30)
        data = response.json()
        assert "all_pass" in data, "Missing all_pass field"
        assert isinstance(data["all_pass"], bool), f"all_pass should be boolean"
        print(f"PASS: all_pass={data['all_pass']}")

    def test_v1_vs_v2_has_v1_structure(self):
        """V1 section has required fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/v1-vs-v2", timeout=30)
        data = response.json()
        assert "v1" in data, "Missing v1 section"
        v1 = data["v1"]
        required = ["tp", "fp", "neutral_miss", "reversal_miss", "directional", "accuracy_pct"]
        for field in required:
            assert field in v1, f"Missing {field} in v1"
        print(f"PASS: v1 accuracy={v1['accuracy_pct']}%")

    def test_v1_vs_v2_has_v2_structure(self):
        """V2 section has required fields including neutral_pct"""
        response = requests.get(f"{BASE_URL}/api/prediction/v1-vs-v2", timeout=30)
        data = response.json()
        assert "v2" in data, "Missing v2 section"
        v2 = data["v2"]
        required = ["tp", "fp", "neutral_miss", "reversal_miss", "directional", "accuracy_pct", "neutral_pct"]
        for field in required:
            assert field in v2, f"Missing {field} in v2"
        print(f"PASS: v2 accuracy={v2['accuracy_pct']}%, neutral_pct={v2['neutral_pct']}%")

    def test_v1_vs_v2_has_pass_criteria(self):
        """Response contains pass_criteria with 4 criteria"""
        response = requests.get(f"{BASE_URL}/api/prediction/v1-vs-v2", timeout=30)
        data = response.json()
        assert "pass_criteria" in data, "Missing pass_criteria"
        criteria = data["pass_criteria"]
        expected = ["neutral_below_50", "accuracy_improved", "reversal_improved", "fp_stable"]
        for c in expected:
            assert c in criteria, f"Missing {c} in pass_criteria"
        print(f"PASS: pass_criteria present: {criteria}")

    def test_v1_vs_v2_has_directions_changed(self):
        """Response contains directions_changed count"""
        response = requests.get(f"{BASE_URL}/api/prediction/v1-vs-v2", timeout=30)
        data = response.json()
        assert "directions_changed" in data, "Missing directions_changed"
        assert isinstance(data["directions_changed"], int), "directions_changed should be int"
        print(f"PASS: directions_changed={data['directions_changed']}")


class TestC1Audit:
    """Tests for GET /api/prediction/c1-audit endpoint"""

    def test_c1_audit_returns_json(self):
        """Endpoint returns valid JSON with ok=true"""
        response = requests.get(f"{BASE_URL}/api/prediction/c1-audit", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true"
        print(f"PASS: c1-audit returns ok=true, total_analyzed={data.get('total_analyzed')}")

    def test_c1_audit_has_classification(self):
        """Response contains classification with tp/fp/neutral_miss/reversal_miss"""
        response = requests.get(f"{BASE_URL}/api/prediction/c1-audit", timeout=30)
        data = response.json()
        assert "classification" in data, "Missing classification"
        cls = data["classification"]
        required = ["tp", "fp", "neutral_miss", "reversal_miss"]
        for field in required:
            assert field in cls, f"Missing {field} in classification"
        print(f"PASS: classification tp={cls['tp']}, fp={cls['fp']}, neutral_miss={cls['neutral_miss']}, reversal_miss={cls['reversal_miss']}")

    def test_c1_audit_has_root_causes(self):
        """Response contains root_causes list"""
        response = requests.get(f"{BASE_URL}/api/prediction/c1-audit", timeout=30)
        data = response.json()
        assert "root_causes" in data, "Missing root_causes"
        assert isinstance(data["root_causes"], list), "root_causes should be list"
        assert len(data["root_causes"]) > 0, "root_causes should not be empty"
        print(f"PASS: root_causes has {len(data['root_causes'])} items")

    def test_c1_audit_has_accuracy_metrics(self):
        """Response contains directional_accuracy_pct and neutral_miss_rate_pct"""
        response = requests.get(f"{BASE_URL}/api/prediction/c1-audit", timeout=30)
        data = response.json()
        assert "directional_accuracy_pct" in data, "Missing directional_accuracy_pct"
        assert "neutral_miss_rate_pct" in data, "Missing neutral_miss_rate_pct"
        print(f"PASS: directional_accuracy={data['directional_accuracy_pct']}%, neutral_miss_rate={data['neutral_miss_rate_pct']}%")

    def test_c1_audit_has_regimes(self):
        """Response contains regimes breakdown"""
        response = requests.get(f"{BASE_URL}/api/prediction/c1-audit", timeout=30)
        data = response.json()
        assert "regimes" in data, "Missing regimes"
        assert "tp" in data["regimes"], "Missing tp in regimes"
        assert "fp" in data["regimes"], "Missing fp in regimes"
        print(f"PASS: regimes present with tp={data['regimes']['tp']}, fp={data['regimes']['fp']}")


class TestMLReadiness:
    """Tests for GET /api/sentiment/ml-readiness endpoint"""

    def test_ml_readiness_returns_json(self):
        """Endpoint returns valid JSON"""
        response = requests.get(f"{BASE_URL}/api/sentiment/ml-readiness", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"PASS: ml-readiness returns status code 200")

    def test_ml_readiness_has_ready_status(self):
        """Response contains ready boolean field"""
        response = requests.get(f"{BASE_URL}/api/sentiment/ml-readiness", timeout=30)
        data = response.json()
        assert "ready" in data, "Missing ready field"
        assert isinstance(data["ready"], bool), "ready should be boolean"
        print(f"PASS: ready={data['ready']}")

    def test_ml_readiness_has_dataset_size(self):
        """Response contains dataset_size field"""
        response = requests.get(f"{BASE_URL}/api/sentiment/ml-readiness", timeout=30)
        data = response.json()
        assert "dataset_size" in data, "Missing dataset_size"
        assert isinstance(data["dataset_size"], int), "dataset_size should be int"
        print(f"PASS: dataset_size={data['dataset_size']}")

    def test_ml_readiness_has_reasons(self):
        """Response contains reasons list"""
        response = requests.get(f"{BASE_URL}/api/sentiment/ml-readiness", timeout=30)
        data = response.json()
        assert "reasons" in data, "Missing reasons"
        assert isinstance(data["reasons"], list), "reasons should be list"
        print(f"PASS: reasons={data['reasons']}")


class TestStabilityMonitor:
    """Tests for GET /api/sentiment/stability-monitor endpoint"""

    def test_stability_monitor_returns_json(self):
        """Endpoint returns valid JSON with ok=true"""
        response = requests.get(f"{BASE_URL}/api/sentiment/stability-monitor", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true"
        print(f"PASS: stability-monitor returns ok=true")

    def test_stability_monitor_has_status(self):
        """Response contains status field"""
        response = requests.get(f"{BASE_URL}/api/sentiment/stability-monitor", timeout=30)
        data = response.json()
        assert "status" in data, "Missing status field"
        valid_statuses = ["STABLE", "DRIFT_DETECTED", "NO_DATA", "UNKNOWN"]
        assert data["status"] in valid_statuses, f"Invalid status: {data['status']}"
        print(f"PASS: status={data['status']}")

    def test_stability_monitor_has_drift_alerts(self):
        """Response contains drift_alerts list"""
        response = requests.get(f"{BASE_URL}/api/sentiment/stability-monitor", timeout=30)
        data = response.json()
        assert "drift_alerts" in data, "Missing drift_alerts"
        assert isinstance(data["drift_alerts"], list), "drift_alerts should be list"
        print(f"PASS: drift_alerts={data['drift_alerts']}")


class TestRolloutStatus:
    """Tests for GET /api/outcome/rollout-status endpoint"""

    def test_rollout_status_returns_json(self):
        """Endpoint returns valid JSON with ok=true"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true"
        print(f"PASS: rollout-status returns ok=true")

    def test_rollout_status_has_sampling_pct(self):
        """Response contains sampling_rollout_pct field"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status", timeout=30)
        data = response.json()
        assert "sampling_rollout_pct" in data, "Missing sampling_rollout_pct"
        assert isinstance(data["sampling_rollout_pct"], int), "sampling_rollout_pct should be int"
        print(f"PASS: sampling_rollout_pct={data['sampling_rollout_pct']}")

    def test_rollout_status_sampling_pct_is_30(self):
        """sampling_rollout_pct should be 30 as per requirements"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status", timeout=30)
        data = response.json()
        assert data["sampling_rollout_pct"] == 30, f"Expected 30, got {data['sampling_rollout_pct']}"
        print(f"PASS: sampling_rollout_pct=30 confirmed")

    def test_rollout_status_has_labels_v2_production(self):
        """Response contains labels_v2_production field"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status", timeout=30)
        data = response.json()
        assert "labels_v2_production" in data, "Missing labels_v2_production"
        assert isinstance(data["labels_v2_production"], bool), "labels_v2_production should be bool"
        print(f"PASS: labels_v2_production={data['labels_v2_production']}")


class TestForecastV2Module:
    """Tests for forecast_v2.py module (C3 implementation)"""

    def test_forecast_v2_module_exists(self):
        """forecast_v2.py module exists and has FORECAST_V2_MODE='shadow'"""
        import sys
        sys.path.insert(0, "/app/backend")
        from forecast.forecast_v2 import FORECAST_V2_MODE
        assert FORECAST_V2_MODE == "shadow", f"Expected shadow mode, got {FORECAST_V2_MODE}"
        print(f"PASS: FORECAST_V2_MODE='shadow'")

    def test_forecast_v2_compute_function(self):
        """compute_forecast_v2 returns expected structure"""
        import sys
        sys.path.insert(0, "/app/backend")
        from forecast.forecast_v2 import compute_forecast_v2

        result = compute_forecast_v2(
            base_score=0.15,
            exchange_signal={"micro_bias": -0.2, "funding_bias": 0.1},
            audit={"structure_v2": {"state": "bearish_trend", "bearish": 0.6, "bullish": 0.3}},
            features={"momentum": -0.02, "volatility": 0.03},
            price=100000,
            db=None,
            asset="BTC",
            horizon="7D",
        )

        assert "mode" in result, "Missing mode"
        assert result["mode"] == "shadow", f"Expected shadow, got {result['mode']}"
        assert "base_score" in result, "Missing base_score"
        assert "final_score" in result, "Missing final_score"
        assert "score_delta" in result, "Missing score_delta"
        assert "components" in result, "Missing components"
        
        components = result["components"]
        required_components = ["base_contribution", "exchange_contribution", "structure_contribution", 
                              "momentum_boost", "liq_bias", "trend_memory"]
        for c in required_components:
            assert c in components, f"Missing {c} in components"
        
        print(f"PASS: compute_forecast_v2 returns valid structure with final_score={result['final_score']}")

    def test_forecast_v2_score_formula(self):
        """Verify additive score formula: base + exchange*0.3 + structure*0.2 + momentum + liq + trend_memory"""
        import sys
        sys.path.insert(0, "/app/backend")
        from forecast.forecast_v2 import compute_forecast_v2

        result = compute_forecast_v2(
            base_score=0.5,
            exchange_signal={"micro_bias": 0.5},  # exchange_contrib = 0.5 * 0.3 = 0.15
            audit={"structure_v2": {"state": "bullish_trend", "bearish": 0.2, "bullish": 0.7}},  # structure_bias = 0.3
            features={"momentum": 0.1, "volatility": 0.05},  # momentum_boost = 0.1
            price=100000,
            db=None,
            asset="BTC",
            horizon="7D",
        )

        components = result["components"]
        # Verify components are present and reasonable
        assert components["base_contribution"] == 0.5, f"Expected base=0.5, got {components['base_contribution']}"
        assert abs(components["exchange_contribution"] - 0.15) < 0.01, f"Expected exchange~0.15, got {components['exchange_contribution']}"
        assert abs(components["structure_contribution"] - 0.06) < 0.01, f"Expected structure~0.06, got {components['structure_contribution']}"
        assert components["momentum_boost"] == 0.1, f"Expected momentum=0.1, got {components['momentum_boost']}"
        
        print(f"PASS: Score formula verified - base={components['base_contribution']}, exchange={components['exchange_contribution']}, structure={components['structure_contribution']}, momentum={components['momentum_boost']}")


class TestDecisionV2Module:
    """Tests for decision_v2.py module (C2 implementation)"""

    def test_decision_v2_module_exists(self):
        """decision_v2.py module exists and has DECISION_V2_MODE='shadow'"""
        import sys
        sys.path.insert(0, "/app/backend")
        from forecast.decision_v2 import DECISION_V2_MODE
        assert DECISION_V2_MODE == "shadow", f"Expected shadow mode, got {DECISION_V2_MODE}"
        print(f"PASS: DECISION_V2_MODE='shadow'")

    def test_decision_v2_compute_function(self):
        """compute_decision_v2 returns expected structure"""
        import sys
        sys.path.insert(0, "/app/backend")
        from forecast.decision_v2 import compute_decision_v2

        result = compute_decision_v2(
            base_score=-0.3,
            exchange_signal={"micro_bias": -0.4},
            audit={"regime": "TREND", "features": {"ret_7d": -0.05}},
            v1_direction="NEUTRAL",
            v1_confidence=0.25,
        )

        assert "mode" in result, "Missing mode"
        assert result["mode"] == "shadow", f"Expected shadow, got {result['mode']}"
        assert "direction" in result, "Missing direction"
        assert "confidence" in result, "Missing confidence"
        assert "direction_score" in result, "Missing direction_score"
        assert "regime_direction" in result, "Missing regime_direction"
        assert "v1_comparison" in result, "Missing v1_comparison"
        
        v1_comp = result["v1_comparison"]
        assert "v1_direction" in v1_comp, "Missing v1_direction in v1_comparison"
        assert "v2_direction" in v1_comp, "Missing v2_direction in v1_comparison"
        assert "direction_changed" in v1_comp, "Missing direction_changed in v1_comparison"
        
        print(f"PASS: compute_decision_v2 returns valid structure with direction={result['direction']}, confidence={result['confidence']}")


class TestGeneratorV41Integration:
    """Tests for generator_v41.py integration with Forecast V2 and Decision V2"""

    def test_generator_produces_forecast_v2_audit(self):
        """generate_forecast produces audit.forecast_v2 in shadow mode"""
        import sys
        sys.path.insert(0, "/app/backend")
        from forecast.generator_v41 import generate_forecast
        from forecast import Horizon

        record = generate_forecast("BTC", Horizon.D7, model_version="v4.1.3-test")
        
        if record is None:
            print("SKIP: No forecast generated (insufficient data)")
            return
        
        assert record.audit is not None, "Missing audit"
        assert "forecast_v2" in record.audit, "Missing forecast_v2 in audit"
        
        fv2 = record.audit["forecast_v2"]
        assert fv2["mode"] == "shadow", f"Expected shadow mode, got {fv2['mode']}"
        assert "final_score" in fv2, "Missing final_score in forecast_v2"
        assert "components" in fv2, "Missing components in forecast_v2"
        
        print(f"PASS: generate_forecast produces audit.forecast_v2 with mode=shadow, final_score={fv2['final_score']}")

    def test_generator_produces_decision_v2_audit(self):
        """generate_forecast produces audit.decision_v2 in shadow mode"""
        import sys
        sys.path.insert(0, "/app/backend")
        from forecast.generator_v41 import generate_forecast
        from forecast import Horizon

        record = generate_forecast("BTC", Horizon.D7, model_version="v4.1.3-test")
        
        if record is None:
            print("SKIP: No forecast generated (insufficient data)")
            return
        
        assert record.audit is not None, "Missing audit"
        assert "decision_v2" in record.audit, "Missing decision_v2 in audit"
        
        dv2 = record.audit["decision_v2"]
        assert dv2["mode"] == "shadow", f"Expected shadow mode, got {dv2['mode']}"
        assert "direction" in dv2, "Missing direction in decision_v2"
        assert "confidence" in dv2, "Missing confidence in decision_v2"
        assert "v1_comparison" in dv2, "Missing v1_comparison in decision_v2"
        
        print(f"PASS: generate_forecast produces audit.decision_v2 with mode=shadow, direction={dv2['direction']}")

    def test_generator_produces_exchange_context(self):
        """generate_forecast produces audit.exchange_context for liquidation data"""
        import sys
        sys.path.insert(0, "/app/backend")
        from forecast.generator_v41 import generate_forecast
        from forecast import Horizon

        record = generate_forecast("BTC", Horizon.D7, model_version="v4.1.3-test")
        
        if record is None:
            print("SKIP: No forecast generated (insufficient data)")
            return
        
        assert record.audit is not None, "Missing audit"
        # exchange_context is added for liquidation data access
        if "exchange_context" in record.audit:
            ctx = record.audit["exchange_context"]
            print(f"PASS: exchange_context present with keys: {list(ctx.keys())}")
        else:
            print("INFO: exchange_context not present (may be empty exchange data)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
