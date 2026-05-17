"""
Test suite for OnChain Overview V4 - New Blocks (Activity Timeline, Whale Monitor, Liquidity Radar)
=================================================================================================
Tests the 3 new endpoints: /timeline, /whales, /radar
Plus validates existing endpoints for regression testing
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestTimelineEndpoint:
    """Tests for /api/onchain-overview/timeline endpoint"""
    
    def test_timeline_returns_200(self):
        """Timeline endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/timeline?window=7d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Timeline endpoint returns 200")
    
    def test_timeline_response_structure(self):
        """Timeline returns buckets with expected fields"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/timeline?window=7d")
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=true"
        assert "buckets" in data, "Response should have buckets array"
        assert isinstance(data["buckets"], list), "Buckets should be a list"
        assert "bucket_hours" in data, "Response should have bucket_hours"
        assert "window" in data, "Response should have window"
        print(f"PASS: Timeline returns {len(data['buckets'])} buckets")
    
    def test_timeline_bucket_fields(self):
        """Each bucket has required fields: ts, label, transfers, volume_usd, signals, volume_fmt"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/timeline?window=7d")
        data = response.json()
        
        if data.get("buckets"):
            bucket = data["buckets"][0]
            required_fields = ["ts", "label", "transfers", "volume_usd", "signals", "volume_fmt"]
            for field in required_fields:
                assert field in bucket, f"Bucket missing field: {field}"
            
            # Type checks
            assert isinstance(bucket["ts"], int), "ts should be int"
            assert isinstance(bucket["label"], str), "label should be string"
            assert isinstance(bucket["transfers"], int), "transfers should be int"
            assert isinstance(bucket["volume_usd"], (int, float)), "volume_usd should be numeric"
            assert isinstance(bucket["signals"], int), "signals should be int"
            print("PASS: Timeline bucket fields are correct")
    
    def test_timeline_window_24h(self):
        """Timeline with 24h window returns hourly buckets"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/timeline?window=24h")
        data = response.json()
        assert data.get("ok") == True
        assert data.get("bucket_hours") == 1, "24h window should have 1-hour buckets"
        print("PASS: 24h window uses 1-hour buckets")
    
    def test_timeline_window_30d(self):
        """Timeline with 30d window returns daily buckets"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/timeline?window=30d")
        data = response.json()
        assert data.get("ok") == True
        assert data.get("bucket_hours") == 24, "30d window should have 24-hour buckets"
        print("PASS: 30d window uses 24-hour buckets")


class TestWhalesEndpoint:
    """Tests for /api/onchain-overview/whales endpoint"""
    
    def test_whales_returns_200(self):
        """Whales endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/whales?window=30d&limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Whales endpoint returns 200")
    
    def test_whales_response_structure(self):
        """Whales returns top_transactions, whale_wallets, deposits, withdrawals"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/whales?window=30d&limit=10")
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=true"
        required_fields = ["top_transactions", "whale_wallets", "deposits", "withdrawals"]
        for field in required_fields:
            assert field in data, f"Response missing field: {field}"
            assert isinstance(data[field], list), f"{field} should be a list"
        print(f"PASS: Whales returns {len(data['top_transactions'])} transactions, {len(data['whale_wallets'])} wallets")
    
    def test_whales_transaction_fields(self):
        """Each transaction has required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/whales?window=30d&limit=10")
        data = response.json()
        
        if data.get("top_transactions"):
            tx = data["top_transactions"][0]
            required_fields = ["token", "amount_fmt", "usd_value", "usd_fmt", "from_label", "to_label", "chain", "time_ago", "tx_type"]
            for field in required_fields:
                assert field in tx, f"Transaction missing field: {field}"
            assert isinstance(tx["usd_value"], (int, float)), "usd_value should be numeric"
            print("PASS: Transaction fields are correct")
    
    def test_whales_wallet_fields(self):
        """Each whale wallet has required fields including short_addr for UI"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/whales?window=30d&limit=10")
        data = response.json()
        
        if data.get("whale_wallets"):
            wallet = data["whale_wallets"][0]
            required_fields = ["address", "short_addr", "entity", "volume_usd", "volume_fmt", "tx_count", "last_seen"]
            for field in required_fields:
                assert field in wallet, f"Wallet missing field: {field}"
            # Verify short_addr format (e.g., 0xeae7...a4f4)
            assert "..." in wallet["short_addr"], "short_addr should be truncated (e.g., 0xeae7...a4f4)"
            print("PASS: Wallet fields are correct with short_addr")
    
    def test_whales_deposits_withdrawals_fields(self):
        """Deposits and withdrawals have exchange, usd_fmt, count"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/whales?window=30d&limit=10")
        data = response.json()
        
        if data.get("deposits"):
            deposit = data["deposits"][0]
            assert "exchange" in deposit, "Deposit missing exchange field"
            assert "usd_fmt" in deposit, "Deposit missing usd_fmt field"
            assert "count" in deposit, "Deposit missing count field"
            print("PASS: Deposit/withdrawal fields are correct")


class TestRadarEndpoint:
    """Tests for /api/onchain-overview/radar endpoint"""
    
    def test_radar_returns_200(self):
        """Radar endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/radar?window=30d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Radar endpoint returns 200")
    
    def test_radar_response_structure(self):
        """Radar returns by_exchange, by_chain, by_token arrays"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/radar?window=30d")
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=true"
        required_fields = ["by_exchange", "by_chain", "by_token"]
        for field in required_fields:
            assert field in data, f"Response missing field: {field}"
            assert isinstance(data[field], list), f"{field} should be a list"
        print(f"PASS: Radar returns {len(data['by_exchange'])} exchanges, {len(data['by_chain'])} chains, {len(data['by_token'])} tokens")
    
    def test_radar_share_pct_present(self):
        """Each radar item has share_pct for progress bars"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/radar?window=30d")
        data = response.json()
        
        if data.get("by_exchange"):
            item = data["by_exchange"][0]
            assert "share_pct" in item, "Exchange item missing share_pct"
            assert isinstance(item["share_pct"], (int, float)), "share_pct should be numeric"
            assert 0 <= item["share_pct"] <= 100, "share_pct should be 0-100"
        
        if data.get("by_chain"):
            item = data["by_chain"][0]
            assert "share_pct" in item, "Chain item missing share_pct"
        
        if data.get("by_token"):
            item = data["by_token"][0]
            assert "share_pct" in item, "Token item missing share_pct"
        
        print("PASS: All radar items have share_pct")
    
    def test_radar_exchange_fields(self):
        """Exchange items have name, volume_fmt, volume_usd, tx_count, share_pct"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/radar?window=30d")
        data = response.json()
        
        if data.get("by_exchange"):
            item = data["by_exchange"][0]
            required_fields = ["name", "volume_fmt", "volume_usd", "tx_count", "share_pct"]
            for field in required_fields:
                assert field in item, f"Exchange item missing field: {field}"
            print("PASS: Exchange radar items have correct fields")
    
    def test_radar_chain_fields(self):
        """Chain items have chain, volume_fmt, share_pct"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/radar?window=30d")
        data = response.json()
        
        if data.get("by_chain"):
            item = data["by_chain"][0]
            assert "chain" in item, "Chain item missing chain field"
            assert "volume_fmt" in item, "Chain item missing volume_fmt"
            assert "share_pct" in item, "Chain item missing share_pct"
            print("PASS: Chain radar items have correct fields")
    
    def test_radar_token_fields(self):
        """Token items have token, volume_fmt, share_pct"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/radar?window=30d")
        data = response.json()
        
        if data.get("by_token"):
            item = data["by_token"][0]
            assert "token" in item, "Token item missing token field"
            assert "volume_fmt" in item, "Token item missing volume_fmt"
            assert "share_pct" in item, "Token item missing share_pct"
            print("PASS: Token radar items have correct fields")


class TestExistingEndpointsRegression:
    """Regression tests for existing endpoints"""
    
    def test_summary_endpoint(self):
        """Summary endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/summary?window=30d")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "active_wallets" in data
        assert "volume_usd_fmt" in data
        print("PASS: Summary endpoint works")
    
    def test_context_endpoint(self):
        """Context endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/context?window=30d")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "market_bias" in data
        print("PASS: Context endpoint works")
    
    def test_story_endpoint(self):
        """Story endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/story?window=30d")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "sentences" in data
        print("PASS: Story endpoint works")
    
    def test_exchange_flows_endpoint(self):
        """Exchange flows endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/exchange-flows?window=30d")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "flows" in data
        assert "totals" in data
        print("PASS: Exchange flows endpoint works")
    
    def test_smart_money_endpoint(self):
        """Smart money endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/smart-money?window=30d&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "wallets" in data
        print("PASS: Smart money endpoint works")
    
    def test_entities_endpoint(self):
        """Entities endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/entities?window=30d&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "entities" in data
        print("PASS: Entities endpoint works")
    
    def test_clusters_endpoint(self):
        """Clusters endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/clusters?window=30d&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "clusters" in data
        print("PASS: Clusters endpoint works")
    
    def test_signals_endpoint(self):
        """Signals endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/signals?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "signals" in data
        print("PASS: Signals endpoint works")
    
    def test_transfers_endpoint(self):
        """Transfers endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/transfers?window=30d&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "transfers" in data
        print("PASS: Transfers endpoint works")


class TestWindowParameter:
    """Test window parameter across all endpoints"""
    
    @pytest.mark.parametrize("endpoint", [
        "summary", "context", "story", "exchange-flows", "smart-money",
        "entities", "token-flows", "clusters", "transfers", "timeline", "whales", "radar"
    ])
    def test_window_24h(self, endpoint):
        """All endpoints accept window=24h"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/{endpoint}?window=24h")
        assert response.status_code == 200, f"{endpoint} failed with 24h window"
    
    @pytest.mark.parametrize("endpoint", [
        "summary", "context", "story", "exchange-flows", "smart-money",
        "entities", "token-flows", "clusters", "transfers", "timeline", "whales", "radar"
    ])
    def test_window_7d(self, endpoint):
        """All endpoints accept window=7d"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/{endpoint}?window=7d")
        assert response.status_code == 200, f"{endpoint} failed with 7d window"
    
    @pytest.mark.parametrize("endpoint", [
        "summary", "context", "story", "exchange-flows", "smart-money",
        "entities", "token-flows", "clusters", "transfers", "timeline", "whales", "radar"
    ])
    def test_window_30d(self, endpoint):
        """All endpoints accept window=30d"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/{endpoint}?window=30d")
        assert response.status_code == 200, f"{endpoint} failed with 30d window"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
