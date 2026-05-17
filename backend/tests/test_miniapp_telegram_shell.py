"""
MiniApp Telegram Shell Tests - Testing all MiniApp endpoints and features
Tests: Home, Feed, Edge, Profile APIs and data structure validation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMiniAppHomeAPI:
    """Test /api/miniapp/home endpoint for all assets"""
    
    def test_home_btc_returns_200(self):
        """Test home endpoint for BTC returns 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data.get('asset') == 'BTC'
    
    def test_home_btc_has_decision_data(self):
        """Test BTC home has decision with action, confidence, strength"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        data = response.json()
        assert 'decision' in data
        decision = data['decision']
        assert 'action' in decision
        assert decision['action'] in ['BUY', 'SELL', 'WAIT', 'AVOID']
        assert 'confidence' in decision
        assert 0 <= decision['confidence'] <= 1
        assert 'strength' in decision
        assert 'mode' in decision
        assert 'riskLevel' in decision
    
    def test_home_btc_has_price(self):
        """Test BTC home has price data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        data = response.json()
        assert 'price' in data
        assert isinstance(data['price'], (int, float))
        assert data['price'] > 0
    
    def test_home_btc_has_structure(self):
        """Test BTC home has structure data with h24, d7, d30"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        data = response.json()
        assert 'structure' in data
        structure = data['structure']
        assert 'h24' in structure
        assert 'd7' in structure
        assert 'd30' in structure
        assert 'alignment' in structure
    
    def test_home_btc_has_pressure(self):
        """Test BTC home has pressure data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        data = response.json()
        assert 'pressure' in data
        pressure = data['pressure']
        assert 'exchange' in pressure
        assert 'onchain' in pressure
        assert 'sentiment' in pressure
        assert 'net' in pressure
    
    def test_home_btc_has_action_plan(self):
        """Test BTC home has actionPlan"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        data = response.json()
        assert 'actionPlan' in data
        plan = data['actionPlan']
        assert 'summary' in plan
    
    def test_home_btc_has_why_reasons(self):
        """Test BTC home has why reasons array"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        data = response.json()
        assert 'why' in data
        assert isinstance(data['why'], list)
    
    def test_home_eth_returns_200(self):
        """Test home endpoint for ETH returns 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=ETH")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data.get('asset') == 'ETH'
    
    def test_home_sol_returns_200(self):
        """Test home endpoint for SOL returns 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=SOL")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data.get('asset') == 'SOL'


class TestMiniAppFeedAPI:
    """Test /api/miniapp/feed endpoint"""
    
    def test_feed_returns_200(self):
        """Test feed endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
    
    def test_feed_has_sections(self):
        """Test feed has sections array (Now, Today, Earlier)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed")
        data = response.json()
        assert 'sections' in data
        assert isinstance(data['sections'], list)
    
    def test_feed_sections_have_labels(self):
        """Test feed sections have label and items"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed")
        data = response.json()
        for section in data.get('sections', []):
            assert 'label' in section
            assert 'items' in section
            assert isinstance(section['items'], list)
    
    def test_feed_items_have_required_fields(self):
        """Test feed items have required fields"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed")
        data = response.json()
        for section in data.get('sections', []):
            for item in section.get('items', []):
                # Check required fields
                assert 'source' in item
                assert 'direction' in item
                assert 'impact' in item
                assert 'title' in item


class TestMiniAppEdgeAPI:
    """Test /api/miniapp/edge endpoint"""
    
    def test_edge_returns_200(self):
        """Test edge endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
    
    def test_edge_has_status(self):
        """Test edge has status field"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        data = response.json()
        assert 'status' in data
    
    def test_edge_has_markets(self):
        """Test edge has markets array"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        data = response.json()
        assert 'markets' in data
        assert isinstance(data['markets'], list)
    
    def test_edge_markets_have_required_fields(self):
        """Test edge markets have required fields"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        data = response.json()
        for market in data.get('markets', []):
            assert 'asset' in market
            assert 'question' in market
            assert 'marketProbability' in market
            assert 'modelProbability' in market
            assert 'edge' in market
            assert 'direction' in market
            assert 'confidence' in market
    
    def test_edge_best_market_exists_when_active(self):
        """Test edge has best market when status is ACTIVE"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        data = response.json()
        if data.get('status') == 'ACTIVE':
            assert 'best' in data
            best = data['best']
            assert 'asset' in best
            assert 'edge' in best
            assert 'direction' in best


class TestMiniAppProfileAPI:
    """Test /api/miniapp/profile endpoint"""
    
    def test_profile_returns_200(self):
        """Test profile endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
    
    def test_profile_has_user(self):
        """Test profile has user data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        data = response.json()
        assert 'user' in data
        user = data['user']
        assert 'name' in user
        assert 'planStatus' in user
    
    def test_profile_has_performance(self):
        """Test profile has performance data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        data = response.json()
        assert 'performance' in data
        perf = data['performance']
        assert 'totalDecisions' in perf
        assert 'accuracy' in perf
    
    def test_profile_has_favorites(self):
        """Test profile has favorites array"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        data = response.json()
        assert 'favorites' in data
        assert isinstance(data['favorites'], list)
    
    def test_profile_has_referral(self):
        """Test profile has referral data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        data = response.json()
        assert 'referral' in data
        referral = data['referral']
        assert 'code' in referral
        assert 'inviteLink' in referral
    
    def test_profile_has_settings(self):
        """Test profile has settings"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        data = response.json()
        assert 'settings' in data
        settings = data['settings']
        assert 'alertsEnabled' in settings


class TestMiniAppBillingAPI:
    """Test /api/miniapp/billing endpoints"""
    
    def test_billing_plans_returns_200(self):
        """Test billing plans endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
    
    def test_billing_status_returns_200(self):
        """Test billing status endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True


class TestMiniAppSearchAPI:
    """Test /api/miniapp/search endpoint"""
    
    def test_search_btc_returns_results(self):
        """Test search for BTC returns results"""
        response = requests.get(f"{BASE_URL}/api/miniapp/search?q=BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'results' in data
    
    def test_search_empty_query_returns_200(self):
        """Test search with empty query returns 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/search?q=")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
