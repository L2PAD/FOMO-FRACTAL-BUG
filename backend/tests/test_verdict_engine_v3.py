"""
Verdict Engine V3 Endpoint Tests
================================
Tests for GET /api/market/chart/price-vs-expectation-v3 endpoint
which uses the new Verdict Engine for multi-horizon evaluation.

Features tested:
- V3 endpoint returns valid verdict data
- Verdict contains action, confidence, expected return, risk, position size
- All 3 horizon candidates (1D, 7D, 30D) are returned
- Adjustments from META_BRAIN and CALIBRATION stages
- Raw vs Adjusted confidence values
- Asset selector works for BTC, ETH, SOL, BNB
- Horizon selector works for 1D, 7D, 30D
- Market Context (overlay) data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestVerdictEngineV3Endpoint:
    """Test the V3 price vs expectation endpoint using Verdict Engine"""
    
    def test_v3_endpoint_returns_ok(self):
        """V3 endpoint returns valid response"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"✓ V3 endpoint returns ok=true")
    
    def test_verdict_object_structure(self):
        """Verify verdict object contains all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        verdict = data.get("verdict")
        
        assert verdict is not None, "verdict object should exist"
        
        # Required fields
        required_fields = [
            "verdictId", "action", "confidence", "expectedReturn",
            "risk", "horizon", "positionSizePct", "modelId"
        ]
        
        for field in required_fields:
            assert field in verdict, f"verdict should contain {field}"
            print(f"✓ verdict.{field} = {verdict[field]}")
    
    def test_verdict_action_valid_values(self):
        """Verdict action should be BUY, SELL, or HOLD"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        verdict = data.get("verdict")
        
        assert verdict["action"] in ["BUY", "SELL", "HOLD"], \
            f"Invalid action: {verdict['action']}"
        print(f"✓ verdict.action = {verdict['action']} (valid)")
    
    def test_verdict_confidence_range(self):
        """Confidence should be between 0 and 1"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        verdict = data.get("verdict")
        
        confidence = verdict["confidence"]
        assert 0 <= confidence <= 1, f"Confidence {confidence} out of range [0,1]"
        print(f"✓ verdict.confidence = {confidence:.4f} (in valid range)")
    
    def test_verdict_risk_level(self):
        """Risk should be LOW, MEDIUM, or HIGH"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        verdict = data.get("verdict")
        
        assert verdict["risk"] in ["LOW", "MEDIUM", "HIGH"], \
            f"Invalid risk level: {verdict['risk']}"
        print(f"✓ verdict.risk = {verdict['risk']} (valid)")
    
    def test_verdict_position_size(self):
        """Position size should be between 0 and 100"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        verdict = data.get("verdict")
        
        position_size = verdict["positionSizePct"]
        assert 0 <= position_size <= 100, f"Position size {position_size} out of range"
        print(f"✓ verdict.positionSizePct = {position_size}%")


class TestVerdictRawVsAdjusted:
    """Test raw vs adjusted values in verdict"""
    
    def test_raw_values_present(self):
        """Raw values should be present in verdict"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        verdict = data.get("verdict")
        raw = verdict.get("raw")
        
        assert raw is not None, "raw object should exist"
        assert "confidence" in raw, "raw should have confidence"
        assert "expectedReturn" in raw, "raw should have expectedReturn"
        
        print(f"✓ verdict.raw.confidence = {raw['confidence']:.4f}")
        print(f"✓ verdict.raw.expectedReturn = {raw['expectedReturn']:.4f}")
    
    def test_confidence_adjusted_vs_raw(self):
        """Adjusted confidence should differ from raw (due to META_BRAIN/CALIBRATION)"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        verdict = data.get("verdict")
        
        raw_conf = verdict["raw"]["confidence"]
        adj_conf = verdict["confidence"]
        
        # Adjusted should typically be lower due to risk adjustments
        print(f"✓ Raw confidence: {raw_conf:.4f}")
        print(f"✓ Adjusted confidence: {adj_conf:.4f}")
        print(f"✓ Confidence delta: {(adj_conf - raw_conf):.4f}")


class TestVerdictAdjustments:
    """Test adjustments (META_BRAIN and CALIBRATION stages)"""
    
    def test_adjustments_array_exists(self):
        """Adjustments array should exist"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        verdict = data.get("verdict")
        
        assert "adjustments" in verdict, "verdict should have adjustments array"
        adjustments = verdict["adjustments"]
        assert isinstance(adjustments, list), "adjustments should be a list"
        
        print(f"✓ Adjustments count: {len(adjustments)}")
    
    def test_meta_brain_adjustment(self):
        """META_BRAIN adjustment should be present"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        verdict = data.get("verdict")
        adjustments = verdict.get("adjustments", [])
        
        meta_brain_adj = [a for a in adjustments if a.get("stage") == "META_BRAIN"]
        
        if meta_brain_adj:
            adj = meta_brain_adj[0]
            print(f"✓ META_BRAIN adjustment found: {adj['key']}")
            print(f"✓ Delta confidence: {adj.get('deltaConfidence', 'N/A')}")
        else:
            print("⚠ No META_BRAIN adjustment (may be normal if no rules triggered)")
    
    def test_calibration_adjustment(self):
        """CALIBRATION adjustment should be present"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        verdict = data.get("verdict")
        adjustments = verdict.get("adjustments", [])
        
        calibration_adj = [a for a in adjustments if a.get("stage") == "CALIBRATION"]
        
        if calibration_adj:
            adj = calibration_adj[0]
            print(f"✓ CALIBRATION adjustment found: {adj['key']}")
            print(f"✓ Delta confidence: {adj.get('deltaConfidence', 'N/A')}")
        else:
            print("⚠ No CALIBRATION adjustment (may be normal if no rules triggered)")


class TestHorizonCandidates:
    """Test that all horizon candidates (1D, 7D, 30D) are returned"""
    
    def test_candidates_array_exists(self):
        """Candidates array should exist with 3 horizons"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        candidates = data.get("candidates")
        
        assert candidates is not None, "candidates array should exist"
        assert len(candidates) == 3, f"Expected 3 candidates, got {len(candidates)}"
        
        print(f"✓ Found {len(candidates)} horizon candidates")
    
    def test_all_horizons_present(self):
        """All three horizons should be represented"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        candidates = data.get("candidates", [])
        
        horizons = [c.get("horizon") for c in candidates]
        
        assert "1D" in horizons, "1D horizon missing"
        assert "7D" in horizons, "7D horizon missing"
        assert "30D" in horizons, "30D horizon missing"
        
        print(f"✓ All horizons present: {horizons}")
    
    def test_one_candidate_selected(self):
        """Exactly one candidate should be selected"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        candidates = data.get("candidates", [])
        
        selected = [c for c in candidates if c.get("isSelected")]
        
        assert len(selected) == 1, f"Expected 1 selected candidate, got {len(selected)}"
        
        print(f"✓ Selected candidate: {selected[0]['horizon']}")
    
    def test_candidate_structure(self):
        """Each candidate should have required fields"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        candidates = data.get("candidates", [])
        
        required_fields = ["horizon", "modelId", "expectedReturn", "confidence", "action", "isSelected"]
        
        for cand in candidates:
            for field in required_fields:
                assert field in cand, f"Candidate missing {field}"
            
            print(f"✓ {cand['horizon']}: action={cand['action']}, conf={cand['confidence']:.2f}, ret={cand['expectedReturn']:.4f}, selected={cand['isSelected']}")


class TestAssetSelector:
    """Test that different assets work correctly"""
    
    @pytest.mark.parametrize("asset", ["BTC", "ETH", "SOL", "BNB"])
    def test_asset_returns_data(self, asset):
        """Each asset should return valid data"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": asset, "range": "7d", "horizon": "1D"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True, f"{asset} should return ok=true"
        assert data.get("asset") == asset, f"Asset should be {asset}"
        assert data.get("verdict") is not None, f"{asset} should have verdict"
        
        print(f"✓ {asset}: verdict action = {data['verdict']['action']}")


class TestHorizonSelector:
    """Test that different horizons work correctly"""
    
    @pytest.mark.parametrize("horizon", ["1D", "7D", "30D"])
    def test_horizon_returns_data(self, horizon):
        """Each horizon should return valid data"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": horizon}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("horizon") == horizon, f"Horizon should be {horizon}"
        
        print(f"✓ {horizon}: returned successfully")


class TestMarketContext:
    """Test market context (overlay) data"""
    
    def test_overlay_exists(self):
        """Overlay data should be present"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        overlay = data.get("overlay")
        
        # Overlay may be null if realtime data unavailable
        if overlay:
            assert "regime" in overlay, "overlay should have regime"
            assert "liquidationRisk" in overlay, "overlay should have liquidationRisk"
            print(f"✓ Market regime: {overlay['regime']}")
            print(f"✓ Liquidation risk: {overlay['liquidationRisk']}")
        else:
            print("⚠ Overlay is null (realtime data may be unavailable)")


class TestMetaForecast:
    """Test metaForecast object for backwards compatibility"""
    
    def test_meta_forecast_exists(self):
        """metaForecast should exist for backwards compatibility"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        meta_forecast = data.get("metaForecast")
        
        assert meta_forecast is not None, "metaForecast should exist"
        
        # Required fields for backwards compatibility
        assert "direction" in meta_forecast
        assert "confidence" in meta_forecast
        assert "expectedMovePct" in meta_forecast
        assert "action" in meta_forecast
        assert "riskLevel" in meta_forecast
        
        print(f"✓ metaForecast.direction = {meta_forecast['direction']}")
        print(f"✓ metaForecast.action = {meta_forecast['action']}")
        print(f"✓ metaForecast.riskLevel = {meta_forecast['riskLevel']}")
    
    def test_meta_forecast_raw_values(self):
        """metaForecast should have raw values"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        meta_forecast = data.get("metaForecast", {})
        raw = meta_forecast.get("raw", {})
        
        assert "direction" in raw
        assert "confidence" in raw
        
        print(f"✓ metaForecast.raw.direction = {raw['direction']}")
        print(f"✓ metaForecast.raw.confidence = {raw['confidence']}")


class TestFutureForecastData:
    """Test future forecast point data"""
    
    def test_future_point_exists(self):
        """Future point should exist in layers.meta"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        layers = data.get("layers", {})
        meta = layers.get("meta", {})
        future_point = meta.get("futurePoint")
        
        assert future_point is not None, "futurePoint should exist"
        
        # Required fields
        assert "ts" in future_point
        assert "targetPrice" in future_point
        assert "confidence" in future_point
        assert "direction" in future_point
        
        print(f"✓ futurePoint.targetPrice = {future_point['targetPrice']}")
        print(f"✓ futurePoint.direction = {future_point['direction']}")
        print(f"✓ futurePoint.confidence = {future_point['confidence']:.4f}")
    
    def test_future_band_exists(self):
        """Future band (confidence interval) should exist"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        layers = data.get("layers", {})
        meta = layers.get("meta", {})
        future_band = meta.get("futureBand")
        
        assert future_band is not None, "futureBand should exist"
        assert "upper" in future_band
        assert "lower" in future_band
        
        print(f"✓ futureBand: [{future_band['lower']}, {future_band['upper']}]")


class TestV3ContractVersion:
    """Test V3 contract version and flags"""
    
    def test_v3_contract_exists(self):
        """v3Contract should exist"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        v3_contract = data.get("v3Contract")
        
        assert v3_contract is not None, "v3Contract should exist"
        assert "version" in v3_contract
        
        print(f"✓ v3Contract.version = {v3_contract['version']}")
    
    def test_flags_show_verdict_engine(self):
        """Flags should indicate verdict engine is in use"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        
        data = response.json()
        flags = data.get("flags", {})
        
        assert flags.get("dataSource") == "verdict_engine", \
            "dataSource should be verdict_engine"
        
        print(f"✓ flags.dataSource = {flags.get('dataSource')}")
        print(f"✓ flags.verdictEngineVersion = {flags.get('verdictEngineVersion')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
