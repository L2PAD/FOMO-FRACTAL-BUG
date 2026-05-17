"""
Auto-Discovery Scheduler
========================
Periodically runs auto-discovery to find missing data and new providers.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DiscoveryScheduler:
    """Scheduler for periodic auto-discovery"""
    
    def __init__(self, db, interval_minutes: int = 60):
        self.db = db
        self.interval = interval_minutes * 60  # Convert to seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_run: Optional[datetime] = None
        self._last_result: Optional[Dict] = None
        self._run_count = 0
        
    async def _run_discovery(self):
        """Run a single discovery cycle"""
        from modules.intel.full_auto_discovery import get_full_discovery
        import os
        
        engine = get_full_discovery(self.db)
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
        
        try:
            result = await engine.run_full_discovery_cycle(base_url)
            self._last_result = result
            self._last_run = datetime.now(timezone.utc)
            self._run_count += 1
            
            logger.info(f"Discovery scheduler run #{self._run_count}: "
                       f"Found {result.get('new_sources_total', 0)} new sources")
            
            return result
        except Exception as e:
            logger.error(f"Discovery scheduler error: {e}")
            return {"error": str(e)}
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        logger.info(f"Discovery scheduler started (interval: {self.interval}s)")
        
        while self._running:
            try:
                await self._run_discovery()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)  # Wait 1 min on error
        
        logger.info("Discovery scheduler stopped")
    
    def start(self):
        """Start the scheduler"""
        if self._running:
            return {"status": "already_running"}
        
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        
        return {
            "status": "started",
            "interval_minutes": self.interval // 60
        }
    
    def stop(self):
        """Stop the scheduler"""
        if not self._running:
            return {"status": "not_running"}
        
        self._running = False
        if self._task:
            self._task.cancel()
        
        return {"status": "stopped"}
    
    def get_status(self) -> Dict:
        """Get scheduler status"""
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "running": self._running,
            "interval_minutes": self.interval // 60,
            "run_count": self._run_count,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "next_run": (self._last_run + timedelta(seconds=self.interval)).isoformat() 
                       if self._last_run and self._running else None,
            "last_result_summary": {
                "new_sources": self._last_result.get("new_sources_total", 0),
                "working_pct": self._last_result.get("audit_summary", {}).get("working_pct", 0)
            } if self._last_result else None
        }
    
    async def run_now(self) -> Dict:
        """Run discovery immediately (manual trigger)"""
        return await self._run_discovery()


# Global scheduler instance
_discovery_scheduler = None

def get_discovery_scheduler(db):
    global _discovery_scheduler
    if _discovery_scheduler is None:
        _discovery_scheduler = DiscoveryScheduler(db)
    return _discovery_scheduler
