"""
Exchange Tree Scheduler
=======================
Separate scheduler for market data from exchanges.
Independent from Intel Tree scheduler.

Exchange Tree handles:
- Price data (real-time)
- OHLCV candles
- Volume
- Open Interest
- Funding rates
- Liquidations
- Trading pairs
- Exchange markets

Intervals:
- Prices: 5s-1min (real-time via WebSocket preferred)
- Candles: 1min
- OI/Funding: 1min
- Instruments: 30min
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Exchange sync intervals (seconds)
EXCHANGE_INTERVALS = {
    "prices": 60,        # 1 min (fallback, prefer WebSocket)
    "candles": 60,       # 1 min
    "funding": 60,       # 1 min
    "oi": 60,            # 1 min
    "instruments": 1800, # 30 min
}


@dataclass
class ExchangeHealth:
    """Health tracking for exchange provider"""
    exchange_id: str
    success_count: int = 0
    fail_count: int = 0
    consecutive_fails: int = 0
    last_success: Optional[datetime] = None
    last_fail: Optional[datetime] = None
    latency_ms: float = 0
    is_paused: bool = False
    
    @property
    def health_score(self) -> float:
        if self.success_count + self.fail_count == 0:
            return 1.0
        base = self.success_count / (self.success_count + self.fail_count)
        if self.consecutive_fails > 0:
            base -= min(0.3, self.consecutive_fails * 0.1)
        return max(0, min(1, base))
    
    def record_success(self, latency_ms: float = 0):
        self.success_count += 1
        self.consecutive_fails = 0
        self.last_success = datetime.now(timezone.utc)
        self.latency_ms = latency_ms
    
    def record_fail(self):
        self.fail_count += 1
        self.consecutive_fails += 1
        self.last_fail = datetime.now(timezone.utc)
        if self.consecutive_fails >= 5:
            self.is_paused = True
    
    def to_dict(self) -> Dict:
        return {
            "exchange_id": self.exchange_id,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "consecutive_fails": self.consecutive_fails,
            "health_score": round(self.health_score, 2),
            "latency_ms": round(self.latency_ms, 1),
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "is_paused": self.is_paused
        }


class ExchangeTreeScheduler:
    """
    Scheduler for Exchange Tree data.
    Separate from Intel Tree - handles market data only.
    """
    
    def __init__(self, db):
        self.db = db
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._running = False
        self._exchange_health: Dict[str, ExchangeHealth] = {}
        self._last_sync: Dict[str, datetime] = {}
        
        # Supported exchanges
        self.exchanges = ["binance", "bybit", "hyperliquid"]
    
    def _get_health(self, exchange_id: str) -> ExchangeHealth:
        if exchange_id not in self._exchange_health:
            self._exchange_health[exchange_id] = ExchangeHealth(exchange_id=exchange_id)
        return self._exchange_health[exchange_id]
    
    # ═══════════════════════════════════════════════════════════════
    # SYNC FUNCTIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def _sync_instruments(self):
        """Sync trading instruments from all exchanges"""
        logger.info("[ExchangeTree] Syncing instruments...")
        
        try:
            from modules.market_data.services.instrument_registry import instrument_registry
            await instrument_registry.sync_all(force=True)
            
            for exchange in self.exchanges:
                self._get_health(exchange).record_success()
            
            logger.info("[ExchangeTree] Instruments synced")
        except Exception as e:
            logger.error(f"[ExchangeTree] Instruments sync error: {e}")
            for exchange in self.exchanges:
                self._get_health(exchange).record_fail()
    
    async def _sync_prices(self):
        """Sync latest prices from exchanges"""
        logger.info("[ExchangeTree] Syncing prices...")
        
        try:
            from modules.market_data.providers.registry import provider_registry
            
            for exchange in self.exchanges:
                health = self._get_health(exchange)
                if health.is_paused:
                    continue
                
                try:
                    provider = provider_registry.get(exchange)
                    if provider:
                        start = datetime.now(timezone.utc)
                        # Get top assets prices
                        tickers = await provider.get_tickers() if hasattr(provider, 'get_tickers') else []
                        latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                        health.record_success(latency)
                        
                        # Store in MongoDB (fallback storage)
                        if tickers:
                            now = datetime.now(timezone.utc).isoformat()
                            for ticker in tickers[:100]:  # Top 100
                                await self.db.market_prices.update_one(
                                    {"symbol": ticker.get("symbol"), "exchange": exchange},
                                    {"$set": {
                                        **ticker,
                                        "exchange": exchange,
                                        "updated_at": now
                                    }},
                                    upsert=True
                                )
                except Exception as e:
                    logger.warning(f"[ExchangeTree] {exchange} price sync failed: {e}")
                    health.record_fail()
            
            self._last_sync["prices"] = datetime.now(timezone.utc)
            logger.info("[ExchangeTree] Prices synced")
        except Exception as e:
            logger.error(f"[ExchangeTree] Prices sync error: {e}")
    
    async def _sync_candles(self):
        """Sync 1m candles from exchanges (stored in MongoDB as fallback)"""
        logger.info("[ExchangeTree] Syncing candles...")
        
        try:
            from modules.market_data.providers.registry import provider_registry
            
            # Top symbols to track
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
            
            for exchange in self.exchanges:
                health = self._get_health(exchange)
                if health.is_paused:
                    continue
                
                try:
                    provider = provider_registry.get(exchange)
                    if provider and hasattr(provider, 'get_candles'):
                        for symbol in symbols:
                            try:
                                candles = await provider.get_candles(symbol, "1m", limit=10)
                                if candles:
                                    now = datetime.now(timezone.utc).isoformat()
                                    for c in candles:
                                        await self.db.market_candles.update_one(
                                            {
                                                "exchange": exchange,
                                                "symbol": symbol,
                                                "tf": "1m",
                                                "ts": c.get("ts") or c.get("timestamp")
                                            },
                                            {"$set": {
                                                **c,
                                                "exchange": exchange,
                                                "symbol": symbol,
                                                "tf": "1m",
                                                "updated_at": now
                                            }},
                                            upsert=True
                                        )
                                    health.record_success()
                            except:
                                pass
                except Exception as e:
                    logger.warning(f"[ExchangeTree] {exchange} candles failed: {e}")
                    health.record_fail()
            
            self._last_sync["candles"] = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"[ExchangeTree] Candles sync error: {e}")
    
    async def _sync_funding_oi(self):
        """Sync funding rates and open interest"""
        logger.info("[ExchangeTree] Syncing funding/OI...")
        
        try:
            from modules.market_data.providers.registry import provider_registry
            
            for exchange in self.exchanges:
                health = self._get_health(exchange)
                if health.is_paused:
                    continue
                
                try:
                    provider = provider_registry.get(exchange)
                    if provider:
                        # Get funding rates
                        if hasattr(provider, 'get_funding_rates'):
                            rates = await provider.get_funding_rates()
                            if rates:
                                now = datetime.now(timezone.utc).isoformat()
                                for r in rates[:50]:
                                    await self.db.market_funding.update_one(
                                        {"exchange": exchange, "symbol": r.get("symbol")},
                                        {"$set": {**r, "exchange": exchange, "updated_at": now}},
                                        upsert=True
                                    )
                        
                        # Get open interest
                        if hasattr(provider, 'get_open_interest'):
                            oi_data = await provider.get_open_interest()
                            if oi_data:
                                now = datetime.now(timezone.utc).isoformat()
                                for oi in oi_data[:50]:
                                    await self.db.market_oi.update_one(
                                        {"exchange": exchange, "symbol": oi.get("symbol")},
                                        {"$set": {**oi, "exchange": exchange, "updated_at": now}},
                                        upsert=True
                                    )
                        
                        health.record_success()
                except Exception as e:
                    logger.warning(f"[ExchangeTree] {exchange} funding/OI failed: {e}")
                    health.record_fail()
            
            self._last_sync["funding_oi"] = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"[ExchangeTree] Funding/OI sync error: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # SCHEDULER SETUP
    # ═══════════════════════════════════════════════════════════════
    
    def setup_jobs(self):
        """Setup exchange sync jobs"""
        # Instruments - every 30 min
        self.scheduler.add_job(
            self._sync_instruments,
            trigger=IntervalTrigger(seconds=EXCHANGE_INTERVALS["instruments"]),
            id="exchange_instruments",
            name="Exchange Instruments",
            replace_existing=True
        )
        
        # Prices - every 1 min
        self.scheduler.add_job(
            self._sync_prices,
            trigger=IntervalTrigger(seconds=EXCHANGE_INTERVALS["prices"]),
            id="exchange_prices",
            name="Exchange Prices",
            replace_existing=True
        )
        
        # Candles - every 1 min
        self.scheduler.add_job(
            self._sync_candles,
            trigger=IntervalTrigger(seconds=EXCHANGE_INTERVALS["candles"]),
            id="exchange_candles",
            name="Exchange Candles",
            replace_existing=True
        )
        
        # Funding/OI - every 1 min
        self.scheduler.add_job(
            self._sync_funding_oi,
            trigger=IntervalTrigger(seconds=EXCHANGE_INTERVALS["funding"]),
            id="exchange_funding_oi",
            name="Exchange Funding/OI",
            replace_existing=True
        )
        
        logger.info("[ExchangeTree] Setup 4 exchange sync jobs")
    
    def start(self):
        """Start the scheduler"""
        if not self._running:
            self.setup_jobs()
            self.scheduler.start()
            self._running = True
            logger.info("[ExchangeTree] Scheduler started")
            
            # Initial sync
            asyncio.create_task(self._sync_instruments())
    
    def stop(self):
        """Stop the scheduler"""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("[ExchangeTree] Scheduler stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        return {
            "running": self._running,
            "tree": "exchange",
            "exchanges": self.exchanges,
            "intervals": EXCHANGE_INTERVALS,
            "health": {ex: h.to_dict() for ex, h in self._exchange_health.items()},
            "last_sync": {k: v.isoformat() if v else None for k, v in self._last_sync.items()},
            "jobs": [
                {"id": job.id, "name": job.name, "next_run": str(job.next_run_time)}
                for job in self.scheduler.get_jobs()
            ] if self._running else []
        }
    
    def pause_exchange(self, exchange_id: str):
        """Pause an exchange"""
        health = self._get_health(exchange_id)
        health.is_paused = True
        logger.info(f"[ExchangeTree] Paused {exchange_id}")
    
    def unpause_exchange(self, exchange_id: str):
        """Unpause an exchange"""
        health = self._get_health(exchange_id)
        health.is_paused = False
        health.consecutive_fails = 0
        logger.info(f"[ExchangeTree] Unpaused {exchange_id}")


# Global instance
_exchange_scheduler: Optional[ExchangeTreeScheduler] = None


def get_exchange_scheduler(db) -> ExchangeTreeScheduler:
    """Get or create exchange scheduler"""
    global _exchange_scheduler
    if _exchange_scheduler is None:
        _exchange_scheduler = ExchangeTreeScheduler(db)
    return _exchange_scheduler


def init_exchange_scheduler(db, auto_start: bool = False) -> ExchangeTreeScheduler:
    """Initialize exchange scheduler"""
    scheduler = get_exchange_scheduler(db)
    if auto_start:
        scheduler.start()
    return scheduler
