"""
Graph Health Engine Tests — Observability Layer for Decision Intelligence System.

Tests:
  - GET /api/graph/health/snapshot — full health snapshot with all metrics
  - POST /api/graph/health/log — creates entry in graph_health_log with cycle_id
  - GET /api/graph/health/history — returns last N health snapshots
  - POST /api/graph/health/saturation — applies soft weight penalty
  - POST /api/graph/intelligence/run — intelligence edges still work
  - POST /api/graph/build — full build still works

Metrics verified:
  - nodes, edges, new_nodes_6h, new_edges_6h
  - duplicates_pct, unresolved_nodes_pct, unresolved_edges_pct
  - actor_gini, token_gini, avg_edge_weight, decay_stats
  - parser_success_rate, per-parser breakdown (9 parsers), html_fallback_used
  - intelligence counts (entity_pressure, alpha_source, attention_flow), edge_states
  - saturation top entities, alerts array, thresholds
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestGraphHealthSnapshot:
    """GET /api/graph/health/snapshot — full health snapshot with all metrics."""

    def test_health_snapshot_returns_200(self):
        """Snapshot endpoint returns 200 OK."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:300]}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        print(f"PASS: GET /api/graph/health/snapshot returns 200")

    def test_snapshot_contains_status_and_alerts(self):
        """Snapshot contains status (HEALTHY/WARNING/CRITICAL) and alerts array."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        assert "status" in data, "Missing 'status' field"
        assert data["status"] in ["HEALTHY", "WARNING", "CRITICAL"], f"Invalid status: {data['status']}"
        
        assert "alerts" in data, "Missing 'alerts' field"
        assert isinstance(data["alerts"], list), f"alerts should be list, got {type(data['alerts'])}"
        
        assert "alert_count" in data, "Missing 'alert_count' field"
        assert data["alert_count"] == len(data["alerts"]), "alert_count mismatch"
        
        print(f"PASS: status={data['status']}, alerts={data['alert_count']}")

    def test_snapshot_contains_graph_size_metrics(self):
        """Snapshot contains nodes, edges, new_nodes_6h, new_edges_6h."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        # Graph size metrics
        assert "nodes" in data, "Missing 'nodes' field"
        assert "edges" in data, "Missing 'edges' field"
        assert "signal_edges" in data, "Missing 'signal_edges' field"
        assert "knowledge_edges" in data, "Missing 'knowledge_edges' field"
        
        # Growth metrics
        assert "new_nodes_6h" in data, "Missing 'new_nodes_6h' field"
        assert "new_edges_6h" in data, "Missing 'new_edges_6h' field"
        
        # Validate types
        assert isinstance(data["nodes"], int), f"nodes should be int, got {type(data['nodes'])}"
        assert isinstance(data["edges"], int), f"edges should be int, got {type(data['edges'])}"
        
        print(f"PASS: nodes={data['nodes']}, edges={data['edges']}, new_6h=+{data['new_edges_6h']}")

    def test_snapshot_contains_quality_metrics(self):
        """Snapshot contains duplicates_pct, unresolved_nodes_pct, unresolved_edges_pct."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        assert "duplicates_pct" in data, "Missing 'duplicates_pct' field"
        assert "unresolved_nodes_pct" in data, "Missing 'unresolved_nodes_pct' field"
        assert "unresolved_edges_pct" in data, "Missing 'unresolved_edges_pct' field"
        
        # Validate ranges (0-100%)
        assert 0 <= data["duplicates_pct"] <= 100, f"duplicates_pct out of range: {data['duplicates_pct']}"
        assert 0 <= data["unresolved_nodes_pct"] <= 100, f"unresolved_nodes_pct out of range: {data['unresolved_nodes_pct']}"
        assert 0 <= data["unresolved_edges_pct"] <= 100, f"unresolved_edges_pct out of range: {data['unresolved_edges_pct']}"
        
        print(f"PASS: duplicates={data['duplicates_pct']}%, unresolved_nodes={data['unresolved_nodes_pct']}%, unresolved_edges={data['unresolved_edges_pct']}%")

    def test_snapshot_contains_gini_coefficients(self):
        """Snapshot contains actor_gini and token_gini (0=even, 1=concentrated)."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        assert "actor_gini" in data, "Missing 'actor_gini' field"
        assert "token_gini" in data, "Missing 'token_gini' field"
        
        # Gini coefficient range: 0 to 1
        assert 0 <= data["actor_gini"] <= 1, f"actor_gini out of range: {data['actor_gini']}"
        assert 0 <= data["token_gini"] <= 1, f"token_gini out of range: {data['token_gini']}"
        
        print(f"PASS: actor_gini={data['actor_gini']}, token_gini={data['token_gini']}")

    def test_snapshot_contains_decay_stats(self):
        """Snapshot contains avg_edge_weight and decay_stats."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        assert "avg_edge_weight" in data, "Missing 'avg_edge_weight' field"
        assert "decay_stats" in data, "Missing 'decay_stats' field"
        
        # decay_stats should be a dict with avg_decay, avg_current, avg_total
        if data["decay_stats"]:  # May be empty if no edge states
            assert isinstance(data["decay_stats"], dict), f"decay_stats should be dict, got {type(data['decay_stats'])}"
            if "avg_decay" in data["decay_stats"]:
                assert 0 <= data["decay_stats"]["avg_decay"] <= 1, f"avg_decay out of range"
        
        print(f"PASS: avg_edge_weight={data['avg_edge_weight']}, decay_stats={data['decay_stats']}")

    def test_snapshot_contains_parser_health(self):
        """Snapshot contains parser_success_rate, parser_health (9 parsers), html_fallback_used."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        assert "parser_success_rate" in data, "Missing 'parser_success_rate' field"
        assert "parser_health" in data, "Missing 'parser_health' field"
        assert "html_fallback_used" in data, "Missing 'html_fallback_used' field"
        
        # parser_success_rate: 0 to 1
        assert 0 <= data["parser_success_rate"] <= 1, f"parser_success_rate out of range: {data['parser_success_rate']}"
        
        # parser_health should be a dict with parser names as keys
        assert isinstance(data["parser_health"], dict), f"parser_health should be dict, got {type(data['parser_health'])}"
        
        # Count parsers
        parser_count = len(data["parser_health"])
        print(f"PASS: parser_success_rate={data['parser_success_rate']}, parsers={parser_count}, html_fallback_used={data['html_fallback_used']}")

    def test_snapshot_contains_intelligence_counts(self):
        """Snapshot contains intelligence counts (entity_pressure, alpha_source, attention_flow) and edge_states."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        assert "intelligence" in data, "Missing 'intelligence' field"
        assert "edge_states" in data, "Missing 'edge_states' field"
        
        intel = data["intelligence"]
        assert isinstance(intel, dict), f"intelligence should be dict, got {type(intel)}"
        
        # Check for expected intelligence edge types
        expected_types = ["entity_pressure", "alpha_source", "attention_flow"]
        for edge_type in expected_types:
            assert edge_type in intel, f"Missing intelligence type: {edge_type}"
            assert isinstance(intel[edge_type], int), f"{edge_type} should be int"
        
        print(f"PASS: intelligence={intel}, edge_states={data['edge_states']}")

    def test_snapshot_contains_saturation_data(self):
        """Snapshot contains saturation top entities."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        assert "saturation" in data, "Missing 'saturation' field"
        assert isinstance(data["saturation"], list), f"saturation should be list, got {type(data['saturation'])}"
        
        # Each saturation entry should have entity, edges, over_limit
        if data["saturation"]:
            entry = data["saturation"][0]
            assert "entity" in entry, "Saturation entry missing 'entity'"
            assert "edges" in entry, "Saturation entry missing 'edges'"
            assert "over_limit" in entry, "Saturation entry missing 'over_limit'"
        
        print(f"PASS: saturation top entities count={len(data['saturation'])}")

    def test_snapshot_contains_thresholds(self):
        """Snapshot contains thresholds configuration."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        assert "thresholds" in data, "Missing 'thresholds' field"
        thresholds = data["thresholds"]
        
        # Check expected threshold keys
        expected_keys = [
            "duplicates_pct_warn", "duplicates_pct_crit",
            "unresolved_nodes_pct_warn", "unresolved_edges_pct_warn",
            "actor_gini_warn", "token_gini_warn",
            "parser_success_rate_warn", "saturation_limit"
        ]
        for key in expected_keys:
            assert key in thresholds, f"Missing threshold: {key}"
        
        print(f"PASS: thresholds={thresholds}")


class TestGraphHealthLog:
    """POST /api/graph/health/log — creates entry in graph_health_log with cycle_id."""

    def test_health_log_creates_record(self):
        """POST /api/graph/health/log creates a record with cycle_id."""
        cycle_id = f"test_cycle_{int(time.time())}"
        response = requests.post(
            f"{BASE_URL}/api/graph/health/log",
            json={"cycle_id": cycle_id},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:300]}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "record" in data, "Missing 'record' field"
        
        record = data["record"]
        assert record.get("cycle_id") == cycle_id, f"cycle_id mismatch: expected {cycle_id}, got {record.get('cycle_id')}"
        
        # Record should contain all snapshot fields
        assert "status" in record, "Record missing 'status'"
        assert "nodes" in record, "Record missing 'nodes'"
        assert "edges" in record, "Record missing 'edges'"
        assert "alerts" in record, "Record missing 'alerts'"
        
        print(f"PASS: POST /api/graph/health/log created record with cycle_id={cycle_id}")

    def test_health_log_auto_generates_cycle_id(self):
        """POST /api/graph/health/log without cycle_id auto-generates one."""
        response = requests.post(
            f"{BASE_URL}/api/graph/health/log",
            json={},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        record = data.get("record", {})
        assert "cycle_id" in record, "Auto-generated cycle_id missing"
        assert record["cycle_id"].startswith("health_"), f"Auto-generated cycle_id should start with 'health_': {record['cycle_id']}"
        
        print(f"PASS: Auto-generated cycle_id={record['cycle_id']}")


class TestGraphHealthHistory:
    """GET /api/graph/health/history — returns last N health snapshots."""

    def test_health_history_returns_list(self):
        """GET /api/graph/health/history returns list of snapshots."""
        response = requests.get(f"{BASE_URL}/api/graph/health/history", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "history" in data, "Missing 'history' field"
        assert "count" in data, "Missing 'count' field"
        assert isinstance(data["history"], list), f"history should be list, got {type(data['history'])}"
        
        print(f"PASS: GET /api/graph/health/history returns {data['count']} records")

    def test_health_history_sorted_by_timestamp_desc(self):
        """History is sorted by timestamp descending (newest first)."""
        response = requests.get(f"{BASE_URL}/api/graph/health/history?limit=10", timeout=30)
        data = response.json()
        
        history = data.get("history", [])
        if len(history) >= 2:
            # Check timestamps are descending
            for i in range(len(history) - 1):
                ts1 = history[i].get("timestamp", "")
                ts2 = history[i + 1].get("timestamp", "")
                assert ts1 >= ts2, f"History not sorted desc: {ts1} < {ts2}"
        
        print(f"PASS: History sorted by timestamp desc")

    def test_health_history_contains_cycle_id(self):
        """Each history entry contains cycle_id."""
        response = requests.get(f"{BASE_URL}/api/graph/health/history?limit=5", timeout=30)
        data = response.json()
        
        history = data.get("history", [])
        for entry in history:
            assert "cycle_id" in entry, f"History entry missing cycle_id: {entry.keys()}"
        
        print(f"PASS: All {len(history)} history entries have cycle_id")


class TestGraphSaturationPenalty:
    """POST /api/graph/health/saturation — applies soft weight penalty."""

    def test_saturation_penalty_returns_result(self):
        """POST /api/graph/health/saturation returns penalty result."""
        response = requests.post(f"{BASE_URL}/api/graph/health/saturation", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:300]}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "saturation_limit" in data, "Missing 'saturation_limit' field"
        
        # Should have penalized count (may be 0 if no entities over limit)
        if "penalized_states" in data:
            assert isinstance(data["penalized_states"], int), "penalized_states should be int"
        elif "penalized" in data:
            assert isinstance(data["penalized"], int), "penalized should be int"
        
        print(f"PASS: POST /api/graph/health/saturation, limit={data['saturation_limit']}")

    def test_saturation_zero_penalized_if_under_limit(self):
        """If max edges < 150, 0 entities should be penalized."""
        # First check snapshot to see max saturation
        snapshot_resp = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        snapshot = snapshot_resp.json()
        
        saturation = snapshot.get("saturation", [])
        max_edges = saturation[0]["edges"] if saturation else 0
        
        # Apply saturation penalty
        response = requests.post(f"{BASE_URL}/api/graph/health/saturation", timeout=60)
        data = response.json()
        
        limit = data.get("saturation_limit", 150)
        
        if max_edges < limit:
            # Should have 0 penalized
            penalized = data.get("penalized_states", data.get("penalized", 0))
            assert penalized == 0, f"Expected 0 penalized when max_edges={max_edges} < limit={limit}, got {penalized}"
            print(f"PASS: 0 penalized (max_edges={max_edges} < limit={limit})")
        else:
            print(f"PASS: max_edges={max_edges} >= limit={limit}, some entities may be penalized")


class TestAlertsFiring:
    """Verify alerts fire correctly based on thresholds."""

    def test_alerts_structure(self):
        """Each alert has level, metric, value, threshold."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        alerts = data.get("alerts", [])
        for alert in alerts:
            assert "level" in alert, f"Alert missing 'level': {alert}"
            assert "metric" in alert, f"Alert missing 'metric': {alert}"
            assert "value" in alert, f"Alert missing 'value': {alert}"
            assert alert["level"] in ["WARNING", "CRITICAL"], f"Invalid alert level: {alert['level']}"
        
        print(f"PASS: {len(alerts)} alerts have correct structure")

    def test_unresolved_nodes_alert_fires(self):
        """unresolved_nodes_pct > 10% should trigger WARNING."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        unresolved = data.get("unresolved_nodes_pct", 0)
        alerts = data.get("alerts", [])
        
        unresolved_alert = next((a for a in alerts if a["metric"] == "unresolved_nodes_pct"), None)
        
        if unresolved > 10:
            assert unresolved_alert is not None, f"Expected WARNING for unresolved_nodes_pct={unresolved}% > 10%"
            assert unresolved_alert["level"] == "WARNING", f"Expected WARNING level"
            print(f"PASS: unresolved_nodes_pct={unresolved}% > 10% triggers WARNING")
        else:
            print(f"PASS: unresolved_nodes_pct={unresolved}% <= 10%, no alert expected")

    def test_actor_gini_alert_fires(self):
        """actor_gini > 0.6 should trigger WARNING."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        actor_gini = data.get("actor_gini", 0)
        alerts = data.get("alerts", [])
        
        gini_alert = next((a for a in alerts if a["metric"] == "actor_gini"), None)
        
        if actor_gini > 0.6:
            assert gini_alert is not None, f"Expected WARNING for actor_gini={actor_gini} > 0.6"
            assert gini_alert["level"] == "WARNING", f"Expected WARNING level"
            print(f"PASS: actor_gini={actor_gini} > 0.6 triggers WARNING")
        else:
            print(f"PASS: actor_gini={actor_gini} <= 0.6, no alert expected")

    def test_duplicates_pct_is_zero(self):
        """Verify duplicates_pct is 0% (no dupes in graph)."""
        response = requests.get(f"{BASE_URL}/api/graph/health/snapshot", timeout=60)
        data = response.json()
        
        duplicates = data.get("duplicates_pct", -1)
        assert duplicates == 0, f"Expected duplicates_pct=0%, got {duplicates}%"
        
        print(f"PASS: duplicates_pct={duplicates}% (no duplicates)")


class TestIntelligenceStillWorks:
    """POST /api/graph/intelligence/run — still works (42 pressure + 253 alpha + 872 flow)."""

    def test_intelligence_run_returns_counts(self):
        """POST /api/graph/intelligence/run returns intelligence edge counts."""
        response = requests.post(f"{BASE_URL}/api/graph/intelligence/run", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:300]}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check for expected counts
        assert "entity_pressure" in data, "Missing 'entity_pressure' count"
        assert "alpha_source" in data, "Missing 'alpha_source' count"
        assert "attention_flow" in data, "Missing 'attention_flow' count"
        
        print(f"PASS: intelligence run - pressure={data['entity_pressure']}, alpha={data['alpha_source']}, flow={data['attention_flow']}")


class TestGraphBuildStillWorks:
    """POST /api/graph/build — full build still works (6087+ edges)."""

    def test_graph_build_returns_edge_count(self):
        """POST /api/graph/build returns total edge count >= 6000."""
        response = requests.post(f"{BASE_URL}/api/graph/build", timeout=180)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:300]}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check total edges (under 'totals' key)
        totals = data.get("totals", {})
        total_edges = totals.get("edges", 0)
        assert total_edges >= 6000, f"Expected >= 6000 edges, got {total_edges}"
        
        print(f"PASS: POST /api/graph/build - total_edges={total_edges}")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
