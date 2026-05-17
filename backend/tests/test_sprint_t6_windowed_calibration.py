"""Sprint T6 — Windowed Reliability (dual-memory) tests.

Validates the dual-memory calibration architecture:
- Lifetime (`trading_calibration_v2`) is IMMUTABLE — never overwritten by recent path
- Recent windowed (`trading_calibration_recent_v1`) with 30d/90d windows is parallel
- Verdict overlay priority hierarchy:
    1. recent_30d sample>=10 AND winRate<0.35 → regime_hard_gate (flip to WAIT)
    2. recent_30d sample>=5 AND winRate<0.40 AND lifetime sample>=10 AND
       winRate>=0.50 → regime_degradation_soft_adjust
    3. otherwise fall through to T4 lifetime ladder
- Minimum sample threshold (recent>=5) gates the recent path
- Lazy refresh on stale buckets
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


# ── Helpers ──────────────────────────────────────────────────────────

def _seed(db, symbol, side, bucket, risk, n, outcome="loss",
          close_reason="stop", pnl_pct=-0.5, age_days=0):
    """Direct seed into trading_outcomes_v2 + refresh BOTH lifetime and recent buckets."""
    now_dt = datetime.now(timezone.utc)
    closed_dt = now_dt - timedelta(days=age_days) if age_days else now_dt
    now = now_dt.isoformat()
    closed = closed_dt.isoformat()
    docs = []
    for _ in range(n):
        pid = f"TEST_T6_{symbol}_{side}_{bucket}_{risk}_{uuid.uuid4().hex[:8]}"
        docs.append({
            "positionId": pid,
            "orderId": f"TEST_T6_ord_{pid}",
            "symbol": symbol, "side": side,
            "entry": 100.0,
            "close": 99.5 if outcome == "loss" else 101.0,
            "closeReason": close_reason,
            "outcome": outcome,
            "pnlPct": pnl_pct, "pnlUsd": pnl_pct * 10, "barsHeld": 5,
            "alignmentScore": 0.5, "alignmentBucket": bucket,
            "risk": risk, "rr": 1.5,
            "verdictSnapshot": {"alignment": {"score": 0.5}, "risk": risk},
            "openedAt": closed, "closedAt": closed,
            "createdAt": now, "firstSeenAt": now,
            "_seedTag": "T6_TEST",
        })
    if docs:
        db.trading_outcomes_v2.insert_many(docs)
    from services import calibration as _calib
    _calib._refresh_bucket(symbol, side, bucket, risk)
    _calib._refresh_recent_buckets(symbol, side, bucket, risk)
    return [d["positionId"] for d in docs]


def _cleanup(db, symbol):
    db.trading_outcomes_v2.delete_many({"_seedTag": "T6_TEST", "symbol": symbol})
    db.trading_calibration_v2.delete_many({"symbol": symbol})
    db.trading_calibration_recent_v1.delete_many({"symbol": symbol})


# ── 1. Report shape: lifetime + recent30d + recent90d ─────────────────

class TestReportShape:
    def test_report_has_recent30d_and_recent90d(self, s):
        r = s.get(f"{BASE_URL}/api/trading/intelligence/calibration?symbol=BTC",
                  timeout=15).json()
        assert r.get("ok") is True
        assert "recent30d" in r, f"missing recent30d: {list(r.keys())}"
        assert "recent90d" in r, f"missing recent90d: {list(r.keys())}"
        # recent30d block keys
        rec = r["recent30d"]
        for k in ("totalSample", "totalWins", "winRate", "reliability", "buckets"):
            assert k in rec, f"recent30d missing {k}: {list(rec.keys())}"
        assert isinstance(rec["buckets"], list)
        # recent90d block keys (buckets at minimum)
        assert "buckets" in r["recent90d"]
        assert isinstance(r["recent90d"]["buckets"], list)

    def test_thresholds_include_t6_fields(self, s):
        r = s.get(f"{BASE_URL}/api/trading/intelligence/calibration?symbol=BTC",
                  timeout=15).json()
        thr = r.get("thresholds") or {}
        assert thr.get("recent_min_sample") == 5, f"expected recent_min_sample=5: {thr}"
        assert thr.get("recent_degradation_winrate") == 0.40, \
            f"expected recent_degradation_winrate=0.40: {thr}"
        # T4 thresholds preserved
        for k in ("observe_only_max", "warn_only_max", "soft_adjust_max", "hard_gate_min"):
            assert k in thr, f"missing T4 threshold {k}"


# ── 2. Collection + compound unique index ─────────────────────────────

class TestRecentCollection:
    def test_recent_collection_exists_with_compound_index(self, db):
        idx = db.trading_calibration_recent_v1.index_information()
        compound = None
        for _, info in idx.items():
            keys = [k for k, _ in info.get("key", [])]
            if keys == ["symbol", "side", "alignmentBucket", "risk", "window"]:
                compound = info
                break
        assert compound is not None, f"compound index missing: {list(idx.keys())}"
        assert compound.get("unique") is True, f"compound index not unique: {compound}"


# ── 3. record_outcome / direct seed → 3 docs (lifetime + 30d + 90d) ───

class TestDualWriteback:
    def test_seed_creates_three_docs_per_cell(self, db):
        sym = "ZZT6WB"
        _cleanup(db, sym)
        try:
            _seed(db, sym, "LONG", "0.33_0.67", "N/A", 5, age_days=0)
            life = db.trading_calibration_v2.find_one(
                {"symbol": sym, "side": "LONG",
                 "alignmentBucket": "0.33_0.67", "risk": "N/A"})
            assert life is not None and life["sample"] == 5
            r30 = db.trading_calibration_recent_v1.find_one(
                {"symbol": sym, "window": "30d", "side": "LONG",
                 "alignmentBucket": "0.33_0.67", "risk": "N/A"})
            r90 = db.trading_calibration_recent_v1.find_one(
                {"symbol": sym, "window": "90d", "side": "LONG",
                 "alignmentBucket": "0.33_0.67", "risk": "N/A"})
            assert r30 is not None and r30["sample"] == 5, f"recent30d: {r30}"
            assert r90 is not None and r90["sample"] == 5, f"recent90d: {r90}"
        finally:
            _cleanup(db, sym)


# ── 4. Verdict has recent30d subblock + regimeSignal ─────────────────

class TestVerdictRecentSubblock:
    def test_verdict_calibration_has_recent30d(self, s):
        r = s.get(f"{BASE_URL}/api/trading/verdict/BTC", timeout=20).json()
        block = r.get("calibration", {})
        # recent30d subblock only present when verdict was directional (LONG/SHORT)
        action = (r.get("action") or "").upper()
        if action in ("LONG", "SHORT"):
            assert "recent30d" in block, f"missing recent30d in directional verdict: {block}"
            rec = block["recent30d"]
            for k in ("sample", "wins", "losses", "winRate", "targetRate", "reliability"):
                assert k in rec, f"recent30d missing {k}: {rec}"
            assert "regimeSignal" in block, f"missing regimeSignal: {block}"
            assert block["regimeSignal"] in (
                "no_recent_sample", "recent_sample_emerging",
                "current_regime_compatible", "current_regime_mixed",
                "current_regime_weak", "actively_hostile", "degrading",
            ), f"unexpected regimeSignal: {block['regimeSignal']}"
        else:
            # WAIT → none_wait_verdict path, recent subblock may be absent
            assert block.get("appliedAdjustment") == "none_wait_verdict"


# ── 5. T6 REGIME_HARD_GATE ────────────────────────────────────────────

class TestRegimeHardGate:
    def test_regime_hard_gate_flips_to_wait(self, db):
        from services import calibration as _calib
        sym = "ZZT6HG"
        _cleanup(db, sym)
        try:
            # 12 LOSSES, all closedAt=now → recent30d sample=12, winRate=0.0
            # No lifetime-only extras → lifetime is same 12 losses (sample=12, wr=0)
            # But T6 hard-gate fires first because recent sample>=10 AND wr<0.35
            _seed(db, sym, "LONG", "0.33_0.67", "LOW", 12, age_days=0)
            verdict = {
                "symbol": sym, "action": "LONG", "confidence": 0.8,
                "risk": "LOW", "alignment": {"score": 0.5}, "reasons": [],
                "entry": 100.0, "stop": 95.0, "target": 110.0,
                "rr": 2.0, "sizeUsd": 100,
            }
            out = _calib.apply_to_verdict(verdict)
            block = out["calibration"]
            assert block["appliedAdjustment"] == "regime_hard_gate", \
                f"expected regime_hard_gate: {block}"
            assert block["regimeSignal"] == "actively_hostile", \
                f"expected actively_hostile: {block}"
            assert out["action"] == "WAIT", f"action not flipped: {out['action']}"
            assert out.get("actionBeforeCalibration") == "LONG"
            assert out["entry"] is None
            assert out["stop"] is None
            assert out["target"] is None
            assert out["rr"] is None
            assert out["sizeUsd"] is None
            assert any("current_regime_hostile" in b
                       for b in out.get("blockedBy", [])), \
                f"blockedBy missing: {out.get('blockedBy')}"
        finally:
            _cleanup(db, sym)


# ── 6. T6 REGIME_DEGRADATION_SOFT_ADJUST ──────────────────────────────

class TestRegimeDegradation:
    def test_regime_degradation_soft_adjust(self, db):
        from services import calibration as _calib
        sym = "ZZT6DEG"
        _cleanup(db, sym)
        try:
            # Lifetime: 20 wins age_days=120 (outside 30d window) → lifetime
            #   sample=20, winRate=1.0
            # Recent: 6 losses age_days=0 (in 30d window) → recent sample=6,
            #   winRate=0.0
            # NOTE: recent window also includes everything within 30d, but the
            # 20 wins are 120 days old so excluded from recent.
            # Combined lifetime: 20 wins + 6 losses = 26, wr=20/26=0.769
            _seed(db, sym, "LONG", "0.33_0.67", "LOW", 20,
                  outcome="win", close_reason="target",
                  pnl_pct=0.5, age_days=120)
            _seed(db, sym, "LONG", "0.33_0.67", "LOW", 6,
                  outcome="loss", close_reason="stop",
                  pnl_pct=-0.5, age_days=0)
            # Snapshot lifetime BEFORE apply_to_verdict
            life_before = db.trading_calibration_v2.find_one(
                {"symbol": sym, "side": "LONG",
                 "alignmentBucket": "0.33_0.67", "risk": "LOW"},
                {"_id": 0})
            assert life_before is not None
            assert life_before["sample"] == 26
            assert life_before["wins"] == 20
            assert life_before["winRate"] >= 0.50
            verdict = {
                "symbol": sym, "action": "LONG", "confidence": 0.8,
                "risk": "LOW", "alignment": {"score": 0.5}, "reasons": [],
                "entry": 100.0, "stop": 95.0, "target": 110.0,
                "rr": 2.0, "sizeUsd": 100,
            }
            out = _calib.apply_to_verdict(verdict)
            block = out["calibration"]
            assert block["appliedAdjustment"] == "regime_degradation_soft_adjust", \
                f"expected regime_degradation_soft_adjust: {block}"
            assert block["regimeSignal"] == "degrading", \
                f"expected degrading: {block}"
            # Action stays LONG (not WAIT)
            assert out["action"] == "LONG", f"action should NOT flip: {out['action']}"
            # Confidence reduced by 0.15
            assert out["confidence"] == round(0.8 - 0.15, 3), \
                f"confidence not reduced 0.15: {out['confidence']}"
            # Risk bumped (LOW → MED) and riskBeforeCalibration preserved
            assert out.get("riskBeforeCalibration") == "LOW"
            assert out["risk"] == "MED"
            # Reasons contain the specific phrases
            reasons_str = " ".join(out.get("reasons", []))
            assert "lifetime held up" in reasons_str, f"reasons: {out.get('reasons')}"
            assert "recent follow-through deteriorated" in reasons_str, \
                f"reasons: {out.get('reasons')}"
            # LIFETIME IMMUTABILITY check
            life_after = db.trading_calibration_v2.find_one(
                {"symbol": sym, "side": "LONG",
                 "alignmentBucket": "0.33_0.67", "risk": "LOW"},
                {"_id": 0})
            assert life_after["sample"] == life_before["sample"]
            assert life_after["wins"] == life_before["wins"]
            assert life_after["winRate"] == life_before["winRate"]
        finally:
            _cleanup(db, sym)


# ── 7. T6 MINIMUM SAMPLE GUARD ────────────────────────────────────────

class TestMinimumSampleGuard:
    def test_recent_below_5_does_not_trigger_regime(self, db):
        from services import calibration as _calib
        sym = "ZZT6MIN"
        _cleanup(db, sym)
        try:
            # 4 losses age_days=0, risk="LOW" → recent sample=4 (below min 5)
            _seed(db, sym, "LONG", "0.33_0.67", "LOW", 4, age_days=0)
            verdict = {
                "symbol": sym, "action": "LONG", "confidence": 0.8,
                "risk": "LOW", "alignment": {"score": 0.5}, "reasons": [],
            }
            out = _calib.apply_to_verdict(verdict)
            block = out["calibration"]
            # Must fall through to lifetime ladder. sample=4 → observe_only.
            assert block["appliedAdjustment"] == "observe_only", \
                f"expected observe_only (sample=4): {block}"
            assert block.get("regimeSignal") == "recent_sample_emerging", \
                f"expected recent_sample_emerging: {block}"
            assert out["action"] == "LONG"
            assert out["confidence"] == 0.8
        finally:
            _cleanup(db, sym)


# ── 8. T6 LIFETIME LADDER STILL FIRES when recent doesn't ────────────

class TestLifetimeLadderFiresWithoutRecent:
    def test_lifetime_hard_gate_with_no_recent(self, db):
        from services import calibration as _calib
        sym = "ZZT6LIFE"
        _cleanup(db, sym)
        try:
            # 30 losses age_days=120 → lifetime sample=30, wr=0.0, no recent
            _seed(db, sym, "LONG", "0.33_0.67", "LOW", 30, age_days=120)
            verdict = {
                "symbol": sym, "action": "LONG", "confidence": 0.8,
                "risk": "LOW", "alignment": {"score": 0.5}, "reasons": [],
                "entry": 100.0, "stop": 95.0, "target": 110.0,
                "rr": 2.0, "sizeUsd": 100,
            }
            out = _calib.apply_to_verdict(verdict)
            block = out["calibration"]
            assert block["appliedAdjustment"] == "hard_gate_wait", \
                f"expected hard_gate_wait (T4 path): {block}"
            assert block.get("regimeSignal") == "no_recent_sample", \
                f"expected no_recent_sample: {block}"
            assert out["action"] == "WAIT"
            assert any("historically_unprofitable_at_this_alignment" in b
                       for b in out.get("blockedBy", []))
        finally:
            _cleanup(db, sym)


# ── 9. T6 LAZY REFRESH ───────────────────────────────────────────────

class TestLazyRefresh:
    def test_lookup_recent_refreshes_stale_bucket(self, db):
        from services import calibration as _calib
        sym = "ZZT6LAZY"
        _cleanup(db, sym)
        try:
            _seed(db, sym, "LONG", "0.33_0.67", "LOW", 5, age_days=0)
            # Manipulate updatedAt to 1 hour ago (stale, TTL=600s)
            stale_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            db.trading_calibration_recent_v1.update_one(
                {"symbol": sym, "window": "30d", "side": "LONG",
                 "alignmentBucket": "0.33_0.67", "risk": "LOW"},
                {"$set": {"updatedAt": stale_iso, "sample": 999}},
            )
            before = db.trading_calibration_recent_v1.find_one(
                {"symbol": sym, "window": "30d", "side": "LONG",
                 "alignmentBucket": "0.33_0.67", "risk": "LOW"})
            assert before["sample"] == 999
            # Call lookup_recent — should refresh
            doc = _calib.lookup_recent(sym, "LONG", "0.33_0.67", "LOW", "30d")
            assert doc is not None
            assert doc["sample"] == 5, f"lazy refresh did not run: sample={doc['sample']}"
            # updatedAt should be recent
            after = db.trading_calibration_recent_v1.find_one(
                {"symbol": sym, "window": "30d", "side": "LONG",
                 "alignmentBucket": "0.33_0.67", "risk": "LOW"})
            assert after["sample"] == 5
            new_ts = datetime.fromisoformat(after["updatedAt"].replace("Z", "+00:00")).timestamp()
            now_ts = datetime.now(timezone.utc).timestamp()
            assert now_ts - new_ts < 60, \
                f"updatedAt not refreshed: {after['updatedAt']}"
        finally:
            _cleanup(db, sym)


# ── 10. Regression smoke (T1-T5 endpoints) ────────────────────────────

class TestT1ToT5Regression:
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
        "/api/miniapp/lite",
        "/api/panel/admin",
    ])
    def test_endpoint_ok(self, s, path):
        r = s.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"

    def test_terminal_honest_404(self, s):
        r = s.get(f"{BASE_URL}/api/terminal/status", timeout=10)
        assert r.status_code == 404
