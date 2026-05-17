"""
Asset Resolver Engine
=====================

Resolves any identifier to a canonical asset_id.

Resolution order:
1. Exact match on external_id
2. Exact match on canonical_symbol
3. Exact match on contract address
4. Fuzzy match on canonical_name
5. Search by symbol pattern

Examples:
- "BTC" -> asset_btc
- "bitcoin" -> asset_btc  
- "BTCUSDT" -> asset_btc
- "0x..." (contract) -> asset_xxx
"""

import re
import logging
from typing import Optional, List, Tuple
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class AssetResolver:
    """
    Asset Resolution Engine.
    Converts any external identifier to canonical asset_id.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.assets = db.assets
        self.external_ids = db.asset_external_ids
        self.market_symbols = db.asset_market_symbols
        
        # Cache for frequently resolved assets
        self._cache: dict = {}
        self._cache_ttl = 300  # 5 minutes
        self._cache_ts: dict = {}
    
    # ═══════════════════════════════════════════════════════════════
    # MAIN RESOLVE METHOD
    # ═══════════════════════════════════════════════════════════════
    
    async def resolve(
        self, 
        query: str, 
        source: Optional[str] = None,
        chain: Optional[str] = None
    ) -> dict:
        """
        Resolve any identifier to canonical asset.
        
        Args:
            query: Any identifier (symbol, name, external_id, contract, trading pair)
            source: Optional source hint (coingecko, binance, etc.)
            chain: Optional chain hint (ethereum, solana, etc.)
            
        Returns:
            {
                "resolved": bool,
                "asset_id": str or None,
                "asset": dict or None,
                "match_type": str,
                "confidence": float,
                "alternatives": list
            }
        """
        if not query:
            return self._not_found(query)
        
        query_clean = query.strip()
        query_lower = query_clean.lower()
        query_upper = query_clean.upper()
        
        # Check cache first
        cache_key = f"{query_lower}:{source or ''}:{chain or ''}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        # Resolution chain
        result = None
        
        # 1. Exact match on external_id (with source)
        if source:
            result = await self._resolve_by_external_id(query_clean, source)
            if result["resolved"]:
                result["match_type"] = "external_id_exact"
                result["confidence"] = 1.0
        
        # 2. Exact match on external_id (any source)
        if not result or not result["resolved"]:
            result = await self._resolve_by_external_id(query_clean)
            if result["resolved"]:
                result["match_type"] = "external_id"
                result["confidence"] = 0.95
        
        # 3. Exact match on canonical symbol
        if not result or not result["resolved"]:
            result = await self._resolve_by_symbol(query_upper)
            if result["resolved"]:
                result["match_type"] = "symbol"
                result["confidence"] = 0.9
        
        # 4. Match on trading pair (BTCUSDT -> BTC)
        if not result or not result["resolved"]:
            result = await self._resolve_by_trading_pair(query_upper)
            if result["resolved"]:
                result["match_type"] = "trading_pair"
                result["confidence"] = 0.85
        
        # 5. Match on market symbol (exchange-specific)
        if not result or not result["resolved"]:
            result = await self._resolve_by_market_symbol(query_upper, source)
            if result["resolved"]:
                result["match_type"] = "market_symbol"
                result["confidence"] = 0.85
        
        # 6. Match on contract address
        if not result or not result["resolved"]:
            if self._is_contract_address(query_clean):
                result = await self._resolve_by_contract(query_clean, chain)
                if result["resolved"]:
                    result["match_type"] = "contract"
                    result["confidence"] = 0.95
        
        # 7. Fuzzy match on name
        if not result or not result["resolved"]:
            result = await self._resolve_by_name(query_clean)
            if result["resolved"]:
                result["match_type"] = "name"
                result["confidence"] = 0.7
        
        # Cache result
        if result and result["resolved"]:
            self._set_cached(cache_key, result)
        
        return result or self._not_found(query)
    
    # ═══════════════════════════════════════════════════════════════
    # RESOLUTION METHODS
    # ═══════════════════════════════════════════════════════════════
    
    async def _resolve_by_external_id(
        self, 
        external_id: str, 
        source: Optional[str] = None
    ) -> dict:
        """Resolve by external source ID"""
        query = {"external_id": {"$regex": f"^{re.escape(external_id)}$", "$options": "i"}}
        if source:
            query["source"] = source
        
        mapping = await self.external_ids.find_one(query)
        if mapping:
            asset = await self.assets.find_one({"id": mapping["asset_id"]})
            if asset:
                return self._found(external_id, asset)
        
        return self._not_found(external_id)
    
    async def _resolve_by_symbol(self, symbol: str) -> dict:
        """Resolve by canonical symbol"""
        asset = await self.assets.find_one({
            "canonical_symbol": {"$regex": f"^{re.escape(symbol)}$", "$options": "i"},
            "status": "active"
        })
        if asset:
            return self._found(symbol, asset)
        return self._not_found(symbol)
    
    async def _resolve_by_trading_pair(self, pair: str) -> dict:
        """
        Resolve trading pair to base asset.
        BTCUSDT -> BTC
        ETH-USD -> ETH
        BTC-PERP -> BTC
        """
        # Common quote currencies
        quotes = ["USDT", "USDC", "USD", "BUSD", "EUR", "BTC", "ETH", "PERP", "SWAP"]
        
        base = pair
        for quote in quotes:
            if pair.endswith(quote):
                base = pair[:-len(quote)]
                break
            if pair.endswith(f"-{quote}"):
                base = pair[:-(len(quote) + 1)]
                break
        
        if base and base != pair:
            return await self._resolve_by_symbol(base)
        
        return self._not_found(pair)
    
    async def _resolve_by_market_symbol(
        self, 
        symbol: str, 
        exchange: Optional[str] = None
    ) -> dict:
        """Resolve by exchange market symbol"""
        query = {"symbol": {"$regex": f"^{re.escape(symbol)}$", "$options": "i"}}
        if exchange:
            query["exchange"] = exchange.lower()
        
        market = await self.market_symbols.find_one(query)
        if market:
            asset = await self.assets.find_one({"id": market["asset_id"]})
            if asset:
                return self._found(symbol, asset)
        
        return self._not_found(symbol)
    
    async def _resolve_by_contract(
        self, 
        contract: str, 
        chain: Optional[str] = None
    ) -> dict:
        """Resolve by contract address"""
        contract_lower = contract.lower()
        query = {"contract": {"$regex": f"^{re.escape(contract_lower)}$", "$options": "i"}}
        if chain:
            query["chain"] = chain.lower()
        
        mapping = await self.external_ids.find_one(query)
        if mapping:
            asset = await self.assets.find_one({"id": mapping["asset_id"]})
            if asset:
                return self._found(contract, asset)
        
        return self._not_found(contract)
    
    async def _resolve_by_name(self, name: str) -> dict:
        """Fuzzy resolve by canonical name"""
        # Exact name match first
        asset = await self.assets.find_one({
            "canonical_name": {"$regex": f"^{re.escape(name)}$", "$options": "i"},
            "status": "active"
        })
        if asset:
            return self._found(name, asset)
        
        # Partial name match
        asset = await self.assets.find_one({
            "canonical_name": {"$regex": re.escape(name), "$options": "i"},
            "status": "active"
        })
        if asset:
            return self._found(name, asset)
        
        return self._not_found(name)
    
    # ═══════════════════════════════════════════════════════════════
    # BULK RESOLVE
    # ═══════════════════════════════════════════════════════════════
    
    async def resolve_many(
        self, 
        queries: List[str], 
        source: Optional[str] = None
    ) -> dict:
        """
        Resolve multiple identifiers at once.
        
        Returns:
            {
                "resolved": {query: asset_id, ...},
                "unresolved": [query, ...]
            }
        """
        resolved = {}
        unresolved = []
        
        for query in queries:
            result = await self.resolve(query, source)
            if result["resolved"]:
                resolved[query] = result["asset_id"]
            else:
                unresolved.append(query)
        
        return {
            "resolved": resolved,
            "unresolved": unresolved,
            "stats": {
                "total": len(queries),
                "resolved_count": len(resolved),
                "unresolved_count": len(unresolved)
            }
        }
    
    # ═══════════════════════════════════════════════════════════════
    # SEARCH
    # ═══════════════════════════════════════════════════════════════
    
    async def search(
        self, 
        query: str, 
        limit: int = 10
    ) -> List[dict]:
        """
        Search for assets by query.
        Returns list of matching assets with relevance score.
        """
        if not query or len(query) < 2:
            return []
        
        query_pattern = re.escape(query)
        results = []
        
        # Search by symbol (highest priority)
        cursor = self.assets.find({
            "canonical_symbol": {"$regex": query_pattern, "$options": "i"},
            "status": "active"
        }).limit(limit)
        async for asset in cursor:
            asset.pop("_id", None)
            results.append({
                "asset": asset,
                "match_type": "symbol",
                "relevance": 1.0 if asset["canonical_symbol"].upper() == query.upper() else 0.8
            })
        
        # Search by name
        if len(results) < limit:
            cursor = self.assets.find({
                "canonical_name": {"$regex": query_pattern, "$options": "i"},
                "status": "active"
            }).limit(limit - len(results))
            async for asset in cursor:
                asset.pop("_id", None)
                # Skip if already in results
                if not any(r["asset"]["id"] == asset["id"] for r in results):
                    results.append({
                        "asset": asset,
                        "match_type": "name",
                        "relevance": 0.6
                    })
        
        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        
        return results[:limit]
    
    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    def _is_contract_address(self, s: str) -> bool:
        """Check if string looks like a contract address"""
        # Ethereum-like
        if re.match(r'^0x[a-fA-F0-9]{40}$', s):
            return True
        # Solana-like (base58)
        if re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', s):
            return True
        return False
    
    def _found(self, query: str, asset: dict) -> dict:
        """Build found result"""
        asset.pop("_id", None)
        return {
            "query": query,
            "resolved": True,
            "asset_id": asset["id"],
            "asset": asset,
            "match_type": None,
            "confidence": 0.0,
            "alternatives": []
        }
    
    def _not_found(self, query: str) -> dict:
        """Build not found result"""
        return {
            "query": query,
            "resolved": False,
            "asset_id": None,
            "asset": None,
            "match_type": None,
            "confidence": 0.0,
            "alternatives": []
        }
    
    def _get_cached(self, key: str) -> Optional[dict]:
        """Get from cache if not expired"""
        if key in self._cache:
            ts = self._cache_ts.get(key, 0)
            now = datetime.now(timezone.utc).timestamp()
            if now - ts < self._cache_ttl:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._cache_ts[key]
        return None
    
    def _set_cached(self, key: str, value: dict):
        """Set cache value"""
        self._cache[key] = value
        self._cache_ts[key] = datetime.now(timezone.utc).timestamp()
        
        # Limit cache size
        if len(self._cache) > 10000:
            # Remove oldest entries
            oldest = sorted(self._cache_ts.items(), key=lambda x: x[1])[:1000]
            for k, _ in oldest:
                self._cache.pop(k, None)
                self._cache_ts.pop(k, None)
    
    def clear_cache(self):
        """Clear resolver cache"""
        self._cache.clear()
        self._cache_ts.clear()
