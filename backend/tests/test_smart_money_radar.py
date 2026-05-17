"""
Smart Money Radar API Tests
============================
Sprint 1.2: Tests for GET /api/onchain/smart-money/radar endpoint
Tests radar events with sort, window, and limit parameters
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://expo-telegram-web.preview.emergentagent.com").rstrip("/")


class TestSmartMoneyRadarAPI:
    """Tests for Smart Money Radar endpoint"""

    # --- Basic endpoint tests ---
    def test_radar_basic_request(self):
        """Test basic radar endpoint returns ok=true with events"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "events" in data
        assert isinstance(data["events"], list)
        assert "meta" in data

    def test_radar_meta_fields(self):
        """Test meta fields are returned correctly"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h")
        assert response.status_code == 200
        data = response.json()
        meta = data.get("meta", {})
        assert meta.get("chainId") == 1
        assert meta.get("window") == "24h"
        assert "sort" in meta
        assert "count" in meta

    # --- Window parameter tests ---
    def test_radar_window_24h(self):
        """Test 24h window parameter"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data["meta"]["window"] == "24h"

    def test_radar_window_7d(self):
        """Test 7d window parameter"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=7d")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data["meta"]["window"] == "7d"

    def test_radar_window_30d(self):
        """Test 30d window parameter"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=30d")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data["meta"]["window"] == "30d"

    # --- Sort parameter tests ---
    def test_radar_sort_confidence(self):
        """Test sort=confidence parameter"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&sort=confidence")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data["meta"]["sort"] == "confidence"
        # Verify descending order by confidence
        events = data.get("events", [])
        if len(events) >= 2:
            assert events[0]["confidence"] >= events[1]["confidence"]

    def test_radar_sort_net_flow(self):
        """Test sort=net_flow parameter"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&sort=net_flow")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data["meta"]["sort"] == "net_flow"
        # Verify sorted by abs(net_flow) descending
        events = data.get("events", [])
        if len(events) >= 2:
            assert abs(events[0]["net_flow_usd"]) >= abs(events[1]["net_flow_usd"])

    def test_radar_sort_recency(self):
        """Test sort=recency parameter"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&sort=recency")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data["meta"]["sort"] == "recency"

    # --- Event structure tests ---
    def test_radar_event_structure(self):
        """Test radar event has all required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        if len(events) > 0:
            event = events[0]
            # Required fields
            assert "event_type" in event
            assert "entity" in event
            assert "entity_type" in event
            assert "net_flow_usd" in event
            assert "confidence" in event
            assert "timing_score" in event
            assert "last_activity" in event
            assert "reason" in event
            assert "trades" in event

    def test_radar_event_types(self):
        """Test that event_type values are valid"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        valid_types = {"early_accumulation", "early_distribution", "smart_wallet_detected", "cluster_activity"}
        for event in events:
            assert event["event_type"] in valid_types, f"Invalid event_type: {event['event_type']}"

    def test_radar_confidence_range(self):
        """Test confidence values are in valid range (0-100)"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        for event in events:
            assert 0 <= event["confidence"] <= 100, f"Confidence out of range: {event['confidence']}"

    def test_radar_timing_score_range(self):
        """Test timing_score values are in valid range (-10 to +15)"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        for event in events:
            assert -10 <= event["timing_score"] <= 15, f"Timing score out of range: {event['timing_score']}"

    def test_radar_reason_is_list(self):
        """Test reason field is a list of strings"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        for event in events:
            assert isinstance(event["reason"], list)
            for reason in event["reason"]:
                assert isinstance(reason, str)

    # --- Limit parameter tests ---
    def test_radar_limit_parameter(self):
        """Test limit parameter restricts event count"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&limit=5")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        assert len(events) <= 5

    # --- Cluster events tests ---
    def test_radar_cluster_activity_fields(self):
        """Test cluster_activity events have cluster_wallets field"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        cluster_events = [e for e in events if e["event_type"] == "cluster_activity"]
        for event in cluster_events:
            assert "cluster_wallets" in event
            assert event["cluster_wallets"] >= 3  # Minimum cluster size


class TestExistingSmartMoneyAPIs:
    """Tests for existing Smart Money APIs (Market Pressure, Buying/Selling)"""

    def test_actors_accumulation_list(self):
        """Test accumulation actors endpoint"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/market/actors/list?chainId=1&window=24h&direction=accumulation&limit=20")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data

    def test_actors_distribution_list(self):
        """Test distribution actors endpoint"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/market/actors/list?chainId=1&window=24h&direction=distribution&limit=20")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
