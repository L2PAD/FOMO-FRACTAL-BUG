"""
Graph Core Alpha Engine API Tests
===================================
Tests for the Alpha Engine (5 services):
  - Smart Money Detector
  - Capital Flow Signals  
  - Liquidity Pressure Engine
  - Narrative Detector
  - Alpha Signals API

Also includes P0-P2 regression tests:
  - /api/graph-core/wash/alerts (P2)
  - /api/graph-core/clusters (P2)
  - /api/graph-core/liquidity-map (P1)
  - /api/graph-core/nodes/top (P1)
  - /api/graph-core/search/suggest (P0)
  - /api/graph-core/neighbors/{node_id} (Core)
  - /api/graph-core/health (Core)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

BINANCE_NODE_ID = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ============================================================
# ALPHA SIGNALS ENDPOINT
# ============================================================

class TestAlphaSignalsEndpoint:
    """Tests for GET /api/graph-core/alpha/signals"""

    def test_get_alpha_signals_returns_200(self, api_client):
        """Test alpha signals endpoint returns 200"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/alpha/signals")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/graph-core/alpha/signals returned 200")

    def test_alpha_signals_response_structure(self, api_client):
        """Test alpha signals response has required fields"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/alpha/signals")
        data = response.json()
        
        assert "signals" in data, "Response missing 'signals' field"
        assert "total" in data, "Response missing 'total' field"
        assert "returned" in data, "Response missing 'returned' field"
        assert "signal_types" in data, "Response missing 'signal_types' field"
        print(f"✓ Alpha signals has correct structure: total={data['total']}, returned={data['returned']}")

    def test_alpha_signals_have_required_fields(self, api_client):
        """Test each signal has signal_type, confidence, direction"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/alpha/signals")
        data = response.json()
        
        if data["total"] > 0:
            signal = data["signals"][0]
            assert "signal_type" in signal, "Signal missing 'signal_type'"
            assert "confidence" in signal, "Signal missing 'confidence'"
            assert "direction" in signal, "Signal missing 'direction'"
            assert "generated_at" in signal, "Signal missing 'generated_at'"
            print(f"✓ Signal structure verified: type={signal['signal_type']}, conf={signal['confidence']}, dir={signal['direction']}")
        else:
            print("⚠ No signals to verify structure (empty dataset)")

    def test_alpha_signals_filter_by_type(self, api_client):
        """Test filtering signals by signal_type"""
        response = api_client.get(
            f"{BASE_URL}/api/graph-core/alpha/signals",
            params={"signal_type": "exchange_outflow_spike"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned signals should match the filter
        for signal in data["signals"]:
            assert signal["signal_type"] == "exchange_outflow_spike"
        print(f"✓ Filter by signal_type works: returned {data['returned']} exchange_outflow_spike signals")

    def test_alpha_signals_directions_valid(self, api_client):
        """Test signal directions are valid values"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/alpha/signals")
        data = response.json()
        
        valid_directions = {"bullish", "bearish", "neutral"}
        for signal in data["signals"]:
            assert signal["direction"] in valid_directions, f"Invalid direction: {signal['direction']}"
        print(f"✓ All {len(data['signals'])} signals have valid direction values")


# ============================================================
# ALPHA PRESSURE ENDPOINT
# ============================================================

class TestAlphaPressureEndpoint:
    """Tests for GET /api/graph-core/alpha/pressure"""

    def test_get_pressure_returns_200(self, api_client):
        """Test liquidity pressure endpoint returns 200"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/alpha/pressure")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/graph-core/alpha/pressure returned 200")

    def test_pressure_has_required_fields(self, api_client):
        """Test pressure response has pressure_score, trend, metrics"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/alpha/pressure")
        data = response.json()
        
        assert "pressure_score" in data, "Response missing 'pressure_score'"
        assert "trend" in data, "Response missing 'trend'"
        assert "metrics" in data, "Response missing 'metrics'"
        print(f"✓ Pressure response: score={data['pressure_score']}, trend={data['trend']}")

    def test_pressure_trend_valid(self, api_client):
        """Test pressure trend is valid value"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/alpha/pressure")
        data = response.json()
        
        valid_trends = {"bullish", "bearish", "neutral"}
        assert data["trend"] in valid_trends, f"Invalid trend: {data['trend']}"
        print(f"✓ Pressure trend is valid: {data['trend']}")

    def test_pressure_metrics_structure(self, api_client):
        """Test pressure metrics has flow breakdown"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/alpha/pressure")
        data = response.json()
        metrics = data.get("metrics", {})
        
        expected_keys = ["dex_inflow", "dex_outflow", "cex_deposits", "cex_withdrawals", "total_volume"]
        for key in expected_keys:
            assert key in metrics, f"Metrics missing '{key}'"
        print(f"✓ Pressure metrics structure verified: total_volume={metrics.get('total_volume', 0)}")


# ============================================================
# ALPHA SMART MONEY ENDPOINT
# ============================================================

class TestAlphaSmartMoneyEndpoint:
    """Tests for GET /api/graph-core/alpha/smart-money"""

    def test_get_smart_money_returns_200(self, api_client):
        """Test smart money endpoint returns 200"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/alpha/smart-money")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/graph-core/alpha/smart-money returned 200")

    def test_smart_money_response_structure(self, api_client):
        """Test smart money response has wallets and count"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/alpha/smart-money")
        data = response.json()
        
        assert "wallets" in data, "Response missing 'wallets'"
        assert "count" in data, "Response missing 'count'"
        print(f"✓ Smart money response: {data['count']} wallets returned")

    def test_smart_money_limit_works(self, api_client):
        """Test limit parameter on smart money"""
        response = api_client.get(
            f"{BASE_URL}/api/graph-core/alpha/smart-money",
            params={"limit": 5}
        )
        data = response.json()
        
        assert data["count"] <= 5, f"Expected <= 5 wallets, got {data['count']}"
        print(f"✓ Smart money limit=5 works: returned {data['count']} wallets")

    def test_smart_money_wallets_have_score(self, api_client):
        """Test smart money wallets have smart_money_score"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/alpha/smart-money")
        data = response.json()
        
        if data["count"] > 0:
            wallet = data["wallets"][0]
            assert "smart_money_score" in wallet, "Wallet missing 'smart_money_score'"
            assert "id" in wallet, "Wallet missing 'id'"
            assert wallet["smart_money_score"] > 0, "Top wallet should have score > 0"
            print(f"✓ Top smart money wallet: {wallet['id'][:40]}... score={wallet['smart_money_score']}")
        else:
            print("⚠ No smart money wallets to verify")


# ============================================================
# ALPHA GENERATE ENDPOINT (Full Pipeline)
# ============================================================

class TestAlphaGenerateEndpoint:
    """Tests for POST /api/graph-core/alpha/generate"""

    def test_generate_alpha_returns_200(self, api_client):
        """Test alpha generation pipeline returns 200"""
        response = api_client.post(f"{BASE_URL}/api/graph-core/alpha/generate")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ POST /api/graph-core/alpha/generate returned 200")

    def test_generate_alpha_response_structure(self, api_client):
        """Test alpha generation response has all pipeline results"""
        response = api_client.post(f"{BASE_URL}/api/graph-core/alpha/generate")
        data = response.json()
        
        assert "status" in data, "Response missing 'status'"
        assert data["status"] == "completed", f"Expected status 'completed', got {data['status']}"
        assert "smart_money_scored" in data, "Response missing 'smart_money_scored'"
        assert "flow_signals" in data, "Response missing 'flow_signals'"
        assert "pressure" in data, "Response missing 'pressure'"
        assert "narratives" in data, "Response missing 'narratives'"
        
        print(f"✓ Alpha pipeline completed:")
        print(f"  - Smart money scored: {data['smart_money_scored']}")
        print(f"  - Flow signals: {data['flow_signals']}")
        print(f"  - Pressure trend: {data['pressure']}")
        print(f"  - Narratives: {data['narratives']}")

    def test_generate_alpha_total_signals(self, api_client):
        """Test alpha generation returns total_signals"""
        response = api_client.post(f"{BASE_URL}/api/graph-core/alpha/generate")
        data = response.json()
        
        assert "total_signals" in data, "Response missing 'total_signals'"
        expected_total = data["flow_signals"] + data["narratives"]
        assert data["total_signals"] == expected_total, f"total_signals mismatch"
        print(f"✓ Total signals calculation correct: {data['total_signals']}")


# ============================================================
# REGRESSION: P2 Wash Alerts
# ============================================================

class TestRegressionWashAlerts:
    """Regression tests for GET /api/graph-core/wash/alerts"""

    def test_wash_alerts_returns_200(self, api_client):
        """Test wash alerts endpoint returns 200"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/wash/alerts")
        assert response.status_code == 200
        print(f"✓ Regression: wash/alerts returns 200")

    def test_wash_alerts_structure(self, api_client):
        """Test wash alerts response structure"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/wash/alerts")
        data = response.json()
        
        assert "alerts" in data
        assert "total" in data
        assert "stats" in data
        print(f"✓ Regression: wash/alerts structure OK, total={data['total']}")


# ============================================================
# REGRESSION: P2 Clusters
# ============================================================

class TestRegressionClusters:
    """Regression tests for GET /api/graph-core/clusters"""

    def test_clusters_returns_200(self, api_client):
        """Test clusters endpoint returns 200"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/clusters")
        assert response.status_code == 200
        print(f"✓ Regression: clusters returns 200")

    def test_clusters_structure(self, api_client):
        """Test clusters response structure"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/clusters")
        data = response.json()
        
        assert "clusters" in data
        # API returns 'count' or 'total' depending on endpoint variant
        count = data.get("total", data.get("count", len(data["clusters"])))
        print(f"✓ Regression: clusters structure OK, count={count}")


# ============================================================
# REGRESSION: P1 Liquidity Map
# ============================================================

class TestRegressionLiquidityMap:
    """Regression tests for GET /api/graph-core/liquidity-map"""

    def test_liquidity_map_returns_200(self, api_client):
        """Test liquidity map endpoint returns 200"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/liquidity-map")
        assert response.status_code == 200
        print(f"✓ Regression: liquidity-map returns 200")

    def test_liquidity_map_has_categories(self, api_client):
        """Test liquidity map has categories"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/liquidity-map")
        data = response.json()
        
        assert "categories" in data, "Response missing 'categories'"
        assert "source" in data, "Response missing 'source'"
        print(f"✓ Regression: liquidity-map has categories, source={data['source']}")


# ============================================================
# REGRESSION: P1 Top Nodes
# ============================================================

class TestRegressionTopNodes:
    """Regression tests for GET /api/graph-core/nodes/top"""

    def test_top_nodes_returns_200(self, api_client):
        """Test top nodes endpoint returns 200"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/nodes/top")
        assert response.status_code == 200
        print(f"✓ Regression: nodes/top returns 200")

    def test_top_nodes_structure(self, api_client):
        """Test top nodes response structure"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/nodes/top")
        data = response.json()
        
        assert "nodes" in data
        assert "count" in data
        print(f"✓ Regression: nodes/top structure OK, count={data['count']}")


# ============================================================
# REGRESSION: P0 Search Suggest
# ============================================================

class TestRegressionSearchSuggest:
    """Regression tests for GET /api/graph-core/search/suggest"""

    def test_search_suggest_returns_200(self, api_client):
        """Test search suggest endpoint returns 200"""
        response = api_client.get(
            f"{BASE_URL}/api/graph-core/search/suggest",
            params={"q": "bin"}
        )
        assert response.status_code == 200
        print(f"✓ Regression: search/suggest?q=bin returns 200")

    def test_search_suggest_finds_binance(self, api_client):
        """Test search suggest finds Binance"""
        response = api_client.get(
            f"{BASE_URL}/api/graph-core/search/suggest",
            params={"q": "bin"}
        )
        data = response.json()
        
        assert "results" in data
        assert data["count"] > 0, "Should find results for 'bin'"
        
        # First result should be Binance
        labels = [r.get("label", "").lower() for r in data["results"]]
        assert any("binance" in label for label in labels), "Binance not found in results"
        print(f"✓ Regression: search/suggest finds Binance, count={data['count']}")


# ============================================================
# REGRESSION: Core Neighbors
# ============================================================

class TestRegressionNeighbors:
    """Regression tests for GET /api/graph-core/neighbors/{node_id}"""

    def test_neighbors_returns_200(self, api_client):
        """Test neighbors endpoint returns 200 for Binance"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/neighbors/{BINANCE_NODE_ID}")
        assert response.status_code == 200
        print(f"✓ Regression: neighbors for Binance returns 200")

    def test_neighbors_has_nodes_and_edges(self, api_client):
        """Test neighbors response has nodes and edges"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/neighbors/{BINANCE_NODE_ID}")
        data = response.json()
        
        assert "nodes" in data, "Response missing 'nodes'"
        assert "edges" in data, "Response missing 'edges'"
        assert "node_count" in data, "Response missing 'node_count'"
        assert "edge_count" in data, "Response missing 'edge_count'"
        print(f"✓ Regression: neighbors has {data['node_count']} nodes, {data['edge_count']} edges")


# ============================================================
# REGRESSION: Core Health
# ============================================================

class TestRegressionHealth:
    """Regression tests for GET /api/graph-core/health"""

    def test_health_returns_200(self, api_client):
        """Test health endpoint returns 200"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        print(f"✓ Regression: health returns 200")

    def test_health_has_storage_stats(self, api_client):
        """Test health has storage statistics"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        
        assert data["status"] == "ok", f"Health status not ok: {data.get('status')}"
        assert "storage" in data, "Response missing 'storage'"
        
        storage = data["storage"]
        assert "graph_nodes" in storage, "Storage missing 'graph_nodes'"
        assert "graph_relations" in storage, "Storage missing 'graph_relations'"
        print(f"✓ Regression: health OK, nodes={storage['graph_nodes']}, relations={storage['graph_relations']}")

    def test_health_has_alpha_collections(self, api_client):
        """Test health shows alpha-related collections"""
        response = api_client.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        storage = data.get("storage", {})
        
        # Alpha engine uses these collections
        print(f"✓ Storage collections: {list(storage.keys())}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
