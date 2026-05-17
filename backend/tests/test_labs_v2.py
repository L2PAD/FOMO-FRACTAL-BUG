"""
Labs V2 API Tests — Indicator Intelligence System
Tests for 3 modes: Global, Universe, Asset
Tests for drilldown and symbols endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://expo-telegram-web.preview.emergentagent.com"


class TestLabsGlobalMode:
    """Test Labs API in Global mode (BTC proxy)"""
    
    def test_global_mode_returns_ok(self):
        """GET /api/exchange/labs?mode=global returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=global")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("mode") == "global"
    
    def test_global_mode_has_groups(self):
        """Global mode returns groups array with 4 groups"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=global")
        data = response.json()
        assert "groups" in data
        assert len(data["groups"]) == 4
        
        # Verify group names
        group_names = [g["name"] for g in data["groups"]]
        assert "Market Structure" in group_names
        assert "Flow & Participation" in group_names
        assert "Smart Money & Risk" in group_names
        assert "Meta / Quality" in group_names
    
    def test_global_mode_has_overall_state(self):
        """Global mode returns overallState with required fields"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=global")
        data = response.json()
        assert "overallState" in data
        
        state = data["overallState"]
        assert "stateKey" in state
        assert "stateLabel" in state
        assert "confidence" in state
        assert isinstance(state["confidence"], (int, float))
    
    def test_global_mode_has_explain(self):
        """Global mode returns explain with human-readable text"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=global")
        data = response.json()
        assert "explain" in data
        
        explain = data["explain"]
        assert "oneLiner" in explain
        assert "bullets" in explain
        assert isinstance(explain["bullets"], list)
    
    def test_global_mode_has_integrity(self):
        """Global mode returns integrity status"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=global")
        data = response.json()
        assert "integrity" in data
        
        integrity = data["integrity"]
        assert "status" in integrity
        assert "coveragePct" in integrity
        assert "freshnessSec" in integrity
        assert integrity["status"] in ["HEALTHY", "DEGRADED", "CRITICAL"]
    
    def test_global_mode_has_active_risks(self):
        """Global mode returns activeRisks array"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=global")
        data = response.json()
        assert "activeRisks" in data
        assert isinstance(data["activeRisks"], list)


class TestLabsAssetMode:
    """Test Labs API in Asset mode"""
    
    def test_asset_mode_btc(self):
        """GET /api/exchange/labs?mode=asset&asset=BTCUSDT returns labs data"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=asset&asset=BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("mode") == "asset"
        assert data.get("asset") == "BTCUSDT"
    
    def test_asset_mode_eth(self):
        """GET /api/exchange/labs?mode=asset&asset=ETHUSDT returns labs data"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=asset&asset=ETHUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "ETHUSDT"
    
    def test_asset_mode_lab_cards(self):
        """Asset mode returns labs with expected fields"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=asset&asset=BTCUSDT")
        data = response.json()
        
        # Check first group has labs
        assert len(data["groups"]) > 0
        labs = data["groups"][0]["labs"]
        assert len(labs) > 0
        
        # Verify lab structure
        lab = labs[0]
        assert "lab" in lab
        assert "displayName" in lab
        assert "state" in lab
        assert "abnormality" in lab
        assert "riskContribution" in lab
        assert "convictionContribution" in lab
        assert "confidence" in lab
        assert "metrics" in lab


class TestLabsUniverseMode:
    """Test Labs API in Universe mode (cross-asset analytics)"""
    
    def test_universe_mode_returns_ok(self):
        """GET /api/exchange/labs?mode=universe returns universe data"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=universe", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("mode") == "universe"
    
    def test_universe_mode_has_state_distribution(self):
        """Universe mode returns stateDistribution"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=universe", timeout=30)
        data = response.json()
        assert "universe" in data
        
        universe = data["universe"]
        assert "stateDistribution" in universe
        
        # Check distribution structure
        dist = universe["stateDistribution"]
        for key, val in dist.items():
            assert "count" in val
            assert "pct" in val
    
    def test_universe_mode_has_top_edges(self):
        """Universe mode returns topEdges array"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=universe", timeout=30)
        data = response.json()
        
        universe = data["universe"]
        assert "topEdges" in universe
        assert isinstance(universe["topEdges"], list)
        
        if len(universe["topEdges"]) > 0:
            edge = universe["topEdges"][0]
            assert "symbol" in edge
            assert "state" in edge
            assert "confidence" in edge
    
    def test_universe_mode_has_lab_heat(self):
        """Universe mode returns labHeat array"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs?mode=universe", timeout=30)
        data = response.json()
        
        universe = data["universe"]
        assert "labHeat" in universe
        assert isinstance(universe["labHeat"], list)
        
        if len(universe["labHeat"]) > 0:
            heat = universe["labHeat"][0]
            assert "lab" in heat
            assert "avgAbnormality" in heat


class TestLabsDrilldown:
    """Test Labs drilldown API"""
    
    def test_liquidity_drilldown(self):
        """GET /api/exchange/labs/drilldown?lab=liquidity&asset=BTCUSDT returns metrics"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs/drilldown?lab=liquidity&asset=BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("lab") == "liquidity"
    
    def test_regime_drilldown(self):
        """GET /api/exchange/labs/drilldown?lab=regime&asset=BTCUSDT returns metrics"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs/drilldown?lab=regime&asset=BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("lab") == "regime"
    
    def test_drilldown_has_metrics(self):
        """Drilldown returns metrics array with raw values"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs/drilldown?lab=regime&asset=BTCUSDT")
        data = response.json()
        
        assert "metrics" in data
        assert len(data["metrics"]) > 0
        
        metric = data["metrics"][0]
        assert "key" in metric
        assert "raw" in metric
        assert "norm" in metric
        assert "abnormality" in metric
    
    def test_drilldown_has_evidence(self):
        """Drilldown returns evidence array"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs/drilldown?lab=regime&asset=BTCUSDT")
        data = response.json()
        
        assert "evidence" in data
        assert isinstance(data["evidence"], list)
    
    def test_drilldown_has_horizon_impact(self):
        """Drilldown returns horizonW (horizon impact weights)"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs/drilldown?lab=regime&asset=BTCUSDT")
        data = response.json()
        
        assert "horizonW" in data
        assert "short" in data["horizonW"]
        assert "mid" in data["horizonW"]
        assert "swing" in data["horizonW"]
    
    def test_invalid_lab_returns_error(self):
        """Drilldown for invalid lab returns error"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs/drilldown?lab=invalid_lab&asset=BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == False


class TestLabsSymbols:
    """Test Labs symbols endpoint"""
    
    def test_symbols_returns_list(self):
        """GET /api/exchange/labs/symbols returns list of symbols"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs/symbols")
        assert response.status_code == 200
        data = response.json()
        assert "symbols" in data
        assert isinstance(data["symbols"], list)
        assert len(data["symbols"]) > 0
    
    def test_symbols_include_major(self):
        """Symbols list includes major assets"""
        response = requests.get(f"{BASE_URL}/api/exchange/labs/symbols")
        data = response.json()
        symbols = data["symbols"]
        
        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
