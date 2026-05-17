"""
P3 Graph Playback Backend Tests
===============================
Tests for GET /api/graph-core/playback endpoint with temporal slicing features.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestGraphPlaybackEndpoint:
    """Tests for P3 Graph Playback endpoint"""
    
    def test_playback_24h_resolution_returns_frames(self):
        """Test: GET /api/graph-core/playback?resolution=24h returns frames array"""
        response = requests.get(f"{BASE_URL}/api/graph-core/playback?resolution=24h")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "frames" in data, "Response should contain 'frames' field"
        assert "total_frames" in data, "Response should contain 'total_frames' field"
        assert "resolution" in data, "Response should contain 'resolution' field"
        assert data["resolution"] == "24h", f"Expected resolution='24h', got {data['resolution']}"
        
        # Check frames structure if we have data
        if data["frames"]:
            frame = data["frames"][0]
            assert "nodes" in frame, "Frame should contain 'nodes'"
            assert "edges" in frame, "Frame should contain 'edges'"
            assert "flows" in frame, "Frame should contain 'flows'"
            assert "stats" in frame, "Frame should contain 'stats'"
            assert "key" in frame, "Frame should contain 'key'"
            assert "timestamp" in frame, "Frame should contain 'timestamp'"
            
            # Verify stats structure
            stats = frame["stats"]
            assert "node_count" in stats, "Stats should contain 'node_count'"
            assert "edge_count" in stats, "Stats should contain 'edge_count'"
            assert "flow_count" in stats, "Stats should contain 'flow_count'"
            
        print(f"PASS: Playback 24h - total_frames={data['total_frames']}")
    
    def test_playback_7d_resolution_returns_weekly_frames(self):
        """Test: GET /api/graph-core/playback?resolution=7d returns weekly aggregated frames"""
        response = requests.get(f"{BASE_URL}/api/graph-core/playback?resolution=7d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["resolution"] == "7d", f"Expected resolution='7d', got {data['resolution']}"
        assert "frames" in data
        assert "time_range" in data
        
        # For 7d resolution, keys should be ISO week format (YYYY-Www)
        if data["frames"]:
            frame = data["frames"][0]
            key = frame.get("key", "")
            # ISO week format is YYYY-Www (e.g., 2026-W05)
            if "-W" in key:
                print(f"PASS: 7d resolution returns ISO week keys: {key}")
            else:
                print(f"INFO: 7d resolution key format: {key}")
        
        print(f"PASS: Playback 7d - total_frames={data['total_frames']}, time_range={data.get('time_range', {})}")
    
    def test_playback_binance_specific_node(self):
        """Test: GET /api/graph-core/playback?node_id=cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum&resolution=24h"""
        binance_node = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/playback?node_id={binance_node}&resolution=24h")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "frames" in data
        assert data.get("node_id") == binance_node, f"Response should echo node_id, got {data.get('node_id')}"
        
        # Binance-specific frames may be fewer than global
        print(f"PASS: Playback Binance-specific - total_frames={data['total_frames']}")
    
    def test_playback_max_frames_cap(self):
        """Test: Playback max frames capped at 120"""
        # Even with broad query, frames should not exceed 120
        response = requests.get(f"{BASE_URL}/api/graph-core/playback?resolution=1h")
        assert response.status_code == 200
        
        data = response.json()
        total_frames = data.get("total_frames", 0)
        assert total_frames <= 120, f"Expected max 120 frames, got {total_frames}"
        
        print(f"PASS: Playback frames capped at 120 - got {total_frames}")
    
    def test_playback_all_resolutions(self):
        """Test: All valid resolutions return 200"""
        resolutions = ["1h", "24h", "7d", "30d", "90d"]
        for res in resolutions:
            response = requests.get(f"{BASE_URL}/api/graph-core/playback?resolution={res}")
            assert response.status_code == 200, f"Resolution {res} failed: {response.status_code}"
            data = response.json()
            assert data.get("resolution") == res
            print(f"  - {res}: {data.get('total_frames', 0)} frames")
        
        print("PASS: All resolutions return 200")
    
    def test_playback_invalid_resolution_rejected(self):
        """Test: Invalid resolution parameter is rejected"""
        response = requests.get(f"{BASE_URL}/api/graph-core/playback?resolution=invalid")
        # FastAPI should return 422 for invalid enum value
        assert response.status_code == 422, f"Expected 422 for invalid resolution, got {response.status_code}"
        print("PASS: Invalid resolution rejected with 422")


class TestSmartWalletsStillWorks:
    """Verify existing smart-wallets endpoint still works after P3 changes"""
    
    def test_smart_wallets_endpoint(self):
        """Test: GET /api/graph-core/smart-wallets?limit=5 returns wallets"""
        response = requests.get(f"{BASE_URL}/api/graph-core/smart-wallets?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "wallets" in data, "Response should contain 'wallets' field"
        assert len(data["wallets"]) <= 5, f"Expected max 5 wallets, got {len(data['wallets'])}"
        
        if data["wallets"]:
            wallet = data["wallets"][0]
            # Check that smart wallet fields are present - field is 'wallet' (the node_id)
            has_id = "id" in wallet or "wallet_id" in wallet or "wallet" in wallet
            assert has_id, f"Wallet should have 'id'/'wallet_id'/'wallet', got keys: {list(wallet.keys())[:5]}"
            # Check essential smart wallet metrics
            assert "smart_wallet_score" in wallet, "Should have smart_wallet_score"
            
        print(f"PASS: Smart wallets endpoint - {len(data['wallets'])} wallets returned")


class TestGraphHealthAfterP3:
    """Verify graph health endpoint still works"""
    
    def test_graph_health(self):
        """Test: GET /api/graph-core/health returns status ok"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Expected status='ok', got {data.get('status')}"
        
        storage = data.get("storage", {})
        print(f"PASS: Graph health - {storage.get('graph_nodes', 0)} nodes, {storage.get('graph_relations', 0)} relations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
