"""
Weekly Digest API Tests — Weekly Learning Digest System

Tests for:
- POST /api/weekly-digest/generate — Generate a new weekly digest
- GET /api/weekly-digest/latest — Get the most recent digest
- GET /api/weekly-digest/history — Get digest history
- Python proxy endpoints at /api/prediction/weekly-digest/*

11 Analysis Services:
- performance-aggregator (time segments + regime split)
- timing-analysis
- edge-attribution
- decision-quality (lucky wins vs high quality)
- source-performance
- market-pattern
- missed-opportunity
- calibration-analysis (confidence drift)
- alert-performance
- learning-extractor (lessons/mistakes/improvements/what-changed)
- digest-builder (orchestrator reading from MongoDB)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestWeeklyDigestNodeEndpoints:
    """Test Node.js Weekly Digest endpoints directly"""
    
    def test_generate_digest(self):
        """POST /api/weekly-digest/generate — Generate a new weekly digest"""
        response = requests.post(
            f"{BASE_URL}/api/weekly-digest/generate",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"Generate digest response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Generate response: {data.get('ok')}")
        assert data.get("ok") is True, "Expected ok=true"
        
        digest = data.get("digest")
        assert digest is not None, "Expected digest in response"
        
        # Verify digest structure
        assert "period" in digest, "Expected period in digest"
        assert "generatedAt" in digest, "Expected generatedAt in digest"
        assert "performance" in digest, "Expected performance in digest"
        assert "timing" in digest, "Expected timing in digest"
        assert "edgeAttribution" in digest, "Expected edgeAttribution in digest"
        assert "decisionQuality" in digest, "Expected decisionQuality in digest"
        assert "calibration" in digest, "Expected calibration in digest"
        assert "sources" in digest, "Expected sources in digest"
        assert "patterns" in digest, "Expected patterns in digest"
        assert "missedOpportunities" in digest, "Expected missedOpportunities in digest"
        assert "alertPerformance" in digest, "Expected alertPerformance in digest"
        assert "lessons" in digest, "Expected lessons in digest"
        assert "mistakes" in digest, "Expected mistakes in digest"
        assert "improvements" in digest, "Expected improvements in digest"
        
        print("✓ Generate digest endpoint working correctly")
        return digest
    
    def test_get_latest_digest(self):
        """GET /api/weekly-digest/latest — Get the most recent digest"""
        response = requests.get(
            f"{BASE_URL}/api/weekly-digest/latest",
            timeout=15
        )
        print(f"Get latest digest response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        
        # Digest may be null if none generated yet
        digest = data.get("digest")
        if digest:
            assert "period" in digest, "Expected period in digest"
            assert "performance" in digest, "Expected performance in digest"
            print(f"✓ Latest digest found: {digest.get('period')}")
        else:
            print("✓ No digest found (expected if none generated)")
        
        return digest
    
    def test_get_digest_history(self):
        """GET /api/weekly-digest/history — Get digest history"""
        response = requests.get(
            f"{BASE_URL}/api/weekly-digest/history?limit=5",
            timeout=15
        )
        print(f"Get digest history response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "digests" in data, "Expected digests array"
        assert "count" in data, "Expected count"
        
        digests = data.get("digests", [])
        print(f"✓ Found {len(digests)} digests in history")
        
        # Verify each digest has required fields
        for d in digests[:3]:
            assert "period" in d, "Expected period in each digest"
            assert "generatedAt" in d, "Expected generatedAt in each digest"
        
        return digests


class TestWeeklyDigestPythonProxy:
    """Test Python proxy endpoints for Weekly Digest"""
    
    def test_python_generate_digest(self):
        """POST /api/prediction/weekly-digest/generate — Python proxy"""
        response = requests.post(
            f"{BASE_URL}/api/prediction/weekly-digest/generate",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"Python generate digest response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Python generate response ok: {data.get('ok')}")
        assert data.get("ok") is True, "Expected ok=true"
        
        digest = data.get("digest")
        assert digest is not None, "Expected digest in response"
        print("✓ Python proxy generate endpoint working")
        return digest
    
    def test_python_get_latest_digest(self):
        """GET /api/prediction/weekly-digest/latest — Python proxy"""
        response = requests.get(
            f"{BASE_URL}/api/prediction/weekly-digest/latest",
            timeout=15
        )
        print(f"Python get latest digest response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        print("✓ Python proxy latest endpoint working")
        return data.get("digest")
    
    def test_python_get_digest_history(self):
        """GET /api/prediction/weekly-digest/history — Python proxy"""
        response = requests.get(
            f"{BASE_URL}/api/prediction/weekly-digest/history?limit=10",
            timeout=15
        )
        print(f"Python get digest history response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "digests" in data, "Expected digests array"
        assert "count" in data, "Expected count"
        print(f"✓ Python proxy history endpoint working, count: {data.get('count')}")
        return data.get("digests", [])


class TestDigestPerformanceSection:
    """Test performance section of digest"""
    
    def test_performance_fields(self):
        """Verify performance section has all required fields"""
        response = requests.get(f"{BASE_URL}/api/weekly-digest/latest", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get("digest")
        if not digest:
            pytest.skip("No digest available to test")
        
        perf = digest.get("performance", {})
        
        # Required fields
        assert "accuracy" in perf, "Expected accuracy"
        assert "edgeWeightedAccuracy" in perf, "Expected edgeWeightedAccuracy"
        assert "convictionWeightedAccuracy" in perf, "Expected convictionWeightedAccuracy"
        assert "avgGrade" in perf, "Expected avgGrade"
        assert "gradeDistribution" in perf, "Expected gradeDistribution"
        assert "totalMarkets" in perf, "Expected totalMarkets"
        
        # Segment breakdown
        assert "bySegment" in perf, "Expected bySegment"
        by_segment = perf.get("bySegment", {})
        assert "earlyWeek" in by_segment, "Expected earlyWeek segment"
        assert "midWeek" in by_segment, "Expected midWeek segment"
        assert "lateWeek" in by_segment, "Expected lateWeek segment"
        
        # Regime breakdown
        assert "byRegime" in perf, "Expected byRegime"
        by_regime = perf.get("byRegime", {})
        assert "bull" in by_regime, "Expected bull regime"
        assert "bear" in by_regime, "Expected bear regime"
        assert "transition" in by_regime, "Expected transition regime"
        
        print(f"✓ Performance section verified: accuracy={perf.get('accuracy')}%, grade={perf.get('avgGrade')}")


class TestDigestTimingSection:
    """Test timing analysis section of digest"""
    
    def test_timing_fields(self):
        """Verify timing section has all required fields"""
        response = requests.get(f"{BASE_URL}/api/weekly-digest/latest", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get("digest")
        if not digest:
            pytest.skip("No digest available to test")
        
        timing = digest.get("timing", {})
        
        # Required fields
        assert "early" in timing, "Expected early count"
        assert "good" in timing, "Expected good count"
        assert "ok" in timing, "Expected ok count"
        assert "late" in timing, "Expected late count"
        assert "bad" in timing, "Expected bad count"
        assert "avgTimingQuality" in timing, "Expected avgTimingQuality"
        assert "lateEntryPct" in timing, "Expected lateEntryPct"
        assert "missedWindowPct" in timing, "Expected missedWindowPct"
        
        print(f"✓ Timing section verified: avgQuality={timing.get('avgTimingQuality')}, lateEntry={timing.get('lateEntryPct')}%")


class TestDigestEdgeAttribution:
    """Test edge attribution section of digest"""
    
    def test_edge_attribution_fields(self):
        """Verify edge attribution has all source categories"""
        response = requests.get(f"{BASE_URL}/api/weekly-digest/latest", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get("digest")
        if not digest:
            pytest.skip("No digest available to test")
        
        edge = digest.get("edgeAttribution", {})
        
        # Required source categories
        assert "exchange" in edge, "Expected exchange attribution"
        assert "onchain" in edge, "Expected onchain attribution"
        assert "sentiment" in edge, "Expected sentiment attribution"
        assert "social" in edge, "Expected social attribution"
        assert "project" in edge, "Expected project attribution"
        assert "intelligence" in edge, "Expected intelligence attribution"
        
        print(f"✓ Edge attribution verified: exchange={edge.get('exchange')}, onchain={edge.get('onchain')}")


class TestDigestDecisionQuality:
    """Test decision quality section of digest"""
    
    def test_decision_quality_fields(self):
        """Verify decision quality has all required fields"""
        response = requests.get(f"{BASE_URL}/api/weekly-digest/latest", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get("digest")
        if not digest:
            pytest.skip("No digest available to test")
        
        dq = digest.get("decisionQuality", {})
        
        # Required fields
        assert "highQualityDecisions" in dq, "Expected highQualityDecisions"
        assert "luckyWins" in dq, "Expected luckyWins"
        assert "badButCorrect" in dq, "Expected badButCorrect"
        assert "skillfulLosses" in dq, "Expected skillfulLosses"
        assert "decisionQualityScore" in dq, "Expected decisionQualityScore"
        
        print(f"✓ Decision quality verified: score={dq.get('decisionQualityScore')}, highQuality={dq.get('highQualityDecisions')}")


class TestDigestCalibration:
    """Test calibration analysis section of digest"""
    
    def test_calibration_fields(self):
        """Verify calibration has all required fields"""
        response = requests.get(f"{BASE_URL}/api/weekly-digest/latest", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get("digest")
        if not digest:
            pytest.skip("No digest available to test")
        
        cal = digest.get("calibration", {})
        
        # Required fields
        assert "overconfident" in cal, "Expected overconfident count"
        assert "underconfident" in cal, "Expected underconfident count"
        assert "wellCalibrated" in cal, "Expected wellCalibrated count"
        assert "confidenceDrift" in cal, "Expected confidenceDrift"
        assert "driftDirection" in cal, "Expected driftDirection"
        
        # driftDirection should be UP, DOWN, or STABLE
        assert cal.get("driftDirection") in ["UP", "DOWN", "STABLE"], f"Invalid driftDirection: {cal.get('driftDirection')}"
        
        print(f"✓ Calibration verified: drift={cal.get('driftDirection')}, confidenceDrift={cal.get('confidenceDrift')}")


class TestDigestSources:
    """Test source performance section of digest"""
    
    def test_sources_fields(self):
        """Verify sources section has all required fields"""
        response = requests.get(f"{BASE_URL}/api/weekly-digest/latest", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get("digest")
        if not digest:
            pytest.skip("No digest available to test")
        
        sources = digest.get("sources", {})
        
        # Required arrays
        assert "topSources" in sources, "Expected topSources array"
        assert "decliningSources" in sources, "Expected decliningSources array"
        assert "noisySources" in sources, "Expected noisySources array"
        
        # Verify source structure if any exist
        for s in sources.get("topSources", [])[:2]:
            assert "source" in s, "Expected source name"
            assert "winRate" in s, "Expected winRate"
        
        print(f"✓ Sources verified: top={len(sources.get('topSources', []))}, declining={len(sources.get('decliningSources', []))}")


class TestDigestPatterns:
    """Test market patterns section of digest"""
    
    def test_patterns_fields(self):
        """Verify patterns section has best and worst arrays"""
        response = requests.get(f"{BASE_URL}/api/weekly-digest/latest", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get("digest")
        if not digest:
            pytest.skip("No digest available to test")
        
        patterns = digest.get("patterns", {})
        
        # Required arrays
        assert "best" in patterns, "Expected best patterns array"
        assert "worst" in patterns, "Expected worst patterns array"
        
        # Verify pattern structure if any exist
        for p in patterns.get("best", [])[:2]:
            assert "pattern" in p, "Expected pattern name"
            assert "accuracy" in p, "Expected accuracy"
            assert "count" in p, "Expected count"
        
        print(f"✓ Patterns verified: best={len(patterns.get('best', []))}, worst={len(patterns.get('worst', []))}")


class TestDigestLearning:
    """Test learning extractor output (lessons, mistakes, improvements)"""
    
    def test_learning_arrays(self):
        """Verify lessons, mistakes, improvements arrays exist"""
        response = requests.get(f"{BASE_URL}/api/weekly-digest/latest", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get("digest")
        if not digest:
            pytest.skip("No digest available to test")
        
        # Required arrays
        assert "lessons" in digest, "Expected lessons array"
        assert "mistakes" in digest, "Expected mistakes array"
        assert "improvements" in digest, "Expected improvements array"
        
        # Arrays should be lists
        assert isinstance(digest.get("lessons"), list), "lessons should be a list"
        assert isinstance(digest.get("mistakes"), list), "mistakes should be a list"
        assert isinstance(digest.get("improvements"), list), "improvements should be a list"
        
        print(f"✓ Learning verified: lessons={len(digest.get('lessons', []))}, mistakes={len(digest.get('mistakes', []))}, improvements={len(digest.get('improvements', []))}")


class TestDigestMissedOpportunities:
    """Test missed opportunities section of digest"""
    
    def test_missed_opportunities_structure(self):
        """Verify missed opportunities array structure"""
        response = requests.get(f"{BASE_URL}/api/weekly-digest/latest", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get("digest")
        if not digest:
            pytest.skip("No digest available to test")
        
        missed = digest.get("missedOpportunities", [])
        assert isinstance(missed, list), "missedOpportunities should be a list"
        
        # Verify structure if any exist
        for m in missed[:2]:
            assert "market" in m or "asset" in m, "Expected market or asset"
            assert "missedEdge" in m, "Expected missedEdge"
            assert "reason" in m, "Expected reason"
        
        print(f"✓ Missed opportunities verified: count={len(missed)}")


class TestDigestAlertPerformance:
    """Test alert performance section of digest"""
    
    def test_alert_performance_fields(self):
        """Verify alert performance has all required fields"""
        response = requests.get(f"{BASE_URL}/api/weekly-digest/latest", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get("digest")
        if not digest:
            pytest.skip("No digest available to test")
        
        alert_perf = digest.get("alertPerformance", {})
        
        # Required fields
        assert "alertsTriggered" in alert_perf or "triggered" in alert_perf, "Expected alertsTriggered or triggered"
        assert "actionableAlerts" in alert_perf or "actionable" in alert_perf, "Expected actionableAlerts or actionable"
        assert "correctAlerts" in alert_perf or "correct" in alert_perf, "Expected correctAlerts or correct"
        assert "falsePositives" in alert_perf, "Expected falsePositives"
        
        print(f"✓ Alert performance verified: triggered={alert_perf.get('alertsTriggered', alert_perf.get('triggered', 0))}")


class TestDigestGenerateWithDateRange:
    """Test digest generation with custom date range"""
    
    def test_generate_with_date_range(self):
        """POST /api/weekly-digest/generate with from/to dates"""
        from datetime import datetime, timedelta
        
        to_date = datetime.now()
        from_date = to_date - timedelta(days=14)
        
        response = requests.post(
            f"{BASE_URL}/api/weekly-digest/generate",
            json={
                "from": from_date.isoformat(),
                "to": to_date.isoformat()
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"Generate with date range response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        
        digest = data.get("digest")
        if digest:
            period = digest.get("period", {})
            print(f"✓ Generated digest for period: {period.get('from')} to {period.get('to')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
