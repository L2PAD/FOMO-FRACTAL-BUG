"""
Compute Separation Architecture
===============================

Separates system into 3 computational clusters to prevent:
- UI blocking by heavy jobs
- Cascade failures
- Ingestion delays from compute load

3 Clusters:
1. Data Ingestion Cluster
   - Parsers, API ingestion, discovery
   - Stateless workers with retry queue
   
2. Intelligence Compute Cluster  
   - Entity resolution, event building, topic/narrative detection
   - Graph building, derived edges, momentum engine
   - Async via job queue
   
3. API / Query Cluster
   - Only reads from projections/caches
   - Never does heavy compute
   - Guarantees UI responsiveness

Key principles:
- UI never blocks on heavy compute
- Compute never blocks ingestion
- Graph fully rebuildable from normalized data

Collections for job orchestration:
    compute_jobs - Job queue with priority
    compute_workers - Worker status tracking
    compute_metrics - Performance metrics
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class ComputeCluster(str, Enum):
    INGESTION = "ingestion"
    INTELLIGENCE = "intelligence"
    QUERY = "query"


class JobPriority(int, Enum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class ComputeJob:
    """Job definition for compute queue"""
    job_id: str
    job_type: str
    cluster: ComputeCluster
    priority: JobPriority = JobPriority.NORMAL
    payload: Dict[str, Any] = field(default_factory=dict)
    max_retries: int = 3
    timeout_seconds: int = 300
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "cluster": self.cluster.value,
            "priority": self.priority.value,
            "payload": self.payload,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "status": JobStatus.PENDING.value,
            "retries": 0,
            "created_at": self.created_at,
            "updated_at": self.created_at
        }


# Job type definitions by cluster
INGESTION_JOBS = {
    "news_ingest": {"timeout": 120, "priority": JobPriority.HIGH},
    "market_sync": {"timeout": 60, "priority": JobPriority.CRITICAL},
    "entity_ingest": {"timeout": 180, "priority": JobPriority.NORMAL},
    "provider_sync": {"timeout": 90, "priority": JobPriority.NORMAL},
    "source_discovery": {"timeout": 300, "priority": JobPriority.LOW},
}

INTELLIGENCE_JOBS = {
    "entity_resolution": {"timeout": 300, "priority": JobPriority.HIGH},
    "root_event_builder": {"timeout": 180, "priority": JobPriority.HIGH},
    "topic_detection": {"timeout": 240, "priority": JobPriority.NORMAL},
    "narrative_detection": {"timeout": 300, "priority": JobPriority.NORMAL},
    "early_narrative_engine": {"timeout": 180, "priority": JobPriority.HIGH},
    "graph_builder": {"timeout": 600, "priority": JobPriority.NORMAL},
    "derived_edges": {"timeout": 300, "priority": JobPriority.LOW},
    "intelligence_edges": {"timeout": 300, "priority": JobPriority.NORMAL},
    "momentum_update": {"timeout": 300, "priority": JobPriority.NORMAL},
    "projection_rebuild": {"timeout": 180, "priority": JobPriority.LOW},
}


class ComputeJobQueue:
    """
    Distributed job queue for compute separation.
    Jobs are processed by cluster-specific workers.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.jobs = db.compute_jobs
        self.workers = db.compute_workers
        self.metrics = db.compute_metrics
        
        self._handlers: Dict[str, Callable] = {}
        self._running_workers: Dict[str, asyncio.Task] = {}
    
    async def ensure_indexes(self):
        """Create indexes for job queue"""
        await self.jobs.create_index("job_id", unique=True)
        await self.jobs.create_index([("cluster", 1), ("status", 1), ("priority", 1)])
        await self.jobs.create_index("status")
        await self.jobs.create_index("created_at")
        
        await self.workers.create_index("worker_id", unique=True)
        await self.workers.create_index("cluster")
        await self.workers.create_index("status")
        
        await self.metrics.create_index([("cluster", 1), ("date", -1)])
        
        logger.info("[ComputeQueue] Indexes created")
    
    def register_handler(self, job_type: str, handler: Callable):
        """Register a handler function for a job type"""
        self._handlers[job_type] = handler
        logger.info(f"[ComputeQueue] Registered handler: {job_type}")
    
    async def enqueue(
        self,
        job_type: str,
        cluster: ComputeCluster,
        payload: Dict[str, Any] = None,
        priority: JobPriority = None
    ) -> str:
        """
        Add a job to the queue.
        Returns job_id.
        """
        # Get job config
        if cluster == ComputeCluster.INGESTION:
            config = INGESTION_JOBS.get(job_type, {})
        else:
            config = INTELLIGENCE_JOBS.get(job_type, {})
        
        if priority is None:
            priority = config.get("priority", JobPriority.NORMAL)
        
        timeout = config.get("timeout", 300)
        
        # Generate job ID
        job_id = f"{job_type}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        
        job = ComputeJob(
            job_id=job_id,
            job_type=job_type,
            cluster=cluster,
            priority=priority,
            payload=payload or {},
            timeout_seconds=timeout
        )
        
        await self.jobs.insert_one(job.to_dict())
        
        logger.debug(f"[ComputeQueue] Enqueued: {job_type} ({cluster.value})")
        
        return job_id
    
    async def get_next_job(self, cluster: ComputeCluster) -> Optional[Dict]:
        """
        Get next job for a cluster worker.
        Uses findAndModify for atomic claim.
        """
        now = datetime.now(timezone.utc)
        
        result = await self.jobs.find_one_and_update(
            {
                "cluster": cluster.value,
                "status": {"$in": [JobStatus.PENDING.value, JobStatus.RETRY.value]}
            },
            {
                "$set": {
                    "status": JobStatus.RUNNING.value,
                    "started_at": now,
                    "updated_at": now
                }
            },
            sort=[("priority", 1), ("created_at", 1)],
            return_document=True
        )
        
        if result:
            # Remove _id for JSON serialization
            result.pop("_id", None)
        
        return result
    
    async def complete_job(
        self,
        job_id: str,
        success: bool,
        result: Dict[str, Any] = None,
        error: str = None
    ):
        """Mark job as completed or failed"""
        now = datetime.now(timezone.utc)
        
        job = await self.jobs.find_one({"job_id": job_id})
        if not job:
            return
        
        if success:
            await self.jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": JobStatus.COMPLETED.value,
                        "completed_at": now,
                        "updated_at": now,
                        "result": result
                    }
                }
            )
            
            # Record metric
            await self._record_metric(job["cluster"], job["job_type"], True)
        else:
            retries = job.get("retries", 0)
            max_retries = job.get("max_retries", 3)
            
            if retries < max_retries:
                # Retry
                await self.jobs.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "status": JobStatus.RETRY.value,
                            "updated_at": now,
                            "last_error": error
                        },
                        "$inc": {"retries": 1}
                    }
                )
            else:
                # Final failure
                await self.jobs.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "status": JobStatus.FAILED.value,
                            "failed_at": now,
                            "updated_at": now,
                            "last_error": error
                        }
                    }
                )
                
                await self._record_metric(job["cluster"], job["job_type"], False)
    
    async def _record_metric(
        self,
        cluster: str,
        job_type: str,
        success: bool
    ):
        """Record job completion metric"""
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        update = {
            "$inc": {
                "total_jobs": 1,
                f"jobs_by_type.{job_type}": 1
            }
        }
        
        if success:
            update["$inc"]["success_count"] = 1
        else:
            update["$inc"]["fail_count"] = 1
        
        await self.metrics.update_one(
            {"cluster": cluster, "date": today},
            {
                "$setOnInsert": {"cluster": cluster, "date": today},
                **update
            },
            upsert=True
        )
    
    async def process_jobs(
        self,
        cluster: ComputeCluster,
        max_concurrent: int = 3
    ):
        """
        Process jobs for a cluster.
        Runs as background worker.
        """
        worker_id = f"{cluster.value}_{datetime.now(timezone.utc).strftime('%H%M%S')}"
        
        # Register worker
        await self.workers.update_one(
            {"worker_id": worker_id},
            {
                "$set": {
                    "cluster": cluster.value,
                    "status": "running",
                    "started_at": datetime.now(timezone.utc),
                    "jobs_processed": 0
                }
            },
            upsert=True
        )
        
        logger.info(f"[ComputeQueue] Worker started: {worker_id}")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        while True:
            async with semaphore:
                job = await self.get_next_job(cluster)
                
                if not job:
                    await asyncio.sleep(5)  # No jobs, wait
                    continue
                
                # Process job
                job_type = job["job_type"]
                handler = self._handlers.get(job_type)
                
                if not handler:
                    logger.warning(f"[ComputeQueue] No handler for: {job_type}")
                    await self.complete_job(job["job_id"], False, error="No handler")
                    continue
                
                try:
                    # Run with timeout
                    result = await asyncio.wait_for(
                        handler(job["payload"]),
                        timeout=job.get("timeout_seconds", 300)
                    )
                    
                    await self.complete_job(job["job_id"], True, result=result)
                    
                    # Update worker stats
                    await self.workers.update_one(
                        {"worker_id": worker_id},
                        {"$inc": {"jobs_processed": 1}}
                    )
                    
                except asyncio.TimeoutError:
                    await self.complete_job(
                        job["job_id"],
                        False,
                        error=f"Timeout after {job['timeout_seconds']}s"
                    )
                except Exception as e:
                    logger.error(f"[ComputeQueue] Job {job['job_id']} failed: {e}")
                    await self.complete_job(job["job_id"], False, error=str(e))
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        # Count jobs by status and cluster
        pipeline = [
            {"$group": {
                "_id": {"cluster": "$cluster", "status": "$status"},
                "count": {"$sum": 1}
            }}
        ]
        
        results = await self.jobs.aggregate(pipeline).to_list(100)
        
        stats = {
            "ingestion": {"pending": 0, "running": 0, "completed": 0, "failed": 0},
            "intelligence": {"pending": 0, "running": 0, "completed": 0, "failed": 0}
        }
        
        for r in results:
            cluster = r["_id"]["cluster"]
            status = r["_id"]["status"]
            if cluster in stats and status in stats[cluster]:
                stats[cluster][status] = r["count"]
        
        # Get active workers
        workers = await self.workers.find(
            {"status": "running"},
            {"_id": 0}
        ).to_list(20)
        
        return {
            "queue_stats": stats,
            "active_workers": len(workers),
            "workers": workers
        }
    
    async def get_cluster_metrics(
        self,
        cluster: ComputeCluster,
        days: int = 7
    ) -> List[Dict]:
        """Get metrics for a cluster"""
        from_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        cursor = self.metrics.find(
            {"cluster": cluster.value, "date": {"$gte": from_date}},
            {"_id": 0}
        ).sort("date", -1)
        
        return await cursor.to_list(length=days)
    
    async def cleanup_old_jobs(self, days: int = 7) -> int:
        """Remove completed jobs older than X days"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        result = await self.jobs.delete_many({
            "status": {"$in": [JobStatus.COMPLETED.value, JobStatus.FAILED.value]},
            "created_at": {"$lt": cutoff}
        })
        
        logger.info(f"[ComputeQueue] Cleaned up {result.deleted_count} old jobs")
        
        return result.deleted_count


class ProjectionLayer:
    """
    Pre-computed projection layer for fast UI reads.
    Sits between compute and query clusters.
    
    Collections:
        feed_cards - Pre-rendered feed items
        graph_projection - Pre-computed subgraphs
        narrative_projection - Narrative summaries
        momentum_projection - Top momentum entities
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.feed_cards = db.feed_cards
        self.graph_projection = db.graph_projection
        self.narrative_projection = db.narrative_projection
        self.momentum_projection = db.momentum_projection
    
    async def ensure_indexes(self):
        """Create indexes for projection collections"""
        await self.feed_cards.create_index("card_id", unique=True)
        await self.feed_cards.create_index("entity_key")
        await self.feed_cards.create_index("created_at")
        
        await self.narrative_projection.create_index("narrative_id", unique=True)
        await self.narrative_projection.create_index("momentum_score")
        
        await self.momentum_projection.create_index("projection_type")
        await self.momentum_projection.create_index("updated_at")
        
        logger.info("[ProjectionLayer] Indexes created")
    
    async def update_feed_projection(self, limit: int = 100) -> int:
        """
        Update feed cards projection from events.
        Called by intelligence compute job.
        """
        now = datetime.now(timezone.utc)
        updated = 0
        
        # Get latest events
        cursor = self.db.news_events.find({
            "status": {"$ne": "archived"}
        }).sort("created_at", -1).limit(limit)
        
        async for event in cursor:
            card = {
                "card_id": f"evt_{event.get('id')}",
                "event_id": event.get("id"),
                "title": event.get("title_en") or event.get("title"),
                "summary": event.get("summary_en") or event.get("summary"),
                "event_type": event.get("event_type"),
                "primary_assets": event.get("primary_assets", []),
                "fomo_score": event.get("fomo_score", 0),
                "feed_score": event.get("feed_score", 0),
                "source_count": event.get("source_count", 1),
                "created_at": event.get("created_at") or now,
                "projected_at": now
            }
            
            await self.feed_cards.update_one(
                {"card_id": card["card_id"]},
                {"$set": card},
                upsert=True
            )
            updated += 1
        
        logger.info(f"[ProjectionLayer] Updated {updated} feed cards")
        return updated
    
    async def update_narrative_projection(self) -> int:
        """
        Update narrative projections with current stats.
        """
        now = datetime.now(timezone.utc)
        updated = 0
        
        cursor = self.db.narratives.find({
            "lifecycle": {"$ne": "dormant"}
        })
        
        async for narrative in cursor:
            # Get top entities for narrative
            top_entities = await self.db.entity_momentum.find(
                {"entity_key": {"$in": narrative.get("entity_keys", [])}}
            ).sort("momentum_score", -1).limit(5).to_list(5)
            
            projection = {
                "narrative_id": narrative.get("id"),
                "name": narrative.get("name"),
                "canonical_name": narrative.get("canonical_name"),
                "momentum_score": narrative.get("momentum_score", 0),
                "lifecycle": narrative.get("lifecycle"),
                "trend_direction": narrative.get("trend_direction"),
                "event_count": narrative.get("event_count", 0),
                "top_entities": [
                    {
                        "entity_key": e.get("entity_key"),
                        "momentum": e.get("momentum_score", 0)
                    }
                    for e in top_entities
                ],
                "projected_at": now
            }
            
            await self.narrative_projection.update_one(
                {"narrative_id": projection["narrative_id"]},
                {"$set": projection},
                upsert=True
            )
            updated += 1
        
        logger.info(f"[ProjectionLayer] Updated {updated} narrative projections")
        return updated
    
    async def update_momentum_projection(self) -> Dict[str, Any]:
        """
        Update momentum ranking projections.
        Pre-computes top momentum lists for fast UI access.
        """
        now = datetime.now(timezone.utc)
        
        projections_updated = 0
        
        # Top overall
        top_all = await self.db.entity_momentum.find(
            {},
            {"_id": 0, "entity_key": 1, "entity_type": 1, "momentum_score": 1}
        ).sort("momentum_score", -1).limit(20).to_list(20)
        
        await self.momentum_projection.update_one(
            {"projection_type": "top_overall"},
            {
                "$set": {
                    "projection_type": "top_overall",
                    "entities": top_all,
                    "updated_at": now
                }
            },
            upsert=True
        )
        projections_updated += 1
        
        # Fastest growing
        fastest = await self.db.entity_momentum.find(
            {"momentum_velocity": {"$gt": 0}},
            {"_id": 0, "entity_key": 1, "entity_type": 1, "momentum_score": 1, "momentum_velocity": 1}
        ).sort("momentum_velocity", -1).limit(20).to_list(20)
        
        await self.momentum_projection.update_one(
            {"projection_type": "fastest_growing"},
            {
                "$set": {
                    "projection_type": "fastest_growing",
                    "entities": fastest,
                    "updated_at": now
                }
            },
            upsert=True
        )
        projections_updated += 1
        
        # Top by type
        for entity_type in ["project", "fund", "person"]:
            top_type = await self.db.entity_momentum.find(
                {"entity_type": entity_type},
                {"_id": 0, "entity_key": 1, "momentum_score": 1}
            ).sort("momentum_score", -1).limit(10).to_list(10)
            
            await self.momentum_projection.update_one(
                {"projection_type": f"top_{entity_type}"},
                {
                    "$set": {
                        "projection_type": f"top_{entity_type}",
                        "entities": top_type,
                        "updated_at": now
                    }
                },
                upsert=True
            )
            projections_updated += 1
        
        logger.info(f"[ProjectionLayer] Updated {projections_updated} momentum projections")
        
        return {
            "projections_updated": projections_updated,
            "updated_at": now.isoformat()
        }
    
    async def get_feed_cards(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get pre-rendered feed cards.
        Fast path for UI - no heavy compute.
        """
        cursor = self.feed_cards.find(
            {},
            {"_id": 0}
        ).sort("created_at", -1).skip(offset).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_momentum_ranking(
        self,
        ranking_type: str = "top_overall"
    ) -> Dict[str, Any]:
        """
        Get pre-computed momentum ranking.
        Fast path - just reads projection.
        """
        projection = await self.momentum_projection.find_one(
            {"projection_type": ranking_type},
            {"_id": 0}
        )
        
        return projection or {"entities": [], "error": "Projection not found"}


# Singleton instances
_job_queue: Optional[ComputeJobQueue] = None
_projection_layer: Optional[ProjectionLayer] = None


def get_compute_job_queue(db: AsyncIOMotorDatabase = None) -> ComputeJobQueue:
    """Get or create job queue instance"""
    global _job_queue
    if db is not None:
        _job_queue = ComputeJobQueue(db)
    return _job_queue


def get_projection_layer(db: AsyncIOMotorDatabase = None) -> ProjectionLayer:
    """Get or create projection layer instance"""
    global _projection_layer
    if db is not None:
        _projection_layer = ProjectionLayer(db)
    return _projection_layer
