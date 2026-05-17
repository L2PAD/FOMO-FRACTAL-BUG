"""
Blocks 8-11 Implementation Tests
================================

Block 8: Horizon Switch Logic (decoupled Chart range from Forecast horizon)
Block 9: Outcome Markers enhanced (TP/FP tooltips with expected/actual/confidence)
Block 10: Confidence Band Refinement (volatility + health calibration factors)
Block 11: Multi-Horizon Visual Cohesion (horizon badges, timeline indicators)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')

class TestBlock8HorizonSwitchDecoupling:
    """Block 8: Verify chart range is decoupled from forecast horizon"""
    
    def test_horizon_1d_with_range_7d(self):
        """Test 1D horizon with default 7d chart range"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
            "asset": "BTC",
            "range": "7d",
            "horizon": "1D"
        }, timeout=90)
        
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        # Verify decoupling - range and horizon are independent
        assert data['range'] == '7d'
        assert data['horizon'] == '1D'
        assert data['forecastOverlay']['horizon'] == '1D'
        print(f"✅ Block 8: range={data['range']}, horizon={data['horizon']} - Decoupled correctly")
    
    def test_horizon_7d_with_range_7d(self):
        """Test 7D horizon with 7d chart range"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
            "asset": "BTC",
            "range": "7d",
            "horizon": "7D"
        }, timeout=90)
        
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        assert data['range'] == '7d'
        assert data['horizon'] == '7D'
        assert data['forecastOverlay']['horizon'] == '7D'
        print(f"✅ Block 8: 7D horizon with 7d chart - Independent selection works")
    
    def test_horizon_30d_with_range_24h(self):
        """Test 30D horizon with 24h chart range (completely different)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
            "asset": "BTC",
            "range": "24h",
            "horizon": "30D"
        }, timeout=90)
        
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        # Chart shows 24h of data, but forecast is for 30D
        assert data['range'] == '24h'
        assert data['horizon'] == '30D'
        assert data['forecastOverlay']['horizon'] == '30D'
        print(f"✅ Block 8: 30D forecast on 24h chart - Maximum decoupling verified")


class TestBlock9OutcomeMarkersTooltip:
    """Block 9: Verify outcome markers have enhanced tooltip data"""
    
    def test_outcome_markers_have_required_fields(self):
        """Verify outcomeMarkers contain expected, actual, confidence for tooltips"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
            "asset": "BTC",
            "range": "7d",
            "horizon": "1D"
        }, timeout=90)
        
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        markers = data.get('outcomeMarkers', [])
        
        # Markers may be empty if no evaluated forecasts yet
        if len(markers) > 0:
            for marker in markers:
                # Block 9: Each marker should have expected, actual, confidence
                assert 'expectedMovePct' in marker, "Missing expectedMovePct in marker"
                assert 'actualMovePct' in marker, "Missing actualMovePct in marker"
                assert 'confidence' in marker, "Missing confidence in marker"
                assert 'label' in marker, "Missing label in marker"
                assert marker['label'] in ['TP', 'FP', 'FN', 'WEAK'], f"Invalid label: {marker['label']}"
                
            print(f"✅ Block 9: {len(markers)} outcome markers have expected/actual/confidence fields")
            print(f"   Sample marker: label={markers[0]['label']}, expected={markers[0]['expectedMovePct']:.1f}%, actual={markers[0]['actualMovePct']:.1f}%, conf={markers[0]['confidence']}")
        else:
            print("⚠️ Block 9: No outcome markers available (no evaluated forecasts yet)")


class TestBlock10ConfidenceBandRefinement:
    """Block 10: Verify forecastOverlay contains volatility and health factors"""
    
    def test_forecast_overlay_has_volatility(self):
        """Verify forecastOverlay includes volatility field"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
            "asset": "BTC",
            "range": "7d",
            "horizon": "1D"
        }, timeout=90)
        
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        overlay = data['forecastOverlay']
        
        # Block 10: Required volatility field
        assert 'volatility' in overlay, "Missing volatility in forecastOverlay"
        assert isinstance(overlay['volatility'], (int, float)), "volatility should be numeric"
        assert overlay['volatility'] >= 0, "volatility should be non-negative"
        
        print(f"✅ Block 10: forecastOverlay.volatility = {overlay['volatility']:.4f} ({overlay['volatility']*100:.2f}%)")
    
    def test_forecast_overlay_has_health_state(self):
        """Verify forecastOverlay includes healthState field"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
            "asset": "BTC",
            "range": "7d",
            "horizon": "1D"
        }, timeout=90)
        
        assert response.status_code == 200
        data = response.json()
        overlay = data['forecastOverlay']
        
        # Block 10: Required health fields
        assert 'healthState' in overlay, "Missing healthState in forecastOverlay"
        assert overlay['healthState'] in ['HEALTHY', 'DEGRADED', 'CRITICAL'], f"Invalid healthState: {overlay['healthState']}"
        
        print(f"✅ Block 10: forecastOverlay.healthState = {overlay['healthState']}")
    
    def test_forecast_overlay_has_health_modifier(self):
        """Verify forecastOverlay includes healthModifier field"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
            "asset": "BTC",
            "range": "7d",
            "horizon": "1D"
        }, timeout=90)
        
        assert response.status_code == 200
        data = response.json()
        overlay = data['forecastOverlay']
        
        # Block 10: Health modifier for band width calculation
        assert 'healthModifier' in overlay, "Missing healthModifier in forecastOverlay"
        assert isinstance(overlay['healthModifier'], (int, float)), "healthModifier should be numeric"
        assert 0 <= overlay['healthModifier'] <= 1, f"healthModifier should be 0-1, got {overlay['healthModifier']}"
        
        print(f"✅ Block 10: forecastOverlay.healthModifier = {overlay['healthModifier']}")
    
    def test_forecast_overlay_has_band_width_factors(self):
        """Verify forecastOverlay includes bandWidthFactors for refined calculation"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
            "asset": "BTC",
            "range": "7d",
            "horizon": "1D"
        }, timeout=90)
        
        assert response.status_code == 200
        data = response.json()
        overlay = data['forecastOverlay']
        
        # Block 10: Band width factors breakdown
        assert 'bandWidthFactors' in overlay, "Missing bandWidthFactors in forecastOverlay"
        factors = overlay['bandWidthFactors']
        
        assert 'baseWidth' in factors, "Missing baseWidth in bandWidthFactors"
        assert 'volatilityContribution' in factors, "Missing volatilityContribution in bandWidthFactors"
        assert 'uncertaintyContribution' in factors, "Missing uncertaintyContribution in bandWidthFactors"
        
        print(f"✅ Block 10: bandWidthFactors present:")
        print(f"   baseWidth: ${factors['baseWidth']:.2f}")
        print(f"   volatilityContribution: ${factors['volatilityContribution']:.2f}")
        print(f"   uncertaintyContribution: ${factors['uncertaintyContribution']:.2f}")


class TestBlock11MultiHorizonVisualCohesion:
    """Block 11: Verify horizon badges and timeline indicators"""
    
    def test_forecast_overlay_has_horizon_field(self):
        """Verify forecastOverlay includes horizon for badge rendering"""
        for horizon in ['1D', '7D', '30D']:
            response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
                "asset": "BTC",
                "range": "7d",
                "horizon": horizon
            }, timeout=90)
            
            assert response.status_code == 200
            data = response.json()
            overlay = data['forecastOverlay']
            
            # Block 11: Horizon field for badge
            assert 'horizon' in overlay, "Missing horizon in forecastOverlay"
            assert overlay['horizon'] == horizon, f"Expected horizon={horizon}, got {overlay['horizon']}"
            
            print(f"✅ Block 11: {horizon} horizon badge data present")
    
    def test_forecast_overlay_has_timestamps_for_timeline(self):
        """Verify forecastOverlay has fromTs and toTs for timeline indicator"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
            "asset": "BTC",
            "range": "7d",
            "horizon": "1D"
        }, timeout=90)
        
        assert response.status_code == 200
        data = response.json()
        overlay = data['forecastOverlay']
        
        # Block 11: Timeline indicator requires timestamps
        assert 'fromTs' in overlay, "Missing fromTs for timeline indicator"
        assert 'toTs' in overlay, "Missing toTs for timeline indicator"
        
        # Calculate time delta for timeline label (+Xd or +Xh)
        from_ts = overlay['fromTs']
        to_ts = overlay['toTs']
        delta_ms = to_ts - from_ts
        delta_hours = delta_ms / (60 * 60 * 1000)
        delta_days = delta_hours / 24
        
        print(f"✅ Block 11: Timeline indicator data:")
        print(f"   fromTs: {from_ts}")
        print(f"   toTs: {to_ts}")
        print(f"   Delta: {delta_hours:.0f}h ({delta_days:.1f}d)")
        print(f"   Label would be: +{int(delta_days)}d" if delta_days >= 1 else f"   Label would be: +{int(delta_hours)}h")
    
    def test_horizon_timestamps_correspond_to_horizon(self):
        """Verify toTs - fromTs matches the selected horizon"""
        horizons_expected_hours = {
            '1D': 24,
            '7D': 7 * 24,
            '30D': 30 * 24
        }
        
        for horizon, expected_hours in horizons_expected_hours.items():
            response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
                "asset": "BTC",
                "range": "7d",
                "horizon": horizon
            }, timeout=90)
            
            assert response.status_code == 200
            data = response.json()
            overlay = data['forecastOverlay']
            
            delta_ms = overlay['toTs'] - overlay['fromTs']
            delta_hours = delta_ms / (60 * 60 * 1000)
            
            # Allow 5% tolerance for timing differences
            tolerance = expected_hours * 0.05
            assert abs(delta_hours - expected_hours) < tolerance, \
                f"Horizon {horizon}: expected ~{expected_hours}h, got {delta_hours:.1f}h"
            
            print(f"✅ Block 11: {horizon} horizon = {delta_hours:.0f}h (expected ~{expected_hours}h)")


class TestIntegration:
    """Integration tests for all blocks together"""
    
    def test_full_response_structure(self):
        """Verify complete API response has all Block 8-11 features"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v3", params={
            "asset": "BTC",
            "range": "7d",
            "horizon": "1D"
        }, timeout=90)
        
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        # Block 8: Decoupled range/horizon
        assert 'range' in data
        assert 'horizon' in data
        
        # Block 9: Outcome markers
        assert 'outcomeMarkers' in data
        
        # Block 10 & 11: Enhanced forecastOverlay
        overlay = data['forecastOverlay']
        required_fields = [
            'horizon', 'volatility', 'healthState', 'healthModifier', 
            'bandWidthFactors', 'fromTs', 'toTs', 'confidence', 
            'targetPrice', 'direction', 'action'
        ]
        
        for field in required_fields:
            assert field in overlay, f"Missing {field} in forecastOverlay"
        
        print("✅ Integration: All Block 8-11 features present in API response")
        print(f"   Block 8: range={data['range']}, horizon={data['horizon']}")
        print(f"   Block 9: {len(data['outcomeMarkers'])} outcome markers")
        print(f"   Block 10: volatility={overlay['volatility']:.4f}, healthState={overlay['healthState']}")
        print(f"   Block 11: horizon={overlay['horizon']}, toTs-fromTs={overlay['toTs']-overlay['fromTs']}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
