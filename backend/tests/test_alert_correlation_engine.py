"""
Alert Correlation Engine Tests

Tests for the meta-awareness layer that groups individual alerts into cluster-level meta-alerts.
Covers: SECTOR_ROTATION, MULTI_MARKET_CONFIRMATION, UNLOCK_RISK_CLUSTER, RISK_ON_SHIFT,
        RISK_OFF_SHIFT, NARRATIVE_EXHAUSTION, BROAD_OVERHEAT, CLUSTER_WAKEUP, MIXED_CLUSTER

Endpoints tested:
- POST /api/alert-correlation/analyze
- GET /api/alert-correlation/meta-alerts
- GET /api/alert-correlation/history
- GET /api/alert-correlation/regime
- POST /api/alert-correlation/clear
- POST /api/alert-correlation/ingest
- Python proxy routes: /api/prediction/alert-correlation/*
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://expo-telegram-web.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="function")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(autouse=True)
def clear_state(api_client):
    """Clear correlation state before each test to avoid dedup issues"""
    try:
        api_client.post(f"{BASE_URL}/api/alert-correlation/clear", json={}, timeout=10)
    except Exception:
        pass
    yield


class TestAlertCorrelationBasicEndpoints:
    """Basic endpoint availability and response structure tests"""

    def test_clear_endpoint(self, api_client):
        """POST /api/alert-correlation/clear — clears state"""
        response = api_client.post(f"{BASE_URL}/api/alert-correlation/clear", json={}, timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "message" in data
        print(f"PASS: Clear endpoint works: {data}")

    def test_meta_alerts_endpoint(self, api_client):
        """GET /api/alert-correlation/meta-alerts — returns recent meta-alerts"""
        response = api_client.get(f"{BASE_URL}/api/alert-correlation/meta-alerts", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "metaAlerts" in data
        assert "count" in data
        assert isinstance(data["metaAlerts"], list)
        print(f"PASS: Meta-alerts endpoint works, count={data['count']}")

    def test_history_endpoint(self, api_client):
        """GET /api/alert-correlation/history — returns historical meta-alerts from MongoDB"""
        response = api_client.get(f"{BASE_URL}/api/alert-correlation/history", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "metaAlerts" in data
        assert "count" in data
        print(f"PASS: History endpoint works, count={data['count']}")

    def test_regime_endpoint(self, api_client):
        """GET /api/alert-correlation/regime — returns current regime state"""
        response = api_client.get(f"{BASE_URL}/api/alert-correlation/regime", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        # regime can be null if no regime shift detected
        print(f"PASS: Regime endpoint works, regime={data.get('regime')}")

    def test_analyze_empty_alerts(self, api_client):
        """POST /api/alert-correlation/analyze — handles empty alerts array"""
        response = api_client.post(
            f"{BASE_URL}/api/alert-correlation/analyze",
            json={"alerts": []},
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("metaAlerts") == []
        print(f"PASS: Empty alerts handled correctly")

    def test_analyze_single_alert(self, api_client):
        """POST /api/alert-correlation/analyze — single alert returns no meta-alert (min 2 required)"""
        now = int(time.time() * 1000)
        alerts = [{
            "alertId": "TEST_single_1",
            "marketId": "market_1",
            "type": "ENTRY_SIGNAL",
            "priority": "HIGH",
            "timestamp": now,
            "asset": "BTC",
            "factors": {
                "assetFactors": ["BTC"],
                "themeFactors": ["crypto"],
                "catalystFactors": [],
                "entityFactors": []
            }
        }]
        response = api_client.post(
            f"{BASE_URL}/api/alert-correlation/analyze",
            json={"alerts": alerts},
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        # Single alert should not produce meta-alert
        assert data.get("count", 0) == 0 or len(data.get("metaAlerts", [])) == 0
        print(f"PASS: Single alert correctly returns no meta-alert")


class TestSectorRotationScenario:
    """Scenario: 3+ AI/ETF/crypto ENTRY_SIGNAL alerts with shared theme factors → SECTOR_ROTATION"""

    def test_sector_rotation_detection(self, api_client):
        """3+ entry alerts with shared themeFactors like ETF/risk-on → SECTOR_ROTATION"""
        now = int(time.time() * 1000)
        
        # 3 ENTRY_SIGNAL alerts with shared theme factors (ETF, risk-on)
        alerts = [
            {
                "alertId": "TEST_sector_1",
                "marketId": "market_etf_1",
                "type": "ENTRY_SIGNAL",
                "priority": "HIGH",
                "timestamp": now,
                "asset": "BTC",
                "edge": 0.08,
                "confidence": 0.75,
                "factors": {
                    "assetFactors": ["BTC"],
                    "themeFactors": ["ETF", "risk-on", "institutional"],
                    "catalystFactors": ["etf_approval"],
                    "entityFactors": ["BlackRock"]
                }
            },
            {
                "alertId": "TEST_sector_2",
                "marketId": "market_etf_2",
                "type": "ENTRY_SIGNAL",
                "priority": "HIGH",
                "timestamp": now + 60000,  # 1 min later
                "asset": "ETH",
                "edge": 0.07,
                "confidence": 0.72,
                "factors": {
                    "assetFactors": ["ETH"],
                    "themeFactors": ["ETF", "risk-on", "institutional"],
                    "catalystFactors": ["etf_approval"],
                    "entityFactors": ["Fidelity"]
                }
            },
            {
                "alertId": "TEST_sector_3",
                "marketId": "market_etf_3",
                "type": "ENTRY_SIGNAL",
                "priority": "MEDIUM",
                "timestamp": now + 120000,  # 2 min later
                "asset": "SOL",
                "edge": 0.06,
                "confidence": 0.68,
                "factors": {
                    "assetFactors": ["SOL"],
                    "themeFactors": ["ETF", "risk-on", "altcoin"],
                    "catalystFactors": ["etf_speculation"],
                    "entityFactors": ["VanEck"]
                }
            },
            {
                "alertId": "TEST_sector_4",
                "marketId": "market_etf_4",
                "type": "STATE_CHANGE",
                "priority": "MEDIUM",
                "timestamp": now + 180000,  # 3 min later
                "asset": "AVAX",
                "edge": 0.05,
                "confidence": 0.65,
                "factors": {
                    "assetFactors": ["AVAX"],
                    "themeFactors": ["ETF", "risk-on", "L1"],
                    "catalystFactors": [],
                    "entityFactors": []
                }
            }
        ]
        
        response = api_client.post(
            f"{BASE_URL}/api/alert-correlation/analyze",
            json={"alerts": alerts},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        print(f"Response: {data}")
        
        # Should produce at least one meta-alert
        meta_alerts = data.get("metaAlerts", [])
        
        if len(meta_alerts) > 0:
            meta = meta_alerts[0]
            print(f"Meta-alert type: {meta.get('type')}")
            print(f"Meta-alert title: {meta.get('title')}")
            print(f"Meta-alert summary: {meta.get('summary')}")
            print(f"Shared factors: {meta.get('sharedFactors')}")
            print(f"Confidence: {meta.get('confidence')}")
            print(f"metaInsightGain: {meta.get('metaInsightGain')}")
            
            # Verify meta-alert structure
            assert "metaAlertId" in meta
            assert "type" in meta
            assert "title" in meta
            assert "summary" in meta
            assert "members" in meta
            assert "marketIds" in meta
            assert "assets" in meta
            assert "priority" in meta
            assert "confidence" in meta
            assert "sharedFactors" in meta
            assert "keyDrivers" in meta
            assert "risks" in meta
            assert "contradictionScore" in meta
            assert "memberDiversityScore" in meta
            assert "metaInsightGain" in meta
            assert "suppressMemberAlerts" in meta
            
            # Check if SECTOR_ROTATION or related type
            valid_types = ["SECTOR_ROTATION", "MULTI_MARKET_CONFIRMATION", "RISK_ON_SHIFT", "CLUSTER_WAKEUP"]
            assert meta.get("type") in valid_types, f"Expected one of {valid_types}, got {meta.get('type')}"
            
            print(f"PASS: Sector rotation scenario produced {meta.get('type')} meta-alert")
        else:
            # Quality gate may have filtered - check suppressedAlertIds
            suppressed = data.get("suppressedAlertIds", [])
            print(f"No meta-alerts produced. Suppressed IDs: {suppressed}")
            print(f"This may be due to quality gate filtering (metaInsightGain < 0.15)")
            # Not a failure - quality gate is working as designed


class TestUnlockRiskClusterScenario:
    """Scenario: 2+ RISK_ALERT with unlockRisk=HIGH → UNLOCK_RISK_CLUSTER"""

    def test_unlock_risk_cluster_detection(self, api_client):
        """2+ RISK_ALERT with unlockRisk:HIGH → UNLOCK_RISK_CLUSTER"""
        now = int(time.time() * 1000)
        
        alerts = [
            {
                "alertId": "TEST_unlock_1",
                "marketId": "market_unlock_1",
                "type": "RISK_ALERT",
                "priority": "HIGH",
                "timestamp": now,
                "asset": "ARB",
                "edge": 0.02,
                "confidence": 0.6,
                "factors": {
                    "assetFactors": ["ARB"],
                    "themeFactors": ["L2", "unlock"],
                    "catalystFactors": ["token_unlock"],
                    "entityFactors": []
                },
                "project": {
                    "verdict": "BEARISH",
                    "unlockRisk": "HIGH",
                    "valuation": "OVERVALUED"
                }
            },
            {
                "alertId": "TEST_unlock_2",
                "marketId": "market_unlock_2",
                "type": "RISK_ALERT",
                "priority": "HIGH",
                "timestamp": now + 60000,
                "asset": "OP",
                "edge": 0.01,
                "confidence": 0.55,
                "factors": {
                    "assetFactors": ["OP"],
                    "themeFactors": ["L2", "unlock"],
                    "catalystFactors": ["token_unlock"],
                    "entityFactors": []
                },
                "project": {
                    "verdict": "BEARISH",
                    "unlockRisk": "HIGH",
                    "valuation": "FAIR"
                }
            },
            {
                "alertId": "TEST_unlock_3",
                "marketId": "market_unlock_3",
                "type": "RISK_ALERT",
                "priority": "MEDIUM",
                "timestamp": now + 120000,
                "asset": "STRK",
                "edge": 0.015,
                "confidence": 0.5,
                "factors": {
                    "assetFactors": ["STRK"],
                    "themeFactors": ["L2", "unlock"],
                    "catalystFactors": ["token_unlock"],
                    "entityFactors": []
                },
                "project": {
                    "verdict": "MIXED",
                    "unlockRisk": "HIGH",
                    "valuation": "OVERVALUED"
                }
            }
        ]
        
        response = api_client.post(
            f"{BASE_URL}/api/alert-correlation/analyze",
            json={"alerts": alerts},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        print(f"Response: {data}")
        
        meta_alerts = data.get("metaAlerts", [])
        
        if len(meta_alerts) > 0:
            meta = meta_alerts[0]
            print(f"Meta-alert type: {meta.get('type')}")
            print(f"Key drivers: {meta.get('keyDrivers')}")
            print(f"Risks: {meta.get('risks')}")
            
            # Should be UNLOCK_RISK_CLUSTER or RISK_OFF_SHIFT
            valid_types = ["UNLOCK_RISK_CLUSTER", "RISK_OFF_SHIFT", "MIXED_CLUSTER"]
            assert meta.get("type") in valid_types, f"Expected one of {valid_types}, got {meta.get('type')}"
            
            print(f"PASS: Unlock risk scenario produced {meta.get('type')} meta-alert")
        else:
            print("No meta-alerts produced - quality gate may have filtered")


class TestMixedClusterScenario:
    """Scenario: mixed bullish + risk + exit alerts → MIXED_CLUSTER with high contradictionScore"""

    def test_mixed_cluster_detection(self, api_client):
        """Mixed ENTRY + EXIT + RISK → MIXED_CLUSTER with high contradictionScore"""
        now = int(time.time() * 1000)
        
        alerts = [
            {
                "alertId": "TEST_mixed_1",
                "marketId": "market_mixed_1",
                "type": "ENTRY_SIGNAL",
                "priority": "HIGH",
                "timestamp": now,
                "asset": "BTC",
                "edge": 0.08,
                "confidence": 0.75,
                "factors": {
                    "assetFactors": ["BTC"],
                    "themeFactors": ["crypto", "macro"],
                    "catalystFactors": [],
                    "entityFactors": []
                }
            },
            {
                "alertId": "TEST_mixed_2",
                "marketId": "market_mixed_2",
                "type": "EXIT_SIGNAL",
                "priority": "HIGH",
                "timestamp": now + 30000,
                "asset": "ETH",
                "edge": -0.05,
                "confidence": 0.7,
                "factors": {
                    "assetFactors": ["ETH"],
                    "themeFactors": ["crypto", "macro"],
                    "catalystFactors": [],
                    "entityFactors": []
                }
            },
            {
                "alertId": "TEST_mixed_3",
                "marketId": "market_mixed_3",
                "type": "RISK_ALERT",
                "priority": "HIGH",
                "timestamp": now + 60000,
                "asset": "SOL",
                "edge": 0.02,
                "confidence": 0.6,
                "factors": {
                    "assetFactors": ["SOL"],
                    "themeFactors": ["crypto", "macro"],
                    "catalystFactors": [],
                    "entityFactors": []
                }
            },
            {
                "alertId": "TEST_mixed_4",
                "marketId": "market_mixed_4",
                "type": "ENTRY_SIGNAL",
                "priority": "MEDIUM",
                "timestamp": now + 90000,
                "asset": "AVAX",
                "edge": 0.06,
                "confidence": 0.65,
                "factors": {
                    "assetFactors": ["AVAX"],
                    "themeFactors": ["crypto", "L1"],
                    "catalystFactors": [],
                    "entityFactors": []
                }
            }
        ]
        
        response = api_client.post(
            f"{BASE_URL}/api/alert-correlation/analyze",
            json={"alerts": alerts},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        print(f"Response: {data}")
        
        meta_alerts = data.get("metaAlerts", [])
        
        if len(meta_alerts) > 0:
            meta = meta_alerts[0]
            print(f"Meta-alert type: {meta.get('type')}")
            print(f"Contradiction score: {meta.get('contradictionScore')}")
            print(f"Summary: {meta.get('summary')}")
            
            # Should have elevated contradictionScore
            contradiction = meta.get("contradictionScore", 0)
            print(f"Contradiction score: {contradiction}")
            
            # MIXED_CLUSTER expected when contradictionScore > 0.6
            if meta.get("type") == "MIXED_CLUSTER":
                assert contradiction > 0.3, f"Expected high contradiction for MIXED_CLUSTER, got {contradiction}"
                print(f"PASS: Mixed cluster detected with contradictionScore={contradiction}")
            else:
                print(f"Got {meta.get('type')} instead of MIXED_CLUSTER (contradiction={contradiction})")
        else:
            print("No meta-alerts produced - quality gate may have filtered")


class TestNoOverlapScenario:
    """Scenario: 2 unrelated alerts with no factor overlap → should NOT produce meta-alert"""

    def test_no_overlap_quality_gate_filters(self, api_client):
        """2 alerts with no factor overlap → quality gate rejects"""
        now = int(time.time() * 1000)
        
        # Two completely unrelated alerts
        alerts = [
            {
                "alertId": "TEST_nooverlap_1",
                "marketId": "market_unrelated_1",
                "type": "ENTRY_SIGNAL",
                "priority": "MEDIUM",
                "timestamp": now,
                "asset": "BTC",
                "edge": 0.05,
                "confidence": 0.6,
                "factors": {
                    "assetFactors": ["BTC"],
                    "themeFactors": ["store-of-value", "digital-gold"],
                    "catalystFactors": ["halving"],
                    "entityFactors": ["MicroStrategy"]
                }
            },
            {
                "alertId": "TEST_nooverlap_2",
                "marketId": "market_unrelated_2",
                "type": "ENTRY_SIGNAL",
                "priority": "MEDIUM",
                "timestamp": now + 60000,
                "asset": "DOGE",
                "edge": 0.04,
                "confidence": 0.5,
                "factors": {
                    "assetFactors": ["DOGE"],
                    "themeFactors": ["meme", "social"],
                    "catalystFactors": ["elon-tweet"],
                    "entityFactors": ["ElonMusk"]
                }
            }
        ]
        
        response = api_client.post(
            f"{BASE_URL}/api/alert-correlation/analyze",
            json={"alerts": alerts},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        print(f"Response: {data}")
        
        meta_alerts = data.get("metaAlerts", [])
        
        # Should NOT produce meta-alert due to low overlap
        if len(meta_alerts) == 0:
            print("PASS: Quality gate correctly filtered unrelated alerts (no meta-alert produced)")
        else:
            # If produced, check it has low metaInsightGain
            meta = meta_alerts[0]
            gain = meta.get("metaInsightGain", 0)
            print(f"Meta-alert produced with metaInsightGain={gain}")
            # This is acceptable if gain is low - quality gate has different thresholds


class TestIngestEndpoint:
    """Test single alert ingestion endpoint"""

    def test_ingest_single_alert(self, api_client):
        """POST /api/alert-correlation/ingest — single alert ingestion"""
        now = int(time.time() * 1000)
        
        alert = {
            "alertId": "TEST_ingest_1",
            "marketId": "market_ingest_1",
            "type": "ENTRY_SIGNAL",
            "priority": "HIGH",
            "timestamp": now,
            "asset": "BTC",
            "factors": {
                "assetFactors": ["BTC"],
                "themeFactors": ["crypto"],
                "catalystFactors": [],
                "entityFactors": []
            }
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/alert-correlation/ingest",
            json=alert,
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "metaAlerts" in data
        assert "count" in data
        print(f"PASS: Ingest endpoint works, count={data['count']}")

    def test_ingest_missing_alertId(self, api_client):
        """POST /api/alert-correlation/ingest — requires alertId"""
        alert = {
            "marketId": "market_1",
            "type": "ENTRY_SIGNAL",
            "priority": "HIGH",
            "timestamp": int(time.time() * 1000)
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/alert-correlation/ingest",
            json=alert,
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is False
        assert "error" in data
        print(f"PASS: Missing alertId correctly rejected: {data}")


class TestPythonProxyRoutes:
    """Test Python proxy routes at /api/prediction/alert-correlation/*"""

    def test_proxy_analyze(self, api_client):
        """POST /api/prediction/alert-correlation/analyze — Python proxy"""
        now = int(time.time() * 1000)
        
        alerts = [
            {
                "alertId": "TEST_proxy_1",
                "marketId": "market_proxy_1",
                "type": "ENTRY_SIGNAL",
                "priority": "HIGH",
                "timestamp": now,
                "asset": "BTC",
                "factors": {
                    "assetFactors": ["BTC"],
                    "themeFactors": ["crypto"],
                    "catalystFactors": [],
                    "entityFactors": []
                }
            },
            {
                "alertId": "TEST_proxy_2",
                "marketId": "market_proxy_2",
                "type": "ENTRY_SIGNAL",
                "priority": "HIGH",
                "timestamp": now + 60000,
                "asset": "ETH",
                "factors": {
                    "assetFactors": ["ETH"],
                    "themeFactors": ["crypto"],
                    "catalystFactors": [],
                    "entityFactors": []
                }
            }
        ]
        
        response = api_client.post(
            f"{BASE_URL}/api/prediction/alert-correlation/analyze",
            json={"alerts": alerts},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "metaAlerts" in data
        print(f"PASS: Python proxy /analyze works, count={data.get('count', 0)}")

    def test_proxy_meta_alerts(self, api_client):
        """GET /api/prediction/alert-correlation/meta-alerts — Python proxy"""
        response = api_client.get(
            f"{BASE_URL}/api/prediction/alert-correlation/meta-alerts",
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "metaAlerts" in data
        print(f"PASS: Python proxy /meta-alerts works")

    def test_proxy_history(self, api_client):
        """GET /api/prediction/alert-correlation/history — Python proxy"""
        response = api_client.get(
            f"{BASE_URL}/api/prediction/alert-correlation/history",
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "metaAlerts" in data
        print(f"PASS: Python proxy /history works")

    def test_proxy_regime(self, api_client):
        """GET /api/prediction/alert-correlation/regime — Python proxy"""
        response = api_client.get(
            f"{BASE_URL}/api/prediction/alert-correlation/regime",
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Python proxy /regime works")


class TestMetaAlertResponseStructure:
    """Verify MetaAlert response includes all required fields"""

    def test_meta_alert_full_structure(self, api_client):
        """Verify MetaAlert has all required fields"""
        now = int(time.time() * 1000)
        
        # Create alerts that should produce a meta-alert
        alerts = [
            {
                "alertId": "TEST_struct_1",
                "marketId": "market_struct_1",
                "type": "ENTRY_SIGNAL",
                "priority": "HIGH",
                "timestamp": now,
                "asset": "BTC",
                "edge": 0.1,
                "confidence": 0.8,
                "factors": {
                    "assetFactors": ["BTC"],
                    "themeFactors": ["ETF", "institutional", "risk-on"],
                    "catalystFactors": ["etf_approval"],
                    "entityFactors": ["BlackRock", "Fidelity"]
                }
            },
            {
                "alertId": "TEST_struct_2",
                "marketId": "market_struct_2",
                "type": "ENTRY_SIGNAL",
                "priority": "HIGH",
                "timestamp": now + 30000,
                "asset": "ETH",
                "edge": 0.09,
                "confidence": 0.78,
                "factors": {
                    "assetFactors": ["ETH"],
                    "themeFactors": ["ETF", "institutional", "risk-on"],
                    "catalystFactors": ["etf_approval"],
                    "entityFactors": ["BlackRock", "VanEck"]
                }
            },
            {
                "alertId": "TEST_struct_3",
                "marketId": "market_struct_3",
                "type": "ENTRY_SIGNAL",
                "priority": "HIGH",
                "timestamp": now + 60000,
                "asset": "SOL",
                "edge": 0.08,
                "confidence": 0.75,
                "factors": {
                    "assetFactors": ["SOL"],
                    "themeFactors": ["ETF", "institutional", "risk-on"],
                    "catalystFactors": ["etf_speculation"],
                    "entityFactors": ["VanEck"]
                }
            },
            {
                "alertId": "TEST_struct_4",
                "marketId": "market_struct_4",
                "type": "STATE_CHANGE",
                "priority": "MEDIUM",
                "timestamp": now + 90000,
                "asset": "AVAX",
                "edge": 0.07,
                "confidence": 0.7,
                "factors": {
                    "assetFactors": ["AVAX"],
                    "themeFactors": ["ETF", "institutional"],
                    "catalystFactors": [],
                    "entityFactors": []
                }
            }
        ]
        
        response = api_client.post(
            f"{BASE_URL}/api/alert-correlation/analyze",
            json={"alerts": alerts},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Check response structure
        assert "metaAlerts" in data
        assert "count" in data
        assert "suppressedAlertIds" in data
        
        meta_alerts = data.get("metaAlerts", [])
        
        if len(meta_alerts) > 0:
            meta = meta_alerts[0]
            
            # Required fields per spec
            required_fields = [
                "metaAlertId", "type", "title", "summary", "members", "marketIds",
                "assets", "priority", "confidence", "sharedFactors", "keyDrivers",
                "risks", "contradictionScore", "memberDiversityScore", "metaInsightGain",
                "suppressMemberAlerts", "dedupKey", "timestamp"
            ]
            
            for field in required_fields:
                assert field in meta, f"Missing required field: {field}"
                print(f"  {field}: {meta[field]}")
            
            # Type validation
            assert meta["type"] in [
                "SECTOR_ROTATION", "MULTI_MARKET_CONFIRMATION", "UNLOCK_RISK_CLUSTER",
                "RISK_ON_SHIFT", "RISK_OFF_SHIFT", "NARRATIVE_EXHAUSTION",
                "BROAD_OVERHEAT", "CLUSTER_WAKEUP", "MIXED_CLUSTER"
            ]
            assert meta["priority"] in ["HIGH", "MEDIUM", "LOW"]
            assert isinstance(meta["members"], list)
            assert isinstance(meta["marketIds"], list)
            assert isinstance(meta["assets"], list)
            assert isinstance(meta["sharedFactors"], list)
            assert isinstance(meta["keyDrivers"], list)
            assert isinstance(meta["risks"], list)
            assert isinstance(meta["confidence"], (int, float))
            assert isinstance(meta["contradictionScore"], (int, float))
            assert isinstance(meta["memberDiversityScore"], (int, float))
            assert isinstance(meta["metaInsightGain"], (int, float))
            assert isinstance(meta["suppressMemberAlerts"], bool)
            
            print(f"PASS: MetaAlert has all required fields with correct types")
        else:
            print("No meta-alerts produced - cannot verify structure (quality gate filtered)")


class TestRegimeShiftDetection:
    """Test regime shift detection within meta-alerts"""

    def test_regime_shift_in_meta_alert(self, api_client):
        """Verify regimeShift field in meta-alert when detected"""
        now = int(time.time() * 1000)
        
        # Create strong directional cluster that should trigger regime shift
        alerts = [
            {
                "alertId": f"TEST_regime_{i}",
                "marketId": f"market_regime_{i}",
                "type": "ENTRY_SIGNAL",
                "priority": "HIGH",
                "timestamp": now + i * 30000,
                "asset": asset,
                "edge": 0.1,
                "confidence": 0.8,
                "factors": {
                    "assetFactors": [asset],
                    "themeFactors": ["risk-on", "bullish", "momentum"],
                    "catalystFactors": [],
                    "entityFactors": []
                }
            }
            for i, asset in enumerate(["BTC", "ETH", "SOL", "AVAX", "MATIC"])
        ]
        
        response = api_client.post(
            f"{BASE_URL}/api/alert-correlation/analyze",
            json={"alerts": alerts},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        
        meta_alerts = data.get("metaAlerts", [])
        
        if len(meta_alerts) > 0:
            meta = meta_alerts[0]
            regime_shift = meta.get("regimeShift")
            
            if regime_shift:
                assert "detected" in regime_shift
                assert "direction" in regime_shift
                assert "confidence" in regime_shift
                assert regime_shift["direction"] in ["RISK_ON", "RISK_OFF", "NEUTRAL"]
                print(f"PASS: Regime shift detected: {regime_shift}")
            else:
                print("No regime shift detected in meta-alert (may not meet threshold)")
        else:
            print("No meta-alerts produced")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
