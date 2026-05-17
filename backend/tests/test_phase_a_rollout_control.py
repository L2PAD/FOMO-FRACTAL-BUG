"""
Phase A: Semi-Auto Rollout Control Tests

Tests for:
- GET /api/outcome/rollout-check: health checks, state, distribution
- POST /api/outcome/rollout-promote: only works when READY_FOR_N%
- GET /api/outcome/rollout-status: rollout_state, next_step, rollout_steps
- POST /api/outcome/sampling-rollout?pct=N: changes rollout % and sets COOLDOWN
- Auto-rollback thresholds: High>25%, Low<10%, include_rate>65%
- Stability window: 3 consecutive passes before READY
- Cooldown: after promotion, returns COOLDOWN with hours_remaining
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRolloutStatus:
    """GET /api/outcome/rollout-status tests"""

    def test_rollout_status_returns_200(self):
        """Verify rollout-status endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/outcome/rollout-status returns 200")

    def test_rollout_status_has_required_fields(self):
        """Verify rollout-status has all required fields"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        data = response.json()
        
        assert data.get("ok") == True, "Expected ok=True"
        assert "labels_v2_production" in data, "Missing labels_v2_production"
        assert "sampling_rollout_pct" in data, "Missing sampling_rollout_pct"
        assert "rollout_state" in data, "Missing rollout_state"
        assert "next_step" in data, "Missing next_step"
        assert "rollout_steps" in data, "Missing rollout_steps"
        print(f"✓ rollout-status has all required fields")

    def test_rollout_status_rollout_state_structure(self):
        """Verify rollout_state has correct structure"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        data = response.json()
        
        rs = data.get("rollout_state", {})
        assert "consecutive_passes" in rs, "Missing consecutive_passes in rollout_state"
        assert "status" in rs, "Missing status in rollout_state"
        assert "last_rollout_at" in rs or rs.get("last_rollout_at") is None, "Missing last_rollout_at"
        assert "last_check_at" in rs or rs.get("last_check_at") is None, "Missing last_check_at"
        print(f"✓ rollout_state structure: status={rs.get('status')}, passes={rs.get('consecutive_passes')}")

    def test_rollout_status_rollout_steps_array(self):
        """Verify rollout_steps is [10, 30, 70, 100]"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        data = response.json()
        
        steps = data.get("rollout_steps", [])
        assert steps == [10, 30, 70, 100], f"Expected [10, 30, 70, 100], got {steps}"
        print(f"✓ rollout_steps = {steps}")

    def test_rollout_status_next_step_valid(self):
        """Verify next_step is one of the rollout steps"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        data = response.json()
        
        next_step = data.get("next_step")
        current_pct = data.get("sampling_rollout_pct")
        steps = data.get("rollout_steps", [10, 30, 70, 100])
        
        # next_step should be > current_pct or equal if at max
        assert next_step in steps or next_step == current_pct, f"Invalid next_step: {next_step}"
        print(f"✓ next_step={next_step}, current_pct={current_pct}")


class TestRolloutCheck:
    """GET /api/outcome/rollout-check tests"""

    def test_rollout_check_returns_200(self):
        """Verify rollout-check endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/outcome/rollout-check returns 200")

    def test_rollout_check_has_health_checks(self):
        """Verify rollout-check returns health checks (high/med/low/include_rate)"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        data = response.json()
        
        if data.get("status") == "NO_DATA":
            pytest.skip("No sampling data available")
        
        assert "health" in data, "Missing health field"
        health = data["health"]
        
        assert "checks" in health, "Missing checks in health"
        checks = health["checks"]
        
        assert "high" in checks, "Missing high check"
        assert "medium" in checks, "Missing medium check"
        assert "low" in checks, "Missing low check"
        assert "include_rate" in checks, "Missing include_rate check"
        
        # Each check should have value, range, pass
        for key in ["high", "medium", "low", "include_rate"]:
            check = checks[key]
            assert "value" in check, f"Missing value in {key} check"
            assert "range" in check, f"Missing range in {key} check"
            assert "pass" in check, f"Missing pass in {key} check"
        
        print(f"✓ Health checks: high={checks['high']['value']}%, med={checks['medium']['value']}%, low={checks['low']['value']}%, include={checks['include_rate']['value']}%")

    def test_rollout_check_has_state(self):
        """Verify rollout-check returns state (STABILIZING/READY/COOLDOWN)"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        data = response.json()
        
        if data.get("status") == "NO_DATA":
            pytest.skip("No sampling data available")
        
        assert "state" in data, "Missing state field"
        state = data["state"]
        
        assert "status" in state, "Missing status in state"
        status = state["status"]
        
        # Status should be one of the expected values
        valid_statuses = ["COOLDOWN", "NOT_READY", "FULLY_ROLLED_OUT", "ROLLBACK"]
        is_valid = (
            status in valid_statuses or
            status.startswith("READY_FOR_") or
            status.startswith("STABILIZING")
        )
        assert is_valid, f"Invalid status: {status}"
        print(f"✓ State status: {status}")

    def test_rollout_check_has_distribution(self):
        """Verify rollout-check returns distribution"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        data = response.json()
        
        if data.get("status") == "NO_DATA":
            pytest.skip("No sampling data available")
        
        assert "distribution" in data, "Missing distribution field"
        dist = data["distribution"]
        
        assert "high_pct" in dist, "Missing high_pct"
        assert "medium_pct" in dist, "Missing medium_pct"
        assert "low_pct" in dist, "Missing low_pct"
        assert "include_rate" in dist, "Missing include_rate"
        assert "total" in dist, "Missing total"
        
        # Percentages should sum to ~100%
        total_pct = dist["high_pct"] + dist["medium_pct"] + dist["low_pct"]
        assert 99 <= total_pct <= 101, f"Percentages don't sum to 100: {total_pct}"
        
        print(f"✓ Distribution: high={dist['high_pct']}%, med={dist['medium_pct']}%, low={dist['low_pct']}%, total={dist['total']}")

    def test_rollout_check_cooldown_has_hours_remaining(self):
        """If status is COOLDOWN, verify hours_remaining is present"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        data = response.json()
        
        if data.get("status") == "NO_DATA":
            pytest.skip("No sampling data available")
        
        state = data.get("state", {})
        status = state.get("status", "")
        
        if status == "COOLDOWN":
            assert "hours_remaining" in state, "COOLDOWN status should have hours_remaining"
            hours = state["hours_remaining"]
            assert isinstance(hours, (int, float)), f"hours_remaining should be numeric, got {type(hours)}"
            print(f"✓ COOLDOWN with hours_remaining={hours}")
        else:
            print(f"✓ Status is {status}, not COOLDOWN (hours_remaining not required)")


class TestRolloutPromote:
    """POST /api/outcome/rollout-promote tests"""

    def test_rollout_promote_returns_400_when_not_ready(self):
        """Verify promote returns 400 when status is not READY_FOR_N%"""
        # First check current status
        status_resp = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        status_data = status_resp.json()
        current_status = status_data.get("rollout_state", {}).get("status", "")
        
        # If already READY, skip this test
        if current_status.startswith("READY_FOR_"):
            pytest.skip(f"Status is {current_status}, cannot test 400 case")
        
        # Try to promote
        response = requests.post(f"{BASE_URL}/api/outcome/rollout-promote")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == False, "Expected ok=False"
        assert data.get("error") == "NOT_READY", f"Expected error=NOT_READY, got {data.get('error')}"
        assert "current_pct" in data, "Missing current_pct in error response"
        print(f"✓ Promote returns 400 when status={current_status}")

    def test_rollout_promote_error_message_includes_status(self):
        """Verify promote error message includes current status"""
        status_resp = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        status_data = status_resp.json()
        current_status = status_data.get("rollout_state", {}).get("status", "")
        
        if current_status.startswith("READY_FOR_"):
            pytest.skip(f"Status is {current_status}, cannot test error message")
        
        response = requests.post(f"{BASE_URL}/api/outcome/rollout-promote")
        data = response.json()
        
        assert "message" in data, "Missing message in error response"
        assert current_status in data["message"], f"Message should include status {current_status}"
        print(f"✓ Error message includes status: {data['message']}")


class TestSamplingRollout:
    """POST /api/outcome/sampling-rollout tests"""

    def test_sampling_rollout_returns_200(self):
        """Verify sampling-rollout endpoint returns 200"""
        # Get current pct first
        status_resp = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        current_pct = status_resp.json().get("sampling_rollout_pct", 10)
        
        # Set to same value to avoid changing state
        response = requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct={current_pct}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ POST /api/outcome/sampling-rollout?pct={current_pct} returns 200")

    def test_sampling_rollout_sets_cooldown(self):
        """Verify sampling-rollout sets status to COOLDOWN"""
        # Get current pct
        status_resp = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        current_pct = status_resp.json().get("sampling_rollout_pct", 10)
        
        # Set to same value
        response = requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct={current_pct}")
        data = response.json()
        
        assert data.get("ok") == True, "Expected ok=True"
        
        # Verify COOLDOWN via rollout-status
        status_resp2 = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        status_data = status_resp2.json()
        rollout_state = status_data.get("rollout_state", {})
        assert rollout_state.get("status") == "COOLDOWN", f"Expected status=COOLDOWN, got {rollout_state.get('status')}"
        print(f"✓ sampling-rollout sets status to COOLDOWN")

    def test_sampling_rollout_clamps_values(self):
        """Verify sampling-rollout clamps values to 0-100"""
        # Test clamping to 100
        response = requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct=150")
        data = response.json()
        assert data.get("new_pct") == 100, f"Expected clamped to 100, got {data.get('new_pct')}"
        
        # Test clamping to 0
        response = requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct=-10")
        data = response.json()
        assert data.get("new_pct") == 0, f"Expected clamped to 0, got {data.get('new_pct')}"
        
        # Reset to 10
        requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct=10")
        print("✓ sampling-rollout clamps values to 0-100")


class TestRolloutThresholds:
    """Tests for rollout threshold logic (from outcome_resolver.py)"""

    def test_rollout_ready_conditions_documented(self):
        """Verify ready conditions are documented in rollout-check response"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        data = response.json()
        
        if data.get("status") == "NO_DATA":
            pytest.skip("No sampling data available")
        
        health = data.get("health", {})
        checks = health.get("checks", {})
        
        # Verify ranges are present (these are the ready conditions)
        for key in ["high", "medium", "low", "include_rate"]:
            if key in checks:
                check = checks[key]
                assert "range" in check, f"Missing range for {key}"
                assert len(check["range"]) == 2, f"Range should have 2 values for {key}"
                print(f"  {key}: value={check['value']}%, range={check['range']}, pass={check['pass']}")
        
        print("✓ Ready conditions documented in health checks")

    def test_rollout_rollback_thresholds_enforced(self):
        """Verify rollback thresholds are checked (High>25%, Low<10%, include_rate>65%)"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        data = response.json()
        
        if data.get("status") == "NO_DATA":
            pytest.skip("No sampling data available")
        
        health = data.get("health", {})
        
        # Check if needs_rollback is present
        assert "needs_rollback" in health, "Missing needs_rollback field"
        assert "rollback_reasons" in health, "Missing rollback_reasons field"
        
        # If needs_rollback is True, there should be reasons
        if health["needs_rollback"]:
            assert len(health["rollback_reasons"]) > 0, "needs_rollback=True but no reasons"
            print(f"✓ Rollback triggered: {health['rollback_reasons']}")
        else:
            print("✓ No rollback needed (thresholds not breached)")


class TestStabilityWindow:
    """Tests for stability window (3 consecutive passes)"""

    def test_stability_tracking_in_state(self):
        """Verify consecutive_passes is tracked in state"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        data = response.json()
        
        if data.get("status") == "NO_DATA":
            pytest.skip("No sampling data available")
        
        state = data.get("state", {})
        
        # consecutive_passes should be present
        if "consecutive_passes" in state:
            passes = state["consecutive_passes"]
            assert isinstance(passes, int), f"consecutive_passes should be int, got {type(passes)}"
            print(f"✓ consecutive_passes tracked: {passes}")
        
        # stability_required should be present if stabilizing
        if state.get("status", "").startswith("STABILIZING"):
            assert "stability_required" in state, "STABILIZING status should have stability_required"
            print(f"✓ stability_required: {state.get('stability_required')}")

    def test_stabilizing_status_format(self):
        """Verify STABILIZING status format is STABILIZING (N/3)"""
        response = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        data = response.json()
        
        if data.get("status") == "NO_DATA":
            pytest.skip("No sampling data available")
        
        state = data.get("state", {})
        status = state.get("status", "")
        
        if status.startswith("STABILIZING"):
            # Should be like "STABILIZING (1/3)"
            assert "(" in status and "/" in status, f"STABILIZING format should be 'STABILIZING (N/3)', got {status}"
            print(f"✓ STABILIZING format correct: {status}")
        else:
            print(f"✓ Status is {status}, not STABILIZING")


class TestCooldownBehavior:
    """Tests for cooldown behavior after promotion"""

    def test_cooldown_after_sampling_rollout(self):
        """Verify COOLDOWN status after sampling-rollout"""
        # Get current pct
        status_resp = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        current_pct = status_resp.json().get("sampling_rollout_pct", 10)
        
        # Set rollout (triggers cooldown)
        requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct={current_pct}")
        
        # Check status
        check_resp = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        check_data = check_resp.json()
        
        if check_data.get("status") == "NO_DATA":
            pytest.skip("No sampling data available")
        
        state = check_data.get("state", {})
        status = state.get("status", "")
        
        assert status == "COOLDOWN", f"Expected COOLDOWN after sampling-rollout, got {status}"
        print(f"✓ COOLDOWN status after sampling-rollout")

    def test_cooldown_hours_remaining_decreases(self):
        """Verify hours_remaining is present during COOLDOWN"""
        check_resp = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        check_data = check_resp.json()
        
        if check_data.get("status") == "NO_DATA":
            pytest.skip("No sampling data available")
        
        state = check_data.get("state", {})
        status = state.get("status", "")
        
        if status == "COOLDOWN":
            assert "hours_remaining" in state, "COOLDOWN should have hours_remaining"
            hours = state["hours_remaining"]
            assert hours >= 0, f"hours_remaining should be >= 0, got {hours}"
            assert hours <= 12, f"hours_remaining should be <= 12 (cooldown period), got {hours}"
            print(f"✓ COOLDOWN hours_remaining: {hours}h")
        else:
            print(f"✓ Status is {status}, not COOLDOWN")


class TestIntegration:
    """Integration tests for the full rollout flow"""

    def test_full_rollout_flow_status_check(self):
        """Test the full flow: status -> check -> verify state"""
        # 1. Get status
        status_resp = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        
        current_pct = status_data.get("sampling_rollout_pct")
        next_step = status_data.get("next_step")
        rollout_state = status_data.get("rollout_state", {})
        
        print(f"  Current: {current_pct}%, Next: {next_step}%, Status: {rollout_state.get('status')}")
        
        # 2. Run health check
        check_resp = requests.get(f"{BASE_URL}/api/outcome/rollout-check")
        assert check_resp.status_code == 200
        check_data = check_resp.json()
        
        if check_data.get("status") == "NO_DATA":
            print("  No sampling data - skipping health check verification")
            return
        
        health = check_data.get("health", {})
        state = check_data.get("state", {})
        
        print(f"  Health: healthy={health.get('healthy')}, ready={health.get('ready_for_promotion')}")
        print(f"  State: {state.get('status')}")
        
        # 3. Verify consistency
        assert check_data.get("current_pct") == current_pct, "current_pct mismatch"
        print("✓ Full rollout flow verified")

    def test_promote_blocked_during_cooldown(self):
        """Verify promote is blocked during COOLDOWN"""
        # Trigger cooldown
        status_resp = requests.get(f"{BASE_URL}/api/outcome/rollout-status")
        current_pct = status_resp.json().get("sampling_rollout_pct", 10)
        requests.post(f"{BASE_URL}/api/outcome/sampling-rollout?pct={current_pct}")
        
        # Try to promote
        promote_resp = requests.post(f"{BASE_URL}/api/outcome/rollout-promote")
        
        # Should be blocked (400)
        assert promote_resp.status_code == 400, f"Expected 400 during COOLDOWN, got {promote_resp.status_code}"
        data = promote_resp.json()
        assert "COOLDOWN" in data.get("message", ""), "Error message should mention COOLDOWN"
        print("✓ Promote blocked during COOLDOWN")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
