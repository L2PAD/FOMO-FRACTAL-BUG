"""
DexScreener Adapter
Priority: 4 (DEX data, real-time)
"""

import httpx
from typing import List
from . import BaseAdapter, AdapterResult
import logging

logger = logging.getLogger(__name__)


class DexScreenerAdapter(BaseAdapter):
    """DexScreener - DEX price data (free, no auth)"""
    
    BASE_URL = "https://api.dexscreener.com"
    
    # Token addresses for major assets (Ethereum mainnet)
    TOKEN_ADDRESSES = {
        "ETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "DAI": "0x6B175474E89094C44Da98b954EesdfdeF1cA7",
        "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
        "AAVE": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
        "CRV": "0xD533a949740bb3306d119CC777fa900bA034cd52",
    }
    
    def __init__(self):
        super().__init__(name="dexscreener", priority=4)
    
    async def get_quote(self, asset: str) -> AdapterResult:
        """Get DEX quote for asset"""
        
        async def _fetch():
            # Search for the token
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/latest/dex/search",
                    params={"q": asset}
                )
                resp.raise_for_status()
                data = resp.json()
                
                pairs = data.get("pairs", [])
                if not pairs:
                    raise ValueError(f"No DEX data for {asset}")
                
                # Get most liquid pair
                best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                
                return {
                    "asset": asset.upper(),
                    "price": float(best_pair.get("priceUsd", 0)),
                    "change_24h": float(best_pair.get("priceChange", {}).get("h24", 0) or 0),
                    "volume_24h": float(best_pair.get("volume", {}).get("h24", 0) or 0),
                    "market_cap": float(best_pair.get("fdv", 0) or 0),
                    "dex": best_pair.get("dexId"),
                    "pair": best_pair.get("pairAddress"),
                    "timestamp": int(httpx._utils.get_timestamp() * 1000)
                }
        
        return await self._timed_request(_fetch())
    
    async def get_bulk_quotes(self, assets: List[str]) -> AdapterResult:
        """Get multiple DEX quotes"""
        
        async def _fetch():
            quotes = []
            async with httpx.AsyncClient(timeout=20) as client:
                for asset in assets:
                    try:
                        resp = await client.get(
                            f"{self.BASE_URL}/latest/dex/search",
                            params={"q": asset}
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            pairs = data.get("pairs", [])
                            
                            if pairs:
                                best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                                quotes.append({
                                    "asset": asset.upper(),
                                    "price": float(best.get("priceUsd", 0)),
                                    "change_24h": float(best.get("priceChange", {}).get("h24", 0) or 0),
                                    "volume_24h": float(best.get("volume", {}).get("h24", 0) or 0),
                                    "market_cap": float(best.get("fdv", 0) or 0),
                                    "timestamp": int(httpx._utils.get_timestamp() * 1000)
                                })
                    except Exception as e:
                        logger.debug(f"DexScreener failed for {asset}: {e}")
                        continue
            
            return quotes
        
        return await self._timed_request(_fetch())
    
    async def get_overview(self) -> AdapterResult:
        """DexScreener doesn't provide global overview"""
        return AdapterResult(
            success=False,
            error="DexScreener doesn't support market overview",
            source=self.name
        )
