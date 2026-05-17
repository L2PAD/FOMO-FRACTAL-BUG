"""
Phase BT (Engine Backtest) and Phase F (OnChain Health) Tests
=============================================================
Tests for:
- POST /api/v10/onchain-v2/engine/backtest/run (valid, empty body, invalid window)
- GET /api/v10/onchain-v2/engine/backtest/last
- GET /api/v10/onchain-v2/system/health/onchain
- Persistence verification (run -> last retrieval)
- Multi-chain support (chainId=1, 10, 42161, 8453)
- Existing endpoints regression (/wallets/tokens, /system/chains, /wallets/health)
"""

import pytest
import requests
import os
import time

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://expo-telegram-web.preview.emergentagent.com"

API_PREFIX = f"{BASE_URL}/api/v10/onchain-v2"


class TestEngineBacktestRun:
    """Tests for POST /engine/backtest/run endpoint"""

    def test_backtest_run_valid_request_chainid_1(self):
        """POST /engine/backtest/run with valid body returns ok:true with summary"""
        url = f"{API_PREFIX}/engine/backtest/run"
        payload = {
            "chainId": 1,
            "from": "2026-02-25",
            "to": "2026-02-26",
            "stepDays": 1,
            "window": "24h",
            "topK": 5,
            "mode": "BUY_ONLY",
            "horizons": [7]
        }
        
        response = requests.post(url, json=payload, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        assert "summary" in data, f"Expected summary in response, got {data}"
        
        summary = data["summary"]
        # Verify summary structure
        assert "points" in summary, "Expected 'points' in summary"
        assert "actionableRate" in summary, "Expected 'actionableRate' in summary"
        assert "coverage" in summary, "Expected 'coverage' in summary"
        assert "byH" in summary, "Expected 'byH' in summary"
        assert "chainId" in summary, "Expected 'chainId' in summary"
        assert summary["chainId"] == 1, f"Expected chainId=1, got {summary['chainId']}"
        
        print(f"Backtest summary: points={summary['points']}, actionableRate={summary['actionableRate']}, coverage={summary['coverage']}")
        print(f"byH: {summary.get('byH', {})}")
        if summary.get("dataWarning"):
            print(f"Data warning (expected): {summary['dataWarning']}")

    def test_backtest_run_empty_body_returns_400(self):
        """POST /engine/backtest/run with empty body returns 400 INVALID_DATES"""
        url = f"{API_PREFIX}/engine/backtest/run"
        
        response = requests.post(url, json={}, timeout=30)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is False, f"Expected ok:false, got {data}"
        assert data.get("error") == "INVALID_DATES", f"Expected error:INVALID_DATES, got {data.get('error')}"
        print(f"Empty body error: {data}")

    def test_backtest_run_invalid_window_returns_400(self):
        """POST /engine/backtest/run with invalid window returns 400 INVALID_WINDOW"""
        url = f"{API_PREFIX}/engine/backtest/run"
        payload = {
            "chainId": 1,
            "from": "2026-02-25",
            "to": "2026-02-26",
            "stepDays": 1,
            "window": "invalid_window",
            "topK": 5,
            "mode": "BUY_ONLY",
            "horizons": [7]
        }
        
        response = requests.post(url, json=payload, timeout=30)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is False, f"Expected ok:false, got {data}"
        assert data.get("error") == "INVALID_WINDOW", f"Expected error:INVALID_WINDOW, got {data.get('error')}"
        print(f"Invalid window error: {data}")

    def test_backtest_run_chainid_10_op(self):
        """POST /engine/backtest/run for chainId=10 (OP) returns ok even with sparse data"""
        url = f"{API_PREFIX}/engine/backtest/run"
        payload = {
            "chainId": 10,
            "from": "2026-02-25",
            "to": "2026-02-26",
            "stepDays": 1,
            "window": "24h",
            "topK": 5,
            "mode": "BUY_ONLY",
            "horizons": [7]
        }
        
        response = requests.post(url, json=payload, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        assert "summary" in data, f"Expected summary in response"
        
        summary = data["summary"]
        assert summary["chainId"] == 10, f"Expected chainId=10, got {summary['chainId']}"
        print(f"OP backtest: points={summary['points']}, actionableRate={summary['actionableRate']}")
        if summary.get("dataWarning"):
            print(f"Data warning (expected for OP): {summary['dataWarning']}")


class TestEngineBacktestLast:
    """Tests for GET /engine/backtest/last endpoint"""

    def test_backtest_last_chainid_1(self):
        """GET /engine/backtest/last?chainId=1 returns ok:true with runs array"""
        url = f"{API_PREFIX}/engine/backtest/last"
        params = {"chainId": 1}
        
        response = requests.get(url, params=params, timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        assert "runs" in data, f"Expected 'runs' in response, got {data}"
        assert isinstance(data["runs"], list), f"Expected runs to be a list, got {type(data['runs'])}"
        
        print(f"Retrieved {len(data['runs'])} backtest runs for chainId=1")
        if data["runs"]:
            latest = data["runs"][0]
            print(f"Latest run: points={latest.get('points')}, actionableRate={latest.get('actionableRate')}")


class TestBacktestPersistence:
    """Test that backtest results persist to DB and can be retrieved"""

    def test_backtest_run_and_retrieve(self):
        """Run backtest, then verify it appears in /backtest/last"""
        # Run a new backtest with unique params
        run_url = f"{API_PREFIX}/engine/backtest/run"
        payload = {
            "chainId": 1,
            "from": "2026-02-24",
            "to": "2026-02-25",
            "stepDays": 1,
            "window": "7d",
            "topK": 3,
            "mode": "BUY_ONLY",
            "horizons": [7, 14]
        }
        
        run_response = requests.post(run_url, json=payload, timeout=60)
        assert run_response.status_code == 200, f"Backtest run failed: {run_response.text}"
        
        run_data = run_response.json()
        assert run_data.get("ok") is True
        
        # Now retrieve via /backtest/last
        last_url = f"{API_PREFIX}/engine/backtest/last"
        last_response = requests.get(last_url, params={"chainId": 1, "limit": 5}, timeout=30)
        assert last_response.status_code == 200, f"Failed to retrieve runs: {last_response.text}"
        
        last_data = last_response.json()
        assert last_data.get("ok") is True
        assert len(last_data["runs"]) > 0, "Expected at least one run to be persisted"
        
        # Verify the run we just created is in the list
        found = False
        for run in last_data["runs"]:
            if (run.get("window") == "7d" and 
                run.get("topK") == 3 and 
                run.get("from") == "2026-02-24"):
                found = True
                print(f"Found persisted run: {run}")
                break
        
        assert found, f"Could not find our persisted run in {last_data['runs']}"


class TestOnchainHealthEndpoint:
    """Tests for GET /system/health/onchain endpoint"""

    def test_health_onchain_returns_ok(self):
        """GET /system/health/onchain returns ok:true with chains array"""
        url = f"{API_PREFIX}/system/health/onchain"
        
        response = requests.get(url, timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        assert "chains" in data, f"Expected 'chains' in response"
        assert "invariants" in data, f"Expected 'invariants' in response"
        assert "warnings" in data, f"Expected 'warnings' in response"
        
        print(f"Health check: {len(data['chains'])} chains, {len(data['warnings'])} warnings")

    def test_health_shows_all_4_chains(self):
        """Health endpoint shows all 4 chains with correct keys: eth, arb, op, base"""
        url = f"{API_PREFIX}/system/health/onchain"
        
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        chains = data.get("chains", [])
        
        # Expected chains
        expected_keys = {"eth", "arb", "op", "base"}
        expected_chain_ids = {1, 42161, 10, 8453}
        
        found_keys = set()
        found_chain_ids = set()
        
        for chain in chains:
            key = chain.get("key", "")
            chain_id = chain.get("chainId")
            found_keys.add(key)
            if chain_id:
                found_chain_ids.add(chain_id)
            print(f"Chain: {key} (chainId={chain_id}, enabled={chain.get('enabled')}, pools={chain.get('pools')})")
        
        # Verify all expected chains are present
        for expected_key in expected_keys:
            assert expected_key in found_keys, f"Expected chain key '{expected_key}' not found in {found_keys}"
        
        for expected_id in expected_chain_ids:
            assert expected_id in found_chain_ids, f"Expected chainId {expected_id} not found in {found_chain_ids}"
        
        print(f"All 4 chains verified: {found_keys}")

    def test_health_shows_pricing_freshness(self):
        """Health endpoint returns pricing freshness per chain"""
        url = f"{API_PREFIX}/system/health/onchain"
        
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        chains = data.get("chains", [])
        
        for chain in chains:
            key = chain.get("key", "")
            freshness = chain.get("pricingFreshness")
            assert freshness is not None, f"Chain {key} missing pricingFreshness"
            assert freshness in ["FRESH", "RECENT", "STALE", "NO_DATA"], f"Invalid freshness: {freshness}"
            print(f"Chain {key}: pricingFreshness={freshness}, altflowLastBucket={chain.get('altflowLastBucket')}")

    def test_health_invariants_structure(self):
        """Health endpoint invariants has expected structure"""
        url = f"{API_PREFIX}/system/health/onchain"
        
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        invariants = data.get("invariants", {})
        
        assert "noHardcodedChainId" in invariants
        assert "allCollectionsIndexed" in invariants
        assert "noNaN" in invariants
        
        print(f"Invariants: {invariants}")


class TestExistingEndpointsRegression:
    """Regression tests for existing endpoints to ensure they still work"""

    def test_wallets_tokens_endpoint(self):
        """GET /wallets/tokens still works"""
        url = f"{API_PREFIX}/wallets/tokens"
        params = {
            "chainId": 1,
            "address": "0x0000000000000000000000000000000000000000",
            "window": "7d"
        }
        
        response = requests.get(url, params=params, timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print(f"Wallets tokens: {len(data.get('items', []))} items")

    def test_system_chains_endpoint(self):
        """GET /system/chains still works"""
        url = f"{BASE_URL}/api/system/chains"
        
        response = requests.get(url, timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        assert "chains" in data, f"Expected 'chains' in response"
        print(f"System chains: {len(data.get('chains', []))} chains")

    def test_wallets_health_endpoint(self):
        """GET /wallets/health still works"""
        url = f"{API_PREFIX}/wallets/health"
        
        response = requests.get(url, timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print(f"Wallets health: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
