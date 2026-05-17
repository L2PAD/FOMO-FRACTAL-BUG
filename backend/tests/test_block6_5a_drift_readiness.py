"""
Block 6 (Drift Intelligence Layer) + Block 5.A (ML Data Readiness) API Tests
=============================================================================

Tests for:
- GET /api/drift/intelligence - Full drift intelligence report
- GET /api/ml-overlay/readiness - ML dataset readiness dashboard
- GET /api/ml-overlay/proto-overlay - Rule-based risk overlay
- GET /api/market/chart/exchange-v2 - Exchange chart with phase risk flags

All endpoints are GET requests, no authentication required.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestDriftIntelligenceEndpoint:
    """Block 6 - GET /api/drift/intelligence tests"""

    def test_drift_intelligence_basic(self):
        """Test /api/drift/intelligence returns expected structure"""
        response = requests.get(
            f"{BASE_URL}/api/drift/intelligence",
            params={"horizon": 7, "asset": "BTC"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=True"
        
        # Verify drift_score and level
        assert "drift_score" in data, "Missing drift_score"
        assert isinstance(data["drift_score"], (int, float)), "drift_score should be numeric"
        assert 0 <= data["drift_score"] <= 1, "drift_score should be 0-1"
        
        assert "level" in data, "Missing level"
        assert data["level"] in ["low", "medium", "high", "critical"], f"Invalid level: {data['level']}"

    def test_drift_intelligence_alerts(self):
        """Test alerts field in drift/intelligence response"""
        response = requests.get(
            f"{BASE_URL}/api/drift/intelligence",
            params={"horizon": 7, "asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "alerts" in data, "Missing alerts field"
        assert isinstance(data["alerts"], list), "alerts should be a list"
        
        # If alerts exist, verify structure
        for alert in data["alerts"]:
            assert "type" in alert, "Alert missing type"
            assert "severity" in alert, "Alert missing severity"
            assert "message" in alert, "Alert missing message"

    def test_drift_intelligence_recommendations(self):
        """Test recommendations field in drift/intelligence response"""
        response = requests.get(
            f"{BASE_URL}/api/drift/intelligence",
            params={"horizon": 7, "asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "recommendations" in data, "Missing recommendations field"
        assert isinstance(data["recommendations"], list), "recommendations should be a list"
        
        # If recommendations exist, verify structure
        for rec in data["recommendations"]:
            assert "priority" in rec, "Recommendation missing priority"
            assert "action" in rec, "Recommendation missing action"
            assert "description" in rec, "Recommendation missing description"

    def test_drift_intelligence_metrics_structure(self):
        """Test metrics field has all required sub-dimensions"""
        response = requests.get(
            f"{BASE_URL}/api/drift/intelligence",
            params={"horizon": 7, "asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "metrics" in data, "Missing metrics field"
        
        metrics = data["metrics"]
        
        # by_time dimension
        assert "by_time" in metrics, "Missing by_time in metrics"
        assert isinstance(metrics["by_time"], dict), "by_time should be a dict"
        
        # by_confidence dimension
        assert "by_confidence" in metrics, "Missing by_confidence in metrics"
        assert isinstance(metrics["by_confidence"], dict), "by_confidence should be a dict"
        
        # by_version dimension
        assert "by_version" in metrics, "Missing by_version in metrics"
        assert isinstance(metrics["by_version"], dict), "by_version should be a dict"
        
        # by_direction dimension
        assert "by_direction" in metrics, "Missing by_direction in metrics"
        assert isinstance(metrics["by_direction"], dict), "by_direction should be a dict"
        
        # by_regime dimension
        assert "by_regime" in metrics, "Missing by_regime in metrics"
        assert isinstance(metrics["by_regime"], dict), "by_regime should be a dict"
        
        # label_trend dimension
        assert "label_trend" in metrics, "Missing label_trend in metrics"
        assert isinstance(metrics["label_trend"], dict), "label_trend should be a dict"

    def test_drift_intelligence_global_metrics(self):
        """Test global metrics structure in drift/intelligence response"""
        response = requests.get(
            f"{BASE_URL}/api/drift/intelligence",
            params={"horizon": 7, "asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        global_metrics = data.get("metrics", {}).get("global", {})
        
        # Verify global metrics fields
        assert "n" in global_metrics, "Missing n in global metrics"
        assert "accuracy" in global_metrics, "Missing accuracy in global metrics"
        assert "pnl" in global_metrics, "Missing pnl in global metrics"
        assert "catastrophic_rate" in global_metrics, "Missing catastrophic_rate in global metrics"
        assert "avg_error" in global_metrics, "Missing avg_error in global metrics"

    def test_drift_intelligence_score_components(self):
        """Test score_components breakdown in drift/intelligence response"""
        response = requests.get(
            f"{BASE_URL}/api/drift/intelligence",
            params={"horizon": 7, "asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "score_components" in data, "Missing score_components"
        
        components = data["score_components"]
        assert "accuracy_drop" in components, "Missing accuracy_drop in score_components"
        assert "pnl_drop" in components, "Missing pnl_drop in score_components"
        assert "catastrophic" in components, "Missing catastrophic in score_components"

    def test_drift_intelligence_with_different_window(self):
        """Test drift/intelligence with different rolling window parameter"""
        response = requests.get(
            f"{BASE_URL}/api/drift/intelligence",
            params={"horizon": 7, "asset": "BTC", "window": 30}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True


class TestMLReadinessEndpoint:
    """Block 5.A.2 - GET /api/ml-overlay/readiness tests"""

    def test_readiness_basic(self):
        """Test /api/ml-overlay/readiness returns expected structure"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/readiness",
            params={"horizon": 7, "asset": "BTC"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=True"
        
        # Verify verdict
        assert "verdict" in data, "Missing verdict"
        assert data["verdict"] in ["READY", "HOLD", "NO_DATA"], f"Invalid verdict: {data['verdict']}"
        
        # Verify passed count
        assert "passed" in data, "Missing passed count"
        assert "/" in data["passed"], "passed should be in format 'X/6'"

    def test_readiness_metrics_coverage(self):
        """Test coverage metrics in readiness response"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/readiness",
            params={"horizon": 7, "asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        metrics = data.get("metrics", {})
        
        # Verify coverage sub-metrics
        assert "coverage" in metrics, "Missing coverage in metrics"
        coverage = metrics["coverage"]
        
        assert "observations" in coverage, "Missing observations coverage"
        assert "funding" in coverage, "Missing funding coverage"
        assert "tactical" in coverage, "Missing tactical coverage"
        
        # Verify coverage values are between 0 and 1
        for key, val in coverage.items():
            assert 0 <= val <= 1, f"{key} coverage should be 0-1, got {val}"

    def test_readiness_metrics_distribution(self):
        """Test distribution metrics in readiness response"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/readiness",
            params={"horizon": 7, "asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        metrics = data.get("metrics", {})
        
        # Verify distribution sub-metrics
        assert "distribution" in metrics, "Missing distribution in metrics"
        dist = metrics["distribution"]
        
        assert "neutral_share" in dist, "Missing neutral_share"
        assert "non_neutral_share" in dist, "Missing non_neutral_share"
        assert "confidence_std" in dist, "Missing confidence_std"

    def test_readiness_thresholds_and_checks(self):
        """Test thresholds and checks fields in readiness response"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/readiness",
            params={"horizon": 7, "asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify thresholds
        assert "thresholds" in data, "Missing thresholds"
        thresholds = data["thresholds"]
        
        expected_threshold_keys = [
            "obs_coverage", "funding_coverage", "tactical_coverage",
            "non_neutral_share", "confidence_std", "usable_rows"
        ]
        for key in expected_threshold_keys:
            assert key in thresholds, f"Missing threshold: {key}"
        
        # Verify checks
        assert "checks" in data, "Missing checks"
        checks = data["checks"]
        
        for key in expected_threshold_keys:
            assert key in checks, f"Missing check: {key}"
            assert isinstance(checks[key], bool), f"Check {key} should be boolean"

    def test_readiness_row_counts(self):
        """Test row count metrics in readiness response"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/readiness",
            params={"horizon": 7, "asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        metrics = data.get("metrics", {})
        
        assert "total_rows" in metrics, "Missing total_rows"
        assert "modern_rows" in metrics, "Missing modern_rows"
        assert "usable_rows" in metrics, "Missing usable_rows"
        
        # Verify counts are non-negative integers
        assert metrics["total_rows"] >= 0, "total_rows should be >= 0"
        assert metrics["modern_rows"] >= 0, "modern_rows should be >= 0"
        assert metrics["usable_rows"] >= 0, "usable_rows should be >= 0"


class TestProtoOverlayEndpoint:
    """Block 5.A.6 - GET /api/ml-overlay/proto-overlay tests"""

    def test_proto_overlay_basic(self):
        """Test /api/ml-overlay/proto-overlay returns expected structure"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/proto-overlay",
            params={"asset": "BTC"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=True"
        
        # Verify risk_score
        assert "risk_score" in data, "Missing risk_score"
        assert isinstance(data["risk_score"], (int, float)), "risk_score should be numeric"
        assert 0 <= data["risk_score"] <= 1, "risk_score should be 0-1"

    def test_proto_overlay_multipliers(self):
        """Test multiplier fields in proto-overlay response"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/proto-overlay",
            params={"asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify size_mult
        assert "size_mult" in data, "Missing size_mult"
        assert 0.5 <= data["size_mult"] <= 1.0, f"size_mult should be 0.5-1.0, got {data['size_mult']}"
        
        # Verify confidence_mult
        assert "confidence_mult" in data, "Missing confidence_mult"
        assert 0.7 <= data["confidence_mult"] <= 1.0, f"confidence_mult should be 0.7-1.0, got {data['confidence_mult']}"

    def test_proto_overlay_flags(self):
        """Test flags field in proto-overlay response"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/proto-overlay",
            params={"asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify flags is a list
        assert "flags" in data, "Missing flags"
        assert isinstance(data["flags"], list), "flags should be a list"
        
        # Verify known flag types if present
        known_flags = [
            "unstable_transition", "high_entropy", "wide_scenario_spread",
            "tactical_bearish_high_uncertainty", "tactical_bearish", "high_uncertainty"
        ]
        for flag in data["flags"]:
            assert flag in known_flags, f"Unknown flag: {flag}"

    def test_proto_overlay_action(self):
        """Test action field in proto-overlay response"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/proto-overlay",
            params={"asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify action
        assert "action" in data, "Missing action"
        valid_actions = ["strong_penalty", "soft_penalty", "flag_only", "none"]
        assert data["action"] in valid_actions, f"Invalid action: {data['action']}"

    def test_proto_overlay_context(self):
        """Test context field in proto-overlay response"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/proto-overlay",
            params={"asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify context
        assert "context" in data, "Missing context"
        context = data["context"]
        
        # Verify context fields
        expected_context_fields = ["entropy", "uncertainty", "tactical_bias", "regime_flags"]
        for field in expected_context_fields:
            assert field in context, f"Missing context field: {field}"


class TestExchangeChartV2Endpoint:
    """Exchange chart v2 tests with phase risk flags"""

    def test_exchange_chart_v2_basic(self):
        """Test /api/market/chart/exchange-v2 returns expected structure"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v2",
            params={"symbol": "BTCUSDT", "horizon": "7D"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=True"

    def test_exchange_chart_v2_forecast(self):
        """Test forecast field in exchange-v2 response"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v2",
            params={"symbol": "BTCUSDT", "horizon": "7D"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "forecast" in data, "Missing forecast"
        
        forecast = data["forecast"]
        assert "entry" in forecast, "Missing entry in forecast"
        assert "targetFinal" in forecast, "Missing targetFinal in forecast"
        assert "direction" in forecast, "Missing direction in forecast"
        assert "bandLow" in forecast, "Missing bandLow in forecast"
        assert "bandHigh" in forecast, "Missing bandHigh in forecast"

    def test_exchange_chart_v2_reliability(self):
        """Test reliability field in exchange-v2 response"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v2",
            params={"symbol": "BTCUSDT", "horizon": "7D"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "reliability" in data, "Missing reliability"
        
        reliability = data["reliability"]
        assert "rawConfidence" in reliability, "Missing rawConfidence"
        assert "finalConfidence" in reliability, "Missing finalConfidence"

    def test_exchange_chart_v2_chart_candles(self):
        """Test chart candles in exchange-v2 response"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v2",
            params={"symbol": "BTCUSDT", "horizon": "7D"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "chart" in data, "Missing chart"
        assert "candles" in data["chart"], "Missing candles in chart"
        
        candles = data["chart"]["candles"]
        assert isinstance(candles, list), "candles should be a list"
        assert len(candles) > 0, "candles should not be empty"
        
        # Verify candle structure
        candle = candles[0]
        assert "time" in candle, "Missing time in candle"
        assert "open" in candle, "Missing open in candle"
        assert "high" in candle, "Missing high in candle"
        assert "low" in candle, "Missing low in candle"
        assert "close" in candle, "Missing close in candle"

    def test_exchange_chart_v2_meta(self):
        """Test meta field in exchange-v2 response"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v2",
            params={"symbol": "BTCUSDT", "horizon": "7D"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "meta" in data, "Missing meta"
        
        meta = data["meta"]
        assert "symbol" in meta, "Missing symbol in meta"
        assert "horizon" in meta, "Missing horizon in meta"
        assert "generatedAt" in meta, "Missing generatedAt in meta"


class TestCrossEndpointConsistency:
    """Cross-endpoint consistency tests"""

    def test_drift_and_readiness_horizon_consistency(self):
        """Verify drift and readiness use same horizon format"""
        drift_response = requests.get(
            f"{BASE_URL}/api/drift/intelligence",
            params={"horizon": 7, "asset": "BTC"}
        )
        readiness_response = requests.get(
            f"{BASE_URL}/api/ml-overlay/readiness",
            params={"horizon": 7, "asset": "BTC"}
        )
        
        assert drift_response.status_code == 200
        assert readiness_response.status_code == 200
        
        drift_data = drift_response.json()
        readiness_data = readiness_response.json()
        
        # Both should succeed
        assert drift_data.get("ok") is True
        assert readiness_data.get("ok") is True

    def test_proto_overlay_uses_forecast_context(self):
        """Verify proto-overlay pulls context from forecast audit"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/proto-overlay",
            params={"asset": "BTC"}
        )
        assert response.status_code == 200
        
        data = response.json()
        context = data.get("context", {})
        
        # Should have regime_flags from forecast audit
        assert "regime_flags" in context
        assert isinstance(context["regime_flags"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
