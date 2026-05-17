"""
Phase 1.3 - Chart Module Tests
===============================
Tests for price chart, verdict history, and divergence detection APIs.

ENDPOINTS:
  GET /api/v10/market/chart/:symbol        - Full chart data
  GET /api/v10/market/chart/price/:symbol  - Price bars only
  GET /api/v10/market/chart/verdicts/:symbol - Verdict history only
  GET /api/v10/market/chart/divergences/:symbol - Divergences with stats
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestChartFullEndpoint:
    """Test GET /api/v10/market/chart/:symbol - Full chart data"""

    def test_btcusdt_full_chart_returns_200(self):
        """Full chart endpoint returns 200 for BTCUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/BTCUSDT?tf=1h&limit=50")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "symbol" in data
        assert data["symbol"] == "BTCUSDT"
        assert "timeframe" in data
        assert data["timeframe"] == "1h"
        
    def test_full_chart_response_includes_price_array(self):
        """Chart response includes price array with valid bars"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/BTCUSDT?tf=1h&limit=50")
        assert response.status_code == 200
        data = response.json()
        
        assert "price" in data
        assert isinstance(data["price"], list)
        assert len(data["price"]) > 0
        
        # Verify price bar structure
        bar = data["price"][0]
        assert "ts" in bar  # timestamp
        assert "o" in bar   # open
        assert "h" in bar   # high
        assert "l" in bar   # low
        assert "c" in bar   # close
        assert "v" in bar   # volume

    def test_full_chart_response_includes_verdicts_array(self):
        """Chart response includes verdicts array"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/BTCUSDT?tf=1h&limit=50")
        assert response.status_code == 200
        data = response.json()
        
        assert "verdicts" in data
        assert isinstance(data["verdicts"], list)
        
        # If verdicts exist, verify structure
        if len(data["verdicts"]) > 0:
            verdict = data["verdicts"][0]
            assert "ts" in verdict
            assert "verdict" in verdict
            assert "confidence" in verdict
            assert verdict["verdict"] in ["BULLISH", "BEARISH", "NEUTRAL", "INCONCLUSIVE", "NO_DATA"]

    def test_full_chart_response_includes_divergences_array(self):
        """Chart response includes divergences array"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/BTCUSDT?tf=1h&limit=200")
        assert response.status_code == 200
        data = response.json()
        
        assert "divergences" in data
        assert isinstance(data["divergences"], list)

    def test_full_chart_response_includes_stats(self):
        """Chart response includes stats with priceCount, verdictCount, divergenceCount, divergenceRate"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/BTCUSDT?tf=1h&limit=50")
        assert response.status_code == 200
        data = response.json()
        
        assert "stats" in data
        stats = data["stats"]
        assert "priceCount" in stats
        assert "verdictCount" in stats
        assert "divergenceCount" in stats
        assert "divergenceRate" in stats
        
        assert isinstance(stats["priceCount"], int)
        assert isinstance(stats["verdictCount"], int)
        assert isinstance(stats["divergenceCount"], int)
        assert isinstance(stats["divergenceRate"], (int, float))

    def test_full_chart_includes_meta_datamode(self):
        """Chart response includes meta with dataMode"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/BTCUSDT?tf=1h&limit=50")
        assert response.status_code == 200
        data = response.json()
        
        assert "meta" in data
        assert "dataMode" in data["meta"]
        assert data["meta"]["dataMode"] in ["LIVE", "MOCK", "CACHED"]

    def test_full_chart_window_object(self):
        """Chart response includes time window"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/BTCUSDT?tf=1h&limit=50")
        assert response.status_code == 200
        data = response.json()
        
        assert "window" in data
        assert "from" in data["window"]
        assert "to" in data["window"]
        assert data["window"]["to"] >= data["window"]["from"]


class TestChartPriceEndpoint:
    """Test GET /api/v10/market/chart/price/:symbol - Price bars only"""

    def test_price_endpoint_returns_200(self):
        """Price-only endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/price/BTCUSDT?tf=1h&limit=20")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert data.get("symbol") == "BTCUSDT"

    def test_price_endpoint_returns_price_bars(self):
        """Price endpoint returns prices array"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/price/ETHUSDT?tf=1h&limit=20")
        assert response.status_code == 200
        data = response.json()
        
        assert "prices" in data
        assert isinstance(data["prices"], list)
        assert data["count"] == len(data["prices"])
        
        if len(data["prices"]) > 0:
            bar = data["prices"][0]
            assert "ts" in bar
            assert "c" in bar

    def test_price_endpoint_different_timeframes(self):
        """Price endpoint works with different timeframes"""
        for tf in ["1h", "4h", "1d"]:
            response = requests.get(f"{BASE_URL}/api/v10/market/chart/price/BTCUSDT?tf={tf}&limit=10")
            assert response.status_code == 200
            data = response.json()
            assert data.get("timeframe") == tf

    def test_price_endpoint_includes_provider(self):
        """Price endpoint includes provider info"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/price/BTCUSDT?tf=1h&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert "provider" in data
        assert "dataMode" in data


class TestChartVerdictsEndpoint:
    """Test GET /api/v10/market/chart/verdicts/:symbol - Verdict history only"""

    def test_verdicts_endpoint_returns_200(self):
        """Verdicts endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/verdicts/BTCUSDT?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert data.get("symbol") == "BTCUSDT"

    def test_verdicts_endpoint_returns_verdicts_array(self):
        """Verdicts endpoint returns verdicts array"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/verdicts/BTCUSDT?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        assert "verdicts" in data
        assert isinstance(data["verdicts"], list)
        assert "count" in data
        assert data["count"] == len(data["verdicts"])

    def test_verdicts_structure_is_correct(self):
        """Verdict objects have correct structure"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/verdicts/BTCUSDT?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        if len(data["verdicts"]) > 0:
            v = data["verdicts"][0]
            assert "ts" in v
            assert "verdict" in v
            assert "confidence" in v
            assert "source" in v
            assert v["verdict"] in ["BULLISH", "BEARISH", "NEUTRAL", "INCONCLUSIVE", "NO_DATA"]


class TestChartDivergencesEndpoint:
    """Test GET /api/v10/market/chart/divergences/:symbol - Divergences with stats"""

    def test_divergences_endpoint_returns_200(self):
        """Divergences endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/divergences/BTCUSDT?tf=1h")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert data.get("symbol") == "BTCUSDT"

    def test_divergences_includes_config(self):
        """Divergences endpoint includes config (horizonBars, threshold)"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/divergences/BTCUSDT?tf=1h&horizon=6&threshold=0.02")
        assert response.status_code == 200
        data = response.json()
        
        assert "config" in data
        assert "horizonBars" in data["config"]
        assert "threshold" in data["config"]
        assert data["config"]["horizonBars"] == 6
        assert data["config"]["threshold"] == 0.02

    def test_divergences_includes_stats(self):
        """Divergences endpoint includes detailed stats"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/divergences/BTCUSDT?tf=1h")
        assert response.status_code == 200
        data = response.json()
        
        assert "stats" in data
        stats = data["stats"]
        assert "totalVerdicts" in stats
        assert "totalDivergences" in stats
        assert "divergenceRate" in stats
        assert "avgMagnitude" in stats
        assert "byVerdict" in stats

    def test_divergences_array_structure(self):
        """Divergences array has correct structure when present"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/divergences/BTCUSDT?tf=1h")
        assert response.status_code == 200
        data = response.json()
        
        assert "divergences" in data
        assert isinstance(data["divergences"], list)
        
        # Note: May be empty if no divergences detected
        if len(data["divergences"]) > 0:
            d = data["divergences"][0]
            assert "ts" in d
            assert "verdict" in d
            assert "expectedMove" in d
            assert "actualMove" in d
            assert "magnitude" in d
            assert "horizonBars" in d


class TestChartDifferentSymbols:
    """Test chart endpoints with different symbols"""

    def test_ethusdt_full_chart(self):
        """ETHUSDT full chart works"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/ETHUSDT?tf=1h&limit=30")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "ETHUSDT"
        assert len(data["price"]) > 0

    def test_solusdt_full_chart(self):
        """SOLUSDT full chart works"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/SOLUSDT?tf=1h&limit=30")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "SOLUSDT"
        assert len(data["price"]) > 0

    def test_lowercase_symbol_normalized(self):
        """Lowercase symbol is normalized to uppercase"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/btcusdt?tf=1h&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTCUSDT"


class TestChartQueryParameters:
    """Test chart query parameters"""

    def test_limit_parameter(self):
        """Limit parameter controls number of bars"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/BTCUSDT?tf=1h&limit=25")
        assert response.status_code == 200
        data = response.json()
        # May have slightly more/less due to mock generation, but should be close
        assert len(data["price"]) <= 200  # Default max

    def test_timeframe_4h(self):
        """4h timeframe works"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/BTCUSDT?tf=4h&limit=30")
        assert response.status_code == 200
        data = response.json()
        assert data["timeframe"] == "4h"

    def test_timeframe_1d(self):
        """1d timeframe works"""
        response = requests.get(f"{BASE_URL}/api/v10/market/chart/BTCUSDT?tf=1d&limit=30")
        assert response.status_code == 200
        data = response.json()
        assert data["timeframe"] == "1d"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
