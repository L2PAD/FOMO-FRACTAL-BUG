"""
Event Feed MVP Tests

Tests for the Real Event Feed MVP:
- GET /api/event-feed — main curated feed with query params
- GET /api/event-feed/asset/:asset — feed filtered by asset
- GET /api/event-feed/stats — feed statistics
- GET /api/event-feed/sources — source registry
- POST /api/event-feed/related — related events for entities
- GET /api/prediction/run — full pipeline with event feed integration

Validates:
- Cluster structure (clusterId, canonicalTitle, eventType, primaryAsset, assets, entities, etc.)
- Deduplication (totalRawEvents > totalClusters, compression ratio > 1)
- Priority bands (critical >= 0.80, high >= 0.60, medium >= 0.40, low < 0.40)
- Source tiers (tier1 = 6, tier2 = 9, tier3 = 10)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEventFeedHealth:
    """Basic health checks for Event Feed endpoints"""

    def test_event_feed_endpoint_accessible(self):
        """Test that /api/event-feed endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/event-feed", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"

    def test_event_feed_stats_accessible(self):
        """Test that /api/event-feed/stats endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/event-feed/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"

    def test_event_feed_sources_accessible(self):
        """Test that /api/event-feed/sources endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/event-feed/sources", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"


class TestEventFeedMain:
    """Tests for GET /api/event-feed — main curated feed"""

    def test_feed_returns_clusters_and_meta(self):
        """Test that feed returns clusters array and meta object"""
        response = requests.get(f"{BASE_URL}/api/event-feed", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "clusters" in data, "Response should contain 'clusters'"
        assert "meta" in data, "Response should contain 'meta'"
        assert isinstance(data["clusters"], list), "clusters should be a list"
        assert isinstance(data["meta"], dict), "meta should be a dict"

    def test_feed_meta_fields(self):
        """Test that meta contains required fields"""
        response = requests.get(f"{BASE_URL}/api/event-feed", timeout=30)
        data = response.json()
        meta = data.get("meta", {})
        
        required_fields = [
            "totalRawEvents", "totalNormalized", "totalClusters",
            "criticalCount", "highCount", "mediumCount", "lowCount",
            "timeRangeHours", "compressionRatio", "generatedAt"
        ]
        for field in required_fields:
            assert field in meta, f"meta should contain '{field}'"

    def test_feed_cluster_structure(self):
        """Test that clusters have correct fields"""
        response = requests.get(f"{BASE_URL}/api/event-feed", timeout=30)
        data = response.json()
        clusters = data.get("clusters", [])
        
        if len(clusters) > 0:
            cluster = clusters[0]
            required_fields = [
                "clusterId", "canonicalTitle", "eventType", "primaryAsset",
                "assets", "entities", "sentimentHint", "sourcesCount",
                "priority", "priorityBand", "relevanceScore"
            ]
            for field in required_fields:
                assert field in cluster, f"cluster should contain '{field}'"
            
            # Validate types
            assert isinstance(cluster["clusterId"], str), "clusterId should be string"
            assert isinstance(cluster["canonicalTitle"], str), "canonicalTitle should be string"
            assert isinstance(cluster["assets"], list), "assets should be list"
            assert isinstance(cluster["entities"], list), "entities should be list"
            assert isinstance(cluster["priority"], (int, float)), "priority should be number"
            assert cluster["priorityBand"] in ["critical", "high", "medium", "low"], \
                f"priorityBand should be one of critical/high/medium/low, got {cluster['priorityBand']}"

    def test_feed_query_params_hours_back(self):
        """Test hoursBack query parameter"""
        response = requests.get(f"{BASE_URL}/api/event-feed?hoursBack=48", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["timeRangeHours"] == 48, "timeRangeHours should match hoursBack param"

    def test_feed_query_params_limit(self):
        """Test limit query parameter"""
        response = requests.get(f"{BASE_URL}/api/event-feed?limit=5", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert len(data["clusters"]) <= 5, "clusters count should not exceed limit"

    def test_feed_query_params_priority_band(self):
        """Test priorityBand query parameter"""
        response = requests.get(f"{BASE_URL}/api/event-feed?priorityBand=high", timeout=30)
        assert response.status_code == 200
        data = response.json()
        for cluster in data.get("clusters", []):
            assert cluster["priorityBand"] == "high", \
                f"All clusters should have priorityBand=high, got {cluster['priorityBand']}"

    def test_feed_query_params_min_priority(self):
        """Test minPriority query parameter"""
        response = requests.get(f"{BASE_URL}/api/event-feed?minPriority=0.5", timeout=30)
        assert response.status_code == 200
        data = response.json()
        for cluster in data.get("clusters", []):
            assert cluster["priority"] >= 0.5, \
                f"All clusters should have priority >= 0.5, got {cluster['priority']}"


class TestEventFeedAsset:
    """Tests for GET /api/event-feed/asset/:asset — feed filtered by asset"""

    def test_asset_feed_btc(self):
        """Test feed for BTC asset"""
        response = requests.get(f"{BASE_URL}/api/event-feed/asset/BTC", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("asset") == "BTC"
        assert "clusters" in data
        assert "count" in data
        assert isinstance(data["clusters"], list)

    def test_asset_feed_eth(self):
        """Test feed for ETH asset"""
        response = requests.get(f"{BASE_URL}/api/event-feed/asset/ETH", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("asset") == "ETH"

    def test_asset_feed_sol(self):
        """Test feed for SOL asset"""
        response = requests.get(f"{BASE_URL}/api/event-feed/asset/SOL", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("asset") == "SOL"

    def test_asset_feed_with_hours_back(self):
        """Test asset feed with hoursBack parameter"""
        response = requests.get(f"{BASE_URL}/api/event-feed/asset/BTC?hoursBack=72", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True


class TestEventFeedStats:
    """Tests for GET /api/event-feed/stats — feed statistics"""

    def test_stats_structure(self):
        """Test stats endpoint returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/event-feed/stats", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "sources" in data, "stats should contain 'sources'"
        assert "feed" in data, "stats should contain 'feed'"
        assert "topClusters" in data, "stats should contain 'topClusters'"

    def test_stats_sources_counts(self):
        """Test stats sources counts"""
        response = requests.get(f"{BASE_URL}/api/event-feed/stats", timeout=30)
        data = response.json()
        sources = data.get("sources", {})
        
        assert "tier1" in sources
        assert "tier2" in sources
        assert "tier3" in sources
        assert "total" in sources
        
        # Verify tier counts match expected (6 tier1, 9 tier2, 10 tier3 = 25 total)
        assert sources["tier1"] == 6, f"Expected 6 tier1 sources, got {sources['tier1']}"
        assert sources["tier2"] == 9, f"Expected 9 tier2 sources, got {sources['tier2']}"
        assert sources["tier3"] == 10, f"Expected 10 tier3 sources, got {sources['tier3']}"
        assert sources["total"] == 25, f"Expected 25 total sources, got {sources['total']}"

    def test_stats_feed_counts(self):
        """Test stats feed counts"""
        response = requests.get(f"{BASE_URL}/api/event-feed/stats", timeout=30)
        data = response.json()
        feed = data.get("feed", {})
        
        assert "totalRaw" in feed
        assert "totalClusters" in feed
        assert "breaking" in feed
        assert "critical" in feed
        assert "high" in feed

    def test_stats_top_clusters(self):
        """Test stats topClusters structure"""
        response = requests.get(f"{BASE_URL}/api/event-feed/stats", timeout=30)
        data = response.json()
        top_clusters = data.get("topClusters", [])
        
        assert isinstance(top_clusters, list)
        if len(top_clusters) > 0:
            cluster = top_clusters[0]
            assert "title" in cluster
            assert "priority" in cluster
            assert "band" in cluster
            assert "sources" in cluster
            assert "assets" in cluster


class TestEventFeedSources:
    """Tests for GET /api/event-feed/sources — source registry"""

    def test_sources_structure(self):
        """Test sources endpoint returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/event-feed/sources", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "sources" in data
        assert "summary" in data
        assert isinstance(data["sources"], list)

    def test_sources_count(self):
        """Test that we have 25 sources (6 tier1 + 9 tier2 + 10 tier3)"""
        response = requests.get(f"{BASE_URL}/api/event-feed/sources", timeout=30)
        data = response.json()
        
        sources = data.get("sources", [])
        summary = data.get("summary", {})
        
        assert len(sources) == 25, f"Expected 25 sources, got {len(sources)}"
        assert summary.get("total") == 25
        assert summary.get("tier1") == 6
        assert summary.get("tier2") == 9
        assert summary.get("tier3") == 10

    def test_sources_tier1_list(self):
        """Test tier 1 sources (SEC, CFTC, Fed, Treasury, White House)"""
        response = requests.get(f"{BASE_URL}/api/event-feed/sources", timeout=30)
        data = response.json()
        sources = data.get("sources", [])
        
        tier1_sources = [s for s in sources if s.get("tier") == 1]
        tier1_names = {s.get("name") for s in tier1_sources}
        
        expected_tier1 = {"SEC EDGAR", "SEC Press", "CFTC", "Fed Minutes", "US Treasury", "White House"}
        assert tier1_names == expected_tier1, f"Expected tier1 sources {expected_tier1}, got {tier1_names}"

    def test_sources_tier2_list(self):
        """Test tier 2 sources (news outlets)"""
        response = requests.get(f"{BASE_URL}/api/event-feed/sources", timeout=30)
        data = response.json()
        sources = data.get("sources", [])
        
        tier2_sources = [s for s in sources if s.get("tier") == 2]
        assert len(tier2_sources) == 9, f"Expected 9 tier2 sources, got {len(tier2_sources)}"
        
        tier2_names = {s.get("name") for s in tier2_sources}
        expected_tier2 = {
            "CoinDesk", "The Block", "Blockworks", "Bloomberg Crypto",
            "Reuters Crypto", "CoinTelegraph", "The Defiant", "DL News", "Decrypt"
        }
        assert tier2_names == expected_tier2, f"Expected tier2 sources {expected_tier2}, got {tier2_names}"

    def test_sources_tier3_list(self):
        """Test tier 3 sources (Twitter accounts)"""
        response = requests.get(f"{BASE_URL}/api/event-feed/sources", timeout=30)
        data = response.json()
        sources = data.get("sources", [])
        
        tier3_sources = [s for s in sources if s.get("tier") == 3]
        assert len(tier3_sources) == 10, f"Expected 10 tier3 sources, got {len(tier3_sources)}"

    def test_source_structure(self):
        """Test individual source structure"""
        response = requests.get(f"{BASE_URL}/api/event-feed/sources", timeout=30)
        data = response.json()
        sources = data.get("sources", [])
        
        if len(sources) > 0:
            source = sources[0]
            required_fields = ["id", "name", "tier", "type", "trustScore", "enabled"]
            for field in required_fields:
                assert field in source, f"source should contain '{field}'"
            
            assert source["tier"] in [1, 2, 3], f"tier should be 1, 2, or 3"
            assert source["type"] in ["official", "news", "twitter", "onchain", "regulatory"]
            assert 0 <= source["trustScore"] <= 1, "trustScore should be between 0 and 1"


class TestEventFeedRelated:
    """Tests for POST /api/event-feed/related — related events for entities"""

    def test_related_events_basic(self):
        """Test related events endpoint with basic request"""
        payload = {
            "entities": ["BTC", "Bitcoin"],
            "eventType": "price",
            "hoursBack": 48
        }
        response = requests.post(
            f"{BASE_URL}/api/event-feed/related",
            json=payload,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "events" in data
        assert "count" in data
        assert isinstance(data["events"], list)

    def test_related_events_empty_entities(self):
        """Test related events with empty entities returns empty list"""
        payload = {
            "entities": [],
            "eventType": "etf"
        }
        response = requests.post(
            f"{BASE_URL}/api/event-feed/related",
            json=payload,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("events") == []

    def test_related_events_structure(self):
        """Test related events response structure"""
        payload = {
            "entities": ["SEC", "ETF"],
            "eventType": "etf",
            "hoursBack": 72
        }
        response = requests.post(
            f"{BASE_URL}/api/event-feed/related",
            json=payload,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        events = data.get("events", [])
        if len(events) > 0:
            event = events[0]
            # Check legacy format fields for Python adapter
            expected_fields = ["title", "text", "source", "source_type", "source_quality", "relevance_score"]
            for field in expected_fields:
                assert field in event, f"event should contain '{field}'"


class TestPriorityBands:
    """Tests for priority band thresholds"""

    def test_priority_band_thresholds(self):
        """Test that priority bands follow correct thresholds"""
        response = requests.get(f"{BASE_URL}/api/event-feed?limit=50", timeout=30)
        data = response.json()
        clusters = data.get("clusters", [])
        
        for cluster in clusters:
            priority = cluster["priority"]
            band = cluster["priorityBand"]
            
            if band == "critical":
                assert priority >= 0.80, f"critical band should have priority >= 0.80, got {priority}"
            elif band == "high":
                assert 0.60 <= priority < 0.80, f"high band should have 0.60 <= priority < 0.80, got {priority}"
            elif band == "medium":
                assert 0.40 <= priority < 0.60, f"medium band should have 0.40 <= priority < 0.60, got {priority}"
            elif band == "low":
                assert priority < 0.40, f"low band should have priority < 0.40, got {priority}"


class TestDeduplication:
    """Tests for deduplication and compression"""

    def test_compression_ratio(self):
        """Test that compression ratio is calculated correctly"""
        response = requests.get(f"{BASE_URL}/api/event-feed", timeout=30)
        data = response.json()
        meta = data.get("meta", {})
        
        total_raw = meta.get("totalRawEvents", 0)
        total_clusters = meta.get("totalClusters", 0)
        compression_ratio = meta.get("compressionRatio", 1)
        
        if total_raw > 0 and total_clusters > 0:
            expected_ratio = round(total_raw / total_clusters, 1)
            assert compression_ratio == expected_ratio, \
                f"compressionRatio should be {expected_ratio}, got {compression_ratio}"

    def test_deduplication_works(self):
        """Test that deduplication reduces event count"""
        response = requests.get(f"{BASE_URL}/api/event-feed?hoursBack=48", timeout=30)
        data = response.json()
        meta = data.get("meta", {})
        
        total_raw = meta.get("totalRawEvents", 0)
        total_clusters = meta.get("totalClusters", 0)
        
        # If we have raw events, clusters should be <= raw events
        if total_raw > 0:
            assert total_clusters <= total_raw, \
                f"totalClusters ({total_clusters}) should be <= totalRawEvents ({total_raw})"


class TestPredictionPipelineIntegration:
    """Tests for /api/prediction/run integration with event feed"""

    def test_prediction_run_works(self):
        """Test that prediction pipeline still works with event feed"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=10", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") is True

    def test_prediction_run_structure(self):
        """Test prediction run response structure"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=5", timeout=60)
        data = response.json()
        
        assert "total_markets" in data
        assert "classified" in data
        assert "sections" in data
        
        sections = data.get("sections", {})
        expected_sections = [
            "best_opportunities", "emerging_opportunities", "entry_windows_open",
            "new_mispricings", "repricing_now", "watchlist", "late_moves",
            "avoid_zone", "state_changes"
        ]
        for section in expected_sections:
            assert section in sections, f"sections should contain '{section}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
