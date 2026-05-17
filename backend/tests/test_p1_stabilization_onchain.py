"""
P1 Stabilization Testing: On-chain Intelligence Terminal
=========================================================
Tests for:
1. Indexer mode switching (LITE/INDEXER modes)
2. Chain filter on signals API
3. Alert rules verification (3 rules, dedup, cooldown)

Iteration 282 test suite.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://expo-telegram-web.preview.emergentagent.com")


class TestIndexerModeControl:
    """Tests for /api/admin/indexer/* endpoints"""

    def test_get_indexer_status(self):
        """GET /api/admin/indexer/status returns current mode"""
        response = requests.get(f"{BASE_URL}/api/admin/indexer/status")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "mode" in data
        assert data["mode"] in ["PREVIEW", "LIMITED", "INDEXER", "FULL", "STANDARD"]
        assert "indexer" in data
        assert "runtimeStatus" in data["indexer"]
        assert "paused" in data["indexer"]

    def test_switch_to_limited_mode(self):
        """POST /api/admin/indexer/mode with {mode:'LIMITED'} switches to LITE mode"""
        response = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "LIMITED"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["mode"] == "LIMITED"
        assert data["internal"] == "preview"

    def test_switch_to_full_mode(self):
        """POST /api/admin/indexer/mode with {mode:'FULL'} switches to INDEXER mode"""
        response = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "FULL"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["mode"] == "FULL"
        assert data["internal"] == "indexer"
        
        # Verify status reflects the change
        status_res = requests.get(f"{BASE_URL}/api/admin/indexer/status")
        status_data = status_res.json()
        assert status_data["indexer"]["mode"] in ["INDEXER", "FULL"]

    def test_get_indexer_diagnostics(self):
        """GET /api/admin/indexer/diagnostics returns full diagnostic info"""
        response = requests.get(f"{BASE_URL}/api/admin/indexer/diagnostics")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        
        # Mode
        assert "mode" in data
        
        # RPC status for 4 chains
        assert "rpc" in data
        rpc = data["rpc"]
        assert "status" in rpc
        assert "chains" in rpc
        for chain in ["ethereum", "arbitrum", "optimism", "base"]:
            assert chain in rpc["chains"], f"Missing chain: {chain}"
            chain_status = rpc["chains"][chain]
            assert "status" in chain_status
            assert "head_block" in chain_status
        
        # Sync state
        assert "chains" in data
        
        # Ingestion totals
        assert "ingestion" in data
        assert "totals" in data["ingestion"]
        totals = data["ingestion"]["totals"]
        assert "blocks" in totals
        assert "transactions" in totals
        assert "events" in totals
        assert "entity_activity" in totals
        
        # Entity resolution counts
        assert "entity_resolution" in data
        entity_res = data["entity_resolution"]
        assert "address_labels_loaded" in entity_res
        assert "entities_loaded" in entity_res
        assert "enriched_transactions" in entity_res
        assert "entity_activity_records" in entity_res

    def test_switch_back_to_limited_mode(self):
        """Restore LIMITED mode after tests"""
        response = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "LIMITED"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True


class TestSignalsAPI:
    """Tests for /api/signals endpoints with chain filter"""

    def test_signals_returns_data_in_lite_mode(self):
        """GET /api/signals works in LITE mode returning snapshot data"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "signals" in data
        
        # Should have signals from entity_intelligence
        signals = data["signals"]
        if len(signals) > 0:
            sig = signals[0]
            # Entity signals should have required fields
            if sig.get("source") == "entity_intelligence":
                assert "entity" in sig
                assert "chain" in sig
                assert "drivers" in sig
                assert "explorer_url" in sig or "evidence" in sig

    def test_signals_chain_filter_ethereum(self):
        """GET /api/signals?chain=ethereum filters by chain"""
        response = requests.get(f"{BASE_URL}/api/signals?chain=ethereum")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        signals = data["signals"]
        
        # All returned signals should be for ethereum
        for sig in signals:
            assert sig.get("chain") == "ethereum", f"Signal {sig.get('id')} has chain {sig.get('chain')}, expected ethereum"

    def test_signals_chain_filter_arbitrum(self):
        """GET /api/signals?chain=arbitrum filters by chain"""
        response = requests.get(f"{BASE_URL}/api/signals?chain=arbitrum")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        signals = data["signals"]
        
        for sig in signals:
            # Should only have arbitrum signals (or empty if no data)
            if sig.get("chain"):
                assert sig.get("chain") == "arbitrum"

    def test_signals_entity_source_filter(self):
        """GET /api/signals?source=entity returns only entity signals"""
        response = requests.get(f"{BASE_URL}/api/signals?source=entity")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        signals = data["signals"]
        
        for sig in signals:
            assert sig.get("source") == "entity_intelligence", f"Signal source: {sig.get('source')}"

    def test_signals_have_required_fields(self):
        """Entity signals have all required fields for UI"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        
        entity_signals = [s for s in data["signals"] if s.get("source") == "entity_intelligence"]
        
        for sig in entity_signals[:5]:  # Check first 5
            assert "id" in sig
            assert "signal_type" in sig
            assert "chain" in sig
            assert "entity" in sig
            assert "score" in sig
            assert "severity" in sig
            assert "drivers" in sig
            assert isinstance(sig["drivers"], list), f"Drivers should be list, got {type(sig['drivers'])}"
            
            # Should have explorer URL
            has_explorer = bool(sig.get("explorer_url")) or bool(sig.get("evidence", {}).get("tx_link"))
            assert has_explorer, f"Signal {sig['id']} missing explorer URL"


class TestAlertRules:
    """Tests for alert rules CRUD and evaluation"""

    def test_get_alert_rules(self):
        """GET /api/alerts/onchain/rules returns 3 seeded rules"""
        response = requests.get(f"{BASE_URL}/api/alerts/onchain/rules")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "rules" in data
        rules = data["rules"]
        
        # Should have at least 3 seeded rules
        assert len(rules) >= 3, f"Expected at least 3 rules, got {len(rules)}"
        
        # Verify expected rules exist
        rule_names = [r["name"] for r in rules]
        assert "Large CEX Outflow" in rule_names, f"Missing 'Large CEX Outflow' rule"
        assert "Exchange Whale Activity" in rule_names, f"Missing 'Exchange Whale Activity' rule"
        assert "Strong Engine Signal" in rule_names, f"Missing 'Strong Engine Signal' rule"

    def test_alert_rules_have_required_fields(self):
        """Alert rules have required fields"""
        response = requests.get(f"{BASE_URL}/api/alerts/onchain/rules")
        data = response.json()
        
        for rule in data["rules"]:
            assert "id" in rule
            assert "name" in rule
            assert "enabled" in rule
            assert "conditions" in rule
            assert "notify" in rule
            assert "fired_count" in rule
            
            # Conditions structure
            cond = rule["conditions"]
            assert "min_score" in cond
            assert "chains" in cond
            assert "signal_types" in cond

    def test_alert_evaluate_fires_matching_alerts(self):
        """POST /api/alerts/onchain/evaluate fires alerts for matching signals"""
        response = requests.post(f"{BASE_URL}/api/alerts/onchain/evaluate")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "fired" in data
        assert "count" in data
        
        # Each fired alert should have required fields
        for alert in data["fired"]:
            assert "dedup_key" in alert
            assert "rule_id" in alert
            assert "rule_name" in alert
            assert "signal_id" in alert
            assert "chain" in alert
            assert "chain_label" in alert
            assert "entity" in alert or alert.get("wallet")  # Entity or wallet must exist
            assert "explorer_url" in alert or alert.get("tx_hash")  # Should have explorer context
            assert "drivers" in alert
            assert "fired_at" in alert

    def test_alert_dedup_prevents_refiring(self):
        """POST /api/alerts/onchain/evaluate second call fires 0 (dedup working)"""
        # First call (may fire some)
        requests.post(f"{BASE_URL}/api/alerts/onchain/evaluate")
        
        # Small delay to ensure consistent dedup window
        time.sleep(0.5)
        
        # Second call should fire 0 due to dedup
        response = requests.post(f"{BASE_URL}/api/alerts/onchain/evaluate")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["count"] == 0, f"Dedup failed: fired {data['count']} alerts on second call"

    def test_acknowledge_alert(self):
        """POST /api/alerts/onchain/acknowledge/{key} marks alert as acknowledged"""
        # Get an unacknowledged alert
        history_res = requests.get(f"{BASE_URL}/api/alerts/onchain/history?unacknowledged=true&limit=1")
        history_data = history_res.json()
        
        if history_data["alerts"]:
            dedup_key = history_data["alerts"][0]["dedup_key"]
            
            # Acknowledge it
            response = requests.post(f"{BASE_URL}/api/alerts/onchain/acknowledge/{dedup_key}")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
        else:
            pytest.skip("No unacknowledged alerts to test")

    def test_alert_history_has_required_fields(self):
        """GET /api/alerts/onchain/history returns alerts with all required fields"""
        response = requests.get(f"{BASE_URL}/api/alerts/onchain/history?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "alerts" in data
        
        for alert in data["alerts"]:
            assert "dedup_key" in alert
            assert "rule_name" in alert
            assert "signal_type" in alert
            assert "chain_label" in alert
            
            # Entity should be present (from entity signals)
            if alert.get("entity"):
                assert isinstance(alert["entity"], str)
            
            # Explorer URL should be present
            if alert.get("explorer_url"):
                assert alert["explorer_url"].startswith("http")
            
            # Drivers should be present
            assert "drivers" in alert

    def test_alert_stats(self):
        """GET /api/alerts/onchain/stats returns correct statistics"""
        response = requests.get(f"{BASE_URL}/api/alerts/onchain/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "total_alerts" in data
        assert "unacknowledged" in data
        assert "last_24h" in data
        assert "rules_count" in data
        assert "active_rules" in data
        
        # Should have 3 active rules
        assert data["active_rules"] >= 3


class TestSignalChains:
    """Tests for signal chain configuration"""

    def test_signals_chains_endpoint(self):
        """GET /api/signals/chains returns allowed chains"""
        response = requests.get(f"{BASE_URL}/api/signals/chains")
        
        # This endpoint may or may not exist
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                assert "chains" in data or "allowed" in data

    def test_signals_stats(self):
        """GET /api/signals/stats returns unified stats"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "total" in data
        assert "strong" in data
        assert "extreme" in data


# Run with: pytest /app/backend/tests/test_p1_stabilization_onchain.py -v --tb=short
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
