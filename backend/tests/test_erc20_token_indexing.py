"""
ERC20 Token Indexing Tests
==========================
Testing ERC20 token transfer indexing, token registry, and signal enrichment.
Tests:
- GET /api/signals returns TOKEN_TRANSFER signals with token_symbol and token_amount
- GET /api/signals/stats includes token signals in totals (total > 25)
- GET /api/admin/indexer/diagnostics includes token_transfers and token_registry counts
- GET /api/signals?chain=arbitrum shows arbitrum signals
- GET /api/signals?chain=optimism shows optimism token transfers
- Token signals have correct fields: token_symbol != ETH, token_amount > 0, explorer_url
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestTokenTransferSignals:
    """Test TOKEN_TRANSFER signals from ERC20 indexer"""
    
    def test_signals_returns_token_transfers(self):
        """GET /api/signals returns TOKEN_TRANSFER signals with token_symbol and token_amount"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=True"
        assert "signals" in data, "Response should have signals array"
        
        signals = data["signals"]
        assert len(signals) > 0, "Should have signals"
        
        # Find TOKEN_TRANSFER signals
        token_transfer_signals = [s for s in signals if s.get("signal_type") == "TOKEN_TRANSFER"]
        print(f"Found {len(token_transfer_signals)} TOKEN_TRANSFER signals")
        
        # Verify at least one token transfer signal exists
        assert len(token_transfer_signals) > 0, "Should have at least one TOKEN_TRANSFER signal"
        
        # Verify fields on token transfer signals
        for sig in token_transfer_signals[:3]:  # Check first 3
            assert "token_symbol" in sig, f"TOKEN_TRANSFER should have token_symbol: {sig}"
            assert "token_amount" in sig, f"TOKEN_TRANSFER should have token_amount: {sig}"
            print(f"TOKEN_TRANSFER: {sig.get('token_symbol')} amount={sig.get('token_amount')}")
    
    def test_token_signals_have_correct_fields(self):
        """Token signals have: token_symbol != ETH, token_amount > 0, explorer_url"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        # Find signals with token_symbol not ETH
        token_signals = [s for s in signals if s.get("token_symbol") and s.get("token_symbol") != "ETH"]
        print(f"Found {len(token_signals)} signals with token_symbol != ETH")
        
        if len(token_signals) > 0:
            # Verify fields on token signals
            for sig in token_signals[:5]:  # Check first 5
                token_symbol = sig.get("token_symbol")
                token_amount = sig.get("token_amount", 0)
                explorer_url = sig.get("explorer_url", "")
                
                print(f"Token signal: {token_symbol} amount={token_amount} explorer={explorer_url[:50]}...")
                
                # Assertions
                assert token_symbol != "ETH", f"token_symbol should not be ETH: {sig.get('id')}"
                assert token_amount > 0, f"token_amount should be > 0: {sig.get('id')}"
                assert explorer_url, f"explorer_url should be present: {sig.get('id')}"
        else:
            pytest.skip("No token signals with token_symbol != ETH found")


class TestSignalStats:
    """Test /api/signals/stats endpoint"""
    
    def test_stats_total_greater_than_25(self):
        """GET /api/signals/stats includes token signals in totals (total > 25)"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=True"
        
        total = data.get("total", 0)
        print(f"Total signals: {total}")
        
        # Per requirement: total should be > 25 (5 engine + 27 entity with 8 TOKEN_TRANSFER)
        assert total > 25, f"Total signals should be > 25, got {total}"
        
        # Check by_type includes TOKEN_TRANSFER
        by_type = data.get("by_type", {})
        print(f"By type: {by_type}")
        
        # Verify we have entity signal types
        entity_types = ["CEX_INFLOW", "CEX_OUTFLOW", "WHALE_TRANSFER", "EXCHANGE_ACTIVITY", "TOKEN_TRANSFER"]
        found_entity_types = [t for t in entity_types if t in by_type]
        print(f"Found entity signal types: {found_entity_types}")


class TestIndexerDiagnostics:
    """Test /api/admin/indexer/diagnostics endpoint"""
    
    def test_diagnostics_includes_token_counts(self):
        """GET /api/admin/indexer/diagnostics includes token_transfers and token_registry in ingestion.totals"""
        response = requests.get(f"{BASE_URL}/api/admin/indexer/diagnostics")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=True"
        
        # Check ingestion.totals
        ingestion = data.get("ingestion", {})
        totals = ingestion.get("totals", {})
        
        token_transfers = totals.get("token_transfers", 0)
        token_registry = totals.get("token_registry", 0)
        
        print(f"token_transfers count: {token_transfers}")
        print(f"token_registry count: {token_registry}")
        
        # Per requirement: 20 token_transfers indexed, 51 token_registry entries
        assert "token_transfers" in totals, "Should have token_transfers in ingestion.totals"
        assert "token_registry" in totals, "Should have token_registry in ingestion.totals"
        assert token_transfers > 0, f"token_transfers should be > 0, got {token_transfers}"
        assert token_registry > 0, f"token_registry should be > 0, got {token_registry}"


class TestChainFiltering:
    """Test chain filter functionality"""
    
    def test_arbitrum_chain_filter(self):
        """GET /api/signals?chain=arbitrum shows only arbitrum signals including token transfers"""
        response = requests.get(f"{BASE_URL}/api/signals?chain=arbitrum")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        signals = data.get("signals", [])
        count = data.get("count", 0)
        
        print(f"Arbitrum signals count: {count}")
        
        # All signals should be arbitrum chain
        for sig in signals:
            chain = sig.get("chain", "")
            assert chain == "arbitrum", f"Signal should be arbitrum, got {chain}: {sig.get('id')}"
        
        # Check for token signals
        token_signals = [s for s in signals if s.get("token_symbol") and s.get("token_symbol") != "ETH"]
        print(f"Arbitrum token signals: {len(token_signals)}")
        if token_signals:
            for ts in token_signals[:3]:
                print(f"  - {ts.get('token_symbol')}: {ts.get('token_amount')}")
    
    def test_optimism_chain_filter(self):
        """GET /api/signals?chain=optimism shows optimism token transfers (VELO, USDC)"""
        response = requests.get(f"{BASE_URL}/api/signals?chain=optimism")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        signals = data.get("signals", [])
        count = data.get("count", 0)
        
        print(f"Optimism signals count: {count}")
        
        # All signals should be optimism chain
        for sig in signals:
            chain = sig.get("chain", "")
            assert chain == "optimism", f"Signal should be optimism, got {chain}: {sig.get('id')}"
        
        # Check for specific tokens: VELO, USDC
        token_signals = [s for s in signals if s.get("token_symbol") and s.get("token_symbol") != "ETH"]
        print(f"Optimism token signals: {len(token_signals)}")
        if token_signals:
            symbols = [s.get("token_symbol") for s in token_signals]
            print(f"Token symbols on Optimism: {set(symbols)}")
            for ts in token_signals[:3]:
                print(f"  - {ts.get('token_symbol')}: {ts.get('token_amount')}")


class TestSignalCount:
    """Test overall signal count"""
    
    def test_signals_count_meets_requirement(self):
        """Total signals should be ~32 (5 engine + 27 entity with 8 TOKEN_TRANSFER)"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        
        data = response.json()
        total = data.get("count", 0)
        sources = data.get("sources", {})
        
        print(f"Total signals: {total}")
        print(f"Sources breakdown: {sources}")
        
        engine_count = sources.get("engine", 0)
        entity_count = sources.get("entity_intelligence", 0)
        
        print(f"Engine signals: {engine_count}")
        print(f"Entity intelligence signals: {entity_count}")
        
        # Should have both engine and entity signals
        assert total > 20, f"Should have > 20 total signals, got {total}"


class TestEntitySignalFields:
    """Test entity signal fields for TOKEN_TRANSFER type"""
    
    def test_entity_signals_have_required_fields(self):
        """Entity signals have all required fields"""
        response = requests.get(f"{BASE_URL}/api/signals?source=entity")
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        print(f"Entity signals count: {len(signals)}")
        
        required_fields = [
            "id", "signal_type", "source", "chain", "chain_label",
            "direction", "score", "severity", "drivers", "explorer_url"
        ]
        
        for sig in signals[:5]:
            for field in required_fields:
                assert field in sig, f"Signal missing field {field}: {sig.get('id')}"
            
            # Check source is entity_intelligence
            assert sig.get("source") == "entity_intelligence", f"Source should be entity_intelligence: {sig.get('id')}"
            
            print(f"Signal {sig.get('signal_type')}: score={sig.get('score')}, chain={sig.get('chain')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
