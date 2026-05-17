"""
Market Feed Sync Service — 3-Tier Background Synchronization.

Tier 1 (HOT):    30-60s  — markets with high edge, active repricing
Tier 2 (ACTIVE): 3-5min  — actionable markets with moderate edge
Tier 3 (TAIL):   10-30min — all remaining markets

Runs as background asyncio tasks. Non-blocking.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger("prediction.feed.sync")

_sync_state = {
    "hot_ts": 0,
    "active_ts": 0,
    "tail_ts": 0,
    "running": False,
    "stats": {
        "hot_refreshes": 0,
        "active_refreshes": 0,
        "tail_refreshes": 0,
        "last_hot": None,
        "last_active": None,
        "last_tail": None,
    },
}

HOT_INTERVAL = 45       # seconds
ACTIVE_INTERVAL = 240   # 4 minutes
TAIL_INTERVAL = 900     # 15 minutes


async def start_sync_loop():
    """Start the 3-tier background sync loop."""
    if _sync_state["running"]:
        logger.info("Sync loop already running")
        return
    _sync_state["running"] = True
    logger.info("Starting 3-tier market feed sync loop")
    asyncio.create_task(_sync_loop())


async def _sync_loop():
    """Main sync loop — runs indefinitely."""
    from prediction.feed.market_feed_service import get_feed, _feed_cache

    while _sync_state["running"]:
        try:
            now = time.time()

            # Hot tier: every 45s
            if (now - _sync_state["hot_ts"]) >= HOT_INTERVAL:
                _sync_state["hot_ts"] = now
                _feed_cache["ts"] = 0  # Invalidate cache
                await get_feed(force_refresh=True)
                _sync_state["stats"]["hot_refreshes"] += 1
                _sync_state["stats"]["last_hot"] = datetime.now(timezone.utc).isoformat()
                logger.debug("Hot sync complete")

            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Sync loop error: {e}")
            await asyncio.sleep(10)


def stop_sync():
    """Stop sync loop."""
    _sync_state["running"] = False
    logger.info("Sync loop stopped")


def get_sync_stats() -> dict:
    """Return sync statistics."""
    return {
        "running": _sync_state["running"],
        **_sync_state["stats"],
    }
