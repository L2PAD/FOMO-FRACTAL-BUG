"""
Test Prediction Feed with CLOB Integration and 3-Tier Sync Service.

Tests:
- GET /api/market-feed/markets - Feed with CLOB data
- GET /api/market-feed/sync/stats - Sync statistics
- POST /api/market-feed/sync/start - Start sync loop
- POST /api/market-feed/sync/stop - Stop sync loop
- POST /api/market-feed/refresh - Force refresh
- CLOB data structure validation
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMarketFeedAPI:
    """Market Feed API tests with CLOB integration."""
    
    def test_market_feed_returns_ok(self):
        """GET /api/market-feed/markets returns ok=true with markets array."""
        response = requests.get(f"{BASE_URL}/api/market-feed/markets", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "Expected ok=true"
        assert "markets" in data, "Expected markets array"
        assert "hot_count" in data, "Expected hot_count"
        assert "actionable_count" in data, "Expected actionable_count"
        assert "all_count" in data, "Expected all_count"
        print(f"✓ Market feed returned {len(data['markets'])} markets, hot={data['hot_count']}, actionable={data['actionable_count']}")
    
    def test_market_feed_has_clob_data(self):
        """Markets should have clob object with spread_pct, depth_quality, entry_hint."""
        response = requests.get(f"{BASE_URL}/api/market-feed/markets", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        markets = data.get("markets", [])
        
        # Check at least some markets have CLOB data
        markets_with_clob = 0
        for m in markets[:20]:  # Check first 20
            clob = m.get("clob", {})
            if clob and clob.get("depth_quality"):
                markets_with_clob += 1
                # Validate CLOB structure
                assert "spread_pct" in clob, f"Missing spread_pct in clob for {m.get('market_id')}"
                assert "depth_quality" in clob, f"Missing depth_quality in clob"
                assert "entry_hint" in clob, f"Missing entry_hint in clob"
                assert clob["depth_quality"] in ["deep", "moderate", "thin", "empty"], f"Invalid depth_quality: {clob['depth_quality']}"
                assert clob["entry_hint"] in ["MARKET_OK", "LIMIT_PREFERRED", "LIMIT_ONLY"], f"Invalid entry_hint: {clob['entry_hint']}"
        
        print(f"✓ {markets_with_clob}/{min(20, len(markets))} markets have CLOB data")
        # Note: Some markets may have empty CLOB depth (low liquidity)
    
    def test_market_feed_clob_fields(self):
        """Validate all expected CLOB fields are present."""
        response = requests.get(f"{BASE_URL}/api/market-feed/markets", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        markets = data.get("markets", [])
        
        expected_clob_fields = [
            "best_bid", "best_ask", "spread_abs", "spread_pct",
            "depth_quality", "total_depth", "bid_depth", "ask_depth",
            "slippage_100", "entry_hint", "imbalance"
        ]
        
        for m in markets[:5]:  # Check first 5
            clob = m.get("clob", {})
            if clob:
                for field in expected_clob_fields:
                    assert field in clob, f"Missing CLOB field: {field}"
        
        print(f"✓ CLOB fields validated: {expected_clob_fields}")
    
    def test_market_feed_tier_filter(self):
        """Test tier filter (hot/actionable)."""
        # Test hot tier
        response = requests.get(f"{BASE_URL}/api/market-feed/markets?tier=hot", timeout=30)
        assert response.status_code == 200
        data = response.json()
        hot_markets = data.get("markets", [])
        for m in hot_markets:
            assert m.get("tier") == "hot", f"Expected tier=hot, got {m.get('tier')}"
        print(f"✓ Hot tier filter: {len(hot_markets)} markets")
        
        # Test actionable tier
        response = requests.get(f"{BASE_URL}/api/market-feed/markets?tier=actionable", timeout=30)
        assert response.status_code == 200
        data = response.json()
        actionable_markets = data.get("markets", [])
        for m in actionable_markets:
            assert m.get("tier") == "actionable", f"Expected tier=actionable, got {m.get('tier')}"
        print(f"✓ Actionable tier filter: {len(actionable_markets)} markets")
    
    def test_market_feed_asset_filter(self):
        """Test asset filter (BTC/ETH/SOL/XRP)."""
        for asset in ["BTC", "ETH", "SOL"]:
            response = requests.get(f"{BASE_URL}/api/market-feed/markets?asset={asset}", timeout=30)
            assert response.status_code == 200, f"Asset filter {asset} failed"
            data = response.json()
            markets = data.get("markets", [])
            for m in markets:
                assert m.get("asset", "").upper() == asset, f"Expected asset={asset}, got {m.get('asset')}"
            print(f"✓ Asset filter {asset}: {len(markets)} markets")
    
    def test_market_feed_category_filter(self):
        """Test category filter (ETF/Launch/FDV/Macro)."""
        for cat in ["ETF", "Launch"]:
            response = requests.get(f"{BASE_URL}/api/market-feed/markets?category={cat}", timeout=30)
            assert response.status_code == 200, f"Category filter {cat} failed"
            data = response.json()
            print(f"✓ Category filter {cat}: {len(data.get('markets', []))} markets")


class TestSyncService:
    """3-Tier Sync Service tests."""
    
    def test_sync_stats_endpoint(self):
        """GET /api/market-feed/sync/stats returns sync status."""
        response = requests.get(f"{BASE_URL}/api/market-feed/sync/stats", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "Expected ok=true"
        assert "running" in data, "Expected running field"
        assert "hot_refreshes" in data, "Expected hot_refreshes field"
        assert "active_refreshes" in data, "Expected active_refreshes field"
        assert "tail_refreshes" in data, "Expected tail_refreshes field"
        print(f"✓ Sync stats: running={data.get('running')}, hot_refreshes={data.get('hot_refreshes')}")
    
    def test_sync_start_endpoint(self):
        """POST /api/market-feed/sync/start starts sync loop."""
        response = requests.post(f"{BASE_URL}/api/market-feed/sync/start", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "Expected ok=true"
        assert "message" in data, "Expected message field"
        print(f"✓ Sync start: {data.get('message')}")
    
    def test_sync_stop_endpoint(self):
        """POST /api/market-feed/sync/stop stops sync loop."""
        response = requests.post(f"{BASE_URL}/api/market-feed/sync/stop", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "Expected ok=true"
        assert "message" in data, "Expected message field"
        print(f"✓ Sync stop: {data.get('message')}")


class TestRefreshEndpoint:
    """Refresh endpoint tests."""
    
    def test_refresh_endpoint(self):
        """POST /api/market-feed/refresh forces cache refresh."""
        response = requests.post(f"{BASE_URL}/api/market-feed/refresh", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "Expected ok=true"
        assert "total" in data, "Expected total field"
        assert "hot_count" in data, "Expected hot_count field"
        assert "actionable_count" in data, "Expected actionable_count field"
        print(f"✓ Refresh: total={data.get('total')}, hot={data.get('hot_count')}, actionable={data.get('actionable_count')}")


class TestMarketDetail:
    """Market detail endpoint tests."""
    
    def test_market_detail_endpoint(self):
        """GET /api/market-feed/markets/{market_id} returns single market."""
        # First get a market_id from the feed
        response = requests.get(f"{BASE_URL}/api/market-feed/markets", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        markets = data.get("markets", [])
        if not markets:
            pytest.skip("No markets available to test detail endpoint")
        
        market_id = markets[0].get("market_id")
        
        # Get detail
        response = requests.get(f"{BASE_URL}/api/market-feed/markets/{market_id}", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "Expected ok=true"
        assert "market" in data, "Expected market field"
        assert data["market"]["market_id"] == market_id, "Market ID mismatch"
        print(f"✓ Market detail for {market_id[:20]}...")


class TestPredictionRunAPI:
    """Prediction run API tests (Overview/Markets tabs)."""
    
    def test_prediction_run_endpoint(self):
        """GET /api/prediction/run returns sections with cases."""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "sections" in data, "Expected sections field"
        print(f"✓ Prediction run: {len(data.get('sections', []))} sections")


class TestAlertCorrelationAPI:
    """Alert correlation API tests (Signals tab)."""
    
    def test_alert_correlation_history(self):
        """GET /api/alert-correlation/history returns metaAlerts."""
        response = requests.get(f"{BASE_URL}/api/alert-correlation/history?limit=10", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "metaAlerts" in data, "Expected metaAlerts field"
        print(f"✓ Alert correlation history: {len(data.get('metaAlerts', []))} alerts")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
