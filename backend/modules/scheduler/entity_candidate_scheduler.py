"""
Entity Candidate Discovery Scheduler
=====================================

Periodically runs entity candidate discovery to find new entities
from articles, funding rounds, and other data sources.

Jobs:
1. entity_candidate_discovery (every 10 min) - Extract candidates from data
2. entity_candidate_validation (every 15 min) - Validate and promote candidates
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class EntityCandidateScheduler:
    """Scheduler for entity candidate discovery and validation"""
    
    def __init__(self, db, discovery_interval_minutes: int = 10, validation_interval_minutes: int = 15):
        self.db = db
        self.discovery_interval = discovery_interval_minutes * 60
        self.validation_interval = validation_interval_minutes * 60
        self._running = False
        self._discovery_task: Optional[asyncio.Task] = None
        self._validation_task: Optional[asyncio.Task] = None
        self._last_discovery_run: Optional[datetime] = None
        self._last_validation_run: Optional[datetime] = None
        self._discovery_count = 0
        self._validation_count = 0
        self._stats = {}
    
    async def _run_discovery(self):
        """Run a single discovery cycle"""
        from modules.knowledge_graph.entity_candidate_discovery import get_entity_candidate_discovery
        
        discovery = get_entity_candidate_discovery(self.db)
        
        try:
            result = await discovery.run_discovery_job()
            self._last_discovery_run = datetime.now(timezone.utc)
            self._discovery_count += 1
            self._stats["last_discovery"] = result
            
            total_discovered = (
                result.get("articles", {}).get("discovered", 0) +
                result.get("funding", {}).get("discovered", 0)
            )
            
            logger.info(f"[EntityCandidateScheduler] Discovery #{self._discovery_count}: "
                       f"Found {total_discovered} candidates")
            
            return result
        except Exception as e:
            logger.error(f"[EntityCandidateScheduler] Discovery error: {e}")
            return {"error": str(e)}
    
    async def _run_validation(self):
        """Run a single validation cycle"""
        from modules.knowledge_graph.entity_candidate_discovery import get_entity_candidate_discovery
        
        discovery = get_entity_candidate_discovery(self.db)
        
        try:
            result = await discovery.validate_candidates()
            self._last_validation_run = datetime.now(timezone.utc)
            self._validation_count += 1
            self._stats["last_validation"] = result
            
            logger.info(f"[EntityCandidateScheduler] Validation #{self._validation_count}: "
                       f"Approved {result.get('approved', 0)} candidates")
            
            # If entities were approved, run graph expansion
            if result.get("approved", 0) > 0:
                await self._run_graph_expansion()
            
            return result
        except Exception as e:
            logger.error(f"[EntityCandidateScheduler] Validation error: {e}")
            return {"error": str(e)}
    
    async def _run_graph_expansion(self):
        """Run graph expansion for newly approved entities"""
        from modules.knowledge_graph.graph_expansion_service import get_graph_expansion_service
        
        try:
            service = get_graph_expansion_service(self.db)
            result = await service.expand_new_entities()
            self._stats["last_expansion"] = result
            logger.info(f"[EntityCandidateScheduler] Graph expansion: {result.get('edges_created', 0)} edges created")
            return result
        except Exception as e:
            logger.error(f"[EntityCandidateScheduler] Expansion error: {e}")
            return {"error": str(e)}
    
    async def _run_alias_monitoring(self):
        """Run alias stability monitoring"""
        from modules.knowledge_graph.alias_stability_service import get_alias_stability_service
        
        try:
            service = get_alias_stability_service(self.db)
            report = await service.run_monitoring_job()
            self._stats["alias_health"] = {
                "score": report.get("health_score"),
                "is_healthy": report.get("is_healthy"),
                "conflicts": report.get("conflicts", {}).get("count", 0)
            }
            return report
        except Exception as e:
            logger.error(f"[EntityCandidateScheduler] Alias monitoring error: {e}")
            return {"error": str(e)}
    
    async def _run_materialization(self):
        """Run neighbor materialization"""
        from modules.knowledge_graph.neighbor_materialization_service import get_neighbor_materialization_service
        
        try:
            service = get_neighbor_materialization_service(self.db)
            result = await service.run_materialization_job()
            self._stats["last_materialization"] = {
                "materialized": result.get("hot_entities", {}).get("materialized", 0),
                "refreshed": result.get("stale_refresh", {}).get("refreshed", 0)
            }
            return result
        except Exception as e:
            logger.error(f"[EntityCandidateScheduler] Materialization error: {e}")
            return {"error": str(e)}
    
    async def _discovery_loop(self):
        """Discovery scheduler loop"""
        logger.info(f"[EntityCandidateScheduler] Discovery loop started (interval: {self.discovery_interval}s)")
        
        # Initial run
        await self._run_discovery()
        
        while self._running:
            try:
                await asyncio.sleep(self.discovery_interval)
                if self._running:
                    await self._run_discovery()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[EntityCandidateScheduler] Discovery loop error: {e}")
                await asyncio.sleep(60)
        
        logger.info("[EntityCandidateScheduler] Discovery loop stopped")
    
    async def _validation_loop(self):
        """Validation scheduler loop"""
        logger.info(f"[EntityCandidateScheduler] Validation loop started (interval: {self.validation_interval}s)")
        
        # Wait a bit before first run
        await asyncio.sleep(120)  # 2 min delay after discovery starts
        
        cycle = 0
        while self._running:
            try:
                cycle += 1
                
                if self._running:
                    # Always run validation
                    await self._run_validation()
                    
                    # Run alias monitoring every 3rd cycle (~45 min)
                    if cycle % 3 == 0:
                        await self._run_alias_monitoring()
                    
                    # Run materialization every 4th cycle (~60 min)
                    if cycle % 4 == 0:
                        await self._run_materialization()
                
                await asyncio.sleep(self.validation_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[EntityCandidateScheduler] Validation loop error: {e}")
                await asyncio.sleep(60)
        
        logger.info("[EntityCandidateScheduler] Validation loop stopped")
    
    async def start(self):
        """Start the scheduler"""
        if self._running:
            return {"status": "already_running"}
        
        # Initialize discovery engine
        from modules.knowledge_graph.entity_candidate_discovery import get_entity_candidate_discovery
        discovery = get_entity_candidate_discovery(self.db)
        await discovery.ensure_indexes()
        
        # Seed known entities if needed
        stats = await discovery.get_stats()
        if stats.get("total", 0) == 0:
            logger.info("[EntityCandidateScheduler] Seeding known entities...")
            await discovery.seed_known_entities()
        
        self._running = True
        self._discovery_task = asyncio.create_task(self._discovery_loop())
        self._validation_task = asyncio.create_task(self._validation_loop())
        
        return {
            "status": "started",
            "discovery_interval_minutes": self.discovery_interval // 60,
            "validation_interval_minutes": self.validation_interval // 60
        }
    
    def stop(self):
        """Stop the scheduler"""
        if not self._running:
            return {"status": "not_running"}
        
        self._running = False
        if self._discovery_task:
            self._discovery_task.cancel()
        if self._validation_task:
            self._validation_task.cancel()
        
        return {"status": "stopped"}
    
    def get_status(self) -> Dict:
        """Get scheduler status"""
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "running": self._running,
            "discovery": {
                "interval_minutes": self.discovery_interval // 60,
                "run_count": self._discovery_count,
                "last_run": self._last_discovery_run.isoformat() if self._last_discovery_run else None,
                "next_run": (self._last_discovery_run + timedelta(seconds=self.discovery_interval)).isoformat() 
                           if self._last_discovery_run and self._running else None
            },
            "validation": {
                "interval_minutes": self.validation_interval // 60,
                "run_count": self._validation_count,
                "last_run": self._last_validation_run.isoformat() if self._last_validation_run else None,
                "next_run": (self._last_validation_run + timedelta(seconds=self.validation_interval)).isoformat() 
                           if self._last_validation_run and self._running else None
            },
            "stats": self._stats
        }
    
    async def run_discovery_now(self) -> Dict:
        """Run discovery immediately (manual trigger)"""
        return await self._run_discovery()
    
    async def run_validation_now(self) -> Dict:
        """Run validation immediately (manual trigger)"""
        return await self._run_validation()


# Global scheduler instance
_entity_candidate_scheduler = None


def get_entity_candidate_scheduler(db):
    global _entity_candidate_scheduler
    if _entity_candidate_scheduler is None:
        _entity_candidate_scheduler = EntityCandidateScheduler(db)
    return _entity_candidate_scheduler
