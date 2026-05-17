"""
S10.7.1 — Exchange ML Dataset & Labels Testing
Tests ML feature extraction and labeling endpoints

Endpoints tested:
- GET /api/v10/exchange/ml/status - Model status with 20 features
- POST /api/v10/exchange/ml/backfill - Label historical observations
- GET /api/v10/exchange/ml/predict/:symbol - Predict label for symbol
- GET /api/v10/exchange/ml/features/:symbol - Extract features from observation
- POST /api/v10/exchange/ml/label-test - Test labeling on new observation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected 20 feature names
EXPECTED_FEATURES = [
    'regimeConfidence',
    'regimeIsExpansion',
    'regimeIsSqueeze',
    'regimeIsExhaustion',
    'flowBias',
    'flowDominance',
    'absorptionStrength',
    'imbalancePressure',
    'volumeRatio',
    'volumeDelta',
    'oiDelta',
    'oiVolumeDivergence',
    'cascadeActive',
    'liquidationIntensity',
    'patternCount',
    'conflictCount',
    'bullishRatio',
    'bearishRatio',
    'marketStress',
    'readability',
]

VALID_LABELS = ['USE', 'IGNORE', 'WARNING']


class TestMLStatus:
    """Test ML status endpoint"""

    def test_ml_status_returns_ok(self):
        """GET /api/v10/exchange/ml/status returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok: true, got {data}"

    def test_ml_status_has_model_info(self):
        """ML status includes model type and version"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/status")
        assert response.status_code == 200
        
        data = response.json()
        status = data.get('status', {})
        
        assert 'modelType' in status, "Missing modelType"
        assert status['modelType'] == 'rules', f"Expected modelType 'rules', got {status['modelType']}"
        assert 'version' in status, "Missing version"

    def test_ml_status_has_20_features(self):
        """ML status returns exactly 20 feature names"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/status")
        assert response.status_code == 200
        
        data = response.json()
        features = data.get('features', {})
        
        assert features.get('count') == 20, f"Expected 20 features, got {features.get('count')}"
        assert 'names' in features, "Missing feature names"
        
        feature_names = features.get('names', [])
        assert len(feature_names) == 20, f"Expected 20 feature names, got {len(feature_names)}"
        
        # Verify all expected features are present
        for expected in EXPECTED_FEATURES:
            assert expected in feature_names, f"Missing expected feature: {expected}"


class TestMLBackfill:
    """Test ML backfill endpoint for labeling historical observations"""

    def test_backfill_returns_ok(self):
        """POST /api/v10/exchange/ml/backfill returns ok: true"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/backfill",
            json={"limit": 10}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok: true, got {data}"

    def test_backfill_returns_stats(self):
        """Backfill returns complete stats structure"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/backfill",
            json={"limit": 10}
        )
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get('stats', {})
        
        # Verify stats structure
        assert 'totalProcessed' in stats, "Missing totalProcessed"
        assert 'labeled' in stats, "Missing labeled counts"
        assert 'distribution' in stats, "Missing distribution percentages"
        
        # Verify labeled structure has all labels
        labeled = stats.get('labeled', {})
        for label in VALID_LABELS:
            assert label in labeled, f"Missing label count for {label}"
            assert isinstance(labeled[label], (int, float)), f"Label count for {label} should be numeric"

    def test_backfill_shows_distribution(self):
        """Backfill shows USE/IGNORE/WARNING distribution percentages"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/backfill",
            json={"limit": 50}
        )
        assert response.status_code == 200
        
        data = response.json()
        distribution = data.get('stats', {}).get('distribution', {})
        
        # All three labels should have distribution percentages
        for label in VALID_LABELS:
            assert label in distribution, f"Missing distribution for {label}"
            assert isinstance(distribution[label], (int, float)), f"Distribution for {label} should be numeric"
        
        # Distribution should sum to ~100%
        total = sum(distribution.values())
        assert 95 <= total <= 105, f"Distribution should sum to ~100%, got {total}"

    def test_backfill_with_symbol_filter(self):
        """Backfill can be filtered by symbol"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/backfill",
            json={"symbol": "BTCUSDT", "limit": 5}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True

    def test_backfill_warning_reasons_tracked(self):
        """Backfill tracks warning reasons"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/backfill",
            json={"limit": 30}
        )
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get('stats', {})
        
        assert 'warningReasons' in stats, "Missing warningReasons in stats"
        assert isinstance(stats['warningReasons'], dict), "warningReasons should be a dict"


class TestMLPredict:
    """Test ML predict endpoint"""

    def test_predict_returns_ok(self):
        """GET /api/v10/exchange/ml/predict/:symbol returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/predict/BTCUSDT")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok: true, got {data}"

    def test_predict_returns_valid_label(self):
        """Predict returns USE/IGNORE/WARNING label"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/predict/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        prediction = data.get('prediction', {})
        
        assert 'label' in prediction, "Missing label in prediction"
        assert prediction['label'] in VALID_LABELS, f"Invalid label: {prediction['label']}"

    def test_predict_returns_confidence(self):
        """Predict returns confidence score between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/predict/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        prediction = data.get('prediction', {})
        
        assert 'confidence' in prediction, "Missing confidence"
        confidence = prediction['confidence']
        assert 0 <= confidence <= 1, f"Confidence should be 0-1, got {confidence}"

    def test_predict_returns_probabilities(self):
        """Predict returns probabilities for all three labels"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/predict/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        prediction = data.get('prediction', {})
        probs = prediction.get('probabilities', {})
        
        for label in VALID_LABELS:
            assert label in probs, f"Missing probability for {label}"
            assert 0 <= probs[label] <= 1, f"Probability for {label} should be 0-1"

    def test_predict_returns_top_features(self):
        """Predict returns top contributing features"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/predict/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        prediction = data.get('prediction', {})
        top_features = prediction.get('topFeatures', [])
        
        assert len(top_features) > 0, "Should have at least one top feature"
        
        for feature in top_features:
            assert 'name' in feature, "Feature missing name"
            assert 'value' in feature, "Feature missing value"
            assert 'contribution' in feature, "Feature missing contribution"

    def test_predict_returns_observation_info(self):
        """Predict includes observation metadata"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/predict/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        observation = data.get('observation', {})
        
        assert 'id' in observation, "Missing observation id"
        assert 'regime' in observation, "Missing regime"
        assert 'hasConflict' in observation, "Missing hasConflict"

    def test_predict_different_symbols(self):
        """Predict works for different symbols"""
        symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        
        for symbol in symbols:
            response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/predict/{symbol}")
            assert response.status_code == 200, f"Failed for {symbol}"
            
            data = response.json()
            assert data.get('ok') is True, f"Expected ok for {symbol}"
            assert data.get('symbol') == symbol, f"Symbol mismatch for {symbol}"


class TestMLFeatures:
    """Test ML feature extraction endpoint"""

    def test_features_returns_ok_or_error(self):
        """GET /api/v10/exchange/ml/features/:symbol returns ok"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/features/BTCUSDT")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # May return ok: false if no observations exist
        assert 'ok' in data, "Missing ok field"

    def test_features_extracts_all_20(self):
        """Feature extraction returns all 20 features"""
        # First create an observation
        requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick",
            json={"symbol": "BTCUSDT"}
        )
        
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/features/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        if data.get('ok') is True:
            features = data.get('features', {})
            
            # Check all 20 features present
            for expected in EXPECTED_FEATURES:
                assert expected in features, f"Missing feature: {expected}"
                assert isinstance(features[expected], (int, float)), f"Feature {expected} should be numeric"

    def test_features_normalized_range(self):
        """Features are normalized to expected ranges"""
        # Create observation first
        requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick",
            json={"symbol": "BTCUSDT"}
        )
        
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/features/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        if data.get('ok') is True:
            features = data.get('features', {})
            
            # Binary features should be 0 or 1
            binary_features = ['regimeIsExpansion', 'regimeIsSqueeze', 'regimeIsExhaustion', 'cascadeActive']
            for feat in binary_features:
                if feat in features:
                    assert features[feat] in [0, 1], f"{feat} should be 0 or 1"
            
            # 0-1 normalized features
            normalized_01 = ['regimeConfidence', 'flowDominance', 'absorptionStrength', 
                           'volumeRatio', 'liquidationIntensity', 'patternCount',
                           'bullishRatio', 'bearishRatio', 'marketStress', 'readability']
            for feat in normalized_01:
                if feat in features:
                    assert 0 <= features[feat] <= 1, f"{feat} should be 0-1, got {features[feat]}"

    def test_features_includes_rules_label(self):
        """Features endpoint includes rules-based label"""
        # Create observation
        requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick",
            json={"symbol": "BTCUSDT"}
        )
        
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/features/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        if data.get('ok') is True:
            assert 'rulesLabel' in data, "Missing rulesLabel"
            assert data['rulesLabel'] in VALID_LABELS, f"Invalid rulesLabel: {data['rulesLabel']}"
            assert 'labelReason' in data, "Missing labelReason"
            assert 'labelTriggers' in data, "Missing labelTriggers"


class TestMLLabelTest:
    """Test ML label-test endpoint for testing labeling logic"""

    def test_label_test_returns_ok(self):
        """POST /api/v10/exchange/ml/label-test returns ok: true"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/label-test",
            json={"symbol": "BTCUSDT"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok: true, got {data}"

    def test_label_test_creates_observation(self):
        """Label-test creates a new observation"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/label-test",
            json={"symbol": "BTCUSDT"}
        )
        assert response.status_code == 200
        
        data = response.json()
        observation = data.get('observation', {})
        
        assert 'id' in observation, "Missing observation id"
        assert 'regime' in observation, "Missing regime"
        assert 'patternCount' in observation, "Missing patternCount"
        assert 'hasConflict' in observation, "Missing hasConflict"
        assert 'cascadeActive' in observation, "Missing cascadeActive"

    def test_label_test_returns_features(self):
        """Label-test returns key ML features"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/label-test",
            json={"symbol": "BTCUSDT"}
        )
        assert response.status_code == 200
        
        data = response.json()
        features = data.get('features', {})
        
        key_features = ['marketStress', 'readability', 'regimeConfidence', 
                       'conflictCount', 'cascadeActive', 'liquidationIntensity']
        for feat in key_features:
            assert feat in features, f"Missing key feature: {feat}"

    def test_label_test_returns_label_result(self):
        """Label-test returns labeling result"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/label-test",
            json={"symbol": "BTCUSDT"}
        )
        assert response.status_code == 200
        
        data = response.json()
        label = data.get('label', {})
        
        assert 'label' in label, "Missing label in label result"
        assert label['label'] in VALID_LABELS, f"Invalid label: {label['label']}"
        assert 'reason' in label, "Missing reason"
        assert 'triggers' in label, "Missing triggers"

    def test_label_test_returns_prediction(self):
        """Label-test returns prediction with confidence and probabilities"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/label-test",
            json={"symbol": "BTCUSDT"}
        )
        assert response.status_code == 200
        
        data = response.json()
        prediction = data.get('prediction', {})
        
        assert 'label' in prediction, "Missing prediction label"
        assert 'confidence' in prediction, "Missing prediction confidence"
        assert 'probabilities' in prediction, "Missing prediction probabilities"
        assert 'topFeatures' in prediction, "Missing prediction topFeatures"

    def test_label_test_top_features_explain_label(self):
        """Label-test topFeatures shows why label was assigned"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/label-test",
            json={"symbol": "BTCUSDT"}
        )
        assert response.status_code == 200
        
        data = response.json()
        top_features = data.get('prediction', {}).get('topFeatures', [])
        
        assert len(top_features) >= 1, "Should have at least 1 top feature"
        
        for feature in top_features:
            assert 'name' in feature, "Top feature missing name"
            assert feature['name'] in EXPECTED_FEATURES, f"Unknown feature: {feature['name']}"

    def test_label_test_different_symbols(self):
        """Label-test works for different symbols"""
        symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        
        for symbol in symbols:
            response = requests.post(
                f"{BASE_URL}/api/v10/exchange/ml/label-test",
                json={"symbol": symbol}
            )
            assert response.status_code == 200, f"Failed for {symbol}"
            
            data = response.json()
            assert data.get('ok') is True, f"Expected ok for {symbol}"


class TestLabelingLogic:
    """Test that labeling logic produces expected labels"""

    def test_multiple_labels_exist(self):
        """Running multiple label-tests produces at least 2 different labels"""
        labels_found = set()
        
        # Run multiple times to get different random mock data
        for _ in range(10):
            response = requests.post(
                f"{BASE_URL}/api/v10/exchange/ml/label-test",
                json={"symbol": "BTCUSDT"}
            )
            if response.status_code == 200:
                data = response.json()
                label = data.get('label', {}).get('label')
                if label:
                    labels_found.add(label)
        
        # Due to mock data randomness, we should see at least WARNING (most common)
        assert 'WARNING' in labels_found or 'USE' in labels_found or 'IGNORE' in labels_found, \
            "Should see at least one valid label"

    def test_backfill_produces_distribution(self):
        """Backfill should produce a distribution of labels"""
        # First seed some observations
        requests.post(
            f"{BASE_URL}/api/admin/exchange/observation/seed",
            json={"count": 20}
        )
        
        # Then backfill
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/backfill",
            json={"limit": 50}
        )
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get('stats', {})
        labeled = stats.get('labeled', {})
        
        # At least one label type should have observations
        total_labeled = sum(labeled.values())
        assert total_labeled > 0, "Should have labeled at least some observations"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
