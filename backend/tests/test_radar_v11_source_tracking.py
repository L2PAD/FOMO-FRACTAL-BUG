"""
Test Suite: Alt Radar V11 - Source Tracking & Signal Quality
==============================================================
Tests P0 features: batch-optimized spot engine, source field tracking,
source distribution in debug stats, BUY signals from observations.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDebugStatsSourceDistribution:
    """Verify debug/stats returns sourceDistribution field for all universes"""
    
    def test_main_universe_has_source_distribution(self):
        """GET /api/v11/exchange/radar/debug/stats?universe=main returns sourceDistribution"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/debug/stats?universe=main")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data.get("ok") is True
        assert data.get("universe") == "main"
        assert "sourceDistribution" in data, "Missing sourceDistribution field"
        
        source_dist = data["sourceDistribution"]
        assert isinstance(source_dist, dict)
        # Should have observations and/or snapshot sources
        assert len(source_dist) > 0, "sourceDistribution is empty"
        
        print(f"Main sourceDistribution: {source_dist}")
        print(f"Main verdictDistribution: {data.get('verdictDistribution', {})}")
    
    def test_alpha_universe_has_source_distribution(self):
        """GET /api/v11/exchange/radar/debug/stats?universe=alpha returns sourceDistribution"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/debug/stats?universe=alpha")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data.get("ok") is True
        assert data.get("universe") == "alpha"
        assert "sourceDistribution" in data, "Missing sourceDistribution field"
        
        source_dist = data["sourceDistribution"]
        assert isinstance(source_dist, dict)
        
        # Alpha should have observations source
        observations_count = source_dist.get("observations", 0)
        print(f"Alpha sourceDistribution: {source_dist}")
        print(f"Alpha has {observations_count} observations-powered rows")


class TestSpotSourceFieldPopulated:
    """Verify spot radar rows have source field populated"""
    
    def test_main_venue_rows_have_source(self):
        """GET /api/v11/exchange/radar/spot?venue=main returns rows with source field"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data.get("ok") is True
        rows = data.get("rows", [])
        assert len(rows) > 0, "No rows returned"
        
        # Check all rows have source field
        sources_found = set()
        for row in rows:
            source = row.get("source")
            assert source is not None, f"Row {row['symbol']} missing source field"
            assert source in ["observations", "verdict", "snapshot", "none"], f"Invalid source: {source}"
            sources_found.add(source)
        
        print(f"Main venue sources found: {sources_found}")
        print(f"Sample rows: {[{'symbol': r['symbol'], 'source': r['source']} for r in rows[:5]]}")
    
    def test_alpha_venue_rows_have_source(self):
        """GET /api/v11/exchange/radar/spot?venue=alpha returns rows with source field"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data.get("ok") is True
        rows = data.get("rows", [])
        assert len(rows) > 0, "No alpha rows returned"
        
        # Check all rows have source field
        sources_found = {}
        for row in rows:
            source = row.get("source")
            assert source is not None, f"Row {row['symbol']} missing source field"
            sources_found[source] = sources_found.get(source, 0) + 1
        
        print(f"Alpha venue sources count: {sources_found}")
        
        # Alpha should be observations-powered
        obs_count = sources_found.get("observations", 0)
        total = len(rows)
        print(f"Alpha: {obs_count}/{total} rows from observations")


class TestResponseTime:
    """Verify spot engine responds within acceptable time"""
    
    def test_main_venue_under_10_seconds(self):
        """GET /api/v11/exchange/radar/spot?venue=main responds in under 10 seconds"""
        start = time.time()
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main")
        elapsed = time.time() - start
        
        assert resp.status_code == 200
        print(f"Main venue response time: {elapsed:.2f}s")
        assert elapsed < 10, f"Response took too long: {elapsed:.2f}s (expected < 10s)"
    
    def test_alpha_venue_under_10_seconds(self):
        """GET /api/v11/exchange/radar/spot?venue=alpha responds in under 10 seconds"""
        start = time.time()
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha")
        elapsed = time.time() - start
        
        assert resp.status_code == 200
        print(f"Alpha venue response time: {elapsed:.2f}s")
        assert elapsed < 10, f"Response took too long: {elapsed:.2f}s (expected < 10s)"


class TestAlphaBuySignals:
    """Verify Alpha tab shows active signals from observations"""
    
    def test_alpha_has_buy_signals(self):
        """GET /api/v11/exchange/radar/spot?venue=alpha includes BUY signals"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha")
        assert resp.status_code == 200
        data = resp.json()
        
        rows = data.get("rows", [])
        assert len(rows) > 0, "No alpha rows"
        
        buy_rows = [r for r in rows if r.get("verdict") == "buy"]
        watch_rows = [r for r in rows if r.get("verdict") == "watch"]
        neutral_rows = [r for r in rows if r.get("verdict") == "neutral"]
        data_gap_rows = [r for r in rows if r.get("verdict") == "data_gap"]
        
        print(f"Alpha verdict distribution: BUY={len(buy_rows)}, WATCH={len(watch_rows)}, NEUTRAL={len(neutral_rows)}, DATA_GAP={len(data_gap_rows)}")
        
        # Alpha should have some BUY signals (observations-powered)
        assert len(buy_rows) > 0, "Alpha should have BUY signals from observations"
        
        # All BUY signals should be from observations source
        for row in buy_rows:
            assert row.get("source") == "observations", f"BUY signal {row['symbol']} should be from observations, got {row.get('source')}"
        
        print(f"BUY signals: {[r['symbol'] for r in buy_rows]}")
    
    def test_alpha_not_all_neutral_or_data_gap(self):
        """Alpha tab shows active signals, not all NEUTRAL or DATA_GAP"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha")
        assert resp.status_code == 200
        data = resp.json()
        
        rows = data.get("rows", [])
        assert len(rows) > 0
        
        active_rows = [r for r in rows if r.get("verdict") in ["buy", "sell", "watch"]]
        inactive_rows = [r for r in rows if r.get("verdict") in ["neutral", "data_gap"]]
        
        active_pct = len(active_rows) / len(rows) * 100
        print(f"Alpha active signals: {len(active_rows)}/{len(rows)} ({active_pct:.1f}%)")
        
        # Should have at least some active signals
        assert len(active_rows) > 0, "Alpha should have active signals (BUY/SELL/WATCH)"


class TestBTCSearch:
    """Verify BTC search returns correct data"""
    
    def test_btc_search_main_venue(self):
        """GET /api/v11/exchange/radar/spot?venue=main&search=BTC returns BTC with source"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&search=BTC")
        assert resp.status_code == 200
        data = resp.json()
        
        rows = data.get("rows", [])
        assert len(rows) >= 1, "BTC search should return at least 1 result"
        
        btc_row = next((r for r in rows if r["symbol"] == "BTCUSDT"), None)
        assert btc_row is not None, "BTCUSDT not found in search results"
        
        assert btc_row.get("source") is not None, "BTCUSDT missing source field"
        print(f"BTCUSDT: source={btc_row['source']}, verdict={btc_row['verdict']}, direction={btc_row.get('direction')}")


class TestSpotTopSetups:
    """Verify spot tab shows top setups with conviction and direction"""
    
    def test_spot_has_conviction_values(self):
        """Spot rows have conviction values"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        
        rows = data.get("rows", [])
        assert len(rows) > 0
        
        for row in rows:
            assert "conviction" in row, f"Row {row['symbol']} missing conviction"
            assert "direction" in row, f"Row {row['symbol']} missing direction"
            assert isinstance(row["conviction"], int)
            assert row["direction"] in ["long", "short", "neutral"]
        
        # Rows should be sorted by conviction (descending)
        convictions = [r["conviction"] for r in rows]
        assert convictions == sorted(convictions, reverse=True), "Rows not sorted by conviction"
        
        print(f"Top setups: {[(r['symbol'], r['conviction'], r['direction']) for r in rows[:5]]}")
