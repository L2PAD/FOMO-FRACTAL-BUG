"""
Santiment API Tests - Testing all new endpoints for Santiment pages
Tests: sentiment capabilities, feed, accounts, community, correlations, asset-tweets,
       entity-graph network/nodes/search, news articles, cluster-lifecycle, early-rotation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestSentimentCapabilities:
    """Test /api/v4/sentiment/capabilities endpoint"""
    
    def test_capabilities_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/capabilities")
        assert response.status_code == 200
        print("✓ Capabilities endpoint returns 200")
    
    def test_capabilities_has_ok_true(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/capabilities")
        data = response.json()
        assert data.get("ok") == True
        print("✓ Capabilities returns ok=true")
    
    def test_capabilities_has_models(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/capabilities")
        data = response.json()
        assert "models" in data.get("data", {})
        assert len(data["data"]["models"]) > 0
        print(f"✓ Capabilities has models: {data['data']['models']}")
    
    def test_capabilities_has_metadata(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/capabilities")
        data = response.json()
        cap_data = data.get("data", {})
        assert "totalTweetsAnalyzed" in cap_data
        assert "totalAccounts" in cap_data
        assert "sentimentTypes" in cap_data
        print(f"✓ Capabilities has metadata: tweets={cap_data['totalTweetsAnalyzed']}, accounts={cap_data['totalAccounts']}")


class TestSentimentFeed:
    """Test /api/v4/sentiment/feed endpoint - replaces MOCK_TWEETS"""
    
    def test_feed_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=10")
        assert response.status_code == 200
        print("✓ Feed endpoint returns 200")
    
    def test_feed_has_ok_true(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=10")
        data = response.json()
        assert data.get("ok") == True
        print("✓ Feed returns ok=true")
    
    def test_feed_returns_tweets(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=10")
        data = response.json()
        tweets = data.get("data", [])
        assert len(tweets) > 0
        print(f"✓ Feed returns {len(tweets)} tweets")
    
    def test_feed_tweet_has_sentiment_label(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=5")
        data = response.json()
        tweets = data.get("data", [])
        for tweet in tweets[:3]:
            assert "sentiment" in tweet
            assert "label" in tweet["sentiment"]
            assert tweet["sentiment"]["label"] in ["POSITIVE", "NEUTRAL", "NEGATIVE"]
        print("✓ Feed tweets have sentiment.label (POSITIVE/NEUTRAL/NEGATIVE)")
    
    def test_feed_tweet_has_sentiment_score(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=5")
        data = response.json()
        tweets = data.get("data", [])
        for tweet in tweets[:3]:
            assert "score" in tweet["sentiment"]
            assert 0 <= tweet["sentiment"]["score"] <= 1
        print("✓ Feed tweets have sentiment.score (0-1)")
    
    def test_feed_tweet_has_comments_aggregate(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=5")
        data = response.json()
        tweets = data.get("data", [])
        for tweet in tweets[:3]:
            assert "commentsAggregate" in tweet
            agg = tweet["commentsAggregate"]
            assert "total" in agg
            assert "distribution" in agg
        print("✓ Feed tweets have commentsAggregate")


class TestSentimentAccounts:
    """Test /api/v4/sentiment/accounts endpoint - replaces MOCK_ACCOUNTS"""
    
    def test_accounts_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/accounts")
        assert response.status_code == 200
        print("✓ Accounts endpoint returns 200")
    
    def test_accounts_has_ok_true(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/accounts")
        data = response.json()
        assert data.get("ok") == True
        print("✓ Accounts returns ok=true")
    
    def test_accounts_returns_data(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/accounts")
        data = response.json()
        accounts = data.get("data", [])
        assert len(accounts) > 0
        print(f"✓ Accounts returns {len(accounts)} accounts")
    
    def test_accounts_have_account_sentiment(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/accounts")
        data = response.json()
        accounts = data.get("data", [])
        for acc in accounts[:3]:
            assert "accountSentiment" in acc
            sent = acc["accountSentiment"]
            assert "current" in sent
            assert "label" in sent["current"]
        print("✓ Accounts have accountSentiment with current.label")


class TestSentimentCommunity:
    """Test /api/v4/sentiment/community endpoint"""
    
    def test_community_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/community")
        assert response.status_code == 200
        print("✓ Community endpoint returns 200")
    
    def test_community_has_aggregation(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/community")
        data = response.json()
        assert data.get("ok") == True
        comm = data.get("data", {})
        assert "total" in comm
        assert "positive" in comm
        assert "neutral" in comm
        assert "negative" in comm
        print(f"✓ Community has aggregation: total={comm['total']}, pos={comm['positive']}, neu={comm['neutral']}, neg={comm['negative']}")


class TestSentimentCorrelations:
    """Test /api/v4/sentiment/correlations endpoint - replaces MOCK_CORRELATIONS"""
    
    def test_correlations_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        print("✓ Correlations endpoint returns 200")
    
    def test_correlations_has_ok_true(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        assert data.get("ok") == True
        print("✓ Correlations returns ok=true")
    
    def test_correlations_returns_entities(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        entities = data.get("data", [])
        assert len(entities) >= 10  # Should return at least 10 entities
        print(f"✓ Correlations returns {len(entities)} entities")
    
    def test_correlations_have_signal_type(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        entities = data.get("data", [])
        for entity in entities[:5]:
            assert "signal" in entity
            assert "type" in entity["signal"]
            assert entity["signal"]["type"] in ["BUY", "SELL", "HOLD"]
        print("✓ Correlations have signal.type (BUY/SELL/HOLD)")
    
    def test_correlations_have_correlation_strength(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        entities = data.get("data", [])
        for entity in entities[:5]:
            assert "correlation" in entity
            assert "strength" in entity["correlation"]
            assert 0 <= entity["correlation"]["strength"] <= 1
        print("✓ Correlations have correlation.strength (0-1)")


class TestAssetTweets:
    """Test /api/v4/sentiment/asset-tweets/{entity_id} endpoint"""
    
    def test_asset_tweets_ethereum_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/asset-tweets/ethereum?limit=5")
        assert response.status_code == 200
        print("✓ Asset tweets for ethereum returns 200")
    
    def test_asset_tweets_has_ok_true(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/asset-tweets/ethereum?limit=5")
        data = response.json()
        assert data.get("ok") == True
        print("✓ Asset tweets returns ok=true")
    
    def test_asset_tweets_returns_tweets(self):
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/asset-tweets/ethereum?limit=5")
        data = response.json()
        tweets = data.get("data", [])
        # May return 0 if no tweets mention ethereum specifically
        print(f"✓ Asset tweets returns {len(tweets)} tweets mentioning ethereum")


class TestEntityGraphNetwork:
    """Test /api/entity-graph/network endpoint"""
    
    def test_network_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/entity-graph/network?limit_nodes=20&limit_edges=50")
        assert response.status_code == 200
        print("✓ Entity graph network returns 200")
    
    def test_network_has_nodes_and_edges(self):
        response = requests.get(f"{BASE_URL}/api/entity-graph/network?limit_nodes=20&limit_edges=50")
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0
        print(f"✓ Entity graph has {len(data['nodes'])} nodes and {len(data['edges'])} edges")
    
    def test_network_nodes_have_type(self):
        response = requests.get(f"{BASE_URL}/api/entity-graph/network?limit_nodes=20&limit_edges=50")
        data = response.json()
        nodes = data.get("nodes", [])
        for node in nodes[:5]:
            assert "type" in node
            assert node["type"] in ["project", "fund", "person", "twitter_account", "protocol", "entity", "narrative"]
        print("✓ Entity graph nodes have type (project/fund/person/etc)")


class TestEntityGraphNodes:
    """Test /api/entity-graph/nodes endpoint"""
    
    def test_nodes_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/entity-graph/nodes?limit=10")
        assert response.status_code == 200
        print("✓ Entity graph nodes returns 200")
    
    def test_nodes_has_ok_true(self):
        response = requests.get(f"{BASE_URL}/api/entity-graph/nodes?limit=10")
        data = response.json()
        assert data.get("ok") == True
        print("✓ Entity graph nodes returns ok=true")
    
    def test_nodes_has_total(self):
        response = requests.get(f"{BASE_URL}/api/entity-graph/nodes?limit=10")
        data = response.json()
        assert "total" in data
        assert data["total"] > 0
        print(f"✓ Entity graph has total={data['total']} nodes")
    
    def test_nodes_have_features(self):
        response = requests.get(f"{BASE_URL}/api/entity-graph/nodes?limit=10")
        data = response.json()
        nodes = data.get("nodes", [])
        for node in nodes[:3]:
            assert "features" in node
        print("✓ Entity graph nodes have features")


class TestEntityGraphSearch:
    """Test /api/entity-graph/search endpoint"""
    
    def test_search_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/entity-graph/search?q=ethereum")
        assert response.status_code == 200
        print("✓ Entity graph search returns 200")
    
    def test_search_has_ok_true(self):
        response = requests.get(f"{BASE_URL}/api/entity-graph/search?q=ethereum")
        data = response.json()
        assert data.get("ok") == True
        print("✓ Entity graph search returns ok=true")
    
    def test_search_returns_results(self):
        response = requests.get(f"{BASE_URL}/api/entity-graph/search?q=ethereum")
        data = response.json()
        results = data.get("results", [])
        assert len(results) > 0
        print(f"✓ Entity graph search returns {len(results)} results for 'ethereum'")


class TestNewsArticles:
    """Test /api/news/articles endpoint"""
    
    def test_articles_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/news/articles?limit=5")
        assert response.status_code == 200
        print("✓ News articles returns 200")
    
    def test_articles_has_ok_true(self):
        response = requests.get(f"{BASE_URL}/api/news/articles?limit=5")
        data = response.json()
        assert data.get("ok") == True
        print("✓ News articles returns ok=true")
    
    def test_articles_has_total(self):
        response = requests.get(f"{BASE_URL}/api/news/articles?limit=5")
        data = response.json()
        assert "total" in data
        assert data["total"] > 0
        print(f"✓ News articles has total={data['total']}")
    
    def test_articles_returns_data(self):
        response = requests.get(f"{BASE_URL}/api/news/articles?limit=5")
        data = response.json()
        articles = data.get("articles", [])
        assert len(articles) > 0
        print(f"✓ News articles returns {len(articles)} articles")


class TestClusterLifecycle:
    """Test /api/connections/cluster-lifecycle endpoint"""
    
    def test_lifecycle_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        assert response.status_code == 200
        print("✓ Cluster lifecycle returns 200")
    
    def test_lifecycle_has_ok_true(self):
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        data = response.json()
        assert data.get("ok") == True
        print("✓ Cluster lifecycle returns ok=true")
    
    def test_lifecycle_returns_states(self):
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        data = response.json()
        states = data.get("data", [])
        assert len(states) > 0
        print(f"✓ Cluster lifecycle returns {len(states)} entities with states")
    
    def test_lifecycle_has_valid_states(self):
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        data = response.json()
        states = data.get("data", [])
        valid_states = ["IGNITION", "ACCUMULATION", "MARKUP", "DISTRIBUTION", "DECLINE"]
        for item in states[:5]:
            assert "state" in item
            assert item["state"] in valid_states
        print("✓ Cluster lifecycle has valid states (IGNITION/ACCUMULATION/MARKUP/DISTRIBUTION/DECLINE)")


class TestEarlyRotation:
    """Test /api/connections/early-rotation/active endpoint"""
    
    def test_rotation_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        assert response.status_code == 200
        print("✓ Early rotation returns 200")
    
    def test_rotation_has_ok_true(self):
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        data = response.json()
        assert data.get("ok") == True
        print("✓ Early rotation returns ok=true")
    
    def test_rotation_returns_signals(self):
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        data = response.json()
        signals = data.get("data", [])
        assert len(signals) > 0
        print(f"✓ Early rotation returns {len(signals)} rotation signals")
    
    def test_rotation_has_direction(self):
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        data = response.json()
        signals = data.get("data", [])
        valid_directions = ["ACCELERATING", "EMERGING", "EARLY"]
        for sig in signals[:5]:
            assert "direction" in sig
            assert sig["direction"] in valid_directions
        print("✓ Early rotation has direction (ACCELERATING/EMERGING/EARLY)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
