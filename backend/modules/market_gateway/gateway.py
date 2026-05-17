"""
Market Gateway - Provider-agnostic market data gateway
Dynamic routing based on latency and availability
"""

import time
import asyncio
from typing import List, Optional, Dict, Any
import logging

from .adapters.defillama_adapter import DefiLlamaAdapter
from .adapters.coingecko_adapter import CoinGeckoAdapter
from .adapters.dexscreener_adapter import DexScreenerAdapter
from .adapters.exchange_adapter import ExchangeAdapter
from .adapters import BaseAdapter, AdapterResult
from .cache import cache_layer, CacheLayer
from .models import ProviderStatus, ProviderHealth

logger = logging.getLogger(__name__)


class MarketGateway:
    """
    Provider-agnostic Market Gateway
    
    Architecture:
    Market API → Market Gateway → Asset Resolver → Provider Pool → Provider Adapters → Cache Layer → External APIs
    
    Provider Priority:
    1. DefiLlama (free, reliable)
    2. CoinGecko (comprehensive)
    3. DexScreener (DEX data)
    4. Exchange APIs (direct)
    """
    
    # Latency threshold for fallback (ms)
    LATENCY_THRESHOLD = 2000
    
    def __init__(self):
        self.adapters: Dict[str, BaseAdapter] = {}
        self.cache = cache_layer
        self._initialized = False
        self._init_lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize all adapters"""
        async with self._init_lock:
            if self._initialized:
                return
            
            # Create adapters in priority order
            self.adapters = {
                "defillama": DefiLlamaAdapter(),
                "coingecko": CoinGeckoAdapter(),
                "dexscreener": DexScreenerAdapter(),
                "exchanges": ExchangeAdapter(),
            }
            
            self._initialized = True
            logger.info(f"Market Gateway initialized with {len(self.adapters)} adapters")
    
    def _get_sorted_adapters(self, exclude: List[str] = None) -> List[BaseAdapter]:
        """Get adapters sorted by priority and latency"""
        exclude = exclude or []
        adapters = [a for name, a in self.adapters.items() if name not in exclude and a.is_healthy]
        
        # Sort by: priority first, then latency
        return sorted(adapters, key=lambda a: (a.priority, a.latency))
    
    async def _try_adapters(self, method_name: str, *args, **kwargs) -> AdapterResult:
        """Try adapters in order until one succeeds"""
        await self.initialize()
        
        errors = []
        for adapter in self._get_sorted_adapters():
            method = getattr(adapter, method_name, None)
            if not method:
                continue
            
            result = await method(*args, **kwargs)
            
            if result.success:
                # Check latency threshold
                if result.latency_ms > self.LATENCY_THRESHOLD:
                    logger.warning(f"[{adapter.name}] High latency: {result.latency_ms}ms")
                return result
            
            errors.append(f"{adapter.name}: {result.error}")
        
        # All failed
        return AdapterResult(
            success=False,
            error=f"All providers failed: {'; '.join(errors)}",
            source="gateway"
        )
    
    # ═══════════════════════════════════════════════════════════════
    # QUOTE ENDPOINTS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_quote(self, asset: str) -> dict:
        """
        GET /api/market/quote?asset=BTC
        Returns single asset quote with caching (TTL=10s)
        """
        await self.initialize()
        asset = asset.upper()
        
        # Check cache
        cached = await self.cache.get("quote", asset)
        if cached:
            return {**cached, "cached": True}
        
        # Try adapters
        result = await self._try_adapters("get_quote", asset)
        
        if result.success:
            data = {
                **result.data,
                "source": result.source,
                "latency_ms": result.latency_ms
            }
            await self.cache.set("quote", data, asset)
            return data
        
        raise ValueError(result.error)
    
    async def get_bulk_quotes(self, assets: List[str]) -> dict:
        """
        GET /api/market/quotes?assets=BTC,ETH,SOL
        Returns multiple quotes with bulk request optimization (TTL=10s)
        """
        await self.initialize()
        assets = [a.upper() for a in assets]
        cache_key = ",".join(sorted(assets))
        
        # Check cache
        cached = await self.cache.get("quotes", cache_key)
        if cached:
            return {"quotes": cached, "cached": True, "ts": int(time.time() * 1000)}
        
        # Try adapters with bulk support
        result = await self._try_adapters("get_bulk_quotes", assets)
        
        if result.success:
            quotes = result.data
            await self.cache.set("quotes", quotes, cache_key)
            return {
                "ts": int(time.time() * 1000),
                "quotes": quotes,
                "sources_used": [result.source],
                "latency_ms": result.latency_ms
            }
        
        raise ValueError(result.error)
    
    # ═══════════════════════════════════════════════════════════════
    # MARKET OVERVIEW
    # ═══════════════════════════════════════════════════════════════
    
    async def get_overview(self) -> dict:
        """
        GET /api/market/overview
        Returns global market metrics (TTL=60s)
        """
        await self.initialize()
        
        # Check cache
        cached = await self.cache.get("overview")
        if cached:
            return {**cached, "cached": True}
        
        # Try CoinGecko first for overview (best data)
        coingecko = self.adapters.get("coingecko")
        if coingecko:
            result = await coingecko.get_overview()
            if result.success:
                data = {
                    "ts": int(time.time() * 1000),
                    **result.data,
                    "source": result.source
                }
                await self.cache.set("overview", data)
                return data
        
        # Fallback to DefiLlama
        defillama = self.adapters.get("defillama")
        if defillama:
            result = await defillama.get_overview()
            if result.success:
                data = {
                    "ts": int(time.time() * 1000),
                    **result.data,
                    "source": result.source
                }
                await self.cache.set("overview", data)
                return data
        
        raise ValueError("No provider available for market overview")
    
    # ═══════════════════════════════════════════════════════════════
    # CANDLES
    # ═══════════════════════════════════════════════════════════════
    
    async def get_candles(self, asset: str, interval: str = "1h", limit: int = 100) -> dict:
        """
        GET /api/market/candles?asset=BTC&interval=1h&limit=100
        Returns OHLCV candles (TTL=5min)
        """
        await self.initialize()
        asset = asset.upper()
        
        # Check cache
        cached = await self.cache.get("candles", asset, interval, limit)
        if cached:
            return {**cached, "cached": True}
        
        # Try exchange adapter first (best candle data)
        exchange = self.adapters.get("exchanges")
        if exchange:
            result = await exchange.get_candles(asset, interval, limit)
            if result.success:
                data = {
                    "ts": int(time.time() * 1000),
                    "asset": asset,
                    "interval": interval,
                    "candles": result.data,
                    "source": result.source
                }
                await self.cache.set("candles", data, asset, interval, limit)
                return data
        
        # Fallback to other adapters
        result = await self._try_adapters("get_candles", asset, interval, limit)
        
        if result.success:
            data = {
                "ts": int(time.time() * 1000),
                "asset": asset,
                "interval": interval,
                "candles": result.data,
                "source": result.source
            }
            await self.cache.set("candles", data, asset, interval, limit)
            return data
        
        raise ValueError(result.error)
    
    # ═══════════════════════════════════════════════════════════════
    # EXCHANGE DATA
    # ═══════════════════════════════════════════════════════════════
    
    async def get_exchanges(self, asset: str) -> dict:
        """
        GET /api/market/exchanges/BTC
        Returns available exchanges and their prices for asset (TTL=30s)
        """
        await self.initialize()
        asset = asset.upper()
        
        # Check cache
        cached = await self.cache.get("exchanges", asset)
        if cached:
            return {**cached, "cached": True}
        
        exchange_adapter = self.adapters.get("exchanges")
        if not exchange_adapter:
            raise ValueError("Exchange adapter not available")
        
        result = await exchange_adapter.get_exchanges_for_asset(asset)
        
        if result.success:
            data = {
                "ts": int(time.time() * 1000),
                "asset": asset,
                "exchanges": result.data
            }
            await self.cache.set("exchanges", data, asset)
            return data
        
        raise ValueError(result.error)
    
    async def get_orderbook(self, asset: str, exchange: str = "coinbase", limit: int = 20) -> dict:
        """
        GET /api/market/orderbook/BTC?exchange=coinbase
        Returns orderbook (TTL=5s)
        """
        await self.initialize()
        asset = asset.upper()
        
        # Check cache
        cached = await self.cache.get("orderbook", asset, exchange)
        if cached:
            return {**cached, "cached": True}
        
        exchange_adapter = self.adapters.get("exchanges")
        if not exchange_adapter:
            raise ValueError("Exchange adapter not available")
        
        result = await exchange_adapter.get_orderbook(asset, exchange, limit)
        
        if result.success:
            data = {
                "ts": int(time.time() * 1000),
                "asset": asset,
                **result.data
            }
            await self.cache.set("orderbook", data, asset, exchange)
            return data
        
        raise ValueError(result.error)
    
    async def get_trades(self, asset: str, exchange: str = "coinbase", limit: int = 50) -> dict:
        """
        GET /api/market/trades/BTC?exchange=coinbase
        Returns recent trades (TTL=5s)
        """
        await self.initialize()
        asset = asset.upper()
        
        # Check cache
        cached = await self.cache.get("trades", asset, exchange)
        if cached:
            return {**cached, "cached": True}
        
        exchange_adapter = self.adapters.get("exchanges")
        if not exchange_adapter:
            raise ValueError("Exchange adapter not available")
        
        result = await exchange_adapter.get_trades(asset, exchange, limit)
        
        if result.success:
            data = {
                "ts": int(time.time() * 1000),
                "asset": asset,
                **result.data
            }
            await self.cache.set("trades", data, asset, exchange)
            return data
        
        raise ValueError(result.error)
    
    # ═══════════════════════════════════════════════════════════════
    # HEALTH & STATUS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_providers_health(self) -> dict:
        """
        GET /api/providers/health
        Returns health status of all providers (TTL=30s)
        """
        await self.initialize()
        
        # Check cache
        cached = await self.cache.get("health")
        if cached:
            return {**cached, "cached": True}
        
        providers = {}
        
        for name, adapter in self.adapters.items():
            result = await adapter.health_check()
            
            if adapter.is_healthy:
                status = ProviderStatus.HEALTHY
            elif adapter._error_count < 5:
                status = ProviderStatus.DEGRADED
            else:
                status = ProviderStatus.DOWN
            
            providers[name] = {
                "id": name,
                "name": adapter.name,
                "status": status.value,
                "latency_ms": adapter.latency,
                "success_rate": adapter.success_rate,
                "error_count": adapter._error_count,
                "last_error": adapter._last_error
            }
        
        data = {
            "ts": int(time.time() * 1000),
            "providers": providers
        }
        
        await self.cache.set("health", data)
        return data
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        return self.cache.get_stats()


# Global gateway instance
market_gateway = MarketGateway()
