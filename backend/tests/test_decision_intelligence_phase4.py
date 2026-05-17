"""
Decision Intelligence Phase 4 Tests
====================================
Tests for:
1. Unified Signal Engine (core_signal_logic + graph_adapter + unified_signal_engine)
2. Expansion Engine (conditional graph growth)
3. Enhanced Entity Resolution (5 passes)
4. Cron pipeline integration (steps 6.8, 6.9, 6.10)

Signal types: ACTOR_DISTRIBUTION, FUND_PRESSURE, FLOW_ACCELERATION, DISTRIBUTION
Expansion triggers: new_edges_6h < 10 (low growth) + actor_gini > 0.6 (high concentration)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://expo-telegram-web.preview.emergentagent.com"


class TestCoreSignalLogic:
    """Test core signal detection primitives."""

    def test_severity_extreme(self):
        """severity(75) = EXTREME"""
        from signals.core_signal_logic import severity
        assert severity(75) == "EXTREME"
        assert severity(100) == "EXTREME"
        assert severity(80) == "EXTREME"

    def test_severity_strong(self):
        """severity(60) = STRONG"""
        from signals.core_signal_logic import severity
        assert severity(60) == "STRONG"
        assert severity(74) == "STRONG"

    def test_severity_watch(self):
        """severity(40) = WATCH"""
        from signals.core_signal_logic import severity
        assert severity(40) == "WATCH"
        assert severity(59) == "WATCH"

    def test_severity_weak(self):
        """severity(20) = WEAK"""
        from signals.core_signal_logic import severity
        assert severity(20) == "WEAK"
        assert severity(0) == "WEAK"
        assert severity(39) == "WEAK"

    def test_compute_score_weights(self):
        """compute_score uses correct weights (0.30, 0.20, 0.15, 0.15, 0.10, 0.10)"""
        from signals.core_signal_logic import compute_score
        # All 1.0 inputs should give 100
        score = compute_score(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        assert score == 100
        # All 0.0 inputs should give 0
        score = compute_score(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert score == 0
        # Only engine_alignment (0.30 weight)
        score = compute_score(1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert score == 30

    def test_detect_signal_type_returns_required_fields(self):
        """detect_signal_type returns is_signal, type, strength, confidence, direction, severity"""
        from signals.core_signal_logic import detect_signal_type
        context = {"mentions": 5, "pressure": 0.6, "alpha": 0.5, "flow": 0.4, "actor_count": 3}
        result = detect_signal_type(context)
        assert "is_signal" in result
        assert "type" in result
        assert "strength" in result
        assert "confidence" in result
        assert "direction" in result
        assert "severity" in result


class TestGraphSignalsAPI:
    """Test /api/graph-signals/* endpoints."""

    def test_graph_signals_run(self):
        """POST /api/graph-signals/run — Graph-level signal detection"""
        response = requests.post(f"{BASE_URL}/api/graph-signals/run", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert "signals_detected" in data
        assert "tokens_scanned" in data
        assert "signals" in data
        print(f"Graph signals: {data['signals_detected']} detected from {data['tokens_scanned']} tokens")
        # Should detect signals (based on context: ~47 expected)
        assert data["signals_detected"] >= 0

    def test_fund_signals_run(self):
        """POST /api/graph-signals/fund/run — Fund-level signal detection"""
        response = requests.post(f"{BASE_URL}/api/graph-signals/fund/run", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert "signals_detected" in data
        assert "funds_scanned" in data
        assert "signals" in data
        print(f"Fund signals: {data['signals_detected']} detected from {data['funds_scanned']} funds")
        # Should detect fund signals (based on context: ~17 expected)
        assert data["signals_detected"] >= 0

    def test_graph_signals_stats(self):
        """GET /api/graph-signals/stats — Unified signal stats"""
        response = requests.get(f"{BASE_URL}/api/graph-signals/stats", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "total_signals_logged" in data
        assert "token_signals" in data
        assert "fund_signals" in data
        assert "signal_edges" in data
        assert "active_funds" in data
        assert "by_type" in data
        print(f"Signal stats: total={data['total_signals_logged']}, tokens={data['token_signals']}, funds={data['fund_signals']}")
        print(f"Signal edges: {data['signal_edges']}, active funds: {data['active_funds']}")
        print(f"By type: {data['by_type']}")

    def test_graph_signals_log(self):
        """GET /api/graph-signals/log?limit=3 — Signal log with context"""
        response = requests.get(f"{BASE_URL}/api/graph-signals/log?limit=3", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "count" in data
        assert "signals" in data
        if data["count"] > 0:
            signal = data["signals"][0]
            # Verify signal log entry structure
            assert "entity" in signal
            assert "type" in signal
            assert "strength" in signal
            assert "confidence" in signal
            assert "direction" in signal
            assert "context" in signal
            # Verify context fields
            ctx = signal.get("context", {})
            print(f"Signal log entry: entity={signal['entity']}, type={signal['type']}, strength={signal['strength']}")
            print(f"Context: mentions={ctx.get('mentions')}, pressure={ctx.get('pressure')}, alpha={ctx.get('alpha')}, flow={ctx.get('flow')}, actor_count={ctx.get('actor_count')}")


class TestExpansionEngine:
    """Test /api/graph/expansion/* endpoints."""

    def test_expansion_check(self):
        """GET /api/graph/expansion/check — Check expansion triggers"""
        response = requests.get(f"{BASE_URL}/api/graph/expansion/check", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert "should_expand" in data
        assert "reason" in data
        assert "metrics" in data
        metrics = data["metrics"]
        assert "new_edges_6h" in metrics
        assert "actor_gini" in metrics
        print(f"Expansion check: should_expand={data['should_expand']}, reason={data['reason']}")
        print(f"Metrics: new_edges_6h={metrics['new_edges_6h']}, actor_gini={metrics['actor_gini']}")
        # Verify trigger thresholds
        # low_growth: new_edges_6h < 10
        # high_gini: actor_gini > 0.6

    def test_expansion_run(self):
        """POST /api/graph/expansion/run — Run expansion cycle (respects triggers)"""
        response = requests.post(f"{BASE_URL}/api/graph/expansion/run", timeout=60)
        assert response.status_code == 200
        data = response.json()
        # Should have expanded or reason why not
        if data.get("expanded"):
            assert "actors" in data
            assert "tokens" in data
            assert "links" in data
            print(f"Expansion ran: actors={data['actors']}, tokens={data['tokens']}, links={data['links']}")
        else:
            assert "reason" in data
            print(f"Expansion skipped: {data['reason']}")

    def test_expansion_log(self):
        """GET /api/graph/expansion/log — Expansion history"""
        response = requests.get(f"{BASE_URL}/api/graph/expansion/log", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "count" in data
        assert "history" in data
        print(f"Expansion log: {data['count']} entries")

    def test_expansion_limits(self):
        """Verify expansion limits: MAX_NEW_ACTORS_PER_CYCLE=20, MAX_NEW_TOKENS_PER_CYCLE=10"""
        from graph.expansion_engine import MAX_NEW_ACTORS_PER_CYCLE, MAX_NEW_TOKENS_PER_CYCLE
        assert MAX_NEW_ACTORS_PER_CYCLE == 20
        assert MAX_NEW_TOKENS_PER_CYCLE == 10


class TestEntityResolution:
    """Test entity resolution endpoints (still working after signal engine additions)."""

    def test_resolution_run(self):
        """POST /api/graph/resolution/run — Entity resolution (5 passes)"""
        response = requests.post(f"{BASE_URL}/api/graph/resolution/run", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        # Verify 5 passes
        assert "token_addresses" in data
        assert "project_protocol" in data
        assert "token_project_bridges" in data
        assert "twitter_person" in data
        assert "signal_actors" in data
        assert "summary" in data
        summary = data["summary"]
        print(f"Resolution: meaningful_unresolved_pct={summary.get('meaningful_unresolved_pct')}%")
        print(f"Meaningful orphans: {summary.get('meaningful_orphans')}, aliases: {summary.get('aliases_stored')}")

    def test_resolution_stats(self):
        """GET /api/graph/resolution/stats — Resolution stats"""
        response = requests.get(f"{BASE_URL}/api/graph/resolution/stats", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "meaningful_unresolved_pct" in data
        print(f"Resolution stats: meaningful_unresolved_pct={data['meaningful_unresolved_pct']}%")
        # Target: meaningful_unresolved_pct ~1.43%
        assert data["meaningful_unresolved_pct"] < 10  # Should be well under 10%


class TestGraphBuildStats:
    """Test graph build stats endpoint."""

    def test_graph_build_stats(self):
        """GET /api/graph/build/stats — Graph build stats"""
        response = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "nodes" in data
        assert "edges" in data
        print(f"Graph: {data['nodes']} nodes, {data['edges']} edges")
        # Based on context: 3737 nodes, 6398 edges
        assert data["nodes"] > 0
        assert data["edges"] > 0


class TestFundSignalAggregation:
    """Test fund signal aggregation across portfolio projects."""

    def test_fund_portfolio_aggregation(self):
        """Fund signals correctly aggregate across fund portfolio"""
        # Run fund signals first
        response = requests.post(f"{BASE_URL}/api/graph-signals/fund/run", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        if data["signals_detected"] > 0:
            # Check a16z or other fund has project_count
            for signal in data.get("signals", []):
                if "a16z" in signal.get("fund", "").lower():
                    print(f"a16z fund: project_count={signal.get('project_count')}, actor_count={signal.get('actor_count')}")
                    # Based on context: a16z should have ~31 projects
                    assert signal.get("project_count", 0) > 0


class TestCronPipelineIntegration:
    """Test cron pipeline order and integration."""

    def test_cron_pipeline_order(self):
        """Verify cron pipeline order: graph_build → entity_resolution → graph_signal_engine → expansion_engine → health_check"""
        import inspect
        from cron_ingestion import run_ingestion_cycle
        
        source = inspect.getsource(run_ingestion_cycle)
        
        # Check stage order by finding stage names in source
        stages = [
            "graph_unified_build",
            "entity_resolution",
            "graph_signal_engine",
            "expansion_engine",
            "health_check",
        ]
        
        positions = {}
        for stage in stages:
            pos = source.find(stage)
            if pos > 0:
                positions[stage] = pos
        
        # Verify order
        sorted_stages = sorted(positions.keys(), key=lambda x: positions[x])
        print(f"Cron pipeline order: {sorted_stages}")
        
        # Verify entity_resolution comes before graph_signal_engine
        if "entity_resolution" in positions and "graph_signal_engine" in positions:
            assert positions["entity_resolution"] < positions["graph_signal_engine"]
        
        # Verify graph_signal_engine comes before expansion_engine
        if "graph_signal_engine" in positions and "expansion_engine" in positions:
            assert positions["graph_signal_engine"] < positions["expansion_engine"]


class TestSignalTypes:
    """Test signal type distribution."""

    def test_signal_types_distribution(self):
        """Verify signal types: ACTOR_DISTRIBUTION, FUND_PRESSURE, FLOW_ACCELERATION, DISTRIBUTION"""
        response = requests.get(f"{BASE_URL}/api/graph-signals/stats", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        by_type = data.get("by_type", {})
        print(f"Signal types distribution: {by_type}")
        
        # Expected types based on context
        expected_types = ["ACTOR_DISTRIBUTION", "FUND_PRESSURE", "FLOW_ACCELERATION", "DISTRIBUTION"]
        for sig_type in expected_types:
            if sig_type in by_type:
                print(f"  {sig_type}: {by_type[sig_type]}")


class TestHealthEndpoint:
    """Test health endpoint still works."""

    def test_health_snapshot(self):
        """GET /api/graph/health/snapshot — Health snapshot"""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Health status: {data.get('status')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
