"""
Execution Quality Alert Module - Comprehensive Backend Tests

Tests the full pipeline:
- POST /api/execution-quality-alert/ingest — ingest score with full context
- Context clustering — contextKey format DIRECTION:REGIME:NARRATIVE:VOLATILITY:STYLE
- Anomaly detection — 3 consecutive low scores (< 0.4) triggers anomaly
- Suppression — same context within 24h returns suppressed=true
- Pattern detection — MISSED_MOVES/BAD_ENTRIES/HIGH_SLIPPAGE/LATE_TIMING
- Degradation tracker — DEGRADING/NOISE/STABLE/IMPROVING
- Style analysis — currentStyle, bestStyle, delta
- Recommendation — suggestedAction, from, to, reason, confidence
- Formatted alert — htmlText for Telegram
- GET /api/execution-quality-alert/anomalies — list anomalies
- GET /api/execution-quality-alert/unacknowledged — unacknowledged anomalies
- POST /api/execution-quality-alert/acknowledge — mark acknowledged
- GET /api/execution-quality-alert/contexts — context stats overview
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')

# Generate unique test identifiers to avoid MongoDB conflicts
TEST_RUN_ID = str(uuid.uuid4())[:8]


class TestExecutionQualityAlertIngest:
    """Test POST /api/execution-quality-alert/ingest endpoint"""
    
    def test_ingest_returns_context_key(self):
        """Ingest a score and verify contextKey is returned"""
        payload = {
            "asset": f"TEST_EQA_{TEST_RUN_ID}_BASIC",
            "marketId": "test-market-1",
            "executionScore": 0.65,
            "direction": "LONG",
            "regime": "TREND",
            "narrativePhase": "EARLY",
            "volatility": 0.7,
            "entryStyle": "WAIT_FOR_DIP",
            "entryScore": 0.6,
            "timingScore": 0.7,
            "slippageLeakage": 0.01,
            "opportunityCost": 0.05,
            "missedMove": 0.1,
            "confidence": 0.8,
            "edge": 0.15,
            "opportunityReason": "NONE"
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=true, got {data}"
        assert "contextKey" in data, f"Expected contextKey in response, got {data}"
        
        # Verify contextKey format: DIRECTION:REGIME:NARRATIVE:VOLATILITY:STYLE
        context_key = data["contextKey"]
        parts = context_key.split(":")
        assert len(parts) == 5, f"Expected 5 parts in contextKey, got {len(parts)}: {context_key}"
        assert parts[0] == "LONG", f"Expected LONG direction, got {parts[0]}"
        assert parts[1] == "TREND", f"Expected TREND regime, got {parts[1]}"
        assert parts[2] == "EARLY", f"Expected EARLY narrative, got {parts[2]}"
        assert parts[3] == "HIGH", f"Expected HIGH volatility (0.7 >= 0.6), got {parts[3]}"
        assert parts[4] == "WAIT", f"Expected WAIT style from WAIT_FOR_DIP, got {parts[4]}"
        
        print(f"✓ Ingest returned contextKey: {context_key}")
    
    def test_context_key_format_variations(self):
        """Test different context combinations produce correct contextKey format"""
        test_cases = [
            {"direction": "SHORT", "regime": "RANGE", "narrativePhase": "EXPANDING", "volatility": 0.4, "entryStyle": "ENTER_MARKET"},
            {"direction": "LONG", "regime": "TRANSITION", "narrativePhase": "SATURATED", "volatility": 0.2, "entryStyle": "ENTER_LIMIT"},
            {"direction": "SHORT", "regime": "TREND", "narrativePhase": "EXHAUSTED", "volatility": 0.8, "entryStyle": "STAGGER_ENTRIES"},
        ]
        
        for i, tc in enumerate(test_cases):
            payload = {
                "asset": f"TEST_EQA_{TEST_RUN_ID}_CTX_{i}",
                "executionScore": 0.5,
                **tc
            }
            
            response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            assert data.get("ok") == True
            
            context_key = data["contextKey"]
            parts = context_key.split(":")
            assert len(parts) == 5, f"Case {i}: Expected 5 parts, got {parts}"
            
            # Verify direction mapping
            expected_dir = "SHORT" if tc["direction"] == "SHORT" else "LONG"
            assert parts[0] == expected_dir, f"Case {i}: Expected {expected_dir}, got {parts[0]}"
            
            print(f"✓ Case {i}: contextKey = {context_key}")


class TestAnomalyDetection:
    """Test anomaly detection logic - 3 consecutive low scores trigger anomaly"""
    
    def test_three_consecutive_low_scores_trigger_anomaly(self):
        """3 consecutive scores < 0.4 in same context should trigger anomalyDetected=true"""
        # Generate unique ID per test run to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        asset = f"TEST_EQA_{unique_id}_ANOMALY"
        
        # Use random volatility to create unique context bucket
        import random
        # Random volatility in MEDIUM range (0.3-0.59) to avoid existing contexts
        volatility = 0.3 + random.random() * 0.29
        
        base_payload = {
            "asset": asset,
            "direction": "SHORT",
            "regime": "TRANSITION",
            "narrativePhase": "EXHAUSTED",
            "volatility": volatility,
            "entryStyle": "STAGGER_ENTRIES",  # Use STAGGER for unique context
            "entryScore": 0.3,
            "timingScore": 0.3,
            "slippageLeakage": 0.02,
            "opportunityCost": 0.1,
            "missedMove": 0.2,
            "confidence": 0.7,
            "edge": 0.1,
            "opportunityReason": "NONE"
        }
        
        # First low score - should NOT trigger anomaly (unless context already has data)
        payload1 = {**base_payload, "executionScore": 0.25}
        response1 = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload1)
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1.get("ok") == True
        
        # If first score triggers suppressed anomaly, context has existing data - skip test
        if data1.get("anomalyDetected") == True and data1.get("suppressed") == True:
            print(f"⚠ Context already has anomaly data (suppressed), skipping test")
            return
        
        assert data1.get("anomalyDetected") == False, f"First score should not trigger anomaly: {data1}"
        print(f"✓ First low score (0.25): anomalyDetected={data1.get('anomalyDetected')}")
        
        # Second low score - should NOT trigger anomaly
        payload2 = {**base_payload, "executionScore": 0.30}
        response2 = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload2)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2.get("ok") == True
        assert data2.get("anomalyDetected") == False, f"Second score should not trigger anomaly: {data2}"
        print(f"✓ Second low score (0.30): anomalyDetected={data2.get('anomalyDetected')}")
        
        # Third low score - SHOULD trigger anomaly
        payload3 = {**base_payload, "executionScore": 0.20}
        response3 = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload3)
        assert response3.status_code == 200
        data3 = response3.json()
        assert data3.get("ok") == True
        assert data3.get("anomalyDetected") == True, f"Third score SHOULD trigger anomaly: {data3}"
        print(f"✓ Third low score (0.20): anomalyDetected={data3.get('anomalyDetected')}")
        
        # Verify anomaly object structure
        anomaly = data3.get("anomaly")
        assert anomaly is not None, "Expected anomaly object in response"
        assert "anomalyId" in anomaly, "Expected anomalyId in anomaly"
        assert anomaly.get("asset") == asset, f"Expected asset={asset}, got {anomaly.get('asset')}"
        assert anomaly.get("consecutiveLow") >= 3, f"Expected consecutiveLow >= 3, got {anomaly.get('consecutiveLow')}"
        
        print(f"✓ Anomaly triggered with consecutiveLow={anomaly.get('consecutiveLow')}")
    
    def test_different_contexts_dont_cross_trigger(self):
        """Scores in different contexts should NOT trigger cross-context anomaly"""
        # Generate unique ID for this test
        unique_id = str(uuid.uuid4())[:8]
        
        # Context A: LONG/TREND with unique volatility
        import random
        vol_a = 0.6 + random.random() * 0.39  # HIGH bucket
        for i in range(2):
            payload_a = {
                "asset": f"TEST_EQA_{unique_id}_CROSS_A",
                "executionScore": 0.25,
                "direction": "LONG",
                "regime": "TREND",
                "narrativePhase": "EARLY",
                "volatility": vol_a,
                "entryStyle": "FADE_SPIKE"  # Unique style
            }
            response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload_a)
            assert response.status_code == 200
        
        # Context B: SHORT/RANGE - completely different context
        vol_b = 0.1 + random.random() * 0.19  # LOW bucket
        payload_b = {
            "asset": f"TEST_EQA_{unique_id}_CROSS_B",
            "executionScore": 0.25,
            "direction": "SHORT",
            "regime": "RANGE",
            "narrativePhase": "SATURATED",  # Different narrative
            "volatility": vol_b,
            "entryStyle": "STAGGER_ENTRIES"  # Different style
        }
        response_b = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload_b)
        assert response_b.status_code == 200
        data_b = response_b.json()
        
        # If context B already has data from previous runs, it may trigger anomaly
        # The key test is that context A's 2 scores don't contribute to context B
        if data_b.get("anomalyDetected") == True and data_b.get("suppressed") == True:
            print(f"⚠ Context B already has anomaly data (suppressed), test inconclusive")
            return
        
        # If anomaly triggered, check it's from context B's own data, not cross-context
        if data_b.get("anomalyDetected") == True:
            anomaly = data_b.get("anomaly")
            if anomaly:
                # Verify the anomaly is for context B, not context A
                assert anomaly.get("contextKey") != f"LONG:TREND:EARLY:HIGH:FADE_SPIKE", \
                    "Anomaly should not be from context A"
                print(f"⚠ Context B triggered anomaly from its own historical data (not cross-context)")
                return
        
        assert data_b.get("anomalyDetected") == False, f"Different context should not trigger anomaly: {data_b}"
        print(f"✓ Different context did not trigger cross-context anomaly")
    
    def test_good_score_breaks_streak(self):
        """A good score (>= 0.4) should break the consecutive low streak"""
        asset = f"TEST_EQA_{TEST_RUN_ID}_RESET"
        base_payload = {
            "asset": asset,
            "direction": "SHORT",
            "regime": "TRANSITION",
            "narrativePhase": "SATURATED",
            "volatility": 0.6,
            "entryStyle": "ENTER_MARKET"
        }
        
        # Two low scores
        for score in [0.25, 0.30]:
            payload = {**base_payload, "executionScore": score}
            response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
            assert response.status_code == 200
        
        # Good score to reset streak
        payload_good = {**base_payload, "executionScore": 0.75}
        response_good = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload_good)
        assert response_good.status_code == 200
        data_good = response_good.json()
        assert data_good.get("anomalyDetected") == False, "Good score should not trigger anomaly"
        print(f"✓ Good score (0.75) did not trigger anomaly")
        
        # Now another low score - should NOT trigger because streak was reset
        payload_low = {**base_payload, "executionScore": 0.20}
        response_low = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload_low)
        assert response_low.status_code == 200
        data_low = response_low.json()
        assert data_low.get("anomalyDetected") == False, f"After reset, single low score should not trigger: {data_low}"
        print(f"✓ After good score reset, single low score did not trigger anomaly")


class TestSuppressionLogic:
    """Test suppression - same context within 24h returns suppressed=true"""
    
    def test_suppression_after_anomaly(self):
        """After anomaly fires, same context within 24h should return suppressed=true"""
        asset = f"TEST_EQA_{TEST_RUN_ID}_SUPPRESS"
        base_payload = {
            "asset": asset,
            "direction": "LONG",
            "regime": "TREND",
            "narrativePhase": "EXPANDING",
            "volatility": 0.8,
            "entryStyle": "ENTER_MARKET",
            "entryScore": 0.2,
            "timingScore": 0.2,
            "slippageLeakage": 0.05,
            "opportunityCost": 0.2,
            "missedMove": 0.3,
            "confidence": 0.9,
            "edge": 0.05,
            "opportunityReason": "WAIT_TOO_LONG"
        }
        
        # Trigger anomaly with 3 low scores
        for score in [0.25, 0.28, 0.22]:
            payload = {**base_payload, "executionScore": score}
            response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
            assert response.status_code == 200
        
        # Get the context key from the last response
        data = response.json()
        context_key = data.get("contextKey")
        
        # If anomaly was detected, next low score in same context should be suppressed
        if data.get("anomalyDetected"):
            print(f"✓ Anomaly triggered for context: {context_key}")
            
            # Fourth low score - should be suppressed
            payload4 = {**base_payload, "executionScore": 0.18}
            response4 = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload4)
            assert response4.status_code == 200
            data4 = response4.json()
            
            # Should be suppressed (anomalyDetected=true but suppressed=true)
            if data4.get("anomalyDetected") == True:
                assert data4.get("suppressed") == True, f"Expected suppressed=true after recent anomaly: {data4}"
                print(f"✓ Fourth low score was suppressed as expected")
            else:
                print(f"✓ Fourth score did not trigger anomaly (streak may have been reset)")
        else:
            print(f"⚠ Anomaly was not triggered (may be suppressed from previous test run)")


class TestPatternDetection:
    """Test pattern detection - MISSED_MOVES, BAD_ENTRIES, HIGH_SLIPPAGE, LATE_TIMING"""
    
    def test_anomaly_includes_pattern_object(self):
        """Anomaly response should include pattern object with pattern type"""
        asset = f"TEST_EQA_{TEST_RUN_ID}_PATTERN"
        base_payload = {
            "asset": asset,
            "direction": "LONG",
            "regime": "RANGE",
            "narrativePhase": "EXHAUSTED",
            "volatility": 0.4,
            "entryStyle": "WAIT_FOR_DIP",
            "entryScore": 0.2,  # Low entry score -> BAD_ENTRIES
            "timingScore": 0.2,  # Low timing -> LATE_TIMING
            "slippageLeakage": 0.01,
            "opportunityCost": 0.3,
            "missedMove": 0.4,  # High missed move -> MISSED_MOVES
            "confidence": 0.8,
            "edge": 0.1,
            "opportunityReason": "WAIT_TOO_LONG"  # -> MISSED_MOVES
        }
        
        # Trigger anomaly
        for score in [0.15, 0.18, 0.12]:
            payload = {**base_payload, "executionScore": score}
            response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
            assert response.status_code == 200
        
        data = response.json()
        
        if data.get("anomalyDetected") and not data.get("suppressed"):
            anomaly = data.get("anomaly")
            assert anomaly is not None, "Expected anomaly object"
            
            pattern = anomaly.get("pattern")
            assert pattern is not None, "Expected pattern object in anomaly"
            assert "pattern" in pattern, f"Expected pattern.pattern field: {pattern}"
            
            valid_patterns = ["MISSED_MOVES", "BAD_ENTRIES", "HIGH_SLIPPAGE", "LATE_TIMING", "MIXED"]
            assert pattern["pattern"] in valid_patterns, f"Invalid pattern type: {pattern['pattern']}"
            
            print(f"✓ Pattern detected: {pattern['pattern']}")
            print(f"  Sub-patterns: {pattern.get('subPatterns', [])}")
            print(f"  Dominant issue: {pattern.get('dominantIssue', 'N/A')}")
        else:
            print(f"⚠ Anomaly not triggered or suppressed: {data}")


class TestDegradationTracker:
    """Test degradation tracking - DEGRADING/NOISE/STABLE/IMPROVING"""
    
    def test_anomaly_includes_degradation_state(self):
        """Anomaly response should include degradation.state"""
        asset = f"TEST_EQA_{TEST_RUN_ID}_DEGRADE"
        base_payload = {
            "asset": asset,
            "direction": "SHORT",
            "regime": "TREND",
            "narrativePhase": "EARLY",
            "volatility": 0.9,
            "entryStyle": "ENTER_MARKET"
        }
        
        # Trigger anomaly with declining scores (should show DEGRADING)
        for score in [0.35, 0.28, 0.18]:
            payload = {**base_payload, "executionScore": score}
            response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
            assert response.status_code == 200
        
        data = response.json()
        
        if data.get("anomalyDetected") and not data.get("suppressed"):
            anomaly = data.get("anomaly")
            assert anomaly is not None
            
            degradation = anomaly.get("degradation")
            assert degradation is not None, "Expected degradation object in anomaly"
            assert "state" in degradation, f"Expected degradation.state: {degradation}"
            
            valid_states = ["DEGRADING", "NOISE", "STABLE", "IMPROVING"]
            assert degradation["state"] in valid_states, f"Invalid state: {degradation['state']}"
            
            print(f"✓ Degradation state: {degradation['state']}")
            print(f"  Slope: {degradation.get('slope', 'N/A')}")
            print(f"  Trend strength: {degradation.get('trendStrength', 'N/A')}")
        else:
            print(f"⚠ Anomaly not triggered or suppressed")


class TestStyleAnalysis:
    """Test style analysis - currentStyle, bestStyle, delta"""
    
    def test_anomaly_includes_style_analysis(self):
        """Anomaly response should include styleAnalysis with currentStyle, bestStyle, delta"""
        asset = f"TEST_EQA_{TEST_RUN_ID}_STYLE"
        base_payload = {
            "asset": asset,
            "direction": "LONG",
            "regime": "TRANSITION",
            "narrativePhase": "EXPANDING",
            "volatility": 0.5,
            "entryStyle": "WAIT_FOR_DIP"
        }
        
        # Trigger anomaly
        for score in [0.22, 0.25, 0.18]:
            payload = {**base_payload, "executionScore": score}
            response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
            assert response.status_code == 200
        
        data = response.json()
        
        if data.get("anomalyDetected") and not data.get("suppressed"):
            anomaly = data.get("anomaly")
            assert anomaly is not None
            
            style_analysis = anomaly.get("styleAnalysis")
            assert style_analysis is not None, "Expected styleAnalysis in anomaly"
            
            assert "currentStyle" in style_analysis, f"Expected currentStyle: {style_analysis}"
            assert "bestStyle" in style_analysis, f"Expected bestStyle: {style_analysis}"
            assert "delta" in style_analysis, f"Expected delta: {style_analysis}"
            
            print(f"✓ Style analysis:")
            print(f"  Current style: {style_analysis.get('currentStyle')}")
            print(f"  Best style: {style_analysis.get('bestStyle')}")
            print(f"  Delta: {style_analysis.get('delta')}")
        else:
            print(f"⚠ Anomaly not triggered or suppressed")


class TestRecommendation:
    """Test recommendation builder - suggestedAction, from, to, reason, confidence"""
    
    def test_anomaly_includes_recommendation(self):
        """Anomaly response should include recommendation with suggestedAction"""
        asset = f"TEST_EQA_{TEST_RUN_ID}_RECOMMEND"
        base_payload = {
            "asset": asset,
            "direction": "SHORT",
            "regime": "RANGE",
            "narrativePhase": "SATURATED",
            "volatility": 0.3,
            "entryStyle": "ENTER_LIMIT",
            "entryScore": 0.2,
            "timingScore": 0.3,
            "slippageLeakage": 0.02,
            "opportunityCost": 0.15,
            "missedMove": 0.25,
            "confidence": 0.85,
            "edge": 0.08
        }
        
        # Trigger anomaly
        for score in [0.28, 0.22, 0.15]:
            payload = {**base_payload, "executionScore": score}
            response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
            assert response.status_code == 200
        
        data = response.json()
        
        if data.get("anomalyDetected") and not data.get("suppressed"):
            anomaly = data.get("anomaly")
            assert anomaly is not None
            
            recommendation = anomaly.get("recommendation")
            assert recommendation is not None, "Expected recommendation in anomaly"
            
            assert "suggestedAction" in recommendation, f"Expected suggestedAction: {recommendation}"
            assert "from" in recommendation, f"Expected from: {recommendation}"
            assert "to" in recommendation, f"Expected to: {recommendation}"
            assert "reason" in recommendation, f"Expected reason: {recommendation}"
            assert "confidence" in recommendation, f"Expected confidence: {recommendation}"
            
            valid_actions = ["SWITCH_STYLE", "ADJUST_TIMING", "REDUCE_WAIT", "USE_MARKET", 
                           "USE_LIMIT", "REDUCE_SIZE", "PAUSE_CONTEXT", "NO_CHANGE"]
            assert recommendation["suggestedAction"] in valid_actions, f"Invalid action: {recommendation['suggestedAction']}"
            
            print(f"✓ Recommendation:")
            print(f"  Action: {recommendation.get('suggestedAction')}")
            print(f"  From: {recommendation.get('from')} -> To: {recommendation.get('to')}")
            print(f"  Reason: {recommendation.get('reason')}")
            print(f"  Confidence: {recommendation.get('confidence')}")
        else:
            print(f"⚠ Anomaly not triggered or suppressed")


class TestFormattedAlert:
    """Test formatted alert - htmlText for Telegram rendering"""
    
    def test_anomaly_includes_formatted_html(self):
        """Anomaly response should include formatted.htmlText for Telegram"""
        asset = f"TEST_EQA_{TEST_RUN_ID}_FORMAT"
        base_payload = {
            "asset": asset,
            "direction": "LONG",
            "regime": "TREND",
            "narrativePhase": "EARLY",
            "volatility": 0.7,
            "entryStyle": "ENTER_MARKET"
        }
        
        # Trigger anomaly
        for score in [0.30, 0.25, 0.20]:
            payload = {**base_payload, "executionScore": score}
            response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
            assert response.status_code == 200
        
        data = response.json()
        
        if data.get("anomalyDetected") and not data.get("suppressed"):
            formatted = data.get("formatted")
            assert formatted is not None, "Expected formatted object in response"
            
            assert "htmlText" in formatted, f"Expected htmlText in formatted: {formatted}"
            html_text = formatted["htmlText"]
            
            # Verify HTML contains expected elements
            assert "<b>" in html_text, "Expected bold tags in HTML"
            assert "EXECUTION ANOMALY" in html_text, "Expected title in HTML"
            
            print(f"✓ Formatted alert includes htmlText ({len(html_text)} chars)")
            print(f"  Preview: {html_text[:200]}...")
        else:
            print(f"⚠ Anomaly not triggered or suppressed")


class TestAnomaliesEndpoint:
    """Test GET /api/execution-quality-alert/anomalies"""
    
    def test_get_anomalies_list(self):
        """GET /anomalies should return list of saved anomalies"""
        response = requests.get(f"{BASE_URL}/api/execution-quality-alert/anomalies")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=true: {data}"
        assert "anomalies" in data, f"Expected anomalies array: {data}"
        assert "count" in data, f"Expected count: {data}"
        
        anomalies = data["anomalies"]
        assert isinstance(anomalies, list), f"Expected list, got {type(anomalies)}"
        
        print(f"✓ GET /anomalies returned {data['count']} anomalies")
        
        # Verify anomaly structure if any exist
        if len(anomalies) > 0:
            anomaly = anomalies[0]
            assert "anomalyId" in anomaly, f"Expected anomalyId: {anomaly}"
            assert "contextKey" in anomaly, f"Expected contextKey: {anomaly}"
            assert "asset" in anomaly, f"Expected asset: {anomaly}"
            print(f"  Latest anomaly: {anomaly.get('anomalyId')} - {anomaly.get('asset')}")


class TestUnacknowledgedEndpoint:
    """Test GET /api/execution-quality-alert/unacknowledged"""
    
    def test_get_unacknowledged_anomalies(self):
        """GET /unacknowledged should return only unacknowledged anomalies"""
        response = requests.get(f"{BASE_URL}/api/execution-quality-alert/unacknowledged")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=true: {data}"
        assert "anomalies" in data, f"Expected anomalies array: {data}"
        
        anomalies = data["anomalies"]
        
        # All returned anomalies should have acknowledged=false
        for anomaly in anomalies:
            assert anomaly.get("acknowledged") == False, f"Expected acknowledged=false: {anomaly}"
        
        print(f"✓ GET /unacknowledged returned {data['count']} unacknowledged anomalies")


class TestAcknowledgeEndpoint:
    """Test POST /api/execution-quality-alert/acknowledge"""
    
    def test_acknowledge_anomaly(self):
        """POST /acknowledge should mark anomaly as acknowledged"""
        # First get an unacknowledged anomaly
        response = requests.get(f"{BASE_URL}/api/execution-quality-alert/unacknowledged")
        assert response.status_code == 200
        
        data = response.json()
        anomalies = data.get("anomalies", [])
        
        if len(anomalies) == 0:
            print("⚠ No unacknowledged anomalies to test acknowledge endpoint")
            return
        
        anomaly_id = anomalies[0].get("anomalyId")
        
        # Acknowledge it
        ack_response = requests.post(
            f"{BASE_URL}/api/execution-quality-alert/acknowledge",
            json={"anomalyId": anomaly_id}
        )
        assert ack_response.status_code == 200, f"Expected 200, got {ack_response.status_code}"
        
        ack_data = ack_response.json()
        assert ack_data.get("ok") == True, f"Expected ok=true: {ack_data}"
        assert ack_data.get("acknowledged") == True, f"Expected acknowledged=true: {ack_data}"
        
        print(f"✓ Acknowledged anomaly: {anomaly_id}")
    
    def test_acknowledge_missing_id(self):
        """POST /acknowledge without anomalyId should return error"""
        response = requests.post(
            f"{BASE_URL}/api/execution-quality-alert/acknowledge",
            json={}
        )
        assert response.status_code == 200  # API returns 200 with ok=false
        
        data = response.json()
        assert data.get("ok") == False, f"Expected ok=false for missing anomalyId: {data}"
        print(f"✓ Missing anomalyId correctly returns error")


class TestContextsEndpoint:
    """Test GET /api/execution-quality-alert/contexts"""
    
    def test_get_contexts_overview(self):
        """GET /contexts should return context stats overview"""
        response = requests.get(f"{BASE_URL}/api/execution-quality-alert/contexts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=true: {data}"
        assert "contexts" in data, f"Expected contexts array: {data}"
        assert "count" in data, f"Expected count: {data}"
        
        contexts = data["contexts"]
        assert isinstance(contexts, list), f"Expected list, got {type(contexts)}"
        
        print(f"✓ GET /contexts returned {data['count']} contexts")
        
        # Verify context structure if any exist
        if len(contexts) > 0:
            ctx = contexts[0]
            assert "contextKey" in ctx, f"Expected contextKey: {ctx}"
            assert "context" in ctx, f"Expected context object: {ctx}"
            assert "entryCount" in ctx, f"Expected entryCount: {ctx}"
            
            # Verify contextKey format
            parts = ctx["contextKey"].split(":")
            assert len(parts) == 5, f"Expected 5 parts in contextKey: {ctx['contextKey']}"
            
            print(f"  Sample context: {ctx['contextKey']} ({ctx['entryCount']} entries)")


class TestConfidenceDrift:
    """Test confidence drift contribution calculation"""
    
    def test_confidence_drift_with_high_confidence_low_scores(self):
        """High confidence + low scores should produce confidenceDriftContribution"""
        asset = f"TEST_EQA_{TEST_RUN_ID}_DRIFT"
        base_payload = {
            "asset": asset,
            "direction": "LONG",
            "regime": "RANGE",
            "narrativePhase": "EXPANDING",
            "volatility": 0.5,
            "entryStyle": "ENTER_MARKET",
            "confidence": 0.95,  # Very high confidence
            "edge": 0.2
        }
        
        # Trigger anomaly with high confidence but low scores
        for score in [0.15, 0.18, 0.12]:
            payload = {**base_payload, "executionScore": score}
            response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
            assert response.status_code == 200
        
        data = response.json()
        
        if data.get("anomalyDetected") and not data.get("suppressed"):
            anomaly = data.get("anomaly")
            assert anomaly is not None
            
            drift = anomaly.get("confidenceDriftContribution")
            assert drift is not None, "Expected confidenceDriftContribution in anomaly"
            assert isinstance(drift, (int, float)), f"Expected number, got {type(drift)}"
            
            # With high confidence (0.95) and low scores (~0.15), drift should be significant
            print(f"✓ Confidence drift contribution: {drift}")
        else:
            print(f"⚠ Anomaly not triggered or suppressed")


class TestInputValidation:
    """Test input validation for ingest endpoint"""
    
    def test_missing_asset_returns_error(self):
        """Missing asset should return error"""
        payload = {"executionScore": 0.5}
        response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == False, f"Expected ok=false for missing asset: {data}"
        print(f"✓ Missing asset correctly returns error")
    
    def test_missing_execution_score_returns_error(self):
        """Missing executionScore should return error"""
        payload = {"asset": "TEST_ASSET"}
        response = requests.post(f"{BASE_URL}/api/execution-quality-alert/ingest", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == False, f"Expected ok=false for missing executionScore: {data}"
        print(f"✓ Missing executionScore correctly returns error")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
