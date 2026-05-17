"""
Data Sync Scheduler v2
======================
Tier-ordered scheduler with health monitoring and fail score tracking.

Execution Order: T1 → T2 → T3 → T4 (strictly sequential by tier)
Within tier: parallel execution allowed

Features:
- Tier-ordered job execution (never T2 before T1)
- Source fail_score tracking
- Health monitoring with auto-pause
- Skip logic for failed sources
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

logger = logging.getLogger(__name__)

# TIER intervals in minutes
TIER_INTERVALS = {
    1: 10,   # Core Data
    2: 15,   # Token/Market  
    3: 30,   # Activities
    4: 180,  # Research
}

# Health thresholds
FAIL_THRESHOLD = 3          # Pause after N consecutive fails
PAUSE_DURATION_MIN = 60     # Pause duration in minutes
HEALTH_SCORE_MIN = 0.3      # Minimum health score before pause


@dataclass
class SourceHealth:
    """Health tracking for a data source"""
    source_id: str
    success_count: int = 0
    fail_count: int = 0
    consecutive_fails: int = 0
    last_success: Optional[datetime] = None
    last_fail: Optional[datetime] = None
    last_error: Optional[str] = None
    is_paused: bool = False
    pause_until: Optional[datetime] = None
    
    @property
    def total_runs(self) -> int:
        return self.success_count + self.fail_count
    
    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 1.0
        return self.success_count / self.total_runs
    
    @property
    def health_score(self) -> float:
        """
        Calculate health score 0-1
        Based on success rate and recent fails
        """
        if self.total_runs == 0:
            return 1.0
        
        base_score = self.success_rate
        
        # Penalize consecutive fails
        if self.consecutive_fails > 0:
            penalty = min(0.3, self.consecutive_fails * 0.1)
            base_score -= penalty
        
        return max(0, min(1, base_score))
    
    def record_success(self):
        self.success_count += 1
        self._was_failing = self.consecutive_fails > 0  # Track if was failing
        self.consecutive_fails = 0
        self.last_success = datetime.now(timezone.utc)
        self.is_paused = False
        self.pause_until = None
    
    def record_fail(self, error: str = None):
        self.fail_count += 1
        self.consecutive_fails += 1
        self.last_fail = datetime.now(timezone.utc)
        self.last_error = error[:200] if error else None
        
        # Auto-pause if too many consecutive fails
        if self.consecutive_fails >= FAIL_THRESHOLD:
            self.pause(PAUSE_DURATION_MIN)
    
    def pause(self, minutes: int):
        self.is_paused = True
        self.pause_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        logger.warning(f"[Health] Source {self.source_id} paused for {minutes} minutes")
    
    def check_pause(self) -> bool:
        """Check if source is still paused"""
        if not self.is_paused:
            return False
        
        if self.pause_until and datetime.now(timezone.utc) > self.pause_until:
            self.is_paused = False
            self.pause_until = None
            self.consecutive_fails = 0  # Reset on unpause
            logger.info(f"[Health] Source {self.source_id} unpaused")
            return False
        
        return True
    
    def to_dict(self) -> Dict:
        return {
            "source_id": self.source_id,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "consecutive_fails": self.consecutive_fails,
            "success_rate": round(self.success_rate, 2),
            "health_score": round(self.health_score, 2),
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_fail": self.last_fail.isoformat() if self.last_fail else None,
            "last_error": self.last_error,
            "is_paused": self.is_paused,
            "pause_until": self.pause_until.isoformat() if self.pause_until else None
        }


@dataclass
class TierJob:
    """Job definition with tier info"""
    id: str
    name: str
    tier: int
    source_id: str
    func: Callable
    priority_score: int = 0
    enabled: bool = True


class TierOrderedScheduler:
    """
    Scheduler that executes jobs strictly by tier order.
    T1 → T2 → T3 → T4
    """
    
    def __init__(self, db):
        self.db = db
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._running = False
        self._tier_jobs: Dict[int, List[TierJob]] = {1: [], 2: [], 3: [], 4: []}
        self._source_health: Dict[str, SourceHealth] = {}
        self._last_tier_run: Dict[int, datetime] = {}
        self._execution_lock = asyncio.Lock()
        self._telegram = None  # Telegram integration
        
        # Register event listeners
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
    
    def _get_telegram(self):
        """Lazy load telegram integration"""
        if self._telegram is None:
            from modules.scheduler.telegram_integration import get_telegram_integration
            self._telegram = get_telegram_integration(self.db)
        return self._telegram
    
    def _get_health(self, source_id: str) -> SourceHealth:
        """Get or create health tracker for source"""
        if source_id not in self._source_health:
            self._source_health[source_id] = SourceHealth(source_id=source_id)
        return self._source_health[source_id]
    
    def _on_job_executed(self, event):
        """Track successful job execution"""
        job_id = event.job_id
        # Extract source_id from job_id (e.g., "tier1_cryptorank" -> "cryptorank")
        parts = job_id.split("_", 1)
        source_id = parts[1] if len(parts) > 1 else job_id
        
        health = self._get_health(source_id)
        was_failing = getattr(health, '_was_failing', False)
        health.record_success()
        
        logger.info(f"[SYNC] ✓ {job_id} completed (health: {health.health_score:.2f})")
        
        # Send recovery alert if source was failing before
        if was_failing:
            import asyncio
            try:
                telegram = self._get_telegram()
                asyncio.create_task(telegram.on_source_recovered(source_id))
            except Exception as e:
                logger.error(f"[SYNC] Failed to send recovery alert: {e}")
    
    def _on_job_error(self, event):
        """Track failed job execution"""
        job_id = event.job_id
        parts = job_id.split("_", 1)
        source_id = parts[1] if len(parts) > 1 else job_id
        
        health = self._get_health(source_id)
        was_paused = health.is_paused
        health.record_fail(str(event.exception))
        
        logger.error(f"[SYNC] ✗ {job_id} failed (consecutive: {health.consecutive_fails}, health: {health.health_score:.2f})")
        
        # Send alerts via Telegram
        import asyncio
        try:
            telegram = self._get_telegram()
            
            # Send parser_failed on first fail
            if health.consecutive_fails == 1:
                asyncio.create_task(telegram.on_parser_failed(source_id, str(event.exception)))
            
            # Send source_down when auto-paused
            if health.is_paused and not was_paused:
                asyncio.create_task(telegram.on_source_down(
                    source_id, 
                    health.consecutive_fails,
                    str(event.exception)
                ))
        except Exception as e:
            logger.error(f"[SYNC] Failed to send failure alert: {e}")
    
    async def _run_tier(self, tier: int):
        """
        Run all jobs for a tier in parallel.
        Skip paused sources.
        """
        jobs = self._tier_jobs.get(tier, [])
        if not jobs:
            return
        
        logger.info(f"[SYNC] Starting TIER {tier} ({len(jobs)} sources)")
        
        tasks = []
        for job in sorted(jobs, key=lambda j: -j.priority_score):
            if not job.enabled:
                continue
            
            health = self._get_health(job.source_id)
            
            # Skip if paused
            if health.check_pause():
                logger.info(f"[SYNC] Skipping {job.source_id} (paused until {health.pause_until})")
                continue
            
            # Skip if health too low
            if health.health_score < HEALTH_SCORE_MIN:
                logger.warning(f"[SYNC] Skipping {job.source_id} (health: {health.health_score:.2f} < {HEALTH_SCORE_MIN})")
                continue
            
            tasks.append(self._run_job_safe(job))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self._last_tier_run[tier] = datetime.now(timezone.utc)
        logger.info(f"[SYNC] Completed TIER {tier}")
    
    async def _run_job_safe(self, job: TierJob):
        """Run a job with error handling"""
        try:
            logger.info(f"[SYNC] T{job.tier} {job.source_id}")
            await job.func()
            health = self._get_health(job.source_id)
            health.record_success()
        except Exception as e:
            health = self._get_health(job.source_id)
            health.record_fail(str(e))
            logger.error(f"[SYNC] T{job.tier} {job.source_id} error: {e}")
    
    async def _tier_sync_cycle(self):
        """
        Main sync cycle - runs tiers in strict order.
        T1 → T2 → T3 → T4
        """
        async with self._execution_lock:
            now = datetime.now(timezone.utc)
            
            # Check each tier
            for tier in [1, 2, 3, 4]:
                interval_min = TIER_INTERVALS[tier]
                last_run = self._last_tier_run.get(tier)
                
                # Run if never run or interval passed
                should_run = (
                    last_run is None or 
                    (now - last_run).total_seconds() >= interval_min * 60
                )
                
                if should_run:
                    await self._run_tier(tier)
    
    # ─────────────────────────────────────────────────────────────
    # Parser functions
    # ─────────────────────────────────────────────────────────────
    
    async def _run_coingecko_sync(self):
        from modules.parsers.parser_coingecko import sync_coingecko_data
        await sync_coingecko_data(self.db, full=False)
    
    async def _run_cryptorank_sync(self):
        from modules.parsers.parser_cryptorank import sync_cryptorank_data
        await sync_cryptorank_data(self.db)
    
    async def _run_defillama_sync(self):
        from modules.parsers.parser_defillama import sync_defillama_data
        await sync_defillama_data(self.db, limit=100)
    
    async def _run_tokenunlocks_sync(self):
        from modules.parsers.parser_tokenunlocks import sync_tokenunlocks_data
        await sync_tokenunlocks_data(self.db)
    
    async def _run_messari_sync(self):
        from modules.parsers.parser_messari import sync_messari_data
        await sync_messari_data(self.db, limit=50)
    
    async def _run_activities_sync(self):
        from modules.parsers.parser_activities import sync_activities_data
        await sync_activities_data(self.db)
    
    async def _run_rootdata_sync(self):
        """RootData sync - funding, investors, projects"""
        from modules.parsers.parser_rootdata import sync_rootdata_data
        await sync_rootdata_data(self.db, limit=50)
    
    async def _run_instruments_sync(self):
        """Sync exchange instruments using InstrumentRegistry.sync_all()"""
        from modules.market_data.services.instrument_registry import instrument_registry
        try:
            await instrument_registry.sync_all(force=True)
        except Exception as e:
            logger.error(f"Instruments sync error: {e}")
    
    # ─────────────────────────────────────────────────────────────
    # TIER 3: Activities Parsers
    # ─────────────────────────────────────────────────────────────
    
    async def _run_dropsearn_sync(self):
        """DropsEarn - airdrop campaigns"""
        from modules.parsers.parser_dropsearn import sync_dropsearn_data
        await sync_dropsearn_data(self.db, limit=50)
    
    async def _run_icodrops_sync(self):
        """ICO Drops - ICO calendar"""
        from modules.parsers.parser_icodrops import sync_icodrops_data
        await sync_icodrops_data(self.db, limit=50)
    
    async def _run_dappradar_sync(self):
        """DappRadar - DApp rankings"""
        from modules.parsers.parser_dappradar import sync_dappradar_data
        await sync_dappradar_data(self.db, limit=50)
    
    async def _run_airdropalert_sync(self):
        """AirdropAlert - airdrop alerts"""
        from modules.parsers.parser_airdropalert import sync_airdropalert_data
        await sync_airdropalert_data(self.db)
    
    async def _run_github_sync(self):
        """GitHub - developer activity, contributors"""
        from modules.parsers.parser_github import sync_github_data
        await sync_github_data(self.db, batch_size=5)
    
    def setup_tier_jobs(self):
        """
        Setup jobs organized by tier.
        Jobs within same tier can run in parallel.
        Tiers execute sequentially: T1 → T2 → T3 → T4
        """
        # ═══════════════════════════════════════════════════════════════
        # TIER 1: CORE DATA (every 10 min)
        # ═══════════════════════════════════════════════════════════════
        self._tier_jobs[1] = [
            TierJob(
                id="tier1_cryptorank",
                name="[T1] CryptoRank - Core Data",
                tier=1,
                source_id="cryptorank",
                func=self._run_cryptorank_sync,
                priority_score=100
            ),
            TierJob(
                id="tier1_rootdata",
                name="[T1] RootData - Core Data",
                tier=1,
                source_id="rootdata",
                func=self._run_rootdata_sync,
                priority_score=95
            ),
            TierJob(
                id="tier1_defillama",
                name="[T1] DefiLlama - Core Data",
                tier=1,
                source_id="defillama",
                func=self._run_defillama_sync,
                priority_score=90
            ),
            TierJob(
                id="tier1_dropstab",
                name="[T1] Dropstab - Core Data",
                tier=1,
                source_id="dropstab",
                func=self._run_activities_sync,
                priority_score=85
            ),
        ]
        
        # ═══════════════════════════════════════════════════════════════
        # TIER 2: TOKEN / MARKET DATA (every 15 min)
        # ═══════════════════════════════════════════════════════════════
        self._tier_jobs[2] = [
            TierJob(
                id="tier2_coingecko",
                name="[T2] CoinGecko - Market Data",
                tier=2,
                source_id="coingecko",
                func=self._run_coingecko_sync,
                priority_score=80
            ),
            TierJob(
                id="tier2_tokenunlocks",
                name="[T2] TokenUnlocks - Market Data",
                tier=2,
                source_id="tokenunlocks",
                func=self._run_tokenunlocks_sync,
                priority_score=70
            ),
        ]
        
        # ═══════════════════════════════════════════════════════════════
        # TIER 3: ACTIVITIES (every 30 min)
        # DropsEarn, ICO Drops, DappRadar, AirdropAlert
        # ═══════════════════════════════════════════════════════════════
        self._tier_jobs[3] = [
            TierJob(
                id="tier3_dropsearn",
                name="[T3] DropsEarn - Activities",
                tier=3,
                source_id="dropsearn",
                func=self._run_dropsearn_sync,
                priority_score=60
            ),
            TierJob(
                id="tier3_icodrops",
                name="[T3] ICO Drops - Activities",
                tier=3,
                source_id="icodrops",
                func=self._run_icodrops_sync,
                priority_score=55
            ),
            TierJob(
                id="tier3_dappradar",
                name="[T3] DappRadar - Activities",
                tier=3,
                source_id="dappradar",
                func=self._run_dappradar_sync,
                priority_score=50
            ),
            TierJob(
                id="tier3_airdropalert",
                name="[T3] AirdropAlert - Activities",
                tier=3,
                source_id="airdropalert",
                func=self._run_airdropalert_sync,
                priority_score=45
            ),
            TierJob(
                id="tier3_github",
                name="[T3] GitHub - Developer Activity",
                tier=3,
                source_id="github",
                func=self._run_github_sync,
                priority_score=42
            ),
            TierJob(
                id="tier3_instruments",
                name="[T3] Exchange Instruments",
                tier=3,
                source_id="instruments",
                func=self._run_instruments_sync,
                priority_score=40
            ),
        ]
        
        # ═══════════════════════════════════════════════════════════════
        # TIER 4: RESEARCH (every 3 hours - skip if no API)
        # ═══════════════════════════════════════════════════════════════
        self._tier_jobs[4] = [
            TierJob(
                id="tier4_messari",
                name="[T4] Messari - Research",
                tier=4,
                source_id="messari",
                func=self._run_messari_sync,
                priority_score=30
            ),
        ]
        
        total_jobs = sum(len(jobs) for jobs in self._tier_jobs.values())
        logger.info(f"[Scheduler] Setup {total_jobs} tier-ordered jobs")
        logger.info(f"[Scheduler] T1: {len(self._tier_jobs[1])}, T2: {len(self._tier_jobs[2])}, T3: {len(self._tier_jobs[3])}, T4: {len(self._tier_jobs[4])}")
    
    def _setup_master_scheduler(self):
        """Setup master scheduler that triggers tier sync cycle"""
        # Run tier cycle every 5 minutes (will check intervals internally)
        self.scheduler.add_job(
            self._tier_sync_cycle,
            trigger=IntervalTrigger(minutes=5),
            id="master_tier_cycle",
            name="Master Tier Cycle",
            replace_existing=True
        )
    
    def start(self):
        """Start the scheduler"""
        if not self._running:
            self.setup_tier_jobs()
            self._setup_master_scheduler()
            self.scheduler.start()
            self._running = True
            logger.info("[Scheduler] Started with tier-ordered execution")
            
            # Run initial sync
            asyncio.create_task(self._tier_sync_cycle())
    
    def stop(self):
        """Stop the scheduler"""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("[Scheduler] Stopped")
    
    def pause_source(self, source_id: str, minutes: int = 60):
        """Manually pause a source"""
        health = self._get_health(source_id)
        health.pause(minutes)
    
    def unpause_source(self, source_id: str):
        """Manually unpause a source"""
        health = self._get_health(source_id)
        health.is_paused = False
        health.pause_until = None
        health.consecutive_fails = 0
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status for all sources"""
        return {
            source_id: health.to_dict() 
            for source_id, health in self._source_health.items()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get full scheduler status"""
        jobs = []
        for tier, tier_jobs in self._tier_jobs.items():
            for job in tier_jobs:
                health = self._get_health(job.source_id)
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "tier": tier,
                    "source_id": job.source_id,
                    "priority_score": job.priority_score,
                    "enabled": job.enabled,
                    "health_score": round(health.health_score, 2),
                    "is_paused": health.is_paused,
                    "consecutive_fails": health.consecutive_fails,
                    "last_run": self._last_tier_run.get(tier, None)
                })
        
        return {
            "running": self._running,
            "job_count": len(jobs),
            "tier_intervals": TIER_INTERVALS,
            "jobs": sorted(jobs, key=lambda j: (j["tier"], -j["priority_score"])),
            "health": self.get_health_status(),
            "last_tier_runs": {
                tier: run.isoformat() if run else None 
                for tier, run in self._last_tier_run.items()
            }
        }


# ═══════════════════════════════════════════════════════════════
# Legacy compatibility layer
# ═══════════════════════════════════════════════════════════════

class DataSyncScheduler(TierOrderedScheduler):
    """Legacy alias for backward compatibility"""
    
    def setup_default_jobs(self):
        """Legacy method - calls new setup"""
        self.setup_tier_jobs()
        self._setup_master_scheduler()


# Global scheduler instance
_scheduler: Optional[TierOrderedScheduler] = None


def get_scheduler(db) -> TierOrderedScheduler:
    """Get or create scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TierOrderedScheduler(db)
    return _scheduler


def init_scheduler(db, auto_start: bool = False):
    """Initialize and optionally start scheduler"""
    scheduler = get_scheduler(db)
    if auto_start:
        scheduler.start()
    return scheduler
