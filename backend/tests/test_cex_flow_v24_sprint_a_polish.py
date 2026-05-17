"""
CEX Flow v2.4 Sprint A Polish API Tests
========================================
Testing Sprint A UI Polish features:
1. dominant_venue in Hero block
2. dominant_asset in Hero block
3. interpretation text in market_liquidity
4. significance + volume_share in largest_transfers
5. confidence_band in pump_setups

Also includes regression tests for Sprint B (liquidity_shock, exchange_inventory, flow_classification)
and Sprint C (behavior_map, liquidity_engine) features.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestCexFlowSprintAPolish:
    """Sprint A Polish - New features in Hero, Market Liquidity, Transfers, Pump blocks"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Load API response once for all tests"""
        self.response = requests.get(
            f"{BASE_URL}/api/onchain/cex/context",
            params={"window": "30d", "chainId": 1},
            timeout=45
        )
        self.data = self.response.json()
    
    def test_api_returns_200(self):
        """API should return 200 OK"""
        assert self.response.status_code == 200
        assert self.data.get("ok") is True
    
    # ── Sprint A Feature 1: Dominant Venue ──
    def test_dominant_venue_exists(self):
        """dominant_venue object should be present in response"""
        dv = self.data.get("dominant_venue")
        assert dv is not None, "dominant_venue should not be None"
    
    def test_dominant_venue_has_exchange(self):
        """dominant_venue.exchange should be a non-empty string"""
        dv = self.data.get("dominant_venue", {})
        assert "exchange" in dv
        assert isinstance(dv["exchange"], str)
        assert len(dv["exchange"]) > 0
    
    def test_dominant_venue_has_volume_fmt(self):
        """dominant_venue.volume_fmt should be formatted string like $X.XK"""
        dv = self.data.get("dominant_venue", {})
        assert "volume_fmt" in dv
        assert dv["volume_fmt"].startswith("$")
    
    def test_dominant_venue_has_share(self):
        """dominant_venue.share should be 0-100 percentage"""
        dv = self.data.get("dominant_venue", {})
        assert "share" in dv
        assert 0 <= dv["share"] <= 100
    
    def test_dominant_venue_has_net_fmt(self):
        """dominant_venue.net_fmt should be formatted string with +/- prefix"""
        dv = self.data.get("dominant_venue", {})
        assert "net_fmt" in dv
        assert isinstance(dv["net_fmt"], str)
    
    def test_dominant_venue_has_bias(self):
        """dominant_venue.bias should be sell_pressure, accumulation, or neutral"""
        dv = self.data.get("dominant_venue", {})
        assert "bias" in dv
        assert dv["bias"] in ("sell_pressure", "accumulation", "neutral")
    
    # ── Sprint A Feature 2: Dominant Asset ──
    def test_dominant_asset_exists(self):
        """dominant_asset object should be present in response"""
        da = self.data.get("dominant_asset")
        assert da is not None, "dominant_asset should not be None"
    
    def test_dominant_asset_has_token(self):
        """dominant_asset.token should be a non-empty string"""
        da = self.data.get("dominant_asset", {})
        assert "token" in da
        assert isinstance(da["token"], str)
        assert len(da["token"]) > 0
    
    def test_dominant_asset_has_volume_fmt(self):
        """dominant_asset.volume_fmt should be formatted string"""
        da = self.data.get("dominant_asset", {})
        assert "volume_fmt" in da
        assert da["volume_fmt"].startswith("$")
    
    def test_dominant_asset_has_share(self):
        """dominant_asset.share should be 0-100 percentage"""
        da = self.data.get("dominant_asset", {})
        assert "share" in da
        assert 0 <= da["share"] <= 100
    
    def test_dominant_asset_has_net_fmt(self):
        """dominant_asset.net_fmt should be formatted string"""
        da = self.data.get("dominant_asset", {})
        assert "net_fmt" in da
        assert isinstance(da["net_fmt"], str)
    
    def test_dominant_asset_has_bias(self):
        """dominant_asset.bias should be sell_pressure, accumulation, or neutral"""
        da = self.data.get("dominant_asset", {})
        assert "bias" in da
        assert da["bias"] in ("sell_pressure", "accumulation", "neutral")
    
    # ── Sprint A Feature 3: Market Liquidity Interpretation ──
    def test_market_liquidity_has_interpretation(self):
        """market_liquidity should have interpretation field"""
        ml = self.data.get("market_liquidity", {})
        assert "interpretation" in ml, "interpretation field missing from market_liquidity"
        assert isinstance(ml["interpretation"], str)
        assert len(ml["interpretation"]) > 0
    
    def test_market_liquidity_interpretation_meaningful(self):
        """interpretation should contain contextual text about buy/sell"""
        ml = self.data.get("market_liquidity", {})
        interp = ml.get("interpretation", "")
        # Should contain at least one of these keywords
        keywords = ["buy", "sell", "liquidity", "pressure", "balanced"]
        assert any(kw in interp.lower() for kw in keywords), \
            f"interpretation '{interp}' doesn't contain expected keywords"
    
    # ── Sprint A Feature 4: Transfer Significance ──
    def test_largest_transfers_have_significance(self):
        """All transfers should have significance field (HIGH/MEDIUM/LOW)"""
        transfers = self.data.get("largest_transfers", [])
        assert len(transfers) > 0, "Should have at least one transfer"
        for i, t in enumerate(transfers):
            assert "significance" in t, f"Transfer {i} missing significance"
            assert t["significance"] in ("HIGH", "MEDIUM", "LOW"), \
                f"Transfer {i} has invalid significance: {t['significance']}"
    
    def test_largest_transfers_have_volume_share(self):
        """All transfers should have volume_share field (0-100)"""
        transfers = self.data.get("largest_transfers", [])
        for i, t in enumerate(transfers):
            assert "volume_share" in t, f"Transfer {i} missing volume_share"
            assert isinstance(t["volume_share"], (int, float)), \
                f"Transfer {i} volume_share should be number"
            assert 0 <= t["volume_share"] <= 100
    
    def test_significance_correlates_with_volume_share(self):
        """HIGH significance should have high volume_share (>=5%)"""
        transfers = self.data.get("largest_transfers", [])
        for t in transfers:
            if t.get("significance") == "HIGH":
                # HIGH = >=5% according to service logic
                # Allow some tolerance due to rounding
                assert t.get("volume_share", 0) >= 4.5, \
                    f"HIGH significance but volume_share only {t.get('volume_share')}"
    
    # ── Sprint A Feature 5: Pump Confidence Band ──
    def test_pump_setups_have_confidence_band(self):
        """All pump_setups should have confidence_band object"""
        setups = self.data.get("pump_setups", [])
        if len(setups) == 0:
            pytest.skip("No pump_setups available")
        for i, s in enumerate(setups):
            assert "confidence_band" in s, f"Setup {i} missing confidence_band"
            cb = s["confidence_band"]
            assert isinstance(cb, dict), f"Setup {i} confidence_band should be dict"
    
    def test_confidence_band_has_low(self):
        """confidence_band.low should be 5-95"""
        setups = self.data.get("pump_setups", [])
        for i, s in enumerate(setups):
            cb = s.get("confidence_band", {})
            assert "low" in cb, f"Setup {i} missing confidence_band.low"
            assert 5 <= cb["low"] <= 95
    
    def test_confidence_band_has_high(self):
        """confidence_band.high should be 5-95"""
        setups = self.data.get("pump_setups", [])
        for i, s in enumerate(setups):
            cb = s.get("confidence_band", {})
            assert "high" in cb, f"Setup {i} missing confidence_band.high"
            assert 5 <= cb["high"] <= 95
    
    def test_confidence_band_has_spread(self):
        """confidence_band.spread should be positive number"""
        setups = self.data.get("pump_setups", [])
        for i, s in enumerate(setups):
            cb = s.get("confidence_band", {})
            assert "spread" in cb, f"Setup {i} missing confidence_band.spread"
            assert cb["spread"] > 0
    
    def test_confidence_band_has_level(self):
        """confidence_band.level should be high/moderate/low"""
        setups = self.data.get("pump_setups", [])
        for i, s in enumerate(setups):
            cb = s.get("confidence_band", {})
            assert "level" in cb, f"Setup {i} missing confidence_band.level"
            assert cb["level"] in ("high", "moderate", "low")
    
    def test_confidence_band_range_valid(self):
        """confidence_band low should be <= high"""
        setups = self.data.get("pump_setups", [])
        for i, s in enumerate(setups):
            cb = s.get("confidence_band", {})
            assert cb.get("low", 100) <= cb.get("high", 0), \
                f"Setup {i} has invalid band: low={cb.get('low')} > high={cb.get('high')}"


class TestCexFlowSprintBRegression:
    """Sprint B Regression - liquidity_shock, exchange_inventory, flow_classification"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.response = requests.get(
            f"{BASE_URL}/api/onchain/cex/context",
            params={"window": "30d", "chainId": 1},
            timeout=45
        )
        self.data = self.response.json()
    
    # ── Liquidity Shock ──
    def test_liquidity_shock_exists(self):
        """liquidity_shock object should be present"""
        assert "liquidity_shock" in self.data
        assert self.data["liquidity_shock"] is not None
    
    def test_liquidity_shock_has_state(self):
        """liquidity_shock.state should be one of 5 states"""
        ls = self.data.get("liquidity_shock", {})
        valid_states = [
            "strong_bullish_shock", "bullish_imbalance", "neutral",
            "bearish_imbalance", "strong_bearish_shock"
        ]
        assert ls.get("state") in valid_states
    
    def test_liquidity_shock_has_buy_sell(self):
        """liquidity_shock should have buy_power and sell_supply"""
        ls = self.data.get("liquidity_shock", {})
        assert "buy_power" in ls
        assert "sell_supply" in ls
        assert "buy_power_fmt" in ls
        assert "sell_supply_fmt" in ls
    
    # ── Exchange Inventory ──
    def test_exchange_inventory_exists(self):
        """exchange_inventory should be a list"""
        inv = self.data.get("exchange_inventory")
        assert isinstance(inv, list)
    
    def test_exchange_inventory_items_have_state(self):
        """Each inventory item should have state (growing/shrinking/stable)"""
        inv = self.data.get("exchange_inventory", [])
        for i, item in enumerate(inv):
            assert item.get("state") in ("growing", "shrinking", "stable")
    
    # ── Flow Classification ──
    def test_flow_classification_exists(self):
        """flow_classification should exist and have composition"""
        fc = self.data.get("flow_classification")
        assert fc is not None
        assert "composition" in fc
        assert isinstance(fc["composition"], list)
    
    def test_flow_classification_has_dominant(self):
        """flow_classification should have dominant flow type"""
        fc = self.data.get("flow_classification", {})
        assert "dominant_type" in fc
        assert "dominant_label" in fc
        assert "dominant_pct" in fc


class TestCexFlowSprintCRegression:
    """Sprint C Regression - behavior_map, liquidity_engine"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.response = requests.get(
            f"{BASE_URL}/api/onchain/cex/context",
            params={"window": "30d", "chainId": 1},
            timeout=45
        )
        self.data = self.response.json()
    
    # ── Behavior Map ──
    def test_behavior_map_exists(self):
        """behavior_map should exist with points array"""
        bm = self.data.get("behavior_map")
        assert bm is not None
        assert "points" in bm
        assert isinstance(bm["points"], list)
    
    def test_behavior_map_points_have_quadrant(self):
        """Each point should have quadrant classification"""
        bm = self.data.get("behavior_map", {})
        for p in bm.get("points", []):
            assert "quadrant" in p
            assert p["quadrant"] in ("accumulation", "distribution", "liquidity_hub", "neutral")
    
    def test_behavior_map_has_dominant_venue(self):
        """behavior_map should have dominant_venue"""
        bm = self.data.get("behavior_map", {})
        dv = bm.get("dominant_venue")
        if dv:  # May be null if no exchanges
            assert "exchange" in dv
            assert "quadrant_label" in dv
    
    # ── Liquidity Engine ──
    def test_liquidity_engine_exists(self):
        """liquidity_engine should exist with tokens and aggregate"""
        le = self.data.get("liquidity_engine")
        assert le is not None
        assert "tokens" in le
        assert "aggregate" in le
    
    def test_liquidity_engine_aggregate_has_state(self):
        """liquidity_engine.aggregate should have state"""
        le = self.data.get("liquidity_engine", {})
        agg = le.get("aggregate", {})
        assert "state" in agg
        assert "total_buy_power" in agg
        assert "total_sell_supply" in agg


class TestCexFlowBasicRegression:
    """Basic regression - core fields from Sprint A"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.response = requests.get(
            f"{BASE_URL}/api/onchain/cex/context",
            params={"window": "30d", "chainId": 1},
            timeout=45
        )
        self.data = self.response.json()
    
    def test_market_bias_exists(self):
        """market_bias should be bullish/bearish/neutral"""
        assert self.data.get("market_bias") in ("bullish", "bearish", "neutral")
    
    def test_exchange_pressure_exists(self):
        """exchange_pressure object should exist"""
        ep = self.data.get("exchange_pressure")
        assert ep is not None
        assert "deposits" in ep
        assert "withdrawals" in ep
        assert "active_exchanges" in ep
    
    def test_stablecoin_power_exists(self):
        """stablecoin_power should exist"""
        sp = self.data.get("stablecoin_power")
        assert sp is not None
        assert "net_power" in sp
    
    def test_top_exchanges_exists(self):
        """top_exchanges should be a list"""
        te = self.data.get("top_exchanges")
        assert isinstance(te, list)
    
    def test_market_liquidity_exists(self):
        """market_liquidity should exist with buy_power and sell_supply"""
        ml = self.data.get("market_liquidity")
        assert ml is not None
        assert "buy_power" in ml
        assert "sell_supply" in ml
        assert "bias" in ml
