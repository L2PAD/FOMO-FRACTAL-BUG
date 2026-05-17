"""
FOMO Market API Layer
=====================
First layer of market intelligence - exchange data, quotes, derivatives, indicators.

Endpoints:
- /api/market/global - Global market stats
- /api/market/quote/{symbol} - Price quotes
- /api/market/candles/{symbol} - OHLCV data
- /api/market/instruments - Trading instruments
- /api/market/exchanges - Exchange info
- /api/market/exchanges/{symbol} - Where token trades
- /api/market/orderbook - Order book
- /api/market/trades - Recent trades
- /api/market/index/{symbol} - Aggregated index price
- /api/market/health/{symbol} - Market health
- /api/market/signals/{symbol} - Market signals
- /api/market/indicators - Indicator widgets
- /api/market/screener - Market screener
- /api/market/pump-radar - Pump detection
- /api/market/context - Market context
- /api/market/rotation - Capital rotation
- /api/derivatives/* - Derivatives data
- /api/indices/* - Market indices
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import asyncio
import statistics
import math

router = APIRouter(prefix="/api/market", tags=["Market Data"])


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def resolve_symbol(symbol: str) -> dict:
    """Normalize symbol to canonical form"""
    symbol = symbol.upper().replace("-", "").replace("/", "").replace("_", "")
    # Map common variations
    mappings = {
        "BTCUSDT": "BTC",
        "BTCUSD": "BTC", 
        "BITCOIN": "BTC",
        "ETHUSDT": "ETH",
        "ETHUSD": "ETH",
        "ETHEREUM": "ETH",
        "SOLUSDT": "SOL",
        "SOLUSD": "SOL",
    }
    canonical = mappings.get(symbol, symbol.replace("USDT", "").replace("USD", "").replace("PERP", ""))
    return {
        "canonical": canonical,
        "usdt_pair": f"{canonical}USDT",
        "usd_pair": f"{canonical}USD",
        "perp": f"{canonical}-PERP"
    }


async def get_provider_quote(symbol: str, provider: str) -> dict:
    """Get quote from specific provider"""
    from modules.market_data.providers.registry import provider_registry
    from modules.market_data.domain.types import Venue
    
    resolved = resolve_symbol(symbol)
    
    try:
        # Convert string to Venue enum
        venue_map = {
            "hyperliquid": Venue.HYPERLIQUID,
            "binance": Venue.BINANCE,
            "bybit": Venue.BYBIT,
            "coinbase": Venue.COINBASE
        }
        venue = venue_map.get(provider.lower())
        if not venue:
            return None
        
        # Different providers use different pair formats
        pair_formats = {
            "hyperliquid": resolved["canonical"],  # HyperLiquid uses just BTC
            "binance": resolved["usdt_pair"],      # Binance uses BTCUSDT
            "bybit": resolved["usdt_pair"],        # Bybit uses BTCUSDT
            "coinbase": f"{resolved['canonical']}-USD"  # Coinbase uses BTC-USD
        }
        pair = pair_formats.get(provider.lower(), resolved["usdt_pair"])
            
        adapter = provider_registry.get(venue)
        if not adapter:
            return None
            
        ticker = await adapter.get_ticker(pair)
        if ticker:
            # Handle both Pydantic models and dicts
            if hasattr(ticker, 'model_dump'):
                ticker_dict = ticker.model_dump()
            elif hasattr(ticker, '__dict__'):
                ticker_dict = ticker.__dict__
            elif isinstance(ticker, dict):
                ticker_dict = ticker
            else:
                return None
            
            return {
                "provider": provider,
                "price": ticker_dict.get("last") or ticker_dict.get("price"),
                "bid": ticker_dict.get("bid"),
                "ask": ticker_dict.get("ask"),
                "volume_24h": ticker_dict.get("volume") or ticker_dict.get("volume_24h") or ticker_dict.get("quoteVolume"),
                "change_24h": ticker_dict.get("change24h") or ticker_dict.get("change_24h") or ticker_dict.get("priceChangePercent"),
                "high_24h": ticker_dict.get("high24h") or ticker_dict.get("high_24h") or ticker_dict.get("highPrice"),
                "low_24h": ticker_dict.get("low24h") or ticker_dict.get("low_24h") or ticker_dict.get("lowPrice"),
                "ts": ts_now()
            }
    except Exception as e:
        return {"provider": provider, "error": str(e)}
    
    return None


async def get_best_quote(symbol: str) -> dict:
    """Get best quote from all providers"""
    # Try providers in order of reliability
    providers = ["hyperliquid", "coinbase", "binance", "bybit"]
    
    for provider in providers:
        try:
            quote = await get_provider_quote(symbol, provider)
            if quote and quote.get("price") and not quote.get("error"):
                return quote
        except Exception as e:
            continue
    
    return None


# ═══════════════════════════════════════════════════════════════
# GLOBAL MARKET STATS
# ═══════════════════════════════════════════════════════════════

@router.get("/global")
async def get_global_market():
    """
    Global market statistics.
    
    Returns:
    - total_market_cap
    - 24h_volume
    - btc_dominance
    - eth_dominance
    """
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.coingecko.com/api/v3/global",
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    market = data.get("data", {})
                    
                    return {
                        "ts": ts_now(),
                        "total_market_cap": market.get("total_market_cap", {}).get("usd"),
                        "total_volume_24h": market.get("total_volume", {}).get("usd"),
                        "btc_dominance": market.get("market_cap_percentage", {}).get("btc"),
                        "eth_dominance": market.get("market_cap_percentage", {}).get("eth"),
                        "active_cryptocurrencies": market.get("active_cryptocurrencies"),
                        "markets": market.get("markets"),
                        "market_cap_change_24h": market.get("market_cap_change_percentage_24h_usd"),
                        "_meta": {"source": "coingecko", "cache_sec": 60}
                    }
    except Exception as e:
        pass
    
    # Fallback: calculate from providers
    btc_quote = await get_best_quote("BTC")
    eth_quote = await get_best_quote("ETH")
    
    return {
        "ts": ts_now(),
        "btc_price": btc_quote.get("price") if btc_quote else None,
        "eth_price": eth_quote.get("price") if eth_quote else None,
        "_meta": {"source": "providers", "cache_sec": 30}
    }


@router.get("/coins")
async def get_market_coins(
    limit: int = Query(50, ge=1, le=200, description="Number of assets"),
    sort: str = Query("market_cap", description="Sort by: market_cap, volume, price_change"),
    order: str = Query("desc", description="Order: asc, desc")
):
    """
    Get market overview with top assets.
    
    Uses CoinGecko synced data from market_data collection.
    Returns: price, market_cap, volume, 24h change for top coins.
    """
    from server import db
    
    # Get from synced market data
    sort_field = {
        "market_cap": "market_cap",
        "volume": "total_volume",
        "price_change": "price_change_24h",
        "rank": "market_cap_rank"
    }.get(sort, "market_cap")
    
    sort_dir = -1 if order == "desc" else 1
    
    cursor = db.market_data.find(
        {"source": "coingecko"},
        {"_id": 0}
    ).sort(sort_field, sort_dir).limit(limit)
    
    assets = await cursor.to_list(limit)
    
    # Calculate totals
    total_market_cap = sum(a.get("market_cap", 0) or 0 for a in assets)
    total_volume = sum(a.get("total_volume", 0) or 0 for a in assets)
    
    formatted_assets = [
        {
            "symbol": a.get("symbol", "").upper(),
            "name": a.get("name"),
            "current_price": a.get("current_price"),
            "market_cap": a.get("market_cap"),
            "market_cap_rank": a.get("market_cap_rank"),
            "total_volume": a.get("total_volume"),
            "price_change_24h": a.get("price_change_24h"),
            "circulating_supply": a.get("circulating_supply"),
            "total_supply": a.get("total_supply"),
            "logo_url": a.get("logo_url"),
            "ath": a.get("ath")
        }
        for a in assets
    ]
    
    return {
        "ts": ts_now(),
        "count": len(formatted_assets),
        "totals": {
            "market_cap": total_market_cap,
            "volume_24h": total_volume
        },
        "assets": formatted_assets,
        "_meta": {"source": "coingecko", "cache_sec": 60}
    }


@router.get("/assets")
async def get_market_assets(
    category: Optional[str] = Query(None, description="Filter by category"),
    trending: bool = Query(False, description="Show trending only"),
    new: bool = Query(False, description="Show new listings only"),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get market assets with filters.
    """
    from server import db
    
    query = {"source": "coingecko"}
    
    if trending:
        # Top gainers
        query["price_change_24h"] = {"$gt": 5}
    
    cursor = db.market_data.find(
        query,
        {"_id": 0}
    ).sort("market_cap_rank", 1).limit(limit)
    
    assets = await cursor.to_list(limit)
    
    return {
        "ts": ts_now(),
        "count": len(assets),
        "filters": {
            "category": category,
            "trending": trending,
            "new": new
        },
        "assets": [
            {
                "symbol": a.get("symbol", "").upper(),
                "name": a.get("name"),
                "current_price": a.get("current_price"),
                "market_cap": a.get("market_cap"),
                "rank": a.get("market_cap_rank"),
                "price_change_24h": a.get("price_change_24h"),
                "volume_24h": a.get("total_volume"),
                "logo_url": a.get("logo_url")
            }
            for a in assets
        ],
        "_meta": {"source": "coingecko", "cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# QUOTE ENDPOINT
# ═══════════════════════════════════════════════════════════════

@router.get("/quote/{symbol}")
async def get_quote(
    symbol: str,
    provider: str = Query("auto", description="Provider: auto, binance, bybit, hyperliquid, coinbase"),
    vs: str = Query("usd", description="Quote currency")
):
    """
    Get price quote for symbol.
    
    Returns:
    - price
    - change (1h, 24h, 7d)
    - volume
    - high/low 24h
    """
    resolved = resolve_symbol(symbol)
    
    if provider == "auto":
        quote = await get_best_quote(resolved["canonical"])
    else:
        quote = await get_provider_quote(resolved["canonical"], provider)
    
    if not quote or not quote.get("price"):
        raise HTTPException(status_code=404, detail=f"No quote found for {symbol}")
    
    return {
        "symbol": resolved["canonical"],
        "vs": vs,
        "ts": ts_now(),
        "provider": quote.get("provider"),
        "price": quote.get("price"),
        "change": {
            "24h": quote.get("change_24h")
        },
        "volume": {
            "24h": quote.get("volume_24h")
        },
        "high_low": {
            "24h_high": quote.get("high_24h"),
            "24h_low": quote.get("low_24h")
        },
        "_meta": {"cache_sec": 5, "confidence": 0.98}
    }


# ═══════════════════════════════════════════════════════════════
# CANDLES ENDPOINT
# ═══════════════════════════════════════════════════════════════

@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    tf: str = Query("1h", description="Timeframe: 1m, 5m, 15m, 1h, 4h, 1d"),
    limit: int = Query(300, le=1000),
    provider: str = Query("auto", description="Provider")
):
    """
    Get OHLCV candles for charting.
    
    Format: [timestamp, open, high, low, close, volume]
    """
    from modules.market_data.providers.registry import provider_registry
    from modules.market_data.domain.types import Venue
    
    resolved = resolve_symbol(symbol)
    pair = resolved["usdt_pair"]
    
    # Map timeframe to provider format
    tf_map = {
        "1m": "1m", "5m": "5m", "15m": "15m",
        "1h": "1h", "4h": "4h", "1d": "1d"
    }
    interval = tf_map.get(tf, "1h")
    
    venue_map = {
        "hyperliquid": Venue.HYPERLIQUID,
        "binance": Venue.BINANCE,
        "bybit": Venue.BYBIT,
        "coinbase": Venue.COINBASE
    }
    
    providers_to_try = ["hyperliquid", "binance", "bybit"] if provider == "auto" else [provider]
    
    for prov in providers_to_try:
        try:
            venue = venue_map.get(prov.lower())
            if not venue:
                continue
                
            adapter = provider_registry.get(venue)
            if not adapter:
                continue
                
            candles = await adapter.get_candles(pair, interval, limit)
            if candles and len(candles) > 0:
                # Normalize to [t, o, h, l, c, v] format
                formatted = []
                for c in candles:
                    if isinstance(c, dict):
                        formatted.append([
                            c.get("timestamp") or c.get("t"),
                            c.get("open") or c.get("o"),
                            c.get("high") or c.get("h"),
                            c.get("low") or c.get("l"),
                            c.get("close") or c.get("c"),
                            c.get("volume") or c.get("v")
                        ])
                    elif isinstance(c, (list, tuple)):
                        formatted.append(list(c[:6]))
                
                return {
                    "symbol": resolved["canonical"],
                    "tf": tf,
                    "provider": prov,
                    "ts": ts_now(),
                    "candles": formatted,
                    "_meta": {"cache_sec": 10, "count": len(formatted)}
                }
        except Exception as e:
            continue
    
    raise HTTPException(status_code=404, detail=f"No candles found for {symbol}")


# ═══════════════════════════════════════════════════════════════
# INSTRUMENTS
# ═══════════════════════════════════════════════════════════════

@router.get("/instruments")
async def get_instruments(
    type: str = Query(None, description="Filter: spot, perp"),
    exchange: str = Query(None, description="Filter by exchange"),
    limit: int = Query(100, le=1000)
):
    """
    Get list of trading instruments.
    """
    from modules.market_data.services import instrument_registry
    
    instruments = instrument_registry.list_instruments()
    
    # Filter
    filtered = []
    for inst in instruments[:limit]:
        # Handle Pydantic model
        inst_dict = inst.model_dump() if hasattr(inst, 'model_dump') else inst.__dict__
        
        if type and inst_dict.get("market_type") != type:
            continue
        if exchange and inst_dict.get("venue") != exchange:
            continue
        filtered.append({
            "symbol": inst_dict.get("native_symbol"),
            "exchange": inst_dict.get("venue"),
            "type": inst_dict.get("market_type", "spot"),
            "base": inst_dict.get("base"),
            "quote": inst_dict.get("quote"),
            "status": "active"
        })
    
    return {
        "ts": ts_now(),
        "count": len(filtered),
        "instruments": filtered[:limit],
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# EXCHANGES
# ═══════════════════════════════════════════════════════════════

@router.get("/exchanges")
async def get_exchanges():
    """
    Get list of supported exchanges with status.
    """
    from modules.market_data.providers.registry import provider_registry
    from modules.market_data.domain.types import Venue
    
    venue_map = {
        "binance": Venue.BINANCE,
        "bybit": Venue.BYBIT,
        "hyperliquid": Venue.HYPERLIQUID,
        "coinbase": Venue.COINBASE
    }
    
    exchanges = []
    for venue_name, venue in venue_map.items():
        try:
            adapter = provider_registry.get(venue)
            if adapter:
                health = await adapter.health_check()
                
                exchanges.append({
                    "exchange": venue_name,
                    "type": "cex",
                    "healthy": health if isinstance(health, bool) else health.get("healthy", False),
                    "latency_ms": health.get("latency_ms") if isinstance(health, dict) else None,
                    "using_proxy": health.get("using_proxy", False) if isinstance(health, dict) else False
                })
            else:
                exchanges.append({
                    "exchange": venue_name,
                    "healthy": False,
                    "error": "Provider not available"
                })
        except Exception as e:
            exchanges.append({
                "exchange": venue_name,
                "healthy": False,
                "error": str(e)
            })
    
    return {
        "ts": ts_now(),
        "exchanges": exchanges,
        "_meta": {"cache_sec": 60}
    }


@router.get("/exchanges/{symbol}")
async def get_token_exchanges(symbol: str):
    """
    Get exchanges where token is traded.
    
    Shows:
    - Exchange name
    - Number of pairs
    - Top pairs
    - Volume 24h
    - Last price
    """
    from modules.market_data.services import instrument_registry
    
    resolved = resolve_symbol(symbol)
    canonical = resolved["canonical"]
    
    # Get all instruments for this symbol
    instruments = instrument_registry.list_instruments()
    
    exchange_data = {}
    for inst in instruments:
        # Handle Pydantic model
        inst_dict = inst.model_dump() if hasattr(inst, 'model_dump') else inst.__dict__
        
        base = inst_dict.get("base", "").upper()
        if base == canonical:
            venue = inst_dict.get("venue")
            if venue not in exchange_data:
                exchange_data[venue] = {
                    "exchange": venue,
                    "pairs": [],
                    "volume_24h": 0
                }
            
            pair = inst_dict.get("native_symbol")
            exchange_data[venue]["pairs"].append(pair)
    
    # Get quotes for each exchange
    exchanges = []
    for venue, data in exchange_data.items():
        quote = await get_provider_quote(canonical, venue)
        
        exchanges.append({
            "exchange": venue,
            "pairs_count": len(data["pairs"]),
            "top_pairs": data["pairs"][:3],
            "volume_24h": quote.get("volume_24h") if quote else None,
            "last_price": quote.get("price") if quote else None,
            "spread_bps": None  # Would need orderbook
        })
    
    # Sort by volume
    exchanges.sort(key=lambda x: x.get("volume_24h") or 0, reverse=True)
    
    return {
        "symbol": canonical,
        "ts": ts_now(),
        "exchanges_count": len(exchanges),
        "exchanges": exchanges,
        "_meta": {"cache_sec": 3600}
    }


# ═══════════════════════════════════════════════════════════════
# ORDERBOOK
# ═══════════════════════════════════════════════════════════════

@router.get("/orderbook")
async def get_orderbook(
    symbol: str = Query(..., description="Symbol"),
    exchange: str = Query("hyperliquid", description="Exchange"),
    depth: int = Query(20, le=100)
):
    """
    Get order book (bids/asks).
    """
    from modules.market_data.providers.registry import provider_registry
    from modules.market_data.domain.types import Venue
    
    resolved = resolve_symbol(symbol)
    pair = resolved["usdt_pair"]
    
    venue_map = {
        "hyperliquid": Venue.HYPERLIQUID,
        "binance": Venue.BINANCE,
        "bybit": Venue.BYBIT,
        "coinbase": Venue.COINBASE
    }
    
    venue = venue_map.get(exchange.lower())
    if not venue:
        raise HTTPException(status_code=400, detail=f"Unknown exchange: {exchange}")
    
    try:
        adapter = provider_registry.get(venue)
        if not adapter:
            raise HTTPException(status_code=400, detail=f"Exchange not available: {exchange}")
        
        book = await adapter.get_orderbook(pair, depth)
        if book:
            # Handle both Pydantic models and dicts
            if hasattr(book, 'model_dump'):
                book_dict = book.model_dump()
            elif hasattr(book, '__dict__'):
                book_dict = book.__dict__
            else:
                book_dict = book
            
            return {
                "symbol": resolved["canonical"],
                "exchange": exchange,
                "ts": ts_now(),
                "bids": book_dict.get("bids", [])[:depth],
                "asks": book_dict.get("asks", [])[:depth],
                "spread": None,
                "_meta": {"cache_sec": 1}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=404, detail="Orderbook not available")


# ═══════════════════════════════════════════════════════════════
# TRADES
# ═══════════════════════════════════════════════════════════════

@router.get("/trades")
async def get_trades(
    symbol: str = Query(..., description="Symbol"),
    exchange: str = Query("hyperliquid", description="Exchange"),
    limit: int = Query(50, le=200)
):
    """
    Get recent trades.
    """
    from modules.market_data.providers.registry import provider_registry
    from modules.market_data.domain.types import Venue
    
    resolved = resolve_symbol(symbol)
    pair = resolved["usdt_pair"]
    
    venue_map = {
        "hyperliquid": Venue.HYPERLIQUID,
        "binance": Venue.BINANCE,
        "bybit": Venue.BYBIT,
        "coinbase": Venue.COINBASE
    }
    
    venue = venue_map.get(exchange.lower())
    if not venue:
        raise HTTPException(status_code=400, detail=f"Unknown exchange: {exchange}")
    
    try:
        adapter = provider_registry.get(venue)
        if not adapter:
            raise HTTPException(status_code=400, detail=f"Exchange not available: {exchange}")
        
        trades = await adapter.get_trades(pair, limit)
        if trades:
            return {
                "symbol": resolved["canonical"],
                "exchange": exchange,
                "ts": ts_now(),
                "trades": trades[:limit],
                "_meta": {"cache_sec": 1}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=404, detail="Trades not available")


# ═══════════════════════════════════════════════════════════════
# INDEX PRICE (Aggregated)
# ═══════════════════════════════════════════════════════════════

@router.get("/index/{symbol}")
async def get_index_price(symbol: str):
    """
    Get aggregated index price from all exchanges.
    
    Method: Robust VWAP (Volume-Weighted Average Price)
    """
    resolved = resolve_symbol(symbol)
    providers = ["hyperliquid", "binance", "bybit", "coinbase"]
    
    tasks = [get_provider_quote(resolved["canonical"], p) for p in providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    sources = []
    prices = []
    volumes = []
    
    for r in results:
        if isinstance(r, dict) and r and r.get("price"):
            sources.append({
                "exchange": r.get("provider"),
                "price": r.get("price"),
                "volume": r.get("volume_24h") or 0
            })
            prices.append(r.get("price"))
            volumes.append(r.get("volume_24h") or 1)
    
    if not prices:
        raise HTTPException(status_code=404, detail=f"No price data for {symbol}")
    
    # Calculate VWAP
    total_volume = sum(volumes)
    if total_volume > 0:
        vwap = sum(p * v for p, v in zip(prices, volumes)) / total_volume
    else:
        vwap = statistics.median(prices)
    
    # Calculate weights
    for s in sources:
        s["weight"] = round(s["volume"] / total_volume, 4) if total_volume > 0 else 1/len(sources)
    
    # Find outliers (>2.5% deviation)
    outliers = []
    for s in sources:
        deviation = abs(s["price"] - vwap) / vwap * 100
        if deviation > 2.5:
            outliers.append({
                "exchange": s["exchange"],
                "price": s["price"],
                "reason": f"deviation>{deviation:.1f}%"
            })
    
    # Calculate spread
    if len(prices) > 1:
        spread_bps = (max(prices) - min(prices)) / vwap * 10000
    else:
        spread_bps = 0
    
    return {
        "symbol": resolved["canonical"],
        "index_price": round(vwap, 4),
        "method": "robust_vwap",
        "sources": sources,
        "outliers": outliers,
        "spread_bps": round(spread_bps, 2),
        "ts": ts_now(),
        "_meta": {"cache_sec": 5}
    }


# ═══════════════════════════════════════════════════════════════
# MARKET HEALTH
# ═══════════════════════════════════════════════════════════════

@router.get("/health/{symbol}")
async def get_market_health(symbol: str):
    """
    Get market health / data quality assessment.
    
    Shows:
    - Freshness
    - Missing providers
    - Price dispersion
    - Anomalies
    """
    resolved = resolve_symbol(symbol)
    providers = ["hyperliquid", "binance", "bybit", "coinbase"]
    
    tasks = [get_provider_quote(resolved["canonical"], p) for p in providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    available = []
    missing = []
    prices = []
    
    for i, r in enumerate(results):
        if isinstance(r, dict) and r and r.get("price"):
            available.append(providers[i])
            prices.append(r.get("price"))
        else:
            missing.append(providers[i])
    
    # Calculate dispersion
    dispersion = 0
    if len(prices) > 1:
        mean_price = statistics.mean(prices)
        dispersion = statistics.stdev(prices) / mean_price * 100
    
    # Health score
    health_score = 100
    health_score -= len(missing) * 15  # -15 per missing provider
    health_score -= min(dispersion * 10, 30)  # -10 per 1% dispersion, max -30
    health_score = max(0, health_score)
    
    # Anomalies
    anomalies = []
    if dispersion > 1:
        anomalies.append({"type": "high_dispersion", "value": f"{dispersion:.2f}%"})
    if len(missing) > 2:
        anomalies.append({"type": "low_coverage", "value": f"{len(missing)} providers offline"})
    
    return {
        "symbol": resolved["canonical"],
        "ts": ts_now(),
        "health_score": round(health_score),
        "freshness": "live",
        "providers": {
            "available": available,
            "missing": missing
        },
        "dispersion_pct": round(dispersion, 4),
        "anomalies": anomalies,
        "_meta": {"cache_sec": 10}
    }


# ═══════════════════════════════════════════════════════════════
# MARKET CONTEXT (Dashboard Block)
# ═══════════════════════════════════════════════════════════════

@router.get("/context")
async def get_market_context():
    """
    Market context block for dashboard.
    
    Returns:
    - Total market cap
    - BTC dominance
    - ETH dominance
    - Fear & Greed index
    - Alt season index
    - 24h volume
    """
    import aiohttp
    
    context = {
        "ts": ts_now(),
        "total_market_cap": None,
        "btc_dominance": None,
        "eth_dominance": None,
        "btc_volume_24h": None,
        "fear_greed": None,
        "altseason_index": None
    }
    
    # Get global data
    try:
        async with aiohttp.ClientSession() as session:
            # CoinGecko global
            async with session.get(
                "https://api.coingecko.com/api/v3/global",
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    market = data.get("data", {})
                    context["total_market_cap"] = market.get("total_market_cap", {}).get("usd")
                    context["btc_dominance"] = round(market.get("market_cap_percentage", {}).get("btc", 0), 2)
                    context["eth_dominance"] = round(market.get("market_cap_percentage", {}).get("eth", 0), 2)
                    context["total_volume_24h"] = market.get("total_volume", {}).get("usd")
    except:
        pass
    
    # Get BTC quote for volume
    btc_quote = await get_best_quote("BTC")
    if btc_quote:
        context["btc_price"] = btc_quote.get("price")
        context["btc_volume_24h"] = btc_quote.get("volume_24h")
        context["btc_change_24h"] = btc_quote.get("change_24h")
    
    # Fear & Greed (alternative.me)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.alternative.me/fng/",
                timeout=5
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    fg_data = data.get("data", [{}])[0]
                    context["fear_greed"] = int(fg_data.get("value", 50))
                    context["fear_greed_label"] = fg_data.get("value_classification")
    except:
        pass
    
    context["_meta"] = {"cache_sec": 60}
    return context


# ═══════════════════════════════════════════════════════════════
# PUMP RADAR
# ═══════════════════════════════════════════════════════════════

@router.get("/pump-radar")
async def get_pump_radar(
    window: str = Query("1h", description="Window: 1h, 4h, 24h"),
    limit: int = Query(20, le=100)
):
    """
    Pump detection radar.
    
    Detects pumps using:
    - Price velocity
    - Volume spike
    - OI growth (if available)
    - Funding shift
    """
    import aiohttp
    
    # Get trending/top movers from CoinGecko
    items = []
    
    try:
        async with aiohttp.ClientSession() as session:
            # Top gainers
            async with session.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "price_change_percentage_24h_desc",
                    "per_page": limit,
                    "page": 1,
                    "sparkline": False
                },
                timeout=10
            ) as resp:
                if resp.status == 200:
                    coins = await resp.json()
                    
                    for coin in coins:
                        price_velocity = coin.get("price_change_percentage_24h", 0) / 100
                        volume = coin.get("total_volume", 0)
                        mcap = coin.get("market_cap", 1)
                        
                        # Volume spike approximation
                        volume_spike = volume / mcap * 100 if mcap > 0 else 0
                        
                        # Pump score
                        pump_score = (
                            abs(price_velocity) * 0.5 +
                            min(volume_spike / 10, 0.3) +
                            (0.2 if price_velocity > 0.1 else 0)
                        )
                        
                        items.append({
                            "symbol": coin.get("symbol", "").upper(),
                            "name": coin.get("name"),
                            "pump_score": round(min(pump_score * 100, 100)),
                            "signals": {
                                "price_velocity": round(price_velocity, 4),
                                "volume_spike": round(volume_spike, 2),
                                "volume_24h": volume,
                                "change_24h": coin.get("price_change_percentage_24h")
                            },
                            "price": coin.get("current_price"),
                            "mcap": mcap
                        })
    except Exception as e:
        pass
    
    # Sort by pump_score
    items.sort(key=lambda x: x.get("pump_score", 0), reverse=True)
    
    return {
        "ts": ts_now(),
        "window": window,
        "items": items[:limit],
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# CAPITAL ROTATION
# ═══════════════════════════════════════════════════════════════

@router.get("/rotation")
async def get_capital_rotation(
    window: str = Query("24h", description="Window: 24h, 7d")
):
    """
    Capital rotation indicator.
    
    Shows:
    - BTC → Alts flow
    - Alts → Stables flow
    - Sector rotation
    """
    import aiohttp
    
    rotation = {
        "ts": ts_now(),
        "window": window,
        "btc_to_alts": None,
        "regime": None
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.coingecko.com/api/v3/global",
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    market = data.get("data", {})
                    
                    btc_dom = market.get("market_cap_percentage", {}).get("btc", 0)
                    eth_dom = market.get("market_cap_percentage", {}).get("eth", 0)
                    
                    # Alt dominance = 100 - BTC - Stables (approx)
                    alt_dom = 100 - btc_dom - 5  # Assume ~5% stables
                    
                    rotation["btc_dominance"] = round(btc_dom, 2)
                    rotation["eth_dominance"] = round(eth_dom, 2)
                    rotation["alt_dominance"] = round(alt_dom, 2)
                    
                    # Regime detection
                    if btc_dom > 55:
                        rotation["regime"] = "btc_season"
                        rotation["regime_score"] = round((btc_dom - 50) * 10)
                    elif alt_dom > 40:
                        rotation["regime"] = "alt_season"
                        rotation["regime_score"] = round((alt_dom - 35) * 10)
                    else:
                        rotation["regime"] = "neutral"
                        rotation["regime_score"] = 50
    except:
        pass
    
    rotation["_meta"] = {"cache_sec": 300}
    return rotation


# ═══════════════════════════════════════════════════════════════
# SCREENER
# ═══════════════════════════════════════════════════════════════

@router.get("/screener")
async def get_screener(
    view: str = Query("gainers_24h", description="View: trending, gainers_24h, losers_24h, volume, new_7d"),
    limit: int = Query(20, le=100),
    min_mcap: int = Query(None, description="Min market cap filter"),
    min_volume: int = Query(None, description="Min 24h volume filter")
):
    """
    Market screener - ready-to-use lists.
    
    Views:
    - trending: Most searched/viewed
    - gainers_24h: Top gainers
    - losers_24h: Top losers
    - volume: Highest volume
    - new_7d: Recently added
    """
    import aiohttp
    
    items = []
    
    try:
        async with aiohttp.ClientSession() as session:
            if view == "trending":
                # CoinGecko trending
                async with session.get(
                    "https://api.coingecko.com/api/v3/search/trending",
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for coin in data.get("coins", []):
                            item = coin.get("item", {})
                            items.append({
                                "symbol": item.get("symbol", "").upper(),
                                "name": item.get("name"),
                                "rank": item.get("market_cap_rank"),
                                "price_btc": item.get("price_btc"),
                                "score": item.get("score")
                            })
            
            elif view in ["gainers_24h", "losers_24h", "volume"]:
                order = {
                    "gainers_24h": "price_change_percentage_24h_desc",
                    "losers_24h": "price_change_percentage_24h_asc",
                    "volume": "volume_desc"
                }[view]
                
                async with session.get(
                    "https://api.coingecko.com/api/v3/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "order": order,
                        "per_page": limit * 2,  # Get more to filter
                        "page": 1,
                        "sparkline": False
                    },
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        coins = await resp.json()
                        
                        for coin in coins:
                            mcap = coin.get("market_cap", 0)
                            vol = coin.get("total_volume", 0)
                            
                            # Apply filters
                            if min_mcap and mcap < min_mcap:
                                continue
                            if min_volume and vol < min_volume:
                                continue
                            
                            items.append({
                                "symbol": coin.get("symbol", "").upper(),
                                "name": coin.get("name"),
                                "price": coin.get("current_price"),
                                "change_24h": coin.get("price_change_percentage_24h"),
                                "volume_24h": vol,
                                "mcap": mcap,
                                "rank": coin.get("market_cap_rank")
                            })
    except Exception as e:
        pass
    
    return {
        "ts": ts_now(),
        "view": view,
        "items": items[:limit],
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# MARKET SIGNALS (per symbol)
# ═══════════════════════════════════════════════════════════════

@router.get("/signals/{symbol}")
async def get_market_signals(
    symbol: str,
    timeframe: str = Query("1h", description="Timeframe: 1h, 4h, 1d")
):
    """
    Get market signals for symbol.
    
    Signals:
    1. Momentum (velocity + acceleration)
    2. Trend Strength
    3. Volatility
    4. Liquidity Depth
    5. Funding Pressure (for perps)
    """
    resolved = resolve_symbol(symbol)
    
    # Get quote
    quote = await get_best_quote(resolved["canonical"])
    if not quote:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")
    
    # Get candles for calculations
    candles_data = None
    try:
        from modules.market_data.providers.registry import provider_registry
        for prov in ["hyperliquid", "binance", "bybit"]:
            try:
                adapter = provider_registry.get(prov)
                if adapter:
                    candles = await adapter.get_candles(resolved["usdt_pair"], timeframe, 24)
                    if candles and len(candles) >= 10:
                        candles_data = candles
                        break
            except:
                continue
    except:
        pass
    
    signals = {}
    
    # 1. Momentum (price change rate)
    change_24h = quote.get("change_24h", 0) or 0
    momentum_value = change_24h / 100 if change_24h else 0
    signals["momentum"] = {
        "value": round(momentum_value, 4),
        "unit": "ratio",
        "interpretation": "bullish" if momentum_value > 0.02 else "bearish" if momentum_value < -0.02 else "neutral"
    }
    
    # 2. Trend Strength (simplified)
    if candles_data and len(candles_data) >= 10:
        closes = []
        for c in candles_data:
            if isinstance(c, dict):
                closes.append(c.get("close") or c.get("c", 0))
            elif isinstance(c, (list, tuple)):
                closes.append(c[4])  # close is index 4
        
        if len(closes) >= 2:
            # Count green candles
            green = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
            trend_consistency = green / (len(closes) - 1)
            
            # Slope
            slope = (closes[-1] - closes[0]) / closes[0] if closes[0] else 0
            
            trend_strength = (abs(slope) * 0.6 + trend_consistency * 0.4) * 100
            signals["trend_strength"] = {
                "value": round(min(trend_strength, 100), 1),
                "unit": "index",
                "interpretation": "strong" if trend_strength > 50 else "weak"
            }
    
    # 3. Volatility
    if candles_data and len(candles_data) >= 5:
        try:
            returns = []
            for i in range(1, len(closes)):
                if closes[i-1] > 0:
                    returns.append((closes[i] - closes[i-1]) / closes[i-1])
            
            if returns:
                volatility = statistics.stdev(returns) if len(returns) > 1 else 0
                signals["volatility"] = {
                    "value": round(volatility, 4),
                    "unit": "ratio",
                    "interpretation": "high" if volatility > 0.03 else "low" if volatility < 0.01 else "normal"
                }
        except:
            pass
    
    # 4. Liquidity (based on volume)
    volume = quote.get("volume_24h", 0) or 0
    price = quote.get("price", 0) or 0
    
    # Rough liquidity score
    if volume > 1_000_000_000:
        liq_score = 0.95
    elif volume > 100_000_000:
        liq_score = 0.8
    elif volume > 10_000_000:
        liq_score = 0.6
    else:
        liq_score = 0.3
    
    signals["liquidity_depth"] = {
        "value": round(liq_score, 2),
        "unit": "score",
        "interpretation": "healthy" if liq_score > 0.7 else "thin"
    }
    
    # 5. Funding Pressure (placeholder - needs derivatives data)
    signals["funding_pressure"] = {
        "value": 0,
        "unit": "score",
        "interpretation": "neutral"
    }
    
    return {
        "symbol": resolved["canonical"],
        "timeframe": timeframe,
        "ts": ts_now(),
        "signals": signals,
        "inputs": {
            "price": price,
            "volume_24h": volume,
            "provider": quote.get("provider")
        },
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# INDICATORS (Widget Collection)
# ═══════════════════════════════════════════════════════════════

@router.get("/indicators")
async def get_indicators(
    set: str = Query("base", description="Indicator set: base"),
    limit: int = Query(10, le=50)
):
    """
    Get indicator widgets - ready-to-render data.
    
    Widgets:
    - trending
    - gainers_24h
    - accumulation_24h
    - new_7d
    - token_unlocks
    - market_context
    """
    import aiohttp
    from server import db
    
    widgets = []
    
    try:
        async with aiohttp.ClientSession() as session:
            # Trending
            try:
                async with session.get(
                    "https://api.coingecko.com/api/v3/search/trending",
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = []
                        for coin in data.get("coins", [])[:limit]:
                            item = coin.get("item", {})
                            items.append({
                                "symbol": item.get("symbol", "").upper(),
                                "name": item.get("name"),
                                "rank": item.get("market_cap_rank")
                            })
                        widgets.append({
                            "key": "trending",
                            "title": "Trending",
                            "items": items,
                            "cache_sec": 300
                        })
            except:
                pass
            
            # Top Gainers
            try:
                async with session.get(
                    "https://api.coingecko.com/api/v3/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "order": "price_change_percentage_24h_desc",
                        "per_page": limit,
                        "page": 1
                    },
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        coins = await resp.json()
                        items = []
                        for coin in coins:
                            items.append({
                                "symbol": coin.get("symbol", "").upper(),
                                "name": coin.get("name"),
                                "price": coin.get("current_price"),
                                "change_24h": coin.get("price_change_percentage_24h"),
                                "volume_24h": coin.get("total_volume")
                            })
                        widgets.append({
                            "key": "gainers_24h",
                            "title": "Top Gainers (24h)",
                            "items": items,
                            "cache_sec": 60
                        })
            except:
                pass
    except:
        pass
    
    # Token Unlocks from Intel layer
    try:
        unlocks = []
        cursor = db.intel_unlocks.find({}).sort("unlock_date", 1).limit(limit)
        async for doc in cursor:
            unlocks.append({
                "symbol": doc.get("symbol"),
                "project": doc.get("project_name"),
                "unlock_date": doc.get("unlock_date"),
                "value_usd": doc.get("value_usd"),
                "percent_supply": doc.get("percent_supply")
            })
        
        if unlocks:
            widgets.append({
                "key": "token_unlocks",
                "title": "Token Unlocks",
                "items": unlocks,
                "cache_sec": 300
            })
    except:
        pass
    
    # Market Context
    context = await get_market_context()
    widgets.append({
        "key": "market_context",
        "title": "Market Context",
        "data": {
            "total_market_cap": context.get("total_market_cap"),
            "btc_dominance": context.get("btc_dominance"),
            "fear_greed": context.get("fear_greed")
        },
        "cache_sec": 60
    })
    
    return {
        "ts": ts_now(),
        "set": set,
        "widgets": widgets,
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# LIQUIDITY
# ═══════════════════════════════════════════════════════════════

@router.get("/liquidity/{symbol}")
async def get_liquidity(symbol: str):
    """
    Get liquidity metrics for symbol.
    
    Returns:
    - liquidity_score: 0-100 score
    - orderbook_depth_2pct: Depth within 2% of mid price
    - spread_bps: Bid-ask spread in basis points
    - slippage_estimate: Estimated slippage for $100k order
    """
    from modules.market_data.providers.registry import provider_registry
    from modules.market_data.domain.types import Venue
    
    resolved = resolve_symbol(symbol)
    
    liquidity = {
        "ts": ts_now(),
        "symbol": resolved["canonical"],
        "liquidity_score": 0,
        "orderbook_depth_2pct": None,
        "spread_bps": None,
        "slippage_estimate_100k": None,
        "by_exchange": {}
    }
    
    # Try to get orderbook from HyperLiquid
    try:
        adapter = provider_registry.get(Venue.HYPERLIQUID)
        if adapter:
            book = await adapter.get_orderbook(resolved["canonical"], 20)
            if book:
                bids = book.get("bids", [])
                asks = book.get("asks", [])
                
                if bids and asks:
                    # Calculate spread
                    best_bid = float(bids[0][0]) if isinstance(bids[0], (list, tuple)) else float(bids[0].get("price", 0))
                    best_ask = float(asks[0][0]) if isinstance(asks[0], (list, tuple)) else float(asks[0].get("price", 0))
                    mid_price = (best_bid + best_ask) / 2
                    
                    if mid_price > 0:
                        spread_bps = (best_ask - best_bid) / mid_price * 10000
                        liquidity["spread_bps"] = round(spread_bps, 2)
                        
                        # Calculate depth within 2%
                        bid_depth = sum(
                            float(b[1]) * float(b[0]) if isinstance(b, (list, tuple)) else float(b.get("size", 0)) * float(b.get("price", 0))
                            for b in bids[:10]
                            if (isinstance(b, (list, tuple)) and float(b[0]) >= mid_price * 0.98) or 
                               (isinstance(b, dict) and float(b.get("price", 0)) >= mid_price * 0.98)
                        )
                        ask_depth = sum(
                            float(a[1]) * float(a[0]) if isinstance(a, (list, tuple)) else float(a.get("size", 0)) * float(a.get("price", 0))
                            for a in asks[:10]
                            if (isinstance(a, (list, tuple)) and float(a[0]) <= mid_price * 1.02) or 
                               (isinstance(a, dict) and float(a.get("price", 0)) <= mid_price * 1.02)
                        )
                        
                        liquidity["orderbook_depth_2pct"] = round(bid_depth + ask_depth, 2)
                        liquidity["by_exchange"]["hyperliquid"] = {
                            "depth": round(bid_depth + ask_depth, 2),
                            "spread_bps": round(spread_bps, 2)
                        }
                        
                        # Estimate slippage for $100k order
                        if bid_depth > 0:
                            slippage = 100000 / bid_depth * 100 if bid_depth > 100000 else 1.0
                            liquidity["slippage_estimate_100k"] = round(min(slippage, 5.0), 2)
    except Exception as e:
        pass
    
    # Calculate liquidity score
    score = 50  # Base score
    if liquidity["spread_bps"]:
        if liquidity["spread_bps"] < 5:
            score += 25
        elif liquidity["spread_bps"] < 20:
            score += 15
        elif liquidity["spread_bps"] < 50:
            score += 5
    
    if liquidity["orderbook_depth_2pct"]:
        if liquidity["orderbook_depth_2pct"] > 1000000:
            score += 25
        elif liquidity["orderbook_depth_2pct"] > 100000:
            score += 15
        elif liquidity["orderbook_depth_2pct"] > 10000:
            score += 5
    
    liquidity["liquidity_score"] = min(score, 100)
    liquidity["_meta"] = {"cache_sec": 30}
    
    return liquidity


# ═══════════════════════════════════════════════════════════════
# VOLUME CHANGE
# ═══════════════════════════════════════════════════════════════

@router.get("/volume-change/{symbol}")
async def get_volume_change(symbol: str):
    """
    Get volume change metrics.
    
    Returns:
    - volume_24h
    - volume_change_24h_pct
    - volume_7d_avg
    - volume_spike_ratio
    """
    resolved = resolve_symbol(symbol)
    
    # Get quote for volume
    quote = await get_best_quote(resolved["canonical"])
    
    volume_data = {
        "ts": ts_now(),
        "symbol": resolved["canonical"],
        "volume_24h": quote.get("volume_24h") if quote else None,
        "volume_change_24h_pct": None,
        "volume_7d_avg": None,
        "volume_spike_ratio": None,
        "_meta": {"cache_sec": 60}
    }
    
    # Note: Real historical volume comparison requires candle data
    # For now, provide current volume with placeholder for comparison
    if volume_data["volume_24h"]:
        # Assume 7d avg is similar (would need historical data)
        volume_data["volume_7d_avg"] = volume_data["volume_24h"]
        volume_data["volume_spike_ratio"] = 1.0
    
    return volume_data


# ═══════════════════════════════════════════════════════════════
# TURNOVER RATIO
# ═══════════════════════════════════════════════════════════════

@router.get("/turnover/{symbol}")
async def get_turnover(symbol: str):
    """
    Get turnover ratio = volume / marketcap.
    
    High turnover (>0.3) = market potentially overheated
    Low turnover (<0.05) = low activity/interest
    """
    import aiohttp
    
    resolved = resolve_symbol(symbol)
    
    turnover_data = {
        "ts": ts_now(),
        "symbol": resolved["canonical"],
        "volume_24h": None,
        "market_cap": None,
        "turnover_ratio": None,
        "interpretation": None,
        "_meta": {"cache_sec": 60}
    }
    
    # Get volume from quote
    quote = await get_best_quote(resolved["canonical"])
    if quote:
        turnover_data["volume_24h"] = quote.get("volume_24h")
    
    # Get market cap from CoinGecko
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.coingecko.com/api/v3/coins/{resolved['canonical'].lower()}",
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    turnover_data["market_cap"] = data.get("market_data", {}).get("market_cap", {}).get("usd")
    except:
        pass
    
    # Calculate turnover
    if turnover_data["volume_24h"] and turnover_data["market_cap"]:
        ratio = turnover_data["volume_24h"] / turnover_data["market_cap"]
        turnover_data["turnover_ratio"] = round(ratio, 4)
        
        if ratio > 0.5:
            turnover_data["interpretation"] = "extremely_high"
        elif ratio > 0.3:
            turnover_data["interpretation"] = "high"
        elif ratio > 0.1:
            turnover_data["interpretation"] = "normal"
        elif ratio > 0.05:
            turnover_data["interpretation"] = "low"
        else:
            turnover_data["interpretation"] = "very_low"
    
    return turnover_data


# ═══════════════════════════════════════════════════════════════
# SPREAD
# ═══════════════════════════════════════════════════════════════

@router.get("/spread/{symbol}")
async def get_spread(symbol: str):
    """
    Get bid-ask spread across exchanges.
    """
    liquidity = await get_liquidity(symbol)
    
    return {
        "ts": ts_now(),
        "symbol": liquidity["symbol"],
        "spread_bps": liquidity["spread_bps"],
        "by_exchange": liquidity["by_exchange"],
        "_meta": {"cache_sec": 30}
    }


# ═══════════════════════════════════════════════════════════════
# ARBITRAGE
# ═══════════════════════════════════════════════════════════════

@router.get("/arbitrage/{symbol}")
async def get_arbitrage(symbol: str):
    """
    Get arbitrage opportunities - price differences across exchanges.
    """
    resolved = resolve_symbol(symbol)
    providers = ["hyperliquid", "binance", "bybit", "coinbase"]
    
    prices = []
    for provider in providers:
        try:
            quote = await get_provider_quote(resolved["canonical"], provider)
            if quote and quote.get("price") and not quote.get("error"):
                prices.append({
                    "exchange": provider,
                    "price": quote["price"]
                })
        except:
            pass
    
    if len(prices) < 2:
        return {
            "ts": ts_now(),
            "symbol": resolved["canonical"],
            "arbitrage_available": False,
            "message": "Insufficient price data",
            "_meta": {"cache_sec": 30}
        }
    
    # Find min/max prices
    prices.sort(key=lambda x: x["price"])
    min_price = prices[0]
    max_price = prices[-1]
    
    spread = (max_price["price"] - min_price["price"]) / min_price["price"] * 100
    
    return {
        "ts": ts_now(),
        "symbol": resolved["canonical"],
        "arbitrage_available": spread > 0.1,
        "spread_pct": round(spread, 4),
        "buy_exchange": min_price["exchange"],
        "buy_price": min_price["price"],
        "sell_exchange": max_price["exchange"],
        "sell_price": max_price["price"],
        "all_prices": prices,
        "_meta": {"cache_sec": 30}
    }


# ═══════════════════════════════════════════════════════════════
# MARKET HEATMAP
# ═══════════════════════════════════════════════════════════════

@router.get("/heatmap")
async def get_market_heatmap(
    limit: int = Query(50, le=100)
):
    """
    Market Heat Score - combined indicator.
    
    Heat = 0.25 * volume_spike + 0.25 * price_momentum + 0.25 * oi_change + 0.25 * liq_imbalance
    
    High heat = high activity/interest
    """
    import aiohttp
    
    items = []
    
    # Get top tokens from CoinGecko
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
                        symbol = coin.get("symbol", "").upper()
                        price_change = coin.get("price_change_percentage_24h", 0) or 0
                        volume = coin.get("total_volume", 0) or 0
                        mcap = coin.get("market_cap", 1) or 1
                        
                        # Calculate components
                        # Volume spike (volume/mcap normalized)
                        volume_spike_score = min(volume / mcap * 10, 25)  # Max 25
                        
                        # Price momentum (abs change, capped)
                        momentum_score = min(abs(price_change) * 2.5, 25)  # Max 25
                        
                        # Heat score (simplified without derivatives)
                        heat_score = volume_spike_score + momentum_score + 25 + 25  # Base 50 for missing OI/liq
                        
                        items.append({
                            "symbol": symbol,
                            "name": coin.get("name"),
                            "heat_score": round(heat_score),
                            "components": {
                                "volume_spike": round(volume_spike_score, 1),
                                "price_momentum": round(momentum_score, 1),
                                "oi_change": 25,  # Placeholder
                                "liq_imbalance": 25  # Placeholder
                            },
                            "price": coin.get("current_price"),
                            "price_change_24h": price_change,
                            "volume_24h": volume,
                            "mcap": mcap,
                            "interpretation": "hot" if heat_score > 70 else "warm" if heat_score > 50 else "neutral"
                        })
    except:
        pass
    
    # Sort by heat score
    items.sort(key=lambda x: x["heat_score"], reverse=True)
    
    return {
        "ts": ts_now(),
        "items": items[:limit],
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# EXCHANGE MARKET SHARE
# ═══════════════════════════════════════════════════════════════

@router.get("/exchange-share/{symbol}")
async def get_exchange_share(symbol: str):
    """
    Get market share of each exchange for a token.
    
    Returns:
    - Exchange name
    - Volume share percentage
    - Volume 24h
    """
    resolved = resolve_symbol(symbol)
    providers = ["hyperliquid", "binance", "bybit", "coinbase"]
    
    volumes = []
    total_volume = 0
    
    for provider in providers:
        try:
            quote = await get_provider_quote(resolved["canonical"], provider)
            if quote and quote.get("volume_24h") and not quote.get("error"):
                vol = quote["volume_24h"]
                volumes.append({
                    "exchange": provider,
                    "volume_24h": vol,
                    "share_pct": 0  # Calculate after total
                })
                total_volume += vol
        except:
            pass
    
    # Calculate shares
    for v in volumes:
        if total_volume > 0:
            v["share_pct"] = round(v["volume_24h"] / total_volume * 100, 2)
    
    # Sort by share
    volumes.sort(key=lambda x: x["share_pct"], reverse=True)
    
    return {
        "ts": ts_now(),
        "symbol": resolved["canonical"],
        "total_volume_24h": total_volume,
        "exchanges": volumes,
        "dominant_exchange": volumes[0]["exchange"] if volumes else None,
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# MOMENTUM SCORE (Signals)
# ═══════════════════════════════════════════════════════════════

@router.get("/momentum/{symbol}")
async def get_momentum_score(symbol: str):
    """
    Calculate Momentum Score using FOMO formula.
    
    Momentum Score = 
        0.35 * price_change_24h +
        0.25 * volume_change_24h +
        0.20 * oi_change +
        0.20 * funding_pressure
    """
    resolved = resolve_symbol(symbol)
    
    # Get quote
    quote = await get_best_quote(resolved["canonical"])
    
    if not quote:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")
    
    price_change = quote.get("change_24h") or 0
    volume = quote.get("volume_24h") or 0
    
    # Normalize price change to 0-100 scale
    price_score = min(max(price_change + 10, 0), 20) * 5  # -10% to +10% -> 0-100
    
    # Volume score (based on absolute value, normalized)
    volume_score = 50  # Default without historical comparison
    if volume > 1_000_000_000:
        volume_score = 80
    elif volume > 100_000_000:
        volume_score = 60
    elif volume > 10_000_000:
        volume_score = 40
    
    # Get derivatives data if available
    oi_score = 50
    funding_score = 50
    
    try:
        from modules.market_data.providers.hyperliquid.adapter import hyperliquid_adapter
        funding = await hyperliquid_adapter.get_funding(f"{resolved['canonical']}-PERP")
        if funding:
            funding_dict = funding.model_dump() if hasattr(funding, 'model_dump') else {}
            funding_rate = funding_dict.get("funding_rate", 0)
            
            # Funding score: high positive = bullish pressure, high negative = bearish pressure
            funding_score = 50 + funding_rate * 10000  # Scale to 0-100ish
            funding_score = min(max(funding_score, 0), 100)
    except:
        pass
    
    # Calculate final momentum score
    momentum_score = (
        0.35 * price_score +
        0.25 * volume_score +
        0.20 * oi_score +
        0.20 * funding_score
    )
    
    return {
        "ts": ts_now(),
        "symbol": resolved["canonical"],
        "momentum_score": round(momentum_score, 1),
        "components": {
            "price_change_score": round(price_score, 1),
            "volume_score": round(volume_score, 1),
            "oi_change_score": round(oi_score, 1),
            "funding_pressure_score": round(funding_score, 1)
        },
        "raw_data": {
            "price_change_24h": price_change,
            "volume_24h": volume
        },
        "interpretation": "bullish" if momentum_score > 60 else "bearish" if momentum_score < 40 else "neutral",
        "_meta": {"cache_sec": 60}
    }
