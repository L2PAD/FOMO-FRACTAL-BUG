"""Sprint T4 — Feedback / Calibration Runtime tests.

Validates:
- GET /api/trading/intelligence/calibration empty & insufficient-data shape
- Unknown symbol → graceful 0-sample
- Open + close paper position → writeback to trading_outcomes_v2 + bucket refresh
- Idempotency: closing same position twice does not duplicate outcome rows
- trading_calibration_v2 unique index on (symbol, side, alignmentBucket, risk)
- /verdict/{symbol} has calibration block; WAIT verdicts → none_wait_verdict
- /calibration/cell single-cell lookup
- Scheduler auto-close (stop hit via Mongo mutation) writes outcome too
- Reliability ladder thresholds (4/7/15/30) using direct outcome seeding
- Graduated adjustments: soft_adjust (12 losses) + hard_gate (30 losses)
- Regression: T1/T2/T3 endpoints + scheduler still running
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or os.environ.get("EXPO_BACKEND_URL")
            or "https://merge-verify-4.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ACC = "default-paper-account"
TEST_SYM = "ZZTEST"  # synthetic symbol so we can seed buckets without colliding with live BTC


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json", "X-User-Id": "dev_user"})
    return sess


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


# ── Helpers ───────────────────────────────────────────────────────────

def _seed_outcomes(db, symbol, side, bucket, risk, n, outcome="loss",
                   close_reason="stop", pnl_pct=-0.5, age_days=0):
    """Insert N outcome rows directly into trading_outcomes_v2 and refresh bucket.

    age_days: how many days in the past `closedAt` should be. Use age_days>=100
    to seed STRICTLY lifetime outcomes (outside any T6 recent window).
    """
    from datetime import timedelta
    now_dt = datetime.now(timezone.utc)
    closed_dt = now_dt - timedelta(days=age_days) if age_days else now_dt
    now = now_dt.isoformat()
    closed = closed_dt.isoformat()
    docs = []
    for i in range(n):
        pid = f"TEST_{symbol}_{side}_{bucket}_{risk}_{uuid.uuid4().hex[:8]}"
        docs.append({
            "positionId": pid,
            "orderId": f"TEST_ord_{pid}",
            "symbol": symbol,
            "side": side,
            "entry": 100.0,
            "close": 99.5 if outcome == "loss" else 101.0,
            "closeReason": close_reason,
            "outcome": outcome,
            "pnlPct": pnl_pct,
            "pnlUsd": pnl_pct * 10,
            "barsHeld": 5,
            "alignmentScore": 0.5,
            "alignmentBucket": bucket,
            "risk": risk,
            "rr": 1.5,
            "verdictSnapshot": {"alignment": {"score": 0.5}, "risk": risk},
            "openedAt": closed,
            "closedAt": closed,
            "createdAt": now,
            "firstSeenAt": now,
            "_seedTag": "T4_TEST",
        })
    if docs:
        db.trading_outcomes_v2.insert_many(docs)
    # Refresh both lifetime AND recent buckets via service
    from services import calibration as _calib
    _calib._refresh_bucket(symbol, side, bucket, risk)
    _calib._refresh_recent_buckets(symbol, side, bucket, risk)
    return [d["positionId"] for d in docs]


def _cleanup_seeded(db, symbol=None):
    q = {"_seedTag": "T4_TEST"}
    if symbol:
        q["symbol"] = symbol
    db.trading_outcomes_v2.delete_many(q)
    # Also clean any leftover calibration_recent rows for test symbols
    if symbol:
        db.trading_calibration_recent_v1.delete_many({"symbol": symbol})
    if symbol:
        db.trading_calibration_v2.delete_many({"symbol": symbol})


# ── 1. Empty / insufficient-data shape ────────────────────────────────

class TestEmptyAndUnknown:
    def test_unknown_symbol_no_outcomes(self, s, db):
        # Ensure clean
        db.trading_outcomes_v2.delete_many({"symbol": "INVALIDXYZ"})
        db.trading_calibration_v2.delete_many({"symbol": "INVALIDXYZ"})
        r = s.get(f"{BASE_URL}/api/trading/intelligence/calibration?symbol=INVALIDXYZ", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert d.get("symbol") == "INVALIDXYZ"
        assert d.get("totalSample") == 0
        assert d.get("reliability") == "weak_sample"
        assert "no_outcomes_yet" in d.get("warnings", [])
        thresholds = d.get("thresholds") or {}
        assert "observe_only_max" in thresholds
        assert "warn_only_max" in thresholds
        assert "soft_adjust_max" in thresholds
        assert "hard_gate_min" in thresholds
        assert d.get("buckets") == []

    def test_missing_symbol_param_errors(self, s):
        r = s.get(f"{BASE_URL}/api/trading/intelligence/calibration", timeout=10)
        assert r.status_code in (400, 422), f"expected 4xx, got {r.status_code}"


# ── 2. Open + close paper position → writeback ────────────────────────

class TestWriteback:
    @pytest.fixture(scope="class")
    def closed_btc(self, s, db):
        # Cleanup existing OPEN BTC positions
        for p in list(db.paper_positions_v2.find({"accountId": ACC, "symbol": "BTC", "status": "OPEN"})):
            s.post(f"{BASE_URL}/api/trading/paper/close",
                   json={"positionId": p["positionId"], "reason": "test_cleanup"}, timeout=10)

        # Try submit with retries (price cache may be warming)
        sub = None
        for _ in range(5):
            r = s.post(f"{BASE_URL}/api/trading/paper/submit",
                       json={"symbol": "BTC", "action": "LONG"}, timeout=15).json()
            if r.get("ok"):
                sub = r
                break
            time.sleep(3)
        if not sub:
            pytest.skip(f"could not submit BTC paper order: {r}")

        pid = sub["positionId"]
        cl = s.post(f"{BASE_URL}/api/trading/paper/close",
                    json={"positionId": pid, "reason": "manual"}, timeout=15).json()
        assert cl.get("ok") is True, f"close failed: {cl}"
        return {"positionId": pid, "submit": sub, "close": cl}

    def test_outcome_row_written(self, db, closed_btc):
        pid = closed_btc["positionId"]
        doc = db.trading_outcomes_v2.find_one({"positionId": pid}, {"_id": 0})
        assert doc is not None, "outcome row not written"
        for key in ("positionId", "orderId", "symbol", "side", "entry", "close",
                    "closeReason", "outcome", "pnlPct", "pnlUsd", "barsHeld",
                    "alignmentScore", "alignmentBucket", "risk", "rr", "verdictSnapshot"):
            assert key in doc, f"outcome missing field: {key}"
        assert doc["symbol"] == "BTC"
        assert doc["outcome"] in ("win", "loss")
        assert doc["alignmentBucket"] in ("0_0.33", "0.33_0.67", "0.67_1.0", "unknown")

    def test_calibration_shows_sample_at_least_1(self, s):
        r = s.get(f"{BASE_URL}/api/trading/intelligence/calibration?symbol=BTC", timeout=15).json()
        assert r.get("ok") is True
        assert r.get("totalSample", 0) >= 1, f"expected sample≥1: {r}"

    def test_idempotency_double_close(self, s, db, closed_btc):
        pid = closed_btc["positionId"]
        # Count outcome rows for this positionId
        before = db.trading_outcomes_v2.count_documents({"positionId": pid})
        # Try closing same position again
        r = s.post(f"{BASE_URL}/api/trading/paper/close",
                   json={"positionId": pid, "reason": "manual"}, timeout=10).json()
        # Should return error / not_found_or_closed
        assert r.get("ok") is False or "not_found" in str(r).lower() or "closed" in str(r).lower(), \
            f"expected failure on double-close: {r}"
        after = db.trading_outcomes_v2.count_documents({"positionId": pid})
        assert after == before, f"duplicate outcome row: before={before} after={after}"
        # Should remain exactly 1
        assert after == 1


# ── 3. Unique index on (symbol, side, alignmentBucket, risk) ──────────

class TestCalibrationUniqueness:
    def test_unique_compound_index(self, db):
        # Read index info
        idx = db.trading_calibration_v2.index_information()
        compound = None
        for name, info in idx.items():
            keys = [k for k, _ in info.get("key", [])]
            if keys == ["symbol", "side", "alignmentBucket", "risk"]:
                compound = info
                break
        assert compound is not None, f"compound index missing: {idx.keys()}"
        assert compound.get("unique") is True, f"compound index not unique: {compound}"

    def test_only_one_doc_per_bucket(self, db):
        # Aggregate by the compound key — every group must have count=1
        pipe = [{"$group": {"_id": {"s": "$symbol", "side": "$side",
                                    "b": "$alignmentBucket", "r": "$risk"},
                            "n": {"$sum": 1}}},
                {"$match": {"n": {"$gt": 1}}}]
        dupes = list(db.trading_calibration_v2.aggregate(pipe))
        assert dupes == [], f"duplicate bucket docs: {dupes}"


# ── 4. /calibration/cell ──────────────────────────────────────────────

class TestCalibrationCell:
    def test_cell_found_after_seed(self, s, db):
        # Use the live BTC bucket cell that already exists from TestWriteback
        # First find an existing cell
        any_doc = db.trading_calibration_v2.find_one({"symbol": "BTC"}, {"_id": 0})
        if not any_doc:
            pytest.skip("no calibration cell yet")
        r = s.get(f"{BASE_URL}/api/trading/intelligence/calibration/cell",
                  params={"symbol": "BTC", "side": any_doc["side"],
                          "bucket": any_doc["alignmentBucket"], "risk": any_doc["risk"]},
                  timeout=10).json()
        assert r.get("ok") is True
        assert r.get("found") is True
        assert r.get("cell") is not None
        cell = r["cell"]
        assert cell["symbol"] == "BTC"
        assert cell["side"] == any_doc["side"]
        assert cell["alignmentBucket"] == any_doc["alignmentBucket"]

    def test_cell_not_found(self, s):
        r = s.get(f"{BASE_URL}/api/trading/intelligence/calibration/cell",
                  params={"symbol": "NEVERSEEN", "side": "LONG",
                          "bucket": "0.67_1.0", "risk": "N/A"},
                  timeout=10).json()
        assert r.get("ok") is True
        assert r.get("found") is False
        assert r.get("cell") is None


# ── 5. Verdict has calibration block ──────────────────────────────────

class TestVerdictCalibrationBlock:
    def test_verdict_has_calibration(self, s):
        r = s.get(f"{BASE_URL}/api/trading/verdict/BTC", timeout=20).json()
        assert "calibration" in r, f"verdict missing calibration: {list(r.keys())}"
        block = r["calibration"]
        for k in ("sample", "reliability", "alignmentBucket", "appliedAdjustment"):
            assert k in block, f"calibration block missing {k}: {block}"
        action = (r.get("action") or "").upper()
        if action == "WAIT":
            assert block["appliedAdjustment"] == "none_wait_verdict", \
                f"WAIT verdict must have appliedAdjustment='none_wait_verdict': {block}"
        else:
            # For LONG/SHORT, with small sample (1-4) → observe_only
            assert block["appliedAdjustment"] in (
                "observe_only", "warn_only", "soft_adjust", "soft_pass",
                "strong_soft_adjust", "strong_pass", "hard_gate_wait"
            ), f"unexpected appliedAdjustment: {block}"


# ── 6. Reliability ladder transitions (direct seed) ───────────────────

class TestReliabilityLadder:
    @pytest.fixture(autouse=True)
    def _cleanup(self, db):
        _cleanup_seeded(db, TEST_SYM)
        yield
        _cleanup_seeded(db, TEST_SYM)

    @pytest.mark.parametrize("n,expected", [
        (4, "weak_sample"),
        (7, "emerging"),
        (15, "usable"),
        (30, "strong"),
    ])
    def test_reliability_at_sample(self, s, db, n, expected):
        _seed_outcomes(db, TEST_SYM, "LONG", "0.33_0.67", "N/A", n)
        r = s.get(f"{BASE_URL}/api/trading/intelligence/calibration?symbol={TEST_SYM}", timeout=10).json()
        assert r.get("totalSample") == n, f"sample mismatch n={n}: {r.get('totalSample')}"
        # Per-bucket reliability
        buckets = r.get("buckets", [])
        assert buckets, "no buckets returned"
        b = buckets[0]
        assert b["sample"] == n
        assert b["reliability"] == expected, f"bucket reliability for n={n}: expected {expected} got {b['reliability']}"
        # Also overall reliability
        assert r["reliability"] == expected, f"top-level reliability for n={n}: expected {expected} got {r['reliability']}"


# ── 7. Graduated adjustments via verdict ──────────────────────────────

class TestGraduatedAdjustments:
    def test_soft_adjust_at_12_losses(self, s, db):
        """Seed 12 LOSS outcomes in a bucket → if verdict matches that bucket+side,
        apply_to_verdict must reduce confidence by 0.1 and bump risk."""
        from services import calibration as _calib
        # Build a fake verdict and pass through apply_to_verdict directly
        sym = "ZZSOFT"
        _cleanup_seeded(db, sym)
        try:
            _seed_outcomes(db, sym, "LONG", "0.33_0.67", "LOW", 12, age_days=120)
            verdict = {
                "symbol": sym, "action": "LONG", "confidence": 0.8,
                "risk": "LOW", "alignment": {"score": 0.5},
                "reasons": [],
            }
            out = _calib.apply_to_verdict(verdict)
            assert out["calibration"]["appliedAdjustment"] == "soft_adjust", \
                f"expected soft_adjust: {out['calibration']}"
            assert out["confidence"] == round(0.8 - 0.10, 3)
            assert out["risk"] == "MED", f"risk should bump LOW→MED: {out['risk']}"
            assert any("Calibration" in r for r in out["reasons"]), \
                f"reason note missing: {out['reasons']}"
        finally:
            _cleanup_seeded(db, sym)

    def test_hard_gate_at_30_losses(self, s, db):
        from services import calibration as _calib
        sym = "ZZHARD"
        _cleanup_seeded(db, sym)
        try:
            _seed_outcomes(db, sym, "LONG", "0.33_0.67", "LOW", 30, age_days=120)
            verdict = {
                "symbol": sym, "action": "LONG", "confidence": 0.8,
                "risk": "LOW", "alignment": {"score": 0.5}, "reasons": [],
                "entry": 100.0, "stop": 95.0, "target": 110.0, "rr": 2.0, "sizeUsd": 100,
            }
            out = _calib.apply_to_verdict(verdict)
            assert out["calibration"]["appliedAdjustment"] == "hard_gate_wait", \
                f"expected hard_gate_wait: {out['calibration']}"
            assert out["action"] == "WAIT"
            assert out["actionBeforeCalibration"] == "LONG"
            assert out["entry"] is None
            assert out["stop"] is None
            assert out["target"] is None
            assert out["rr"] is None
            assert out["sizeUsd"] is None
            assert any("historically_unprofitable_at_this_alignment" in b
                       for b in out.get("blockedBy", [])), f"blockedBy: {out.get('blockedBy')}"
        finally:
            _cleanup_seeded(db, sym)

    def test_observe_only_below_5(self, s, db):
        from services import calibration as _calib
        sym = "ZZOBS"
        _cleanup_seeded(db, sym)
        try:
            _seed_outcomes(db, sym, "LONG", "0.33_0.67", "N/A", 3)
            verdict = {
                "symbol": sym, "action": "LONG", "confidence": 0.8,
                "risk": "LOW", "alignment": {"score": 0.5}, "reasons": [],
            }
            out = _calib.apply_to_verdict(verdict)
            assert out["calibration"]["appliedAdjustment"] == "observe_only"
            assert out["action"] == "LONG"  # unchanged
            assert out["confidence"] == 0.8  # unchanged
            assert out["risk"] == "LOW"  # unchanged
        finally:
            _cleanup_seeded(db, sym)

    def test_warn_only_5_to_9(self, s, db):
        from services import calibration as _calib
        sym = "ZZWARN"
        _cleanup_seeded(db, sym)
        try:
            _seed_outcomes(db, sym, "LONG", "0.33_0.67", "LOW", 7)
            verdict = {
                "symbol": sym, "action": "LONG", "confidence": 0.8,
                "risk": "LOW", "alignment": {"score": 0.5}, "reasons": [],
            }
            out = _calib.apply_to_verdict(verdict)
            assert out["calibration"]["appliedAdjustment"] == "warn_only"
            assert out["action"] == "LONG"
            assert out["confidence"] == 0.8  # unchanged
            assert out["risk"] == "LOW"  # unchanged
            assert any("emerging sample" in r for r in out["reasons"]), \
                f"warn note missing: {out['reasons']}"
        finally:
            _cleanup_seeded(db, sym)


# ── 8. Scheduler auto-close also writes outcome ───────────────────────

class TestSchedulerWriteback:
    def test_scheduler_forced_stop_writes_outcome(self, s, db):
        # Cleanup any existing OPEN ETH positions
        for p in list(db.paper_positions_v2.find({"accountId": ACC, "symbol": "ETH", "status": "OPEN"})):
            s.post(f"{BASE_URL}/api/trading/paper/close",
                   json={"positionId": p["positionId"], "reason": "test_cleanup"}, timeout=10)

        sub = None
        for _ in range(5):
            r = s.post(f"{BASE_URL}/api/trading/paper/submit",
                       json={"symbol": "ETH", "action": "LONG"}, timeout=15).json()
            if r.get("ok"):
                sub = r
                break
            time.sleep(3)
        if not sub:
            pytest.skip(f"could not submit ETH paper order: {r}")
        pid = sub["positionId"]
        entry = float(sub["entry"])

        # Force stop hit (LONG: set stopPrice ABOVE entry to guarantee tick fallback fires)
        db.paper_positions_v2.update_one(
            {"positionId": pid, "status": "OPEN"},
            {"$set": {"stopPrice": round(entry * 1.5, 2)}},
        )
        run = s.post(f"{BASE_URL}/api/trading/paper/scheduler/run-once", timeout=20).json()
        assert run.get("ok") is True
        # Position should be CLOSED
        pos = db.paper_positions_v2.find_one({"positionId": pid}, {"_id": 0})
        assert pos["status"] == "CLOSED", f"position not closed: {pos}"
        # Outcome row should exist (writeback from scheduler path)
        out = db.trading_outcomes_v2.find_one({"positionId": pid}, {"_id": 0})
        assert out is not None, f"scheduler did NOT write outcome for {pid}"
        assert out["closeReason"] == "stop"
        assert out["outcome"] in ("win", "loss")
        assert out["symbol"] == "ETH"


# ── 9. Regression: T1/T2/T3 endpoints still healthy ───────────────────

class TestRegression:
    @pytest.mark.parametrize("path", [
        "/api/trading/verdict/BTC",
        "/api/trading/opportunities?symbols=BTC,ETH,SOL",
        "/api/trading/paper/account",
        "/api/trading/paper/positions?status=OPEN",
        "/api/trading/paper/orders?limit=10",
        "/api/trading/paper/events?limit=10",
        "/api/trading/runtime/status",
        "/api/trading/paper/scheduler/status",
    ])
    def test_endpoint_ok(self, s, path):
        r = s.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"

    def test_verdict_full_shape(self, s):
        r = s.get(f"{BASE_URL}/api/trading/verdict/BTC", timeout=15).json()
        for key in ("action", "entry", "stop", "target", "rr", "risk", "sizeUsd",
                    "confidence", "reasons", "blockedBy", "alignment",
                    "currentPrice", "support", "resistance", "moduleConfidence",
                    "asOf", "source", "calibration"):
            assert key in r, f"verdict missing key: {key}"

    def test_scheduler_still_running(self, s):
        r = s.get(f"{BASE_URL}/api/trading/paper/scheduler/status", timeout=10).json()
        assert r.get("enabled") is True
        assert r.get("running") is True

    def test_legacy_terminal_404(self, s):
        r = s.get(f"{BASE_URL}/api/terminal/status", timeout=10)
        assert r.status_code == 404

    def test_miniapp_lite(self, s):
        r = s.get(f"{BASE_URL}/api/miniapp/lite", timeout=15)
        assert r.status_code == 200

    def test_panel_admin(self, s):
        r = s.get(f"{BASE_URL}/api/panel/admin", timeout=15)
        assert r.status_code == 200
