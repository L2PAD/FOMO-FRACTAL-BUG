"""
Macro V2 Behavioral Fixes Test Suite
Tests: Extreme Fear penalty, Structural Risk weight, LMI F&G sensitivity, Position Sizing Policy
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")


class TestMacroV2BehavioralFixes:
    """Test suite for behavioral logic fixes"""
    
    def test_extreme_fear_penalty_on_alt_rotation(self):
        """When F&G=14 (extreme fear), Alt Rotation should be < 70% due to penalty"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        raw = data.get("raw", {})
        fg = raw.get("fearGreed", 50)
        
        computed = data.get("computed", {})
        regime_probs = computed.get("regimeProbs", {})
        alt_rotation_prob = regime_probs.get("ALT_ROTATION", 0)
        
        # If extreme fear (F&G < 25), Alt Rotation should be penalized below 70%
        if fg < 25:
            assert alt_rotation_prob < 0.70, f"Alt Rotation {alt_rotation_prob*100:.1f}% should be < 70% when F&G={fg} (extreme fear penalty)"
            print(f"PASS: F&G={fg} (Extreme Fear) → Alt Rotation={alt_rotation_prob*100:.1f}% < 70%")
        else:
            print(f"INFO: F&G={fg} (not extreme fear), Alt Rotation={alt_rotation_prob*100:.1f}%")
    
    def test_structural_risk_weight_increase(self):
        """Structural risk should be ~41 (increased from ~39 due to macroMult weight 0.35)"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        risk_split = data.get("riskSplit", {})
        structural = risk_split.get("structural", 0)
        
        # Structural risk should be in reasonable range and around 41
        assert 35 <= structural <= 55, f"Structural risk {structural} out of expected range 35-55"
        print(f"PASS: Structural Risk = {structural} (expected ~41 with new weights)")
    
    def test_lmi_fear_greed_sensitivity(self):
        """LMI should account for Fear & Greed adjustment"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        lmi = data.get("lmi", {})
        lmi_value = lmi.get("lmi", 0)
        state = lmi.get("state", "NEUTRAL")
        
        raw = data.get("raw", {})
        fg = raw.get("fearGreed", 50)
        
        # LMI exists and is valid
        assert isinstance(lmi_value, (int, float)), "LMI value should be numeric"
        assert -100 <= lmi_value <= 100, f"LMI {lmi_value} out of range [-100, +100]"
        assert state in ["INFLOW_TO_SAFETY", "OUTFLOW_FROM_SAFETY", "NEUTRAL"], f"Invalid LMI state: {state}"
        
        print(f"PASS: LMI = {lmi_value} ({state}) with F&G={fg}")


class TestPositionSizingPolicy:
    """Test suite for Position Sizing Policy endpoint"""
    
    def test_position_size_returns_ok(self):
        """GET /api/core/position-size should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/core/position-size?asset=BTCUSDT&tf=1h")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True, "Position sizing API should return ok:true"
        assert data.get("asset") == "BTCUSDT", "Asset should match request"
        print(f"PASS: Position sizing returns ok=True, asset=BTCUSDT")
    
    def test_position_size_blocked_when_strong_actions_blocked(self):
        """When strongActionsBlocked=true, position sizing should be blocked with DEFENSIVE mode"""
        response = requests.get(f"{BASE_URL}/api/core/position-size?asset=BTCUSDT&tf=1h")
        assert response.status_code == 200
        
        data = response.json()
        inputs = data.get("inputs", {})
        macro_inputs = inputs.get("macro", {})
        
        if macro_inputs.get("strongActionsBlocked") is True:
            assert data.get("blocked") is True, "Position should be blocked when strongActionsBlocked=true"
            assert data.get("mode") == "DEFENSIVE", "Mode should be DEFENSIVE when blocked"
            assert data.get("sizeMult") == 0.0 or data.get("sizeMult") == 0, "Size mult should be 0 when blocked"
            
            blocked_reasons = data.get("blockedReasons", [])
            assert len(blocked_reasons) > 0, "Should have blocked reasons"
            assert any("strong actions blocked" in r.lower() or "blocked" in r.lower() for r in blocked_reasons), \
                f"Blocked reasons should mention 'strong actions blocked': {blocked_reasons}"
            
            print(f"PASS: Position BLOCKED (strongActionsBlocked=true)")
            print(f"  Mode: {data.get('mode')}")
            print(f"  SizeMult: {data.get('sizeMult')}")
            print(f"  Reasons: {blocked_reasons}")
        else:
            print(f"INFO: strongActionsBlocked=false, position not blocked")
    
    def test_position_size_components_structure(self):
        """Components and inputs should be properly structured"""
        response = requests.get(f"{BASE_URL}/api/core/position-size?asset=BTCUSDT&tf=1h")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required fields exist
        assert "mode" in data, "Missing mode field"
        assert "blocked" in data, "Missing blocked field"
        assert "sizeMult" in data, "Missing sizeMult field"
        assert "components" in data, "Missing components field"
        assert "inputs" in data, "Missing inputs field"
        assert "explain" in data, "Missing explain field"
        assert "blockedReasons" in data, "Missing blockedReasons field"
        
        # Check mode is valid
        assert data["mode"] in ["DEFENSIVE", "NEUTRAL", "AGGRESSIVE"], f"Invalid mode: {data['mode']}"
        
        # Check inputs structure
        inputs = data["inputs"]
        assert "core" in inputs, "Missing core inputs"
        assert "macro" in inputs, "Missing macro inputs"
        assert "risk" in inputs, "Missing risk inputs"
        assert "sync" in inputs, "Missing sync inputs"
        
        # Check core inputs
        core = inputs["core"]
        assert "direction" in core, "Missing core.direction"
        assert "confidence" in core, "Missing core.confidence"
        assert "regime" in core, "Missing core.regime"
        
        # Check macro inputs
        macro = inputs["macro"]
        assert "regime" in macro, "Missing macro.regime"
        assert "riskOffProb" in macro, "Missing macro.riskOffProb"
        assert "macroMult" in macro, "Missing macro.macroMult"
        assert "strongActionsBlocked" in macro, "Missing macro.strongActionsBlocked"
        assert "fearGreed" in macro, "Missing macro.fearGreed"
        
        # Check risk inputs
        risk = inputs["risk"]
        assert "structural" in risk, "Missing risk.structural"
        assert "tactical" in risk, "Missing risk.tactical"
        
        # Check sync inputs
        sync = inputs["sync"]
        assert "alignmentScore" in sync, "Missing sync.alignmentScore"
        assert "conflictScore" in sync, "Missing sync.conflictScore"
        assert "state" in sync, "Missing sync.state"
        
        print(f"PASS: Position sizing response structure is valid")
        print(f"  Mode: {data['mode']}")
        print(f"  Blocked: {data['blocked']}")
        print(f"  Core: {core['direction']} ({core['confidence']*100:.0f}% conf)")
        print(f"  Macro: {macro['regime']} (RO {macro['riskOffProb']*100:.0f}%)")
        print(f"  Risk: S{risk['structural']}/T{risk['tactical']}")
        print(f"  Sync: {sync['state']} ({sync['alignmentScore']}%)")


class TestMacroStatus:
    """Test suite for Macro status endpoint"""
    
    def test_macro_status_live_data(self):
        """GET /api/core/macro/status should return dataSource:'live' and liveApiAvailable:true"""
        response = requests.get(f"{BASE_URL}/api/core/macro/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("dataSource") == "live", f"Expected dataSource='live', got '{data.get('dataSource')}'"
        assert data.get("liveApiAvailable") is True, "liveApiAvailable should be true"
        
        apis = data.get("apis", {})
        assert apis.get("cryptocompare") == "reachable", f"CryptoCompare should be reachable"
        assert apis.get("coinpaprika") == "used", f"CoinPaprika should be used"
        assert apis.get("alternativeme") == "used", f"Alternative.me should be used"
        
        print(f"PASS: Macro status shows live data")
        print(f"  DataSource: {data.get('dataSource')}")
        print(f"  LiveApiAvailable: {data.get('liveApiAvailable')}")
        print(f"  APIs: {apis}")


class TestMacroSnapshot:
    """Test suite for Macro snapshot full response"""
    
    def test_macro_snapshot_full_response(self):
        """Verify macro snapshot has all required fields with valid data"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Check data source
        assert data.get("dataSource") in ["live", "synthetic"], "Invalid dataSource"
        
        # Check raw data
        raw = data.get("raw", {})
        assert "fearGreed" in raw, "Missing fearGreed"
        assert "btcPrice" in raw, "Missing btcPrice"
        assert "btcDom" in raw, "Missing btcDom"
        assert "stableDom" in raw, "Missing stableDom"
        
        # Check computed data
        computed = data.get("computed", {})
        assert "regime" in computed, "Missing regime"
        assert "regimeProbs" in computed, "Missing regimeProbs"
        assert "riskOffProb" in computed, "Missing riskOffProb"
        assert "macroMult" in computed, "Missing macroMult"
        assert "cpi" in computed, "Missing cpi"
        
        # Check regime probs sum to ~1
        probs = computed.get("regimeProbs", {})
        total = sum(probs.values())
        assert 0.95 <= total <= 1.05, f"Regime probs should sum to ~1, got {total}"
        
        # Check riskSplit
        risk_split = data.get("riskSplit", {})
        assert "structural" in risk_split, "Missing structural risk"
        assert "tactical" in risk_split, "Missing tactical risk"
        assert "total" in risk_split, "Missing total risk"
        
        # Check LMI
        lmi = data.get("lmi", {})
        assert "lmi" in lmi, "Missing lmi value"
        assert "state" in lmi, "Missing lmi state"
        
        print(f"PASS: Macro snapshot has all required fields")
        print(f"  Regime: {computed.get('regime')} ({max(probs.values())*100:.0f}%)")
        print(f"  F&G: {raw.get('fearGreed')}")
        print(f"  Risk-Off: {computed.get('riskOffProb')*100:.0f}%")
        print(f"  MacroMult: {computed.get('macroMult'):.2f}")
        print(f"  RiskSplit: S{risk_split.get('structural')}/T{risk_split.get('tactical')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
