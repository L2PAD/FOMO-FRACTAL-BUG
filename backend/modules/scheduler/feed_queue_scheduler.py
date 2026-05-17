"""
Feed & Queue Scheduler

Scheduled jobs for:
- Feed projection updates
- Archive management
- Queue processing
- Maintenance tasks
"""

import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class FeedQueueScheduler:
    """
    Scheduler for feed projection and queue processing
    """
    
    def __init__(self, db):
        self.db = db
        self.scheduler = AsyncIOScheduler()
        self._started = False
    
    def start(self):
        """Start all scheduled jobs"""
        if self._started:
            return
        
        logger.info("[FeedQueueScheduler] Starting...")
        
        # Feed projection - every 5 minutes
        self.scheduler.add_job(
            self._run_feed_projection,
            IntervalTrigger(minutes=5),
            id="feed_projection",
            name="Feed Projection",
            replace_existing=True,
            max_instances=1
        )
        
        # Feed updates (for changed events) - every 2 minutes
        self.scheduler.add_job(
            self._run_feed_updates,
            IntervalTrigger(minutes=2),
            id="feed_updates",
            name="Feed Updates",
            replace_existing=True,
            max_instances=1
        )
        
        # Archive old cards - daily at 3 AM
        self.scheduler.add_job(
            self._run_archive,
            CronTrigger(hour=3, minute=0),
            id="feed_archive",
            name="Feed Archive",
            replace_existing=True,
            max_instances=1
        )
        
        # Queue processing - continuous
        self.scheduler.add_job(
            self._process_queue,
            IntervalTrigger(seconds=10),
            id="queue_process",
            name="Queue Process",
            replace_existing=True,
            max_instances=1
        )
        
        # Narrative lifecycle updates - every 30 minutes
        self.scheduler.add_job(
            self._update_narrative_lifecycles,
            IntervalTrigger(minutes=30),
            id="narrative_lifecycle",
            name="Narrative Lifecycle",
            replace_existing=True,
            max_instances=1
        )
        
        # Root events population - every 10 minutes
        self.scheduler.add_job(
            self._populate_root_events,
            IntervalTrigger(minutes=10),
            id="root_events_population",
            name="Root Events Population",
            replace_existing=True,
            max_instances=1
        )
        
        # Topic detection - every 15 minutes
        self.scheduler.add_job(
            self._update_topics,
            IntervalTrigger(minutes=15),
            id="topic_detection",
            name="Topic Detection",
            replace_existing=True,
            max_instances=1
        )
        
        # Narrative early detection - every 30 minutes
        self.scheduler.add_job(
            self._detect_narratives,
            IntervalTrigger(minutes=30),
            id="narrative_detection",
            name="Narrative Early Detection",
            replace_existing=True,
            max_instances=1
        )
        
        # System metrics recording - every 5 minutes
        self.scheduler.add_job(
            self._record_system_metrics,
            IntervalTrigger(minutes=5),
            id="system_metrics",
            name="System Metrics",
            replace_existing=True,
            max_instances=1
        )
        
        # ═══════════════════════════════════════════════════════════════
        # ARCHITECTURE ENHANCEMENT JOBS
        # ═══════════════════════════════════════════════════════════════
        
        # Graph Projection rebuild - every 15 minutes
        self.scheduler.add_job(
            self._rebuild_graph_projections,
            IntervalTrigger(minutes=15),
            id="graph_projection_rebuild",
            name="Graph Projection Rebuild",
            replace_existing=True,
            max_instances=1
        )
        
        # Event Entity linking - every 10 minutes
        self.scheduler.add_job(
            self._link_event_entities,
            IntervalTrigger(minutes=10),
            id="event_entity_linking",
            name="Event Entity Linking",
            replace_existing=True,
            max_instances=1
        )
        
        # Source reliability recalculation - every 15 minutes
        self.scheduler.add_job(
            self._update_source_reliability,
            IntervalTrigger(minutes=15),
            id="source_reliability_update",
            name="Source Reliability Update",
            replace_existing=True,
            max_instances=1
        )
        
        # Compute derived graph edges - every hour
        self.scheduler.add_job(
            self._compute_derived_edges,
            IntervalTrigger(hours=1),
            id="compute_derived_edges",
            name="Compute Derived Edges",
            replace_existing=True,
            max_instances=1
        )
        
        # Parser sync job - every 30 minutes
        self.scheduler.add_job(
            self._sync_parsers,
            IntervalTrigger(minutes=30),
            id="parser_sync",
            name="Parser Data Sync",
            replace_existing=True,
            max_instances=1
        )
        
        # Source alerting check - every 5 minutes
        self.scheduler.add_job(
            self._check_source_alerts,
            IntervalTrigger(minutes=5),
            id="source_alerting",
            name="Source Alerting Check",
            replace_existing=True,
            max_instances=1
        )
        
        self.scheduler.start()
        self._started = True
        
        logger.info("[FeedQueueScheduler] Started with 15 jobs")
    
    def stop(self):
        """Stop scheduler"""
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("[FeedQueueScheduler] Stopped")
    
    async def _run_feed_projection(self):
        """Run feed projection for new events"""
        try:
            from modules.intelligence.feed_worker import FeedProjectionWorker
            
            worker = FeedProjectionWorker(self.db)
            await worker.initialize()
            
            stats = await worker.project_new_events(limit=200)
            
            if stats["created"] > 0:
                logger.info(f"[FeedProjection] Created {stats['created']} feed cards")
            
        except Exception as e:
            logger.error(f"[FeedProjection] Error: {e}")
    
    async def _run_feed_updates(self):
        """Update feed cards for changed events"""
        try:
            from modules.intelligence.feed_worker import FeedProjectionWorker
            
            worker = FeedProjectionWorker(self.db)
            await worker.initialize()
            
            stats = await worker.update_changed_events()
            
            if stats["updated"] > 0:
                logger.info(f"[FeedUpdates] Updated {stats['updated']} feed cards")
            
        except Exception as e:
            logger.error(f"[FeedUpdates] Error: {e}")
    
    async def _run_archive(self):
        """Archive old feed cards"""
        try:
            from modules.intelligence.feed_worker import FeedProjectionWorker
            
            worker = FeedProjectionWorker(self.db)
            await worker.initialize()
            
            stats = await worker.archive_old_cards()
            
            logger.info(f"[FeedArchive] Archived {stats['archived']} cards")
            
        except Exception as e:
            logger.error(f"[FeedArchive] Error: {e}")
    
    async def _process_queue(self):
        """Process pending jobs from queue"""
        try:
            from modules.queue.enhanced_queue import get_job_queue, WorkerType
            
            queue = get_job_queue(self.db)
            
            # Process each worker type
            for worker_type in WorkerType:
                stats = await queue.process_worker(worker_type, max_jobs=10)
                
                if stats["processed"] > 0:
                    logger.debug(f"[Queue:{worker_type.value}] Processed {stats['processed']} jobs")
            
        except Exception as e:
            logger.error(f"[QueueProcess] Error: {e}")
    
    async def _update_narrative_lifecycles(self):
        """Update narrative lifecycle metrics"""
        try:
            from modules.narrative.enhanced_narrative import EnhancedNarrativeService
            
            service = EnhancedNarrativeService(self.db)
            
            # Get active narratives
            cursor = self.db.narratives.find({
                "lifecycle_state": {"$ne": "dead"}
            })
            
            updated = 0
            async for narrative in cursor:
                narrative_id = narrative.get("id")
                if narrative_id:
                    await service.update_lifecycle_metrics(narrative_id)
                    updated += 1
            
            if updated > 0:
                logger.info(f"[NarrativeLifecycle] Updated {updated} narratives")
            
        except Exception as e:
            logger.error(f"[NarrativeLifecycle] Error: {e}")
    
    async def _record_system_metrics(self):
        """Record system metrics snapshot"""
        try:
            from modules.system.observability import ObservabilityService
            
            service = ObservabilityService(self.db)
            await service.record_system_metrics()
            
        except Exception as e:
            logger.error(f"[SystemMetrics] Error: {e}")
    
    async def _populate_root_events(self):
        """Populate root_events from news articles"""
        try:
            from modules.intelligence.topic_layer import RootEventPopulationService
            
            service = RootEventPopulationService(self.db)
            stats = await service.populate_from_articles(limit=200)
            
            if stats["events_created"] > 0:
                logger.info(f"[RootEventsPopulation] Created {stats['events_created']} events, linked {stats['topics_linked']} topics")
            
        except Exception as e:
            logger.error(f"[RootEventsPopulation] Error: {e}")
    
    async def _update_topics(self):
        """Update topic momentum scores"""
        try:
            from modules.intelligence.topic_layer import TopicService
            
            service = TopicService(self.db)
            
            # Get all active topics
            cursor = self.db.topics.find({"status": {"$ne": "archived"}})
            
            updated = 0
            async for topic in cursor:
                topic_id = topic.get("id")
                if topic_id:
                    await service.update_topic_momentum(topic_id)
                    updated += 1
            
            if updated > 0:
                logger.info(f"[TopicDetection] Updated {updated} topics")
            
        except Exception as e:
            logger.error(f"[TopicDetection] Error: {e}")
    
    async def _detect_narratives(self):
        """Run narrative early detection"""
        try:
            from modules.narrative.early_detection import NarrativeEarlyDetector
            
            detector = NarrativeEarlyDetector(self.db)
            emerging = await detector.detect_emerging_narratives()
            
            if emerging:
                logger.info(f"[NarrativeDetection] Detected {len(emerging)} narratives")
            
        except Exception as e:
            logger.error(f"[NarrativeDetection] Error: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # ARCHITECTURE ENHANCEMENT JOBS
    # ═══════════════════════════════════════════════════════════════
    
    async def _rebuild_graph_projections(self):
        """Rebuild pre-computed graph projections for hot entities"""
        try:
            from modules.knowledge_graph.graph_projection import get_projection_service
            
            service = get_projection_service(self.db)
            result = await service.rebuild_hot_graphs()
            
            if result.get("success", 0) > 0:
                logger.info(f"[GraphProjection] Rebuilt {result['success']} projections in {result.get('elapsed_seconds', 0):.1f}s")
            
        except Exception as e:
            logger.error(f"[GraphProjection] Error: {e}")
    
    async def _link_event_entities(self):
        """Link new events to entities in event_entities registry"""
        try:
            from modules.intelligence.event_entity_registry import get_event_entity_registry, EventType
            
            registry = get_event_entity_registry(self.db)
            
            # Find recent news_events not yet linked
            cutoff = datetime.now(timezone.utc)
            
            cursor = self.db.news_events.find({
                "created_at": {"$gte": cutoff.isoformat()}
            }).limit(100)
            
            linked_count = 0
            async for event in cursor:
                event_id = event.get("id")
                if not event_id:
                    continue
                
                # Check if already linked
                existing = await self.db.event_entities.find_one({"event_id": event_id})
                if existing:
                    continue
                
                # Build entities list
                entities = []
                
                for entity in event.get("primary_entities", []):
                    if isinstance(entity, str):
                        entities.append({
                            "entity_type": "unknown",
                            "entity_id": entity.lower(),
                            "role": "primary",
                            "confidence": 0.9
                        })
                
                for asset in event.get("primary_assets", []):
                    if isinstance(asset, str):
                        entities.append({
                            "entity_type": "project",
                            "entity_id": asset.lower(),
                            "role": "primary",
                            "confidence": 0.85
                        })
                
                if entities:
                    await registry.link_event_entities(event_id, EventType.NEWS, entities)
                    linked_count += 1
            
            if linked_count > 0:
                logger.info(f"[EventEntityLinking] Linked {linked_count} events")
            
        except Exception as e:
            logger.error(f"[EventEntityLinking] Error: {e}")
    
    async def _update_source_reliability(self):
        """Recalculate source reliability scores"""
        try:
            from modules.provider_gateway.source_reliability import get_source_reliability
            
            system = get_source_reliability(self.db)
            stats = await system.get_stats()
            
            logger.debug(f"[SourceReliability] Stats: {stats['healthy']} healthy, {stats['degraded']} degraded, {stats['down']} down")
            
        except Exception as e:
            logger.error(f"[SourceReliability] Error: {e}")
    
    async def _compute_derived_edges(self):
        """Compute derived graph edges from factual data"""
        try:
            from modules.knowledge_graph.graph_layers import get_graph_layer_service
            
            service = get_graph_layer_service(self.db)
            
            # Compute coinvested_with edges
            coinvested = await service.compute_derived_edges("coinvested_with")
            
            # Compute shares_investor_with edges
            shares_investor = await service.compute_derived_edges("shares_investor_with")
            
            # Link events to create intelligence edges
            intelligence = await service.link_events_to_entities(limit=200)
            
            if coinvested > 0 or shares_investor > 0 or intelligence > 0:
                logger.info(f"[DerivedEdges] Computed: coinvested={coinvested}, shares_investor={shares_investor}, intelligence={intelligence}")
            
        except Exception as e:
            logger.error(f"[DerivedEdges] Error: {e}")
    
    async def _check_source_alerts(self):
        """Check source health and generate alerts"""
        try:
            from modules.provider_gateway.source_alerting import get_source_alerting
            
            system = get_source_alerting(self.db)
            new_alerts = await system.check_sources_and_alert()
            
            if new_alerts:
                logger.warning(f"[SourceAlerting] Generated {len(new_alerts)} new alerts")
                for alert in new_alerts:
                    logger.warning(f"  - {alert['severity'].upper()}: {alert['title']}")
            
        except Exception as e:
            logger.error(f"[SourceAlerting] Error: {e}")
    
    async def _sync_parsers(self):
        """Sync data from external parsers (generates reliability metrics)"""
        try:
            from modules.parsers.parser_coingecko import sync_coingecko_data
            from modules.parsers.parser_cryptorank import sync_cryptorank_data
            from modules.parsers.parser_defillama import sync_defillama_data
            
            # Run syncs - these now have reliability tracking
            try:
                await sync_coingecko_data(self.db, full=False)
                logger.debug("[ParserSync] CoinGecko sync complete")
            except Exception as e:
                logger.warning(f"[ParserSync] CoinGecko failed: {e}")
            
            try:
                await sync_cryptorank_data(self.db)
                logger.debug("[ParserSync] CryptoRank sync complete")
            except Exception as e:
                logger.warning(f"[ParserSync] CryptoRank failed: {e}")
            
            try:
                await sync_defillama_data(self.db)
                logger.debug("[ParserSync] DefiLlama sync complete")
            except Exception as e:
                logger.warning(f"[ParserSync] DefiLlama failed: {e}")
            
            logger.info("[ParserSync] All parsers synced")
            
        except Exception as e:
            logger.error(f"[ParserSync] Error: {e}")
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None
            })
        
        return {
            "running": self._started,
            "job_count": len(jobs),
            "jobs": jobs
        }


# =============================================================================
# SINGLETON
# =============================================================================

_scheduler_instance: FeedQueueScheduler = None


def get_feed_queue_scheduler(db) -> FeedQueueScheduler:
    """Get or create scheduler singleton"""
    global _scheduler_instance
    
    if _scheduler_instance is None:
        _scheduler_instance = FeedQueueScheduler(db)
    
    return _scheduler_instance


def start_feed_queue_scheduler(db) -> FeedQueueScheduler:
    """Start the feed queue scheduler"""
    scheduler = get_feed_queue_scheduler(db)
    scheduler.start()
    return scheduler
