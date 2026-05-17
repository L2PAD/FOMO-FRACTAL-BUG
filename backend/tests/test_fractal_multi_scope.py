"""
Fractal Multi-Scope Pipeline Tests
===================================
Tests for the three independent fractal forecast pipelines:
- BTC: /api/fractal/btc/forecasts (entry ~73K)
- SPX: /api/fractal/spx/forecasts (entry ~6900)
- DXY: /api/fractal/dxy/forecasts (entry ~118)

Plus manual triggers and legacy endpoint compatibility.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected price ranges for data isolation validation
BTC_PRICE_RANGE = (50000, 120000)  # BTC typically 50K-120K
SPX_PRICE_RANGE = (4000, 8000)     # SPX typically 4000-8000
DXY_PRICE_RANGE = (90, 130)        # DXY typically 90-130


class TestBtcFractalForecasts:
    """BTC-specific forecast endpoint tests"""

    def test_btc_forecasts_returns_ok(self):
        """GET /api/fractal/btc/forecasts returns valid response"""
        resp = requests.get(f"{BASE_URL}/api/fractal/btc/forecasts")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True, "Expected ok:true"
        assert data.get("scope") == "BTC", f"Expected scope BTC, got {data.get('scope')}"
        assert "rows" in data, "Missing rows array"
        assert "summary" in data, "Missing summary object"
        print(f"BTC forecasts: {len(data['rows'])} rows, summary: {data['summary']}")

    def test_btc_forecasts_entry_price_range(self):
        """BTC forecasts have entry prices in BTC range (~73K)"""
        resp = requests.get(f"{BASE_URL}/api/fractal/btc/forecasts?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data.get("rows", []):
            entry = row.get("entryPrice")
            if entry is not None and entry > 0:
                assert BTC_PRICE_RANGE[0] <= entry <= BTC_PRICE_RANGE[1], \
                    f"BTC entry price {entry} outside expected range {BTC_PRICE_RANGE}"
                print(f"BTC entry price: ${entry:,.2f} - within expected range")

    def test_btc_forecasts_with_horizon_filter(self):
        """GET /api/fractal/btc/forecasts?horizon=7D returns only 7D rows"""
        resp = requests.get(f"{BASE_URL}/api/fractal/btc/forecasts?horizon=7D")
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data.get("rows", []):
            assert row.get("horizon") == "7D", f"Expected horizon 7D, got {row.get('horizon')}"
        print(f"BTC 7D filter: {len(data['rows'])} rows, all with horizon=7D")

    def test_btc_forecasts_with_limit(self):
        """GET /api/fractal/btc/forecasts?limit=5 respects limit"""
        resp = requests.get(f"{BASE_URL}/api/fractal/btc/forecasts?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data.get("rows", [])) <= 5, f"Expected max 5 rows, got {len(data.get('rows', []))}"
        print(f"BTC limit=5: {len(data['rows'])} rows returned")


class TestSpxFractalForecasts:
    """SPX-specific forecast endpoint tests"""

    def test_spx_forecasts_returns_ok(self):
        """GET /api/fractal/spx/forecasts returns valid response"""
        resp = requests.get(f"{BASE_URL}/api/fractal/spx/forecasts")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True, "Expected ok:true"
        assert data.get("scope") == "SPX", f"Expected scope SPX, got {data.get('scope')}"
        assert "rows" in data, "Missing rows array"
        assert "summary" in data, "Missing summary object"
        print(f"SPX forecasts: {len(data['rows'])} rows, summary: {data['summary']}")

    def test_spx_forecasts_entry_price_range(self):
        """SPX forecasts have entry prices in SPX range (~6900)"""
        resp = requests.get(f"{BASE_URL}/api/fractal/spx/forecasts?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data.get("rows", []):
            entry = row.get("entryPrice")
            if entry is not None and entry > 0:
                assert SPX_PRICE_RANGE[0] <= entry <= SPX_PRICE_RANGE[1], \
                    f"SPX entry price {entry} outside expected range {SPX_PRICE_RANGE}"
                print(f"SPX entry price: ${entry:,.2f} - within expected range")

    def test_spx_forecasts_with_horizon_filter(self):
        """GET /api/fractal/spx/forecasts?horizon=30D returns only 30D rows"""
        resp = requests.get(f"{BASE_URL}/api/fractal/spx/forecasts?horizon=30D")
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data.get("rows", []):
            assert row.get("horizon") == "30D", f"Expected horizon 30D, got {row.get('horizon')}"
        print(f"SPX 30D filter: {len(data['rows'])} rows, all with horizon=30D")

    def test_spx_forecasts_with_limit(self):
        """GET /api/fractal/spx/forecasts?limit=5 respects limit"""
        resp = requests.get(f"{BASE_URL}/api/fractal/spx/forecasts?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data.get("rows", [])) <= 5, f"Expected max 5 rows, got {len(data.get('rows', []))}"
        print(f"SPX limit=5: {len(data['rows'])} rows returned")


class TestDxyFractalForecasts:
    """DXY-specific forecast endpoint tests"""

    def test_dxy_forecasts_returns_ok(self):
        """GET /api/fractal/dxy/forecasts returns valid response"""
        resp = requests.get(f"{BASE_URL}/api/fractal/dxy/forecasts")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True, "Expected ok:true"
        assert data.get("scope") == "DXY", f"Expected scope DXY, got {data.get('scope')}"
        assert "rows" in data, "Missing rows array"
        assert "summary" in data, "Missing summary object"
        print(f"DXY forecasts: {len(data['rows'])} rows, summary: {data['summary']}")

    def test_dxy_forecasts_entry_price_range(self):
        """DXY forecasts have entry prices in DXY range (~118)"""
        resp = requests.get(f"{BASE_URL}/api/fractal/dxy/forecasts?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data.get("rows", []):
            entry = row.get("entryPrice")
            if entry is not None and entry > 0:
                assert DXY_PRICE_RANGE[0] <= entry <= DXY_PRICE_RANGE[1], \
                    f"DXY entry price {entry} outside expected range {DXY_PRICE_RANGE}"
                print(f"DXY entry price: ${entry:,.2f} - within expected range")

    def test_dxy_forecasts_with_horizon_filter(self):
        """GET /api/fractal/dxy/forecasts?horizon=90D returns only 90D rows"""
        resp = requests.get(f"{BASE_URL}/api/fractal/dxy/forecasts?horizon=90D")
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data.get("rows", []):
            assert row.get("horizon") == "90D", f"Expected horizon 90D, got {row.get('horizon')}"
        print(f"DXY 90D filter: {len(data['rows'])} rows, all with horizon=90D")

    def test_dxy_forecasts_with_limit(self):
        """GET /api/fractal/dxy/forecasts?limit=5 respects limit"""
        resp = requests.get(f"{BASE_URL}/api/fractal/dxy/forecasts?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data.get("rows", [])) <= 5, f"Expected max 5 rows, got {len(data.get('rows', []))}"
        print(f"DXY limit=5: {len(data['rows'])} rows returned")


class TestDataIsolation:
    """Cross-scope data isolation validation"""

    def test_no_price_mixing_btc_vs_spx(self):
        """BTC and SPX forecasts have clearly different price ranges"""
        btc_resp = requests.get(f"{BASE_URL}/api/fractal/btc/forecasts?limit=5")
        spx_resp = requests.get(f"{BASE_URL}/api/fractal/spx/forecasts?limit=5")
        
        assert btc_resp.status_code == 200
        assert spx_resp.status_code == 200
        
        btc_data = btc_resp.json()
        spx_data = spx_resp.json()
        
        # Get entry prices
        btc_entries = [r.get("entryPrice") for r in btc_data.get("rows", []) if r.get("entryPrice")]
        spx_entries = [r.get("entryPrice") for r in spx_data.get("rows", []) if r.get("entryPrice")]
        
        if btc_entries and spx_entries:
            # BTC should be at least 10x higher than SPX
            min_btc = min(btc_entries)
            max_spx = max(spx_entries)
            assert min_btc > max_spx * 5, \
                f"BTC ({min_btc}) should be >> SPX ({max_spx}). Possible data mixing!"
            print(f"Data isolation OK: BTC min ${min_btc:,.0f} >> SPX max ${max_spx:,.0f}")

    def test_no_price_mixing_spx_vs_dxy(self):
        """SPX and DXY forecasts have clearly different price ranges"""
        spx_resp = requests.get(f"{BASE_URL}/api/fractal/spx/forecasts?limit=5")
        dxy_resp = requests.get(f"{BASE_URL}/api/fractal/dxy/forecasts?limit=5")
        
        assert spx_resp.status_code == 200
        assert dxy_resp.status_code == 200
        
        spx_data = spx_resp.json()
        dxy_data = dxy_resp.json()
        
        # Get entry prices
        spx_entries = [r.get("entryPrice") for r in spx_data.get("rows", []) if r.get("entryPrice")]
        dxy_entries = [r.get("entryPrice") for r in dxy_data.get("rows", []) if r.get("entryPrice")]
        
        if spx_entries and dxy_entries:
            # SPX should be at least 30x higher than DXY
            min_spx = min(spx_entries)
            max_dxy = max(dxy_entries)
            assert min_spx > max_dxy * 20, \
                f"SPX ({min_spx}) should be >> DXY ({max_dxy}). Possible data mixing!"
            print(f"Data isolation OK: SPX min ${min_spx:,.0f} >> DXY max ${max_dxy:,.2f}")

    def test_scope_field_matches_endpoint(self):
        """Each endpoint returns rows with matching scope field"""
        endpoints = [
            ("/api/fractal/btc/forecasts", "BTC"),
            ("/api/fractal/spx/forecasts", "SPX"),
            ("/api/fractal/dxy/forecasts", "DXY"),
        ]
        
        for endpoint, expected_scope in endpoints:
            resp = requests.get(f"{BASE_URL}{endpoint}?limit=10")
            assert resp.status_code == 200
            data = resp.json()
            
            # Check response-level scope
            assert data.get("scope") == expected_scope, \
                f"{endpoint} response scope mismatch: expected {expected_scope}, got {data.get('scope')}"
            
            # Check row-level scope
            for row in data.get("rows", []):
                row_scope = row.get("scope", expected_scope)  # scope may be in row or inherited
                assert row_scope == expected_scope, \
                    f"{endpoint} row scope mismatch: expected {expected_scope}, got {row_scope}"
            
            print(f"{endpoint}: scope={expected_scope} verified for {len(data.get('rows', []))} rows")


class TestPipelineTriggers:
    """Manual pipeline trigger tests (POST endpoints)"""

    def test_btc_pipeline_trigger(self):
        """POST /api/fractal/btc/forecasts/run triggers BTC pipeline"""
        resp = requests.post(f"{BASE_URL}/api/fractal/btc/forecasts/run")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True, "Expected ok:true"
        print(f"BTC pipeline trigger response: {data}")

    def test_spx_pipeline_trigger(self):
        """POST /api/fractal/spx/forecasts/run triggers SPX pipeline"""
        resp = requests.post(f"{BASE_URL}/api/fractal/spx/forecasts/run")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True, "Expected ok:true"
        print(f"SPX pipeline trigger response: {data}")

    def test_dxy_pipeline_trigger(self):
        """POST /api/fractal/dxy/forecasts/run triggers DXY pipeline"""
        resp = requests.post(f"{BASE_URL}/api/fractal/dxy/forecasts/run")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True, "Expected ok:true"
        print(f"DXY pipeline trigger response: {data}")

    def test_run_all_pipelines(self):
        """POST /api/fractal/forecasts/run-all triggers all three pipelines"""
        resp = requests.post(f"{BASE_URL}/api/fractal/forecasts/run-all")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True, "Expected ok:true"
        assert "results" in data, "Expected results object"
        print(f"Run-all response: {data}")


class TestLegacyEndpoint:
    """Legacy endpoint backward compatibility tests"""

    def test_legacy_endpoint_default_btc(self):
        """GET /api/fractal/forecasts defaults to BTC scope"""
        resp = requests.get(f"{BASE_URL}/api/fractal/forecasts")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True, "Expected ok:true"
        assert data.get("scope") == "BTC", f"Expected default scope BTC, got {data.get('scope')}"
        print(f"Legacy endpoint (default): scope={data.get('scope')}, {len(data.get('rows', []))} rows")

    def test_legacy_endpoint_with_scope_btc(self):
        """GET /api/fractal/forecasts?scope=BTC returns BTC data"""
        resp = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("scope") == "BTC"
        
        # Verify BTC price range
        for row in data.get("rows", []):
            entry = row.get("entryPrice")
            if entry and entry > 0:
                assert BTC_PRICE_RANGE[0] <= entry <= BTC_PRICE_RANGE[1], \
                    f"Legacy BTC entry {entry} outside expected range"
        print(f"Legacy endpoint (scope=BTC): verified {len(data.get('rows', []))} rows")

    def test_legacy_endpoint_with_scope_spx(self):
        """GET /api/fractal/forecasts?scope=SPX returns SPX data"""
        resp = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=SPX")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("scope") == "SPX"
        
        # Verify SPX price range
        for row in data.get("rows", []):
            entry = row.get("entryPrice")
            if entry and entry > 0:
                assert SPX_PRICE_RANGE[0] <= entry <= SPX_PRICE_RANGE[1], \
                    f"Legacy SPX entry {entry} outside expected range"
        print(f"Legacy endpoint (scope=SPX): verified {len(data.get('rows', []))} rows")

    def test_legacy_endpoint_with_scope_dxy(self):
        """GET /api/fractal/forecasts?scope=DXY returns DXY data"""
        resp = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=DXY")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("scope") == "DXY"
        
        # Verify DXY price range
        for row in data.get("rows", []):
            entry = row.get("entryPrice")
            if entry and entry > 0:
                assert DXY_PRICE_RANGE[0] <= entry <= DXY_PRICE_RANGE[1], \
                    f"Legacy DXY entry {entry} outside expected range"
        print(f"Legacy endpoint (scope=DXY): verified {len(data.get('rows', []))} rows")

    def test_legacy_endpoint_with_horizon(self):
        """GET /api/fractal/forecasts?scope=BTC&horizon=7D filters correctly"""
        resp = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC&horizon=7D")
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data.get("rows", []):
            assert row.get("horizon") == "7D", f"Expected 7D, got {row.get('horizon')}"
        print(f"Legacy endpoint with horizon filter: {len(data.get('rows', []))} rows, all 7D")


class TestResponseStructure:
    """Response structure validation"""

    def test_row_fields_complete(self):
        """All rows have required fields"""
        required_fields = [
            "scope", "createdAt", "evaluateAt", "horizon", "entryPrice",
            "targetPrice", "expectedReturn", "direction", "confidence", "status"
        ]
        
        resp = requests.get(f"{BASE_URL}/api/fractal/btc/forecasts?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        
        for i, row in enumerate(data.get("rows", [])):
            for field in required_fields:
                assert field in row, f"Row {i} missing field: {field}"
        print(f"All {len(data.get('rows', []))} rows have required fields")

    def test_summary_fields_complete(self):
        """Summary has required fields"""
        required_summary_fields = [
            "total", "evaluated", "wins", "losses", "pending",
            "overdue", "winRate", "dirAccuracy", "avgReturn", "avgError"
        ]
        
        resp = requests.get(f"{BASE_URL}/api/fractal/btc/forecasts")
        assert resp.status_code == 200
        data = resp.json()
        summary = data.get("summary", {})
        
        for field in required_summary_fields:
            assert field in summary, f"Summary missing field: {field}"
        print(f"Summary has all required fields: {summary}")
