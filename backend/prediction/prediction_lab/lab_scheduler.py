"""
Prediction Lab Scheduler — background jobs for the Truth Engine.

Jobs:
  1. Price Tracker     — every 5 min  — snapshot prices for pending forecasts
  2. Forecast Resolver — every 10 min — check Polymarket for resolutions
  3. Analytics Recalc  — every 60 min — recalculate calibration + families

All jobs have retry-safe logic with exponential backoff.
Runs as asyncio tasks inside FastAPI lifespan.
"""
import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger("prediction_lab.scheduler")

# Job intervals (seconds)
PRICE_TRACK_INTERVAL = 300     # 5 min
RESOLVE_INTERVAL = 600         # 10 min
RECALCULATE_INTERVAL = 3600    # 1 hour
STARTUP_DELAY = 30             # wait for app to be ready

# Retry config
MAX_RETRIES = 3
BASE_DELAY = 5  # seconds


def _get_db():
    from prediction.prediction_lab.db_helper import get_sync_db
    return get_sync_db()


async def _run_with_retry(job_name: str, coro_fn, *args):
    """Run an async job with exponential backoff retries."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await coro_fn(*args)
            if attempt > 1:
                logger.info(f"[{job_name}] Succeeded on attempt {attempt}")
            return result
        except Exception as e:
            delay = BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(f"[{job_name}] Attempt {attempt}/{MAX_RETRIES} failed: {e}. Retry in {delay}s")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(delay)
            else:
                logger.error(f"[{job_name}] All {MAX_RETRIES} attempts exhausted")
    return None


def _run_sync_with_retry(job_name: str, fn, *args):
    """Run a sync job with retries."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = fn(*args)
            return result
        except Exception as e:
            logger.warning(f"[{job_name}] Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt >= MAX_RETRIES:
                logger.error(f"[{job_name}] All attempts exhausted")
    return None


async def price_tracker_loop():
    """Background loop: track prices for pending forecasts every 5 min."""
    await asyncio.sleep(STARTUP_DELAY)
    logger.info("[PriceTracker] Started (5min interval)")

    while True:
        try:
            db = _get_db()
            if db is not None:
                from prediction.prediction_lab.price_tracker import track_pending_prices
                result = await _run_with_retry("PriceTracker", track_pending_prices, db)
                if result:
                    tracked = result.get("tracked", 0)
                    if tracked > 0:
                        logger.info(f"[PriceTracker] Tracked {tracked} prices")
        except Exception as e:
            logger.error(f"[PriceTracker] Loop error: {e}")

        await asyncio.sleep(PRICE_TRACK_INTERVAL)


async def resolver_loop():
    """Background loop: resolve pending forecasts every 10 min."""
    await asyncio.sleep(STARTUP_DELAY + 15)  # offset from price tracker
    logger.info("[Resolver] Started (10min interval)")

    while True:
        try:
            db = _get_db()
            if db is not None:
                from prediction.prediction_lab.lab_orchestrator import run_resolve_cycle
                result = await _run_with_retry("Resolver", run_resolve_cycle, db)
                if result:
                    resolved = result.get("resolved", 0)
                    if resolved > 0:
                        logger.info(f"[Resolver] Resolved {resolved} forecasts")
        except Exception as e:
            logger.error(f"[Resolver] Loop error: {e}")

        await asyncio.sleep(RESOLVE_INTERVAL)


async def recalculate_loop():
    """Background loop: recalculate analytics every hour."""
    await asyncio.sleep(STARTUP_DELAY + 60)  # offset
    logger.info("[Recalculate] Started (60min interval)")

    while True:
        try:
            db = _get_db()
            if db is not None:
                from prediction.prediction_lab.lab_orchestrator import run_recalculate
                result = _run_sync_with_retry("Recalculate", run_recalculate, db)
                if result:
                    logger.info(f"[Recalculate] Done: {result}")
        except Exception as e:
            logger.error(f"[Recalculate] Loop error: {e}")

        await asyncio.sleep(RECALCULATE_INTERVAL)


async def start_lab_scheduler():
    """Start all Prediction Lab background tasks. Called from server.py startup."""
    logger.info("[PredictionLab] Starting scheduler (3 background jobs)")
    asyncio.create_task(price_tracker_loop())
    asyncio.create_task(resolver_loop())
    asyncio.create_task(recalculate_loop())
