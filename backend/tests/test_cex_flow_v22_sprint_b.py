"""
CEX Intelligence Sprint B Tests - v2.2
======================================
Tests for 3 new intelligence engines:
- Exchange Inventory
- Flow Type Classification
- Liquidity Shock Detector

Regression tests for Sprint A features (Hero, Exchange Flows, Transfers).
"""
import pytest
import requests
import os

# Use local backend for tests since external has ingress timeout issues
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')


class TestCexContextSprintBFields:
    """Verify Sprint B new fields in /api/onchain/cex/context"""
    
    @pytest.fixture(scope="class")
    def cex_response(self):
        """Single API call for the class to reduce load"""
        response = requests.get(
            f"{BASE_URL}/api/onchain/cex/context",
            params={"chainId": 1, "window": "30d"},
            timeout=60
        )
        assert response.status_code == 200, f"API returned {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"API returned error: {data.get('error')}"
        return data
    
    def test_api_returns_200(self, cex_response):
        """Basic API health check"""
        assert cex_response.get("ok") is True
        print(f"PASS: API returned ok=True, market_bias={cex_response.get('market_bias')}")
    
    # ══════════════════════════════════════════════════════════
    # Sprint B: LIQUIDITY SHOCK DETECTOR
    # ══════════════════════════════════════════════════════════
    def test_liquidity_shock_present(self, cex_response):
        """Liquidity shock object exists"""
        shock = cex_response.get("liquidity_shock")
        assert shock is not None, "liquidity_shock not present in response"
        print(f"PASS: liquidity_shock present with state={shock.get('state')}")
    
    def test_liquidity_shock_state(self, cex_response):
        """Shock state is one of 5 valid states"""
        shock = cex_response.get("liquidity_shock", {})
        valid_states = [
            "strong_bullish_shock", "bullish_imbalance", 
            "neutral", 
            "bearish_imbalance", "strong_bearish_shock"
        ]
        assert shock.get("state") in valid_states, f"Invalid shock state: {shock.get('state')}"
        assert shock.get("label") is not None, "shock.label missing"
        print(f"PASS: shock state={shock.get('state')}, label={shock.get('label')}")
    
    def test_liquidity_shock_buy_sell(self, cex_response):
        """Shock has buy_power and sell_supply"""
        shock = cex_response.get("liquidity_shock", {})
        assert "buy_power" in shock, "shock.buy_power missing"
        assert "sell_supply" in shock, "shock.sell_supply missing"
        assert "net" in shock, "shock.net missing"
        assert shock.get("buy_power_fmt") is not None, "shock.buy_power_fmt missing"
        assert shock.get("sell_supply_fmt") is not None, "shock.sell_supply_fmt missing"
        assert shock.get("net_fmt") is not None, "shock.net_fmt missing"
        print(f"PASS: buy_power={shock.get('buy_power_fmt')}, sell_supply={shock.get('sell_supply_fmt')}, net={shock.get('net_fmt')}")
    
    def test_liquidity_shock_interpretation(self, cex_response):
        """Shock has interpretation"""
        shock = cex_response.get("liquidity_shock", {})
        assert "interpretation" in shock, "shock.interpretation missing"
        print(f"PASS: shock interpretation='{shock.get('interpretation')}'")
    
    def test_liquidity_shock_drivers(self, cex_response):
        """Shock has drivers array"""
        shock = cex_response.get("liquidity_shock", {})
        drivers = shock.get("drivers", [])
        assert isinstance(drivers, list), "shock.drivers is not a list"
        print(f"PASS: shock drivers count={len(drivers)}, sample={drivers[:2] if drivers else 'none'}")
    
    def test_liquidity_shock_exchange_drivers(self, cex_response):
        """Shock has exchange_drivers with contribution"""
        shock = cex_response.get("liquidity_shock", {})
        ex_drivers = shock.get("exchange_drivers", [])
        assert isinstance(ex_drivers, list), "shock.exchange_drivers is not a list"
        if ex_drivers:
            ed = ex_drivers[0]
            assert "exchange" in ed, "exchange_driver.exchange missing"
            assert "contribution" in ed, "exchange_driver.contribution missing"
            assert "dominant_factor" in ed, "exchange_driver.dominant_factor missing"
            print(f"PASS: exchange_drivers count={len(ex_drivers)}, top={ed.get('exchange')}: {ed.get('contribution_fmt')}")
        else:
            print("WARN: No exchange_drivers (may be due to data)")
    
    # ══════════════════════════════════════════════════════════
    # Sprint B: EXCHANGE INVENTORY
    # ══════════════════════════════════════════════════════════
    def test_exchange_inventory_present(self, cex_response):
        """Exchange inventory array exists"""
        inventory = cex_response.get("exchange_inventory")
        assert inventory is not None, "exchange_inventory not present"
        assert isinstance(inventory, list), "exchange_inventory is not a list"
        print(f"PASS: exchange_inventory present with {len(inventory)} tokens")
    
    def test_exchange_inventory_structure(self, cex_response):
        """Each inventory item has required fields"""
        inventory = cex_response.get("exchange_inventory", [])
        if not inventory:
            pytest.skip("No inventory data to test")
        
        item = inventory[0]
        required = ["token", "deposits", "withdrawals", "net_change", "state", "interpretation"]
        for field in required:
            assert field in item, f"inventory item missing {field}"
        
        assert item.get("state") in ["growing", "shrinking", "stable"], f"Invalid state: {item.get('state')}"
        print(f"PASS: inventory[0] token={item.get('token')}, state={item.get('state')}, net={item.get('net_change_fmt')}")
    
    def test_exchange_inventory_per_exchange(self, cex_response):
        """Inventory items have per_exchange breakdown"""
        inventory = cex_response.get("exchange_inventory", [])
        if not inventory:
            pytest.skip("No inventory data")
        
        item = inventory[0]
        per_ex = item.get("per_exchange", [])
        assert isinstance(per_ex, list), "per_exchange is not a list"
        if per_ex:
            pe = per_ex[0]
            assert "exchange" in pe, "per_exchange.exchange missing"
            assert "deposits" in pe, "per_exchange.deposits missing"
            assert "withdrawals" in pe, "per_exchange.withdrawals missing"
            assert "net" in pe, "per_exchange.net missing"
            print(f"PASS: per_exchange count={len(per_ex)}, top={pe.get('exchange')}: net={pe.get('net_fmt')}")
        else:
            print("WARN: No per_exchange data")
    
    # ══════════════════════════════════════════════════════════
    # Sprint B: FLOW TYPE CLASSIFICATION
    # ══════════════════════════════════════════════════════════
    def test_flow_classification_present(self, cex_response):
        """Flow classification object exists"""
        flow = cex_response.get("flow_classification")
        assert flow is not None, "flow_classification not present"
        print(f"PASS: flow_classification present, dominant={flow.get('dominant_label')}")
    
    def test_flow_classification_composition(self, cex_response):
        """Flow classification has 4 flow types"""
        flow = cex_response.get("flow_classification", {})
        composition = flow.get("composition", [])
        assert len(composition) == 4, f"Expected 4 flow types, got {len(composition)}"
        
        types_found = [c.get("type") for c in composition]
        expected_types = ["distribution", "accumulation", "liquidity_provision", "market_making"]
        for t in expected_types:
            assert t in types_found, f"Missing flow type: {t}"
        print(f"PASS: All 4 flow types present: {types_found}")
    
    def test_flow_classification_dominant(self, cex_response):
        """Flow classification has dominant type"""
        flow = cex_response.get("flow_classification", {})
        assert "dominant_type" in flow, "dominant_type missing"
        assert "dominant_label" in flow, "dominant_label missing"
        assert "dominant_pct" in flow, "dominant_pct missing"
        assert "interpretation" in flow, "interpretation missing"
        print(f"PASS: dominant={flow.get('dominant_label')} ({flow.get('dominant_pct')}%), interpretation='{flow.get('interpretation')}'")
    
    def test_flow_classification_item_structure(self, cex_response):
        """Each flow type has required fields"""
        flow = cex_response.get("flow_classification", {})
        composition = flow.get("composition", [])
        if not composition:
            pytest.skip("No flow composition data")
        
        item = composition[0]
        required = ["type", "label", "usd", "usd_fmt", "percentage", "tx_count"]
        for field in required:
            assert field in item, f"composition item missing {field}"
        print(f"PASS: composition[0] type={item.get('type')}, label={item.get('label')}, pct={item.get('percentage')}%")


class TestCexContextRegressionSprintA:
    """Regression tests for Sprint A v2.1 fields"""
    
    @pytest.fixture(scope="class")
    def cex_response(self):
        response = requests.get(
            f"{BASE_URL}/api/onchain/cex/context",
            params={"chainId": 1, "window": "30d"},
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        return data
    
    # ══════════════════════════════════════════════════════════
    # HERO BLOCK REGRESSION
    # ══════════════════════════════════════════════════════════
    def test_hero_drivers(self, cex_response):
        """Hero has drivers array"""
        drivers = cex_response.get("drivers", [])
        assert isinstance(drivers, list), "drivers is not a list"
        print(f"PASS: drivers count={len(drivers)}, items={drivers}")
    
    def test_hero_offsetting_factors(self, cex_response):
        """Hero has offsetting_factors array"""
        offsetting = cex_response.get("offsetting_factors", [])
        assert isinstance(offsetting, list), "offsetting_factors is not a list"
        print(f"PASS: offsetting_factors count={len(offsetting)}, items={offsetting}")
    
    def test_hero_indicators(self, cex_response):
        """Hero has 3 indicators"""
        indicators = cex_response.get("indicators")
        assert indicators is not None, "indicators not present"
        assert "sell_pressure" in indicators, "sell_pressure missing"
        assert "liquidity" in indicators, "liquidity missing"
        assert "confidence" in indicators, "confidence missing"
        print(f"PASS: indicators sell_pressure={indicators.get('sell_pressure')}, liquidity={indicators.get('liquidity')}, confidence={indicators.get('confidence')}")
    
    # ══════════════════════════════════════════════════════════
    # EXCHANGE FLOWS REGRESSION
    # ══════════════════════════════════════════════════════════
    def test_exchange_flows_present(self, cex_response):
        """Top exchanges array exists"""
        exchanges = cex_response.get("top_exchanges", [])
        assert isinstance(exchanges, list), "top_exchanges is not a list"
        assert len(exchanges) > 0, "No exchanges in top_exchanges"
        print(f"PASS: top_exchanges count={len(exchanges)}")
    
    def test_exchange_flows_market_share(self, cex_response):
        """Exchanges have market_share"""
        exchanges = cex_response.get("top_exchanges", [])
        if not exchanges:
            pytest.skip("No exchanges")
        ex = exchanges[0]
        assert "market_share" in ex, "market_share missing"
        print(f"PASS: {ex.get('entityName')} market_share={ex.get('market_share')}%")
    
    def test_exchange_flows_dominant_direction(self, cex_response):
        """Exchanges have dominant_direction"""
        exchanges = cex_response.get("top_exchanges", [])
        if not exchanges:
            pytest.skip("No exchanges")
        ex = exchanges[0]
        assert "dominant_direction" in ex, "dominant_direction missing"
        print(f"PASS: {ex.get('entityName')} dominant_direction={ex.get('dominant_direction')}")
    
    def test_exchange_flows_behavior_label(self, cex_response):
        """Exchanges have behavior_label"""
        exchanges = cex_response.get("top_exchanges", [])
        if not exchanges:
            pytest.skip("No exchanges")
        ex = exchanges[0]
        assert "behavior_label" in ex, "behavior_label missing"
        print(f"PASS: {ex.get('entityName')} behavior_label={ex.get('behavior_label')}")
    
    # ══════════════════════════════════════════════════════════
    # LARGEST TRANSFERS REGRESSION
    # ══════════════════════════════════════════════════════════
    def test_transfers_present(self, cex_response):
        """Largest transfers array exists"""
        transfers = cex_response.get("largest_transfers", [])
        assert isinstance(transfers, list), "largest_transfers is not a list"
        print(f"PASS: largest_transfers count={len(transfers)}")
    
    def test_transfers_impact_label(self, cex_response):
        """Transfers have impact_label"""
        transfers = cex_response.get("largest_transfers", [])
        if not transfers:
            pytest.skip("No transfers")
        t = transfers[0]
        assert "impact_label" in t, "impact_label missing"
        valid_labels = ["BUY LIQUIDITY", "SELL PRESSURE", "ACCUMULATION", "CAPITAL EXIT"]
        assert t.get("impact_label") in valid_labels, f"Invalid impact_label: {t.get('impact_label')}"
        print(f"PASS: transfer[0] {t.get('token')} {t.get('usd_fmt')} impact_label={t.get('impact_label')}")
    
    # ══════════════════════════════════════════════════════════
    # OTHER REGRESSION FIELDS
    # ══════════════════════════════════════════════════════════
    def test_market_liquidity(self, cex_response):
        """Market liquidity map present"""
        liq = cex_response.get("market_liquidity")
        assert liq is not None, "market_liquidity not present"
        assert "buy_power" in liq, "buy_power missing"
        assert "sell_supply" in liq, "sell_supply missing"
        assert "net_liquidity" in liq, "net_liquidity missing"
        print(f"PASS: market_liquidity buy={liq.get('buy_power_fmt')}, sell={liq.get('sell_supply_fmt')}, net={liq.get('net_liquidity_fmt')}")
    
    def test_pump_setups(self, cex_response):
        """Pump setups present"""
        setups = cex_response.get("pump_setups", [])
        assert isinstance(setups, list), "pump_setups is not a list"
        if setups:
            s = setups[0]
            assert "token" in s, "pump setup token missing"
            assert "drivers" in s, "pump setup drivers missing"
            print(f"PASS: pump_setups[0] token={s.get('token')}, pump_prob={s.get('pump_probability')}%")
        else:
            print("WARN: No pump setups (may be due to data)")
    
    def test_rotation_fallback(self, cex_response):
        """Rotation fallback array present"""
        fallback = cex_response.get("rotation_fallback")
        assert fallback is not None, "rotation_fallback not present"
        assert isinstance(fallback, list), "rotation_fallback is not a list"
        print(f"PASS: rotation_fallback present (count={len(fallback)})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
