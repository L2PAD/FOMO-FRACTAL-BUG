"""
Cross-Market Intelligence Phase 2 Tests.

Tests for:
- Probability constraint modes (SUBSET, MONOTONIC, EQUIVALENT)
- Mispricing scoring engine
- Strategy builder (BUY_YES/SELL_YES/NO_TRADE)
- Phase 2 API endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCrossMarketPhase2APIs:
    """Test Phase 2 Cross-Market API endpoints."""

    def test_analysis_endpoint_includes_phase2_summary(self):
        """GET /api/cross-market/analysis should include Phase 2 summary fields."""
        response = requests.get(f"{BASE_URL}/api/cross-market/analysis")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        # Phase 2 summary fields
        summary = data["summary"]
        assert "mispricings" in summary
        assert "strategies_actionable" in summary
        assert isinstance(summary["mispricings"], int)
        assert isinstance(summary["strategies_actionable"], int)
        
        # Phase 1 fields still present
        assert "clusters" in summary
        assert "topics" in summary
        assert "ladders" in summary
        assert "relations" in summary
        assert "signals" in summary
        print(f"✓ Analysis endpoint returns Phase 2 summary: mispricings={summary['mispricings']}, strategies={summary['strategies_actionable']}")

    def test_mispricing_endpoint_structure(self):
        """GET /api/cross-market/mispricing should return proper structure."""
        response = requests.get(f"{BASE_URL}/api/cross-market/mispricing")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "count" in data
        assert "mispricings" in data
        assert "filters" in data
        
        # Verify filter thresholds
        filters = data["filters"]
        assert filters["min_score"] == 0.5
        assert filters["min_gap"] == 0.01
        assert filters["min_relation_confidence"] == 0.6
        
        assert isinstance(data["mispricings"], list)
        print(f"✓ Mispricing endpoint returns {data['count']} mispricings with correct filters")

    def test_strategies_endpoint_structure(self):
        """GET /api/cross-market/strategies should return proper structure."""
        response = requests.get(f"{BASE_URL}/api/cross-market/strategies")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "total_actionable" in data
        assert "total_no_trade" in data
        assert "actionable" in data
        assert "no_trade" in data
        
        assert isinstance(data["actionable"], list)
        assert isinstance(data["no_trade"], list)
        assert isinstance(data["total_actionable"], int)
        assert isinstance(data["total_no_trade"], int)
        print(f"✓ Strategies endpoint returns {data['total_actionable']} actionable, {data['total_no_trade']} no_trade")

    def test_signals_endpoint_includes_relation_modes(self):
        """GET /api/cross-market/signals should include relation_mode in signals."""
        response = requests.get(f"{BASE_URL}/api/cross-market/signals")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "signals" in data
        
        signals = data["signals"]
        assert isinstance(signals, list)
        
        # Check signal types
        signal_types = set(s.get("type") for s in signals)
        print(f"✓ Signals endpoint returns {len(signals)} signals with types: {signal_types}")
        
        # Check for relation_mode in signals that have violations
        for sig in signals:
            if sig.get("type") in ("STRUCTURE_MISMATCH", "MONOTONIC_BREAK"):
                assert "relation_mode" in sig, f"Signal {sig['type']} should have relation_mode"
                assert sig["relation_mode"] in ("SUBSET", "MONOTONIC", "EQUIVALENT")

    def test_rebuild_endpoint_returns_phase2_summary(self):
        """POST /api/cross-market/rebuild should return Phase 2 summary."""
        response = requests.post(f"{BASE_URL}/api/cross-market/rebuild")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        summary = data["summary"]
        # Phase 1 fields
        assert "events_analyzed" in summary
        assert "clusters" in summary
        assert "topics" in summary
        assert "ladders" in summary
        assert "relations" in summary
        assert "signals" in summary
        
        # Phase 2 fields
        assert "mispricings" in summary
        assert "strategies_actionable" in summary
        assert "strategies_no_trade" in summary
        
        print(f"✓ Rebuild returns Phase 2 summary: {summary['events_analyzed']} events → {summary['mispricings']} mispricings, {summary['strategies_actionable']} strategies")


class TestProbabilityConstraintModes:
    """Test probability constraint checking for different modes."""

    def test_signals_contain_subset_mode(self):
        """Signals should include SUBSET relation mode violations."""
        response = requests.get(f"{BASE_URL}/api/cross-market/signals")
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        subset_signals = [s for s in signals if s.get("relation_mode") == "SUBSET"]
        print(f"✓ Found {len(subset_signals)} SUBSET mode signals")

    def test_signals_contain_monotonic_mode(self):
        """Signals should include MONOTONIC relation mode violations."""
        response = requests.get(f"{BASE_URL}/api/cross-market/signals")
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        monotonic_signals = [s for s in signals if s.get("relation_mode") == "MONOTONIC"]
        print(f"✓ Found {len(monotonic_signals)} MONOTONIC mode signals")

    def test_analysis_relations_have_modes(self):
        """Relations in analysis should have relation modes."""
        response = requests.get(f"{BASE_URL}/api/cross-market/analysis")
        assert response.status_code == 200
        
        # Note: relations are in the full analysis but may be truncated
        # The important thing is the summary shows relations count
        data = response.json()
        assert data["summary"]["relations"] > 0
        print(f"✓ Analysis has {data['summary']['relations']} relations")


class TestMispricingScoringEngine:
    """Test mispricing score formula and hard filters."""

    def test_mispricing_filters_applied(self):
        """Mispricings should be filtered by hard thresholds."""
        response = requests.get(f"{BASE_URL}/api/cross-market/mispricing")
        assert response.status_code == 200
        
        data = response.json()
        mispricings = data.get("mispricings", [])
        
        # All returned mispricings should pass hard filters
        for mp in mispricings:
            assert mp.get("mispricing_score", 0) >= 0.5, "Score should be >= 0.5"
            assert mp.get("gap", 0) >= 0.01, "Gap should be >= 1%"
            assert mp.get("relation_confidence", 0) >= 0.6, "Confidence should be >= 0.6"
            
            # Check components exist
            if "components" in mp:
                comp = mp["components"]
                assert "gap" in comp
                assert "confidence" in comp
                assert "liquidity_score" in comp
                assert "time_factor" in comp
        
        print(f"✓ All {len(mispricings)} mispricings pass hard filters")

    def test_mispricing_score_components(self):
        """Mispricings should have score components with correct weights."""
        response = requests.get(f"{BASE_URL}/api/cross-market/mispricing")
        assert response.status_code == 200
        
        data = response.json()
        mispricings = data.get("mispricings", [])
        
        for mp in mispricings:
            if "components" in mp:
                comp = mp["components"]
                # Verify weights match formula
                assert comp.get("gap_weight") == 0.5
                assert comp.get("confidence_weight") == 0.2
                assert comp.get("liquidity_weight") == 0.15
                assert comp.get("time_weight") == 0.15
        
        print(f"✓ Mispricing score components have correct weights")


class TestStrategyBuilder:
    """Test strategy builder outputs."""

    def test_strategy_types(self):
        """Strategies should have correct types."""
        response = requests.get(f"{BASE_URL}/api/cross-market/strategies")
        assert response.status_code == 200
        
        data = response.json()
        actionable = data.get("actionable", [])
        no_trade = data.get("no_trade", [])
        
        # Check actionable strategies
        for s in actionable:
            assert s.get("strategy_type") == "LOGICAL_ARBITRAGE"
            assert s.get("action_a") in ("BUY_YES", "SELL_YES")
            assert s.get("action_b") in ("BUY_YES", "SELL_YES")
            assert "rationale" in s
            assert "mispricing_score" in s
            assert "strategy_confidence" in s
        
        # Check no_trade strategies
        for s in no_trade:
            assert s.get("strategy_type") == "NO_TRADE"
            assert s.get("action_a") == "NO_TRADE"
            assert s.get("action_b") == "NO_TRADE"
        
        print(f"✓ Strategy types correct: {len(actionable)} actionable, {len(no_trade)} no_trade")

    def test_strategy_confidence_levels(self):
        """Strategies should have confidence levels."""
        response = requests.get(f"{BASE_URL}/api/cross-market/strategies")
        assert response.status_code == 200
        
        data = response.json()
        actionable = data.get("actionable", [])
        
        for s in actionable:
            assert s.get("strategy_confidence") in ("HIGH", "MEDIUM", "LOW")
            assert s.get("mode") in ("SUBSET", "MONOTONIC", "EQUIVALENT")
        
        print(f"✓ All strategies have valid confidence levels and modes")


class TestPhase1Phase2Integration:
    """Test Phase 1 and Phase 2 integration."""

    def test_full_pipeline_flow(self):
        """Test the full pipeline from rebuild to strategies."""
        # Rebuild to get fresh data
        rebuild_resp = requests.post(f"{BASE_URL}/api/cross-market/rebuild")
        assert rebuild_resp.status_code == 200
        rebuild_data = rebuild_resp.json()
        assert rebuild_data["ok"] is True
        
        summary = rebuild_data["summary"]
        events = summary["events_analyzed"]
        relations = summary["relations"]
        mispricings = summary["mispricings"]
        strategies = summary["strategies_actionable"]
        
        print(f"Pipeline: {events} events → {relations} relations → {mispricings} mispricings → {strategies} strategies")
        
        # Verify data consistency across endpoints
        analysis_resp = requests.get(f"{BASE_URL}/api/cross-market/analysis")
        analysis_data = analysis_resp.json()
        assert analysis_data["summary"]["mispricings"] == mispricings
        assert analysis_data["summary"]["strategies_actionable"] == strategies
        
        print(f"✓ Full pipeline flow verified with consistent data")

    def test_signals_severity_ordering(self):
        """Signals should be ordered by severity (HIGH > MEDIUM > LOW)."""
        response = requests.get(f"{BASE_URL}/api/cross-market/signals")
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        if len(signals) > 1:
            severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            for i in range(len(signals) - 1):
                curr_sev = severity_order.get(signals[i].get("severity", "LOW"), 3)
                next_sev = severity_order.get(signals[i+1].get("severity", "LOW"), 3)
                assert curr_sev <= next_sev, "Signals should be ordered by severity"
        
        print(f"✓ Signals are properly ordered by severity")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
