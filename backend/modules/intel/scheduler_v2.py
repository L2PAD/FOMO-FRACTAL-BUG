"""
Intel Scheduler v2 - SOURCE BASED Architecture

Правильный подход:
- Scraper собирает ВСЁ из источника
- Parser определяет тип данных
- Pipeline обрабатывает unified schema
- Post-pipeline: Dedup → Entity Resolution → Event Building → Confidence

Jobs:
- dropstab_full_sync → все данные из Dropstab
- cryptorank_full_sync → все данные из CryptoRank  
- coingecko_sync → все данные из CoinGecko
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


@dataclass
class SourceSyncJob:
    """Source-based sync job"""
    name: str
    source: str
    interval_minutes: int
    priority: int = 0
    enabled: bool = True
    last_run: Optional[datetime] = None
    last_status: SyncStatus = SyncStatus.IDLE
    last_result: Optional[Dict] = None
    last_error: Optional[str] = None
    run_count: int = 0
    error_count: int = 0
    entities_synced: List[str] = None  # Parser determines these
    
    def __post_init__(self):
        if self.entities_synced is None:
            self.entities_synced = []


class IntelSchedulerV2:
    """
    Source-based scheduler.
    
    Architecture:
    SOURCE → SCRAPER → RAW → PARSER → NORMALIZED → DEDUP → CURATED
    
    Scraper is DUMB (just collects)
    Parser is SMART (determines data types)
    """
    
    def __init__(self, db=None):
        self.db = db
        self.running = False
        self._task: Optional[asyncio.Task] = None
        
        # SOURCE-BASED JOBS (not entity-based!)
        self.jobs: Dict[str, SourceSyncJob] = {
            # ═══════════════════════════════════════════════════════════════
            # COINGECKO - API based, always available
            # Collects: prices, mcap, volume, categories, trending
            # ═══════════════════════════════════════════════════════════════
            "coingecko_full": SourceSyncJob(
                name="CoinGecko Full Sync",
                source="coingecko",
                interval_minutes=30,  # Every 30 min
                priority=0,
                enabled=True
            ),
            
            # ═══════════════════════════════════════════════════════════════
            # DROPSTAB - Browser scraper, collects ALL endpoints
            # Parser will detect: unlocks, funding, investors, markets
            # ═══════════════════════════════════════════════════════════════
            "dropstab_full": SourceSyncJob(
                name="Dropstab Full Sync",
                source="dropstab",
                interval_minutes=60,  # Every 1h
                priority=1,
                enabled=False  # Requires browser
            ),
            
            # ═══════════════════════════════════════════════════════════════
            # CRYPTORANK - Browser scraper, collects ALL endpoints
            # Parser will detect: fundraising, unlocks, investors, sales
            # ═══════════════════════════════════════════════════════════════
            "cryptorank_full": SourceSyncJob(
                name="CryptoRank Full Sync",
                source="cryptorank",
                interval_minutes=60,  # Every 1h
                priority=2,
                enabled=False  # Requires browser
            ),
        }
    
    async def _sync_coingecko(self) -> Dict[str, Any]:
        """
        Sync ALL data from CoinGecko.
        Parser determines entity types from response structure.
        """
        from modules.intel.sources.coingecko.sync import CoinGeckoSync
        sync = CoinGeckoSync(self.db)
        
        results = {
            "source": "coingecko",
            "entities": {},
            "total_synced": 0,
            "errors": []
        }
        
        # Collect ALL endpoints
        endpoints = [
            ("markets", lambda: sync.sync_top_coins(limit=250)),
            ("categories", lambda: sync.sync_categories()),
            ("trending", lambda: sync.sync_trending()),
            ("global", lambda: sync.sync_global()),
        ]
        
        for entity, sync_func in endpoints:
            try:
                result = await sync_func()
                count = result.get("synced", result.get("count", 0))
                results["entities"][entity] = {
                    "status": "ok",
                    "count": count
                }
                results["total_synced"] += count if isinstance(count, int) else 0
            except Exception as e:
                results["entities"][entity] = {
                    "status": "error",
                    "error": str(e)
                }
                results["errors"].append(f"{entity}: {str(e)}")
        
        return results
    
    async def _sync_dropstab(self) -> Dict[str, Any]:
        """
        Sync ALL data from Dropstab using browser discovery.
        Scraper discovers all API endpoints, Parser categorizes them.
        """
        from modules.intel.scraper_engine import scraper_engine
        
        results = {
            "source": "dropstab",
            "entities": {},
            "total_synced": 0,
            "errors": [],
            "discovered_endpoints": []
        }
        
        try:
            # Step 1: Discovery - find ALL endpoints
            discovery = await scraper_engine.discover_source("dropstab")
            endpoints = discovery.get("endpoints", [])
            results["discovered_endpoints"] = [e.get("url", e.get("target")) for e in endpoints]
            
            # Step 2: Scrape ALL discovered endpoints
            for endpoint in endpoints:
                target = endpoint.get("target", "unknown")
                try:
                    # Scrape and save to raw
                    raw_result = await scraper_engine.scrape_endpoint(
                        source="dropstab",
                        endpoint=endpoint
                    )
                    
                    count = raw_result.get("records", 0)
                    results["entities"][target] = {
                        "status": "ok",
                        "count": count
                    }
                    results["total_synced"] += count if isinstance(count, int) else 0
                    
                except Exception as e:
                    results["entities"][target] = {
                        "status": "error",
                        "error": str(e)
                    }
                    results["errors"].append(f"{target}: {str(e)}")
            
            # Step 3: Run parser on raw data
            # Parser will automatically detect entity types
            from modules.intel.parser import intel_parser
            parse_result = await intel_parser.parse_source("dropstab")
            results["parsed"] = parse_result
            
        except Exception as e:
            results["errors"].append(f"Discovery failed: {str(e)}")
        
        return results
    
    async def _sync_cryptorank(self) -> Dict[str, Any]:
        """
        Sync ALL data from CryptoRank using browser discovery.
        Same approach as Dropstab.
        """
        from modules.intel.scraper_engine import scraper_engine
        
        results = {
            "source": "cryptorank",
            "entities": {},
            "total_synced": 0,
            "errors": [],
            "discovered_endpoints": []
        }
        
        try:
            # Step 1: Discovery - find ALL endpoints
            discovery = await scraper_engine.discover_source("cryptorank")
            endpoints = discovery.get("endpoints", [])
            results["discovered_endpoints"] = [e.get("url", e.get("target")) for e in endpoints]
            
            # Step 2: Scrape ALL discovered endpoints
            for endpoint in endpoints:
                target = endpoint.get("target", "unknown")
                try:
                    raw_result = await scraper_engine.scrape_endpoint(
                        source="cryptorank",
                        endpoint=endpoint
                    )
                    
                    count = raw_result.get("records", 0)
                    results["entities"][target] = {
                        "status": "ok",
                        "count": count
                    }
                    results["total_synced"] += count if isinstance(count, int) else 0
                    
                except Exception as e:
                    results["entities"][target] = {
                        "status": "error",
                        "error": str(e)
                    }
                    results["errors"].append(f"{target}: {str(e)}")
            
            # Step 3: Run parser
            from modules.intel.parser import intel_parser
            parse_result = await intel_parser.parse_source("cryptorank")
            results["parsed"] = parse_result
            
        except Exception as e:
            results["errors"].append(f"Discovery failed: {str(e)}")
        
        return results
    
    async def _run_post_pipeline(self, source: str) -> Dict[str, Any]:
        """
        Post-sync pipeline: Dedup → Entity Resolution → Event Building → Consistency Check.
        Runs automatically after each source sync completes.
        """
        pipeline_start = time.time()
        results = {
            "source": source,
            "dedupe": None,
            "entity_resolution": None,
            "event_building": None,
            "consistency": None,
            "errors": []
        }
        
        # Step 1: Deduplication
        try:
            from modules.intel.normalization import create_normalization_engine
            engine = create_normalization_engine(self.db)
            dedup_result = await engine.run_full_pipeline()
            results["dedupe"] = dedup_result
            logger.info(f"[PostPipeline] Dedup complete: {dedup_result}")
        except Exception as e:
            results["errors"].append(f"dedupe: {str(e)}")
            logger.error(f"[PostPipeline] Dedup failed: {e}")
        
        # Step 2: Entity Resolution - resolve entities from normalized data
        try:
            from modules.intel.engine.entity_intelligence import init_entity_engine, entity_engine
            if entity_engine is None:
                init_entity_engine(self.db)
            from modules.intel.engine.entity_intelligence import entity_engine as ent_engine
            
            resolved_count = 0
            # Resolve entities from normalized investors
            cursor = self.db.normalized_investors.find(
                {"entity_id": {"$exists": False}}, {"_id": 0}
            ).limit(500)
            async for record in cursor:
                name = record.get("name", "")
                if name:
                    match = await ent_engine.resolve(name, source=source)
                    await self.db.normalized_investors.update_one(
                        {"id": record.get("id")},
                        {"$set": {"entity_id": match.entity_id}}
                    )
                    resolved_count += 1
            
            # Resolve entities from normalized funding
            cursor = self.db.normalized_funding.find(
                {"entity_id": {"$exists": False}}, {"_id": 0}
            ).limit(500)
            async for record in cursor:
                name = record.get("project", "") or record.get("symbol", "")
                symbol = record.get("symbol")
                if name:
                    match = await ent_engine.resolve(name, symbol=symbol, source=source)
                    await self.db.normalized_funding.update_one(
                        {"id": record.get("id")},
                        {"$set": {"entity_id": match.entity_id}}
                    )
                    resolved_count += 1
            
            results["entity_resolution"] = {"resolved": resolved_count}
            logger.info(f"[PostPipeline] Entity resolution: {resolved_count} resolved")
        except Exception as e:
            results["errors"].append(f"entity_resolution: {str(e)}")
            logger.error(f"[PostPipeline] Entity resolution failed: {e}")
        
        # Step 3: Event Building
        try:
            from modules.intel.engine.event_intelligence import init_event_engine, event_engine
            if event_engine is None:
                init_event_engine(self.db)
            from modules.intel.engine.event_intelligence import event_engine as evt_engine
            
            event_result = await evt_engine.process_all_events()
            results["event_building"] = event_result
            logger.info(f"[PostPipeline] Events built: {event_result}")
        except Exception as e:
            results["errors"].append(f"event_building: {str(e)}")
            logger.error(f"[PostPipeline] Event building failed: {e}")
        
        # Step 4: Consistency / Drift Check
        try:
            from modules.intel.engine.consistency_engine import DataConsistencyEngine
            consistency_engine = DataConsistencyEngine(self.db)
            checks = await consistency_engine.run_all_checks()
            health = consistency_engine.get_health_status()
            results["consistency"] = {
                "status": health.get("status"),
                "total_checks": health.get("total_checks"),
                "passed": health.get("passed"),
                "warnings": health.get("warnings"),
                "failures": health.get("failures")
            }
            logger.info(f"[PostPipeline] Consistency: {results['consistency']}")
        except Exception as e:
            results["errors"].append(f"consistency: {str(e)}")
            logger.error(f"[PostPipeline] Consistency check failed: {e}")
        
        elapsed = time.time() - pipeline_start
        results["elapsed_sec"] = round(elapsed, 1)
        logger.info(f"[PostPipeline] Complete for {source} in {elapsed:.1f}s")
        
        return results
    
    async def _run_job(self, job: SourceSyncJob) -> Dict[str, Any]:
        """Execute source sync job + post-pipeline"""
        logger.info(f"[SchedulerV2] Running: {job.name}")
        job.last_status = SyncStatus.RUNNING
        
        try:
            # Route to appropriate sync method
            if job.source == "coingecko":
                result = await self._sync_coingecko()
            elif job.source == "dropstab":
                result = await self._sync_dropstab()
            elif job.source == "cryptorank":
                result = await self._sync_cryptorank()
            else:
                result = {"error": f"Unknown source: {job.source}"}
            
            # Run post-processing pipeline after successful sync
            if not result.get("error") and result.get("total_synced", 0) > 0:
                try:
                    pipeline_result = await self._run_post_pipeline(job.source)
                    result["post_pipeline"] = pipeline_result
                except Exception as e:
                    logger.error(f"[SchedulerV2] Post-pipeline failed for {job.source}: {e}")
                    result["post_pipeline_error"] = str(e)
            
            # Update job status
            job.last_run = datetime.now(timezone.utc)
            job.last_result = result
            job.last_status = SyncStatus.SUCCESS if not result.get("errors") else SyncStatus.FAILED
            job.run_count += 1
            job.entities_synced = list(result.get("entities", {}).keys())
            job.last_error = None if not result.get("errors") else "; ".join(result["errors"])
            
            logger.info(f"[SchedulerV2] Completed: {job.name} - synced {result.get('total_synced', 0)} records")
            return result
            
        except Exception as e:
            job.last_status = SyncStatus.FAILED
            job.last_error = str(e)
            job.error_count += 1
            
            if "429" in str(e) or "rate" in str(e).lower():
                job.last_status = SyncStatus.RATE_LIMITED
            
            logger.error(f"[SchedulerV2] Failed: {job.name} - {e}")
            return {"error": str(e)}
    
    def _should_run(self, job: SourceSyncJob) -> bool:
        """Check if job should run based on interval"""
        if not job.enabled:
            return False
        
        if job.last_run is None:
            return True
        
        next_run = job.last_run + timedelta(minutes=job.interval_minutes)
        return datetime.now(timezone.utc) >= next_run
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        logger.info("[SchedulerV2] Starting source-based scheduler loop...")
        
        while self.running:
            try:
                # Get jobs that should run
                due_jobs = [
                    job for job in self.jobs.values()
                    if self._should_run(job)
                ]
                due_jobs.sort(key=lambda j: j.priority)
                
                for job in due_jobs:
                    if not self.running:
                        break
                    
                    await self._run_job(job)
                    await asyncio.sleep(5)  # Delay between sources
                
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[SchedulerV2] Loop error: {e}")
                await asyncio.sleep(60)
        
        logger.info("[SchedulerV2] Scheduler loop stopped")
    
    async def start(self) -> Dict[str, Any]:
        """Start the scheduler"""
        if self.running:
            return {"status": "already_running"}
        
        self.running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        
        logger.info("[SchedulerV2] Started - SOURCE BASED architecture")
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "status": "started",
            "architecture": "source_based",
            "jobs": {
                name: {
                    "name": job.name,
                    "source": job.source,
                    "interval_minutes": job.interval_minutes,
                    "enabled": job.enabled
                }
                for name, job in self.jobs.items()
            }
        }
    
    async def stop(self) -> Dict[str, Any]:
        """Stop the scheduler"""
        if not self.running:
            return {"status": "not_running"}
        
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("[SchedulerV2] Stopped")
        return {"status": "stopped"}
    
    async def run_source(self, source: str) -> Dict[str, Any]:
        """Run sync for specific source immediately"""
        job_name = f"{source}_full"
        if job_name not in self.jobs:
            # Find job by source
            for name, job in self.jobs.items():
                if job.source == source:
                    return await self._run_job(job)
            return {"error": f"Unknown source: {source}"}
        
        return await self._run_job(self.jobs[job_name])
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "running": self.running,
            "architecture": "source_based",
            "jobs": {
                name: {
                    "name": job.name,
                    "source": job.source,
                    "interval_minutes": job.interval_minutes,
                    "enabled": job.enabled,
                    "status": job.last_status.value,
                    "last_run": job.last_run.isoformat() if job.last_run else None,
                    "run_count": job.run_count,
                    "error_count": job.error_count,
                    "entities_synced": job.entities_synced,
                    "last_error": job.last_error
                }
                for name, job in self.jobs.items()
            }
        }
    
    def enable_source(self, source: str) -> Dict[str, Any]:
        """Enable sync for a source"""
        for name, job in self.jobs.items():
            if job.source == source:
                job.enabled = True
                return {"source": source, "enabled": True}
        return {"error": f"Unknown source: {source}"}
    
    def disable_source(self, source: str) -> Dict[str, Any]:
        """Disable sync for a source"""
        for name, job in self.jobs.items():
            if job.source == source:
                job.enabled = False
                return {"source": source, "enabled": False}
        return {"error": f"Unknown source: {source}"}


# Singleton instance
scheduler_v2: Optional[IntelSchedulerV2] = None


def init_scheduler_v2(db):
    """Initialize source-based scheduler"""
    global scheduler_v2
    scheduler_v2 = IntelSchedulerV2(db)
    return scheduler_v2
