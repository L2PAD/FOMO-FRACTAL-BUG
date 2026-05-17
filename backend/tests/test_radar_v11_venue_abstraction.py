"""
P1.1 — Venue Abstraction Layer Tests
=====================================
Tests for venueCount and venues fields in SpotRadarRow.
DUAL_VENUE_ENABLED=false → all rows should have venueCount=1, venues=['binance']
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestVenueAbstractionAlpha:
    """Test venueCount and venues fields for alpha venue"""
    
    def test_alpha_endpoint_returns_ok(self):
        """GET /api/v11/exchange/radar/spot?venue=alpha&limit=5 returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("venue") == "alpha"
        print(f"✓ Alpha endpoint returns ok=true with {len(data.get('rows', []))} rows")
    
    def test_alpha_rows_have_venue_count(self):
        """All alpha rows have venueCount field (integer)"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        assert len(rows) > 0, "Expected at least one row"
        
        for row in rows:
            assert "venueCount" in row, f"Row {row['symbol']} missing venueCount"
            assert isinstance(row["venueCount"], int), f"Row {row['symbol']} venueCount not int"
            print(f"✓ {row['symbol']}: venueCount={row['venueCount']}")
    
    def test_alpha_rows_have_venues_array(self):
        """All alpha rows have venues field (array of strings)"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert "venues" in row, f"Row {row['symbol']} missing venues"
            assert isinstance(row["venues"], list), f"Row {row['symbol']} venues not list"
            assert all(isinstance(v, str) for v in row["venues"]), f"Row {row['symbol']} venues contains non-string"
            print(f"✓ {row['symbol']}: venues={row['venues']}")
    
    def test_alpha_dual_venue_disabled_returns_single_venue(self):
        """With DUAL_VENUE_ENABLED=false, all rows have venueCount=1, venues=['binance']"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=20")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert row["venueCount"] == 1, f"Row {row['symbol']} expected venueCount=1, got {row['venueCount']}"
            assert row["venues"] == ["binance"], f"Row {row['symbol']} expected venues=['binance'], got {row['venues']}"
        
        print(f"✓ All {len(rows)} alpha rows have venueCount=1, venues=['binance']")


class TestVenueAbstractionMain:
    """Test venueCount and venues fields for main venue"""
    
    def test_main_endpoint_returns_ok(self):
        """GET /api/v11/exchange/radar/spot?venue=main&limit=5 returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("venue") == "main"
        print(f"✓ Main endpoint returns ok=true with {len(data.get('rows', []))} rows")
    
    def test_main_rows_have_venue_count(self):
        """All main rows have venueCount field (integer)"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        assert len(rows) > 0, "Expected at least one row"
        
        for row in rows:
            assert "venueCount" in row, f"Row {row['symbol']} missing venueCount"
            assert isinstance(row["venueCount"], int), f"Row {row['symbol']} venueCount not int"
            print(f"✓ {row['symbol']}: venueCount={row['venueCount']}")
    
    def test_main_rows_have_venues_array(self):
        """All main rows have venues field (array of strings)"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert "venues" in row, f"Row {row['symbol']} missing venues"
            assert isinstance(row["venues"], list), f"Row {row['symbol']} venues not list"
            assert all(isinstance(v, str) for v in row["venues"]), f"Row {row['symbol']} venues contains non-string"
            print(f"✓ {row['symbol']}: venues={row['venues']}")
    
    def test_main_dual_venue_disabled_returns_single_venue(self):
        """With DUAL_VENUE_ENABLED=false, all rows have venueCount=1, venues=['binance']"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=20")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert row["venueCount"] == 1, f"Row {row['symbol']} expected venueCount=1, got {row['venueCount']}"
            assert row["venues"] == ["binance"], f"Row {row['symbol']} expected venues=['binance'], got {row['venues']}"
        
        print(f"✓ All {len(rows)} main rows have venueCount=1, venues=['binance']")


class TestExistingRadarFieldsIntegrity:
    """Verify existing radar fields still work correctly (no regression)"""
    
    def test_conviction_field_present_and_valid(self):
        """conviction field is present and 0-100"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert "conviction" in row, f"Row {row['symbol']} missing conviction"
            assert 0 <= row["conviction"] <= 100, f"Row {row['symbol']} conviction out of range: {row['conviction']}"
        print(f"✓ All rows have valid conviction (0-100)")
    
    def test_verdict_field_present_and_valid(self):
        """verdict field is present and has valid values"""
        valid_verdicts = ["buy", "sell", "watch", "neutral", "data_gap"]
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert "verdict" in row, f"Row {row['symbol']} missing verdict"
            assert row["verdict"] in valid_verdicts, f"Row {row['symbol']} invalid verdict: {row['verdict']}"
        print(f"✓ All rows have valid verdict")
    
    def test_horizons_field_present(self):
        """horizons field is present with short/mid/swing/primary"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            if row["verdict"] != "data_gap":
                assert "horizons" in row, f"Row {row['symbol']} missing horizons"
                if row["horizons"]:
                    assert "short" in row["horizons"], f"Row {row['symbol']} horizons missing short"
                    assert "mid" in row["horizons"], f"Row {row['symbol']} horizons missing mid"
                    assert "swing" in row["horizons"], f"Row {row['symbol']} horizons missing swing"
                    assert "primary" in row["horizons"], f"Row {row['symbol']} horizons missing primary"
        print(f"✓ All non-data_gap rows have horizons with short/mid/swing/primary")
    
    def test_integrity_field_present(self):
        """integrity field is present with status, coveragePct, setupScore"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            if row["verdict"] != "data_gap":
                assert "integrity" in row, f"Row {row['symbol']} missing integrity"
                if row["integrity"]:
                    assert "status" in row["integrity"], f"Row {row['symbol']} integrity missing status"
                    assert "coveragePct" in row["integrity"], f"Row {row['symbol']} integrity missing coveragePct"
                    assert "setupScore" in row["integrity"], f"Row {row['symbol']} integrity missing setupScore"
        print(f"✓ All non-data_gap rows have integrity with status/coveragePct/setupScore")
    
    def test_explain_one_liner_present(self):
        """explain.oneLiner field is present for all rows"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        for row in rows:
            assert "explain" in row, f"Row {row['symbol']} missing explain"
            assert "oneLiner" in row["explain"], f"Row {row['symbol']} explain missing oneLiner"
            assert row["explain"]["oneLiner"] is not None, f"Row {row['symbol']} oneLiner is None"
            assert len(row["explain"]["oneLiner"]) > 0, f"Row {row['symbol']} oneLiner is empty"
        print(f"✓ All rows have explain.oneLiner field")


class TestVenueFieldsNotNull:
    """Verify venueCount and venues fields are never null"""
    
    def test_alpha_venue_fields_not_null(self):
        """venueCount and venues fields are not null for all alpha rows"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=50")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        null_venue_count = []
        null_venues = []
        
        for row in rows:
            if row.get("venueCount") is None:
                null_venue_count.append(row["symbol"])
            if row.get("venues") is None:
                null_venues.append(row["symbol"])
        
        assert len(null_venue_count) == 0, f"Rows with null venueCount: {null_venue_count}"
        assert len(null_venues) == 0, f"Rows with null venues: {null_venues}"
        print(f"✓ All {len(rows)} alpha rows have non-null venueCount and venues")
    
    def test_main_venue_fields_not_null(self):
        """venueCount and venues fields are not null for all main rows"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=50")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        null_venue_count = []
        null_venues = []
        
        for row in rows:
            if row.get("venueCount") is None:
                null_venue_count.append(row["symbol"])
            if row.get("venues") is None:
                null_venues.append(row["symbol"])
        
        assert len(null_venue_count) == 0, f"Rows with null venueCount: {null_venue_count}"
        assert len(null_venues) == 0, f"Rows with null venues: {null_venues}"
        print(f"✓ All {len(rows)} main rows have non-null venueCount and venues")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
