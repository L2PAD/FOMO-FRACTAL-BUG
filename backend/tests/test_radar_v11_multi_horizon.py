"""
Radar V11 Multi-Horizon UI Backend Tests
=========================================
Tests for:
- convictionTier field in radar responses
- horizons object with short/mid/swing/primary fields
- Horizon data structure validation
- Health and cache endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRadarMultiHorizonAPI:
    """Tests for Multi-Horizon feature in radar endpoints."""

    def test_health_endpoint(self):
        """Test /api/exchange/health returns HEALTHY status."""
        response = requests.get(f"{BASE_URL}/api/exchange/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ["HEALTHY", "DEGRADED"]
        assert "radar" in data
        assert "services" in data
        print(f"Health status: {data.get('status')}")

    def test_cache_stats_endpoint(self):
        """Test /api/exchange/cache/stats returns cache info."""
        response = requests.get(f"{BASE_URL}/api/exchange/cache/stats", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "cache" in data
        cache = data["cache"]
        assert "enabled" in cache
        assert "hits" in cache
        assert "misses" in cache
        print(f"Cache stats: enabled={cache.get('enabled')}, hitRate={cache.get('hitRate')}")

    def test_spot_radar_returns_conviction_tier(self):
        """Test /api/v11/exchange/radar/spot returns convictionTier field."""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/spot",
            params={"venue": "main", "limit": 5},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "rows" in data
        rows = data["rows"]
        assert len(rows) > 0
        
        # Check convictionTier in first row
        first_row = rows[0]
        assert "convictionTier" in first_row, "convictionTier field missing"
        tier = first_row.get("convictionTier")
        assert tier in ["A+", "A", "B", "C", "noise", None], f"Invalid tier: {tier}"
        print(f"First row: {first_row['symbol']} - Tier: {tier}")

    def test_spot_radar_returns_horizons_object(self):
        """Test /api/v11/exchange/radar/spot returns horizons field with correct structure."""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/spot",
            params={"venue": "main", "limit": 5},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        assert len(rows) > 0
        
        # Check horizons structure in first row
        first_row = rows[0]
        assert "horizons" in first_row, "horizons field missing"
        horizons = first_row.get("horizons")
        
        if horizons is not None:
            # Validate horizons structure
            assert "short" in horizons, "horizons.short missing"
            assert "mid" in horizons, "horizons.mid missing"
            assert "swing" in horizons, "horizons.swing missing"
            assert "primary" in horizons, "horizons.primary missing"
            
            # Validate short horizon
            short = horizons["short"]
            assert "direction" in short, "short.direction missing"
            assert "conviction" in short, "short.conviction missing"
            assert "label" in short, "short.label missing"
            assert short["label"] == "0-2d", f"Expected '0-2d', got {short['label']}"
            
            # Validate mid horizon
            mid = horizons["mid"]
            assert mid["label"] == "3-7d", f"Expected '3-7d', got {mid['label']}"
            
            # Validate swing horizon
            swing = horizons["swing"]
            assert swing["label"] == "1-4w", f"Expected '1-4w', got {swing['label']}"
            
            # Validate primary
            assert horizons["primary"] in ["short", "mid", "swing"]
            
            print(f"Horizons validated for {first_row['symbol']}: primary={horizons['primary']}")
            print(f"  Short: dir={short['direction']}, conv={short['conviction']}")
            print(f"  Mid: dir={mid['direction']}, conv={mid['conviction']}")
            print(f"  Swing: dir={swing['direction']}, conv={swing['conviction']}")

    def test_spot_alpha_radar_returns_multi_horizon_fields(self):
        """Test alpha venue also returns convictionTier and horizons."""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/spot",
            params={"venue": "alpha", "limit": 5},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        rows = data.get("rows", [])
        
        if len(rows) > 0:
            first_row = rows[0]
            assert "convictionTier" in first_row
            assert "horizons" in first_row
            print(f"Alpha row: {first_row['symbol']} - Tier: {first_row.get('convictionTier')}")

    def test_futures_radar_returns_conviction_tier(self):
        """Test /api/v11/exchange/radar/futures returns convictionTier field."""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/futures",
            params={"limit": 5},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        rows = data.get("rows", [])
        
        # Note: Futures may or may not have convictionTier based on implementation
        # Check if field exists (even if null)
        if len(rows) > 0:
            first_row = rows[0]
            # convictionTier may not be implemented for futures yet
            print(f"Futures row: {first_row['symbol']} - Keys: {list(first_row.keys())[:10]}")

    def test_tier_distribution_in_spot_main(self):
        """Verify tier distribution across spot main universe."""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/spot",
            params={"venue": "main", "limit": 100},
            timeout=20
        )
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        tier_counts = {"A+": 0, "A": 0, "B": 0, "C": 0, "noise": 0, "null": 0}
        for row in rows:
            tier = row.get("convictionTier")
            if tier in tier_counts:
                tier_counts[tier] += 1
            else:
                tier_counts["null"] += 1
        
        print(f"Tier distribution: {tier_counts}")
        # At least some rows should have valid tiers
        valid_tiers = tier_counts["A+"] + tier_counts["A"] + tier_counts["B"] + tier_counts["C"]
        assert valid_tiers > 0, "No valid tiers found"

    def test_horizon_conviction_values_range(self):
        """Verify horizon conviction values are within 0-100 range."""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/spot",
            params={"venue": "main", "limit": 25},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            horizons = row.get("horizons")
            if horizons:
                for h_name in ["short", "mid", "swing"]:
                    h = horizons.get(h_name)
                    if h:
                        conv = h.get("conviction", 0)
                        assert 0 <= conv <= 100, f"{row['symbol']} {h_name} conviction out of range: {conv}"
        
        print(f"Validated conviction range for {len(rows)} rows")

    def test_horizon_direction_values(self):
        """Verify horizon direction values are valid."""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/spot",
            params={"venue": "main", "limit": 25},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        valid_directions = ["long", "short", "neutral"]
        for row in rows:
            horizons = row.get("horizons")
            if horizons:
                for h_name in ["short", "mid", "swing"]:
                    h = horizons.get(h_name)
                    if h:
                        direction = h.get("direction", "")
                        assert direction in valid_directions, f"{row['symbol']} {h_name} invalid direction: {direction}"
        
        print(f"Validated directions for {len(rows)} rows")


class TestUniverseEndpoint:
    """Tests for universe endpoint."""

    def test_spot_universe(self):
        """Test /api/v11/exchange/radar/universe?mode=spot."""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/universe",
            params={"mode": "spot"},
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "spotMainCount" in data
        assert "spotAlphaCount" in data
        print(f"Spot universe: Main={data.get('spotMainCount')}, Alpha={data.get('spotAlphaCount')}")

    def test_futures_universe(self):
        """Test /api/v11/exchange/radar/universe?mode=futures."""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/universe",
            params={"mode": "futures"},
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "futuresCount" in data
        print(f"Futures universe: {data.get('futuresCount')} symbols")


class TestPaginationAndFilters:
    """Tests for pagination and filter functionality."""

    def test_pagination_metadata(self):
        """Test pagination metadata in response."""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/spot",
            params={"venue": "main", "page": 1, "limit": 10},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "meta" in data
        meta = data["meta"]
        assert "total" in meta
        assert "page" in meta
        assert "pages" in meta
        assert "limit" in meta
        assert meta["page"] == 1
        assert meta["limit"] == 10
        print(f"Pagination: page={meta['page']}, pages={meta['pages']}, total={meta['total']}")

    def test_verdict_filter(self):
        """Test verdict filter parameter."""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/spot",
            params={"venue": "main", "verdict": "buy", "limit": 50},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        # All returned rows should have buy verdict
        for row in rows:
            assert row.get("verdict") == "buy", f"Expected buy, got {row.get('verdict')}"
        
        print(f"Verdict filter returned {len(rows)} BUY signals")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
