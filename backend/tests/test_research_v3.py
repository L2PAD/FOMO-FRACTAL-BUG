"""
Research V3 API Tests
=====================
Tests the 4 Research V3 endpoints:
- GET /api/v11/exchange/research/global - Global market context
- GET /api/v11/exchange/research/asset/{symbol} - Per-asset research with radar overlay
- GET /api/v11/exchange/research/universe - Universe insight with aggregate stats
- GET /api/v11/exchange/research/symbols - Available symbols list
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestResearchGlobal:
    """Tests for GET /api/v11/exchange/research/global"""

    def test_global_returns_ok(self):
        """Global endpoint returns ok=true, mode='global'"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/global", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("mode") == "global"
        print(f"Global mode: latency={data.get('latencyMs')}ms")

    def test_global_has_market_state(self):
        """Global has marketState with 5 domains"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/global", timeout=30)
        data = response.json()
        ms = data.get("marketState", {})
        assert "regime" in ms
        assert "volatility" in ms
        assert "liquidity" in ms
        assert "flow" in ms
        assert "stress" in ms
        # Each domain has state and confidence
        for key in ["regime", "volatility", "liquidity", "flow", "stress"]:
            assert "state" in ms[key]
            assert "confidence" in ms[key]
        print(f"Market state regime: {ms['regime']['state']}")

    def test_global_has_risk_pressure(self):
        """Global has riskPressure with score, level, drivers"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/global", timeout=30)
        data = response.json()
        rp = data.get("riskPressure", {})
        assert "score" in rp
        assert 0 <= rp["score"] <= 1
        assert rp.get("level") in ["LOW", "MID", "HIGH"]
        assert "drivers" in rp
        print(f"Risk pressure: {rp['score']} ({rp['level']})")

    def test_global_has_horizon_bias(self):
        """Global has horizonBias with short, mid, swing"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/global", timeout=30)
        data = response.json()
        hb = data.get("horizonBias", {})
        for horizon in ["short", "mid", "swing"]:
            assert horizon in hb
            assert "bias" in hb[horizon]
            assert "confidence" in hb[horizon]
        print(f"Horizon bias short: {hb['short']['bias']}")

    def test_global_has_dominant_forces(self):
        """Global has dominantForces array (up to 5)"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/global", timeout=30)
        data = response.json()
        df = data.get("dominantForces", [])
        assert isinstance(df, list)
        assert len(df) <= 5
        if df:
            assert "name" in df[0]
            assert "state" in df[0]
            assert "impactScore" in df[0]
        print(f"Dominant forces count: {len(df)}")

    def test_global_has_execution_implications(self):
        """Global has executionImplications with style, avoid, instruments, controls"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/global", timeout=30)
        data = response.json()
        ei = data.get("executionImplications", {})
        assert "style" in ei
        assert "avoid" in ei
        assert "preferredInstruments" in ei
        assert "riskControls" in ei
        print(f"Execution style: {ei['style']}")

    def test_global_has_integrity(self):
        """Global has integrity with status, coveragePct, reasons"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/global", timeout=30)
        data = response.json()
        integ = data.get("integrity", {})
        assert "status" in integ
        assert integ["status"] in ["HEALTHY", "DEGRADED", "CRITICAL"]
        assert "coveragePct" in integ
        assert "reasons" in integ
        print(f"Integrity: {integ['status']} ({integ['coveragePct']}%)")


class TestResearchAsset:
    """Tests for GET /api/v11/exchange/research/asset/{symbol}"""

    def test_asset_ai16zusdt_returns_ok(self):
        """Asset endpoint for AI16ZUSDT returns ok=true, mode='asset'"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/asset/AI16ZUSDT", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("mode") == "asset"
        assert data.get("symbol") == "AI16ZUSDT"
        print(f"Asset AI16ZUSDT: latency={data.get('latencyMs')}ms")

    def test_asset_ai16zusdt_has_overlay(self):
        """Asset AI16ZUSDT has assetOverlay with verdict, conviction, tier, horizon"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/asset/AI16ZUSDT", timeout=30)
        data = response.json()
        overlay = data.get("assetOverlay")
        assert overlay is not None, "AI16ZUSDT should have assetOverlay"
        assert "verdict" in overlay
        assert overlay["verdict"] in ["buy", "sell", "watch", "neutral"]
        assert "conviction" in overlay
        assert isinstance(overlay["conviction"], (int, float))
        assert "convictionTier" in overlay
        assert "horizon" in overlay
        assert "setupScore" in overlay
        print(f"AI16ZUSDT overlay: {overlay['verdict']} conv={overlay['conviction']} tier={overlay['convictionTier']}")

    def test_asset_solusdt_returns_valid(self):
        """Asset endpoint for SOLUSDT returns valid data"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/asset/SOLUSDT", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("mode") == "asset"
        assert data.get("symbol") == "SOLUSDT"
        overlay = data.get("assetOverlay")
        assert overlay is not None, "SOLUSDT should have assetOverlay"
        print(f"SOLUSDT overlay: {overlay['verdict']} conv={overlay['conviction']}")

    def test_asset_normalizes_symbol(self):
        """Asset endpoint auto-appends USDT if missing"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/asset/SOL", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("symbol") == "SOLUSDT"
        print("Symbol normalization works: SOL -> SOLUSDT")

    def test_asset_has_all_core_fields(self):
        """Asset endpoint has all core report fields"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/asset/BTCUSDT", timeout=30)
        data = response.json()
        assert "marketState" in data
        assert "riskPressure" in data
        assert "horizonBias" in data
        assert "dominantForces" in data
        assert "executionImplications" in data
        assert "integrity" in data
        print("Asset endpoint has all core fields")


class TestResearchUniverse:
    """Tests for GET /api/v11/exchange/research/universe"""

    def test_universe_returns_ok(self):
        """Universe endpoint returns ok=true, mode='universe'"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/universe", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("mode") == "universe"
        print(f"Universe mode: latency={data.get('latencyMs')}ms")

    def test_universe_has_insight(self):
        """Universe has universeInsight with totalSymbols, dominance, stats"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/universe", timeout=30)
        data = response.json()
        insight = data.get("universeInsight", {})
        assert "totalSymbols" in insight
        assert "dominance" in insight
        assert "stats" in insight
        print(f"Universe insight: {insight['totalSymbols']} symbols")

    def test_universe_total_symbols_over_100(self):
        """Universe totalSymbols > 100 (expected ~167)"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/universe", timeout=30)
        data = response.json()
        total = data.get("universeInsight", {}).get("totalSymbols", 0)
        assert total > 100, f"Expected >100 symbols, got {total}"
        print(f"Universe has {total} symbols (expected ~167)")

    def test_universe_dominance_format(self):
        """Universe dominance is array with pct and label"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/universe", timeout=30)
        data = response.json()
        dominance = data.get("universeInsight", {}).get("dominance", [])
        assert isinstance(dominance, list)
        if dominance:
            d = dominance[0]
            assert "pct" in d
            assert "label" in d
            print(f"Top dominance: {d['pct']}% - {d['label']}")

    def test_universe_stats_has_percentages(self):
        """Universe stats has buyPct, sellPct, watchPct, compressionPct, highConvictionPct"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/universe", timeout=30)
        data = response.json()
        stats = data.get("universeInsight", {}).get("stats", {})
        assert "buyPct" in stats
        assert "sellPct" in stats
        assert "watchPct" in stats
        assert "compressionPct" in stats
        assert "highConvictionPct" in stats
        print(f"Universe stats: buy={stats['buyPct']}%, sell={stats['sellPct']}%, watch={stats['watchPct']}%")


class TestResearchSymbols:
    """Tests for GET /api/v11/exchange/research/symbols"""

    def test_symbols_returns_list(self):
        """Symbols endpoint returns list of available symbols"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/symbols", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "symbols" in data
        assert isinstance(data["symbols"], list)
        assert "count" in data
        print(f"Symbols endpoint: {data['count']} symbols available")

    def test_symbols_contains_known_assets(self):
        """Symbols list contains known assets like BTCUSDT, SOLUSDT, AI16ZUSDT"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/symbols", timeout=30)
        data = response.json()
        symbols = data.get("symbols", [])
        assert "BTCUSDT" in symbols
        assert "SOLUSDT" in symbols
        assert "AI16ZUSDT" in symbols
        print("Known assets found in symbols list")

    def test_symbols_count_over_100(self):
        """Symbols count > 100"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/symbols", timeout=30)
        data = response.json()
        count = data.get("count", 0)
        assert count > 100, f"Expected >100 symbols, got {count}"
        print(f"Symbols count: {count}")


class TestResearchCache:
    """Tests for cache behavior"""

    def test_cache_returns_from_cache(self):
        """Second call within 45s returns fromCache=true"""
        # First call to populate cache
        r1 = requests.get(f"{BASE_URL}/api/v11/exchange/research/global", timeout=30)
        # Second call should hit cache
        r2 = requests.get(f"{BASE_URL}/api/v11/exchange/research/global", timeout=30)
        data = r2.json()
        assert data.get("fromCache") is True
        print("Cache working: fromCache=true on second call")

    def test_force_bypasses_cache(self):
        """force=true bypasses cache"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/research/global?force=true", timeout=30)
        data = response.json()
        assert data.get("fromCache") is False
        print("Force bypass working: fromCache=false with force=true")


class TestPreviousFeaturesRegression:
    """Regression tests for previous features"""

    def test_selfcheck_still_works(self):
        """Radar selfcheck endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Selfcheck working: {data.get('coverage', {}).get('totalSymbols')} symbols")

    def test_market_board_still_works(self):
        """Market board endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/board", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("Market board working")

    def test_radar_scan_still_works(self):
        """Radar scan endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/scan?venue=alpha&limit=10", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert len(data.get("rows", [])) > 0
        print(f"Radar scan working: {len(data.get('rows', []))} rows")
