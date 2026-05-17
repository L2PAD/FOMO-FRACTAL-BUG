"""
S10.7.2 — Baseline Rules vs ML Comparison Testing
Tests ML training and comparison endpoints for comparing rules-based labeling vs ML models

Endpoints tested:
- POST /api/v10/exchange/ml/train - Train both Logistic Regression and Decision Tree models
- GET /api/v10/exchange/ml/compare - Compare rules vs ML, returns agreement rate and verdict
- GET /api/v10/exchange/ml/confusion - Returns confusion matrices for model and rules vs ML
- GET /api/v10/exchange/ml/features/importance - Compare feature importance rules vs ML
- GET /api/v10/exchange/ml/cases/disagreement - Returns cases where rules != ML
- GET /api/v10/exchange/ml/stability - Checks ML stability vs noise

Verdict Logic:
- RULES_SUFFICIENT: agreement >= 85%
- ML_ADDS_VALUE: agreement 70-85% AND accuracy >= 80%
- NEEDS_ANALYSIS: agreement < 70%
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

VALID_LABELS = ['USE', 'IGNORE', 'WARNING']
VALID_MODELS = ['logistic', 'tree']
VALID_VERDICTS = ['RULES_SUFFICIENT', 'ML_ADDS_VALUE', 'NEEDS_ANALYSIS', 'NEUTRAL']


class TestMLTraining:
    """Test ML training endpoint - POST /api/v10/exchange/ml/train"""

    def test_train_returns_ok(self):
        """POST /api/v10/exchange/ml/train returns ok: true"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/train",
            json={"limit": 100}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok: true, got {data}"

    def test_train_returns_both_models(self):
        """Training returns both logistic and tree model results"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/train",
            json={"limit": 100}
        )
        assert response.status_code == 200
        
        data = response.json()
        models = data.get('models', {})
        
        # Both models should be present
        assert 'logistic' in models, "Missing logistic model results"
        assert 'tree' in models, "Missing tree model results"
        
        # Each model should have accuracy and training size
        for model_type in ['logistic', 'tree']:
            model = models[model_type]
            assert 'accuracy' in model, f"Missing accuracy for {model_type}"
            assert 'trainingSize' in model, f"Missing trainingSize for {model_type}"
            
            # Accuracy should be 0-1
            assert 0 <= model['accuracy'] <= 1, f"Invalid accuracy for {model_type}: {model['accuracy']}"
            
            # Training size should be positive
            assert model['trainingSize'] > 0, f"Training size should be positive for {model_type}"

    def test_train_returns_data_size(self):
        """Training returns total data size used"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/train",
            json={"limit": 50}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert 'message' in data, "Missing message"
        
        # Message should contain data size info
        assert 'Training complete' in data.get('message', ''), "Message should indicate training complete"

    def test_train_with_symbol_filter(self):
        """Training can be filtered by symbol"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/train",
            json={"symbol": "BTCUSDT", "limit": 50}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True

    def test_train_models_accuracy(self):
        """Both models achieve reasonable accuracy on training data"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/train",
            json={"limit": 100}
        )
        assert response.status_code == 200
        
        data = response.json()
        models = data.get('models', {})
        
        # Both models should achieve at least 50% accuracy (better than random)
        logistic_acc = models.get('logistic', {}).get('accuracy', 0)
        tree_acc = models.get('tree', {}).get('accuracy', 0)
        
        assert logistic_acc >= 0.5, f"Logistic accuracy too low: {logistic_acc}"
        assert tree_acc >= 0.5, f"Tree accuracy too low: {tree_acc}"


class TestMLComparison:
    """Test ML comparison endpoint - GET /api/v10/exchange/ml/compare"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure models are trained before comparison tests"""
        requests.post(f"{BASE_URL}/api/v10/exchange/ml/train", json={"limit": 100})

    def test_compare_returns_ok(self):
        """GET /api/v10/exchange/ml/compare returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok: true, got {data}"

    def test_compare_returns_agreement_rate(self):
        """Comparison returns agreement rate between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare")
        assert response.status_code == 200
        
        data = response.json()
        comparison = data.get('comparison', {})
        
        assert 'agreementRate' in comparison, "Missing agreementRate"
        rate = comparison['agreementRate']
        assert 0 <= rate <= 1, f"Agreement rate should be 0-1, got {rate}"

    def test_compare_returns_verdict(self):
        """Comparison returns verdict recommendation"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare")
        assert response.status_code == 200
        
        data = response.json()
        comparison = data.get('comparison', {})
        verdict = comparison.get('verdict', {})
        
        assert 'recommendation' in verdict, "Missing verdict recommendation"
        assert verdict['recommendation'] in VALID_VERDICTS, f"Invalid verdict: {verdict['recommendation']}"
        assert 'mlValueAdded' in verdict, "Missing mlValueAdded field"
        assert 'reason' in verdict, "Missing verdict reason"

    def test_compare_verdict_logic_rules_sufficient(self):
        """If agreement >= 85%, verdict should be RULES_SUFFICIENT"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare")
        assert response.status_code == 200
        
        data = response.json()
        comparison = data.get('comparison', {})
        agreement_rate = comparison.get('agreementRate', 0)
        verdict = comparison.get('verdict', {})
        
        if agreement_rate >= 0.85:
            assert verdict['recommendation'] == 'RULES_SUFFICIENT', \
                f"With agreement {agreement_rate*100:.1f}%, verdict should be RULES_SUFFICIENT"
            assert verdict['mlValueAdded'] is False

    def test_compare_returns_confusion_matrix_structure(self):
        """Comparison returns rules vs ML confusion matrix"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare")
        assert response.status_code == 200
        
        data = response.json()
        comparison = data.get('comparison', {})
        
        assert 'rulesVsMlMatrix' in comparison, "Missing rulesVsMlMatrix"
        matrix_data = comparison['rulesVsMlMatrix']
        
        assert 'matrix' in matrix_data, "Missing matrix in rulesVsMlMatrix"
        assert 'total' in matrix_data, "Missing total in rulesVsMlMatrix"

    def test_compare_returns_disagreement_count(self):
        """Comparison returns disagreement count"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare")
        assert response.status_code == 200
        
        data = response.json()
        comparison = data.get('comparison', {})
        
        assert 'disagreementCount' in comparison, "Missing disagreementCount"
        assert isinstance(comparison['disagreementCount'], int), "disagreementCount should be int"

    def test_compare_with_logistic_model(self):
        """Comparison works with logistic model (default)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare?model=logistic")
        assert response.status_code == 200
        
        data = response.json()
        comparison = data.get('comparison', {})
        
        assert comparison.get('modelType') == 'logistic', "Should use logistic model"

    def test_compare_with_tree_model(self):
        """Comparison works with decision tree model"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare?model=tree")
        assert response.status_code == 200
        
        data = response.json()
        comparison = data.get('comparison', {})
        
        assert comparison.get('modelType') == 'tree', "Should use tree model"

    def test_compare_returns_label_agreement(self):
        """Comparison returns per-label agreement rates"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare")
        assert response.status_code == 200
        
        data = response.json()
        comparison = data.get('comparison', {})
        
        assert 'labelAgreement' in comparison, "Missing labelAgreement"
        label_agreement = comparison['labelAgreement']
        
        for label in VALID_LABELS:
            assert label in label_agreement, f"Missing agreement for {label}"


class TestMLConfusionMatrix:
    """Test ML confusion matrix endpoint - GET /api/v10/exchange/ml/confusion"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure models are trained"""
        requests.post(f"{BASE_URL}/api/v10/exchange/ml/train", json={"limit": 100})

    def test_confusion_returns_ok(self):
        """GET /api/v10/exchange/ml/confusion returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/confusion")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok: true, got {data}"

    def test_confusion_returns_model_matrix(self):
        """Confusion matrix includes model's confusion matrix"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/confusion")
        assert response.status_code == 200
        
        data = response.json()
        
        assert 'model' in data, "Missing model section"
        model = data['model']
        
        assert 'type' in model, "Missing model type"
        assert 'accuracy' in model, "Missing model accuracy"
        assert 'confusionMatrix' in model, "Missing model confusionMatrix"

    def test_confusion_returns_rules_vs_ml_matrix(self):
        """Confusion matrix includes rules vs ML matrix"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/confusion")
        assert response.status_code == 200
        
        data = response.json()
        
        assert 'rulesVsML' in data, "Missing rulesVsML section"

    def test_confusion_with_logistic_model(self):
        """Confusion matrix works with logistic model"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/confusion?model=logistic")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('model', {}).get('type') == 'logistic'

    def test_confusion_with_tree_model(self):
        """Confusion matrix works with tree model"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/confusion?model=tree")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('model', {}).get('type') == 'tree'


class TestMLFeatureImportance:
    """Test ML feature importance endpoint - GET /api/v10/exchange/ml/features/importance"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure models are trained"""
        requests.post(f"{BASE_URL}/api/v10/exchange/ml/train", json={"limit": 100})

    def test_feature_importance_returns_ok(self):
        """GET /api/v10/exchange/ml/features/importance returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/features/importance")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok: true, got {data}"

    def test_feature_importance_returns_model_type(self):
        """Feature importance returns model type used"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/features/importance")
        assert response.status_code == 200
        
        data = response.json()
        assert 'modelType' in data, "Missing modelType"
        assert data['modelType'] in VALID_MODELS, f"Invalid model type: {data['modelType']}"

    def test_feature_importance_returns_feature_count(self):
        """Feature importance returns feature count"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/features/importance")
        assert response.status_code == 200
        
        data = response.json()
        assert 'featureCount' in data, "Missing featureCount"
        assert data['featureCount'] == 20, f"Expected 20 features, got {data['featureCount']}"

    def test_feature_importance_returns_features_array(self):
        """Feature importance returns features array with rules vs ML comparison"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/features/importance")
        assert response.status_code == 200
        
        data = response.json()
        features = data.get('features', [])
        
        assert len(features) > 0, "Should have features"
        
        # Check structure of each feature
        for feature in features:
            assert 'feature' in feature, "Missing feature name"
            assert 'rulesWeight' in feature, "Missing rulesWeight"
            assert 'mlWeight' in feature, "Missing mlWeight"
            assert 'agreement' in feature, "Missing agreement"
            
            # Weights should be 0-1
            assert 0 <= feature['rulesWeight'] <= 1, f"Invalid rulesWeight for {feature['feature']}"
            assert 0 <= feature['mlWeight'] <= 1, f"Invalid mlWeight for {feature['feature']}"
            assert 0 <= feature['agreement'] <= 1, f"Invalid agreement for {feature['feature']}"

    def test_feature_importance_logistic_model(self):
        """Feature importance works with logistic model"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/features/importance?model=logistic")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('modelType') == 'logistic'

    def test_feature_importance_tree_model(self):
        """Feature importance works with tree model"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/features/importance?model=tree")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('modelType') == 'tree'


class TestMLDisagreementCases:
    """Test ML disagreement cases endpoint - GET /api/v10/exchange/ml/cases/disagreement"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure models are trained"""
        requests.post(f"{BASE_URL}/api/v10/exchange/ml/train", json={"limit": 100})

    def test_disagreement_returns_ok(self):
        """GET /api/v10/exchange/ml/cases/disagreement returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/cases/disagreement")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok: true, got {data}"

    def test_disagreement_returns_model_type(self):
        """Disagreement cases returns model type"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/cases/disagreement")
        assert response.status_code == 200
        
        data = response.json()
        assert 'modelType' in data, "Missing modelType"
        assert data['modelType'] in VALID_MODELS

    def test_disagreement_returns_count(self):
        """Disagreement cases returns count"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/cases/disagreement")
        assert response.status_code == 200
        
        data = response.json()
        assert 'count' in data, "Missing count"
        assert isinstance(data['count'], int), "count should be int"
        assert data['count'] >= 0, "count should be non-negative"

    def test_disagreement_returns_cases_array(self):
        """Disagreement cases returns cases array"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/cases/disagreement")
        assert response.status_code == 200
        
        data = response.json()
        cases = data.get('cases', [])
        
        assert isinstance(cases, list), "cases should be an array"
        
        # Check structure if there are cases
        if len(cases) > 0:
            case = cases[0]
            assert 'observationId' in case, "Case missing observationId"
            assert 'rulesLabel' in case, "Case missing rulesLabel"
            assert 'mlLabel' in case, "Case missing mlLabel"
            assert 'mlConfidence' in case, "Case missing mlConfidence"
            assert 'regime' in case, "Case missing regime"
            
            # Labels should be different (that's what makes it a disagreement)
            assert case['rulesLabel'] != case['mlLabel'], "Disagreement case should have different labels"

    def test_disagreement_with_limit(self):
        """Disagreement cases respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/cases/disagreement?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        cases = data.get('cases', [])
        
        assert len(cases) <= 5, f"Should return at most 5 cases, got {len(cases)}"

    def test_disagreement_logistic_model(self):
        """Disagreement cases works with logistic model"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/cases/disagreement?model=logistic")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('modelType') == 'logistic'

    def test_disagreement_tree_model(self):
        """Disagreement cases works with tree model"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/cases/disagreement?model=tree")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('modelType') == 'tree'


class TestMLStability:
    """Test ML stability endpoint - GET /api/v10/exchange/ml/stability"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure models are trained"""
        requests.post(f"{BASE_URL}/api/v10/exchange/ml/train", json={"limit": 100})

    def test_stability_returns_ok(self):
        """GET /api/v10/exchange/ml/stability returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/stability")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok: true, got {data}"

    def test_stability_returns_model_type(self):
        """Stability check returns model type"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/stability")
        assert response.status_code == 200
        
        data = response.json()
        assert 'modelType' in data, "Missing modelType"
        assert data['modelType'] in VALID_MODELS

    def test_stability_returns_ml_stability(self):
        """Stability check returns ML stability score"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/stability")
        assert response.status_code == 200
        
        data = response.json()
        assert 'mlStability' in data, "Missing mlStability"
        
        stability = data['mlStability']
        assert 0 <= stability <= 1, f"ML stability should be 0-1, got {stability}"

    def test_stability_returns_rules_stability(self):
        """Stability check returns rules stability score"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/stability")
        assert response.status_code == 200
        
        data = response.json()
        assert 'rulesStability' in data, "Missing rulesStability"
        
        stability = data['rulesStability']
        assert 0 <= stability <= 1, f"Rules stability should be 0-1, got {stability}"

    def test_stability_returns_unstable_features(self):
        """Stability check returns unstable features list"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/stability")
        assert response.status_code == 200
        
        data = response.json()
        assert 'unstableFeatures' in data, "Missing unstableFeatures"
        
        unstable = data['unstableFeatures']
        assert isinstance(unstable, list), "unstableFeatures should be an array"

    def test_stability_logistic_model(self):
        """Stability check works with logistic model"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/stability?model=logistic")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('modelType') == 'logistic'

    def test_stability_tree_model(self):
        """Stability check works with tree model"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/stability?model=tree")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('modelType') == 'tree'


class TestVerdictLogic:
    """Test verdict logic based on agreement and accuracy thresholds"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure models are trained with enough data"""
        # Seed more observations for better testing
        requests.post(
            f"{BASE_URL}/api/admin/exchange/observation/seed",
            json={"count": 50}
        )
        requests.post(f"{BASE_URL}/api/v10/exchange/ml/train", json={"limit": 200})

    def test_verdict_present(self):
        """Comparison always returns a verdict"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare")
        assert response.status_code == 200
        
        data = response.json()
        verdict = data.get('comparison', {}).get('verdict', {})
        
        assert 'recommendation' in verdict
        assert verdict['recommendation'] in VALID_VERDICTS

    def test_verdict_consistency_with_agreement(self):
        """Verdict is consistent with agreement rate"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare")
        assert response.status_code == 200
        
        data = response.json()
        comparison = data.get('comparison', {})
        agreement = comparison.get('agreementRate', 0)
        accuracy = comparison.get('modelAccuracy', 0)
        verdict = comparison.get('verdict', {})
        recommendation = verdict.get('recommendation', '')
        
        # Log values for debugging
        print(f"Agreement: {agreement*100:.1f}%, Accuracy: {accuracy*100:.1f}%, Verdict: {recommendation}")
        
        # Check verdict logic
        if agreement >= 0.85:
            assert recommendation == 'RULES_SUFFICIENT', \
                f"With agreement {agreement*100:.1f}%, expected RULES_SUFFICIENT, got {recommendation}"
        elif agreement >= 0.7 and accuracy >= 0.8:
            assert recommendation == 'ML_ADDS_VALUE', \
                f"With agreement {agreement*100:.1f}% and accuracy {accuracy*100:.1f}%, expected ML_ADDS_VALUE"
        elif agreement < 0.7:
            assert recommendation == 'NEEDS_ANALYSIS', \
                f"With agreement {agreement*100:.1f}%, expected NEEDS_ANALYSIS"

    def test_both_models_produce_verdicts(self):
        """Both logistic and tree models produce valid verdicts"""
        for model in ['logistic', 'tree']:
            response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare?model={model}")
            assert response.status_code == 200, f"Failed for {model}"
            
            data = response.json()
            verdict = data.get('comparison', {}).get('verdict', {})
            
            assert verdict.get('recommendation') in VALID_VERDICTS, \
                f"{model} model produced invalid verdict: {verdict}"


class TestMLModelSelection:
    """Test that model selection works correctly via ?model= parameter"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure models are trained"""
        requests.post(f"{BASE_URL}/api/v10/exchange/ml/train", json={"limit": 100})

    def test_default_model_is_logistic(self):
        """Default model selection is logistic"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('comparison', {}).get('modelType') == 'logistic'

    def test_model_parameter_logistic(self):
        """?model=logistic selects logistic model"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare?model=logistic")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('comparison', {}).get('modelType') == 'logistic'

    def test_model_parameter_tree(self):
        """?model=tree selects decision tree model"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/compare?model=tree")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('comparison', {}).get('modelType') == 'tree'

    def test_all_endpoints_support_model_selection(self):
        """All ML endpoints support ?model= parameter"""
        endpoints = [
            '/api/v10/exchange/ml/compare',
            '/api/v10/exchange/ml/confusion',
            '/api/v10/exchange/ml/features/importance',
            '/api/v10/exchange/ml/cases/disagreement',
            '/api/v10/exchange/ml/stability',
        ]
        
        for endpoint in endpoints:
            for model in ['logistic', 'tree']:
                response = requests.get(f"{BASE_URL}{endpoint}?model={model}")
                assert response.status_code == 200, f"Failed: {endpoint}?model={model}"
                
                data = response.json()
                assert data.get('ok') is True, f"Expected ok for {endpoint}?model={model}"


class TestMLStatusAfterTraining:
    """Test that ML status updates after training"""

    def test_status_shows_trained_models(self):
        """After training, status shows both trained models"""
        # Train first
        train_response = requests.post(
            f"{BASE_URL}/api/v10/exchange/ml/train",
            json={"limit": 100}
        )
        assert train_response.status_code == 200
        
        # Check status
        status_response = requests.get(f"{BASE_URL}/api/v10/exchange/ml/status")
        assert status_response.status_code == 200
        
        data = status_response.json()
        models = data.get('models', {})
        
        # Both models should now be present
        assert models.get('logistic') is not None, "Logistic model should be present after training"
        assert models.get('tree') is not None, "Tree model should be present after training"
        
        # Check model details
        for model_type in ['logistic', 'tree']:
            model = models[model_type]
            assert 'type' in model, f"Missing type for {model_type}"
            assert 'accuracy' in model, f"Missing accuracy for {model_type}"
            assert 'trainedAt' in model, f"Missing trainedAt for {model_type}"
            assert 'trainingSize' in model, f"Missing trainingSize for {model_type}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
