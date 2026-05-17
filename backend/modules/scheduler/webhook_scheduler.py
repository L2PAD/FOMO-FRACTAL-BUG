"""
Webhook Scheduler
=================

Periodically checks for new events and emits webhooks.
Runs every 5 minutes.
"""

import logging
import asyncio
from typing import Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Global state
_db = None
_running = False
_task = None
_stats = {
    "runs": 0,
    "last_run": None,
    "total_emitted": {
        "funding": 0,
        "unlocks": 0,
        "news_breaking": 0,
        "news_important": 0
    },
    "errors": 0
}


def set_database(db):
    """Set database reference."""
    global _db
    _db = db


async def _run_webhook_check():
    """Run webhook check cycle."""
    global _stats
    
    if _db is None:
        logger.warning("[WebhookScheduler] Database not set")
        return
    
    try:
        from modules.webhooks.emitter import get_emitter
        from modules.webhooks.routes import get_manager
        
        # 1. Check for new events and emit webhooks
        emitter = get_emitter(_db)
        results = await emitter.run_all_checks()
        
        _stats["runs"] += 1
        _stats["last_run"] = datetime.now(timezone.utc).isoformat()
        _stats["total_emitted"]["funding"] += results.get("funding_emitted", 0)
        _stats["total_emitted"]["unlocks"] += results.get("unlocks_emitted", 0)
        _stats["total_emitted"]["news_breaking"] += results.get("breaking_emitted", 0)
        _stats["total_emitted"]["news_important"] += results.get("important_emitted", 0)
        
        total = (
            results.get("funding_emitted", 0) + 
            results.get("unlocks_emitted", 0) + 
            results.get("breaking_emitted", 0) + 
            results.get("important_emitted", 0)
        )
        
        if total > 0:
            logger.info(f"[WebhookScheduler] Emitted {total} webhooks: {results}")
        
        # 2. Process pending retries
        try:
            manager = get_manager()
            retry_results = await manager.process_pending_retries()
            
            if retry_results.get("processed", 0) > 0:
                logger.info(f"[WebhookScheduler] Processed retries: {retry_results}")
                _stats["retries_processed"] = _stats.get("retries_processed", 0) + retry_results.get("processed", 0)
                _stats["retries_succeeded"] = _stats.get("retries_succeeded", 0) + retry_results.get("succeeded", 0)
                _stats["retries_failed"] = _stats.get("retries_failed", 0) + retry_results.get("failed", 0)
        except Exception as retry_err:
            logger.warning(f"[WebhookScheduler] Error processing retries: {retry_err}")
            
    except Exception as e:
        _stats["errors"] += 1
        logger.error(f"[WebhookScheduler] Error in webhook check: {e}")


async def _scheduler_loop():
    """Main scheduler loop - runs every 5 minutes."""
    global _running
    
    logger.info("[WebhookScheduler] Started webhook scheduler (interval: 5 min)")
    
    # Initial delay to let system stabilize
    await asyncio.sleep(30)
    
    while _running:
        try:
            await _run_webhook_check()
        except Exception as e:
            logger.error(f"[WebhookScheduler] Loop error: {e}")
        
        # Wait 5 minutes
        await asyncio.sleep(300)
    
    logger.info("[WebhookScheduler] Stopped")


def start_scheduler():
    """Start the webhook scheduler."""
    global _running, _task
    
    if _running:
        logger.warning("[WebhookScheduler] Already running")
        return False
    
    _running = True
    _task = asyncio.create_task(_scheduler_loop())
    logger.info("[WebhookScheduler] Scheduler started")
    return True


def stop_scheduler():
    """Stop the webhook scheduler."""
    global _running, _task
    
    if not _running:
        return False
    
    _running = False
    if _task:
        _task.cancel()
        _task = None
    
    logger.info("[WebhookScheduler] Scheduler stopped")
    return True


def get_stats() -> Dict[str, Any]:
    """Get scheduler statistics."""
    return {
        "running": _running,
        "interval_seconds": 300,
        "interval_human": "5 minutes",
        **_stats
    }


def is_running() -> bool:
    """Check if scheduler is running."""
    return _running
