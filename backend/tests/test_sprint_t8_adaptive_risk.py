"""Sprint T8 — Adaptive Capital Restraint Layer tests.

Validates the adaptive sizing formula and integration with verdict + calibration.

Contract under test:
    size = baseSize × lifetimeWeight × regimeWeight × exposureWeight × uncertaintyPenalty

Acceptance:
  * verdict response contains a `sizing` block
  * sizeUsd is sourced from sizing.final (not from raw equity × risk_pct)
  * WAIT verdict → final = 0
  * sample-low reduces size but does NOT block the action
  * hostile-regime (calibration hard-gate) → final = 0
  * UI never receives a deployable size when adaptive layer says zero
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or os.environ.get("EXPO_BACKEND_URL")
            or "https://merge-verify-4.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json", "X-User-Id": "dev_user"})
    return sess


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


# ── Direct unit tests on adaptive_risk.compute_adaptive_sizing ────────


class TestAdaptiveFormulaUnit:
    def _base_account(self, equity=10_000.0):
        return {"accountId": "test", "balanceUsd": equity, "equityUsd": equity}

    def _wait_verdict(self):
        return {
            "symbol": "TEST", "action": "WAIT",
            "sizeUsd": None, "calibration": {"sample": 0, "winRate": None},
        }

    def _long_verdict(self, size=100.0, cal=None):
        return {
            "symbol": "TEST", "action": "LONG", "sizeUsd": size,
            "calibration": cal or {"sample": 0, "winRate": None, "recent30d": {}},
        }

    def test_wait_returns_zero(self):
        from services import adaptive_risk
        out = adaptive_risk.compute_adaptive_sizing(
            self._wait_verdict(), self._base_account(), [], 1.0
        )
        assert out["final"] == 0.0
        assert out["forcedZeroReason"] == "verdict_is_wait"
        # All scales still computed for UI
        assert "lifetimeWeight" in out
        assert "regimeWeight" in out
        assert "exposureWeight" in out
        assert "uncertaintyPenalty" in out

    def test_long_with_no_history_applies_caution_penalty(self):
        """Empty calibration → lifetime 0.75 × regime 1.0 × exposure 1.0 × penalty 0.70."""
        from services import adaptive_risk
        out = adaptive_risk.compute_adaptive_sizing(
            self._long_verdict(size=100.0),
            self._base_account(), [], 1.0,
        )
        # base 100 × 0.75 × 1.0 × 1.0 × 0.70 = 52.5
        assert out["lifetimeWeight"] == 0.75
        assert out["regimeWeight"] == 1.0
        assert out["exposureWeight"] == 1.0
        assert out["uncertaintyPenalty"] == 0.70
        assert out["final"] == 52.50
        assert out["forcedZeroReason"] is None

    def test_strong_lifetime_boosts_within_ceiling(self):
        """Strong lifetime (winRate 0.72, sample 30) × no recent → bounded boost."""
        from services import adaptive_risk
        cal = {
            "sample": 30, "winRate": 0.72,
            "recent30d": {"sample": 0, "winRate": None},
        }
        out = adaptive_risk.compute_adaptive_sizing(
            self._long_verdict(size=100.0, cal=cal),
            self._base_account(), [], 1.0,
        )
        # lifetime 1.25 × regime 1.0 × exposure 1.0 × penalty 0.85 (one sample weak)
        # = 1.0625 → final = 106.25
        assert out["lifetimeWeight"] == 1.25
        assert out["regimeWeight"] == 1.0
        assert out["uncertaintyPenalty"] == 0.85
        assert out["final"] == 106.25

    def test_book_saturated_zeroes_size(self):
        """5 open positions → openCountWeight = 0 → exposure = 0 → final = 0."""
        from services import adaptive_risk
        cal = {
            "sample": 30, "winRate": 0.72,
            "recent30d": {"sample": 30, "winRate": 0.72},
        }
        open_pos = [{"sizeUsd": 100} for _ in range(5)]
        out = adaptive_risk.compute_adaptive_sizing(
            self._long_verdict(size=100.0, cal=cal),
            self._base_account(equity=10_000.0), open_pos, 1.0,
        )
        assert out["exposureWeight"] == 0.0
        assert out["final"] == 0.0
        assert out["forcedZeroReason"] == "book_saturated"

    def test_notional_above_equity_zeroes_size(self):
        """1 huge position whose notional >= equity → notionalWeight = 0."""
        from services import adaptive_risk
        cal = {"sample": 30, "winRate": 0.72, "recent30d": {"sample": 30, "winRate": 0.72}}
        # 1 position with 10,000 notional vs 10,000 equity → ratio 1.0 → weight 0
        out = adaptive_risk.compute_adaptive_sizing(
            self._long_verdict(size=100.0, cal=cal),
            self._base_account(equity=10_000.0),
            [{"sizeUsd": 10_000.0}], 1.0,
        )
        assert out["exposureWeight"] == 0.0
        assert out["final"] == 0.0
        assert out["forcedZeroReason"] == "book_saturated"

    def test_sample_low_does_not_block_action(self):
        """Sample <5 reduces uncertaintyPenalty but action stays LONG."""
        from services import adaptive_risk
        cal = {
            "sample": 2, "winRate": 0.50,
            "recent30d": {"sample": 1, "winRate": 0.50},
        }
        out = adaptive_risk.compute_adaptive_sizing(
            self._long_verdict(size=100.0, cal=cal),
            self._base_account(), [], 1.0,
        )
        # lifetime 0.70 × regime 1.0 (sample<5) × exposure 1.0 × penalty 0.70
        # = 0.49 → final = 49.0
        assert out["lifetimeWeight"] == 0.70
        assert out["uncertaintyPenalty"] == 0.70
        assert out["final"] == 49.00
        # CRITICAL: forced_zero_reason must be None — action not blocked
        assert out["forcedZeroReason"] is None

    def test_divergence_penalty_lower_when_lifetime_regime_disagree(self):
        from services import adaptive_risk
        # Lifetime 0.65 winRate, regime 0.40 winRate, both sample 20
        cal = {
            "sample": 20, "winRate": 0.65,
            "recent30d": {"sample": 20, "winRate": 0.40},
        }
        out = adaptive_risk.compute_adaptive_sizing(
            self._long_verdict(size=100.0, cal=cal),
            self._base_account(), [], 1.0,
        )
        # Divergence = 0.25 → penalty 0.80
        assert out["uncertaintyPenalty"] == 0.80

    def test_no_structural_base_returns_zero(self):
        from services import adaptive_risk
        cal = {"sample": 30, "winRate": 0.72, "recent30d": {"sample": 30, "winRate": 0.72}}
        out = adaptive_risk.compute_adaptive_sizing(
            self._long_verdict(size=0, cal=cal),
            self._base_account(), [], 1.0,
        )
        assert out["final"] == 0.0
        assert out["forcedZeroReason"] == "no_structural_base_size"

    def test_below_min_deployable_floor(self):
        """Tiny base × heavy restraints → final < $1 → zeroed."""
        from services import adaptive_risk
        cal = {"sample": 2, "winRate": 0.5, "recent30d": {"sample": 1, "winRate": 0.5}}
        out = adaptive_risk.compute_adaptive_sizing(
            self._long_verdict(size=2.0, cal=cal),
            self._base_account(), [], 1.0,
        )
        # 2 × 0.70 × 1.0 × 1.0 × 0.70 = 0.98 → below $1 floor
        assert out["final"] == 0.0
        assert out["forcedZeroReason"] == "size_below_min_deployable"

    def test_components_block_complete(self):
        from services import adaptive_risk
        out = adaptive_risk.compute_adaptive_sizing(
            self._long_verdict(size=100.0),
            self._base_account(), [{"sizeUsd": 200}, {"sizeUsd": 300}], 1.0,
        )
        c = out["components"]
        assert c["openCount"] == 2
        assert c["openCountWeight"] == round(1.0 - 0.40, 3)
        assert c["notionalExposureUsd"] == 500.00
        assert c["notionalRatio"] == round(500.0 / 10_000.0, 3)
        assert "lifetimeSample" in c
        assert "regimeSample" in c

    def test_labels_present_for_ui(self):
        from services import adaptive_risk
        out = adaptive_risk.compute_adaptive_sizing(
            self._long_verdict(size=100.0),
            self._base_account(), [], 1.0,
        )
        labels = out["labels"]
        for k in ("lifetime", "regime", "exposure", "uncertainty"):
            assert k in labels
            assert isinstance(labels[k], str) and len(labels[k]) > 0


# ── Integration: verdict endpoint exposes sizing block ───────────────


class TestVerdictExposesSizing:
    def test_verdict_contains_sizing_block(self, s):
        r = s.get(f"{BASE_URL}/api/trading/verdict/BTC", timeout=20).json()
        assert "sizing" in r, f"verdict missing sizing block: {list(r.keys())}"
        sizing = r["sizing"]
        for k in (
            "baseRiskPct", "baseRiskUsd", "baseSize",
            "lifetimeWeight", "regimeWeight", "exposureWeight",
            "uncertaintyPenalty", "final", "components", "labels",
            "explanation", "forcedZeroReason", "version",
        ):
            assert k in sizing, f"sizing missing {k}: {list(sizing.keys())}"
        assert sizing["version"].startswith("t8.")

    def test_size_usd_equals_sizing_final_for_directional(self, s):
        # Run across watchlist to find any directional verdict
        opp = s.get(
            f"{BASE_URL}/api/trading/opportunities?symbols=BTC,ETH,SOL,DOGE,ADA",
            timeout=20,
        ).json()
        if not opp.get("ok"):
            pytest.skip("opportunities endpoint not ok")
        # If any directional, fetch its verdict and check invariant
        for action in ("LONG", "SHORT"):
            picks = opp["opportunities"][action]
            if not picks:
                continue
            sym = picks[0]["symbol"]
            r = s.get(f"{BASE_URL}/api/trading/verdict/{sym}", timeout=20).json()
            if (r.get("action") or "").upper() in ("LONG", "SHORT"):
                final = r["sizing"]["final"]
                if final > 0:
                    assert r["sizeUsd"] == final, (
                        f"sizeUsd ({r['sizeUsd']}) != sizing.final ({final})"
                    )
                else:
                    assert r.get("sizeUsd") is None
                return
        # No directional found — fine, just check WAIT contract
        r = s.get(f"{BASE_URL}/api/trading/verdict/BTC", timeout=20).json()
        assert r["sizing"]["final"] == 0.0
        assert r.get("sizeUsd") is None

    def test_wait_verdict_has_zero_final(self, s):
        r = s.get(f"{BASE_URL}/api/trading/verdict/BTC", timeout=20).json()
        if (r.get("action") or "").upper() == "WAIT":
            assert r["sizing"]["final"] == 0.0
            assert r["sizing"]["forcedZeroReason"] in (
                "verdict_is_wait", "no_structural_base_size",
            )
            assert r.get("sizeUsd") is None


# ── Integration: hostile regime (calibration hard-gate) → final=0 ────


class TestHostileRegimeZeroesSizing:
    def test_regime_hostile_results_in_zero_size(self, db):
        """When calibration regime_hard_gate flips action→WAIT, sizing.final = 0."""
        from services import calibration as _calib
        from services import adaptive_risk
        sym = "ZZT8HG"

        # Seed 12 losses in 30d window → recent30d hostile (wr=0, sample=12)
        db.trading_outcomes_v2.delete_many({"_seedTag": "T8_TEST", "symbol": sym})
        db.trading_calibration_v2.delete_many({"symbol": sym})
        db.trading_calibration_recent_v1.delete_many({"symbol": sym})
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            docs = []
            for _ in range(12):
                pid = f"T8_HG_{uuid.uuid4().hex[:8]}"
                docs.append({
                    "positionId": pid, "orderId": f"ord_{pid}",
                    "symbol": sym, "side": "LONG",
                    "entry": 100.0, "close": 95.0, "closeReason": "stop",
                    "outcome": "loss", "pnlPct": -0.5, "pnlUsd": -5,
                    "barsHeld": 5, "alignmentScore": 0.5,
                    "alignmentBucket": "0.33_0.67", "risk": "LOW", "rr": 1.5,
                    "verdictSnapshot": {"alignment": {"score": 0.5}, "risk": "LOW"},
                    "openedAt": now_iso, "closedAt": now_iso, "createdAt": now_iso,
                    "_seedTag": "T8_TEST",
                })
            db.trading_outcomes_v2.insert_many(docs)
            _calib._refresh_bucket(sym, "LONG", "0.33_0.67", "LOW")
            _calib._refresh_recent_buckets(sym, "LONG", "0.33_0.67", "LOW")

            verdict = {
                "symbol": sym, "action": "LONG", "confidence": 0.8,
                "risk": "LOW", "alignment": {"score": 0.5}, "reasons": [],
                "entry": 100.0, "stop": 95.0, "target": 110.0,
                "rr": 2.0, "sizeUsd": 100.0,
            }
            v = _calib.apply_to_verdict(verdict)
            # Calibration should have hard-gated to WAIT
            assert v["action"] == "WAIT"

            # Now run adaptive layer — must produce 0
            out = adaptive_risk.compute_adaptive_sizing(
                v, {"balanceUsd": 10_000, "equityUsd": 10_000}, [], 1.0,
            )
            assert out["final"] == 0.0
            assert out["forcedZeroReason"] == "verdict_is_wait"
        finally:
            db.trading_outcomes_v2.delete_many({"_seedTag": "T8_TEST", "symbol": sym})
            db.trading_calibration_v2.delete_many({"symbol": sym})
            db.trading_calibration_recent_v1.delete_many({"symbol": sym})


# ── Regression: T1-T7 endpoints still healthy ────────────────────────


class TestRegression:
    @pytest.mark.parametrize("path", [
        "/api/trading/runtime/status",
        "/api/trading/verdict/BTC",
        "/api/trading/opportunities?symbols=BTC,ETH,SOL",
        "/api/trading/paper/account",
        "/api/trading/paper/positions?status=OPEN",
        "/api/trading/paper/orders?limit=10",
        "/api/trading/paper/events?limit=10",
        "/api/trading/paper/scheduler/status",
        "/api/trading/intelligence/calibration?symbol=BTC",
    ])
    def test_endpoint_ok(self, s, path):
        r = s.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"
