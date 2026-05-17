"""
CEX Flow Phase A Tests — A1, A2, A5
====================================

Tests for CEX Registry (A1), CEX Flow Aggregation (A2), and related APIs.

Endpoints tested:
- GET /api/v10/onchain-v2/cex-flow/exchanges
- GET /api/v10/onchain-v2/cex-flow/summary
- GET /api/v10/onchain-v2/cex-flow/cross

Also includes regression tests for Engine tab APIs.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCexFlowExchanges:
    """Tests for CEX Registry (A1) - Exchange list endpoint"""

    def test_exchanges_returns_ok(self):
        """GET /cex-flow/exchanges returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/exchanges?chainId=1")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"Exchanges endpoint returned ok:true")

    def test_exchanges_contains_11_exchanges(self):
        """Exchange list contains 11 CEX entities"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/exchanges?chainId=1")
        assert response.status_code == 200
        data = response.json()
        
        exchanges = data.get('exchanges', [])
        assert len(exchanges) >= 11, f"Expected at least 11 exchanges, got {len(exchanges)}"
        
        # Verify expected exchanges are present
        entity_ids = [ex['entityId'] for ex in exchanges]
        expected = ['binance', 'coinbase', 'kraken', 'okx', 'kucoin', 'gemini', 'bitfinex', 'gate_io', 'htx', 'hyperliquid', 'bybit']
        for expected_id in expected:
            assert expected_id in entity_ids, f"Missing exchange: {expected_id}"
        
        print(f"Found {len(exchanges)} exchanges: {entity_ids}")

    def test_exchanges_have_address_count(self):
        """Each exchange has addressCount field"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/exchanges?chainId=1")
        data = response.json()
        
        for ex in data.get('exchanges', []):
            assert 'addressCount' in ex, f"Missing addressCount for {ex.get('entityId')}"
            assert isinstance(ex['addressCount'], int)
            assert ex['addressCount'] >= 1, f"addressCount should be >= 1 for {ex['entityId']}"
        
        # Verify Binance has multiple addresses (should have 7 based on seed)
        binance = next((ex for ex in data['exchanges'] if ex['entityId'] == 'binance'), None)
        assert binance is not None
        assert binance['addressCount'] >= 5, f"Binance should have at least 5 addresses, got {binance['addressCount']}"
        print(f"Binance has {binance['addressCount']} addresses")


class TestCexFlowSummary:
    """Tests for CEX Flow Summary (A2) endpoint"""

    def test_summary_binance_returns_ok(self):
        """GET /cex-flow/summary returns ok:true for Binance"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary?chainId=1&entityId=binance&window=7d")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"Summary for Binance returned ok:true")

    def test_summary_has_totals(self):
        """Summary contains totals with inUsd/outUsd/netUsd/txCount"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary?chainId=1&entityId=binance&window=7d")
        data = response.json()
        
        assert 'totals' in data, "Missing totals in response"
        totals = data['totals']
        
        # Check required fields
        assert 'inUsd' in totals
        assert 'outUsd' in totals
        assert 'netUsd' in totals
        assert 'txCount' in totals
        
        # Verify types
        assert isinstance(totals['inUsd'], (int, float))
        assert isinstance(totals['outUsd'], (int, float))
        assert isinstance(totals['netUsd'], (int, float))
        assert isinstance(totals['txCount'], int)
        
        print(f"Binance totals: in=${totals['inUsd']:.2f}, out=${totals['outUsd']:.2f}, net=${totals['netUsd']:.2f}, tx={totals['txCount']}")

    def test_summary_has_positive_flows(self):
        """Binance should have positive flow data (real ERC20 logs)"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary?chainId=1&entityId=binance&window=7d")
        data = response.json()
        
        totals = data.get('totals', {})
        # Binance should have real transfer data
        assert totals.get('txCount', 0) > 0, "Binance should have transfers"
        assert totals.get('inUsd', 0) > 0 or totals.get('outUsd', 0) > 0, "Binance should have some USD flows"
        
        print(f"Binance has {totals['txCount']} transfers with ${totals['inUsd'] + totals['outUsd']:.2f} total volume")

    def test_summary_has_token_tables(self):
        """Summary contains topTokensIn and topTokensOut arrays"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary?chainId=1&entityId=binance&window=7d")
        data = response.json()
        
        assert 'topTokensIn' in data
        assert 'topTokensOut' in data
        assert isinstance(data['topTokensIn'], list)
        assert isinstance(data['topTokensOut'], list)
        
        # Check token structure if any tokens exist
        if data['topTokensIn']:
            tok = data['topTokensIn'][0]
            assert 'tokenAddress' in tok
            assert 'tokenSymbol' in tok
            assert 'inUsd' in tok
            print(f"Top inflow token: {tok['tokenSymbol']} with ${tok['inUsd']:.2f}")

    def test_summary_has_quality_metrics(self):
        """Summary contains quality metrics"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary?chainId=1&entityId=binance&window=7d")
        data = response.json()
        
        assert 'quality' in data
        quality = data['quality']
        assert 'totalLogs' in quality
        assert 'pricedLogs' in quality
        assert 'pricedShare' in quality
        
        print(f"Quality: {quality['pricedLogs']}/{quality['totalLogs']} priced ({quality['pricedShare']*100:.1f}%)")

    def test_summary_missing_entity_returns_error(self):
        """Summary without entityId returns error"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary?chainId=1&window=7d")
        data = response.json()
        assert data.get('ok') is False or data.get('error') is not None
        print("Missing entityId correctly returns error")


class TestCexFlowCross:
    """Tests for Cross-Exchange comparison endpoint"""

    def test_cross_returns_ok(self):
        """GET /cex-flow/cross returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/cross?chainId=1&window=7d", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print("Cross endpoint returned ok:true")

    def test_cross_contains_all_exchanges(self):
        """Cross response contains all exchanges with flow data"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/cross?chainId=1&window=7d", timeout=30)
        data = response.json()
        
        exchanges = data.get('exchanges', [])
        assert len(exchanges) >= 11, f"Expected at least 11 exchanges, got {len(exchanges)}"
        
        # Check structure
        for ex in exchanges:
            assert 'entityId' in ex
            assert 'entityName' in ex
            assert 'inUsd' in ex
            assert 'outUsd' in ex
            assert 'netUsd' in ex
            assert 'txCount' in ex
        
        print(f"Cross returned {len(exchanges)} exchanges")

    def test_cross_sorted_by_volume(self):
        """Exchanges are sorted by total volume (in + out) descending"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/cross?chainId=1&window=7d", timeout=30)
        data = response.json()
        
        exchanges = data.get('exchanges', [])
        volumes = [(ex['inUsd'] + ex['outUsd']) for ex in exchanges]
        
        # Verify sorted descending
        for i in range(len(volumes) - 1):
            assert volumes[i] >= volumes[i+1], f"Not sorted at index {i}: {volumes[i]} < {volumes[i+1]}"
        
        if exchanges:
            print(f"Top exchange by volume: {exchanges[0]['entityName']} with ${volumes[0]:.2f}")


class TestCexFlowWindows:
    """Tests for different time windows"""

    @pytest.mark.parametrize("window", ["24h", "7d", "30d"])
    def test_summary_window_parameter(self, window):
        """Summary accepts different window parameters"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary?chainId=1&entityId=binance&window={window}")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data.get('window') == window
        print(f"Window {window} returned ok with window={data.get('window')}")

    @pytest.mark.parametrize("window", ["24h", "7d", "30d"])
    def test_cross_window_parameter(self, window):
        """Cross accepts different window parameters"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/cross?chainId=1&window={window}", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"Cross with window={window} returned ok")


class TestEngineRegression:
    """Regression tests for Engine tab APIs (Phase 4)"""

    def test_engine_decision_returns_ok(self):
        """Engine decision endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/engine/decision?chainId=1&window=7d&symbol=LINK")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"Engine decision returned action={data.get('action')}, score={data.get('score')}")

    def test_engine_decision_has_required_fields(self):
        """Engine decision has action/score/confidence/reasons"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/engine/decision?chainId=1&window=7d&symbol=LINK")
        data = response.json()
        
        assert 'action' in data
        assert 'score' in data
        assert 'confidence' in data
        assert 'reasons' in data
        
        assert data['action'] in ['BUY', 'SELL', 'NO_TRADE', 'HOLD']
        assert isinstance(data['score'], int)
        assert isinstance(data['confidence'], float)
        assert isinstance(data['reasons'], list)


class TestOnchainHealth:
    """Regression test for onchain health endpoint"""

    def test_health_returns_ok(self):
        """Health endpoint returns ok"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"Health status: {data.get('status')}, mode: {data.get('providerMode')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
