"""
Provider Gateway Data Models
============================

Models for provider registry, instances, and capabilities.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class AuthType(str, Enum):
    """Provider authentication type"""
    NONE = "none"           # Public API, no auth needed
    API_KEY = "api_key"     # Requires API key
    OAUTH = "oauth"         # OAuth authentication
    BEARER = "bearer"       # Bearer token


class ProviderStatus(str, Enum):
    """Provider operational status"""
    ACTIVE = "active"
    DEGRADED = "degraded"
    DOWN = "down"
    DISABLED = "disabled"
    RATE_LIMITED = "rate_limited"


class ProviderCategory(str, Enum):
    """Provider data category"""
    MARKET_DATA = "market_data"      # Price, volume, marketcap
    DEFI = "defi"                    # TVL, yields, protocols
    DERIVATIVES = "derivatives"      # Futures, funding, liquidations
    DEX = "dex"                      # DEX pairs, liquidity
    RESEARCH = "research"            # Project profiles, reports
    INTEL = "intel"                  # Funding rounds, activities
    ONCHAIN = "onchain"              # Chain analytics


class ProviderCapability(str, Enum):
    """Specific capabilities a provider offers"""
    # Market
    ASSET_PRICE = "asset_price"
    ASSET_MARKETCAP = "asset_marketcap"
    ASSET_VOLUME = "asset_volume"
    CANDLES = "candles"
    GLOBAL_METRICS = "global_metrics"
    TRENDING = "trending"
    
    # DeFi
    TVL = "tvl"
    YIELDS = "yields"
    BRIDGES = "bridges"
    STABLECOINS = "stablecoins"
    AIRDROPS = "airdrops"
    PROTOCOLS = "protocols"
    
    # Derivatives
    FUNDING_RATES = "funding_rates"
    OPEN_INTEREST = "open_interest"
    LIQUIDATIONS = "liquidations"
    FUTURES = "futures"
    
    # DEX
    DEX_PAIRS = "dex_pairs"
    DEX_VOLUME = "dex_volume"
    NEW_TOKENS = "new_tokens"
    LIQUIDITY_POOLS = "liquidity_pools"
    
    # Research
    PROJECT_PROFILE = "project_profile"
    TOKEN_METRICS = "token_metrics"
    NEWS = "news"
    
    # Intel
    FUNDING_ROUNDS = "funding_rounds"
    ACTIVITIES = "activities"
    UNLOCKS = "unlocks"
    
    # Onchain
    CHAIN_ANALYTICS = "chain_analytics"
    DAU = "dau"
    TRANSACTIONS = "transactions"


# ═══════════════════════════════════════════════════════════════
# PROVIDER MODEL
# ═══════════════════════════════════════════════════════════════

class Provider(BaseModel):
    """
    External data provider configuration.
    
    Example:
    - id: coingecko
    - name: CoinGecko
    - endpoint: https://api.coingecko.com
    - auth_type: api_key
    - category: market_data
    """
    id: str = Field(..., description="Unique provider ID")
    name: str = Field(..., description="Display name")
    endpoint: str = Field(..., description="Base API endpoint")
    
    # Authentication
    auth_type: AuthType = Field(default=AuthType.NONE)
    requires_api_key: bool = Field(default=False)
    api_key_header: Optional[str] = Field(None, description="Header name for API key")
    
    # Category and capabilities
    category: ProviderCategory = Field(default=ProviderCategory.MARKET_DATA)
    capabilities: List[ProviderCapability] = Field(default=[])
    
    # Rate limiting
    rate_limit: int = Field(default=30, description="Requests per minute")
    rate_limit_window: str = Field(default="minute", description="Rate limit window (minute/day)")
    
    # Status
    status: ProviderStatus = Field(default=ProviderStatus.ACTIVE)
    priority: int = Field(default=1, description="Failover priority (1=highest)")
    
    # Metadata
    website: Optional[str] = None
    docs_url: Optional[str] = None
    description: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())


class ProviderCreate(BaseModel):
    """Schema for creating new provider"""
    id: str
    name: str
    endpoint: str
    auth_type: AuthType = AuthType.NONE
    requires_api_key: bool = False
    api_key_header: Optional[str] = None
    category: ProviderCategory = ProviderCategory.MARKET_DATA
    capabilities: List[str] = []
    rate_limit: int = 30
    rate_limit_window: str = "minute"
    priority: int = 1
    website: Optional[str] = None
    docs_url: Optional[str] = None
    description: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# PROVIDER INSTANCE MODEL
# ═══════════════════════════════════════════════════════════════

class ProviderInstance(BaseModel):
    """
    Provider instance with specific proxy and API key binding.
    Multiple instances per provider for failover.
    
    Example:
    - provider_id: coingecko
    - proxy_id: proxy_1
    - api_key_id: key_coingecko_1
    """
    id: str = Field(..., description="Instance ID")
    provider_id: str = Field(..., description="Parent provider ID")
    
    # Bindings
    proxy_id: Optional[str] = Field(None, description="Bound proxy ID")
    api_key_id: Optional[str] = Field(None, description="Bound API key ID")
    
    # Status
    status: ProviderStatus = Field(default=ProviderStatus.ACTIVE)
    
    # Health metrics
    latency_ms: Optional[float] = None
    success_count: int = Field(default=0)
    error_count: int = Field(default=0)
    last_error: Optional[str] = None
    last_check: Optional[datetime] = None
    last_success: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now())


class ProviderInstanceCreate(BaseModel):
    """Schema for creating provider instance"""
    provider_id: str
    proxy_id: Optional[str] = None
    api_key_id: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK MODELS
# ═══════════════════════════════════════════════════════════════

class HealthCheckResult(BaseModel):
    """Result of provider health check"""
    provider_id: str
    instance_id: Optional[str] = None
    status: ProviderStatus
    latency_ms: float
    success: bool
    error: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now())


class ProviderHealth(BaseModel):
    """Aggregated provider health status"""
    provider_id: str
    provider_name: str
    status: ProviderStatus
    instances_total: int
    instances_healthy: int
    avg_latency_ms: float
    error_rate: float
    last_check: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class ProviderProfile(BaseModel):
    """Full provider profile with instances"""
    provider: Provider
    instances: List[ProviderInstance] = []
    health: Optional[ProviderHealth] = None


class GatewayStats(BaseModel):
    """Provider Gateway statistics"""
    total_providers: int
    active_providers: int
    api_key_providers: int
    public_providers: int
    total_instances: int
    healthy_instances: int
    providers_by_category: Dict[str, int]
    capabilities_count: Dict[str, int]
