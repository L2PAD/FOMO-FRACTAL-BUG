"""
BTC Prediction Terminal v4 Backend Tests
=========================================
Tests for v4 features:
- 7D point target with forecastType='point', band=null
- 30D probabilistic band architecture with band object
- Bootstrap status endpoint
- Live price endpoint
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestGraph3_7D_PointTarget:
    """7D horizon returns point forecast, no band"""

    def test_7d_returns_ok(self):
        """GET /api/prediction/exchange/graph3?asset=BTC&horizon=7D returns ok"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        assert r.status_code == 200
        data = r.json()
        assert data.get('ok') is True

    def test_7d_band_is_null(self):
        """7D response has band=null"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        assert r.status_code == 200
        data = r.json()
        assert data.get('band') is None

    def test_7d_current_forecastType_is_point(self):
        """7D current forecast has forecastType='point'"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        assert r.status_code == 200
        data = r.json()
        current = data.get('current', {})
        assert current.get('forecastType') == 'point'

    def test_7d_has_required_fields(self):
        """7D response has required fields: priceSeries, rollingForecasts, current, riskProfile"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        assert r.status_code == 200
        data = r.json()
        assert 'priceSeries' in data
        assert 'rollingForecasts' in data
        assert 'current' in data
        assert 'riskProfile' in data


class TestGraph3_30D_BandArchitecture:
    """30D horizon returns probabilistic band architecture"""

    def test_30d_returns_ok(self):
        """GET /api/prediction/exchange/graph3?asset=BTC&horizon=30D returns ok"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        assert r.status_code == 200
        data = r.json()
        assert data.get('ok') is True

    def test_30d_has_band_object(self):
        """30D response has band object"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        assert r.status_code == 200
        data = r.json()
        band = data.get('band')
        assert band is not None
        assert isinstance(band, dict)

    def test_30d_band_has_medianTarget(self):
        """30D band has medianTarget field"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        assert r.status_code == 200
        band = r.json().get('band', {})
        assert 'medianTarget' in band
        assert isinstance(band['medianTarget'], (int, float))
        assert band['medianTarget'] > 0

    def test_30d_band_has_bandCore(self):
        """30D band has bandCore with low/high"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        assert r.status_code == 200
        band = r.json().get('band', {})
        assert 'bandCore' in band
        assert 'low' in band['bandCore']
        assert 'high' in band['bandCore']
        assert band['bandCore']['low'] > 0
        assert band['bandCore']['high'] > 0

    def test_30d_band_has_bandWide(self):
        """30D band has bandWide with low/high"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        assert r.status_code == 200
        band = r.json().get('band', {})
        assert 'bandWide' in band
        assert 'low' in band['bandWide']
        assert 'high' in band['bandWide']
        assert band['bandWide']['low'] > 0
        assert band['bandWide']['high'] > 0

    def test_30d_band_has_bias(self):
        """30D band has bias field (LONG/SHORT/NEUTRAL)"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        assert r.status_code == 200
        band = r.json().get('band', {})
        assert 'bias' in band
        assert band['bias'] in ['LONG', 'SHORT', 'NEUTRAL']

    def test_30d_band_has_signalStrength(self):
        """30D band has signalStrength field"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        assert r.status_code == 200
        band = r.json().get('band', {})
        assert 'signalStrength' in band
        assert isinstance(band['signalStrength'], (int, float))

    def test_30d_band_ordering_valid(self):
        """30D band: bandCore.low < medianTarget < bandCore.high"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        assert r.status_code == 200
        band = r.json().get('band', {})
        
        core_low = band.get('bandCore', {}).get('low', 0)
        median = band.get('medianTarget', 0)
        core_high = band.get('bandCore', {}).get('high', 0)
        
        assert core_low < median < core_high, f"Order invalid: {core_low} < {median} < {core_high}"


class TestBootstrapStatus:
    """Bootstrap/replay endpoint for cold start status"""

    def test_bootstrap_status_returns_ok(self):
        """GET /api/system/bootstrap/status?asset=BTC returns ok"""
        r = requests.get(f"{BASE_URL}/api/system/bootstrap/status?asset=BTC")
        assert r.status_code == 200
        data = r.json()
        assert data.get('ok') is True

    def test_bootstrap_status_has_total(self):
        """Bootstrap status has total count"""
        r = requests.get(f"{BASE_URL}/api/system/bootstrap/status?asset=BTC")
        assert r.status_code == 200
        data = r.json()
        assert 'total' in data
        assert isinstance(data['total'], int)

    def test_bootstrap_status_has_horizons(self):
        """Bootstrap status has horizons breakdown"""
        r = requests.get(f"{BASE_URL}/api/system/bootstrap/status?asset=BTC")
        assert r.status_code == 200
        data = r.json()
        assert 'horizons' in data
        assert '7D' in data['horizons']
        assert '30D' in data['horizons']

    def test_bootstrap_status_has_dateRange(self):
        """Bootstrap status has dateRange"""
        r = requests.get(f"{BASE_URL}/api/system/bootstrap/status?asset=BTC")
        assert r.status_code == 200
        data = r.json()
        assert 'dateRange' in data
        assert 'oldest' in data['dateRange']
        assert 'newest' in data['dateRange']


class TestLivePrice:
    """Live BTC price endpoint"""

    def test_live_price_returns_ok(self):
        """GET /api/prediction/exchange/live-price?asset=BTC returns ok"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/live-price?asset=BTC")
        assert r.status_code == 200
        data = r.json()
        assert data.get('ok') is True

    def test_live_price_has_price(self):
        """Live price has price field"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/live-price?asset=BTC")
        assert r.status_code == 200
        data = r.json()
        assert 'price' in data
        assert isinstance(data['price'], (int, float))
        assert data['price'] > 0

    def test_live_price_has_source(self):
        """Live price has source field (binance or coinpaprika)"""
        r = requests.get(f"{BASE_URL}/api/prediction/exchange/live-price?asset=BTC")
        assert r.status_code == 200
        data = r.json()
        assert 'source' in data
        assert data['source'] in ['binance', 'coinpaprika', 'unavailable']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
