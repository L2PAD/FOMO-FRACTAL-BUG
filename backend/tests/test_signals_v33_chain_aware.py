"""
Signals V3.3 Chain-Aware Backend Tests
======================================
Sprint 1: Network Guard (allowed chains: ethereum, arbitrum, optimism, base), remove BTC/SOL
Sprint 2: Chain-aware model with chain/source/evidence/provenance fields
Sprint 3: Explorer service, chain badges, evidence block with explorer links

Endpoints:
- GET /api/signals - unified signals stream (chain-aware)
- GET /api/signals/stats - signal summary statistics
- GET /api/signals/{id}/evolution - signal phase history
- GET /api/signals/chains - allowed EVM chains config
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ALLOWED_CHAINS = ["ethereum", "arbitrum", "optimism", "base"]


class TestSignalsChainAware:
    """Test Sprint 1-3: EVM-only chain-aware signals"""

    def test_signals_endpoint_returns_200(self):
        """GET /api/signals returns 200"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "signals" in data
        print(f"PASSED: GET /api/signals returns {len(data['signals'])} signals")

    def test_signals_asset_is_eth_not_btc(self):
        """Sprint 1: All signals have asset='ETH' (BTC removed)"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        signals = data.get("signals", [])
        
        for sig in signals:
            asset = sig.get("asset", "")
            assert asset == "ETH", f"Expected asset='ETH', got '{asset}'"
            assert asset != "BTC", f"BTC should be removed, found asset='{asset}'"
            assert asset != "SOL", f"SOL should be removed, found asset='{asset}'"
        
        print(f"PASSED: All {len(signals)} signals have asset='ETH' (no BTC/SOL)")

    def test_signals_have_chain_field(self):
        """Sprint 2: Each signal has 'chain' field set to allowed chain"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        signals = data.get("signals", [])
        
        for sig in signals:
            chain = sig.get("chain", "")
            assert chain != "", f"Signal {sig.get('id')} missing chain field"
            assert chain in ALLOWED_CHAINS, f"Invalid chain '{chain}', expected one of {ALLOWED_CHAINS}"
        
        print(f"PASSED: All {len(signals)} signals have valid chain field")

    def test_signals_have_chain_label_field(self):
        """Sprint 2: Each signal has 'chain_label' field (ETH, ARB, OP, BASE)"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        signals = data.get("signals", [])
        
        expected_labels = {"ETH", "ARB", "OP", "BASE"}
        for sig in signals:
            label = sig.get("chain_label", "")
            assert label != "", f"Signal {sig.get('id')} missing chain_label field"
            assert label in expected_labels, f"Invalid chain_label '{label}'"
        
        print(f"PASSED: All {len(signals)} signals have valid chain_label field")

    def test_signals_have_source_field(self):
        """Sprint 2: Each signal has 'source' field set to 'engine_analysis'"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        signals = data.get("signals", [])
        
        for sig in signals:
            source = sig.get("source", "")
            assert source != "", f"Signal {sig.get('id')} missing source field"
            assert source == "engine_analysis", f"Expected source='engine_analysis', got '{source}'"
        
        print(f"PASSED: All {len(signals)} signals have source='engine_analysis'")

    def test_signals_have_evidence_object(self):
        """Sprint 2: Each signal has 'evidence' object (may be empty)"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        signals = data.get("signals", [])
        
        for sig in signals:
            evidence = sig.get("evidence")
            assert evidence is not None, f"Signal {sig.get('id')} missing evidence field"
            assert isinstance(evidence, dict), f"Evidence should be dict, got {type(evidence)}"
        
        print(f"PASSED: All {len(signals)} signals have evidence object")

    def test_signals_have_provenance_object(self):
        """Sprint 2: Each signal has 'provenance' object with source/detection/module fields"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        signals = data.get("signals", [])
        
        for sig in signals:
            provenance = sig.get("provenance")
            assert provenance is not None, f"Signal {sig.get('id')} missing provenance field"
            assert isinstance(provenance, dict), f"Provenance should be dict, got {type(provenance)}"
            
            # Required fields
            assert "source" in provenance, f"Provenance missing 'source' field"
            assert "detection" in provenance, f"Provenance missing 'detection' field"
            assert "module" in provenance, f"Provenance missing 'module' field"
            
            # Verify values
            assert provenance["source"] == "engine_snapshot", f"Expected source='engine_snapshot', got '{provenance['source']}'"
        
        print(f"PASSED: All {len(signals)} signals have valid provenance object")


class TestSignalsChainsEndpoint:
    """Test GET /api/signals/chains endpoint"""

    def test_chains_endpoint_returns_200(self):
        """GET /api/signals/chains returns 200"""
        response = requests.get(f"{BASE_URL}/api/signals/chains")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASSED: GET /api/signals/chains returns 200")

    def test_chains_endpoint_returns_allowed_chains(self):
        """GET /api/signals/chains returns allowed_chains array"""
        response = requests.get(f"{BASE_URL}/api/signals/chains")
        assert response.status_code == 200
        data = response.json()
        
        allowed = data.get("allowed_chains", [])
        assert isinstance(allowed, list), f"allowed_chains should be list, got {type(allowed)}"
        assert len(allowed) == 4, f"Expected 4 allowed chains, got {len(allowed)}"
        assert set(allowed) == set(ALLOWED_CHAINS), f"Unexpected chains: {allowed}"
        
        print(f"PASSED: allowed_chains = {allowed}")

    def test_chains_endpoint_returns_chain_config(self):
        """GET /api/signals/chains returns chains config with id/label/color/explorer"""
        response = requests.get(f"{BASE_URL}/api/signals/chains")
        assert response.status_code == 200
        data = response.json()
        
        chains = data.get("chains", {})
        assert isinstance(chains, dict), f"chains should be dict, got {type(chains)}"
        
        for chain_id in ALLOWED_CHAINS:
            assert chain_id in chains, f"Missing chain config for '{chain_id}'"
            cfg = chains[chain_id]
            
            # Required fields
            assert "id" in cfg, f"Chain '{chain_id}' missing 'id'"
            assert "label" in cfg, f"Chain '{chain_id}' missing 'label'"
            assert "color" in cfg, f"Chain '{chain_id}' missing 'color'"
            assert "explorer" in cfg, f"Chain '{chain_id}' missing 'explorer'"
            
            # Verify explorer URLs
            assert cfg["explorer"].startswith("https://"), f"Explorer URL should start with https://"
        
        print(f"PASSED: chains config has all required fields for {list(chains.keys())}")


class TestSignalsFilters:
    """Test signals filters still work with new chain-aware model"""

    def test_direction_filter_bullish(self):
        """GET /api/signals?direction=BULLISH still works"""
        response = requests.get(f"{BASE_URL}/api/signals?direction=BULLISH")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        
        signals = data.get("signals", [])
        for sig in signals:
            assert sig.get("direction") == "BULLISH", f"Filter failed: got {sig.get('direction')}"
            # Still verify chain-aware fields
            assert sig.get("chain") in ALLOWED_CHAINS
        
        print(f"PASSED: direction=BULLISH filter returns {len(signals)} signals")

    def test_direction_filter_bearish(self):
        """GET /api/signals?direction=BEARISH still works"""
        response = requests.get(f"{BASE_URL}/api/signals?direction=BEARISH")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        
        signals = data.get("signals", [])
        for sig in signals:
            assert sig.get("direction") == "BEARISH", f"Filter failed: got {sig.get('direction')}"
        
        print(f"PASSED: direction=BEARISH filter returns {len(signals)} signals")


class TestSignalsStats:
    """Test GET /api/signals/stats still works"""

    def test_stats_endpoint_returns_200(self):
        """GET /api/signals/stats returns 200"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASSED: GET /api/signals/stats returns 200")

    def test_stats_has_required_fields(self):
        """Stats has total, strong, extreme, bullish, bearish fields"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        assert response.status_code == 200
        data = response.json()
        
        required = ["total", "strong", "extreme", "bullish", "bearish", "avg_score"]
        for field in required:
            assert field in data, f"Stats missing '{field}' field"
        
        print(f"PASSED: Stats has all required fields: {required}")


class TestSignalsEvolution:
    """Test GET /api/signals/{id}/evolution still works"""

    def test_evolution_endpoint_with_valid_id(self):
        """GET /api/signals/{id}/evolution returns 200"""
        # First get a signal ID
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        signals = data.get("signals", [])
        
        if not signals:
            pytest.skip("No signals available to test evolution")
        
        signal_id = signals[0].get("id")
        
        # Now test evolution endpoint
        evo_response = requests.get(f"{BASE_URL}/api/signals/{signal_id}/evolution")
        assert evo_response.status_code == 200
        evo_data = evo_response.json()
        assert evo_data.get("ok") == True
        assert "phases" in evo_data
        
        print(f"PASSED: GET /api/signals/{signal_id}/evolution returns {len(evo_data.get('phases', []))} phases")


class TestSignalFullStructure:
    """Test complete signal structure with all new fields"""

    def test_signal_has_all_chain_aware_fields(self):
        """Verify signal has all Sprint 1-3 fields"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        signals = data.get("signals", [])
        
        if not signals:
            pytest.skip("No signals available")
        
        sig = signals[0]
        
        # Sprint 1: Asset = ETH
        assert sig.get("asset") == "ETH", f"Expected ETH, got {sig.get('asset')}"
        
        # Sprint 2: Chain-aware fields
        assert "chain" in sig
        assert "chain_label" in sig
        assert "source" in sig
        assert "evidence" in sig
        assert "provenance" in sig
        
        # Verify chain is valid
        assert sig["chain"] in ALLOWED_CHAINS
        
        # Verify provenance structure
        prov = sig["provenance"]
        assert prov.get("source") == "engine_snapshot"
        assert prov.get("module") == "signal_engine_v3"
        
        print(f"PASSED: Signal {sig['id']} has all chain-aware fields")
        print(f"  - asset: {sig['asset']}")
        print(f"  - chain: {sig['chain']}")
        print(f"  - chain_label: {sig['chain_label']}")
        print(f"  - source: {sig['source']}")
        print(f"  - evidence: {sig['evidence']}")
        print(f"  - provenance: {sig['provenance']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
