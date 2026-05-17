"""
MiniApp Scheduler — Background automation for intelligence pipeline.
=====================================================================
Tasks:
  1. Polymarket Ingestion → Edge Rebuild → Alert Send (every 30 min)
  2. Daily Digest (09:00 UTC)
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger("miniapp.scheduler")

_state = {
    "running": False,
    "tasks": {},
    "last_ingest": None,
    "last_digest": None,
    "ingest_count": 0,
    "digest_count": 0,
    "errors": [],
}

INGEST_INTERVAL_MINUTES = 30
DIGEST_HOUR_UTC = 9


async def _run_ingest_cycle(db):
    """Single ingest → edge → alerts cycle."""
    from miniapp.polymarket_ingestion import ingest_polymarket
    from miniapp.edge_builder import build_edge
    from miniapp.edge_alerts import process_edge_alerts

    ingestion = await ingest_polymarket(db)
    edge_result = await build_edge(db)
    alerts = await process_edge_alerts(db, edge_result.get("markets", []))

    _state["last_ingest"] = datetime.now(timezone.utc).isoformat()
    _state["ingest_count"] += 1

    logger.info(
        f"Ingest cycle #{_state['ingest_count']}: "
        f"ingested={ingestion.get('stored', 0)}, "
        f"alerts_sent={alerts.get('sent', 0)}"
    )
    return {"ingestion": ingestion, "alerts": alerts}


async def _run_digest(db):
    """Send daily digest."""
    from miniapp.edge_alerts import send_daily_digest

    result = await send_daily_digest(db)
    _state["last_digest"] = datetime.now(timezone.utc).isoformat()
    _state["digest_count"] += 1

    logger.info(f"Digest #{_state['digest_count']}: sent={result.get('sent', 0)}")
    return result


async def _ingest_loop(db):
    """Background loop: ingest every INGEST_INTERVAL_MINUTES."""
    while _state["running"]:
        try:
            await _run_ingest_cycle(db)
        except Exception as e:
            err = f"Ingest error: {str(e)[:200]}"
            logger.error(err)
            _state["errors"] = (_state["errors"] + [err])[-10:]
        await asyncio.sleep(INGEST_INTERVAL_MINUTES * 60)


async def _resend_loop(db):
    """Background loop: check for unopened alerts and resend (every 15 min)."""
    while _state["running"]:
        try:
            from miniapp.alert_boost import process_resend_queue
            result = await process_resend_queue(db)
            if result.get("status") != "disabled":
                logger.info(f"Alert Boost resend: {result}")
        except Exception as e:
            err = f"Resend error: {str(e)[:200]}"
            logger.error(err)
            _state["errors"] = (_state["errors"] + [err])[-10:]
        await asyncio.sleep(15 * 60)


async def _digest_loop(db):
    """Background loop: send digest at DIGEST_HOUR_UTC."""
    while _state["running"]:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=DIGEST_HOUR_UTC, minute=0, second=0, microsecond=0)
        if now >= target:
            from datetime import timedelta
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        logger.info(f"Digest scheduled in {wait_seconds/3600:.1f}h")
        await asyncio.sleep(wait_seconds)

        if not _state["running"]:
            break

        try:
            await _run_digest(db)
        except Exception as e:
            err = f"Digest error: {str(e)[:200]}"
            logger.error(err)
            _state["errors"] = (_state["errors"] + [err])[-10:]


def start_scheduler(db):
    """Start background scheduler tasks. Call from app startup."""
    if _state["running"]:
        return {"status": "already_running"}

    _state["running"] = True
    _state["errors"] = []

    loop = asyncio.get_event_loop()
    _state["tasks"]["ingest"] = loop.create_task(_ingest_loop(db))
    _state["tasks"]["digest"] = loop.create_task(_digest_loop(db))
    _state["tasks"]["resend"] = loop.create_task(_resend_loop(db))

    logger.info("Scheduler started: ingest every 30min, digest at 09:00 UTC, resend check every 15min")
    return {"status": "started"}


def stop_scheduler():
    """Stop all background tasks."""
    _state["running"] = False
    for name, task in _state["tasks"].items():
        if task and not task.done():
            task.cancel()
    _state["tasks"] = {}
    logger.info("Scheduler stopped")
    return {"status": "stopped"}


def get_scheduler_status() -> dict:
    """Get current scheduler state."""
    return {
        "running": _state["running"],
        "lastIngest": _state["last_ingest"],
        "lastDigest": _state["last_digest"],
        "ingestCount": _state["ingest_count"],
        "digestCount": _state["digest_count"],
        "ingestIntervalMinutes": INGEST_INTERVAL_MINUTES,
        "digestHourUtc": DIGEST_HOUR_UTC,
        "recentErrors": _state["errors"][-5:],
    }


async def trigger_ingest_now(db) -> dict:
    """Manual trigger for immediate ingest cycle."""
    try:
        return await _run_ingest_cycle(db)
    except Exception as e:
        return {"error": str(e)[:200]}


async def trigger_digest_now(db) -> dict:
    """Manual trigger for immediate digest."""
    try:
        return await _run_digest(db)
    except Exception as e:
        return {"error": str(e)[:200]}
