"""
Tokenomics Routes
=================
Token economics data: vesting, unlocks, inflation, burns, etc.
Uses DefiLlama as primary source (free, no rate limits) with CoinGecko fallback.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import httpx
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tokenomics", tags=["Tokenomics"])

# Simple in-memory cache
_cache: Dict[str, Any] = {}
_cache_ttl = 300  # 5 minutes


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _get_cache(key: str):
    """Get from cache if not expired"""
    if key in _cache:
        entry = _cache[key]
        if datetime.now(timezone.utc).timestamp() < entry["expires"]:
            return entry["data"]
    return None


def _set_cache(key: str, data: Any):
    """Set cache with TTL"""
    _cache[key] = {
        "data": data,
        "expires": datetime.now(timezone.utc).timestamp() + _cache_ttl
    }


# Asset mappings
ASSET_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "AAVE": "aave",
    "ARB": "arbitrum",
    "OP": "optimism",
}

# DefiLlama coin IDs
DEFILLAMA_IDS = {
    "BTC": "coingecko:bitcoin",
    "ETH": "coingecko:ethereum",
    "SOL": "coingecko:solana",
    "BNB": "coingecko:binancecoin",
    "XRP": "coingecko:ripple",
    "ADA": "coingecko:cardano",
    "AVAX": "coingecko:avalanche-2",
    "DOT": "coingecko:polkadot",
    "MATIC": "coingecko:matic-network",
    "LINK": "coingecko:chainlink",
    "UNI": "coingecko:uniswap",
    "AAVE": "coingecko:aave",
    "ARB": "coingecko:arbitrum",
    "OP": "coingecko:optimism",
}


async def _get_token_unlocks(db, symbol: str):
    """Get token unlocks from database"""
    unlocks = await db.token_unlocks.find(
        {"symbol": symbol.upper()},
        {"_id": 0}
    ).sort("unlock_date", 1).to_list(50)
    return unlocks


async def _fetch_defillama_data(symbol: str):
    """Fetch data from DefiLlama (primary, free)"""
    cache_key = f"defillama:{symbol}"
    cached = _get_cache(cache_key)
    if cached:
        return cached
    
    try:
        llama_id = DEFILLAMA_IDS.get(symbol.upper(), f"coingecko:{symbol.lower()}")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://coins.llama.fi/prices/current/{llama_id}")
            if resp.status_code == 200:
                data = resp.json()
                coin = data.get("coins", {}).get(llama_id, {})
                if coin:
                    result = {
                        "price": coin.get("price", 0),
                        "mcap": coin.get("mcap", 0),
                        "change_24h": coin.get("change24h", 0),
                        "symbol": symbol.upper(),
                        "source": "defillama"
                    }
                    _set_cache(cache_key, result)
                    return result
    except Exception as e:
        logger.warning(f"DefiLlama fetch failed: {e}")
    return None


async def _fetch_coingecko_data(coin_id: str):
    """Fetch comprehensive data from CoinGecko (fallback)"""
    cache_key = f"coingecko:{coin_id}"
    cached = _get_cache(cache_key)
    if cached:
        return cached
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}",
                params={"localization": "false", "tickers": "false"}
            )
            if resp.status_code == 200:
                data = resp.json()
                _set_cache(cache_key, data)
                return data
    except Exception as e:
        logger.warning(f"CoinGecko fetch failed: {e}")
    return None


@router.get("/overview/{symbol}")
async def get_tokenomics_overview(symbol: str):
    """
    Get comprehensive tokenomics overview for asset.
    Includes supply, distribution, vesting, inflation metrics.
    """
    from server import db
    
    coin_id = ASSET_IDS.get(symbol.upper(), symbol.lower())
    unlocks = await _get_token_unlocks(db, symbol)
    
    # Try DefiLlama first (no rate limits)
    llama_data = await _fetch_defillama_data(symbol)
    cg_data = await _fetch_coingecko_data(coin_id)
    
    if not llama_data and not cg_data:
        return {
            "ts": ts_now(),
            "symbol": symbol.upper(),
            "error": "Token data not found",
            "source": "unavailable"
        }
    
    # Build response from available data
    if cg_data:
        market_data = cg_data.get("market_data", {})
        circulating = market_data.get("circulating_supply", 0)
        total = market_data.get("total_supply", 0)
        max_supply = market_data.get("max_supply")
        market_cap = market_data.get("market_cap", {}).get("usd")
        fdv = market_data.get("fully_diluted_valuation", {}).get("usd")
        name = cg_data.get("name", symbol.upper())
        source = "coingecko"
    else:
        # Use DefiLlama data
        circulating = 0
        total = 0
        max_supply = None
        market_cap = llama_data.get("mcap", 0)
        fdv = None
        name = symbol.upper()
        source = "defillama"
    
    # Calculate metrics
    circulating_ratio = circulating / total if total else None
    
    # Known inflation rates
    inflation_rates = {
        "BTC": 1.8,
        "ETH": -0.5,
        "SOL": 8.0,
        "BNB": -2.0,
        "ADA": 5.0,
        "DOT": 10.0,
    }
    inflation_rate = inflation_rates.get(symbol.upper())
    
    if inflation_rate is None and total and circulating:
        remaining_pct = (total - circulating) / total * 100 if total else 0
        inflation_rate = remaining_pct / 4  # Assume 4-year emission
    
    return {
        "ts": ts_now(),
        "symbol": symbol.upper(),
        "name": name,
        "price": llama_data.get("price") if llama_data else market_data.get("current_price", {}).get("usd") if cg_data else None,
        "change_24h": llama_data.get("change_24h") if llama_data else None,
        "supply": {
            "circulating": circulating,
            "total": total,
            "max": max_supply,
            "circulating_ratio": circulating_ratio
        },
        "inflation": {
            "estimated_annual_rate": inflation_rate,
            "is_deflationary": inflation_rate < 0 if inflation_rate else None
        },
        "upcoming_unlocks": len(unlocks),
        "market_cap": market_cap,
        "fdv": fdv,
        "mcap_fdv_ratio": (market_cap / fdv) if market_cap and fdv else None,
        "source": source
    }


@router.get("/vesting-pressure/{symbol}")
async def get_vesting_pressure(symbol: str):
    """
    Get vesting/unlock pressure score.
    High score = significant upcoming unlocks relative to circulating supply.
    """
    from server import db
    
    unlocks = await _get_token_unlocks(db, symbol)
    llama_data = await _fetch_defillama_data(symbol)
    
    coin_id = ASSET_IDS.get(symbol.upper(), symbol.lower())
    cg_data = await _fetch_coingecko_data(coin_id)
    
    if not llama_data and not cg_data:
        # Return with database unlocks only
        return {
            "ts": ts_now(),
            "symbol": symbol.upper(),
            "pressure_score": 5 if unlocks else 1,
            "pressure_level": "moderate" if unlocks else "minimal",
            "upcoming_unlocks_count": len(unlocks),
            "source": "db_only"
        }
    
    # Get market data from available source
    if cg_data:
        market_data = cg_data.get("market_data", {})
        circulating = market_data.get("circulating_supply", 0)
        price = market_data.get("current_price", {}).get("usd", 0)
        market_cap = market_data.get("market_cap", {}).get("usd", 0)
    else:
        # Use llama data if CG data not available
        circulating = 0  # Not available from llama
        price = llama_data.get("price", 0)
        market_cap = llama_data.get("mcap", 0)
    
    # Calculate 30-day unlock pressure
    now = datetime.now(timezone.utc)
    thirty_days = now + timedelta(days=30)
    
    upcoming_unlock_value = 0
    for unlock in unlocks:
        try:
            unlock_date = datetime.fromisoformat(unlock.get("unlock_date", "").replace("Z", "+00:00"))
            if now <= unlock_date <= thirty_days:
                tokens = unlock.get("tokens_unlocked", 0)
                upcoming_unlock_value += tokens * price
        except:
            pass
    
    market_cap = circulating * price if circulating and price else 0
    pressure_pct = (upcoming_unlock_value / market_cap * 100) if market_cap > 0 else 0
    
    # Score: 0-10
    if pressure_pct > 10:
        score = 10
        level = "extreme"
    elif pressure_pct > 5:
        score = 8
        level = "high"
    elif pressure_pct > 2:
        score = 5
        level = "moderate"
    elif pressure_pct > 0.5:
        score = 3
        level = "low"
    else:
        score = 1
        level = "minimal"
    
    return {
        "ts": ts_now(),
        "symbol": symbol.upper(),
        "pressure_score": score,
        "pressure_level": level,
        "upcoming_unlock_value_30d": upcoming_unlock_value,
        "unlock_pct_of_mcap": round(pressure_pct, 2),
        "upcoming_unlocks_count": len([u for u in unlocks if u]),
        "source": "coingecko+db"
    }


@router.get("/insider-supply/{symbol}")
async def get_insider_supply(symbol: str):
    """
    Get insider/team/VC supply metrics.
    High insider supply = potential sell pressure.
    """
    coin_id = ASSET_IDS.get(symbol.upper(), symbol.lower())
    cg_data = await _fetch_coingecko_data(coin_id)
    
    if not cg_data:
        return {
            "ts": ts_now(),
            "symbol": symbol.upper(),
            "insider_pct": None,
            "source": "unavailable"
        }
    
    market_data = cg_data.get("market_data", {})
    circulating = market_data.get("circulating_supply", 0)
    total = market_data.get("total_supply", 0)
    
    # Estimate insider supply from circulating ratio
    locked_pct = ((total - circulating) / total * 100) if total > 0 else 0
    
    # For mature assets like BTC/ETH, most is "public"
    if symbol.upper() in ["BTC", "ETH"]:
        insider_pct = 5  # Minimal founders/early investors
    else:
        insider_pct = min(locked_pct, 40)  # Cap at 40%
    
    return {
        "ts": ts_now(),
        "symbol": symbol.upper(),
        "estimated_insider_pct": round(insider_pct, 1),
        "locked_supply_pct": round(locked_pct, 1),
        "circulating_supply": circulating,
        "total_supply": total,
        "risk_level": "high" if insider_pct > 30 else "moderate" if insider_pct > 15 else "low",
        "source": "coingecko+estimated"
    }


@router.get("/sell-pressure-score/{symbol}")
async def get_sell_pressure_score(symbol: str):
    """
    Composite sell pressure score (0-100).
    Combines: unlocks, insider supply, exchange inflows.
    """
    from server import db
    
    coin_id = ASSET_IDS.get(symbol.upper(), symbol.lower())
    cg_data = await _fetch_coingecko_data(coin_id)
    unlocks = await _get_token_unlocks(db, symbol)
    
    if not cg_data:
        return {
            "ts": ts_now(),
            "symbol": symbol.upper(),
            "sell_pressure_score": None,
            "source": "unavailable"
        }
    
    market_data = cg_data.get("market_data", {})
    
    # Factor 1: Circulating ratio (lower = more potential sells)
    circulating = market_data.get("circulating_supply", 0)
    total = market_data.get("total_supply", 0)
    circ_ratio = circulating / total if total else 1
    circ_score = (1 - circ_ratio) * 40  # Max 40 points
    
    # Factor 2: Upcoming unlocks
    unlock_count = len(unlocks)
    unlock_score = min(unlock_count * 2, 30)  # Max 30 points
    
    # Factor 3: Price vs ATH (near ATH = more selling)
    ath = market_data.get("ath", {}).get("usd", 0)
    current = market_data.get("current_price", {}).get("usd", 0)
    ath_ratio = current / ath if ath else 0
    ath_score = ath_ratio * 30  # Max 30 points
    
    total_score = circ_score + unlock_score + ath_score
    
    return {
        "ts": ts_now(),
        "symbol": symbol.upper(),
        "sell_pressure_score": round(total_score, 1),
        "components": {
            "locked_supply_pressure": round(circ_score, 1),
            "unlock_pressure": round(unlock_score, 1),
            "ath_proximity_pressure": round(ath_score, 1)
        },
        "risk_level": "high" if total_score > 60 else "moderate" if total_score > 30 else "low",
        "source": "coingecko+db"
    }


@router.get("/decentralization-score/{symbol}")
async def get_decentralization_score(symbol: str):
    """
    Token decentralization score (0-100).
    Based on holder distribution, governance, supply concentration.
    """
    coin_id = ASSET_IDS.get(symbol.upper(), symbol.lower())
    cg_data = await _fetch_coingecko_data(coin_id)
    
    if not cg_data:
        return {
            "ts": ts_now(),
            "symbol": symbol.upper(),
            "decentralization_score": None,
            "source": "unavailable"
        }
    
    # Score components
    scores = {}
    
    # Age bonus (older = more decentralized typically)
    genesis = cg_data.get("genesis_date")
    if genesis:
        try:
            age_years = (datetime.now() - datetime.fromisoformat(genesis)).days / 365
            scores["age"] = min(age_years * 5, 25)  # Max 25 points
        except:
            scores["age"] = 10
    else:
        scores["age"] = 10
    
    # Circulating ratio (higher = more decentralized)
    market_data = cg_data.get("market_data", {})
    circulating = market_data.get("circulating_supply", 0)
    total = market_data.get("total_supply", 0)
    circ_ratio = circulating / total if total else 0.5
    scores["circulation"] = circ_ratio * 35  # Max 35 points
    
    # Community size (approximate from sentiment)
    community = cg_data.get("community_data", {})
    twitter = community.get("twitter_followers", 0)
    scores["community"] = min(twitter / 100000 * 20, 20)  # Max 20 points
    
    # Known decentralization bonuses
    if symbol.upper() == "BTC":
        scores["known_bonus"] = 20
    elif symbol.upper() == "ETH":
        scores["known_bonus"] = 15
    else:
        scores["known_bonus"] = 0
    
    total_score = sum(scores.values())
    
    return {
        "ts": ts_now(),
        "symbol": symbol.upper(),
        "decentralization_score": round(min(total_score, 100), 1),
        "components": scores,
        "grade": "A" if total_score > 80 else "B" if total_score > 60 else "C" if total_score > 40 else "D",
        "source": "coingecko+estimated"
    }


@router.get("/inflation/{symbol}")
async def get_inflation_rate(symbol: str):
    """
    Get token inflation/deflation rate.
    """
    coin_id = ASSET_IDS.get(symbol.upper(), symbol.lower())
    cg_data = await _fetch_coingecko_data(coin_id)
    
    if not cg_data:
        return {
            "ts": ts_now(),
            "symbol": symbol.upper(),
            "inflation_rate": None,
            "source": "unavailable"
        }
    
    market_data = cg_data.get("market_data", {})
    
    # Known inflation rates
    known_rates = {
        "BTC": 1.8,
        "ETH": -0.5,  # Post-merge deflationary
        "SOL": 8.0,
        "BNB": -2.0,  # Burns
        "ADA": 5.0,
        "DOT": 10.0,
        "AVAX": 5.0,
    }
    
    inflation = known_rates.get(symbol.upper())
    
    if inflation is None:
        # Estimate from supply data
        circulating = market_data.get("circulating_supply", 0)
        total = market_data.get("total_supply", 0)
        if total and circulating:
            remaining_pct = (total - circulating) / total * 100
            inflation = remaining_pct / 4  # Assume 4-year emission
    
    return {
        "ts": ts_now(),
        "symbol": symbol.upper(),
        "annual_inflation_rate": inflation,
        "is_deflationary": inflation < 0 if inflation else None,
        "supply_data": {
            "circulating": market_data.get("circulating_supply"),
            "total": market_data.get("total_supply"),
            "max": market_data.get("max_supply")
        },
        "source": "known_data" if symbol.upper() in known_rates else "estimated"
    }


@router.get("/burns/{symbol}")
async def get_burn_data(symbol: str):
    """
    Get token burn data (if applicable).
    """
    coin_id = ASSET_IDS.get(symbol.upper(), symbol.lower())
    cg_data = await _fetch_coingecko_data(coin_id)
    
    # Known burn mechanisms
    burn_tokens = {
        "BNB": {"has_burns": True, "frequency": "quarterly", "mechanism": "auto-burn"},
        "ETH": {"has_burns": True, "frequency": "per-block", "mechanism": "EIP-1559 base fee burn"},
        "SHIB": {"has_burns": True, "frequency": "variable", "mechanism": "community burns"},
    }
    
    burn_info = burn_tokens.get(symbol.upper(), {"has_burns": False})
    
    return {
        "ts": ts_now(),
        "symbol": symbol.upper(),
        **burn_info,
        "total_burned": None,  # Would need specific API
        "burn_rate_24h": None,
        "source": "known_data" if symbol.upper() in burn_tokens else "unavailable"
    }


@router.get("/unlock-impact/{symbol}")
async def get_unlock_impact(symbol: str):
    """
    Analyze impact of upcoming unlocks on price.
    """
    from server import db
    
    coin_id = ASSET_IDS.get(symbol.upper(), symbol.lower())
    cg_data = await _fetch_coingecko_data(coin_id)
    unlocks = await _get_token_unlocks(db, symbol)
    
    if not cg_data:
        return {
            "ts": ts_now(),
            "symbol": symbol.upper(),
            "impact_score": None,
            "source": "unavailable"
        }
    
    market_data = cg_data.get("market_data", {})
    price = market_data.get("current_price", {}).get("usd", 0)
    market_cap = market_data.get("market_cap", {}).get("usd", 0)
    volume_24h = market_data.get("total_volume", {}).get("usd", 0)
    
    # Calculate unlock impact
    now = datetime.now(timezone.utc)
    impacts = []
    
    for unlock in unlocks[:5]:  # Next 5 unlocks
        try:
            tokens = unlock.get("tokens_unlocked", 0)
            value = tokens * price
            
            # Impact relative to daily volume
            volume_impact = value / volume_24h if volume_24h else 0
            
            impacts.append({
                "date": unlock.get("unlock_date"),
                "tokens": tokens,
                "value_usd": value,
                "volume_days_equiv": round(volume_impact, 2),
                "impact_level": "high" if volume_impact > 1 else "moderate" if volume_impact > 0.3 else "low"
            })
        except:
            pass
    
    return {
        "ts": ts_now(),
        "symbol": symbol.upper(),
        "current_price": price,
        "daily_volume": volume_24h,
        "upcoming_unlocks": impacts,
        "source": "coingecko+db"
    }


@router.get("/unlock-calendar/{symbol}")
async def get_unlock_calendar(
    symbol: str,
    days: int = Query(90, description="Days to look ahead")
):
    """
    Get unlock calendar for next N days.
    """
    from server import db
    
    unlocks = await _get_token_unlocks(db, symbol)
    
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=days)
    
    calendar = []
    for unlock in unlocks:
        try:
            unlock_date = datetime.fromisoformat(unlock.get("unlock_date", "").replace("Z", "+00:00"))
            if now <= unlock_date <= end_date:
                calendar.append({
                    "date": unlock.get("unlock_date"),
                    "tokens": unlock.get("tokens_unlocked"),
                    "category": unlock.get("category", "team"),
                    "cliff_or_linear": unlock.get("unlock_type", "cliff")
                })
        except:
            pass
    
    return {
        "ts": ts_now(),
        "symbol": symbol.upper(),
        "period_days": days,
        "total_unlocks": len(calendar),
        "calendar": calendar,
        "source": "db"
    }
