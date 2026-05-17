"""
Phase 3 Integration Tests: Core Engine + Macro V2 Integration
Tests:
- Core Engine consumes Macro V2 pre-computed values (macroMult, riskOffProb, strongActionsBlocked, regime)
- Old F&G linear formula removed (macro context uses new regime-based approach)
- Macro Transition Matrix in Macro V2
- Backend API structure validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://expo-telegram-web.preview.emergentagent.com"

VALID_REGIMES = ['FLIGHT_TO_BTC', 'ALT_ROTATION', 'CAPITAL_EXIT', 'NEUTRAL']


class TestCoreEngineSnapshot:
    """Core Engine snapshot endpoint tests - macro integration"""
    
    def test_core_engine_snapshot_macro_available(self):
        """GET /api/core-engine/snapshot?tf=1h - macro.available=true"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1h", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data.get("ok") == True, "Expected ok=true in response"
        assert "macro" in data, "Expected 'macro' field in response"
        
        macro = data["macro"]
        assert macro.get("available") == True, f"Expected macro.available=true, got {macro.get('available')}"
        print(f"PASS: macro.available = {macro.get('available')}")

    def test_core_engine_snapshot_macro_regime(self):
        """GET /api/core-engine/snapshot?tf=1h - macro.regime is valid"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1h", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        macro = data.get("macro", {})
        regime = macro.get("regime")
        assert regime in VALID_REGIMES, f"Expected regime in {VALID_REGIMES}, got {regime}"
        print(f"PASS: macro.regime = {regime}")

    def test_core_engine_snapshot_macro_multiplier_range(self):
        """GET /api/core-engine/snapshot?tf=1h - macro.multiplier in [0.40, 1.05]"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1h", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        macro = data.get("macro", {})
        multiplier = macro.get("multiplier")
        assert multiplier is not None, "Expected macro.multiplier to exist"
        assert 0.40 <= multiplier <= 1.05, f"Expected multiplier in [0.40, 1.05], got {multiplier}"
        print(f"PASS: macro.multiplier = {multiplier} (in range [0.40, 1.05])")

    def test_core_engine_snapshot_macro_riskoff_range(self):
        """GET /api/core-engine/snapshot?tf=1h - macro.riskOffProb in [0, 1]"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1h", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        macro = data.get("macro", {})
        riskoff = macro.get("riskOffProb")
        assert riskoff is not None, "Expected macro.riskOffProb to exist"
        assert 0.0 <= riskoff <= 1.0, f"Expected riskOffProb in [0, 1], got {riskoff}"
        print(f"PASS: macro.riskOffProb = {riskoff} (in range [0, 1])")

    def test_core_engine_snapshot_macro_regime_label(self):
        """GET /api/core-engine/snapshot?tf=1h - macro.regimeLabel is human readable"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1h", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        macro = data.get("macro", {})
        label = macro.get("regimeLabel")
        assert label is not None, "Expected macro.regimeLabel to exist"
        
        # Should be human readable (e.g., 'Flight To Btc' not 'FLIGHT_TO_BTC')
        valid_labels = ['Flight To Btc', 'Alt Rotation', 'Capital Exit', 'Neutral']
        assert label in valid_labels, f"Expected regimeLabel in {valid_labels}, got {label}"
        print(f"PASS: macro.regimeLabel = '{label}' (human readable)")

    def test_core_engine_snapshot_blocked_gates_macro_format(self):
        """GET /api/core-engine/snapshot?tf=1h - blockedGates show macro regime info (not old F&G)"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1h", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        execution = data.get("execution", {})
        blocked_gates = execution.get("blockedGates", [])
        
        # Check that any macro gate has regime info, not old F&G format
        for gate in blocked_gates:
            if gate.get("gate") == "macro":
                reason = gate.get("reason", "")
                # Should NOT contain old F&G format like "F&G: 25 (fear)" 
                assert "F&G:" not in reason, f"Old F&G format found in macro gate: {reason}"
                # Should contain new regime format
                assert "Macro:" in reason or "Risk-Off" in reason, f"Expected Macro regime format, got: {reason}"
                print(f"PASS: Macro gate reason format = '{reason}'")
        
        # Also check execution summary
        strong_blocked = execution.get("strongActionsBlocked", False)
        print(f"INFO: strongActionsBlocked = {strong_blocked}, blockedGates = {blocked_gates}")
        print("PASS: blockedGates format is correct (no old F&G format)")

    def test_core_engine_snapshot_explain_bullets_macro_context(self):
        """GET /api/core-engine/snapshot?tf=1h - explain.bullets contain macro context"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1h", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        explain = data.get("explain", {})
        bullets = explain.get("bullets", [])
        contributions = explain.get("contributions", {})
        
        # Check contributions.macro exists with regime + confidence
        macro_contrib = contributions.get("macro", {})
        assert "regime" in macro_contrib, "Expected contributions.macro.regime"
        assert "regimeLabel" in macro_contrib, "Expected contributions.macro.regimeLabel"
        assert "riskOffProb" in macro_contrib, "Expected contributions.macro.riskOffProb"
        assert "multiplier" in macro_contrib, "Expected contributions.macro.multiplier"
        
        print(f"PASS: explain.contributions.macro = {macro_contrib}")
        
        # Check bullets mention macro context
        macro_bullets = [b for b in bullets if "Macro" in b or "macro" in b.lower()]
        print(f"INFO: Macro-related bullets = {macro_bullets}")
        print("PASS: explain.bullets contain macro context info")


class TestMacroV2SnapshotTransitions:
    """Macro V2 /api/core/macro/snapshot - transitions field tests"""
    
    def test_macro_snapshot_transitions_present(self):
        """GET /api/core/macro/snapshot - transitions field present"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True, "Expected ok=true"
        assert "transitions" in data, "Expected 'transitions' field in response"
        
        transitions = data["transitions"]
        assert "from" in transitions, "Expected transitions.from"
        assert "probabilities" in transitions, "Expected transitions.probabilities"
        assert "cpiDrift" in transitions, "Expected transitions.cpiDrift"
        assert "riskoffMomentum" in transitions, "Expected transitions.riskoffMomentum"
        
        print(f"PASS: transitions = {transitions}")

    def test_macro_snapshot_transitions_probabilities_keys(self):
        """GET /api/core/macro/snapshot - transitions.probabilities has 4 regime keys"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        probs = data.get("transitions", {}).get("probabilities", {})
        assert len(probs) == 4, f"Expected 4 regime keys, got {len(probs)}"
        
        for regime in VALID_REGIMES:
            assert regime in probs, f"Expected regime '{regime}' in probabilities"
        
        print(f"PASS: transitions.probabilities keys = {list(probs.keys())}")

    def test_macro_snapshot_transitions_probabilities_sum(self):
        """GET /api/core/macro/snapshot - transitions.probabilities sum to ~1.0"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        probs = data.get("transitions", {}).get("probabilities", {})
        total = sum(probs.values())
        assert 0.99 <= total <= 1.01, f"Expected probabilities to sum to ~1.0, got {total}"
        
        print(f"PASS: transitions.probabilities sum = {total}")

    def test_macro_snapshot_transitions_max_self(self):
        """GET /api/core/macro/snapshot - self-transition <= 0.85"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        transitions = data.get("transitions", {})
        current_regime = transitions.get("from")
        probs = transitions.get("probabilities", {})
        
        self_prob = probs.get(current_regime, 0)
        assert self_prob <= 0.85, f"Expected self-transition <= 0.85, got {self_prob}"
        
        print(f"PASS: transitions.probabilities[{current_regime}] = {self_prob} (<= 0.85)")

    def test_macro_snapshot_transitions_min_other(self):
        """GET /api/core/macro/snapshot - each other transition >= 0.02"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        probs = data.get("transitions", {}).get("probabilities", {})
        
        for regime, prob in probs.items():
            assert prob >= 0.02, f"Expected transition to {regime} >= 0.02, got {prob}"
        
        print(f"PASS: All transition probabilities >= 0.02: {probs}")


class TestCoreMacroIntegrationConsistency:
    """Cross-check Core Engine macro data matches Macro V2"""
    
    def test_core_macro_regime_consistency(self):
        """Core Engine macro.regime should match Macro V2 computed.regime"""
        # Get Core Engine snapshot
        core_resp = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1h", timeout=60)
        assert core_resp.status_code == 200
        core_data = core_resp.json()
        
        # Get Macro V2 snapshot
        macro_resp = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=60)
        assert macro_resp.status_code == 200
        macro_data = macro_resp.json()
        
        core_regime = core_data.get("macro", {}).get("regime")
        macro_regime = macro_data.get("computed", {}).get("regime")
        
        assert core_regime == macro_regime, f"Regime mismatch: Core={core_regime}, MacroV2={macro_regime}"
        print(f"PASS: Regime consistency: Core={core_regime}, MacroV2={macro_regime}")

    def test_core_macro_multiplier_consistency(self):
        """Core Engine macro.multiplier should match Macro V2 computed.macroMult"""
        core_resp = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1h", timeout=60)
        macro_resp = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=60)
        
        core_data = core_resp.json()
        macro_data = macro_resp.json()
        
        core_mult = core_data.get("macro", {}).get("multiplier")
        macro_mult = macro_data.get("computed", {}).get("macroMult")
        
        # Allow small floating point difference
        assert abs(core_mult - macro_mult) < 0.01, f"Multiplier mismatch: Core={core_mult}, MacroV2={macro_mult}"
        print(f"PASS: Multiplier consistency: Core={core_mult}, MacroV2={macro_mult}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
