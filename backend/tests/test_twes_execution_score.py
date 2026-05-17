"""
TWES (Time-Weighted Execution Score) Integration Tests

Tests:
- POST /api/execution-score/evaluate — single case scoring with direction-aware LONG/SHORT
- POST /api/execution-score/evaluate/batch — batch scoring returns results keyed by market_id
- GET /api/execution-score/styles — style performance stats
- POST /api/prediction/weekly-digest/generate — includes executionQuality when reviews have data
- GET /api/prediction/weekly-digest/latest — returns latest digest with all fields
- GET /api/prediction/execution-score/styles — Python proxy for styles
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestExecutionScoreEvaluate:
    """POST /api/execution-score/evaluate — Single case execution scoring"""

    def test_evaluate_long_direction(self):
        """Test LONG direction case scoring"""
        payload = {
            "case": {
                "market_id": "test_long_001",
                "asset": "BTC",
                "analysis": {
                    "fair_prob": 0.70,
                    "market_prob": 0.55,
                    "net_edge": 0.15,
                    "model_confidence": 0.80,
                    "regime": "TREND"
                },
                "recommendation": {
                    "action": "YES_NOW",
                    "conviction": "HIGH",
                    "size": "MEDIUM"
                },
                "executionLayer": {
                    "entryStyle": "ENTER_LIMIT",
                    "slippageRisk": 0.10,
                    "entryQualityScore": 0.75,
                    "spreadRegime": "NORMAL",
                    "depthQuality": "OK",
                    "maxSlippageBps": 50
                },
                "repricing": {
                    "repricing_state": "early_repricing"
                }
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        
        result = data.get("result", {})
        # Verify all required fields
        assert "executionScore" in result
        assert "executionGrade" in result
        assert "entry" in result
        assert "timing" in result
        assert "slippage" in result
        assert "opportunity" in result
        assert "context" in result
        assert "lessons" in result
        
        # Verify direction is LONG (YES_NOW = LONG)
        assert result["context"]["direction"] == "LONG"
        
        # Verify score is between 0 and 1
        assert 0 <= result["executionScore"] <= 1
        
        # Verify grade is valid
        assert result["executionGrade"] in ["A", "B", "C", "D", "F"]
        
        print(f"PASS: LONG direction scoring - Score: {result['executionScore']}, Grade: {result['executionGrade']}")

    def test_evaluate_short_direction(self):
        """Test SHORT direction case scoring"""
        payload = {
            "case": {
                "market_id": "test_short_001",
                "asset": "ETH",
                "analysis": {
                    "fair_prob": 0.35,
                    "market_prob": 0.55,
                    "net_edge": -0.20,
                    "model_confidence": 0.75,
                    "regime": "RANGE"
                },
                "recommendation": {
                    "action": "NO_NOW",
                    "conviction": "HIGH",
                    "size": "MEDIUM"
                },
                "executionLayer": {
                    "entryStyle": "ENTER_MARKET",
                    "slippageRisk": 0.08,
                    "entryQualityScore": 0.80,
                    "spreadRegime": "NARROW",
                    "depthQuality": "DEEP",
                    "maxSlippageBps": 30
                },
                "repricing": {
                    "repricing_state": "fresh_mispricing"
                }
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        result = data.get("result", {})
        # Verify direction is SHORT (NO_NOW = SHORT)
        assert result["context"]["direction"] == "SHORT"
        
        # Verify entry evaluation
        entry = result.get("entry", {})
        assert "quality" in entry
        assert entry["quality"] in ["EXCELLENT", "GOOD", "OK", "BAD"]
        
        # Verify timing evaluation
        timing = result.get("timing", {})
        assert "quality" in timing
        assert timing["quality"] in ["EXCELLENT", "GOOD", "OK", "LATE", "BAD"]
        
        print(f"PASS: SHORT direction scoring - Score: {result['executionScore']}, Direction: {result['context']['direction']}")

    def test_evaluate_with_snapshots(self):
        """Test scoring with market path snapshots"""
        payload = {
            "case": {
                "market_id": "test_snapshots_001",
                "asset": "SOL",
                "analysis": {
                    "fair_prob": 0.60,
                    "market_prob": 0.50,
                    "net_edge": 0.10,
                    "regime": "TRANSITION"
                },
                "recommendation": {"action": "YES_SMALL"},
                "executionLayer": {
                    "entryStyle": "STAGGER_LIMIT",
                    "maxSlippageBps": 40
                }
            },
            "snapshots": [
                {"timestamp": "2026-01-01T10:00:00Z", "marketProb": 0.48},
                {"timestamp": "2026-01-01T10:15:00Z", "marketProb": 0.50},
                {"timestamp": "2026-01-01T10:30:00Z", "marketProb": 0.52},
                {"timestamp": "2026-01-01T11:00:00Z", "marketProb": 0.55}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        result = data.get("result", {})
        assert "executionScore" in result
        assert "lessons" in result
        assert isinstance(result["lessons"], list)
        
        print(f"PASS: Scoring with snapshots - Lessons: {len(result['lessons'])}")

    def test_evaluate_missing_case_data(self):
        """Test error handling for missing case data"""
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is False
        assert "error" in data
        
        print("PASS: Missing case data returns error")


class TestExecutionScoreBatch:
    """POST /api/execution-score/evaluate/batch — Batch execution scoring"""

    def test_batch_evaluate_multiple_cases(self):
        """Test batch scoring returns results keyed by market_id"""
        payload = {
            "cases": [
                {
                    "market_id": "batch_btc_001",
                    "asset": "BTC",
                    "analysis": {"fair_prob": 0.65, "market_prob": 0.55, "net_edge": 0.10, "regime": "TREND"},
                    "recommendation": {"action": "YES_NOW"},
                    "executionLayer": {"entryStyle": "ENTER_LIMIT", "maxSlippageBps": 50}
                },
                {
                    "market_id": "batch_eth_002",
                    "asset": "ETH",
                    "analysis": {"fair_prob": 0.40, "market_prob": 0.55, "net_edge": -0.15, "regime": "RANGE"},
                    "recommendation": {"action": "NO_NOW"},
                    "executionLayer": {"entryStyle": "ENTER_MARKET", "maxSlippageBps": 30}
                },
                {
                    "market_id": "batch_sol_003",
                    "asset": "SOL",
                    "analysis": {"fair_prob": 0.55, "market_prob": 0.50, "net_edge": 0.05, "regime": "TRANSITION"},
                    "recommendation": {"action": "YES_SMALL"},
                    "executionLayer": {"entryStyle": "WAIT_RETRACE", "maxSlippageBps": 40}
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate/batch", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "results" in data
        assert "count" in data
        
        results = data["results"]
        # Verify results are keyed by market_id
        assert "batch_btc_001" in results
        assert "batch_eth_002" in results
        assert "batch_sol_003" in results
        
        # Verify count matches
        assert data["count"] == 3
        
        # Verify each result has required fields
        for market_id, result in results.items():
            assert "executionScore" in result
            assert "executionGrade" in result
            assert "context" in result
            assert "direction" in result["context"]
        
        # Verify directions
        assert results["batch_btc_001"]["context"]["direction"] == "LONG"
        assert results["batch_eth_002"]["context"]["direction"] == "SHORT"
        assert results["batch_sol_003"]["context"]["direction"] == "LONG"
        
        print(f"PASS: Batch scoring - {data['count']} cases scored")

    def test_batch_evaluate_empty_cases(self):
        """Test error handling for empty cases array"""
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate/batch", json={"cases": []})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is False
        assert "error" in data
        
        print("PASS: Empty cases array returns error")


class TestExecutionScoreStyles:
    """GET /api/execution-score/styles — Style performance stats"""

    def test_get_style_performance(self):
        """Test style performance aggregation"""
        response = requests.get(f"{BASE_URL}/api/execution-score/styles")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "styles" in data
        assert "lessons" in data
        assert "adjustments" in data
        
        styles = data["styles"]
        assert isinstance(styles, list)
        
        # Verify style structure
        for style in styles:
            assert "style" in style
            assert "avgScore" in style
            assert "count" in style
            assert "winRate" in style
            assert "avgLeakage" in style
            assert "missRate" in style
            assert "bestContext" in style
            assert "worstContext" in style
        
        print(f"PASS: Style performance - {len(styles)} styles tracked")

    def test_python_proxy_styles(self):
        """Test Python proxy endpoint for styles"""
        response = requests.get(f"{BASE_URL}/api/prediction/execution-score/styles")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "styles" in data
        
        print("PASS: Python proxy for styles working")


class TestWeeklyDigestWithExecutionQuality:
    """Weekly Digest integration with Execution Quality"""

    def test_generate_weekly_digest(self):
        """Test weekly digest generation"""
        response = requests.post(f"{BASE_URL}/api/prediction/weekly-digest/generate")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "digest" in data
        
        digest = data["digest"]
        # Verify all required sections
        assert "period" in digest
        assert "generatedAt" in digest
        assert "performance" in digest
        assert "timing" in digest
        assert "sources" in digest
        assert "patterns" in digest
        assert "edgeAttribution" in digest
        assert "decisionQuality" in digest
        assert "calibration" in digest
        assert "alertPerformance" in digest
        assert "lessons" in digest
        assert "mistakes" in digest
        
        # executionQuality may be null if no reviews have execution data
        # This is expected behavior
        if digest.get("executionQuality"):
            eq = digest["executionQuality"]
            assert "avgScore" in eq
            assert "avgGrade" in eq
            assert "totalEvaluated" in eq
            assert "byDirection" in eq
            assert "entryQuality" in eq
            assert "timingQuality" in eq
            print(f"PASS: Weekly digest with executionQuality - {eq['totalEvaluated']} evaluated")
        else:
            print("PASS: Weekly digest generated (executionQuality null - no execution data in reviews)")

    def test_get_latest_digest(self):
        """Test getting latest weekly digest"""
        response = requests.get(f"{BASE_URL}/api/prediction/weekly-digest/latest")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        if data.get("digest"):
            digest = data["digest"]
            assert "period" in digest
            assert "performance" in digest
            print(f"PASS: Latest digest retrieved - Period: {digest['period']['from']} to {digest['period']['to']}")
        else:
            print("PASS: No digest available yet")

    def test_get_digest_history(self):
        """Test getting digest history"""
        response = requests.get(f"{BASE_URL}/api/prediction/weekly-digest/history?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "digests" in data
        assert "count" in data
        
        print(f"PASS: Digest history - {data['count']} digests")


class TestExecutionScoreContextTags:
    """Test context tagging (regime/narrative/volatility)"""

    def test_context_regime_trend(self):
        """Test TREND regime context"""
        payload = {
            "case": {
                "market_id": "ctx_trend_001",
                "asset": "BTC",
                "analysis": {"fair_prob": 0.70, "market_prob": 0.55, "net_edge": 0.15, "regime": "TREND"},
                "recommendation": {"action": "YES_NOW"},
                "executionLayer": {"entryStyle": "ENTER_LIMIT", "maxSlippageBps": 50}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json=payload)
        data = response.json()
        
        assert data.get("ok") is True
        assert data["result"]["context"]["regime"] == "TREND"
        print("PASS: TREND regime context")

    def test_context_regime_range(self):
        """Test RANGE regime context"""
        payload = {
            "case": {
                "market_id": "ctx_range_001",
                "asset": "ETH",
                "analysis": {"fair_prob": 0.45, "market_prob": 0.50, "net_edge": -0.05, "regime": "RANGE"},
                "recommendation": {"action": "NO_SMALL"},
                "executionLayer": {"entryStyle": "STAGGER_LIMIT", "maxSlippageBps": 30}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json=payload)
        data = response.json()
        
        assert data.get("ok") is True
        assert data["result"]["context"]["regime"] == "RANGE"
        print("PASS: RANGE regime context")

    def test_context_narrative_phase(self):
        """Test narrative phase context"""
        payload = {
            "case": {
                "market_id": "ctx_narrative_001",
                "asset": "SOL",
                "analysis": {"fair_prob": 0.60, "market_prob": 0.50, "net_edge": 0.10, "regime": "TRANSITION"},
                "recommendation": {"action": "YES_SMALL"},
                "executionLayer": {"entryStyle": "ENTER_LIMIT", "maxSlippageBps": 40}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json=payload)
        data = response.json()
        
        assert data.get("ok") is True
        assert "narrativePhase" in data["result"]["context"]
        assert data["result"]["context"]["narrativePhase"] in ["EARLY", "EXPANDING", "SATURATED", "EXHAUSTED"]
        print(f"PASS: Narrative phase context - {data['result']['context']['narrativePhase']}")


class TestExecutionScoreEntryEvaluation:
    """Test entry evaluation (optimal zone, position)"""

    def test_entry_quality_excellent(self):
        """Test excellent entry quality detection"""
        payload = {
            "case": {
                "market_id": "entry_excellent_001",
                "asset": "BTC",
                "analysis": {"fair_prob": 0.75, "market_prob": 0.50, "net_edge": 0.25, "regime": "TREND"},
                "recommendation": {"action": "YES_NOW"},
                "executionLayer": {"entryStyle": "ENTER_MARKET", "maxSlippageBps": 20}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json=payload)
        data = response.json()
        
        assert data.get("ok") is True
        entry = data["result"]["entry"]
        assert "quality" in entry
        assert "position" in entry
        assert entry["position"] in ["INSIDE_OPTIMAL", "EDGE_OPTIMAL", "OUTSIDE_OPTIMAL"]
        print(f"PASS: Entry evaluation - Quality: {entry['quality']}, Position: {entry['position']}")


class TestExecutionScoreTimingEvaluation:
    """Test timing evaluation (edge windows, decay)"""

    def test_timing_quality(self):
        """Test timing quality evaluation"""
        payload = {
            "case": {
                "market_id": "timing_001",
                "asset": "ETH",
                "analysis": {"fair_prob": 0.65, "market_prob": 0.55, "net_edge": 0.10, "regime": "RANGE"},
                "recommendation": {"action": "YES_NOW"},
                "executionLayer": {"entryStyle": "ENTER_LIMIT", "maxSlippageBps": 40},
                "repricing": {"repricing_state": "active_repricing"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json=payload)
        data = response.json()
        
        assert data.get("ok") is True
        timing = data["result"]["timing"]
        assert "quality" in timing
        assert "wasEarly" in timing
        assert "wasLate" in timing
        assert "missedBetterWindow" in timing
        assert "edgeDecayRate" in timing
        print(f"PASS: Timing evaluation - Quality: {timing['quality']}, Missed window: {timing['missedBetterWindow']}")


class TestExecutionScoreSlippageEvaluation:
    """Test slippage evaluation"""

    def test_slippage_leakage(self):
        """Test slippage leakage calculation"""
        payload = {
            "case": {
                "market_id": "slippage_001",
                "asset": "SOL",
                "analysis": {"fair_prob": 0.60, "market_prob": 0.50, "net_edge": 0.10, "regime": "TREND"},
                "recommendation": {"action": "YES_NOW"},
                "executionLayer": {"entryStyle": "ENTER_MARKET", "maxSlippageBps": 100}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json=payload)
        data = response.json()
        
        assert data.get("ok") is True
        slippage = data["result"]["slippage"]
        assert "expected" in slippage
        assert "actual" in slippage
        assert "leakage" in slippage
        assert "leakageScore" in slippage
        print(f"PASS: Slippage evaluation - Leakage: {slippage['leakage']}")


class TestExecutionScoreOpportunityCost:
    """Test opportunity cost evaluation"""

    def test_opportunity_cost(self):
        """Test opportunity cost calculation"""
        payload = {
            "case": {
                "market_id": "opportunity_001",
                "asset": "BTC",
                "analysis": {"fair_prob": 0.70, "market_prob": 0.55, "net_edge": 0.15, "regime": "TREND"},
                "recommendation": {"action": "YES_NOW"},
                "executionLayer": {"entryStyle": "WAIT_RETRACE", "maxSlippageBps": 50}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json=payload)
        data = response.json()
        
        assert data.get("ok") is True
        opportunity = data["result"]["opportunity"]
        assert "missedMove" in opportunity
        assert "missedReturn" in opportunity
        assert "reason" in opportunity
        assert opportunity["reason"] in ["WAIT_TOO_LONG", "LIMIT_NOT_FILLED", "LATE_ENTRY", "NONE"]
        print(f"PASS: Opportunity cost - Missed move: {opportunity['missedMove']}, Reason: {opportunity['reason']}")


class TestExecutionScoreLessons:
    """Test lesson generation"""

    def test_lessons_generated(self):
        """Test that lessons are generated based on execution quality"""
        payload = {
            "case": {
                "market_id": "lessons_001",
                "asset": "ETH",
                "analysis": {"fair_prob": 0.65, "market_prob": 0.55, "net_edge": 0.10, "regime": "TREND"},
                "recommendation": {"action": "YES_NOW"},
                "executionLayer": {"entryStyle": "ENTER_LIMIT", "maxSlippageBps": 50},
                "repricing": {"repricing_state": "late_repricing"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/execution-score/evaluate", json=payload)
        data = response.json()
        
        assert data.get("ok") is True
        lessons = data["result"]["lessons"]
        assert isinstance(lessons, list)
        print(f"PASS: Lessons generated - {len(lessons)} lessons")
        for lesson in lessons[:3]:
            print(f"  - {lesson}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
