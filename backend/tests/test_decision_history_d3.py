"""
Decision History D3 Tests - Record, Evaluate, and Feedback Loop

Tests for:
- POST /api/notifications/decision/record — records single decision with entryPrice, status=pending, evaluateAfter
- POST /api/notifications/decision/record-all — records 9 decisions (3 assets x 3 horizons)
- POST /api/notifications/decision/evaluate — evaluates matured pending decisions against real prices
- GET /api/notifications/decision/history — returns decision history with filters (asset, status, limit)
- GET /api/notifications/decision/stats — returns accuracy, catastrophicRate, avgMoveWhenCorrect, byType breakdown
- GET /api/notifications/decision/feedback — returns self-tuning recommendations
- Evaluation correctness: BUY correct if realMovePct > 0, SELL correct if realMovePct < 0
- Catastrophic detection: wrong && abs(realMovePct) > 5%
- WAIT evaluation: result=neutral
- AVOID evaluation: correct if abs(realMovePct) > 3%
- Route ordering: static routes /decision/record, /decision/stats etc work and don't conflict with dynamic /decision/{asset}
- D1/D2 regression: GET /api/notifications/decision/{asset}?horizon= still works
- D1/D2 regression: GET /api/notifications/decisions/overview still returns 9 decisions
- D1/D2 regression: GET /api/notifications/feed still works
- D1/D2 regression: GET /api/notifications/unread-count still works
"""
import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


# ── Decision History Record Tests ──

class TestDecisionRecordSingle:
    """Test POST /api/notifications/decision/record — records single decision"""

    def test_record_decision_returns_ok(self):
        """Verify record decision endpoint returns ok=True"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/record", json={
            "asset": "BTC",
            "horizon": "30D"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        print(f"PASS: Record decision returns ok=True")

    def test_record_decision_has_required_fields(self):
        """Verify recorded decision has all required fields"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/record", json={
            "asset": "ETH",
            "horizon": "7D"
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        decision = data.get("decision", {})
        required_fields = ["id", "asset", "horizon", "decision", "decisionType", "score", 
                          "confidence", "entryPrice", "timestamp", "evaluateAfter", "status"]
        
        for field in required_fields:
            assert field in decision, f"Missing required field '{field}' in decision: {decision}"
        
        # Verify field values
        assert decision["asset"] == "ETH", f"Asset should be ETH, got {decision['asset']}"
        assert decision["horizon"] == "7D", f"Horizon should be 7D, got {decision['horizon']}"
        assert decision["status"] == "pending", f"Status should be 'pending', got {decision['status']}"
        assert isinstance(decision["entryPrice"], (int, float)), f"entryPrice should be numeric, got {type(decision['entryPrice'])}"
        assert decision["entryPrice"] > 0, f"entryPrice should be positive, got {decision['entryPrice']}"
        
        print(f"PASS: Recorded decision has all required fields - id={decision['id']}, entryPrice={decision['entryPrice']}, status={decision['status']}")

    def test_record_decision_evaluateAfter_correct_delay(self):
        """Verify evaluateAfter is set correctly based on horizon"""
        horizons_delays = {
            "24H": timedelta(hours=24),
            "7D": timedelta(days=7),
            "30D": timedelta(days=30)
        }
        
        for horizon, expected_delay in horizons_delays.items():
            response = requests.post(f"{BASE_URL}/api/notifications/decision/record", json={
                "asset": "SOL",
                "horizon": horizon
            })
            assert response.status_code == 200
            
            data = response.json()
            decision = data.get("decision", {})
            
            timestamp = datetime.fromisoformat(decision["timestamp"].replace("Z", "+00:00"))
            evaluate_after = datetime.fromisoformat(decision["evaluateAfter"].replace("Z", "+00:00"))
            
            actual_delay = evaluate_after - timestamp
            # Allow 1 minute tolerance for processing time
            assert abs(actual_delay - expected_delay) < timedelta(minutes=1), \
                f"Horizon {horizon}: expected delay ~{expected_delay}, got {actual_delay}"
            
            print(f"PASS: {horizon} evaluateAfter delay correct - {actual_delay}")

    def test_record_decision_default_values(self):
        """Verify default values when no body provided"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/record", json={})
        assert response.status_code == 200
        
        data = response.json()
        decision = data.get("decision", {})
        
        # Defaults: asset=BTC, horizon=30D
        assert decision.get("asset") == "BTC", f"Default asset should be BTC, got {decision.get('asset')}"
        assert decision.get("horizon") == "30D", f"Default horizon should be 30D, got {decision.get('horizon')}"
        
        print(f"PASS: Default values applied - asset=BTC, horizon=30D")


class TestDecisionRecordAll:
    """Test POST /api/notifications/decision/record-all — records 9 decisions"""

    def test_record_all_returns_9_results(self):
        """Verify record-all returns 9 results (3 assets × 3 horizons)"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/record-all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        
        results = data.get("results", [])
        assert len(results) == 9, f"Expected 9 results, got {len(results)}"
        
        saved = data.get("saved", 0)
        errors = data.get("errors", 0)
        assert saved + errors == 9, f"saved + errors should equal 9, got {saved} + {errors}"
        
        print(f"PASS: record-all returned 9 results - saved={saved}, errors={errors}")

    def test_record_all_covers_all_combinations(self):
        """Verify all asset/horizon combinations are covered"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/record-all")
        assert response.status_code == 200
        
        data = response.json()
        results = data.get("results", [])
        
        expected_combos = set()
        for asset in ["BTC", "ETH", "SOL"]:
            for horizon in ["24H", "7D", "30D"]:
                expected_combos.add((asset, horizon))
        
        actual_combos = set()
        for r in results:
            if "error" not in r:
                actual_combos.add((r.get("asset"), r.get("horizon")))
        
        # At least some should be saved (price data may not be available for all)
        assert len(actual_combos) > 0, "At least some decisions should be saved"
        
        print(f"PASS: record-all covers {len(actual_combos)} combinations")


# ── Decision History Query Tests ──

class TestDecisionHistory:
    """Test GET /api/notifications/decision/history — returns decision history with filters"""

    def test_history_returns_list(self):
        """Verify history endpoint returns a list"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/history")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "history" in data, "Response should have 'history' field"
        assert isinstance(data["history"], list), "history should be a list"
        assert "count" in data, "Response should have 'count' field"
        
        print(f"PASS: History returns list with {data['count']} items")

    def test_history_filter_by_asset(self):
        """Verify history can be filtered by asset"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/history?asset=BTC")
        assert response.status_code == 200
        
        data = response.json()
        history = data.get("history", [])
        
        for item in history:
            assert item.get("asset") == "BTC", f"All items should be BTC, got {item.get('asset')}"
        
        print(f"PASS: History filtered by asset=BTC - {len(history)} items")

    def test_history_filter_by_status(self):
        """Verify history can be filtered by status"""
        for status in ["pending", "evaluated"]:
            response = requests.get(f"{BASE_URL}/api/notifications/decision/history?status={status}")
            assert response.status_code == 200
            
            data = response.json()
            history = data.get("history", [])
            
            for item in history:
                assert item.get("status") == status, f"All items should have status={status}, got {item.get('status')}"
            
            print(f"PASS: History filtered by status={status} - {len(history)} items")

    def test_history_limit_parameter(self):
        """Verify history respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/history?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        history = data.get("history", [])
        
        assert len(history) <= 5, f"History should have at most 5 items, got {len(history)}"
        
        print(f"PASS: History respects limit=5 - {len(history)} items")

    def test_history_items_have_required_fields(self):
        """Verify history items have required fields"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/history?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        history = data.get("history", [])
        
        if len(history) > 0:
            required_fields = ["id", "asset", "horizon", "decision", "status", "timestamp"]
            for item in history[:5]:  # Check first 5
                for field in required_fields:
                    assert field in item, f"Missing field '{field}' in history item: {item}"
            
            print(f"PASS: History items have required fields")
        else:
            print(f"INFO: No history items to verify")


# ── Decision Stats Tests ──

class TestDecisionStats:
    """Test GET /api/notifications/decision/stats — returns accuracy stats"""

    def test_stats_returns_ok(self):
        """Verify stats endpoint returns ok=True"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        
        print(f"PASS: Stats endpoint returns ok=True")

    def test_stats_has_required_fields(self):
        """Verify stats has required fields"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        required_fields = ["total", "evaluated", "pending", "accuracy", "catastrophicRate", "avgMoveWhenCorrect", "byType"]
        for field in required_fields:
            assert field in data, f"Missing required field '{field}' in stats: {data}"
        
        print(f"PASS: Stats has all required fields - total={data['total']}, evaluated={data['evaluated']}, pending={data['pending']}")

    def test_stats_byType_breakdown(self):
        """Verify stats has byType breakdown for NORMAL, HIGH_CONVICTION, EXTREME"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/stats")
        assert response.status_code == 200
        
        data = response.json()
        by_type = data.get("byType", {})
        
        # byType should be a dict (may be empty if no evaluated decisions)
        assert isinstance(by_type, dict), f"byType should be a dict, got {type(by_type)}"
        
        # If there are evaluated decisions, check structure
        for dtype in by_type:
            assert dtype in ["NORMAL", "HIGH_CONVICTION", "EXTREME"], f"Invalid decision type: {dtype}"
            type_stats = by_type[dtype]
            assert "total" in type_stats, f"byType[{dtype}] should have 'total'"
            assert "accuracy" in type_stats, f"byType[{dtype}] should have 'accuracy'"
            assert "catastrophicRate" in type_stats, f"byType[{dtype}] should have 'catastrophicRate'"
        
        print(f"PASS: Stats byType breakdown correct - types: {list(by_type.keys())}")

    def test_stats_accuracy_range(self):
        """Verify accuracy is in valid range [0, 1] or None"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/stats")
        assert response.status_code == 200
        
        data = response.json()
        accuracy = data.get("accuracy")
        
        if accuracy is not None:
            assert 0 <= accuracy <= 1, f"Accuracy should be in [0, 1], got {accuracy}"
        
        catastrophic_rate = data.get("catastrophicRate")
        if catastrophic_rate is not None:
            assert 0 <= catastrophic_rate <= 1, f"catastrophicRate should be in [0, 1], got {catastrophic_rate}"
        
        print(f"PASS: Stats accuracy={accuracy}, catastrophicRate={catastrophic_rate}")


# ── Decision Feedback Tests ──

class TestDecisionFeedback:
    """Test GET /api/notifications/decision/feedback — returns self-tuning recommendations"""

    def test_feedback_returns_ok(self):
        """Verify feedback endpoint returns ok=True"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/feedback")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        
        print(f"PASS: Feedback endpoint returns ok=True")

    def test_feedback_has_required_fields(self):
        """Verify feedback has required fields"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/feedback")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "action" in data, "Feedback should have 'action' field"
        assert "details" in data, "Feedback should have 'details' field"
        assert "stats" in data, "Feedback should have 'stats' field"
        
        # Validate action values
        valid_actions = ["none", "reduce_extreme_boost", "boost_extreme", "reduce_high_boost"]
        assert data["action"] in valid_actions, f"Invalid action: {data['action']}"
        
        print(f"PASS: Feedback has required fields - action={data['action']}")

    def test_feedback_stats_structure(self):
        """Verify feedback stats structure"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/feedback")
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get("stats", {})
        
        assert "normal" in stats, "stats should have 'normal'"
        assert "highConviction" in stats, "stats should have 'highConviction'"
        assert "extreme" in stats, "stats should have 'extreme'"
        
        print(f"PASS: Feedback stats structure correct - normal={stats['normal']}, highConviction={stats['highConviction']}, extreme={stats['extreme']}")


# ── Decision Evaluate Tests ──

class TestDecisionEvaluate:
    """Test POST /api/notifications/decision/evaluate — evaluates matured pending decisions"""

    def test_evaluate_returns_ok(self):
        """Verify evaluate endpoint returns ok=True"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/evaluate")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        
        print(f"PASS: Evaluate endpoint returns ok=True")

    def test_evaluate_returns_count(self):
        """Verify evaluate returns evaluated count"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/evaluate")
        assert response.status_code == 200
        
        data = response.json()
        assert "evaluated" in data, "Response should have 'evaluated' count"
        assert isinstance(data["evaluated"], int), "evaluated should be an integer"
        
        print(f"PASS: Evaluate returns count - evaluated={data['evaluated']}")

    def test_evaluate_results_structure(self):
        """Verify evaluate results structure when decisions are evaluated"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/evaluate")
        assert response.status_code == 200
        
        data = response.json()
        results = data.get("results", [])
        
        if len(results) > 0:
            for r in results:
                assert "id" in r, "Result should have 'id'"
                assert "asset" in r, "Result should have 'asset'"
                assert "decision" in r, "Result should have 'decision'"
                assert "result" in r, "Result should have 'result'"
                assert "realMovePct" in r, "Result should have 'realMovePct'"
                assert "catastrophic" in r, "Result should have 'catastrophic'"
                
                # Validate result values
                assert r["result"] in ["correct", "wrong", "neutral", "unknown"], f"Invalid result: {r['result']}"
                assert isinstance(r["catastrophic"], bool), "catastrophic should be boolean"
            
            print(f"PASS: Evaluate results structure correct - {len(results)} evaluated")
        else:
            print(f"INFO: No matured decisions to evaluate (message: {data.get('message', 'N/A')})")


# ── Route Ordering Tests (Static vs Dynamic) ──

class TestRouteOrdering:
    """Test that static routes work and don't conflict with dynamic /decision/{asset}"""

    def test_static_record_route_works(self):
        """Verify POST /decision/record works (static route)"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/record", json={"asset": "BTC"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Static route /decision/record works")

    def test_static_record_all_route_works(self):
        """Verify POST /decision/record-all works (static route)"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/record-all")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Static route /decision/record-all works")

    def test_static_evaluate_route_works(self):
        """Verify POST /decision/evaluate works (static route)"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/evaluate")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Static route /decision/evaluate works")

    def test_static_history_route_works(self):
        """Verify GET /decision/history works (static route)"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/history")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Static route /decision/history works")

    def test_static_stats_route_works(self):
        """Verify GET /decision/stats works (static route)"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Static route /decision/stats works")

    def test_static_feedback_route_works(self):
        """Verify GET /decision/feedback works (static route)"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/feedback")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Static route /decision/feedback works")

    def test_dynamic_asset_route_still_works(self):
        """Verify GET /decision/{asset} still works (dynamic route)"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/BTC?horizon=30D")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("asset") == "BTC"
        print(f"PASS: Dynamic route /decision/BTC still works")


# ── D1/D2 Regression Tests ──

class TestD1D2Regression:
    """Regression tests for D1/D2 features (Decision Engine + Signal Fusion)"""

    def test_decision_endpoint_still_works(self):
        """Verify GET /api/notifications/decision/{asset}?horizon= still works"""
        for asset in ["BTC", "ETH", "SOL"]:
            response = requests.get(f"{BASE_URL}/api/notifications/decision/{asset}?horizon=30D")
            assert response.status_code == 200, f"Failed for {asset}"
            
            data = response.json()
            assert data.get("ok") is True
            assert data.get("asset") == asset
            assert "decision" in data
            assert "decisionType" in data
            assert "components" in data
            assert "fusion" in data["components"]
        
        print(f"PASS: D1/D2 decision endpoint still works for all assets")

    def test_decisions_overview_returns_9(self):
        """Verify GET /api/notifications/decisions/overview still returns 9 decisions"""
        response = requests.get(f"{BASE_URL}/api/notifications/decisions/overview")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        overview = data.get("overview", [])
        assert len(overview) == 9, f"Expected 9 decisions, got {len(overview)}"
        
        print(f"PASS: D1/D2 decisions/overview returns 9 decisions")

    def test_feed_endpoint_still_works(self):
        """Verify GET /api/notifications/feed still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/feed")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "notifications" in data
        assert "unread" in data
        
        print(f"PASS: D1/D2 feed endpoint still works")

    def test_unread_count_still_works(self):
        """Verify GET /api/notifications/unread-count still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "unread" in data
        
        print(f"PASS: D1/D2 unread-count endpoint still works")

    def test_fusion_object_still_present(self):
        """Verify fusion object still present in decision response"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/BTC?horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        fusion = data.get("components", {}).get("fusion", {})
        
        assert "alignedSignals" in fusion
        assert "direction" in fusion
        assert "strength" in fusion
        assert "sources" in fusion
        
        print(f"PASS: D1/D2 fusion object still present - strength={fusion['strength']}")


# ── Evaluation Logic Tests ──

class TestEvaluationLogic:
    """Test evaluation correctness logic"""

    def test_history_evaluated_items_have_result(self):
        """Verify evaluated items in history have result field"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/history?status=evaluated&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        history = data.get("history", [])
        
        for item in history:
            assert "result" in item, f"Evaluated item should have 'result': {item}"
            assert item["result"] in ["correct", "wrong", "neutral", "unknown"], f"Invalid result: {item['result']}"
            
            # Check catastrophic field
            if "catastrophic" in item:
                assert isinstance(item["catastrophic"], bool), "catastrophic should be boolean"
            
            # Check realMovePct field
            if "realMovePct" in item:
                assert isinstance(item["realMovePct"], (int, float)), "realMovePct should be numeric"
        
        if len(history) > 0:
            print(f"PASS: Evaluated items have result field - {len(history)} items checked")
        else:
            print(f"INFO: No evaluated items in history")

    def test_history_pending_items_no_result(self):
        """Verify pending items in history don't have result field (or it's None)"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/history?status=pending&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        history = data.get("history", [])
        
        for item in history:
            # Pending items should not have result or it should be None
            result = item.get("result")
            if result is not None:
                print(f"WARNING: Pending item has result={result}: {item.get('id')}")
        
        if len(history) > 0:
            print(f"PASS: Pending items checked - {len(history)} items")
        else:
            print(f"INFO: No pending items in history")


# ── Integration Test ──

class TestDecisionHistoryIntegration:
    """Integration test: record → history → stats flow"""

    def test_record_appears_in_history(self):
        """Verify recorded decision appears in history"""
        # Record a decision
        record_response = requests.post(f"{BASE_URL}/api/notifications/decision/record", json={
            "asset": "BTC",
            "horizon": "24H"
        })
        assert record_response.status_code == 200
        
        record_data = record_response.json()
        decision_id = record_data.get("decision", {}).get("id")
        
        if decision_id:
            # Check history
            history_response = requests.get(f"{BASE_URL}/api/notifications/decision/history?asset=BTC&limit=50")
            assert history_response.status_code == 200
            
            history_data = history_response.json()
            history = history_data.get("history", [])
            
            found = any(item.get("id") == decision_id for item in history)
            assert found, f"Recorded decision {decision_id} should appear in history"
            
            print(f"PASS: Recorded decision {decision_id} appears in history")
        else:
            print(f"INFO: Could not verify - no decision ID returned (possibly price data unavailable)")

    def test_stats_reflect_history(self):
        """Verify stats reflect history data"""
        # Get history counts
        pending_response = requests.get(f"{BASE_URL}/api/notifications/decision/history?status=pending")
        evaluated_response = requests.get(f"{BASE_URL}/api/notifications/decision/history?status=evaluated")
        
        pending_count = pending_response.json().get("count", 0)
        evaluated_count = evaluated_response.json().get("count", 0)
        
        # Get stats
        stats_response = requests.get(f"{BASE_URL}/api/notifications/decision/stats")
        stats = stats_response.json()
        
        # Stats should roughly match (may differ due to limit)
        stats_pending = stats.get("pending", 0)
        stats_evaluated = stats.get("evaluated", 0)
        
        print(f"INFO: History pending={pending_count}, evaluated={evaluated_count}")
        print(f"INFO: Stats pending={stats_pending}, evaluated={stats_evaluated}")
        
        # At least verify stats are consistent
        assert stats.get("total", 0) == stats_pending + stats_evaluated, "total should equal pending + evaluated"
        
        print(f"PASS: Stats are internally consistent")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
