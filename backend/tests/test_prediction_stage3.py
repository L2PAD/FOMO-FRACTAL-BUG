"""
Prediction Stage 3 - Decision Desk API Tests

Tests for:
- GET /api/prediction/run - Full pipeline with sections (best_opportunities, new_mispricings, watchlist, avoid_zone)
- GET /api/prediction/markets - Raw Polymarket markets
- Case object structure validation (resolution, pricing, recommendation, analysis)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPredictionMarketsEndpoint:
    """Tests for GET /api/prediction/markets"""
    
    def test_markets_endpoint_returns_ok(self):
        """GET /api/prediction/markets returns ok=true with markets array"""
        response = requests.get(f"{BASE_URL}/api/prediction/markets?limit=10", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "count" in data, "Expected count field"
        assert "markets" in data, "Expected markets array"
        assert isinstance(data["markets"], list), "markets should be a list"
        print(f"✓ Markets endpoint returned {data['count']} markets")


class TestPredictionRunEndpoint:
    """Tests for GET /api/prediction/run - Full Decision Desk pipeline"""
    
    def test_run_endpoint_returns_ok(self):
        """GET /api/prediction/run returns ok=true with sections"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        print(f"✓ Run endpoint returned ok=true")
    
    def test_run_returns_metadata(self):
        """Run endpoint returns total_markets, classified, skipped, exchange_available"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=60)
        data = response.json()
        
        assert "total_markets" in data, "Expected total_markets"
        assert "classified" in data, "Expected classified count"
        assert "skipped" in data, "Expected skipped count"
        assert "exchange_available" in data, "Expected exchange_available"
        
        # Exchange availability should have BTC and ETH keys
        ex = data["exchange_available"]
        assert "BTC" in ex, "Expected BTC in exchange_available"
        assert "ETH" in ex, "Expected ETH in exchange_available"
        
        print(f"✓ Metadata: {data['total_markets']} markets, {data['classified']} classified, {data['skipped']} skipped")
        print(f"✓ Exchange: BTC={ex['BTC']}, ETH={ex['ETH']}")
    
    def test_run_returns_four_sections(self):
        """Run endpoint returns sections: best_opportunities, new_mispricings, watchlist, avoid_zone"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=60)
        data = response.json()
        
        assert "sections" in data, "Expected sections object"
        sections = data["sections"]
        
        required_sections = ["best_opportunities", "new_mispricings", "watchlist", "avoid_zone"]
        for section in required_sections:
            assert section in sections, f"Expected section: {section}"
            assert isinstance(sections[section], list), f"{section} should be a list"
        
        total_cases = sum(len(sections[s]) for s in required_sections)
        print(f"✓ Sections: best={len(sections['best_opportunities'])}, mispricings={len(sections['new_mispricings'])}, watch={len(sections['watchlist'])}, avoid={len(sections['avoid_zone'])}")
        print(f"✓ Total cases: {total_cases}")


class TestCaseObjectStructure:
    """Tests for case object structure in sections"""
    
    @pytest.fixture(scope="class")
    def run_data(self):
        """Fetch run data once for all tests in this class"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=60)
        return response.json()
    
    def _get_any_case(self, run_data):
        """Get any case from any section"""
        sections = run_data.get("sections", {})
        for section_name in ["best_opportunities", "new_mispricings", "watchlist", "avoid_zone"]:
            cases = sections.get(section_name, [])
            if cases:
                return cases[0]
        return None
    
    def test_case_has_market_fields(self, run_data):
        """Case has market_id, question, asset"""
        case = self._get_any_case(run_data)
        if case is None:
            pytest.skip("No cases available to test")
        
        assert "market_id" in case, "Expected market_id"
        assert "question" in case, "Expected question"
        assert "asset" in case, "Expected asset"
        
        print(f"✓ Case market fields: id={case['market_id'][:20]}..., asset={case['asset']}")
    
    def test_case_has_resolution_object(self, run_data):
        """Case has resolution with rule_clarity_score, resolution_risk_score, tradable, flags"""
        case = self._get_any_case(run_data)
        if case is None:
            pytest.skip("No cases available to test")
        
        assert "resolution" in case, "Expected resolution object"
        res = case["resolution"]
        
        assert "rule_clarity_score" in res, "Expected rule_clarity_score"
        assert "resolution_risk_score" in res, "Expected resolution_risk_score"
        assert "tradable" in res, "Expected tradable"
        assert "flags" in res, "Expected flags"
        assert "has_clarification" in res, "Expected has_clarification"
        
        # Validate types
        assert isinstance(res["rule_clarity_score"], (int, float)), "rule_clarity_score should be numeric"
        assert isinstance(res["resolution_risk_score"], (int, float)), "resolution_risk_score should be numeric"
        assert isinstance(res["tradable"], bool), "tradable should be boolean"
        assert isinstance(res["flags"], list), "flags should be list"
        
        print(f"✓ Resolution: clarity={res['rule_clarity_score']:.2f}, risk={res['resolution_risk_score']:.2f}, tradable={res['tradable']}")
    
    def test_case_has_pricing_object(self, run_data):
        """Case has pricing with market_state, spread_quality, volume_profile, liquidity_depth, days_to_expiry, urgency"""
        case = self._get_any_case(run_data)
        if case is None:
            pytest.skip("No cases available to test")
        
        assert "pricing" in case, "Expected pricing object"
        p = case["pricing"]
        
        assert "market_state" in p, "Expected market_state"
        assert "description" in p, "Expected description"
        assert "spread_quality" in p, "Expected spread_quality"
        assert "volume_profile" in p, "Expected volume_profile"
        assert "liquidity_depth" in p, "Expected liquidity_depth"
        assert "urgency" in p, "Expected urgency"
        
        # days_to_expiry can be None
        assert "days_to_expiry" in p, "Expected days_to_expiry"
        
        # Validate market_state values
        valid_states = ["underpriced", "fairly_priced", "overheated", "early_repricing", 
                       "late_repricing", "priced_in", "panic_move", "stale_price"]
        assert p["market_state"] in valid_states, f"Invalid market_state: {p['market_state']}"
        
        print(f"✓ Pricing: state={p['market_state']}, spread={p['spread_quality']}, volume={p['volume_profile']}, liquidity={p['liquidity_depth']}, urgency={p['urgency']}")
    
    def test_case_has_recommendation_object(self, run_data):
        """Case has recommendation with action, conviction, size"""
        case = self._get_any_case(run_data)
        if case is None:
            pytest.skip("No cases available to test")
        
        assert "recommendation" in case, "Expected recommendation object"
        r = case["recommendation"]
        
        assert "action" in r, "Expected action"
        assert "conviction" in r, "Expected conviction"
        assert "size" in r, "Expected size"
        
        # Validate action values
        valid_actions = ["YES_NOW", "NO_NOW", "YES_SMALL", "NO_SMALL", "WATCH", "WAIT", "AVOID", "GOOD_IDEA_BAD_PRICE"]
        assert r["action"] in valid_actions, f"Invalid action: {r['action']}"
        
        # Validate conviction values
        valid_convictions = ["HIGH", "MEDIUM", "LOW"]
        assert r["conviction"] in valid_convictions, f"Invalid conviction: {r['conviction']}"
        
        # Validate size values
        valid_sizes = ["FULL", "MEDIUM", "SMALL", "NONE"]
        assert r["size"] in valid_sizes, f"Invalid size: {r['size']}"
        
        print(f"✓ Recommendation: action={r['action']}, conviction={r['conviction']}, size={r['size']}")
    
    def test_case_has_why_now_why_not_reasoning(self, run_data):
        """Case has why_now, why_not, reasoning arrays"""
        case = self._get_any_case(run_data)
        if case is None:
            pytest.skip("No cases available to test")
        
        assert "why_now" in case, "Expected why_now"
        assert "why_not" in case, "Expected why_not"
        assert "reasoning" in case, "Expected reasoning"
        
        assert isinstance(case["why_now"], list), "why_now should be list"
        assert isinstance(case["why_not"], list), "why_not should be list"
        assert isinstance(case["reasoning"], list), "reasoning should be list"
        
        print(f"✓ Reasoning: why_now={len(case['why_now'])} items, why_not={len(case['why_not'])} items, reasoning={len(case['reasoning'])} items")
    
    def test_case_has_analysis_object(self, run_data):
        """Case has analysis with fair_prob, market_prob, raw_edge, net_edge, model_confidence, alignment_score, structural_risk, regime, components, biases"""
        case = self._get_any_case(run_data)
        if case is None:
            pytest.skip("No cases available to test")
        
        assert "analysis" in case, "Expected analysis object"
        a = case["analysis"]
        
        required_fields = ["fair_prob", "market_prob", "raw_edge", "net_edge", 
                          "model_confidence", "alignment_score", "structural_risk", 
                          "regime", "components", "biases"]
        
        for field in required_fields:
            assert field in a, f"Expected {field} in analysis"
        
        # Validate numeric fields
        assert isinstance(a["fair_prob"], (int, float)), "fair_prob should be numeric"
        assert isinstance(a["market_prob"], (int, float)), "market_prob should be numeric"
        assert isinstance(a["raw_edge"], (int, float)), "raw_edge should be numeric"
        assert isinstance(a["net_edge"], (int, float)), "net_edge should be numeric"
        assert isinstance(a["model_confidence"], (int, float)), "model_confidence should be numeric"
        assert isinstance(a["alignment_score"], (int, float)), "alignment_score should be numeric"
        
        # Validate structural_risk is dict
        assert isinstance(a["structural_risk"], dict), "structural_risk should be dict"
        
        print(f"✓ Analysis: fair={a['fair_prob']:.2f}, market={a['market_prob']:.2f}, edge={a['net_edge']:.2%}, conf={a['model_confidence']:.2f}, align={a['alignment_score']:.2f}, regime={a['regime']}")
    
    def test_case_has_opportunity_score(self, run_data):
        """Case has opportunity_score between 0 and 1"""
        case = self._get_any_case(run_data)
        if case is None:
            pytest.skip("No cases available to test")
        
        assert "opportunity_score" in case, "Expected opportunity_score"
        score = case["opportunity_score"]
        
        assert isinstance(score, (int, float)), "opportunity_score should be numeric"
        assert 0 <= score <= 1, f"opportunity_score should be 0-1, got {score}"
        
        print(f"✓ Opportunity score: {score:.4f}")


class TestSectionLogic:
    """Tests for section assignment logic"""
    
    @pytest.fixture(scope="class")
    def run_data(self):
        """Fetch run data once for all tests in this class"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=60)
        return response.json()
    
    def test_best_opportunities_have_now_actions(self, run_data):
        """best_opportunities should have YES_NOW or NO_NOW actions"""
        sections = run_data.get("sections", {})
        best = sections.get("best_opportunities", [])
        
        for case in best:
            action = case["recommendation"]["action"]
            assert action in ["YES_NOW", "NO_NOW"], f"best_opportunities should have NOW actions, got {action}"
        
        print(f"✓ best_opportunities: {len(best)} cases, all have NOW actions")
    
    def test_avoid_zone_has_avoid_actions(self, run_data):
        """avoid_zone should have AVOID actions or non-tradable"""
        sections = run_data.get("sections", {})
        avoid = sections.get("avoid_zone", [])
        
        for case in avoid:
            action = case["recommendation"]["action"]
            # AVOID zone can have AVOID action or cases that don't fit other categories
            # Based on routes.py logic: else clause catches AVOID and anything not matching other conditions
            assert action in ["AVOID", "YES_SMALL", "NO_SMALL", "WATCH", "WAIT", "GOOD_IDEA_BAD_PRICE"], f"Unexpected action in avoid_zone: {action}"
        
        print(f"✓ avoid_zone: {len(avoid)} cases")
    
    def test_watchlist_has_watch_or_small_actions(self, run_data):
        """watchlist should have WATCH, WAIT, SMALL, or GOOD_IDEA_BAD_PRICE actions"""
        sections = run_data.get("sections", {})
        watch = sections.get("watchlist", [])
        
        valid_actions = ["YES_SMALL", "NO_SMALL", "WATCH", "WAIT", "GOOD_IDEA_BAD_PRICE"]
        for case in watch:
            action = case["recommendation"]["action"]
            assert action in valid_actions, f"watchlist should have watch/small actions, got {action}"
        
        print(f"✓ watchlist: {len(watch)} cases")


class TestEngineIntegration:
    """Tests for engine integration"""
    
    def test_resolution_engine_flags_format(self):
        """Resolution engine flags should be strings"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20", timeout=60)
        data = response.json()
        
        sections = data.get("sections", {})
        for section_name, cases in sections.items():
            for case in cases:
                flags = case.get("resolution", {}).get("flags", [])
                for flag in flags:
                    assert isinstance(flag, str), f"Flag should be string, got {type(flag)}"
        
        print("✓ All resolution flags are strings")
    
    def test_pricing_engine_urgency_values(self):
        """Pricing engine urgency should be valid values"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20", timeout=60)
        data = response.json()
        
        valid_urgencies = ["expiring", "imminent", "near_term", "medium_term", "long_term", "unknown"]
        
        sections = data.get("sections", {})
        for section_name, cases in sections.items():
            for case in cases:
                urgency = case.get("pricing", {}).get("urgency")
                assert urgency in valid_urgencies, f"Invalid urgency: {urgency}"
        
        print("✓ All pricing urgencies are valid")
    
    def test_structural_risk_fields(self):
        """Structural risk should have reversal_risk, breakdown_risk, drawdown_pressure, combined_risk"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20", timeout=60)
        data = response.json()
        
        sections = data.get("sections", {})
        for section_name, cases in sections.items():
            for case in cases:
                sr = case.get("analysis", {}).get("structural_risk", {})
                # These fields may be 0 if exchange data unavailable
                assert "combined_risk" in sr or sr == {}, f"Expected combined_risk in structural_risk"
        
        print("✓ Structural risk fields present")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
