"""
Prediction Exchange Routes - Backend API Tests
Tests for Exchange Prediction blocks 2-5:
  - /api/prediction/exchange/forecast (Block 2)
  - /api/prediction/exchange/alts (Block 3)
  - /api/prediction/exchange/top-signals (Block 4)
  - /api/prediction/exchange/model-health (Block 5)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPredictionExchangeAPIs:
    """Test all 4 Prediction Exchange API endpoints"""
    
    # Block 2: Forecast API
    def test_forecast_api_returns_200(self):
        """Verify /api/prediction/exchange/forecast returns 200"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/forecast?asset=BTC")
        assert response.status_code == 200
        print(f"✓ Forecast API status: {response.status_code}")
    
    def test_forecast_api_returns_ok_true(self):
        """Verify forecast response has ok:true"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/forecast?asset=BTC")
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Forecast API ok field: {data.get('ok')}")
    
    def test_forecast_api_has_series(self):
        """Verify forecast response has series array with price data"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/forecast?asset=BTC&lookback=90")
        data = response.json()
        assert "series" in data
        assert isinstance(data["series"], list)
        assert len(data["series"]) > 0
        # Verify series item structure
        if data["series"]:
            item = data["series"][0]
            assert "ts" in item
            assert "price" in item
        print(f"✓ Forecast series count: {len(data['series'])}")
    
    def test_forecast_api_has_targets(self):
        """Verify forecast response has targets array"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/forecast?asset=BTC")
        data = response.json()
        assert "targets" in data
        assert isinstance(data["targets"], list)
        print(f"✓ Forecast targets count: {len(data['targets'])}")
    
    def test_forecast_targets_structure(self):
        """Verify target structure has required fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/forecast?asset=BTC")
        data = response.json()
        if data.get("targets"):
            target = data["targets"][0]
            required_fields = ["horizon", "direction", "entryPrice", "targetPrice", "confidence", "movePct", "status"]
            for field in required_fields:
                assert field in target, f"Missing field: {field}"
            # Verify horizon is one of expected values
            assert target["horizon"] in ["24H", "7D", "30D"]
            # Verify direction is valid
            assert target["direction"] in ["LONG", "SHORT", "NEUTRAL"]
            # Verify status is valid
            assert target["status"] in ["PENDING", "EVALUATED", "STALE"]
            print(f"✓ Target structure verified for horizon: {target['horizon']}")
    
    # Block 3: Alt Signals API
    def test_alts_api_returns_200(self):
        """Verify /api/prediction/exchange/alts returns 200"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/alts?horizon=7D")
        assert response.status_code == 200
        print(f"✓ Alts API status: {response.status_code}")
    
    def test_alts_api_returns_ok_true(self):
        """Verify alts response has ok:true"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/alts?horizon=7D")
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Alts API ok field: {data.get('ok')}")
    
    def test_alts_api_has_rows(self):
        """Verify alts response has rows array"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/alts?horizon=7D&limit=30")
        data = response.json()
        assert "rows" in data
        assert isinstance(data["rows"], list)
        print(f"✓ Alts rows count: {len(data['rows'])}")
    
    def test_alts_api_has_universe(self):
        """Verify alts response has universe metadata"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/alts?horizon=7D")
        data = response.json()
        assert "universe" in data
        assert "count" in data["universe"]
        print(f"✓ Alts universe count: {data['universe']['count']}")
    
    def test_alts_horizon_selector(self):
        """Verify different horizons work"""
        for horizon in ["24H", "7D", "30D"]:
            response = requests.get(f"{BASE_URL}/api/prediction/exchange/alts?horizon={horizon}")
            data = response.json()
            assert data.get("ok") == True
            assert data.get("horizon") == horizon
            print(f"✓ Alts horizon {horizon}: OK")
    
    # Block 4: Top Signals API
    def test_top_signals_api_returns_200(self):
        """Verify /api/prediction/exchange/top-signals returns 200"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/top-signals?limit=10")
        assert response.status_code == 200
        print(f"✓ Top Signals API status: {response.status_code}")
    
    def test_top_signals_api_returns_ok_true(self):
        """Verify top-signals response has ok:true"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/top-signals?limit=10")
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Top Signals API ok field: {data.get('ok')}")
    
    def test_top_signals_api_has_signals(self):
        """Verify top-signals response has signals array"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/top-signals?limit=10")
        data = response.json()
        assert "signals" in data
        assert isinstance(data["signals"], list)
        print(f"✓ Top Signals count: {len(data['signals'])}")
    
    def test_top_signals_structure(self):
        """Verify signal structure has required fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/top-signals?limit=10")
        data = response.json()
        if data.get("signals"):
            signal = data["signals"][0]
            required_fields = ["symbol", "action", "tier", "conviction", "oneLiner", "integrity"]
            for field in required_fields:
                assert field in signal, f"Missing field: {field}"
            # Verify action is valid
            assert signal["action"] in ["BUY", "SELL", "WATCH"]
            # Verify tier is valid
            assert signal["tier"] in ["A", "B", "C"]
            # Verify conviction is percentage
            assert 0 <= signal["conviction"] <= 100
            print(f"✓ Signal structure verified: {signal['symbol']} - {signal['action']}")
    
    # Block 5: Model Health API
    def test_model_health_api_returns_200(self):
        """Verify /api/prediction/exchange/model-health returns 200"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/model-health?asset=BTC")
        assert response.status_code == 200
        print(f"✓ Model Health API status: {response.status_code}")
    
    def test_model_health_api_returns_ok_true(self):
        """Verify model-health response has ok:true"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/model-health?asset=BTC")
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Model Health API ok field: {data.get('ok')}")
    
    def test_model_health_api_has_horizons(self):
        """Verify model-health response has horizons object with 24H/7D/30D"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/model-health?asset=BTC")
        data = response.json()
        assert "horizons" in data
        horizons = data["horizons"]
        assert "24H" in horizons
        assert "7D" in horizons
        assert "30D" in horizons
        print(f"✓ Model Health horizons: {list(horizons.keys())}")
    
    def test_model_health_horizon_structure(self):
        """Verify each horizon has required metrics"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/model-health?asset=BTC")
        data = response.json()
        horizons = data.get("horizons", {})
        for h in ["24H", "7D", "30D"]:
            if h in horizons:
                metrics = horizons[h]
                required_fields = ["n", "winRate", "avgErrPct", "overdue", "tp", "fp", "weak"]
                for field in required_fields:
                    assert field in metrics, f"Missing field {field} in {h}"
                # Verify winRate is between 0 and 1
                assert 0 <= metrics["winRate"] <= 1
                print(f"✓ Model Health {h}: n={metrics['n']}, winRate={metrics['winRate']}")
    
    def test_model_health_has_flags(self):
        """Verify model-health response has flags array"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/model-health?asset=BTC")
        data = response.json()
        assert "flags" in data
        assert isinstance(data["flags"], list)
        print(f"✓ Model Health flags: {data['flags']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
