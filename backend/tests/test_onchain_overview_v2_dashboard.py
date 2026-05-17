"""
On-Chain Overview Dashboard v2 API Tests
==========================================
Tests all 8 endpoints with USD values, time filters, human labels.

Endpoints tested:
- GET /api/onchain-overview/summary?window=24h|7d|30d
- GET /api/onchain-overview/entities
- GET /api/onchain-overview/exchange-flows
- GET /api/onchain-overview/smart-money
- GET /api/onchain-overview/token-flows
- GET /api/onchain-overview/clusters
- GET /api/onchain-overview/transfers (NEW)
- GET /api/onchain-overview/signals
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestOnchainOverviewSummary:
    """Summary endpoint - time filter & USD volume"""

    def test_summary_30d_returns_usd_volume(self):
        """GET /api/onchain-overview/summary?window=30d returns USD volume"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/summary?window=30d")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "volume_usd" in data
        assert "volume_usd_fmt" in data
        # USD format check - should start with $ 
        assert data["volume_usd_fmt"].startswith("$")
        assert data["window"] == "30d"
        # Must have all summary fields
        assert "active_wallets" in data
        assert "clusters_detected" in data
        assert "smart_money_wallets" in data
        assert "large_transfers" in data
        print(f"PASS: Summary 30d - Volume: {data['volume_usd_fmt']}")

    def test_summary_24h_filter_works(self):
        """GET /api/onchain-overview/summary?window=24h uses 24h filter"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/summary?window=24h")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["window"] == "24h"
        assert "volume_usd_fmt" in data
        print(f"PASS: Summary 24h filter works - Volume: {data['volume_usd_fmt']}")

    def test_summary_7d_filter_works(self):
        """GET /api/onchain-overview/summary?window=7d uses 7d filter"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/summary?window=7d")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["window"] == "7d"
        print(f"PASS: Summary 7d filter works")


class TestOnchainOverviewExchangeFlows:
    """Exchange flows endpoint - USD inflow/outflow/net"""

    def test_exchange_flows_usd_format(self):
        """GET /api/onchain-overview/exchange-flows returns USD values"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/exchange-flows?window=30d")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "flows" in data
        assert "totals" in data
        
        # Check totals have USD format
        totals = data["totals"]
        assert "inflow_fmt" in totals
        assert "outflow_fmt" in totals
        assert "net_fmt" in totals
        assert totals["inflow_fmt"].startswith("$") or totals["inflow_fmt"] == "$0"
        assert totals["outflow_fmt"].startswith("$") or totals["outflow_fmt"] == "$0"
        
        # Check individual flow format
        if data["flows"]:
            flow = data["flows"][0]
            assert "entity" in flow
            assert "inflow_fmt" in flow
            assert "outflow_fmt" in flow
            assert "net_fmt" in flow
            print(f"PASS: Exchange flows USD - {flow['entity']}: in={flow['inflow_fmt']}, out={flow['outflow_fmt']}, net={flow['net_fmt']}")
        else:
            print("PASS: Exchange flows endpoint works (no data)")


class TestOnchainOverviewSmartMoney:
    """Smart money endpoint - human labels, volume, activity"""

    def test_smart_money_human_labels(self):
        """GET /api/onchain-overview/smart-money returns human labels (not 'Auto-discovered')"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/smart-money?window=30d")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "wallets" in data
        
        if data["wallets"]:
            wallet = data["wallets"][0]
            # Must have human-readable label
            assert "label" in wallet
            # Label should NOT be 'Auto-discovered' - should be human readable
            assert wallet["label"] != "Auto-discovered", "Label should be human-readable, not 'Auto-discovered'"
            # Valid labels: Multi-Exchange, Smart Money Wallet, Whale, Bridge, Fund Wallet, Protocol, Exchange Wallet
            valid_labels = ["Multi-Exchange", "Smart Money Wallet", "Whale", "Bridge", "Fund Wallet", "Protocol", "Exchange Wallet", "Wallet"]
            assert any(vl in wallet["label"] for vl in valid_labels), f"Label '{wallet['label']}' not in valid labels"
            
            # Must have volume in USD format
            assert "volume_fmt" in wallet
            assert "volume_usd" in wallet
            
            # Must have last_activity relative time
            assert "last_activity" in wallet
            
            print(f"PASS: Smart money labels - {wallet['label']}, volume: {wallet['volume_fmt']}, last: {wallet['last_activity']}")
        else:
            print("PASS: Smart money endpoint works (no data)")


class TestOnchainOverviewTokenFlows:
    """Token flows endpoint - USD volume aggregation"""

    def test_token_flows_usd_volume(self):
        """GET /api/onchain-overview/token-flows returns tokens sorted by USD volume"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/token-flows?window=30d")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "tokens" in data
        
        if data["tokens"]:
            token = data["tokens"][0]
            assert "token" in token
            assert "volume_usd" in token
            assert "volume_fmt" in token
            assert "transfer_count" in token
            
            # Check sorted by volume (first should be highest)
            if len(data["tokens"]) > 1:
                assert data["tokens"][0]["volume_usd"] >= data["tokens"][1]["volume_usd"], "Tokens should be sorted by volume DESC"
            
            print(f"PASS: Token flows USD - {token['token']}: {token['volume_fmt']}, {token['transfer_count']} tx")
        else:
            print("PASS: Token flows endpoint works (no data)")


class TestOnchainOverviewEntities:
    """Entities endpoint - USD volume"""

    def test_entities_usd_volume(self):
        """GET /api/onchain-overview/entities returns entities with USD volume"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/entities?window=30d")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "entities" in data
        
        if data["entities"]:
            entity = data["entities"][0]
            assert "entity" in entity
            assert "volume_usd" in entity
            assert "volume_usd_fmt" in entity
            assert "tx_count" in entity
            assert "entity_type" in entity
            
            # USD format
            assert entity["volume_usd_fmt"].startswith("$") or entity["volume_usd_fmt"] == "$0"
            
            print(f"PASS: Entities USD - {entity['entity']}: {entity['volume_usd_fmt']}, {entity['tx_count']} tx")
        else:
            print("PASS: Entities endpoint works (no data)")


class TestOnchainOverviewClusters:
    """Clusters endpoint - USD volume"""

    def test_clusters_usd_volume(self):
        """GET /api/onchain-overview/clusters returns clusters with USD volume"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/clusters?window=30d")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "clusters" in data
        
        if data["clusters"]:
            cluster = data["clusters"][0]
            assert "cluster_id" in cluster
            assert "cluster_type" in cluster
            assert "volume_usd" in cluster
            assert "volume_fmt" in cluster
            assert "wallet_count" in cluster
            
            # USD format
            assert cluster["volume_fmt"].startswith("$") or cluster["volume_fmt"] == "$0"
            
            print(f"PASS: Clusters USD - {cluster['cluster_id']}: {cluster['volume_fmt']}, {cluster['wallet_count']} wallets")
        else:
            print("PASS: Clusters endpoint works (no data)")


class TestOnchainOverviewTransfers:
    """Large transfers endpoint (NEW) - USD, labels, time_ago"""

    def test_transfers_endpoint_exists(self):
        """GET /api/onchain-overview/transfers returns large transfers"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/transfers?window=30d")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "transfers" in data
        
        if data["transfers"]:
            transfer = data["transfers"][0]
            # Required fields
            assert "token" in transfer
            assert "usd_value" in transfer
            assert "usd_fmt" in transfer
            assert "from_label" in transfer
            assert "to_label" in transfer
            assert "time_ago" in transfer
            assert "tx_type" in transfer
            
            # USD format
            assert transfer["usd_fmt"].startswith("$") or transfer["usd_fmt"] == "$0"
            
            # time_ago format (e.g., "7h ago", "2d ago")
            assert "ago" in transfer["time_ago"]
            
            # Labels should be human-readable (not addresses)
            # They can be "Unknown" or entity names like "Binance", "Coinbase"
            assert transfer["from_label"] != "", "from_label should not be empty"
            assert transfer["to_label"] != "", "to_label should not be empty"
            
            print(f"PASS: Transfers - {transfer['token']} {transfer['usd_fmt']}: {transfer['from_label']} -> {transfer['to_label']}, {transfer['time_ago']}")
        else:
            print("PASS: Transfers endpoint works (no data)")


class TestOnchainOverviewSignals:
    """Signals endpoint - human-readable titles"""

    def test_signals_human_readable_titles(self):
        """GET /api/onchain-overview/signals returns human-readable titles"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/signals?limit=20")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "signals" in data
        
        if data["signals"]:
            signal = data["signals"][0]
            # Must have human-readable title and description
            assert "title" in signal
            assert "description" in signal
            assert "signal_type" in signal
            assert "score" in signal
            assert "severity" in signal
            
            # Title should NOT be raw signal_type like "CLUSTER_ACTIVITY"
            # It should be human-readable like "Fund Cluster Activity"
            # Check it's not just uppercase with underscores
            assert " " in signal["title"] or signal["title"].istitle(), f"Title '{signal['title']}' should be human-readable"
            
            print(f"PASS: Signals - Title: '{signal['title']}', Desc: '{signal['description'][:50]}...', Score: {signal['score']}")
        else:
            print("PASS: Signals endpoint works (no data)")


class TestTimeFilterConsistency:
    """Verify time filter works across all endpoints"""

    def test_24h_filter_across_endpoints(self):
        """24h filter should return consistent data across endpoints"""
        endpoints = [
            "/api/onchain-overview/summary",
            "/api/onchain-overview/entities",
            "/api/onchain-overview/exchange-flows",
            "/api/onchain-overview/smart-money",
            "/api/onchain-overview/token-flows",
            "/api/onchain-overview/clusters",
            "/api/onchain-overview/transfers",
        ]
        
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}?window=24h")
            assert response.status_code == 200, f"Endpoint {endpoint} failed with 24h filter"
            data = response.json()
            assert data["ok"] is True, f"Endpoint {endpoint} returned ok=false with 24h filter"
        
        print("PASS: All endpoints support 24h filter")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
