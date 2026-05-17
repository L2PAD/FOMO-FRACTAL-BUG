"""
Intelligence Scheduler
======================

Scheduled jobs for intelligence engine:
- Momentum update (every 30 min)
- Projection updates (every 15 min)
- Narrative linking (every hour)
- Graph growth snapshot (every 6 hours)
- Momentum alerts check (every 15 min)
- Entity discovery (every hour)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class IntelligenceScheduler:
    """
    Scheduler for intelligence engine jobs.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._running = False
    
    async def _update_momentum(self):
        """Update entity momentum scores"""
        try:
            from modules.intelligence.entity_momentum import get_momentum_engine
            engine = get_momentum_engine(self.db)
            
            result = await engine.update_all_entities(limit=300)
            logger.info(f"[IntelScheduler] Momentum update: {result.get('processed', 0)} entities")
        except Exception as e:
            logger.error(f"[IntelScheduler] Momentum update failed: {e}")
    
    async def _update_projections(self):
        """Update projection layer"""
        try:
            from modules.intelligence.compute_separation import get_projection_layer
            layer = get_projection_layer(self.db)
            
            # Feed projection
            feed_count = await layer.update_feed_projection(limit=100)
            
            # Momentum projection
            momentum_result = await layer.update_momentum_projection()
            
            # Narrative projection
            narrative_count = await layer.update_narrative_projection()
            
            logger.info(f"[IntelScheduler] Projections updated: {feed_count} feed, {narrative_count} narratives")
        except Exception as e:
            logger.error(f"[IntelScheduler] Projection update failed: {e}")
    
    async def _link_narratives(self):
        """Auto-link entities to narratives"""
        try:
            from modules.intelligence.narrative_entity_linking import get_narrative_entity_linker
            linker = get_narrative_entity_linker(self.db)
            
            result = await linker.batch_link_entities(limit=100)
            logger.info(f"[IntelScheduler] Narrative linking: {result.get('links_created', 0)} new links")
        except Exception as e:
            logger.error(f"[IntelScheduler] Narrative linking failed: {e}")
    
    async def _capture_graph_growth(self):
        """Capture graph growth snapshot"""
        try:
            from modules.intelligence.graph_growth_monitor import get_graph_growth_monitor
            monitor = get_graph_growth_monitor(self.db)
            
            snapshot = await monitor.capture_snapshot()
            logger.info(f"[IntelScheduler] Graph snapshot: {snapshot.get('nodes_total', 0)} nodes, {snapshot.get('edges_total', 0)} edges")
        except Exception as e:
            logger.error(f"[IntelScheduler] Graph snapshot failed: {e}")
    
    async def _check_momentum_alerts(self):
        """Check for momentum velocity alerts and send to Telegram"""
        try:
            from modules.intelligence.momentum_alerts import get_momentum_alert_engine
            from modules.scheduler.telegram_integration import get_telegram_integration
            
            engine = get_momentum_alert_engine(self.db)
            telegram = get_telegram_integration(self.db)
            
            result = await engine.check_all_entities()
            alerts_created = result.get('alerts_created', 0)
            
            # Send Telegram notifications for new alerts
            if alerts_created > 0:
                # Get the actual alerts that were created
                new_alerts = result.get('alerts', [])
                for alert in new_alerts[:5]:  # Limit to 5 per batch
                    try:
                        await telegram.on_momentum_spike(
                            entity_id=alert.get('entity_id', 'unknown'),
                            entity_type=alert.get('entity_type', 'unknown'),
                            velocity=alert.get('velocity', 0),
                            score=alert.get('score', 0)
                        )
                    except Exception as e:
                        logger.error(f"[IntelScheduler] Failed to send momentum alert: {e}")
            
            logger.info(f"[IntelScheduler] Momentum alerts: {alerts_created} new alerts")
        except Exception as e:
            logger.error(f"[IntelScheduler] Momentum alerts check failed: {e}")
    
    async def _process_discovery_queue(self):
        """Process entity discovery queue"""
        try:
            from modules.intelligence.entity_discovery import get_entity_discovery_engine
            engine = get_entity_discovery_engine(self.db)
            
            result = await engine.process_queue(limit=20)
            logger.info(f"[IntelScheduler] Discovery: {result.get('processed', 0)} entities processed")
        except Exception as e:
            logger.error(f"[IntelScheduler] Discovery processing failed: {e}")
    
    async def _precompute_hot_graphs(self):
        """Precompute graphs for hot entities (Redis Layer 2)"""
        try:
            from modules.cache.graph_precompute import get_precompute_service
            
            service = get_precompute_service(self.db)
            if service is None:
                logger.warning("[IntelScheduler] Precompute service not initialized")
                return
            
            result = await service.precompute_hot_entities(limit=100)
            
            if result.get("ok"):
                logger.info(
                    f"[IntelScheduler] Graph precompute: {result.get('precomputed', 0)}/{result.get('hot_detected', 0)} "
                    f"entities in {result.get('duration_seconds', 0):.1f}s "
                    f"(Redis: {result.get('cached_redis', 0)}, Mongo: {result.get('cached_mongo', 0)})"
                )
            else:
                logger.warning(f"[IntelScheduler] Precompute incomplete: {result.get('error', 'unknown')}")
        except Exception as e:
            logger.error(f"[IntelScheduler] Graph precompute failed: {e}")
    
    async def _update_intelligence_index(self):
        """Update Entity Intelligence Index"""
        try:
            from modules.intelligence.entity_intelligence_index import get_intelligence_index
            
            index = get_intelligence_index(self.db)
            result = await index.update_all_entities(limit=300)
            
            logger.info(
                f"[IntelScheduler] Intelligence Index: {result.get('processed', 0)} entities "
                f"in {result.get('elapsed_seconds', 0):.1f}s"
            )
        except Exception as e:
            logger.error(f"[IntelScheduler] Intelligence Index update failed: {e}")
    
    async def _update_narrative_scores(self):
        """Update Entity Narrative Scores (Event → Topic → Narrative pipeline)"""
        try:
            from modules.intelligence.entity_narrative_score import get_narrative_score_engine
            
            engine = get_narrative_score_engine(self.db)
            result = await engine.update_all_entities(limit=200)
            
            logger.info(
                f"[IntelScheduler] Narrative Scores: {result.get('processed', 0)} entities "
                f"({result.get('with_narratives', 0)} with narratives) in {result.get('elapsed_seconds', 0):.1f}s"
            )
        except Exception as e:
            logger.error(f"[IntelScheduler] Narrative Scores update failed: {e}")
    
    async def _update_activity_scores(self):
        """Update Entity Activity Scores"""
        try:
            from modules.intelligence.entity_activity_engine import get_activity_engine
            
            engine = get_activity_engine(self.db)
            result = await engine.update_all_entities(limit=200)
            
            logger.info(
                f"[IntelScheduler] Activity Scores: {result.get('processed', 0)} entities "
                f"({result.get('active', 0)} active) in {result.get('elapsed_seconds', 0):.1f}s"
            )
        except Exception as e:
            logger.error(f"[IntelScheduler] Activity Scores update failed: {e}")
    
    async def _send_daily_report(self):
        """Send daily system report to Telegram"""
        try:
            from modules.telegram_service.alert_engine import get_alert_engine
            
            engine = get_alert_engine(self.db)
            
            # Gather real stats
            nodes = await self.db.graph_nodes.count_documents({})
            edges = await self.db.graph_edges.count_documents({})
            momentum = await self.db.entity_momentum.count_documents({})
            high_mom = await self.db.entity_momentum.count_documents({"momentum_score": {"$gte": 50}})
            
            # Get scheduler health
            from modules.scheduler.data_sync_scheduler import get_scheduler
            scheduler = get_scheduler(self.db)
            health = scheduler.get_health_status()
            
            healthy = sum(1 for h in health.values() if h.get('health_score', 0) >= 0.7)
            degraded = sum(1 for h in health.values() if 0.3 <= h.get('health_score', 0) < 0.7)
            down = sum(1 for h in health.values() if h.get('is_paused', False))
            
            success_count = sum(h.get('success_count', 0) for h in health.values())
            fail_count = sum(h.get('fail_count', 0) for h in health.values())
            
            data = {
                "sources_healthy": healthy,
                "sources_degraded": degraded,
                "sources_down": down,
                "parsers_success": success_count,
                "parsers_errors": fail_count,
                "graph_nodes": nodes,
                "graph_edges": edges,
                "momentum_tracked": momentum,
                "momentum_high": high_mom,
                "new_entities": 0,  # Could track this
                "status_message": "Ежедневный отчет системы." if down == 0 else f"Внимание: {down} источников недоступны."
            }
            
            await engine.emit_alert(
                alert_code="daily_system_report",
                data=data,
                entity="daily_report",
                force=True
            )
            
            logger.info(f"[IntelScheduler] Daily report sent")
        except Exception as e:
            logger.error(f"[IntelScheduler] Daily report failed: {e}")
    
    def setup_jobs(self):
        """Setup scheduled jobs"""
        # Momentum update - every 30 minutes
        self.scheduler.add_job(
            self._update_momentum,
            trigger=IntervalTrigger(minutes=30),
            id="intel_momentum_update",
            name="Entity Momentum Update",
            replace_existing=True
        )
        
        # Projection update - every 15 minutes
        self.scheduler.add_job(
            self._update_projections,
            trigger=IntervalTrigger(minutes=15),
            id="intel_projection_update",
            name="Projection Layer Update",
            replace_existing=True
        )
        
        # Narrative linking - every hour
        self.scheduler.add_job(
            self._link_narratives,
            trigger=IntervalTrigger(hours=1),
            id="intel_narrative_linking",
            name="Narrative Entity Linking",
            replace_existing=True
        )
        
        # Graph growth snapshot - every 6 hours
        self.scheduler.add_job(
            self._capture_graph_growth,
            trigger=IntervalTrigger(hours=6),
            id="intel_graph_growth",
            name="Graph Growth Snapshot",
            replace_existing=True
        )
        
        # Momentum alerts - every 15 minutes
        self.scheduler.add_job(
            self._check_momentum_alerts,
            trigger=IntervalTrigger(minutes=15),
            id="intel_momentum_alerts",
            name="Momentum Velocity Alerts",
            replace_existing=True
        )
        
        # Entity discovery - every hour
        self.scheduler.add_job(
            self._process_discovery_queue,
            trigger=IntervalTrigger(hours=1),
            id="intel_entity_discovery",
            name="Entity Discovery Queue",
            replace_existing=True
        )
        
        # Graph precompute - every 5 minutes (Redis Layer 2)
        self.scheduler.add_job(
            self._precompute_hot_graphs,
            trigger=IntervalTrigger(minutes=5),
            id="intel_graph_precompute",
            name="Hot Graph Precomputation",
            replace_existing=True
        )
        
        # Intelligence Index - every 10 minutes
        self.scheduler.add_job(
            self._update_intelligence_index,
            trigger=IntervalTrigger(minutes=10),
            id="intel_intelligence_index",
            name="Entity Intelligence Index Update",
            replace_existing=True
        )
        
        # Narrative Scores - every 15 minutes (Event→Topic→Narrative pipeline)
        self.scheduler.add_job(
            self._update_narrative_scores,
            trigger=IntervalTrigger(minutes=15),
            id="intel_narrative_scores",
            name="Entity Narrative Scores Update",
            replace_existing=True
        )
        
        # Activity Scores - every 15 minutes
        self.scheduler.add_job(
            self._update_activity_scores,
            trigger=IntervalTrigger(minutes=15),
            id="intel_activity_scores",
            name="Entity Activity Scores Update",
            replace_existing=True
        )
        
        # Daily report - every 24 hours (at startup + every 24h)
        self.scheduler.add_job(
            self._send_daily_report,
            trigger=IntervalTrigger(hours=24),
            id="intel_daily_report",
            name="Daily System Report",
            replace_existing=True
        )
        
        logger.info("[IntelScheduler] Setup 11 jobs: momentum, projections, narrative_linking, graph_growth, alerts, discovery, precompute, intelligence_index, narrative_scores, activity_scores, daily_report")
    
    def start(self):
        """Start the scheduler"""
        if not self._running:
            self.setup_jobs()
            self.scheduler.start()
            self._running = True
            logger.info("[IntelScheduler] Started")
    
    def stop(self):
        """Stop the scheduler"""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("[IntelScheduler] Stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            })
        
        return {
            "running": self._running,
            "job_count": len(jobs),
            "jobs": jobs
        }


# Singleton
_scheduler: Optional[IntelligenceScheduler] = None


def get_intelligence_scheduler(db: AsyncIOMotorDatabase = None) -> IntelligenceScheduler:
    """Get or create intelligence scheduler"""
    global _scheduler
    if db is not None:
        _scheduler = IntelligenceScheduler(db)
    return _scheduler


def start_intelligence_scheduler(db: AsyncIOMotorDatabase) -> IntelligenceScheduler:
    """Start intelligence scheduler"""
    scheduler = get_intelligence_scheduler(db)
    scheduler.start()
    return scheduler
