"""
Exchange / forecast periodic loop — TRADING-ACTIVATION-3.

Calls forecast.scheduler.run_gen_job() every EXCHANGE_PERIODIC_INTERVAL_SEC
(default: 15 minutes).  This is the canonical forecast generation entry —
uses idempotent sub-daily bucket allocation, so the loop is safe to call
more often than the natural bucket resolution.

Backed by services/forecast/generator.py — pure live generator (NO LLM,
NO Emergent), works against current price + sentiment + actor history.

Failsafe loop — exceptions in a tick are caught and logged; the next
tick continues regardless of previous outcome.
"""

import asyncio
import os
from datetime import datetime, timezone


_DEFAULT_INTERVAL_SEC = 15 * 60  # 15 minutes


def _interval() -> int:
    try:
        v = int(os.environ.get("EXCHANGE_PERIODIC_INTERVAL_SEC", _DEFAULT_INTERVAL_SEC))
        return max(60, v)
    except Exception:
        return _DEFAULT_INTERVAL_SEC


async def run_once() -> dict:
    """Single forecast generation tick — public for manual triggers."""
    import sys
    sys.path.insert(0, "/app/backend")
    from forecast.scheduler import run_gen_job
    started = datetime.now(timezone.utc)
    try:
        # run_gen_job is sync — wrap in thread executor
        generated, errors = await asyncio.to_thread(run_gen_job)
        return {
            "ok": True,
            "ts": started.isoformat(),
            "generated": generated,
            "errors": errors,
        }
    except Exception as exc:
        return {
            "ok": False,
            "ts": started.isoformat(),
            "error": repr(exc),
        }


async def _loop():
    interval = _interval()
    print(f"[ExchangePeriodic] starting loop interval={interval}s")
    # Initial 90s delay so we don't compete with sentiment_periodic + startup
    await asyncio.sleep(90)
    while True:
        try:
            tick = await run_once()
            status = "ok" if tick.get("ok") else "FAIL"
            print(
                f"[ExchangePeriodic] {tick.get('ts')} {status} "
                f"generated={tick.get('generated', 0)} errors={tick.get('errors', 0)} "
                f"err={tick.get('error')}"
            )
        except Exception as exc:
            print(f"[ExchangePeriodic] loop error: {exc!r}")
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            print("[ExchangePeriodic] loop cancelled")
            raise


def start_loop_if_enabled() -> dict:
    """Schedule the periodic loop as a background task."""
    flag = os.environ.get("EXCHANGE_PERIODIC_ENABLED", "true").strip().lower()
    if flag in ("0", "false", "no", "off", ""):
        print("[ExchangePeriodic] disabled by EXCHANGE_PERIODIC_ENABLED")
        return {"started": False, "reason": "disabled_by_flag"}
    task = asyncio.create_task(_loop())
    return {"started": True, "interval_sec": _interval()}
