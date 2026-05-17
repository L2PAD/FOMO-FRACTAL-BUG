"""
Asset Registry Data Models
==========================

Pydantic models for the Unified Asset Registry.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AssetType(str, Enum):
    """Type of asset"""
    TOKEN = "token"
    COIN = "coin"
    STABLECOIN = "stablecoin"
    WRAPPED = "wrapped"
    LP_TOKEN = "lp_token"
    NFT = "nft"


class AssetStatus(str, Enum):
    """Asset status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class MarketType(str, Enum):
    """Type of market"""
    SPOT = "spot"
    PERP = "perp"
    FUTURES = "futures"
    OPTIONS = "options"


# ═══════════════════════════════════════════════════════════════
# CORE ASSET MODEL
# ═══════════════════════════════════════════════════════════════

class Asset(BaseModel):
    """
    Core asset in the Unified Asset Registry.
    This is the canonical representation of any token/coin.
    """
    id: str = Field(..., description="Canonical asset ID (e.g., asset_btc)")
    canonical_symbol: str = Field(..., description="Canonical symbol (e.g., BTC)")
    canonical_name: str = Field(..., description="Canonical name (e.g., Bitcoin)")
    asset_type: AssetType = Field(default=AssetType.TOKEN)
    
    # Links to other entities
    project_id: Optional[str] = Field(None, description="Link to project")
    token_id: Optional[str] = Field(None, description="Link to token details")
    
    # Metadata
    logo: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    
    # Status
    status: AssetStatus = Field(default=AssetStatus.ACTIVE)
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())


class AssetCreate(BaseModel):
    """Schema for creating new asset"""
    canonical_symbol: str
    canonical_name: str
    asset_type: AssetType = AssetType.TOKEN
    project_id: Optional[str] = None
    token_id: Optional[str] = None
    logo: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# EXTERNAL ID MAPPING
# ═══════════════════════════════════════════════════════════════

class AssetExternalId(BaseModel):
    """
    Maps external source identifiers to canonical asset_id.
    
    Example:
    - asset_id: asset_btc
    - source: coingecko
    - external_id: bitcoin
    - external_symbol: btc
    """
    id: str = Field(..., description="Unique mapping ID")
    asset_id: str = Field(..., description="Canonical asset ID")
    
    # Source info
    source: str = Field(..., description="Source name (coingecko, coinmarketcap, etc.)")
    external_id: str = Field(..., description="ID in external source")
    external_symbol: Optional[str] = Field(None, description="Symbol in external source")
    external_name: Optional[str] = Field(None, description="Name in external source")
    
    # Chain-specific (for tokens)
    chain: Optional[str] = Field(None, description="Blockchain (ethereum, solana, etc.)")
    contract: Optional[str] = Field(None, description="Token contract address")
    
    # Metadata
    is_primary: bool = Field(default=False, description="Primary mapping for this source")
    created_at: datetime = Field(default_factory=lambda: datetime.now())


class AssetExternalIdCreate(BaseModel):
    """Schema for adding external ID mapping"""
    asset_id: Optional[str] = None
    source: str
    external_id: str
    external_symbol: Optional[str] = None
    external_name: Optional[str] = None
    chain: Optional[str] = None
    contract: Optional[str] = None
    is_primary: bool = False


# ═══════════════════════════════════════════════════════════════
# MARKET SYMBOLS (EXCHANGE TICKERS)
# ═══════════════════════════════════════════════════════════════

class AssetMarketSymbol(BaseModel):
    """
    Maps exchange trading pairs to canonical asset_id.
    
    Example:
    - asset_id: asset_btc
    - exchange: binance
    - symbol: BTCUSDT
    - market_type: spot
    - base_asset: BTC
    - quote_asset: USDT
    """
    id: str = Field(..., description="Unique symbol ID")
    asset_id: str = Field(..., description="Canonical asset ID")
    
    # Exchange info
    exchange: str = Field(..., description="Exchange name (binance, coinbase, etc.)")
    symbol: str = Field(..., description="Trading symbol on exchange")
    market_type: MarketType = Field(default=MarketType.SPOT)
    
    # Pair info
    base_asset: str = Field(..., description="Base asset symbol")
    quote_asset: str = Field(..., description="Quote asset symbol")
    
    # Status
    status: AssetStatus = Field(default=AssetStatus.ACTIVE)
    
    # Metadata
    min_qty: Optional[float] = None
    tick_size: Optional[float] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now())


class AssetMarketSymbolCreate(BaseModel):
    """Schema for adding market symbol mapping"""
    asset_id: Optional[str] = None
    exchange: str
    symbol: str
    market_type: MarketType = MarketType.SPOT
    base_asset: str
    quote_asset: str
    min_qty: Optional[float] = None
    tick_size: Optional[float] = None


# ═══════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class AssetProfile(BaseModel):
    """Full asset profile with all linked data"""
    asset: Asset
    external_ids: List[AssetExternalId] = []
    market_symbols: List[AssetMarketSymbol] = []
    project: Optional[dict] = None
    token: Optional[dict] = None


class ResolveResult(BaseModel):
    """Result of asset resolution"""
    query: str
    resolved: bool
    asset_id: Optional[str] = None
    asset: Optional[Asset] = None
    match_type: Optional[str] = None  # exact, symbol, name, contract
    confidence: float = 0.0
    alternatives: List[dict] = []
