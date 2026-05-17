"""
FOMO Market Indices API
=======================
Market indices and dominance calculations.

Endpoints:
- /api/indices/dominance/btc - BTC dominance
- /api/indices/dominance/stables - Stablecoin dominance (USDT + USDC)
- /api/indices/dominance/alts-clean - Alt dominance (excluding BTC + stables)
- /api/indices/overview - Full market overview
- /api/indices/fear-greed - Fear & Greed index
"""

from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime, timezone
import aiohttp

router = APIRouter(prefix="/api/indices", tags=["Market Indices"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


async def get_global_data():
    """Fetch global market data from CoinGecko"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.coingecko.com/api/v3/global",
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", {})
    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════
# BTC DOMINANCE
# ═══════════════════════════════════════════════════════════════

@router.get("/dominance/btc")
async def get_btc_dominance():
    """
    BTC market dominance.
    """
    market = await get_global_data()
    
    btc_dom = market.get("market_cap_percentage", {}).get("btc", 0)
    
    # Trend interpretation
    trend = "neutral"
    if btc_dom > 55:
        trend = "btc_season"
    elif btc_dom < 45:
        trend = "alt_season"
    
    return {
        "ts": ts_now(),
        "btc_dominance": round(btc_dom, 2),
        "btc_market_cap": market.get("total_market_cap", {}).get("btc"),
        "total_market_cap": market.get("total_market_cap", {}).get("usd"),
        "trend": trend,
        "_meta": {"cache_sec": 60}
    }


# ═══════════════════════════════════════════════════════════════
# STABLECOIN DOMINANCE
# ═══════════════════════════════════════════════════════════════

@router.get("/dominance/stables")
async def get_stable_dominance(
    symbols: str = Query("USDT,USDC", description="Stablecoin symbols")
):
    """
    Stablecoin dominance (USDT + USDC by default).
    
    High stable dominance = "cash on sidelines"
    Low stable dominance = "risk on"
    """
    market = await get_global_data()
    
    stable_symbols = [s.strip().lower() for s in symbols.split(",")]
    
    total_mcap = market.get("total_market_cap", {}).get("usd", 0)
    
    stable_dom = 0
    stable_mcaps = {}
    
    # Get individual stablecoin market caps
    try:
        async with aiohttp.ClientSession() as session:
            for sym in stable_symbols:
                try:
                    async with session.get(
                        f"https://api.coingecko.com/api/v3/coins/{sym}",
                        timeout=5
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            mcap = data.get("market_data", {}).get("market_cap", {}).get("usd", 0)
                            stable_mcaps[sym.upper()] = mcap
                except:
                    pass
    except:
        pass
    
    total_stable_mcap = sum(stable_mcaps.values())
    
    if total_mcap > 0:
        stable_dom = total_stable_mcap / total_mcap * 100
    
    # Interpretation
    sentiment = "neutral"
    if stable_dom > 8:
        sentiment = "risk_off"
    elif stable_dom < 4:
        sentiment = "risk_on"
    
    return {
        "ts": ts_now(),
        "stable_dominance": round(stable_dom, 2),
        "total_stable_mcap": total_stable_mcap,
        "breakdown": stable_mcaps,
        "sentiment": sentiment,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# ALT DOMINANCE (Clean - excluding BTC and stables)
# ═══════════════════════════════════════════════════════════════

@router.get("/dominance/alts-clean")
async def get_alt_dominance(
    exclude: str = Query("BTC,USDT,USDC", description="Symbols to exclude")
):
    """
    Clean alt dominance = Total - BTC - Stables.
    
    This shows "real alt season" without stablecoin distortion.
    """
    market = await get_global_data()
    
    total_mcap = market.get("total_market_cap", {}).get("usd", 0)
    btc_dom = market.get("market_cap_percentage", {}).get("btc", 0)
    
    btc_mcap = total_mcap * btc_dom / 100 if total_mcap else 0
    
    # Get stablecoin mcap
    stable_data = await get_stable_dominance("USDT,USDC")
    stable_mcap = stable_data.get("total_stable_mcap", 0)
    
    # Calculate clean alt mcap
    alt_mcap = total_mcap - btc_mcap - stable_mcap
    alt_dom = alt_mcap / total_mcap * 100 if total_mcap > 0 else 0
    
    # Season detection
    season = "neutral"
    if alt_dom > 42:
        season = "alt_season"
    elif alt_dom < 35:
        season = "btc_season"
    
    return {
        "ts": ts_now(),
        "alt_dominance": round(alt_dom, 2),
        "alt_market_cap": alt_mcap,
        "btc_market_cap": btc_mcap,
        "stable_market_cap": stable_mcap,
        "total_market_cap": total_mcap,
        "season": season,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# FULL OVERVIEW
# ═══════════════════════════════════════════════════════════════

@router.get("/overview")
async def get_indices_overview():
    """
    Full market indices overview.
    
    Combines all dominance metrics + Fear & Greed.
    """
    market = await get_global_data()
    
    overview = {
        "ts": ts_now(),
        "total_market_cap": market.get("total_market_cap", {}).get("usd"),
        "total_volume_24h": market.get("total_volume", {}).get("usd"),
        "market_cap_change_24h": market.get("market_cap_change_percentage_24h_usd"),
        "active_cryptocurrencies": market.get("active_cryptocurrencies"),
        "markets": market.get("markets"),
        "dominance": {
            "btc": round(market.get("market_cap_percentage", {}).get("btc", 0), 2),
            "eth": round(market.get("market_cap_percentage", {}).get("eth", 0), 2)
        },
        "fear_greed": None,
        "fear_greed_label": None
    }
    
    # Fear & Greed
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.alternative.me/fng/",
                timeout=5
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    fg_data = data.get("data", [{}])[0]
                    overview["fear_greed"] = int(fg_data.get("value", 50))
                    overview["fear_greed_label"] = fg_data.get("value_classification")
    except:
        pass
    
    overview["_meta"] = {"cache_sec": 60}
    return overview


# ═══════════════════════════════════════════════════════════════
# FEAR & GREED
# ═══════════════════════════════════════════════════════════════

@router.get("/fear-greed")
async def get_fear_greed():
    """
    Fear & Greed Index.
    
    0-24: Extreme Fear
    25-49: Fear
    50-74: Greed
    75-100: Extreme Greed
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.alternative.me/fng/?limit=7",
                timeout=5
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    fg_list = data.get("data", [])
                    
                    current = fg_list[0] if fg_list else {}
                    
                    return {
                        "ts": ts_now(),
                        "value": int(current.get("value", 50)),
                        "label": current.get("value_classification"),
                        "timestamp": current.get("timestamp"),
                        "history": [
                            {
                                "value": int(item.get("value", 50)),
                                "label": item.get("value_classification"),
                                "date": item.get("timestamp")
                            }
                            for item in fg_list
                        ],
                        "_meta": {"cache_sec": 3600}
                    }
    except:
        pass
    
    return {
        "ts": ts_now(),
        "value": 50,
        "label": "Neutral",
        "_meta": {"cache_sec": 3600, "error": "Could not fetch data"}
    }
