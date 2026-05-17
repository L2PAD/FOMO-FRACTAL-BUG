"""
Source Health Monitor
=====================

Monitors health of news sources and automatically pauses problematic ones.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SourceStatus(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    PAUSED = "paused"
    DISABLED = "disabled"


@dataclass
class SourceHealthMetrics:
    """Health metrics for a single source."""
    source_id: str
    source_name: str = ""
    
    # Fetch metrics
    total_fetches: int = 0
    successful_fetches: int = 0
    failed_fetches: int = 0
    timeout_fetches: int = 0
    
    # Validation metrics
    total_articles: int = 0
    valid_articles: int = 0
    invalid_articles: int = 0
    avg_confidence: float = 1.0
    
    # Timing
    avg_latency_ms: float = 0.0
    last_fetch: Optional[str] = None
    last_success: Optional[str] = None
    last_error: Optional[str] = None
    last_error_message: Optional[str] = None
    
    # Status
    status: SourceStatus = SourceStatus.ACTIVE
    consecutive_errors: int = 0
    paused_until: Optional[str] = None
    
    def success_rate(self) -> float:
        if self.total_fetches == 0:
            return 1.0
        return self.successful_fetches / self.total_fetches
    
    def valid_rate(self) -> float:
        if self.total_articles == 0:
            return 1.0
        return self.valid_articles / self.total_articles
    
    def health_score(self) -> float:
        """Calculate overall health score (0-1)."""
        fetch_score = self.success_rate()
        valid_score = self.valid_rate()
        confidence_score = self.avg_confidence
        
        # Weighted average
        return (
            fetch_score * 0.4 +
            valid_score * 0.3 +
            confidence_score * 0.3
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "status": self.status.value,
            "health_score": round(self.health_score(), 3),
            "success_rate": round(self.success_rate(), 3),
            "valid_rate": round(self.valid_rate(), 3),
            "avg_confidence": round(self.avg_confidence, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "total_fetches": self.total_fetches,
            "total_articles": self.total_articles,
            "consecutive_errors": self.consecutive_errors,
            "last_fetch": self.last_fetch,
            "last_success": self.last_success,
            "last_error": self.last_error,
            "last_error_message": self.last_error_message,
            "paused_until": self.paused_until
        }


class SourceHealthMonitor:
    """
    Monitors health of news sources.
    
    Features:
    - Tracks fetch success/failure
    - Tracks validation metrics
    - Auto-pause problematic sources
    - Drift detection
    """
    
    def __init__(self, db=None):
        self.db = db
        self.sources: Dict[str, SourceHealthMetrics] = {}
        
        # Config
        self.error_threshold = 5  # Consecutive errors before pause
        self.pause_duration_minutes = 30
        self.min_health_score = 0.4
    
    def get_or_create_metrics(self, source_id: str, source_name: str = "") -> SourceHealthMetrics:
        """Get or create metrics for source."""
        if source_id not in self.sources:
            self.sources[source_id] = SourceHealthMetrics(
                source_id=source_id,
                source_name=source_name
            )
        return self.sources[source_id]
    
    def record_fetch(
        self,
        source_id: str,
        source_name: str,
        success: bool,
        articles_count: int = 0,
        latency_ms: float = 0,
        error_message: Optional[str] = None,
        is_timeout: bool = False
    ):
        """Record a fetch attempt."""
        metrics = self.get_or_create_metrics(source_id, source_name)
        now = datetime.now(timezone.utc).isoformat()
        
        metrics.total_fetches += 1
        metrics.last_fetch = now
        
        # Update latency (rolling average)
        n = metrics.total_fetches
        metrics.avg_latency_ms = (
            (metrics.avg_latency_ms * (n - 1) + latency_ms) / n
        )
        
        if success:
            metrics.successful_fetches += 1
            metrics.last_success = now
            metrics.consecutive_errors = 0
            metrics.total_articles += articles_count
        else:
            metrics.failed_fetches += 1
            metrics.consecutive_errors += 1
            metrics.last_error = now
            metrics.last_error_message = error_message
            
            if is_timeout:
                metrics.timeout_fetches += 1
        
        # Check if should pause
        self._check_auto_pause(metrics)
    
    def record_validation(
        self,
        source_id: str,
        is_valid: bool,
        confidence: float
    ):
        """Record article validation result."""
        if source_id not in self.sources:
            return
        
        metrics = self.sources[source_id]
        
        if is_valid:
            metrics.valid_articles += 1
        else:
            metrics.invalid_articles += 1
        
        # Update average confidence (rolling)
        total = metrics.valid_articles + metrics.invalid_articles
        metrics.avg_confidence = (
            (metrics.avg_confidence * (total - 1) + confidence) / total
        )
    
    def _check_auto_pause(self, metrics: SourceHealthMetrics):
        """Check if source should be auto-paused."""
        # Already paused
        if metrics.status == SourceStatus.PAUSED:
            return
        
        # Too many consecutive errors
        if metrics.consecutive_errors >= self.error_threshold:
            self._pause_source(metrics, f"Too many errors ({metrics.consecutive_errors})")
            return
        
        # Low health score (after enough data)
        if metrics.total_fetches >= 10 and metrics.health_score() < self.min_health_score:
            self._pause_source(metrics, f"Low health score ({metrics.health_score():.2f})")
            return
        
        # Update status based on health
        health = metrics.health_score()
        if health >= 0.8:
            metrics.status = SourceStatus.ACTIVE
        elif health >= 0.5:
            metrics.status = SourceStatus.DEGRADED
    
    def _pause_source(self, metrics: SourceHealthMetrics, reason: str):
        """Pause a source."""
        metrics.status = SourceStatus.PAUSED
        pause_until = datetime.now(timezone.utc) + timedelta(minutes=self.pause_duration_minutes)
        metrics.paused_until = pause_until.isoformat()
        
        logger.warning(f"[HealthMonitor] Paused source {metrics.source_id}: {reason}")
    
    def is_source_available(self, source_id: str) -> bool:
        """Check if source is available for fetching."""
        if source_id not in self.sources:
            return True
        
        metrics = self.sources[source_id]
        
        if metrics.status == SourceStatus.DISABLED:
            return False
        
        if metrics.status == SourceStatus.PAUSED:
            # Check if pause expired
            if metrics.paused_until:
                pause_until = datetime.fromisoformat(metrics.paused_until)
                if datetime.now(timezone.utc) >= pause_until:
                    # Unpause
                    metrics.status = SourceStatus.DEGRADED
                    metrics.paused_until = None
                    metrics.consecutive_errors = 0
                    logger.info(f"[HealthMonitor] Unpaused source {source_id}")
                    return True
            return False
        
        return True
    
    def get_source_health(self, source_id: str) -> Dict[str, Any]:
        """Get health metrics for a source."""
        if source_id not in self.sources:
            return {
                "source_id": source_id,
                "status": "unknown",
                "health_score": 1.0
            }
        return self.sources[source_id].to_dict()
    
    def get_all_health(self) -> List[Dict[str, Any]]:
        """Get health metrics for all sources."""
        return [
            metrics.to_dict()
            for metrics in sorted(
                self.sources.values(),
                key=lambda m: m.health_score()
            )
        ]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of source health."""
        total = len(self.sources)
        if total == 0:
            return {
                "total_sources": 0,
                "active": 0,
                "degraded": 0,
                "paused": 0,
                "disabled": 0,
                "avg_health_score": 1.0
            }
        
        active = sum(1 for m in self.sources.values() if m.status == SourceStatus.ACTIVE)
        degraded = sum(1 for m in self.sources.values() if m.status == SourceStatus.DEGRADED)
        paused = sum(1 for m in self.sources.values() if m.status == SourceStatus.PAUSED)
        disabled = sum(1 for m in self.sources.values() if m.status == SourceStatus.DISABLED)
        
        avg_health = sum(m.health_score() for m in self.sources.values()) / total
        
        return {
            "total_sources": total,
            "active": active,
            "degraded": degraded,
            "paused": paused,
            "disabled": disabled,
            "avg_health_score": round(avg_health, 3)
        }
    
    def detect_drift(self, source_id: str) -> bool:
        """Detect if parser might be drifting."""
        if source_id not in self.sources:
            return False
        
        metrics = self.sources[source_id]
        
        # Need enough data
        if metrics.total_articles < 10:
            return False
        
        # Low validation rate indicates drift
        if metrics.valid_rate() < 0.5:
            return True
        
        # Low confidence indicates drift
        if metrics.avg_confidence < 0.6:
            return True
        
        return False


# Global monitor instance
_monitor: Optional[SourceHealthMonitor] = None


def get_health_monitor() -> SourceHealthMonitor:
    """Get global health monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = SourceHealthMonitor()
    return _monitor
