"""
Macro Intelligence Regime Engine Tests
Tests all endpoints for the Market Regime Engine (P2+ feature)

Endpoints tested:
- GET /api/v10/macro-intel/health - module health check
- GET /api/v10/macro-intel/snapshot - full macro snapshot
- GET /api/v10/macro-intel/regime - current regime simplified
- GET /api/v10/macro-intel/grid - 8-regime grid with active highlighted
- GET /api/v10/macro-intel/active - active regime cell with raw values
- GET /api/v10/macro-intel/context - context for Meta-Brain
- GET /api/v10/macro-intel/ml-features - ML features output
- GET /api/v10/macro-intel/definitions - regime definitions
- GET /api/v10/macro-intel/explain/:regime - regime explanation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMacroIntelHealth:
    """Test /api/v10/macro-intel/health endpoint"""
    
    def test_health_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
    def test_health_has_module_info(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/health")
        data = response.json()
        assert data["module"] == "macro-intel"
        assert data["version"] == "v1.0"
        
    def test_health_has_regime_data(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/health")
        data = response.json()
        assert data["hasData"] == True
        assert data["currentRegime"] is not None
        assert data["quality"] in ["LIVE", "CACHED", "DEGRADED", "NO_DATA"]


class TestMacroIntelSnapshot:
    """Test /api/v10/macro-intel/snapshot endpoint"""
    
    def test_snapshot_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/snapshot")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
    def test_snapshot_has_raw_data(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/snapshot")
        data = response.json()["data"]
        
        raw = data["raw"]
        assert "fearGreedIndex" in raw
        assert "fearGreedLabel" in raw
        assert "btcDominance" in raw
        assert "stableDominance" in raw
        assert "altDominance" in raw
        assert "btcPrice" in raw
        assert "btcPriceChange24h" in raw
        assert "timestamp" in raw
        
    def test_snapshot_has_state(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/snapshot")
        data = response.json()["data"]
        
        state = data["state"]
        assert "regime" in state
        assert "regimeId" in state
        assert "regimeLabel" in state
        assert "trends" in state
        assert "trendValues" in state
        assert "riskLevel" in state
        assert "marketBias" in state
        assert "confidenceMultiplier" in state
        assert "blocks" in state
        assert "flags" in state
        
    def test_snapshot_has_context(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/snapshot")
        data = response.json()["data"]
        
        context = data["context"]
        assert "regimeId" in context
        assert "regimeLabel" in context
        assert "fearGreed" in context
        assert "fearGreedNorm" in context
        assert "confidenceMultiplier" in context
        assert "blockStrongActions" in context
        assert "flags" in context
        
    def test_snapshot_has_ml_features(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/snapshot")
        data = response.json()["data"]
        
        ml = data["mlFeatures"]
        assert "macro_regime_id" in ml
        assert "macro_risk_level" in ml
        assert "fear_greed_norm" in ml
        assert "btc_dom_trend" in ml
        assert "stable_dom_trend" in ml
        assert "alt_flow_proxy" in ml
        
    def test_snapshot_has_quality(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/snapshot")
        data = response.json()["data"]
        
        quality = data["quality"]
        assert quality["mode"] in ["LIVE", "CACHED", "DEGRADED", "NO_DATA"]
        assert "missing" in quality
        
    def test_snapshot_refresh_param(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/snapshot?refresh=true")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True


class TestMacroIntelRegime:
    """Test /api/v10/macro-intel/regime endpoint"""
    
    def test_regime_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/regime")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
    def test_regime_has_basic_info(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/regime")
        data = response.json()["data"]
        
        assert "regime" in data
        assert "regimeId" in data
        assert "regimeLabel" in data
        
    def test_regime_has_risk_and_bias(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/regime")
        data = response.json()["data"]
        
        assert data["riskLevel"] in ["LOW", "MEDIUM", "HIGH", "EXTREME"]
        assert data["marketBias"] in ["BTC_ONLY", "ALTS", "DEFENSIVE", "NEUTRAL"]
        
    def test_regime_has_confidence_multiplier(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/regime")
        data = response.json()["data"]
        
        cm = data["confidenceMultiplier"]
        assert isinstance(cm, (int, float))
        assert 0.4 <= cm <= 1.0  # Within bounds from MACRO_INTEL_THRESHOLDS
        
    def test_regime_has_blocks(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/regime")
        data = response.json()["data"]
        
        blocks = data["blocks"]
        assert "strongActions" in blocks
        assert "altExposure" in blocks
        assert "btcExposure" in blocks
        
    def test_regime_has_flags(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/regime")
        data = response.json()["data"]
        
        flags = data["flags"]
        assert "MACRO_PANIC" in flags
        assert "RISK_OFF" in flags
        assert "ALT_SEASON" in flags
        assert "FLIGHT_TO_BTC" in flags
        assert "CAPITAL_EXIT" in flags
        assert "EXTREME_FEAR" in flags
        assert "EXTREME_GREED" in flags
        
    def test_regime_has_trends(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/regime")
        data = response.json()["data"]
        
        trends = data["trends"]
        assert trends["btcDominance"] in ["UP", "DOWN", "FLAT"]
        assert trends["stableDominance"] in ["UP", "DOWN", "FLAT"]
        assert trends["btcPrice"] in ["UP", "DOWN", "FLAT"]
        assert trends["altMarket"] in ["UP", "DOWN", "FLAT"]


class TestMacroIntelGrid:
    """Test /api/v10/macro-intel/grid endpoint"""
    
    def test_grid_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/grid")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
    def test_grid_has_8_regimes(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/grid")
        data = response.json()["data"]
        
        grid = data["grid"]
        assert len(grid) == 8
        
    def test_grid_cell_structure(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/grid")
        grid = response.json()["data"]["grid"]
        
        for cell in grid:
            assert "regime" in cell
            assert "regimeId" in cell
            assert "title" in cell
            assert "description" in cell
            assert "interpretation" in cell
            assert "riskLevel" in cell
            assert "marketBias" in cell
            assert "historicalBias" in cell
            assert "labsSignals" in cell
            
    def test_grid_has_active_regime(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/grid")
        data = response.json()["data"]
        
        assert "activeRegime" in data
        assert "activeCell" in data
        
    def test_grid_active_regime_matches_cell(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/grid")
        data = response.json()["data"]
        
        active_regime = data["activeRegime"]
        active_cell = data["activeCell"]
        
        assert active_cell["regime"] == active_regime
        
    def test_grid_all_regime_ids_present(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/grid")
        grid = response.json()["data"]["grid"]
        
        ids = [cell["regimeId"] for cell in grid]
        assert sorted(ids) == [0, 1, 2, 3, 4, 5, 6, 7]


class TestMacroIntelActive:
    """Test /api/v10/macro-intel/active endpoint"""
    
    def test_active_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/active")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
    def test_active_has_regime_info(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/active")
        data = response.json()["data"]
        
        assert "regime" in data
        assert "regimeId" in data
        assert "title" in data
        assert "description" in data
        assert "interpretation" in data
        
    def test_active_has_is_current_flag(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/active")
        data = response.json()["data"]
        
        assert data["isCurrent"] == True
        
    def test_active_has_raw_values(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/active")
        data = response.json()["data"]
        
        raw = data["raw"]
        assert "fearGreed" in raw
        assert "btcDominance" in raw
        assert "stableDominance" in raw
        assert "btcPrice" in raw
        assert "btcPriceChange24h" in raw
        
    def test_active_has_blocks(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/active")
        data = response.json()["data"]
        
        blocks = data["blocks"]
        assert "strongActions" in blocks
        assert "altExposure" in blocks
        assert "btcExposure" in blocks


class TestMacroIntelContext:
    """Test /api/v10/macro-intel/context endpoint"""
    
    def test_context_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/context")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
    def test_context_for_meta_brain(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/context")
        data = response.json()["data"]
        
        # Key fields for Meta-Brain integration
        assert "regimeId" in data
        assert "regimeLabel" in data
        assert "regime" in data
        assert "fearGreed" in data
        assert "fearGreedNorm" in data
        assert "confidenceMultiplier" in data
        assert "blockStrongActions" in data
        assert "timestamp" in data
        
    def test_context_trend_values(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/context")
        data = response.json()["data"]
        
        assert data["btcDominanceTrend"] in [-1, 0, 1]
        assert data["stableDominanceTrend"] in [-1, 0, 1]
        assert data["btcPriceTrend"] in [-1, 0, 1]
        assert data["altMarketTrend"] in [-1, 0, 1]


class TestMacroIntelMLFeatures:
    """Test /api/v10/macro-intel/ml-features endpoint"""
    
    def test_ml_features_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/ml-features")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
    def test_ml_features_structure(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/ml-features")
        data = response.json()["data"]
        
        assert "macro_regime_id" in data
        assert "macro_risk_level" in data
        assert "fear_greed_norm" in data
        assert "btc_dom_trend" in data
        assert "stable_dom_trend" in data
        assert "alt_flow_proxy" in data
        
    def test_ml_features_values_in_range(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/ml-features")
        data = response.json()["data"]
        
        # Regime ID: 0-7
        assert 0 <= data["macro_regime_id"] <= 7
        # Risk level: 0-3
        assert 0 <= data["macro_risk_level"] <= 3
        # Fear greed norm: 0-1
        assert 0 <= data["fear_greed_norm"] <= 1
        # Trends: -1 to 1
        assert data["btc_dom_trend"] in [-1, 0, 1]
        assert data["stable_dom_trend"] in [-1, 0, 1]
        # Alt flow proxy: 0-1
        assert 0 <= data["alt_flow_proxy"] <= 1


class TestMacroIntelDefinitions:
    """Test /api/v10/macro-intel/definitions endpoint"""
    
    def test_definitions_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/definitions")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
    def test_definitions_has_all_regimes(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/definitions")
        regimes = response.json()["data"]["regimes"]
        
        expected_regimes = [
            "BTC_FLIGHT_TO_SAFETY",
            "PANIC_SELL_OFF",
            "BTC_LEADS_ALT_FOLLOW",
            "BTC_MAX_PRESSURE",
            "ALT_ROTATION",
            "FULL_RISK_OFF",
            "ALT_SEASON",
            "CAPITAL_EXIT"
        ]
        
        for regime in expected_regimes:
            assert regime in regimes
            
    def test_definitions_regime_structure(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/definitions")
        regimes = response.json()["data"]["regimes"]
        
        for regime_name, def_data in regimes.items():
            assert "regime" in def_data
            assert "title" in def_data
            assert "description" in def_data
            assert "interpretation" in def_data
            assert "condition" in def_data
            assert "riskLevel" in def_data
            assert "marketBias" in def_data
            assert "confidenceMultiplier" in def_data
            assert "blocks" in def_data
            assert "labsSignals" in def_data
            
    def test_definitions_has_thresholds(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/definitions")
        thresholds = response.json()["data"]["thresholds"]
        
        assert "TREND_UP_THRESHOLD" in thresholds
        assert "TREND_DOWN_THRESHOLD" in thresholds
        assert "EXTREME_FEAR_THRESHOLD" in thresholds
        assert "FEAR_THRESHOLD" in thresholds
        assert "GREED_THRESHOLD" in thresholds
        assert "EXTREME_GREED_THRESHOLD" in thresholds
        
    def test_definitions_is_locked(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/definitions")
        data = response.json()["data"]
        
        assert data["locked"] == True
        assert data["version"] == "v1.0"


class TestMacroIntelExplain:
    """Test /api/v10/macro-intel/explain/:regime endpoint"""
    
    def test_explain_valid_regime(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/explain/BTC_FLIGHT_TO_SAFETY")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
    def test_explain_returns_full_info(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/explain/PANIC_SELL_OFF")
        data = response.json()["data"]
        
        assert data["regime"] == "PANIC_SELL_OFF"
        assert data["title"] == "Market Panic"
        assert "description" in data
        assert "interpretation" in data
        assert "riskLevel" in data
        assert "marketBias" in data
        assert "confidenceMultiplier" in data
        assert "blocks" in data
        assert "labsSignals" in data
        
    def test_explain_all_regimes(self):
        regimes = [
            "BTC_FLIGHT_TO_SAFETY",
            "PANIC_SELL_OFF",
            "BTC_LEADS_ALT_FOLLOW",
            "BTC_MAX_PRESSURE",
            "ALT_ROTATION",
            "FULL_RISK_OFF",
            "ALT_SEASON",
            "CAPITAL_EXIT"
        ]
        
        for regime in regimes:
            response = requests.get(f"{BASE_URL}/api/v10/macro-intel/explain/{regime}")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] == True
            assert data["data"]["regime"] == regime
            
    def test_explain_invalid_regime(self):
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/explain/INVALID_REGIME")
        assert response.status_code == 404
        data = response.json()
        assert data["ok"] == False
        assert "validRegimes" in data


class TestCurrentMarketState:
    """Test current market conditions (based on review request context)"""
    
    def test_current_regime_btc_flight_to_safety(self):
        """Main agent stated current regime is BTC_FLIGHT_TO_SAFETY"""
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/regime")
        data = response.json()["data"]
        
        assert data["regime"] == "BTC_FLIGHT_TO_SAFETY"
        
    def test_extreme_fear_flag(self):
        """Current market has EXTREME_FEAR flag"""
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/regime")
        data = response.json()["data"]
        
        assert data["flags"]["EXTREME_FEAR"] == True
        
    def test_high_risk_level(self):
        """Current risk level should be HIGH"""
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/regime")
        data = response.json()["data"]
        
        assert data["riskLevel"] == "HIGH"
        
    def test_confidence_multiplier_around_068(self):
        """Main agent stated confidence multiplier is 0.68"""
        response = requests.get(f"{BASE_URL}/api/v10/macro-intel/regime")
        data = response.json()["data"]
        
        # Allow small variation due to market changes
        assert 0.60 <= data["confidenceMultiplier"] <= 0.75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
