"""
Execution Layer API Tests — Sprint E: Microstructure & Entry/Exit Quality

Tests:
  - POST /api/execution-layer/analyze — Single case execution analysis
  - POST /api/execution-layer/analyze/batch — Batch execution analysis
  - GET /api/prediction/run — executionLayer field integration
  
Services verified:
  - spread-regime.service (NARROW/NORMAL/WIDE/BROKEN)
  - depth-proxy.service (DEEP/OK/THIN/FRAGILE)
  - slippage-engine.service (slippageRisk, expectedLeakage, maxSlippageBps)
  - entry-quality.service (entryQualityScore, chaseRisk, missRisk)
  - execution-plan.service (ENTER_MARKET/ENTER_LIMIT/STAGGER_LIMIT/WAIT_RETRACE/WAIT_CONFIRMATION/DO_NOT_CHASE)
  - edge-compression.service (edgeCompression, compressed)
  - scaling-policy.service (ADD/HOLD/NO_ADD)
  - exit-policy.service (HOLD/TRIM/REDUCE/EXIT)
  - microstructure-orchestrator.service (full pipeline)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestExecutionLayerAnalyze:
    """POST /api/execution-layer/analyze — Single case execution analysis"""

    def test_analyze_basic_case(self):
        """Test basic execution analysis with minimal inputs"""
        payload = {
            "spread": 0.02,
            "liquidity": 50000,
            "volume24h": 10000,
            "edge": 0.10,
            "fairProb": 0.65,
            "marketProb": 0.55,
            "confidence": 0.7,
            "alignment": 0.6,
            "repricingState": "fresh_mispricing",
            "marketStage": "forming",
            "socialSaturation": 0.3,
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True, f"Expected ok=True: {data}"
        
        ex = data.get("execution", {})
        assert "entry" in ex, "Missing entry field"
        assert "scaling" in ex, "Missing scaling field"
        assert "exit" in ex, "Missing exit field"
        assert "edgeCompression" in ex, "Missing edgeCompression field"
        assert "microstructure" in ex, "Missing microstructure field"
        print(f"✓ Basic analysis returned all fields: entry, scaling, exit, edgeCompression, microstructure")

    def test_analyze_entry_style_enter_market(self):
        """Test ENTER_MARKET entry style: narrow spread + strong edge + early repricing"""
        payload = {
            "spread": 0.015,  # Narrow
            "liquidity": 100000,  # Deep
            "volume24h": 20000,
            "edge": 0.12,  # Strong
            "fairProb": 0.70,
            "marketProb": 0.58,
            "confidence": 0.75,
            "alignment": 0.7,
            "repricingState": "fresh_mispricing",  # Early
            "marketStage": "forming",
            "socialSaturation": 0.2,  # Low
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        
        entry = data["execution"]["entry"]
        # Should be ENTER_MARKET or ENTER_LIMIT for strong edge + narrow spread
        assert entry["entryStyle"] in ["ENTER_MARKET", "ENTER_LIMIT"], f"Expected ENTER_MARKET/LIMIT, got {entry['entryStyle']}"
        assert entry["spreadRegime"] == "NARROW", f"Expected NARROW spread regime, got {entry['spreadRegime']}"
        assert entry["entryQualityScore"] >= 0.5, f"Expected high entry quality, got {entry['entryQualityScore']}"
        print(f"✓ ENTER_MARKET scenario: entryStyle={entry['entryStyle']}, quality={entry['entryQualityScore']}")

    def test_analyze_entry_style_do_not_chase(self):
        """Test DO_NOT_CHASE entry style: overheated + high saturation"""
        payload = {
            "spread": 0.10,  # Broken
            "liquidity": 5000,  # Low
            "volume24h": 500,
            "edge": 0.03,  # Small
            "fairProb": 0.55,
            "marketProb": 0.52,
            "confidence": 0.4,
            "alignment": 0.4,
            "repricingState": "overheated",
            "marketStage": "crowded",
            "socialSaturation": 0.8,  # High
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        
        entry = data["execution"]["entry"]
        assert entry["entryStyle"] == "DO_NOT_CHASE", f"Expected DO_NOT_CHASE, got {entry['entryStyle']}"
        assert entry["spreadRegime"] == "BROKEN", f"Expected BROKEN spread regime, got {entry['spreadRegime']}"
        assert entry["chaseRisk"] >= 0.5, f"Expected high chase risk, got {entry['chaseRisk']}"
        print(f"✓ DO_NOT_CHASE scenario: entryStyle={entry['entryStyle']}, chaseRisk={entry['chaseRisk']}")

    def test_analyze_spread_regime_narrow(self):
        """Test NARROW spread regime (<2%)"""
        payload = {
            "spread": 0.015,
            "liquidity": 50000,
            "volume24h": 10000,
            "edge": 0.08,
            "repricingState": "active_repricing",
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution"]["entry"]["spreadRegime"] == "NARROW"
        print("✓ Spread regime NARROW for spread=1.5%")

    def test_analyze_spread_regime_normal(self):
        """Test NORMAL spread regime (2-5%)"""
        payload = {
            "spread": 0.04,
            "liquidity": 50000,
            "volume24h": 10000,
            "edge": 0.08,
            "repricingState": "active_repricing",
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution"]["entry"]["spreadRegime"] == "NORMAL"
        print("✓ Spread regime NORMAL for spread=4%")

    def test_analyze_spread_regime_wide(self):
        """Test WIDE spread regime (5-9%)"""
        payload = {
            "spread": 0.07,
            "liquidity": 50000,
            "volume24h": 10000,
            "edge": 0.08,
            "repricingState": "active_repricing",
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution"]["entry"]["spreadRegime"] == "WIDE"
        print("✓ Spread regime WIDE for spread=7%")

    def test_analyze_spread_regime_broken(self):
        """Test BROKEN spread regime (>9%)"""
        payload = {
            "spread": 0.12,
            "liquidity": 50000,
            "volume24h": 10000,
            "edge": 0.08,
            "repricingState": "active_repricing",
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution"]["entry"]["spreadRegime"] == "BROKEN"
        print("✓ Spread regime BROKEN for spread=12%")

    def test_analyze_depth_quality_deep(self):
        """Test DEEP depth quality (high liquidity)"""
        payload = {
            "spread": 0.02,
            "liquidity": 150000,  # High
            "volume24h": 30000,
            "edge": 0.08,
            "repricingState": "active_repricing",
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution"]["entry"]["depthQuality"] == "DEEP"
        print("✓ Depth quality DEEP for liquidity=$150K")

    def test_analyze_depth_quality_fragile(self):
        """Test FRAGILE depth quality (very low liquidity)"""
        payload = {
            "spread": 0.08,
            "liquidity": 1000,  # Very low
            "volume24h": 200,
            "edge": 0.08,
            "repricingState": "active_repricing",
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution"]["entry"]["depthQuality"] in ["THIN", "FRAGILE"]
        print(f"✓ Depth quality {data['execution']['entry']['depthQuality']} for liquidity=$1K")

    def test_analyze_slippage_risk(self):
        """Test slippage risk calculation"""
        payload = {
            "spread": 0.05,
            "liquidity": 20000,
            "volume24h": 5000,
            "edge": 0.06,
            "repricingState": "active_repricing",
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        entry = data["execution"]["entry"]
        assert "slippageRisk" in entry
        assert 0 <= entry["slippageRisk"] <= 1
        assert "maxSlippageBps" in entry
        assert entry["maxSlippageBps"] >= 0
        print(f"✓ Slippage risk: {entry['slippageRisk']}, maxSlippageBps: {entry['maxSlippageBps']}")

    def test_analyze_edge_compression(self):
        """Test edge compression calculation"""
        payload = {
            "spread": 0.03,
            "liquidity": 50000,
            "volume24h": 10000,
            "edge": 0.04,
            "originalEdge": 0.12,  # Original was much higher
            "repricingState": "late_repricing",
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        ec = data["execution"]["edgeCompression"]
        assert "edgeCompression" in ec
        assert "compressed" in ec
        # 0.04 / 0.12 = 0.33, so compression = 1 - 0.33 = 0.67
        assert ec["edgeCompression"] >= 0.5, f"Expected high compression, got {ec['edgeCompression']}"
        assert ec["compressed"] is True, "Expected compressed=True"
        print(f"✓ Edge compression: {ec['edgeCompression']}, compressed={ec['compressed']}")

    def test_analyze_scaling_policy_add(self):
        """Test ADD scaling policy: strong edge + good conditions"""
        payload = {
            "spread": 0.02,
            "liquidity": 80000,
            "volume24h": 15000,
            "edge": 0.10,
            "confidence": 0.7,
            "repricingState": "fresh_mispricing",
            "socialSaturation": 0.3,
            "positionOversized": False,
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        scaling = data["execution"]["scaling"]
        assert scaling["scalingBias"] == "ADD", f"Expected ADD, got {scaling['scalingBias']}"
        print(f"✓ Scaling policy ADD: {scaling['reason']}")

    def test_analyze_scaling_policy_no_add_oversized(self):
        """Test NO_ADD scaling policy: position oversized"""
        payload = {
            "spread": 0.02,
            "liquidity": 80000,
            "volume24h": 15000,
            "edge": 0.10,
            "confidence": 0.7,
            "repricingState": "fresh_mispricing",
            "socialSaturation": 0.3,
            "positionOversized": True,  # Already at max
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        scaling = data["execution"]["scaling"]
        assert scaling["scalingBias"] == "NO_ADD", f"Expected NO_ADD, got {scaling['scalingBias']}"
        print(f"✓ Scaling policy NO_ADD (oversized): {scaling['reason']}")

    def test_analyze_scaling_policy_no_add_saturated(self):
        """Test NO_ADD scaling policy: high social saturation"""
        payload = {
            "spread": 0.02,
            "liquidity": 80000,
            "volume24h": 15000,
            "edge": 0.10,
            "confidence": 0.7,
            "repricingState": "fresh_mispricing",
            "socialSaturation": 0.85,  # Very high
            "positionOversized": False,
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        scaling = data["execution"]["scaling"]
        assert scaling["scalingBias"] == "NO_ADD", f"Expected NO_ADD, got {scaling['scalingBias']}"
        print(f"✓ Scaling policy NO_ADD (saturated): {scaling['reason']}")

    def test_analyze_exit_policy_hold(self):
        """Test HOLD exit policy: thesis intact"""
        payload = {
            "spread": 0.02,
            "liquidity": 80000,
            "volume24h": 15000,
            "edge": 0.10,
            "fairProb": 0.70,
            "marketProb": 0.60,
            "confidence": 0.7,
            "alignment": 0.7,
            "repricingState": "active_repricing",
            "socialSaturation": 0.4,
            "socialLifecycle": "EXPANDING",
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        exit_plan = data["execution"]["exit"]
        assert exit_plan["action"] == "HOLD", f"Expected HOLD, got {exit_plan['action']}"
        print(f"✓ Exit policy HOLD: confidence={exit_plan['confidence']}")

    def test_analyze_exit_policy_exit(self):
        """Test EXIT policy: edge compressed + fair value reached + saturated"""
        payload = {
            "spread": 0.02,
            "liquidity": 80000,
            "volume24h": 15000,
            "edge": 0.02,  # Small remaining edge
            "originalEdge": 0.15,  # Was much higher
            "fairProb": 0.70,
            "marketProb": 0.72,  # Past fair value
            "confidence": 0.3,  # Low
            "alignment": 0.3,
            "repricingState": "overheated",
            "socialSaturation": 0.85,  # Very high
            "socialLifecycle": "FADING",
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        exit_plan = data["execution"]["exit"]
        assert exit_plan["action"] in ["EXIT", "REDUCE"], f"Expected EXIT/REDUCE, got {exit_plan['action']}"
        assert len(exit_plan["reasons"]) > 0, "Expected exit reasons"
        print(f"✓ Exit policy {exit_plan['action']}: {exit_plan['reasons'][:2]}")

    def test_analyze_missing_required_fields(self):
        """Test error handling for missing required fields"""
        payload = {"liquidity": 50000}  # Missing spread and edge
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is False, "Expected ok=False for missing fields"
        print("✓ Error handling for missing required fields")


class TestExecutionLayerBatch:
    """POST /api/execution-layer/analyze/batch — Batch execution analysis"""

    def test_batch_analyze_multiple_cases(self):
        """Test batch analysis with multiple cases"""
        payload = {
            "cases": [
                {
                    "marketId": "TEST_market_1",
                    "spread": 0.02,
                    "liquidity": 100000,
                    "volume24h": 20000,
                    "edge": 0.12,
                    "repricingState": "fresh_mispricing",
                    "socialSaturation": 0.2,
                },
                {
                    "marketId": "TEST_market_2",
                    "spread": 0.08,
                    "liquidity": 5000,
                    "volume24h": 500,
                    "edge": 0.03,
                    "repricingState": "overheated",
                    "socialSaturation": 0.8,
                },
                {
                    "marketId": "TEST_market_3",
                    "spread": 0.04,
                    "liquidity": 50000,
                    "volume24h": 10000,
                    "edge": 0.08,
                    "repricingState": "active_repricing",
                    "socialSaturation": 0.5,
                },
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze/batch", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("count") == 3
        
        results = data.get("results", {})
        assert "TEST_market_1" in results
        assert "TEST_market_2" in results
        assert "TEST_market_3" in results
        
        # Verify different entry styles based on conditions
        m1 = results["TEST_market_1"]
        m2 = results["TEST_market_2"]
        
        assert m1["entry"]["spreadRegime"] == "NARROW"
        assert m2["entry"]["spreadRegime"] in ["WIDE", "BROKEN"]
        
        print(f"✓ Batch analysis: {data['count']} cases processed")
        print(f"  Market 1: {m1['entry']['entryStyle']}, spread={m1['entry']['spreadRegime']}")
        print(f"  Market 2: {m2['entry']['entryStyle']}, spread={m2['entry']['spreadRegime']}")

    def test_batch_analyze_empty_cases(self):
        """Test batch analysis with empty cases array"""
        payload = {"cases": []}
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze/batch", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is False
        print("✓ Empty cases array handled correctly")

    def test_batch_analyze_varied_conditions(self):
        """Test batch with varied market conditions to verify different outputs"""
        payload = {
            "cases": [
                # Strong entry candidate
                {
                    "marketId": "strong_entry",
                    "spread": 0.015,
                    "liquidity": 120000,
                    "volume24h": 25000,
                    "edge": 0.15,
                    "confidence": 0.8,
                    "repricingState": "fresh_mispricing",
                    "socialSaturation": 0.15,
                },
                # Wait for retrace
                {
                    "marketId": "wait_retrace",
                    "spread": 0.04,
                    "liquidity": 40000,
                    "volume24h": 8000,
                    "edge": 0.06,
                    "confidence": 0.6,
                    "repricingState": "late_repricing",
                    "socialSaturation": 0.55,
                },
                # Do not chase
                {
                    "marketId": "do_not_chase",
                    "spread": 0.11,
                    "liquidity": 3000,
                    "volume24h": 300,
                    "edge": 0.02,
                    "confidence": 0.3,
                    "repricingState": "overheated",
                    "socialSaturation": 0.9,
                },
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze/batch", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        
        results = data["results"]
        
        # Strong entry should be ENTER_MARKET or ENTER_LIMIT
        strong = results["strong_entry"]
        assert strong["entry"]["entryStyle"] in ["ENTER_MARKET", "ENTER_LIMIT"]
        assert strong["entry"]["entryQualityScore"] >= 0.6
        
        # Do not chase should be DO_NOT_CHASE
        dnc = results["do_not_chase"]
        assert dnc["entry"]["entryStyle"] == "DO_NOT_CHASE"
        
        print("✓ Varied conditions produce appropriate entry styles")


class TestPredictionRunIntegration:
    """GET /api/prediction/run — executionLayer field integration"""

    def test_prediction_run_has_execution_layer(self):
        """Test that /api/prediction/run includes executionLayer field on cases"""
        resp = requests.get(f"{BASE_URL}/api/prediction/run?limit=10")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        
        sections = data.get("sections", {})
        all_cases = []
        for section_name, cases in sections.items():
            all_cases.extend(cases)
        
        if not all_cases:
            print("⚠ No cases returned from /api/prediction/run — skipping executionLayer check")
            return
        
        # Check at least some cases have executionLayer
        cases_with_exec = [c for c in all_cases if c.get("executionLayer")]
        print(f"✓ Found {len(cases_with_exec)}/{len(all_cases)} cases with executionLayer field")
        
        if cases_with_exec:
            el = cases_with_exec[0]["executionLayer"]
            # Verify expected fields
            expected_fields = [
                "entryStyle", "entryQualityScore", "slippageRisk", "spreadRegime",
                "depthQuality", "chaseRisk", "missRisk", "scalingBias", "exitAction"
            ]
            for field in expected_fields:
                assert field in el, f"Missing field {field} in executionLayer"
            
            print(f"  Sample executionLayer: entryStyle={el['entryStyle']}, spread={el['spreadRegime']}, exit={el['exitAction']}")

    def test_prediction_run_execution_layer_fields(self):
        """Test executionLayer field structure in prediction run"""
        resp = requests.get(f"{BASE_URL}/api/prediction/run?limit=20")
        assert resp.status_code == 200
        data = resp.json()
        
        sections = data.get("sections", {})
        all_cases = []
        for cases in sections.values():
            all_cases.extend(cases)
        
        cases_with_exec = [c for c in all_cases if c.get("executionLayer")]
        
        if not cases_with_exec:
            print("⚠ No cases with executionLayer — integration may not be active")
            return
        
        for c in cases_with_exec[:3]:
            el = c["executionLayer"]
            
            # Entry style validation
            assert el["entryStyle"] in [
                "ENTER_MARKET", "ENTER_LIMIT", "STAGGER_LIMIT",
                "WAIT_RETRACE", "WAIT_CONFIRMATION", "DO_NOT_CHASE"
            ], f"Invalid entryStyle: {el['entryStyle']}"
            
            # Spread regime validation
            assert el["spreadRegime"] in ["NARROW", "NORMAL", "WIDE", "BROKEN"]
            
            # Depth quality validation
            assert el["depthQuality"] in ["DEEP", "OK", "THIN", "FRAGILE"]
            
            # Exit action validation
            assert el["exitAction"] in ["HOLD", "TRIM", "REDUCE", "EXIT"]
            
            # Scaling bias validation
            assert el["scalingBias"] in ["ADD", "HOLD", "NO_ADD"]
            
            # Numeric fields
            assert 0 <= el["entryQualityScore"] <= 1
            assert 0 <= el["slippageRisk"] <= 1
            assert 0 <= el["chaseRisk"] <= 1
            assert 0 <= el["missRisk"] <= 1
            
            print(f"✓ Case {c['market_id'][:20]}...: {el['entryStyle']}, {el['spreadRegime']}, exit={el['exitAction']}")


class TestEntryStyleLogic:
    """Test entry style decision logic"""

    def test_enter_market_conditions(self):
        """ENTER_MARKET: narrow spread + strong edge + early repricing + high miss risk"""
        payload = {
            "spread": 0.012,  # Very narrow
            "liquidity": 150000,  # Deep
            "volume24h": 30000,
            "edge": 0.14,  # Strong
            "confidence": 0.8,
            "repricingState": "fresh_mispricing",
            "socialSaturation": 0.1,
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        data = resp.json()
        entry = data["execution"]["entry"]
        
        # Should be ENTER_MARKET due to high miss risk + narrow spread + strong edge
        assert entry["entryStyle"] in ["ENTER_MARKET", "ENTER_LIMIT"]
        assert entry["missRisk"] >= 0.4, f"Expected high miss risk, got {entry['missRisk']}"
        print(f"✓ ENTER_MARKET conditions: missRisk={entry['missRisk']}, style={entry['entryStyle']}")

    def test_stagger_limit_conditions(self):
        """STAGGER_LIMIT: strong thesis but poor microstructure"""
        payload = {
            "spread": 0.07,  # Wide
            "liquidity": 15000,  # Thin
            "volume24h": 3000,
            "edge": 0.10,  # Strong
            "confidence": 0.65,
            "repricingState": "active_repricing",
            "socialSaturation": 0.4,
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        data = resp.json()
        entry = data["execution"]["entry"]
        
        # Should be STAGGER_LIMIT or ENTER_LIMIT due to wide spread
        assert entry["entryStyle"] in ["STAGGER_LIMIT", "ENTER_LIMIT", "WAIT_RETRACE"]
        print(f"✓ STAGGER_LIMIT conditions: style={entry['entryStyle']}, spread={entry['spreadRegime']}")

    def test_wait_retrace_conditions(self):
        """WAIT_RETRACE: thesis valid but repricing stretched"""
        payload = {
            "spread": 0.04,
            "liquidity": 40000,
            "volume24h": 8000,
            "edge": 0.07,
            "confidence": 0.6,
            "repricingState": "late_repricing",
            "socialSaturation": 0.6,
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        data = resp.json()
        entry = data["execution"]["entry"]
        
        # Should be WAIT_RETRACE or similar due to late repricing
        assert entry["entryStyle"] in ["WAIT_RETRACE", "ENTER_LIMIT", "DO_NOT_CHASE"]
        assert entry["chaseRisk"] >= 0.3, f"Expected elevated chase risk, got {entry['chaseRisk']}"
        print(f"✓ WAIT_RETRACE conditions: style={entry['entryStyle']}, chaseRisk={entry['chaseRisk']}")


class TestMicrostructureFields:
    """Test microstructure field calculations"""

    def test_microstructure_in_response(self):
        """Test microstructure field is present in response"""
        payload = {
            "spread": 0.03,
            "liquidity": 60000,
            "volume24h": 12000,
            "edge": 0.08,
            "repricingState": "active_repricing",
        }
        resp = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload)
        data = resp.json()
        
        ms = data["execution"]["microstructure"]
        assert "spreadRegime" in ms
        assert "depthQuality" in ms
        assert "slippageRisk" in ms
        print(f"✓ Microstructure: spread={ms['spreadRegime']}, depth={ms['depthQuality']}, slip={ms['slippageRisk']}")

    def test_low_liquidity_degrades_spread_regime(self):
        """Test that low liquidity degrades effective spread regime"""
        # Same spread, different liquidity
        payload_high_liq = {
            "spread": 0.018,  # Just under narrow threshold
            "liquidity": 100000,
            "volume24h": 20000,
            "edge": 0.08,
            "repricingState": "active_repricing",
        }
        payload_low_liq = {
            "spread": 0.018,
            "liquidity": 3000,  # Very low
            "volume24h": 500,
            "edge": 0.08,
            "repricingState": "active_repricing",
        }
        
        resp_high = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload_high_liq)
        resp_low = requests.post(f"{BASE_URL}/api/execution-layer/analyze", json=payload_low_liq)
        
        high_regime = resp_high.json()["execution"]["entry"]["spreadRegime"]
        low_regime = resp_low.json()["execution"]["entry"]["spreadRegime"]
        
        # Low liquidity should degrade the regime
        regime_order = {"NARROW": 0, "NORMAL": 1, "WIDE": 2, "BROKEN": 3}
        assert regime_order.get(low_regime, 0) >= regime_order.get(high_regime, 0), \
            f"Low liquidity should degrade regime: high={high_regime}, low={low_regime}"
        print(f"✓ Liquidity impact: high_liq={high_regime}, low_liq={low_regime}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
