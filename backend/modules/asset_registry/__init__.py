"""
Unified Asset Registry Module
============================

Central registry for all assets/tokens across the platform.
Links external sources (CoinGecko, CoinMarketCap, exchanges) to canonical asset IDs.

Collections:
- assets: Core asset registry
- asset_external_ids: External source mappings
- asset_market_symbols: Exchange trading pairs

Services:
- AssetResolver: Resolves any identifier to canonical asset_id
- AssetRegistry: CRUD operations for assets
"""

from .models import Asset, AssetExternalId, AssetMarketSymbol
from .resolver import AssetResolver
from .registry import AssetRegistry
from .api.routes import router as asset_router

__all__ = [
    'Asset',
    'AssetExternalId', 
    'AssetMarketSymbol',
    'AssetResolver',
    'AssetRegistry',
    'asset_router'
]
