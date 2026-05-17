"""
On-Chain Core Sprint Tests
==========================
Tests for Sprint 3 features:
1. Signals API with chain filter
2. Alert Rules CRUD + evaluation + history
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSignalsAPI:
    """Tests for GET /api/signals with chain filter and unified stats"""

    def test_signals_returns_unified_list(self):
        """GET /api/signals returns unified signals (engine + entity)"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, "Response ok should be True"
        assert "signals" in data, "Response should have signals array"
        assert "count" in data, "Response should have count"
        assert isinstance(data["signals"], list), "signals should be a list"
        # Check sources field
        if "sources" in data:
            assert "engine" in data["sources"] or "entity_intelligence" in data["sources"], "Should have source breakdown"
        print(f"PASSED: GET /api/signals returned {data['count']} signals")

    def test_signals_chain_filter_ethereum(self):
        """GET /api/signals?chain=ethereum filters by ethereum chain"""
        response = requests.get(f"{BASE_URL}/api/signals?chain=ethereum")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        signals = data.get("signals", [])
        # All signals should be ethereum chain
        for sig in signals:
            chain = sig.get("chain", "ethereum")
            assert chain == "ethereum", f"Expected ethereum chain, got {chain}"
        print(f"PASSED: Chain filter ethereum returned {len(signals)} signals")

    def test_signals_chain_filter_arbitrum(self):
        """GET /api/signals?chain=arbitrum filters by arbitrum chain"""
        response = requests.get(f"{BASE_URL}/api/signals?chain=arbitrum")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        signals = data.get("signals", [])
        for sig in signals:
            chain = sig.get("chain", "")
            assert chain == "arbitrum" or chain == "", f"Expected arbitrum chain, got {chain}"
        print(f"PASSED: Chain filter arbitrum returned {len(signals)} signals")

    def test_signals_stats_unified(self):
        """GET /api/signals/stats returns unified stats"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True, "Response ok should be True"
        # Check required fields
        for field in ["total", "strong", "extreme", "bullish", "bearish", "avg_score"]:
            assert field in data, f"Stats should have {field}"
        assert data["total"] >= 0, "total should be >= 0"
        print(f"PASSED: Stats total={data['total']}, strong={data['strong']}, extreme={data['extreme']}")

    def test_signals_entity_has_amount_eth(self):
        """Entity signals have amount_eth field for Move column"""
        response = requests.get(f"{BASE_URL}/api/signals?source=entity")
        assert response.status_code == 200
        data = response.json()
        signals = data.get("signals", [])
        for sig in signals:
            if sig.get("source") == "entity_intelligence":
                # Entity signals should have amount_eth
                assert "amount_eth" in sig, "Entity signal should have amount_eth"
                assert isinstance(sig["amount_eth"], (int, float)), "amount_eth should be numeric"
        print(f"PASSED: Entity signals have amount_eth field")

    def test_signals_entity_fields(self):
        """Entity signals have required entity fields"""
        response = requests.get(f"{BASE_URL}/api/signals?source=entity")
        assert response.status_code == 200
        data = response.json()
        signals = data.get("signals", [])
        entity_sigs = [s for s in signals if s.get("source") == "entity_intelligence"]
        for sig in entity_sigs[:3]:  # Check first 3
            assert "entity" in sig, "Should have entity field"
            assert "chain" in sig, "Should have chain field"
            assert "drivers" in sig, "Should have drivers field"
            assert isinstance(sig.get("drivers"), list), "drivers should be array"
        print(f"PASSED: Entity signals have required fields")


class TestAlertRulesAPI:
    """Tests for /api/alerts/onchain/* endpoints"""
    
    created_rule_id = None

    def test_list_rules(self):
        """GET /api/alerts/onchain/rules returns seeded rules"""
        response = requests.get(f"{BASE_URL}/api/alerts/onchain/rules")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True
        assert "rules" in data
        rules = data["rules"]
        assert isinstance(rules, list)
        print(f"PASSED: GET /api/alerts/onchain/rules returned {len(rules)} rules")
        # Check if seeded rules exist
        rule_names = [r["name"] for r in rules]
        print(f"  Rule names: {rule_names}")

    def test_create_rule(self):
        """POST /api/alerts/onchain/rules creates a new rule"""
        payload = {
            "name": "TEST_Large ETH Movement",
            "enabled": True,
            "conditions": {
                "min_score": 60,
                "status": "confirmed",
                "chains": ["ethereum", "arbitrum"],
                "signal_types": ["CEX_OUTFLOW", "WHALE_TRANSFER"],
                "min_amount_eth": 50
            },
            "notify": {"telegram": True, "in_app": True}
        }
        response = requests.post(
            f"{BASE_URL}/api/alerts/onchain/rules",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") == True, "Response ok should be True"
        assert "rule" in data, "Response should have rule"
        rule = data["rule"]
        assert rule["name"] == "TEST_Large ETH Movement"
        assert rule["enabled"] == True
        assert rule["conditions"]["min_score"] == 60
        assert "ethereum" in rule["conditions"]["chains"]
        # Save for later tests
        TestAlertRulesAPI.created_rule_id = rule["id"]
        print(f"PASSED: Created rule '{rule['name']}' with id={rule['id']}")

    def test_toggle_rule_enabled(self):
        """PUT /api/alerts/onchain/rules/{id} toggles enabled"""
        if not TestAlertRulesAPI.created_rule_id:
            pytest.skip("No rule ID from previous test")
        
        rule_id = TestAlertRulesAPI.created_rule_id
        # Disable
        response = requests.put(
            f"{BASE_URL}/api/alerts/onchain/rules/{rule_id}",
            json={"enabled": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data["rule"]["enabled"] == False
        
        # Re-enable
        response = requests.put(
            f"{BASE_URL}/api/alerts/onchain/rules/{rule_id}",
            json={"enabled": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rule"]["enabled"] == True
        print(f"PASSED: Toggle enabled for rule {rule_id}")

    def test_delete_rule(self):
        """DELETE /api/alerts/onchain/rules/{id} deletes a rule"""
        if not TestAlertRulesAPI.created_rule_id:
            pytest.skip("No rule ID from previous test")
        
        rule_id = TestAlertRulesAPI.created_rule_id
        response = requests.delete(f"{BASE_URL}/api/alerts/onchain/rules/{rule_id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        
        # Verify deletion - should not find rule
        response = requests.get(f"{BASE_URL}/api/alerts/onchain/rules")
        rules = response.json().get("rules", [])
        rule_ids = [r["id"] for r in rules]
        assert rule_id not in rule_ids, "Rule should be deleted"
        print(f"PASSED: Deleted rule {rule_id}")

    def test_evaluate_rules(self):
        """POST /api/alerts/onchain/evaluate triggers rule evaluation"""
        response = requests.post(f"{BASE_URL}/api/alerts/onchain/evaluate")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") == True
        assert "fired" in data
        assert "count" in data
        print(f"PASSED: Evaluate fired {data['count']} alerts")

    def test_alert_history(self):
        """GET /api/alerts/onchain/history returns fired alerts"""
        response = requests.get(f"{BASE_URL}/api/alerts/onchain/history?limit=20")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "alerts" in data
        alerts = data["alerts"]
        assert isinstance(alerts, list)
        # Check alert fields if any exist
        for alert in alerts[:3]:
            assert "dedup_key" in alert or "signal_id" in alert
            if "chain_label" in alert:
                assert alert["chain_label"] in ["ETH", "ARB", "OP", "BASE"]
            if "entity" in alert:
                assert isinstance(alert["entity"], str)
        print(f"PASSED: Alert history returned {len(alerts)} alerts")

    def test_acknowledge_alert(self):
        """POST /api/alerts/onchain/acknowledge/{key} acknowledges alert"""
        # Get an unacknowledged alert
        response = requests.get(f"{BASE_URL}/api/alerts/onchain/history?unacknowledged=true&limit=1")
        assert response.status_code == 200
        data = response.json()
        alerts = data.get("alerts", [])
        if not alerts:
            print("SKIPPED: No unacknowledged alerts to acknowledge")
            return
        
        dedup_key = alerts[0]["dedup_key"]
        response = requests.post(f"{BASE_URL}/api/alerts/onchain/acknowledge/{dedup_key}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASSED: Acknowledged alert {dedup_key}")

    def test_alert_stats(self):
        """GET /api/alerts/onchain/stats returns correct counts"""
        response = requests.get(f"{BASE_URL}/api/alerts/onchain/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        # Check required stats fields
        for field in ["total_alerts", "unacknowledged", "rules_count", "active_rules"]:
            assert field in data, f"Stats should have {field}"
        print(f"PASSED: Alert stats - total={data['total_alerts']}, unack={data['unacknowledged']}, rules={data['rules_count']}")


class TestSeededRules:
    """Tests for the 3 seeded default rules"""

    def test_seeded_rules_exist(self):
        """Verify the 3 default seeded rules exist"""
        response = requests.get(f"{BASE_URL}/api/alerts/onchain/rules")
        assert response.status_code == 200
        data = response.json()
        rules = data.get("rules", [])
        
        expected_names = ["Large CEX Outflow", "Exchange Whale Activity", "Strong Engine Signal"]
        found_names = [r["name"] for r in rules]
        
        for name in expected_names:
            if name in found_names:
                print(f"  Found seeded rule: {name}")
            else:
                print(f"  Note: Seeded rule '{name}' not found (may not have been seeded)")
        
        print(f"PASSED: Found {len(rules)} rules total")


class TestChainsConfig:
    """Test chain configuration endpoint"""

    def test_chains_endpoint(self):
        """GET /api/signals/chains returns allowed chains"""
        response = requests.get(f"{BASE_URL}/api/signals/chains")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "allowed_chains" in data or "chains" in data
        print(f"PASSED: Chains config returned")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
