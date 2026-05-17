"""
Overview V2.3 Intelligence Page — Backend API Tests

Tests for:
- GET /api/overview with V2.3 fields (directionFinal in decision)
- GET /api/overview/history (series, events, stats)
- GET /api/labs/drilldown (state, risk, explain)
- GET /api/admin/config
- PATCH /api/admin/config
- POST /api/admin/freeze
- POST /api/admin/unfreeze
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestOverviewV23API:
    """V2.3 Overview endpoint tests including new directionFinal field"""
    
    def test_overview_returns_ok(self):
        """Basic overview endpoint returns OK"""
        res = requests.get(f"{BASE_URL}/api/overview?asset=BTCUSDT")
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        print(f"Overview OK: {data.get('asset')}, action={data.get('decision', {}).get('action')}")
    
    def test_overview_decision_has_directionFinal(self):
        """V2.3: decision object must have directionFinal for strength gauge"""
        res = requests.get(f"{BASE_URL}/api/overview?asset=BTCUSDT")
        assert res.status_code == 200
        data = res.json()
        decision = data.get("decision", {})
        assert "directionFinal" in decision, "directionFinal field missing from decision"
        df = decision["directionFinal"]
        assert isinstance(df, (int, float)), f"directionFinal should be numeric, got {type(df)}"
        assert -1.5 <= df <= 1.5, f"directionFinal={df} out of expected range [-1.5, 1.5]"
        print(f"directionFinal = {df}")
    
    def test_overview_decision_standard_fields(self):
        """Standard V2.2 decision fields still present"""
        res = requests.get(f"{BASE_URL}/api/overview?asset=BTCUSDT")
        data = res.json()
        decision = data.get("decision", {})
        required_fields = ["action", "sizeMult", "mode", "confidence", "gates", "reasons",
                          "sizeBreakdown", "allocation", "flipTriggers", "trace", "stability"]
        for field in required_fields:
            assert field in decision, f"Missing decision field: {field}"
        print(f"All standard fields present: {list(decision.keys())}")
    
    def test_overview_altOutlook_has_phase(self):
        """V2.3: altOutlook must have phase field (ACCELERATION/NEUTRAL/COMPRESSION)"""
        res = requests.get(f"{BASE_URL}/api/overview?asset=BTCUSDT")
        data = res.json()
        alt = data.get("altOutlook", {})
        assert "phase" in alt, "altOutlook missing phase field"
        phase = alt["phase"]
        assert phase in ["ACCELERATION", "NEUTRAL", "COMPRESSION"], f"Invalid phase: {phase}"
        print(f"Alt phase: {phase}, status: {alt.get('status')}, score: {alt.get('score')}")


class TestPositionHistoryAPI:
    """P1: Position History Panel API tests"""
    
    def test_history_endpoint_returns_structure(self):
        """GET /api/overview/history returns required structure"""
        res = requests.get(f"{BASE_URL}/api/overview/history?asset=BTCUSDT&range=30d")
        assert res.status_code == 200
        data = res.json()
        # Required top-level keys
        assert "series" in data, "Missing series array"
        assert "events" in data, "Missing events array"
        assert "stats" in data, "Missing stats object"
        assert "range" in data, "Missing range field"
        print(f"History: range={data['range']}, totalPoints={data.get('stats',{}).get('totalPoints', 0)}")
    
    def test_history_stats_fields(self):
        """stats object has flipCount, avgSize, avgStability, blockedPct, totalPoints"""
        res = requests.get(f"{BASE_URL}/api/overview/history?asset=BTCUSDT&range=30d")
        data = res.json()
        stats = data.get("stats", {})
        required = ["flipCount", "avgSize", "avgStability", "blockedPct", "totalPoints"]
        for field in required:
            assert field in stats, f"Missing stats field: {field}"
        print(f"Stats: flips={stats['flipCount']}, avgSize={stats['avgSize']}, stability={stats['avgStability']}, blocked={stats['blockedPct']}, total={stats['totalPoints']}")
    
    def test_history_series_item_structure(self):
        """If series has items, verify rich snapshot structure"""
        res = requests.get(f"{BASE_URL}/api/overview/history?asset=BTCUSDT&range=30d")
        data = res.json()
        series = data.get("series", [])
        if len(series) > 0:
            item = series[-1]  # Most recent
            required = ["ts", "sizeMult", "directionFinal", "macroMult", "totalRisk", 
                       "action", "mode", "confidence", "edge", "gates"]
            for field in required:
                assert field in item, f"Series item missing field: {field}"
            print(f"Latest series item: action={item['action']}, sizeMult={item['sizeMult']}, ts={item['ts']}")
        else:
            print("No series data yet (position history accumulates over time)")
    
    def test_history_range_options(self):
        """Test different range parameters: 6h, 24h, 7d, 30d"""
        for r in ["6h", "24h", "7d", "30d"]:
            res = requests.get(f"{BASE_URL}/api/overview/history?asset=BTCUSDT&range={r}")
            assert res.status_code == 200
            data = res.json()
            assert data["range"] == r
            print(f"Range {r}: {data['stats']['totalPoints']} points")


class TestLabsDrilldownAPI:
    """P2: Labs Drilldown Drawer API tests"""
    
    def test_labs_drilldown_returns_structure(self):
        """GET /api/labs/drilldown returns state, risk, explain"""
        res = requests.get(f"{BASE_URL}/api/labs/drilldown?asset=BTCUSDT")
        assert res.status_code == 200
        data = res.json()
        assert "state" in data, "Missing state section"
        assert "risk" in data, "Missing risk section"
        assert "explain" in data, "Missing explain section"
        print("Labs drilldown has: state, risk, explain")
    
    def test_labs_state_regimeProbs(self):
        """state.regimeProbs is array with current flag"""
        res = requests.get(f"{BASE_URL}/api/labs/drilldown?asset=BTCUSDT")
        data = res.json()
        state = data.get("state", {})
        probs = state.get("regimeProbs", [])
        assert isinstance(probs, list), "regimeProbs should be array"
        if len(probs) > 0:
            item = probs[0]
            assert "id" in item, "regimeProbs item missing id"
            assert "p" in item, "regimeProbs item missing p (probability)"
            assert "current" in item, "regimeProbs item missing current flag"
            # Find current regime
            current_regimes = [r for r in probs if r.get("current")]
            print(f"Current regime: {current_regimes[0]['id'] if current_regimes else 'none'}")
        print(f"Regime probabilities: {len(probs)} entries")
    
    def test_labs_state_transitions(self):
        """state.transitions array"""
        res = requests.get(f"{BASE_URL}/api/labs/drilldown?asset=BTCUSDT")
        data = res.json()
        state = data.get("state", {})
        trans = state.get("transitions", [])
        assert isinstance(trans, list), "transitions should be array"
        if len(trans) > 0:
            t = trans[0]
            assert "to" in t, "transition missing 'to' field"
            assert "p" in t, "transition missing probability"
        print(f"Transitions: {len(trans)} entries")
    
    def test_labs_state_transitionMeta(self):
        """state.transitionMeta has inertia, cpiDrift, riskOffMom"""
        res = requests.get(f"{BASE_URL}/api/labs/drilldown?asset=BTCUSDT")
        data = res.json()
        meta = data.get("state", {}).get("transitionMeta", {})
        assert "inertia" in meta, "transitionMeta missing inertia"
        assert "cpiDrift" in meta, "transitionMeta missing cpiDrift"
        assert "riskOffMom" in meta, "transitionMeta missing riskOffMom"
        print(f"TransitionMeta: inertia={meta['inertia']}, cpiDrift={meta['cpiDrift']}, riskOffMom={meta['riskOffMom']}")
    
    def test_labs_risk_split(self):
        """risk.split has macro, core, signals"""
        res = requests.get(f"{BASE_URL}/api/labs/drilldown?asset=BTCUSDT")
        data = res.json()
        split = data.get("risk", {}).get("split", {})
        assert "macro" in split, "risk.split missing macro"
        assert "core" in split, "risk.split missing core"
        assert "signals" in split, "risk.split missing signals"
        total = split.get("macro", 0) + split.get("core", 0) + split.get("signals", 0)
        assert 0.95 <= total <= 1.05, f"Risk split should sum to ~1.0, got {total}"
        print(f"Risk split: macro={split['macro']:.2%}, core={split['core']:.2%}, signals={split['signals']:.2%}")
    
    def test_labs_risk_drivers(self):
        """risk.drivers is array with key, label, value, sign, conf"""
        res = requests.get(f"{BASE_URL}/api/labs/drilldown?asset=BTCUSDT")
        data = res.json()
        drivers = data.get("risk", {}).get("drivers", [])
        assert isinstance(drivers, list), "risk.drivers should be array"
        if len(drivers) > 0:
            d = drivers[0]
            for field in ["key", "label", "value", "sign", "conf"]:
                assert field in d, f"risk.driver missing field: {field}"
            print(f"Top risk driver: {d['label']} ({d['sign']}{d['value']:.3f}, conf={d['conf']:.0%})")
        print(f"Risk drivers: {len(drivers)} entries")
    
    def test_labs_explain_bullets_and_narrative(self):
        """explain has bullets array and narrative string"""
        res = requests.get(f"{BASE_URL}/api/labs/drilldown?asset=BTCUSDT")
        data = res.json()
        explain = data.get("explain", {})
        assert "bullets" in explain, "explain missing bullets"
        assert "narrative" in explain, "explain missing narrative"
        bullets = explain["bullets"]
        narrative = explain["narrative"]
        assert isinstance(bullets, list), "bullets should be array"
        assert isinstance(narrative, str), "narrative should be string"
        print(f"Bullets: {len(bullets)}, narrative: '{narrative[:60]}...'")


class TestAdminConfigAPI:
    """P3: Admin UI API tests"""
    
    def test_admin_config_get_structure(self):
        """GET /api/admin/config returns config and defaults"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        assert "config" in data, "Missing config object"
        assert "defaults" in data, "Missing defaults object"
        print(f"Admin config loaded: profile={data['config'].get('profile')}")
    
    def test_admin_config_threshold_groups(self):
        """config has signals, decision, macroGates, altOutlook groups"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        data = res.json()
        config = data.get("config", {})
        required_groups = ["signals", "decision", "macroGates", "altOutlook"]
        for grp in required_groups:
            assert grp in config, f"Config missing group: {grp}"
        print(f"Config groups: {list(config.keys())}")
    
    def test_admin_config_signals_fields(self):
        """signals group has executionThreshold, lowActivityThreshold"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        config = res.json().get("config", {}).get("signals", {})
        assert "executionThreshold" in config
        assert "lowActivityThreshold" in config
        print(f"Signals: execThreshold={config['executionThreshold']}, lowActivity={config['lowActivityThreshold']}")
    
    def test_admin_config_decision_fields(self):
        """decision group has holdThreshold, edgeMin, buyThreshold"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        config = res.json().get("config", {}).get("decision", {})
        assert "holdThreshold" in config
        assert "edgeMin" in config
        assert "buyThreshold" in config
        print(f"Decision: hold={config['holdThreshold']}, edgeMin={config['edgeMin']}, buy={config['buyThreshold']}")
    
    def test_admin_config_macroGates_fields(self):
        """macroGates has riskOffBlockThreshold, structuralRiskBlock, extremeFearThreshold, fearRecoveryTarget"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        config = res.json().get("config", {}).get("macroGates", {})
        required = ["riskOffBlockThreshold", "structuralRiskBlock", "extremeFearThreshold", "fearRecoveryTarget"]
        for field in required:
            assert field in config, f"macroGates missing: {field}"
        print(f"MacroGates: riskOff={config['riskOffBlockThreshold']}, structural={config['structuralRiskBlock']}, fear={config['extremeFearThreshold']}")
    
    def test_admin_config_frozen_status(self):
        """config has frozen boolean status"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        config = res.json().get("config", {})
        assert "frozen" in config
        assert isinstance(config["frozen"], bool)
        print(f"Frozen status: {config['frozen']}")
    
    def test_admin_config_patch(self):
        """PATCH /api/admin/config updates and returns updated config"""
        # Get original value
        orig = requests.get(f"{BASE_URL}/api/admin/config").json().get("config", {})
        orig_threshold = orig.get("signals", {}).get("executionThreshold", 0.45)
        
        # Patch with new value
        new_val = 0.48 if orig_threshold != 0.48 else 0.47
        res = requests.patch(f"{BASE_URL}/api/admin/config", json={"signals": {"executionThreshold": new_val}})
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        updated_val = data.get("config", {}).get("signals", {}).get("executionThreshold")
        assert abs(updated_val - new_val) < 0.001, f"Expected {new_val}, got {updated_val}"
        print(f"Patched executionThreshold: {orig_threshold} -> {updated_val}")
        
        # Restore original
        requests.patch(f"{BASE_URL}/api/admin/config", json={"signals": {"executionThreshold": orig_threshold}})


class TestAdminFreezeAPI:
    """Admin freeze/unfreeze functionality"""
    
    def test_admin_freeze_sets_frozen(self):
        """POST /api/admin/freeze sets frozen=true"""
        res = requests.post(f"{BASE_URL}/api/admin/freeze", json={"reason": "pytest test"})
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        assert data.get("frozen") is True
        print(f"Freeze response: frozen={data['frozen']}, reason={data.get('reason')}")
        
        # Verify in config
        cfg = requests.get(f"{BASE_URL}/api/admin/config").json().get("config", {})
        assert cfg.get("frozen") is True
        assert cfg.get("frozenReason") == "pytest test"
    
    def test_admin_unfreeze_clears_frozen(self):
        """POST /api/admin/unfreeze sets frozen=false"""
        # First freeze
        requests.post(f"{BASE_URL}/api/admin/freeze", json={"reason": "test"})
        
        # Then unfreeze
        res = requests.post(f"{BASE_URL}/api/admin/unfreeze")
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        assert data.get("frozen") is False
        print(f"Unfreeze response: frozen={data['frozen']}")
        
        # Verify in config
        cfg = requests.get(f"{BASE_URL}/api/admin/config").json().get("config", {})
        assert cfg.get("frozen") is False
        assert cfg.get("frozenReason") is None


class TestHybridSubtitle:
    """Quick fix: Hybrid panel shows 'Modifies amplitude only' subtitle"""
    
    def test_hybrid_present_in_overview(self):
        """Hybrid data is present in overview response"""
        res = requests.get(f"{BASE_URL}/api/overview?asset=BTCUSDT")
        data = res.json()
        hybrid = data.get("hybrid")
        # Hybrid may be None if no SPX data
        if hybrid:
            assert "hybridScore" in hybrid
            assert "interpretation" in hybrid
            print(f"Hybrid: score={hybrid['hybridScore']}, interp='{hybrid['interpretation']}'")
        else:
            print("Hybrid: None (no SPX data)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
