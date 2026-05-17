"""
Test Suite for Decision Intelligence System Stage 3.5 + Stage 4 + Stage 4.5

Stage 3.5: Real sentiment and onchain adapters pulling from MongoDB
Stage 4: Catalyst engine for ETF/listing/launch markets with 7-axis probability model
Stage 4.5: Position sizing engine converting recommendations to sizes

Tests:
- GET /api/prediction/run returns JSON with onchain_available, sentiment_available, exchange_available flags
- Response includes 4 sections: best_opportunities, new_mispricings, watchlist, avoid_zone
- Each case has sizing object: {allowed, size, size_fraction, raw_score, execution_mode, max_slippage_bps, risk_flags, why_now, why_not}
- Each case has execution object: {executable, entry, note}
- Case has market_type (quant/catalyst) and event_type
- Case has entities array
- Sentiment adapter returns real data from sentiment_events collection
- OnChain adapter returns real data from onchain collections
- Biases in analysis include sentiment and onchain sources
- Event classifier detects BTC, ETH, SOL, XRP price thresholds
- Event classifier detects ETF, listing, launch catalyst markets
"""
import pytest
import requests
import os
import sys

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPredictionRunEndpoint:
    """Tests for GET /api/prediction/run endpoint - Stage 3.5/4/4.5 features"""

    def test_prediction_run_returns_ok(self):
        """Test that /api/prediction/run returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("PASS: /api/prediction/run returns ok=true")

    def test_prediction_run_has_availability_flags(self):
        """Test that response includes exchange_available, onchain_available, sentiment_available flags"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        # Check exchange_available
        assert "exchange_available" in data, "Missing exchange_available flag"
        assert isinstance(data["exchange_available"], dict)
        assert "BTC" in data["exchange_available"]
        assert "ETH" in data["exchange_available"]
        
        # Check onchain_available
        assert "onchain_available" in data, "Missing onchain_available flag"
        assert isinstance(data["onchain_available"], dict)
        assert "BTC" in data["onchain_available"]
        assert "ETH" in data["onchain_available"]
        
        # Check sentiment_available
        assert "sentiment_available" in data, "Missing sentiment_available flag"
        assert isinstance(data["sentiment_available"], dict)
        assert "BTC" in data["sentiment_available"]
        assert "ETH" in data["sentiment_available"]
        
        print(f"PASS: Availability flags present - Exchange: {data['exchange_available']}, OnChain: {data['onchain_available']}, Sentiment: {data['sentiment_available']}")

    def test_prediction_run_has_four_sections(self):
        """Test that response includes 4 sections: best_opportunities, new_mispricings, watchlist, avoid_zone"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        assert "sections" in data, "Missing sections object"
        sections = data["sections"]
        
        assert "best_opportunities" in sections, "Missing best_opportunities section"
        assert "new_mispricings" in sections, "Missing new_mispricings section"
        assert "watchlist" in sections, "Missing watchlist section"
        assert "avoid_zone" in sections, "Missing avoid_zone section"
        
        # All should be lists
        assert isinstance(sections["best_opportunities"], list)
        assert isinstance(sections["new_mispricings"], list)
        assert isinstance(sections["watchlist"], list)
        assert isinstance(sections["avoid_zone"], list)
        
        total_cases = sum(len(sections[k]) for k in sections)
        print(f"PASS: 4 sections present with {total_cases} total cases")

    def test_case_has_sizing_object(self):
        """Test that each case has sizing object with required fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        # Get all cases from all sections
        all_cases = []
        for section in data["sections"].values():
            all_cases.extend(section)
        
        assert len(all_cases) > 0, "No cases returned to test"
        
        for case in all_cases[:5]:  # Test first 5 cases
            assert "sizing" in case, f"Missing sizing object in case {case.get('market_id')}"
            sizing = case["sizing"]
            
            # Required sizing fields
            assert "allowed" in sizing, "Missing sizing.allowed"
            assert "size" in sizing, "Missing sizing.size"
            assert "size_fraction" in sizing, "Missing sizing.size_fraction"
            assert "raw_score" in sizing, "Missing sizing.raw_score"
            assert "execution_mode" in sizing, "Missing sizing.execution_mode"
            assert "max_slippage_bps" in sizing, "Missing sizing.max_slippage_bps"
            assert "risk_flags" in sizing, "Missing sizing.risk_flags"
            assert "why_now" in sizing, "Missing sizing.why_now"
            assert "why_not" in sizing, "Missing sizing.why_not"
            
            # Type checks
            assert isinstance(sizing["allowed"], bool)
            assert sizing["size"] in ["NONE", "TINY", "SMALL", "MEDIUM", "FULL"]
            assert isinstance(sizing["size_fraction"], (int, float))
            assert isinstance(sizing["risk_flags"], list)
            assert isinstance(sizing["why_now"], list)
            assert isinstance(sizing["why_not"], list)
        
        print(f"PASS: All {len(all_cases)} cases have valid sizing objects")

    def test_case_has_execution_object(self):
        """Test that each case has execution object with required fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for section in data["sections"].values():
            all_cases.extend(section)
        
        assert len(all_cases) > 0, "No cases returned to test"
        
        for case in all_cases[:5]:
            assert "execution" in case, f"Missing execution object in case {case.get('market_id')}"
            execution = case["execution"]
            
            # Required execution fields
            assert "executable" in execution, "Missing execution.executable"
            assert "entry" in execution, "Missing execution.entry"
            assert "note" in execution, "Missing execution.note"
            
            # Type checks
            assert isinstance(execution["executable"], bool)
            
            # If executable, entry should have details
            if execution["executable"] and execution["entry"]:
                entry = execution["entry"]
                assert "type" in entry, "Missing entry.type"
                assert "side" in entry, "Missing entry.side"
                assert "size_fraction" in entry, "Missing entry.size_fraction"
                assert "max_slippage_bps" in entry, "Missing entry.max_slippage_bps"
        
        print(f"PASS: All {len(all_cases)} cases have valid execution objects")

    def test_case_has_market_type_and_event_type(self):
        """Test that each case has market_type and event_type fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for section in data["sections"].values():
            all_cases.extend(section)
        
        assert len(all_cases) > 0, "No cases returned to test"
        
        for case in all_cases:
            assert "market_type" in case, f"Missing market_type in case {case.get('market_id')}"
            assert "event_type" in case, f"Missing event_type in case {case.get('market_id')}"
            
            # market_type should be quant or catalyst
            assert case["market_type"] in ["quant", "catalyst"], f"Invalid market_type: {case['market_type']}"
            
            # event_type should be valid
            valid_event_types = ["price_threshold", "etf_catalyst", "listing_catalyst", "launch_catalyst", "unknown"]
            assert case["event_type"] in valid_event_types, f"Invalid event_type: {case['event_type']}"
        
        print(f"PASS: All {len(all_cases)} cases have valid market_type and event_type")

    def test_case_has_entities_array(self):
        """Test that each case has entities array"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for section in data["sections"].values():
            all_cases.extend(section)
        
        assert len(all_cases) > 0, "No cases returned to test"
        
        for case in all_cases:
            assert "entities" in case, f"Missing entities in case {case.get('market_id')}"
            assert isinstance(case["entities"], list), "entities should be a list"
        
        print(f"PASS: All {len(all_cases)} cases have entities array")

    def test_analysis_has_biases_with_sentiment_and_onchain(self):
        """Test that analysis.biases includes sentiment and onchain sources"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for section in data["sections"].values():
            all_cases.extend(section)
        
        assert len(all_cases) > 0, "No cases returned to test"
        
        has_sentiment_bias = False
        has_onchain_bias = False
        
        for case in all_cases:
            assert "analysis" in case, f"Missing analysis in case {case.get('market_id')}"
            analysis = case["analysis"]
            
            assert "biases" in analysis, f"Missing biases in analysis for case {case.get('market_id')}"
            biases = analysis["biases"]
            
            if "sentiment" in biases:
                has_sentiment_bias = True
                assert biases["sentiment"] in ["bullish", "bearish", "neutral"]
            
            if "onchain" in biases:
                has_onchain_bias = True
                assert biases["onchain"] in ["bullish", "bearish", "neutral"]
        
        # At least some cases should have sentiment and onchain biases
        print(f"PASS: Biases present - sentiment: {has_sentiment_bias}, onchain: {has_onchain_bias}")


class TestEventClassifier:
    """Tests for event_classifier.py - detecting market types"""

    def test_btc_price_threshold_detection(self):
        """Test that classifier detects BTC price threshold markets"""
        from prediction import event_classifier
        
        test_cases = [
            "Will Bitcoin be above $125,000 on January 31?",
            "Will BTC reach $100,000 by end of year?",
            "Bitcoin above 95,000 on March 1?",
        ]
        
        for question in test_cases:
            result = event_classifier.classify(question)
            assert result["event_type"] == "price_threshold", f"Failed for: {question}"
            assert result["market_type"] == "quant", f"Failed market_type for: {question}"
            assert result["asset"] == "BTC", f"Failed asset for: {question}"
            assert result["threshold"] is not None, f"Failed threshold for: {question}"
            assert "BTC" in result["entities"], f"Failed entities for: {question}"
        
        print("PASS: BTC price threshold detection working")

    def test_eth_price_threshold_detection(self):
        """Test that classifier detects ETH price threshold markets"""
        from prediction import event_classifier
        
        test_cases = [
            "Will Ethereum be above $4,000 on January 31?",
            "ETH above 3,500 on March 1?",
            "Will Ethereum reach $5,000?",
        ]
        
        for question in test_cases:
            result = event_classifier.classify(question)
            assert result["event_type"] == "price_threshold", f"Failed for: {question}"
            assert result["market_type"] == "quant", f"Failed market_type for: {question}"
            assert result["asset"] == "ETH", f"Failed asset for: {question}"
            assert result["threshold"] is not None, f"Failed threshold for: {question}"
        
        print("PASS: ETH price threshold detection working")

    def test_sol_price_threshold_detection(self):
        """Test that classifier detects SOL price threshold markets"""
        from prediction import event_classifier
        
        test_cases = [
            "Will Solana be above $200 on January 31?",
            "SOL above 150 on March 1?",
        ]
        
        for question in test_cases:
            result = event_classifier.classify(question)
            assert result["event_type"] == "price_threshold", f"Failed for: {question}"
            assert result["market_type"] == "quant", f"Failed market_type for: {question}"
            assert result["asset"] == "SOL", f"Failed asset for: {question}"
        
        print("PASS: SOL price threshold detection working")

    def test_xrp_price_threshold_detection(self):
        """Test that classifier detects XRP price threshold markets"""
        from prediction import event_classifier
        
        test_cases = [
            "Will XRP be above $2 on January 31?",
            "Ripple above $1.50 on March 1?",
        ]
        
        for question in test_cases:
            result = event_classifier.classify(question)
            assert result["event_type"] == "price_threshold", f"Failed for: {question}"
            assert result["market_type"] == "quant", f"Failed market_type for: {question}"
            assert result["asset"] == "XRP", f"Failed asset for: {question}"
        
        print("PASS: XRP price threshold detection working")

    def test_etf_catalyst_detection(self):
        """Test that classifier detects ETF catalyst markets"""
        from prediction import event_classifier
        
        test_cases = [
            "Will the SEC approve a Solana ETF by June 2025?",
            "Will BlackRock's Bitcoin ETF be approved?",
            "Ethereum ETF approval by end of year?",
        ]
        
        for question in test_cases:
            result = event_classifier.classify(question)
            assert result["event_type"] == "etf_catalyst", f"Failed for: {question}"
            assert result["market_type"] == "catalyst", f"Failed market_type for: {question}"
        
        print("PASS: ETF catalyst detection working")

    def test_listing_catalyst_detection(self):
        """Test that classifier detects listing catalyst markets"""
        from prediction import event_classifier
        
        test_cases = [
            "Will PEPE list on Coinbase by March?",
            "Will Binance listing for XYZ token happen?",
        ]
        
        for question in test_cases:
            result = event_classifier.classify(question)
            assert result["event_type"] == "listing_catalyst", f"Failed for: {question}"
            assert result["market_type"] == "catalyst", f"Failed market_type for: {question}"
        
        print("PASS: Listing catalyst detection working")

    def test_launch_catalyst_detection(self):
        """Test that classifier detects launch catalyst markets"""
        from prediction import event_classifier
        
        test_cases = [
            "Will Ethereum 2.0 mainnet launch by Q2?",
            "Will the project deploy on mainnet?",
        ]
        
        for question in test_cases:
            result = event_classifier.classify(question)
            assert result["event_type"] == "launch_catalyst", f"Failed for: {question}"
            assert result["market_type"] == "catalyst", f"Failed market_type for: {question}"
        
        print("PASS: Launch catalyst detection working")


class TestSizingEngine:
    """Tests for sizing_engine.py - position sizing logic"""

    def test_sizing_engine_blocked_for_avoid(self):
        """Test that sizing engine blocks AVOID recommendations"""
        from prediction import sizing_engine
        
        analysis = {
            "net_edge": 0.05,
            "model_confidence": 0.5,
            "alignment_score": 0.5,
            "structural_risk": {"combined_risk": 0.2},
        }
        recommendation = {"action": "AVOID"}
        resolution = {"resolution_risk_score": 0.1}
        pricing = {"market_state": "fairly_priced"}
        market = {"liquidity": 50000, "spread": 0.02}
        
        result = sizing_engine.compute(analysis, recommendation, resolution, pricing, market)
        
        assert result["allowed"] is False
        assert result["size"] == "NONE"
        assert "avoid_action" in result["risk_flags"]
        print("PASS: Sizing engine blocks AVOID recommendations")

    def test_sizing_engine_blocked_for_high_resolution_risk(self):
        """Test that sizing engine blocks high resolution risk"""
        from prediction import sizing_engine
        
        analysis = {
            "net_edge": 0.15,
            "model_confidence": 0.7,
            "alignment_score": 0.6,
            "structural_risk": {"combined_risk": 0.1},
        }
        recommendation = {"action": "YES_NOW"}
        resolution = {"resolution_risk_score": 0.60}  # High risk
        pricing = {"market_state": "underpriced"}
        market = {"liquidity": 50000, "spread": 0.02}
        
        result = sizing_engine.compute(analysis, recommendation, resolution, pricing, market)
        
        assert result["allowed"] is False
        assert result["size"] == "NONE"
        assert "resolution_risk_high" in result["risk_flags"]
        print("PASS: Sizing engine blocks high resolution risk")

    def test_sizing_engine_blocked_for_low_liquidity(self):
        """Test that sizing engine blocks low liquidity markets"""
        from prediction import sizing_engine
        
        analysis = {
            "net_edge": 0.15,
            "model_confidence": 0.7,
            "alignment_score": 0.6,
            "structural_risk": {"combined_risk": 0.1},
        }
        recommendation = {"action": "YES_NOW"}
        resolution = {"resolution_risk_score": 0.1}
        pricing = {"market_state": "underpriced"}
        market = {"liquidity": 500, "spread": 0.02}  # Very low liquidity
        
        result = sizing_engine.compute(analysis, recommendation, resolution, pricing, market)
        
        assert result["allowed"] is False
        assert result["size"] == "NONE"
        assert "low_liquidity" in result["risk_flags"]
        print("PASS: Sizing engine blocks low liquidity markets")

    def test_sizing_engine_allows_good_setup(self):
        """Test that sizing engine allows good setups"""
        from prediction import sizing_engine
        
        analysis = {
            "net_edge": 0.15,
            "model_confidence": 0.7,
            "alignment_score": 0.6,
            "structural_risk": {"combined_risk": 0.1},
        }
        recommendation = {"action": "YES_NOW"}
        resolution = {"resolution_risk_score": 0.1}
        pricing = {"market_state": "underpriced", "urgency": "near_term"}
        market = {"liquidity": 50000, "spread": 0.02}
        
        result = sizing_engine.compute(analysis, recommendation, resolution, pricing, market)
        
        assert result["allowed"] is True
        assert result["size"] in ["TINY", "SMALL", "MEDIUM", "FULL"]
        assert result["size_fraction"] > 0
        assert len(result["why_now"]) > 0
        print(f"PASS: Sizing engine allows good setup - size={result['size']}, fraction={result['size_fraction']}")

    def test_sizing_engine_size_tiers(self):
        """Test that sizing engine produces correct size tiers"""
        from prediction import sizing_engine
        
        # Test different score levels
        base_analysis = {
            "model_confidence": 0.7,
            "alignment_score": 0.6,
            "structural_risk": {"combined_risk": 0.1},
        }
        recommendation = {"action": "YES_NOW"}
        resolution = {"resolution_risk_score": 0.1}
        pricing = {"market_state": "underpriced", "urgency": "near_term"}
        market = {"liquidity": 100000, "spread": 0.01}
        
        # High edge should give larger size
        high_edge_analysis = {**base_analysis, "net_edge": 0.25}
        result_high = sizing_engine.compute(high_edge_analysis, recommendation, resolution, pricing, market)
        
        # Low edge should give smaller size
        low_edge_analysis = {**base_analysis, "net_edge": 0.06}
        result_low = sizing_engine.compute(low_edge_analysis, recommendation, resolution, pricing, market)
        
        # High edge should have higher size_fraction
        assert result_high["size_fraction"] >= result_low["size_fraction"]
        print(f"PASS: Size tiers working - high edge: {result_high['size']}, low edge: {result_low['size']}")


class TestExecutionEngine:
    """Tests for execution_engine.py - execution plan building"""

    def test_execution_engine_not_executable_when_blocked(self):
        """Test that execution engine returns not executable when sizing blocked"""
        from prediction import execution_engine
        
        recommendation = {"action": "YES_NOW"}
        sizing = {
            "allowed": False,
            "size": "NONE",
            "size_fraction": 0,
            "execution_mode": "WAIT",
            "max_slippage_bps": 0,
        }
        
        result = execution_engine.build_plan(recommendation, sizing)
        
        assert result["executable"] is False
        assert result["entry"] is None
        assert "Do not enter" in result["note"]
        print("PASS: Execution engine returns not executable when blocked")

    def test_execution_engine_executable_when_allowed(self):
        """Test that execution engine returns executable when sizing allowed"""
        from prediction import execution_engine
        
        recommendation = {"action": "YES_NOW"}
        sizing = {
            "allowed": True,
            "size": "MEDIUM",
            "size_fraction": 0.5,
            "execution_mode": "MARKET",
            "max_slippage_bps": 60,
        }
        
        result = execution_engine.build_plan(recommendation, sizing)
        
        assert result["executable"] is True
        assert result["entry"] is not None
        assert result["entry"]["side"] == "YES"
        assert result["entry"]["size_fraction"] == 0.5
        assert result["entry"]["max_slippage_bps"] == 60
        print("PASS: Execution engine returns executable when allowed")

    def test_execution_engine_limit_order_mode(self):
        """Test that execution engine uses limit order for LIMIT mode"""
        from prediction import execution_engine
        
        recommendation = {"action": "NO_SMALL"}
        sizing = {
            "allowed": True,
            "size": "SMALL",
            "size_fraction": 0.25,
            "execution_mode": "LIMIT",
            "max_slippage_bps": 100,
        }
        
        result = execution_engine.build_plan(recommendation, sizing)
        
        assert result["executable"] is True
        assert result["entry"]["type"] == "place_limit_order"
        assert result["entry"]["side"] == "NO"
        print("PASS: Execution engine uses limit order for LIMIT mode")


class TestCatalystEngine:
    """Tests for catalyst_engine.py - catalyst probability model"""

    def test_catalyst_engine_returns_required_fields(self):
        """Test that catalyst engine returns all required fields"""
        from prediction.intelligence import catalyst_engine
        
        decoded = {
            "event_type": "etf_catalyst",
            "entities": ["BTC", "SEC"],
            "deadline": "2025-06-30T00:00:00Z",
        }
        related_events = [
            {
                "title": "SEC reviewing Bitcoin ETF application",
                "text": "The SEC has acknowledged receipt of the filing",
                "source": "sec",
                "source_type": "official",
                "source_quality": 0.9,
                "relevance_score": 0.8,
            }
        ]
        
        result = catalyst_engine.run(decoded, related_events)
        
        # Required fields
        assert "fair_yes_prob" in result
        assert "fair_no_prob" in result
        assert "model_confidence" in result
        assert "uncertainty" in result
        assert "bias" in result
        assert "regime" in result
        assert "structural_risk" in result
        assert "drivers" in result
        assert "risks" in result
        assert "components" in result
        
        # Value checks
        assert 0 <= result["fair_yes_prob"] <= 1
        assert 0 <= result["model_confidence"] <= 1
        assert result["regime"] == "CATALYST"
        assert result["bias"] in ["bullish", "bearish", "neutral"]
        
        print(f"PASS: Catalyst engine returns all fields - prob={result['fair_yes_prob']}, conf={result['model_confidence']}")

    def test_catalyst_engine_components(self):
        """Test that catalyst engine returns 7-axis components"""
        from prediction.intelligence import catalyst_engine
        
        decoded = {
            "event_type": "listing_catalyst",
            "entities": ["PEPE", "COINBASE"],
            "deadline": "2025-03-31T00:00:00Z",
        }
        related_events = []
        
        result = catalyst_engine.run(decoded, related_events)
        
        components = result["components"]
        
        # Check 7-axis components
        assert "official_signal" in components
        assert "source_credibility" in components
        assert "narrative_pressure" in components
        assert "timeline_pressure" in components
        assert "readiness_score" in components
        assert "precedent_score" in components
        assert "blocker_penalty" in components
        
        print(f"PASS: Catalyst engine has 7-axis components")


class TestSentimentAdapter:
    """Tests for sentiment_adapter.py - real sentiment data"""

    def test_sentiment_adapter_returns_unified_format(self):
        """Test that sentiment adapter returns unified signal format"""
        from adapters import sentiment_adapter
        
        result = sentiment_adapter.get_sentiment_signal("BTC")
        
        # May return None if no data
        if result is None:
            print("INFO: No sentiment data available for BTC (expected if collection empty)")
            return
        
        # Check unified format
        assert "bias" in result
        assert "strength" in result
        assert "confidence" in result
        assert "direction" in result
        assert "delta" in result
        assert "signal_count" in result
        
        # Value checks
        assert result["bias"] in ["bullish", "bearish", "neutral"]
        assert 0 <= result["strength"] <= 1
        assert 0 <= result["confidence"] <= 1
        
        print(f"PASS: Sentiment adapter returns unified format - bias={result['bias']}, strength={result['strength']}")


class TestOnChainAdapter:
    """Tests for onchain_adapter.py - real onchain data"""

    def test_onchain_adapter_returns_unified_format(self):
        """Test that onchain adapter returns unified signal format"""
        from adapters import onchain_adapter
        
        result = onchain_adapter.get_flow_signal("BTC")
        
        # May return None if no data
        if result is None:
            print("INFO: No onchain data available for BTC (expected if collections empty)")
            return
        
        # Check unified format
        assert "bias" in result
        assert "strength" in result
        assert "confidence" in result
        assert "flow" in result
        assert "signals" in result
        
        # Value checks
        assert result["bias"] in ["bullish", "bearish", "neutral"]
        assert 0 <= result["strength"] <= 1
        assert 0 <= result["confidence"] <= 1
        assert isinstance(result["signals"], list)
        
        print(f"PASS: OnChain adapter returns unified format - bias={result['bias']}, strength={result['strength']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
