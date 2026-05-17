"""
Queue Layer (Phase A)

Job queue infrastructure for async processing.

Currently using in-memory queue with APScheduler.
Ready for migration to Redis/BullMQ when needed.

Job Types:
- news_ingest: Process incoming news
- market_sync: Sync market data from exchanges
- intel_sync: Sync intel data from providers
- scoring_pipeline: Score events
- narrative_build: Update narrative clusters
- graph_rebuild: Rebuild knowledge graph
- entity_resolution: Resolve entity aliases
- feed_projection: Update feed cards
- archive_job: Archive old data
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Callable
from pydantic import BaseModel, Field
from enum import Enum
import asyncio
import logging
import hashlib
from collections import deque

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Status of a job"""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"  # Moved to dead letter queue


class JobPriority(int, Enum):
    """Job priority levels"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class JobType(str, Enum):
    """Standard job types"""
    NEWS_INGEST = "news_ingest"
    MARKET_SYNC = "market_sync"
    INTEL_SYNC = "intel_sync"
    SCORING_PIPELINE = "scoring_pipeline"
    NARRATIVE_BUILD = "narrative_build"
    GRAPH_REBUILD = "graph_rebuild"
    ENTITY_RESOLUTION = "entity_resolution"
    FEED_PROJECTION = "feed_projection"
    ARCHIVE_JOB = "archive_job"
    LIFECYCLE_UPDATE = "lifecycle_update"


class Job(BaseModel):
    """A job in the queue"""
    id: str
    job_type: JobType
    priority: JobPriority = JobPriority.NORMAL
    
    # Status
    status: JobStatus = JobStatus.PENDING
    
    # Payload
    payload: Dict = Field(default_factory=dict)
    
    # Retry policy
    max_retries: int = 3
    retry_count: int = 0
    retry_delay_seconds: int = 60
    
    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    
    # Result
    result: Optional[Dict] = None
    error: Optional[str] = None
    
    # Rate limiting
    rate_limit_key: Optional[str] = None  # For grouping rate-limited jobs
    
    class Config:
        use_enum_values = True


class JobQueue:
    """
    In-memory job queue with priority and retry support
    
    Can be replaced with Redis/BullMQ for production scale
    """
    
    def __init__(self, db=None):
        self.db = db
        self.queues: Dict[str, deque] = {}
        self.handlers: Dict[str, Callable] = {}
        self.rate_limiters: Dict[str, datetime] = {}
        
        # Default rate limits (requests per minute)
        self.rate_limits = {
            "cryptorank": 100,
            "rootdata": 60,
            "defillama": 300,
            "coingecko": 30,
            "binance": 1200,
            "github": 60,
        }
        
        # Stats
        self.stats = {
            "pending": 0,
            "active": 0,
            "completed_24h": 0,
            "failed_24h": 0
        }
    
    def register_handler(self, job_type: JobType, handler: Callable):
        """Register a handler function for a job type"""
        self.handlers[job_type.value] = handler
    
    async def enqueue(
        self,
        job_type: JobType,
        payload: Dict,
        priority: JobPriority = JobPriority.NORMAL,
        rate_limit_key: str = None
    ) -> Job:
        """
        Add job to queue
        """
        job = Job(
            id=self._generate_job_id(job_type),
            job_type=job_type,
            priority=priority,
            payload=payload,
            rate_limit_key=rate_limit_key
        )
        
        queue_name = f"{job_type.value}_{priority.value}"
        if queue_name not in self.queues:
            self.queues[queue_name] = deque()
        
        self.queues[queue_name].append(job)
        self.stats["pending"] += 1
        
        # Persist to DB if available
        if self.db:
            await self.db.job_queue.insert_one(job.dict())
        
        return job
    
    async def process_next(self, job_type: JobType = None) -> Optional[Job]:
        """
        Process next job from queue
        """
        job = await self._get_next_job(job_type)
        if not job:
            return None
        
        # Check rate limit
        if job.rate_limit_key and not self._check_rate_limit(job.rate_limit_key):
            # Re-queue with delay
            job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=60)
            await self._requeue(job)
            return None
        
        # Mark as active
        job.status = JobStatus.ACTIVE
        job.started_at = datetime.now(timezone.utc)
        self.stats["active"] += 1
        self.stats["pending"] -= 1
        
        # Get handler
        handler = self.handlers.get(job.job_type)
        if not handler:
            logger.error(f"No handler for job type: {job.job_type}")
            job.status = JobStatus.FAILED
            job.error = "No handler registered"
            self.stats["active"] -= 1
            self.stats["failed_24h"] += 1
            return job
        
        try:
            # Execute
            result = await handler(job.payload)
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.result = result
            self.stats["active"] -= 1
            self.stats["completed_24h"] += 1
            
            # Update rate limit usage
            if job.rate_limit_key:
                self._record_rate_limit(job.rate_limit_key)
            
        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            job.error = str(e)
            
            if job.retry_count < job.max_retries:
                # Retry
                job.retry_count += 1
                job.status = JobStatus.PENDING
                job.next_retry_at = datetime.now(timezone.utc) + timedelta(
                    seconds=job.retry_delay_seconds * job.retry_count
                )
                await self._requeue(job)
            else:
                # Move to dead letter
                job.status = JobStatus.DEAD
                self.stats["failed_24h"] += 1
                await self._move_to_dead_letter(job)
            
            self.stats["active"] -= 1
        
        # Update DB
        if self.db:
            await self.db.job_queue.update_one(
                {"id": job.id},
                {"$set": job.dict()}
            )
        
        return job
    
    async def process_all(self, job_type: JobType = None, max_jobs: int = 100):
        """
        Process all pending jobs of a type
        """
        processed = 0
        while processed < max_jobs:
            job = await self.process_next(job_type)
            if not job:
                break
            processed += 1
        return processed
    
    async def _get_next_job(self, job_type: JobType = None) -> Optional[Job]:
        """Get next job respecting priority"""
        # Check all queues in priority order
        for priority in sorted(JobPriority, key=lambda x: x.value):
            if job_type:
                queue_name = f"{job_type.value}_{priority.value}"
                if queue_name in self.queues and self.queues[queue_name]:
                    return self.queues[queue_name].popleft()
            else:
                # Check all job types at this priority
                for jt in JobType:
                    queue_name = f"{jt.value}_{priority.value}"
                    if queue_name in self.queues and self.queues[queue_name]:
                        return self.queues[queue_name].popleft()
        return None
    
    async def _requeue(self, job: Job):
        """Re-add job to queue"""
        queue_name = f"{job.job_type}_{job.priority}"
        if queue_name not in self.queues:
            self.queues[queue_name] = deque()
        self.queues[queue_name].append(job)
    
    async def _move_to_dead_letter(self, job: Job):
        """Move job to dead letter queue"""
        if self.db:
            await self.db.dead_letter_queue.insert_one(job.dict())
        logger.warning(f"Job {job.id} moved to dead letter queue")
    
    def _check_rate_limit(self, key: str) -> bool:
        """Check if rate limit allows request"""
        limit = self.rate_limits.get(key, 100)
        window_start = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        # Simple check - would need proper tracking for production
        last_request = self.rate_limiters.get(key)
        if last_request and last_request > window_start:
            return False
        return True
    
    def _record_rate_limit(self, key: str):
        """Record rate limit usage"""
        self.rate_limiters[key] = datetime.now(timezone.utc)
    
    def get_stats(self) -> Dict:
        """Get queue statistics"""
        total_pending = sum(len(q) for q in self.queues.values())
        return {
            "pending": total_pending,
            "active": self.stats["active"],
            "completed_24h": self.stats["completed_24h"],
            "failed_24h": self.stats["failed_24h"],
            "queues": {k: len(v) for k, v in self.queues.items() if v}
        }
    
    @staticmethod
    def _generate_job_id(job_type: JobType) -> str:
        """Generate unique job ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        hash_part = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"job_{job_type.value}_{hash_part}"


# =============================================================================
# JOB HANDLERS
# =============================================================================

class JobHandlers:
    """
    Standard job handlers
    """
    
    def __init__(self, db, services: Dict = None):
        self.db = db
        self.services = services or {}
    
    async def handle_news_ingest(self, payload: Dict) -> Dict:
        """Process incoming news article"""
        # Would call news processing pipeline
        return {"status": "processed", "article_id": payload.get("article_id")}
    
    async def handle_scoring_pipeline(self, payload: Dict) -> Dict:
        """Score an event"""
        from modules.intelligence.enhanced_scoring import enhanced_scoring_pipeline
        
        scores = enhanced_scoring_pipeline.score_article(
            title=payload.get("title", ""),
            content=payload.get("content", ""),
            source=payload.get("source", ""),
            entities=payload.get("entities", [])
        )
        
        return {"scores": scores.dict()}
    
    async def handle_feed_projection(self, payload: Dict) -> Dict:
        """Update feed projection for an event"""
        from modules.intelligence.feed_projection import FeedProjectionService
        
        service = FeedProjectionService(self.db)
        event = payload.get("event")
        
        if event:
            card = await service.create_card_from_event(event)
            return {"card_id": card.id}
        
        return {"status": "no_event"}
    
    async def handle_lifecycle_update(self, payload: Dict) -> Dict:
        """Update narrative lifecycle metrics"""
        from modules.narrative.enhanced_narrative import EnhancedNarrativeService
        
        service = EnhancedNarrativeService(self.db)
        narrative_id = payload.get("narrative_id")
        
        if narrative_id:
            await service.update_lifecycle_metrics(narrative_id)
            return {"status": "updated", "narrative_id": narrative_id}
        
        return {"status": "no_narrative_id"}


def setup_queue(db) -> JobQueue:
    """
    Setup job queue with handlers
    """
    queue = JobQueue(db)
    handlers = JobHandlers(db)
    
    # Register handlers
    queue.register_handler(JobType.NEWS_INGEST, handlers.handle_news_ingest)
    queue.register_handler(JobType.SCORING_PIPELINE, handlers.handle_scoring_pipeline)
    queue.register_handler(JobType.FEED_PROJECTION, handlers.handle_feed_projection)
    queue.register_handler(JobType.LIFECYCLE_UPDATE, handlers.handle_lifecycle_update)
    
    return queue
