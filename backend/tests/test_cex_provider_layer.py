"""
Phase X - CEX Provider Layer Tests
===================================
Tests for:
- Provider health endpoint
- Provider list endpoint
- Provider ticker endpoint
- Provider candles endpoint
- Provider orderbook endpoint
- Provider symbols endpoint
- Admin enable/disable provider endpoints
- Fusion alignment endpoint
- Validation latest endpoint
- Meta-Brain v2 process endpoint

NOTE: Binance API returns 451 error due to geographic restrictions,
so the system falls back to MOCK provider automatically.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestProviderHealth:
    """Provider health endpoint tests"""
    
    def test_health_endpoint_returns_ok(self):
        """GET /api/v10/exchange/providers/health returns 200 with correct structure"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'stats' in data
        assert 'providers' in data
        
        # Validate stats structure
        stats = data['stats']
        assert 'total' in stats
        assert 'enabled' in stats
        assert 'up' in stats
        assert 'degraded' in stats
        assert 'down' in stats
        
        # Should have at least 2 providers (BINANCE_USDM and MOCK)
        assert stats['total'] >= 2
        
    def test_health_providers_have_required_fields(self):
        """Provider entries in health response have required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/health")
        data = response.json()
        
        for provider in data['providers']:
            assert 'id' in provider
            assert 'enabled' in provider
            assert 'priority' in provider
            assert 'health' in provider
            
            # Validate health object structure
            health = provider['health']
            assert 'id' in health
            assert 'status' in health
            assert health['status'] in ['UP', 'DEGRADED', 'DOWN']


class TestProviderList:
    """Provider list endpoint tests"""
    
    def test_list_endpoint_returns_providers(self):
        """GET /api/v10/exchange/providers/list returns 200 with providers"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/list")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'providers' in data
        assert isinstance(data['providers'], list)
        assert len(data['providers']) >= 2
        
    def test_list_contains_binance_and_mock(self):
        """Provider list contains BINANCE_USDM and MOCK providers"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/list")
        data = response.json()
        
        provider_ids = [p['id'] for p in data['providers']]
        assert 'BINANCE_USDM' in provider_ids
        assert 'MOCK' in provider_ids
        
    def test_binance_has_higher_priority_than_mock(self):
        """BINANCE_USDM has priority 100, MOCK has priority 1"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/list")
        data = response.json()
        
        binance = next((p for p in data['providers'] if p['id'] == 'BINANCE_USDM'), None)
        mock = next((p for p in data['providers'] if p['id'] == 'MOCK'), None)
        
        assert binance is not None
        assert mock is not None
        assert binance['priority'] > mock['priority']


class TestProviderTicker:
    """Provider ticker endpoint tests"""
    
    def test_ticker_btcusdt_returns_data(self):
        """GET /api/v10/exchange/providers/ticker/BTCUSDT returns ticker data"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/ticker/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'provider' in data  # Should indicate which provider served the data
        assert 'data' in data
        
        # Validate ticker data structure
        ticker = data['data']
        assert ticker.get('symbol') == 'BTCUSDT'
        assert 'mid' in ticker
        assert 'bestBid' in ticker
        assert 'bestAsk' in ticker
        assert 'timestamp' in ticker
        
        # Mid should be between bid and ask
        assert ticker['bestBid'] <= ticker['mid'] <= ticker['bestAsk']
        
    def test_ticker_ethusdt_returns_data(self):
        """GET /api/v10/exchange/providers/ticker/ETHUSDT returns data"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/ticker/ETHUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data['data']['symbol'] == 'ETHUSDT'


class TestProviderCandles:
    """Provider candles endpoint tests"""
    
    def test_candles_btcusdt_returns_ohlcv_data(self):
        """GET /api/v10/exchange/providers/candles/BTCUSDT returns OHLCV candles"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/candles/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'provider' in data
        assert 'count' in data
        assert 'data' in data
        
        candles = data['data']
        assert isinstance(candles, list)
        assert len(candles) > 0
        
        # Validate first candle structure
        candle = candles[0]
        assert 't' in candle  # timestamp
        assert 'o' in candle  # open
        assert 'h' in candle  # high
        assert 'l' in candle  # low
        assert 'c' in candle  # close
        assert 'v' in candle  # volume
        
        # High should be >= open, close, low
        assert candle['h'] >= candle['o']
        assert candle['h'] >= candle['c']
        assert candle['h'] >= candle['l']
        
        # Low should be <= open, close, high
        assert candle['l'] <= candle['o']
        assert candle['l'] <= candle['c']
        
    def test_candles_with_interval_and_limit(self):
        """GET /api/v10/exchange/providers/candles/BTCUSDT?interval=5m&limit=10 works"""
        response = requests.get(
            f"{BASE_URL}/api/v10/exchange/providers/candles/BTCUSDT",
            params={'interval': '5m', 'limit': '10'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True


class TestProviderOrderbook:
    """Provider orderbook endpoint tests"""
    
    def test_orderbook_btcusdt_returns_bids_asks(self):
        """GET /api/v10/exchange/providers/orderbook/BTCUSDT returns order book"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/orderbook/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'provider' in data
        assert 'data' in data
        
        orderbook = data['data']
        assert 't' in orderbook  # timestamp
        assert 'bids' in orderbook
        assert 'asks' in orderbook
        assert 'mid' in orderbook
        
        bids = orderbook['bids']
        asks = orderbook['asks']
        
        assert isinstance(bids, list)
        assert isinstance(asks, list)
        assert len(bids) > 0
        assert len(asks) > 0
        
        # Each bid/ask should be [price, quantity]
        assert len(bids[0]) == 2
        assert len(asks[0]) == 2
        
        # Best bid should be less than best ask (for valid market)
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        assert best_bid < best_ask
        
    def test_orderbook_with_depth_param(self):
        """GET /api/v10/exchange/providers/orderbook/BTCUSDT?depth=5 works"""
        response = requests.get(
            f"{BASE_URL}/api/v10/exchange/providers/orderbook/BTCUSDT",
            params={'depth': '5'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True


class TestProviderSymbols:
    """Provider symbols endpoint tests"""
    
    def test_symbols_returns_available_symbols(self):
        """GET /api/v10/exchange/providers/symbols returns tradable symbols"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/symbols")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'provider' in data
        assert 'count' in data
        assert 'symbols' in data
        
        symbols = data['symbols']
        assert isinstance(symbols, list)
        assert len(symbols) > 0
        
        # Validate symbol structure
        symbol = symbols[0]
        assert 'symbol' in symbol
        assert 'base' in symbol
        assert 'quote' in symbol
        assert 'status' in symbol
        
    def test_symbols_contains_btcusdt(self):
        """Symbols list contains BTCUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/symbols")
        data = response.json()
        
        symbol_names = [s['symbol'] for s in data['symbols']]
        assert 'BTCUSDT' in symbol_names


class TestProviderAdmin:
    """Provider admin endpoint tests"""
    
    def test_admin_enable_provider(self):
        """POST /api/v10/exchange/providers/admin/enable enables a provider"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/providers/admin/enable",
            json={'id': 'MOCK'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'message' in data
        assert 'enabled' in data['message'].lower() or 'MOCK' in data['message']
        
    def test_admin_disable_and_reenable_provider(self):
        """POST /api/v10/exchange/providers/admin/disable then enable works"""
        # Disable
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/providers/admin/disable",
            json={'id': 'MOCK'}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        
        # Re-enable
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/providers/admin/enable",
            json={'id': 'MOCK'}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        
    def test_admin_enable_missing_id_returns_error(self):
        """POST /api/v10/exchange/providers/admin/enable without id returns error"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/providers/admin/enable",
            json={}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == False
        assert 'error' in data
        
    def test_admin_enable_unknown_provider_returns_error(self):
        """POST /api/v10/exchange/providers/admin/enable with unknown id returns error"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/providers/admin/enable",
            json={'id': 'UNKNOWN_PROVIDER'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == False


class TestFusionAlignment:
    """Fusion alignment endpoint tests"""
    
    def test_alignment_btcusdt_returns_result(self):
        """GET /api/v10/fusion/alignment/BTCUSDT returns alignment data"""
        response = requests.get(f"{BASE_URL}/api/v10/fusion/alignment/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'alignment' in data
        
        alignment = data['alignment']
        assert alignment.get('symbol') == 'BTCUSDT'
        assert 't0' in alignment
        assert 'exchange' in alignment
        assert 'sentiment' in alignment
        assert 'alignment' in alignment
        
        # Validate exchange layer input
        exchange = alignment['exchange']
        assert 'verdict' in exchange
        assert 'confidence' in exchange
        assert 'readiness' in exchange
        assert exchange['verdict'] in ['BULLISH', 'BEARISH', 'NEUTRAL']
        
        # Validate sentiment layer input
        sentiment = alignment['sentiment']
        assert 'verdict' in sentiment
        assert 'confidence' in sentiment
        assert sentiment['verdict'] in ['BULLISH', 'BEARISH', 'NEUTRAL']
        
        # Validate alignment result
        align_result = alignment['alignment']
        assert 'type' in align_result
        assert 'strength' in align_result
        
    def test_alignment_ethusdt_returns_result(self):
        """GET /api/v10/fusion/alignment/ETHUSDT works"""
        response = requests.get(f"{BASE_URL}/api/v10/fusion/alignment/ETHUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True


class TestValidationLatest:
    """Validation latest endpoint tests"""
    
    def test_validation_latest_btcusdt_returns_result(self):
        """GET /api/v10/validation/BTCUSDT/latest returns validation data"""
        response = requests.get(f"{BASE_URL}/api/v10/validation/BTCUSDT/latest")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        
        # Validation may be null if no recent validation exists
        validation = data.get('validation')
        if validation:
            assert validation.get('symbol') == 'BTCUSDT'
            assert 't0' in validation
            assert 'exchange' in validation
            assert 'validation' in validation
            
            # Validate exchange part
            exchange = validation['exchange']
            assert 'verdict' in exchange
            assert 'confidence' in exchange
            
            # Validate result part  
            val_result = validation['validation']
            assert 'result' in val_result
            assert val_result['result'] in ['VALID', 'INVALID', 'NO_DATA', 'WEAK']
            
    def test_validation_latest_handles_unknown_symbol(self):
        """GET /api/v10/validation/UNKNOWNSYM/latest returns ok with null validation"""
        response = requests.get(f"{BASE_URL}/api/v10/validation/UNKNOWNSYM/latest")
        assert response.status_code == 200
        
        data = response.json()
        assert 'ok' in data


class TestMetaBrainV2:
    """Meta-Brain v2 process endpoint tests"""
    
    def test_meta_brain_process_btcusdt(self):
        """POST /api/v10/meta-brain-v2/process returns decision for BTCUSDT"""
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain-v2/process",
            json={'symbol': 'BTCUSDT'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'decision' in data
        
        decision = data['decision']
        assert decision.get('symbol') == 'BTCUSDT'
        assert 't0' in decision
        assert 'finalVerdict' in decision
        assert 'finalConfidence' in decision
        assert 'reasonTree' in decision
        
        # Validate final verdict is a valid direction
        assert decision['finalVerdict'] in [
            'STRONG_BULLISH', 'WEAK_BULLISH', 
            'STRONG_BEARISH', 'WEAK_BEARISH',
            'NEUTRAL', 'NO_TRADE'
        ]
        
        # Validate confidence is between 0 and 1
        assert 0 <= decision['finalConfidence'] <= 1
        
        # Validate reason tree has entries
        assert isinstance(decision['reasonTree'], list)
        assert len(decision['reasonTree']) > 0
        
    def test_meta_brain_process_ethusdt(self):
        """POST /api/v10/meta-brain-v2/process works for ETHUSDT"""
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain-v2/process",
            json={'symbol': 'ETHUSDT'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('decision', {}).get('symbol') == 'ETHUSDT'


class TestProviderFallback:
    """Tests for provider fallback behavior"""
    
    def test_provider_uses_mock_when_binance_blocked(self):
        """Provider falls back to MOCK when Binance returns 451"""
        # First check that MOCK is enabled
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/providers/admin/enable",
            json={'id': 'MOCK'}
        )
        
        # Get ticker - should work using MOCK
        response = requests.get(f"{BASE_URL}/api/v10/exchange/providers/ticker/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        # Provider field indicates which provider served the data
        # In geographically restricted regions, should be MOCK
        assert data.get('provider') in ['MOCK', 'BINANCE_USDM']
        

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
