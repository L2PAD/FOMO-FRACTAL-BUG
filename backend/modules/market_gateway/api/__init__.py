"""
Market Gateway API Routes
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import time

from ..gateway import market_gateway

router = APIRouter(prefix="/api/market", tags=["Market Gateway"])


# ═══════════════════════════════════════════════════════════════
# QUOTE ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/quote")
async def get_quote(asset: str = Query(..., description="Asset symbol (e.g., BTC, ETH)")):
    """
    Get single asset quote
    
    Returns:
    - asset: Symbol
    - price: Current USD price
    - change_24h: 24h price change %
    - volume_24h: 24h trading volume
    - market_cap: Market capitalization
    - source: Data provider used
    
    Cache TTL: 10 seconds
    """
    try:
        return await market_gateway.get_quote(asset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quotes")
async def get_bulk_quotes(
    assets: str = Query(..., description="Comma-separated asset symbols (e.g., BTC,ETH,SOL)")
):
    """
    Get quotes for multiple assets (bulk request)
    
    Uses bulk API calls to minimize rate limit usage.
    
    Cache TTL: 10 seconds
    """
    try:
        asset_list = [a.strip() for a in assets.split(",") if a.strip()]
        if not asset_list:
            raise HTTPException(status_code=400, detail="No assets provided")
        
        if len(asset_list) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 assets per request")
        
        return await market_gateway.get_bulk_quotes(asset_list)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# MARKET OVERVIEW
# ═══════════════════════════════════════════════════════════════

@router.get("/global")
async def get_market_overview():
    """
    Get global market overview
    
    Returns:
    - market_cap_total: Total crypto market cap
    - btc_dominance: Bitcoin dominance %
    - eth_dominance: Ethereum dominance %
    - volume_24h: Total 24h trading volume
    - active_cryptocurrencies: Number of active coins
    
    Cache TTL: 60 seconds
    """
    try:
        return await market_gateway.get_overview()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# CANDLES / OHLCV
# ═══════════════════════════════════════════════════════════════

@router.get("/candles")
async def get_candles(
    asset: str = Query(..., description="Asset symbol"),
    interval: str = Query("1h", description="Candle interval (1h, 4h, 1d)"),
    limit: int = Query(100, ge=1, le=500, description="Number of candles")
):
    """
    Get OHLCV candles for asset
    
    Returns:
    - candles: Array of [timestamp, open, high, low, close, volume]
    
    Cache TTL: 5 minutes
    """
    try:
        return await market_gateway.get_candles(asset, interval, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# EXCHANGE DATA
# ═══════════════════════════════════════════════════════════════

@router.get("/exchanges/{asset}")
async def get_exchanges(asset: str):
    """
    Get all exchanges listing the asset with their prices
    
    Returns:
    - exchanges: List of exchanges with price, volume, spread info
    
    Exchanges covered:
    - Binance
    - Coinbase
    - Hyperliquid
    
    Cache TTL: 30 seconds
    """
    try:
        return await market_gateway.get_exchanges(asset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orderbook/{asset}")
async def get_orderbook(
    asset: str,
    exchange: str = Query("coinbase", description="Exchange (coinbase, binance)"),
    limit: int = Query(20, ge=1, le=100, description="Orderbook depth")
):
    """
    Get orderbook for asset on specific exchange
    
    Returns:
    - bids: Buy orders [price, amount]
    - asks: Sell orders [price, amount]
    
    Cache TTL: 5 seconds
    """
    try:
        return await market_gateway.get_orderbook(asset, exchange, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades/{asset}")
async def get_trades(
    asset: str,
    exchange: str = Query("coinbase", description="Exchange (coinbase, binance)"),
    limit: int = Query(50, ge=1, le=200, description="Number of trades")
):
    """
    Get recent trades for asset on specific exchange
    
    Returns:
    - trades: List of {id, price, amount, side, timestamp}
    
    Cache TTL: 5 seconds
    """
    try:
        return await market_gateway.get_trades(asset, exchange, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# PROVIDER HEALTH
# ═══════════════════════════════════════════════════════════════

@router.get("/providers/health")
async def get_providers_health():
    """
    Get health status of all market data providers
    
    Returns status for:
    - DefiLlama (primary)
    - CoinGecko
    - DexScreener
    - Exchange APIs
    
    Status values: healthy, degraded, down
    
    Cache TTL: 30 seconds
    """
    try:
        return await market_gateway.get_providers_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics
    
    Returns:
    - hits: Cache hits
    - misses: Cache misses  
    - hit_rate: Hit rate %
    - entries: Current cache entries
    """
    return {
        "ts": int(time.time() * 1000),
        **market_gateway.get_cache_stats()
    }
