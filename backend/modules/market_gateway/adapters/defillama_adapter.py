"""
DefiLlama Adapter
Priority: 1 (Primary - free, reliable, no rate limits)
"""

import httpx
from typing import List
from . import BaseAdapter, AdapterResult
import logging

logger = logging.getLogger(__name__)


class DefiLlamaAdapter(BaseAdapter):
    """DefiLlama - Primary provider (free, no auth required)"""
    
    BASE_URL = "https://api.llama.fi"
    COINS_URL = "https://coins.llama.fi"
    
    # DefiLlama uses different IDs
    ASSET_MAPPING = {
        "BTC": "coingecko:bitcoin",
        "ETH": "coingecko:ethereum",
        "SOL": "coingecko:solana",
        "BNB": "coingecko:binancecoin",
        "XRP": "coingecko:ripple",
        "ADA": "coingecko:cardano",
        "DOGE": "coingecko:dogecoin",
        "DOT": "coingecko:polkadot",
        "AVAX": "coingecko:avalanche-2",
        "MATIC": "coingecko:matic-network",
        "LINK": "coingecko:chainlink",
        "UNI": "coingecko:uniswap",
        "ATOM": "coingecko:cosmos",
        "LTC": "coingecko:litecoin",
        "TRX": "coingecko:tron",
        "USDT": "coingecko:tether",
        "USDC": "coingecko:usd-coin",
        "DAI": "coingecko:dai",
        "ARB": "coingecko:arbitrum",
        "OP": "coingecko:optimism",
        "NEAR": "coingecko:near",
        "APT": "coingecko:aptos",
        "SUI": "coingecko:sui",
        "AAVE": "coingecko:aave",
        "CRV": "coingecko:curve-dao-token",
    }
    
    def __init__(self):
        super().__init__(name="defillama", priority=1)
    
    def _get_llama_id(self, asset: str) -> str:
        """Convert symbol to DefiLlama ID"""
        return self.ASSET_MAPPING.get(asset.upper(), f"coingecko:{asset.lower()}")
    
    async def get_quote(self, asset: str) -> AdapterResult:
        """Get single asset price from DefiLlama"""
        
        async def _fetch():
            llama_id = self._get_llama_id(asset)
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.COINS_URL}/prices/current/{llama_id}")
                resp.raise_for_status()
                data = resp.json()
                
                coin_data = data.get("coins", {}).get(llama_id, {})
                if not coin_data:
                    raise ValueError(f"No data for {asset}")
                
                return {
                    "asset": asset.upper(),
                    "price": coin_data.get("price", 0),
                    "change_24h": coin_data.get("change24h"),
                    "market_cap": coin_data.get("mcap"),
                    "volume_24h": None,  # DefiLlama doesn't provide this
                    "timestamp": int(coin_data.get("timestamp", 0) * 1000)
                }
        
        return await self._timed_request(_fetch())
    
    async def get_bulk_quotes(self, assets: List[str]) -> AdapterResult:
        """Get multiple asset prices - DefiLlama supports bulk requests!"""
        
        async def _fetch():
            llama_ids = [self._get_llama_id(a) for a in assets]
            coins_param = ",".join(llama_ids)
            
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{self.COINS_URL}/prices/current/{coins_param}")
                resp.raise_for_status()
                data = resp.json()
                
                quotes = []
                coins_data = data.get("coins", {})
                
                for asset in assets:
                    llama_id = self._get_llama_id(asset)
                    coin = coins_data.get(llama_id, {})
                    
                    if coin:
                        quotes.append({
                            "asset": asset.upper(),
                            "price": coin.get("price", 0),
                            "change_24h": coin.get("change24h"),
                            "market_cap": coin.get("mcap"),
                            "volume_24h": None,
                            "timestamp": int(coin.get("timestamp", 0) * 1000)
                        })
                
                return quotes
        
        return await self._timed_request(_fetch())
    
    async def get_overview(self) -> AdapterResult:
        """Get global market overview from DefiLlama"""
        
        async def _fetch():
            async with httpx.AsyncClient(timeout=10) as client:
                # Get TVL overview
                resp = await client.get(f"{self.BASE_URL}/v2/historicalChainTvl")
                resp.raise_for_status()
                tvl_data = resp.json()
                
                # Get latest point
                latest = tvl_data[-1] if tvl_data else {}
                
                # Also get stablecoins data
                stables_resp = await client.get(f"{self.BASE_URL}/stablecoins")
                stables = stables_resp.json() if stables_resp.status_code == 200 else {}
                
                total_stables = sum(
                    s.get("circulating", {}).get("peggedUSD", 0)
                    for s in stables.get("peggedAssets", [])
                )
                
                return {
                    "total_tvl": latest.get("tvl", 0),
                    "stablecoin_mcap": total_stables,
                    "timestamp": latest.get("date", 0) * 1000
                }
        
        return await self._timed_request(_fetch())
    
    async def get_candles(self, asset: str, interval: str, limit: int = 100) -> AdapterResult:
        """Get historical prices from DefiLlama"""
        
        async def _fetch():
            llama_id = self._get_llama_id(asset)
            
            # Convert interval to DefiLlama format (they use daily/hourly)
            period = "hourly" if interval in ["1h", "4h"] else "daily"
            
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.COINS_URL}/chart/{llama_id}",
                    params={"period": period, "span": limit}
                )
                resp.raise_for_status()
                data = resp.json()
                
                prices = data.get("coins", {}).get(llama_id, {}).get("prices", [])
                
                candles = []
                for p in prices[-limit:]:
                    candles.append({
                        "timestamp": int(p.get("timestamp", 0) * 1000),
                        "open": p.get("price", 0),
                        "high": p.get("price", 0),
                        "low": p.get("price", 0),
                        "close": p.get("price", 0),
                        "volume": 0
                    })
                
                return candles
        
        return await self._timed_request(_fetch())
