"""
MBrain Directional Integrity — HTTP routes & diagnostic dashboard.

Endpoints:
    GET  /api/mbrain/integrity/health
    POST /api/mbrain/integrity/distribution/run    — trigger fresh audit
    GET  /api/mbrain/integrity/distribution/latest — latest snapshot metrics
    GET  /api/mbrain/integrity/distribution/raw    — raw decisions sample
    GET  /api/mbrain/integrity/snapshots           — list of historical snapshots
    GET  /api/mbrain/integrity/dashboard           — diagnostic-first HTML

NO mutations to side-car. NO writes to trading_os. NO production influence.
"""
from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from modules.mbrain_integrity import (
    fetch_audit_decisions,
    compute_distribution,
    run_distribution_audit,
    list_snapshots,
    latest_snapshot,
)
from modules.mbrain_integrity.replay import (
    run_replay,
    DEFAULT_ASSETS,
    DEFAULT_HORIZONS,
    DEFAULT_RANGES,
)

router = APIRouter(prefix="/api/mbrain/integrity", tags=["mbrain-integrity"])

_HERE = os.path.dirname(os.path.abspath(__file__))
_DASHBOARD_HTML = os.path.join(_HERE, "_mbrain_integrity_dashboard.html")


@router.get("/health")
async def health():
    """Lightweight health check — no side-effects."""
    rows = await asyncio.to_thread(fetch_audit_decisions, 1)
    return {"ok": True, "audit_channel_alive": len(rows) > 0, "sample_count": len(rows)}


@router.post("/distribution/run")
async def run_audit(
    limit: int = Query(5000, ge=10, le=50000),
    persist: bool = Query(True),
):
    """Pull /api/audit/decisions, compute metrics, optionally persist a snapshot."""
    return await asyncio.to_thread(run_distribution_audit, limit, persist)


@router.post("/replay/run")
async def replay_run(
    assets: str = Query("", description="Comma-separated asset list; empty=defaults"),
    horizons: str = Query("", description="Comma-separated horizons; empty=defaults"),
    ranges: str = Query("", description="Comma-separated ranges; empty=defaults"),
    max_decisions: int = Query(500, ge=1, le=2000),
    timeout_seconds: float = Query(60.0, ge=5.0, le=300.0),
):
    """G2 replay — REAL ML pipeline through side-car heavy-compute, no commit,
    no persistence in side-car. Sweeps (assets × ranges × horizons) and
    audits the resulting Verdict v2 decisions."""
    a = [x.strip() for x in assets.split(",") if x.strip()] or None
    h = [x.strip() for x in horizons.split(",") if x.strip()] or None
    r = [x.strip() for x in ranges.split(",") if x.strip()] or None
    return await asyncio.to_thread(
        run_replay, a, h, r, int(max_decisions), float(timeout_seconds),
    )


# ─── Module 2B — forward outcome resolution ────────────────────────────
@router.get("/asymmetry/pending")
async def asymmetry_pending(limit: int = Query(200, ge=1, le=2000)):
    """List pending forward-tracking outcomes (resolveAtEpoch ahead/past)."""
    from pymongo import MongoClient
    import os, time
    cli = MongoClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    now = time.time()
    rows = list(db.mbrain_integrity_outcomes.find(
        {"status": "PENDING"}, {"_id": 0}).limit(limit))
    ready = [r for r in rows if (r.get("resolveAtEpoch") or 0) <= now]
    return {
        "ok": True,
        "n_pending": len(rows),
        "n_ready_to_resolve": len(ready),
        "now_epoch": now,
        "sample": rows[:10],
    }


@router.post("/asymmetry/resolve")
async def asymmetry_resolve(
    persist: bool = Query(True),
    only_ready: bool = Query(True),
):
    """Resolve forward-tracking outcomes whose horizon has elapsed.
    HTTP-only to side-car (fetch close price). Updates records in
    `test_database.mbrain_integrity_outcomes`. Returns the realized
    asymmetry slice for whatever has been resolved so far.
    NO trading_os writes. NO production fusion influence."""
    from pymongo import MongoClient
    from modules.mbrain_integrity.asymmetry import (
        resolve_pending_outcomes, compute_realized_asymmetry,
    )
    from routes.mbrain_positions import _fetch_prices_parallel
    import os, time

    cli = MongoClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    now = time.time()
    rows = list(db.mbrain_integrity_outcomes.find({"status": "PENDING"}))
    if only_ready:
        rows = [r for r in rows
                if (r.get("resolveAtEpoch") or 0) <= now]

    # Pre-fetch all close prices async-parallel via side-car. This avoids
    # the worker thread getting blocked by sequential httpx.Client() calls.
    symbols = sorted({r.get("symbol") for r in rows if r.get("symbol")})
    raw_cache = await _fetch_prices_parallel(symbols, timeout=12.0)
    price_cache = {s: p for s, p in raw_cache.items() if p is not None}

    def _do() -> dict:
        out = resolve_pending_outcomes(rows, now, price_cache=price_cache)
        if persist and out["updates"]:
            for u in out["updates"]:
                db.mbrain_integrity_outcomes.update_one(
                    {"symbol": u["symbol"], "horizon": u["horizon"],
                     "ts_iso": u["ts_iso"]},
                    {"$set": u},
                )
        # Build outcome class map from latest records.
        cls_map = {}
        for r in db.mbrain_integrity_outcomes.find(
                {}, {"symbol": 1, "ts_iso": 1, "outcome_class": 1, "_id": 0}):
            cls_map[(r["symbol"], r["ts_iso"])] = r.get("outcome_class")
        # Pull resolved set for asymmetry analysis.
        resolved = list(db.mbrain_integrity_outcomes.find(
            {"status": "RESOLVED"}, {"_id": 0}))
        report = compute_realized_asymmetry(resolved, cls_map)
        return {
            "ok": True,
            "n_attempted": len(rows),
            "n_resolved_now": len(out["updates"]),
            "n_failures": len(out["failures"]),
            "failures_sample": out["failures"][:10],
            "n_priced_symbols": len(price_cache),
            "n_total_symbols": len(symbols),
            "realized_asymmetry": report,
        }

    return await asyncio.to_thread(_do)


# ─── Module 3 — Confidence calibration audit ──────────────────────────
@router.post("/calibration/run")
async def calibration_run():
    """Module 3 — meta-brain attenuation curve and (if 2B has resolved
    enough outcomes) realized confidence calibration.
    Pure read-only over `mbrain_integrity_outcomes`."""
    from pymongo import MongoClient
    from modules.mbrain_integrity.calibration import (
        compute_meta_brain_attenuation,
        compute_realized_calibration,
    )
    import os

    def _do() -> dict:
        cli = MongoClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        rows = list(db.mbrain_integrity_outcomes.find({}, {"_id": 0}))
        # Reconstruct minimal decisions for attenuation curve
        decisions = []
        for r in rows:
            if r.get("raw_expected_return") is None:
                continue
            decisions.append({
                "symbol": r.get("symbol"),
                "timeframe": r.get("horizon"),
                "ts": r.get("ts_iso"),
                "decision_raw": {
                    "direction": r.get("raw_direction"),
                    "confidence": r.get("raw_confidence"),
                    "expectedReturn": r.get("raw_expected_return"),
                },
                "stages": {
                    "raw": {"direction": r.get("raw_direction"),
                            "confidence": r.get("raw_confidence"),
                            "expectedReturn": r.get("raw_expected_return")},
                    "after_meta_brain": {
                        "direction": r.get("after_meta_direction"),
                        "confidence": None,  # not preserved in outcomes
                    },
                    "final": {"direction": r.get("final_direction")},
                },
                "regime": r.get("regime"),
                "modelId": r.get("modelId"),
            })
        m3_attenuation = compute_meta_brain_attenuation(decisions)
        # Realized calibration (only if we have RESOLVED rows)
        resolved = [r for r in rows if r.get("status") == "RESOLVED"]
        m3_realized = compute_realized_calibration(resolved)
        return {
            "ok": True,
            "n_decisions": len(decisions),
            "n_resolved": len(resolved),
            "attenuation": m3_attenuation,
            "realized_calibration": m3_realized,
        }

    return await asyncio.to_thread(_do)


@router.get("/distribution/latest")
async def latest():
    """Return the most recent persisted snapshot."""
    snap = await asyncio.to_thread(latest_snapshot)
    if not snap:
        return {"ok": False, "error": "no snapshot yet — call POST /distribution/run"}
    return {"ok": True, "snapshot": snap}


@router.get("/distribution/raw")
async def raw_sample(limit: int = Query(20, ge=1, le=200)):
    """Read-only view into raw side-car decisions (for spot-checks)."""
    rows = await asyncio.to_thread(fetch_audit_decisions, limit)
    # Strip heavy fields (portfolio_state etc.) for the API response
    slim = []
    for r in rows[: int(limit)]:
        slim.append({
            "ts": r.get("timestamp"),
            "trace_id": r.get("trace_id"),
            "symbol": r.get("symbol"),
            "timeframe": r.get("timeframe"),
            "raw_direction": (r.get("decision_raw") or {}).get("direction"),
            "raw_confidence": (r.get("decision_raw") or {}).get("confidence"),
            "raw_action": (r.get("decision_raw") or {}).get("action"),
            "enforced_direction": (r.get("decision_enforced") or {}).get("direction"),
            "final_action": r.get("final_action"),
            "blocked": r.get("blocked"),
            "block_reason": r.get("block_reason"),
            "reason_chain": r.get("reason_chain"),
        })
    return {"ok": True, "n": len(slim), "rows": slim}


@router.get("/snapshots")
async def snapshots(limit: int = Query(50, ge=1, le=500)):
    """List historical snapshot headers (no metrics body)."""
    return {"ok": True, "rows": await asyncio.to_thread(list_snapshots, limit)}


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Diagnostic-first HTML dashboard. Answers the 4 directive questions:
       1) Where is LONG dominance maximum?
       2) Are there regimes where SHORT almost never appears?
       3) Where does SHORT die — at generation or later?
       4) Is the bias global or regime-specific?
    """
    try:
        with open(_DASHBOARD_HTML, "r", encoding="utf-8") as fh:
            html = fh.read()
    except FileNotFoundError:
        html = "<h1>Directional Integrity dashboard missing</h1>"
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache"})
