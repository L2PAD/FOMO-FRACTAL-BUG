"""
Base Parser with Reliability Tracking
=====================================

Base class for all parsers that integrates with Source Reliability System.
Automatically tracks fetch success/failure, latency, and data freshness.

Usage:
    class MyParser(BaseReliableParser):
        source_id = "my_source"
        
        async def fetch_data(self):
            async with self.track_fetch("endpoint_name") as tracker:
                data = await self._do_fetch()
                tracker.set_freshness_hours(0.5)  # Data is 30 min old
                return data
"""

import time
import logging
from datetime import datetime, timezone
from typing import Optional, Any
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class FetchTracker:
    """Context manager for tracking a single fetch operation"""
    
    def __init__(self, parser: 'BaseReliableParser', endpoint: str):
        self.parser = parser
        self.endpoint = endpoint
        self.start_time = None
        self.success = False
        self.error = None
        self.freshness_hours = None
    
    def set_freshness_hours(self, hours: float):
        """Set data freshness in hours"""
        self.freshness_hours = hours
    
    def mark_success(self):
        """Mark fetch as successful"""
        self.success = True
    
    def mark_failure(self, error: str):
        """Mark fetch as failed"""
        self.success = False
        self.error = error
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        latency_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is not None:
            self.success = False
            self.error = str(exc_val)
        
        # Record to reliability system
        await self.parser._record_fetch(
            endpoint=self.endpoint,
            success=self.success,
            latency_ms=latency_ms,
            data_freshness_hours=self.freshness_hours,
            error=self.error
        )
        
        return False  # Don't suppress exceptions


class BaseReliableParser:
    """
    Base class for parsers with reliability tracking.
    
    Subclasses should:
    1. Set source_id class attribute
    2. Use track_fetch() context manager for all HTTP requests
    3. Call tracker.mark_success() on successful parsing
    """
    
    source_id: str = "unknown"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._reliability_system = None
    
    @property
    def reliability_system(self):
        """Lazy load reliability system"""
        if self._reliability_system is None:
            from modules.provider_gateway.source_reliability import get_source_reliability
            self._reliability_system = get_source_reliability(self.db)
        return self._reliability_system
    
    @asynccontextmanager
    async def track_fetch(self, endpoint: str = "default"):
        """
        Context manager for tracking fetch operations.
        
        Usage:
            async with self.track_fetch("coins") as tracker:
                data = await self.client.get(url)
                if data:
                    tracker.mark_success()
                    tracker.set_freshness_hours(0.5)
                return data
        """
        tracker = FetchTracker(self, endpoint)
        async with tracker:
            yield tracker
    
    async def _record_fetch(
        self,
        endpoint: str,
        success: bool,
        latency_ms: float,
        data_freshness_hours: Optional[float] = None,
        error: Optional[str] = None
    ):
        """Record fetch to reliability system"""
        try:
            if self.reliability_system:
                await self.reliability_system.record_fetch(
                    source_id=self.source_id,
                    success=success,
                    latency_ms=latency_ms,
                    data_freshness_hours=data_freshness_hours,
                    endpoint=endpoint,
                    error=error
                )
                
                if success:
                    logger.debug(f"[{self.source_id}] Fetch success: {endpoint} ({latency_ms:.0f}ms)")
                else:
                    logger.debug(f"[{self.source_id}] Fetch failed: {endpoint} - {error}")
        except Exception as e:
            # Don't fail the actual fetch if reliability tracking fails
            logger.warning(f"[{self.source_id}] Failed to record fetch: {e}")
    
    async def record_fetch_simple(
        self,
        success: bool,
        latency_ms: float,
        endpoint: str = "default",
        data_freshness_hours: Optional[float] = None,
        error: Optional[str] = None
    ):
        """
        Simple method to record fetch without context manager.
        
        Usage:
            start = time.time()
            try:
                data = await fetch()
                await self.record_fetch_simple(True, (time.time() - start) * 1000)
            except Exception as e:
                await self.record_fetch_simple(False, (time.time() - start) * 1000, error=str(e))
        """
        await self._record_fetch(
            endpoint=endpoint,
            success=success,
            latency_ms=latency_ms,
            data_freshness_hours=data_freshness_hours,
            error=error
        )


def create_reliable_wrapper(parser_class, db):
    """
    Factory function to wrap existing parser with reliability tracking.
    
    For parsers that don't inherit from BaseReliableParser.
    """
    
    class ReliableWrapper(BaseReliableParser):
        source_id = getattr(parser_class, 'source_id', 'unknown')
        
        def __init__(self, db):
            super().__init__(db)
            self.wrapped = parser_class(db)
        
        def __getattr__(self, name):
            return getattr(self.wrapped, name)
    
    return ReliableWrapper(db)
