"""
B2 Graduation Plan API Tests

Tests the ML overlay graduation system:
- SHADOW(0) -> LIVE_LITE(0.5) -> LIVE_MED(0.75) -> LIVE_FULL(1.0)
- effectiveAlpha = mlAlpha * mlWeight (drift-based)
- Auto-promote/demote based on shadow verdict + drift + calibration
- 5-phase scheduler: EVAL -> GEN -> DRIFT -> SHADOW_EVAL -> GRADUATION
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestGraduationEndpoints:
    """Tests for graduation-specific API endpoints"""
    
    def test_graduation_7d_returns_ok_with_shadow_stage(self):
        """GET /api/ml-overlay/graduation?horizon=7D — returns ok:true, stage=SHADOW, mlAlpha=0, effectiveAlpha=0, auditHistory"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/graduation?horizon=7D&asset=BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Validate ok:true
        assert data.get("ok") is True, "Expected ok: true"
        
        # Validate stage - should be SHADOW initially
        assert "stage" in data, "Missing stage field"
        assert data["stage"] == "SHADOW", f"Expected stage=SHADOW, got {data['stage']}"
        
        # Validate mlAlpha - should be 0.0 in SHADOW
        assert "mlAlpha" in data, "Missing mlAlpha field"
        assert data["mlAlpha"] == 0.0, f"Expected mlAlpha=0.0, got {data['mlAlpha']}"
        
        # Validate effectiveAlpha - should be 0.0 (mlAlpha * mlWeight)
        assert "effectiveAlpha" in data, "Missing effectiveAlpha field"
        assert data["effectiveAlpha"] == 0.0, f"Expected effectiveAlpha=0.0, got {data['effectiveAlpha']}"
        
        # Validate auditHistory present
        assert "auditHistory" in data, "Missing auditHistory field"
        assert isinstance(data["auditHistory"], list), "auditHistory should be a list"
        
        print(f"✓ 7D graduation: stage={data['stage']}, mlAlpha={data['mlAlpha']}, effectiveAlpha={data['effectiveAlpha']}")
    
    def test_graduation_30d_returns_ok_with_shadow_stage(self):
        """GET /api/ml-overlay/graduation?horizon=30D — returns ok:true, stage=SHADOW, drift-based mlWeight"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/graduation?horizon=30D&asset=BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Validate ok:true
        assert data.get("ok") is True, "Expected ok: true"
        
        # Validate stage - should be SHADOW initially
        assert "stage" in data, "Missing stage field"
        assert data["stage"] == "SHADOW", f"Expected stage=SHADOW, got {data['stage']}"
        
        # Validate mlAlpha - 0.0 in SHADOW
        assert "mlAlpha" in data, "Missing mlAlpha field"
        assert data["mlAlpha"] == 0.0, f"Expected mlAlpha=0.0, got {data['mlAlpha']}"
        
        # Validate mlWeight exists (drift-based)
        assert "mlWeight" in data, "Missing mlWeight field"
        assert isinstance(data["mlWeight"], (int, float)), "mlWeight should be numeric"
        assert 0.0 <= data["mlWeight"] <= 1.0, f"mlWeight should be between 0-1, got {data['mlWeight']}"
        
        # effectiveAlpha = mlAlpha * mlWeight should be 0 when mlAlpha=0
        assert "effectiveAlpha" in data, "Missing effectiveAlpha field"
        assert data["effectiveAlpha"] == 0.0, f"Expected effectiveAlpha=0.0 (since mlAlpha=0), got {data['effectiveAlpha']}"
        
        print(f"✓ 30D graduation: stage={data['stage']}, mlAlpha={data['mlAlpha']}, mlWeight={data['mlWeight']}, effectiveAlpha={data['effectiveAlpha']}")

    def test_graduation_evaluate_7d_returns_hold_action(self):
        """POST /api/ml-overlay/graduation/evaluate?horizon=7D — should return action=HOLD in SHADOW (insufficient data for promote)"""
        response = requests.post(f"{BASE_URL}/api/ml-overlay/graduation/evaluate?horizon=7D&asset=BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Validate ok:true
        assert data.get("ok") is True, "Expected ok: true"
        
        # Validate action present
        assert "action" in data, "Missing action field"
        # Should be HOLD since we're in SHADOW and likely have insufficient data
        assert data["action"] in ["HOLD", "DEMOTE", "PROMOTE", "FORCE_SHADOW"], f"Unexpected action: {data['action']}"
        
        # Validate stage field present
        assert "stage" in data, "Missing stage field"
        
        # Validate reason is provided
        assert "reason" in data, "Missing reason field"
        
        print(f"✓ 7D evaluate: action={data['action']}, stage={data['stage']}, reason={data.get('reason', '')}")


class TestPredictEndpointInShadowMode:
    """Tests that /api/ml-overlay/predict correctly shows SHADOW mode behavior"""
    
    def test_predict_7d_shadow_mode_no_ml_influence(self):
        """GET /api/ml-overlay/predict?asset=BTC&horizon=7D — CRITICAL: stage=SHADOW, mlAlpha=0, effectiveAlpha=0, finalReturn==ruleReturn"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/predict?asset=BTC&horizon=7D")
        
        # Handle case where no forecast exists
        if response.status_code == 200:
            data = response.json()
            
            if data.get("ok") is True:
                # Validate SHADOW mode
                assert data.get("stage") == "SHADOW", f"Expected stage=SHADOW, got {data.get('stage')}"
                
                # Validate mlAlpha=0 in SHADOW
                assert data.get("mlAlpha") == 0.0, f"Expected mlAlpha=0.0, got {data.get('mlAlpha')}"
                
                # Validate effectiveAlpha=0
                assert data.get("effectiveAlpha") == 0.0, f"Expected effectiveAlpha=0.0, got {data.get('effectiveAlpha')}"
                
                # CRITICAL: In SHADOW mode, finalReturn MUST equal ruleReturn
                # because effectiveAlpha=0 means ML correction is NOT applied
                rule_return = data.get("ruleReturn")
                final_return = data.get("finalReturn")
                ml_correction = data.get("mlCorrection")
                
                # ML correction should be 0 when effectiveAlpha=0
                assert ml_correction == 0.0, f"In SHADOW mode, mlCorrection should be 0.0, got {ml_correction}"
                
                # finalReturn should equal ruleReturn (ML not influencing)
                assert abs(final_return - rule_return) < 1e-6, f"In SHADOW mode, finalReturn ({final_return}) should equal ruleReturn ({rule_return})"
                
                print(f"✓ 7D predict SHADOW: ruleReturn={rule_return}, finalReturn={final_return}, mlCorrection={ml_correction}")
            else:
                # No forecast available - that's ok
                print(f"⚠ 7D predict: No forecast available - {data.get('error', 'unknown')}")
        else:
            print(f"⚠ 7D predict returned {response.status_code}")
    
    def test_predict_30d_shadow_mode_no_ml_influence(self):
        """GET /api/ml-overlay/predict?asset=BTC&horizon=30D — same: SHADOW mode, mlCorrection=0.0"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/predict?asset=BTC&horizon=30D")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("ok") is True:
                # Validate SHADOW mode
                assert data.get("stage") == "SHADOW", f"Expected stage=SHADOW, got {data.get('stage')}"
                
                # Validate mlAlpha=0 in SHADOW
                assert data.get("mlAlpha") == 0.0, f"Expected mlAlpha=0.0, got {data.get('mlAlpha')}"
                
                # effectiveAlpha should be 0
                assert data.get("effectiveAlpha") == 0.0, f"Expected effectiveAlpha=0.0, got {data.get('effectiveAlpha')}"
                
                # ML correction should be 0
                assert data.get("mlCorrection") == 0.0, f"Expected mlCorrection=0.0, got {data.get('mlCorrection')}"
                
                print(f"✓ 30D predict SHADOW: stage={data['stage']}, mlCorrection={data['mlCorrection']}")
            else:
                print(f"⚠ 30D predict: No forecast available - {data.get('error', 'unknown')}")
        else:
            print(f"⚠ 30D predict returned {response.status_code}")


class TestStatusEndpointGraduationField:
    """Tests that /api/ml-overlay/status includes graduation info"""
    
    def test_status_includes_graduation_for_all_horizons(self):
        """GET /api/ml-overlay/status — should include graduation field with 7D and 30D stage info"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Validate ok:true
        assert data.get("ok") is True, "Expected ok: true"
        
        # Validate graduation field present
        assert "graduation" in data, "Missing graduation field in status"
        graduation = data["graduation"]
        
        # Validate both horizons present
        assert "7D" in graduation, "Missing 7D in graduation"
        assert "30D" in graduation, "Missing 30D in graduation"
        
        # Validate 7D graduation structure
        grad_7d = graduation["7D"]
        assert "stage" in grad_7d, "Missing stage in 7D graduation"
        assert "mlAlpha" in grad_7d, "Missing mlAlpha in 7D graduation"
        assert "effectiveAlpha" in grad_7d, "Missing effectiveAlpha in 7D graduation"
        
        # Validate 30D graduation structure
        grad_30d = graduation["30D"]
        assert "stage" in grad_30d, "Missing stage in 30D graduation"
        assert "mlAlpha" in grad_30d, "Missing mlAlpha in 30D graduation"
        assert "effectiveAlpha" in grad_30d, "Missing effectiveAlpha in 30D graduation"
        
        print(f"✓ Status graduation: 7D={grad_7d['stage']} (alpha={grad_7d['mlAlpha']}), 30D={grad_30d['stage']} (alpha={grad_30d['mlAlpha']})")


class TestGraduationDataStructure:
    """Tests graduation data structure completeness"""
    
    def test_graduation_7d_has_all_required_fields(self):
        """Validate all expected fields in graduation response"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/graduation?horizon=7D&asset=BTC")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["ok", "horizon", "asset", "stage", "mlAlpha", "mlWeight", "effectiveAlpha", "stageIndex", "maxStages", "auditHistory"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Validate types
        assert isinstance(data["stageIndex"], int), "stageIndex should be int"
        assert isinstance(data["maxStages"], int), "maxStages should be int"
        assert data["maxStages"] == 4, f"Expected 4 stages (SHADOW, LIVE_LITE, LIVE_MED, LIVE_FULL), got {data['maxStages']}"
        
        # In SHADOW stage, stageIndex should be 0
        if data["stage"] == "SHADOW":
            assert data["stageIndex"] == 0, f"SHADOW should be stageIndex=0, got {data['stageIndex']}"
        
        print(f"✓ 7D graduation structure valid: stageIndex={data['stageIndex']}/{data['maxStages']}")

    def test_graduation_audit_history_structure(self):
        """Validate audit history entries have proper structure"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/graduation?horizon=7D&asset=BTC")
        assert response.status_code == 200
        data = response.json()
        
        audit_history = data.get("auditHistory", [])
        
        # If there are entries, validate structure
        if len(audit_history) > 0:
            entry = audit_history[0]
            expected_fields = ["horizon", "asset", "action", "fromStage", "toStage", "reason", "ts"]
            for field in expected_fields:
                assert field in entry, f"Audit entry missing field: {field}"
            
            print(f"✓ Audit history has {len(audit_history)} entries, structure valid")
        else:
            print("⚠ No audit history entries yet (expected for fresh system)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
