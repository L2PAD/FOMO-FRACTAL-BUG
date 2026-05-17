"""
CoinMarketCap Parser
====================

Parser for CoinMarketCap - Market data (requires API key).
Note: Uses free tier endpoints where possible.
"""

import httpx
import logging
import os
from typing import Dict, List, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CMC_API_BASE = "https://pro-api.coinmarketcap.com/v1"
CMC_API_KEY = os.environ.get("CMC_API_KEY", "")


async def fetch_cmc_listings(limit: int = 100) -> List[Dict]:
    """Fetch cryptocurrency listings from CMC"""
    cryptos = []
    
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY} if CMC_API_KEY else {}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{CMC_API_BASE}/cryptocurrency/listings/latest",
                params={"limit": limit, "convert": "USD"},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                cryptos = data.get("data", [])
            elif response.status_code == 401:
                logger.warning("CMC API key required or invalid")
            else:
                logger.warning(f"CMC API returned {response.status_code}")
    except Exception as e:
        logger.error(f"CMC fetch error: {e}")
    
    return cryptos


async def fetch_cmc_trending() -> List[Dict]:
    """Fetch trending cryptocurrencies from CMC"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{CMC_API_BASE}/cryptocurrency/trending/latest",
                headers={"X-CMC_PRO_API_KEY": CMC_API_KEY} if CMC_API_KEY else {}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
    except Exception as e:
        logger.error(f"CMC trending fetch error: {e}")
    
    return []


async def sync_coinmarketcap_data(db, limit: int = 100) -> Dict[str, Any]:
    """Sync CoinMarketCap data to MongoDB"""
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "ok": True,
        "source": "coinmarketcap",
        "cryptos": 0,
        "errors": []
    }
    
    if not CMC_API_KEY:
        results["errors"].append("CMC_API_KEY not configured")
        logger.warning("[CMC] API key not configured, skipping sync")
        return results
    
    try:
        listings = await fetch_cmc_listings(limit)
        
        for item in listings:
            quote = item.get("quote", {}).get("USD", {})
            
            doc = {
                "id": f"cmc_{item.get('id', '')}",
                "source": "coinmarketcap",
                "symbol": item.get("symbol", ""),
                "name": item.get("name", ""),
                "slug": item.get("slug", ""),
                "rank": item.get("cmc_rank"),
                "price_usd": quote.get("price"),
                "market_cap_usd": quote.get("market_cap"),
                "volume_24h_usd": quote.get("volume_24h"),
                "percent_change_24h": quote.get("percent_change_24h"),
                "percent_change_7d": quote.get("percent_change_7d"),
                "circulating_supply": item.get("circulating_supply"),
                "total_supply": item.get("total_supply"),
                "max_supply": item.get("max_supply"),
                "last_updated": item.get("last_updated"),
                "created_at": now,
                "updated_at": now
            }
            
            await db.market_data.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            results["cryptos"] += 1
    except Exception as e:
        results["errors"].append(f"Listings sync error: {e}")
    
    # Update data source status
    status = "active" if results["cryptos"] > 0 else "partial"
    await db.data_sources.update_one(
        {"id": "coinmarketcap"},
        {
            "$set": {
                "last_sync": now,
                "status": status,
                "updated_at": now
            },
            "$inc": {"sync_count": 1}
        }
    )
    
    logger.info(f"[CoinMarketCap] Synced: {results['cryptos']} cryptocurrencies")
    return results
