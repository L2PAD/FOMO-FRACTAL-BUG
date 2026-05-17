"""
Field Ownership & Provider Capability Map

Core principle: Each data field has ONE canonical owner.
This prevents data conflicts and ensures single source of truth.

Rules:
- Market data NEVER comes from intel sources
- Intel data NEVER comes from exchanges
- Each field knows its owner, fallbacks, and forbidden sources
"""

from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field
from dataclasses import dataclass


class DataTree(str, Enum):
    """Two-tree architecture"""
    EXCHANGE = "exchange"  # Market data only
    INTEL = "intel"        # Intelligence data only


class FieldOwnership(BaseModel):
    """Defines ownership rules for a data field"""
    field: str
    tree: DataTree
    owner: str                           # Primary owner
    fallbacks: List[str] = Field(default_factory=list)  # Fallback sources in order
    forbidden: List[str] = Field(default_factory=list)  # Sources that cannot provide this
    refresh_interval: int = 3600         # Seconds
    priority: int = 1                    # 1=highest


class ProviderCapability(BaseModel):
    """Defines what a provider can supply"""
    provider_id: str
    name: str
    tree: DataTree
    fields: List[str]
    reliability_score: float = Field(0.0, ge=0, le=1)
    freshness: str = "daily"  # realtime, hourly, daily, weekly
    rate_limit: int = 100     # requests per minute
    requires_auth: bool = False
    is_active: bool = True


# =============================================================================
# FIELD OWNERSHIP MAP
# =============================================================================

FIELD_OWNERSHIP_MAP: Dict[str, FieldOwnership] = {
    # =========================================================================
    # EXCHANGE TREE - Market Data
    # =========================================================================
    "spot_price": FieldOwnership(
        field="spot_price",
        tree=DataTree.EXCHANGE,
        owner="binance",
        fallbacks=["bybit", "okx", "coinbase"],
        forbidden=["cryptorank", "rootdata", "messari", "defillama"],
        refresh_interval=10
    ),
    "candles": FieldOwnership(
        field="candles",
        tree=DataTree.EXCHANGE,
        owner="binance",
        fallbacks=["bybit", "okx"],
        forbidden=["intel_tree"],
        refresh_interval=60
    ),
    "volume_24h": FieldOwnership(
        field="volume_24h",
        tree=DataTree.EXCHANGE,
        owner="binance",
        fallbacks=["coingecko", "coinmarketcap"],
        refresh_interval=300
    ),
    "open_interest": FieldOwnership(
        field="open_interest",
        tree=DataTree.EXCHANGE,
        owner="binance",
        fallbacks=["bybit", "okx", "hyperliquid"],
        forbidden=["intel_tree"],
        refresh_interval=60
    ),
    "funding_rate": FieldOwnership(
        field="funding_rate",
        tree=DataTree.EXCHANGE,
        owner="binance",
        fallbacks=["bybit", "hyperliquid"],
        refresh_interval=60
    ),
    "liquidations": FieldOwnership(
        field="liquidations",
        tree=DataTree.EXCHANGE,
        owner="binance",
        fallbacks=["bybit"],
        refresh_interval=30
    ),
    "market_pairs": FieldOwnership(
        field="market_pairs",
        tree=DataTree.EXCHANGE,
        owner="binance",
        fallbacks=["coingecko"],
        refresh_interval=3600
    ),
    "exchange_listings": FieldOwnership(
        field="exchange_listings",
        tree=DataTree.EXCHANGE,
        owner="coingecko",
        fallbacks=["coinmarketcap"],
        refresh_interval=3600
    ),
    
    # =========================================================================
    # INTEL TREE - Project Data
    # =========================================================================
    "project_profile": FieldOwnership(
        field="project_profile",
        tree=DataTree.INTEL,
        owner="messari",
        fallbacks=["cryptorank", "rootdata", "project_site"],
        forbidden=["binance", "bybit", "okx"],
        refresh_interval=86400
    ),
    "project_description": FieldOwnership(
        field="project_description",
        tree=DataTree.INTEL,
        owner="messari",
        fallbacks=["rootdata", "project_site"],
        refresh_interval=86400
    ),
    "tvl": FieldOwnership(
        field="tvl",
        tree=DataTree.INTEL,
        owner="defillama",
        fallbacks=["coingecko"],
        forbidden=["exchange_tree"],
        refresh_interval=3600
    ),
    "tokenomics": FieldOwnership(
        field="tokenomics",
        tree=DataTree.INTEL,
        owner="cryptorank",
        fallbacks=["rootdata", "messari"],
        refresh_interval=86400
    ),
    "circulating_supply": FieldOwnership(
        field="circulating_supply",
        tree=DataTree.INTEL,
        owner="coingecko",
        fallbacks=["coinmarketcap", "cryptorank"],
        refresh_interval=3600
    ),
    
    # =========================================================================
    # INTEL TREE - Funding & Investment
    # =========================================================================
    "funding_rounds": FieldOwnership(
        field="funding_rounds",
        tree=DataTree.INTEL,
        owner="cryptorank",
        fallbacks=["rootdata", "messari"],
        forbidden=["exchange_tree"],
        refresh_interval=86400
    ),
    "investors": FieldOwnership(
        field="investors",
        tree=DataTree.INTEL,
        owner="cryptorank",
        fallbacks=["rootdata"],
        refresh_interval=86400
    ),
    "fund_portfolio": FieldOwnership(
        field="fund_portfolio",
        tree=DataTree.INTEL,
        owner="rootdata",
        fallbacks=["cryptorank"],
        refresh_interval=86400
    ),
    
    # =========================================================================
    # INTEL TREE - Team & People
    # =========================================================================
    "team_members": FieldOwnership(
        field="team_members",
        tree=DataTree.INTEL,
        owner="rootdata",
        fallbacks=["cryptorank", "linkedin"],
        refresh_interval=86400
    ),
    "team_positions": FieldOwnership(
        field="team_positions",
        tree=DataTree.INTEL,
        owner="rootdata",
        fallbacks=["linkedin"],
        refresh_interval=86400
    ),
    "advisors": FieldOwnership(
        field="advisors",
        tree=DataTree.INTEL,
        owner="rootdata",
        fallbacks=["cryptorank"],
        refresh_interval=86400
    ),
    
    # =========================================================================
    # INTEL TREE - Token Events
    # =========================================================================
    "unlock_schedule": FieldOwnership(
        field="unlock_schedule",
        tree=DataTree.INTEL,
        owner="tokenunlocks",
        fallbacks=["cryptorank"],
        forbidden=["exchange_tree"],
        refresh_interval=3600
    ),
    "upcoming_unlocks": FieldOwnership(
        field="upcoming_unlocks",
        tree=DataTree.INTEL,
        owner="tokenunlocks",
        refresh_interval=3600
    ),
    "airdrop_info": FieldOwnership(
        field="airdrop_info",
        tree=DataTree.INTEL,
        owner="dropsearn",
        fallbacks=["airdropalert"],
        refresh_interval=3600
    ),
    "ico_sale_info": FieldOwnership(
        field="ico_sale_info",
        tree=DataTree.INTEL,
        owner="icodrops",
        fallbacks=["cryptorank"],
        refresh_interval=3600
    ),
    
    # =========================================================================
    # INTEL TREE - DeFi & Protocol
    # =========================================================================
    "protocol_tvl": FieldOwnership(
        field="protocol_tvl",
        tree=DataTree.INTEL,
        owner="defillama",
        forbidden=["exchange_tree"],
        refresh_interval=3600
    ),
    "protocol_fees": FieldOwnership(
        field="protocol_fees",
        tree=DataTree.INTEL,
        owner="defillama",
        refresh_interval=3600
    ),
    "protocol_revenue": FieldOwnership(
        field="protocol_revenue",
        tree=DataTree.INTEL,
        owner="defillama",
        refresh_interval=3600
    ),
    "dapp_usage": FieldOwnership(
        field="dapp_usage",
        tree=DataTree.INTEL,
        owner="dappradar",
        refresh_interval=3600
    ),
    
    # =========================================================================
    # INTEL TREE - Development
    # =========================================================================
    "github_activity": FieldOwnership(
        field="github_activity",
        tree=DataTree.INTEL,
        owner="github",
        refresh_interval=3600
    ),
    "developer_count": FieldOwnership(
        field="developer_count",
        tree=DataTree.INTEL,
        owner="github",
        fallbacks=["cryptorank"],
        refresh_interval=86400
    ),
    "code_commits": FieldOwnership(
        field="code_commits",
        tree=DataTree.INTEL,
        owner="github",
        refresh_interval=3600
    ),
}


# =============================================================================
# PROVIDER CAPABILITIES
# =============================================================================

PROVIDER_CAPABILITIES: Dict[str, ProviderCapability] = {
    # =========================================================================
    # EXCHANGE TREE PROVIDERS
    # =========================================================================
    "binance": ProviderCapability(
        provider_id="binance",
        name="Binance",
        tree=DataTree.EXCHANGE,
        fields=["spot_price", "candles", "volume_24h", "open_interest", 
                "funding_rate", "liquidations", "market_pairs"],
        reliability_score=0.99,
        freshness="realtime",
        rate_limit=1200
    ),
    "bybit": ProviderCapability(
        provider_id="bybit",
        name="Bybit",
        tree=DataTree.EXCHANGE,
        fields=["spot_price", "candles", "open_interest", "funding_rate", "liquidations"],
        reliability_score=0.97,
        freshness="realtime",
        rate_limit=600
    ),
    "okx": ProviderCapability(
        provider_id="okx",
        name="OKX",
        tree=DataTree.EXCHANGE,
        fields=["spot_price", "candles", "open_interest", "funding_rate"],
        reliability_score=0.96,
        freshness="realtime",
        rate_limit=600
    ),
    "coinbase": ProviderCapability(
        provider_id="coinbase",
        name="Coinbase",
        tree=DataTree.EXCHANGE,
        fields=["spot_price", "candles", "volume_24h"],
        reliability_score=0.98,
        freshness="realtime",
        rate_limit=300
    ),
    "hyperliquid": ProviderCapability(
        provider_id="hyperliquid",
        name="Hyperliquid",
        tree=DataTree.EXCHANGE,
        fields=["open_interest", "funding_rate", "liquidations"],
        reliability_score=0.94,
        freshness="realtime",
        rate_limit=300
    ),
    
    # =========================================================================
    # INTEL TREE PROVIDERS
    # =========================================================================
    "cryptorank": ProviderCapability(
        provider_id="cryptorank",
        name="CryptoRank",
        tree=DataTree.INTEL,
        fields=["funding_rounds", "investors", "tokenomics", "team_members", 
                "project_profile", "ico_sale_info"],
        reliability_score=0.95,
        freshness="daily",
        rate_limit=100
    ),
    "rootdata": ProviderCapability(
        provider_id="rootdata",
        name="RootData",
        tree=DataTree.INTEL,
        fields=["funding_rounds", "investors", "team_members", "team_positions",
                "advisors", "fund_portfolio", "project_profile"],
        reliability_score=0.93,
        freshness="daily",
        rate_limit=60
    ),
    "defillama": ProviderCapability(
        provider_id="defillama",
        name="DefiLlama",
        tree=DataTree.INTEL,
        fields=["tvl", "protocol_tvl", "protocol_fees", "protocol_revenue"],
        reliability_score=0.97,
        freshness="hourly",
        rate_limit=300
    ),
    "messari": ProviderCapability(
        provider_id="messari",
        name="Messari",
        tree=DataTree.INTEL,
        fields=["project_profile", "project_description", "tokenomics"],
        reliability_score=0.92,
        freshness="daily",
        rate_limit=30,
        requires_auth=True
    ),
    "tokenunlocks": ProviderCapability(
        provider_id="tokenunlocks",
        name="TokenUnlocks",
        tree=DataTree.INTEL,
        fields=["unlock_schedule", "upcoming_unlocks"],
        reliability_score=0.96,
        freshness="hourly",
        rate_limit=60
    ),
    "coingecko": ProviderCapability(
        provider_id="coingecko",
        name="CoinGecko",
        tree=DataTree.INTEL,
        fields=["circulating_supply", "volume_24h", "market_pairs", "exchange_listings", "tvl"],
        reliability_score=0.94,
        freshness="hourly",
        rate_limit=30
    ),
    "coinmarketcap": ProviderCapability(
        provider_id="coinmarketcap",
        name="CoinMarketCap",
        tree=DataTree.INTEL,
        fields=["circulating_supply", "volume_24h", "exchange_listings"],
        reliability_score=0.93,
        freshness="hourly",
        rate_limit=30,
        requires_auth=True
    ),
    "dropsearn": ProviderCapability(
        provider_id="dropsearn",
        name="DropsEarn",
        tree=DataTree.INTEL,
        fields=["airdrop_info"],
        reliability_score=0.85,
        freshness="daily",
        rate_limit=30
    ),
    "icodrops": ProviderCapability(
        provider_id="icodrops",
        name="ICO Drops",
        tree=DataTree.INTEL,
        fields=["ico_sale_info"],
        reliability_score=0.88,
        freshness="daily",
        rate_limit=30
    ),
    "dappradar": ProviderCapability(
        provider_id="dappradar",
        name="DappRadar",
        tree=DataTree.INTEL,
        fields=["dapp_usage"],
        reliability_score=0.90,
        freshness="hourly",
        rate_limit=60
    ),
    "github": ProviderCapability(
        provider_id="github",
        name="GitHub",
        tree=DataTree.INTEL,
        fields=["github_activity", "developer_count", "code_commits"],
        reliability_score=0.99,
        freshness="hourly",
        rate_limit=60,
        requires_auth=True
    ),
}


class OwnershipService:
    """
    Service for resolving field ownership and provider selection
    """
    
    def __init__(self):
        self.ownership_map = FIELD_OWNERSHIP_MAP
        self.provider_map = PROVIDER_CAPABILITIES
    
    def get_owner(self, field: str) -> Optional[str]:
        """Get canonical owner for a field"""
        ownership = self.ownership_map.get(field)
        return ownership.owner if ownership else None
    
    def get_fallbacks(self, field: str) -> List[str]:
        """Get fallback providers for a field"""
        ownership = self.ownership_map.get(field)
        return ownership.fallbacks if ownership else []
    
    def is_forbidden(self, field: str, provider: str) -> bool:
        """Check if provider is forbidden for this field"""
        ownership = self.ownership_map.get(field)
        if not ownership:
            return False
        return provider in ownership.forbidden
    
    def get_best_provider(
        self, 
        field: str, 
        available_providers: List[str]
    ) -> Optional[str]:
        """
        Get best available provider for a field
        Respects ownership hierarchy and forbidden list
        """
        ownership = self.ownership_map.get(field)
        if not ownership:
            return available_providers[0] if available_providers else None
        
        # Filter out forbidden providers
        valid_providers = [
            p for p in available_providers 
            if p not in ownership.forbidden
        ]
        
        # Check owner first
        if ownership.owner in valid_providers:
            return ownership.owner
        
        # Check fallbacks in order
        for fallback in ownership.fallbacks:
            if fallback in valid_providers:
                return fallback
        
        return valid_providers[0] if valid_providers else None
    
    def get_tree(self, field: str) -> Optional[DataTree]:
        """Get which tree a field belongs to"""
        ownership = self.ownership_map.get(field)
        return ownership.tree if ownership else None
    
    def validate_source(self, field: str, provider: str) -> bool:
        """
        Validate that provider can supply this field
        Returns False if:
        - Provider is forbidden
        - Provider is from wrong tree
        - Provider doesn't have capability
        """
        ownership = self.ownership_map.get(field)
        capability = self.provider_map.get(provider)
        
        if not ownership or not capability:
            return False
        
        # Check tree match
        if ownership.tree != capability.tree:
            return False
        
        # Check forbidden
        if provider in ownership.forbidden:
            return False
        
        # Check capability
        if field not in capability.fields:
            return False
        
        return True
    
    def get_provider_fields(self, provider: str) -> List[str]:
        """Get all fields a provider can supply"""
        capability = self.provider_map.get(provider)
        return capability.fields if capability else []
    
    def get_field_refresh_interval(self, field: str) -> int:
        """Get refresh interval for a field in seconds"""
        ownership = self.ownership_map.get(field)
        return ownership.refresh_interval if ownership else 3600


# Singleton instance
ownership_service = OwnershipService()
