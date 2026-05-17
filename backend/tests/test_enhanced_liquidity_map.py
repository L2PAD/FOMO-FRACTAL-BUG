"""
Enhanced Liquidity Map Table Tests (iteration 341)
===================================================
Tests for enhanced liquidity map table features:
1. New summary fields: edges_total, tx_count, tx_in, tx_out, flow_driver
2. from_aggregates/to_aggregates new structure: {key: {amount, pct}}
3. top_counterparties array with label, amount, tx_count
4. flow_state is always ACCUMULATION or DISTRIBUTION (never NEUTRAL)
5. POST /api/graph-core/liquidity-map/refresh returns updated data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')


class TestEnhancedLiquidityMapSummary:
    """Test new summary fields in liquidity-map endpoint"""

    def test_summary_has_edges_total(self):
        """Verify summary contains edges_total field"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        summary = data.get("summary", {})
        
        assert "edges_total" in summary, "Missing edges_total in summary"
        assert isinstance(summary["edges_total"], int), "edges_total should be integer"
        print(f"edges_total: {summary['edges_total']}")

    def test_summary_has_tx_count_fields(self):
        """Verify summary contains tx_count, tx_in, tx_out fields"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        summary = data.get("summary", {})
        
        assert "tx_count" in summary, "Missing tx_count in summary"
        assert "tx_in" in summary, "Missing tx_in in summary"
        assert "tx_out" in summary, "Missing tx_out in summary"
        
        assert isinstance(summary["tx_count"], int), "tx_count should be integer"
        assert isinstance(summary["tx_in"], int), "tx_in should be integer"
        assert isinstance(summary["tx_out"], int), "tx_out should be integer"
        
        print(f"tx_count: {summary['tx_count']}, tx_in: {summary['tx_in']}, tx_out: {summary['tx_out']}")

    def test_summary_has_flow_driver(self):
        """Verify summary contains flow_driver field"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        summary = data.get("summary", {})
        
        assert "flow_driver" in summary, "Missing flow_driver in summary"
        flow_driver = summary["flow_driver"]
        
        # flow_driver should be null or a string like "CEX-driven", "DEX-driven", "Wallets exit", etc.
        if flow_driver is not None:
            assert isinstance(flow_driver, str), "flow_driver should be string or null"
            print(f"flow_driver: {flow_driver}")
        else:
            print("flow_driver: null (no dominant source)")

    def test_flow_state_no_neutral(self):
        """Verify flow_state is always ACCUMULATION or DISTRIBUTION, never NEUTRAL"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        summary = data.get("summary", {})
        
        flow_state = summary.get("flow_state")
        assert flow_state in ["ACCUMULATION", "DISTRIBUTION"], \
            f"flow_state should be ACCUMULATION or DISTRIBUTION only, got: {flow_state}"
        print(f"flow_state: {flow_state} (verified: no NEUTRAL)")


class TestFromToAggregatesStructure:
    """Test new from_aggregates and to_aggregates structure with {amount, pct}"""

    def test_from_aggregates_has_amount_pct(self):
        """Verify from_aggregates entries have {amount, pct} structure"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        from_agg = data.get("from_aggregates", {})
        
        assert isinstance(from_agg, dict), "from_aggregates should be an object"
        
        # Check expected keys: CEX, Wallets, DEX, Bridge
        expected_keys = ["CEX", "Wallets", "DEX", "Bridge"]
        for key in expected_keys:
            if key in from_agg:
                entry = from_agg[key]
                assert isinstance(entry, dict), f"from_aggregates[{key}] should be an object"
                assert "amount" in entry, f"from_aggregates[{key}] missing 'amount'"
                assert "pct" in entry, f"from_aggregates[{key}] missing 'pct'"
                assert isinstance(entry["amount"], (int, float)), f"from_aggregates[{key}].amount should be numeric"
                assert isinstance(entry["pct"], (int, float)), f"from_aggregates[{key}].pct should be numeric"
                print(f"from_aggregates[{key}]: amount={entry['amount']}, pct={entry['pct']}%")

    def test_to_aggregates_has_amount_pct(self):
        """Verify to_aggregates entries have {amount, pct} structure"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        to_agg = data.get("to_aggregates", {})
        
        assert isinstance(to_agg, dict), "to_aggregates should be an object"
        
        # Check expected keys: CEX, Wallets, DEX, Bridge
        expected_keys = ["CEX", "Wallets", "DEX", "Bridge"]
        for key in expected_keys:
            if key in to_agg:
                entry = to_agg[key]
                assert isinstance(entry, dict), f"to_aggregates[{key}] should be an object"
                assert "amount" in entry, f"to_aggregates[{key}] missing 'amount'"
                assert "pct" in entry, f"to_aggregates[{key}] missing 'pct'"
                assert isinstance(entry["amount"], (int, float)), f"to_aggregates[{key}].amount should be numeric"
                assert isinstance(entry["pct"], (int, float)), f"to_aggregates[{key}].pct should be numeric"
                print(f"to_aggregates[{key}]: amount={entry['amount']}, pct={entry['pct']}%")

    def test_percentages_sum_to_100(self):
        """Verify percentages in from_aggregates and to_aggregates sum to ~100%"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        from_agg = data.get("from_aggregates", {})
        to_agg = data.get("to_aggregates", {})
        
        from_pct_sum = sum(e.get("pct", 0) for e in from_agg.values() if isinstance(e, dict))
        to_pct_sum = sum(e.get("pct", 0) for e in to_agg.values() if isinstance(e, dict))
        
        print(f"from_aggregates pct sum: {from_pct_sum}%")
        print(f"to_aggregates pct sum: {to_pct_sum}%")
        
        # Allow small floating point tolerance
        if from_pct_sum > 0:
            assert 99.5 <= from_pct_sum <= 100.5, f"from_aggregates percentages should sum to ~100%, got {from_pct_sum}%"
        if to_pct_sum > 0:
            assert 99.5 <= to_pct_sum <= 100.5, f"to_aggregates percentages should sum to ~100%, got {to_pct_sum}%"


class TestTopCounterparties:
    """Test top_counterparties array"""

    def test_top_counterparties_exists(self):
        """Verify top_counterparties array exists"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "top_counterparties" in data, "Missing top_counterparties in response"
        top_cp = data["top_counterparties"]
        assert isinstance(top_cp, list), "top_counterparties should be an array"
        print(f"top_counterparties count: {len(top_cp)}")

    def test_top_counterparties_structure(self):
        """Verify top_counterparties entries have label, amount, tx_count fields"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        top_cp = data.get("top_counterparties", [])
        
        if len(top_cp) == 0:
            pytest.skip("No top_counterparties data to verify")
        
        for i, cp in enumerate(top_cp[:5]):  # Check first 5
            assert "label" in cp, f"top_counterparties[{i}] missing 'label'"
            assert "amount" in cp, f"top_counterparties[{i}] missing 'amount'"
            assert "tx_count" in cp, f"top_counterparties[{i}] missing 'tx_count'"
            
            assert isinstance(cp["label"], str), f"top_counterparties[{i}].label should be string"
            assert isinstance(cp["amount"], (int, float)), f"top_counterparties[{i}].amount should be numeric"
            assert isinstance(cp["tx_count"], int), f"top_counterparties[{i}].tx_count should be integer"
            
            print(f"Counterparty {i+1}: {cp['label']} - ${cp['amount']:,.2f} ({cp['tx_count']} txs)")

    def test_top_counterparties_are_real_entities(self):
        """Verify top_counterparties are real entities (not types like 'CEX')"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        top_cp = data.get("top_counterparties", [])
        
        if len(top_cp) == 0:
            pytest.skip("No top_counterparties data to verify")
        
        # Labels should NOT be generic type names like "CEX", "DEX", "Bridge", "Wallets"
        generic_types = {"CEX", "DEX", "Bridge", "Wallets", "wallet", "cex", "dex", "bridge"}
        
        for cp in top_cp[:10]:
            label = cp.get("label", "")
            # The label should be a specific entity name like "Binance", "DAI", etc.
            # not a generic category
            assert label not in generic_types, \
                f"top_counterparties should have real entity names, got generic type: {label}"
        
        print("Verified: all top_counterparties are real entities (not generic types)")


class TestLiquidityMapRefresh:
    """Test POST /api/graph-core/liquidity-map/refresh"""

    def test_refresh_returns_updated_data(self):
        """Verify POST refresh returns status and updated summary with new fields"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map/refresh"
        response = requests.post(url, timeout=60)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "status" in data, "Refresh response missing 'status'"
        assert data["status"] == "refreshed", f"Expected status='refreshed', got {data['status']}"
        
        summary = data.get("summary", {})
        print(f"Refresh returned summary with {len(summary)} fields")
        
        # Verify new fields are in the summary
        assert "edges_total" in summary, "Refresh summary missing edges_total"
        assert "tx_count" in summary, "Refresh summary missing tx_count"
        assert "tx_in" in summary, "Refresh summary missing tx_in"
        assert "tx_out" in summary, "Refresh summary missing tx_out"
        assert "flow_state" in summary, "Refresh summary missing flow_state"
        assert "flow_driver" in summary, "Refresh summary missing flow_driver"
        
        # Verify flow_state is not NEUTRAL
        flow_state = summary.get("flow_state")
        assert flow_state in ["ACCUMULATION", "DISTRIBUTION"], \
            f"flow_state should be ACCUMULATION or DISTRIBUTION, got: {flow_state}"
        
        print(f"Refresh verified: edges_total={summary.get('edges_total')}, "
              f"tx_count={summary.get('tx_count')}, flow_state={flow_state}")


class TestHealthCheck:
    """Basic health check"""

    def test_graph_core_health(self):
        """Verify graph-core health endpoint is working"""
        url = f"{BASE_URL}/api/graph-core/health"
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok", f"Health check failed: {data}"
        print("Graph core health: OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
