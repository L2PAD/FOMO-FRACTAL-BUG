"""
Parser Sandbox Layer
====================

Provides isolation and resource limits for parser workers.
Prevents broken parsers from crashing the entire system.
"""

import asyncio
import logging
import time
import traceback
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SandboxStatus(str, Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"
    VALIDATION_FAILED = "validation_failed"
    RESOURCE_EXCEEDED = "resource_exceeded"


@dataclass
class SandboxConfig:
    """Sandbox configuration."""
    timeout_seconds: float = 10.0
    max_response_size: int = 2 * 1024 * 1024  # 2MB
    max_articles_per_fetch: int = 50
    retry_count: int = 3
    retry_delay: float = 1.0


@dataclass
class SandboxResult:
    """Result from sandboxed parser execution."""
    status: SandboxStatus
    source_id: str
    articles_count: int
    duration_ms: float
    error_message: Optional[str] = None
    articles: Optional[List[Any]] = None


class ParserSandbox:
    """
    Executes parsers in isolated environment with:
    - Timeout protection
    - Resource limits
    - Error isolation
    - Retry logic
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.execution_stats: Dict[str, Dict] = {}
    
    async def execute(
        self,
        source_id: str,
        parser_func: Callable,
        *args,
        **kwargs
    ) -> SandboxResult:
        """
        Execute parser in sandbox with timeout and error handling.
        """
        start_time = time.time()
        
        for attempt in range(self.config.retry_count):
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    parser_func(*args, **kwargs),
                    timeout=self.config.timeout_seconds
                )
                
                duration_ms = (time.time() - start_time) * 1000
                
                # Validate result
                if result is None:
                    result = []
                
                articles_count = len(result) if isinstance(result, list) else 0
                
                # Check limits
                if articles_count > self.config.max_articles_per_fetch:
                    logger.warning(f"[Sandbox] {source_id}: too many articles ({articles_count}), truncating")
                    result = result[:self.config.max_articles_per_fetch]
                    articles_count = len(result)
                
                # Update stats
                self._update_stats(source_id, SandboxStatus.SUCCESS, duration_ms)
                
                return SandboxResult(
                    status=SandboxStatus.SUCCESS,
                    source_id=source_id,
                    articles_count=articles_count,
                    duration_ms=duration_ms,
                    articles=result
                )
                
            except asyncio.TimeoutError:
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(f"[Sandbox] {source_id}: timeout after {duration_ms:.0f}ms (attempt {attempt + 1})")
                
                if attempt < self.config.retry_count - 1:
                    await asyncio.sleep(self.config.retry_delay)
                    continue
                
                self._update_stats(source_id, SandboxStatus.TIMEOUT, duration_ms)
                
                return SandboxResult(
                    status=SandboxStatus.TIMEOUT,
                    source_id=source_id,
                    articles_count=0,
                    duration_ms=duration_ms,
                    error_message=f"Timeout after {self.config.timeout_seconds}s"
                )
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                error_msg = f"{type(e).__name__}: {str(e)}"
                logger.error(f"[Sandbox] {source_id}: error - {error_msg}")
                
                if attempt < self.config.retry_count - 1:
                    await asyncio.sleep(self.config.retry_delay)
                    continue
                
                self._update_stats(source_id, SandboxStatus.ERROR, duration_ms)
                
                return SandboxResult(
                    status=SandboxStatus.ERROR,
                    source_id=source_id,
                    articles_count=0,
                    duration_ms=duration_ms,
                    error_message=error_msg
                )
        
        # Should not reach here
        return SandboxResult(
            status=SandboxStatus.ERROR,
            source_id=source_id,
            articles_count=0,
            duration_ms=(time.time() - start_time) * 1000,
            error_message="Unknown error"
        )
    
    def _update_stats(self, source_id: str, status: SandboxStatus, duration_ms: float):
        """Update execution statistics for source."""
        if source_id not in self.execution_stats:
            self.execution_stats[source_id] = {
                "total_executions": 0,
                "successes": 0,
                "timeouts": 0,
                "errors": 0,
                "total_duration_ms": 0,
                "last_execution": None,
                "last_status": None
            }
        
        stats = self.execution_stats[source_id]
        stats["total_executions"] += 1
        stats["total_duration_ms"] += duration_ms
        stats["last_execution"] = datetime.now(timezone.utc).isoformat()
        stats["last_status"] = status.value
        
        if status == SandboxStatus.SUCCESS:
            stats["successes"] += 1
        elif status == SandboxStatus.TIMEOUT:
            stats["timeouts"] += 1
        else:
            stats["errors"] += 1
    
    def get_source_health(self, source_id: str) -> Dict[str, Any]:
        """Get health metrics for a source."""
        if source_id not in self.execution_stats:
            return {
                "source_id": source_id,
                "health_score": 1.0,
                "status": "unknown"
            }
        
        stats = self.execution_stats[source_id]
        total = stats["total_executions"]
        
        if total == 0:
            return {
                "source_id": source_id,
                "health_score": 1.0,
                "status": "no_data"
            }
        
        success_rate = stats["successes"] / total
        avg_duration = stats["total_duration_ms"] / total
        
        # Calculate health score
        health_score = success_rate
        
        # Penalize slow sources
        if avg_duration > 5000:
            health_score *= 0.9
        elif avg_duration > 8000:
            health_score *= 0.7
        
        # Determine status
        if health_score >= 0.9:
            status = "healthy"
        elif health_score >= 0.7:
            status = "degraded"
        elif health_score >= 0.5:
            status = "unhealthy"
        else:
            status = "critical"
        
        return {
            "source_id": source_id,
            "health_score": round(health_score, 3),
            "success_rate": round(success_rate, 3),
            "avg_duration_ms": round(avg_duration, 1),
            "total_executions": total,
            "successes": stats["successes"],
            "timeouts": stats["timeouts"],
            "errors": stats["errors"],
            "last_execution": stats["last_execution"],
            "last_status": stats["last_status"],
            "status": status
        }
    
    def get_all_health(self) -> List[Dict[str, Any]]:
        """Get health metrics for all sources."""
        return [
            self.get_source_health(source_id)
            for source_id in self.execution_stats
        ]
    
    def should_pause_source(self, source_id: str, error_threshold: float = 0.5) -> bool:
        """Check if source should be paused due to errors."""
        health = self.get_source_health(source_id)
        
        if health.get("total_executions", 0) < 3:
            return False
        
        return health.get("success_rate", 1.0) < error_threshold


# Global sandbox instance
_sandbox: Optional[ParserSandbox] = None


def get_sandbox() -> ParserSandbox:
    """Get global sandbox instance."""
    global _sandbox
    if _sandbox is None:
        _sandbox = ParserSandbox()
    return _sandbox
