"""
Prediction Module Tests — Event Probability Intelligence (Polymarket Integration)

Tests for:
- GET /api/prediction/markets — raw Polymarket markets
- GET /api/prediction/run — full pipeline: markets → classify → probability → edge → decision
- Probability engine fallback when Exchange data unavailable
- Decision values: YES, NO, WAIT, AVOID
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPredictionMarkets:
    """Tests for GET /api/prediction/markets endpoint"""

    def test_markets_endpoint_returns_ok(self):
        """GET /api/prediction/markets returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/prediction/markets?limit=5", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true in response"
        assert "count" in data, "Expected 'count' field in response"
        assert "markets" in data, "Expected 'markets' field in response"
        assert isinstance(data["markets"], list), "Expected 'markets' to be a list"
        print(f"✓ Markets endpoint returned {data['count']} markets")

    def test_markets_structure(self):
        """Each market has required fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/markets?limit=5", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        if data["count"] > 0:
            market = data["markets"][0]
            required_fields = ["market_id", "question", "yes_price", "no_price", "volume", "liquidity"]
            for field in required_fields:
                assert field in market, f"Missing field '{field}' in market"
            print(f"✓ Market structure validated: {list(market.keys())}")
        else:
            pytest.skip("No markets returned from Polymarket API")


class TestPredictionRun:
    """Tests for GET /api/prediction/run endpoint (full pipeline)"""

    def test_run_endpoint_returns_ok(self):
        """GET /api/prediction/run returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true in response"
        print(f"✓ Run endpoint returned ok=true")

    def test_run_returns_classified_count(self):
        """GET /api/prediction/run returns classified count"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        assert "total_markets" in data, "Expected 'total_markets' field"
        assert "classified" in data, "Expected 'classified' field"
        assert "skipped" in data, "Expected 'skipped' field"
        assert isinstance(data["classified"], int), "Expected 'classified' to be int"
        print(f"✓ Total: {data['total_markets']}, Classified: {data['classified']}, Skipped: {data['skipped']}")

    def test_run_returns_results_array(self):
        """GET /api/prediction/run returns results array"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data, "Expected 'results' field"
        assert isinstance(data["results"], list), "Expected 'results' to be a list"
        print(f"✓ Results array contains {len(data['results'])} items")

    def test_run_result_structure(self):
        """Each result has required fields: market_id, question, asset, threshold, implied_prob, fair_prob, net_edge, decision, confidence, reasoning"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        if len(data["results"]) > 0:
            result = data["results"][0]
            required_fields = [
                "market_id", "question", "asset", "threshold",
                "implied_prob", "fair_prob", "net_edge",
                "decision", "confidence", "reasoning"
            ]
            for field in required_fields:
                assert field in result, f"Missing field '{field}' in result"
            print(f"✓ Result structure validated with all required fields")
            print(f"  Sample: {result['question'][:50]}... → {result['decision']}")
        else:
            pytest.skip("No classified results (no BTC/ETH threshold markets found)")

    def test_decision_values_valid(self):
        """Decision values are only: YES, NO, WAIT, AVOID"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        valid_decisions = {"YES", "NO", "WAIT", "AVOID"}
        
        for result in data["results"]:
            decision = result.get("decision")
            assert decision in valid_decisions, f"Invalid decision '{decision}', expected one of {valid_decisions}"
        
        # Count decisions
        decision_counts = {}
        for r in data["results"]:
            d = r["decision"]
            decision_counts[d] = decision_counts.get(d, 0) + 1
        
        print(f"✓ All decisions valid. Distribution: {decision_counts}")

    def test_exchange_availability_reported(self):
        """Response includes exchange_available status for BTC and ETH"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=10", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        assert "exchange_available" in data, "Expected 'exchange_available' field"
        assert "BTC" in data["exchange_available"], "Expected BTC in exchange_available"
        assert "ETH" in data["exchange_available"], "Expected ETH in exchange_available"
        
        btc_available = data["exchange_available"]["BTC"]
        eth_available = data["exchange_available"]["ETH"]
        print(f"✓ Exchange availability: BTC={btc_available}, ETH={eth_available}")


class TestProbabilityEngineFallback:
    """Tests for probability engine fallback behavior"""

    def test_fair_prob_within_bounds(self):
        """fair_prob should be between 0.02 and 0.98"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        for result in data["results"]:
            fair_prob = result.get("fair_prob", 0)
            assert 0.02 <= fair_prob <= 0.98, f"fair_prob {fair_prob} out of bounds [0.02, 0.98]"
        
        print(f"✓ All {len(data['results'])} fair_prob values within bounds")

    def test_components_included(self):
        """Results include probability components breakdown"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=10", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        if len(data["results"]) > 0:
            result = data["results"][0]
            assert "components" in result, "Expected 'components' field in result"
            components = result["components"]
            assert "exchange_base" in components, "Expected 'exchange_base' in components"
            print(f"✓ Components: {components}")
        else:
            pytest.skip("No results to check components")


class TestEdgeComputation:
    """Tests for edge computation"""

    def test_net_edge_computed(self):
        """net_edge is computed for all results"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        for result in data["results"]:
            assert "net_edge" in result, "Missing 'net_edge' field"
            assert isinstance(result["net_edge"], (int, float)), "net_edge should be numeric"
        
        print(f"✓ net_edge computed for all {len(data['results'])} results")

    def test_implied_prob_from_market(self):
        """implied_prob comes from market yes_price"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=10", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        for result in data["results"]:
            implied = result.get("implied_prob", 0)
            assert 0 <= implied <= 1, f"implied_prob {implied} out of bounds [0, 1]"
        
        print(f"✓ All implied_prob values within [0, 1]")


class TestAssetClassification:
    """Tests for BTC/ETH asset classification"""

    def test_only_btc_eth_classified(self):
        """Only BTC and ETH assets are classified (MVP scope)"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        valid_assets = {"BTC", "ETH"}
        
        for result in data["results"]:
            asset = result.get("asset")
            assert asset in valid_assets, f"Unexpected asset '{asset}', expected BTC or ETH"
        
        # Count by asset
        asset_counts = {}
        for r in data["results"]:
            a = r["asset"]
            asset_counts[a] = asset_counts.get(a, 0) + 1
        
        print(f"✓ All assets valid. Distribution: {asset_counts}")

    def test_threshold_extracted(self):
        """Threshold is extracted from market question"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        for result in data["results"]:
            threshold = result.get("threshold")
            assert threshold is not None, "Missing 'threshold' field"
            assert isinstance(threshold, (int, float)), "threshold should be numeric"
            assert threshold > 0, f"threshold {threshold} should be positive"
        
        print(f"✓ All thresholds extracted and positive")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
