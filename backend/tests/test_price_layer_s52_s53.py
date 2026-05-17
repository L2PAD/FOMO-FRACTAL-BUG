"""
S5.2 Price Layer + S5.3 Outcome Labeling API Tests

Tests the complete pipeline:
- Signal creation with automatic t0 price collection
- Price fetching for BTC, ETH, SOL
- Statistics and outcome endpoints
- Manual outcome labeling
- Correlation matrix

Collections: signal_events, price_observations, price_reactions, outcomes
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Add delay between requests to avoid rate limiting
@pytest.fixture(autouse=True)
def slow_down_tests():
    yield
    time.sleep(0.5)  # 500ms delay between tests

class TestPriceLayerHealth:
    """Basic health checks for Price Layer endpoints"""
    
    def test_stats_endpoint_returns_200(self):
        """GET /api/v5/price-layer/stats should return 200"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/stats")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
        
    def test_stats_contains_required_fields(self):
        """Stats should contain all required fields"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/stats")
        data = response.json()['data']
        
        required_fields = [
            'totalSignals', 'signalsByAsset', 'signalsBySentiment',
            'reactionsByDirection', 'reactionsByMagnitude', 'avgDeltaByHorizon',
            'completenessRate', 'totalOutcomes', 'outcomesByLabel', 'signalAccuracy'
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestPriceEndpoints:
    """Test price fetching for supported assets"""
    
    def test_get_btc_price(self):
        """GET /api/v5/price-layer/price/BTC should return price data"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/price/BTC")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        price_data = data['data']
        assert price_data['asset'] == 'BTC'
        assert 'price' in price_data
        assert price_data['price'] > 0
        assert 'source' in price_data
        assert price_data['source'] in ['coingecko', 'fallback', 'cached', 'dex']
        
    def test_get_eth_price(self):
        """GET /api/v5/price-layer/price/ETH should return price data"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/price/ETH")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        price_data = data['data']
        assert price_data['asset'] == 'ETH'
        assert price_data['price'] > 0
        
    def test_get_sol_price(self):
        """GET /api/v5/price-layer/price/SOL should return price data"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/price/SOL")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        price_data = data['data']
        assert price_data['asset'] == 'SOL'
        assert price_data['price'] > 0
        
    def test_unknown_asset_returns_400(self):
        """GET /api/v5/price-layer/price/UNKNOWN should return 400"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/price/UNKNOWN")
        assert response.status_code == 400
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'UNKNOWN_ASSET'


class TestSignalCreation:
    """Test signal creation and retrieval"""
    
    def test_create_signal_with_positive_sentiment(self):
        """POST /api/v5/price-layer/signal should create signal with t0 price"""
        payload = {
            "asset": "BTC",
            "sentiment": {
                "label": "POSITIVE",
                "score": 0.85,
                "confidence": 0.92
            },
            "meta": {
                "text": "TEST_S52_positive_signal_creation"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/signal",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        signal_data = data['data']
        assert 'signal_id' in signal_data
        assert signal_data['asset'] == 'BTC'
        assert signal_data['sentiment']['label'] == 'POSITIVE'
        assert 'message' in signal_data
        
        # Verify signal was created with t0 observation
        signal_id = signal_data['signal_id']
        get_response = requests.get(f"{BASE_URL}/api/v5/price-layer/signal/{signal_id}")
        assert get_response.status_code == 200
        
        signal_full = get_response.json()['data']
        assert signal_full['signal']['signal_id'] == signal_id
        assert len(signal_full['observations']) >= 1
        
        # Check t0 observation exists
        t0_obs = [o for o in signal_full['observations'] if o['horizon'] == 't0']
        assert len(t0_obs) == 1
        assert t0_obs[0]['price'] > 0
        
    def test_create_signal_with_negative_sentiment(self):
        """POST /api/v5/price-layer/signal with NEGATIVE sentiment"""
        payload = {
            "asset": "ETH",
            "sentiment": {
                "label": "NEGATIVE",
                "score": 0.25,
                "confidence": 0.88
            },
            "meta": {
                "text": "TEST_S52_negative_signal_creation"
            },
            "source": "twitter"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/signal",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        assert data['data']['sentiment']['label'] == 'NEGATIVE'
        
    def test_create_signal_with_neutral_sentiment(self):
        """POST /api/v5/price-layer/signal with NEUTRAL sentiment"""
        payload = {
            "asset": "SOL",
            "sentiment": {
                "label": "NEUTRAL",
                "score": 0.50,
                "confidence": 0.75
            },
            "meta": {
                "text": "TEST_S52_neutral_signal_creation"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/signal",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        assert data['data']['sentiment']['label'] == 'NEUTRAL'
        
    def test_create_signal_missing_asset_returns_400(self):
        """POST /api/v5/price-layer/signal without asset should return 400"""
        payload = {
            "sentiment": {
                "label": "POSITIVE",
                "score": 0.85,
                "confidence": 0.92
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/signal",
            json=payload
        )
        assert response.status_code == 400
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'INVALID_REQUEST'
        
    def test_create_signal_missing_sentiment_returns_400(self):
        """POST /api/v5/price-layer/signal without sentiment should return 400"""
        payload = {
            "asset": "BTC"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/signal",
            json=payload
        )
        assert response.status_code == 400
        data = response.json()
        assert data['ok'] == False


class TestSignalRetrieval:
    """Test signal retrieval endpoints"""
    
    def test_get_signals_list(self):
        """GET /api/v5/price-layer/signals should return list of signals"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/signals")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
        assert 'signals' in data['data']
        assert 'count' in data['data']
        
    def test_get_signals_with_limit(self):
        """GET /api/v5/price-layer/signals?limit=5 should respect limit"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/signals?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        assert len(data['data']['signals']) <= 5
        
    def test_get_signal_by_id_not_found(self):
        """GET /api/v5/price-layer/signal/:id with invalid ID returns 404"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/signal/invalid_signal_id")
        assert response.status_code == 404
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'NOT_FOUND'
        
    def test_get_existing_signal_with_full_data(self):
        """GET /api/v5/price-layer/signal/:id returns full signal data"""
        # First get list of signals
        list_response = requests.get(f"{BASE_URL}/api/v5/price-layer/signals?limit=1")
        signals = list_response.json()['data']['signals']
        
        if len(signals) > 0:
            signal_id = signals[0]['signal_id']
            response = requests.get(f"{BASE_URL}/api/v5/price-layer/signal/{signal_id}")
            assert response.status_code == 200
            data = response.json()['data']
            
            # Verify structure
            assert 'signal' in data
            assert 'observations' in data
            assert 'reactions' in data
            assert 'outcomes' in data
            
            # Verify signal fields
            signal = data['signal']
            assert 'signal_id' in signal
            assert 'asset' in signal
            assert 'sentiment' in signal
            assert 'timestamp' in signal


class TestOutcomeLabeling:
    """Test S5.3 Outcome Labeling endpoints"""
    
    def test_outcomes_stats_endpoint(self):
        """GET /api/v5/price-layer/outcomes/stats should return outcome statistics"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/outcomes/stats")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        stats = data['data']
        required_fields = [
            'totalOutcomes', 'outcomesByLabel', 'outcomesBySentiment',
            'accuracyByHorizon', 'avgConfidenceByOutcome'
        ]
        for field in required_fields:
            assert field in stats, f"Missing field: {field}"
            
    def test_outcomes_summary_endpoint(self):
        """GET /api/v5/price-layer/outcomes/summary should return summary for Admin UI"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/outcomes/summary")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        summary = data['data']
        assert 'total' in summary
        assert 'distribution' in summary
        assert 'accuracy' in summary
        assert 'sentimentBreakdown' in summary
        assert 'confidence' in summary
        
    def test_manual_labeling_missing_params_returns_400(self):
        """POST /api/v5/price-layer/outcomes/label-manual without params returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/outcomes/label-manual",
            json={}
        )
        assert response.status_code == 400
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'INVALID_REQUEST'
        
    def test_manual_labeling_invalid_signal_returns_404(self):
        """POST /api/v5/price-layer/outcomes/label-manual with invalid signal returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/outcomes/label-manual",
            json={"signal_id": "invalid_signal", "horizon": "5m"}
        )
        assert response.status_code == 404
        data = response.json()
        assert data['ok'] == False
        
    def test_manual_labeling_existing_signal_with_reaction(self):
        """POST /api/v5/price-layer/outcomes/label-manual with valid signal"""
        # Get a signal that has reactions
        list_response = requests.get(f"{BASE_URL}/api/v5/price-layer/signals?limit=10")
        signals = list_response.json()['data']['signals']
        
        # Find signal with reactions
        signal_with_reaction = None
        for sig in signals:
            if len(sig.get('reactions', [])) > 0:
                signal_with_reaction = sig
                break
                
        if signal_with_reaction:
            signal_id = signal_with_reaction['signal_id']
            horizon = signal_with_reaction['reactions'][0]['horizon']
            
            response = requests.post(
                f"{BASE_URL}/api/v5/price-layer/outcomes/label-manual",
                json={"signal_id": signal_id, "horizon": horizon}
            )
            assert response.status_code == 200
            data = response.json()
            assert data['ok'] == True
            
            outcome_data = data['data']
            assert 'outcome' in outcome_data
            assert outcome_data['outcome'] in [
                'TRUE_POSITIVE', 'FALSE_POSITIVE', 'TRUE_NEGATIVE',
                'FALSE_NEGATIVE', 'MISSED_OPPORTUNITY', 'NO_SIGNAL', 'PENDING'
            ]
            assert 'outcome_confidence' in outcome_data
            
    def test_get_outcomes_for_signal(self):
        """GET /api/v5/price-layer/outcomes/:signal_id returns outcomes"""
        # Get a signal that has outcomes
        list_response = requests.get(f"{BASE_URL}/api/v5/price-layer/signals?limit=10")
        signals = list_response.json()['data']['signals']
        
        if len(signals) > 0:
            signal_id = signals[0]['signal_id']
            response = requests.get(f"{BASE_URL}/api/v5/price-layer/outcomes/{signal_id}")
            assert response.status_code == 200
            data = response.json()
            assert data['ok'] == True
            assert 'outcomes' in data['data']


class TestCorrelationMatrix:
    """Test correlation matrix endpoint"""
    
    def test_correlation_endpoint(self):
        """GET /api/v5/price-layer/correlation should return correlation matrix"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/correlation")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        
        correlation = data['data']
        assert 'matrix' in correlation
        assert 'totals' in correlation
        
    def test_correlation_matrix_structure(self):
        """Correlation matrix entries should have required fields"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/correlation")
        data = response.json()['data']
        
        for entry in data['matrix']:
            assert 'sentiment' in entry
            assert 'direction' in entry
            assert 'horizon' in entry
            assert 'count' in entry
            assert 'avgDelta' in entry


class TestCollectFromSentiment:
    """Test integration endpoint for sentiment test harness"""
    
    def test_collect_from_sentiment_btc(self):
        """POST /api/v5/price-layer/collect-from-sentiment creates signal from sentiment"""
        payload = {
            "text": "TEST_S52_BTC is looking bullish today!",
            "sentiment": {
                "label": "POSITIVE",
                "score": 0.82,
                "confidence": 0.90
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/collect-from-sentiment",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        assert data['data']['asset'] == 'BTC'  # Default asset
        
    def test_collect_from_sentiment_eth_detection(self):
        """POST /api/v5/price-layer/collect-from-sentiment detects ETH from text"""
        payload = {
            "text": "TEST_S52_Ethereum network upgrade coming soon!",
            "sentiment": {
                "label": "POSITIVE",
                "score": 0.75,
                "confidence": 0.85
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/collect-from-sentiment",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        assert data['data']['asset'] == 'ETH'  # Detected from text
        
    def test_collect_from_sentiment_sol_detection(self):
        """POST /api/v5/price-layer/collect-from-sentiment detects SOL from text"""
        payload = {
            "text": "TEST_S52_Solana TPS hitting new records!",
            "sentiment": {
                "label": "POSITIVE",
                "score": 0.80,
                "confidence": 0.88
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/collect-from-sentiment",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        assert data['data']['asset'] == 'SOL'  # Detected from text
        
    def test_collect_from_sentiment_missing_text_returns_400(self):
        """POST /api/v5/price-layer/collect-from-sentiment without text returns 400"""
        payload = {
            "sentiment": {
                "label": "POSITIVE",
                "score": 0.82,
                "confidence": 0.90
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/collect-from-sentiment",
            json=payload
        )
        assert response.status_code == 400


class TestOutcomeLabelingLogic:
    """Test the deterministic outcome labeling logic"""
    
    def test_outcome_labels_are_valid(self):
        """All outcomes should have valid labels"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/outcomes/stats")
        data = response.json()['data']
        
        valid_labels = [
            'TRUE_POSITIVE', 'FALSE_POSITIVE', 'TRUE_NEGATIVE',
            'FALSE_NEGATIVE', 'MISSED_OPPORTUNITY', 'NO_SIGNAL', 'PENDING'
        ]
        
        for label in data['outcomesByLabel'].keys():
            assert label in valid_labels, f"Invalid outcome label: {label}"
            
    def test_accuracy_rate_is_valid(self):
        """Accuracy rate should be between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/v5/price-layer/outcomes/stats")
        data = response.json()['data']
        
        for horizon, accuracy in data['accuracyByHorizon'].items():
            assert 0 <= accuracy['rate'] <= 1, f"Invalid accuracy rate for {horizon}"
            assert accuracy['correct'] <= accuracy['total']


class TestDataPersistence:
    """Test that data is properly persisted"""
    
    def test_signal_count_increases_after_creation(self):
        """Creating a signal should increase total count"""
        # Get initial count
        stats_before = requests.get(f"{BASE_URL}/api/v5/price-layer/stats").json()['data']
        initial_count = stats_before['totalSignals']
        
        # Create new signal
        payload = {
            "asset": "BTC",
            "sentiment": {
                "label": "POSITIVE",
                "score": 0.85,
                "confidence": 0.92
            },
            "meta": {
                "text": "TEST_S52_persistence_test"
            }
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/v5/price-layer/signal",
            json=payload
        )
        assert create_response.status_code == 200
        
        # Verify count increased
        stats_after = requests.get(f"{BASE_URL}/api/v5/price-layer/stats").json()['data']
        assert stats_after['totalSignals'] == initial_count + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
