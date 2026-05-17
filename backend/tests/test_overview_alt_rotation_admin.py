"""
Test Overview V2.3 - Alt Rotation Panel, Rotation Index, Sector Strength, Impact % fixes, Admin Engine Config
Focus: P0-P1 tasks listed in review request
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAltRotationAPI:
    """Alt Rotation endpoint /api/overview/alt-rotation tests"""

    def test_alt_rotation_returns_ok(self):
        """Alt rotation endpoint returns ok: true"""
        res = requests.get(f"{BASE_URL}/api/overview/alt-rotation?asset=BTCUSDT&tf=1h")
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") == True

    def test_alt_rotation_has_alts_array(self):
        """Alt rotation returns alts array with 20 altcoins"""
        res = requests.get(f"{BASE_URL}/api/overview/alt-rotation?asset=BTCUSDT&tf=1h")
        data = res.json()
        assert "alts" in data
        assert isinstance(data["alts"], list)
        assert len(data["alts"]) == 20  # ALT_UNIVERSE has 20 alts

    def test_alt_rotation_alts_structure(self):
        """Each alt has required fields: symbol, name, sector, momentum, volume, flow, score, action, rank"""
        res = requests.get(f"{BASE_URL}/api/overview/alt-rotation?asset=BTCUSDT&tf=1h")
        data = res.json()
        for alt in data["alts"]:
            assert "symbol" in alt
            assert "name" in alt
            assert "sector" in alt
            assert "momentum" in alt
            assert "volume" in alt
            assert "flow" in alt
            assert "score" in alt
            assert "action" in alt
            assert "rank" in alt

    def test_alt_rotation_actions_valid(self):
        """Alt action is one of BUY/SELL/HOLD"""
        res = requests.get(f"{BASE_URL}/api/overview/alt-rotation?asset=BTCUSDT&tf=1h")
        data = res.json()
        for alt in data["alts"]:
            assert alt["action"] in ["BUY", "SELL", "HOLD"]

    def test_alt_rotation_sectors_valid(self):
        """Alt sectors are valid: L1, L2, DeFi, AI, INFRA, MEME"""
        res = requests.get(f"{BASE_URL}/api/overview/alt-rotation?asset=BTCUSDT&tf=1h")
        data = res.json()
        valid_sectors = {"L1", "L2", "DeFi", "AI", "INFRA", "MEME"}
        for alt in data["alts"]:
            assert alt["sector"] in valid_sectors

    def test_alt_rotation_ranking_sorted(self):
        """Alts are sorted by score descending (rank 1 has highest score)"""
        res = requests.get(f"{BASE_URL}/api/overview/alt-rotation?asset=BTCUSDT&tf=1h")
        data = res.json()
        alts = data["alts"]
        for i in range(len(alts) - 1):
            assert alts[i]["score"] >= alts[i + 1]["score"], f"Alt {alts[i]['symbol']} score should be >= {alts[i+1]['symbol']}"

    def test_alt_rotation_rotation_index(self):
        """Rotation Index is present and is avg of top 5 scores"""
        res = requests.get(f"{BASE_URL}/api/overview/alt-rotation?asset=BTCUSDT&tf=1h")
        data = res.json()
        assert "rotationIndex" in data
        assert isinstance(data["rotationIndex"], (int, float))
        # Verify it's approximately the avg of top 5
        top5 = data["alts"][:5]
        expected_ri = sum(a["score"] for a in top5) / 5
        assert abs(data["rotationIndex"] - expected_ri) < 0.01

    def test_alt_rotation_sector_strength(self):
        """Sector Strength map is present with all sectors"""
        res = requests.get(f"{BASE_URL}/api/overview/alt-rotation?asset=BTCUSDT&tf=1h")
        data = res.json()
        assert "sectorStrength" in data
        ss = data["sectorStrength"]
        assert isinstance(ss, dict)
        # Should have multiple sectors
        assert len(ss) >= 5

    def test_alt_rotation_meta_counts(self):
        """Meta has buyCount, sellCount, holdCount that sum to 20"""
        res = requests.get(f"{BASE_URL}/api/overview/alt-rotation?asset=BTCUSDT&tf=1h")
        data = res.json()
        assert "meta" in data
        meta = data["meta"]
        assert "count" in meta
        assert "buyCount" in meta
        assert "sellCount" in meta
        assert "holdCount" in meta
        assert meta["count"] == 20
        assert meta["buyCount"] + meta["sellCount"] + meta["holdCount"] == 20


class TestOverviewImpactPct:
    """Overview decision.reasons should have impactPct field"""

    def test_overview_reasons_have_impactPct(self):
        """Each reason has impactPct field showing percentage"""
        res = requests.get(f"{BASE_URL}/api/overview?asset=BTCUSDT&tf=1h")
        data = res.json()
        reasons = data.get("decision", {}).get("reasons", [])
        assert len(reasons) >= 3  # macro, core, signals
        for r in reasons:
            assert "impactPct" in r, f"Reason '{r.get('layer')}' missing impactPct"
            assert isinstance(r["impactPct"], (int, float))
            assert 0 <= r["impactPct"] <= 100

    def test_overview_reasons_impactPct_sums_to_100(self):
        """Sum of impactPct should be approximately 100%"""
        res = requests.get(f"{BASE_URL}/api/overview?asset=BTCUSDT&tf=1h")
        data = res.json()
        reasons = data.get("decision", {}).get("reasons", [])
        total_pct = sum(r.get("impactPct", 0) for r in reasons)
        assert 99 <= total_pct <= 101, f"Impact percentages should sum to ~100, got {total_pct}"


class TestAdminConfig:
    """Admin config endpoint /api/admin/config tests"""

    def test_admin_config_returns_ok(self):
        """Admin config endpoint returns ok: true"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") == True

    def test_admin_config_has_config_and_defaults(self):
        """Response has config and defaults objects"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        data = res.json()
        assert "config" in data
        assert "defaults" in data

    def test_admin_config_threshold_groups(self):
        """Config has all 4 threshold groups: signals, decision, macroGates, altOutlook"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        cfg = res.json().get("config", {})
        assert "signals" in cfg
        assert "decision" in cfg
        assert "macroGates" in cfg
        assert "altOutlook" in cfg

    def test_admin_config_signals_fields(self):
        """Signals group has executionThreshold, lowActivityThreshold"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        signals = res.json().get("config", {}).get("signals", {})
        assert "executionThreshold" in signals
        assert "lowActivityThreshold" in signals

    def test_admin_config_decision_fields(self):
        """Decision group has holdThreshold, edgeMin, buyThreshold"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        decision = res.json().get("config", {}).get("decision", {})
        assert "holdThreshold" in decision
        assert "edgeMin" in decision
        assert "buyThreshold" in decision

    def test_admin_config_macro_gates_fields(self):
        """MacroGates group has riskOffBlockThreshold, structuralRiskBlock, extremeFearThreshold, fearRecoveryTarget"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        mg = res.json().get("config", {}).get("macroGates", {})
        assert "riskOffBlockThreshold" in mg
        assert "structuralRiskBlock" in mg
        assert "extremeFearThreshold" in mg
        assert "fearRecoveryTarget" in mg

    def test_admin_config_frozen_status(self):
        """Config has frozen status"""
        res = requests.get(f"{BASE_URL}/api/admin/config")
        cfg = res.json().get("config", {})
        assert "frozen" in cfg
        assert isinstance(cfg["frozen"], bool)


class TestStabilityMetric:
    """Stability metric in decision - should be 1 - |directionFinal(t) - directionFinal(t-1)|"""

    def test_stability_present(self):
        """Stability object present in decision"""
        res = requests.get(f"{BASE_URL}/api/overview?asset=BTCUSDT&tf=1h")
        decision = res.json().get("decision", {})
        assert "stability" in decision
        stability = decision["stability"]
        assert "index" in stability
        assert 0 <= stability["index"] <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
