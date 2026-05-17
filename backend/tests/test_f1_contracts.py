"""
Phase F1 — Contract Tests (API Invariants)
=============================================
Validates that all key API endpoints:
  - Return correct shape (ok, required fields)
  - Accept chainId parameter (multichain)
  - Don't return NaN/Infinity
  - Don't break on edge cases
  - No cross-chain contamination

Run: pytest /app/backend/tests/test_f1_contracts.py -v
"""

import os
import json
import math
import pytest
import requests

API = os.environ.get("API_URL", "").rstrip("/")
if not API:
    # Read from frontend .env
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        for line in open(env_path):
            if line.startswith("REACT_APP_BACKEND_URL="):
                API = line.split("=", 1)[1].strip().rstrip("/")

BASE = f"{API}/api/v10/onchain-v2"
CHAINS = [1, 42161, 10, 8453]
TEST_ADDR = "0x51c72848c68a965f66fa7a88855f9f7784502a7f"


def no_nan(obj, path=""):
    """Recursively check that no value is NaN or Infinity."""
    if isinstance(obj, float):
        assert not math.isnan(obj), f"NaN at {path}"
        assert not math.isinf(obj), f"Infinity at {path}"
    elif isinstance(obj, dict):
        for k, v in obj.items():
            no_nan(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            no_nan(v, f"{path}[{i}]")


# ═══════════════════════════════════════════════════════
# SYSTEM
# ═══════════════════════════════════════════════════════

class TestSystemEndpoints:
    def test_chains(self):
        r = requests.get(f"{API}/api/system/chains")
        d = r.json()
        assert d.get("ok") or "chains" in d
        chains = d.get("chains", [])
        ids = {c["chainId"] for c in chains}
        assert 1 in ids, "ETH missing"
        assert 42161 in ids, "ARB missing"
        assert 10 in ids, "OP missing"
        assert 8453 in ids, "BASE missing"

    def test_health_onchain(self):
        r = requests.get(f"{BASE}/system/health/onchain")
        d = r.json()
        assert d["ok"] is True
        assert "chains" in d
        assert "invariants" in d
        assert "warnings" in d
        no_nan(d)
        # All 4 chains present
        keys = {c["key"] for c in d["chains"]}
        assert {"eth", "arb", "op", "base"}.issubset(keys)

    def test_job_readiness(self):
        r = requests.get(f"{BASE}/chains/job-readiness")
        d = r.json()
        assert "enabledChains" in d
        assert "featureFlags" in d
        flags = d["featureFlags"]
        for prefix in ["ARB", "OP", "BASE"]:
            assert flags.get(f"ENABLE_{prefix}_INGESTION") is True


# ═══════════════════════════════════════════════════════
# WALLETS
# ═══════════════════════════════════════════════════════

class TestWalletEndpoints:
    def test_wallets_health(self):
        r = requests.get(f"{BASE}/wallets/health")
        d = r.json()
        assert d["ok"] is True

    @pytest.mark.parametrize("chain_id", CHAINS)
    def test_wallets_tokens(self, chain_id):
        r = requests.get(f"{BASE}/wallets/tokens", params={
            "address": TEST_ADDR, "chainId": chain_id, "window": "7d"
        })
        d = r.json()
        assert d["ok"] is True
        assert "items" in d
        assert isinstance(d["items"], list)
        no_nan(d)

    @pytest.mark.parametrize("chain_id", CHAINS)
    def test_wallets_counterparties(self, chain_id):
        r = requests.get(f"{BASE}/wallets/counterparties", params={
            "address": TEST_ADDR, "chainId": chain_id, "window": "7d"
        })
        d = r.json()
        assert d["ok"] is True
        assert "items" in d
        no_nan(d)

    def test_wallets_tokens_missing_address(self):
        r = requests.get(f"{BASE}/wallets/tokens", params={
            "chainId": 1, "window": "7d"
        })
        d = r.json()
        assert d["ok"] is False
        assert d["error"] == "MISSING_ADDRESS"

    def test_wallets_profile(self):
        r = requests.get(f"{BASE}/wallets/profile", params={
            "address": TEST_ADDR, "window": "7d"
        })
        d = r.json()
        assert d["ok"] is True
        assert "totals" in d
        no_nan(d)

    def test_wallets_series(self):
        r = requests.get(f"{BASE}/wallets/series", params={
            "address": TEST_ADDR, "window": "7d", "metric": "netUsd"
        })
        d = r.json()
        assert d["ok"] is True
        no_nan(d)


# ═══════════════════════════════════════════════════════
# ENGINE
# ═══════════════════════════════════════════════════════

class TestEngineEndpoints:
    def test_projects_default(self):
        r = requests.get(f"{BASE}/engine/projects", params={
            "chainId": 1, "window": "7d"
        })
        d = r.json()
        assert d["ok"] is True
        assert "projects" in d
        no_nan(d)

    def test_projects_with_atTs(self):
        """BT2: engine/projects supports atTs for as-of ranking."""
        import time
        at_ts = int(time.time() * 1000)
        r = requests.get(f"{BASE}/engine/projects", params={
            "chainId": 1, "window": "24h", "atTs": at_ts
        })
        d = r.json()
        assert d["ok"] is True
        no_nan(d)

    @pytest.mark.parametrize("chain_id", CHAINS)
    def test_projects_multichain(self, chain_id):
        r = requests.get(f"{BASE}/engine/projects", params={
            "chainId": chain_id, "window": "7d"
        })
        d = r.json()
        assert d["ok"] is True
        no_nan(d)


# ═══════════════════════════════════════════════════════
# BACKTEST
# ═══════════════════════════════════════════════════════

class TestBacktestEndpoints:
    def test_backtest_run(self):
        r = requests.post(f"{BASE}/engine/backtest/run", json={
            "chainId": 1,
            "from": "2026-02-25",
            "to": "2026-02-26",
            "stepDays": 1,
            "window": "24h",
            "topK": 5,
            "mode": "BUY_ONLY",
            "horizons": [7]
        })
        d = r.json()
        assert d["ok"] is True
        s = d["summary"]
        assert "points" in s
        assert "actionableRate" in s
        assert "coverage" in s
        assert "byH" in s
        assert "table" in s
        assert "dataWarning" in s
        no_nan(d)

    def test_backtest_buy_neutral(self):
        r = requests.post(f"{BASE}/engine/backtest/run", json={
            "chainId": 1,
            "from": "2026-02-25",
            "to": "2026-02-26",
            "stepDays": 1,
            "window": "24h",
            "topK": 5,
            "mode": "BUY_NEUTRAL",
            "horizons": [7, 14]
        })
        d = r.json()
        assert d["ok"] is True
        no_nan(d)

    def test_backtest_invalid_dates(self):
        r = requests.post(f"{BASE}/engine/backtest/run", json={})
        assert r.status_code == 400
        d = r.json()
        assert d["ok"] is False
        assert d["error"] == "INVALID_DATES"

    def test_backtest_last(self):
        r = requests.get(f"{BASE}/engine/backtest/last", params={"chainId": 1})
        d = r.json()
        assert d["ok"] is True
        assert "runs" in d
        assert isinstance(d["runs"], list)

    def test_backtest_multichain(self):
        """Backtest works on OP chain too."""
        r = requests.post(f"{BASE}/engine/backtest/run", json={
            "chainId": 10,
            "from": "2026-02-25",
            "to": "2026-02-26",
            "stepDays": 1,
            "window": "24h",
            "topK": 5,
            "mode": "BUY_ONLY",
            "horizons": [7]
        })
        d = r.json()
        assert d["ok"] is True
        no_nan(d)


# ═══════════════════════════════════════════════════════
# ALTFLOW & MARKET
# ═══════════════════════════════════════════════════════

class TestMarketEndpoints:
    def test_altflow(self):
        r = requests.get(f"{BASE}/market/altflow", params={
            "chainId": 1, "window": "24h"
        })
        d = r.json()
        assert d["ok"] is True
        no_nan(d)

    def test_token_suggest(self):
        r = requests.get(f"{BASE}/market/tokens/suggest", params={
            "chainId": 1, "q": "weth"
        })
        d = r.json()
        assert d["ok"] is True

    @pytest.mark.parametrize("chain_id", [1, 10, 8453])
    def test_token_suggest_multichain(self, chain_id):
        r = requests.get(f"{BASE}/market/tokens/suggest", params={
            "chainId": chain_id, "q": "weth"
        })
        d = r.json()
        assert d["ok"] is True


# ═══════════════════════════════════════════════════════
# CROSS-CHAIN CONTAMINATION
# ═══════════════════════════════════════════════════════

class TestCrossChainSafety:
    def test_no_contamination_wallets(self):
        """ETH wallet data should NOT appear when querying chainId=8453."""
        r_eth = requests.get(f"{BASE}/wallets/tokens", params={
            "address": TEST_ADDR, "chainId": 1, "window": "30d"
        })
        r_base = requests.get(f"{BASE}/wallets/tokens", params={
            "address": TEST_ADDR, "chainId": 8453, "window": "30d"
        })
        eth_items = r_eth.json().get("items", [])
        base_items = r_base.json().get("items", [])
        # If ETH has data, Base should be empty (different chains)
        if len(eth_items) > 0:
            assert len(base_items) == 0, "Cross-chain contamination: ETH data in Base"


# ═══════════════════════════════════════════════════════
# INVARIANTS
# ═══════════════════════════════════════════════════════

class TestInvariants:
    def test_no_negative_volumes(self):
        """Wallet tokens should not have negative transfers count."""
        r = requests.get(f"{BASE}/wallets/tokens", params={
            "address": TEST_ADDR, "chainId": 1, "window": "30d"
        })
        for item in r.json().get("items", []):
            assert item.get("transfers", 0) >= 0

    def test_confidence_range(self):
        """Engine projects confidence should be in [0, 1]."""
        r = requests.get(f"{BASE}/engine/projects", params={
            "chainId": 1, "window": "7d"
        })
        for p in r.json().get("projects", []):
            conf = p.get("confidence", 0)
            assert 0 <= conf <= 1, f"Confidence {conf} out of range for {p.get('symbol')}"

    def test_score_range(self):
        """Engine scores should be in [-1, 1]."""
        r = requests.get(f"{BASE}/engine/projects", params={
            "chainId": 1, "window": "7d"
        })
        for p in r.json().get("projects", []):
            score = p.get("score", 0)
            assert -1 <= score <= 1, f"Score {score} out of range for {p.get('symbol')}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
