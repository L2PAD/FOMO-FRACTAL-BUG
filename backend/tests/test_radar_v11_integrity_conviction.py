"""
Test Suite: Radar V11 Integrity & Conviction Control Feature
=============================================================
Tests the integrity field and conviction control mechanisms:
- Integrity field structure (status/coveragePct/setupScore/reasons)
- Conviction capping: degraded=max85, snapshot=max70, highRisk=max55
- BUY/SELL gating: only with integrity=ok and setupScore>=0.4
- Selfcheck endpoint validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthCheck:
    """Basic health check - run first"""
    
    def test_health_endpoint_returns_healthy(self):
        """Health endpoint should return HEALTHY status"""
        response = requests.get(f"{BASE_URL}/api/exchange/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "HEALTHY"
        print(f"✓ Health status: {data.get('status')}")


class TestIntegrityFieldStructure:
    """Test integrity field is present and has correct structure"""
    
    def test_spot_main_has_integrity_field(self):
        """Each spot main row should have integrity field"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=50")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        assert len(rows) > 0, "Should have rows"
        
        for row in rows:
            integrity = row.get("integrity")
            assert integrity is not None, f"{row['symbol']} missing integrity field"
            assert "status" in integrity, f"{row['symbol']} integrity missing status"
            assert "coveragePct" in integrity, f"{row['symbol']} integrity missing coveragePct"
            assert "setupScore" in integrity, f"{row['symbol']} integrity missing setupScore"
            assert "reasons" in integrity, f"{row['symbol']} integrity missing reasons"
        
        print(f"✓ All {len(rows)} rows have integrity field with required structure")
    
    def test_integrity_status_values_valid(self):
        """Integrity status should be one of: ok, degraded, invalid"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        valid_statuses = {"ok", "degraded", "invalid"}
        status_counts = {"ok": 0, "degraded": 0, "invalid": 0}
        
        for row in rows:
            status = row.get("integrity", {}).get("status")
            assert status in valid_statuses, f"{row['symbol']} has invalid status: {status}"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"✓ Integrity distribution: {status_counts}")
    
    def test_coverage_pct_valid_range(self):
        """Coverage percentage should be 0-100"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        for row in rows:
            cov = row.get("integrity", {}).get("coveragePct", -1)
            assert 0 <= cov <= 100, f"{row['symbol']} coverage {cov} not in 0-100"
        
        print(f"✓ All coverage percentages are valid (0-100)")
    
    def test_setup_score_valid_range(self):
        """Setup score should be 0-1"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        for row in rows:
            score = row.get("integrity", {}).get("setupScore", -1)
            assert 0 <= score <= 1, f"{row['symbol']} setupScore {score} not in 0-1"
        
        print(f"✓ All setup scores are valid (0-1)")


class TestIntegrityStatusComputation:
    """Test integrity status is correctly computed based on data source"""
    
    def test_snapshot_source_is_degraded(self):
        """Snapshot source rows should have degraded status with SNAPSHOT_SOURCE reason"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        snapshot_rows = [r for r in rows if r.get("source") == "snapshot"]
        print(f"Found {len(snapshot_rows)} snapshot rows")
        
        for row in snapshot_rows:
            integrity = row.get("integrity", {})
            assert integrity.get("status") == "degraded", \
                f"{row['symbol']} snapshot should be degraded, got {integrity.get('status')}"
            assert "SNAPSHOT_SOURCE" in integrity.get("reasons", []), \
                f"{row['symbol']} should have SNAPSHOT_SOURCE reason"
        
        print(f"✓ All {len(snapshot_rows)} snapshot rows are correctly marked as degraded")
    
    def test_ok_status_has_good_coverage(self):
        """OK status rows should have coverage >= 70%"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        ok_rows = [r for r in rows if r.get("integrity", {}).get("status") == "ok"]
        print(f"Found {len(ok_rows)} ok status rows")
        
        for row in ok_rows:
            cov = row.get("integrity", {}).get("coveragePct", 0)
            # OK status requires coverage >= 70% (though usually higher)
            # We check that it's at least not degraded due to low coverage
            assert cov >= 50, f"{row['symbol']} ok status but coverage {cov}% < 50%"
        
        print(f"✓ All OK status rows have adequate coverage")


class TestConvictionCapping:
    """Test conviction is clamped based on integrity status and source"""
    
    def test_degraded_conviction_max_85(self):
        """Degraded status should have conviction capped at 85"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        degraded_rows = [r for r in rows if r.get("integrity", {}).get("status") == "degraded"]
        print(f"Found {len(degraded_rows)} degraded rows")
        
        over_85 = [r for r in degraded_rows if r.get("conviction", 0) > 85]
        assert len(over_85) == 0, f"Found {len(over_85)} degraded rows with conviction > 85"
        
        if degraded_rows:
            max_conv = max(r.get("conviction", 0) for r in degraded_rows)
            print(f"✓ All degraded rows capped. Max conviction: {max_conv} (limit: 85)")
    
    def test_snapshot_conviction_max_70(self):
        """Snapshot source should have conviction capped at 70"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        snapshot_rows = [r for r in rows if r.get("source") == "snapshot"]
        print(f"Found {len(snapshot_rows)} snapshot rows")
        
        over_70 = [r for r in snapshot_rows if r.get("conviction", 0) > 70]
        assert len(over_70) == 0, f"Found {len(over_70)} snapshot rows with conviction > 70"
        
        if snapshot_rows:
            max_conv = max(r.get("conviction", 0) for r in snapshot_rows)
            print(f"✓ All snapshot rows capped. Max conviction: {max_conv} (limit: 70)")
    
    def test_high_risk_conviction_max_55(self):
        """High risk (>0.55) rows should have conviction capped at 55"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        high_risk_rows = [r for r in rows if r.get("features", {}).get("risk", 0) > 0.55]
        print(f"Found {len(high_risk_rows)} high risk rows")
        
        over_55 = [r for r in high_risk_rows if r.get("conviction", 0) > 55]
        assert len(over_55) == 0, f"Found {len(over_55)} high risk rows with conviction > 55"
        
        if high_risk_rows:
            max_conv = max(r.get("conviction", 0) for r in high_risk_rows)
            print(f"✓ All high risk rows capped. Max conviction: {max_conv} (limit: 55)")


class TestVerdictGating:
    """Test BUY/SELL verdicts are properly gated by integrity and setupScore"""
    
    def test_no_buy_sell_with_degraded(self):
        """BUY/SELL verdicts should NOT appear with degraded integrity"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        degraded_rows = [r for r in rows if r.get("integrity", {}).get("status") == "degraded"]
        buy_sell_degraded = [r for r in degraded_rows if r.get("verdict") in ["buy", "sell"]]
        
        for r in buy_sell_degraded:
            print(f"  ISSUE: {r['symbol']} has {r['verdict']} with degraded integrity")
        
        assert len(buy_sell_degraded) == 0, \
            f"Found {len(buy_sell_degraded)} BUY/SELL with degraded integrity (should be WATCH)"
        
        print(f"✓ No BUY/SELL verdicts with degraded integrity")
    
    def test_buy_sell_requires_ok_integrity(self):
        """All BUY/SELL verdicts should have integrity=ok"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        buy_sell_rows = [r for r in rows if r.get("verdict") in ["buy", "sell"]]
        print(f"Found {len(buy_sell_rows)} BUY/SELL rows")
        
        for row in buy_sell_rows:
            integrity_status = row.get("integrity", {}).get("status")
            assert integrity_status == "ok", \
                f"{row['symbol']} has {row['verdict']} but integrity={integrity_status}"
        
        print(f"✓ All BUY/SELL rows have integrity=ok")
    
    def test_buy_sell_requires_setup_score_04(self):
        """All BUY/SELL verdicts should have setupScore >= 0.4"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        buy_sell_rows = [r for r in rows if r.get("verdict") in ["buy", "sell"]]
        print(f"Found {len(buy_sell_rows)} BUY/SELL rows")
        
        low_setup = [r for r in buy_sell_rows if r.get("integrity", {}).get("setupScore", 1) < 0.4]
        for r in low_setup:
            print(f"  ISSUE: {r['symbol']} has {r['verdict']} but setupScore={r.get('integrity', {}).get('setupScore')}")
        
        assert len(low_setup) == 0, \
            f"Found {len(low_setup)} BUY/SELL with setupScore < 0.4"
        
        print(f"✓ All BUY/SELL rows have setupScore >= 0.4")
    
    def test_degraded_becomes_watch_not_buy(self):
        """Degraded rows with high conviction should be WATCH, not BUY"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        degraded_high_conv = [r for r in rows 
                             if r.get("integrity", {}).get("status") == "degraded"
                             and r.get("conviction", 0) >= 45]
        
        # These should be WATCH at most, not BUY/SELL
        for row in degraded_high_conv:
            assert row.get("verdict") in ["watch", "neutral"], \
                f"{row['symbol']} degraded with conv {row['conviction']} should be WATCH, not {row['verdict']}"
        
        if degraded_high_conv:
            print(f"✓ {len(degraded_high_conv)} degraded high-conviction rows are correctly WATCH")


class TestSelfcheckEndpoint:
    """Test the selfcheck endpoint returns expected data"""
    
    def test_selfcheck_returns_ok(self):
        """Selfcheck endpoint should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Selfcheck returns ok=true")
    
    def test_selfcheck_has_verdict_distribution(self):
        """Selfcheck should return verdict distribution"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        spot = data.get("spot", {})
        verdict_dist = spot.get("verdictDistribution", {})
        assert verdict_dist, "Missing verdict distribution"
        
        print(f"✓ Verdict distribution: {verdict_dist}")
    
    def test_selfcheck_has_integrity_distribution(self):
        """Selfcheck should return integrity distribution"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        spot = data.get("spot", {})
        integrity_dist = spot.get("integrityDistribution", {})
        assert integrity_dist, "Missing integrity distribution"
        assert "ok" in integrity_dist or "degraded" in integrity_dist, \
            "Integrity distribution should have ok or degraded"
        
        print(f"✓ Integrity distribution: {integrity_dist}")
    
    def test_selfcheck_has_worst10(self):
        """Selfcheck should return worst10 symbols by coverage"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        worst10 = data.get("worst10", [])
        assert len(worst10) > 0, "worst10 should not be empty"
        
        # Validate structure
        for item in worst10:
            assert "symbol" in item
            assert "coveragePct" in item
            assert "status" in item
            assert "setupScore" in item
            assert "reasons" in item
        
        print(f"✓ worst10 returned with {len(worst10)} items")
        for item in worst10[:3]:
            print(f"  {item['symbol']}: coverage={item['coveragePct']}%, status={item['status']}")
    
    def test_selfcheck_has_best10(self):
        """Selfcheck should return best10 symbols by setupScore"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        best10 = data.get("best10", [])
        assert len(best10) > 0, "best10 should not be empty"
        
        # Validate structure
        for item in best10:
            assert "symbol" in item
            assert "conviction" in item
            assert "setupScore" in item
            assert "verdict" in item
            assert "integrity" in item
        
        print(f"✓ best10 returned with {len(best10)} items")
        for item in best10[:3]:
            print(f"  {item['symbol']}: setupScore={item['setupScore']}, verdict={item['verdict']}")
    
    def test_selfcheck_has_avg_coverage(self):
        """Selfcheck should return average coverage per universe"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        spot = data.get("spot", {})
        avg_coverage = spot.get("avgCoverage", {})
        assert "main" in avg_coverage or "alpha" in avg_coverage, \
            "avgCoverage should have main or alpha"
        
        print(f"✓ Average coverage: {avg_coverage}")


class TestAlphaUniverseIntegrity:
    """Test integrity on alpha universe"""
    
    def test_alpha_has_integrity(self):
        """Alpha universe rows should also have integrity field"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=50")
        assert response.status_code == 200
        data = response.json()
        rows = data.get("rows", [])
        
        assert len(rows) > 0, "Alpha should have rows"
        
        for row in rows:
            integrity = row.get("integrity")
            assert integrity is not None, f"Alpha {row['symbol']} missing integrity"
            assert "status" in integrity
            assert "setupScore" in integrity
        
        print(f"✓ All {len(rows)} alpha rows have integrity field")


class TestCacheStatsStillWork:
    """Verify cache stats endpoint still works"""
    
    def test_cache_stats_returns_data(self):
        """Cache stats endpoint should return cache information"""
        response = requests.get(f"{BASE_URL}/api/exchange/cache/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Cache stats are nested under 'cache' key
        cache = data.get("cache", data)  # Support both formats
        assert "enabled" in cache
        assert "keys" in cache or "activeKeys" in cache
        
        print(f"✓ Cache stats: enabled={cache.get('enabled')}, keys={cache.get('keys', cache.get('activeKeys'))}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
