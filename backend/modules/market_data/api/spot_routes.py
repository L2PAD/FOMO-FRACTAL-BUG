"""
FOMO Spot/Exchange API
======================
Spot market data and exchange-specific endpoints.

Endpoints:
- /api/spot/activity - Spot market activity
- /api/spot/leaders/volume - Volume leaders
- /api/exchanges/{exchange}/hot - Hot tokens on exchange
- /api/exchanges/{exchange}/instruments - Exchange instruments
- /api/exchanges/{exchange}/status - Exchange status
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from datetime import datetime, timezone
import asyncio

from ..domain.types import Venue

router = APIRouter(tags=["Spot/Exchange"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ═══════════════════════════════════════════════════════════════
# SPOT ACTIVITY
# ═══════════════════════════════════════════════════════════════

@router.get("/api/spot/activity")
async def get_spot_activity(
    exchange: str = Query("all", description="Exchange filter"),
    limit: int = Query(50, le=100)
):
    """
    Spot market activity - where the action is.
    """
    from modules.market_data.services import instrument_registry
    from modules.market_data.providers.registry import provider_registry
    
    items = []
    
    exchanges = ["binance", "bybit", "coinbase", "hyperliquid"] if exchange == "all" else [exchange]
    
    for exch in exchanges:
        try:
            adapter = provider_registry.get(exch)
            if not adapter:
                continue
            
            # Get top instruments
            instruments = instrument_registry.list_instruments()
            exch_instruments = []
            for i in instruments:
                inst_dict = i.model_dump() if hasattr(i, 'model_dump') else i.__dict__
                if inst_dict.get("venue") == exch:
                    exch_instruments.append(inst_dict)
            
            for inst in exch_instruments[:20]:
                symbol = inst.get("native_symbol")
                try:
                    ticker = await adapter.get_ticker(symbol)
                    if ticker:
                        items.append({
                            "symbol": symbol,
                            "exchange": exch,
                            "price": ticker.get("last") or ticker.get("price"),
                            "volume_24h": ticker.get("volume") or ticker.get("quoteVolume"),
                            "change_24h": ticker.get("change24h") or ticker.get("priceChangePercent")
                        })
                except:
                    pass
        except:
            pass
    
    # Sort by volume
    items.sort(key=lambda x: x.get("volume_24h") or 0, reverse=True)
    
    return {
        "ts": ts_now(),
        "exchange": exchange,
        "items": items[:limit],
        "_meta": {"cache_sec": 30}
    }


# ═══════════════════════════════════════════════════════════════
# VOLUME LEADERS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/spot/leaders/volume")
async def get_volume_leaders(
    window: str = Query("24h", description="Window"),
    exchange: str = Query("all", description="Exchange filter"),
    limit: int = Query(50, le=100)
):
    """
    Top tokens by trading volume.
    """
    import aiohttp
    
    items = []
    
    # Use CoinGecko for comprehensive volume data
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "volume_desc",
                    "per_page": limit,
                    "page": 1
                },
                timeout=10
            ) as resp:
                if resp.status == 200:
                    coins = await resp.json()
                    
                    for coin in coins:
                        items.append({
                            "symbol": coin.get("symbol", "").upper(),
                            "name": coin.get("name"),
                            "price": coin.get("current_price"),
                            "volume_24h": coin.get("total_volume"),
                            "change_24h": coin.get("price_change_percentage_24h"),
                            "mcap": coin.get("market_cap"),
                            "rank": coin.get("market_cap_rank")
                        })
    except:
        pass
    
    return {
        "ts": ts_now(),
        "window": window,
        "exchange": exchange,
        "items": items[:limit],
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# EXCHANGE HOT LIST
# ═══════════════════════════════════════════════════════════════

@router.get("/api/exchanges/{exchange}/hot")
async def get_exchange_hot(
    exchange: str,
    window: str = Query("24h", description="Window"),
    limit: int = Query(50, le=100)
):
    """
    Hot tokens on specific exchange.
    
    Shows top traded tokens on Binance, Bybit, etc.
    """
    from modules.market_data.providers.registry import provider_registry
    from modules.market_data.services import instrument_registry
    
    items = []
    
    try:
        # Convert string to Venue enum if needed
        venue_map = {
            "hyperliquid": Venue.HYPERLIQUID,
            "binance": Venue.BINANCE,
            "bybit": Venue.BYBIT,
            "coinbase": Venue.COINBASE
        }
        venue = venue_map.get(exchange.lower())
            
        if not venue:
            raise HTTPException(status_code=400, detail=f"Unknown exchange: {exchange}")
        
        adapter = provider_registry.get(venue)
        if not adapter:
            raise HTTPException(status_code=400, detail=f"Exchange not available: {exchange}")
        
        # Get instruments for this exchange
        instruments = instrument_registry.list_instruments()
        exch_instruments = []
        for i in instruments:
            inst_dict = i.model_dump() if hasattr(i, 'model_dump') else i.__dict__
            if inst_dict.get("venue") == venue:
                exch_instruments.append(inst_dict)
        
        # Get tickers for top instruments
        for inst in exch_instruments[:limit * 2]:  # Get more to filter
            symbol = inst.get("native_symbol")
            try:
                ticker = await adapter.get_ticker(symbol)
                if ticker and ticker.get("volume"):
                    items.append({
                        "symbol": symbol,
                        "base": inst.get("base"),
                        "quote": inst.get("quote"),
                        "price": ticker.get("last") or ticker.get("price"),
                        "volume_24h": ticker.get("volume") or ticker.get("quoteVolume"),
                        "change_24h": ticker.get("change24h") or ticker.get("priceChangePercent")
                    })
            except:
                pass
    except Exception as e:
        if "Unknown exchange" in str(e):
            raise
        pass
    
    # Sort by volume
    items.sort(key=lambda x: x.get("volume_24h") or 0, reverse=True)
    
    return {
        "ts": ts_now(),
        "exchange": exchange,
        "window": window,
        "tokens": items[:limit],
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# EXCHANGE INSTRUMENTS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/exchanges/{exchange}/instruments")
async def get_exchange_instruments(
    exchange: str,
    type: str = Query(None, description="Filter: spot, perp"),
    limit: int = Query(100, le=500)
):
    """
    Get all instruments on exchange.
    """
    from modules.market_data.services import instrument_registry
    
    instruments = instrument_registry.list_instruments()
    
    filtered = []
    for inst in instruments:
        # Handle Pydantic model
        inst_dict = inst.model_dump() if hasattr(inst, 'model_dump') else inst.__dict__
        
        if inst_dict.get("venue") != exchange:
            continue
        if type and inst_dict.get("market_type") != type:
            continue
        
        filtered.append({
            "symbol": inst_dict.get("native_symbol"),
            "base": inst_dict.get("base"),
            "quote": inst_dict.get("quote"),
            "type": inst_dict.get("market_type", "spot"),
            "status": "active",
            "tick_size": inst_dict.get("tick_size"),
            "step_size": inst_dict.get("step_size"),
            "min_notional": inst_dict.get("min_notional")
        })
    
    return {
        "ts": ts_now(),
        "exchange": exchange,
        "count": len(filtered),
        "instruments": filtered[:limit],
        "_meta": {"cache_sec": 3600}
    }


# ═══════════════════════════════════════════════════════════════
# EXCHANGE STATUS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/exchanges/{exchange}/status")
async def get_exchange_status(exchange: str):
    """
    Get exchange health status.
    """
    from modules.market_data.providers.registry import provider_registry
    
    try:
        # Convert string to Venue enum if needed
        venue_map = {
            "hyperliquid": Venue.HYPERLIQUID,
            "binance": Venue.BINANCE,
            "bybit": Venue.BYBIT,
            "coinbase": Venue.COINBASE
        }
        venue = venue_map.get(exchange.lower())
            
        if not venue:
            raise HTTPException(status_code=400, detail=f"Unknown exchange: {exchange}")
        
        adapter = provider_registry.get(venue)
        if not adapter:
            raise HTTPException(status_code=400, detail=f"Exchange not available: {exchange}")
        
        health = await adapter.health_check()
        
        return {
            "ts": ts_now(),
            "exchange": exchange,
            "healthy": health if isinstance(health, bool) else health.get("healthy", False),
            "latency_ms": health.get("latency_ms") if isinstance(health, dict) else None,
            "using_proxy": health.get("using_proxy", False) if isinstance(health, dict) else False,
            "error": health.get("error") if isinstance(health, dict) else None,
            "_meta": {"cache_sec": 30}
        }
    except Exception as e:
        if "Unknown exchange" in str(e):
            raise
        return {
            "ts": ts_now(),
            "exchange": exchange,
            "healthy": False,
            "error": str(e)
        }
