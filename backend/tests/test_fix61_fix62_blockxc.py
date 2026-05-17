"""
Test Suite for FIX 6.1, FIX 6.2 and Block X.C
==============================================
FIX 6.1: NEUTRAL regime risk reduction (2-level protection)
FIX 6.2: Drift Execution Hook (3-level drift adjustments)
Block X.C: Tactical Panel UI as Decision Enhancer

Tests:
- drift_execution_hook.compute_drift_adjustments() logic
- /api/tactical/1d endpoint
- /api/drift/intelligence endpoint
- /api/ml/readiness endpoint
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct module testing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')


class TestFix62DriftExecutionHook:
    """FIX 6.2: Test drift_execution_hook module directly"""
    
    def test_defensive_mode_high_drift(self):
        """drift_score > 0.7 should trigger defensive mode with size_mult=0.6"""
        from drift.drift_execution_hook import compute_drift_adjustments
        
        result = compute_drift_adjustments(0.75, 0.1)
        
        assert result["mode"] == "defensive", f"Expected defensive mode, got {result['mode']}"
        assert result["size_mult"] == 0.6, f"Expected size_mult=0.6, got {result['size_mult']}"
        assert "drift_defensive" in result["flags"], "Expected drift_defensive flag"
        assert result["drift_score"] == 0.75
        assert result["catastrophic_rate"] == 0.1
    
    def test_cautious_mode_medium_drift(self):
        """drift_score > 0.5 (but <= 0.7) should trigger cautious mode with size_mult=0.8"""
        from drift.drift_execution_hook import compute_drift_adjustments
        
        result = compute_drift_adjustments(0.55, 0.1)
        
        assert result["mode"] == "cautious", f"Expected cautious mode, got {result['mode']}"
        assert result["size_mult"] == 0.8, f"Expected size_mult=0.8, got {result['size_mult']}"
        assert "drift_cautious" in result["flags"]
    
    def test_normal_mode_low_drift(self):
        """drift_score <= 0.5 should be normal mode with size_mult=1.0"""
        from drift.drift_execution_hook import compute_drift_adjustments
        
        result = compute_drift_adjustments(0.3, 0.1)
        
        assert result["mode"] == "normal", f"Expected normal mode, got {result['mode']}"
        assert result["size_mult"] == 1.0, f"Expected size_mult=1.0, got {result['size_mult']}"
    
    def test_catastrophic_rate_multiplier(self):
        """catastrophic_rate > 0.25 should apply additional 0.7 multiplier"""
        from drift.drift_execution_hook import compute_drift_adjustments
        
        result = compute_drift_adjustments(0.3, 0.3)  # normal mode + catastrophic
        
        assert result["mode"] == "normal"
        assert result["size_mult"] == 0.7, f"Expected size_mult=0.7 (1.0 * 0.7), got {result['size_mult']}"
        assert "high_catastrophic_rate" in result["flags"]
    
    def test_combined_defensive_and_catastrophic(self):
        """High drift + high catastrophic should stack: 0.6 * 0.7 = 0.42"""
        from drift.drift_execution_hook import compute_drift_adjustments
        
        result = compute_drift_adjustments(0.8, 0.3)
        
        assert result["mode"] == "defensive"
        assert result["size_mult"] == 0.42, f"Expected size_mult=0.42 (0.6*0.7), got {result['size_mult']}"
        assert "drift_defensive" in result["flags"]
        assert "high_catastrophic_rate" in result["flags"]
        assert "extreme_risk_mode" in result["flags"]
    
    def test_size_mult_floor(self):
        """size_mult should never go below 0.3 floor"""
        from drift.drift_execution_hook import compute_drift_adjustments
        
        # Even extreme values should be floored at 0.3
        result = compute_drift_adjustments(0.99, 0.99)
        
        assert result["size_mult"] >= 0.3, f"size_mult should be >= 0.3, got {result['size_mult']}"


class TestTacticalAPI:
    """Block X.C: Test /api/tactical/1d endpoint"""
    
    def test_tactical_1d_returns_ok(self):
        """Tactical endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/tactical/1d?asset=BTC")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
    
    def test_tactical_1d_has_tactical_bias(self):
        """Should return tacticalBias field"""
        response = requests.get(f"{BASE_URL}/api/tactical/1d?asset=BTC")
        data = response.json()
        
        assert "tacticalBias" in data, "Missing tacticalBias field"
        assert data["tacticalBias"] in ["bullish", "bearish", "neutral"], \
            f"Invalid tacticalBias: {data['tacticalBias']}"
    
    def test_tactical_1d_has_execution_advice(self):
        """Should return executionAdvice field"""
        response = requests.get(f"{BASE_URL}/api/tactical/1d?asset=BTC")
        data = response.json()
        
        assert "executionAdvice" in data, "Missing executionAdvice field"
        valid_advice = ["normal", "reduced", "wait", "avoid_aggressive"]
        assert data["executionAdvice"] in valid_advice, \
            f"Invalid executionAdvice: {data['executionAdvice']}"
    
    def test_tactical_1d_has_signals(self):
        """Should return signals object with orderflow, liquidations, funding, absorption"""
        response = requests.get(f"{BASE_URL}/api/tactical/1d?asset=BTC")
        data = response.json()
        
        assert "signals" in data, "Missing signals field"
        signals = data["signals"]
        
        assert "orderflow" in signals, "Missing orderflow in signals"
        assert "liquidations" in signals, "Missing liquidations in signals"
        assert "funding" in signals, "Missing funding in signals"
        assert "absorption" in signals, "Missing absorption in signals"
    
    def test_tactical_1d_has_execution_impact(self):
        """Should return executionImpact object with sizeModifier, sizePct, impacts"""
        response = requests.get(f"{BASE_URL}/api/tactical/1d?asset=BTC")
        data = response.json()
        
        assert "executionImpact" in data, "Missing executionImpact field"
        impact = data["executionImpact"]
        
        assert "sizeModifier" in impact, "Missing sizeModifier in executionImpact"
        assert "sizePct" in impact, "Missing sizePct in executionImpact"
        assert "impacts" in impact, "Missing impacts array in executionImpact"
        assert isinstance(impact["impacts"], list), "impacts should be a list"


class TestDriftIntelligenceAPI:
    """Block 6: Test /api/drift/intelligence endpoint"""
    
    def test_drift_intelligence_returns_ok(self):
        """Drift intelligence endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/drift/intelligence?horizon=7&asset=BTC")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
    
    def test_drift_intelligence_has_drift_score(self):
        """Should return drift_score between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/drift/intelligence?horizon=7&asset=BTC")
        data = response.json()
        
        assert "drift_score" in data, "Missing drift_score field"
        assert 0 <= data["drift_score"] <= 1, f"drift_score out of range: {data['drift_score']}"
    
    def test_drift_intelligence_has_level(self):
        """Should return level (low/medium/high/critical)"""
        response = requests.get(f"{BASE_URL}/api/drift/intelligence?horizon=7&asset=BTC")
        data = response.json()
        
        assert "level" in data, "Missing level field"
        valid_levels = ["low", "medium", "high", "critical"]
        assert data["level"] in valid_levels, f"Invalid level: {data['level']}"
    
    def test_drift_intelligence_has_metrics(self):
        """Should return metrics object with global, by_time, by_confidence, etc."""
        response = requests.get(f"{BASE_URL}/api/drift/intelligence?horizon=7&asset=BTC")
        data = response.json()
        
        assert "metrics" in data, "Missing metrics field"
        metrics = data["metrics"]
        
        assert "global" in metrics, "Missing global metrics"
        assert "by_time" in metrics, "Missing by_time metrics"
        assert "by_confidence" in metrics, "Missing by_confidence metrics"


class TestMLReadinessAPI:
    """Block 5.A: Test /api/ml/readiness endpoint"""
    
    def test_ml_readiness_returns_ok(self):
        """ML readiness endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/ml/readiness")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
    
    def test_ml_readiness_has_data_status(self):
        """Should return data.status field"""
        response = requests.get(f"{BASE_URL}/api/ml/readiness")
        data = response.json()
        
        assert "data" in data, "Missing data field"
        assert "status" in data["data"], "Missing status in data"
        valid_statuses = ["READY", "BLOCKED", "PENDING"]
        assert data["data"]["status"] in valid_statuses, \
            f"Invalid status: {data['data']['status']}"
    
    def test_ml_readiness_has_gates(self):
        """Should return gates object with readiness checks"""
        response = requests.get(f"{BASE_URL}/api/ml/readiness")
        data = response.json()
        
        assert "data" in data
        assert "gates" in data["data"], "Missing gates in data"
        gates = data["data"]["gates"]
        
        # Should have coverage, dataset, model quality checks
        expected_gates = ["coverageOk", "datasetOk", "modelQualityOk"]
        for gate in expected_gates:
            assert gate in gates, f"Missing gate: {gate}"


class TestEndpointIntegration:
    """Cross-endpoint consistency tests"""
    
    def test_all_endpoints_respond(self):
        """All 3 endpoints should respond successfully"""
        endpoints = [
            "/api/tactical/1d?asset=BTC",
            "/api/drift/intelligence?horizon=7&asset=BTC",
            "/api/ml/readiness"
        ]
        
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code == 200, f"{endpoint} returned {response.status_code}"
            data = response.json()
            assert data.get("ok") is True, f"{endpoint} returned ok=false"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
