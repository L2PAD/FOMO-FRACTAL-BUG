"""
Signals V3.2 Backend Tests — Sprint 1 (UX fixes) + Sprint 2 (Context Layer)
============================================================================
Tests for:
- Context object: regime, risk, pulse, pressure, asset_pressure, ranking
- Context score modifier applied to signal scores
- Freshness decay on final score
- Real age_min field (integer)
- Direction filter (BULLISH/BEARISH)
- /api/signals/stats endpoint
"""

import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSignalsContextLayer:
    """Sprint 2: Signal Context Layer tests"""

    def test_signals_have_context_object(self):
        """Each signal should have context object with required fields"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        
        signals = data.get("signals", [])
        assert len(signals) > 0, "Expected at least 1 signal"
        
        for sig in signals:
            context = sig.get("context")
            assert context is not None, f"Signal {sig['id']} missing context object"
            
            # Required context fields from Sprint 2
            assert "regime" in context, "context missing 'regime'"
            assert "risk" in context, "context missing 'risk'"
            assert "pulse" in context, "context missing 'pulse'"
            assert "pressure" in context, "context missing 'pressure'"
            assert "asset_pressure" in context, "context missing 'asset_pressure'"
            assert "ranking" in context, "context missing 'ranking'"
            
            # Validate types
            assert isinstance(context["regime"], str), "regime should be string"
            assert isinstance(context["risk"], str), "risk should be string"
            assert isinstance(context["pulse"], str), "pulse should be string"
            assert isinstance(context["pressure"], str), "pressure should be string"
            assert isinstance(context["asset_pressure"], str), "asset_pressure should be string"
            assert isinstance(context["ranking"], int), "ranking should be integer"
            
            print(f"Signal {sig['id']}: regime={context['regime']}, risk={context['risk']}, ranking={context['ranking']}")

    def test_context_pressure_values(self):
        """Context pressure should be bullish/bearish/neutral"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        assert resp.status_code == 200
        data = resp.json()
        
        valid_pressures = {"bullish", "bearish", "neutral"}
        for sig in data.get("signals", []):
            context = sig.get("context", {})
            pressure = context.get("pressure")
            assert pressure in valid_pressures, f"Invalid pressure: {pressure}"
            
            asset_pressure = context.get("asset_pressure")
            assert asset_pressure in valid_pressures, f"Invalid asset_pressure: {asset_pressure}"

    def test_context_regime_values(self):
        """Context regime should be valid regime types"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        assert resp.status_code == 200
        data = resp.json()
        
        valid_regimes = {"bull_trend", "bear_trend", "accumulation", "distribution", 
                        "neutral_chop", "early_bull", "capitulation"}
        for sig in data.get("signals", []):
            context = sig.get("context", {})
            regime = context.get("regime")
            assert regime in valid_regimes, f"Invalid regime: {regime}"


class TestSignalsAgeField:
    """Sprint 1: Real age_min field tests"""

    def test_signals_have_age_min_field(self):
        """Each signal should have age_min field (integer)"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        assert resp.status_code == 200
        data = resp.json()
        
        signals = data.get("signals", [])
        for sig in signals:
            assert "age_min" in sig, f"Signal {sig['id']} missing age_min"
            age_min = sig["age_min"]
            assert isinstance(age_min, int), f"age_min should be int, got {type(age_min)}"
            assert age_min >= 0, "age_min should be non-negative"
            print(f"Signal {sig['id']}: age_min={age_min}")


class TestSignalsFreshnessDecay:
    """Sprint 2: Freshness decay on final score"""

    def test_signals_have_freshness_field(self):
        """Each signal should have freshness field (0-1 float)"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        assert resp.status_code == 200
        data = resp.json()
        
        signals = data.get("signals", [])
        for sig in signals:
            assert "freshness" in sig, f"Signal {sig['id']} missing freshness"
            freshness = sig["freshness"]
            assert isinstance(freshness, (int, float)), f"freshness should be numeric"
            assert 0 <= freshness <= 1.0, f"freshness should be 0-1, got {freshness}"
            print(f"Signal {sig['id']}: freshness={freshness}")


class TestSignalsDriversAndStructure:
    """Sprint 1: Per-signal drivers and structure"""

    def test_signals_have_drivers(self):
        """Each signal should have drivers dict"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        assert resp.status_code == 200
        data = resp.json()
        
        for sig in data.get("signals", []):
            drivers = sig.get("drivers")
            assert drivers is not None, f"Signal {sig['id']} missing drivers"
            assert isinstance(drivers, dict), "drivers should be dict"
            assert len(drivers) > 0, "drivers should not be empty"
            print(f"Signal {sig['id']}: drivers={list(drivers.keys())}")

    def test_signals_have_expected_move_and_timeframe(self):
        """Signals should have expected_move and timeframe fields"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        assert resp.status_code == 200
        data = resp.json()
        
        for sig in data.get("signals", []):
            assert "expected_move" in sig, "missing expected_move"
            assert "timeframe" in sig, "missing timeframe"
            # expected_move can be empty string, timeframe should always have value
            assert isinstance(sig["timeframe"], str), "timeframe should be string"

    def test_signals_have_invalidation(self):
        """Each signal should have invalidation object"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        assert resp.status_code == 200
        data = resp.json()
        
        for sig in data.get("signals", []):
            inv = sig.get("invalidation")
            assert inv is not None, f"Signal {sig['id']} missing invalidation"
            assert "type" in inv, "invalidation missing type"
            assert "description" in inv, "invalidation missing description"


class TestSignalsDirectionFilter:
    """Direction filter tests"""

    def test_direction_filter_bullish(self):
        """?direction=BULLISH should filter signals"""
        resp = requests.get(f"{BASE_URL}/api/signals?direction=BULLISH")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        
        for sig in data.get("signals", []):
            assert sig["direction"] == "BULLISH", f"Expected BULLISH, got {sig['direction']}"

    def test_direction_filter_bearish(self):
        """?direction=BEARISH should filter signals"""
        resp = requests.get(f"{BASE_URL}/api/signals?direction=BEARISH")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        # All returned signals (if any) should be BEARISH
        for sig in data.get("signals", []):
            assert sig["direction"] == "BEARISH", f"Expected BEARISH, got {sig['direction']}"


class TestSignalsStats:
    """Stats endpoint tests"""

    def test_stats_endpoint_works(self):
        """GET /api/signals/stats should return summary"""
        resp = requests.get(f"{BASE_URL}/api/signals/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        
        # Required fields
        assert "total" in data
        assert "strong" in data
        assert "extreme" in data
        assert "bullish" in data
        assert "bearish" in data
        assert "avg_score" in data
        assert "has_cluster" in data
        assert "cluster_count" in data
        
        print(f"Stats: total={data['total']}, strong={data['strong']}, avg={data['avg_score']}")

    def test_stats_strong_count_matches_signals(self):
        """Strong count should match signals with score >= 60"""
        stats_resp = requests.get(f"{BASE_URL}/api/signals/stats")
        sig_resp = requests.get(f"{BASE_URL}/api/signals")
        
        stats = stats_resp.json()
        signals = sig_resp.json().get("signals", [])
        
        strong_from_signals = sum(1 for s in signals if s["score"] >= 60)
        assert stats["strong"] == strong_from_signals, f"Strong count mismatch: stats={stats['strong']}, calculated={strong_from_signals}"


class TestSignalsScoreThresholds:
    """Score thresholds for Strong/Watch signals"""

    def test_strong_signals_have_score_gte_60(self):
        """STRONG/EXTREME signals should have score >= 60"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        signals = resp.json().get("signals", [])
        
        strong_severities = {"STRONG", "EXTREME"}
        for sig in signals:
            if sig["severity"] in strong_severities:
                assert sig["score"] >= 60, f"STRONG signal {sig['id']} has score {sig['score']} < 60"

    def test_watch_signals_have_score_40_to_59(self):
        """WATCH signals should have score 40-59"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        signals = resp.json().get("signals", [])
        
        for sig in signals:
            if sig["severity"] == "WATCH":
                assert 40 <= sig["score"] < 60, f"WATCH signal {sig['id']} has score {sig['score']} outside 40-59"

    def test_signals_sorted_by_score_desc(self):
        """Signals should be sorted by score descending"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        signals = resp.json().get("signals", [])
        
        scores = [s["score"] for s in signals]
        assert scores == sorted(scores, reverse=True), "Signals not sorted by score descending"


class TestSignalsClustering:
    """Clustering tests"""

    def test_clustered_signals_have_cluster_fields(self):
        """Clustered signals should have cluster_id, cluster_score, cluster_count"""
        resp = requests.get(f"{BASE_URL}/api/signals")
        signals = resp.json().get("signals", [])
        
        for sig in signals:
            assert "cluster_count" in sig, "missing cluster_count"
            if sig["cluster_count"] > 1:
                assert sig.get("cluster_id") is not None, f"Clustered signal {sig['id']} missing cluster_id"
                assert "cluster_score" in sig, f"Clustered signal {sig['id']} missing cluster_score"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
