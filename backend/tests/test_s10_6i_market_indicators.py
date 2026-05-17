"""
S10.6I.5 — Market Indicators Layer Tests
Testing all 32 indicator calculators:
- 8 PRICE_STRUCTURE
- 6 MOMENTUM
- 6 VOLUME
- 6 ORDER_BOOK
- 6 POSITIONING (NEW in S10.6I.5)

Indicators = SENSORS, not SIGNALS

S10.6I.5 adds 6 Positioning / Derivatives indicators for RISK ASSESSMENT:
- Open Interest Level (OIL) - oi_level
- Open Interest Delta (OID) - oi_delta
- OI / Volume Ratio (OVR) - oi_volume_ratio
- Funding Rate Pressure (FRP) - funding_pressure
- Long / Short Ratio (LSR) - long_short_ratio
- Position Crowding Index (PCI) - position_crowding

This is RISK ASSESSMENT, not DIRECTION.
Indicator v1 COMPLETE (32/32).
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ══════════════════════════════════════════════════════════════════
# INDICATOR DEFINITIONS (S10.6I.3: 8 + 6 + 6 = 20 total)
# ══════════════════════════════════════════════════════════════════

PRICE_STRUCTURE_INDICATORS = [
    'ema_distance_fast',
    'ema_distance_mid', 
    'ema_distance_slow',
    'vwap_deviation',
    'median_price_deviation',
    'atr_normalized',
    'trend_slope',
    'range_compression'
]

MOMENTUM_INDICATORS = [
    'rsi_normalized',
    'stochastic',
    'macd_delta',
    'roc',
    'momentum_decay',
    'directional_momentum_balance'
]

# S10.6I.3 — 6 Volume / Participation indicators
VOLUME_INDICATORS = [
    'volume_index',           # Total Volume Index
    'volume_delta',           # Volume Delta
    'buy_sell_ratio',         # Buy / Sell Ratio
    'volume_price_response',  # Volume vs Price Response
    'relative_volume',        # Relative Volume Index
    'participation_intensity' # Participation Intensity
]

# S10.6I.4 — 6 Order Book / Depth indicators
ORDER_BOOK_INDICATORS = [
    'book_imbalance',         # Order Book Imbalance (OBI)
    'depth_density',          # Depth Density Index (DDI)
    'liquidity_walls',        # Liquidity Wall Strength (LWS)
    'absorption_strength',    # Absorption Strength (ABS)
    'liquidity_vacuum',       # Liquidity Vacuum Index (LVI)
    'spread_pressure'         # Spread Pressure Index (SPI)
]

# S10.6I.5 — 6 Positioning / Derivatives indicators (RISK ASSESSMENT)
POSITIONING_INDICATORS = [
    'oi_level',               # Open Interest Level (OIL)
    'oi_delta',               # Open Interest Delta (OID)
    'oi_volume_ratio',        # OI / Volume Ratio (OVR)
    'funding_pressure',       # Funding Rate Pressure (FRP)
    'long_short_ratio',       # Long / Short Ratio (LSR)
    'position_crowding'       # Position Crowding Index (PCI)
]

# Expected ranges for normalized values
INDICATOR_RANGES = {
    # PRICE_STRUCTURE (8)
    'ema_distance_fast': (-3, 3),
    'ema_distance_mid': (-3, 3),
    'ema_distance_slow': (-5, 5),
    'vwap_deviation': (-3, 3),
    'median_price_deviation': (-1, 1),
    'atr_normalized': (0, 3),
    'trend_slope': (-2, 2),
    'range_compression': (0, 3),
    # MOMENTUM (6)
    'rsi_normalized': (-1, 1),
    'stochastic': (-1, 1),
    'macd_delta': (-1, 1),
    'roc': (-2, 2),
    'momentum_decay': (0, 3),
    'directional_momentum_balance': (-1, 1),
    # VOLUME (6) — S10.6I.3
    'volume_index': (-1, 1),
    'volume_delta': (-1, 1),
    'buy_sell_ratio': (-1, 1),
    'volume_price_response': (0, 1),
    'relative_volume': (-1, 1),
    'participation_intensity': (0, 1),
    # ORDER_BOOK (6) — S10.6I.4
    'book_imbalance': (-1, 1),       # Volume skew between bid and ask
    'depth_density': (0, 1),          # Density around current price
    'liquidity_walls': (0, 1),        # Presence of liquidity walls
    'absorption_strength': (0, 1),    # Limit order absorption
    'liquidity_vacuum': (0, 1),       # Voids in order book
    'spread_pressure': (0, 1),        # Spread tension
    # POSITIONING (6) — S10.6I.5 (RISK ASSESSMENT)
    'oi_level': (-1, 1),              # OI vs SMA normalized
    'oi_delta': (-1, 1),              # OI change (tanh normalized)
    'oi_volume_ratio': (-1, 1),       # OI delta / volume
    'funding_pressure': (-1, 1),      # Funding rate relative to avg
    'long_short_ratio': (-1, 1),      # Log-normalized L/S ratio
    'position_crowding': (0, 1)       # Composite crowding index
}

# Total expected indicators
TOTAL_INDICATORS = 32  # 8 + 6 + 6 + 6 + 6


class TestIndicatorStatus:
    """Registry status tests"""
    
    def test_registry_status_returns_32_indicators(self):
        """GET /api/v10/exchange/indicators/status - verify 32 indicators registered (S10.6I.5 COMPLETE)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['status']['totalRegistered'] == TOTAL_INDICATORS
        assert data['status']['byCategory']['PRICE_STRUCTURE'] == 8
        assert data['status']['byCategory']['MOMENTUM'] == 6
        assert data['status']['byCategory']['VOLUME'] == 6
        assert data['status']['byCategory']['ORDER_BOOK'] == 6
        assert data['status']['byCategory']['POSITIONING'] == 6  # S10.6I.5
        assert data['status']['ready'] == True
        assert len(data['status']['missing']) == 0
        print(f"✓ Registry status: {TOTAL_INDICATORS} indicators (8+6+6+6+6) - ALL CATEGORIES COMPLETE")
    
    def test_registry_all_categories_populated(self):
        """All 5 categories now have indicators (S10.6I.5 COMPLETE)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/status")
        data = response.json()
        
        # All categories now populated
        assert data['status']['byCategory']['PRICE_STRUCTURE'] == 8
        assert data['status']['byCategory']['MOMENTUM'] == 6
        assert data['status']['byCategory']['VOLUME'] == 6
        assert data['status']['byCategory']['ORDER_BOOK'] == 6
        assert data['status']['byCategory']['POSITIONING'] == 6
        assert data['status']['ready'] == True
        assert data['status']['missing'] == []
        print("✓ All 5 categories populated - Indicator v1 COMPLETE (32/32)")


class TestIndicatorDefinitions:
    """Indicator definitions metadata tests"""
    
    def test_all_definitions_returns_32(self):
        """GET /api/v10/exchange/indicators/definitions - all 32 definitions"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/definitions")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['count'] == TOTAL_INDICATORS
        assert len(data['definitions']) == TOTAL_INDICATORS
        print(f"✓ All definitions: {data['count']} indicators (S10.6I.5 COMPLETE)")
    
    def test_definition_structure_complete(self):
        """Verify each definition has required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/definitions")
        data = response.json()
        
        required_fields = ['id', 'name', 'category', 'description', 'formula', 
                          'range', 'normalized', 'interpretations', 'dependencies', 'parameters']
        
        for definition in data['definitions']:
            for field in required_fields:
                assert field in definition, f"Missing field {field} in {definition.get('id')}"
            
            # Verify range structure
            assert 'min' in definition['range']
            assert 'max' in definition['range']
            
            # Verify interpretations structure
            assert 'low' in definition['interpretations']
            assert 'neutral' in definition['interpretations']
            assert 'high' in definition['interpretations']
        
        print("✓ All definitions have complete structure")
    
    def test_price_structure_definitions(self):
        """GET /api/v10/exchange/indicators/definitions/PRICE_STRUCTURE - 8 indicators"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/definitions/PRICE_STRUCTURE")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['category'] == 'PRICE_STRUCTURE'
        assert data['count'] == 8
        
        ids = [d['id'] for d in data['definitions']]
        for expected_id in PRICE_STRUCTURE_INDICATORS:
            assert expected_id in ids, f"Missing {expected_id}"
        
        print(f"✓ PRICE_STRUCTURE definitions: {data['count']} indicators")
    
    def test_momentum_definitions(self):
        """GET /api/v10/exchange/indicators/definitions/MOMENTUM - 6 indicators"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/definitions/MOMENTUM")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['category'] == 'MOMENTUM'
        assert data['count'] == 6
        
        ids = [d['id'] for d in data['definitions']]
        for expected_id in MOMENTUM_INDICATORS:
            assert expected_id in ids, f"Missing {expected_id}"
        
        print(f"✓ MOMENTUM definitions: {data['count']} indicators")
    
    def test_volume_definitions(self):
        """GET /api/v10/exchange/indicators/definitions/VOLUME - 6 indicators (S10.6I.3)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/definitions/VOLUME")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['category'] == 'VOLUME'
        assert data['count'] == 6
        
        ids = [d['id'] for d in data['definitions']]
        for expected_id in VOLUME_INDICATORS:
            assert expected_id in ids, f"Missing {expected_id}"
        
        print(f"✓ VOLUME definitions: {data['count']} indicators (S10.6I.3)")
    
    def test_order_book_definitions(self):
        """GET /api/v10/exchange/indicators/definitions/ORDER_BOOK - 6 indicators (S10.6I.4)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/definitions/ORDER_BOOK")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['category'] == 'ORDER_BOOK'
        assert data['count'] == 6
        
        ids = [d['id'] for d in data['definitions']]
        for expected_id in ORDER_BOOK_INDICATORS:
            assert expected_id in ids, f"Missing {expected_id}"
        
        print(f"✓ ORDER_BOOK definitions: {data['count']} indicators (S10.6I.4)")
    
    def test_positioning_definitions(self):
        """GET /api/v10/exchange/indicators/definitions/POSITIONING - 6 indicators (S10.6I.5)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/definitions/POSITIONING")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['category'] == 'POSITIONING'
        assert data['count'] == 6
        
        ids = [d['id'] for d in data['definitions']]
        for expected_id in POSITIONING_INDICATORS:
            assert expected_id in ids, f"Missing {expected_id}"
        
        # Verify definitions have required fields
        for definition in data['definitions']:
            assert 'formula' in definition
            assert 'interpretations' in definition
            assert 'low' in definition['interpretations']
            assert 'neutral' in definition['interpretations']
            assert 'high' in definition['interpretations']
        
        print(f"✓ POSITIONING definitions: {data['count']} indicators (S10.6I.5 - RISK ASSESSMENT)")
    
    def test_invalid_category_returns_error(self):
        """Invalid category returns error"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/definitions/INVALID")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == False
        assert 'error' in data
        print("✓ Invalid category returns error")


class TestIndicatorSnapshot:
    """Full indicator snapshot tests"""
    
    def test_btcusdt_snapshot_returns_32_indicators(self):
        """GET /api/v10/exchange/indicators/BTCUSDT - full snapshot with 32 indicators"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['symbol'] == 'BTCUSDT'
        
        snapshot = data['snapshot']
        assert len(snapshot['indicators']) == TOTAL_INDICATORS
        assert 'byCategory' in snapshot
        assert 'byId' in snapshot
        assert 'calculatedAt' in snapshot
        assert 'calculationMs' in snapshot
        
        print(f"✓ BTCUSDT snapshot: {len(snapshot['indicators'])} indicators (ALL CATEGORIES COMPLETE)")
    
    def test_snapshot_byCategory_structure(self):
        """Verify byCategory grouping is correct (8+6+6+6+6)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT")
        data = response.json()
        
        by_category = data['snapshot']['byCategory']
        assert len(by_category['PRICE_STRUCTURE']) == 8
        assert len(by_category['MOMENTUM']) == 6
        assert len(by_category['VOLUME']) == 6
        assert len(by_category['ORDER_BOOK']) == 6
        assert len(by_category['POSITIONING']) == 6  # S10.6I.5
        
        print("✓ byCategory structure correct (8+6+6+6+6)")
    
    def test_snapshot_byId_lookup(self):
        """Verify byId provides quick lookup for all 32 indicators"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT")
        data = response.json()
        
        by_id = data['snapshot']['byId']
        
        # Check all 32 indicators accessible by ID
        all_ids = PRICE_STRUCTURE_INDICATORS + MOMENTUM_INDICATORS + VOLUME_INDICATORS + ORDER_BOOK_INDICATORS + POSITIONING_INDICATORS
        for ind_id in all_ids:
            assert ind_id in by_id, f"Missing {ind_id} in byId lookup"
            assert by_id[ind_id]['id'] == ind_id
        
        print(f"✓ byId lookup contains all {TOTAL_INDICATORS} indicators")


class TestPriceStructureIndicators:
    """Test 8 PRICE_STRUCTURE indicators"""
    
    def test_price_structure_category_returns_8(self):
        """GET /api/v10/exchange/indicators/BTCUSDT/PRICE_STRUCTURE"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/PRICE_STRUCTURE")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['category'] == 'PRICE_STRUCTURE'
        assert data['count'] == 8
        
        print(f"✓ PRICE_STRUCTURE category: {data['count']} indicators")
    
    def test_price_structure_all_normalized(self):
        """All PRICE_STRUCTURE indicators should be normalized"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/PRICE_STRUCTURE")
        data = response.json()
        
        for ind in data['indicators']:
            assert ind['normalized'] == True, f"{ind['id']} not normalized"
            assert ind['category'] == 'PRICE_STRUCTURE'
        
        print("✓ All PRICE_STRUCTURE indicators normalized")
    
    def test_price_structure_values_in_range(self):
        """All PRICE_STRUCTURE values within expected ranges"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/PRICE_STRUCTURE")
        data = response.json()
        
        for ind in data['indicators']:
            ind_id = ind['id']
            value = ind['value']
            min_val, max_val = INDICATOR_RANGES[ind_id]
            
            assert min_val <= value <= max_val, \
                f"{ind_id} value {value} out of range [{min_val}, {max_val}]"
        
        print("✓ All PRICE_STRUCTURE values in expected ranges")
    
    def test_price_structure_interpretations_not_empty(self):
        """All PRICE_STRUCTURE indicators have non-empty interpretations"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/PRICE_STRUCTURE")
        data = response.json()
        
        for ind in data['indicators']:
            assert ind['interpretation'], f"{ind['id']} has empty interpretation"
            assert len(ind['interpretation']) > 0
        
        print("✓ All PRICE_STRUCTURE indicators have interpretations")


class TestMomentumIndicators:
    """Test 6 MOMENTUM indicators"""
    
    def test_momentum_category_returns_6(self):
        """GET /api/v10/exchange/indicators/BTCUSDT/MOMENTUM"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/MOMENTUM")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['category'] == 'MOMENTUM'
        assert data['count'] == 6
        
        print(f"✓ MOMENTUM category: {data['count']} indicators")
    
    def test_momentum_all_normalized(self):
        """All MOMENTUM indicators should be normalized"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/MOMENTUM")
        data = response.json()
        
        for ind in data['indicators']:
            assert ind['normalized'] == True, f"{ind['id']} not normalized"
            assert ind['category'] == 'MOMENTUM'
        
        print("✓ All MOMENTUM indicators normalized")
    
    def test_momentum_values_in_range(self):
        """All MOMENTUM values within expected ranges"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/MOMENTUM")
        data = response.json()
        
        for ind in data['indicators']:
            ind_id = ind['id']
            value = ind['value']
            min_val, max_val = INDICATOR_RANGES[ind_id]
            
            assert min_val <= value <= max_val, \
                f"{ind_id} value {value} out of range [{min_val}, {max_val}]"
        
        print("✓ All MOMENTUM values in expected ranges")
    
    def test_momentum_interpretations_not_empty(self):
        """All MOMENTUM indicators have non-empty interpretations"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/MOMENTUM")
        data = response.json()
        
        for ind in data['indicators']:
            assert ind['interpretation'], f"{ind['id']} has empty interpretation"
            assert len(ind['interpretation']) > 0
        
        print("✓ All MOMENTUM indicators have interpretations")


class TestVolumeIndicators:
    """Test 6 VOLUME indicators (S10.6I.3)"""
    
    def test_volume_category_returns_6(self):
        """GET /api/v10/exchange/indicators/BTCUSDT/VOLUME - 6 volume indicators"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/VOLUME")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['category'] == 'VOLUME'
        assert data['count'] == 6
        
        print(f"✓ VOLUME category: {data['count']} indicators (S10.6I.3)")
    
    def test_volume_all_normalized(self):
        """All VOLUME indicators should be normalized"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/VOLUME")
        data = response.json()
        
        for ind in data['indicators']:
            assert ind['normalized'] == True, f"{ind['id']} not normalized"
            assert ind['category'] == 'VOLUME'
        
        print("✓ All VOLUME indicators normalized")
    
    def test_volume_index_normalized_minus1_to_1(self):
        """volume_index normalized in [-1, 1]"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/VOLUME")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'volume_index'), None)
        assert ind is not None, "volume_index not found"
        assert -1 <= ind['value'] <= 1, f"volume_index {ind['value']} out of range [-1, 1]"
        assert ind['interpretation'], "volume_index has empty interpretation"
        
        print(f"✓ volume_index: {ind['value']:.4f} in [-1, 1] - '{ind['interpretation']}'")
    
    def test_volume_delta_normalized_minus1_to_1(self):
        """volume_delta normalized in [-1, 1]"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/VOLUME")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'volume_delta'), None)
        assert ind is not None, "volume_delta not found"
        assert -1 <= ind['value'] <= 1, f"volume_delta {ind['value']} out of range [-1, 1]"
        assert ind['interpretation'], "volume_delta has empty interpretation"
        
        print(f"✓ volume_delta: {ind['value']:.4f} in [-1, 1] - '{ind['interpretation']}'")
    
    def test_buy_sell_ratio_normalized_minus1_to_1(self):
        """buy_sell_ratio normalized in [-1, 1]"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/VOLUME")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'buy_sell_ratio'), None)
        assert ind is not None, "buy_sell_ratio not found"
        assert -1 <= ind['value'] <= 1, f"buy_sell_ratio {ind['value']} out of range [-1, 1]"
        assert ind['interpretation'], "buy_sell_ratio has empty interpretation"
        
        print(f"✓ buy_sell_ratio: {ind['value']:.4f} in [-1, 1] - '{ind['interpretation']}'")
    
    def test_volume_price_response_normalized_0_to_1(self):
        """volume_price_response normalized in [0, 1]"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/VOLUME")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'volume_price_response'), None)
        assert ind is not None, "volume_price_response not found"
        assert 0 <= ind['value'] <= 1, f"volume_price_response {ind['value']} out of range [0, 1]"
        assert ind['interpretation'], "volume_price_response has empty interpretation"
        
        print(f"✓ volume_price_response: {ind['value']:.4f} in [0, 1] - '{ind['interpretation']}'")
    
    def test_relative_volume_normalized_minus1_to_1(self):
        """relative_volume normalized in [-1, 1]"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/VOLUME")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'relative_volume'), None)
        assert ind is not None, "relative_volume not found"
        assert -1 <= ind['value'] <= 1, f"relative_volume {ind['value']} out of range [-1, 1]"
        assert ind['interpretation'], "relative_volume has empty interpretation"
        
        print(f"✓ relative_volume: {ind['value']:.4f} in [-1, 1] - '{ind['interpretation']}'")
    
    def test_participation_intensity_normalized_0_to_1(self):
        """participation_intensity normalized in [0, 1]"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/VOLUME")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'participation_intensity'), None)
        assert ind is not None, "participation_intensity not found"
        assert 0 <= ind['value'] <= 1, f"participation_intensity {ind['value']} out of range [0, 1]"
        assert ind['interpretation'], "participation_intensity has empty interpretation"
        
        print(f"✓ participation_intensity: {ind['value']:.4f} in [0, 1] - '{ind['interpretation']}'")
    
    def test_volume_interpretations_not_empty(self):
        """All VOLUME indicators have non-empty interpretations"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/VOLUME")
        data = response.json()
        
        for ind in data['indicators']:
            assert ind['interpretation'], f"{ind['id']} has empty interpretation"
            assert len(ind['interpretation']) > 0
        
        print("✓ All VOLUME indicators have interpretations")


class TestOrderBookIndicators:
    """Test 6 ORDER_BOOK indicators (S10.6I.4)"""
    
    def test_order_book_category_returns_6(self):
        """GET /api/v10/exchange/indicators/BTCUSDT/ORDER_BOOK - 6 order book indicators"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/ORDER_BOOK")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['category'] == 'ORDER_BOOK'
        assert data['count'] == 6
        
        print(f"✓ ORDER_BOOK category: {data['count']} indicators (S10.6I.4)")
    
    def test_order_book_all_normalized(self):
        """All ORDER_BOOK indicators should be normalized"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/ORDER_BOOK")
        data = response.json()
        
        for ind in data['indicators']:
            assert ind['normalized'] == True, f"{ind['id']} not normalized"
            assert ind['category'] == 'ORDER_BOOK'
        
        print("✓ All ORDER_BOOK indicators normalized")
    
    def test_book_imbalance_normalized_minus1_to_1(self):
        """book_imbalance normalized in [-1, 1] - OBI measures volume skew"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/ORDER_BOOK")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'book_imbalance'), None)
        assert ind is not None, "book_imbalance not found"
        assert -1 <= ind['value'] <= 1, f"book_imbalance {ind['value']} out of range [-1, 1]"
        assert ind['interpretation'], "book_imbalance has empty interpretation"
        
        print(f"✓ book_imbalance: {ind['value']:.4f} in [-1, 1] - '{ind['interpretation']}'")
    
    def test_depth_density_normalized_0_to_1(self):
        """depth_density normalized in [0, 1] - DDI measures order book density"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/ORDER_BOOK")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'depth_density'), None)
        assert ind is not None, "depth_density not found"
        assert 0 <= ind['value'] <= 1, f"depth_density {ind['value']} out of range [0, 1]"
        assert ind['interpretation'], "depth_density has empty interpretation"
        
        print(f"✓ depth_density: {ind['value']:.4f} in [0, 1] - '{ind['interpretation']}'")
    
    def test_liquidity_walls_normalized_0_to_1(self):
        """liquidity_walls normalized in [0, 1] - LWS measures wall presence"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/ORDER_BOOK")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'liquidity_walls'), None)
        assert ind is not None, "liquidity_walls not found"
        assert 0 <= ind['value'] <= 1, f"liquidity_walls {ind['value']} out of range [0, 1]"
        assert ind['interpretation'], "liquidity_walls has empty interpretation"
        
        print(f"✓ liquidity_walls: {ind['value']:.4f} in [0, 1] - '{ind['interpretation']}'")
    
    def test_absorption_strength_normalized_0_to_1(self):
        """absorption_strength normalized in [0, 1] - ABS measures limit absorption"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/ORDER_BOOK")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'absorption_strength'), None)
        assert ind is not None, "absorption_strength not found"
        assert 0 <= ind['value'] <= 1, f"absorption_strength {ind['value']} out of range [0, 1]"
        assert ind['interpretation'], "absorption_strength has empty interpretation"
        
        print(f"✓ absorption_strength: {ind['value']:.4f} in [0, 1] - '{ind['interpretation']}'")
    
    def test_liquidity_vacuum_normalized_0_to_1(self):
        """liquidity_vacuum normalized in [0, 1] - LVI measures order book voids"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/ORDER_BOOK")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'liquidity_vacuum'), None)
        assert ind is not None, "liquidity_vacuum not found"
        assert 0 <= ind['value'] <= 1, f"liquidity_vacuum {ind['value']} out of range [0, 1]"
        assert ind['interpretation'], "liquidity_vacuum has empty interpretation"
        
        print(f"✓ liquidity_vacuum: {ind['value']:.4f} in [0, 1] - '{ind['interpretation']}'")
    
    def test_spread_pressure_normalized_0_to_1(self):
        """spread_pressure normalized in [0, 1] - SPI measures spread tension"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/ORDER_BOOK")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'spread_pressure'), None)
        assert ind is not None, "spread_pressure not found"
        assert 0 <= ind['value'] <= 1, f"spread_pressure {ind['value']} out of range [0, 1]"
        assert ind['interpretation'], "spread_pressure has empty interpretation"
        
        print(f"✓ spread_pressure: {ind['value']:.4f} in [0, 1] - '{ind['interpretation']}'")
    
    def test_order_book_interpretations_not_empty(self):
        """All ORDER_BOOK indicators have non-empty interpretations"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/ORDER_BOOK")
        data = response.json()
        
        for ind in data['indicators']:
            assert ind['interpretation'], f"{ind['id']} has empty interpretation"
            assert len(ind['interpretation']) > 0
        
        print("✓ All ORDER_BOOK indicators have interpretations")


class TestPositioningIndicators:
    """Test 6 POSITIONING indicators (S10.6I.5) - RISK ASSESSMENT, not DIRECTION"""
    
    def test_positioning_category_returns_6(self):
        """GET /api/v10/exchange/indicators/BTCUSDT/POSITIONING - 6 positioning indicators"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/POSITIONING")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['category'] == 'POSITIONING'
        assert data['count'] == 6
        
        print(f"✓ POSITIONING category: {data['count']} indicators (S10.6I.5)")
    
    def test_positioning_all_normalized(self):
        """All POSITIONING indicators should be normalized"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/POSITIONING")
        data = response.json()
        
        for ind in data['indicators']:
            assert ind['normalized'] == True, f"{ind['id']} not normalized"
            assert ind['category'] == 'POSITIONING'
        
        print("✓ All POSITIONING indicators normalized")
    
    def test_oi_level_normalized_minus1_to_1(self):
        """oi_level (OIL) normalized in [-1, 1] - Market position load"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/POSITIONING")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'oi_level'), None)
        assert ind is not None, "oi_level not found"
        assert -1 <= ind['value'] <= 1, f"oi_level {ind['value']} out of range [-1, 1]"
        assert ind['interpretation'], "oi_level has empty interpretation"
        
        print(f"✓ oi_level: {ind['value']:.4f} in [-1, 1] - '{ind['interpretation']}'")
    
    def test_oi_delta_normalized_minus1_to_1(self):
        """oi_delta (OID) normalized in [-1, 1] via tanh - Position inflow/outflow"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/POSITIONING")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'oi_delta'), None)
        assert ind is not None, "oi_delta not found"
        assert -1 <= ind['value'] <= 1, f"oi_delta {ind['value']} out of range [-1, 1]"
        assert ind['interpretation'], "oi_delta has empty interpretation"
        
        print(f"✓ oi_delta: {ind['value']:.4f} in [-1, 1] (tanh) - '{ind['interpretation']}'")
    
    def test_oi_volume_ratio_normalized_minus1_to_1(self):
        """oi_volume_ratio (OVR) normalized in [-1, 1] - New positions vs turnover"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/POSITIONING")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'oi_volume_ratio'), None)
        assert ind is not None, "oi_volume_ratio not found"
        assert -1 <= ind['value'] <= 1, f"oi_volume_ratio {ind['value']} out of range [-1, 1]"
        assert ind['interpretation'], "oi_volume_ratio has empty interpretation"
        
        print(f"✓ oi_volume_ratio: {ind['value']:.4f} in [-1, 1] - '{ind['interpretation']}'")
    
    def test_funding_pressure_normalized_minus1_to_1(self):
        """funding_pressure (FRP) normalized in [-1, 1] - Which side pays"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/POSITIONING")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'funding_pressure'), None)
        assert ind is not None, "funding_pressure not found"
        assert -1 <= ind['value'] <= 1, f"funding_pressure {ind['value']} out of range [-1, 1]"
        assert ind['interpretation'], "funding_pressure has empty interpretation"
        
        print(f"✓ funding_pressure: {ind['value']:.4f} in [-1, 1] - '{ind['interpretation']}'")
    
    def test_long_short_ratio_normalized_minus1_to_1(self):
        """long_short_ratio (LSR) normalized in [-1, 1] via log - Crowd skew"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/POSITIONING")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'long_short_ratio'), None)
        assert ind is not None, "long_short_ratio not found"
        assert -1 <= ind['value'] <= 1, f"long_short_ratio {ind['value']} out of range [-1, 1]"
        assert ind['interpretation'], "long_short_ratio has empty interpretation"
        
        print(f"✓ long_short_ratio: {ind['value']:.4f} in [-1, 1] (log) - '{ind['interpretation']}'")
    
    def test_position_crowding_normalized_0_to_1(self):
        """position_crowding (PCI) normalized in [0, 1] - Composite squeeze/flush risk"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/POSITIONING")
        data = response.json()
        
        ind = next((i for i in data['indicators'] if i['id'] == 'position_crowding'), None)
        assert ind is not None, "position_crowding not found"
        assert 0 <= ind['value'] <= 1, f"position_crowding {ind['value']} out of range [0, 1]"
        assert ind['interpretation'], "position_crowding has empty interpretation"
        
        print(f"✓ position_crowding: {ind['value']:.4f} in [0, 1] (composite) - '{ind['interpretation']}'")
    
    def test_positioning_interpretations_not_empty(self):
        """All POSITIONING indicators have non-empty interpretations"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/POSITIONING")
        data = response.json()
        
        for ind in data['indicators']:
            assert ind['interpretation'], f"{ind['id']} has empty interpretation"
            assert len(ind['interpretation']) > 0
        
        print("✓ All POSITIONING indicators have interpretations")
    
    def test_positioning_values_in_expected_ranges(self):
        """All POSITIONING values within expected ranges"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/POSITIONING")
        data = response.json()
        
        for ind in data['indicators']:
            ind_id = ind['id']
            value = ind['value']
            min_val, max_val = INDICATOR_RANGES[ind_id]
            
            assert min_val <= value <= max_val, \
                f"{ind_id} value {value} out of range [{min_val}, {max_val}]"
        
        print("✓ All POSITIONING values in expected ranges")


class TestSingleIndicator:
    """Test single indicator endpoint"""
    
    def test_single_rsi_normalized(self):
        """GET /api/v10/exchange/indicators/BTCUSDT/single/rsi_normalized"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/single/rsi_normalized")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['symbol'] == 'BTCUSDT'
        
        ind = data['indicator']
        assert ind['id'] == 'rsi_normalized'
        assert ind['category'] == 'MOMENTUM'
        assert ind['normalized'] == True
        assert -1 <= ind['value'] <= 1
        assert ind['interpretation']
        
        print(f"✓ Single RSI: value={ind['value']:.4f}, interpretation={ind['interpretation']}")
    
    def test_single_ema_distance_fast(self):
        """GET /api/v10/exchange/indicators/BTCUSDT/single/ema_distance_fast"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/single/ema_distance_fast")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        
        ind = data['indicator']
        assert ind['id'] == 'ema_distance_fast'
        assert ind['category'] == 'PRICE_STRUCTURE'
        assert -3 <= ind['value'] <= 3
        
        print(f"✓ Single EMA Distance Fast: value={ind['value']:.4f}")
    
    def test_single_volume_index(self):
        """GET /api/v10/exchange/indicators/BTCUSDT/single/volume_index (S10.6I.3)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/single/volume_index")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        
        ind = data['indicator']
        assert ind['id'] == 'volume_index'
        assert ind['category'] == 'VOLUME'
        assert ind['normalized'] == True
        assert -1 <= ind['value'] <= 1
        assert ind['interpretation']
        
        print(f"✓ Single Volume Index: value={ind['value']:.4f}")
    
    def test_single_book_imbalance(self):
        """GET /api/v10/exchange/indicators/BTCUSDT/single/book_imbalance (S10.6I.4)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/single/book_imbalance")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        
        ind = data['indicator']
        assert ind['id'] == 'book_imbalance'
        assert ind['category'] == 'ORDER_BOOK'
        assert ind['normalized'] == True
        assert -1 <= ind['value'] <= 1
        assert ind['interpretation']
        
        print(f"✓ Single Book Imbalance: value={ind['value']:.4f}")
    
    def test_single_oi_level(self):
        """GET /api/v10/exchange/indicators/BTCUSDT/single/oi_level (S10.6I.5)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/single/oi_level")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        
        ind = data['indicator']
        assert ind['id'] == 'oi_level'
        assert ind['category'] == 'POSITIONING'
        assert ind['normalized'] == True
        assert -1 <= ind['value'] <= 1
        assert ind['interpretation']
        
        print(f"✓ Single OI Level: value={ind['value']:.4f}")
    
    def test_single_position_crowding(self):
        """GET /api/v10/exchange/indicators/BTCUSDT/single/position_crowding (S10.6I.5)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/single/position_crowding")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        
        ind = data['indicator']
        assert ind['id'] == 'position_crowding'
        assert ind['category'] == 'POSITIONING'
        assert ind['normalized'] == True
        assert 0 <= ind['value'] <= 1  # Composite in [0, 1]
        assert ind['interpretation']
        
        print(f"✓ Single Position Crowding: value={ind['value']:.4f}")
    
    def test_single_nonexistent_returns_error(self):
        """Nonexistent indicator returns error"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT/single/nonexistent_indicator")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == False
        assert 'error' in data
        assert 'not found' in data['error'].lower()
        
        print("✓ Nonexistent indicator returns error")


class TestBatchRequest:
    """Test batch endpoint for multiple symbols"""
    
    def test_batch_multiple_symbols(self):
        """POST /api/v10/exchange/indicators/batch - multiple symbols return 32 indicators each"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/indicators/batch",
            json={"symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['count'] == 3
        
        results = data['results']
        assert 'BTCUSDT' in results
        assert 'ETHUSDT' in results
        assert 'SOLUSDT' in results
        
        # Each result should have 32 indicators (S10.6I.5 COMPLETE)
        for symbol in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']:
            assert len(results[symbol]['indicators']) == TOTAL_INDICATORS
        
        print(f"✓ Batch request: {data['count']} symbols, {TOTAL_INDICATORS} indicators each (COMPLETE)")
    
    def test_batch_empty_array_returns_error(self):
        """Empty symbols array returns error"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/indicators/batch",
            json={"symbols": []}
        )
        
        data = response.json()
        assert data['ok'] == False
        assert 'error' in data
        
        print("✓ Empty symbols array returns error")
    
    def test_batch_max_10_symbols(self):
        """More than 10 symbols returns error"""
        symbols = [f"SYMBOL{i}USDT" for i in range(15)]
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/indicators/batch",
            json={"symbols": symbols}
        )
        
        data = response.json()
        assert data['ok'] == False
        assert 'Maximum' in data['error'] or '10' in data['error']
        
        print("✓ Batch max 10 symbols enforced")


class TestIndicatorValueRanges:
    """Test that all normalized values are within expected ranges"""
    
    def test_all_indicator_ranges_btcusdt(self):
        """Verify all 32 indicators have values within documented ranges"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT")
        data = response.json()
        
        in_range_count = 0
        for ind in data['snapshot']['indicators']:
            ind_id = ind['id']
            value = ind['value']
            min_val, max_val = INDICATOR_RANGES[ind_id]
            
            in_range = min_val <= value <= max_val
            if in_range:
                in_range_count += 1
            
            assert in_range, f"{ind_id}: {value} not in [{min_val}, {max_val}]"
        
        print(f"✓ All {in_range_count}/{TOTAL_INDICATORS} indicators within expected ranges")
    
    def test_all_indicator_ranges_ethusdt(self):
        """Test ranges for ETHUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/ETHUSDT")
        data = response.json()
        
        for ind in data['snapshot']['indicators']:
            ind_id = ind['id']
            value = ind['value']
            min_val, max_val = INDICATOR_RANGES[ind_id]
            
            assert min_val <= value <= max_val, \
                f"ETHUSDT {ind_id}: {value} not in [{min_val}, {max_val}]"
        
        print("✓ All ETHUSDT indicator values in range")


class TestIndicatorConsistency:
    """Test indicator data consistency"""
    
    def test_timestamps_present(self):
        """All indicators should have timestamps"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT")
        data = response.json()
        
        for ind in data['snapshot']['indicators']:
            assert 'timestamp' in ind
            assert ind['timestamp'] > 0
        
        print("✓ All indicators have timestamps")
    
    def test_category_consistency(self):
        """Indicators should have consistent categories"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT")
        data = response.json()
        
        for ind in data['snapshot']['indicators']:
            if ind['id'] in PRICE_STRUCTURE_INDICATORS:
                assert ind['category'] == 'PRICE_STRUCTURE'
            elif ind['id'] in MOMENTUM_INDICATORS:
                assert ind['category'] == 'MOMENTUM'
            elif ind['id'] in VOLUME_INDICATORS:
                assert ind['category'] == 'VOLUME'
            elif ind['id'] in ORDER_BOOK_INDICATORS:
                assert ind['category'] == 'ORDER_BOOK'
            elif ind['id'] in POSITIONING_INDICATORS:
                assert ind['category'] == 'POSITIONING'
        
        print("✓ All indicators have consistent categories")
    
    def test_symbol_case_normalization(self):
        """Symbol should be normalized to uppercase"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/btcusdt")
        data = response.json()
        
        assert data['symbol'] == 'BTCUSDT'
        assert data['snapshot']['symbol'] == 'BTCUSDT'
        
        print("✓ Symbol normalized to uppercase")


class TestIndicatorCaching:
    """Test caching behavior"""
    
    def test_repeated_requests_consistent(self):
        """Same symbol returns consistent data (within cache TTL)"""
        response1 = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT")
        response2 = requests.get(f"{BASE_URL}/api/v10/exchange/indicators/BTCUSDT")
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Within cache TTL (5 seconds), calculatedAt should be same
        # Values should be identical if from cache
        assert data1['snapshot']['calculatedAt'] == data2['snapshot']['calculatedAt']
        
        print("✓ Caching working - repeated requests return same calculatedAt")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
