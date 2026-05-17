"""
Meta-Aware Forecast Integration Tests (P0)
==========================================

Tests the Meta-Brain risk adjustment layer integration into the forecast endpoint.
This is a P0 (critical) feature that ensures:
- UI shows FINAL, risk-adjusted predictions (not raw exchange model output)
- metaForecast object contains all required fields
- Risk badges, confidence reduction, and applied overlays are displayed

Endpoint: GET /api/market/chart/price-vs-expectation-v2
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestMetaAwareForecastEndpoint:
    """Tests for the /api/market/chart/price-vs-expectation-v2 endpoint with Meta-Brain integration"""
    
    def test_endpoint_returns_ok(self):
        """Test that the endpoint returns successfully"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print("✅ Endpoint returns OK status")
    
    def test_metaforecast_object_present(self):
        """Test that metaForecast object is included in the response"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        
        # Note: metaForecast is only present when there's a pending forecast
        if data.get('layers', {}).get('meta', {}).get('futurePoint'):
            assert 'metaForecast' in data, "metaForecast should be present when there's a pending forecast"
            print("✅ metaForecast object present in response")
        else:
            pytest.skip("No pending forecast available to test metaForecast")
    
    def test_metaforecast_raw_values(self):
        """Test that metaForecast contains raw (original) values"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        
        meta = data.get('metaForecast')
        if not meta:
            pytest.skip("No metaForecast available")
        
        raw = meta.get('raw', {})
        assert 'direction' in raw, "raw.direction should be present"
        assert 'confidence' in raw, "raw.confidence should be present"
        assert 'expectedMovePct' in raw, "raw.expectedMovePct should be present"
        
        # Validate data types
        assert isinstance(raw['confidence'], (int, float))
        assert raw['confidence'] >= 0 and raw['confidence'] <= 1
        assert raw['direction'] in ['UP', 'DOWN', 'FLAT']
        
        print(f"✅ raw values: direction={raw['direction']}, confidence={raw['confidence']}, expectedMovePct={raw['expectedMovePct']}")
    
    def test_metaforecast_adjusted_values(self):
        """Test that metaForecast contains risk-adjusted values"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        
        meta = data.get('metaForecast')
        if not meta:
            pytest.skip("No metaForecast available")
        
        # Check all required adjusted fields
        assert 'direction' in meta, "direction should be present"
        assert 'confidence' in meta, "confidence should be present"
        assert 'expectedMovePct' in meta, "expectedMovePct should be present"
        
        # Validate data types
        assert isinstance(meta['confidence'], (int, float))
        assert meta['confidence'] >= 0 and meta['confidence'] <= 1
        
        print(f"✅ adjusted values: direction={meta['direction']}, confidence={meta['confidence']}, expectedMovePct={meta['expectedMovePct']}")
    
    def test_metaforecast_action_field(self):
        """Test that metaForecast contains action field (BUY/SELL/AVOID)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        
        meta = data.get('metaForecast')
        if not meta:
            pytest.skip("No metaForecast available")
        
        assert 'action' in meta, "action should be present"
        assert meta['action'] in ['BUY', 'SELL', 'AVOID'], f"action should be BUY/SELL/AVOID, got: {meta['action']}"
        
        print(f"✅ action field: {meta['action']}")
    
    def test_metaforecast_risk_level(self):
        """Test that metaForecast contains riskLevel field"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        
        meta = data.get('metaForecast')
        if not meta:
            pytest.skip("No metaForecast available")
        
        assert 'riskLevel' in meta, "riskLevel should be present"
        assert meta['riskLevel'] in ['LOW', 'MEDIUM', 'HIGH', 'EXTREME'], f"riskLevel should be LOW/MEDIUM/HIGH/EXTREME, got: {meta['riskLevel']}"
        
        print(f"✅ riskLevel field: {meta['riskLevel']}")
    
    def test_metaforecast_applied_overlays(self):
        """Test that metaForecast contains appliedOverlays array"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        
        meta = data.get('metaForecast')
        if not meta:
            pytest.skip("No metaForecast available")
        
        assert 'appliedOverlays' in meta, "appliedOverlays should be present"
        assert isinstance(meta['appliedOverlays'], list), "appliedOverlays should be a list"
        
        # If there are overlays, validate their structure
        for overlay in meta['appliedOverlays']:
            assert 'id' in overlay, "overlay.id should be present"
            assert 'source' in overlay, "overlay.source should be present"
            assert 'reason' in overlay, "overlay.reason should be present"
            assert 'effect' in overlay, "overlay.effect should be present"
            print(f"  - Overlay: {overlay['source']}: {overlay['id']}")
        
        print(f"✅ appliedOverlays count: {len(meta['appliedOverlays'])}")
    
    def test_metaforecast_is_adjusted_flag(self):
        """Test that metaForecast contains isMetaAdjusted flag"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        
        meta = data.get('metaForecast')
        if not meta:
            pytest.skip("No metaForecast available")
        
        assert 'isMetaAdjusted' in meta, "isMetaAdjusted should be present"
        assert isinstance(meta['isMetaAdjusted'], bool), "isMetaAdjusted should be a boolean"
        
        print(f"✅ isMetaAdjusted: {meta['isMetaAdjusted']}")
    
    def test_confidence_only_reduced_not_increased(self):
        """Test that Meta-Brain can only LOWER confidence, never increase"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        
        meta = data.get('metaForecast')
        if not meta:
            pytest.skip("No metaForecast available")
        
        raw_confidence = meta.get('raw', {}).get('confidence', 0)
        adjusted_confidence = meta.get('confidence', 0)
        
        # Meta-brain should only reduce confidence
        assert adjusted_confidence <= raw_confidence, f"Adjusted confidence ({adjusted_confidence}) should be <= raw confidence ({raw_confidence})"
        
        if adjusted_confidence < raw_confidence:
            reduction = round((raw_confidence - adjusted_confidence) * 100, 1)
            print(f"✅ Confidence reduced by {reduction}%: {raw_confidence} → {adjusted_confidence}")
        else:
            print(f"✅ Confidence unchanged (no risk overlays applied): {raw_confidence}")


class TestMetaAwareForecastMultipleAssets:
    """Test Meta-Brain integration across multiple assets"""
    
    @pytest.mark.parametrize("asset", ["BTC", "ETH", "SOL", "BNB"])
    def test_endpoint_works_for_asset(self, asset):
        """Test that endpoint works for different assets"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset={asset}&range=7d&horizon=1D")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data.get('asset') == asset
        print(f"✅ {asset}: endpoint returns OK")


class TestMetaAwareForecastMultipleHorizons:
    """Test Meta-Brain integration across multiple horizons"""
    
    @pytest.mark.parametrize("horizon", ["1D", "7D", "30D"])
    def test_endpoint_works_for_horizon(self, horizon):
        """Test that endpoint works for different horizons"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon={horizon}")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data.get('horizon') == horizon
        print(f"✅ Horizon {horizon}: endpoint returns OK")


class TestMetaAwareForecastFuturePoint:
    """Test that futurePoint contains meta-adjusted values"""
    
    def test_future_point_uses_adjusted_confidence(self):
        """Test that futurePoint uses meta-adjusted confidence"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        
        future_point = data.get('layers', {}).get('meta', {}).get('futurePoint')
        meta = data.get('metaForecast')
        
        if not future_point or not meta:
            pytest.skip("No futurePoint or metaForecast available")
        
        # futurePoint should use the adjusted confidence
        assert future_point.get('confidence') == meta.get('confidence'), \
            f"futurePoint.confidence ({future_point.get('confidence')}) should match metaForecast.confidence ({meta.get('confidence')})"
        
        print(f"✅ futurePoint uses adjusted confidence: {future_point.get('confidence')}")
    
    def test_future_point_uses_adjusted_target_price(self):
        """Test that futurePoint uses meta-adjusted target price"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        
        future_point = data.get('layers', {}).get('meta', {}).get('futurePoint')
        meta = data.get('metaForecast')
        
        if not future_point or not meta:
            pytest.skip("No futurePoint or metaForecast available")
        
        # futurePoint should use the adjusted target price
        assert future_point.get('targetPrice') == meta.get('targetPrice'), \
            f"futurePoint.targetPrice ({future_point.get('targetPrice')}) should match metaForecast.targetPrice ({meta.get('targetPrice')})"
        
        print(f"✅ futurePoint uses adjusted targetPrice: ${future_point.get('targetPrice')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
