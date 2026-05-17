"""
S10.7.3 & S10.7.4 — ML Freeze & Admin UI Backend Tests

Tests:
- POST /api/v10/exchange/ml/freeze - Freeze model in MIRROR_MODE
- GET /api/v10/exchange/ml/registry - Registry state with FROZEN status
- GET /api/v10/exchange/ml/drift - Drift metrics
- POST /api/v10/exchange/ml/drift/check - Run drift check
- GET /api/v10/exchange/ml/admin/summary - Complete admin summary

S10.7.3: ML freeze in MIRROR_MODE - ML mirrors rules, used only for drift detection
S10.7.4: Admin UI endpoints for model health monitoring
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestS10_7_3_MLFreeze:
    """S10.7.3 - ML Freeze in MIRROR_MODE tests"""
    
    def test_freeze_endpoint_returns_ok(self, api_client):
        """POST /freeze should freeze model successfully"""
        response = api_client.post(f"{BASE_URL}/api/v10/exchange/ml/freeze", json={"model": "logistic"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("success") == True
        print("✓ Freeze endpoint returns ok:true, success:true")
    
    def test_freeze_sets_mirror_mode(self, api_client):
        """Freeze should set mode to MIRROR_MODE"""
        response = api_client.post(f"{BASE_URL}/api/v10/exchange/ml/freeze", json={"model": "logistic"})
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        assert registry.get("mode") == "MIRROR_MODE"
        print("✓ Model frozen in MIRROR_MODE")
    
    def test_freeze_sets_frozen_status(self, api_client):
        """Freeze should set status to FROZEN"""
        response = api_client.post(f"{BASE_URL}/api/v10/exchange/ml/freeze", json={"model": "logistic"})
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        assert registry.get("status") == "FROZEN"
        print("✓ Model status is FROZEN")
    
    def test_freeze_disables_influence_and_retrain(self, api_client):
        """Frozen model cannot influence decisions or retrain"""
        response = api_client.post(f"{BASE_URL}/api/v10/exchange/ml/freeze", json={"model": "logistic"})
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        assert registry.get("canInfluenceDecision") == False
        assert registry.get("canRetrain") == False
        print("✓ canInfluenceDecision=false, canRetrain=false")
    
    def test_freeze_returns_message(self, api_client):
        """Freeze should return success message"""
        response = api_client.post(f"{BASE_URL}/api/v10/exchange/ml/freeze", json={"model": "logistic"})
        assert response.status_code == 200
        data = response.json()
        message = data.get("message", "")
        assert "frozen successfully" in message
        assert "MIRROR_MODE" in message
        print(f"✓ Freeze message: {message}")


class TestS10_7_3_Registry:
    """S10.7.3 - Registry state tests"""
    
    def test_registry_endpoint_returns_ok(self, api_client):
        """GET /registry should return ok"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/registry")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("✓ Registry endpoint returns ok:true")
    
    def test_registry_shows_frozen_status(self, api_client):
        """Registry should show FROZEN status"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/registry")
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        assert registry.get("status") == "FROZEN"
        print("✓ Registry shows status=FROZEN")
    
    def test_registry_shows_mirror_mode(self, api_client):
        """Registry should show MIRROR_MODE"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/registry")
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        assert registry.get("mode") == "MIRROR_MODE"
        print("✓ Registry shows mode=MIRROR_MODE")
    
    def test_registry_has_version(self, api_client):
        """Registry should have version"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/registry")
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        assert "version" in registry
        assert registry.get("version") == "v1"
        print(f"✓ Registry version: {registry.get('version')}")
    
    def test_registry_has_model_type(self, api_client):
        """Registry should have modelType"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/registry")
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        assert registry.get("modelType") == "logistic"
        print(f"✓ Registry modelType: {registry.get('modelType')}")
    
    def test_registry_has_feature_count(self, api_client):
        """Registry should show 20 features"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/registry")
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        assert registry.get("featureCount") == 20
        print(f"✓ Registry featureCount: {registry.get('featureCount')}")
    
    def test_registry_has_agreement_rate(self, api_client):
        """Registry should have agreementRate"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/registry")
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        agreement = registry.get("agreementRate", 0)
        assert 0 <= agreement <= 1
        print(f"✓ Registry agreementRate: {agreement * 100:.1f}%")
    
    def test_registry_has_health_status(self, api_client):
        """Registry should have healthStatus"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/registry")
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        health = registry.get("healthStatus")
        assert health in ["STABLE", "WATCH", "DRIFT"]
        print(f"✓ Registry healthStatus: {health}")
    
    def test_registry_has_drift_status(self, api_client):
        """Registry should have driftStatus"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/registry")
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        drift = registry.get("driftStatus")
        assert drift in ["NO_DRIFT", "SOFT_DRIFT", "HARD_DRIFT"]
        print(f"✓ Registry driftStatus: {drift}")
    
    def test_registry_has_constraints(self, api_client):
        """Registry should have canInfluenceDecision and canRetrain"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/registry")
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        assert "canInfluenceDecision" in registry
        assert "canRetrain" in registry
        assert registry.get("canInfluenceDecision") == False
        assert registry.get("canRetrain") == False
        print("✓ Registry has constraints: canInfluenceDecision=false, canRetrain=false")
    
    def test_registry_has_frozen_weights(self, api_client):
        """Registry should return frozen weights info"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/registry")
        assert response.status_code == 200
        data = response.json()
        weights = data.get("frozenWeights")
        assert weights is not None
        assert weights.get("version") == "v1"
        assert weights.get("modelType") == "logistic"
        assert "thresholds" in weights
        print(f"✓ Frozen weights: version={weights.get('version')}, type={weights.get('modelType')}")


class TestS10_7_4_Drift:
    """S10.7.4 - Drift monitoring tests"""
    
    def test_drift_endpoint_returns_ok(self, api_client):
        """GET /drift should return ok"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/drift")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("✓ Drift endpoint returns ok:true")
    
    def test_drift_has_current_agreement(self, api_client):
        """Drift should have currentAgreement"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/drift")
        assert response.status_code == 200
        data = response.json()
        assert "currentAgreement" in data
        agreement = data.get("currentAgreement", 0)
        assert 0 <= agreement <= 1
        print(f"✓ Current agreement: {agreement * 100:.1f}%")
    
    def test_drift_has_baseline(self, api_client):
        """Drift should have baselineAgreement"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/drift")
        assert response.status_code == 200
        data = response.json()
        assert "baselineAgreement" in data
        print(f"✓ Baseline agreement: {data.get('baselineAgreement')}")
    
    def test_drift_has_delta(self, api_client):
        """Drift should have agreementDelta"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/drift")
        assert response.status_code == 200
        data = response.json()
        assert "agreementDelta" in data
        delta = data.get("agreementDelta", 0)
        print(f"✓ Agreement delta: {delta * 100:.2f}%")
    
    def test_drift_has_status(self, api_client):
        """Drift should have driftStatus"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/drift")
        assert response.status_code == 200
        data = response.json()
        status = data.get("driftStatus")
        assert status in ["NO_DRIFT", "SOFT_DRIFT", "HARD_DRIFT"]
        print(f"✓ Drift status: {status}")
    
    def test_drift_has_health_status(self, api_client):
        """Drift should have healthStatus"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/drift")
        assert response.status_code == 200
        data = response.json()
        health = data.get("healthStatus")
        assert health in ["STABLE", "WATCH", "DRIFT"]
        print(f"✓ Health status: {health}")
    
    def test_drift_has_samples_analyzed(self, api_client):
        """Drift should have samplesAnalyzed"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/drift")
        assert response.status_code == 200
        data = response.json()
        assert "samplesAnalyzed" in data
        samples = data.get("samplesAnalyzed", 0)
        assert samples >= 0
        print(f"✓ Samples analyzed: {samples}")
    
    def test_drift_has_feature_drift(self, api_client):
        """Drift should have featureDrift per feature"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/drift")
        assert response.status_code == 200
        data = response.json()
        feature_drift = data.get("featureDrift", {})
        assert isinstance(feature_drift, dict)
        assert len(feature_drift) >= 1  # At least one feature
        print(f"✓ Feature drift tracking {len(feature_drift)} features")


class TestS10_7_4_DriftCheck:
    """S10.7.4 - Drift check endpoint tests"""
    
    def test_drift_check_returns_ok(self, api_client):
        """POST /drift/check should return ok"""
        response = api_client.post(f"{BASE_URL}/api/v10/exchange/ml/drift/check", json={"model": "logistic"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("✓ Drift check returns ok:true")
    
    def test_drift_check_returns_previous_agreement(self, api_client):
        """Drift check should return previousAgreement"""
        response = api_client.post(f"{BASE_URL}/api/v10/exchange/ml/drift/check", json={"model": "logistic"})
        assert response.status_code == 200
        data = response.json()
        assert "previousAgreement" in data
        print(f"✓ Previous agreement: {data.get('previousAgreement')}")
    
    def test_drift_check_returns_current_agreement(self, api_client):
        """Drift check should return currentAgreement"""
        response = api_client.post(f"{BASE_URL}/api/v10/exchange/ml/drift/check", json={"model": "logistic"})
        assert response.status_code == 200
        data = response.json()
        assert "currentAgreement" in data
        print(f"✓ Current agreement: {data.get('currentAgreement')}")
    
    def test_drift_check_returns_drift_detected(self, api_client):
        """Drift check should return driftDetected boolean"""
        response = api_client.post(f"{BASE_URL}/api/v10/exchange/ml/drift/check", json={"model": "logistic"})
        assert response.status_code == 200
        data = response.json()
        assert "driftDetected" in data
        assert isinstance(data.get("driftDetected"), bool)
        print(f"✓ Drift detected: {data.get('driftDetected')}")
    
    def test_drift_check_returns_drift_status(self, api_client):
        """Drift check should return driftStatus"""
        response = api_client.post(f"{BASE_URL}/api/v10/exchange/ml/drift/check", json={"model": "logistic"})
        assert response.status_code == 200
        data = response.json()
        status = data.get("driftStatus")
        assert status in ["NO_DRIFT", "SOFT_DRIFT", "HARD_DRIFT"]
        print(f"✓ Drift check status: {status}")


class TestS10_7_4_AdminSummary:
    """S10.7.4 - Admin summary endpoint tests"""
    
    def test_admin_summary_returns_ok(self, api_client):
        """GET /admin/summary should return ok"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/admin/summary")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("✓ Admin summary returns ok:true")
    
    def test_admin_summary_has_registry(self, api_client):
        """Admin summary should include registry"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/admin/summary")
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        assert "mode" in registry
        assert "status" in registry
        assert "healthStatus" in registry
        print(f"✓ Registry: mode={registry.get('mode')}, status={registry.get('status')}")
    
    def test_admin_summary_has_models(self, api_client):
        """Admin summary should include models info"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/admin/summary")
        assert response.status_code == 200
        data = response.json()
        models = data.get("models", {})
        assert "logistic" in models or "tree" in models
        if models.get("logistic"):
            assert "accuracy" in models["logistic"]
            print(f"✓ Logistic model accuracy: {models['logistic'].get('accuracy')}")
        if models.get("tree"):
            assert "accuracy" in models["tree"]
            print(f"✓ Tree model accuracy: {models['tree'].get('accuracy')}")
    
    def test_admin_summary_has_comparison(self, api_client):
        """Admin summary should include last comparison"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/admin/summary")
        assert response.status_code == 200
        data = response.json()
        comparison = data.get("lastComparison")
        if comparison:
            assert "agreementRate" in comparison
            assert "disagreementCount" in comparison
            print(f"✓ Comparison: agreement={comparison.get('agreementRate')}, disagreements={comparison.get('disagreementCount')}")
        else:
            print("! No comparison data (train models first)")
    
    def test_admin_summary_has_drift(self, api_client):
        """Admin summary should include drift metrics"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/admin/summary")
        assert response.status_code == 200
        data = response.json()
        drift = data.get("drift", {})
        assert "currentAgreement" in drift
        assert "driftStatus" in drift
        assert "healthStatus" in drift
        print(f"✓ Drift: status={drift.get('driftStatus')}, health={drift.get('healthStatus')}")
    
    def test_admin_summary_has_feature_importance(self, api_client):
        """Admin summary should include feature importance"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/admin/summary")
        assert response.status_code == 200
        data = response.json()
        importance = data.get("featureImportance", [])
        assert isinstance(importance, list)
        if len(importance) > 0:
            # Check first feature has required fields
            first = importance[0]
            assert "feature" in first
            assert "rulesWeight" in first
            assert "mlWeight" in first
            print(f"✓ Feature importance: {len(importance)} features tracked")
            print(f"  Top feature: {first.get('feature')} (rules={first.get('rulesWeight'):.2f}, ml={first.get('mlWeight'):.2f})")
        else:
            print("! No feature importance data (train models first)")
    
    def test_admin_summary_registry_constraints(self, api_client):
        """Admin summary registry should show ML constraints"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/admin/summary")
        assert response.status_code == 200
        data = response.json()
        registry = data.get("registry", {})
        assert registry.get("canInfluenceDecision") == False
        assert registry.get("canRetrain") == False
        print("✓ Admin summary confirms: canInfluenceDecision=false, canRetrain=false")
    
    def test_admin_summary_complete_structure(self, api_client):
        """Admin summary should have all required sections"""
        response = api_client.get(f"{BASE_URL}/api/v10/exchange/ml/admin/summary")
        assert response.status_code == 200
        data = response.json()
        
        # All required top-level keys
        required_keys = ["ok", "registry", "models", "drift", "featureImportance"]
        for key in required_keys:
            assert key in data, f"Missing required key: {key}"
        
        print("✓ Admin summary has complete structure")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
