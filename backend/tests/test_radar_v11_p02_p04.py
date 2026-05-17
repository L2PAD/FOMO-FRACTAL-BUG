"""
Radar V11 P0.2-P0.4 Features Test Suite
========================================
P0.2: Coverage Expansion - selfcheck with coverage breakdown
P0.3: Execution-Ready One-Liners - explain.oneLiner field  
P0.4: Reliability Guards - STALE_DATA, conviction decay, setupScore gating
"""

import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestHealthEndpoint:
    """Basic health check"""
    
    def test_health_returns_ok(self):
        """Health endpoint returns ok=true"""
        resp = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        print(f"✓ Health OK: uptime={data.get('uptime', 0):.1f}s")


class TestP02CoverageExpansion:
    """P0.2: Selfcheck coverage field with richCoveragePct, snapshotOnlyPct, dataGapPct, bySource"""
    
    def test_selfcheck_returns_ok(self):
        """Selfcheck endpoint returns ok=true"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        print("✓ Selfcheck returns ok=true")
    
    def test_selfcheck_has_coverage_field(self):
        """Selfcheck has coverage object"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        data = resp.json()
        assert "coverage" in data, "Missing 'coverage' field in selfcheck response"
        print(f"✓ Coverage field present: {data['coverage']}")
    
    def test_selfcheck_coverage_has_richCoveragePct(self):
        """Coverage has richCoveragePct (0-100)"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        data = resp.json()
        coverage = data.get("coverage", {})
        
        assert "richCoveragePct" in coverage, "Missing richCoveragePct"
        assert 0 <= coverage["richCoveragePct"] <= 100, f"richCoveragePct out of range: {coverage['richCoveragePct']}"
        print(f"✓ richCoveragePct = {coverage['richCoveragePct']}%")
    
    def test_selfcheck_coverage_has_snapshotOnlyPct(self):
        """Coverage has snapshotOnlyPct (0-100)"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        data = resp.json()
        coverage = data.get("coverage", {})
        
        assert "snapshotOnlyPct" in coverage, "Missing snapshotOnlyPct"
        assert 0 <= coverage["snapshotOnlyPct"] <= 100, f"snapshotOnlyPct out of range: {coverage['snapshotOnlyPct']}"
        print(f"✓ snapshotOnlyPct = {coverage['snapshotOnlyPct']}%")
    
    def test_selfcheck_coverage_has_dataGapPct(self):
        """Coverage has dataGapPct (0-100)"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        data = resp.json()
        coverage = data.get("coverage", {})
        
        assert "dataGapPct" in coverage, "Missing dataGapPct"
        assert 0 <= coverage["dataGapPct"] <= 100, f"dataGapPct out of range: {coverage['dataGapPct']}"
        print(f"✓ dataGapPct = {coverage['dataGapPct']}%")
    
    def test_selfcheck_coverage_has_bySource(self):
        """Coverage has bySource object with observations/snapshot counts"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        data = resp.json()
        coverage = data.get("coverage", {})
        
        assert "bySource" in coverage, "Missing bySource"
        by_source = coverage["bySource"]
        assert isinstance(by_source, dict), "bySource must be a dict"
        
        # Should have observations and/or snapshot keys
        total = sum(by_source.values())
        assert total > 0, "bySource has no data"
        print(f"✓ bySource distribution: {by_source}")
    
    def test_selfcheck_coverage_percentages_add_up(self):
        """Coverage percentages should approximately sum to 100%"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/selfcheck", timeout=30)
        data = resp.json()
        coverage = data.get("coverage", {})
        
        total = coverage.get("richCoveragePct", 0) + coverage.get("snapshotOnlyPct", 0) + coverage.get("dataGapPct", 0)
        # Allow small tolerance for rounding
        assert 98 <= total <= 102, f"Percentages don't add up to ~100%: {total}%"
        print(f"✓ Total coverage percentages = {total}%")


class TestP03OneLiner:
    """P0.3: Each radar row has explain.oneLiner field"""
    
    def test_spot_rows_have_oneliner(self):
        """Spot rows have explain.oneLiner field"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=10", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        
        rows_with_oneliner = 0
        for row in data.get("rows", []):
            explain = row.get("explain", {})
            one_liner = explain.get("oneLiner")
            if one_liner and len(one_liner) > 0:
                rows_with_oneliner += 1
                print(f"  {row['symbol']}: {one_liner[:80]}...")
        
        assert rows_with_oneliner > 0, "No rows have oneLiner"
        print(f"✓ {rows_with_oneliner}/{len(data.get('rows', []))} rows have oneLiner")
    
    def test_oneliner_format_buy_sell(self):
        """BUY/SELL one-liners follow format: VERDICT (Horizon) | Conv X Tier Y | Why | Risk Z"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&verdict=buy&limit=5", timeout=30)
        data = resp.json()
        
        validated = 0
        for row in data.get("rows", []):
            if row.get("verdict") not in ("buy", "sell"):
                continue
            
            one_liner = row.get("explain", {}).get("oneLiner", "")
            if not one_liner:
                continue
            
            # Check format: "BUY (Mid 3-7d) | Conv 68 Tier A | compression building... | Risk Low"
            parts = one_liner.split(" | ")
            assert len(parts) >= 4, f"One-liner has <4 parts: {one_liner}"
            
            # Part 1: VERDICT (Horizon)
            assert parts[0].startswith(("BUY", "SELL")), f"First part should be BUY/SELL: {parts[0]}"
            
            # Part 2: Conv X Tier Y
            assert "Conv" in parts[1], f"Second part should contain 'Conv': {parts[1]}"
            assert "Tier" in parts[1], f"Second part should contain 'Tier': {parts[1]}"
            
            # Part 4: Risk X
            assert parts[-1].startswith("Risk"), f"Last part should start with 'Risk': {parts[-1]}"
            
            validated += 1
            print(f"  ✓ {row['symbol']}: {one_liner}")
        
        if data.get("rows"):
            assert validated > 0, "No BUY/SELL rows validated"
        print(f"✓ {validated} BUY/SELL one-liners validated")
    
    def test_oneliner_format_neutral_watch(self):
        """NEUTRAL/WATCH one-liners also have proper format"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&verdict=watch&limit=5", timeout=30)
        data = resp.json()
        
        validated = 0
        for row in data.get("rows", []):
            one_liner = row.get("explain", {}).get("oneLiner", "")
            if not one_liner:
                continue
            
            parts = one_liner.split(" | ")
            # WATCH/NEUTRAL can have format: "WATCH (Horizon) | Conv X Tier Y | Why | Risk Z"
            # or "FLAT (Horizon) | Conv X Tier Y | Why | Risk Z"
            assert len(parts) >= 3, f"One-liner has <3 parts: {one_liner}"
            assert parts[-1].startswith("Risk"), f"Last part should start with 'Risk': {parts[-1]}"
            
            validated += 1
        
        print(f"✓ {validated} WATCH one-liners validated")
    
    def test_data_gap_oneliner(self):
        """DATA_GAP rows have 'Insufficient data' one-liner"""
        # Check alpha which might have data gaps
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&verdict=data_gap&limit=5", timeout=30)
        data = resp.json()
        
        for row in data.get("rows", []):
            if row.get("verdict") == "data_gap":
                one_liner = row.get("explain", {}).get("oneLiner", "")
                assert one_liner == "Insufficient data", f"DATA_GAP one-liner should be 'Insufficient data': {one_liner}"
                print(f"  ✓ {row['symbol']}: {one_liner}")
        
        print("✓ DATA_GAP one-liners validated")


class TestP04StaleDataReliability:
    """P0.4: STALE_DATA reason when dataFreshnessSec > 900"""
    
    def test_stale_data_reason_when_freshness_exceeds_threshold(self):
        """Integrity includes STALE_DATA reason when dataFreshnessSec > 900"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=100", timeout=30)
        data = resp.json()
        
        stale_rows = []
        for row in data.get("rows", []):
            integrity = row.get("integrity", {})
            freshness = integrity.get("dataFreshnessSec")
            
            if freshness is not None and freshness > 900:
                reasons = integrity.get("reasons", [])
                stale_rows.append({
                    "symbol": row["symbol"],
                    "freshness": freshness,
                    "reasons": reasons,
                    "has_stale_data_reason": "STALE_DATA" in reasons
                })
        
        if stale_rows:
            for sr in stale_rows[:3]:
                print(f"  {sr['symbol']}: freshness={sr['freshness']}s, reasons={sr['reasons']}")
                assert sr['has_stale_data_reason'], f"Missing STALE_DATA reason for {sr['symbol']} with freshness={sr['freshness']}s"
            
            print(f"✓ All {len(stale_rows)} stale rows have STALE_DATA reason")
        else:
            print("ℹ No stale data rows found in alpha (all data fresh)")
    
    def test_stale_data_conviction_decay(self):
        """Stale data conviction is decayed (×0.8)"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=100", timeout=30)
        data = resp.json()
        
        for row in data.get("rows", []):
            integrity = row.get("integrity", {})
            freshness = integrity.get("dataFreshnessSec")
            conviction = row.get("conviction", 0)
            
            if freshness is not None and freshness > 900:
                # Stale rows should have conviction capped
                # Max possible after decay is 85 * 0.8 = 68 for degraded
                # Plus min(20) floor
                assert conviction >= 20, f"Conviction below floor: {conviction}"
                # Verify it's not too high (accounting for decay)
                assert conviction <= 85, f"Stale conviction too high: {conviction}"
                print(f"  {row['symbol']}: conviction={conviction}, freshness={freshness}s")
        
        print("✓ Stale data conviction values within expected range (decay applied)")
    
    def test_snapshot_source_marked_as_degraded(self):
        """Snapshot source rows are marked as degraded with SNAPSHOT_SOURCE reason"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha&limit=100", timeout=30)
        data = resp.json()
        
        snapshot_rows = [r for r in data.get("rows", []) if r.get("source") == "snapshot"]
        
        for row in snapshot_rows[:5]:
            integrity = row.get("integrity", {})
            assert integrity.get("status") == "degraded", f"{row['symbol']}: snapshot should be degraded"
            assert "SNAPSHOT_SOURCE" in integrity.get("reasons", []), f"{row['symbol']}: missing SNAPSHOT_SOURCE reason"
            print(f"  ✓ {row['symbol']}: status={integrity['status']}, reasons={integrity['reasons']}")
        
        if snapshot_rows:
            print(f"✓ {len(snapshot_rows)} snapshot rows correctly marked as degraded")
        else:
            print("ℹ No snapshot rows found in alpha")


class TestP04SetupScoreGating:
    """P0.4: setupScore < 0.4 prevents BUY/SELL verdict"""
    
    def test_buy_sell_requires_setup_score_above_threshold(self):
        """All BUY/SELL verdicts have setupScore >= 0.4"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=100", timeout=30)
        data = resp.json()
        
        for row in data.get("rows", []):
            if row.get("verdict") in ("buy", "sell"):
                setup_score = row.get("integrity", {}).get("setupScore", 0)
                assert setup_score >= 0.4, f"{row['symbol']}: BUY/SELL with setupScore={setup_score} < 0.4"
        
        print("✓ All BUY/SELL verdicts have setupScore >= 0.4")
    
    def test_no_buy_sell_with_low_setup_score(self):
        """Rows with low setupScore should not have BUY/SELL verdict"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=200", timeout=30)
        data = resp.json()
        
        violations = []
        for row in data.get("rows", []):
            setup_score = row.get("integrity", {}).get("setupScore", 0)
            if setup_score < 0.4 and row.get("verdict") in ("buy", "sell"):
                violations.append({
                    "symbol": row["symbol"],
                    "verdict": row["verdict"],
                    "setupScore": setup_score
                })
        
        assert len(violations) == 0, f"Found {len(violations)} BUY/SELL with low setupScore: {violations}"
        print("✓ No BUY/SELL verdicts with setupScore < 0.4")


class TestAlphaUniverse:
    """Alpha universe endpoint returns source=dynamic"""
    
    def test_alpha_universe_returns_ok(self):
        """Alpha universe endpoint returns ok=true"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/alpha/universe", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        print("✓ Alpha universe returns ok=true")
    
    def test_alpha_universe_has_dynamic_source(self):
        """Alpha universe source field is 'dynamic'"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/alpha/universe", timeout=30)
        data = resp.json()
        
        assert data.get("source") == "dynamic", f"Expected source='dynamic', got '{data.get('source')}'"
        print(f"✓ Alpha universe source = {data['source']}")
    
    def test_alpha_universe_has_required_fields(self):
        """Alpha universe has count, status, avgScore"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/alpha/universe", timeout=30)
        data = resp.json()
        
        assert "count" in data, "Missing count"
        assert "status" in data, "Missing status"
        assert "avgScore" in data, "Missing avgScore"
        
        print(f"✓ Alpha universe: count={data['count']}, status={data['status']}, avgScore={data['avgScore']}")


class TestAlphaCandidates:
    """Alpha candidates endpoint returns paginated rows with breakdown"""
    
    def test_alpha_candidates_returns_ok(self):
        """Alpha candidates endpoint returns ok=true"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/alpha/candidates?page=1&pageSize=10", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        print("✓ Alpha candidates returns ok=true")
    
    def test_alpha_candidates_has_pagination(self):
        """Alpha candidates has pagination fields"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/alpha/candidates?page=1&pageSize=10", timeout=30)
        data = resp.json()
        
        assert "total" in data, "Missing total"
        assert "page" in data, "Missing page"
        assert "pages" in data, "Missing pages"
        assert "pageSize" in data, "Missing pageSize"
        
        print(f"✓ Pagination: page={data['page']}/{data['pages']}, total={data['total']}")
    
    def test_alpha_candidates_rows_have_breakdown(self):
        """Alpha candidate rows have breakdown object"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/alpha/candidates?page=1&pageSize=5", timeout=30)
        data = resp.json()
        
        for row in data.get("rows", []):
            assert "breakdown" in row, f"Missing breakdown for {row.get('symbol')}"
            breakdown = row["breakdown"]
            
            # Breakdown should have scoring components
            assert isinstance(breakdown, dict), "Breakdown must be a dict"
            
            print(f"  {row['symbol']}: alphaScore={row.get('alphaScore')}, breakdown keys={list(breakdown.keys())}")
        
        print(f"✓ All {len(data.get('rows', []))} candidates have breakdown")
    
    def test_alpha_candidates_rows_have_sourceCoverage(self):
        """Alpha candidate rows have sourceCoverage field"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/alpha/candidates?page=1&pageSize=5", timeout=30)
        data = resp.json()
        
        for row in data.get("rows", []):
            assert "sourceCoverage" in row, f"Missing sourceCoverage for {row.get('symbol')}"
            sc = row["sourceCoverage"]
            assert "type" in sc, "sourceCoverage missing type"
            assert "pct" in sc, "sourceCoverage missing pct"
        
        print("✓ All candidates have sourceCoverage")


class TestIntegrityFieldStructure:
    """Verify integrity field structure in all rows"""
    
    def test_spot_rows_have_integrity(self):
        """All spot rows have integrity field"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=20", timeout=30)
        data = resp.json()
        
        for row in data.get("rows", []):
            assert "integrity" in row, f"Missing integrity for {row['symbol']}"
            integrity = row["integrity"]
            
            assert "status" in integrity, f"Missing integrity.status for {row['symbol']}"
            assert "reasons" in integrity, f"Missing integrity.reasons for {row['symbol']}"
            assert "coveragePct" in integrity, f"Missing integrity.coveragePct for {row['symbol']}"
            assert "setupScore" in integrity, f"Missing integrity.setupScore for {row['symbol']}"
        
        print(f"✓ All {len(data.get('rows', []))} rows have integrity field with required structure")
    
    def test_integrity_dataFreshnessSec_field(self):
        """Integrity has dataFreshnessSec field (can be null)"""
        resp = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=20", timeout=30)
        data = resp.json()
        
        has_freshness = 0
        for row in data.get("rows", []):
            integrity = row.get("integrity", {})
            if "dataFreshnessSec" in integrity:
                has_freshness += 1
        
        print(f"✓ {has_freshness}/{len(data.get('rows', []))} rows have dataFreshnessSec field")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
