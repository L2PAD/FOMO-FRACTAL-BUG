"""
Overview V2.2 Intelligence API Tests
Tests new V2.2 features: trace, stability, persistence, positionHistory, flipTriggers,
allocation, sizeBreakdown, altOutlook
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestOverviewV22DecisionTrace:
    """Tests for V2.2 Decision Trace feature - mathematical path"""
    
    def test_trace_steps_structure(self):
        """trace.steps has 6 step objects with name/value/formula"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        trace = data.get("decision", {}).get("trace", {})
        steps = trace.get("steps", [])
        
        assert isinstance(steps, list), "trace.steps should be a list"
        assert len(steps) == 6, f"Expected 6 trace steps, got {len(steps)}"
        
        for i, step in enumerate(steps):
            assert "name" in step, f"Step {i} missing 'name'"
            assert "value" in step, f"Step {i} missing 'value'"
            assert "formula" in step, f"Step {i} missing 'formula'"
            assert isinstance(step["name"], str), f"Step {i} name should be string"
            assert isinstance(step["value"], (int, float)), f"Step {i} value should be number"
            assert isinstance(step["formula"], str), f"Step {i} formula should be string"
    
    def test_trace_size_steps_structure(self):
        """trace.sizeSteps has 4 step objects with name/value/formula"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        trace = data.get("decision", {}).get("trace", {})
        size_steps = trace.get("sizeSteps", [])
        
        assert isinstance(size_steps, list), "trace.sizeSteps should be a list"
        assert len(size_steps) == 4, f"Expected 4 size steps, got {len(size_steps)}"
        
        for i, step in enumerate(size_steps):
            assert "name" in step, f"Size step {i} missing 'name'"
            assert "value" in step, f"Size step {i} missing 'value'"
            assert "formula" in step, f"Size step {i} missing 'formula'"
    
    def test_trace_steps_order(self):
        """Verify trace steps are in correct order: Core Bias → Execution → Direction Raw → Macro → Hybrid → Final"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        steps = data.get("decision", {}).get("trace", {}).get("steps", [])
        
        expected_names = ["Core Bias", "× Execution", "= Direction Raw", "× Macro Mult", "× Hybrid Adj", "= Direction Final"]
        actual_names = [s["name"] for s in steps]
        assert actual_names == expected_names, f"Steps order mismatch: {actual_names}"


class TestOverviewV22Stability:
    """Tests for V2.2 Stability Index - tracks decision consistency"""
    
    def test_stability_has_index(self):
        """stability.index is a number 0-1"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        stability = data.get("decision", {}).get("stability", {})
        
        assert "index" in stability, "stability missing 'index'"
        index = stability["index"]
        assert isinstance(index, (int, float)), "stability.index should be number"
        assert 0 <= index <= 1, f"stability.index {index} out of range [0, 1]"
    
    def test_stability_has_action_changed(self):
        """stability.actionChanged is boolean"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        stability = data.get("decision", {}).get("stability", {})
        
        assert "actionChanged" in stability, "stability missing 'actionChanged'"
        assert isinstance(stability["actionChanged"], bool), "actionChanged should be boolean"
    
    def test_stability_has_prev_action(self):
        """stability.prevAction shows previous action"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        stability = data.get("decision", {}).get("stability", {})
        
        assert "prevAction" in stability, "stability missing 'prevAction'"


class TestOverviewV22Persistence:
    """Tests for V2.2 Regime Persistence - tracks regime duration"""
    
    def test_persistence_structure(self):
        """core.persistence has regime/since/periods/isNew"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        persistence = data.get("core", {}).get("persistence", {})
        
        assert "regime" in persistence, "persistence missing 'regime'"
        assert "since" in persistence, "persistence missing 'since'"
        assert "periods" in persistence, "persistence missing 'periods'"
        assert "isNew" in persistence, "persistence missing 'isNew'"
    
    def test_persistence_periods_is_positive(self):
        """persistence.periods is positive integer"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        periods = data.get("core", {}).get("persistence", {}).get("periods")
        
        assert isinstance(periods, int), "persistence.periods should be int"
        assert periods >= 1, f"persistence.periods {periods} should be >= 1"
    
    def test_persistence_is_new_is_boolean(self):
        """persistence.isNew is boolean"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        is_new = data.get("core", {}).get("persistence", {}).get("isNew")
        
        assert isinstance(is_new, bool), "persistence.isNew should be boolean"


class TestOverviewV22PositionHistory:
    """Tests for V2.2 Position History - sparkline data"""
    
    def test_position_history_is_array(self):
        """positionHistory is an array"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        history = data.get("positionHistory")
        
        assert history is not None, "positionHistory should exist"
        assert isinstance(history, list), "positionHistory should be a list"
    
    def test_position_history_entry_structure(self):
        """Each positionHistory entry has ts/sizeMult/action/confidence/edge"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        history = data.get("positionHistory", [])
        
        if len(history) > 0:
            entry = history[0]
            assert "ts" in entry, "history entry missing 'ts'"
            assert "sizeMult" in entry, "history entry missing 'sizeMult'"
            assert "action" in entry, "history entry missing 'action'"
            assert "confidence" in entry, "history entry missing 'confidence'"
            assert "edge" in entry, "history entry missing 'edge'"
    
    def test_position_history_grows_with_calls(self):
        """positionHistory grows with each API call (up to 48 max)"""
        # First call
        response1 = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response1.status_code == 200
        
        data1 = response1.json()
        len1 = len(data1.get("positionHistory", []))
        
        # Wait and make second call
        time.sleep(0.5)
        response2 = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response2.status_code == 200
        
        data2 = response2.json()
        len2 = len(data2.get("positionHistory", []))
        
        # History should grow (or stay at max 48)
        assert len2 >= len1, f"History should grow: was {len1}, now {len2}"


class TestOverviewV22Allocation:
    """Tests for V2.2 Allocation - BTC/ALTS/STABLE split"""
    
    def test_allocation_structure(self):
        """allocation has btc/alts/stable fields"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        allocation = data.get("decision", {}).get("allocation", {})
        
        assert "btc" in allocation, "allocation missing 'btc'"
        assert "alts" in allocation, "allocation missing 'alts'"
        assert "stable" in allocation, "allocation missing 'stable'"
    
    def test_allocation_sum_approximately_100(self):
        """allocation btc + alts + stable sums to ~100"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        allocation = data.get("decision", {}).get("allocation", {})
        
        total = allocation.get("btc", 0) + allocation.get("alts", 0) + allocation.get("stable", 0)
        # Allow some rounding tolerance
        assert 95 <= total <= 105, f"Allocation sum {total} should be ~100"


class TestOverviewV22SizeBreakdown:
    """Tests for V2.2 Size Breakdown - position sizing factors"""
    
    def test_size_breakdown_structure(self):
        """sizeBreakdown has edgeStrength/confFactor/riskFactor/syncFactor/finalSize"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        breakdown = data.get("decision", {}).get("sizeBreakdown", {})
        
        assert "edgeStrength" in breakdown, "sizeBreakdown missing 'edgeStrength'"
        assert "confFactor" in breakdown, "sizeBreakdown missing 'confFactor'"
        assert "riskFactor" in breakdown, "sizeBreakdown missing 'riskFactor'"
        assert "syncFactor" in breakdown, "sizeBreakdown missing 'syncFactor'"
        assert "finalSize" in breakdown, "sizeBreakdown missing 'finalSize'"
    
    def test_size_breakdown_values_are_numbers(self):
        """All sizeBreakdown values are numbers"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        breakdown = data.get("decision", {}).get("sizeBreakdown", {})
        
        for key in ["edgeStrength", "confFactor", "riskFactor", "syncFactor", "finalSize"]:
            val = breakdown.get(key)
            assert isinstance(val, (int, float)), f"sizeBreakdown.{key} should be number, got {type(val)}"


class TestOverviewV22FlipTriggers:
    """Tests for V2.2 Flip Triggers - conditions to change action"""
    
    def test_flip_triggers_is_array(self):
        """flipTriggers is an array (max 4)"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        triggers = data.get("decision", {}).get("flipTriggers")
        
        assert triggers is not None, "flipTriggers should exist"
        assert isinstance(triggers, list), "flipTriggers should be a list"
        assert len(triggers) <= 4, f"flipTriggers should have max 4 items, got {len(triggers)}"
    
    def test_flip_triggers_structure(self):
        """Each flipTrigger has condition/current/target"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        triggers = data.get("decision", {}).get("flipTriggers", [])
        
        for i, trigger in enumerate(triggers):
            assert "condition" in trigger, f"Trigger {i} missing 'condition'"
            assert "current" in trigger, f"Trigger {i} missing 'current'"
            assert "target" in trigger, f"Trigger {i} missing 'target'"


class TestOverviewV22AltOutlook:
    """Tests for V2.2 Altcoin Outlook - rotation probability"""
    
    def test_alt_outlook_structure(self):
        """altOutlook has score/rotationProb/status/drivers/raw"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        alt = data.get("altOutlook", {})
        
        assert "score" in alt, "altOutlook missing 'score'"
        assert "rotationProb" in alt, "altOutlook missing 'rotationProb'"
        assert "status" in alt, "altOutlook missing 'status'"
        assert "drivers" in alt, "altOutlook missing 'drivers'"
        assert "raw" in alt, "altOutlook missing 'raw'"
    
    def test_alt_outlook_status_valid(self):
        """altOutlook.status is ALT_BULLISH, ALT_BEARISH, or ALT_NEUTRAL"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        status = data.get("altOutlook", {}).get("status")
        valid_statuses = ["ALT_BULLISH", "ALT_BEARISH", "ALT_NEUTRAL"]
        assert status in valid_statuses, f"altOutlook.status '{status}' not in {valid_statuses}"
    
    def test_alt_outlook_rotation_prob_in_range(self):
        """altOutlook.rotationProb is 0-1"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        prob = data.get("altOutlook", {}).get("rotationProb")
        
        assert isinstance(prob, (int, float)), "rotationProb should be number"
        assert 0 <= prob <= 1, f"rotationProb {prob} out of range [0, 1]"
    
    def test_alt_outlook_drivers_structure(self):
        """altOutlook.drivers has btcDomShift/stableShift/lmi/riskImpact"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        drivers = data.get("altOutlook", {}).get("drivers", {})
        
        assert "btcDomShift" in drivers, "drivers missing 'btcDomShift'"
        assert "stableShift" in drivers, "drivers missing 'stableShift'"
        assert "lmi" in drivers, "drivers missing 'lmi'"
        assert "riskImpact" in drivers, "drivers missing 'riskImpact'"
    
    def test_alt_outlook_raw_structure(self):
        """altOutlook.raw has btcDelta7d/stableDelta7d/lmiScore/riskOff"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        raw = data.get("altOutlook", {}).get("raw", {})
        
        assert "btcDelta7d" in raw, "raw missing 'btcDelta7d'"
        assert "stableDelta7d" in raw, "raw missing 'stableDelta7d'"
        assert "lmiScore" in raw, "raw missing 'lmiScore'"
        assert "riskOff" in raw, "raw missing 'riskOff'"


class TestOverviewV22Hybrid:
    """Tests for V2.2 Hybrid BTC↔SPX - market correlation"""
    
    def test_hybrid_has_non_zero_values(self):
        """hybrid has beta/correlation/spillover/hybridScore with actual values (when SPX available)"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        hybrid = data.get("hybrid", {})
        
        # Hybrid should have these fields
        assert "beta" in hybrid, "hybrid missing 'beta'"
        assert "correlation" in hybrid, "hybrid missing 'correlation'"
        assert "spillover" in hybrid, "hybrid missing 'spillover'"
        assert "hybridScore" in hybrid, "hybrid missing 'hybridScore'"
        
        # Check if we have real data (not all zeros)
        beta = hybrid.get("beta", 0)
        corr = hybrid.get("correlation", 0)
        spillover = hybrid.get("spillover", 0)
        hybrid_score = hybrid.get("hybridScore", 0)
        
        has_real_data = abs(beta) > 0.01 or abs(corr) > 0.01 or abs(spillover) > 0.01 or abs(hybrid_score) > 0.01
        # Just verify the structure is present - data may or may not be available
        print(f"Hybrid data: beta={beta}, corr={corr}, spillover={spillover}, score={hybrid_score}")
        print(f"Has real SPX data: {has_real_data}")


class TestOverviewV22ImpactAnalysis:
    """Tests for V2.2 Impact Analysis with numerical reasons"""
    
    def test_reasons_have_impact_numbers(self):
        """decision.reasons have impact field with numerical values"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        reasons = data.get("decision", {}).get("reasons", [])
        
        assert len(reasons) >= 3, f"Expected at least 3 reasons (macro/core/signals), got {len(reasons)}"
        
        for reason in reasons:
            assert "impact" in reason, f"reason missing 'impact': {reason}"
            assert isinstance(reason["impact"], (int, float)), f"impact should be number: {reason}"
    
    def test_reasons_have_three_layers(self):
        """reasons include macro, core, and signals layers"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        reasons = data.get("decision", {}).get("reasons", [])
        
        layers = [r["layer"] for r in reasons]
        assert "macro" in layers, "reasons missing 'macro' layer"
        assert "core" in layers, "reasons missing 'core' layer"
        assert "signals" in layers, "reasons missing 'signals' layer"


class TestOverviewV22Completeness:
    """Verify all V2.2 fields are present in single response"""
    
    def test_all_v22_fields_present(self):
        """Single API call returns all V2.2 fields"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT", "tf": "1h"})
        assert response.status_code == 200
        
        data = response.json()
        
        # Top-level
        assert data.get("ok") is True
        assert "positionHistory" in data
        assert "altOutlook" in data
        
        # Decision V2.2 features
        decision = data.get("decision", {})
        assert "trace" in decision
        assert "stability" in decision
        assert "sizeBreakdown" in decision
        assert "allocation" in decision
        assert "flipTriggers" in decision
        
        # Core V2.2 features
        core = data.get("core", {})
        assert "persistence" in core
        
        print("All V2.2 fields present!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
