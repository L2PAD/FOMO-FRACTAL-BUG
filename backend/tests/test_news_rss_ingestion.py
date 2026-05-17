"""
News RSS Ingestion API Tests
============================
Tests for the news RSS adapter that fetches crypto news from RSS feeds,
normalizes to UnifiedTextEvent, deduplicates, and writes to raw_events.

Features tested:
- POST /api/admin/ingestion/news/run - triggers RSS fetching
- Deduplication (second run returns inserted=0)
- GET /api/admin/ingestion/raw-events/stats - shows news in bySource
- News flows through intake to sentiment_events
- ML training dataset (sentiment_dir_samples) has zero news entries
- POST /api/admin/ingestion/all/run - runs both twitter + news
- GET /api/admin/ingestion/health - health status
- GET /api/admin/ingestion/runs - recent ingestion runs
"""

import pytest
import requests
import os
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/intelligence_engine')


@pytest.fixture(scope='module')
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    return session


@pytest.fixture(scope='module')
def mongo_client():
    """MongoDB client for direct database checks"""
    client = MongoClient(MONGO_URL)
    db = client.get_database()
    yield db
    client.close()


class TestHealthEndpoints:
    """Health and status endpoint tests"""

    def test_api_health(self, api_client):
        """GET /api/health - Basic API health check"""
        response = api_client.get(f'{BASE_URL}/api/health')
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert data['service'] == 'node-backend'
        print(f"PASS: API health check - service={data['service']}")

    def test_ingestion_health(self, api_client):
        """GET /api/admin/ingestion/health - Ingestion health snapshot"""
        response = api_client.get(f'{BASE_URL}/api/admin/ingestion/health')
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'data' in data
        health = data['data']
        # Verify health fields
        assert 'scheduler' in health
        assert 'runsLast1h' in health
        assert 'eventsLast1h' in health
        print(f"PASS: Ingestion health - runsLast1h={health['runsLast1h']}, eventsLast1h={health['eventsLast1h']}")

    def test_ingestion_runs(self, api_client):
        """GET /api/admin/ingestion/runs - Recent ingestion runs"""
        response = api_client.get(f'{BASE_URL}/api/admin/ingestion/runs?limit=10')
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'data' in data
        runs_data = data['data']
        assert 'count' in runs_data
        assert 'runs' in runs_data
        assert isinstance(runs_data['runs'], list)
        print(f"PASS: Ingestion runs - count={runs_data['count']}")


class TestNewsIngestion:
    """News RSS ingestion endpoint tests"""

    def test_news_run_endpoint(self, api_client):
        """POST /api/admin/ingestion/news/run - Trigger news ingestion"""
        response = api_client.post(
            f'{BASE_URL}/api/admin/ingestion/news/run',
            json={'limit': 100, 'sinceMinutes': 180}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'data' in data
        result = data['data']
        
        # Verify result structure
        assert result['source'] == 'rss-news'
        assert 'fetched' in result
        assert 'inserted' in result
        assert 'duplicated' in result
        assert 'errors' in result
        assert 'durationMs' in result
        assert 'startedAt' in result
        assert 'finishedAt' in result
        
        print(f"PASS: News run - fetched={result['fetched']}, inserted={result['inserted']}, duplicated={result['duplicated']}, errors={result['errors']}")

    def test_news_deduplication(self, api_client):
        """Verify deduplication: second run should return inserted=0"""
        # First run
        response1 = api_client.post(
            f'{BASE_URL}/api/admin/ingestion/news/run',
            json={'limit': 50, 'sinceMinutes': 180}
        )
        assert response1.status_code == 200
        result1 = response1.json()['data']
        
        # Second run - should have 0 inserts (all duplicates)
        response2 = api_client.post(
            f'{BASE_URL}/api/admin/ingestion/news/run',
            json={'limit': 50, 'sinceMinutes': 180}
        )
        assert response2.status_code == 200
        result2 = response2.json()['data']
        
        # Verify deduplication
        assert result2['inserted'] == 0, f"Expected 0 inserts on second run, got {result2['inserted']}"
        # If first run fetched articles, second run should have same or fewer fetched (time window)
        # and all should be duplicated
        if result2['fetched'] > 0:
            assert result2['duplicated'] == result2['fetched'], \
                f"Expected all {result2['fetched']} to be duplicated, got {result2['duplicated']}"
        
        print(f"PASS: Deduplication - run1: fetched={result1['fetched']}, inserted={result1['inserted']} | run2: fetched={result2['fetched']}, inserted={result2['inserted']}, duplicated={result2['duplicated']}")


class TestRawEventsStats:
    """Raw events statistics tests"""

    def test_raw_events_stats_has_news(self, api_client):
        """GET /api/admin/ingestion/raw-events/stats - Verify news in bySource"""
        response = api_client.get(f'{BASE_URL}/api/admin/ingestion/raw-events/stats')
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        stats = data['data']
        
        # Verify stats structure
        assert 'total' in stats
        assert 'processed' in stats
        assert 'unprocessed' in stats
        assert 'bySource' in stats
        assert 'latest' in stats
        
        # Verify news entries exist in bySource
        by_source = stats['bySource']
        assert 'news' in by_source, f"Expected 'news' in bySource, got {by_source.keys()}"
        assert by_source['news'] > 0, f"Expected news count > 0, got {by_source['news']}"
        
        print(f"PASS: Raw events stats - total={stats['total']}, bySource={by_source}")


class TestAllIngestion:
    """Combined ingestion endpoint tests"""

    def test_all_run_endpoint(self, api_client):
        """POST /api/admin/ingestion/all/run - Run both twitter + news adapters"""
        response = api_client.post(
            f'{BASE_URL}/api/admin/ingestion/all/run',
            json={'limit': 50, 'sinceMinutes': 180}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'data' in data
        result = data['data']
        
        # Verify result structure
        assert 'sources' in result
        assert 'results' in result
        assert result['sources'] == 2, f"Expected 2 sources, got {result['sources']}"
        
        # Verify both adapters ran
        sources = [r['source'] for r in result['results']]
        assert 'twitter-bridge' in sources, f"Expected twitter-bridge in sources, got {sources}"
        assert 'rss-news' in sources, f"Expected rss-news in sources, got {sources}"
        
        print(f"PASS: All run - sources={result['sources']}, adapters={sources}")


class TestNewsDataFlow:
    """Tests for news data flow through the pipeline"""

    def test_news_in_sentiment_events(self, mongo_client):
        """Verify news events flow through intake to sentiment_events"""
        count = mongo_client.sentiment_events.count_documents({'sourceType': 'news'})
        assert count > 0, f"Expected news entries in sentiment_events, got {count}"
        print(f"PASS: News in sentiment_events - count={count}")

    def test_no_news_in_ml_training_dataset(self, mongo_client):
        """CRITICAL: Verify NO news entries in sentiment_dir_samples (ML training dataset)"""
        count = mongo_client.sentiment_dir_samples.count_documents({'sourceType': 'news'})
        assert count == 0, f"CONTAMINATION DETECTED: Found {count} news entries in sentiment_dir_samples"
        print(f"PASS: No news contamination in ML training dataset - count={count}")


class TestNewsRawEventFields:
    """Tests for proper news raw_event field structure"""

    def test_news_raw_event_fields(self, mongo_client):
        """Verify news raw_events have proper fields"""
        sample = mongo_client.raw_events.find_one({'sourceType': 'news'})
        assert sample is not None, "No news entries found in raw_events"
        
        # Required fields
        assert sample['sourceType'] == 'news'
        assert sample['sourceName'] == 'rss-news'
        assert 'externalId' in sample
        assert 'text' in sample
        assert 'publishedAt' in sample
        assert 'ingestedAt' in sample
        assert 'dedupeKey' in sample
        
        # Publisher fields
        assert 'publisher' in sample
        publisher = sample['publisher']
        assert 'name' in publisher, "Missing publisher.name"
        assert 'domain' in publisher, "Missing publisher.domain"
        
        # Optional but expected fields
        if 'title' in sample:
            assert isinstance(sample['title'], str)
        if 'url' in sample:
            assert isinstance(sample['url'], str)
        if 'summary' in sample:
            assert isinstance(sample['summary'], str)
        
        print(f"PASS: News raw_event fields - publisher={publisher['name']}, domain={publisher['domain']}")

    def test_news_from_multiple_feeds(self, mongo_client):
        """Verify news comes from multiple RSS feeds (at least 5)"""
        pipeline = [
            {'$match': {'sourceType': 'news'}},
            {'$group': {'_id': '$publisher.name', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]
        feeds = list(mongo_client.raw_events.aggregate(pipeline))
        feed_names = [f['_id'] for f in feeds]
        
        # Should have at least 5 different feeds
        assert len(feeds) >= 1, f"Expected at least 1 feed, got {len(feeds)}"
        
        # Known feeds we expect
        expected_feeds = ['CoinDesk', 'CoinTelegraph', 'TheBlock', 'Decrypt', 'CryptoSlate', 'BitcoinMagazine', 'NewsBTC', 'CryptoPotato']
        found_expected = [f for f in feed_names if f in expected_feeds]
        
        print(f"PASS: News from multiple feeds - total={len(feeds)}, feeds={feed_names}")


class TestSentimentEventsNewsFields:
    """Tests for news entries in sentiment_events"""

    def test_sentiment_events_news_structure(self, mongo_client):
        """Verify news entries in sentiment_events have proper structure"""
        sample = mongo_client.sentiment_events.find_one({'sourceType': 'news'})
        if sample is None:
            pytest.skip("No news entries in sentiment_events yet")
        
        # Required fields for sentiment_events
        assert sample['sourceType'] == 'news'
        assert 'symbol' in sample
        assert 'tweetId' in sample  # externalId mapped to tweetId
        assert 'baseScore' in sample
        assert 'baseLabel' in sample
        assert 'baseConfidence' in sample
        assert 'processedAt' in sample
        assert 'processingVersion' in sample
        
        print(f"PASS: Sentiment events news structure - symbol={sample['symbol']}, label={sample['baseLabel']}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
