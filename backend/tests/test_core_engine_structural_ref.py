"""
Core Engine v2.2 - TF Tooltips & Structural Reference Tests

Tests for:
1. TF selector buttons (30m, 1H, 4H, 1D, 1W) work
2. structuralRef field presence/absence based on TF
3. structuralRef contains regime, risk, shift, blocked status
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestStructuralReference:
    """Tests for 4H structural reference feature"""
    
    def test_30m_has_structural_ref_with_4h_tf(self):
        """GET /api/core-engine/snapshot?tf=30m returns structuralRef with tf=4h"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=30m", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert data.get('meta', {}).get('tf') == '30m'
        
        # Verify structuralRef is present for 30m
        struct_ref = data.get('structuralRef')
        assert struct_ref is not None, "structuralRef should be present for tf=30m"
        assert struct_ref.get('tf') == '4h', "structuralRef.tf should be '4h'"
        
        # Verify structuralRef contains required fields
        assert 'regime' in struct_ref, "structuralRef should contain 'regime'"
        assert 'risk' in struct_ref, "structuralRef should contain 'risk'"
        assert 'shiftProbability' in struct_ref, "structuralRef should contain 'shiftProbability'"
        assert 'strongActionsBlocked' in struct_ref, "structuralRef should contain 'strongActionsBlocked'"
        assert 'riskLevel' in struct_ref, "structuralRef should contain 'riskLevel'"
        
        print(f"30m structuralRef: regime={struct_ref['regime']}, risk={struct_ref['risk']}, shift={struct_ref['shiftProbability']:.2f}")
    
    def test_1h_has_structural_ref_with_4h_tf(self):
        """GET /api/core-engine/snapshot?tf=1h returns structuralRef with tf=4h"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1h", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert data.get('meta', {}).get('tf') == '1h'
        
        # Verify structuralRef is present for 1h
        struct_ref = data.get('structuralRef')
        assert struct_ref is not None, "structuralRef should be present for tf=1h"
        assert struct_ref.get('tf') == '4h', "structuralRef.tf should be '4h'"
        
        # Verify structuralRef contains required fields
        assert 'regime' in struct_ref
        assert 'risk' in struct_ref
        assert 'shiftProbability' in struct_ref
        assert 'strongActionsBlocked' in struct_ref
        
        print(f"1h structuralRef: regime={struct_ref['regime']}, risk={struct_ref['risk']}, shift={struct_ref['shiftProbability']:.2f}")
    
    def test_4h_has_no_structural_ref(self):
        """GET /api/core-engine/snapshot?tf=4h returns structuralRef=null"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=4h", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert data.get('meta', {}).get('tf') == '4h'
        
        # Verify structuralRef is null for 4h
        struct_ref = data.get('structuralRef')
        assert struct_ref is None, "structuralRef should be null for tf=4h"
        print("4h correctly has no structuralRef")
    
    def test_1d_has_no_structural_ref(self):
        """GET /api/core-engine/snapshot?tf=1d returns structuralRef=null"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1d", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert data.get('meta', {}).get('tf') == '1d'
        
        # Verify structuralRef is null for 1d
        struct_ref = data.get('structuralRef')
        assert struct_ref is None, "structuralRef should be null for tf=1d"
        print("1d correctly has no structuralRef")
    
    def test_1w_has_no_structural_ref(self):
        """GET /api/core-engine/snapshot?tf=1w returns structuralRef=null"""
        response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1w", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        # Verify structuralRef is null for 1w
        struct_ref = data.get('structuralRef')
        assert struct_ref is None, "structuralRef should be null for tf=1w"
        print("1w correctly has no structuralRef")


class TestTFDifferentiation:
    """Tests verifying different TFs produce different KPI values"""
    
    def test_tf_produces_different_risk_values(self):
        """Different TFs should produce different risk values"""
        tfs = ['30m', '1h', '4h', '1d', '1w']
        risks = {}
        
        for tf in tfs:
            response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf={tf}", timeout=30)
            assert response.status_code == 200
            data = response.json()
            risks[tf] = data.get('risk', {}).get('totalIndex', 0)
        
        # Verify that we get different values (TFs should produce differentiated results)
        unique_risks = set(risks.values())
        assert len(unique_risks) > 1, f"Expected different risk values across TFs, got: {risks}"
        
        # Print for visibility
        for tf, risk in risks.items():
            print(f"TF={tf}: risk={risk}")
    
    def test_tf_produces_different_shift_values(self):
        """Different TFs should produce different shift probability values"""
        tfs = ['30m', '1h', '4h', '1d', '1w']
        shifts = {}
        
        for tf in tfs:
            response = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf={tf}", timeout=30)
            assert response.status_code == 200
            data = response.json()
            shifts[tf] = data.get('transition', {}).get('shiftProbability', 0)
        
        # Verify that we get different values
        unique_shifts = set(round(v, 2) for v in shifts.values())
        assert len(unique_shifts) > 1, f"Expected different shift values across TFs, got: {shifts}"
        
        # Print for visibility
        for tf, shift in shifts.items():
            print(f"TF={tf}: shift={shift:.2f}")


class TestStructuralRefContent:
    """Tests for structural reference content validation"""
    
    def test_structural_ref_regime_matches_4h_snapshot(self):
        """structuralRef regime should match standalone 4h snapshot regime"""
        # Get 1h snapshot with structuralRef
        response_1h = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=1h", timeout=30)
        assert response_1h.status_code == 200
        data_1h = response_1h.json()
        struct_ref = data_1h.get('structuralRef')
        
        # Get standalone 4h snapshot
        response_4h = requests.get(f"{BASE_URL}/api/core-engine/snapshot?tf=4h", timeout=30)
        assert response_4h.status_code == 200
        data_4h = response_4h.json()
        
        # Compare regime
        assert struct_ref is not None
        assert struct_ref.get('regime') == data_4h.get('regime', {}).get('dominant'), \
            "structuralRef regime should match 4h snapshot regime"
        
        print(f"structuralRef.regime={struct_ref.get('regime')}, 4h.regime={data_4h.get('regime', {}).get('dominant')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
