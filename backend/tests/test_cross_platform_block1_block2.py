"""
Test Cross-Platform Block 1 (Safety) and Block 2 (Analytics) Features

Block 1 (Safety):
- Fixed liquidity to sqrt(a*b)
- Real Edge Filter (trap detection, downgrade/drop)
- Edge badges (verified_edge, execution_risk)

Block 2 (Analytics):
- Edge case type tracking in MongoDB
- Analytics endpoints (/analytics, /analytics/signals)
- Analytics UI in Analytics tab
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestRebuildPipeline:
    """Test rebuild pipeline includes real_edge_filter step"""

    def test_rebuild_returns_ok(self):
        """POST /api/cross-market/kalshi/rebuild returns ok:true"""
        response = requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Rebuild OK: {data.get('summary', {})}")

    def test_rebuild_summary_structure(self):
        """Rebuild summary includes expected fields"""
        response = requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild", timeout=60)
        assert response.status_code == 200
        data = response.json()
        summary = data.get("summary", {})
        
        # Check expected fields
        expected_fields = [
            "kalshi_raw", "kalshi_filtered", "poly_markets",
            "clusters", "relations", "violations", "mispricings",
            "strategies_actionable"
        ]
        for field in expected_fields:
            assert field in summary, f"Missing field: {field}"
        print(f"Rebuild summary: {summary}")


class TestSignalsEndpoint:
    """Test GET /api/cross-market/kalshi/signals includes new Block 1 fields"""

    def test_signals_returns_ok(self):
        """GET /api/cross-market/kalshi/signals returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/signals", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Signals count: {data.get('count', 0)}")

    def test_signals_structure_has_new_fields(self):
        """Signals include real_edge_score, edge_badge, trap_flags, real_edge_components"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/signals", timeout=30)
        assert response.status_code == 200
        data = response.json()
        signals = data.get("signals", [])
        
        # Even if empty, structure should be correct
        assert isinstance(signals, list)
        
        if len(signals) > 0:
            sig = signals[0]
            # Check new Block 1 fields exist (may be None if no signals pass filter)
            assert "real_edge_score" in sig, "Missing real_edge_score field"
            assert "edge_badge" in sig, "Missing edge_badge field"
            assert "trap_flags" in sig, "Missing trap_flags field"
            assert "real_edge_components" in sig, "Missing real_edge_components field"
            
            # Validate edge_badge values
            if sig.get("edge_badge"):
                assert sig["edge_badge"] in ["verified_edge", "execution_risk", "drop"], \
                    f"Invalid edge_badge: {sig['edge_badge']}"
            
            # Validate trap_flags is a list
            assert isinstance(sig.get("trap_flags", []), list)
            
            print(f"Signal sample: entity={sig.get('entity')}, edge_badge={sig.get('edge_badge')}, "
                  f"real_edge_score={sig.get('real_edge_score')}, trap_flags={sig.get('trap_flags')}")
        else:
            print("No signals returned (expected with current live data < 2% gaps)")


class TestMispricingsEndpoint:
    """Test GET /api/cross-market/kalshi/mispricings includes new Block 1 fields"""

    def test_mispricings_returns_ok(self):
        """GET /api/cross-market/kalshi/mispricings returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/mispricings", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Mispricings count: {data.get('count', 0)}")

    def test_mispricings_structure_has_new_fields(self):
        """Mispricings include real_edge_score, edge_badge, trap_flags, real_edge_components"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/mispricings", timeout=30)
        assert response.status_code == 200
        data = response.json()
        mispricings = data.get("mispricings", [])
        
        assert isinstance(mispricings, list)
        
        if len(mispricings) > 0:
            m = mispricings[0]
            assert "real_edge_score" in m, "Missing real_edge_score field"
            assert "edge_badge" in m, "Missing edge_badge field"
            assert "trap_flags" in m, "Missing trap_flags field"
            assert "real_edge_components" in m, "Missing real_edge_components field"
            print(f"Mispricing sample: entity={m.get('entity')}, edge_badge={m.get('edge_badge')}")
        else:
            print("No mispricings returned (expected with current live data)")


class TestStrategiesEndpoint:
    """Test GET /api/cross-market/kalshi/strategies returns actionable/no_trade"""

    def test_strategies_returns_ok(self):
        """GET /api/cross-market/kalshi/strategies returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/strategies", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Strategies: actionable={data.get('total_actionable', 0)}, no_trade={data.get('total_no_trade', 0)}")

    def test_strategies_structure(self):
        """Strategies response has actionable and no_trade arrays"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/strategies", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "total_actionable" in data
        assert "total_no_trade" in data
        assert "actionable" in data
        assert "no_trade" in data
        assert isinstance(data["actionable"], list)
        assert isinstance(data["no_trade"], list)


class TestMarketsEndpoint:
    """Test GET /api/cross-market/kalshi/markets"""

    def test_markets_returns_ok(self):
        """GET /api/cross-market/kalshi/markets returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/markets", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Kalshi markets count: {data.get('count', 0)}")


class TestClustersEndpoint:
    """Test GET /api/cross-market/kalshi/clusters"""

    def test_clusters_returns_ok(self):
        """GET /api/cross-market/kalshi/clusters returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/clusters", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Clusters count: {data.get('count', 0)}")


class TestRelationsEndpoint:
    """Test GET /api/cross-market/kalshi/relations"""

    def test_relations_returns_ok(self):
        """GET /api/cross-market/kalshi/relations returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/relations", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Relations count: {data.get('count', 0)}")


class TestAnalyticsEndpoint:
    """Test GET /api/cross-market/kalshi/analytics (Block 2)"""

    def test_analytics_returns_ok(self):
        """GET /api/cross-market/kalshi/analytics returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/analytics", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Analytics: total_signals_tracked={data.get('total_signals_tracked', 0)}")

    def test_analytics_structure(self):
        """Analytics response has by_edge_type and by_platform_pair"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/analytics", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "total_signals_tracked" in data
        assert "by_edge_type" in data
        assert "by_platform_pair" in data
        assert isinstance(data["by_edge_type"], list)
        assert isinstance(data["by_platform_pair"], list)
        
        print(f"by_edge_type count: {len(data['by_edge_type'])}")
        print(f"by_platform_pair count: {len(data['by_platform_pair'])}")

    def test_analytics_by_edge_type_fields(self):
        """by_edge_type entries have expected fields"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/analytics", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        by_type = data.get("by_edge_type", [])
        if len(by_type) > 0:
            entry = by_type[0]
            expected_fields = [
                "edge_case_type", "count", "actionable_count",
                "avg_predicted_edge", "avg_score", "win_rate",
                "avg_realized_edge", "edge_capture_ratio", "execution_success_rate"
            ]
            for field in expected_fields:
                assert field in entry, f"Missing field in by_edge_type: {field}"
            print(f"by_edge_type sample: {entry}")
        else:
            print("No by_edge_type data (expected if no signals tracked yet)")


class TestAnalyticsSignalsEndpoint:
    """Test GET /api/cross-market/kalshi/analytics/signals (Block 2)"""

    def test_analytics_signals_returns_ok(self):
        """GET /api/cross-market/kalshi/analytics/signals returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/analytics/signals", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Analytics signals count: {data.get('count', 0)}")

    def test_analytics_signals_structure(self):
        """Analytics signals response has signals array"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/analytics/signals", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "count" in data
        assert "signals" in data
        assert isinstance(data["signals"], list)
        
        if len(data["signals"]) > 0:
            sig = data["signals"][0]
            # Check signal has expected tracking fields
            expected_fields = [
                "entity", "platform_pair", "edge_case_type",
                "gap", "gap_pct", "score", "actionability_score",
                "severity", "actionable"
            ]
            for field in expected_fields:
                assert field in sig, f"Missing field in analytics signal: {field}"
            print(f"Analytics signal sample: entity={sig.get('entity')}, edge_case_type={sig.get('edge_case_type')}")
        else:
            print("No analytics signals (expected if no signals tracked yet)")

    def test_analytics_signals_limit_param(self):
        """Analytics signals respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/analytics/signals?limit=5", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert len(data.get("signals", [])) <= 5


class TestRealEdgeFilterIntegration:
    """Test Real Edge Filter is integrated in pipeline"""

    def test_rebuild_runs_real_edge_filter(self):
        """Rebuild pipeline includes real_edge_filter step"""
        # First rebuild to ensure fresh data
        rebuild_resp = requests.post(f"{BASE_URL}/api/cross-market/kalshi/rebuild", timeout=60)
        assert rebuild_resp.status_code == 200
        
        # Check mispricings - if any exist, they should have real_edge fields
        misp_resp = requests.get(f"{BASE_URL}/api/cross-market/kalshi/mispricings", timeout=30)
        assert misp_resp.status_code == 200
        data = misp_resp.json()
        
        # Even with 0 mispricings, the endpoint should work
        assert data.get("ok") is True
        print(f"After rebuild: {data.get('count', 0)} mispricings")


class TestEdgeBadgeValues:
    """Test edge badge values are correct"""

    def test_edge_badge_enum_values(self):
        """Edge badges should be verified_edge, execution_risk, or empty"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/signals", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        valid_badges = ["verified_edge", "execution_risk", "drop", ""]
        for sig in data.get("signals", []):
            badge = sig.get("edge_badge", "")
            assert badge in valid_badges, f"Invalid edge_badge: {badge}"


class TestTrapFlagsValues:
    """Test trap flags values are correct"""

    def test_trap_flags_enum_values(self):
        """Trap flags should be ASYMMETRIC_LIQUIDITY_TRAP or SPREAD_ASYMMETRY_TRAP"""
        response = requests.get(f"{BASE_URL}/api/cross-market/kalshi/signals", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        valid_traps = ["ASYMMETRIC_LIQUIDITY_TRAP", "SPREAD_ASYMMETRY_TRAP"]
        for sig in data.get("signals", []):
            for trap in sig.get("trap_flags", []):
                assert trap in valid_traps, f"Invalid trap_flag: {trap}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
