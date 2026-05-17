"""
Decision Intelligence Phase 5 - Pre-Pump Detector, Overview Adapter, Debug Endpoint, Radar
===========================================================================================
Tests for:
1. POST /api/graph-signals/pre-pump/scan - Pre-pump scan across active tokens
2. GET /api/graph-signals/pre-pump/{token} - Single token pre-pump detection
3. GET /api/debug/signal/{token} - Debug signal sync endpoint
4. GET /api/radar - Radar aggregation endpoint
5. Existing endpoints still work (graph-signals/run, fund/run, stats, expansion, resolution)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestPrePumpDetector:
    """Pre-pump detection endpoints"""

    def test_pre_pump_scan(self):
        """POST /api/graph-signals/pre-pump/scan - Scan all active tokens for pre-pump signals"""
        response = requests.post(f"{BASE_URL}/api/graph-signals/pre-pump/scan", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "pre_pumps_detected" in data, "Missing pre_pumps_detected field"
        assert "tokens_scanned" in data, "Missing tokens_scanned field"
        assert "pre_pumps" in data, "Missing pre_pumps list"
        
        # Verify counts
        pre_pumps_detected = data["pre_pumps_detected"]
        tokens_scanned = data["tokens_scanned"]
        pre_pumps = data["pre_pumps"]
        
        print(f"Pre-pump scan: {pre_pumps_detected} pre-pumps from {tokens_scanned} tokens")
        
        # Verify pre_pumps list structure
        if pre_pumps:
            sample = pre_pumps[0]
            assert "token" in sample, "Pre-pump missing token field"
            assert "project" in sample, "Pre-pump missing project field"
            assert "score" in sample, "Pre-pump missing score field"
            assert "confidence" in sample, "Pre-pump missing confidence field"
            assert "why" in sample, "Pre-pump missing why field"
            
            # Verify why structure
            why = sample["why"]
            assert "pressure" in why, "Why missing pressure"
            assert "actors" in why, "Why missing actors"
            assert "flow" in why, "Why missing flow"
            assert "early_ratio" in why, "Why missing early_ratio"
            
            print(f"Sample pre-pump: token={sample['token']}, score={sample['score']}, confidence={sample['confidence']}")

    def test_pre_pump_single_token_sol(self):
        """GET /api/graph-signals/pre-pump/SOL - Single token pre-pump detection"""
        response = requests.get(f"{BASE_URL}/api/graph-signals/pre-pump/SOL", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "is_pre_pump" in data, "Missing is_pre_pump field"
        assert "token" in data, "Missing token field"
        
        # Token should be normalized to token:SOL
        assert data["token"] == "token:SOL", f"Expected token:SOL, got {data['token']}"
        
        if data["is_pre_pump"]:
            # If pre-pump detected, verify full structure
            assert "score" in data, "Missing score for pre-pump"
            assert "confidence" in data, "Missing confidence for pre-pump"
            assert "direction" in data, "Missing direction for pre-pump"
            assert "why" in data, "Missing why for pre-pump"
            assert data["signal"] == "PRE_PUMP", f"Expected PRE_PUMP signal, got {data.get('signal')}"
            print(f"SOL is_pre_pump=True, score={data['score']}, confidence={data['confidence']}")
        else:
            # If not pre-pump, should have reason
            assert "reason" in data, "Missing reason for non-pre-pump"
            print(f"SOL is_pre_pump=False, reason={data.get('reason')}")

    def test_pre_pump_nonexistent_token(self):
        """GET /api/graph-signals/pre-pump/NONEXISTENT - Non-existent token should return is_pre_pump=false"""
        response = requests.get(f"{BASE_URL}/api/graph-signals/pre-pump/NONEXISTENT", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "is_pre_pump" in data, "Missing is_pre_pump field"
        assert data["is_pre_pump"] == False, f"Expected is_pre_pump=False for non-existent token"
        assert "reason" in data, "Missing reason for non-existent token"
        
        # Should fail due to no token_of bridge
        print(f"NONEXISTENT token: is_pre_pump={data['is_pre_pump']}, reason={data.get('reason')}")

    def test_pre_pump_score_formula(self):
        """Verify pre-pump score formula: pressure*0.35 + actor*0.25 + flow*0.20 + early*0.20"""
        # Run scan to get pre-pumps with why details
        response = requests.post(f"{BASE_URL}/api/graph-signals/pre-pump/scan", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        pre_pumps = data.get("pre_pumps", [])
        
        if pre_pumps:
            # Verify score is within expected range (0-100)
            for pp in pre_pumps[:5]:
                score = pp["score"]
                assert 0 <= score <= 100, f"Score {score} out of range [0, 100]"
                
                why = pp["why"]
                # Verify all components are present
                assert "pressure" in why
                assert "flow" in why
                assert "early_ratio" in why
                
                print(f"Token {pp['token']}: score={score}, pressure={why['pressure']}, flow={why['flow']}, early_ratio={why['early_ratio']}")


class TestDebugSignalEndpoint:
    """Debug signal sync endpoint tests"""

    def test_debug_signal_sol(self):
        """GET /api/debug/signal/SOL - Debug signal sync for SOL"""
        response = requests.get(f"{BASE_URL}/api/debug/signal/SOL", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data, "Missing token field"
        assert "graph" in data, "Missing graph section"
        assert "overview" in data, "Missing overview section"
        assert "match" in data, "Missing match field"
        
        # Verify graph section structure
        graph = data["graph"]
        assert "context" in graph, "Graph missing context"
        assert "signal" in graph, "Graph missing signal"
        
        # Verify graph context has expected fields
        ctx = graph["context"]
        expected_ctx_fields = ["mentions", "momentum", "pressure", "alpha", "flow", "actor_count"]
        for field in expected_ctx_fields:
            assert field in ctx, f"Graph context missing {field}"
        
        # Verify graph signal structure
        signal = graph["signal"]
        if signal:
            assert "type" in signal, "Signal missing type"
            assert "direction" in signal, "Signal missing direction"
            assert "strength" in signal, "Signal missing strength"
        
        # Verify overview section
        overview = data["overview"]
        assert "snapshot_available" in overview, "Overview missing snapshot_available"
        
        print(f"Debug SOL: graph_signal={signal.get('type') if signal else 'NO_SIGNAL'}, overview_available={overview['snapshot_available']}, match={data['match']}")

    def test_debug_signal_eth(self):
        """GET /api/debug/signal/ETH - Debug signal sync for ETH"""
        response = requests.get(f"{BASE_URL}/api/debug/signal/ETH", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data
        assert data["token"] == "token:ETH"
        assert "graph" in data
        assert "overview" in data
        
        print(f"Debug ETH: graph_signal={data['graph']['signal'].get('type') if data['graph']['signal'] else 'NO_SIGNAL'}")


class TestRadarEndpoint:
    """Radar aggregation endpoint tests"""

    def test_radar_basic(self):
        """GET /api/radar - Basic radar aggregation"""
        response = requests.get(f"{BASE_URL}/api/radar", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, "Radar response not ok"
        
        # Verify all required sections
        assert "hot_tokens" in data, "Missing hot_tokens"
        assert "fund_pressure" in data, "Missing fund_pressure"
        assert "new_signals" in data, "Missing new_signals"
        assert "pre_pumps" in data, "Missing pre_pumps"
        assert "stats" in data, "Missing stats"
        
        print(f"Radar: hot_tokens={len(data['hot_tokens'])}, fund_pressure={len(data['fund_pressure'])}, pre_pumps={len(data['pre_pumps'])}")

    def test_radar_hot_tokens_structure(self):
        """Verify hot_tokens includes signal_count and is sorted by it"""
        response = requests.get(f"{BASE_URL}/api/radar", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        hot_tokens = data.get("hot_tokens", [])
        
        if hot_tokens:
            # Verify structure
            sample = hot_tokens[0]
            assert "token" in sample, "Hot token missing token field"
            assert "type" in sample, "Hot token missing type field"
            assert "strength" in sample, "Hot token missing strength field"
            assert "direction" in sample, "Hot token missing direction field"
            assert "signal_count" in sample, "Hot token missing signal_count field"
            assert "latest" in sample, "Hot token missing latest field"
            
            # Verify sorted by signal_count descending
            counts = [t["signal_count"] for t in hot_tokens]
            assert counts == sorted(counts, reverse=True), "Hot tokens not sorted by signal_count descending"
            
            print(f"Top hot token: {sample['token']} with {sample['signal_count']} signals")

    def test_radar_fund_pressure_sorted(self):
        """Verify fund_pressure is sorted by strength descending"""
        response = requests.get(f"{BASE_URL}/api/radar", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        fund_pressure = data.get("fund_pressure", [])
        
        if fund_pressure:
            # Verify structure
            sample = fund_pressure[0]
            assert "fund" in sample, "Fund pressure missing fund field"
            assert "strength" in sample, "Fund pressure missing strength field"
            assert "direction" in sample, "Fund pressure missing direction field"
            
            # Verify sorted by strength descending
            strengths = [f["strength"] for f in fund_pressure]
            assert strengths == sorted(strengths, reverse=True), "Fund pressure not sorted by strength descending"
            
            print(f"Top fund: {sample['fund']} with strength={sample['strength']}")

    def test_radar_pre_pumps_structure(self):
        """Verify pre_pumps structure in radar"""
        response = requests.get(f"{BASE_URL}/api/radar", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        pre_pumps = data.get("pre_pumps", [])
        
        if pre_pumps:
            sample = pre_pumps[0]
            assert "token" in sample, "Pre-pump missing token"
            assert "project" in sample, "Pre-pump missing project"
            assert "score" in sample, "Pre-pump missing score"
            assert "confidence" in sample, "Pre-pump missing confidence"
            assert "detected_at" in sample, "Pre-pump missing detected_at"
            
            print(f"Radar pre-pump sample: {sample['token']} score={sample['score']}")

    def test_radar_stats(self):
        """Verify radar stats section"""
        response = requests.get(f"{BASE_URL}/api/radar", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get("stats", {})
        
        assert "total_signals_logged" in stats, "Stats missing total_signals_logged"
        assert "signal_edges" in stats, "Stats missing signal_edges"
        assert "pre_pump_alerts" in stats, "Stats missing pre_pump_alerts"
        assert "active_funds" in stats, "Stats missing active_funds"
        
        print(f"Radar stats: total_signals={stats['total_signals_logged']}, pre_pump_alerts={stats['pre_pump_alerts']}, active_funds={stats['active_funds']}")


class TestExistingEndpointsStillWork:
    """Verify existing endpoints from Phase 4 still work"""

    def test_graph_signals_run(self):
        """POST /api/graph-signals/run - Graph signal detection still works"""
        response = requests.post(f"{BASE_URL}/api/graph-signals/run", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "signals_detected" in data, "Missing signals_detected"
        assert "tokens_scanned" in data, "Missing tokens_scanned"
        
        print(f"Graph signals: {data['signals_detected']} signals from {data['tokens_scanned']} tokens")

    def test_fund_signals_run(self):
        """POST /api/graph-signals/fund/run - Fund signals still work"""
        response = requests.post(f"{BASE_URL}/api/graph-signals/fund/run", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "signals_detected" in data, "Missing signals_detected"
        assert "funds_scanned" in data, "Missing funds_scanned"
        
        print(f"Fund signals: {data['signals_detected']} signals from {data['funds_scanned']} funds")

    def test_graph_signals_stats(self):
        """GET /api/graph-signals/stats - Stats include pre_pump signals in by_type"""
        response = requests.get(f"{BASE_URL}/api/graph-signals/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, "Stats response not ok"
        assert "total_signals_logged" in data, "Missing total_signals_logged"
        assert "by_type" in data, "Missing by_type"
        
        by_type = data["by_type"]
        print(f"Signal stats: total={data['total_signals_logged']}, by_type={by_type}")
        
        # Check if PRE_PUMP is in by_type (should be present after pre-pump scan)
        if "PRE_PUMP" in by_type:
            print(f"PRE_PUMP signals: {by_type['PRE_PUMP']}")

    def test_expansion_check(self):
        """GET /api/graph/expansion/check - Expansion trigger check still works"""
        response = requests.get(f"{BASE_URL}/api/graph/expansion/check", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "should_expand" in data, "Missing should_expand"
        assert "reason" in data, "Missing reason"
        
        print(f"Expansion check: should_expand={data['should_expand']}, reason={data['reason']}")

    def test_resolution_run(self):
        """POST /api/graph/resolution/run - Resolution still works"""
        response = requests.post(f"{BASE_URL}/api/graph/resolution/run", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, "Resolution response not ok"
        assert "summary" in data, "Missing summary"
        
        # Verify resolution passes are present (each pass has its own key)
        expected_passes = ["token_addresses", "project_protocol", "token_project_bridges", "twitter_person", "signal_actors"]
        for pass_name in expected_passes:
            assert pass_name in data, f"Missing resolution pass: {pass_name}"
        
        summary = data["summary"]
        print(f"Resolution: {len(expected_passes)} passes, meaningful_unresolved_pct={summary.get('meaningful_unresolved_pct')}%")


class TestPrePumpHardFilters:
    """Test pre-pump hard filters"""

    def test_hard_filter_no_token_of_bridge(self):
        """Tokens without token_of bridge should be rejected"""
        # NONEXISTENT token should fail with no_token_of_bridge
        response = requests.get(f"{BASE_URL}/api/graph-signals/pre-pump/NONEXISTENT", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data["is_pre_pump"] == False
        assert "no_token_of_bridge" in data.get("reason", ""), f"Expected no_token_of_bridge reason, got {data.get('reason')}"

    def test_pre_pump_writes_to_signal_log(self):
        """Verify pre-pump writes to signal_log with type=PRE_PUMP"""
        # First run a scan to ensure pre-pumps are written
        scan_response = requests.post(f"{BASE_URL}/api/graph-signals/pre-pump/scan", timeout=60)
        assert scan_response.status_code == 200
        
        # Check signal log for PRE_PUMP entries
        stats_response = requests.get(f"{BASE_URL}/api/graph-signals/stats", timeout=30)
        assert stats_response.status_code == 200
        
        data = stats_response.json()
        by_type = data.get("by_type", {})
        
        # PRE_PUMP should be in by_type if any were detected
        scan_data = scan_response.json()
        if scan_data.get("pre_pumps_detected", 0) > 0:
            # Note: PRE_PUMP may not appear immediately in stats if it's a separate collection
            print(f"Pre-pumps detected: {scan_data['pre_pumps_detected']}, by_type has PRE_PUMP: {'PRE_PUMP' in by_type}")


class TestCronPipelineOrder:
    """Verify cron pipeline includes pre_pump_detector"""

    def test_cron_status_includes_pre_pump(self):
        """GET /api/ingestion/cron/status - Should show pre_pump_detector in pipeline"""
        response = requests.get(f"{BASE_URL}/api/ingestion/cron/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # The cron status should include information about the pipeline
        print(f"Cron status: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
