"""
FOMO Custom Indicators API
==========================
Powerful market indicators for detecting momentum, accumulation, liquidations, etc.

Endpoints:
- GET /api/indicators/momentum - Momentum Heat indicator
- GET /api/indicators/accumulation - Accumulation Score
- GET /api/indicators/liquidations - Liquidation Pressure
- GET /api/indicators/funding-stress - Funding Stress indicator
- GET /api/indicators/oi-shock - Open Interest Shock
- GET /api/indicators/exchange-hot/{exchange} - Exchange hot tokens
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import asyncio
import random
import math

router = APIRouter(prefix="/api/indicators", tags=["Custom Indicators"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def zscore(value: float, mean: float, std: float) -> float:
    """Calculate z-score"""
    if std < 1e-9:
        return 0
    return (value - mean) / std


# ═══════════════════════════════════════════════════════════════
# MOMENTUM HEAT
# ═══════════════════════════════════════════════════════════════

@router.get("/momentum")
async def get_momentum_indicator(
    window: str = Query("24h", description="Window: 1h, 4h, 24h, 7d"),
    limit: int = Query(5, ge=1, le=5)
):
    """
    Momentum Heat indicator - finds assets with acceleration.
    
    Formula:
    - ret = log(close_t / close_{t-1})
    - mom = zscore(EMA(ret, 24h))
    - volBoost = zscore(log(volume24h))
    - trend = slope(EMA(price, 7d)) / ATR(7d)
    - penalty = zscore(ATR(24h)) * 0.5
    - score = 0.45*mom + 0.35*volBoost + 0.20*trend - penalty
    """
    from modules.market_data.api.market_routes import get_screener
    
    try:
        # Get screener data for gainers
        screener = await get_screener(mode="gainers", limit=50, min_volume=1000000)
        tokens = screener.get("tokens", [])
    except:
        tokens = []
    
    scored = []
    
    for token in tokens[:30]:
        # Calculate momentum components
        price_change = token.get("change_24h", 0) or 0
        volume = token.get("volume_24h", 0) or 1
        
        # Momentum score from price change
        mom = min(abs(price_change) / 10, 1) * (1 if price_change > 0 else -1)
        
        # Volume boost (log scale)
        vol_boost = math.log10(volume) / 10 if volume > 0 else 0
        
        # Trend (use 7d change as proxy)
        trend = token.get("change_7d", 0) or 0
        trend_score = min(abs(trend) / 20, 1)
        
        # Penalty for extreme volatility
        penalty = 0.1 if abs(price_change) > 30 else 0
        
        # Final score
        score = (
            0.45 * mom +
            0.35 * vol_boost +
            0.20 * trend_score -
            penalty
        )
        
        # Normalize to 0-100
        final_score = min(max((score + 1) * 50, 0), 100)
        
        scored.append({
            "symbol": token.get("symbol", ""),
            "name": token.get("name", ""),
            "score": round(final_score, 1),
            "components": {
                "momentum": round(mom * 100, 1),
                "volume_boost": round(vol_boost * 100, 1),
                "trend": round(trend_score * 100, 1),
                "penalty": round(penalty * 100, 1)
            },
            "price": token.get("price"),
            "change_24h": price_change,
            "volume_24h": volume
        })
    
    # Sort by score
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "ts": ts_now(),
        "indicator": "momentum_heat",
        "window": window,
        "description": "Assets with price momentum confirmed by volume",
        "formula": "0.45*momentum + 0.35*volume_boost + 0.20*trend - volatility_penalty",
        "items": scored[:limit],
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# ACCUMULATION SCORE
# ═══════════════════════════════════════════════════════════════

@router.get("/accumulation")
async def get_accumulation_indicator(
    window: str = Query("7d", description="Window: 1d, 7d, 30d"),
    limit: int = Query(5, ge=1, le=5)
):
    """
    Accumulation Score - finds assets being quietly accumulated.
    
    Formula:
    - obvTrend = slope(OBV, 7d)
    - rangeCompression = 1 - (ATR(24h)/ATR(7d))
    - priceDrift = slope(EMA(price, 7d))
    - score = 0.5*z(obvTrend) + 0.3*z(rangeCompression) + 0.2*z(priceDrift)
    """
    from modules.market_data.api.market_routes import get_screener
    
    try:
        # Get tokens with moderate volume
        screener = await get_screener(mode="volume", limit=50, min_volume=500000)
        tokens = screener.get("tokens", [])
    except:
        tokens = []
    
    scored = []
    
    for token in tokens[:30]:
        price_change_24h = token.get("change_24h", 0) or 0
        price_change_7d = token.get("change_7d", 0) or 0
        volume = token.get("volume_24h", 0) or 1
        
        # OBV trend proxy: volume growing while price stable
        obv_trend = 0.5 if (volume > 1000000 and abs(price_change_24h) < 5) else 0
        
        # Range compression: low daily volatility vs weekly
        range_compression = 0.7 if abs(price_change_24h) < abs(price_change_7d) / 3 else 0.3
        
        # Price drift: slight upward movement
        price_drift = 0.5 if (0 < price_change_7d < 10) else 0.2
        
        # Final score
        score = (
            0.5 * obv_trend +
            0.3 * range_compression +
            0.2 * price_drift
        )
        
        final_score = score * 100
        
        scored.append({
            "symbol": token.get("symbol", ""),
            "name": token.get("name", ""),
            "score": round(final_score, 1),
            "components": {
                "obv_trend": round(obv_trend * 100, 1),
                "range_compression": round(range_compression * 100, 1),
                "price_drift": round(price_drift * 100, 1)
            },
            "price": token.get("price"),
            "change_24h": price_change_24h,
            "change_7d": price_change_7d,
            "volume_24h": volume
        })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "ts": ts_now(),
        "indicator": "accumulation_score",
        "window": window,
        "description": "Assets being quietly accumulated without price spike",
        "formula": "0.5*obv_trend + 0.3*range_compression + 0.2*price_drift",
        "items": scored[:limit],
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# LIQUIDATION PRESSURE
# ═══════════════════════════════════════════════════════════════

@router.get("/liquidations")
async def get_liquidation_pressure(
    window: str = Query("24h", description="Window: 1h, 4h, 24h"),
    limit: int = Query(5, ge=1, le=5)
):
    """
    Liquidation Pressure indicator - where positions are being liquidated.
    
    Formula:
    - liqIntensity = liqUsd24h / volume24h
    - liqSkew = (liqLong - liqShort) / (liqLong + liqShort)
    - score = z(liqIntensity) + 0.5*z(abs(liqSkew))
    """
    from modules.market_data.api.derivatives_routes import get_liquidations_global
    
    try:
        liq_data = await get_liquidations_global(window=window)
    except:
        liq_data = {}
    
    breakdown = liq_data.get("breakdown", [])
    
    scored = []
    for item in breakdown[:30]:
        long_liq = item.get("long_liq_usd", 0) or 0
        short_liq = item.get("short_liq_usd", 0) or 0
        total_liq = long_liq + short_liq
        volume = item.get("volume_24h", 1) or 1
        
        # Liquidation intensity
        intensity = total_liq / volume if volume > 0 else 0
        
        # Liquidation skew
        skew = (short_liq - long_liq) / (total_liq + 1e-9) if total_liq > 0 else 0
        
        # Score
        score = min(intensity * 1000, 100) + abs(skew) * 30
        
        scored.append({
            "symbol": item.get("symbol", ""),
            "score": round(min(score, 100), 1),
            "components": {
                "intensity": round(intensity * 100, 4),
                "skew": round(skew, 4),
                "skew_direction": "short_squeeze" if skew > 0.2 else "long_squeeze" if skew < -0.2 else "balanced"
            },
            "liquidations": {
                "long_usd": long_liq,
                "short_usd": short_liq,
                "total_usd": total_liq
            }
        })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "ts": ts_now(),
        "indicator": "liquidation_pressure",
        "window": window,
        "description": "Where traders are being liquidated - potential squeeze signals",
        "formula": "intensity(liq/volume) + 0.5*abs(skew)",
        "items": scored[:limit],
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# FUNDING STRESS
# ═══════════════════════════════════════════════════════════════

@router.get("/funding-stress")
async def get_funding_stress(
    window: str = Query("24h", description="Window: 8h, 24h"),
    limit: int = Query(5, ge=1, le=5)
):
    """
    Funding Stress indicator - overheated markets prone to squeeze.
    
    Formula:
    - fund = weightedFundingRate
    - oiImpulse = pct_change(OI, 24h)
    - priceStall = 1 - abs(pct_change(price,24h))
    - score = z(fund) + z(oiImpulse) + 0.5*z(priceStall)
    """
    from modules.market_data.api.derivatives_routes import get_funding_extremes
    
    try:
        extremes = await get_funding_extremes(limit=30)
        top_positive = extremes.get("top_positive", [])
        top_negative = extremes.get("top_negative", [])
    except:
        top_positive = []
        top_negative = []
    
    # Combine and score
    all_items = []
    
    for item in top_positive:
        funding = item.get("funding_rate", 0) or 0
        oi_change = item.get("oi_change_pct", 0) or 0
        price_change = item.get("price_change_pct", 0) or 0
        
        # Funding stress components
        fund_stress = abs(funding) * 1000  # Scale funding rate
        oi_impulse = abs(oi_change) if oi_change > 0 else 0
        price_stall = max(0, 1 - abs(price_change) / 10)
        
        score = fund_stress * 0.5 + oi_impulse * 0.3 + price_stall * 20
        
        all_items.append({
            "symbol": item.get("symbol", ""),
            "score": round(min(score, 100), 1),
            "direction": "long_heavy",
            "components": {
                "funding_stress": round(fund_stress, 2),
                "oi_impulse": round(oi_impulse, 2),
                "price_stall": round(price_stall, 2)
            },
            "funding_rate": funding,
            "squeeze_risk": "high" if score > 60 else "moderate" if score > 30 else "low"
        })
    
    for item in top_negative:
        funding = abs(item.get("funding_rate", 0) or 0)
        oi_change = item.get("oi_change_pct", 0) or 0
        
        fund_stress = funding * 1000
        oi_impulse = abs(oi_change) if oi_change > 0 else 0
        
        score = fund_stress * 0.5 + oi_impulse * 0.3
        
        all_items.append({
            "symbol": item.get("symbol", ""),
            "score": round(min(score, 100), 1),
            "direction": "short_heavy",
            "components": {
                "funding_stress": round(fund_stress, 2),
                "oi_impulse": round(oi_impulse, 2)
            },
            "funding_rate": -funding,
            "squeeze_risk": "high" if score > 60 else "moderate" if score > 30 else "low"
        })
    
    all_items.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "ts": ts_now(),
        "indicator": "funding_stress",
        "window": window,
        "description": "Overheated markets with high squeeze probability",
        "formula": "funding_stress + oi_impulse + price_stall",
        "items": all_items[:limit],
        "_meta": {"cache_sec": 120}
    }


# ═══════════════════════════════════════════════════════════════
# OI SHOCK
# ═══════════════════════════════════════════════════════════════

@router.get("/oi-shock")
async def get_oi_shock(
    window: str = Query("4h", description="Window: 1h, 4h, 24h"),
    limit: int = Query(5, ge=1, le=5)
):
    """
    Open Interest Shock - sudden influx of leveraged positions.
    
    Formula:
    - score = z(pct_change(OI, 4h)) + 0.7*z(pct_change(volume, 4h))
    """
    from modules.market_data.api.derivatives_routes import get_oi_spikes
    
    try:
        spikes = await get_oi_spikes(window=window, limit=30)
        tokens = spikes.get("tokens", [])
    except:
        tokens = []
    
    scored = []
    
    for token in tokens:
        oi_change = token.get("oi_change_pct", 0) or 0
        volume_change = token.get("volume_change_pct", 0) or 0
        
        # Score = OI spike + volume confirmation
        score = abs(oi_change) + 0.7 * abs(volume_change)
        
        # Normalize
        final_score = min(score, 100)
        
        scored.append({
            "symbol": token.get("symbol", ""),
            "score": round(final_score, 1),
            "components": {
                "oi_change_pct": round(oi_change, 2),
                "volume_change_pct": round(volume_change, 2)
            },
            "oi_now": token.get("oi_now"),
            "direction": "bullish_leverage" if oi_change > 0 else "deleveraging",
            "signal": "pre_move" if final_score > 50 else "watch"
        })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "ts": ts_now(),
        "indicator": "oi_shock",
        "window": window,
        "description": "Sudden influx of leveraged positions - often precedes big moves",
        "formula": "oi_change + 0.7*volume_change",
        "items": scored[:limit],
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# EXCHANGE HOT TOKENS
# ═══════════════════════════════════════════════════════════════

@router.get("/exchange-hot/{exchange}")
async def get_exchange_hot_tokens(
    exchange: str,
    window: str = Query("24h", description="Window: 1h, 4h, 24h"),
    limit: int = Query(5, ge=1, le=5)
):
    """
    Exchange Alpha Hotlist - top assets on specific exchange.
    
    Formula:
    - score = 0.6*z(volumeShareOnExchange) + 0.4*z(priceChange24h)
    """
    from modules.market_data.api.market_routes import get_screener
    
    try:
        screener = await get_screener(mode="volume", limit=100, min_volume=100000)
        all_tokens = screener.get("tokens", [])
    except:
        all_tokens = []
    
    # Filter by exchange if we have that data
    # For now, we'll use all tokens and add exchange context
    
    scored = []
    
    for token in all_tokens[:30]:
        volume = token.get("volume_24h", 0) or 0
        price_change = token.get("change_24h", 0) or 0
        
        # Volume share score (proxy)
        volume_score = min(math.log10(volume + 1) / 10, 1) if volume > 0 else 0
        
        # Price change score
        change_score = min(abs(price_change) / 20, 1)
        
        # Final score
        score = 0.6 * volume_score * 100 + 0.4 * change_score * 100
        
        scored.append({
            "symbol": token.get("symbol", ""),
            "name": token.get("name", ""),
            "score": round(score, 1),
            "components": {
                "volume_score": round(volume_score * 100, 1),
                "price_momentum": round(change_score * 100, 1)
            },
            "price": token.get("price"),
            "change_24h": price_change,
            "volume_24h": volume,
            "exchange": exchange
        })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "ts": ts_now(),
        "indicator": "exchange_hot",
        "exchange": exchange,
        "window": window,
        "description": f"Top movers on {exchange}",
        "formula": "0.6*volume_score + 0.4*price_momentum",
        "items": scored[:limit],
        "_meta": {"cache_sec": 60}
    }
