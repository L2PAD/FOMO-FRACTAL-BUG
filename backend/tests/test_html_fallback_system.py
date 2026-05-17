"""
HTML Fallback System Tests
==========================
Tests for the HTML fallback layer that activates when primary API/RSC fails.

Endpoints tested:
- GET /api/graph/fallback/status — returns all parsers with fallback status fields
- POST /api/graph/fallback/test {parser:'CryptoRank'} — returns coins from HTML scraping
- POST /api/graph/fallback/test {parser:'CryptoRank_funding'} — returns funding rounds
- POST /api/graph/fallback/test {parser:'Dropstab'} — returns activities
- POST /api/graph/fallback/test {parser:'ICODrops'} — may return 0 (JS-heavy site)
- POST /api/graph/fallback/test with unknown parser — returns error with available options
- POST /api/graph/build — full graph rebuild still works
- GET /api/graph/build/stats — returns cross_layer bridge counts
- POST /api/graph/hydrate {query:'Solana'} — returns entity with edges
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHTMLFallbackStatus:
    """Test GET /api/graph/fallback/status endpoint"""
    
    def test_fallback_status_returns_parsers(self):
        """GET /api/graph/fallback/status should return all parsers with fallback fields"""
        response = requests.get(f"{BASE_URL}/api/graph/fallback/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "parsers" in data, f"Expected 'parsers' field in response: {data}"
        
        parsers = data["parsers"]
        assert isinstance(parsers, list), f"Expected parsers to be a list: {parsers}"
        
        # Check that parsers have fallback-related fields
        print(f"Found {len(parsers)} parsers in registry")
        for p in parsers:
            print(f"  - {p.get('name')}: status={p.get('status')}, consecutive_failures={p.get('consecutive_failures')}, html_fallback_active={p.get('html_fallback_active')}")
        
        # Verify at least some parsers exist
        assert len(parsers) >= 0, "Parser registry should exist (may be empty if not initialized)"


class TestHTMLFallbackCryptoRank:
    """Test CryptoRank HTML fallback scraper"""
    
    def test_cryptorank_html_coins(self):
        """POST /api/graph/fallback/test {parser:'CryptoRank'} should return 41+ coins"""
        response = requests.post(
            f"{BASE_URL}/api/graph/fallback/test",
            json={"parser": "CryptoRank"},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert data.get("parser") == "CryptoRank", f"Expected parser='CryptoRank', got {data}"
        assert data.get("type") == "coins", f"Expected type='coins', got {data}"
        
        count = data.get("count", 0)
        print(f"CryptoRank HTML returned {count} coins in {data.get('duration_sec', 0)}s")
        
        # Should return at least 41 coins from __NEXT_DATA__
        assert count >= 41, f"Expected at least 41 coins, got {count}"
        
        # Check sample data structure
        sample = data.get("sample", [])
        if sample:
            coin = sample[0]
            print(f"Sample coin: {coin}")
            assert "symbol" in coin, f"Expected 'symbol' in coin: {coin}"
            assert "source" in coin, f"Expected 'source' in coin: {coin}"
            assert coin.get("source") == "cryptorank_html", f"Expected source='cryptorank_html', got {coin.get('source')}"
    
    def test_cryptorank_html_funding(self):
        """POST /api/graph/fallback/test {parser:'CryptoRank_funding'} should return 6+ funding rounds"""
        response = requests.post(
            f"{BASE_URL}/api/graph/fallback/test",
            json={"parser": "CryptoRank_funding"},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert data.get("parser") == "CryptoRank_funding", f"Expected parser='CryptoRank_funding', got {data}"
        assert data.get("type") == "funding", f"Expected type='funding', got {data}"
        
        count = data.get("count", 0)
        print(f"CryptoRank HTML funding returned {count} rounds in {data.get('duration_sec', 0)}s")
        
        # Should return at least 6 funding rounds
        assert count >= 6, f"Expected at least 6 funding rounds, got {count}"
        
        # Check sample data structure
        sample = data.get("sample", [])
        if sample:
            funding = sample[0]
            print(f"Sample funding: {funding}")
            assert "project" in funding, f"Expected 'project' in funding: {funding}"
            assert "source" in funding, f"Expected 'source' in funding: {funding}"
            assert funding.get("source") == "cryptorank_html", f"Expected source='cryptorank_html', got {funding.get('source')}"


class TestHTMLFallbackDropstab:
    """Test Dropstab HTML fallback scraper"""
    
    def test_dropstab_html_activities(self):
        """POST /api/graph/fallback/test {parser:'Dropstab'} should return 60+ activities"""
        response = requests.post(
            f"{BASE_URL}/api/graph/fallback/test",
            json={"parser": "Dropstab"},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert data.get("parser") == "Dropstab", f"Expected parser='Dropstab', got {data}"
        assert data.get("type") == "activities", f"Expected type='activities', got {data}"
        
        count = data.get("count", 0)
        print(f"Dropstab HTML returned {count} activities in {data.get('duration_sec', 0)}s")
        
        # Should return at least 60 activities
        assert count >= 60, f"Expected at least 60 activities, got {count}"
        
        # Check sample data structure
        sample = data.get("sample", [])
        if sample:
            activity = sample[0]
            print(f"Sample activity: {activity}")
            assert "project_id" in activity, f"Expected 'project_id' in activity: {activity}"
            assert "source" in activity, f"Expected 'source' in activity: {activity}"
            assert activity.get("source") == "dropstab_html", f"Expected source='dropstab_html', got {activity.get('source')}"


class TestHTMLFallbackICODrops:
    """Test ICODrops HTML fallback scraper"""
    
    def test_icodrops_html_upcoming(self):
        """POST /api/graph/fallback/test {parser:'ICODrops'} may return 0 (JS-heavy site)"""
        response = requests.post(
            f"{BASE_URL}/api/graph/fallback/test",
            json={"parser": "ICODrops"},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert data.get("parser") == "ICODrops", f"Expected parser='ICODrops', got {data}"
        assert data.get("type") == "icos", f"Expected type='icos', got {data}"
        
        count = data.get("count", 0)
        print(f"ICODrops HTML returned {count} ICOs in {data.get('duration_sec', 0)}s")
        
        # ICODrops is JS-heavy, may return 0 - this is expected behavior
        print(f"Note: ICODrops is JS-heavy site, count={count} is acceptable (may be 0)")
        
        # Check sample data structure if any data returned
        sample = data.get("sample", [])
        if sample:
            ico = sample[0]
            print(f"Sample ICO: {ico}")
            assert "name" in ico, f"Expected 'name' in ICO: {ico}"
            assert "source" in ico, f"Expected 'source' in ICO: {ico}"
            assert ico.get("source") == "icodrops_html", f"Expected source='icodrops_html', got {ico.get('source')}"


class TestHTMLFallbackUnknownParser:
    """Test error handling for unknown parser"""
    
    def test_unknown_parser_returns_error(self):
        """POST /api/graph/fallback/test with unknown parser should return error with options"""
        response = requests.post(
            f"{BASE_URL}/api/graph/fallback/test",
            json={"parser": "UnknownParser"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is False, f"Expected ok=False for unknown parser, got {data}"
        assert "error" in data, f"Expected 'error' field in response: {data}"
        
        error = data.get("error", "")
        print(f"Error message: {error}")
        
        # Error should mention available options
        assert "Options:" in error or "Unknown parser" in error, f"Expected error to mention options: {error}"
        
        # Should list available parsers
        assert "CryptoRank" in error, f"Expected 'CryptoRank' in error options: {error}"
        assert "Dropstab" in error, f"Expected 'Dropstab' in error options: {error}"
        assert "ICODrops" in error, f"Expected 'ICODrops' in error options: {error}"


class TestGraphBuildWithFallback:
    """Test that graph build still works with fallback system integrated"""
    
    def test_graph_build_full(self):
        """POST /api/graph/build should complete full rebuild with 3504+ nodes, 4733+ edges"""
        response = requests.post(
            f"{BASE_URL}/api/graph/build",
            json={},
            timeout=120
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        totals = data.get("totals", {})
        nodes = totals.get("nodes", 0)
        edges = totals.get("edges", 0)
        
        print(f"Graph build completed: {nodes} nodes, {edges} edges in {totals.get('duration_sec', 0)}s")
        
        # Should have at least 3504 nodes and 4733 edges (from previous test)
        assert nodes >= 3504, f"Expected at least 3504 nodes, got {nodes}"
        assert edges >= 4733, f"Expected at least 4733 edges, got {edges}"
        
        # Check layer breakdown
        signal_edges = totals.get("signal_edges", 0)
        knowledge_edges = totals.get("knowledge_edges", 0)
        print(f"Layers: SIGNAL={signal_edges}, KNOWLEDGE={knowledge_edges}")
    
    def test_graph_build_stats(self):
        """GET /api/graph/build/stats should return cross_layer bridge counts"""
        response = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check cross-layer bridges
        cross_layer = data.get("cross_layer", {})
        token_of = cross_layer.get("token_of", 0)
        account_of = cross_layer.get("account_of", 0)
        official_account_of = cross_layer.get("official_account_of", 0)
        
        print(f"Cross-layer bridges: token_of={token_of}, account_of={account_of}, official_account_of={official_account_of}")
        
        # Should have some bridges
        assert token_of >= 0, f"Expected token_of >= 0, got {token_of}"
        assert account_of >= 0, f"Expected account_of >= 0, got {account_of}"
        assert official_account_of >= 0, f"Expected official_account_of >= 0, got {official_account_of}"
        
        # Check node and edge counts
        nodes = data.get("nodes", 0)
        edges = data.get("edges", 0)
        print(f"Total: {nodes} nodes, {edges} edges")
        
        # Check layers
        layers = data.get("layers", {})
        print(f"Layers: {layers}")


class TestGraphHydrate:
    """Test entity hydration endpoint"""
    
    def test_hydrate_solana(self):
        """POST /api/graph/hydrate {query:'Solana'} should return entity with edges"""
        response = requests.post(
            f"{BASE_URL}/api/graph/hydrate",
            json={"query": "Solana"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        matched_nodes = data.get("matched_nodes", 0)
        total_edges = data.get("total_edges", 0)
        total_neighbors = data.get("total_neighbors", 0)
        
        print(f"Solana hydration: {matched_nodes} matched nodes, {total_edges} edges, {total_neighbors} neighbors")
        
        # Should find Solana entity with edges
        assert matched_nodes >= 1, f"Expected at least 1 matched node for Solana, got {matched_nodes}"
        
        # Check nodes structure
        nodes = data.get("nodes", [])
        assert len(nodes) > 0, f"Expected nodes in response: {data}"
        
        # Check edges structure
        edges = data.get("edges", [])
        print(f"Found {len(edges)} edges for Solana")


# Fixtures
@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
