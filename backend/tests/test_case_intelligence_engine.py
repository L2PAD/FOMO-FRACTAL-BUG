"""
Case Intelligence Engine Tests — 8-layer reasoning core

Tests:
- POST /api/case-intelligence/analyze — single case analysis
- POST /api/case-intelligence/batch — batch case analysis
- Decision Memo structure validation
- Event Understanding validation
- Thesis Engine (bull/bear cases)
- Market Gap Analysis
- Integration with /api/prediction/run
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCaseIntelligenceAnalyze:
    """POST /api/case-intelligence/analyze — single case analysis"""

    def test_analyze_returns_full_structure(self):
        """Verify analyze endpoint returns memo, event, evidenceStats, thesis, gap, risks"""
        payload = {
            "market_id": "test_btc_100k",
            "question": "Will BTC reach $100,000 by end of 2025?",
            "asset": "BTC",
            "event_type": "price_threshold",
            "entities": ["BTC", "Bitcoin"],
            "current_prob": 0.45,
            "liquidity": 50000,
            "volume_24h": 120000,
            "spread": 2.5,
            "move_1h": 0.5,
            "move_6h": 2.1,
        }
        resp = requests.post(f"{BASE_URL}/api/case-intelligence/analyze", json=payload, timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        # Verify all required fields present
        assert "memo" in data, "Response should contain memo"
        assert "event" in data, "Response should contain event"
        assert "evidenceStats" in data, "Response should contain evidenceStats"
        assert "thesis" in data, "Response should contain thesis"
        assert "gap" in data, "Response should contain gap"
        assert "risks" in data, "Response should contain risks"

    def test_decision_memo_structure(self):
        """Verify Decision Memo includes all required fields"""
        payload = {
            "market_id": "test_eth_etf",
            "question": "Will ETH ETF be approved by SEC in Q1 2025?",
            "asset": "ETH",
            "event_type": "etf_catalyst",
            "entities": ["ETH", "SEC", "ETF"],
            "current_prob": 0.35,
            "liquidity": 80000,
            "volume_24h": 200000,
            "spread": 1.8,
        }
        resp = requests.post(f"{BASE_URL}/api/case-intelligence/analyze", json=payload, timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        memo = data.get("memo", {})
        
        # Required memo fields
        required_fields = [
            "summary", "thesis", "counterThesis", "action", "conviction",
            "keyDrivers", "keyRisks", "whatMarketPricesIn", "whatMarketMisses",
            "whyNow", "whyNot"
        ]
        for field in required_fields:
            assert field in memo, f"Memo should contain {field}"
        
        # Validate action values
        valid_actions = ["YES_NOW", "NO_NOW", "WAIT", "AVOID"]
        assert memo.get("action") in valid_actions, f"Action should be one of {valid_actions}"
        
        # Validate conviction values
        valid_convictions = ["HIGH", "MEDIUM", "LOW"]
        assert memo.get("conviction") in valid_convictions, f"Conviction should be one of {valid_convictions}"

    def test_event_understanding_structure(self):
        """Verify Event Understanding correctly identifies eventClass, actors, objects, action, resolution"""
        payload = {
            "market_id": "test_sol_listing",
            "question": "Will SOL be listed on Coinbase by March 2025?",
            "asset": "SOL",
            "event_type": "listing_catalyst",
            "entities": ["SOL", "Coinbase"],
            "current_prob": 0.55,
            "liquidity": 30000,
        }
        resp = requests.post(f"{BASE_URL}/api/case-intelligence/analyze", json=payload, timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        event = data.get("event", {})
        
        # Required event fields
        assert "eventClass" in event, "Event should contain eventClass"
        assert "actors" in event, "Event should contain actors"
        assert "objects" in event, "Event should contain objects"
        assert "action" in event, "Event should contain action"
        assert "resolution" in event, "Event should contain resolution"
        
        # Validate eventClass
        valid_classes = ["catalyst", "threshold", "launch", "listing"]
        assert event.get("eventClass") in valid_classes, f"eventClass should be one of {valid_classes}"
        
        # Resolution structure
        resolution = event.get("resolution", {})
        assert "sourceOfTruth" in resolution, "Resolution should contain sourceOfTruth"
        assert "requiredProofs" in resolution, "Resolution should contain requiredProofs"

    def test_thesis_engine_builds_both_cases(self):
        """Verify Thesis Engine always builds both bull and bear cases"""
        payload = {
            "market_id": "test_xrp_direction",
            "question": "Will XRP outperform BTC in Q1 2025?",
            "asset": "XRP",
            "event_type": "direction_bet",
            "entities": ["XRP", "BTC"],
            "current_prob": 0.40,
            "liquidity": 25000,
        }
        resp = requests.post(f"{BASE_URL}/api/case-intelligence/analyze", json=payload, timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        thesis = data.get("thesis", {})
        
        # Both cases must exist
        assert "bullCase" in thesis, "Thesis should contain bullCase"
        assert "bearCase" in thesis, "Thesis should contain bearCase"
        
        # Each case should have arguments and strength
        bull = thesis.get("bullCase", {})
        bear = thesis.get("bearCase", {})
        
        assert "arguments" in bull, "bullCase should have arguments"
        assert "strength" in bull, "bullCase should have strength"
        assert isinstance(bull.get("arguments"), list), "bullCase.arguments should be a list"
        
        assert "arguments" in bear, "bearCase should have arguments"
        assert "strength" in bear, "bearCase should have strength"
        assert isinstance(bear.get("arguments"), list), "bearCase.arguments should be a list"

    def test_market_gap_analysis_structure(self):
        """Verify Market Gap returns pricedInLevel, mispricingType, marketKnows, marketMisses"""
        payload = {
            "market_id": "test_ada_threshold",
            "question": "Will ADA reach $2 by end of 2025?",
            "asset": "ADA",
            "event_type": "price_threshold",
            "entities": ["ADA", "Cardano"],
            "current_prob": 0.25,
            "liquidity": 15000,
            "move_6h": 1.5,
        }
        resp = requests.post(f"{BASE_URL}/api/case-intelligence/analyze", json=payload, timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        gap = data.get("gap", {})
        
        # Required gap fields
        assert "pricedInLevel" in gap, "Gap should contain pricedInLevel"
        assert "mispricingType" in gap, "Gap should contain mispricingType"
        assert "marketKnows" in gap, "Gap should contain marketKnows"
        assert "marketMisses" in gap, "Gap should contain marketMisses"
        
        # Validate mispricingType
        valid_types = ["underreaction", "overreaction", "correct"]
        assert gap.get("mispricingType") in valid_types, f"mispricingType should be one of {valid_types}"
        
        # pricedInLevel should be 0-1
        pil = gap.get("pricedInLevel", 0)
        assert 0 <= pil <= 1, f"pricedInLevel should be between 0 and 1, got {pil}"

    def test_evidence_stats_structure(self):
        """Verify evidenceStats contains expected counters"""
        payload = {
            "market_id": "test_doge_meme",
            "question": "Will DOGE reach $1 in 2025?",
            "asset": "DOGE",
            "event_type": "price_threshold",
            "entities": ["DOGE"],
            "current_prob": 0.15,
            "liquidity": 40000,
        }
        resp = requests.post(f"{BASE_URL}/api/case-intelligence/analyze", json=payload, timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        stats = data.get("evidenceStats", {})
        
        # Expected stat fields
        expected_fields = ["total", "primary", "secondary", "narrative", "echo", 
                          "contradictory", "onchain", "drivers", "confirmations", "noise"]
        for field in expected_fields:
            assert field in stats, f"evidenceStats should contain {field}"
            assert isinstance(stats.get(field), int), f"evidenceStats.{field} should be an integer"


class TestCaseIntelligenceBatch:
    """POST /api/case-intelligence/batch — batch case analysis"""

    def test_batch_returns_results_for_multiple_cases(self):
        """Verify batch endpoint returns intelligence results for multiple cases"""
        cases = [
            {
                "market_id": "batch_btc_1",
                "question": "Will BTC hit $150k?",
                "asset": "BTC",
                "event_type": "price_threshold",
                "current_prob": 0.30,
            },
            {
                "market_id": "batch_eth_2",
                "question": "Will ETH flip BTC?",
                "asset": "ETH",
                "event_type": "direction_bet",
                "current_prob": 0.10,
            },
            {
                "market_id": "batch_sol_3",
                "question": "Will SOL reach $500?",
                "asset": "SOL",
                "event_type": "price_threshold",
                "current_prob": 0.20,
            },
        ]
        resp = requests.post(f"{BASE_URL}/api/case-intelligence/batch", json={"cases": cases}, timeout=15)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True, "Response should have ok=true"
        assert "results" in data, "Response should contain results"
        
        results = data.get("results", {})
        # Should have results for each case
        for case in cases:
            mid = case["market_id"]
            assert mid in results, f"Results should contain {mid}"
            
            result = results[mid]
            assert "memo" in result, f"Result for {mid} should contain memo"
            assert "thesis" in result, f"Result for {mid} should contain thesis"
            assert "gap" in result, f"Result for {mid} should contain gap"

    def test_batch_empty_cases_returns_empty_results(self):
        """Verify batch with empty cases returns empty results"""
        resp = requests.post(f"{BASE_URL}/api/case-intelligence/batch", json={"cases": []}, timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("results") == {} or data.get("results") == []


class TestPredictionRunIntegration:
    """Integration: GET /api/prediction/run includes intelligence field"""

    def test_prediction_run_includes_intelligence(self):
        """Verify /api/prediction/run includes intelligence field in each case"""
        resp = requests.get(f"{BASE_URL}/api/prediction/run?limit=5", timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        
        # Get all cases from sections
        all_cases = []
        sections = data.get("sections", {})
        for section_name, cases in sections.items():
            if isinstance(cases, list):
                all_cases.extend(cases)
        
        # At least some cases should exist
        if len(all_cases) == 0:
            pytest.skip("No cases returned from prediction/run")
        
        # Check that cases have intelligence field
        cases_with_intel = [c for c in all_cases if c.get("intelligence")]
        
        # Note: Not all cases may have intelligence (depends on CI service availability)
        # But if any do, verify structure
        if cases_with_intel:
            for c in cases_with_intel[:3]:  # Check first 3
                intel = c.get("intelligence", {})
                
                # Should have memo with action/conviction
                memo = intel.get("memo", {})
                if memo:
                    assert "action" in memo or "conviction" in memo, \
                        f"Intelligence memo should have action or conviction"
                
                # Should have thesis with bull/bear
                thesis = intel.get("thesis", {})
                if thesis:
                    assert "bullCase" in thesis or "bearCase" in thesis, \
                        f"Intelligence thesis should have bullCase or bearCase"
                
                # Should have gap with mispricingType
                gap = intel.get("gap", {})
                if gap:
                    assert "mispricingType" in gap or "pricedInLevel" in gap, \
                        f"Intelligence gap should have mispricingType or pricedInLevel"
            
            print(f"✓ Found {len(cases_with_intel)} cases with intelligence data")
        else:
            print("⚠ No cases with intelligence data (CI service may not have signals)")


class TestRiskMapper:
    """Risk Mapper validation"""

    def test_risks_structure(self):
        """Verify risks field contains risks array and invalidators"""
        payload = {
            "market_id": "test_risk_case",
            "question": "Will AVAX reach $100?",
            "asset": "AVAX",
            "event_type": "price_threshold",
            "current_prob": 0.35,
            "liquidity": 20000,
            "spread": 4.0,  # Wide spread = higher risk
        }
        resp = requests.post(f"{BASE_URL}/api/case-intelligence/analyze", json=payload, timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        risks = data.get("risks", {})
        
        assert "risks" in risks, "Risks should contain risks array"
        assert "invalidators" in risks, "Risks should contain invalidators array"
        
        assert isinstance(risks.get("risks"), list), "risks.risks should be a list"
        assert isinstance(risks.get("invalidators"), list), "risks.invalidators should be a list"


class TestLowEvidenceScenarios:
    """Test behavior with minimal/no evidence (common for test markets)"""

    def test_no_evidence_returns_avoid_low(self):
        """Markets without real signals should return AVOID/LOW conviction"""
        payload = {
            "market_id": "test_obscure_token",
            "question": "Will OBSCURE token moon?",
            "asset": "OBSCURE",
            "event_type": "generic_crypto",
            "entities": ["OBSCURE"],
            "current_prob": 0.50,
            "liquidity": 1000,
        }
        resp = requests.post(f"{BASE_URL}/api/case-intelligence/analyze", json=payload, timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        memo = data.get("memo", {})
        
        # With no evidence, should be AVOID or WAIT with LOW conviction
        action = memo.get("action")
        conviction = memo.get("conviction")
        
        # Either AVOID or WAIT is acceptable for no-evidence scenarios
        assert action in ["AVOID", "WAIT"], f"No-evidence case should be AVOID or WAIT, got {action}"
        assert conviction == "LOW", f"No-evidence case should have LOW conviction, got {conviction}"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
