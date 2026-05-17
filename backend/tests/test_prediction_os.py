"""
Prediction OS Backend API Tests
Tests for the 5-tab Prediction Markets page:
- Overview/Markets tabs: /api/prediction/run
- Feed tab: /api/market-feed/markets
- Signals tab: /api/alert-correlation/history, /api/alert-correlation/regime
- Analytics tab: /api/prediction/weekly-digest/latest, /api/outcome-lab/stats
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMarketFeedAPI:
    """Feed tab API tests - /api/market-feed/markets"""
    
    def test_market_feed_returns_ok(self):
        """GET /api/market-feed/markets returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/market-feed/markets", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"Market feed returned {data.get('total', 0)} markets")
    
    def test_market_feed_has_required_fields(self):
        """Market feed response has hot_count, actionable_count, all_count, markets"""
        response = requests.get(f"{BASE_URL}/api/market-feed/markets", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "hot_count" in data
        assert "actionable_count" in data
        assert "all_count" in data
        assert "markets" in data
        assert isinstance(data["markets"], list)
        
        print(f"Hot: {data['hot_count']}, Actionable: {data['actionable_count']}, All: {data['all_count']}")
    
    def test_market_feed_market_structure(self):
        """Each market has required fields"""
        response = requests.get(f"{BASE_URL}/api/market-feed/markets", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        if data["markets"]:
            market = data["markets"][0]
            required_fields = ["market_id", "question", "yes_price", "no_price", "asset", "tier"]
            for field in required_fields:
                assert field in market, f"Missing field: {field}"
            
            # Check overlay structure
            assert "overlay" in market
            assert "has_overlay" in market
            
            print(f"First market: {market['question'][:50]}... (tier: {market['tier']})")
    
    def test_market_feed_tier_filter(self):
        """Tier filter works (hot, actionable)"""
        response = requests.get(f"{BASE_URL}/api/market-feed/markets?tier=hot", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # All returned markets should be hot tier
        for market in data["markets"]:
            assert market["tier"] == "hot", f"Expected hot tier, got {market['tier']}"
        
        print(f"Hot tier filter returned {len(data['markets'])} markets")
    
    def test_market_feed_asset_filter(self):
        """Asset filter works (BTC, ETH, etc.)"""
        response = requests.get(f"{BASE_URL}/api/market-feed/markets?asset=BTC", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # All returned markets should have BTC asset
        for market in data["markets"]:
            assert market["asset"] == "BTC", f"Expected BTC asset, got {market['asset']}"
        
        print(f"BTC filter returned {len(data['markets'])} markets")


class TestPredictionRunAPI:
    """Overview/Markets tabs API tests - /api/prediction/run"""
    
    def test_prediction_run_returns_sections(self):
        """GET /api/prediction/run returns sections with analyzed cases"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        assert "sections" in data
        print(f"Prediction run returned sections: {list(data['sections'].keys())}")
    
    def test_prediction_run_section_structure(self):
        """Each section contains market cases"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        sections = data.get("sections", {})
        total_cases = 0
        for section_name, cases in sections.items():
            if isinstance(cases, list):
                total_cases += len(cases)
                if cases:
                    case = cases[0]
                    assert "market_id" in case or "question" in case
        
        print(f"Total cases across all sections: {total_cases}")


class TestAlertCorrelationAPI:
    """Signals tab API tests"""
    
    def test_alert_history_returns_meta_alerts(self):
        """GET /api/alert-correlation/history returns metaAlerts"""
        response = requests.get(f"{BASE_URL}/api/alert-correlation/history?limit=20", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "metaAlerts" in data
        print(f"Alert history returned {len(data['metaAlerts'])} meta alerts")
    
    def test_alert_regime_returns_regime(self):
        """GET /api/alert-correlation/regime returns regime info"""
        response = requests.get(f"{BASE_URL}/api/alert-correlation/regime", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # May have regime or null
        print(f"Regime data: {data.get('regime', 'null')}")


class TestAnalyticsAPI:
    """Analytics tab API tests"""
    
    def test_weekly_digest_latest(self):
        """GET /api/prediction/weekly-digest/latest returns digest"""
        response = requests.get(f"{BASE_URL}/api/prediction/weekly-digest/latest", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # May have digest or null
        if data.get("digest"):
            print(f"Weekly digest found with performance: {data['digest'].get('performance', {})}")
        else:
            print("No weekly digest available yet")
    
    def test_outcome_lab_stats(self):
        """GET /api/outcome-lab/stats returns stats"""
        response = requests.get(f"{BASE_URL}/api/outcome-lab/stats", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        print(f"Outcome lab stats: {data}")


class TestMarketFeedRefresh:
    """Feed refresh API test"""
    
    def test_market_feed_refresh(self):
        """POST /api/market-feed/refresh triggers refresh"""
        response = requests.post(f"{BASE_URL}/api/market-feed/refresh", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        print(f"Refresh returned: hot={data.get('hot_count')}, actionable={data.get('actionable_count')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
