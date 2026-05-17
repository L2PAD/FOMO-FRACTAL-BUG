"""
Alt Radar V11 Expanded Universe Tests (185 Spot Main symbols)
==============================================================
Tests P0 fixes:
1. Expanded Spot universe from 10 to 185 symbols
2. Alpha now has 15 symbols with real data (was 100% DATA_GAP)
3. DATA_GAP verdict for missing data
4. Debug stats and Admin rebuild endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRadarV11UniverseExpansion:
    """Test expanded universe (185 spot main symbols)"""
    
    def test_universe_spot_main_count_185(self):
        """Universe spot mode returns 185 main symbols"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/universe?mode=spot")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("spotMainCount") == 185
        assert data.get("spotAlphaCount") == 28
    
    def test_universe_futures_count(self):
        """Universe futures mode returns correct count"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/universe?mode=futures")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("futuresCount") == 228


class TestRadarV11SpotMain:
    """Test Spot Main scan (185 symbols)"""
    
    def test_spot_main_returns_25_items_page_1(self):
        """Spot main page 1 returns 25 items sorted by conviction"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&page=1&limit=25&sort=conviction")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert len(data.get("rows", [])) == 25
        meta = data.get("meta", {})
        assert meta.get("total") == 185
        assert meta.get("pages") == 8
    
    def test_spot_main_hype_sell_62_first(self):
        """HYPE is SELL with conviction 62 at top"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&page=1&limit=25&sort=conviction")
        assert resp.status_code == 200
        data = resp.json()
        rows = data.get("rows", [])
        assert len(rows) > 0
        first = rows[0]
        assert first.get("symbol") == "HYPEUSDT"
        assert first.get("verdict") == "sell"
        assert first.get("conviction") == 62
    
    def test_spot_main_search_hype_returns_results(self):
        """Search for HYPE returns matching results"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&search=HYPE")
        assert resp.status_code == 200
        data = resp.json()
        rows = data.get("rows", [])
        assert len(rows) >= 1
        symbols = [r.get("symbol") for r in rows]
        assert "HYPEUSDT" in symbols
        # Check HYPEUSDT has sell verdict
        hype_row = next(r for r in rows if r.get("symbol") == "HYPEUSDT")
        assert hype_row.get("verdict") == "sell"
    
    def test_spot_main_verdict_sell_filter(self):
        """Filter by verdict=sell returns only sell rows"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&verdict=sell")
        assert resp.status_code == 200
        data = resp.json()
        rows = data.get("rows", [])
        for row in rows:
            assert row.get("verdict") == "sell"
    
    def test_spot_main_verdict_watch_count_49(self):
        """Filter by verdict=watch returns ~49 items"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&verdict=watch&limit=200")
        assert resp.status_code == 200
        data = resp.json()
        meta = data.get("meta", {})
        assert meta.get("total") == 49
    
    def test_spot_main_pagination_page2_different(self):
        """Page 2 returns different items than page 1"""
        resp1 = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&page=1&limit=25&sort=conviction")
        resp2 = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&page=2&limit=25&sort=conviction")
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        rows1 = [r.get("symbol") for r in resp1.json().get("rows", [])]
        rows2 = [r.get("symbol") for r in resp2.json().get("rows", [])]
        # No overlap between page 1 and page 2
        assert set(rows1).isdisjoint(set(rows2))


class TestRadarV11SpotAlpha:
    """Test Spot Alpha scan (15 with data + 13 DATA_GAP)"""
    
    def test_alpha_has_real_data_not_all_data_gap(self):
        """Alpha returns mix of verdicts, not all DATA_GAP"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&page=1&limit=30")
        assert resp.status_code == 200
        data = resp.json()
        rows = data.get("rows", [])
        verdicts = [r.get("verdict") for r in rows]
        # Should have watch and neutral, not only data_gap
        assert "watch" in verdicts
        assert "neutral" in verdicts
    
    def test_alpha_fartcoin_watch_58(self):
        """FARTCOIN has WATCH verdict with ~58 conviction"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&page=1&limit=30")
        assert resp.status_code == 200
        data = resp.json()
        rows = data.get("rows", [])
        fart = next((r for r in rows if r.get("symbol") == "FARTCOINUSDT"), None)
        assert fart is not None
        assert fart.get("verdict") == "watch"
        assert fart.get("conviction") >= 55
    
    def test_alpha_ai16z_watch(self):
        """AI16Z has WATCH verdict"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&page=1&limit=30")
        assert resp.status_code == 200
        data = resp.json()
        rows = data.get("rows", [])
        ai16z = next((r for r in rows if r.get("symbol") == "AI16ZUSDT"), None)
        assert ai16z is not None
        assert ai16z.get("verdict") == "watch"


class TestRadarV11DebugStats:
    """Test debug stats endpoint"""
    
    def test_debug_stats_main_with_data_count_185(self):
        """Debug stats for main shows withDataCount=185"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/debug/stats?universe=main")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("total") == 185
        dq = data.get("dataQuality", {})
        assert dq.get("withDataCount") == 185
        assert dq.get("dataGapCount") == 0
    
    def test_debug_stats_main_verdict_distribution(self):
        """Debug stats for main shows buy/sell/watch/neutral"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/debug/stats?universe=main")
        assert resp.status_code == 200
        data = resp.json()
        dist = data.get("verdictDistribution", {})
        assert "sell" in dist
        assert "watch" in dist
        assert "neutral" in dist
    
    def test_debug_stats_alpha_data_quality(self):
        """Debug stats for alpha shows dataGapCount ~13 and withDataCount ~15"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/debug/stats?universe=alpha")
        assert resp.status_code == 200
        data = resp.json()
        dq = data.get("dataQuality", {})
        assert dq.get("dataGapCount") == 13
        assert dq.get("withDataCount") == 15


class TestRadarV11AdminRebuild:
    """Test admin rebuild endpoint"""
    
    def test_admin_rebuild_main(self):
        """Admin rebuild for main returns correct stats"""
        resp = requests.post(f"{BASE_URL}/api/v11/exchange/radar/admin/rebuild?universe=main")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("totalScanned") == 185
    
    def test_admin_rebuild_alpha(self):
        """Admin rebuild for alpha returns correct stats"""
        resp = requests.post(f"{BASE_URL}/api/v11/exchange/radar/admin/rebuild?universe=alpha")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("totalScanned") == 28


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
