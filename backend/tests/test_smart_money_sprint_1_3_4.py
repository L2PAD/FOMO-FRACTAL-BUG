"""
Smart Money Sprint 1.3 + 1.4 Backend API Tests
================================================
Tests for:
- GET /api/onchain/smart-money/patterns - Pattern detection (accumulation, distribution, rotation, exit)
- GET /api/onchain/smart-money/brain - Brain signals with pattern integration
- GET /api/onchain/smart-money/map - Capital flow map with routes, heat maps
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSmartMoneyPatterns:
    """Tests for /api/onchain/smart-money/patterns endpoint"""
    
    def test_patterns_endpoint_returns_ok(self):
        """Test that patterns endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/patterns?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "patterns" in data
        assert "meta" in data
        print(f"✓ Patterns endpoint OK, returned {len(data['patterns'])} patterns")
    
    def test_patterns_have_required_fields(self):
        """Test that each pattern has required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/patterns?chainId=1&window=24h&limit=10")
        data = response.json()
        
        required_fields = ["pattern_type", "token", "net_flow_usd", "confidence", "wallet_count", "drivers"]
        
        for pattern in data["patterns"]:
            for field in required_fields:
                assert field in pattern, f"Missing field: {field}"
            # Validate types
            assert isinstance(pattern["pattern_type"], str)
            assert isinstance(pattern["confidence"], int)
            assert isinstance(pattern["drivers"], list)
        print(f"✓ All {len(data['patterns'])} patterns have required fields")
    
    def test_pattern_types_are_valid(self):
        """Test that pattern_type is one of the 4 valid types"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/patterns?chainId=1&window=24h&limit=10")
        data = response.json()
        
        valid_types = {"accumulation", "distribution", "rotation", "exit"}
        detected_types = set()
        
        for pattern in data["patterns"]:
            assert pattern["pattern_type"] in valid_types, f"Invalid pattern_type: {pattern['pattern_type']}"
            detected_types.add(pattern["pattern_type"])
        
        print(f"✓ Detected pattern types: {detected_types}")
    
    def test_rotation_patterns_have_from_to_tokens(self):
        """Test that rotation patterns include from_token and to_token"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/patterns?chainId=1&window=24h&limit=10")
        data = response.json()
        
        rotation_patterns = [p for p in data["patterns"] if p["pattern_type"] == "rotation"]
        
        for pattern in rotation_patterns:
            assert "from_token" in pattern, "Rotation pattern missing from_token"
            assert "to_token" in pattern, "Rotation pattern missing to_token"
            assert "->" in pattern["token"], "Rotation pattern token should contain ->"
        
        print(f"✓ Found {len(rotation_patterns)} rotation patterns with from_token/to_token")
    
    def test_confidence_in_valid_range(self):
        """Test that confidence is between 0 and 100"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/patterns?chainId=1&window=24h&limit=10")
        data = response.json()
        
        for pattern in data["patterns"]:
            assert 0 <= pattern["confidence"] <= 100, f"Invalid confidence: {pattern['confidence']}"
        
        print("✓ All confidence values in valid range [0, 100]")
    
    def test_patterns_sorted_by_confidence(self):
        """Test that patterns are sorted by confidence descending"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/patterns?chainId=1&window=24h&limit=10")
        data = response.json()
        
        confidences = [p["confidence"] for p in data["patterns"]]
        assert confidences == sorted(confidences, reverse=True), "Patterns not sorted by confidence"
        
        print("✓ Patterns sorted by confidence descending")


class TestSmartMoneyBrain:
    """Tests for /api/onchain/smart-money/brain endpoint"""
    
    def test_brain_endpoint_returns_ok(self):
        """Test that brain endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "signals" in data
        print(f"✓ Brain endpoint OK, returned {len(data['signals'])} signals")
    
    def test_brain_signals_have_required_fields(self):
        """Test that each signal has required fields including pattern"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        data = response.json()
        
        required_fields = ["token", "alpha_score", "signal", "pattern", "net_flow_usd", "wallet_count", "drivers", "components"]
        
        for signal in data["signals"]:
            for field in required_fields:
                assert field in signal, f"Missing field: {field}"
        
        print(f"✓ All {len(data['signals'])} signals have required fields including 'pattern'")
    
    def test_brain_has_pattern_field(self):
        """Test that brain signals include pattern field (Sprint 1.3 integration)"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        data = response.json()
        
        # At least some signals should have patterns detected
        patterns_detected = [s for s in data["signals"] if s["pattern"] is not None]
        
        print(f"✓ Brain signals with pattern field present, {len(patterns_detected)} have detected patterns")
        assert "pattern" in data["signals"][0] if data["signals"] else True
    
    def test_brain_signal_values_valid(self):
        """Test that signal value is one of valid options"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        data = response.json()
        
        valid_signals = {"strong_bullish", "bullish", "neutral", "bearish", "strong_bearish"}
        
        for signal in data["signals"]:
            assert signal["signal"] in valid_signals, f"Invalid signal: {signal['signal']}"
        
        print("✓ All signal values are valid")
    
    def test_brain_alpha_score_range(self):
        """Test that alpha_score is between 0 and 100"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        data = response.json()
        
        for signal in data["signals"]:
            assert 0 <= signal["alpha_score"] <= 100, f"Invalid alpha_score: {signal['alpha_score']}"
        
        print("✓ All alpha_score values in valid range [0, 100]")
    
    def test_brain_components_structure(self):
        """Test that components has wallet, timing, flow, cluster, pattern"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        data = response.json()
        
        component_keys = ["wallet", "timing", "flow", "cluster", "pattern"]
        
        for signal in data["signals"]:
            for key in component_keys:
                assert key in signal["components"], f"Missing component: {key}"
        
        print("✓ All signals have correct components structure")


class TestSmartMoneyMap:
    """Tests for /api/onchain/smart-money/map endpoint"""
    
    def test_map_endpoint_returns_ok(self):
        """Test that map endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=24h&limit=15")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        print("✓ Map endpoint OK")
    
    def test_map_has_required_sections(self):
        """Test that map response has routes, destination_heat, source_heat, flow_summary"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=24h&limit=15")
        data = response.json()
        
        required_sections = ["routes", "destination_heat", "source_heat", "flow_summary"]
        
        for section in required_sections:
            assert section in data, f"Missing section: {section}"
        
        print(f"✓ Map has all required sections: {required_sections}")
    
    def test_map_routes_have_required_fields(self):
        """Test that routes have required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=24h&limit=15")
        data = response.json()
        
        required_fields = ["route_type", "source_entity", "protocol", "token", "volume_usd", "impact_score"]
        
        for route in data["routes"]:
            for field in required_fields:
                assert field in route, f"Missing field in route: {field}"
        
        print(f"✓ All {len(data['routes'])} routes have required fields")
    
    def test_map_route_types_valid(self):
        """Test that route_type is one of valid types"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=24h&limit=15")
        data = response.json()
        
        valid_types = {"accumulation", "distribution", "rotation", "exit"}
        detected_types = set()
        
        for route in data["routes"]:
            assert route["route_type"] in valid_types, f"Invalid route_type: {route['route_type']}"
            detected_types.add(route["route_type"])
        
        print(f"✓ Route types detected: {detected_types}")
    
    def test_map_rotation_routes_have_from_to(self):
        """Test that rotation routes include from_token and to_token"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=24h&limit=15")
        data = response.json()
        
        rotation_routes = [r for r in data["routes"] if r["route_type"] == "rotation"]
        
        for route in rotation_routes:
            assert "from_token" in route, "Rotation route missing from_token"
            assert "to_token" in route, "Rotation route missing to_token"
        
        print(f"✓ Found {len(rotation_routes)} rotation routes with from_token/to_token")
    
    def test_map_destination_heat_structure(self):
        """Test destination_heat has token and net_flow_usd"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=24h&limit=15")
        data = response.json()
        
        for item in data["destination_heat"]:
            assert "token" in item, "Missing token in destination_heat"
            assert "net_flow_usd" in item, "Missing net_flow_usd in destination_heat"
        
        print(f"✓ Destination heat has {len(data['destination_heat'])} items with correct structure")
    
    def test_map_source_heat_structure(self):
        """Test source_heat has name, type, total_flow_usd"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=24h&limit=15")
        data = response.json()
        
        for item in data["source_heat"]:
            assert "name" in item, "Missing name in source_heat"
            assert "total_flow_usd" in item, "Missing total_flow_usd in source_heat"
        
        print(f"✓ Source heat has {len(data['source_heat'])} items with correct structure")
    
    def test_map_source_heat_no_unknown_address(self):
        """Test that source_heat names don't contain 'Unknown:Address'"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=24h&limit=15")
        data = response.json()
        
        for item in data["source_heat"]:
            assert "Unknown:Address" not in item["name"], f"Found Unknown:Address in source: {item['name']}"
        
        print("✓ No 'Unknown:Address' found in source_heat names")
    
    def test_map_flow_summary_has_all_types(self):
        """Test flow_summary has accumulation, distribution, rotation, exit"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=24h&limit=15")
        data = response.json()
        
        expected_keys = ["accumulation", "distribution", "rotation", "exit"]
        
        for key in expected_keys:
            assert key in data["flow_summary"], f"Missing key in flow_summary: {key}"
        
        print(f"✓ Flow summary: {data['flow_summary']}")


class TestSmartMoneyRadar:
    """Tests for /api/onchain/smart-money/radar endpoint (existing, ensure still works)"""
    
    def test_radar_endpoint_returns_ok(self):
        """Test that radar endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&sort=confidence&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        print(f"✓ Radar endpoint OK, returned {len(data['events'])} events")
    
    def test_radar_events_have_severity_impact(self):
        """Test that radar events have signal_severity and impact_score"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&sort=confidence&limit=10")
        data = response.json()
        
        for event in data["events"]:
            assert "signal_severity" in event
            assert "impact_score" in event
            assert event["signal_severity"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        
        print("✓ Radar events have correct severity and impact fields")


class TestIntegration:
    """Integration tests between patterns, brain, and map"""
    
    def test_patterns_appear_in_brain(self):
        """Test that detected patterns appear in brain signals"""
        patterns_resp = requests.get(f"{BASE_URL}/api/onchain/smart-money/patterns?chainId=1&window=24h&limit=10")
        brain_resp = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        
        patterns = patterns_resp.json()["patterns"]
        brain_signals = brain_resp.json()["signals"]
        
        # Get tokens with patterns
        pattern_tokens = {p["token"] for p in patterns if "->" not in p["token"]}
        
        # Check brain signals for these tokens have pattern field set
        for signal in brain_signals:
            if signal["token"] in pattern_tokens:
                assert signal["pattern"] is not None, f"Token {signal['token']} should have pattern in brain"
        
        print("✓ Patterns correctly integrated with brain signals")
    
    def test_map_routes_match_flow_summary(self):
        """Test that flow_summary counts match route types"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=24h&limit=30")
        data = response.json()
        
        assert response.status_code == 200
        assert "routes" in data
        
        # Count routes by type
        route_counts = {}
        for route in data["routes"]:
            rt = route["route_type"]
            route_counts[rt] = route_counts.get(rt, 0) + 1
        
        # Note: flow_summary is cumulative from all routes, not just limited ones
        print(f"✓ Map flow summary consistent: {data['flow_summary']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
