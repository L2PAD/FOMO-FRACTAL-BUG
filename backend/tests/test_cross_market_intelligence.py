"""
Cross-Market Intelligence Phase 1 API Tests.

Tests for:
- POST /api/cross-market/rebuild - Force rebuild analysis from current feed
- GET /api/cross-market/analysis - Full analysis (clusters + relations + signals)
- GET /api/cross-market/clusters - Topic clusters only
- GET /api/cross-market/relations - Logical relations only
- GET /api/cross-market/signals - Cross-market signals only
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCrossMarketRebuild:
    """Tests for POST /api/cross-market/rebuild endpoint."""
    
    def test_rebuild_returns_ok_true(self):
        """Rebuild should return ok=true with summary."""
        response = requests.post(f"{BASE_URL}/api/cross-market/rebuild", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        # Verify ok=true
        assert data.get("ok") is True
        
        # Verify summary structure
        summary = data.get("summary", {})
        assert "events_analyzed" in summary
        assert "clusters" in summary
        assert "topics" in summary
        assert "ladders" in summary
        assert "relations" in summary
        assert "violations" in summary
        assert "signals" in summary
        
        # Verify counts are integers
        assert isinstance(summary["events_analyzed"], int)
        assert isinstance(summary["clusters"], int)
        assert isinstance(summary["topics"], int)
        assert isinstance(summary["ladders"], int)
        assert isinstance(summary["relations"], int)
        assert isinstance(summary["violations"], int)
        assert isinstance(summary["signals"], int)
        
        print(f"Rebuild summary: {summary}")
    
    def test_rebuild_has_expected_counts(self):
        """Rebuild should return reasonable counts based on Polymarket data."""
        response = requests.post(f"{BASE_URL}/api/cross-market/rebuild", timeout=60)
        assert response.status_code == 200
        data = response.json()
        summary = data.get("summary", {})
        
        # Expected: ~44 clusters, ~28 topics, ~9 ladders, ~15 signals
        assert summary["events_analyzed"] > 0, "Should have events to analyze"
        assert summary["clusters"] > 0, "Should have clusters"
        assert summary["topics"] > 0, "Should have topics"
        assert summary["ladders"] > 0, "Should have price ladders"
        assert summary["relations"] > 0, "Should have relations"
        assert summary["signals"] > 0, "Should have signals"


class TestCrossMarketAnalysis:
    """Tests for GET /api/cross-market/analysis endpoint."""
    
    def test_analysis_returns_ok_true(self):
        """Analysis should return ok=true with summary, signals, violations, topics."""
        response = requests.get(f"{BASE_URL}/api/cross-market/analysis", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "summary" in data
        assert "signals" in data
        assert "violations" in data
        assert "topics" in data
    
    def test_analysis_summary_structure(self):
        """Analysis summary should have all required fields."""
        response = requests.get(f"{BASE_URL}/api/cross-market/analysis", timeout=30)
        data = response.json()
        summary = data.get("summary", {})
        
        required_fields = ["clusters", "topics", "ladders", "relations", "violations", "signals"]
        for field in required_fields:
            assert field in summary, f"Missing field: {field}"
            assert isinstance(summary[field], int), f"{field} should be int"
    
    def test_analysis_signals_array(self):
        """Analysis signals should be an array with proper structure."""
        response = requests.get(f"{BASE_URL}/api/cross-market/analysis", timeout=30)
        data = response.json()
        signals = data.get("signals", [])
        
        assert isinstance(signals, list)
        if signals:
            signal = signals[0]
            assert "type" in signal
            assert "severity" in signal
            assert "topic_key" in signal
            assert "entity" in signal
            assert "message" in signal
    
    def test_analysis_violations_array(self):
        """Analysis violations should be an array."""
        response = requests.get(f"{BASE_URL}/api/cross-market/analysis", timeout=30)
        data = response.json()
        violations = data.get("violations", [])
        
        assert isinstance(violations, list)
    
    def test_analysis_topics_array(self):
        """Analysis topics should be an array with proper structure."""
        response = requests.get(f"{BASE_URL}/api/cross-market/analysis", timeout=30)
        data = response.json()
        topics = data.get("topics", [])
        
        assert isinstance(topics, list)
        if topics:
            topic = topics[0]
            assert "topic_key" in topic
            assert "entity" in topic
            assert "time_frame" in topic
            assert "topic_type" in topic
            assert "market_count" in topic


class TestCrossMarketClusters:
    """Tests for GET /api/cross-market/clusters endpoint."""
    
    def test_clusters_returns_ok_true(self):
        """Clusters should return ok=true with count and topics array."""
        response = requests.get(f"{BASE_URL}/api/cross-market/clusters", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "count" in data
        assert "topics" in data
        assert isinstance(data["count"], int)
        assert isinstance(data["topics"], list)
    
    def test_clusters_btc_grouping(self):
        """Clusters should correctly group BTC markets together."""
        response = requests.get(f"{BASE_URL}/api/cross-market/clusters", timeout=30)
        data = response.json()
        topics = data.get("topics", [])
        
        btc_topics = [t for t in topics if t.get("entity") == "BTC"]
        assert len(btc_topics) > 0, "Should have BTC clusters"
        
        for topic in btc_topics:
            assert topic["entity"] == "BTC"
            assert topic["market_count"] >= 2, "BTC clusters should have 2+ markets"
        
        print(f"Found {len(btc_topics)} BTC topic clusters")
    
    def test_clusters_eth_grouping(self):
        """Clusters should correctly group ETH markets together."""
        response = requests.get(f"{BASE_URL}/api/cross-market/clusters", timeout=30)
        data = response.json()
        topics = data.get("topics", [])
        
        eth_topics = [t for t in topics if t.get("entity") == "ETH"]
        assert len(eth_topics) > 0, "Should have ETH clusters"
        
        for topic in eth_topics:
            assert topic["entity"] == "ETH"
            assert topic["market_count"] >= 2, "ETH clusters should have 2+ markets"
        
        print(f"Found {len(eth_topics)} ETH topic clusters")
    
    def test_clusters_price_ladder_detection(self):
        """Clusters should detect price ladders (is_ladder=true for price threshold clusters)."""
        response = requests.get(f"{BASE_URL}/api/cross-market/clusters", timeout=30)
        data = response.json()
        topics = data.get("topics", [])
        
        # Check for price_ladder topic types
        ladder_topics = [t for t in topics if t.get("topic_type") == "price_ladder"]
        assert len(ladder_topics) > 0, "Should have price ladder topics"
        
        # Verify BTC and ETH have price ladders
        btc_ladders = [t for t in ladder_topics if t.get("entity") == "BTC"]
        eth_ladders = [t for t in ladder_topics if t.get("entity") == "ETH"]
        
        assert len(btc_ladders) > 0, "BTC should have price ladders"
        assert len(eth_ladders) > 0, "ETH should have price ladders"
        
        print(f"Found {len(btc_ladders)} BTC ladders, {len(eth_ladders)} ETH ladders")


class TestCrossMarketRelations:
    """Tests for GET /api/cross-market/relations endpoint."""
    
    def test_relations_returns_ok_true(self):
        """Relations should return ok=true with count and relations array."""
        response = requests.get(f"{BASE_URL}/api/cross-market/relations", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "count" in data
        assert "relations" in data
        assert isinstance(data["count"], int)
        assert isinstance(data["relations"], list)
    
    def test_relations_subset_type(self):
        """Relations should be SUBSET type with proper explanation."""
        response = requests.get(f"{BASE_URL}/api/cross-market/relations", timeout=30)
        data = response.json()
        relations = data.get("relations", [])
        
        assert len(relations) > 0, "Should have relations"
        
        # All relations should be SUBSET type
        for rel in relations[:10]:  # Check first 10
            assert rel.get("relation") == "SUBSET", f"Expected SUBSET, got {rel.get('relation')}"
            assert "explanation" in rel
            assert "guaranteed" in rel["explanation"].lower(), "Explanation should mention 'guaranteed'"
            assert "threshold_a" in rel
            assert "threshold_b" in rel
            assert rel["threshold_a"] > rel["threshold_b"], "Higher threshold should be subset of lower"
    
    def test_relations_have_prices(self):
        """Relations should include price information."""
        response = requests.get(f"{BASE_URL}/api/cross-market/relations", timeout=30)
        data = response.json()
        relations = data.get("relations", [])
        
        if relations:
            rel = relations[0]
            assert "price_a" in rel
            assert "price_b" in rel
            assert "confidence" in rel


class TestCrossMarketSignals:
    """Tests for GET /api/cross-market/signals endpoint."""
    
    def test_signals_returns_ok_true(self):
        """Signals should return ok=true with count, signals array, and violations array."""
        response = requests.get(f"{BASE_URL}/api/cross-market/signals", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "count" in data
        assert "signals" in data
        assert "violations" in data
        assert isinstance(data["count"], int)
        assert isinstance(data["signals"], list)
        assert isinstance(data["violations"], list)
    
    def test_signals_include_expected_types(self):
        """Signals should include STRUCTURE_MISMATCH, LADDER_VIOLATION, and/or LADDER_GAP types."""
        response = requests.get(f"{BASE_URL}/api/cross-market/signals", timeout=30)
        data = response.json()
        signals = data.get("signals", [])
        
        assert len(signals) > 0, "Should have signals"
        
        signal_types = set(s.get("type") for s in signals)
        expected_types = {"STRUCTURE_MISMATCH", "LADDER_VIOLATION", "LADDER_GAP"}
        
        # At least one expected type should be present
        found_types = signal_types.intersection(expected_types)
        assert len(found_types) > 0, f"Expected at least one of {expected_types}, got {signal_types}"
        
        print(f"Signal types found: {signal_types}")
    
    def test_signals_have_severity(self):
        """Signals should have severity levels."""
        response = requests.get(f"{BASE_URL}/api/cross-market/signals", timeout=30)
        data = response.json()
        signals = data.get("signals", [])
        
        if signals:
            for signal in signals[:5]:
                assert "severity" in signal
                assert signal["severity"] in ["HIGH", "MEDIUM", "LOW"]
    
    def test_signals_have_entity_and_topic(self):
        """Signals should have entity and topic_key."""
        response = requests.get(f"{BASE_URL}/api/cross-market/signals", timeout=30)
        data = response.json()
        signals = data.get("signals", [])
        
        if signals:
            for signal in signals[:5]:
                assert "entity" in signal
                assert "topic_key" in signal
                assert signal["entity"] in ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT", "BNB"]


class TestSelfImprovementAPIsStillWork:
    """Verify existing self-improvement APIs still work after cross-market addition."""
    
    def test_self_improvement_overview(self):
        """Self-improvement overview should still work."""
        response = requests.get(f"{BASE_URL}/api/self-improvement/overview", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "summary" in data
    
    def test_self_improvement_params(self):
        """Self-improvement params should still work."""
        response = requests.get(f"{BASE_URL}/api/self-improvement/params", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "active" in data
    
    def test_self_improvement_patterns(self):
        """Self-improvement patterns should still work."""
        response = requests.get(f"{BASE_URL}/api/self-improvement/patterns", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
