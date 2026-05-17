"""
CEX Flow Sprint C Tests: Exchange Behavior Map + Exchange Liquidity Engine
===========================================================================
Tests Sprint C features:
- behavior_map: quadrant visualization with 6 exchanges, dominant_venue, quadrant_summary
- liquidity_engine: per-token liquidity with aggregate

Also includes regression tests for Sprint A/B features.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Sprint C: Exchange Behavior Map tests
class TestBehaviorMap:
    """Tests for behavior_map field in /api/onchain/cex/context"""

    def test_behavior_map_exists(self):
        """behavior_map field exists in API response"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "behavior_map" in data
        assert data["behavior_map"] is not None

    def test_behavior_map_has_points(self):
        """behavior_map contains points array"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "points" in data["behavior_map"]
        assert isinstance(data["behavior_map"]["points"], list)
        assert len(data["behavior_map"]["points"]) >= 1

    def test_behavior_map_point_structure(self):
        """Each point has required fields: exchange, x, y, quadrant, volume"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        points = data["behavior_map"]["points"]
        
        for point in points:
            assert "exchange" in point, "Missing exchange field"
            assert "entity_id" in point, "Missing entity_id field"
            assert "x" in point, "Missing x coordinate"
            assert "y" in point, "Missing y coordinate"
            assert "volume" in point, "Missing volume field"
            assert "volume_fmt" in point, "Missing volume_fmt field"
            assert "quadrant" in point, "Missing quadrant field"
            assert "quadrant_label" in point, "Missing quadrant_label field"
            assert "net_flow_fmt" in point, "Missing net_flow_fmt field"

    def test_behavior_map_x_y_range(self):
        """x is in [0,1], y is in [-1,+1]"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        points = data["behavior_map"]["points"]
        
        for point in points:
            assert 0 <= point["x"] <= 1, f"x={point['x']} out of [0,1] range for {point['exchange']}"
            assert -1 <= point["y"] <= 1, f"y={point['y']} out of [-1,+1] range for {point['exchange']}"

    def test_behavior_map_valid_quadrants(self):
        """Quadrant is one of: accumulation, distribution, liquidity_hub, neutral"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        points = data["behavior_map"]["points"]
        valid_quadrants = {"accumulation", "distribution", "liquidity_hub", "neutral"}
        
        for point in points:
            assert point["quadrant"] in valid_quadrants, f"Invalid quadrant: {point['quadrant']}"

    def test_behavior_map_dominant_venue(self):
        """dominant_venue contains exchange, quadrant_label, volume_fmt, share"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        
        assert "dominant_venue" in data["behavior_map"]
        dom = data["behavior_map"]["dominant_venue"]
        if dom is not None:
            assert "exchange" in dom, "Missing exchange in dominant_venue"
            assert "quadrant_label" in dom, "Missing quadrant_label in dominant_venue"
            assert "volume_fmt" in dom, "Missing volume_fmt in dominant_venue"
            assert "share" in dom, "Missing share in dominant_venue"
            assert isinstance(dom["share"], (int, float)), "share should be numeric"

    def test_behavior_map_quadrant_summary(self):
        """quadrant_summary has all 4 quadrants with count, total_volume, exchanges"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        
        assert "quadrant_summary" in data["behavior_map"]
        qs = data["behavior_map"]["quadrant_summary"]
        required_quadrants = ["accumulation", "distribution", "liquidity_hub", "neutral"]
        
        for q in required_quadrants:
            assert q in qs, f"Missing {q} in quadrant_summary"
            assert "count" in qs[q], f"Missing count in quadrant_summary[{q}]"
            assert "total_volume" in qs[q], f"Missing total_volume in quadrant_summary[{q}]"
            assert "exchanges" in qs[q], f"Missing exchanges in quadrant_summary[{q}]"

    def test_behavior_map_known_exchanges(self):
        """Verify expected exchanges appear: Binance, Gate.io, etc."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        points = data["behavior_map"]["points"]
        exchange_names = [p["exchange"] for p in points]
        
        # At least Binance should be present (dominant exchange)
        assert "Binance" in exchange_names, "Binance should be in behavior_map"


# Sprint C: Exchange Liquidity Engine tests
class TestLiquidityEngine:
    """Tests for liquidity_engine field in /api/onchain/cex/context"""

    def test_liquidity_engine_exists(self):
        """liquidity_engine field exists in API response"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "liquidity_engine" in data
        assert data["liquidity_engine"] is not None

    def test_liquidity_engine_has_tokens(self):
        """liquidity_engine contains tokens array"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "tokens" in data["liquidity_engine"]
        assert isinstance(data["liquidity_engine"]["tokens"], list)

    def test_liquidity_engine_token_structure(self):
        """Each token has required fields: token, buy_power, sell_supply, net_liquidity, state"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        tokens = data["liquidity_engine"]["tokens"]
        
        if len(tokens) > 0:
            token = tokens[0]
            assert "token" in token, "Missing token field"
            assert "buy_power" in token, "Missing buy_power field"
            assert "buy_power_fmt" in token, "Missing buy_power_fmt field"
            assert "sell_supply" in token, "Missing sell_supply field"
            assert "sell_supply_fmt" in token, "Missing sell_supply_fmt field"
            assert "net_liquidity" in token, "Missing net_liquidity field"
            assert "net_liquidity_fmt" in token, "Missing net_liquidity_fmt field"
            assert "buy_pct" in token, "Missing buy_pct field"
            assert "state" in token, "Missing state field"
            assert "interpretation" in token, "Missing interpretation field"

    def test_liquidity_engine_valid_states(self):
        """Token state is one of: bullish_imbalance, bearish_imbalance, neutral"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        tokens = data["liquidity_engine"]["tokens"]
        valid_states = {"bullish_imbalance", "bearish_imbalance", "neutral"}
        
        for token in tokens:
            assert token["state"] in valid_states, f"Invalid state: {token['state']}"

    def test_liquidity_engine_aggregate(self):
        """liquidity_engine has aggregate with total_buy_power, total_sell_supply, net, state"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        
        assert "aggregate" in data["liquidity_engine"]
        agg = data["liquidity_engine"]["aggregate"]
        assert "total_buy_power" in agg, "Missing total_buy_power in aggregate"
        assert "total_buy_power_fmt" in agg, "Missing total_buy_power_fmt in aggregate"
        assert "total_sell_supply" in agg, "Missing total_sell_supply in aggregate"
        assert "total_sell_supply_fmt" in agg, "Missing total_sell_supply_fmt in aggregate"
        assert "net" in agg, "Missing net in aggregate"
        assert "net_fmt" in agg, "Missing net_fmt in aggregate"
        assert "state" in agg, "Missing state in aggregate"


# Regression: Sprint B features
class TestSprintBRegression:
    """Regression tests for Sprint B: Liquidity Shock, Exchange Inventory, Flow Classification"""

    def test_liquidity_shock_exists(self):
        """liquidity_shock field exists with state, label, buy_power, sell_supply"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "liquidity_shock" in data
        shock = data["liquidity_shock"]
        assert "state" in shock
        assert "label" in shock
        assert "buy_power" in shock
        assert "sell_supply" in shock
        assert "net" in shock
        assert "drivers" in shock
        assert "exchange_drivers" in shock

    def test_exchange_inventory_exists(self):
        """exchange_inventory field exists with token data"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "exchange_inventory" in data
        assert isinstance(data["exchange_inventory"], list)
        
        if len(data["exchange_inventory"]) > 0:
            inv = data["exchange_inventory"][0]
            assert "token" in inv
            assert "deposits" in inv
            assert "withdrawals" in inv
            assert "state" in inv
            assert "per_exchange" in inv

    def test_flow_classification_exists(self):
        """flow_classification field exists with composition and dominant_type"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "flow_classification" in data
        fc = data["flow_classification"]
        assert "composition" in fc
        assert "dominant_type" in fc
        assert "dominant_label" in fc
        assert "interpretation" in fc


# Regression: Sprint A features
class TestSprintARegression:
    """Regression tests for Sprint A: Hero drivers, indicators, behavior labels"""

    def test_hero_drivers_exist(self):
        """drivers field exists with market narrative"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "drivers" in data
        assert isinstance(data["drivers"], list)

    def test_hero_offsetting_exists(self):
        """offsetting_factors field exists"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "offsetting_factors" in data
        assert isinstance(data["offsetting_factors"], list)

    def test_hero_indicators_exist(self):
        """indicators field exists with sell_pressure, liquidity, confidence"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "indicators" in data
        ind = data["indicators"]
        assert "sell_pressure" in ind
        assert "liquidity" in ind
        assert "confidence" in ind

    def test_exchange_behavior_labels(self):
        """top_exchanges have behavior_label field"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "top_exchanges" in data
        
        if len(data["top_exchanges"]) > 0:
            ex = data["top_exchanges"][0]
            assert "behavior_label" in ex

    def test_transfer_impact_labels(self):
        """largest_transfers have impact_label field"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "largest_transfers" in data
        
        if len(data["largest_transfers"]) > 0:
            t = data["largest_transfers"][0]
            assert "impact_label" in t


# Core fields validation
class TestCoreFields:
    """Tests for core CEX context fields"""

    def test_market_bias(self):
        """market_bias is one of: bullish, bearish, neutral"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert data["market_bias"] in ["bullish", "bearish", "neutral"]

    def test_confidence(self):
        """confidence is one of: high, moderate, low"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert data["confidence"] in ["high", "moderate", "low"]

    def test_exchange_pressure(self):
        """exchange_pressure has deposits, withdrawals, net_flow"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "exchange_pressure" in data
        ep = data["exchange_pressure"]
        assert "deposits" in ep
        assert "withdrawals" in ep
        assert "net_flow" in ep

    def test_stablecoin_power(self):
        """stablecoin_power has total_in, total_out, net_power"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=45)
        data = response.json()
        assert "stablecoin_power" in data
        sp = data["stablecoin_power"]
        assert "total_in" in sp
        assert "total_out" in sp
        assert "net_power" in sp


# Different window tests
class TestTimeWindows:
    """Tests for different time windows"""

    def test_24h_window(self):
        """API works with 24h window"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=24h", timeout=45)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True

    def test_7d_window(self):
        """API works with 7d window"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=7d", timeout=45)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
