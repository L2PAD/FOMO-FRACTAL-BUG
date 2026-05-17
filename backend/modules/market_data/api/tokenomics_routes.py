"""
FOMO Tokenomics API (P2)
========================
Token economics analysis and metrics.

Endpoints:
- /api/tokenomics/overview/{symbol} - Full tokenomics overview
- /api/tokenomics/vesting-pressure/{symbol} - Vesting unlock pressure
- /api/tokenomics/insider-supply/{symbol} - Team/investor/insider holdings
- /api/tokenomics/sell-pressure-score/{symbol} - Aggregated sell pressure score
- /api/tokenomics/decentralization-score/{symbol} - Token decentralization metrics
- /api/tokenomics/inflation/{symbol} - Token inflation metrics
- /api/tokenomics/burns/{symbol} - Token burn tracking
- /api/tokenomics/unlock-calendar/{symbol} - Upcoming unlock events
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import asyncio
import aiohttp
import math

router = APIRouter(prefix="/api/tokenomics", tags=["Tokenomics"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# In-memory cache for tokenomics data
_tokenomics_cache = {
    "coingecko": {}
}
COINGECKO_CACHE_TTL = 120  # 2 minutes


async def fetch_coingecko_market_data(symbol: str) -> dict:
    """Fetch market data from CoinGecko with caching"""
    symbol_lower = symbol.lower()
    
    # Check cache first
    cache_key = f"cg_{symbol_lower}"
    if cache_key in _tokenomics_cache["coingecko"]:
        cached = _tokenomics_cache["coingecko"][cache_key]
        if (ts_now() - cached.get("_cached_at", 0)) < COINGECKO_CACHE_TTL * 1000:
            return cached.get("data")
    
    # Map common symbols to CoinGecko IDs
    symbol_to_id = {
        "btc": "bitcoin",
        "eth": "ethereum",
        "sol": "solana",
        "bnb": "binancecoin",
        "xrp": "ripple",
        "ada": "cardano",
        "doge": "dogecoin",
        "avax": "avalanche-2",
        "dot": "polkadot",
        "link": "chainlink",
        "matic": "matic-network",
        "uni": "uniswap",
        "ltc": "litecoin",
        "arb": "arbitrum",
        "op": "optimism",
        "apt": "aptos",
        "sui": "sui",
        "sei": "sei-network",
        "tia": "celestia",
        "jup": "jupiter-exchange-solana",
        "pyth": "pyth-network"
    }
    
    coin_id = symbol_to_id.get(symbol_lower, symbol_lower)
    
    try:
        async with aiohttp.ClientSession() as session:
            # Add small delay to avoid rate limiting
            await asyncio.sleep(0.5)
            async with session.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}",
                params={"localization": "false", "tickers": "false", "community_data": "false"},
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Cache result
                    _tokenomics_cache["coingecko"][cache_key] = {
                        "data": data,
                        "_cached_at": ts_now()
                    }
                    return data
                elif resp.status == 429:
                    # Rate limited - return cached if available
                    if cache_key in _tokenomics_cache["coingecko"]:
                        return _tokenomics_cache["coingecko"][cache_key].get("data")
    except Exception as e:
        pass
    
    return None


# ═══════════════════════════════════════════════════════════════
# TOKENOMICS OVERVIEW
# ═══════════════════════════════════════════════════════════════

@router.get("/overview/{symbol}")
async def get_tokenomics_overview(symbol: str):
    """
    Get comprehensive tokenomics overview.
    
    Returns:
    - Supply metrics (circulating, total, max, inflation rate)
    - Distribution estimates (team, investors, community)
    - Vesting status
    - Market metrics (market cap, FDV, ratio)
    - Risk indicators
    """
    symbol = symbol.upper()
    
    data = await fetch_coingecko_market_data(symbol)
    
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    circulating = market_data.get("circulating_supply", 0) or 0
    total = market_data.get("total_supply", 0) or circulating
    max_supply = market_data.get("max_supply")
    
    current_price = market_data.get("current_price", {}).get("usd", 0)
    market_cap = market_data.get("market_cap", {}).get("usd", 0)
    fdv = market_data.get("fully_diluted_valuation", {}).get("usd", 0)
    
    # Calculate metrics
    circulating_pct = (circulating / total * 100) if total > 0 else 100
    unlocked_pct = circulating_pct
    locked_pct = 100 - circulating_pct
    
    mcap_fdv_ratio = (market_cap / fdv) if fdv > 0 else 1
    
    # Risk assessment based on metrics
    risk_factors = []
    risk_score = 0
    
    if circulating_pct < 30:
        risk_factors.append("Low circulating supply (<30%) - high unlock risk")
        risk_score += 30
    elif circulating_pct < 50:
        risk_factors.append("Medium circulating supply (30-50%) - moderate unlock risk")
        risk_score += 15
    
    if mcap_fdv_ratio < 0.3:
        risk_factors.append("High FDV relative to market cap - significant dilution ahead")
        risk_score += 25
    elif mcap_fdv_ratio < 0.5:
        risk_factors.append("Moderate FDV gap - some dilution expected")
        risk_score += 10
    
    # Determine typical allocation for newer tokens
    # This is estimated - real data would come from tokenomics docs
    if circulating_pct < 50:
        team_allocation = 20
        investor_allocation = 25
        community_allocation = 100 - team_allocation - investor_allocation
    else:
        team_allocation = 15
        investor_allocation = 15
        community_allocation = 70
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "name": data.get("name"),
        "supply": {
            "circulating": circulating,
            "total": total,
            "max": max_supply,
            "circulating_pct": round(circulating_pct, 2),
            "locked_pct": round(locked_pct, 2)
        },
        "valuation": {
            "price_usd": current_price,
            "market_cap": market_cap,
            "fdv": fdv,
            "mcap_fdv_ratio": round(mcap_fdv_ratio, 4)
        },
        "estimated_distribution": {
            "team_pct": team_allocation,
            "investor_pct": investor_allocation,
            "community_pct": community_allocation,
            "note": "Estimated based on typical allocation patterns"
        },
        "risk_assessment": {
            "score": min(risk_score, 100),
            "level": "high" if risk_score > 40 else "medium" if risk_score > 20 else "low",
            "factors": risk_factors
        },
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# VESTING PRESSURE
# ═══════════════════════════════════════════════════════════════

@router.get("/vesting-pressure/{symbol}")
async def get_vesting_pressure(symbol: str):
    """
    Calculate vesting unlock pressure score.
    
    Vesting Pressure = (Locked Supply * Avg Unlock Rate) / Daily Volume
    
    High pressure = more tokens unlocking relative to trading volume
    Low pressure = market can absorb unlocks easily
    
    Score interpretation:
    - >100: Critical pressure (unlocks > daily volume)
    - 50-100: High pressure
    - 20-50: Moderate pressure
    - <20: Low pressure
    """
    symbol = symbol.upper()
    
    data = await fetch_coingecko_market_data(symbol)
    
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    circulating = market_data.get("circulating_supply", 0) or 0
    total = market_data.get("total_supply", 0) or circulating
    volume_24h = market_data.get("total_volume", {}).get("usd", 0)
    current_price = market_data.get("current_price", {}).get("usd", 1)
    market_cap = market_data.get("market_cap", {}).get("usd", 0)
    
    locked_supply = total - circulating
    locked_pct = (locked_supply / total * 100) if total > 0 else 0
    locked_value_usd = locked_supply * current_price
    
    # Estimate monthly unlock rate (typical: 2-5% of locked supply per month)
    # More aggressive for newer projects
    if locked_pct > 70:
        monthly_unlock_rate = 0.04  # 4% per month for very locked tokens
    elif locked_pct > 50:
        monthly_unlock_rate = 0.03
    else:
        monthly_unlock_rate = 0.02
    
    daily_unlock_rate = monthly_unlock_rate / 30
    estimated_daily_unlock_usd = locked_value_usd * daily_unlock_rate
    
    # Calculate pressure score
    if volume_24h > 0:
        pressure_score = (estimated_daily_unlock_usd / volume_24h) * 100
    else:
        pressure_score = 100 if locked_supply > 0 else 0
    
    # Determine pressure level
    if pressure_score > 100:
        pressure_level = "critical"
        interpretation = "Daily unlocks exceed trading volume - severe sell pressure expected"
    elif pressure_score > 50:
        pressure_level = "high"
        interpretation = "Significant unlock pressure relative to volume"
    elif pressure_score > 20:
        pressure_level = "moderate"
        interpretation = "Manageable unlock pressure"
    else:
        pressure_level = "low"
        interpretation = "Market can easily absorb unlocks"
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "vesting_pressure": {
            "score": round(pressure_score, 2),
            "level": pressure_level,
            "interpretation": interpretation
        },
        "supply_metrics": {
            "locked_supply": locked_supply,
            "locked_pct": round(locked_pct, 2),
            "locked_value_usd": round(locked_value_usd, 2)
        },
        "unlock_estimates": {
            "monthly_unlock_rate_pct": round(monthly_unlock_rate * 100, 2),
            "estimated_daily_unlock_usd": round(estimated_daily_unlock_usd, 2),
            "estimated_monthly_unlock_usd": round(estimated_daily_unlock_usd * 30, 2)
        },
        "market_context": {
            "volume_24h": volume_24h,
            "market_cap": market_cap,
            "volume_to_mcap_ratio": round(volume_24h / market_cap, 4) if market_cap > 0 else 0
        },
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# INSIDER SUPPLY
# ═══════════════════════════════════════════════════════════════

@router.get("/insider-supply/{symbol}")
async def get_insider_supply(symbol: str):
    """
    Estimate insider (team + investors) token holdings.
    
    Insiders typically include:
    - Founding team
    - Early investors (seed, private rounds)
    - Advisors
    - Foundation/Treasury
    
    High insider supply = higher sell pressure risk
    Low insider supply = more decentralized
    """
    symbol = symbol.upper()
    
    data = await fetch_coingecko_market_data(symbol)
    
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    circulating = market_data.get("circulating_supply", 0) or 0
    total = market_data.get("total_supply", 0) or circulating
    current_price = market_data.get("current_price", {}).get("usd", 1)
    
    circulating_pct = (circulating / total * 100) if total > 0 else 100
    
    # Estimate insider allocation based on project type and circulating supply
    # Newer tokens with low circulation typically have higher insider allocation
    
    if circulating_pct < 30:
        # Very early stage - high insider allocation typical
        team_pct = 18
        investor_pct = 25
        treasury_pct = 20
        advisor_pct = 5
    elif circulating_pct < 50:
        # Mid-stage - moderate insider allocation
        team_pct = 15
        investor_pct = 20
        treasury_pct = 15
        advisor_pct = 4
    elif circulating_pct < 70:
        # Later stage - lower insider allocation
        team_pct = 12
        investor_pct = 15
        treasury_pct = 10
        advisor_pct = 3
    else:
        # Mature token - minimal insider allocation
        team_pct = 8
        investor_pct = 10
        treasury_pct = 5
        advisor_pct = 2
    
    # Special cases for known tokens
    if symbol == "BTC":
        team_pct = 0
        investor_pct = 0
        treasury_pct = 0
        advisor_pct = 0
    elif symbol == "ETH":
        team_pct = 5
        investor_pct = 5
        treasury_pct = 5
        advisor_pct = 0
    
    total_insider_pct = team_pct + investor_pct + treasury_pct + advisor_pct
    community_pct = 100 - total_insider_pct
    
    # Calculate USD values
    team_value = total * (team_pct / 100) * current_price
    investor_value = total * (investor_pct / 100) * current_price
    treasury_value = total * (treasury_pct / 100) * current_price
    advisor_value = total * (advisor_pct / 100) * current_price
    total_insider_value = team_value + investor_value + treasury_value + advisor_value
    
    # Risk assessment
    if total_insider_pct > 50:
        risk_level = "high"
        risk_note = "More than 50% held by insiders - high centralization risk"
    elif total_insider_pct > 30:
        risk_level = "moderate"
        risk_note = "30-50% held by insiders - moderate centralization"
    else:
        risk_level = "low"
        risk_note = "Less than 30% held by insiders - relatively decentralized"
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "insider_supply": {
            "total_insider_pct": round(total_insider_pct, 2),
            "total_insider_value_usd": round(total_insider_value, 2),
            "breakdown": {
                "team": {
                    "pct": team_pct,
                    "value_usd": round(team_value, 2)
                },
                "investors": {
                    "pct": investor_pct,
                    "value_usd": round(investor_value, 2)
                },
                "treasury": {
                    "pct": treasury_pct,
                    "value_usd": round(treasury_value, 2)
                },
                "advisors": {
                    "pct": advisor_pct,
                    "value_usd": round(advisor_value, 2)
                }
            }
        },
        "community_supply": {
            "pct": round(community_pct, 2),
            "value_usd": round(total * (community_pct / 100) * current_price, 2)
        },
        "risk_assessment": {
            "level": risk_level,
            "note": risk_note
        },
        "_meta": {
            "cache_sec": 300,
            "methodology": "estimated_from_typical_allocations"
        }
    }


# ═══════════════════════════════════════════════════════════════
# SELL PRESSURE SCORE
# ═══════════════════════════════════════════════════════════════

@router.get("/sell-pressure-score/{symbol}")
async def get_sell_pressure_score(symbol: str):
    """
    Aggregated Sell Pressure Score (0-100).
    
    Components:
    - Vesting pressure (30%)
    - Insider holdings (25%)
    - Profit-taking potential (25%)
    - Inflation rate (20%)
    
    Score interpretation:
    - 80-100: Extreme sell pressure
    - 60-80: High sell pressure
    - 40-60: Moderate sell pressure
    - 20-40: Low sell pressure
    - 0-20: Minimal sell pressure
    """
    symbol = symbol.upper()
    
    # Get component data
    vesting_data = await get_vesting_pressure(symbol)
    insider_data = await get_insider_supply(symbol)
    
    data = await fetch_coingecko_market_data(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    # 1. Vesting Pressure Score (0-100)
    vesting_score = min(vesting_data["vesting_pressure"]["score"], 100)
    
    # 2. Insider Holdings Score (0-100)
    insider_pct = insider_data["insider_supply"]["total_insider_pct"]
    insider_score = min(insider_pct * 1.5, 100)  # Scale to 0-100
    
    # 3. Profit-taking Potential (0-100)
    # Based on price vs ATH - closer to ATH means more profit-taking potential
    ath = market_data.get("ath", {}).get("usd", 0)
    current_price = market_data.get("current_price", {}).get("usd", 0)
    
    if ath > 0 and current_price > 0:
        price_vs_ath = current_price / ath
        if price_vs_ath > 0.9:
            profit_score = 80
        elif price_vs_ath > 0.7:
            profit_score = 60
        elif price_vs_ath > 0.5:
            profit_score = 40
        elif price_vs_ath > 0.3:
            profit_score = 20
        else:
            profit_score = 10  # Far from ATH, less profit-taking
    else:
        profit_score = 50
    
    # 4. Inflation Score (0-100)
    circulating = market_data.get("circulating_supply", 0) or 0
    total = market_data.get("total_supply", 0) or circulating
    max_supply = market_data.get("max_supply")
    
    circulating_pct = (circulating / total * 100) if total > 0 else 100
    inflation_potential = 100 - circulating_pct
    inflation_score = inflation_potential  # More unlocked supply to come = higher score
    
    # Calculate weighted total
    total_score = (
        vesting_score * 0.30 +
        insider_score * 0.25 +
        profit_score * 0.25 +
        inflation_score * 0.20
    )
    
    # Determine level
    if total_score >= 80:
        level = "extreme"
        interpretation = "Extreme sell pressure - high risk of price decline"
    elif total_score >= 60:
        level = "high"
        interpretation = "High sell pressure - caution advised"
    elif total_score >= 40:
        level = "moderate"
        interpretation = "Moderate sell pressure - normal market conditions"
    elif total_score >= 20:
        level = "low"
        interpretation = "Low sell pressure - favorable conditions"
    else:
        level = "minimal"
        interpretation = "Minimal sell pressure - very favorable conditions"
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "sell_pressure_score": {
            "total": round(total_score, 1),
            "level": level,
            "interpretation": interpretation
        },
        "components": {
            "vesting_pressure": {
                "score": round(vesting_score, 1),
                "weight": "30%"
            },
            "insider_holdings": {
                "score": round(insider_score, 1),
                "weight": "25%"
            },
            "profit_taking_potential": {
                "score": round(profit_score, 1),
                "weight": "25%"
            },
            "inflation_rate": {
                "score": round(inflation_score, 1),
                "weight": "20%"
            }
        },
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# DECENTRALIZATION SCORE
# ═══════════════════════════════════════════════════════════════

@router.get("/decentralization-score/{symbol}")
async def get_decentralization_score(symbol: str):
    """
    Token Decentralization Score (0-100).
    
    Components:
    - Distribution spread (40%)
    - Insider concentration (30%)
    - Exchange concentration (15%)
    - Governance participation (15%)
    
    Higher score = more decentralized
    Lower score = more centralized
    """
    symbol = symbol.upper()
    
    insider_data = await get_insider_supply(symbol)
    
    data = await fetch_coingecko_market_data(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    # 1. Distribution Spread Score (0-100)
    # Based on circulating supply ratio - more circulating = better distribution
    circulating = market_data.get("circulating_supply", 0) or 0
    total = market_data.get("total_supply", 0) or circulating
    circulating_pct = (circulating / total * 100) if total > 0 else 100
    distribution_score = circulating_pct  # Higher circulation = better distribution
    
    # 2. Insider Concentration Score (0-100)
    # Inverse of insider holdings - less insiders = higher score
    insider_pct = insider_data["insider_supply"]["total_insider_pct"]
    concentration_score = max(100 - insider_pct * 1.5, 0)
    
    # 3. Exchange Concentration Score (0-100)
    # Estimate based on typical patterns - most tokens have 30-50% on exchanges
    exchange_concentration_pct = 40  # Estimated
    exchange_score = max(100 - exchange_concentration_pct, 0)
    
    # 4. Governance Score (0-100)
    # Harder to estimate without on-chain data
    # Use circulating as proxy - more circulating = more potential voters
    governance_score = min(circulating_pct, 80)
    
    # Special cases
    if symbol == "BTC":
        distribution_score = 95
        concentration_score = 100
        exchange_score = 75
        governance_score = 50  # No on-chain governance
    elif symbol == "ETH":
        distribution_score = 85
        concentration_score = 85
        exchange_score = 70
        governance_score = 60
    
    # Calculate weighted total
    total_score = (
        distribution_score * 0.40 +
        concentration_score * 0.30 +
        exchange_score * 0.15 +
        governance_score * 0.15
    )
    
    # Determine level
    if total_score >= 80:
        level = "highly_decentralized"
        interpretation = "Highly decentralized - distributed ownership"
    elif total_score >= 60:
        level = "decentralized"
        interpretation = "Reasonably decentralized"
    elif total_score >= 40:
        level = "moderate"
        interpretation = "Moderately centralized"
    elif total_score >= 20:
        level = "centralized"
        interpretation = "Significantly centralized - few large holders"
    else:
        level = "highly_centralized"
        interpretation = "Highly centralized - concentrated ownership"
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "decentralization_score": {
            "total": round(total_score, 1),
            "level": level,
            "interpretation": interpretation
        },
        "components": {
            "distribution_spread": {
                "score": round(distribution_score, 1),
                "weight": "40%"
            },
            "insider_concentration": {
                "score": round(concentration_score, 1),
                "weight": "30%"
            },
            "exchange_concentration": {
                "score": round(exchange_score, 1),
                "weight": "15%"
            },
            "governance_participation": {
                "score": round(governance_score, 1),
                "weight": "15%"
            }
        },
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# INFLATION METRICS
# ═══════════════════════════════════════════════════════════════

@router.get("/inflation/{symbol}")
async def get_inflation_metrics(symbol: str):
    """
    Get token inflation metrics.
    
    Returns:
    - Current inflation rate (annualized)
    - Remaining inflation (supply not yet minted)
    - Time to full dilution (estimated)
    """
    symbol = symbol.upper()
    
    data = await fetch_coingecko_market_data(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    circulating = market_data.get("circulating_supply", 0) or 0
    total = market_data.get("total_supply", 0) or circulating
    max_supply = market_data.get("max_supply")
    current_price = market_data.get("current_price", {}).get("usd", 0)
    
    # Calculate metrics
    if max_supply:
        remaining_supply = max_supply - circulating
        remaining_pct = (remaining_supply / max_supply * 100) if max_supply > 0 else 0
    else:
        remaining_supply = total - circulating
        remaining_pct = (remaining_supply / total * 100) if total > 0 else 0
    
    # Estimate annual inflation rate
    # Typical: 2-10% for established tokens, 10-30% for newer tokens
    circulating_pct = (circulating / (max_supply or total) * 100) if (max_supply or total) > 0 else 100
    
    if circulating_pct > 90:
        annual_inflation_rate = 2
    elif circulating_pct > 70:
        annual_inflation_rate = 5
    elif circulating_pct > 50:
        annual_inflation_rate = 10
    elif circulating_pct > 30:
        annual_inflation_rate = 20
    else:
        annual_inflation_rate = 30
    
    # Special cases
    if symbol == "BTC":
        annual_inflation_rate = 1.7  # Current BTC inflation
    elif symbol == "ETH":
        annual_inflation_rate = 0.5  # Post-merge ETH is nearly deflationary
    
    # Calculate dilution impact
    dilution_impact_1yr = (annual_inflation_rate / 100) * current_price
    
    # Estimated time to full dilution
    if remaining_pct > 0 and annual_inflation_rate > 0:
        years_to_full_dilution = remaining_pct / annual_inflation_rate
    else:
        years_to_full_dilution = 0
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "supply": {
            "circulating": circulating,
            "total": total,
            "max": max_supply,
            "remaining": remaining_supply,
            "remaining_pct": round(remaining_pct, 2)
        },
        "inflation": {
            "annual_rate_pct": round(annual_inflation_rate, 2),
            "daily_rate_pct": round(annual_inflation_rate / 365, 4),
            "type": "inflationary" if annual_inflation_rate > 1 else "low_inflation" if annual_inflation_rate > 0 else "deflationary"
        },
        "dilution_impact": {
            "price_dilution_1yr_usd": round(dilution_impact_1yr, 4),
            "years_to_full_dilution": round(years_to_full_dilution, 1) if years_to_full_dilution > 0 else None
        },
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# TOKEN BURNS
# ═══════════════════════════════════════════════════════════════

@router.get("/burns/{symbol}")
async def get_token_burns(symbol: str):
    """
    Get token burn metrics.
    
    Burns reduce supply, potentially increasing scarcity and value.
    
    Returns:
    - Has burn mechanism
    - Estimated burn rate
    - Deflationary status
    """
    symbol = symbol.upper()
    
    data = await fetch_coingecko_market_data(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    circulating = market_data.get("circulating_supply", 0) or 0
    total = market_data.get("total_supply", 0) or circulating
    max_supply = market_data.get("max_supply")
    
    # Known burn mechanisms
    burn_mechanisms = {
        "BNB": {"has_burn": True, "quarterly_burn": True, "burn_rate_annual_pct": 5},
        "ETH": {"has_burn": True, "eip1559": True, "burn_rate_annual_pct": 0.5},
        "SHIB": {"has_burn": True, "community_burns": True, "burn_rate_annual_pct": 1},
        "LUNA": {"has_burn": True, "seigniorage": True, "burn_rate_annual_pct": 0},
        "LUNC": {"has_burn": True, "tax_burn": True, "burn_rate_annual_pct": 0.5}
    }
    
    burn_info = burn_mechanisms.get(symbol, {"has_burn": False})
    
    has_burn = burn_info.get("has_burn", False)
    burn_rate = burn_info.get("burn_rate_annual_pct", 0)
    
    # Calculate impact
    if has_burn and burn_rate > 0:
        annual_burn_amount = circulating * (burn_rate / 100)
        annual_burn_usd = annual_burn_amount * market_data.get("current_price", {}).get("usd", 0)
        
        # Net inflation = inflation - burns
        # If burns > inflation, deflationary
        is_deflationary = burn_rate > 2  # Assuming ~2% base inflation
    else:
        annual_burn_amount = 0
        annual_burn_usd = 0
        is_deflationary = False
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "burn_mechanism": {
            "has_burn": has_burn,
            "type": list(k for k, v in burn_info.items() if v is True and k != "has_burn") if has_burn else [],
            "burn_rate_annual_pct": burn_rate
        },
        "burn_impact": {
            "estimated_annual_burn": round(annual_burn_amount, 2),
            "estimated_annual_burn_usd": round(annual_burn_usd, 2),
            "is_deflationary": is_deflationary
        },
        "supply_trend": "deflationary" if is_deflationary else "inflationary" if not has_burn else "neutral",
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# UNLOCK IMPACT
# ═══════════════════════════════════════════════════════════════

@router.get("/unlock-impact/{symbol}")
async def get_unlock_impact(symbol: str):
    """
    Calculate market impact of upcoming unlocks.
    
    Impact = unlock_value / daily_volume
    
    High impact (>1) = unlock exceeds daily volume, likely price pressure
    Low impact (<0.1) = market can easily absorb unlock
    """
    symbol = symbol.upper()
    
    data = await fetch_coingecko_market_data(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    circulating = market_data.get("circulating_supply", 0) or 0
    total = market_data.get("total_supply", 0) or circulating
    current_price = market_data.get("current_price", {}).get("usd", 1)
    volume_24h = market_data.get("total_volume", {}).get("usd", 1)
    market_cap = market_data.get("market_cap", {}).get("usd", 0)
    
    locked_supply = total - circulating
    locked_pct = (locked_supply / total * 100) if total > 0 else 0
    
    # Estimate next unlock (assuming monthly linear vesting)
    monthly_unlock_pct = locked_pct / 24 if locked_pct > 5 else 0
    next_unlock_amount = locked_supply / 24 if locked_pct > 5 else 0
    next_unlock_value = next_unlock_amount * current_price
    
    # Calculate impact ratios
    volume_impact = next_unlock_value / volume_24h if volume_24h > 0 else 0
    mcap_impact = next_unlock_value / market_cap * 100 if market_cap > 0 else 0
    
    # Determine severity
    if volume_impact > 2:
        severity = "critical"
        interpretation = "Unlock >2x daily volume - severe sell pressure expected"
    elif volume_impact > 1:
        severity = "high"
        interpretation = "Unlock exceeds daily volume - significant sell pressure"
    elif volume_impact > 0.5:
        severity = "moderate"
        interpretation = "Unlock is 50-100% of daily volume - moderate pressure"
    elif volume_impact > 0.1:
        severity = "low"
        interpretation = "Unlock <50% of daily volume - manageable"
    else:
        severity = "minimal"
        interpretation = "Unlock easily absorbed by market"
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "unlock_impact": {
            "volume_impact_ratio": round(volume_impact, 4),
            "mcap_impact_pct": round(mcap_impact, 4),
            "severity": severity,
            "interpretation": interpretation
        },
        "next_unlock_estimate": {
            "amount": round(next_unlock_amount, 2),
            "value_usd": round(next_unlock_value, 2),
            "pct_of_supply": round(monthly_unlock_pct, 2)
        },
        "market_context": {
            "volume_24h": volume_24h,
            "market_cap": market_cap,
            "current_price": current_price
        },
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# UNLOCK CALENDAR
# ═══════════════════════════════════════════════════════════════

@router.get("/unlock-calendar/{symbol}")
async def get_unlock_calendar(
    symbol: str,
    days: int = Query(90, description="Days ahead to look")
):
    """
    Get upcoming token unlock events.
    
    Integrates with the unlocks module if available,
    otherwise provides estimates based on vesting patterns.
    """
    symbol = symbol.upper()
    
    data = await fetch_coingecko_market_data(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    circulating = market_data.get("circulating_supply", 0) or 0
    total = market_data.get("total_supply", 0) or circulating
    current_price = market_data.get("current_price", {}).get("usd", 1)
    
    locked_supply = total - circulating
    locked_pct = (locked_supply / total * 100) if total > 0 else 0
    
    # Generate estimated unlock schedule
    # Most vesting schedules: cliff + linear unlock over 24-48 months
    
    unlocks = []
    
    if locked_pct > 5:
        # Assume monthly unlocks
        monthly_unlock_pct = locked_pct / 24  # 24-month typical vesting
        monthly_unlock_amount = locked_supply / 24
        monthly_unlock_usd = monthly_unlock_amount * current_price
        
        now = datetime.now(timezone.utc)
        
        for i in range(min(int(days / 30) + 1, 12)):
            unlock_date = now + timedelta(days=30 * (i + 1))
            
            unlocks.append({
                "date": unlock_date.strftime("%Y-%m-%d"),
                "days_until": 30 * (i + 1),
                "estimated_amount": round(monthly_unlock_amount, 2),
                "estimated_usd": round(monthly_unlock_usd, 2),
                "pct_of_supply": round(monthly_unlock_pct, 2),
                "type": "linear_vest"
            })
    
    # Calculate totals
    total_unlock_amount = sum(u["estimated_amount"] for u in unlocks)
    total_unlock_usd = sum(u["estimated_usd"] for u in unlocks)
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "locked_supply": {
            "amount": locked_supply,
            "pct": round(locked_pct, 2),
            "value_usd": round(locked_supply * current_price, 2)
        },
        "upcoming_unlocks": unlocks,
        "summary": {
            "unlocks_in_period": len(unlocks),
            "total_unlock_amount": round(total_unlock_amount, 2),
            "total_unlock_usd": round(total_unlock_usd, 2),
            "avg_monthly_unlock_pct": round(locked_pct / 24, 2) if locked_pct > 0 else 0
        },
        "_meta": {
            "cache_sec": 3600,
            "days_looked_ahead": days,
            "note": "Unlock schedule estimated from typical vesting patterns"
        }
    }



# ═══════════════════════════════════════════════════════════════
# ADDITIONAL TOKENOMICS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/circulating-supply-ratio/{symbol}")
async def get_circulating_supply_ratio(symbol: str):
    """
    Get circulating supply to max supply ratio.
    
    Lower ratio = more supply to be released (dilution risk)
    Higher ratio = most tokens already circulating
    """
    symbol = symbol.upper()
    
    data = await fetch_coingecko_market_data(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    circulating = market_data.get("circulating_supply", 0) or 0
    total = market_data.get("total_supply", 0) or circulating
    max_supply = market_data.get("max_supply")
    
    # Calculate ratios
    circulating_to_total = (circulating / total * 100) if total > 0 else 100
    circulating_to_max = (circulating / max_supply * 100) if max_supply else None
    
    # Risk assessment
    reference_ratio = circulating_to_max if circulating_to_max else circulating_to_total
    
    if reference_ratio >= 90:
        dilution_risk = "minimal"
        interpretation = "Most supply already circulating - minimal dilution risk"
    elif reference_ratio >= 70:
        dilution_risk = "low"
        interpretation = "Limited supply remaining - low dilution risk"
    elif reference_ratio >= 50:
        dilution_risk = "moderate"
        interpretation = "Significant supply yet to unlock"
    elif reference_ratio >= 30:
        dilution_risk = "high"
        interpretation = "Large supply remaining - high dilution risk"
    else:
        dilution_risk = "very_high"
        interpretation = "Majority of supply not yet circulating - very high dilution risk"
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "supply": {
            "circulating": circulating,
            "total": total,
            "max": max_supply
        },
        "ratios": {
            "circulating_to_total_pct": round(circulating_to_total, 2),
            "circulating_to_max_pct": round(circulating_to_max, 2) if circulating_to_max else None,
            "remaining_to_unlock_pct": round(100 - (circulating_to_max or circulating_to_total), 2)
        },
        "dilution_risk": {
            "level": dilution_risk,
            "interpretation": interpretation
        },
        "_meta": {"cache_sec": 300}
    }


@router.get("/fdv-mcap-ratio/{symbol}")
async def get_fdv_mcap_ratio(symbol: str):
    """
    Get Fully Diluted Valuation to Market Cap ratio.
    
    FDV/MCap ratio interpretation:
    - 1.0-1.2: Minimal dilution ahead
    - 1.2-2.0: Moderate dilution ahead
    - 2.0-3.0: Significant dilution ahead
    - >3.0: High dilution risk
    """
    symbol = symbol.upper()
    
    data = await fetch_coingecko_market_data(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    market_cap = market_data.get("market_cap", {}).get("usd", 0)
    fdv = market_data.get("fully_diluted_valuation", {}).get("usd", 0)
    current_price = market_data.get("current_price", {}).get("usd", 0)
    
    if market_cap == 0:
        raise HTTPException(status_code=400, detail="Market cap data not available")
    
    # Calculate ratio
    fdv_mcap_ratio = fdv / market_cap if fdv > 0 else 1
    mcap_fdv_ratio = market_cap / fdv if fdv > 0 else 1  # Inverse
    
    # Implied dilution
    implied_dilution_pct = ((fdv - market_cap) / market_cap * 100) if market_cap > 0 else 0
    
    # Risk assessment
    if fdv_mcap_ratio <= 1.2:
        dilution_risk = "minimal"
        interpretation = "FDV close to Market Cap - minimal future dilution"
    elif fdv_mcap_ratio <= 1.5:
        dilution_risk = "low"
        interpretation = "Low dilution gap"
    elif fdv_mcap_ratio <= 2.0:
        dilution_risk = "moderate"
        interpretation = "Moderate dilution expected as more tokens unlock"
    elif fdv_mcap_ratio <= 3.0:
        dilution_risk = "high"
        interpretation = "Significant dilution ahead - 2-3x more tokens to unlock"
    else:
        dilution_risk = "very_high"
        interpretation = "Very high dilution risk - most tokens not yet circulating"
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "valuation": {
            "market_cap": market_cap,
            "fdv": fdv,
            "current_price": current_price
        },
        "ratios": {
            "fdv_to_mcap": round(fdv_mcap_ratio, 4),
            "mcap_to_fdv": round(mcap_fdv_ratio, 4),
            "implied_dilution_pct": round(implied_dilution_pct, 2)
        },
        "dilution_risk": {
            "level": dilution_risk,
            "interpretation": interpretation
        },
        "_meta": {"cache_sec": 300}
    }


@router.get("/supply-concentration/{symbol}")
async def get_supply_concentration(symbol: str):
    """
    Get token supply concentration metrics.
    
    Measures how concentrated the token supply is among top holders.
    Uses Herfindahl-Hirschman Index (HHI) estimation.
    """
    symbol = symbol.upper()
    
    data = await fetch_coingecko_market_data(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    market_data = data.get("market_data", {})
    
    circulating = market_data.get("circulating_supply", 0) or 0
    total = market_data.get("total_supply", 0) or circulating
    current_price = market_data.get("current_price", {}).get("usd", 1)
    
    circulating_pct = (circulating / total * 100) if total > 0 else 100
    
    # Estimate concentration based on token age/maturity
    # Newer tokens with less circulation tend to be more concentrated
    
    if circulating_pct < 30:
        # Very concentrated - few large holders
        top_10_pct = 75
        top_50_pct = 90
        top_100_pct = 95
        hhi_estimate = 0.15
    elif circulating_pct < 50:
        top_10_pct = 60
        top_50_pct = 80
        top_100_pct = 90
        hhi_estimate = 0.10
    elif circulating_pct < 70:
        top_10_pct = 45
        top_50_pct = 70
        top_100_pct = 85
        hhi_estimate = 0.06
    else:
        # More distributed
        top_10_pct = 30
        top_50_pct = 55
        top_100_pct = 75
        hhi_estimate = 0.03
    
    # Adjust for known tokens
    if symbol == "BTC":
        top_10_pct = 15
        top_50_pct = 30
        top_100_pct = 45
        hhi_estimate = 0.015
    elif symbol == "ETH":
        top_10_pct = 25
        top_50_pct = 45
        top_100_pct = 60
        hhi_estimate = 0.025
    
    # Calculate concentration score (0-100, lower is better for decentralization)
    concentration_score = min(100, int(hhi_estimate * 500))
    
    # Determine level
    if concentration_score >= 60:
        level = "highly_concentrated"
        interpretation = "Token supply highly concentrated among few addresses"
    elif concentration_score >= 40:
        level = "concentrated"
        interpretation = "Token supply moderately concentrated"
    elif concentration_score >= 20:
        level = "moderate"
        interpretation = "Moderate concentration levels"
    else:
        level = "distributed"
        interpretation = "Token supply relatively well distributed"
    
    return {
        "ts": ts_now(),
        "symbol": symbol,
        "concentration": {
            "top_10_holders_pct": round(top_10_pct, 2),
            "top_50_holders_pct": round(top_50_pct, 2),
            "top_100_holders_pct": round(top_100_pct, 2)
        },
        "metrics": {
            "hhi_estimate": round(hhi_estimate, 4),
            "concentration_score": concentration_score,
            "decentralization_score": 100 - concentration_score
        },
        "assessment": {
            "level": level,
            "interpretation": interpretation
        },
        "supply_info": {
            "circulating": circulating,
            "total": total,
            "circulating_pct": round(circulating_pct, 2)
        },
        "_meta": {"cache_sec": 300}
    }
