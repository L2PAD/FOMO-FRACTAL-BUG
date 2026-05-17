"""
Signal Intelligence Layer VFinal — Backend API Tests

Testing the unified signal endpoint:
  GET /api/signals/vfinal?asset=BTCUSDT

Response structure:
  - L1: Execution Signal (aggregate)
  - L2: Structural Components (exchange, accDist, onchain)
  - L3: Event Feed (triggers)
  - Stats sidebar
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSignalsVFinalEndpoint:
    """Tests for /api/signals/vfinal endpoint"""

    def test_basic_response_structure(self):
        """Test that response has ok:true and all required top-level fields"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "Response should have ok:true"
        assert "execution" in data, "Response missing 'execution' field"
        assert "structural" in data, "Response missing 'structural' field"
        assert "events" in data, "Response missing 'events' field"
        assert "stats" in data, "Response missing 'stats' field"
        assert data.get("asset") == "BTCUSDT", f"Asset should be BTCUSDT, got {data.get('asset')}"
        print(f"✓ Basic response structure OK - ok:{data['ok']}, asset:{data['asset']}")

    def test_execution_score_range(self):
        """Test execution.score is between -1 and 1"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        score = data.get("execution", {}).get("score")
        assert score is not None, "execution.score is missing"
        assert isinstance(score, (int, float)), "execution.score should be numeric"
        assert -1 <= score <= 1, f"execution.score should be [-1, 1], got {score}"
        print(f"✓ Execution score: {score} (valid range)")

    def test_execution_bias_values(self):
        """Test execution.bias is one of: bullish_pressure, bearish_pressure, balanced"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        bias = data.get("execution", {}).get("bias")
        valid_biases = ["bullish_pressure", "bearish_pressure", "balanced"]
        assert bias in valid_biases, f"execution.bias should be one of {valid_biases}, got {bias}"
        print(f"✓ Execution bias: {bias}")

    def test_execution_contributors_structure(self):
        """Test execution.contributors has exchange, accDist, onchain keys with numeric values"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        contributors = data.get("execution", {}).get("contributors", {})
        
        required_keys = ["exchange", "accDist", "onchain"]
        for key in required_keys:
            assert key in contributors, f"contributors missing '{key}'"
            assert isinstance(contributors[key], (int, float)), f"contributors.{key} should be numeric"
        
        print(f"✓ Contributors: exchange={contributors['exchange']:.4f}, accDist={contributors['accDist']:.4f}, onchain={contributors['onchain']:.4f}")

    def test_execution_narrative_not_empty(self):
        """Test execution.narrative is a non-empty string"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        narrative = data.get("execution", {}).get("narrative")
        assert narrative is not None, "execution.narrative is missing"
        assert isinstance(narrative, str), "execution.narrative should be string"
        assert len(narrative) > 0, "execution.narrative should not be empty"
        print(f"✓ Narrative: '{narrative[:60]}...'")

    def test_execution_mode_values(self):
        """Test execution.executionMode is one of: HIGH_ACTIVITY, MODERATE_ACTIVITY, LOW_ACTIVITY"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        mode = data.get("execution", {}).get("executionMode")
        valid_modes = ["HIGH_ACTIVITY", "MODERATE_ACTIVITY", "LOW_ACTIVITY"]
        assert mode in valid_modes, f"executionMode should be one of {valid_modes}, got {mode}"
        print(f"✓ Execution mode: {mode}")

    def test_structural_exchange_block(self):
        """Test structural.exchange has score, strength, confidence, direction"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        exchange = data.get("structural", {}).get("exchange", {})
        
        required_fields = ["score", "strength", "confidence", "direction"]
        for field in required_fields:
            assert field in exchange, f"structural.exchange missing '{field}'"
        
        assert isinstance(exchange["score"], (int, float)), "exchange.score should be numeric"
        assert isinstance(exchange["strength"], (int, float)), "exchange.strength should be numeric"
        assert isinstance(exchange["confidence"], (int, float)), "exchange.confidence should be numeric"
        assert exchange["direction"] in ["bullish", "bearish", "neutral"], f"Invalid direction: {exchange['direction']}"
        
        print(f"✓ Exchange block: score={exchange['score']:.4f}, direction={exchange['direction']}")

    def test_structural_accdist_block(self):
        """Test structural.accDist has score, strength, confidence, direction"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        accdist = data.get("structural", {}).get("accDist", {})
        
        required_fields = ["score", "strength", "confidence", "direction"]
        for field in required_fields:
            assert field in accdist, f"structural.accDist missing '{field}'"
        
        assert isinstance(accdist["score"], (int, float)), "accDist.score should be numeric"
        assert isinstance(accdist["strength"], (int, float)), "accDist.strength should be numeric"
        assert isinstance(accdist["confidence"], (int, float)), "accDist.confidence should be numeric"
        assert accdist["direction"] in ["bullish", "bearish", "neutral"], f"Invalid direction: {accdist['direction']}"
        
        print(f"✓ AccDist block: score={accdist['score']:.4f}, direction={accdist['direction']}")

    def test_structural_onchain_block(self):
        """Test structural.onchain has score, strength, confidence, direction"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        onchain = data.get("structural", {}).get("onchain", {})
        
        required_fields = ["score", "strength", "confidence", "direction"]
        for field in required_fields:
            assert field in onchain, f"structural.onchain missing '{field}'"
        
        assert isinstance(onchain["score"], (int, float)), "onchain.score should be numeric"
        assert isinstance(onchain["strength"], (int, float)), "onchain.strength should be numeric"
        assert isinstance(onchain["confidence"], (int, float)), "onchain.confidence should be numeric"
        assert onchain["direction"] in ["bullish", "bearish", "neutral"], f"Invalid direction: {onchain['direction']}"
        
        print(f"✓ Onchain block: score={onchain['score']:.4f}, direction={onchain['direction']}")

    def test_events_array_structure(self):
        """Test events is an array with proper event structure"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        events = data.get("events", [])
        assert isinstance(events, list), "events should be an array"
        
        if len(events) > 0:
            event = events[0]
            required_fields = ["type", "level", "direction", "impactOnExecution", "ttl", "confidence"]
            for field in required_fields:
                assert field in event, f"Event missing '{field}' field"
            
            assert isinstance(event["impactOnExecution"], (int, float)), "impactOnExecution should be numeric"
            assert isinstance(event["confidence"], (int, float)), "confidence should be numeric"
            print(f"✓ Events array with {len(events)} events, first event type: {event['type']}")
        else:
            print("✓ Events array is empty (no active triggers)")

    def test_stats_structure(self):
        """Test stats has activeEvents, structuralStrength, executionScore, executionBias, executionMode"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get("stats", {})
        
        required_fields = ["activeEvents", "structuralStrength", "executionScore", "executionBias", "executionMode"]
        for field in required_fields:
            assert field in stats, f"stats missing '{field}'"
        
        assert isinstance(stats["activeEvents"], int), "activeEvents should be integer"
        assert isinstance(stats["structuralStrength"], (int, float)), "structuralStrength should be numeric"
        assert isinstance(stats["executionScore"], (int, float)), "executionScore should be numeric"
        assert stats["executionBias"] in ["bullish_pressure", "bearish_pressure", "balanced"], f"Invalid executionBias: {stats['executionBias']}"
        assert stats["executionMode"] in ["HIGH_ACTIVITY", "MODERATE_ACTIVITY", "LOW_ACTIVITY"], f"Invalid executionMode: {stats['executionMode']}"
        
        print(f"✓ Stats: activeEvents={stats['activeEvents']}, executionScore={stats['executionScore']:.4f}, bias={stats['executionBias']}")


class TestSignalsVFinalIntegration:
    """Integration tests for signals vfinal data quality"""

    def test_score_consistency(self):
        """Test that execution.score matches contributors weighted sum"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        execution = data.get("execution", {})
        contributors = execution.get("contributors", {})
        
        # Weighted sum should approximately equal the score
        weighted_sum = contributors.get("exchange", 0) + contributors.get("accDist", 0) + contributors.get("onchain", 0)
        score = execution.get("score", 0)
        
        # Allow some tolerance for rounding
        assert abs(weighted_sum - score) < 0.01, f"Score {score} doesn't match weighted sum {weighted_sum}"
        print(f"✓ Score consistency: score={score:.4f}, weighted_sum={weighted_sum:.4f}")

    def test_bias_matches_score_direction(self):
        """Test bias label matches score sign for extreme values"""
        response = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        score = data.get("execution", {}).get("score", 0)
        bias = data.get("execution", {}).get("bias")
        
        # For scores > 0.45, should be bullish_pressure
        # For scores < -0.45, should be bearish_pressure
        # Otherwise balanced
        if score > 0.45:
            assert bias == "bullish_pressure", f"Score {score} should have bullish_pressure bias"
        elif score < -0.45:
            assert bias == "bearish_pressure", f"Score {score} should have bearish_pressure bias"
        else:
            assert bias == "balanced", f"Score {score} should have balanced bias"
        
        print(f"✓ Bias consistency: score={score:.4f} → bias={bias}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
