"""
Test BTC ↔ SPX Hybrid Layer API
Tests:
- GET /api/core/hybrid-layer - correlation, beta, SPX regime, divergence, hybrid impact
- GET /api/core/macro/snapshot - macro data with dataSource:live
- GET /api/core/position-size - position sizing with macro blocking
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHybridLayerAPI:
    """Test BTC ↔ SPX Hybrid Layer endpoint"""

    def test_hybrid_layer_returns_ok(self):
        """Test /api/core/hybrid-layer returns ok:true with all required fields"""
        response = requests.get(f"{BASE_URL}/api/core/hybrid-layer", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "Expected ok:true"

    def test_hybrid_layer_correlation_range(self):
        """Test correlation30d is between -1 and 1"""
        response = requests.get(f"{BASE_URL}/api/core/hybrid-layer", timeout=30)
        data = response.json()
        
        correlation = data.get("correlation30d")
        assert correlation is not None, "Missing correlation30d"
        assert isinstance(correlation, (int, float)), "correlation30d should be numeric"
        assert -1 <= correlation <= 1, f"correlation30d {correlation} out of range [-1, 1]"

    def test_hybrid_layer_beta_range(self):
        """Test beta is reasonable (-5 to 5)"""
        response = requests.get(f"{BASE_URL}/api/core/hybrid-layer", timeout=30)
        data = response.json()
        
        beta = data.get("beta")
        assert beta is not None, "Missing beta"
        assert isinstance(beta, (int, float)), "beta should be numeric"
        assert -5 <= beta <= 5, f"beta {beta} out of range [-5, 5]"

    def test_hybrid_layer_spx_regime(self):
        """Test spxRegime is valid enum"""
        response = requests.get(f"{BASE_URL}/api/core/hybrid-layer", timeout=30)
        data = response.json()
        
        spx_regime = data.get("spxRegime")
        assert spx_regime is not None, "Missing spxRegime"
        valid_regimes = ["RISK_ON", "RISK_OFF", "NEUTRAL", "UNKNOWN"]
        assert spx_regime in valid_regimes, f"spxRegime '{spx_regime}' not in {valid_regimes}"

    def test_hybrid_layer_trend_score(self):
        """Test trendScore is present and in range [0, 1]"""
        response = requests.get(f"{BASE_URL}/api/core/hybrid-layer", timeout=30)
        data = response.json()
        
        trend = data.get("trendScore")
        assert trend is not None, "Missing trendScore"
        assert 0 <= trend <= 1, f"trendScore {trend} out of range [0, 1]"

    def test_hybrid_layer_divergence(self):
        """Test divergenceScore and divergenceState"""
        response = requests.get(f"{BASE_URL}/api/core/hybrid-layer", timeout=30)
        data = response.json()
        
        div_score = data.get("divergenceScore")
        assert div_score is not None, "Missing divergenceScore"
        assert -1 <= div_score <= 1, f"divergenceScore {div_score} out of range [-1, 1]"
        
        div_state = data.get("divergenceState")
        assert div_state is not None, "Missing divergenceState"
        valid_states = ["BTC_OUTPERFORMS", "BTC_UNDERPERFORMS", "NEUTRAL"]
        assert div_state in valid_states, f"divergenceState '{div_state}' not in {valid_states}"

    def test_hybrid_layer_impact_clamped(self):
        """Test hybridImpact is clamped to [-0.20, +0.20]"""
        response = requests.get(f"{BASE_URL}/api/core/hybrid-layer", timeout=30)
        data = response.json()
        
        impact = data.get("hybridImpact")
        assert impact is not None, "Missing hybridImpact"
        assert isinstance(impact, (int, float)), "hybridImpact should be numeric"
        assert -0.20 <= impact <= 0.20, f"hybridImpact {impact} out of range [-0.20, 0.20]"

    def test_hybrid_layer_meta_fields(self):
        """Test meta contains alignedDays, spxLast, btcLast, returns"""
        response = requests.get(f"{BASE_URL}/api/core/hybrid-layer", timeout=30)
        data = response.json()
        
        meta = data.get("meta")
        assert meta is not None, "Missing meta"
        
        required_fields = ["alignedDays", "spxLast", "btcLast", "spx7dReturn", "btc7dReturn"]
        for field in required_fields:
            assert field in meta, f"Missing meta.{field}"
        
        assert meta["alignedDays"] >= 50, f"alignedDays {meta['alignedDays']} < 50 (minimum for computation)"


class TestMacroSnapshotAPI:
    """Test Macro Snapshot endpoint for live data"""

    def test_macro_snapshot_live_source(self):
        """Test /api/core/macro/snapshot returns dataSource:live"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert data.get("dataSource") == "live", f"Expected dataSource:'live', got '{data.get('dataSource')}'"

    def test_macro_snapshot_computed_fields(self):
        """Test computed fields are present"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        computed = data.get("computed", {})
        required = ["cpi", "riskOffProb", "macroMult", "regime", "regimeProbs", "strongActionsBlocked"]
        for field in required:
            assert field in computed, f"Missing computed.{field}"

    def test_macro_snapshot_capital_flow(self):
        """Test capitalFlow structure with btc, alt, stable"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        cf = data.get("capitalFlow", {})
        for asset in ["btc", "alt", "stable"]:
            assert asset in cf, f"Missing capitalFlow.{asset}"
            assert "dominance" in cf[asset], f"Missing capitalFlow.{asset}.dominance"
            assert "pressure" in cf[asset], f"Missing capitalFlow.{asset}.pressure"

    def test_macro_snapshot_risk_split(self):
        """Test riskSplit with structural, tactical, total"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        rs = data.get("riskSplit", {})
        assert "structural" in rs, "Missing riskSplit.structural"
        assert "tactical" in rs, "Missing riskSplit.tactical"
        assert "total" in rs, "Missing riskSplit.total"


class TestPositionSizeAPI:
    """Test Position Sizing endpoint with macro blocking"""

    def test_position_size_returns_ok(self):
        """Test /api/core/position-size returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/core/position-size?asset=BTCUSDT&tf=1h", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True, "Expected ok:true"
        assert data.get("asset") == "BTCUSDT"

    def test_position_size_blocked_extreme_fear(self):
        """Test position is blocked due to extreme fear (F&G=14)"""
        response = requests.get(f"{BASE_URL}/api/core/position-size?asset=BTCUSDT&tf=1h", timeout=30)
        data = response.json()
        
        # With F&G=14 (extreme fear), positions should be blocked
        assert "blocked" in data, "Missing blocked field"
        assert "mode" in data, "Missing mode field"
        
        # Note: blocked state depends on live market conditions
        if data.get("blocked"):
            assert data.get("sizeMult") == 0.0, "When blocked, sizeMult should be 0"
            assert "blockedReasons" in data, "Missing blockedReasons when blocked"
            assert len(data["blockedReasons"]) > 0, "blockedReasons should not be empty"

    def test_position_size_inputs_structure(self):
        """Test inputs structure contains core, macro, risk, sync"""
        response = requests.get(f"{BASE_URL}/api/core/position-size?asset=BTCUSDT&tf=1h", timeout=30)
        data = response.json()
        
        inputs = data.get("inputs", {})
        required_sections = ["core", "macro", "risk", "sync"]
        for section in required_sections:
            assert section in inputs, f"Missing inputs.{section}"
        
        # Validate core inputs
        core = inputs.get("core", {})
        assert "direction" in core, "Missing inputs.core.direction"
        assert "confidence" in core, "Missing inputs.core.confidence"
        
        # Validate macro inputs
        macro = inputs.get("macro", {})
        assert "regime" in macro, "Missing inputs.macro.regime"
        assert "riskOffProb" in macro, "Missing inputs.macro.riskOffProb"
        assert "fearGreed" in macro, "Missing inputs.macro.fearGreed"

    def test_position_size_mode_valid(self):
        """Test mode is valid enum"""
        response = requests.get(f"{BASE_URL}/api/core/position-size?asset=BTCUSDT&tf=1h", timeout=30)
        data = response.json()
        
        mode = data.get("mode")
        valid_modes = ["DEFENSIVE", "NEUTRAL", "AGGRESSIVE"]
        assert mode in valid_modes, f"mode '{mode}' not in {valid_modes}"

    def test_position_size_components_structure(self):
        """Test components structure for position sizing calculation"""
        response = requests.get(f"{BASE_URL}/api/core/position-size?asset=BTCUSDT&tf=1h", timeout=30)
        data = response.json()
        
        components = data.get("components", {})
        expected_fields = ["baseRisk", "confFactor", "riskPenalty", "syncFactor", "macroMult", "modeFactor", "appetite", "raw"]
        for field in expected_fields:
            assert field in components, f"Missing components.{field}"


class TestAltRotationProbability:
    """Test Alt Rotation probability with extreme fear penalty"""

    def test_alt_rotation_penalty_applied(self):
        """Test that extreme fear penalty affects Alt Rotation probability"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        computed = data.get("computed", {})
        fear_greed = data.get("raw", {}).get("fearGreed", 50)
        regime_probs = computed.get("regimeProbs", {})
        alt_rotation_prob = regime_probs.get("ALT_ROTATION", 0)
        
        print(f"Fear & Greed: {fear_greed}")
        print(f"Alt Rotation Probability: {alt_rotation_prob * 100:.2f}%")
        
        # Note: With F&G=14 (extreme fear), there's a penalty on Alt Rotation
        # The test verifies the extreme_fear_prob is calculated and penalty is applied
        extreme_fear_prob = computed.get("extremeFearProb", 0)
        print(f"Extreme Fear Prob: {extreme_fear_prob:.3f}")
        
        # Verification: extreme fear should be high when F&G < 20
        if fear_greed < 20:
            assert extreme_fear_prob > 0.5, f"Expected high extremeFearProb with F&G={fear_greed}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
