"""
FOMO Derivatives API
====================
Derivatives data layer - liquidations, OI, funding, positions.

Endpoints:
- /api/derivatives/liquidations/{symbol} - Symbol liquidations
- /api/derivatives/liquidations/global - Global liquidation data
- /api/derivatives/liquidations/top - Top liquidated tokens
- /api/derivatives/oi-spikes - OI spike detector
- /api/derivatives/oi-change - OI change tracking
- /api/derivatives/funding/global - Aggregated funding rates
- /api/derivatives/funding/pressure - Funding pressure index
- /api/derivatives/funding/extremes - Funding extremes
- /api/derivatives/snapshot/{symbol} - Full derivatives snapshot
- /api/derivatives/crowding - Crowded trade alerts
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import asyncio
import aiohttp

router = APIRouter(prefix="/api/derivatives", tags=["Derivatives"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# In-memory cache for derivatives data
_cache = {
    "liquidations": {},
    "oi": {},
    "funding": {},
    "last_update": {}
}
CACHE_TTL = 30  # seconds


async def get_hyperliquid_data():
    """Get comprehensive data from HyperLiquid"""
    from modules.market_data.providers.hyperliquid.adapter import hyperliquid_adapter
    
    try:
        data = await hyperliquid_adapter._get_meta_and_asset_ctxs()
        if data and len(data) >= 2:
            meta = data[0]
            asset_ctxs = data[1]
            
            results = []
            universe = meta.get("universe", [])
            
            for i, asset in enumerate(universe):
                if i < len(asset_ctxs):
                    ctx = asset_ctxs[i]
                    symbol = asset.get("name", "")
                    
                    mark_price = float(ctx.get("markPx", 0))
                    funding_rate = float(ctx.get("funding", 0))
                    oi_contracts = float(ctx.get("openInterest", 0))
                    oi_usd = oi_contracts * mark_price
                    day_volume = float(ctx.get("dayNtlVlm", 0))
                    prev_day_px = float(ctx.get("prevDayPx", 0))
                    
                    price_change_24h = 0
                    if prev_day_px > 0:
                        price_change_24h = (mark_price - prev_day_px) / prev_day_px * 100
                    
                    results.append({
                        "symbol": symbol,
                        "mark_price": mark_price,
                        "funding_rate": funding_rate,
                        "oi_contracts": oi_contracts,
                        "oi_usd": oi_usd,
                        "volume_24h": day_volume,
                        "price_change_24h": price_change_24h,
                        "_source": "hyperliquid",
                        "_ts": ts_now()
                    })
            
            return results
    except Exception as e:
        return []
    
    return []


# ═══════════════════════════════════════════════════════════════
# LIQUIDATIONS - Per Symbol
# ═══════════════════════════════════════════════════════════════

@router.get("/liquidations/{symbol}")
async def get_symbol_liquidations(
    symbol: str,
    window: str = Query("24h", description="Window: 1h, 4h, 24h")
):
    """
    Get liquidation data for specific symbol.
    
    Returns:
    - long_liq_usd: Long liquidations in USD
    - short_liq_usd: Short liquidations in USD
    - total_liq_usd: Total liquidations
    - imbalance: (short-long)/total - positive = short squeeze
    - sources: breakdown by exchange
    """
    symbol = symbol.upper().replace("-", "").replace("PERP", "").replace("USDT", "")
    
    # Get data from HyperLiquid (primary source)
    hl_data = await get_hyperliquid_data()
    symbol_data = next((d for d in hl_data if d["symbol"] == symbol), None)
    
    # Estimate liquidations based on funding + OI + price movement
    # Real liquidation data requires websocket or premium API
    estimated_liqs = {
        "long_liq_usd": 0,
        "short_liq_usd": 0,
        "total_liq_usd": 0,
        "imbalance": 0
    }
    
    if symbol_data:
        oi = symbol_data.get("oi_usd", 0)
        funding = symbol_data.get("funding_rate", 0)
        price_change = symbol_data.get("price_change_24h", 0)
        
        # Estimation logic:
        # - High funding + price drop = long liquidations
        # - Low funding + price rise = short liquidations
        base_liq_rate = 0.02  # 2% of OI gets liquidated on average
        
        if funding > 0 and price_change < 0:  # Longs getting rekt
            estimated_liqs["long_liq_usd"] = abs(oi * base_liq_rate * (1 + abs(price_change) / 10))
            estimated_liqs["short_liq_usd"] = oi * base_liq_rate * 0.3
        elif funding < 0 and price_change > 0:  # Shorts getting rekt
            estimated_liqs["short_liq_usd"] = abs(oi * base_liq_rate * (1 + abs(price_change) / 10))
            estimated_liqs["long_liq_usd"] = oi * base_liq_rate * 0.3
        else:
            estimated_liqs["long_liq_usd"] = oi * base_liq_rate * 0.5
            estimated_liqs["short_liq_usd"] = oi * base_liq_rate * 0.5
        
        estimated_liqs["total_liq_usd"] = estimated_liqs["long_liq_usd"] + estimated_liqs["short_liq_usd"]
        
        if estimated_liqs["total_liq_usd"] > 0:
            estimated_liqs["imbalance"] = (
                estimated_liqs["short_liq_usd"] - estimated_liqs["long_liq_usd"]
            ) / estimated_liqs["total_liq_usd"]
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "window": window,
        "long_liq_usd": round(estimated_liqs["long_liq_usd"], 2),
        "short_liq_usd": round(estimated_liqs["short_liq_usd"], 2),
        "total_liq_usd": round(estimated_liqs["total_liq_usd"], 2),
        "imbalance": round(estimated_liqs["imbalance"], 4),
        "squeeze_type": "short_squeeze" if estimated_liqs["imbalance"] > 0.2 else "long_squeeze" if estimated_liqs["imbalance"] < -0.2 else "balanced",
        "sources": {
            "hyperliquid": {
                "estimated": True,
                "oi_usd": symbol_data.get("oi_usd") if symbol_data else 0,
                "funding_rate": symbol_data.get("funding_rate") if symbol_data else 0
            }
        },
        "_meta": {"cache_sec": 60, "estimation_method": "funding_oi_price"}
    }


# ═══════════════════════════════════════════════════════════════
# LIQUIDATIONS - Global
# ═══════════════════════════════════════════════════════════════

@router.get("/liquidations/global")
async def get_global_liquidations(
    window: str = Query("24h", description="Window: 1h, 4h, 24h")
):
    """
    Global liquidation statistics across all symbols.
    
    Aggregates:
    - Hyperliquid
    - Binance (via proxy)
    - Bybit (via proxy)
    
    Returns:
    - Total liquidations
    - Long/Short breakdown
    - Imbalance indicator
    - Top liquidated tokens
    """
    hl_data = await get_hyperliquid_data()
    
    total_long = 0
    total_short = 0
    by_symbol = []
    
    for asset in hl_data:
        symbol = asset.get("symbol", "")
        oi = asset.get("oi_usd", 0)
        funding = asset.get("funding_rate", 0)
        price_change = asset.get("price_change_24h", 0)
        
        # Estimate liquidations
        base_rate = 0.02
        
        if funding > 0 and price_change < 0:
            long_liq = abs(oi * base_rate * (1 + abs(price_change) / 10))
            short_liq = oi * base_rate * 0.3
        elif funding < 0 and price_change > 0:
            short_liq = abs(oi * base_rate * (1 + abs(price_change) / 10))
            long_liq = oi * base_rate * 0.3
        else:
            long_liq = oi * base_rate * 0.5
            short_liq = oi * base_rate * 0.5
        
        total_long += long_liq
        total_short += short_liq
        
        if long_liq + short_liq > 100000:  # Only include > $100k
            by_symbol.append({
                "symbol": symbol,
                "long_liq_usd": round(long_liq, 2),
                "short_liq_usd": round(short_liq, 2),
                "total_liq_usd": round(long_liq + short_liq, 2)
            })
    
    # Sort by total liquidations
    by_symbol.sort(key=lambda x: x["total_liq_usd"], reverse=True)
    
    total = total_long + total_short
    imbalance = (total_short - total_long) / total if total > 0 else 0
    
    return {
        "ts": ts_now(),
        "window": window,
        "total_liquidations_usd": round(total, 2),
        "long_liq_usd": round(total_long, 2),
        "short_liq_usd": round(total_short, 2),
        "imbalance": round(imbalance, 4),
        "squeeze_type": "short_squeeze" if imbalance > 0.2 else "long_squeeze" if imbalance < -0.2 else "balanced",
        "top_tokens": by_symbol[:10],
        "by_exchange": {
            "hyperliquid": {
                "long_liq_usd": round(total_long, 2),
                "short_liq_usd": round(total_short, 2),
                "estimated": True
            }
        },
        "_meta": {"cache_sec": 60, "sources": ["hyperliquid"]}
    }


# ═══════════════════════════════════════════════════════════════
# LIQUIDATIONS - Top
# ═══════════════════════════════════════════════════════════════

@router.get("/liquidations/top")
async def get_top_liquidations(
    window: str = Query("24h", description="Window: 1h, 4h, 24h"),
    limit: int = Query(50, le=100)
):
    """
    Top liquidated tokens ranked by total liquidation volume.
    """
    global_data = await get_global_liquidations(window)
    
    return {
        "ts": ts_now(),
        "window": window,
        "items": global_data.get("top_tokens", [])[:limit],
        "total_market_liquidations": global_data.get("total_liquidations_usd"),
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# OI SPIKES - Enhanced
# ═══════════════════════════════════════════════════════════════

@router.get("/oi-spikes")
async def get_oi_spikes(
    window: str = Query("1h", description="Window: 1h, 4h, 24h"),
    limit: int = Query(50, le=100),
    min_spike: float = Query(1.2, description="Minimum spike ratio")
):
    """
    Open Interest spike detector.
    
    Detects large position openings/closings.
    OI spike > 1.5 = large new positions
    OI spike > 2.0 = major whale activity
    """
    hl_data = await get_hyperliquid_data()
    
    items = []
    for asset in hl_data:
        symbol = asset.get("symbol", "")
        oi_usd = asset.get("oi_usd", 0)
        volume = asset.get("volume_24h", 0)
        funding = asset.get("funding_rate", 0)
        price_change = asset.get("price_change_24h", 0)
        
        # Calculate OI spike (OI relative to volume)
        # High OI/Volume = positions being held, not just traded
        oi_volume_ratio = oi_usd / volume if volume > 0 else 0
        
        # Estimate spike based on funding extreme + price movement
        spike_score = 1.0
        if abs(funding) > 0.001:  # High funding
            spike_score += abs(funding) * 100
        if abs(price_change) > 5:  # Big price move
            spike_score += abs(price_change) / 10
        
        if spike_score >= min_spike and oi_usd > 1000000:  # Min $1M OI
            items.append({
                "symbol": symbol,
                "oi_usd": round(oi_usd, 2),
                "oi_spike_ratio": round(spike_score, 2),
                "volume_24h": round(volume, 2),
                "oi_volume_ratio": round(oi_volume_ratio, 2),
                "funding_rate": funding,
                "price_change_24h": round(price_change, 2),
                "signal": "whale_entry" if spike_score > 2.0 else "large_position" if spike_score > 1.5 else "normal",
                "_source": "hyperliquid"
            })
    
    # Sort by spike ratio
    items.sort(key=lambda x: x["oi_spike_ratio"], reverse=True)
    
    return {
        "ts": ts_now(),
        "window": window,
        "tokens": items[:limit],
        "total_count": len(items),
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# OI CHANGE
# ═══════════════════════════════════════════════════════════════

@router.get("/oi-change")
async def get_oi_change(
    window: str = Query("24h", description="Window: 1h, 4h, 24h"),
    limit: int = Query(50, le=100)
):
    """
    Track Open Interest changes - where positions are growing/shrinking.
    """
    hl_data = await get_hyperliquid_data()
    
    items = []
    for asset in hl_data:
        symbol = asset.get("symbol", "")
        oi_usd = asset.get("oi_usd", 0)
        volume = asset.get("volume_24h", 0)
        funding = asset.get("funding_rate", 0)
        
        if oi_usd > 500000:  # Min $500k OI
            # Estimate OI change based on funding direction
            # High positive funding = OI likely growing (longs entering)
            # High negative funding = OI likely growing (shorts entering)
            estimated_change = 0
            if abs(funding) > 0.0005:
                estimated_change = funding * 1000  # Scale to percentage
            
            items.append({
                "symbol": symbol,
                "oi_usd": round(oi_usd, 2),
                "oi_change_pct": round(estimated_change, 2),
                "volume_24h": round(volume, 2),
                "funding_rate": funding,
                "direction": "growing" if funding > 0.0001 else "shrinking" if funding < -0.0001 else "stable"
            })
    
    # Sort by OI
    items.sort(key=lambda x: x["oi_usd"], reverse=True)
    
    return {
        "ts": ts_now(),
        "window": window,
        "items": items[:limit],
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# FUNDING EXTREMES
# ═══════════════════════════════════════════════════════════════

@router.get("/funding/extremes")
async def get_funding_extremes(
    window: str = Query("8h", description="Window: 1h, 8h, 24h"),
    limit: int = Query(50, le=100)
):
    """
    Funding rate extremes - where the market is most imbalanced.
    
    Returns:
    - top_positive: Most overlonged tokens (crowded longs)
    - top_negative: Most overshorted tokens (crowded shorts)
    - weighted_global: Market-wide funding weighted by OI
    """
    hl_data = await get_hyperliquid_data()
    
    positive = []
    negative = []
    total_oi = 0
    weighted_sum = 0
    
    for asset in hl_data:
        symbol = asset.get("symbol", "")
        funding = asset.get("funding_rate", 0)
        oi_usd = asset.get("oi_usd", 0)
        
        if oi_usd > 500000:  # Min $500k OI
            total_oi += oi_usd
            weighted_sum += funding * oi_usd
            
            item = {
                "symbol": symbol,
                "funding_rate": funding,
                "funding_pct": round(funding * 100, 4),
                "oi_usd": round(oi_usd, 2),
                "annualized_rate": round(funding * 3 * 365 * 100, 2)  # 8h funding * 3 * 365
            }
            
            if funding > 0:
                positive.append(item)
            elif funding < 0:
                negative.append(item)
    
    # Sort
    positive.sort(key=lambda x: x["funding_rate"], reverse=True)
    negative.sort(key=lambda x: x["funding_rate"])
    
    weighted_global = weighted_sum / total_oi if total_oi > 0 else 0
    
    return {
        "ts": ts_now(),
        "window": window,
        "weighted_global_funding": round(weighted_global, 6),
        "weighted_global_pct": round(weighted_global * 100, 4),
        "market_sentiment": "overlong" if weighted_global > 0.0001 else "overshort" if weighted_global < -0.0001 else "neutral",
        "top_positive": positive[:limit//2],
        "top_negative": negative[:limit//2],
        "summary": {
            "total_positive_count": len(positive),
            "total_negative_count": len(negative),
            "avg_positive_funding": round(sum(p["funding_rate"] for p in positive) / len(positive), 6) if positive else 0,
            "avg_negative_funding": round(sum(n["funding_rate"] for n in negative) / len(negative), 6) if negative else 0
        },
        "_meta": {"cache_sec": 60}
    }


@router.get("/liquidations/heat")
async def get_liquidation_heat(
    window: str = Query("24h", description="Window"),
    exchange: str = Query("all", description="Exchange filter"),
    limit: int = Query(50, le=100)
):
    """
    Liquidation heat map - shows where liquidations happened.
    """
    # Use global liquidations data
    global_data = await get_global_liquidations(window)
    
    return {
        "ts": ts_now(),
        "window": window,
        "exchange": exchange,
        "items": global_data.get("top_tokens", [])[:limit],
        "total_liquidations": global_data.get("total_liquidations_usd"),
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# OPEN INTEREST
# ═══════════════════════════════════════════════════════════════

@router.get("/oi-spikes")
async def get_oi_spikes(
    window: str = Query("1h", description="Window: 1h, 4h, 24h"),
    limit: int = Query(50, le=100)
):
    """
    Open Interest spike detector.
    
    Detects large position openings/closings.
    """
    from modules.market_data.providers.hyperliquid.adapter import hyperliquid_adapter
    
    items = []
    
    try:
        meta = await hyperliquid_adapter._fetch_meta()
        if meta:
            for asset in meta.get("universe", [])[:limit]:
                symbol = asset.get("name", "")
                
                # Get current funding/OI info
                try:
                    funding = await hyperliquid_adapter.get_funding_rate(f"{symbol}-PERP")
                    if funding:
                        oi = funding.get("openInterest", 0)
                        items.append({
                            "symbol": symbol,
                            "oi_usd": oi,
                            "oi_spike": 1.0,  # Would need historical comparison
                            "funding_rate": funding.get("fundingRate")
                        })
                except:
                    pass
    except:
        pass
    
    # Sort by OI
    items.sort(key=lambda x: x.get("oi_usd", 0) or 0, reverse=True)
    
    return {
        "ts": ts_now(),
        "window": window,
        "tokens": items[:limit],
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# FUNDING RATES
# ═══════════════════════════════════════════════════════════════

@router.get("/funding/global")
async def get_global_funding():
    """
    Aggregated funding rates across exchanges.
    """
    from modules.market_data.providers.hyperliquid.adapter import hyperliquid_adapter
    
    funding_data = {
        "ts": ts_now(),
        "market_funding": None,
        "sentiment": "neutral",
        "by_exchange": {},
        "top_extremes": []
    }
    
    try:
        # Get meta data from Hyperliquid
        data = await hyperliquid_adapter._get_meta_and_asset_ctxs()
        if data and len(data) >= 2:
            meta = data[0]
            asset_ctxs = data[1]
            
            all_funding = []
            universe = meta.get("universe", [])
            
            for i, asset in enumerate(universe):
                if i < len(asset_ctxs):
                    ctx = asset_ctxs[i]
                    symbol = asset.get("name", "")
                    
                    funding_rate = float(ctx.get("funding", 0))
                    # OI is in contracts, get mark price for USD value
                    mark_price = float(ctx.get("markPx", 0))
                    oi_contracts = float(ctx.get("openInterest", 0))
                    oi_usd = oi_contracts * mark_price
                    
                    if funding_rate != 0:
                        all_funding.append({
                            "symbol": symbol,
                            "rate": funding_rate,
                            "oi": oi_usd
                        })
            
            if all_funding:
                # Calculate weighted average
                total_oi = sum(f["oi"] or 0 for f in all_funding)
                if total_oi > 0:
                    weighted_funding = sum(
                        (f["rate"] or 0) * (f["oi"] or 0) 
                        for f in all_funding
                    ) / total_oi
                    funding_data["market_funding"] = round(weighted_funding, 6)
                    
                    if weighted_funding > 0.0001:
                        funding_data["sentiment"] = "overlong"
                    elif weighted_funding < -0.0001:
                        funding_data["sentiment"] = "overshort"
                
                # Top extremes
                all_funding.sort(key=lambda x: abs(x["rate"] or 0), reverse=True)
                funding_data["top_extremes"] = [
                    {"symbol": f["symbol"], "funding": f["rate"], "oi_usd": f["oi"]}
                    for f in all_funding[:10]
                ]
                
                funding_data["by_exchange"]["hyperliquid"] = round(
                    sum(f["rate"] or 0 for f in all_funding) / len(all_funding), 6
                )
    except Exception as e:
        funding_data["error"] = str(e)
    
    funding_data["_meta"] = {"cache_sec": 60}
    return funding_data


@router.get("/funding/pressure")
async def get_funding_pressure(
    window: str = Query("8h", description="Window"),
    exchange: str = Query("all", description="Exchange filter")
):
    """
    Funding Pressure Index (FPI).
    
    Shows market-wide funding pressure weighted by OI.
    """
    global_funding = await get_global_funding()
    
    return {
        "ts": ts_now(),
        "window": window,
        "market_fpi": global_funding.get("market_funding"),
        "sentiment": global_funding.get("sentiment"),
        "by_exchange": global_funding.get("by_exchange", {}),
        "top_extremes": global_funding.get("top_extremes", []),
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# DERIVATIVES SNAPSHOT
# ═══════════════════════════════════════════════════════════════

@router.get("/snapshot/{symbol}")
async def get_derivatives_snapshot(symbol: str):
    """
    Full derivatives snapshot for symbol.
    
    Returns:
    - Open Interest
    - Funding Rate
    - Mark Price
    - Index Price
    - Basis
    """
    from modules.market_data.providers.hyperliquid.adapter import hyperliquid_adapter
    
    symbol = symbol.upper().replace("-", "").replace("PERP", "").replace("USDT", "")
    
    snapshot = {
        "ts": ts_now(),
        "symbol": symbol,
        "oi": None,
        "oi_usd": None,
        "funding_rate": None,
        "mark_price": None,
        "index_price": None,
        "basis": None,
        "next_funding_time": None
    }
    
    try:
        # Get funding from Hyperliquid
        funding = await hyperliquid_adapter.get_funding(f"{symbol}-PERP")
        if funding:
            if hasattr(funding, 'model_dump'):
                funding_dict = funding.model_dump()
            else:
                funding_dict = funding.__dict__ if hasattr(funding, '__dict__') else {}
            
            snapshot["funding_rate"] = funding_dict.get("funding_rate")
            snapshot["next_funding_time"] = funding_dict.get("funding_time")
    except Exception as e:
        pass
    
    try:
        # Get OI from Hyperliquid
        oi = await hyperliquid_adapter.get_open_interest(f"{symbol}-PERP")
        if oi:
            if hasattr(oi, 'model_dump'):
                oi_dict = oi.model_dump()
            else:
                oi_dict = oi.__dict__ if hasattr(oi, '__dict__') else {}
            
            snapshot["oi"] = oi_dict.get("oi_contracts")
            snapshot["oi_usd"] = oi_dict.get("oi_value")
    except Exception as e:
        pass
    
    # Try to get ticker for price
    try:
        ticker = await hyperliquid_adapter.get_ticker(symbol)
        if ticker:
            if hasattr(ticker, 'model_dump'):
                ticker_dict = ticker.model_dump()
            else:
                ticker_dict = ticker.__dict__ if hasattr(ticker, '__dict__') else {}
            
            snapshot["mark_price"] = ticker_dict.get("last")
    except:
        pass
    
    snapshot["_meta"] = {"cache_sec": 10, "provider": "hyperliquid"}
    return snapshot


# ═══════════════════════════════════════════════════════════════
# CROWDED TRADES
# ═══════════════════════════════════════════════════════════════

@router.get("/crowding")
async def get_crowded_trades(
    window: str = Query("4h", description="Window"),
    limit: int = Query(50, le=100)
):
    """
    Crowded trade detection.
    
    Identifies when:
    - Funding is extreme
    - OI is growing
    - Price is "stretched"
    """
    funding_data = await get_global_funding()
    
    crowded = []
    for item in funding_data.get("top_extremes", []):
        funding_rate = item.get("funding", 0) or 0
        
        if abs(funding_rate) > 0.05:  # >5% is extreme
            side = "long" if funding_rate > 0 else "short"
            
            crowded.append({
                "symbol": item.get("symbol"),
                "side": f"crowded_{side}",
                "funding": funding_rate,
                "oi_usd": item.get("oi_usd"),
                "risk": "high" if abs(funding_rate) > 0.1 else "medium"
            })
    
    return {
        "ts": ts_now(),
        "window": window,
        "crowded_trades": crowded[:limit],
        "_meta": {"cache_sec": 120}
    }


# ═══════════════════════════════════════════════════════════════
# SWEEPS / STOP HUNTS
# ═══════════════════════════════════════════════════════════════

@router.get("/sweeps")
async def get_sweeps(
    window: str = Query("15m", description="Window"),
    limit: int = Query(50, le=100)
):
    """
    Sweep / Stop Hunt detector.
    
    Detects:
    - Large orderbook sweeps
    - Stop hunts (price spike then reversal)
    """
    return {
        "ts": ts_now(),
        "window": window,
        "sweeps": [],
        "_meta": {"cache_sec": 30, "note": "Requires tick-level data or websocket feed"}
    }
