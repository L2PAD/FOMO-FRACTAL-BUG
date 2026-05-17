"""
Asset Registry Service
======================

CRUD operations for Unified Asset Registry.
Manages assets, external IDs, and market symbols.
"""

import re
import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import (
    Asset, AssetCreate, AssetStatus, AssetType,
    AssetExternalId, AssetExternalIdCreate,
    AssetMarketSymbol, AssetMarketSymbolCreate,
    MarketType
)

logger = logging.getLogger(__name__)


class AssetRegistry:
    """
    Unified Asset Registry Service.
    Central registry for all assets in the platform.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.assets = db.assets
        self.external_ids = db.asset_external_ids
        self.market_symbols = db.asset_market_symbols
    
    # ═══════════════════════════════════════════════════════════════
    # ASSET CRUD
    # ═══════════════════════════════════════════════════════════════
    
    async def create_asset(self, data: AssetCreate) -> dict:
        """Create new asset"""
        now = datetime.now(timezone.utc)
        
        # Validate canonical_symbol is not empty
        if not data.canonical_symbol or not data.canonical_symbol.strip():
            return {"ok": False, "error": "canonical_symbol is required and cannot be empty"}
        
        # Generate canonical ID
        asset_id = self._generate_asset_id(data.canonical_symbol)
        
        # Check if exists
        existing = await self.assets.find_one({"id": asset_id})
        if existing:
            return {"ok": False, "error": "Asset already exists", "asset_id": asset_id}
        
        doc = {
            "id": asset_id,
            "canonical_symbol": data.canonical_symbol.upper(),
            "canonical_name": data.canonical_name,
            "asset_type": data.asset_type.value if isinstance(data.asset_type, AssetType) else data.asset_type,
            "project_id": data.project_id,
            "token_id": data.token_id,
            "logo": data.logo,
            "description": data.description,
            "website": data.website,
            "status": AssetStatus.ACTIVE.value,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
        await self.assets.insert_one(doc)
        doc.pop("_id", None)
        
        logger.info(f"Created asset: {asset_id}")
        return {"ok": True, "asset_id": asset_id, "asset": doc}
    
    async def get_asset(self, asset_id: str) -> Optional[dict]:
        """Get asset by ID"""
        asset = await self.assets.find_one({"id": asset_id})
        if asset:
            asset.pop("_id", None)
        return asset
    
    async def get_asset_profile(self, asset_id: str) -> Optional[dict]:
        """Get full asset profile with external IDs and market symbols"""
        asset = await self.get_asset(asset_id)
        if not asset:
            return None
        
        # Get external IDs
        external_ids = []
        cursor = self.external_ids.find({"asset_id": asset_id})
        async for ext in cursor:
            ext.pop("_id", None)
            external_ids.append(ext)
        
        # Get market symbols
        market_symbols = []
        cursor = self.market_symbols.find({"asset_id": asset_id})
        async for sym in cursor:
            sym.pop("_id", None)
            market_symbols.append(sym)
        
        # Get linked project
        project = None
        if asset.get("project_id"):
            project = await self.db.intel_projects.find_one(
                {"$or": [
                    {"key": asset["project_id"]},
                    {"slug": asset["project_id"].replace("seed:project:", "")}
                ]},
                {"_id": 0}
            )
        
        return {
            "asset": asset,
            "external_ids": external_ids,
            "market_symbols": market_symbols,
            "project": project,
            "stats": {
                "external_sources": len(set(e["source"] for e in external_ids)),
                "exchanges": len(set(s["exchange"] for s in market_symbols)),
                "trading_pairs": len(market_symbols)
            }
        }
    
    async def update_asset(self, asset_id: str, updates: dict) -> dict:
        """Update asset"""
        now = datetime.now(timezone.utc)
        updates["updated_at"] = now.isoformat()
        
        result = await self.assets.update_one(
            {"id": asset_id},
            {"$set": updates}
        )
        
        if result.modified_count:
            return {"ok": True, "asset_id": asset_id}
        return {"ok": False, "error": "Asset not found"}
    
    async def list_assets(
        self,
        status: Optional[str] = None,
        asset_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> dict:
        """List assets with filters"""
        query = {}
        if status:
            query["status"] = status
        if asset_type:
            query["asset_type"] = asset_type
        
        total = await self.assets.count_documents(query)
        
        assets = []
        cursor = self.assets.find(query, {"_id": 0}).skip(offset).limit(limit)
        async for asset in cursor:
            assets.append(asset)
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "assets": assets
        }
    
    # ═══════════════════════════════════════════════════════════════
    # EXTERNAL ID OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def add_external_id(self, data: AssetExternalIdCreate) -> dict:
        """Add external ID mapping for asset"""
        now = datetime.now(timezone.utc)
        
        # Check if asset exists
        asset = await self.get_asset(data.asset_id)
        if not asset:
            return {"ok": False, "error": "Asset not found"}
        
        # Generate ID
        ext_id = f"{data.asset_id}:{data.source}:{data.external_id}"
        
        # Check if mapping exists
        existing = await self.external_ids.find_one({
            "asset_id": data.asset_id,
            "source": data.source,
            "external_id": data.external_id
        })
        
        if existing:
            return {"ok": False, "error": "Mapping already exists", "id": existing.get("id")}
        
        doc = {
            "id": ext_id,
            "asset_id": data.asset_id,
            "source": data.source.lower(),
            "external_id": data.external_id,
            "external_symbol": data.external_symbol,
            "external_name": data.external_name,
            "chain": data.chain.lower() if data.chain else None,
            "contract": data.contract.lower() if data.contract else None,
            "is_primary": data.is_primary,
            "created_at": now.isoformat()
        }
        
        await self.external_ids.insert_one(doc)
        doc.pop("_id", None)
        
        logger.info(f"Added external ID: {ext_id}")
        return {"ok": True, "id": ext_id, "mapping": doc}
    
    async def get_external_ids(self, asset_id: str) -> List[dict]:
        """Get all external IDs for asset"""
        ids = []
        cursor = self.external_ids.find({"asset_id": asset_id}, {"_id": 0})
        async for ext in cursor:
            ids.append(ext)
        return ids
    
    async def find_by_external_id(self, source: str, external_id: str) -> Optional[dict]:
        """Find asset by external source ID"""
        mapping = await self.external_ids.find_one({
            "source": source.lower(),
            "external_id": external_id
        })
        
        if mapping:
            return await self.get_asset(mapping["asset_id"])
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # MARKET SYMBOL OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def add_market_symbol(self, data: AssetMarketSymbolCreate) -> dict:
        """Add market symbol (exchange trading pair) for asset"""
        now = datetime.now(timezone.utc)
        
        # Check if asset exists
        asset = await self.get_asset(data.asset_id)
        if not asset:
            return {"ok": False, "error": "Asset not found"}
        
        # Generate ID
        sym_id = f"{data.exchange}:{data.symbol}"
        
        # Check if exists
        existing = await self.market_symbols.find_one({
            "exchange": data.exchange.lower(),
            "symbol": data.symbol
        })
        
        if existing:
            return {"ok": False, "error": "Symbol already exists", "id": existing.get("id")}
        
        doc = {
            "id": sym_id,
            "asset_id": data.asset_id,
            "exchange": data.exchange.lower(),
            "symbol": data.symbol,
            "market_type": data.market_type.value if isinstance(data.market_type, MarketType) else data.market_type,
            "base_asset": data.base_asset.upper(),
            "quote_asset": data.quote_asset.upper(),
            "status": AssetStatus.ACTIVE.value,
            "min_qty": data.min_qty,
            "tick_size": data.tick_size,
            "created_at": now.isoformat()
        }
        
        await self.market_symbols.insert_one(doc)
        doc.pop("_id", None)
        
        logger.info(f"Added market symbol: {sym_id}")
        return {"ok": True, "id": sym_id, "symbol": doc}
    
    async def get_market_symbols(
        self, 
        asset_id: str,
        exchange: Optional[str] = None,
        market_type: Optional[str] = None
    ) -> List[dict]:
        """Get market symbols for asset"""
        query = {"asset_id": asset_id}
        if exchange:
            query["exchange"] = exchange.lower()
        if market_type:
            query["market_type"] = market_type
        
        symbols = []
        cursor = self.market_symbols.find(query, {"_id": 0})
        async for sym in cursor:
            symbols.append(sym)
        return symbols
    
    async def find_by_market_symbol(
        self, 
        exchange: str, 
        symbol: str
    ) -> Optional[dict]:
        """Find asset by exchange market symbol"""
        mapping = await self.market_symbols.find_one({
            "exchange": exchange.lower(),
            "symbol": symbol
        })
        
        if mapping:
            return await self.get_asset(mapping["asset_id"])
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # BULK OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def bulk_create_assets(self, assets: List[dict]) -> dict:
        """Create multiple assets at once"""
        created = 0
        errors = []
        
        for asset_data in assets:
            try:
                data = AssetCreate(**asset_data)
                result = await self.create_asset(data)
                if result["ok"]:
                    created += 1
                else:
                    errors.append({"data": asset_data, "error": result.get("error")})
            except Exception as e:
                errors.append({"data": asset_data, "error": str(e)})
        
        return {
            "ok": True,
            "created": created,
            "errors": errors,
            "total": len(assets)
        }
    
    async def sync_from_coingecko(self, coins: List[dict]) -> dict:
        """
        Sync assets from CoinGecko coin list.
        Creates assets and adds external IDs.
        """
        created = 0
        updated = 0
        
        for coin in coins:
            symbol = coin.get("symbol", "").upper()
            name = coin.get("name", "")
            cg_id = coin.get("id", "")
            
            if not symbol or not name or not cg_id:
                continue
            
            asset_id = self._generate_asset_id(symbol)
            
            # Check if exists
            existing = await self.get_asset(asset_id)
            
            if not existing:
                # Create asset
                result = await self.create_asset(AssetCreate(
                    canonical_symbol=symbol,
                    canonical_name=name,
                    asset_type=AssetType.TOKEN,
                    logo=coin.get("image"),
                ))
                if result["ok"]:
                    created += 1
                    asset_id = result["asset_id"]
            else:
                updated += 1
            
            # Add CoinGecko external ID
            await self.add_external_id(AssetExternalIdCreate(
                asset_id=asset_id,
                source="coingecko",
                external_id=cg_id,
                external_symbol=symbol.lower(),
                external_name=name,
                is_primary=True
            ))
        
        return {"ok": True, "created": created, "updated": updated}
    
    async def sync_from_exchange(
        self, 
        exchange: str, 
        instruments: List[dict]
    ) -> dict:
        """
        Sync market symbols from exchange instruments.
        """
        created = 0
        skipped = 0
        
        for inst in instruments:
            symbol = inst.get("symbol", "")
            base = inst.get("base_asset", inst.get("baseAsset", ""))
            quote = inst.get("quote_asset", inst.get("quoteAsset", ""))
            market_type = inst.get("market_type", "spot")
            
            if not symbol or not base:
                skipped += 1
                continue
            
            # Try to find asset
            asset_id = self._generate_asset_id(base)
            asset = await self.get_asset(asset_id)
            
            if not asset:
                # Create minimal asset
                await self.create_asset(AssetCreate(
                    canonical_symbol=base.upper(),
                    canonical_name=base.upper(),
                    asset_type=AssetType.TOKEN
                ))
            
            # Add market symbol
            result = await self.add_market_symbol(AssetMarketSymbolCreate(
                asset_id=asset_id,
                exchange=exchange,
                symbol=symbol,
                market_type=MarketType(market_type) if market_type in [e.value for e in MarketType] else MarketType.SPOT,
                base_asset=base,
                quote_asset=quote or "USDT"
            ))
            
            if result["ok"]:
                created += 1
        
        return {"ok": True, "created": created, "skipped": skipped}
    
    # ═══════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_stats(self) -> dict:
        """Get registry statistics"""
        total_assets = await self.assets.count_documents({})
        active_assets = await self.assets.count_documents({"status": "active"})
        
        total_external_ids = await self.external_ids.count_documents({})
        total_market_symbols = await self.market_symbols.count_documents({})
        
        # Count by source
        sources_pipeline = [
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        sources = {}
        async for doc in self.external_ids.aggregate(sources_pipeline):
            sources[doc["_id"]] = doc["count"]
        
        # Count by exchange
        exchanges_pipeline = [
            {"$group": {"_id": "$exchange", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        exchanges = {}
        async for doc in self.market_symbols.aggregate(exchanges_pipeline):
            exchanges[doc["_id"]] = doc["count"]
        
        return {
            "total_assets": total_assets,
            "active_assets": active_assets,
            "external_ids": total_external_ids,
            "market_symbols": total_market_symbols,
            "sources": sources,
            "exchanges": exchanges
        }
    
    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    def _generate_asset_id(self, symbol: str) -> str:
        """Generate canonical asset ID from symbol"""
        clean = re.sub(r'[^a-zA-Z0-9]', '', symbol.lower())
        return f"asset_{clean}"
