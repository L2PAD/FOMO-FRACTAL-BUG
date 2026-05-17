"""
Token Intelligence Tab P0 Tests
===============================
Tests for:
- Token Intelligence tab APIs (brain, map, feed, patterns, narrative, top-actors)
- Token Profile page API (/token/{symbol}/context)
- P0 Features: % share in Flow Map, lead time in Signals
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestTokenIntelligenceAPIs:
    """Test all APIs used by Token Intelligence tab (12 blocks)"""
    
    def test_brain_signals_api(self):
        """GET /api/onchain/smart-money/brain - Alpha scores per token"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=7d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "signals" in data
        assert len(data["signals"]) > 0
        
        # Validate token score structure
        for score in data["signals"][:3]:
            assert "token" in score
            assert "alpha_score" in score
            assert "signal" in score
            assert "net_flow_usd" in score
            assert "wallet_count" in score
            assert "avg_timing" in score  # P0: Lead time data
            assert "drivers" in score
            print(f"Token {score['token']}: alpha={score['alpha_score']}, timing={score['avg_timing']}h")
    
    def test_feed_signals_api(self):
        """GET /api/onchain/smart-money/feed - Smart Money Signals"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/feed?chainId=1&window=7d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "signals" in data
        
        # Signals should have conviction and wallet data
        for sig in data["signals"][:3]:
            assert "signal_id" in sig
            assert "token" in sig
            assert "signal_type" in sig
            assert "conviction" in sig
            assert "wallet_count" in sig
            assert "capital_fmt" in sig
            print(f"Signal {sig['signal_id']}: {sig['token']} - {sig['signal_type']} - {sig['conviction']}%")
    
    def test_map_api_with_share_pct(self):
        """GET /api/onchain/smart-money/map - Token Flow Map with destination heat"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=7d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "destination_heat" in data  # P0: Used for % share calculation
        
        # Verify destination_heat has net_flow_usd for % share calculation
        dest_heat = data["destination_heat"]
        assert len(dest_heat) > 0
        
        total_abs_flow = sum(abs(h["net_flow_usd"]) for h in dest_heat)
        for h in dest_heat[:5]:
            assert "token" in h
            assert "net_flow_usd" in h
            share_pct = (abs(h["net_flow_usd"]) / total_abs_flow * 100) if total_abs_flow > 0 else 0
            print(f"Token {h['token']}: flow=${h['net_flow_usd']:,.0f}, share={share_pct:.1f}%")
    
    def test_patterns_api(self):
        """GET /api/onchain/smart-money/patterns - Capital Rotation patterns"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/patterns?chainId=1&window=7d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "patterns" in data
        
        for pat in data["patterns"][:3]:
            assert "pattern_type" in pat
            assert "confidence" in pat
            assert "wallet_count" in pat
            print(f"Pattern: {pat['pattern_type']} - confidence={pat['confidence']}%")
    
    def test_narrative_api(self):
        """GET /api/onchain/smart-money/narrative - Token Narrative"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/narrative?chainId=1&window=7d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "narrative_type" in data
        assert "summary" in data
        print(f"Narrative: {data['narrative_type']} - {data['summary'][:80]}...")
    
    def test_top_actors_api(self):
        """GET /api/onchain/smart-money/top-actors - Wallet Activity"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/top-actors?chainId=1&window=7d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "actors" in data
        
        for actor in data["actors"][:3]:
            assert "wallet" in actor
            assert "name" in actor
            assert "smart_score" in actor
            assert "tokens" in actor
            print(f"Actor: {actor['name']} - score={actor['smart_score']}, tokens={actor['tokens']}")


class TestTokenProfileAPI:
    """Test Token Profile page API"""
    
    def test_token_context_weth(self):
        """GET /api/onchain/smart-money/token/WETH/context - Full token profile"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/WETH/context?chainId=1&window=7d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("symbol") == "WETH"
        
        # P0: Score with components
        score = data.get("score")
        assert score is not None
        assert "alpha_score" in score
        assert "signal" in score
        assert "components" in score
        assert "avg_timing" in score  # P0: Lead time
        
        components = score["components"]
        assert "wallet" in components
        assert "timing" in components
        assert "flow" in components
        assert "cluster" in components
        assert "pattern" in components
        
        print(f"WETH Score: {score['alpha_score']}, Signal: {score['signal']}")
        print(f"Components: {components}")
    
    def test_token_context_rank_and_total(self):
        """Token context should include rank and total tokens"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/WETH/context?chainId=1&window=7d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("rank") is not None
        assert data.get("total_tokens") > 0
        print(f"WETH Rank: {data['rank']} of {data['total_tokens']}")
    
    def test_token_context_patterns(self):
        """Token context should include relevant patterns"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/WETH/context?chainId=1&window=7d")
        data = response.json()
        
        patterns = data.get("patterns", [])
        # Patterns may be empty but should be a list
        assert isinstance(patterns, list)
        print(f"WETH has {len(patterns)} patterns")
        
        for p in patterns[:2]:
            assert "pattern_type" in p
            assert "confidence" in p
    
    def test_token_context_signals(self):
        """Token context should include active signals"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/WETH/context?chainId=1&window=7d")
        data = response.json()
        
        signals = data.get("signals", [])
        assert isinstance(signals, list)
        print(f"WETH has {len(signals)} signals")
        
        for s in signals[:2]:
            assert "signal_id" in s
            assert "signal_type" in s
            assert "conviction" in s
    
    def test_token_context_routes(self):
        """Token context should include capital routes"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/WETH/context?chainId=1&window=7d")
        data = response.json()
        
        routes = data.get("routes", [])
        assert isinstance(routes, list)
        print(f"WETH has {len(routes)} routes")
        
        for r in routes[:2]:
            assert "route_type" in r
            assert "volume_usd" in r
            assert "impact_score" in r
    
    def test_token_context_flow_with_share_pct(self):
        """P0: Token flow should include share_pct"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/WETH/context?chainId=1&window=7d")
        data = response.json()
        
        flow = data.get("flow", {})
        assert "net_flow_usd" in flow
        assert "share_pct" in flow  # P0: % share
        print(f"WETH Flow: ${flow['net_flow_usd']:,.0f}, Share: {flow['share_pct']}%")
    
    def test_token_context_actors(self):
        """Token context should include wallet exposure"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/WETH/context?chainId=1&window=7d")
        data = response.json()
        
        actors = data.get("actors", [])
        assert isinstance(actors, list)
        print(f"WETH has {len(actors)} actors with exposure")
    
    def test_token_context_related_tokens(self):
        """Token context should include related tokens for navigation"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/WETH/context?chainId=1&window=7d")
        data = response.json()
        
        related = data.get("related_tokens", [])
        assert isinstance(related, list)
        print(f"WETH has {len(related)} related tokens")
        
        for rt in related[:3]:
            assert "token" in rt
            assert "alpha_score" in rt
    
    def test_token_context_link(self):
        """Test token context for LINK"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/LINK/context?chainId=1&window=7d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("symbol") == "LINK"
        print(f"LINK Score: {data.get('score', {}).get('alpha_score')}")
    
    def test_token_context_window_selector(self):
        """Token context should work with different windows (24H/7D/30D)"""
        for window in ["24h", "7d", "30d"]:
            response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/WETH/context?chainId=1&window={window}")
            assert response.status_code == 200
            data = response.json()
            assert data.get("ok") is True
            print(f"Window {window}: ok")


class TestP0Features:
    """Test P0 priority features: % share in Flow Map, Lead time in Signals"""
    
    def test_flow_map_has_data_for_share_calculation(self):
        """Token Flow Map needs net_flow_usd for % share calculation"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/map?chainId=1&window=7d")
        data = response.json()
        
        dest_heat = data.get("destination_heat", [])
        assert len(dest_heat) > 0
        
        # Calculate % shares
        total_abs_flow = sum(abs(h["net_flow_usd"]) for h in dest_heat)
        assert total_abs_flow > 0, "Total flow should be positive for % calculation"
        
        for h in dest_heat:
            share = (abs(h["net_flow_usd"]) / total_abs_flow) * 100
            print(f"{h['token']}: {share:.1f}% share")
    
    def test_signals_have_lead_time_from_brain(self):
        """Smart Money Signals need avg_timing (lead time) from brain scores"""
        brain_response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=7d")
        brain_data = brain_response.json()
        
        # Brain signals should have avg_timing for lead time display
        for score in brain_data.get("signals", []):
            assert "avg_timing" in score, f"Token {score['token']} missing avg_timing"
            print(f"{score['token']}: +{score['avg_timing']}h lead time")
    
    def test_token_profile_has_lead_time(self):
        """Token Profile should show lead time in Capital Flow section"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/WETH/context?chainId=1&window=7d")
        data = response.json()
        
        score = data.get("score", {})
        assert "avg_timing" in score, "Score should have avg_timing for lead time"
        print(f"WETH Lead Time: +{score['avg_timing']}h")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
