"""
Graph Playback P1 Feature Tests
================================
Tests for the /api/graph-core/playback/events endpoint.
Verifies: flow event aggregation, resolution filters, node_id/seeds filters.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPlaybackEventsEndpoint:
    """Test GET /api/graph-core/playback/events endpoint"""

    def test_playback_events_default(self):
        """Test default playback events (no filters)"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        # Verify required fields
        assert "events" in data, "Response missing 'events' field"
        assert "time_range" in data, "Response missing 'time_range' field"
        assert "total_events" in data, "Response missing 'total_events' field"
        assert "resolution" in data, "Response missing 'resolution' field"
        assert "bucket_seconds" in data, "Response missing 'bucket_seconds' field"
        
        # Verify time_range structure
        assert "start" in data["time_range"]
        assert "end" in data["time_range"]
        
        # Default resolution should be 24h
        assert data["resolution"] == "24h"
        assert data["bucket_seconds"] == 86400  # 24h in seconds

    def test_playback_events_resolution_1h(self):
        """Test 1-hour resolution"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?resolution=1h")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["resolution"] == "1h"
        assert data["bucket_seconds"] == 3600  # 1h in seconds

    def test_playback_events_resolution_7d(self):
        """Test 7-day resolution"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?resolution=7d")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["resolution"] == "7d"
        assert data["bucket_seconds"] == 604800  # 7d in seconds

    def test_playback_events_resolution_30d(self):
        """Test 30-day resolution"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?resolution=30d")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["resolution"] == "30d"
        assert data["bucket_seconds"] == 2592000  # 30d in seconds

    def test_playback_events_max_events_limit(self):
        """Test max_events parameter limits results"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?max_events=5")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["total_events"] <= 5

    def test_playback_events_event_structure(self):
        """Verify each event has correct fields"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?max_events=10")
        assert resp.status_code == 200
        
        data = resp.json()
        if data["total_events"] > 0:
            event = data["events"][0]
            # Verify event structure
            assert "timestamp" in event, "Event missing 'timestamp'"
            assert "source" in event, "Event missing 'source'"
            assert "target" in event, "Event missing 'target'"
            assert "volume_usd" in event, "Event missing 'volume_usd'"
            assert "tx_count" in event, "Event missing 'tx_count'"
            assert "type" in event, "Event missing 'type'"
            assert "edge_key" in event, "Event missing 'edge_key'"
            
            # Verify edge_key format (source->target)
            assert "->" in event["edge_key"], "edge_key should contain '->' separator"

    def test_playback_events_with_seeds(self):
        """Test filtering by seeds parameter"""
        # First get some valid node IDs
        default_resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?max_events=10")
        default_data = default_resp.json()
        
        if default_data["total_events"] > 0:
            # Use a source node as seed
            seed = default_data["events"][0]["source"]
            
            resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?seeds={seed}")
            assert resp.status_code == 200
            
            data = resp.json()
            # If events returned, verify they involve the seed
            for event in data["events"]:
                assert seed in [event["source"], event["target"]], \
                    f"Event does not involve seed {seed}"

    def test_playback_events_with_node_id(self):
        """Test filtering by node_id parameter"""
        # First get some valid node IDs
        default_resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?max_events=10")
        default_data = default_resp.json()
        
        if default_data["total_events"] > 0:
            # Use a source node as node_id filter
            node_id = default_data["events"][0]["source"]
            
            resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?node_id={node_id}")
            assert resp.status_code == 200
            
            data = resp.json()
            # Events should involve the node_id
            for event in data["events"]:
                assert node_id in [event["source"], event["target"]], \
                    f"Event does not involve node_id {node_id}"

    def test_playback_events_sorted_by_timestamp(self):
        """Verify events are sorted by timestamp (ascending)"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?max_events=50")
        assert resp.status_code == 200
        
        data = resp.json()
        if len(data["events"]) > 1:
            timestamps = [e["timestamp"] for e in data["events"]]
            # Events should be sorted ascending by timestamp
            assert timestamps == sorted(timestamps), "Events not sorted by timestamp"

    def test_playback_events_time_range_matches_events(self):
        """Verify time_range matches actual event timestamps"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?max_events=100")
        assert resp.status_code == 200
        
        data = resp.json()
        if data["total_events"] > 0:
            event_timestamps = [e["timestamp"] for e in data["events"]]
            assert data["time_range"]["start"] == min(event_timestamps)
            assert data["time_range"]["end"] == max(event_timestamps)


class TestGraphCoreHealth:
    """Basic health check for graph-core service"""

    def test_health_endpoint(self):
        """Test /api/graph-core/health returns OK"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["status"] == "ok"
        assert "storage" in data


class TestLegacyPlaybackEndpoint:
    """Test the legacy /api/graph-core/playback endpoint for backwards compatibility"""

    def test_legacy_playback_with_node_id(self):
        """Legacy endpoint should still work"""
        # First get a valid node_id
        events_resp = requests.get(f"{BASE_URL}/api/graph-core/playback/events?max_events=5")
        events_data = events_resp.json()
        
        if events_data["total_events"] > 0:
            node_id = events_data["events"][0]["source"]
            
            resp = requests.get(f"{BASE_URL}/api/graph-core/playback?node_id={node_id}")
            assert resp.status_code == 200
            
            data = resp.json()
            # Legacy format includes frames array
            assert "frames" in data or "events" in data, \
                "Legacy playback should return frames or events"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
