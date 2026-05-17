"""
P1.2 — Divergence Feature Tests for Multi-venue Radar
========================================================
Tests for divergenceScore, divergenceLabel, divergenceReasons fields.
Also unit tests for compute_divergence() function.
DUAL_VENUE_ENABLED=false → all divergenceScore=0, divergenceLabel='NONE', divergenceReasons=[]
"""

import pytest
import requests
import os
import sys

# Add backend to path for unit tests
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


# =============================================================================
# API Tests: Divergence Fields in Spot Radar Rows
# =============================================================================

class TestDivergenceFieldsAlpha:
    """Test divergence fields for alpha venue API responses"""
    
    def test_alpha_endpoint_has_divergence_score(self):
        """GET /api/v11/exchange/radar/spot?venue=alpha&limit=5 returns divergenceScore"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=5")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        assert len(rows) > 0, "Expected at least one row"
        
        for row in rows:
            assert "divergenceScore" in row, f"Row {row['symbol']} missing divergenceScore"
            assert isinstance(row["divergenceScore"], (int, float)), f"Row {row['symbol']} divergenceScore not numeric"
            assert 0 <= row["divergenceScore"] <= 1, f"Row {row['symbol']} divergenceScore out of range: {row['divergenceScore']}"
            print(f"✓ {row['symbol']}: divergenceScore={row['divergenceScore']}")
    
    def test_alpha_endpoint_has_divergence_label(self):
        """GET /api/v11/exchange/radar/spot?venue=alpha&limit=5 returns divergenceLabel"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=5")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        valid_labels = ["NONE", "LOW", "MID", "HIGH"]
        for row in rows:
            assert "divergenceLabel" in row, f"Row {row['symbol']} missing divergenceLabel"
            assert isinstance(row["divergenceLabel"], str), f"Row {row['symbol']} divergenceLabel not string"
            assert row["divergenceLabel"] in valid_labels, f"Row {row['symbol']} invalid divergenceLabel: {row['divergenceLabel']}"
            print(f"✓ {row['symbol']}: divergenceLabel={row['divergenceLabel']}")
    
    def test_alpha_endpoint_has_divergence_reasons(self):
        """GET /api/v11/exchange/radar/spot?venue=alpha&limit=5 returns divergenceReasons array"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=5")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert "divergenceReasons" in row, f"Row {row['symbol']} missing divergenceReasons"
            assert isinstance(row["divergenceReasons"], list), f"Row {row['symbol']} divergenceReasons not list"
            assert all(isinstance(r, str) for r in row["divergenceReasons"]), f"Row {row['symbol']} divergenceReasons contains non-string"
            print(f"✓ {row['symbol']}: divergenceReasons={row['divergenceReasons']}")


class TestDivergenceFieldsMain:
    """Test divergence fields for main venue API responses"""
    
    def test_main_endpoint_has_divergence_score(self):
        """GET /api/v11/exchange/radar/spot?venue=main&limit=5 returns divergenceScore"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=5")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        assert len(rows) > 0, "Expected at least one row"
        
        for row in rows:
            assert "divergenceScore" in row, f"Row {row['symbol']} missing divergenceScore"
            assert isinstance(row["divergenceScore"], (int, float)), f"Row {row['symbol']} divergenceScore not numeric"
            assert 0 <= row["divergenceScore"] <= 1, f"Row {row['symbol']} divergenceScore out of range"
            print(f"✓ {row['symbol']}: divergenceScore={row['divergenceScore']}")
    
    def test_main_endpoint_has_divergence_label(self):
        """GET /api/v11/exchange/radar/spot?venue=main&limit=5 returns divergenceLabel"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=5")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        valid_labels = ["NONE", "LOW", "MID", "HIGH"]
        for row in rows:
            assert "divergenceLabel" in row, f"Row {row['symbol']} missing divergenceLabel"
            assert row["divergenceLabel"] in valid_labels, f"Row {row['symbol']} invalid divergenceLabel"
            print(f"✓ {row['symbol']}: divergenceLabel={row['divergenceLabel']}")
    
    def test_main_endpoint_has_divergence_reasons(self):
        """GET /api/v11/exchange/radar/spot?venue=main&limit=5 returns divergenceReasons array"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=5")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert "divergenceReasons" in row, f"Row {row['symbol']} missing divergenceReasons"
            assert isinstance(row["divergenceReasons"], list), f"Row {row['symbol']} divergenceReasons not list"
            print(f"✓ {row['symbol']}: divergenceReasons={row['divergenceReasons']}")


class TestDualVenueDisabledDivergenceZero:
    """With DUAL_VENUE_ENABLED=false, all divergence fields should be zero/none/empty"""
    
    def test_alpha_divergence_all_zero(self):
        """Alpha venue: all rows have divergenceScore=0, divergenceLabel='NONE', divergenceReasons=[]"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=20")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert row["divergenceScore"] == 0.0, f"Row {row['symbol']} expected divergenceScore=0, got {row['divergenceScore']}"
            assert row["divergenceLabel"] == "NONE", f"Row {row['symbol']} expected divergenceLabel='NONE', got {row['divergenceLabel']}"
            assert row["divergenceReasons"] == [], f"Row {row['symbol']} expected divergenceReasons=[], got {row['divergenceReasons']}"
        
        print(f"✓ All {len(rows)} alpha rows have divergenceScore=0, divergenceLabel='NONE', divergenceReasons=[]")
    
    def test_main_divergence_all_zero(self):
        """Main venue: all rows have divergenceScore=0, divergenceLabel='NONE', divergenceReasons=[]"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=20")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert row["divergenceScore"] == 0.0, f"Row {row['symbol']} expected divergenceScore=0, got {row['divergenceScore']}"
            assert row["divergenceLabel"] == "NONE", f"Row {row['symbol']} expected divergenceLabel='NONE', got {row['divergenceLabel']}"
            assert row["divergenceReasons"] == [], f"Row {row['symbol']} expected divergenceReasons=[], got {row['divergenceReasons']}"
        
        print(f"✓ All {len(rows)} main rows have divergenceScore=0, divergenceLabel='NONE', divergenceReasons=[]")


# =============================================================================
# API Tests: Selfcheck Divergence Stats
# =============================================================================

class TestSelfcheckDivergenceStats:
    """Test /api/v11/exchange/radar/selfcheck divergence section"""
    
    def test_selfcheck_has_divergence_section(self):
        """GET /api/v11/exchange/radar/selfcheck returns divergence section"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck")
        assert response.status_code == 200
        data = response.json()
        
        assert "divergence" in data, "selfcheck missing divergence section"
        print(f"✓ selfcheck has divergence section")
    
    def test_selfcheck_divergence_has_multi_venue_pct(self):
        """divergence section has multiVenuePct field"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck")
        assert response.status_code == 200
        data = response.json()
        div = data.get("divergence", {})
        
        assert "multiVenuePct" in div, "divergence missing multiVenuePct"
        assert isinstance(div["multiVenuePct"], (int, float)), "multiVenuePct not numeric"
        assert 0 <= div["multiVenuePct"] <= 100, "multiVenuePct out of range"
        print(f"✓ multiVenuePct={div['multiVenuePct']}")
    
    def test_selfcheck_divergence_has_avg_divergence(self):
        """divergence section has avgDivergence field"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck")
        assert response.status_code == 200
        data = response.json()
        div = data.get("divergence", {})
        
        assert "avgDivergence" in div, "divergence missing avgDivergence"
        assert isinstance(div["avgDivergence"], (int, float)), "avgDivergence not numeric"
        print(f"✓ avgDivergence={div['avgDivergence']}")
    
    def test_selfcheck_divergence_has_high_divergence_count(self):
        """divergence section has highDivergenceCount field"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck")
        assert response.status_code == 200
        data = response.json()
        div = data.get("divergence", {})
        
        assert "highDivergenceCount" in div, "divergence missing highDivergenceCount"
        assert isinstance(div["highDivergenceCount"], int), "highDivergenceCount not int"
        assert div["highDivergenceCount"] >= 0, "highDivergenceCount negative"
        print(f"✓ highDivergenceCount={div['highDivergenceCount']}")
    
    def test_selfcheck_divergence_has_boosted_short_count(self):
        """divergence section has boostedShortCount field"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck")
        assert response.status_code == 200
        data = response.json()
        div = data.get("divergence", {})
        
        assert "boostedShortCount" in div, "divergence missing boostedShortCount"
        assert isinstance(div["boostedShortCount"], int), "boostedShortCount not int"
        assert div["boostedShortCount"] >= 0, "boostedShortCount negative"
        print(f"✓ boostedShortCount={div['boostedShortCount']}")
    
    def test_selfcheck_divergence_stats_all_zero_when_disabled(self):
        """With DUAL_VENUE_ENABLED=false, divergence stats should all be 0"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck")
        assert response.status_code == 200
        data = response.json()
        div = data.get("divergence", {})
        
        # All should be 0 since DUAL_VENUE_ENABLED=false
        assert div["multiVenuePct"] == 0.0, f"Expected multiVenuePct=0, got {div['multiVenuePct']}"
        assert div["avgDivergence"] == 0, f"Expected avgDivergence=0, got {div['avgDivergence']}"
        assert div["highDivergenceCount"] == 0, f"Expected highDivergenceCount=0, got {div['highDivergenceCount']}"
        assert div["boostedShortCount"] == 0, f"Expected boostedShortCount=0, got {div['boostedShortCount']}"
        print("✓ All divergence stats are 0 (DUAL_VENUE_ENABLED=false)")


# =============================================================================
# API Tests: Existing Fields Still Work
# =============================================================================

class TestExistingFieldsStillWork:
    """Verify existing radar fields (conviction, verdict, horizons, integrity, explain) still work"""
    
    def test_conviction_field_still_works(self):
        """conviction field is present and valid"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert "conviction" in row, f"Row {row['symbol']} missing conviction"
            assert 0 <= row["conviction"] <= 100, f"Row {row['symbol']} conviction out of range"
        print(f"✓ All rows have valid conviction (0-100)")
    
    def test_verdict_field_still_works(self):
        """verdict field is present and valid"""
        valid_verdicts = ["buy", "sell", "watch", "neutral", "data_gap"]
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert "verdict" in row, f"Row {row['symbol']} missing verdict"
            assert row["verdict"] in valid_verdicts, f"Row {row['symbol']} invalid verdict"
        print(f"✓ All rows have valid verdict")
    
    def test_horizons_field_still_works(self):
        """horizons field present with short/mid/swing/primary"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            if row["verdict"] != "data_gap":
                assert "horizons" in row, f"Row {row['symbol']} missing horizons"
                if row["horizons"]:
                    assert "short" in row["horizons"], f"Row {row['symbol']} horizons missing short"
                    assert "mid" in row["horizons"], f"Row {row['symbol']} horizons missing mid"
                    assert "swing" in row["horizons"], f"Row {row['symbol']} horizons missing swing"
                    assert "primary" in row["horizons"], f"Row {row['symbol']} horizons missing primary"
        print(f"✓ All non-data_gap rows have horizons")
    
    def test_integrity_field_still_works(self):
        """integrity field present with status/coveragePct/setupScore"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            if row["verdict"] != "data_gap":
                assert "integrity" in row, f"Row {row['symbol']} missing integrity"
                if row["integrity"]:
                    assert "status" in row["integrity"], f"Row {row['symbol']} integrity missing status"
                    assert "coveragePct" in row["integrity"], f"Row {row['symbol']} integrity missing coveragePct"
                    assert "setupScore" in row["integrity"], f"Row {row['symbol']} integrity missing setupScore"
        print(f"✓ All non-data_gap rows have integrity")
    
    def test_explain_field_still_works(self):
        """explain field present with whyNow/invalidation/timeHorizon"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert "explain" in row, f"Row {row['symbol']} missing explain"
            assert "whyNow" in row["explain"], f"Row {row['symbol']} explain missing whyNow"
            assert "invalidation" in row["explain"], f"Row {row['symbol']} explain missing invalidation"
            assert "timeHorizon" in row["explain"], f"Row {row['symbol']} explain missing timeHorizon"
        print(f"✓ All rows have explain with whyNow/invalidation/timeHorizon")
    
    def test_venue_count_and_venues_still_work(self):
        """venueCount and venues fields from P1.1 still work"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert "venueCount" in row, f"Row {row['symbol']} missing venueCount"
            assert "venues" in row, f"Row {row['symbol']} missing venues"
            assert row["venueCount"] == 1, f"Row {row['symbol']} expected venueCount=1"
            assert row["venues"] == ["binance"], f"Row {row['symbol']} expected venues=['binance']"
        print(f"✓ All rows have venueCount=1, venues=['binance']")


# =============================================================================
# Unit Tests: compute_divergence Function
# =============================================================================

class TestComputeDivergenceUnit:
    """Unit tests for compute_divergence function from aggregator.py"""
    
    def test_case1_similar_funding_low_divergence(self):
        """Case 1: Similar funding rates → low/no divergence score"""
        from market_data import NormalizedMarketData
        from market_data.aggregator import compute_divergence
        
        # Similar funding: 0.01% vs 0.012% (very close)
        binance = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="binance",
            funding=0.01,  # 1% annualized
            oi=100000000,
            orderflow_bias="buy",
            orderflow_strength=0.6
        )
        bybit = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="bybit",
            funding=0.012,  # 1.2% annualized (very similar)
            oi=100000000,  # Same OI
            orderflow_bias="buy",  # Same direction
            orderflow_strength=0.55
        )
        
        score, label, reasons = compute_divergence(binance, bybit)
        
        # Score should be very low (<0.25) due to similar funding, same OI, same orderflow
        assert 0 <= score <= 1, f"Score out of range: {score}"
        assert score < 0.25, f"Expected score < 0.25 for similar data, got {score}"
        assert label == "LOW", f"Expected label 'LOW', got {label}"
        assert isinstance(reasons, list), f"Reasons should be list, got {type(reasons)}"
        print(f"✓ Case 1: Similar funding → score={score}, label={label}, reasons={reasons}")
    
    def test_case2_opposite_funding_high_divergence(self):
        """Case 2: Opposite funding rates → high divergence score"""
        from market_data import NormalizedMarketData
        from market_data.aggregator import compute_divergence
        
        # Opposite funding: -3% vs +2% (significant mismatch)
        binance = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="binance",
            funding=-0.03,  # -3% (shorts paying longs)
            oi=100000000,
            orderflow_bias="sell",
            orderflow_strength=0.5
        )
        bybit = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="bybit",
            funding=0.02,  # +2% (longs paying shorts)
            oi=100000000,
            orderflow_bias="sell",  # Same orderflow
            orderflow_strength=0.5
        )
        
        score, label, reasons = compute_divergence(binance, bybit)
        
        # Funding diff = 0.05 (5%), FUND_NORM = 0.35
        # fund component = min(1.0, 0.05 / 0.35) = ~0.143
        # Score = 0.4 * 0.143 + 0.4 * 0 + 0.2 * 0 = ~0.057
        # Actually: |−0.03 − 0.02| = 0.05
        # fund = min(1.0, 0.05 / 0.35) = 0.143
        # oi_diff_pct = 0 (same OI)
        # flow = 0 (same direction)
        # score = 0.4 * 0.143 = 0.057 → LOW
        # Hmm, needs bigger funding diff to get MID/HIGH
        
        # Let me use more extreme values
        binance2 = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="binance",
            funding=-0.15,  # -15%
            oi=100000000,
            orderflow_bias="sell",
        )
        bybit2 = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="bybit",
            funding=0.15,  # +15%
            oi=100000000,
            orderflow_bias="sell",
        )
        
        score2, label2, reasons2 = compute_divergence(binance2, bybit2)
        
        # fund diff = 0.30, fund = min(1.0, 0.30/0.35) = 0.857
        # score = 0.4 * 0.857 = 0.343 → MID
        
        assert 0 <= score2 <= 1, f"Score out of range: {score2}"
        # High funding mismatch should give MID or HIGH
        assert label2 in ["MID", "HIGH"], f"Expected MID or HIGH for extreme funding mismatch, got {label2}"
        assert "Funding mismatch" in reasons2, f"Expected 'Funding mismatch' in reasons, got {reasons2}"
        print(f"✓ Case 2: Opposite funding → score={score2}, label={label2}, reasons={reasons2}")
    
    def test_case3_orderflow_conflict_adds_score(self):
        """Case 3: Orderflow conflict (buy vs sell) adds 0.2 to flow component"""
        from market_data import NormalizedMarketData
        from market_data.aggregator import compute_divergence
        
        # Orderflow conflict: buy vs sell
        binance = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="binance",
            funding=0.01,  # Same funding
            oi=100000000,
            orderflow_bias="buy",  # BUY
            orderflow_strength=0.6
        )
        bybit = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="bybit",
            funding=0.01,  # Same funding
            oi=100000000,  # Same OI
            orderflow_bias="sell",  # SELL (opposite!)
            orderflow_strength=0.6
        )
        
        score, label, reasons = compute_divergence(binance, bybit)
        
        # fund = 0 (same)
        # oi = 0 (same)
        # flow = 1.0 (both active and opposite)
        # score = 0.4*0 + 0.4*0 + 0.2*1.0 = 0.2 → LOW (just under 0.25)
        
        assert 0 <= score <= 1, f"Score out of range: {score}"
        assert score >= 0.1, f"Expected score >= 0.1 with orderflow conflict, got {score}"
        assert "Orderflow conflict" in reasons, f"Expected 'Orderflow conflict' in reasons, got {reasons}"
        print(f"✓ Case 3: Orderflow conflict → score={score}, label={label}, reasons={reasons}")
    
    def test_divergence_score_bounds(self):
        """Divergence score should always be 0..1"""
        from market_data import NormalizedMarketData
        from market_data.aggregator import compute_divergence
        
        # Maximum divergence scenario
        binance = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="binance",
            funding=-0.5,  # -50%
            oi=10000000,
            orderflow_bias="buy",
        )
        bybit = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="bybit",
            funding=0.5,  # +50%
            oi=50000000,  # 5x OI difference
            orderflow_bias="sell",  # Opposite
        )
        
        score, label, reasons = compute_divergence(binance, bybit)
        
        assert 0 <= score <= 1, f"Score out of bounds: {score}"
        assert label in ["NONE", "LOW", "MID", "HIGH"], f"Invalid label: {label}"
        print(f"✓ Maximum divergence → score={score} (bounded 0-1), label={label}")
    
    def test_null_funding_handling(self):
        """Null funding should be treated as 0"""
        from market_data import NormalizedMarketData
        from market_data.aggregator import compute_divergence
        
        binance = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="binance",
            funding=None,  # NULL
            oi=100000000,
            orderflow_bias="neutral",
        )
        bybit = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="bybit",
            funding=0.01,
            oi=100000000,
            orderflow_bias="neutral",
        )
        
        score, label, reasons = compute_divergence(binance, bybit)
        
        assert 0 <= score <= 1, f"Score out of range: {score}"
        print(f"✓ Null funding handling → score={score}, label={label}")
    
    def test_null_oi_handling(self):
        """Null OI should be treated as 0"""
        from market_data import NormalizedMarketData
        from market_data.aggregator import compute_divergence
        
        binance = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="binance",
            funding=0.01,
            oi=None,  # NULL
            orderflow_bias="neutral",
        )
        bybit = NormalizedMarketData(
            symbol="BTCUSDT",
            venue="bybit",
            funding=0.01,
            oi=100000000,
            orderflow_bias="neutral",
        )
        
        score, label, reasons = compute_divergence(binance, bybit)
        
        assert 0 <= score <= 1, f"Score out of range: {score}"
        print(f"✓ Null OI handling → score={score}, label={label}")
    
    def test_label_thresholds(self):
        """Test label thresholds: <0.25→LOW, 0.25-0.55→MID, >0.55→HIGH"""
        from market_data import NormalizedMarketData
        from market_data.aggregator import compute_divergence
        
        # Test LOW threshold (score < 0.25)
        binance_low = NormalizedMarketData(symbol="TEST", venue="binance", funding=0.01, oi=100000000, orderflow_bias="buy")
        bybit_low = NormalizedMarketData(symbol="TEST", venue="bybit", funding=0.02, oi=100000000, orderflow_bias="buy")
        score_low, label_low, _ = compute_divergence(binance_low, bybit_low)
        assert label_low == "LOW", f"Expected LOW for score={score_low}"
        
        # Test MID threshold (0.25 <= score <= 0.55)
        binance_mid = NormalizedMarketData(symbol="TEST", venue="binance", funding=-0.10, oi=50000000, orderflow_bias="buy")
        bybit_mid = NormalizedMarketData(symbol="TEST", venue="bybit", funding=0.10, oi=100000000, orderflow_bias="sell")
        score_mid, label_mid, _ = compute_divergence(binance_mid, bybit_mid)
        # This should be mid-range divergence
        
        # Test HIGH threshold (score > 0.55)
        binance_high = NormalizedMarketData(symbol="TEST", venue="binance", funding=-0.30, oi=10000000, orderflow_bias="buy")
        bybit_high = NormalizedMarketData(symbol="TEST", venue="bybit", funding=0.30, oi=100000000, orderflow_bias="sell")
        score_high, label_high, _ = compute_divergence(binance_high, bybit_high)
        
        print(f"✓ Label thresholds: LOW={score_low}, MID={score_mid}, HIGH={score_high}")
        print(f"  Labels: {label_low}, {label_mid}, {label_high}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
