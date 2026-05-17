"""
On-Chain Overview Dashboard v3 API Tests
==========================================
Tests all 10 endpoints with v3 features:
- /context (market_bias, liquidity_direction, exchange_pressure, smart_money_activity, cluster_activity)
- /story (sentences array with human-readable narrative)
- /summary (volume_usd_fmt, transfers_count)
- /exchange-flows (USD flows: inflow_fmt/outflow_fmt/net_fmt)
- /transfers (large transfers: usd_fmt, to_label, time_ago)
- /smart-money (wallets with label: Smart Money Wallet, Multi-Exchange, Whale)
- /entities (entities with volume_usd_fmt)
- /token-flows (tokens with volume_fmt in USD)
- /clusters (clusters with wallets array for expand)
- /signals (human-readable title field)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestContextEndpoint:
    """Market Context API - new endpoint for v3"""

    def test_context_returns_5_status_indicators(self):
        """GET /api/onchain-overview/context returns 5 key status indicators"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/context?window=30d")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True

        # Verify 5 required status indicators exist
        assert "market_bias" in data
        assert "liquidity_direction" in data
        assert "exchange_pressure" in data
        assert "smart_money_activity" in data
        assert "cluster_activity" in data

        # Verify metrics structure
        assert "metrics" in data
        metrics = data["metrics"]
        assert "net_flow_usd" in metrics
        assert "net_flow_fmt" in metrics
        assert "active_clusters" in metrics
        assert "high_score_wallets" in metrics

        print(f"Market Context: bias={data['market_bias']}, liquidity={data['liquidity_direction']}")

    def test_context_with_time_filters(self):
        """Context endpoint respects time window filter"""
        for window in ['24h', '7d', '30d']:
            response = requests.get(f"{BASE_URL}/api/onchain-overview/context?window={window}")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "market_bias" in data


class TestStoryEndpoint:
    """Market Story API - narrative generation"""

    def test_story_returns_sentences_array(self):
        """GET /api/onchain-overview/story returns sentences array"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/story?window=30d")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert "sentences" in data
        assert isinstance(data["sentences"], list)
        assert len(data["sentences"]) > 0

        # Verify story field exists
        assert "story" in data
        assert isinstance(data["story"], str)
        assert len(data["story"]) > 0

        print(f"Story has {len(data['sentences'])} sentences")

    def test_story_contains_human_readable_narrative(self):
        """Story sentences should be human-readable"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/story?window=30d")
        data = response.json()

        # Check sentences have actual content
        for sentence in data["sentences"]:
            assert len(sentence) > 10  # At least a short sentence
            # Should contain some financial terms
            assert any(term in sentence.lower() for term in ['market', 'exchange', 'flow', 'wallet', 'cluster', 'smart', 'transfer', 'pressure', 'accumulation', 'posture'])

        print(f"First sentence: {data['sentences'][0]}")


class TestSummaryEndpoint:
    """Network Overview Summary API"""

    def test_summary_returns_volume_usd_fmt(self):
        """GET /api/onchain-overview/summary returns volume_usd_fmt and transfers_count"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/summary?window=30d")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True

        # Required fields
        assert "volume_usd_fmt" in data
        assert "transfers_count" in data
        assert "active_wallets" in data
        assert "clusters_detected" in data
        assert "smart_money_wallets" in data

        # volume_usd_fmt should be formatted string like "$27.3M"
        assert data["volume_usd_fmt"].startswith("$")

        print(f"Summary: volume={data['volume_usd_fmt']}, transfers={data['transfers_count']}")


class TestExchangeFlowsEndpoint:
    """Exchange Flows API - USD formatted flows"""

    def test_exchange_flows_returns_usd_formatted(self):
        """GET /api/onchain-overview/exchange-flows returns USD with inflow_fmt/outflow_fmt/net_fmt"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/exchange-flows?window=30d")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert "flows" in data
        assert "totals" in data

        # Check totals have formatted fields
        totals = data["totals"]
        assert "inflow_fmt" in totals
        assert "outflow_fmt" in totals
        assert "net_fmt" in totals
        assert totals["inflow_fmt"].startswith("$")

        # Check individual flows
        if data["flows"]:
            flow = data["flows"][0]
            assert "inflow_fmt" in flow
            assert "outflow_fmt" in flow
            assert "net_fmt" in flow
            assert "entity" in flow

        print(f"Exchange Flows: inflow={totals['inflow_fmt']}, outflow={totals['outflow_fmt']}, net={totals['net_fmt']}")


class TestTransfersEndpoint:
    """Large Transfers API - new detailed transfer info"""

    def test_transfers_returns_usd_fmt_and_labels(self):
        """GET /api/onchain-overview/transfers returns usd_fmt, to_label, time_ago"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/transfers?window=30d&limit=5")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert "transfers" in data

        if data["transfers"]:
            t = data["transfers"][0]
            # Required fields
            assert "usd_fmt" in t
            assert "to_label" in t
            assert "from_label" in t
            assert "time_ago" in t
            assert "token" in t
            assert "tx_type" in t

            # usd_fmt should be formatted
            assert t["usd_fmt"].startswith("$")

            # time_ago should be human readable
            assert any(unit in t["time_ago"] for unit in ['m ago', 'h ago', 'd ago'])

        print(f"Transfers: {len(data['transfers'])} returned, first={data['transfers'][0]['usd_fmt'] if data['transfers'] else 'none'}")


class TestSmartMoneyEndpoint:
    """Smart Money Radar API - human-readable labels"""

    def test_smart_money_returns_human_labels(self):
        """GET /api/onchain-overview/smart-money returns wallets with human label"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/smart-money?window=30d&limit=10")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert "wallets" in data

        # Valid human-readable labels (NOT "Auto-discovered")
        valid_labels = ["Smart Money Wallet", "Multi-Exchange", "Whale", "Exchange Wallet", "Bridge", "Fund Wallet", "Protocol", "Wallet"]

        if data["wallets"]:
            for wallet in data["wallets"]:
                assert "label" in wallet
                assert "wallet" in wallet
                assert "score" in wallet
                assert "volume_fmt" in wallet

                # Label must be human-readable
                assert wallet["label"] in valid_labels, f"Invalid label: {wallet['label']}"

            print(f"Smart Money: {len(data['wallets'])} wallets, labels={[w['label'] for w in data['wallets'][:3]]}")


class TestEntitiesEndpoint:
    """Top Entities API"""

    def test_entities_returns_volume_usd_fmt(self):
        """GET /api/onchain-overview/entities returns entities with volume_usd_fmt"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/entities?window=30d&limit=5")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert "entities" in data

        if data["entities"]:
            entity = data["entities"][0]
            assert "entity" in entity
            assert "volume_usd_fmt" in entity
            assert "tx_count" in entity

            # volume_usd_fmt should be formatted
            assert entity["volume_usd_fmt"].startswith("$")

        print(f"Entities: {len(data['entities'])} returned, top={data['entities'][0]['entity'] if data['entities'] else 'none'}")


class TestTokenFlowsEndpoint:
    """Token Flows API - USD volume"""

    def test_token_flows_returns_volume_fmt_usd(self):
        """GET /api/onchain-overview/token-flows returns tokens with volume_fmt in USD"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/token-flows?window=30d")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert "tokens" in data

        if data["tokens"]:
            token = data["tokens"][0]
            assert "token" in token
            assert "volume_fmt" in token
            assert "transfer_count" in token

            # volume_fmt should be USD formatted
            assert token["volume_fmt"].startswith("$")

        print(f"Tokens: {len(data['tokens'])} returned, top={data['tokens'][0]['token'] if data['tokens'] else 'none'}")


class TestClustersEndpoint:
    """Cluster Intelligence API - expandable with wallets array"""

    def test_clusters_returns_wallets_array(self):
        """GET /api/onchain-overview/clusters returns clusters with wallets array for expand"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/clusters?window=30d&limit=5")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert "clusters" in data

        if data["clusters"]:
            cluster = data["clusters"][0]
            assert "cluster_id" in cluster
            assert "cluster_type" in cluster
            assert "wallet_count" in cluster
            assert "volume_fmt" in cluster

            # KEY: wallets array for expandability
            assert "wallets" in cluster
            assert isinstance(cluster["wallets"], list)

            # volume_fmt should be USD formatted
            assert cluster["volume_fmt"].startswith("$")

        print(f"Clusters: {len(data['clusters'])} returned, first has {len(data['clusters'][0]['wallets']) if data['clusters'] else 0} wallets")


class TestSignalsEndpoint:
    """Key Signals API - human-readable titles"""

    def test_signals_returns_human_readable_title(self):
        """GET /api/onchain-overview/signals returns human-readable title field"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/signals?limit=5")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert "signals" in data

        if data["signals"]:
            signal = data["signals"][0]
            assert "title" in signal
            assert "description" in signal
            assert "score" in signal
            assert "severity" in signal

            # Title should be human-readable (not raw type like CLUSTER_ACTIVITY)
            assert "_" not in signal["title"] or "Activity" in signal["title"]
            # Title should have spaces
            assert " " in signal["title"]

        print(f"Signals: {len(data['signals'])} returned, titles={[s['title'] for s in data['signals'][:3]]}")


class TestTimeFilterConsistency:
    """Time filter works across all windowed endpoints"""

    def test_24h_filter_works_all_endpoints(self):
        """24h window parameter works on all applicable endpoints"""
        endpoints = [
            "/api/onchain-overview/summary",
            "/api/onchain-overview/context",
            "/api/onchain-overview/story",
            "/api/onchain-overview/exchange-flows",
            "/api/onchain-overview/transfers",
            "/api/onchain-overview/smart-money",
            "/api/onchain-overview/entities",
            "/api/onchain-overview/token-flows",
            "/api/onchain-overview/clusters",
        ]

        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}?window=24h")
            assert response.status_code == 200, f"Failed on {endpoint}"
            data = response.json()
            assert data["ok"] is True, f"Not ok on {endpoint}"

        print("All 9 windowed endpoints work with 24h filter")
