"""
Signal Enrichment Tests
=======================
Tests for unified signals endpoint with entity intelligence integration.

Features tested:
- GET /api/signals returns unified signals from both engine_analysis and entity_intelligence
- GET /api/signals?source=entity returns only entity signals with proper fields
- GET /api/signals/stats returns correct unified stats
- Entity signals have: entity, from_entity, to_entity, amount_eth, cluster_score, drivers (array), evidence with explorer links
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSignalsUnified:
    """Test unified signals endpoint (engine + entity_intelligence)"""

    def test_signals_returns_both_sources(self):
        """GET /api/signals returns signals from both engine_analysis and entity_intelligence"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "signals" in data
        assert "count" in data
        assert "sources" in data
        
        sources = data["sources"]
        assert "engine" in sources
        assert "entity_intelligence" in sources
        
        # Should have signals from both sources
        signals = data["signals"]
        engine_signals = [s for s in signals if s.get("source") != "entity_intelligence"]
        entity_signals = [s for s in signals if s.get("source") == "entity_intelligence"]
        
        print(f"Total signals: {len(signals)}")
        print(f"Engine signals: {len(engine_signals)}")
        print(f"Entity signals: {len(entity_signals)}")

    def test_signals_source_entity_filter(self):
        """GET /api/signals?source=entity returns only entity intelligence signals"""
        response = requests.get(f"{BASE_URL}/api/signals?source=entity")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        signals = data["signals"]
        # All signals should be from entity_intelligence
        for sig in signals:
            assert sig.get("source") == "entity_intelligence", f"Expected entity_intelligence source, got {sig.get('source')}"
            
    def test_signals_source_engine_filter(self):
        """GET /api/signals?source=engine returns only engine signals"""
        response = requests.get(f"{BASE_URL}/api/signals?source=engine")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        signals = data["signals"]
        # All signals should be from engine_analysis
        for sig in signals:
            assert sig.get("source") != "entity_intelligence", f"Expected engine source, got {sig.get('source')}"


class TestEntitySignalFields:
    """Test entity intelligence signal fields"""
    
    def test_entity_signal_has_required_fields(self):
        """Entity signals have all required fields: entity, from_entity, to_entity, amount_eth, cluster_score, drivers, evidence"""
        response = requests.get(f"{BASE_URL}/api/signals?source=entity")
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        if not signals:
            pytest.skip("No entity signals available")
            
        for sig in signals:
            # Entity identification fields
            assert "entity" in sig, "Missing entity field"
            assert "from_entity" in sig, "Missing from_entity field"
            assert "to_entity" in sig, "Missing to_entity field"
            assert "entity_type" in sig, "Missing entity_type field"
            
            # Amount and cluster score
            assert "amount_eth" in sig, "Missing amount_eth field"
            assert "cluster_score" in sig, "Missing cluster_score field"
            assert isinstance(sig["cluster_score"], int), f"cluster_score should be int, got {type(sig['cluster_score'])}"
            
            # Signal type should be entity-specific
            valid_entity_types = {"CEX_INFLOW", "CEX_OUTFLOW", "WHALE_TRANSFER", "EXCHANGE_ACTIVITY", "SMART_MONEY_ACTIVITY", "MM_ACTIVITY"}
            assert sig.get("signal_type") in valid_entity_types, f"Unexpected signal type: {sig.get('signal_type')}"
    
    def test_entity_signal_drivers_is_array(self):
        """Entity signals have drivers as array of strings, not object"""
        response = requests.get(f"{BASE_URL}/api/signals?source=entity")
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        if not signals:
            pytest.skip("No entity signals available")
            
        for sig in signals:
            drivers = sig.get("drivers")
            assert drivers is not None, "Missing drivers field"
            assert isinstance(drivers, list), f"drivers should be list, got {type(drivers)}"
            
            # Each driver should be a string
            for d in drivers:
                assert isinstance(d, str), f"driver should be string, got {type(d)}"
                
            # Should also have driver_labels
            driver_labels = sig.get("driver_labels", [])
            assert isinstance(driver_labels, list), "driver_labels should be list"
            assert len(driver_labels) == len(drivers), "driver_labels length should match drivers"
            
    def test_entity_signal_evidence_has_explorer_links(self):
        """Entity signals have evidence with wallet_link and tx_link"""
        response = requests.get(f"{BASE_URL}/api/signals?source=entity")
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        if not signals:
            pytest.skip("No entity signals available")
            
        for sig in signals:
            evidence = sig.get("evidence")
            assert evidence is not None, "Missing evidence field"
            assert "tx_hash" in evidence or "wallet" in evidence, "Evidence should have tx_hash or wallet"
            
            # Check for explorer links
            assert "tx_link" in evidence or "explorer_url" in evidence, "Evidence should have tx_link or explorer_url"
            assert "wallet_link" in evidence, "Evidence should have wallet_link"
            assert "chain" in evidence, "Evidence should have chain"

    def test_entity_signal_explorer_from_to_fields(self):
        """Entity signals have explorer_from and explorer_to fields"""
        response = requests.get(f"{BASE_URL}/api/signals?source=entity")
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        if not signals:
            pytest.skip("No entity signals available")
            
        for sig in signals:
            assert "explorer_from" in sig, "Missing explorer_from field"
            assert "explorer_to" in sig, "Missing explorer_to field"


class TestSignalStats:
    """Test unified signal stats endpoint"""
    
    def test_stats_returns_unified_totals(self):
        """GET /api/signals/stats returns stats for all signals (engine + entity)"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        # Basic stats fields
        assert "total" in data
        assert "strong" in data
        assert "extreme" in data
        assert "bullish" in data
        assert "bearish" in data
        assert "avg_score" in data
        assert "by_type" in data
        
        # Cluster info
        assert "cluster_count" in data
        assert "max_cluster_score" in data
        
    def test_stats_total_matches_signals_count(self):
        """Stats total should match the count of all signals"""
        # Get stats
        stats_response = requests.get(f"{BASE_URL}/api/signals/stats")
        stats = stats_response.json()
        
        # Get all signals
        signals_response = requests.get(f"{BASE_URL}/api/signals")
        signals = signals_response.json()
        
        # Stats total should be close to signals count (may vary slightly due to timing)
        stats_total = stats.get("total", 0)
        signals_count = signals.get("count", 0)
        
        print(f"Stats total: {stats_total}, Signals count: {signals_count}")
        
        # Allow for small variance due to timing
        assert abs(stats_total - signals_count) <= 2, f"Stats total ({stats_total}) should be close to signals count ({signals_count})"
        
    def test_stats_by_type_includes_entity_types(self):
        """Stats by_type should include entity signal types"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        data = response.json()
        
        by_type = data.get("by_type", {})
        
        # Entity signal types
        entity_types = {"CEX_INFLOW", "CEX_OUTFLOW", "WHALE_TRANSFER", "EXCHANGE_ACTIVITY", "SMART_MONEY_ACTIVITY", "MM_ACTIVITY"}
        
        # Check if any entity types are in by_type
        found_entity_types = entity_types.intersection(set(by_type.keys()))
        
        print(f"Signal types in stats: {list(by_type.keys())}")
        print(f"Entity types found: {found_entity_types}")
        
        # Should have at least one entity type if entity signals exist
        entity_response = requests.get(f"{BASE_URL}/api/signals?source=entity")
        entity_count = entity_response.json().get("count", 0)
        
        if entity_count > 0:
            assert len(found_entity_types) > 0, "Stats should include entity signal types when entity signals exist"


class TestEngineSignalFields:
    """Test engine analysis signal fields for comparison"""
    
    def test_engine_signal_drivers_is_object(self):
        """Engine signals have drivers as object {key: value}, not array"""
        response = requests.get(f"{BASE_URL}/api/signals?source=engine")
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        if not signals:
            pytest.skip("No engine signals available")
            
        for sig in signals:
            drivers = sig.get("drivers")
            assert drivers is not None, "Missing drivers field"
            assert isinstance(drivers, dict), f"Engine drivers should be dict, got {type(drivers)}"
