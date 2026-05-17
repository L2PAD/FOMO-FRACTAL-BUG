"""
CoinGecko Adapter
Priority: 2 (Comprehensive data, rate-limited)
"""

import httpx
from typing import List, Optional
from . import BaseAdapter, AdapterResult
import os
import logging

logger = logging.getLogger(__name__)


class CoinGeckoAdapter(BaseAdapter):
    """CoinGecko - Secondary provider (has API key limits)"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    PRO_URL = "https://pro-api.coingecko.com/api/v3"
    
    # CoinGecko IDs
    ASSET_MAPPING = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "binancecoin",
        "XRP": "ripple",
        "ADA": "cardano",
        "DOGE": "dogecoin",
        "DOT": "polkadot",
        "AVAX": "avalanche-2",
        "MATIC": "matic-network",
        "LINK": "chainlink",
        "UNI": "uniswap",
        "ATOM": "cosmos",
        "LTC": "litecoin",
        "TRX": "tron",
        "USDT": "tether",
        "USDC": "usd-coin",
        "DAI": "dai",
        "ARB": "arbitrum",
        "OP": "optimism",
        "NEAR": "near",
        "APT": "aptos",
        "SUI": "sui",
        "AAVE": "aave",
        "CRV": "curve-dao-token",
    }
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="coingecko", priority=2)
        self.api_key = api_key or os.environ.get("COINGECKO_API_KEY")
        self.base_url = self.PRO_URL if self.api_key else self.BASE_URL
    
    def _get_headers(self) -> dict:
        if self.api_key:
            return {"x-cg-pro-api-key": self.api_key}
        return {}
    
    def _get_cg_id(self, asset: str) -> str:
        return self.ASSET_MAPPING.get(asset.upper(), asset.lower())
    
    async def get_quote(self, asset: str) -> AdapterResult:
        """Get single asset quote"""
        
        async def _fetch():
            cg_id = self._get_cg_id(asset)
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/simple/price",
                    params={
                        "ids": cg_id,
                        "vs_currencies": "usd",
                        "include_24hr_change": "true",
                        "include_24hr_vol": "true",
                        "include_market_cap": "true"
                    },
                    headers=self._get_headers()
                )
                resp.raise_for_status()
                data = resp.json()
                
                coin = data.get(cg_id, {})
                if not coin:
                    raise ValueError(f"No data for {asset}")
                
                return {
                    "asset": asset.upper(),
                    "price": coin.get("usd", 0),
                    "change_24h": coin.get("usd_24h_change"),
                    "volume_24h": coin.get("usd_24h_vol"),
                    "market_cap": coin.get("usd_market_cap"),
                    "timestamp": int(httpx._utils.get_timestamp() * 1000)
                }
        
        return await self._timed_request(_fetch())
    
    async def get_bulk_quotes(self, assets: List[str]) -> AdapterResult:
        """Get multiple quotes - CoinGecko supports bulk!"""
        
        async def _fetch():
            cg_ids = [self._get_cg_id(a) for a in assets]
            ids_param = ",".join(cg_ids)
            
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/simple/price",
                    params={
                        "ids": ids_param,
                        "vs_currencies": "usd",
                        "include_24hr_change": "true",
                        "include_24hr_vol": "true",
                        "include_market_cap": "true"
                    },
                    headers=self._get_headers()
                )
                resp.raise_for_status()
                data = resp.json()
                
                quotes = []
                for asset in assets:
                    cg_id = self._get_cg_id(asset)
                    coin = data.get(cg_id, {})
                    
                    if coin:
                        quotes.append({
                            "asset": asset.upper(),
                            "price": coin.get("usd", 0),
                            "change_24h": coin.get("usd_24h_change"),
                            "volume_24h": coin.get("usd_24h_vol"),
                            "market_cap": coin.get("usd_market_cap"),
                            "timestamp": int(httpx._utils.get_timestamp() * 1000)
                        })
                
                return quotes
        
        return await self._timed_request(_fetch())
    
    async def get_overview(self) -> AdapterResult:
        """Get global market overview"""
        
        async def _fetch():
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/global",
                    headers=self._get_headers()
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})
                
                return {
                    "market_cap_total": data.get("total_market_cap", {}).get("usd", 0),
                    "volume_24h": data.get("total_volume", {}).get("usd", 0),
                    "btc_dominance": data.get("market_cap_percentage", {}).get("btc", 0),
                    "eth_dominance": data.get("market_cap_percentage", {}).get("eth", 0),
                    "active_cryptocurrencies": data.get("active_cryptocurrencies", 0),
                    "timestamp": int(data.get("updated_at", 0) * 1000)
                }
        
        return await self._timed_request(_fetch())
    
    async def get_candles(self, asset: str, interval: str, limit: int = 100) -> AdapterResult:
        """Get OHLCV candles"""
        
        async def _fetch():
            cg_id = self._get_cg_id(asset)
            
            # CoinGecko free tier only supports limited intervals
            # Map to days
            days_map = {
                "1h": 1,
                "4h": 1,
                "1d": 30,
                "1w": 90
            }
            days = days_map.get(interval, 7)
            
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/coins/{cg_id}/ohlc",
                    params={"vs_currency": "usd", "days": days},
                    headers=self._get_headers()
                )
                resp.raise_for_status()
                data = resp.json()
                
                candles = []
                for c in data[-limit:]:
                    candles.append({
                        "timestamp": c[0],
                        "open": c[1],
                        "high": c[2],
                        "low": c[3],
                        "close": c[4],
                        "volume": 0  # CoinGecko OHLC doesn't include volume
                    })
                
                return candles
        
        return await self._timed_request(_fetch())
