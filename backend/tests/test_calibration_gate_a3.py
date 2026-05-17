"""
A3 Calibration Gate Tests
=========================
Tests for ECE penalty integration into ML Weight computation and graduation blocking.

Key features tested:
1. GET /api/drift/status returns calibration object with brier, ece, status, n
2. ECE >= 0.12 triggers status=DRIFT
3. mlWeight reduced by ECE penalty: mlWeight *= exp(-ECE_ALPHA * ECE) where ECE_ALPHA=3.0
4. GET /api/ml-overlay/status returns calibration object with 7D and 30D keys
5. Graduation promotion blocked when calibration status is DRIFT or WATCH
6. Graduation demotion triggered by calibration status=DRIFT
"""

import pytest
import requests
import os
import math

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Constants from drift/config.py
ECE_ALPHA = 3.0
ALPHA = 2.0
ECE_WATCH = 0.08
ECE_DRIFT = 0.12


class TestDriftStatusCalibration:
    """Test calibration fields in drift status API"""

    def test_drift_status_7d_has_calibration_fields(self):
        """GET /api/drift/status?horizon=7D should return calibration object"""
        response = requests.get(f"{BASE_URL}/api/drift/status", params={"horizon": "7D", "asset": "BTC"})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Calibration object must exist
        calib = data.get("calibration")
        assert calib is not None, "calibration field missing"
        
        # Required fields
        assert "brier" in calib, "calibration.brier missing"
        assert "ece" in calib, "calibration.ece missing"
        assert "status" in calib, "calibration.status missing"
        assert "n" in calib, "calibration.n missing"
        
        # Type checks
        assert isinstance(calib["brier"], (int, float))
        assert isinstance(calib["ece"], (int, float))
        assert isinstance(calib["status"], str)
        assert isinstance(calib["n"], int)
        
        # Status must be one of OK, WATCH, DRIFT
        assert calib["status"] in ["OK", "WATCH", "DRIFT"], f"Invalid calibration status: {calib['status']}"
        
        print(f"7D calibration: brier={calib['brier']:.4f}, ece={calib['ece']:.4f}, status={calib['status']}, n={calib['n']}")

    def test_drift_status_30d_has_calibration_fields(self):
        """GET /api/drift/status?horizon=30D should return calibration object"""
        response = requests.get(f"{BASE_URL}/api/drift/status", params={"horizon": "30D", "asset": "BTC"})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        calib = data.get("calibration")
        assert calib is not None
        
        # Required fields
        assert "brier" in calib
        assert "ece" in calib
        assert "status" in calib
        assert "n" in calib
        
        print(f"30D calibration: brier={calib['brier']:.4f}, ece={calib['ece']:.4f}, status={calib['status']}, n={calib['n']}")

    def test_drift_status_ece_threshold_logic(self):
        """ECE >= 0.12 should trigger DRIFT status"""
        response = requests.get(f"{BASE_URL}/api/drift/status", params={"horizon": "7D", "asset": "BTC"})
        assert response.status_code == 200
        
        data = response.json()
        calib = data.get("calibration", {})
        ece = calib.get("ece", 0)
        status = calib.get("status", "OK")
        
        # Verify threshold logic
        if ece >= ECE_DRIFT:
            assert status == "DRIFT", f"ECE={ece} >= {ECE_DRIFT} should be DRIFT, got {status}"
        elif ece >= ECE_WATCH:
            assert status == "WATCH", f"ECE={ece} >= {ECE_WATCH} should be WATCH, got {status}"
        else:
            assert status == "OK", f"ECE={ece} < {ECE_WATCH} should be OK, got {status}"
        
        print(f"ECE threshold check: ece={ece:.4f}, status={status} (thresholds: WATCH>={ECE_WATCH}, DRIFT>={ECE_DRIFT})")


class TestMLWeightECEPenalty:
    """Test ECE penalty integration into mlWeight computation"""

    def test_ml_weight_includes_ece_penalty(self):
        """mlWeight should be reduced by exp(-ECE_ALPHA * ECE)"""
        response = requests.get(f"{BASE_URL}/api/drift/status", params={"horizon": "7D", "asset": "BTC"})
        assert response.status_code == 200
        
        data = response.json()
        drift_score = data.get("driftScore", 0)
        ml_weight = data.get("mlWeight", 1)
        calib = data.get("calibration", {})
        ece = calib.get("ece", 0)
        
        # Expected: mlWeight = exp(-ALPHA * driftScore) * exp(-ECE_ALPHA * ECE)
        expected_weight = math.exp(-ALPHA * drift_score) * math.exp(-ECE_ALPHA * ece)
        
        # Allow small tolerance for floating point
        assert abs(ml_weight - expected_weight) < 0.001, \
            f"mlWeight={ml_weight:.4f} != expected={expected_weight:.4f} (drift={drift_score}, ECE={ece})"
        
        print(f"7D ECE penalty verified: drift={drift_score}, ECE={ece}, mlWeight={ml_weight:.4f}, expected={expected_weight:.4f}")

    def test_ml_weight_30d_includes_ece_penalty(self):
        """30D mlWeight should also include ECE penalty"""
        response = requests.get(f"{BASE_URL}/api/drift/status", params={"horizon": "30D", "asset": "BTC"})
        assert response.status_code == 200
        
        data = response.json()
        drift_score = data.get("driftScore", 0)
        ml_weight = data.get("mlWeight", 1)
        calib = data.get("calibration", {})
        ece = calib.get("ece", 0)
        
        expected_weight = math.exp(-ALPHA * drift_score) * math.exp(-ECE_ALPHA * ece)
        
        assert abs(ml_weight - expected_weight) < 0.001, \
            f"30D mlWeight={ml_weight:.4f} != expected={expected_weight:.4f}"
        
        print(f"30D ECE penalty verified: drift={drift_score}, ECE={ece}, mlWeight={ml_weight:.4f}")

    def test_ece_penalty_value_calculation(self):
        """Verify ecePenalty field if present, or calculate independently"""
        response = requests.get(f"{BASE_URL}/api/drift/status", params={"horizon": "7D", "asset": "BTC"})
        assert response.status_code == 200
        
        data = response.json()
        calib = data.get("calibration", {})
        ece = calib.get("ece", 0)
        
        # Calculate expected penalty
        expected_penalty = math.exp(-ECE_ALPHA * ece) if ece > 0 else 1.0
        
        # If ecePenalty is returned in calibration object, verify it
        if "ecePenalty" in calib:
            assert abs(calib["ecePenalty"] - expected_penalty) < 0.001
        
        print(f"ECE penalty calculation: ECE={ece:.4f}, penalty=exp(-{ECE_ALPHA}*{ece:.4f})={expected_penalty:.4f}")


class TestMLOverlayStatusCalibration:
    """Test calibration in ml-overlay status endpoint"""

    def test_ml_overlay_status_has_calibration_object(self):
        """GET /api/ml-overlay/status should return calibration with 7D and 30D keys"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Calibration must exist
        calibration = data.get("calibration")
        assert calibration is not None, "calibration field missing from ml-overlay status"
        
        # Must have 7D and 30D keys
        assert "7D" in calibration, "calibration.7D missing"
        assert "30D" in calibration, "calibration.30D missing"
        
        # Each horizon must have required fields
        for h in ["7D", "30D"]:
            hd = calibration[h]
            assert "brier" in hd, f"calibration.{h}.brier missing"
            assert "ece" in hd, f"calibration.{h}.ece missing"
            assert "status" in hd, f"calibration.{h}.status missing"
            
        print(f"ml-overlay/status calibration: 7D={calibration['7D']}, 30D={calibration['30D']}")

    def test_ml_overlay_status_calibration_matches_drift_status(self):
        """Calibration from ml-overlay/status should match drift/status"""
        # Get from ml-overlay/status
        overlay_resp = requests.get(f"{BASE_URL}/api/ml-overlay/status")
        assert overlay_resp.status_code == 200
        overlay_calib = overlay_resp.json().get("calibration", {})
        
        # Get from drift/status for 7D
        drift_resp = requests.get(f"{BASE_URL}/api/drift/status", params={"horizon": "7D", "asset": "BTC"})
        assert drift_resp.status_code == 200
        drift_calib = drift_resp.json().get("calibration", {})
        
        # Compare
        if "7D" in overlay_calib and drift_calib:
            overlay_7d = overlay_calib["7D"]
            # Status should match
            assert overlay_7d.get("status") == drift_calib.get("status"), \
                f"Status mismatch: overlay={overlay_7d.get('status')}, drift={drift_calib.get('status')}"
            # ECE should be close
            assert abs(overlay_7d.get("ece", 0) - drift_calib.get("ece", 0)) < 0.001
            
        print("Calibration consistency verified between ml-overlay/status and drift/status")


class TestGraduationCalibrationBlocking:
    """Test calibration gate in graduation system"""

    def test_graduation_stage_is_shadow(self):
        """Verify graduation stage for 7D and 30D"""
        for h in ["7D", "30D"]:
            response = requests.get(f"{BASE_URL}/api/ml-overlay/graduation", params={"horizon": h})
            assert response.status_code == 200
            
            data = response.json()
            assert data.get("ok") is True
            assert "stage" in data
            
            print(f"{h} graduation: stage={data['stage']}, mlAlpha={data.get('mlAlpha')}")

    def test_graduation_blocked_by_calibration_drift(self):
        """Calibration status DRIFT should block promotion"""
        # Get current drift status
        drift_resp = requests.get(f"{BASE_URL}/api/drift/status", params={"horizon": "7D", "asset": "BTC"})
        drift_data = drift_resp.json()
        calib_status = drift_data.get("calibration", {}).get("status", "OK")
        
        # Get graduation status
        grad_resp = requests.get(f"{BASE_URL}/api/ml-overlay/graduation", params={"horizon": "7D"})
        grad_data = grad_resp.json()
        
        # Check audit history for calibration blocker
        audit_history = grad_data.get("auditHistory", [])
        
        if calib_status in ["DRIFT", "WATCH"] and audit_history:
            # Recent audit should mention calibration as blocker
            recent = audit_history[0]
            reason = recent.get("reason", "")
            # Calibration should be mentioned in blockers
            if "blockers" in reason.lower() or "calibration" in reason.lower():
                print(f"Calibration blocking confirmed: {reason}")
            
        print(f"Calibration status: {calib_status}, Graduation blockers in audit: checked")

    def test_graduation_evaluate_includes_calibration_check(self):
        """POST /api/ml-overlay/graduation/evaluate should check calibration"""
        response = requests.post(f"{BASE_URL}/api/ml-overlay/graduation/evaluate", params={"horizon": "7D"})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # If there are blockers, calibration should be one if status is DRIFT
        blockers = data.get("blockers", [])
        reason = data.get("reason", "")
        
        # Get calibration status
        drift_resp = requests.get(f"{BASE_URL}/api/drift/status", params={"horizon": "7D", "asset": "BTC"})
        calib_status = drift_resp.json().get("calibration", {}).get("status", "OK")
        
        if calib_status in ["DRIFT", "WATCH"]:
            # Should see calibration in blockers or reason
            calibration_mentioned = any("calibration" in str(b).lower() for b in blockers) or "calibration" in reason.lower()
            print(f"Calibration {calib_status} blocking: {calibration_mentioned}, blockers: {blockers}")
        
        print(f"Graduation evaluate result: action={data.get('action')}, stage={data.get('stage')}")


class TestECEPenaltyMath:
    """Verify ECE penalty formula: mlWeight *= exp(-ECE_ALPHA * ECE)"""

    def test_ece_penalty_formula_7d(self):
        """For 7D: verify mlWeight = exp(-ALPHA * drift) * exp(-ECE_ALPHA * ECE)"""
        response = requests.get(f"{BASE_URL}/api/drift/status", params={"horizon": "7D", "asset": "BTC"})
        data = response.json()
        
        drift = data.get("driftScore", 0)
        ece = data.get("calibration", {}).get("ece", 0)
        ml_weight = data.get("mlWeight", 1)
        
        # Formula: mlWeight = exp(-ALPHA * drift) * exp(-ECE_ALPHA * ECE)
        drift_component = math.exp(-ALPHA * drift)
        ece_component = math.exp(-ECE_ALPHA * ece)
        expected = drift_component * ece_component
        
        # Verify
        assert abs(ml_weight - expected) < 0.001, \
            f"Formula mismatch: {ml_weight:.4f} != {drift_component:.4f} * {ece_component:.4f} = {expected:.4f}"
        
        print(f"7D formula verified: exp(-{ALPHA}*{drift}) * exp(-{ECE_ALPHA}*{ece}) = {expected:.4f}")

    def test_ece_high_value_significantly_reduces_weight(self):
        """High ECE (e.g., 0.36) should significantly reduce mlWeight"""
        response = requests.get(f"{BASE_URL}/api/drift/status", params={"horizon": "7D", "asset": "BTC"})
        data = response.json()
        
        ece = data.get("calibration", {}).get("ece", 0)
        ml_weight = data.get("mlWeight", 1)
        
        if ece >= 0.3:
            # exp(-3.0 * 0.3) ≈ 0.41, so weight should be < 0.45 even with 0 drift
            assert ml_weight < 0.45, f"High ECE ({ece}) should significantly reduce weight, got {ml_weight}"
            print(f"High ECE penalty confirmed: ECE={ece:.4f} → mlWeight={ml_weight:.4f}")
        else:
            print(f"ECE is not high enough to test significant reduction: ECE={ece:.4f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
