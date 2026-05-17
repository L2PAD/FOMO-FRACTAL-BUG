"""
CoinGecko Parser
================
Fetches real market data from CoinGecko API (free tier).

Data:
- Project profiles (description, links)
- Market data (price, market cap, volume)
- Trending coins
"""

import httpx
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from modules.parsers.base_reliable_parser import BaseReliableParser

logger = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"


class CoinGeckoParser(BaseReliableParser):
    """CoinGecko data parser with reliability tracking"""
    
    source_id = "coingecko"
    
    def __init__(self, db):
        super().__init__(db)
        self.client = httpx.AsyncClient(timeout=30)
        
    async def close(self):
        await self.client.aclose()
    
    async def fetch_trending(self) -> List[Dict]:
        """Fetch trending coins from CoinGecko with reliability tracking"""
        start = time.time()
        try:
            resp = await self.client.get(f"{COINGECKO_BASE}/search/trending")
            latency_ms = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                coins = data.get("coins", [])
                
                await self.record_fetch_simple(
                    success=True,
                    latency_ms=latency_ms,
                    endpoint="trending",
                    data_freshness_hours=0.5
                )
                
                return [
                    {
                        "id": c.get("item", {}).get("id"),
                        "name": c.get("item", {}).get("name"),
                        "symbol": c.get("item", {}).get("symbol"),
                        "market_cap_rank": c.get("item", {}).get("market_cap_rank"),
                        "thumb": c.get("item", {}).get("thumb"),
                        "score": c.get("item", {}).get("score", 0)
                    }
                    for c in coins
                ]
            
            await self.record_fetch_simple(
                success=False,
                latency_ms=latency_ms,
                endpoint="trending",
                error=f"HTTP {resp.status_code}"
            )
            return []
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            await self.record_fetch_simple(
                success=False,
                latency_ms=latency_ms,
                endpoint="trending",
                error=str(e)
            )
            logger.error(f"CoinGecko trending error: {e}")
            return []
    
    async def fetch_coin_details(self, coin_id: str) -> Optional[Dict]:
        """Fetch detailed coin info from CoinGecko with reliability tracking"""
        start = time.time()
        try:
            resp = await self.client.get(
                f"{COINGECKO_BASE}/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "true",
                    "community_data": "false",
                    "developer_data": "false"
                }
            )
            latency_ms = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                
                await self.record_fetch_simple(
                    success=True,
                    latency_ms=latency_ms,
                    endpoint=f"coins/{coin_id}",
                    data_freshness_hours=0.2
                )
                
                # Extract links
                links = data.get("links", {})
                
                return {
                    "coingecko_id": coin_id,
                    "name": data.get("name"),
                    "symbol": data.get("symbol", "").upper(),
                    "description": data.get("description", {}).get("en", "")[:2000],
                    
                    # Market data
                    "market_cap_rank": data.get("market_cap_rank"),
                    "current_price_usd": data.get("market_data", {}).get("current_price", {}).get("usd"),
                    "market_cap_usd": data.get("market_data", {}).get("market_cap", {}).get("usd"),
                    "total_volume_usd": data.get("market_data", {}).get("total_volume", {}).get("usd"),
                    "circulating_supply": data.get("market_data", {}).get("circulating_supply"),
                    "total_supply": data.get("market_data", {}).get("total_supply"),
                    "max_supply": data.get("market_data", {}).get("max_supply"),
                    
                    # Price changes
                    "price_change_24h": data.get("market_data", {}).get("price_change_percentage_24h"),
                    "price_change_7d": data.get("market_data", {}).get("price_change_percentage_7d"),
                    "price_change_30d": data.get("market_data", {}).get("price_change_percentage_30d"),
                    
                    # Links
                    "website": links.get("homepage", [None])[0] if links.get("homepage") else None,
                    "twitter": f"https://twitter.com/{links.get('twitter_screen_name')}" if links.get("twitter_screen_name") else None,
                    "telegram": links.get("telegram_channel_identifier"),
                    "github": links.get("repos_url", {}).get("github", [None])[0] if links.get("repos_url", {}).get("github") else None,
                    "reddit": links.get("subreddit_url"),
                    
                    # Categories
                    "categories": data.get("categories", []),
                    
                    # Images
                    "logo_url": data.get("image", {}).get("large"),
                    
                    "source": "coingecko",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            
            await self.record_fetch_simple(
                success=False,
                latency_ms=latency_ms,
                endpoint=f"coins/{coin_id}",
                error=f"HTTP {resp.status_code}"
            )
            return None
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            await self.record_fetch_simple(
                success=False,
                latency_ms=latency_ms,
                endpoint=f"coins/{coin_id}",
                error=str(e)
            )
            logger.error(f"CoinGecko coin details error: {e}")
            return None
    
    async def fetch_market_data(self, limit: int = 100) -> List[Dict]:
        """Fetch top coins market data with reliability tracking"""
        start = time.time()
        try:
            resp = await self.client.get(
                f"{COINGECKO_BASE}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": limit,
                    "page": 1,
                    "sparkline": "false"
                }
            )
            latency_ms = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                coins = resp.json()
                
                await self.record_fetch_simple(
                    success=True,
                    latency_ms=latency_ms,
                    endpoint="markets",
                    data_freshness_hours=0.1
                )
                
                return [
                    {
                        "coingecko_id": c.get("id"),
                        "symbol": c.get("symbol", "").upper(),
                        "name": c.get("name"),
                        "current_price": c.get("current_price"),
                        "market_cap": c.get("market_cap"),
                        "market_cap_rank": c.get("market_cap_rank"),
                        "total_volume": c.get("total_volume"),
                        "price_change_24h": c.get("price_change_percentage_24h"),
                        "circulating_supply": c.get("circulating_supply"),
                        "total_supply": c.get("total_supply"),
                        "logo_url": c.get("image"),
                        "ath": c.get("ath"),
                        "ath_date": c.get("ath_date"),
                        "source": "coingecko",
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    for c in coins
                ]
            
            await self.record_fetch_simple(
                success=False,
                latency_ms=latency_ms,
                endpoint="markets",
                error=f"HTTP {resp.status_code}"
            )
            return []
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            await self.record_fetch_simple(
                success=False,
                latency_ms=latency_ms,
                endpoint="markets",
                error=str(e)
            )
            logger.error(f"CoinGecko market data error: {e}")
            return []
    
    async def sync_projects(self, coin_ids: List[str] = None):
        """Sync project data from CoinGecko to database"""
        if coin_ids is None:
            # Default top coins
            coin_ids = [
                "bitcoin", "ethereum", "solana", "cardano", "avalanche-2",
                "polkadot", "chainlink", "uniswap", "aave", "maker",
                "arbitrum", "optimism", "celestia", "sui", "aptos",
                "starknet", "layerzero", "eigenlayer", "jupiter", "pyth-network"
            ]
        
        synced = 0
        for coin_id in coin_ids:
            data = await self.fetch_coin_details(coin_id)
            if data:
                # Update project profile
                await self.db.project_profiles.update_one(
                    {"coingecko_id": coin_id},
                    {
                        "$set": {
                            "project_id": f"cg:{coin_id}",
                            "coingecko_id": coin_id,
                            "about": data.get("description"),
                            "categories": data.get("categories"),
                            "logo_url": data.get("logo_url"),
                            "source": "coingecko",
                            "updated_at": data.get("updated_at")
                        }
                    },
                    upsert=True
                )
                
                # Update project links
                links = {
                    "project_id": f"cg:{coin_id}",
                    "coingecko_id": coin_id,
                    "website": data.get("website"),
                    "twitter": data.get("twitter"),
                    "telegram": data.get("telegram"),
                    "github": data.get("github"),
                    "reddit": data.get("reddit"),
                    "source": "coingecko",
                    "updated_at": data.get("updated_at")
                }
                await self.db.project_links.update_one(
                    {"coingecko_id": coin_id},
                    {"$set": links},
                    upsert=True
                )
                
                # Update market data
                market = {
                    "project_id": f"cg:{coin_id}",
                    "coingecko_id": coin_id,
                    "symbol": data.get("symbol"),
                    "name": data.get("name"),
                    "current_price_usd": data.get("current_price_usd"),
                    "market_cap_usd": data.get("market_cap_usd"),
                    "market_cap_rank": data.get("market_cap_rank"),
                    "circulating_supply": data.get("circulating_supply"),
                    "total_supply": data.get("total_supply"),
                    "price_change_24h": data.get("price_change_24h"),
                    "price_change_7d": data.get("price_change_7d"),
                    "price_change_30d": data.get("price_change_30d"),
                    "source": "coingecko",
                    "updated_at": data.get("updated_at")
                }
                await self.db.market_data.update_one(
                    {"coingecko_id": coin_id},
                    {"$set": market},
                    upsert=True
                )
                
                synced += 1
                # Rate limit - CoinGecko free tier is limited
                await asyncio.sleep(1.5)
        
        return {"synced": synced, "source": "coingecko"}
    
    async def sync_market_overview(self):
        """Sync top 100 coins market data"""
        coins = await self.fetch_market_data(100)
        
        synced = 0
        for coin in coins:
            await self.db.market_data.update_one(
                {"coingecko_id": coin.get("coingecko_id")},
                {"$set": coin},
                upsert=True
            )
            synced += 1
        
        return {"synced": synced, "source": "coingecko"}


async def sync_coingecko_data(db, full: bool = False):
    """
    Helper function to sync CoinGecko data.
    Called from bootstrap or scheduled task.
    """
    parser = CoinGeckoParser(db)
    
    try:
        # Sync market overview (fast, no rate limit issues)
        result = await parser.sync_market_overview()
        logger.info(f"CoinGecko market sync: {result}")
        
        if full:
            # Sync detailed project data (slower due to rate limits)
            result = await parser.sync_projects()
            logger.info(f"CoinGecko projects sync: {result}")
        
        return {"ok": True, "source": "coingecko"}
    finally:
        await parser.close()
