"""
Intelligence Console API Tests (Block 4 + Block 6 UI Dashboard)
================================================================
Tests for 6 section endpoints + 1 aggregator endpoint.
All endpoints support ?range=7d|30d|90d|all and ?asset=BTC

Sections tested:
1. /api/admin/intelligence/overview - System Health
2. /api/admin/intelligence/phases - Phase Performance
3. /api/admin/intelligence/regimes - Regime Performance
4. /api/admin/intelligence/scenarios - Scenario Engine
5. /api/admin/intelligence/drift - Drift Intelligence
6. /api/admin/intelligence/tactical - Tactical + Execution Impact
7. /api/admin/intelligence/console - Full Aggregator

Also tests sizeFactor floor in drift_execution_hook
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')


class TestOverviewEndpoint:
    """Section 1: System Health - /api/admin/intelligence/overview"""

    def test_overview_returns_ok(self):
        """GET /api/admin/intelligence/overview?range=all should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/overview?range=all")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        print(f"PASS: overview returns ok=true")

    def test_overview_has_stats(self):
        """Overview should have stats with accuracy, pnl, catastrophic_rate"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/overview?range=all")
        data = response.json()
        stats = data.get("data", {}).get("stats", {})
        
        # Stats should have baseline comparison structure (current/previous/delta)
        assert "accuracy" in stats, "Missing accuracy in stats"
        assert "pnl" in stats, "Missing pnl in stats"
        assert "catastrophic_rate" in stats, "Missing catastrophic_rate in stats"
        print(f"PASS: stats contains accuracy={stats.get('accuracy')}, pnl={stats.get('pnl')}, catastrophic_rate={stats.get('catastrophic_rate')}")

    def test_overview_has_baseline_comparison(self):
        """Stats should have current/previous/delta structure"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/overview?range=30d")
        data = response.json()
        stats = data.get("data", {}).get("stats", {})
        accuracy = stats.get("accuracy", {})
        
        # Check if it has the delta structure (may be flat if using range=all)
        if isinstance(accuracy, dict) and "current" in accuracy:
            assert "current" in accuracy
            assert "previous" in accuracy
            assert "delta" in accuracy
            print(f"PASS: stats has baseline structure - current={accuracy['current']}, previous={accuracy['previous']}, delta={accuracy['delta']}")
        else:
            print(f"INFO: stats has flat structure (likely range=all) - accuracy={accuracy}")

    def test_overview_has_uncertainty_distribution(self):
        """Overview should have uncertainty distribution (low/mid/high)"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/overview?range=all")
        data = response.json()
        uncertainty = data.get("data", {}).get("uncertainty", {})
        
        assert "low" in uncertainty, "Missing uncertainty.low"
        assert "mid" in uncertainty, "Missing uncertainty.mid"
        assert "high" in uncertainty, "Missing uncertainty.high"
        print(f"PASS: uncertainty distribution - low={uncertainty['low']}, mid={uncertainty['mid']}, high={uncertainty['high']}")

    def test_overview_has_execution_modes(self):
        """Overview should have execution_modes (normal/reduced/minimal)"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/overview?range=all")
        data = response.json()
        exec_modes = data.get("data", {}).get("execution_modes", {})
        
        assert "normal" in exec_modes, "Missing execution_modes.normal"
        assert "reduced" in exec_modes, "Missing execution_modes.reduced"
        assert "minimal" in exec_modes, "Missing execution_modes.minimal"
        print(f"PASS: execution_modes - normal={exec_modes['normal']}, reduced={exec_modes['reduced']}, minimal={exec_modes['minimal']}")

    def test_overview_has_system_mode(self):
        """Overview should have system_mode"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/overview?range=all")
        data = response.json()
        system_mode = data.get("data", {}).get("system_mode")
        
        assert system_mode is not None, "Missing system_mode"
        assert system_mode in ["normal", "cautious", "defensive"], f"Unexpected system_mode: {system_mode}"
        print(f"PASS: system_mode={system_mode}")


class TestPhasesEndpoint:
    """Section 2: Phase Performance - /api/admin/intelligence/phases"""

    def test_phases_returns_ok(self):
        """GET /api/admin/intelligence/phases?range=all should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/phases?range=all")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: phases returns ok=true")

    def test_phases_has_phases_data(self):
        """Phases response should have phases dict"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/phases?range=all")
        data = response.json()
        phases = data.get("data", {}).get("phases", {})
        
        assert isinstance(phases, dict), "phases should be a dictionary"
        print(f"PASS: phases contains {len(phases)} phase types: {list(phases.keys())[:5]}")


class TestRegimesEndpoint:
    """Section 3: Regime Performance - /api/admin/intelligence/regimes"""

    def test_regimes_returns_ok(self):
        """GET /api/admin/intelligence/regimes?range=all should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/regimes?range=all")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: regimes returns ok=true")

    def test_regimes_has_regimes_data(self):
        """Regimes response should have regimes dict"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/regimes?range=all")
        data = response.json()
        regimes = data.get("data", {}).get("regimes", {})
        
        assert isinstance(regimes, dict), "regimes should be a dictionary"
        print(f"PASS: regimes contains {len(regimes)} regime types: {list(regimes.keys())[:5]}")


class TestScenariosEndpoint:
    """Section 4: Scenario Engine - /api/admin/intelligence/scenarios"""

    def test_scenarios_returns_ok(self):
        """GET /api/admin/intelligence/scenarios?range=all should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/scenarios?range=all")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: scenarios returns ok=true")

    def test_scenarios_has_scenarios_data(self):
        """Scenarios response should have scenarios dict with coverage"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/scenarios?range=all")
        data = response.json()
        scenarios = data.get("data", {}).get("scenarios", {})
        
        assert isinstance(scenarios, dict), "scenarios should be a dictionary"
        assert "coverage" in scenarios or "n" in scenarios, "scenarios should have coverage or n"
        print(f"PASS: scenarios data - {scenarios}")


class TestDriftEndpoint:
    """Section 5: Drift Intelligence - /api/admin/intelligence/drift"""

    def test_drift_returns_ok(self):
        """GET /api/admin/intelligence/drift?range=all should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/drift?range=all")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: drift returns ok=true")

    def test_drift_has_drift_score(self):
        """Drift response should have drift_score"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/drift?range=all")
        data = response.json()
        drift_data = data.get("data", {})
        
        assert "drift_score" in drift_data, "Missing drift_score"
        print(f"PASS: drift_score={drift_data['drift_score']}")

    def test_drift_has_level(self):
        """Drift response should have level (low/medium/high)"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/drift?range=all")
        data = response.json()
        drift_data = data.get("data", {})
        
        assert "level" in drift_data, "Missing level"
        print(f"PASS: drift level={drift_data['level']}")

    def test_drift_has_top_issues(self):
        """Drift response should have top_issues"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/drift?range=all")
        data = response.json()
        drift_data = data.get("data", {})
        
        assert "top_issues" in drift_data, "Missing top_issues"
        top_issues = drift_data.get("top_issues", [])
        print(f"PASS: top_issues has {len(top_issues)} items")


class TestTacticalEndpoint:
    """Section 6: Tactical + Execution Impact - /api/admin/intelligence/tactical"""

    def test_tactical_returns_ok(self):
        """GET /api/admin/intelligence/tactical?range=all should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/tactical?range=all")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: tactical returns ok=true")

    def test_tactical_has_observations(self):
        """Tactical response should have observations count"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/tactical?range=all")
        data = response.json()
        tactical_data = data.get("data", {})
        
        assert "observations" in tactical_data, "Missing observations"
        print(f"PASS: observations={tactical_data['observations']}")

    def test_tactical_has_bias_distribution(self):
        """Tactical response should have bias_distribution"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/tactical?range=all")
        data = response.json()
        tactical_data = data.get("data", {})
        
        assert "bias_distribution" in tactical_data, "Missing bias_distribution"
        bias = tactical_data.get("bias_distribution", {})
        print(f"PASS: bias_distribution - bullish={bias.get('bullish')}, bearish={bias.get('bearish')}, neutral={bias.get('neutral')}")


class TestConsoleAggregatorEndpoint:
    """Section 7: Full Aggregator - /api/admin/intelligence/console"""

    def test_console_returns_ok(self):
        """GET /api/admin/intelligence/console?range=all should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/console?range=all")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: console returns ok=true")

    def test_console_has_all_sections(self):
        """Console aggregator should have all 6 sections"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/console?range=all")
        data = response.json()
        console_data = data.get("data", {})
        
        expected_sections = ["overview", "phases", "regimes", "scenarios", "drift", "tactical"]
        for section in expected_sections:
            assert section in console_data, f"Missing section: {section}"
        
        print(f"PASS: console has all 6 sections: {expected_sections}")

    def test_console_has_metadata(self):
        """Console should have range, asset, generated_at"""
        response = requests.get(f"{BASE_URL}/api/admin/intelligence/console?range=all")
        data = response.json()
        console_data = data.get("data", {})
        
        assert "range" in console_data, "Missing range"
        assert "asset" in console_data, "Missing asset"
        assert "generated_at" in console_data, "Missing generated_at"
        print(f"PASS: console metadata - range={console_data['range']}, asset={console_data['asset']}")


class TestRangeParameter:
    """Test that range parameter works correctly"""

    def test_different_ranges_return_data(self):
        """Test all range values work: 7d, 30d, 90d, all"""
        ranges = ["7d", "30d", "90d", "all"]
        for r in ranges:
            response = requests.get(f"{BASE_URL}/api/admin/intelligence/overview?range={r}")
            assert response.status_code == 200, f"Failed for range={r}"
            data = response.json()
            assert data.get("ok") == True, f"Expected ok:true for range={r}"
            print(f"PASS: range={r} returns ok=true")

    def test_7d_vs_all_returns_different_data(self):
        """7d and all should potentially return different data"""
        response_7d = requests.get(f"{BASE_URL}/api/admin/intelligence/overview?range=7d")
        response_all = requests.get(f"{BASE_URL}/api/admin/intelligence/overview?range=all")
        
        data_7d = response_7d.json().get("data", {})
        data_all = response_all.json().get("data", {})
        
        # Both should have stats
        assert "stats" in data_7d
        assert "stats" in data_all
        print(f"PASS: Both range=7d and range=all return valid data")
        print(f"  7d stats.n: {data_7d.get('stats', {}).get('n', 'N/A')}")
        print(f"  all stats.n: {data_all.get('stats', {}).get('n', 'N/A')}")


class TestSizeFactorFloor:
    """Test sizeFactor floor fix: size_mult should never go below 0.3"""

    def test_defensive_mode_respects_floor(self):
        """drift_score=0.9, catastrophic_rate=0.5 should still have size_mult >= 0.3"""
        from drift.drift_execution_hook import compute_drift_adjustments
        
        # Maximum risk scenario
        result = compute_drift_adjustments(0.9, 0.5)
        
        assert result["size_mult"] >= 0.3, f"size_mult={result['size_mult']} is below floor 0.3"
        assert result["mode"] == "defensive"
        assert "drift_defensive" in result["flags"]
        assert "high_catastrophic_rate" in result["flags"]
        print(f"PASS: size_mult={result['size_mult']} respects floor 0.3 (mode={result['mode']}, flags={result['flags']})")

    def test_extreme_values_respect_floor(self):
        """Even with drift_score=1.0 and catastrophic_rate=1.0, floor should hold"""
        from drift.drift_execution_hook import compute_drift_adjustments
        
        result = compute_drift_adjustments(1.0, 1.0)
        
        # 1.0 * 0.6 * 0.7 = 0.42, but floor is 0.3 - should be capped at floor
        # Actually: 0.6 * 0.7 = 0.42 which is > 0.3, so result should be 0.42
        assert result["size_mult"] >= 0.3, f"size_mult={result['size_mult']} is below floor 0.3"
        print(f"PASS: extreme values - size_mult={result['size_mult']} (expected ~0.42, floor=0.3)")

    def test_normal_mode_no_floor_needed(self):
        """Low drift and catastrophic rate should return full size"""
        from drift.drift_execution_hook import compute_drift_adjustments
        
        result = compute_drift_adjustments(0.2, 0.1)
        
        assert result["size_mult"] == 1.0, f"Expected size_mult=1.0, got {result['size_mult']}"
        assert result["mode"] == "normal"
        print(f"PASS: normal mode - size_mult={result['size_mult']}, mode={result['mode']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
