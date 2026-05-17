"""
Forecast Scheduler
===================
Orchestrates daily EVAL → GEN cycle.
Idempotent: safe to run multiple times per day.
"""

import time
from datetime import datetime, timezone

from forecast import Horizon
from forecast.generator_v41 import generate_forecast
from forecast.evaluator import evaluate_forecast
from forecast.repo import (
    ensure_indexes,
    get_pending_eval,
    update_eval,
    has_forecast_for_bucket,
    insert_forecast,
    log_run,
    get_overdue_count,
)
from assets.asset_registry import SUPPORTED_ASSETS

ASSETS = SUPPORTED_ASSETS  # Block 7.5: BTC, ETH, SOL


def run_eval_job() -> tuple[int, int]:
    """Phase 1: Evaluate all overdue forecasts. Returns (evaluated, errors)."""
    evaluated = 0
    errors = 0

    pending = get_pending_eval(limit=500)
    print(f"[Eval] Found {len(pending)} pending evaluations")

    for doc in pending:
        try:
            result = evaluate_forecast(doc)
            if result:
                update_eval(doc["id"], result)
                evaluated += 1
                print(f"  [Eval] {doc['asset']}/{doc['horizon']} {doc['createdBucket']} → {result.get('label', result.get('outcome'))}")
        except Exception as e:
            errors += 1
            print(f"  [Eval] Error for {doc.get('id')}: {e}")

    return evaluated, errors


def run_gen_job() -> tuple[int, int]:
    """Phase 2: Generate new forecasts for current slot. Returns (generated, errors)."""
    generated = 0
    errors = 0
    skipped = 0

    # Block 11: Sub-daily bucket
    from forecast.acceleration import get_current_bucket
    bucket = get_current_bucket()
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"

    for asset in ASSETS:
        for horizon in Horizon:
            try:
                # Idempotency check (now slot-aware)
                if has_forecast_for_bucket(asset, horizon.value, bucket):
                    print(f"  [Gen] {asset}/{horizon.value} already exists for {bucket}, skip")
                    continue

                record = generate_forecast(asset, horizon, run_id=run_id)
                if record:
                    inserted = insert_forecast(record)
                    if inserted:
                        generated += 1
                        quality = (record.audit or {}).get("acceleration", {}).get("qualityScore", "?")
                        print(f"  [Gen] {asset}/{horizon.value} → {record.direction} conf={record.confidence:.0%} q={quality}")
                    else:
                        print(f"  [Gen] {asset}/{horizon.value} duplicate (idempotent)")
                else:
                    skipped += 1
                    print(f"  [Gen] {asset}/{horizon.value} skipped (no data or delta guard)")
            except Exception as e:
                errors += 1
                print(f"  [Gen] Error for {asset}/{horizon.value}: {e}")

    print(f"  [Gen] Summary: generated={generated}, skipped={skipped}, errors={errors}")
    return generated, errors


def run_drift_job() -> dict:
    """Phase 3: Compute drift snapshots for all horizons and assets. Returns drift results."""
    results = {}
    for asset in ASSETS:
        for horizon in ["7D", "30D"]:
            key = f"{asset}/{horizon}"
            try:
                from drift.service import compute_drift_snapshot
                snapshot = compute_drift_snapshot(horizon=horizon, asset=asset)
                results[key] = {
                    "driftScore": snapshot["driftScore"],
                    "mlWeight": snapshot["mlWeight"],
                    "status": snapshot["status"],
                }
                print(f"  [Drift] {key}: score={snapshot['driftScore']:.3f} weight={snapshot['mlWeight']:.3f} status={snapshot['status']}")
            except Exception as e:
                results[key] = {"error": str(e)}
                print(f"  [Drift] {key}: Error — {e}")
    return results


def run_shadow_eval_job() -> dict:
    """Phase 4: Evaluate matured shadow predictions and compute verdicts."""
    try:
        from ml_overlay.eval_shadow import evaluate_shadow_forecasts, compute_rolling_verdict
        result = evaluate_shadow_forecasts()
        verdicts = {}
        for h in ["7D", "30D"]:
            v30 = compute_rolling_verdict(h, 30)
            verdicts[h] = {"verdict": v30["verdict"], "n": v30["n"]}
            print(f"  [Shadow] {h}: evaluated={result['evaluated']} verdict={v30['verdict']} n={v30['n']}")
        return {"eval": result, "verdicts": verdicts}
    except Exception as e:
        print(f"  [Shadow] Error: {e}")
        return {"error": str(e)}


def run_graduation_job() -> dict:
    """Phase 5: Evaluate graduation (promote/demote/hold) for each horizon and asset."""
    results = {}
    for asset in ASSETS:
        for horizon in ["7D", "30D"]:
            key = f"{asset}/{horizon}"
            try:
                from ml_overlay.graduation import evaluate_graduation
                result = evaluate_graduation(horizon=horizon, asset=asset)
                results[key] = {
                    "action": result["action"],
                    "stage": result["stage"],
                    "reason": result.get("reason", ""),
                }
                print(f"  [Graduation] {key}: {result['action']} -> {result['stage']} ({result.get('reason', '')})")
            except Exception as e:
                results[key] = {"error": str(e)}
                print(f"  [Graduation] {key}: Error — {e}")
    return results


def run_structure_shadow_eval() -> dict:
    """Phase 2b: Evaluate matured structure A/B shadow records."""
    try:
        from forecast.structure.shadow import evaluate_shadows
        result = evaluate_shadows()
        print(f"  [StructureShadow] evaluated={result['evaluated']} skipped={result['skipped']}")
        return result
    except Exception as e:
        print(f"  [StructureShadow] Error: {e}")
        return {"error": str(e)}


def run_daily():
    """Full daily cycle: EVAL → GEN → SHADOW_STRUCTURE → DRIFT → SHADOW_EVAL → GRADUATION."""
    # Freeze guard: skip mutations if frozen
    from forecast.repo import _cfg
    try:
        if _cfg().freeze_enabled:
            print("[Scheduler] SYSTEM_FROZEN — skipping daily run (read-only mode)")
            return {"evaluated": 0, "generated": 0, "errors": 0, "overdue": 0, "frozen": True}
    except RuntimeError:
        pass  # Config not yet initialized, proceed anyway

    start = time.time()
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
    print(f"\n{'='*50}")
    print(f"[Scheduler] Daily run at {datetime.now(timezone.utc).isoformat()} | {run_id}")
    print(f"{'='*50}")

    # Ensure indexes exist
    ensure_indexes()

    # Phase 1: Evaluate
    print("\n[Phase 1: EVAL]")
    eval_count, eval_errors = run_eval_job()

    # Phase 2: Generate
    print("\n[Phase 2: GEN]")
    gen_count, gen_errors = run_gen_job()

    # Phase 2b: Evaluate structure A/B shadows
    print("\n[Phase 2b: STRUCTURE_SHADOW_EVAL]")
    structure_shadow = run_structure_shadow_eval()

    # Phase 3: Drift monitoring
    print("\n[Phase 3: DRIFT]")
    drift_results = run_drift_job()

    # Phase 4: Shadow evaluation
    print("\n[Phase 4: SHADOW_EVAL]")
    shadow_results = run_shadow_eval_job()

    # Phase 5: Graduation decision
    print("\n[Phase 5: GRADUATION]")
    graduation_results = run_graduation_job()

    duration_ms = int((time.time() - start) * 1000)

    # Log run
    log_run(
        mode="daily",
        generated=gen_count,
        evaluated=eval_count,
        errors=eval_errors + gen_errors,
        duration_ms=duration_ms,
        run_id=run_id,
    )

    overdue = get_overdue_count()

    print(f"\n[Scheduler] Done in {duration_ms}ms")
    print(f"  Evaluated: {eval_count}, Generated: {gen_count}, Errors: {eval_errors + gen_errors}, Overdue: {overdue}")
    print(f"  Structure Shadow: {structure_shadow}")
    print(f"  Drift: {drift_results}")
    print(f"  Shadow: {shadow_results}")
    print(f"  Graduation: {graduation_results}")

    return {
        "evaluated": eval_count,
        "generated": gen_count,
        "errors": eval_errors + gen_errors,
        "overdue": overdue,
        "structureShadow": structure_shadow,
        "drift": drift_results,
        "shadow": shadow_results,
        "graduation": graduation_results,
        "durationMs": duration_ms,
    }
