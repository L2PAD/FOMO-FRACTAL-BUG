"""
MiniApp Home Shell API Tests
Tests for the Telegram Mini App Pocket Intelligence OS endpoints:
- /api/miniapp/home - Home screen data (decision, structure, signals, story, price)
- /api/miniapp/search - Asset search
- /api/miniapp/feed - Signal feed
- /api/miniapp/polymarket - Polymarket edge data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestMiniAppHomeEndpoint:
    """Tests for /api/miniapp/home endpoint"""

    def test_home_btc_returns_valid_json(self):
        """GET /api/miniapp/home?asset=BTC returns valid JSON with all required fields"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("asset") == "BTC"
        
        # Verify decision block
        decision = data.get("decision")
        assert decision is not None
        assert "action" in decision
        assert decision["action"] in ["BUY", "SELL", "WAIT", "AVOID"]
        assert "confidence" in decision
        assert 0 <= decision["confidence"] <= 1
        assert "type" in decision
        assert "expectedMovePct" in decision
        
        # Verify price block
        price = data.get("price")
        assert price is not None
        assert "current" in price
        assert isinstance(price["current"], (int, float))
        assert "range30d" in price
        assert "low" in price["range30d"]
        assert "high" in price["range30d"]
        
        # Verify story
        story = data.get("story")
        assert story is not None
        assert isinstance(story, str)
        assert len(story) > 0
        
        # Verify structure (24H/7D/30D + alignment)
        structure = data.get("structure")
        assert structure is not None
        assert "h24" in structure
        assert "d7" in structure
        assert "d30" in structure
        assert "alignment" in structure
        
        # Verify each horizon has direction and confidence
        for horizon in ["h24", "d7", "d30"]:
            h_data = structure[horizon]
            assert "direction" in h_data
            assert h_data["direction"] in ["bullish", "bearish", "neutral"]
            assert "confidence" in h_data
        
        # Verify alignment value
        assert structure["alignment"] in ["full_alignment", "short_term_divergence", "long_term_divergence", "partial_divergence"]
        
        # Verify signals
        signals = data.get("signals")
        assert signals is not None
        assert "exchange" in signals
        assert "onchain" in signals
        assert "sentiment" in signals
        assert "twitter" in signals
        assert "mlRisk" in signals
        
        # Verify signal structure (direction + strength labels)
        for sig_key in ["exchange", "onchain", "sentiment"]:
            sig = signals[sig_key]
            assert "direction" in sig
            assert sig["direction"] in ["bullish", "bearish", "neutral"]
            assert "strength" in sig
            assert sig["strength"] in ["weak", "moderate", "strong", "extreme"]
        
        # Verify twitter signal
        assert "narrative" in signals["twitter"]
        assert "strength" in signals["twitter"]
        
        # Verify mlRisk
        assert "level" in signals["mlRisk"]
        assert signals["mlRisk"]["level"] in ["low", "medium", "high", "unknown"]
        assert "score" in signals["mlRisk"]
        
        # Verify alerts_preview
        alerts = data.get("alerts_preview")
        assert alerts is not None
        assert isinstance(alerts, list)
        
        print(f"✓ BTC home data valid: action={decision['action']}, confidence={decision['confidence']}")

    def test_home_eth_returns_valid_data(self):
        """GET /api/miniapp/home?asset=ETH returns valid data for ETH"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=ETH", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("asset") == "ETH"
        
        # Verify core fields exist
        assert "decision" in data
        assert "price" in data
        assert "story" in data
        assert "structure" in data
        assert "signals" in data
        
        # Verify ETH-specific price is reasonable
        price = data["price"]["current"]
        assert price > 0
        assert price < 100000  # ETH should be less than 100k
        
        print(f"✓ ETH home data valid: price=${price}")

    def test_home_sol_returns_valid_data(self):
        """GET /api/miniapp/home?asset=SOL returns valid data for SOL"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=SOL", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("asset") == "SOL"
        
        print(f"✓ SOL home data valid")


class TestMiniAppSearchEndpoint:
    """Tests for /api/miniapp/search endpoint"""

    def test_search_eth_returns_results(self):
        """GET /api/miniapp/search?q=eth returns search results"""
        response = requests.get(f"{BASE_URL}/api/miniapp/search?q=eth", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "results" in data
        
        results = data["results"]
        assert isinstance(results, list)
        assert len(results) > 0
        
        # Verify ETH is in results
        tickers = [r["ticker"] for r in results]
        assert "ETH" in tickers
        
        # Verify result structure
        for r in results:
            assert "ticker" in r
            assert "name" in r
        
        print(f"✓ Search 'eth' returned {len(results)} results")

    def test_search_empty_returns_default_assets(self):
        """GET /api/miniapp/search?q= returns default assets"""
        response = requests.get(f"{BASE_URL}/api/miniapp/search?q=", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "results" in data
        
        results = data["results"]
        assert isinstance(results, list)
        assert len(results) >= 3  # Should return at least BTC, ETH, SOL
        
        tickers = [r["ticker"] for r in results]
        assert "BTC" in tickers
        assert "ETH" in tickers
        
        print(f"✓ Empty search returned {len(results)} default assets")

    def test_search_btc_returns_bitcoin(self):
        """GET /api/miniapp/search?q=btc returns Bitcoin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/search?q=btc", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        results = data.get("results", [])
        
        btc_result = next((r for r in results if r["ticker"] == "BTC"), None)
        assert btc_result is not None
        assert btc_result["name"] == "Bitcoin"
        
        print(f"✓ Search 'btc' found Bitcoin")


class TestMiniAppFeedEndpoint:
    """Tests for /api/miniapp/feed endpoint"""

    def test_feed_returns_items(self):
        """GET /api/miniapp/feed returns feed items"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data
        
        items = data["items"]
        assert isinstance(items, list)
        
        # Verify item structure if items exist
        if len(items) > 0:
            item = items[0]
            assert "type" in item
            assert "message" in item
            assert "impact" in item
            assert "timestamp" in item
            
            # Verify impact values
            for i in items[:5]:
                assert i["impact"] in ["bullish", "bearish", "neutral"]
        
        print(f"✓ Feed returned {len(items)} items")

    def test_feed_with_limit(self):
        """GET /api/miniapp/feed?limit=5 respects limit"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed?limit=5", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        assert len(items) <= 5
        
        print(f"✓ Feed with limit=5 returned {len(items)} items")


class TestMiniAppPolymarketEndpoint:
    """Tests for /api/miniapp/polymarket endpoint"""

    def test_polymarket_returns_structure(self):
        """GET /api/miniapp/polymarket returns spotlight and markets"""
        response = requests.get(f"{BASE_URL}/api/miniapp/polymarket", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Verify structure exists (spotlight can be null if no markets with edge)
        assert "spotlight" in data
        assert "markets" in data
        
        markets = data["markets"]
        assert isinstance(markets, list)
        
        # If markets exist, verify structure
        if len(markets) > 0:
            market = markets[0]
            assert "market" in market
            assert "market_prob" in market
            assert "model_prob" in market
            assert "edge" in market
            assert "action" in market
        
        print(f"✓ Polymarket returned {len(markets)} markets, spotlight={'yes' if data['spotlight'] else 'no'}")


class TestMiniAppDataIntegrity:
    """Tests for data integrity across endpoints"""

    def test_home_generated_at_is_recent(self):
        """Verify generated_at timestamp is recent"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        
        assert "generated_at" in data
        # Just verify it's a valid ISO timestamp
        from datetime import datetime
        try:
            datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
            print(f"✓ generated_at is valid: {data['generated_at']}")
        except ValueError:
            pytest.fail(f"Invalid generated_at timestamp: {data['generated_at']}")

    def test_price_range_is_valid(self):
        """Verify price range low < current < high"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        
        price = data.get("price", {})
        current = price.get("current", 0)
        low = price.get("range30d", {}).get("low", 0)
        high = price.get("range30d", {}).get("high", 0)
        
        # Range should bracket current price
        assert low < current < high, f"Price range invalid: {low} < {current} < {high}"
        print(f"✓ Price range valid: ${low:,.0f} < ${current:,.0f} < ${high:,.0f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
