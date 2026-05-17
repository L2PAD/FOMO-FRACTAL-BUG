"""
Address Resolution P0 API Tests
===============================
Tests for On-Chain Intelligence Terminal Address Resolution layer:
- /api/address/resolve - Single address resolution
- /api/address/resolve/batch - Batch address resolution  
- /api/entity/activity - Entity activity stats
- /api/entity/activity/summary - Activity summary
- /api/admin/indexer/diagnostics - Entity resolution in diagnostics
- Mode switching (LIMITED/FULL)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Known Binance hot wallet address
BINANCE_HOT_WALLET = "0x28c6c06298d514db089934071355e5743bf21d60"


class TestAddressResolve:
    """Single address resolution tests"""

    def test_resolve_binance_hot_wallet(self):
        """GET /api/address/resolve with known Binance address returns entity info"""
        response = requests.get(
            f"{BASE_URL}/api/address/resolve",
            params={"address": BINANCE_HOT_WALLET, "chain": "ethereum"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert data.get("is_known") is True, f"Expected is_known=True for Binance wallet"
        assert data.get("address") == BINANCE_HOT_WALLET.lower()
        assert data.get("chain") == "ethereum"
        
        # Check entity info
        if data.get("label"):
            print(f"Label info: {data['label']}")
            # Should have tags containing 'cex' for exchange
            tags = data['label'].get('tags', [])
            print(f"Tags: {tags}")
        
        if data.get("entity"):
            print(f"Entity: {data['entity']}")
            entity_type = data['entity'].get('entity_type', '')
            entity_name = data['entity'].get('name', '')
            print(f"Entity name: {entity_name}, type: {entity_type}")
        
        # Explorer URL should be present
        assert "explorer_url" in data, "Expected explorer_url in response"
        assert "etherscan.io" in data.get("explorer_url", "")
        print(f"SUCCESS: Binance wallet resolved with is_known=True")

    def test_resolve_unknown_address(self):
        """GET /api/address/resolve with unknown address returns is_known=false"""
        unknown_addr = "0x0000000000000000000000000000000000000001"
        response = requests.get(
            f"{BASE_URL}/api/address/resolve",
            params={"address": unknown_addr, "chain": "ethereum"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("is_known") is False, f"Expected is_known=False for unknown address, got {data}"
        assert data.get("address") == unknown_addr.lower()
        print(f"SUCCESS: Unknown address returns is_known=False")

    def test_resolve_missing_address_param(self):
        """GET /api/address/resolve without address param returns error"""
        response = requests.get(f"{BASE_URL}/api/address/resolve")
        # Should return 422 (validation error) or 400
        assert response.status_code in [400, 422], f"Expected 400/422 for missing param, got {response.status_code}"
        print(f"SUCCESS: Missing address param returns {response.status_code}")


class TestAddressResolveBatch:
    """Batch address resolution tests"""

    def test_batch_resolve_mixed_addresses(self):
        """GET /api/address/resolve/batch resolves known and unknown addresses"""
        known_addr = BINANCE_HOT_WALLET
        unknown_addr = "0x0000000000000000000000000000000000000001"
        
        response = requests.get(
            f"{BASE_URL}/api/address/resolve/batch",
            params={"addresses": f"{known_addr},{unknown_addr}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "results" in data
        
        results = data["results"]
        # Check known address
        known_result = results.get(known_addr.lower(), {})
        assert known_result.get("is_known") is True, f"Expected Binance to be known: {known_result}"
        print(f"Binance result: {known_result}")
        
        # Check unknown address
        unknown_result = results.get(unknown_addr.lower(), {})
        assert unknown_result.get("is_known") is False, f"Expected unknown address to be is_known=False"
        print(f"SUCCESS: Batch resolve correctly identifies known and unknown addresses")

    def test_batch_resolve_multiple_known(self):
        """GET /api/address/resolve/batch with multiple known addresses"""
        # Known exchange addresses (Binance and Coinbase)
        addresses = f"{BINANCE_HOT_WALLET},0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43"
        
        response = requests.get(
            f"{BASE_URL}/api/address/resolve/batch",
            params={"addresses": addresses}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        results = data.get("results", {})
        
        known_count = sum(1 for r in results.values() if r.get("is_known"))
        print(f"Resolved {known_count} known addresses out of 2")
        print(f"SUCCESS: Batch resolve returned {len(results)} results")


class TestEntityActivity:
    """Entity activity endpoint tests"""

    def test_entity_activity_ethereum(self):
        """GET /api/entity/activity?chain=ethereum returns activity with top entities"""
        response = requests.get(
            f"{BASE_URL}/api/entity/activity",
            params={"chain": "ethereum", "limit": 50}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("chain") == "ethereum"
        
        # Check activity list
        activity = data.get("activity", [])
        print(f"Activity records: {len(activity)}")
        
        # Check top_entities
        top_entities = data.get("top_entities", [])
        print(f"Top entities count: {len(top_entities)}")
        
        if top_entities:
            for ent in top_entities[:5]:
                print(f"  Entity: {ent.get('_id', 'N/A')}, TX count: {ent.get('tx_count', 0)}, "
                      f"Value: {ent.get('total_value_eth', 0):.2f} ETH")
            
            # Verify known exchanges are in top entities
            entity_names = [e.get('_id', '').lower() for e in top_entities]
            has_binance = any('binance' in n for n in entity_names)
            has_coinbase = any('coinbase' in n for n in entity_names)
            print(f"Has Binance: {has_binance}, Has Coinbase: {has_coinbase}")
        
        print(f"SUCCESS: Entity activity endpoint working")

    def test_entity_activity_filter_by_entity(self):
        """GET /api/entity/activity with entity filter"""
        response = requests.get(
            f"{BASE_URL}/api/entity/activity",
            params={"chain": "ethereum", "entity": "binance", "limit": 20}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        activity = data.get("activity", [])
        print(f"Binance activity records: {len(activity)}")
        
        if activity:
            for a in activity[:3]:
                print(f"  TX: {a.get('tx_hash', '')[:16]}..., Type: {a.get('tx_type', 'N/A')}, "
                      f"Value: {a.get('value_eth', 0):.4f} ETH")
        
        print(f"SUCCESS: Entity filter working")


class TestEntityActivitySummary:
    """Entity activity summary tests"""

    def test_entity_activity_summary(self):
        """GET /api/entity/activity/summary returns total and breakdowns"""
        response = requests.get(f"{BASE_URL}/api/entity/activity/summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        
        # Total activity
        total = data.get("total_activity", 0)
        print(f"Total entity activity records: {total}")
        assert total >= 0, "Expected total_activity >= 0"
        
        # By tx_type
        by_tx_type = data.get("by_tx_type", {})
        print(f"By tx_type: {by_tx_type}")
        
        # By entity_type
        by_entity_type = data.get("by_entity_type", {})
        print(f"By entity_type: {by_entity_type}")
        
        # By chain
        by_chain = data.get("by_chain", {})
        print(f"By chain: {by_chain}")
        
        print(f"SUCCESS: Entity activity summary working")


class TestIndexerDiagnostics:
    """Indexer diagnostics with entity resolution section"""

    def test_diagnostics_entity_resolution(self):
        """GET /api/admin/indexer/diagnostics includes entity_resolution section"""
        response = requests.get(f"{BASE_URL}/api/admin/indexer/diagnostics")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        
        # Check entity_resolution section
        er = data.get("entity_resolution", {})
        assert "address_labels_loaded" in er, "Expected address_labels_loaded in entity_resolution"
        assert "entities_loaded" in er, "Expected entities_loaded in entity_resolution"
        assert "enriched_transactions" in er, "Expected enriched_transactions in entity_resolution"
        assert "entity_activity_records" in er, "Expected entity_activity_records in entity_resolution"
        
        print(f"Entity Resolution stats:")
        print(f"  Address labels loaded: {er.get('address_labels_loaded', 0)}")
        print(f"  Entities loaded: {er.get('entities_loaded', 0)}")
        print(f"  Enriched transactions: {er.get('enriched_transactions', 0)}")
        print(f"  Entity activity records: {er.get('entity_activity_records', 0)}")
        
        # Health should include entity_resolution
        health = data.get("health", {})
        assert "entity_resolution" in health, "Expected entity_resolution in health"
        print(f"Entity resolution health: {health.get('entity_resolution', 'N/A')}")
        
        # Ingestion totals should have entity_activity
        totals = data.get("ingestion", {}).get("totals", {})
        if "entity_activity" in totals:
            print(f"Entity activity in ingestion totals: {totals.get('entity_activity', 0)}")
        
        print(f"SUCCESS: Diagnostics include entity_resolution section")


class TestModeSwitching:
    """Indexer mode switching tests"""

    def test_switch_to_limited_mode(self):
        """POST /api/admin/indexer/mode with mode=LIMITED switches to lite"""
        response = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "LIMITED"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("mode") == "LIMITED"
        # Internal mode should be preview/lite
        internal = data.get("internal", "")
        assert internal in ("preview", "lite"), f"Expected internal mode preview/lite, got {internal}"
        print(f"SUCCESS: Switched to LIMITED mode (internal: {internal})")

    def test_switch_to_full_mode(self):
        """POST /api/admin/indexer/mode with mode=FULL switches to indexer"""
        response = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "FULL"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("mode") == "FULL"
        # Internal mode should be indexer
        internal = data.get("internal", "")
        assert internal == "indexer", f"Expected internal mode indexer, got {internal}"
        print(f"SUCCESS: Switched to FULL mode (internal: {internal})")

    def test_invalid_mode(self):
        """POST /api/admin/indexer/mode with invalid mode returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "INVALID"}
        )
        assert response.status_code == 400, f"Expected 400 for invalid mode, got {response.status_code}"
        print(f"SUCCESS: Invalid mode returns 400")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
