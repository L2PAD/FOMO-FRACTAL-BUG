"""
Exchange Adapter
Priority: 5 (Direct exchange data - Binance, Coinbase, Hyperliquid)
"""

import httpx
from typing import List, Optional
from . import BaseAdapter, AdapterResult
import logging
import time

logger = logging.getLogger(__name__)


class ExchangeAdapter(BaseAdapter):
    """Direct exchange data from Binance, Coinbase, Hyperliquid"""
    
    EXCHANGES = {
        "binance": {
            "ticker": "https://api.binance.com/api/v3/ticker/24hr",
            "orderbook": "https://api.binance.com/api/v3/depth",
            "trades": "https://api.binance.com/api/v3/trades",
            "klines": "https://api.binance.com/api/v3/klines"
        },
        "coinbase": {
            "ticker": "https://api.exchange.coinbase.com/products/{symbol}/ticker",
            "orderbook": "https://api.exchange.coinbase.com/products/{symbol}/book",
            "trades": "https://api.exchange.coinbase.com/products/{symbol}/trades"
        },
        "hyperliquid": {
            "base": "https://api.hyperliquid.xyz/info"
        }
    }
    
    def __init__(self):
        super().__init__(name="exchanges", priority=5)
    
    def _get_symbol(self, asset: str, exchange: str) -> str:
        """Convert asset to exchange symbol"""
        asset = asset.upper()
        if exchange == "binance":
            return f"{asset}USDT"
        elif exchange == "coinbase":
            return f"{asset}-USD"
        elif exchange == "hyperliquid":
            return asset
        return asset
    
    async def get_quote(self, asset: str) -> AdapterResult:
        """Get quote from best available exchange"""
        
        async def _fetch():
            quotes = []
            
            async with httpx.AsyncClient(timeout=10) as client:
                # Try Coinbase first (most reliable)
                try:
                    symbol = self._get_symbol(asset, "coinbase")
                    resp = await client.get(
                        self.EXCHANGES["coinbase"]["ticker"].format(symbol=symbol)
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        quotes.append({
                            "exchange": "coinbase",
                            "price": float(data.get("price", 0)),
                            "volume_24h": float(data.get("volume", 0)),
                            "bid": float(data.get("bid", 0)),
                            "ask": float(data.get("ask", 0))
                        })
                except Exception as e:
                    logger.debug(f"Coinbase error: {e}")
                
                # Try Binance
                try:
                    symbol = self._get_symbol(asset, "binance")
                    resp = await client.get(
                        self.EXCHANGES["binance"]["ticker"],
                        params={"symbol": symbol}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        quotes.append({
                            "exchange": "binance",
                            "price": float(data.get("lastPrice", 0)),
                            "volume_24h": float(data.get("volume", 0)),
                            "change_24h": float(data.get("priceChangePercent", 0))
                        })
                except Exception as e:
                    logger.debug(f"Binance error: {e}")
                
                # Try Hyperliquid
                try:
                    resp = await client.post(
                        self.EXCHANGES["hyperliquid"]["base"],
                        json={"type": "allMids"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if asset.upper() in data:
                            quotes.append({
                                "exchange": "hyperliquid",
                                "price": float(data[asset.upper()])
                            })
                except Exception as e:
                    logger.debug(f"Hyperliquid error: {e}")
            
            if not quotes:
                raise ValueError(f"No exchange data for {asset}")
            
            # Return best quote (by volume or first available)
            best = quotes[0]
            return {
                "asset": asset.upper(),
                "price": best["price"],
                "volume_24h": best.get("volume_24h"),
                "change_24h": best.get("change_24h"),
                "exchange": best["exchange"],
                "all_exchanges": quotes,
                "timestamp": int(time.time() * 1000)
            }
        
        return await self._timed_request(_fetch())
    
    async def get_bulk_quotes(self, assets: List[str]) -> AdapterResult:
        """Get quotes for multiple assets from exchanges"""
        
        async def _fetch():
            quotes = []
            
            async with httpx.AsyncClient(timeout=15) as client:
                # Binance bulk - get all tickers at once
                try:
                    resp = await client.get(self.EXCHANGES["binance"]["ticker"])
                    if resp.status_code == 200:
                        all_tickers = {t["symbol"]: t for t in resp.json()}
                        
                        for asset in assets:
                            symbol = self._get_symbol(asset, "binance")
                            if symbol in all_tickers:
                                t = all_tickers[symbol]
                                quotes.append({
                                    "asset": asset.upper(),
                                    "price": float(t.get("lastPrice", 0)),
                                    "volume_24h": float(t.get("volume", 0)),
                                    "change_24h": float(t.get("priceChangePercent", 0)),
                                    "exchange": "binance",
                                    "timestamp": int(time.time() * 1000)
                                })
                except Exception as e:
                    logger.debug(f"Binance bulk error: {e}")
            
            return quotes
        
        return await self._timed_request(_fetch())
    
    async def get_overview(self) -> AdapterResult:
        """Exchanges don't provide global overview"""
        return AdapterResult(
            success=False,
            error="Exchange adapter doesn't support market overview",
            source=self.name
        )
    
    async def get_exchanges_for_asset(self, asset: str) -> AdapterResult:
        """Get all exchange data for an asset"""
        
        async def _fetch():
            exchanges = []
            
            async with httpx.AsyncClient(timeout=15) as client:
                # Coinbase
                try:
                    symbol = self._get_symbol(asset, "coinbase")
                    resp = await client.get(
                        self.EXCHANGES["coinbase"]["ticker"].format(symbol=symbol)
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        exchanges.append({
                            "exchange": "coinbase",
                            "symbol": symbol,
                            "price": float(data.get("price", 0)),
                            "volume_24h": float(data.get("volume", 0)),
                            "bid": float(data.get("bid", 0)),
                            "ask": float(data.get("ask", 0)),
                            "spread": float(data.get("ask", 0)) - float(data.get("bid", 0)),
                            "status": "healthy"
                        })
                except Exception as e:
                    exchanges.append({
                        "exchange": "coinbase",
                        "symbol": self._get_symbol(asset, "coinbase"),
                        "status": "error",
                        "error": str(e)
                    })
                
                # Binance
                try:
                    symbol = self._get_symbol(asset, "binance")
                    resp = await client.get(
                        self.EXCHANGES["binance"]["ticker"],
                        params={"symbol": symbol}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        exchanges.append({
                            "exchange": "binance",
                            "symbol": symbol,
                            "price": float(data.get("lastPrice", 0)),
                            "volume_24h": float(data.get("volume", 0)),
                            "bid": float(data.get("bidPrice", 0)),
                            "ask": float(data.get("askPrice", 0)),
                            "spread": float(data.get("askPrice", 0)) - float(data.get("bidPrice", 0)),
                            "status": "healthy"
                        })
                    else:
                        exchanges.append({
                            "exchange": "binance",
                            "symbol": symbol,
                            "status": "error",
                            "error": f"HTTP {resp.status_code}"
                        })
                except Exception as e:
                    exchanges.append({
                        "exchange": "binance",
                        "symbol": self._get_symbol(asset, "binance"),
                        "status": "error",
                        "error": str(e)
                    })
                
                # Hyperliquid
                try:
                    resp = await client.post(
                        self.EXCHANGES["hyperliquid"]["base"],
                        json={"type": "allMids"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if asset.upper() in data:
                            exchanges.append({
                                "exchange": "hyperliquid",
                                "symbol": asset.upper(),
                                "price": float(data[asset.upper()]),
                                "status": "healthy"
                            })
                        else:
                            exchanges.append({
                                "exchange": "hyperliquid",
                                "symbol": asset.upper(),
                                "status": "not_listed"
                            })
                except Exception as e:
                    exchanges.append({
                        "exchange": "hyperliquid",
                        "symbol": asset.upper(),
                        "status": "error",
                        "error": str(e)
                    })
            
            return exchanges
        
        return await self._timed_request(_fetch())
    
    async def get_orderbook(self, asset: str, exchange: str = "coinbase", limit: int = 20) -> AdapterResult:
        """Get orderbook from specific exchange"""
        
        async def _fetch():
            async with httpx.AsyncClient(timeout=10) as client:
                if exchange == "coinbase":
                    symbol = self._get_symbol(asset, "coinbase")
                    resp = await client.get(
                        self.EXCHANGES["coinbase"]["orderbook"].format(symbol=symbol),
                        params={"level": 2}
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    
                    return {
                        "bids": [{"price": float(b[0]), "amount": float(b[1])} for b in data.get("bids", [])[:limit]],
                        "asks": [{"price": float(a[0]), "amount": float(a[1])} for a in data.get("asks", [])[:limit]],
                        "exchange": exchange
                    }
                
                elif exchange == "binance":
                    symbol = self._get_symbol(asset, "binance")
                    resp = await client.get(
                        self.EXCHANGES["binance"]["orderbook"],
                        params={"symbol": symbol, "limit": limit}
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    
                    return {
                        "bids": [{"price": float(b[0]), "amount": float(b[1])} for b in data.get("bids", [])],
                        "asks": [{"price": float(a[0]), "amount": float(a[1])} for a in data.get("asks", [])],
                        "exchange": exchange
                    }
                
                else:
                    raise ValueError(f"Unsupported exchange: {exchange}")
        
        return await self._timed_request(_fetch())
    
    async def get_trades(self, asset: str, exchange: str = "coinbase", limit: int = 50) -> AdapterResult:
        """Get recent trades from specific exchange"""
        
        async def _fetch():
            async with httpx.AsyncClient(timeout=10) as client:
                if exchange == "coinbase":
                    symbol = self._get_symbol(asset, "coinbase")
                    resp = await client.get(
                        self.EXCHANGES["coinbase"]["trades"].format(symbol=symbol),
                        params={"limit": limit}
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    
                    return {
                        "trades": [{
                            "id": str(t.get("trade_id", "")),
                            "price": float(t.get("price", 0)),
                            "amount": float(t.get("size", 0)),
                            "side": t.get("side", "unknown"),
                            "timestamp": t.get("time", "")
                        } for t in data],
                        "exchange": exchange
                    }
                
                elif exchange == "binance":
                    symbol = self._get_symbol(asset, "binance")
                    resp = await client.get(
                        self.EXCHANGES["binance"]["trades"],
                        params={"symbol": symbol, "limit": limit}
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    
                    return {
                        "trades": [{
                            "id": str(t.get("id", "")),
                            "price": float(t.get("price", 0)),
                            "amount": float(t.get("qty", 0)),
                            "side": "buy" if t.get("isBuyerMaker") else "sell",
                            "timestamp": t.get("time", 0)
                        } for t in data],
                        "exchange": exchange
                    }
                
                else:
                    raise ValueError(f"Unsupported exchange: {exchange}")
        
        return await self._timed_request(_fetch())
    
    async def get_candles(self, asset: str, interval: str = "1h", limit: int = 100) -> AdapterResult:
        """Get OHLCV candles from Binance"""
        
        async def _fetch():
            symbol = self._get_symbol(asset, "binance")
            
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self.EXCHANGES["binance"]["klines"],
                    params={
                        "symbol": symbol,
                        "interval": interval,
                        "limit": limit
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                
                candles = []
                for c in data:
                    candles.append({
                        "timestamp": c[0],
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": float(c[4]),
                        "volume": float(c[5])
                    })
                
                return candles
        
        return await self._timed_request(_fetch())
