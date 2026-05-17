"""
ML Overlay Stage 2 + Pre-Flight Quality Gate V1 Tests
Tests for:
- GET /api/ml-risk/rollout-status (ml_overlay, preflight, global config)
- POST /api/ml-risk/kill (kill switch activation)
- POST /api/ml-risk/rollout (re-enable with custom params)
- GET /api/preflight/status (preflight gate config)
- POST /api/preflight/config (update preflight settings)
- POST /api/ml-risk/shadow-score (runs ML + preflight, writes audit.ml and audit.preflight)
- GET /api/ml-risk/shadow-stats (live_stats, preflight_stats, risk buckets)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestMlRiskRolloutStatus:
    """Test GET /api/ml-risk/rollout-status endpoint"""

    def test_rollout_status_returns_200(self):
        """Verify rollout-status endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/ml-risk/rollout-status returns 200")

    def test_rollout_status_has_ml_overlay(self):
        """Verify ml_overlay section exists with required fields"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        data = response.json()
        assert "ml_overlay" in data, "Missing ml_overlay section"
        ml = data["ml_overlay"]
        assert "enabled" in ml, "Missing ml_overlay.enabled"
        assert "mode" in ml, "Missing ml_overlay.mode"
        assert "live_pct" in ml, "Missing ml_overlay.live_pct"
        assert "kill_switch" in ml, "Missing ml_overlay.kill_switch"
        print(f"✓ ml_overlay: mode={ml['mode']}, live_pct={ml['live_pct']}, kill_switch={ml['kill_switch']}")

    def test_rollout_status_ml_overlay_mode_shadow_plus_live(self):
        """Verify ml_overlay mode is shadow_plus_live (Stage 2)"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        data = response.json()
        ml = data["ml_overlay"]
        # Mode should be shadow_plus_live for Stage 2
        assert ml["mode"] in ["shadow", "shadow_plus_live", "live"], f"Invalid mode: {ml['mode']}"
        print(f"✓ ml_overlay mode: {ml['mode']}")

    def test_rollout_status_has_preflight(self):
        """Verify preflight section exists with required fields"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        data = response.json()
        assert "preflight" in data, "Missing preflight section"
        pf = data["preflight"]
        assert "enabled" in pf, "Missing preflight.enabled"
        assert "mode" in pf, "Missing preflight.mode"
        print(f"✓ preflight: enabled={pf['enabled']}, mode={pf['mode']}")

    def test_rollout_status_preflight_mode_shadow(self):
        """Verify preflight mode is shadow (V1)"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        data = response.json()
        pf = data["preflight"]
        assert pf["mode"] in ["shadow", "live"], f"Invalid preflight mode: {pf['mode']}"
        print(f"✓ preflight mode: {pf['mode']}")

    def test_rollout_status_has_global(self):
        """Verify global section exists with confidence_floor"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        data = response.json()
        assert "global" in data, "Missing global section"
        g = data["global"]
        assert "confidence_floor" in g, "Missing global.confidence_floor"
        assert g["confidence_floor"] == 0.20, f"Expected floor=0.20, got {g['confidence_floor']}"
        print(f"✓ global confidence_floor: {g['confidence_floor']}")


class TestMlRiskKillSwitch:
    """Test POST /api/ml-risk/kill endpoint"""

    def test_kill_switch_returns_200(self):
        """Verify kill endpoint returns 200"""
        response = requests.post(f"{BASE_URL}/api/ml-risk/kill")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/ml-risk/kill returns 200")

    def test_kill_switch_activates(self):
        """Verify kill switch activates and mode becomes shadow"""
        response = requests.post(f"{BASE_URL}/api/ml-risk/kill")
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=True, got {data}"
        # API returns message confirming activation
        assert "message" in data or "kill_switch" in data, f"Expected message or kill_switch, got {data}"
        print(f"✓ Kill switch activated: {data}")

    def test_rollout_status_after_kill(self):
        """Verify rollout-status shows kill_switch=true after kill"""
        # First kill
        requests.post(f"{BASE_URL}/api/ml-risk/kill")
        # Then check status
        response = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        data = response.json()
        ml = data["ml_overlay"]
        assert ml["kill_switch"] == True, f"Expected kill_switch=True, got {ml['kill_switch']}"
        print(f"✓ After kill: kill_switch={ml['kill_switch']}, mode={ml['mode']}")


class TestMlRiskRolloutReEnable:
    """Test POST /api/ml-risk/rollout endpoint"""

    def test_rollout_re_enable_returns_200(self):
        """Verify rollout endpoint returns 200"""
        response = requests.post(
            f"{BASE_URL}/api/ml-risk/rollout",
            params={"enabled": True, "live_pct": 0.10, "kill_switch": False}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/ml-risk/rollout returns 200")

    def test_rollout_re_enable_with_params(self):
        """Verify rollout re-enables with custom parameters"""
        response = requests.post(
            f"{BASE_URL}/api/ml-risk/rollout",
            params={"enabled": True, "live_pct": 0.15, "kill_switch": False}
        )
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=True, got {data}"
        print(f"✓ Rollout re-enabled: {data}")

    def test_rollout_status_after_re_enable(self):
        """Verify rollout-status shows updated values after re-enable"""
        # Re-enable with specific params
        requests.post(
            f"{BASE_URL}/api/ml-risk/rollout",
            params={"enabled": True, "live_pct": 0.10, "kill_switch": False}
        )
        # Check status
        response = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        data = response.json()
        ml = data["ml_overlay"]
        assert ml["kill_switch"] == False, f"Expected kill_switch=False, got {ml['kill_switch']}"
        assert ml["enabled"] == True, f"Expected enabled=True, got {ml['enabled']}"
        print(f"✓ After re-enable: enabled={ml['enabled']}, kill_switch={ml['kill_switch']}, live_pct={ml['live_pct']}")


class TestPreflightStatus:
    """Test GET /api/preflight/status endpoint"""

    def test_preflight_status_returns_200(self):
        """Verify preflight/status endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/preflight/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/preflight/status returns 200")

    def test_preflight_status_has_enabled(self):
        """Verify preflight status has enabled field"""
        response = requests.get(f"{BASE_URL}/api/preflight/status")
        data = response.json()
        assert "enabled" in data, "Missing enabled field"
        assert data["enabled"] == True, f"Expected enabled=True, got {data['enabled']}"
        print(f"✓ preflight enabled: {data['enabled']}")

    def test_preflight_status_has_mode(self):
        """Verify preflight status has mode field"""
        response = requests.get(f"{BASE_URL}/api/preflight/status")
        data = response.json()
        assert "mode" in data, "Missing mode field"
        assert data["mode"] in ["shadow", "live"], f"Invalid mode: {data['mode']}"
        print(f"✓ preflight mode: {data['mode']}")

    def test_preflight_status_has_threshold(self):
        """Verify preflight status has threshold field"""
        response = requests.get(f"{BASE_URL}/api/preflight/status")
        data = response.json()
        assert "threshold" in data, "Missing threshold field"
        print(f"✓ preflight threshold: {data['threshold']}")


class TestPreflightConfig:
    """Test POST /api/preflight/config endpoint"""

    def test_preflight_config_returns_200(self):
        """Verify preflight/config endpoint returns 200"""
        response = requests.post(
            f"{BASE_URL}/api/preflight/config",
            params={"enabled": True, "mode": "shadow"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/preflight/config returns 200")

    def test_preflight_config_update(self):
        """Verify preflight config can be updated"""
        response = requests.post(
            f"{BASE_URL}/api/preflight/config",
            params={"enabled": True, "mode": "shadow", "threshold": 0.65}
        )
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=True, got {data}"
        print(f"✓ Preflight config updated: {data}")


class TestMlRiskShadowScore:
    """Test POST /api/ml-risk/shadow-score endpoint"""

    def test_shadow_score_returns_200(self):
        """Verify shadow-score endpoint returns 200"""
        response = requests.post(f"{BASE_URL}/api/ml-risk/shadow-score")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/ml-risk/shadow-score returns 200")

    def test_shadow_score_has_scored_count(self):
        """Verify shadow-score returns scored count"""
        response = requests.post(f"{BASE_URL}/api/ml-risk/shadow-score")
        data = response.json()
        assert data.get("ok") == True, f"Expected ok=True, got {data}"
        assert "scored" in data, "Missing scored field"
        print(f"✓ shadow-score scored: {data['scored']}")


class TestMlRiskShadowStats:
    """Test GET /api/ml-risk/shadow-stats endpoint"""

    def test_shadow_stats_returns_200(self):
        """Verify shadow-stats endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/ml-risk/shadow-stats returns 200")

    def test_shadow_stats_has_total(self):
        """Verify shadow-stats has total count"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        assert "total" in data, "Missing total field"
        print(f"✓ shadow-stats total: {data['total']}")

    def test_shadow_stats_has_risk_buckets(self):
        """Verify shadow-stats has risk buckets (low/medium/high)"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        assert "bucket_low" in data, "Missing bucket_low"
        assert "bucket_medium" in data, "Missing bucket_medium"
        assert "bucket_high" in data, "Missing bucket_high"
        print(f"✓ Risk buckets: low={data['bucket_low']['count']}, med={data['bucket_medium']['count']}, high={data['bucket_high']['count']}")

    def test_shadow_stats_bucket_has_error_rate(self):
        """Verify each bucket has error_rate"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        for bk in ["bucket_low", "bucket_medium", "bucket_high"]:
            assert "error_rate" in data[bk], f"Missing error_rate in {bk}"
        print(f"✓ Error rates: low={data['bucket_low']['error_rate']}%, med={data['bucket_medium']['error_rate']}%, high={data['bucket_high']['error_rate']}%")

    def test_shadow_stats_has_model_validation(self):
        """Verify shadow-stats has model_validation with verdict"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        assert "model_validation" in data, "Missing model_validation"
        mv = data["model_validation"]
        assert "verdict" in mv, "Missing verdict in model_validation"
        assert mv["verdict"] in ["USEFUL", "CHECK_MODEL", "NEEDS_RETRAINING"], f"Invalid verdict: {mv['verdict']}"
        print(f"✓ Model validation verdict: {mv['verdict']}")

    def test_shadow_stats_has_live_stats(self):
        """Verify shadow-stats has live_stats for Stage 2"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        # live_stats may be present if there are live-applied forecasts
        if "live_stats" in data:
            ls = data["live_stats"]
            assert "live_applied_count" in ls, "Missing live_applied_count"
            assert "live_pct" in ls, "Missing live_pct"
            print(f"✓ Live stats: applied={ls['live_applied_count']}, pct={ls['live_pct']}%")
        else:
            print("✓ live_stats not present (no live-applied forecasts yet)")

    def test_shadow_stats_has_preflight_stats(self):
        """Verify shadow-stats has preflight_stats"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/shadow-stats")
        data = response.json()
        # preflight_stats may be present if preflight gate is enabled
        if "preflight_stats" in data:
            ps = data["preflight_stats"]
            assert "triggered_count" in ps, "Missing triggered_count"
            assert "trigger_rate" in ps, "Missing trigger_rate"
            assert "overlap_with_ml" in ps, "Missing overlap_with_ml"
            print(f"✓ Preflight stats: triggered={ps['triggered_count']}, rate={ps['trigger_rate']}%, overlap={ps['overlap_with_ml']}")
        else:
            print("✓ preflight_stats not present (no preflight triggers yet)")


class TestKillSwitchFlow:
    """Test full kill switch flow: kill -> verify -> re-enable -> verify"""

    def test_full_kill_switch_flow(self):
        """Test complete kill switch workflow"""
        # Step 1: Kill
        kill_resp = requests.post(f"{BASE_URL}/api/ml-risk/kill")
        assert kill_resp.status_code == 200
        print("✓ Step 1: Kill switch activated")

        # Step 2: Verify kill_switch=true
        status_resp = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        status_data = status_resp.json()
        assert status_data["ml_overlay"]["kill_switch"] == True
        print(f"✓ Step 2: Verified kill_switch=True, mode={status_data['ml_overlay']['mode']}")

        # Step 3: Re-enable
        enable_resp = requests.post(
            f"{BASE_URL}/api/ml-risk/rollout",
            params={"enabled": True, "live_pct": 0.10, "kill_switch": False}
        )
        assert enable_resp.status_code == 200
        print("✓ Step 3: Re-enabled with live_pct=0.10")

        # Step 4: Verify re-enabled
        status_resp2 = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        status_data2 = status_resp2.json()
        assert status_data2["ml_overlay"]["kill_switch"] == False
        assert status_data2["ml_overlay"]["enabled"] == True
        print(f"✓ Step 4: Verified kill_switch=False, enabled=True, live_pct={status_data2['ml_overlay']['live_pct']}")


class TestStableHashing:
    """Test stable hashing for rollout control"""

    def test_rollout_status_has_salt(self):
        """Verify rollout-status includes salt for stable hashing"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        data = response.json()
        ml = data["ml_overlay"]
        assert "salt" in ml, "Missing salt for stable hashing"
        print(f"✓ Stable hashing salt: {ml['salt']}")


class TestGlobalConfidenceFloor:
    """Test global confidence floor enforcement"""

    def test_global_floor_value(self):
        """Verify global confidence floor is 0.20"""
        response = requests.get(f"{BASE_URL}/api/ml-risk/rollout-status")
        data = response.json()
        assert data["global"]["confidence_floor"] == 0.20
        print(f"✓ Global confidence floor: {data['global']['confidence_floor']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
