"""
Base Provider Adapter
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class AdapterResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    latency_ms: float = 0
    source: str = ""


class BaseAdapter(ABC):
    """Base class for all provider adapters"""
    
    def __init__(self, name: str, priority: int = 5):
        self.name = name
        self.priority = priority
        self._last_latency: float = 0
        self._error_count: int = 0
        self._success_count: int = 0
        self._last_error: Optional[str] = None
    
    @property
    def latency(self) -> float:
        return self._last_latency
    
    @property
    def is_healthy(self) -> bool:
        return self._error_count < 3
    
    @property
    def success_rate(self) -> float:
        total = self._success_count + self._error_count
        return (self._success_count / total * 100) if total > 0 else 100
    
    def _record_success(self, latency_ms: float):
        self._last_latency = latency_ms
        self._success_count += 1
        self._error_count = max(0, self._error_count - 1)  # decay errors
    
    def _record_error(self, error: str):
        self._error_count += 1
        self._last_error = error
    
    async def _timed_request(self, coro) -> AdapterResult:
        """Execute request with timing"""
        start = time.time()
        try:
            result = await coro
            latency_ms = (time.time() - start) * 1000
            self._record_success(latency_ms)
            return AdapterResult(
                success=True,
                data=result,
                latency_ms=latency_ms,
                source=self.name
            )
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            error_msg = str(e)
            self._record_error(error_msg)
            logger.warning(f"[{self.name}] Request failed: {error_msg}")
            return AdapterResult(
                success=False,
                error=error_msg,
                latency_ms=latency_ms,
                source=self.name
            )
    
    # === Abstract methods - must be implemented by adapters ===
    
    @abstractmethod
    async def get_quote(self, asset: str) -> AdapterResult:
        """Get single asset quote"""
        pass
    
    @abstractmethod
    async def get_bulk_quotes(self, assets: List[str]) -> AdapterResult:
        """Get quotes for multiple assets"""
        pass
    
    @abstractmethod
    async def get_overview(self) -> AdapterResult:
        """Get market overview"""
        pass
    
    async def get_candles(self, asset: str, interval: str, limit: int = 100) -> AdapterResult:
        """Get OHLCV candles - optional"""
        return AdapterResult(success=False, error="Not supported", source=self.name)
    
    async def health_check(self) -> AdapterResult:
        """Check adapter health"""
        return AdapterResult(
            success=self.is_healthy,
            data={
                "latency_ms": self._last_latency,
                "success_rate": self.success_rate,
                "error_count": self._error_count,
                "last_error": self._last_error
            },
            source=self.name
        )
