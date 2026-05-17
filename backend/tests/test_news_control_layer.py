"""
News Control Layer API Tests
=============================
Tests for the admin API /api/admin/news/ for managing and monitoring
the news ingestion pipeline.

Endpoints tested:
- GET  /api/admin/news/sources        - List all sources with stats
- POST /api/admin/news/sources/toggle - Enable/disable a source
- GET  /api/admin/news/health         - Comprehensive health snapshot
- POST /api/admin/news/run            - Manual news ingestion trigger
- GET  /api/admin/news/events         - Recent news events preview
- GET  /api/admin/news/events/stats   - News event statistics

Features tested:
- Source registry with 8 sources (id, name, url, enabled, tier, successRate, healthy, etc.)
- Toggle source enable/disable
- Health snapshot with alerts (rate_guard, empty_feed, source_failure, high_error_rate)
- Source failure tracking (3 consecutive fails → unhealthy)
- Events filtering by source and asset
- Validation errors (400 for missing fields)
- Existing ingestion endpoints still work
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected source IDs
EXPECTED_SOURCE_IDS = [
    'coindesk', 'cointelegraph', 'theblock', 'decrypt',
    'cryptoslate', 'bitcoinmagazine', 'newsbtc', 'cryptopotato'
]


@pytest.fixture(scope='module')
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    return session


class TestSourcesRegistry:
    """Tests for GET /api/admin/news/sources - Source registry endpoint"""

    def test_get_sources_returns_all_8_sources(self, api_client):
        """GET /api/admin/news/sources - Returns all 8 sources with full stats"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/sources')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data['ok'] is True
        assert 'data' in data
        
        sources_data = data['data']
        assert 'total' in sources_data
        assert 'enabled' in sources_data
        assert 'sources' in sources_data
        
        sources = sources_data['sources']
        assert len(sources) == 8, f"Expected 8 sources, got {len(sources)}"
        
        # Verify all expected source IDs are present
        source_ids = [s['id'] for s in sources]
        for expected_id in EXPECTED_SOURCE_IDS:
            assert expected_id in source_ids, f"Missing source: {expected_id}"
        
        print(f"PASS: Sources registry - total={sources_data['total']}, enabled={sources_data['enabled']}")

    def test_sources_have_required_fields(self, api_client):
        """Verify each source has all required fields"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/sources')
        assert response.status_code == 200
        
        sources = response.json()['data']['sources']
        
        required_fields = [
            'id', 'name', 'url', 'enabled', 'tier', 'lang',
            'lastFetchAt', 'lastSuccessAt', 'lastErrorAt', 'lastError',
            'consecutiveFailures', 'totalFetches', 'totalSuccess', 'totalErrors',
            'totalArticles', 'avgLatencyMs', 'successRate', 'healthy',
            'createdAt', 'updatedAt'
        ]
        
        for source in sources:
            for field in required_fields:
                assert field in source, f"Source {source.get('id', 'unknown')} missing field: {field}"
        
        # Verify tier values
        valid_tiers = ['A', 'B', 'C']
        for source in sources:
            assert source['tier'] in valid_tiers, f"Invalid tier for {source['id']}: {source['tier']}"
        
        print(f"PASS: All sources have required fields")

    def test_sources_stats_tracking(self, api_client):
        """Verify sources have stats tracking fields with correct types"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/sources')
        assert response.status_code == 200
        
        sources = response.json()['data']['sources']
        
        for source in sources:
            # Numeric fields
            assert isinstance(source['consecutiveFailures'], int), f"{source['id']}: consecutiveFailures not int"
            assert isinstance(source['totalFetches'], int), f"{source['id']}: totalFetches not int"
            assert isinstance(source['totalSuccess'], int), f"{source['id']}: totalSuccess not int"
            assert isinstance(source['totalErrors'], int), f"{source['id']}: totalErrors not int"
            assert isinstance(source['totalArticles'], int), f"{source['id']}: totalArticles not int"
            assert isinstance(source['avgLatencyMs'], (int, float)), f"{source['id']}: avgLatencyMs not numeric"
            assert isinstance(source['successRate'], (int, float)), f"{source['id']}: successRate not numeric"
            
            # Boolean fields
            assert isinstance(source['enabled'], bool), f"{source['id']}: enabled not bool"
            assert isinstance(source['healthy'], bool), f"{source['id']}: healthy not bool"
        
        print(f"PASS: Sources stats tracking fields have correct types")


class TestSourceToggle:
    """Tests for POST /api/admin/news/sources/toggle - Toggle source enable/disable"""

    def test_toggle_source_disable(self, api_client):
        """POST /api/admin/news/sources/toggle - Disable a source"""
        # First get current state
        response = api_client.get(f'{BASE_URL}/api/admin/news/sources')
        sources = response.json()['data']['sources']
        test_source = next((s for s in sources if s['id'] == 'newsbtc'), None)
        assert test_source is not None, "newsbtc source not found"
        
        # Toggle to disabled
        toggle_response = api_client.post(
            f'{BASE_URL}/api/admin/news/sources/toggle',
            json={'sourceId': 'newsbtc', 'enabled': False}
        )
        assert toggle_response.status_code == 200, f"Expected 200, got {toggle_response.status_code}: {toggle_response.text}"
        
        data = toggle_response.json()
        assert data['ok'] is True
        assert data['data']['enabled'] is False
        assert data['data']['id'] == 'newsbtc'
        
        print(f"PASS: Toggle source disable - newsbtc disabled")

    def test_toggle_source_enable(self, api_client):
        """POST /api/admin/news/sources/toggle - Enable a source"""
        # Toggle back to enabled
        toggle_response = api_client.post(
            f'{BASE_URL}/api/admin/news/sources/toggle',
            json={'sourceId': 'newsbtc', 'enabled': True}
        )
        assert toggle_response.status_code == 200
        
        data = toggle_response.json()
        assert data['ok'] is True
        assert data['data']['enabled'] is True
        
        print(f"PASS: Toggle source enable - newsbtc enabled")

    def test_toggle_missing_source_id_returns_400(self, api_client):
        """POST /api/admin/news/sources/toggle - Missing sourceId returns 400"""
        response = api_client.post(
            f'{BASE_URL}/api/admin/news/sources/toggle',
            json={'enabled': True}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert data['ok'] is False
        assert 'error' in data
        
        print(f"PASS: Toggle validation - missing sourceId returns 400")

    def test_toggle_missing_enabled_returns_400(self, api_client):
        """POST /api/admin/news/sources/toggle - Missing enabled returns 400"""
        response = api_client.post(
            f'{BASE_URL}/api/admin/news/sources/toggle',
            json={'sourceId': 'coindesk'}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert data['ok'] is False
        
        print(f"PASS: Toggle validation - missing enabled returns 400")

    def test_toggle_nonexistent_source_returns_404(self, api_client):
        """POST /api/admin/news/sources/toggle - Nonexistent source returns 404"""
        response = api_client.post(
            f'{BASE_URL}/api/admin/news/sources/toggle',
            json={'sourceId': 'nonexistent_source', 'enabled': True}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = response.json()
        assert data['ok'] is False
        
        print(f"PASS: Toggle validation - nonexistent source returns 404")


class TestHealthEndpoint:
    """Tests for GET /api/admin/news/health - Comprehensive health snapshot"""

    def test_health_returns_comprehensive_snapshot(self, api_client):
        """GET /api/admin/news/health - Returns comprehensive health snapshot"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/health')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data['ok'] is True
        assert 'data' in data
        
        health = data['data']
        
        # Required fields
        required_fields = [
            'totalSources', 'activeSources', 'healthySources', 'unhealthySources',
            'lastRunAt', 'lastSuccessAt',
            'eventsLast1h', 'eventsLast6h', 'eventsLast24h',
            'errorRate', 'avgLatencyMs', 'dedupeRate',
            'topSources', 'failingSources', 'alerts'
        ]
        
        for field in required_fields:
            assert field in health, f"Missing health field: {field}"
        
        print(f"PASS: Health snapshot - totalSources={health['totalSources']}, activeSources={health['activeSources']}, healthySources={health['healthySources']}")

    def test_health_source_counts(self, api_client):
        """Verify health source counts are consistent"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/health')
        health = response.json()['data']
        
        assert health['totalSources'] == 8, f"Expected 8 total sources, got {health['totalSources']}"
        assert health['activeSources'] <= health['totalSources']
        assert health['healthySources'] <= health['activeSources']
        assert health['unhealthySources'] <= health['activeSources']
        assert health['healthySources'] + health['unhealthySources'] == health['activeSources']
        
        print(f"PASS: Health source counts consistent - healthy={health['healthySources']}, unhealthy={health['unhealthySources']}")

    def test_health_top_sources_structure(self, api_client):
        """Verify topSources has correct structure"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/health')
        health = response.json()['data']
        
        top_sources = health['topSources']
        assert isinstance(top_sources, list)
        
        for source in top_sources:
            assert 'name' in source
            assert 'articles' in source
            assert 'tier' in source
        
        print(f"PASS: Health topSources structure - count={len(top_sources)}")

    def test_health_failing_sources_structure(self, api_client):
        """Verify failingSources has correct structure"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/health')
        health = response.json()['data']
        
        failing_sources = health['failingSources']
        assert isinstance(failing_sources, list)
        
        for source in failing_sources:
            assert 'name' in source
            assert 'error' in source
            assert 'consecutiveFailures' in source
        
        print(f"PASS: Health failingSources structure - count={len(failing_sources)}")

    def test_health_alerts_structure(self, api_client):
        """Verify alerts has correct structure"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/health')
        health = response.json()['data']
        
        alerts = health['alerts']
        assert isinstance(alerts, list)
        
        valid_types = ['rate_guard', 'empty_feed', 'source_failure', 'high_error_rate']
        valid_severities = ['warning', 'critical']
        
        for alert in alerts:
            assert 'type' in alert
            assert 'severity' in alert
            assert 'message' in alert
            assert 'timestamp' in alert
            assert alert['type'] in valid_types, f"Invalid alert type: {alert['type']}"
            assert alert['severity'] in valid_severities, f"Invalid severity: {alert['severity']}"
        
        print(f"PASS: Health alerts structure - count={len(alerts)}")


class TestSourceFailureTracking:
    """Tests for source failure tracking (3 consecutive fails → unhealthy)"""

    def test_cryptopotato_shows_failures(self, api_client):
        """CryptoPotato should show consecutiveFailures > 0 (known 403 error)"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/sources')
        sources = response.json()['data']['sources']
        
        cryptopotato = next((s for s in sources if s['id'] == 'cryptopotato'), None)
        assert cryptopotato is not None, "CryptoPotato source not found"
        
        # CryptoPotato is known to return 403, so it should have failures
        # Note: This may be 0 if no fetches have been attempted yet
        print(f"INFO: CryptoPotato - consecutiveFailures={cryptopotato['consecutiveFailures']}, healthy={cryptopotato['healthy']}, lastError={cryptopotato.get('lastError')}")
        
        # If there have been fetches, check failure tracking
        if cryptopotato['totalFetches'] > 0:
            # CryptoPotato should have errors
            assert cryptopotato['totalErrors'] > 0 or cryptopotato['consecutiveFailures'] > 0, \
                "CryptoPotato should have errors (known 403)"
        
        print(f"PASS: CryptoPotato failure tracking verified")

    def test_failing_sources_in_health(self, api_client):
        """Verify failingSources in health shows sources with consecutiveFailures > 0"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/health')
        health = response.json()['data']
        
        failing_sources = health['failingSources']
        
        # Cross-check with sources registry
        sources_response = api_client.get(f'{BASE_URL}/api/admin/news/sources')
        sources = sources_response.json()['data']['sources']
        
        sources_with_failures = [s for s in sources if s['consecutiveFailures'] > 0]
        
        # failingSources should match sources with consecutiveFailures > 0
        failing_names = [f['name'] for f in failing_sources]
        for source in sources_with_failures:
            assert source['name'] in failing_names, \
                f"Source {source['name']} has {source['consecutiveFailures']} failures but not in failingSources"
        
        print(f"PASS: Failing sources cross-check - failingSources={len(failing_sources)}, sources_with_failures={len(sources_with_failures)}")


class TestManualRun:
    """Tests for POST /api/admin/news/run - Manual news ingestion trigger"""

    def test_manual_run_triggers_ingestion(self, api_client):
        """POST /api/admin/news/run - Triggers manual news ingestion"""
        response = api_client.post(
            f'{BASE_URL}/api/admin/news/run',
            json={'limit': 50, 'sinceMinutes': 180}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data['ok'] is True
        assert 'data' in data
        
        result = data['data']
        
        # Verify result structure
        assert 'source' in result
        assert result['source'] == 'rss-news'
        assert 'fetched' in result
        assert 'inserted' in result
        assert 'duplicated' in result
        assert 'errors' in result
        assert 'durationMs' in result
        assert 'startedAt' in result
        assert 'finishedAt' in result
        
        print(f"PASS: Manual run - fetched={result['fetched']}, inserted={result['inserted']}, duplicated={result['duplicated']}, errors={result['errors']}")

    def test_manual_run_with_seed_all(self, api_client):
        """POST /api/admin/news/run with seedAll=true"""
        response = api_client.post(
            f'{BASE_URL}/api/admin/news/run',
            json={'limit': 10, 'seedAll': True}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        
        print(f"PASS: Manual run with seedAll")


class TestDisabledSourceExclusion:
    """Tests for disabled source exclusion from fetch"""

    def test_disabled_source_not_fetched(self, api_client):
        """Verify disabled source is excluded from next fetch"""
        # Disable a source
        api_client.post(
            f'{BASE_URL}/api/admin/news/sources/toggle',
            json={'sourceId': 'newsbtc', 'enabled': False}
        )
        
        # Get source state before run
        sources_before = api_client.get(f'{BASE_URL}/api/admin/news/sources').json()['data']['sources']
        newsbtc_before = next((s for s in sources_before if s['id'] == 'newsbtc'), None)
        last_fetch_before = newsbtc_before['lastFetchAt']
        
        # Run ingestion
        api_client.post(
            f'{BASE_URL}/api/admin/news/run',
            json={'limit': 50, 'sinceMinutes': 180}
        )
        
        # Get source state after run
        sources_after = api_client.get(f'{BASE_URL}/api/admin/news/sources').json()['data']['sources']
        newsbtc_after = next((s for s in sources_after if s['id'] == 'newsbtc'), None)
        last_fetch_after = newsbtc_after['lastFetchAt']
        
        # lastFetchAt should not have changed for disabled source
        assert last_fetch_before == last_fetch_after, \
            f"Disabled source was fetched: before={last_fetch_before}, after={last_fetch_after}"
        
        # Re-enable the source
        api_client.post(
            f'{BASE_URL}/api/admin/news/sources/toggle',
            json={'sourceId': 'newsbtc', 'enabled': True}
        )
        
        print(f"PASS: Disabled source not fetched")


class TestEventsEndpoint:
    """Tests for GET /api/admin/news/events - Recent news events preview"""

    def test_events_returns_recent_events(self, api_client):
        """GET /api/admin/news/events - Returns recent news events"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/events')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data['ok'] is True
        assert 'data' in data
        
        events_data = data['data']
        assert 'count' in events_data
        assert 'events' in events_data
        assert isinstance(events_data['events'], list)
        
        print(f"PASS: Events endpoint - count={events_data['count']}")

    def test_events_with_limit(self, api_client):
        """GET /api/admin/news/events?limit=5 - Respects limit parameter"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/events?limit=5')
        assert response.status_code == 200
        
        events = response.json()['data']['events']
        assert len(events) <= 5, f"Expected max 5 events, got {len(events)}"
        
        print(f"PASS: Events with limit - count={len(events)}")

    def test_events_filter_by_source(self, api_client):
        """GET /api/admin/news/events?source=CoinDesk - Filter by source"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/events?source=CoinDesk')
        assert response.status_code == 200
        
        events = response.json()['data']['events']
        
        # All events should be from CoinDesk (case-insensitive match)
        for event in events:
            publisher_name = event.get('publisher', {}).get('name', '')
            assert 'coindesk' in publisher_name.lower(), \
                f"Event not from CoinDesk: {publisher_name}"
        
        print(f"PASS: Events filter by source - count={len(events)}")

    def test_events_filter_by_asset(self, api_client):
        """GET /api/admin/news/events?asset=BTC - Filter by asset"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/events?asset=BTC')
        assert response.status_code == 200
        
        events = response.json()['data']['events']
        
        # All events should mention BTC
        for event in events:
            asset_mentions = event.get('assetMentions', [])
            assert 'BTC' in asset_mentions, \
                f"Event doesn't mention BTC: {asset_mentions}"
        
        print(f"PASS: Events filter by asset - count={len(events)}")

    def test_events_have_required_fields(self, api_client):
        """Verify events have required fields"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/events?limit=5')
        events = response.json()['data']['events']
        
        if len(events) == 0:
            pytest.skip("No events to verify")
        
        for event in events:
            assert 'externalId' in event
            assert 'title' in event
            assert 'sourceType' in event
            assert event['sourceType'] == 'news'
            assert 'publishedAt' in event
        
        print(f"PASS: Events have required fields")


class TestEventsStats:
    """Tests for GET /api/admin/news/events/stats - News event statistics"""

    def test_events_stats_returns_statistics(self, api_client):
        """GET /api/admin/news/events/stats - Returns event statistics"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/events/stats')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data['ok'] is True
        assert 'data' in data
        
        stats = data['data']
        
        # Required fields
        required_fields = ['total', 'byPublisher', 'byAsset', 'timeDistribution', 'latest', 'oldest']
        for field in required_fields:
            assert field in stats, f"Missing stats field: {field}"
        
        print(f"PASS: Events stats - total={stats['total']}")

    def test_events_stats_by_publisher(self, api_client):
        """Verify byPublisher has correct structure"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/events/stats')
        stats = response.json()['data']
        
        by_publisher = stats['byPublisher']
        assert isinstance(by_publisher, dict)
        
        # Should have publisher names as keys and counts as values
        for publisher, count in by_publisher.items():
            assert isinstance(publisher, str)
            assert isinstance(count, int)
            assert count > 0
        
        print(f"PASS: Events stats byPublisher - publishers={list(by_publisher.keys())}")

    def test_events_stats_by_asset(self, api_client):
        """Verify byAsset has correct structure"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/events/stats')
        stats = response.json()['data']
        
        by_asset = stats['byAsset']
        assert isinstance(by_asset, dict)
        
        # Should have asset tickers as keys and counts as values
        for asset, count in by_asset.items():
            assert isinstance(asset, str)
            assert isinstance(count, int)
        
        print(f"PASS: Events stats byAsset - assets={list(by_asset.keys())}")

    def test_events_stats_time_distribution(self, api_client):
        """Verify timeDistribution has correct structure"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/events/stats')
        stats = response.json()['data']
        
        time_dist = stats['timeDistribution']
        assert isinstance(time_dist, list)
        
        for entry in time_dist:
            assert 'hour' in entry
            assert 'count' in entry
        
        print(f"PASS: Events stats timeDistribution - entries={len(time_dist)}")

    def test_events_stats_latest_oldest(self, api_client):
        """Verify latest and oldest have correct structure"""
        response = api_client.get(f'{BASE_URL}/api/admin/news/events/stats')
        stats = response.json()['data']
        
        if stats['latest']:
            assert 'title' in stats['latest']
            assert 'publishedAt' in stats['latest']
        
        if stats['oldest']:
            assert 'title' in stats['oldest']
            assert 'publishedAt' in stats['oldest']
        
        print(f"PASS: Events stats latest/oldest structure")


class TestExistingIngestionEndpoints:
    """Tests to verify existing ingestion endpoints still work"""

    def test_existing_news_run_endpoint(self, api_client):
        """POST /api/admin/ingestion/news/run - Existing endpoint still works"""
        response = api_client.post(
            f'{BASE_URL}/api/admin/ingestion/news/run',
            json={'limit': 10, 'sinceMinutes': 180}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data['ok'] is True
        
        print(f"PASS: Existing /api/admin/ingestion/news/run still works")

    def test_existing_ingestion_health(self, api_client):
        """GET /api/admin/ingestion/health - Existing endpoint still works"""
        response = api_client.get(f'{BASE_URL}/api/admin/ingestion/health')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data['ok'] is True
        
        print(f"PASS: Existing /api/admin/ingestion/health still works")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
