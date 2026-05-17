"""
Signals V3 P0/P1 Feature Tests
==============================
Tests for P0 and P1 enhancements of Signals Terminal:
P0: invalidation, direction filter, freshness
P1: alignment, clusters, quality metrics

Endpoints tested:
  - /api/signals — Unified signals stream with filters
  - /api/signals/stats — Signal summary statistics (cluster data)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestP0Invalidation:
    """P0: Invalidation field tests"""

    def test_signals_have_invalidation_object(self):
        """P0-1: Each signal has 'invalidation' object"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        assert len(signals) > 0, "Expected at least one signal"
        
        for signal in signals:
            assert "invalidation" in signal, f"Signal {signal['id']} missing invalidation field"
            assert isinstance(signal["invalidation"], dict), "invalidation should be an object"
        
        print(f"All {len(signals)} signals have invalidation object")

    def test_invalidation_has_required_fields(self):
        """P0-2: Invalidation object has type, description, level fields"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        for signal in signals:
            inv = signal.get("invalidation", {})
            assert "type" in inv, f"Signal {signal['id']} invalidation missing 'type'"
            assert "description" in inv, f"Signal {signal['id']} invalidation missing 'description'"
            assert "level" in inv, f"Signal {signal['id']} invalidation missing 'level'"
            
            # type should be a string
            assert isinstance(inv["type"], str), "invalidation.type should be string"
            # description should be a string
            assert isinstance(inv["description"], str), "invalidation.description should be string"
        
        print(f"All signals have valid invalidation structure with type/description/level")


class TestP0DirectionFilter:
    """P0: Direction filter tests"""

    def test_direction_filter_bullish(self):
        """P0-3: Filter by direction=BULLISH returns only bullish signals"""
        response = requests.get(f"{BASE_URL}/api/signals?direction=BULLISH", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        signals = data.get("signals", [])
        
        for signal in signals:
            assert signal["direction"] == "BULLISH", \
                f"Expected BULLISH, got {signal['direction']}"
        
        print(f"BULLISH filter returned {len(signals)} signals, all BULLISH")

    def test_direction_filter_bearish(self):
        """P0-4: Filter by direction=BEARISH returns only bearish signals"""
        response = requests.get(f"{BASE_URL}/api/signals?direction=BEARISH", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        signals = data.get("signals", [])
        
        # All returned signals should be BEARISH
        for signal in signals:
            assert signal["direction"] == "BEARISH", \
                f"Expected BEARISH, got {signal['direction']}"
        
        print(f"BEARISH filter returned {len(signals)} signals")


class TestP0Freshness:
    """P0: Freshness score tests"""

    def test_signals_have_freshness_field(self):
        """P0-5: Each signal has 'freshness' field (0-1 float)"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        for signal in signals:
            assert "freshness" in signal, f"Signal {signal['id']} missing freshness field"
            freshness = signal["freshness"]
            assert isinstance(freshness, (int, float)), "freshness should be numeric"
            assert 0.0 <= freshness <= 1.0, f"freshness out of range: {freshness}"
        
        print(f"All {len(signals)} signals have valid freshness (0-1)")


class TestP1Alignment:
    """P1: Alignment indicator tests"""

    def test_signals_have_alignment_object(self):
        """P1-1: Each signal has 'alignment' object"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        for signal in signals:
            assert "alignment" in signal, f"Signal {signal['id']} missing alignment field"
            assert isinstance(signal["alignment"], dict), "alignment should be an object"
        
        print(f"All {len(signals)} signals have alignment object")

    def test_alignment_has_required_fields(self):
        """P1-2: Alignment has engine_regime, signal_direction, status fields"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        for signal in signals:
            align = signal.get("alignment", {})
            assert "engine_regime" in align, f"Signal {signal['id']} alignment missing 'engine_regime'"
            assert "signal_direction" in align, f"Signal {signal['id']} alignment missing 'signal_direction'"
            assert "status" in align, f"Signal {signal['id']} alignment missing 'status'"
        
        print(f"All signals have alignment with engine_regime/signal_direction/status")

    def test_alignment_status_values(self):
        """P1-3: Alignment status is aligned/contrarian/neutral"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        valid_statuses = {"aligned", "contrarian", "neutral"}
        
        for signal in signals:
            status = signal.get("alignment", {}).get("status", "")
            assert status in valid_statuses, \
                f"Invalid alignment status: {status}"
        
        print(f"All signals have valid alignment status (aligned/contrarian/neutral)")


class TestP1Quality:
    """P1: Quality metrics tests"""

    def test_signals_have_quality_object(self):
        """P1-4: Each signal has 'quality' object with historical performance"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        for signal in signals:
            assert "quality" in signal, f"Signal {signal['id']} missing quality field"
            assert isinstance(signal["quality"], dict), "quality should be an object"
        
        print(f"All {len(signals)} signals have quality object")

    def test_quality_has_required_fields(self):
        """P1-5: Quality has success_rate, avg_move, samples fields"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        for signal in signals:
            quality = signal.get("quality", {})
            assert "success_rate" in quality, f"Signal {signal['id']} quality missing 'success_rate'"
            assert "avg_move" in quality, f"Signal {signal['id']} quality missing 'avg_move'"
            assert "samples" in quality, f"Signal {signal['id']} quality missing 'samples'"
            
            # Validate types
            assert isinstance(quality["success_rate"], (int, float)), "success_rate should be numeric"
            assert isinstance(quality["avg_move"], (int, float)), "avg_move should be numeric"
            assert isinstance(quality["samples"], int), "samples should be int"
        
        print(f"All signals have quality with success_rate/avg_move/samples")


class TestP1Clusters:
    """P1: Signal clustering tests"""

    def test_stats_has_cluster_fields(self):
        """P1-6: /api/signals/stats returns cluster_count and has_cluster"""
        response = requests.get(f"{BASE_URL}/api/signals/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        assert "cluster_count" in data, "Stats missing cluster_count field"
        assert "has_cluster" in data, "Stats missing has_cluster field"
        
        assert isinstance(data["cluster_count"], int), "cluster_count should be int"
        assert isinstance(data["has_cluster"], bool), "has_cluster should be boolean"
        
        print(f"Stats: has_cluster={data['has_cluster']}, cluster_count={data['cluster_count']}")

    def test_clustered_signals_have_cluster_fields(self):
        """P1-7: Signals with cluster_count > 1 have cluster_id and cluster_score"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        clustered = [s for s in signals if s.get("cluster_count", 0) > 1]
        
        for signal in clustered:
            assert "cluster_id" in signal, f"Clustered signal {signal['id']} missing cluster_id"
            assert "cluster_score" in signal, f"Clustered signal {signal['id']} missing cluster_score"
            assert signal["cluster_id"] is not None, "cluster_id should not be None for clustered signals"
        
        print(f"Found {len(clustered)} clustered signals (cluster_count > 1), all have cluster_id/cluster_score")

    def test_signals_have_cluster_count(self):
        """P1-8: All signals have cluster_count field"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        for signal in signals:
            assert "cluster_count" in signal, f"Signal {signal['id']} missing cluster_count"
            assert isinstance(signal["cluster_count"], int), "cluster_count should be int"
            assert signal["cluster_count"] >= 1, "cluster_count should be >= 1"
        
        print(f"All {len(signals)} signals have cluster_count field")


class TestScoreThreshold:
    """Tests for score thresholds (P0: top cards >= 60)"""

    def test_signals_sorted_by_score_desc(self):
        """Signals should be sorted by score descending"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        if len(signals) > 1:
            for i in range(len(signals) - 1):
                assert signals[i]["score"] >= signals[i+1]["score"], \
                    f"Signals not sorted by score: {signals[i]['score']} < {signals[i+1]['score']}"
        
        print(f"Signals properly sorted by score (highest first)")

    def test_count_strong_signals(self):
        """Count signals with score >= 60 (strong signals for top cards)"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        strong = [s for s in signals if s["score"] >= 60]
        print(f"Strong signals (score >= 60): {len(strong)} out of {len(signals)} total")
        
        # Report the scores
        for s in signals[:5]:
            print(f"  {s['signal_type']}: score={s['score']}, severity={s['severity']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
