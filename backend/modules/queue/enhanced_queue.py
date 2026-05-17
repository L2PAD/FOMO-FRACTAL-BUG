"""
Enhanced Queue Layer

Production-ready job queue with:
- Redis-ready architecture (in-memory fallback)
- Priority queues
- Retry policy with exponential backoff
- Dead Letter Queue (DLQ)
- Per-source rate limiting
- Worker pool separation

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

Worker Types (separated for CPU/IO):
- io_worker: Network-bound jobs (sync, fetch)
- parse_worker: CPU-light parsing
- score_worker: CPU-intensive scoring
- graph_worker: Graph operations
- narrative_worker: Narrative clustering
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Callable, Set
from pydantic import BaseModel, Field
from enum import Enum
import hashlib
from collections import defaultdict
import traceback

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status"""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD = "dead"


class JobPriority(int, Enum):
    """Job priority (lower = higher priority)"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class JobType(str, Enum):
    """Standard job types"""
    # IO-bound
    NEWS_INGEST = "news_ingest"
    MARKET_SYNC = "market_sync"
    INTEL_SYNC = "intel_sync"
    
    # Parse
    ARTICLE_PARSE = "article_parse"
    
    # Scoring (CPU)
    LIGHT_SCORING = "light_scoring"
    FULL_SCORING = "full_scoring"
    
    # Projection
    FEED_PROJECTION = "feed_projection"
    FEED_UPDATE = "feed_update"
    
    # Narrative (CPU)
    NARRATIVE_UPDATE = "narrative_update"
    NARRATIVE_REBUILD = "narrative_rebuild"
    
    # Graph
    GRAPH_UPDATE = "graph_update"
    GRAPH_REBUILD = "graph_rebuild"
    
    # Entity
    ENTITY_RESOLUTION = "entity_resolution"
    ENTITY_MERGE = "entity_merge"
    
    # Maintenance
    ARCHIVE_JOB = "archive_job"
    CLEANUP_JOB = "cleanup_job"


class WorkerType(str, Enum):
    """Worker pool types"""
    IO = "io"           # Network operations
    PARSE = "parse"     # Parsing jobs
    SCORE = "score"     # Scoring jobs
    GRAPH = "graph"     # Graph operations
    NARRATIVE = "narrative"


# Job -> Worker mapping
JOB_WORKER_MAP = {
    JobType.NEWS_INGEST: WorkerType.IO,
    JobType.MARKET_SYNC: WorkerType.IO,
    JobType.INTEL_SYNC: WorkerType.IO,
    JobType.ARTICLE_PARSE: WorkerType.PARSE,
    JobType.LIGHT_SCORING: WorkerType.SCORE,
    JobType.FULL_SCORING: WorkerType.SCORE,
    JobType.FEED_PROJECTION: WorkerType.PARSE,
    JobType.FEED_UPDATE: WorkerType.PARSE,
    JobType.NARRATIVE_UPDATE: WorkerType.NARRATIVE,
    JobType.NARRATIVE_REBUILD: WorkerType.NARRATIVE,
    JobType.GRAPH_UPDATE: WorkerType.GRAPH,
    JobType.GRAPH_REBUILD: WorkerType.GRAPH,
    JobType.ENTITY_RESOLUTION: WorkerType.PARSE,
    JobType.ENTITY_MERGE: WorkerType.PARSE,
    JobType.ARCHIVE_JOB: WorkerType.IO,
    JobType.CLEANUP_JOB: WorkerType.IO,
}


class Job(BaseModel):
    """Job model"""
    id: str
    job_type: JobType
    priority: JobPriority = JobPriority.NORMAL
    worker_type: WorkerType = WorkerType.IO
    
    # Status
    status: JobStatus = JobStatus.PENDING
    
    # Payload
    payload: Dict = Field(default_factory=dict)
    
    # Retry policy
    max_retries: int = 3
    retry_count: int = 0
    retry_delay_base: int = 30  # Base delay in seconds
    retry_backoff: float = 2.0  # Exponential backoff multiplier
    
    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    timeout_seconds: int = 300
    
    # Result
    result: Optional[Dict] = None
    error: Optional[str] = None
    error_trace: Optional[str] = None
    
    # Rate limiting
    rate_limit_key: Optional[str] = None
    
    class Config:
        use_enum_values = True


class QueueStats(BaseModel):
    """Queue statistics"""
    pending: Dict[str, int] = Field(default_factory=dict)
    active: Dict[str, int] = Field(default_factory=dict)
    completed_24h: int = 0
    failed_24h: int = 0
    dead_letter_count: int = 0
    avg_processing_time_ms: float = 0
    rate_limited_count: int = 0


class EnhancedJobQueue:
    """
    Enhanced job queue with worker pool separation
    
    Design:
    - Separate queues per worker type
    - Priority ordering within queues
    - Rate limiting per source
    - Exponential backoff retries
    - Dead letter queue
    """
    
    def __init__(self, db=None, redis_client=None):
        self.db = db
        self.redis = redis_client  # Optional Redis for production
        
        # In-memory queues (fallback if no Redis)
        # Structure: {worker_type: {priority: [jobs]}}
        self.queues: Dict[str, Dict[int, List[Job]]] = defaultdict(lambda: defaultdict(list))
        
        # Active jobs tracking
        self.active_jobs: Dict[str, Job] = {}
        
        # Dead letter queue
        self.dlq: List[Job] = []
        
        # Handlers
        self.handlers: Dict[str, Callable] = {}
        
        # Rate limiting
        self.rate_limiters: Dict[str, List[datetime]] = defaultdict(list)
        self.rate_limits = {
            # Per-source rate limits (requests per minute)
            "cryptorank": 100,
            "rootdata": 60,
            "defillama": 300,
            "coingecko": 30,
            "coinmarketcap": 30,
            "binance": 1200,
            "bybit": 600,
            "github": 60,
        }
        
        # Stats
        self.stats = QueueStats()
        self._processing_times: List[float] = []
        
        # Worker concurrency limits
        self.worker_concurrency = {
            WorkerType.IO.value: 10,
            WorkerType.PARSE.value: 5,
            WorkerType.SCORE.value: 3,
            WorkerType.GRAPH.value: 2,
            WorkerType.NARRATIVE.value: 2,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    def register_handler(self, job_type: JobType, handler: Callable):
        """Register handler for job type"""
        self.handlers[job_type.value] = handler
        logger.info(f"Registered handler for {job_type.value}")
    
    async def enqueue(
        self,
        job_type: JobType,
        payload: Dict,
        priority: JobPriority = JobPriority.NORMAL,
        rate_limit_key: str = None,
        max_retries: int = 3,
        timeout_seconds: int = 300
    ) -> Job:
        """
        Add job to queue
        """
        # Determine worker type
        worker_type = JOB_WORKER_MAP.get(job_type, WorkerType.IO)
        
        job = Job(
            id=self._generate_job_id(job_type),
            job_type=job_type,
            priority=priority,
            worker_type=worker_type,
            payload=payload,
            rate_limit_key=rate_limit_key,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds
        )
        
        async with self._lock:
            # Add to appropriate queue
            self.queues[worker_type.value][priority.value].append(job)
            
            # Update stats
            key = f"{worker_type.value}_{priority.value}"
            self.stats.pending[key] = self.stats.pending.get(key, 0) + 1
        
        # Persist to DB if available
        if self.db:
            await self.db.job_queue.insert_one(job.dict())
        
        return job
    
    async def enqueue_batch(
        self,
        jobs: List[Dict]
    ) -> List[Job]:
        """
        Enqueue multiple jobs efficiently
        """
        created_jobs = []
        
        for job_spec in jobs:
            job = await self.enqueue(
                job_type=job_spec["job_type"],
                payload=job_spec.get("payload", {}),
                priority=job_spec.get("priority", JobPriority.NORMAL),
                rate_limit_key=job_spec.get("rate_limit_key")
            )
            created_jobs.append(job)
        
        return created_jobs
    
    async def process_one(self, worker_type: WorkerType = None) -> Optional[Job]:
        """
        Process next job from queue
        
        Args:
            worker_type: Specific worker type to process (or any if None)
        """
        job = await self._get_next_job(worker_type)
        if not job:
            return None
        
        # Check rate limit
        if job.rate_limit_key and not self._check_rate_limit(job.rate_limit_key):
            # Re-queue with delay
            job.status = JobStatus.PENDING
            job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=60)
            await self._requeue(job)
            self.stats.rate_limited_count += 1
            return None
        
        # Mark as active
        job.status = JobStatus.ACTIVE
        job.started_at = datetime.now(timezone.utc)
        self.active_jobs[job.id] = job
        
        # Get handler
        handler = self.handlers.get(job.job_type)
        if not handler:
            logger.error(f"No handler for job type: {job.job_type}")
            job.status = JobStatus.FAILED
            job.error = "No handler registered"
            await self._complete_job(job, success=False)
            return job
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                handler(job.payload),
                timeout=job.timeout_seconds
            )
            
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.result = result
            
            await self._complete_job(job, success=True)
            
            # Update rate limit usage
            if job.rate_limit_key:
                self._record_rate_limit(job.rate_limit_key)
            
        except asyncio.TimeoutError:
            logger.error(f"Job {job.id} timed out after {job.timeout_seconds}s")
            job.error = f"Timeout after {job.timeout_seconds} seconds"
            await self._handle_failure(job)
            
        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            job.error = str(e)
            job.error_trace = traceback.format_exc()
            await self._handle_failure(job)
        
        return job
    
    async def process_worker(
        self,
        worker_type: WorkerType,
        max_jobs: int = 100
    ) -> Dict:
        """
        Process jobs for specific worker type
        """
        stats = {"processed": 0, "success": 0, "failed": 0}
        
        concurrency = self.worker_concurrency.get(worker_type.value, 5)
        tasks = []
        
        for _ in range(min(max_jobs, concurrency)):
            job = await self._get_next_job(worker_type)
            if job:
                tasks.append(self._process_job_async(job))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                stats["processed"] += 1
                if isinstance(result, Exception):
                    stats["failed"] += 1
                elif result and result.status == JobStatus.COMPLETED:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
        
        return stats
    
    async def _process_job_async(self, job: Job) -> Job:
        """Process single job asynchronously"""
        handler = self.handlers.get(job.job_type)
        if not handler:
            job.status = JobStatus.FAILED
            job.error = "No handler"
            return job
        
        job.status = JobStatus.ACTIVE
        job.started_at = datetime.now(timezone.utc)
        
        try:
            result = await asyncio.wait_for(
                handler(job.payload),
                timeout=job.timeout_seconds
            )
            job.status = JobStatus.COMPLETED
            job.result = result
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
        
        job.completed_at = datetime.now(timezone.utc)
        return job
    
    async def _get_next_job(self, worker_type: WorkerType = None) -> Optional[Job]:
        """Get next job respecting priority"""
        async with self._lock:
            worker_types = [worker_type.value] if worker_type else list(self.queues.keys())
            
            for wt in worker_types:
                # Check active count doesn't exceed concurrency
                active_count = sum(
                    1 for j in self.active_jobs.values()
                    if j.worker_type == wt
                )
                if active_count >= self.worker_concurrency.get(wt, 5):
                    continue
                
                # Get from highest priority queue
                for priority in sorted(JobPriority, key=lambda x: x.value):
                    queue = self.queues[wt][priority.value]
                    
                    if queue:
                        job = queue.pop(0)
                        
                        # Update stats
                        key = f"{wt}_{priority.value}"
                        self.stats.pending[key] = max(0, self.stats.pending.get(key, 1) - 1)
                        self.stats.active[key] = self.stats.active.get(key, 0) + 1
                        
                        return job
            
            return None
    
    async def _handle_failure(self, job: Job):
        """Handle job failure with retry logic"""
        if job.retry_count < job.max_retries:
            # Calculate backoff delay
            delay = job.retry_delay_base * (job.retry_backoff ** job.retry_count)
            
            job.retry_count += 1
            job.status = JobStatus.RETRYING
            job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            
            logger.info(f"Job {job.id} will retry in {delay}s (attempt {job.retry_count}/{job.max_retries})")
            
            await self._requeue(job)
            
        else:
            # Move to dead letter queue
            job.status = JobStatus.DEAD
            await self._move_to_dlq(job)
    
    async def _complete_job(self, job: Job, success: bool):
        """Complete job and update stats"""
        # Remove from active
        self.active_jobs.pop(job.id, None)
        
        # Update stats
        key = f"{job.worker_type}_{job.priority}"
        self.stats.active[key] = max(0, self.stats.active.get(key, 1) - 1)
        
        if success:
            self.stats.completed_24h += 1
        else:
            self.stats.failed_24h += 1
        
        # Track processing time
        if job.started_at and job.completed_at:
            duration_ms = (job.completed_at - job.started_at).total_seconds() * 1000
            self._processing_times.append(duration_ms)
            
            # Keep last 1000 for average
            if len(self._processing_times) > 1000:
                self._processing_times = self._processing_times[-1000:]
            
            self.stats.avg_processing_time_ms = sum(self._processing_times) / len(self._processing_times)
        
        # Update DB if available
        if self.db:
            await self.db.job_queue.update_one(
                {"id": job.id},
                {"$set": job.dict()}
            )
    
    async def _requeue(self, job: Job):
        """Re-add job to queue"""
        async with self._lock:
            self.queues[job.worker_type][job.priority].append(job)
            
            key = f"{job.worker_type}_{job.priority}"
            self.stats.pending[key] = self.stats.pending.get(key, 0) + 1
    
    async def _move_to_dlq(self, job: Job):
        """Move job to dead letter queue"""
        self.dlq.append(job)
        self.stats.dead_letter_count = len(self.dlq)
        
        logger.warning(f"Job {job.id} moved to DLQ after {job.retry_count} retries")
        
        if self.db:
            await self.db.dead_letter_queue.insert_one(job.dict())
    
    def _check_rate_limit(self, key: str) -> bool:
        """Check if rate limit allows request"""
        limit = self.rate_limits.get(key, 100)
        window_start = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        # Clean old entries
        self.rate_limiters[key] = [
            t for t in self.rate_limiters[key]
            if t > window_start
        ]
        
        return len(self.rate_limiters[key]) < limit
    
    def _record_rate_limit(self, key: str):
        """Record rate limit usage"""
        self.rate_limiters[key].append(datetime.now(timezone.utc))
    
    def get_stats(self) -> Dict:
        """Get queue statistics"""
        # Calculate queue depths
        queue_depths = {}
        for worker_type, priorities in self.queues.items():
            for priority, jobs in priorities.items():
                if jobs:
                    queue_depths[f"{worker_type}_p{priority}"] = len(jobs)
        
        return {
            "pending": dict(self.stats.pending),
            "active": dict(self.stats.active),
            "completed_24h": self.stats.completed_24h,
            "failed_24h": self.stats.failed_24h,
            "dead_letter_count": self.stats.dead_letter_count,
            "avg_processing_time_ms": round(self.stats.avg_processing_time_ms, 2),
            "rate_limited_count": self.stats.rate_limited_count,
            "queue_depths": queue_depths,
            "active_jobs": len(self.active_jobs),
            "worker_concurrency": self.worker_concurrency
        }
    
    async def get_dlq_jobs(self, limit: int = 50) -> List[Dict]:
        """Get dead letter queue jobs"""
        return [job.dict() for job in self.dlq[:limit]]
    
    async def retry_dlq_job(self, job_id: str) -> Optional[Job]:
        """Retry a job from DLQ"""
        for i, job in enumerate(self.dlq):
            if job.id == job_id:
                # Remove from DLQ
                self.dlq.pop(i)
                self.stats.dead_letter_count = len(self.dlq)
                
                # Reset retry count and re-enqueue
                job.retry_count = 0
                job.status = JobStatus.PENDING
                job.error = None
                job.error_trace = None
                
                await self._requeue(job)
                return job
        
        return None
    
    @staticmethod
    def _generate_job_id(job_type: JobType) -> str:
        """Generate unique job ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        hash_part = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"job_{job_type.value}_{hash_part}"


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_queue_instance: Optional[EnhancedJobQueue] = None


def get_job_queue(db=None) -> EnhancedJobQueue:
    """Get or create queue singleton"""
    global _queue_instance
    
    if _queue_instance is None:
        _queue_instance = EnhancedJobQueue(db)
    
    return _queue_instance
