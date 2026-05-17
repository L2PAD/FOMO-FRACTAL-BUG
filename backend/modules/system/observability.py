"""
System Observability Layer

Without this, the system becomes unmanageable after 1 year.

Tracks:
- Source health (parser/API success rates)
- Queue health (job completion rates)
- Scheduler health (job timing)
- Provider scores (data quality)
- Drift alerts (schema/API changes)
- System metrics (performance)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class HealthStatus(str, Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    CRITICAL = "critical"  # Immediate action required
    WARNING = "warning"    # Attention needed
    INFO = "info"          # FYI


class AlertType(str, Enum):
    """Types of system alerts"""
    SOURCE_OFFLINE = "source_offline"
    SOURCE_DEGRADED = "source_degraded"
    PARSER_FAILURE = "parser_failure"
    SCHEMA_DRIFT = "schema_drift"
    RATE_LIMIT = "rate_limit"
    DATA_QUALITY = "data_quality"
    SCHEDULER_DELAY = "scheduler_delay"
    QUEUE_BACKUP = "queue_backup"


# =============================================================================
# HEALTH MODELS
# =============================================================================

class SourceHealth(BaseModel):
    """Health metrics for a data source"""
    source_id: str
    source_name: str
    
    # Status
    status: HealthStatus = Field(HealthStatus.HEALTHY)
    last_check: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Success metrics
    success_rate_1h: float = Field(1.0, ge=0, le=1)
    success_rate_24h: float = Field(1.0, ge=0, le=1)
    total_requests_24h: int = 0
    failed_requests_24h: int = 0
    
    # Latency
    avg_latency_ms: float = 0
    p99_latency_ms: float = 0
    
    # Data quality
    data_freshness_minutes: int = 0
    records_fetched_24h: int = 0
    
    # Errors
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    consecutive_failures: int = 0
    
    class Config:
        use_enum_values = True


class ParserHealth(BaseModel):
    """Health metrics for a parser job"""
    parser_id: str
    parser_name: str
    source_id: str
    
    # Status
    status: HealthStatus = Field(HealthStatus.HEALTHY)
    is_running: bool = False
    
    # Execution metrics
    last_run: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    
    # Performance
    avg_duration_seconds: float = 0
    records_processed_last_run: int = 0
    
    # Error tracking
    error_count_24h: int = 0
    last_error: Optional[str] = None
    
    class Config:
        use_enum_values = True


class QueueHealth(BaseModel):
    """Health metrics for job queues"""
    queue_name: str
    
    # Status
    status: HealthStatus = Field(HealthStatus.HEALTHY)
    
    # Queue metrics
    pending_jobs: int = 0
    active_jobs: int = 0
    completed_24h: int = 0
    failed_24h: int = 0
    
    # Latency
    avg_wait_time_seconds: float = 0
    avg_process_time_seconds: float = 0
    
    # Dead letter queue
    dead_letter_count: int = 0
    
    class Config:
        use_enum_values = True


class SchedulerHealth(BaseModel):
    """Health metrics for scheduler"""
    scheduler_name: str
    
    # Status
    status: HealthStatus = Field(HealthStatus.HEALTHY)
    is_running: bool = True
    
    # Jobs
    total_jobs: int = 0
    active_jobs: int = 0
    paused_jobs: int = 0
    
    # Timing
    jobs_on_schedule: int = 0
    jobs_delayed: int = 0
    max_delay_seconds: float = 0
    
    # Last run
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        use_enum_values = True


class ProviderScore(BaseModel):
    """Quality score for a data provider"""
    provider_id: str
    provider_name: str
    
    # Scores (0-100)
    overall_score: float = Field(100, ge=0, le=100)
    reliability_score: float = Field(100, ge=0, le=100)
    freshness_score: float = Field(100, ge=0, le=100)
    accuracy_score: float = Field(100, ge=0, le=100)
    coverage_score: float = Field(100, ge=0, le=100)
    
    # Calculation basis
    sample_size: int = 0
    last_calculated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Trend
    score_trend: str = Field("stable", description="improving/stable/declining")
    score_change_7d: float = 0


class DriftAlert(BaseModel):
    """Alert for schema/API drift detection"""
    id: str
    alert_type: AlertType
    severity: AlertSeverity
    
    # Source
    source_id: str
    source_name: str
    
    # Details
    title: str
    description: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Drift specifics
    field_affected: Optional[str] = None
    expected_schema: Optional[Dict] = None
    actual_schema: Optional[Dict] = None
    
    # Resolution
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    # Auto-handling
    auto_handled: bool = False
    fallback_used: Optional[str] = None
    
    class Config:
        use_enum_values = True


class SystemMetrics(BaseModel):
    """Overall system performance metrics"""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Data volume
    events_created_24h: int = 0
    events_updated_24h: int = 0
    feed_cards_created_24h: int = 0
    articles_processed_24h: int = 0
    
    # Source stats
    active_sources: int = 0
    healthy_sources: int = 0
    degraded_sources: int = 0
    offline_sources: int = 0
    
    # Queue stats
    total_queue_depth: int = 0
    jobs_processed_24h: int = 0
    job_failure_rate: float = 0
    
    # Performance
    avg_event_processing_ms: float = 0
    avg_feed_query_ms: float = 0
    
    # Storage
    db_size_gb: float = 0
    hot_data_count: int = 0
    warm_data_count: int = 0
    archive_data_count: int = 0


# =============================================================================
# OBSERVABILITY SERVICE
# =============================================================================

class ObservabilityService:
    """
    Central observability service
    
    Responsibilities:
    - Collect health metrics
    - Detect and alert on issues
    - Track provider scores
    - Detect schema drift
    """
    
    def __init__(self, db):
        self.db = db
        self.source_health = db.source_health
        self.parser_health = db.parser_health
        self.queue_health = db.queue_health
        self.scheduler_health = db.scheduler_health
        self.provider_scores = db.provider_scores
        self.drift_alerts = db.drift_alerts
        self.system_metrics = db.system_metrics
    
    async def ensure_indexes(self):
        """Create indexes for observability collections"""
        await self.source_health.create_index("source_id", unique=True)
        await self.parser_health.create_index("parser_id", unique=True)
        await self.drift_alerts.create_index("id", unique=True)
        await self.drift_alerts.create_index([("is_resolved", 1), ("severity", -1)])
        await self.system_metrics.create_index("timestamp")
    
    # =========================================================================
    # SOURCE HEALTH
    # =========================================================================
    
    async def record_source_request(
        self,
        source_id: str,
        source_name: str,
        success: bool,
        latency_ms: float,
        records_fetched: int = 0,
        error: str = None
    ):
        """Record a source request for health tracking"""
        update = {
            "source_id": source_id,
            "source_name": source_name,
            "last_check": datetime.now(timezone.utc)
        }
        
        inc_ops = {"total_requests_24h": 1}
        if not success:
            inc_ops["failed_requests_24h"] = 1
            inc_ops["consecutive_failures"] = 1
            update["last_error"] = error
            update["last_error_time"] = datetime.now(timezone.utc)
        else:
            update["consecutive_failures"] = 0
            inc_ops["records_fetched_24h"] = records_fetched
        
        await self.source_health.update_one(
            {"source_id": source_id},
            {
                "$set": update,
                "$inc": inc_ops
            },
            upsert=True
        )
        
        # Update status
        await self._update_source_status(source_id)
    
    async def _update_source_status(self, source_id: str):
        """Update source health status based on metrics"""
        doc = await self.source_health.find_one({"source_id": source_id})
        if not doc:
            return
        
        total = doc.get("total_requests_24h", 0)
        failed = doc.get("failed_requests_24h", 0)
        consecutive = doc.get("consecutive_failures", 0)
        
        success_rate = 1.0 if total == 0 else (total - failed) / total
        
        # Determine status
        status = HealthStatus.HEALTHY
        if consecutive >= 10 or success_rate < 0.5:
            status = HealthStatus.OFFLINE
        elif consecutive >= 5 or success_rate < 0.8:
            status = HealthStatus.UNHEALTHY
        elif consecutive >= 2 or success_rate < 0.95:
            status = HealthStatus.DEGRADED
        
        await self.source_health.update_one(
            {"source_id": source_id},
            {"$set": {
                "status": status.value,
                "success_rate_24h": success_rate
            }}
        )
        
        # Create alert if needed
        if status in [HealthStatus.UNHEALTHY, HealthStatus.OFFLINE]:
            await self._create_source_alert(doc, status)
    
    async def _create_source_alert(self, source_doc: Dict, status: HealthStatus):
        """Create alert for source issues"""
        source_id = source_doc.get("source_id")
        
        # Check if alert already exists
        existing = await self.drift_alerts.find_one({
            "source_id": source_id,
            "alert_type": AlertType.SOURCE_OFFLINE.value if status == HealthStatus.OFFLINE else AlertType.SOURCE_DEGRADED.value,
            "is_resolved": False
        })
        
        if existing:
            return  # Don't duplicate
        
        alert = DriftAlert(
            id=f"alert_{source_id}_{datetime.now(timezone.utc).timestamp()}",
            alert_type=AlertType.SOURCE_OFFLINE if status == HealthStatus.OFFLINE else AlertType.SOURCE_DEGRADED,
            severity=AlertSeverity.CRITICAL if status == HealthStatus.OFFLINE else AlertSeverity.WARNING,
            source_id=source_id,
            source_name=source_doc.get("source_name", source_id),
            title=f"Source {status.value}: {source_id}",
            description=f"Source has {source_doc.get('consecutive_failures', 0)} consecutive failures. Last error: {source_doc.get('last_error', 'Unknown')}"
        )
        
        await self.drift_alerts.insert_one(alert.dict())
    
    async def get_source_health_summary(self) -> Dict:
        """Get summary of all source health"""
        pipeline = [
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        cursor = self.source_health.aggregate(pipeline)
        results = await cursor.to_list(length=10)
        
        summary = {
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "offline": 0
        }
        
        for r in results:
            status = r.get("_id", "healthy")
            summary[status] = r.get("count", 0)
        
        summary["total"] = sum(summary.values())
        return summary
    
    # =========================================================================
    # DRIFT DETECTION
    # =========================================================================
    
    async def detect_schema_drift(
        self,
        source_id: str,
        expected_fields: List[str],
        actual_fields: List[str]
    ) -> Optional[DriftAlert]:
        """
        Detect schema changes from a source
        
        This is called when parsing data to detect API changes
        """
        expected_set = set(expected_fields)
        actual_set = set(actual_fields)
        
        missing = expected_set - actual_set
        new = actual_set - expected_set
        
        if not missing and not new:
            return None  # No drift
        
        # Create alert
        alert = DriftAlert(
            id=f"drift_{source_id}_{datetime.now(timezone.utc).timestamp()}",
            alert_type=AlertType.SCHEMA_DRIFT,
            severity=AlertSeverity.WARNING if not missing else AlertSeverity.CRITICAL,
            source_id=source_id,
            source_name=source_id,
            title=f"Schema drift detected: {source_id}",
            description=f"Missing fields: {list(missing)}. New fields: {list(new)}",
            expected_schema={"fields": list(expected_fields)},
            actual_schema={"fields": list(actual_fields)}
        )
        
        await self.drift_alerts.insert_one(alert.dict())
        return alert
    
    async def get_active_alerts(
        self,
        severity: AlertSeverity = None,
        source_id: str = None,
        limit: int = 50
    ) -> List[DriftAlert]:
        """Get active (unresolved) alerts"""
        query = {"is_resolved": False}
        
        if severity:
            query["severity"] = severity.value
        if source_id:
            query["source_id"] = source_id
        
        cursor = self.drift_alerts.find(query).sort(
            "detected_at", -1
        ).limit(limit)
        
        alerts = await cursor.to_list(length=limit)
        return [DriftAlert(**a) for a in alerts]
    
    async def resolve_alert(
        self,
        alert_id: str,
        notes: str = None
    ):
        """Mark an alert as resolved"""
        await self.drift_alerts.update_one(
            {"id": alert_id},
            {"$set": {
                "is_resolved": True,
                "resolved_at": datetime.now(timezone.utc),
                "resolution_notes": notes
            }}
        )
    
    # =========================================================================
    # SYSTEM METRICS
    # =========================================================================
    
    async def record_system_metrics(self):
        """
        Record current system metrics snapshot
        
        Should be called periodically (every 5 min)
        """
        # Collect metrics from various sources
        source_summary = await self.get_source_health_summary()
        
        # Count recent activity
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(hours=24)
        
        events_24h = await self.db.root_events.count_documents({
            "first_seen": {"$gte": yesterday}
        })
        
        feed_cards_24h = await self.db.feed_cards.count_documents({
            "created_at": {"$gte": yesterday}
        })
        
        metrics = SystemMetrics(
            timestamp=now,
            events_created_24h=events_24h,
            feed_cards_created_24h=feed_cards_24h,
            active_sources=source_summary.get("total", 0),
            healthy_sources=source_summary.get("healthy", 0),
            degraded_sources=source_summary.get("degraded", 0),
            offline_sources=source_summary.get("offline", 0) + source_summary.get("unhealthy", 0)
        )
        
        await self.system_metrics.insert_one(metrics.dict())
        return metrics
    
    async def get_system_dashboard(self) -> Dict:
        """
        Get data for system health dashboard
        """
        return {
            "source_health": await self.get_source_health_summary(),
            "active_alerts": len(await self.get_active_alerts(limit=100)),
            "critical_alerts": len(await self.get_active_alerts(severity=AlertSeverity.CRITICAL)),
            "last_metrics": await self._get_latest_metrics()
        }
    
    async def _get_latest_metrics(self) -> Optional[Dict]:
        """Get most recent system metrics"""
        doc = await self.system_metrics.find_one(
            sort=[("timestamp", -1)]
        )
        return doc if doc else None
