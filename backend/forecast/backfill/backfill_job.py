"""
Backfill Job
==============
Main orchestrator for Historical Shadow Validation.
Runs the full point-in-time replay pipeline and stores results.

Usage:
  POST /api/forecast/backfill/run?asset=BTC&horizon=7D
  GET  /api/forecast/backfill/results?run_id=...
  GET  /api/forecast/backfill/latest
"""

import time
import uuid
from datetime import datetime, timezone

from pymongo import MongoClient

from forecast.backfill.replay_universe_builder import build_replay_jobs
from forecast.backfill.historical_snapshot_builder import build_snapshot
from forecast.backfill.replay_runner import run_dual_replay
from forecast.backfill.historical_outcome_evaluator import evaluate_outcome
from forecast.backfill.shadow_case_comparator import compare_case
from forecast.backfill.pattern_tagger import tag_patterns
from forecast.backfill.shadow_kpi_aggregator import aggregate_kpis
from forecast.backfill.shadow_verdict_engine import build_verdict
from forecast.price_provider import get_price_series


REPLAY_RUNS_COL = "replay_runs"
REPLAY_CASES_COL = "replay_cases"
REPLAY_KPI_COL = "replay_kpi"


def _get_db():
    import os
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    return MongoClient(mongo_url)[db_name]


def run_backfill(
    asset: str = "BTC",
    horizon: str = "7D",
    start_date: str = None,
    end_date: str = None,
    target_version: str = "v4.2.0",
) -> dict:
    """
    Run full historical shadow validation.
    Default: BTC 7D, last ~100 days (leaving room for outcome evaluation).
    """
    start_time = time.time()
    run_id = f"backfill_{uuid.uuid4().hex[:8]}"
    db = _get_db()

    # Get all available price data
    prices = get_price_series(asset, "2025-01-01", "2027-01-01")
    all_dates = sorted(prices.keys())

    if not all_dates:
        return {"ok": False, "error": "No price data available"}

    # Default window: ~100 days ago to ~horizon days before latest
    if not start_date:
        from datetime import timedelta
        latest = datetime.strptime(all_dates[-1], "%Y-%m-%d")
        start_dt = latest - timedelta(days=100)
        start_date = start_dt.strftime("%Y-%m-%d")

    if not end_date:
        end_date = all_dates[-1]

    print(f"[Backfill] {run_id} | {asset}/{horizon} | {start_date} → {end_date}")

    # Phase 1: Build replay universe
    jobs = build_replay_jobs(asset, horizon, start_date, end_date, prices)
    print(f"[Backfill] {len(jobs)} replay jobs built")

    if not jobs:
        return {"ok": False, "error": "No valid replay dates in window"}

    # Log run
    run_doc = {
        "runId": run_id,
        "asset": asset,
        "horizon": horizon,
        "windowStart": start_date,
        "windowEnd": end_date,
        "totalJobs": len(jobs),
        "versions": ["v4.1", "v4.1.1", "v4.1.3"] if target_version == "v4.1.3" else ["v4.1", "v4.1.1", "v4.2.0"],
        "targetVersion": target_version,
        "status": "running",
        "startedAt": datetime.now(timezone.utc).isoformat(),
    }
    db[REPLAY_RUNS_COL].insert_one(run_doc)

    # Phase 2: Process each replay job
    cases = []
    errors = 0
    skipped = 0

    for i, job in enumerate(jobs):
        try:
            result = _process_single_job(job, prices, target_version)
            if result is None:
                skipped += 1
                continue

            result["runId"] = run_id
            db[REPLAY_CASES_COL].insert_one(result)
            cases.append(result)

            if (i + 1) % 10 == 0:
                print(f"[Backfill] Processed {i + 1}/{len(jobs)}")

        except Exception as e:
            errors += 1
            print(f"[Backfill] Error at {job['as_of']}: {e}")

    # Phase 3: Aggregate KPIs
    kpis = aggregate_kpis(cases)

    # Phase 4: Build verdict
    verdict = build_verdict(kpis)

    # Store results
    kpi_doc = {
        "runId": run_id,
        "asset": asset,
        "horizon": horizon,
        "kpis": kpis,
        "verdict": verdict,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    db[REPLAY_KPI_COL].insert_one(kpi_doc)

    duration_s = round(time.time() - start_time, 2)

    # Update run status
    db[REPLAY_RUNS_COL].update_one(
        {"runId": run_id},
        {"$set": {
            "status": "completed",
            "processedCases": len(cases),
            "skipped": skipped,
            "errors": errors,
            "durationSec": duration_s,
            "completedAt": datetime.now(timezone.utc).isoformat(),
        }},
    )

    print(f"[Backfill] Done: {len(cases)} cases, {skipped} skipped, {errors} errors in {duration_s}s")
    print(f"[Backfill] Verdict: {verdict['verdict']} — {verdict['reasons']}")

    return {
        "ok": True,
        "runId": run_id,
        "cases": len(cases),
        "skipped": skipped,
        "errors": errors,
        "durationSec": duration_s,
        "kpis": _sanitize(kpis),
        "verdict": verdict,
    }


def _process_single_job(job: dict, prices: dict, target_version: str = "v4.2.0") -> dict | None:
    """Process a single replay job: snapshot → triple pipeline → evaluate → compare → tag."""
    # Build point-in-time snapshot
    snapshot = build_snapshot(
        asset=job["asset"],
        as_of=job["as_of"],
        horizon=job["horizon"],
        prices=prices,
    )
    if snapshot is None:
        return None

    # Run triple pipeline (v4.1 base / v4.1.1 / v4.1.3 or v4.2.0)
    replay = run_dual_replay(snapshot, target_version=target_version)

    # Evaluate outcome
    outcome = evaluate_outcome(
        prices=prices,
        entry_price=snapshot["features"]["price"],
        outcome_date=job["outcome_date"],
    )
    if outcome is None:
        return None

    # Primary comparison: base vs v4.1.2 (multi-scale)
    comparison = compare_case(
        base=replay["base"],
        structure=replay["structure"],
        outcome=outcome,
    )

    # Supplementary comparison: base vs v4.1.1 (single-scale)
    comparison_v411 = None
    if replay.get("v411"):
        comparison_v411 = compare_case(
            base=replay["base"],
            structure=replay["v411"],
            outcome=outcome,
        )

    # Tag patterns (using v4.1.2 fused features)
    pattern_tags = tag_patterns(
        case=comparison,
        structure_features=replay["structure_features"],
        meta=replay["meta"],
    )

    return {
        "asset": job["asset"],
        "horizon": job["horizon"],
        "as_of": job["as_of"],
        "outcome_date": job["outcome_date"],
        "entry_price": round(snapshot["features"]["price"], 2),
        "replay": replay,
        "outcome": outcome,
        "comparison": comparison,
        "comparison_v411": comparison_v411,
        "multiscale_meta": replay.get("multiscale_meta"),
        "pattern_tags": pattern_tags,
    }


def get_backfill_results(run_id: str) -> dict | None:
    """Get full backfill results for a given run."""
    db = _get_db()

    run = db[REPLAY_RUNS_COL].find_one({"runId": run_id}, {"_id": 0})
    if not run:
        return None

    kpi = db[REPLAY_KPI_COL].find_one({"runId": run_id}, {"_id": 0})
    cases = list(db[REPLAY_CASES_COL].find(
        {"runId": run_id},
        {"_id": 0},
    ))

    return {
        "run": run,
        "kpis": _sanitize(kpi.get("kpis")) if kpi else None,
        "verdict": kpi.get("verdict") if kpi else None,
        "cases_count": len(cases),
    }


def get_latest_backfill(asset: str = "BTC", horizon: str = "7D") -> dict | None:
    """Get the most recent backfill results."""
    db = _get_db()
    kpi = db[REPLAY_KPI_COL].find_one(
        {"asset": asset, "horizon": horizon},
        {"_id": 0},
        sort=[("createdAt", -1)],
    )
    if not kpi:
        return None

    run = db[REPLAY_RUNS_COL].find_one(
        {"runId": kpi["runId"]},
        {"_id": 0},
    )

    return {
        "run": run,
        "kpis": _sanitize(kpi.get("kpis")),
        "verdict": kpi.get("verdict"),
    }


def get_backfill_cases(
    run_id: str,
    case_type: str = None,
    pattern: str = None,
    limit: int = 50,
) -> list[dict]:
    """Get individual cases from a backfill run, with optional filtering."""
    db = _get_db()

    query = {"runId": run_id}
    if case_type:
        query["comparison.case_type"] = case_type
    if pattern:
        query["pattern_tags"] = pattern

    cases = list(db[REPLAY_CASES_COL].find(
        query,
        {"_id": 0},
    ).limit(limit))

    return cases


def _sanitize(obj):
    """Remove any non-serializable objects (MongoDB internals)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items() if k != "_id"}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj
