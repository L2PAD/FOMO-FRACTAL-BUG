"""
Field Ownership Map
===================
Defines which source OWNS each field, fallback sources, and forbidden sources.

Two independent data trees:
1. EXCHANGE TREE - Market data (prices, candles, volume, OI, funding rates)
2. INTEL TREE - Intelligence data (funding, investors, teams, tokenomics, activities)

Rules:
- Each field has ONE owner source
- Fallback sources used if owner fails
- Forbidden sources NEVER used for that field
- System uses owner first, then fallback by weight order
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass


class DataTree(str, Enum):
    """Two independent data trees"""
    EXCHANGE = "exchange"  # Market data from exchanges
    INTEL = "intel"        # Intelligence data from discovery sources


@dataclass
class FieldOwnership:
    """Ownership definition for a single field"""
    field: str
    owner: str
    fallback: List[str]
    forbidden: List[str]
    tree: DataTree
    weight: float = 1.0
    description: str = ""


# ═══════════════════════════════════════════════════════════════
# EXCHANGE TREE FIELDS (Market Data)
# Sources: Binance, Bybit, Hyperliquid, Coinbase, OKX, etc.
# ═══════════════════════════════════════════════════════════════

EXCHANGE_FIELDS = [
    # ─────────────────────────────────────────────────────────────
    # PRICE / OHLCV
    # ─────────────────────────────────────────────────────────────
    FieldOwnership(
        field="spot_price",
        owner="exchange_providers",
        fallback=["coingecko", "coinmarketcap"],
        forbidden=["dropstab", "cryptorank", "messari", "rootdata", "defillama"],
        tree=DataTree.EXCHANGE,
        weight=1.0,
        description="Spot price - only from exchanges"
    ),
    FieldOwnership(
        field="ohlcv",
        owner="exchange_providers",
        fallback=["coingecko"],
        forbidden=["dropstab", "cryptorank", "messari", "defillama", "rootdata"],
        tree=DataTree.EXCHANGE,
        weight=1.0,
        description="OHLCV candles - only from exchanges"
    ),
    FieldOwnership(
        field="candles",
        owner="exchange_providers",
        fallback=["coingecko"],
        forbidden=["dropstab", "cryptorank", "messari", "defillama", "rootdata"],
        tree=DataTree.EXCHANGE,
        weight=1.0,
        description="Candlestick data - only from exchanges"
    ),
    
    # ─────────────────────────────────────────────────────────────
    # VOLUME / LIQUIDITY
    # ─────────────────────────────────────────────────────────────
    FieldOwnership(
        field="spot_volume",
        owner="exchange_providers",
        fallback=["coingecko", "coinmarketcap"],
        forbidden=["dropstab", "cryptorank", "messari", "rootdata"],
        tree=DataTree.EXCHANGE,
        weight=1.0,
        description="Spot trading volume"
    ),
    FieldOwnership(
        field="pair_volume",
        owner="exchange_providers",
        fallback=["coingecko", "coinmarketcap"],
        forbidden=["dropstab", "cryptorank", "messari", "rootdata"],
        tree=DataTree.EXCHANGE,
        weight=1.0,
        description="Trading pair volume"
    ),
    
    # ─────────────────────────────────────────────────────────────
    # DERIVATIVES
    # ─────────────────────────────────────────────────────────────
    FieldOwnership(
        field="open_interest",
        owner="exchange_providers",
        fallback=[],
        forbidden=["coingecko", "coinmarketcap", "dropstab", "cryptorank", "messari"],
        tree=DataTree.EXCHANGE,
        weight=1.0,
        description="Open Interest - ONLY from exchanges"
    ),
    FieldOwnership(
        field="funding_rate",
        owner="exchange_providers",
        fallback=[],
        forbidden=["coingecko", "coinmarketcap", "cryptorank", "dropstab", "messari"],
        tree=DataTree.EXCHANGE,
        weight=1.0,
        description="Funding rates - ONLY from exchanges"
    ),
    FieldOwnership(
        field="liquidations",
        owner="exchange_providers",
        fallback=[],
        forbidden=["coingecko", "coinmarketcap", "dropstab", "cryptorank", "messari"],
        tree=DataTree.EXCHANGE,
        weight=1.0,
        description="Liquidation data - ONLY from exchanges"
    ),
    
    # ─────────────────────────────────────────────────────────────
    # MARKETS / PAIRS
    # ─────────────────────────────────────────────────────────────
    FieldOwnership(
        field="exchange_markets",
        owner="exchange_providers",
        fallback=["coingecko", "coinmarketcap"],
        forbidden=["dropstab", "cryptorank", "messari"],
        tree=DataTree.EXCHANGE,
        weight=1.0,
        description="Markets where asset trades"
    ),
    FieldOwnership(
        field="trading_pairs",
        owner="exchange_providers",
        fallback=["coingecko", "coinmarketcap"],
        forbidden=["dropstab", "cryptorank", "messari"],
        tree=DataTree.EXCHANGE,
        weight=1.0,
        description="Trading pairs available"
    ),
    FieldOwnership(
        field="listed_on",
        owner="exchange_providers",
        fallback=["coingecko", "coinmarketcap"],
        forbidden=["dropstab", "cryptorank", "messari"],
        tree=DataTree.EXCHANGE,
        weight=1.0,
        description="Exchange listings"
    ),
]


# ═══════════════════════════════════════════════════════════════
# INTEL TREE FIELDS (Intelligence Data)
# ═══════════════════════════════════════════════════════════════

INTEL_FIELDS = [
    # ─────────────────────────────────────────────────────────────
    # MARKET AGGREGATES (derived, not raw exchange data)
    # ─────────────────────────────────────────────────────────────
    FieldOwnership(
        field="market_cap",
        owner="coingecko",
        fallback=["coinmarketcap"],
        forbidden=["dropstab", "cryptorank", "messari", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.88,
        description="Market cap - aggregated metric"
    ),
    FieldOwnership(
        field="fdv",
        owner="coingecko",
        fallback=["coinmarketcap", "dropstab"],
        forbidden=["exchange_providers", "cryptorank", "messari"],
        tree=DataTree.INTEL,
        weight=0.88,
        description="Fully Diluted Valuation"
    ),
    FieldOwnership(
        field="circulating_supply",
        owner="coingecko",
        fallback=["coinmarketcap", "dropstab"],
        forbidden=["exchange_providers", "cryptorank"],
        tree=DataTree.INTEL,
        weight=0.88,
        description="Circulating token supply"
    ),
    FieldOwnership(
        field="total_supply",
        owner="coingecko",
        fallback=["coinmarketcap", "dropstab", "messari"],
        forbidden=["exchange_providers", "cryptorank"],
        tree=DataTree.INTEL,
        weight=0.88,
        description="Total token supply"
    ),
    FieldOwnership(
        field="max_supply",
        owner="coingecko",
        fallback=["coinmarketcap", "dropstab", "messari"],
        forbidden=["exchange_providers", "cryptorank"],
        tree=DataTree.INTEL,
        weight=0.88,
        description="Maximum token supply"
    ),
    
    # ─────────────────────────────────────────────────────────────
    # TOKENOMICS / UNLOCKS
    # ─────────────────────────────────────────────────────────────
    FieldOwnership(
        field="unlock_schedule",
        owner="tokenunlocks",
        fallback=["dropstab", "defillama"],
        forbidden=["coingecko", "coinmarketcap", "exchange_providers", "cryptorank", "messari"],
        tree=DataTree.INTEL,
        weight=0.93,
        description="Token unlock schedule"
    ),
    FieldOwnership(
        field="unlock_amount_usd",
        owner="tokenunlocks",
        fallback=["dropstab", "defillama"],
        forbidden=["coingecko", "coinmarketcap", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.93,
        description="USD value of upcoming unlock"
    ),
    FieldOwnership(
        field="unlock_percent",
        owner="tokenunlocks",
        fallback=["dropstab", "defillama"],
        forbidden=["coingecko", "coinmarketcap", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.93,
        description="Percentage of supply unlocking"
    ),
    FieldOwnership(
        field="token_allocations",
        owner="dropstab",
        fallback=["messari", "icodrops"],
        forbidden=["coingecko", "exchange_providers", "cryptorank"],
        tree=DataTree.INTEL,
        weight=0.85,
        description="Token allocation breakdown"
    ),
    FieldOwnership(
        field="vesting_model",
        owner="dropstab",
        fallback=["messari", "tokenunlocks"],
        forbidden=["coingecko", "coinmarketcap", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.85,
        description="Vesting schedule model"
    ),
    FieldOwnership(
        field="insider_supply",
        owner="dropstab",
        fallback=["messari", "tokenunlocks"],
        forbidden=["coingecko", "coinmarketcap", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.85,
        description="Insider/team token holdings"
    ),
    FieldOwnership(
        field="sell_pressure",
        owner="dropstab",
        fallback=["messari", "tokenunlocks"],
        forbidden=["coingecko", "coinmarketcap", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.85,
        description="Calculated sell pressure"
    ),
    
    # ─────────────────────────────────────────────────────────────
    # FUNDING / INVESTORS / FUNDS
    # ─────────────────────────────────────────────────────────────
    FieldOwnership(
        field="funding_rounds",
        owner="cryptorank",
        fallback=["rootdata", "dropstab"],
        forbidden=["coingecko", "coinmarketcap", "exchange_providers", "defillama"],
        tree=DataTree.INTEL,
        weight=0.95,
        description="Project funding rounds"
    ),
    FieldOwnership(
        field="funding_amount",
        owner="cryptorank",
        fallback=["rootdata", "dropstab"],
        forbidden=["coingecko", "coinmarketcap", "messari"],
        tree=DataTree.INTEL,
        weight=0.95,
        description="Total funding raised"
    ),
    FieldOwnership(
        field="investor_list",
        owner="cryptorank",
        fallback=["rootdata", "dropstab"],
        forbidden=["coingecko", "coinmarketcap", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.95,
        description="List of investors"
    ),
    FieldOwnership(
        field="lead_investor",
        owner="cryptorank",
        fallback=["rootdata"],
        forbidden=["dropstab", "coingecko"],
        tree=DataTree.INTEL,
        weight=0.95,
        description="Lead investor in round"
    ),
    FieldOwnership(
        field="fund_profile",
        owner="rootdata",
        fallback=["cryptorank"],
        forbidden=["coingecko", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.90,
        description="VC/Fund profile"
    ),
    FieldOwnership(
        field="fund_portfolio",
        owner="rootdata",
        fallback=["cryptorank"],
        forbidden=["coingecko", "defillama"],
        tree=DataTree.INTEL,
        weight=0.90,
        description="Fund portfolio companies"
    ),
    
    # ─────────────────────────────────────────────────────────────
    # PERSON / TEAM / FOUNDERS
    # ─────────────────────────────────────────────────────────────
    FieldOwnership(
        field="founders",
        owner="rootdata",
        fallback=["cryptorank", "github", "linkedin", "twitter"],
        forbidden=["coingecko", "coinmarketcap", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.90,
        description="Project founders"
    ),
    FieldOwnership(
        field="team_members",
        owner="rootdata",
        fallback=["linkedin", "github"],
        forbidden=["coingecko", "cryptorank"],
        tree=DataTree.INTEL,
        weight=0.90,
        description="Team member profiles"
    ),
    FieldOwnership(
        field="advisors",
        owner="rootdata",
        fallback=["cryptorank", "linkedin"],
        forbidden=["coingecko", "coinmarketcap"],
        tree=DataTree.INTEL,
        weight=0.90,
        description="Project advisors"
    ),
    FieldOwnership(
        field="person_positions",
        owner="linkedin",
        fallback=["rootdata", "github", "twitter"],
        forbidden=["coingecko", "cryptorank"],
        tree=DataTree.INTEL,
        weight=0.85,
        description="Person's work history"
    ),
    FieldOwnership(
        field="worked_at",
        owner="linkedin",
        fallback=["rootdata", "github", "twitter"],
        forbidden=["coingecko", "cryptorank"],
        tree=DataTree.INTEL,
        weight=0.85,
        description="Previous positions"
    ),
    
    # ─────────────────────────────────────────────────────────────
    # PROJECT / PROTOCOL / DEFI
    # ─────────────────────────────────────────────────────────────
    FieldOwnership(
        field="tvl",
        owner="defillama",
        fallback=[],
        forbidden=["coingecko", "cryptorank", "dropstab"],
        tree=DataTree.INTEL,
        weight=0.92,
        description="Total Value Locked - ONLY DefiLlama"
    ),
    FieldOwnership(
        field="protocols",
        owner="defillama",
        fallback=["dappradar"],
        forbidden=["coingecko", "cryptorank"],
        tree=DataTree.INTEL,
        weight=0.92,
        description="Protocol data"
    ),
    FieldOwnership(
        field="chains",
        owner="defillama",
        fallback=["dappradar"],
        forbidden=["coingecko", "cryptorank"],
        tree=DataTree.INTEL,
        weight=0.92,
        description="Blockchain/chain data"
    ),
    FieldOwnership(
        field="defi_categories",
        owner="defillama",
        fallback=["dappradar"],
        forbidden=["coingecko", "cryptorank"],
        tree=DataTree.INTEL,
        weight=0.92,
        description="DeFi category classification"
    ),
    FieldOwnership(
        field="project_category",
        owner="defillama",
        fallback=["coingecko", "messari", "dappradar"],
        forbidden=["cryptorank"],
        tree=DataTree.INTEL,
        weight=0.90,
        description="Project category"
    ),
    FieldOwnership(
        field="ecosystem_type",
        owner="defillama",
        fallback=["coingecko", "messari", "dappradar"],
        forbidden=["cryptorank"],
        tree=DataTree.INTEL,
        weight=0.90,
        description="Ecosystem classification"
    ),
    FieldOwnership(
        field="project_description",
        owner="messari",
        fallback=["coingecko"],
        forbidden=["cryptorank", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.70,
        description="Project description text"
    ),
    FieldOwnership(
        field="official_links",
        owner="coingecko",
        fallback=["messari"],
        forbidden=["cryptorank"],
        tree=DataTree.INTEL,
        weight=0.88,
        description="Official project links"
    ),
    
    # ─────────────────────────────────────────────────────────────
    # ACTIVITIES / AIRDROPS / CAMPAIGNS
    # ─────────────────────────────────────────────────────────────
    FieldOwnership(
        field="airdrop_campaigns",
        owner="dropsearn",
        fallback=["airdropalert", "dappradar"],
        forbidden=["coingecko", "cryptorank", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.85,
        description="Active airdrop campaigns"
    ),
    FieldOwnership(
        field="ico_sale",
        owner="icodrops",
        fallback=["cryptorank"],
        forbidden=["coingecko", "defillama"],
        tree=DataTree.INTEL,
        weight=0.80,
        description="ICO/token sale info"
    ),
    FieldOwnership(
        field="launch",
        owner="icodrops",
        fallback=["cryptorank"],
        forbidden=["coingecko", "defillama"],
        tree=DataTree.INTEL,
        weight=0.80,
        description="Project launch info"
    ),
    FieldOwnership(
        field="ecosystem_activities",
        owner="dropsearn",
        fallback=["dappradar", "airdropalert"],
        forbidden=["coingecko", "cryptorank"],
        tree=DataTree.INTEL,
        weight=0.85,
        description="Ecosystem activities/quests"
    ),
    
    # ─────────────────────────────────────────────────────────────
    # RESEARCH / OPTIONAL
    # ─────────────────────────────────────────────────────────────
    FieldOwnership(
        field="deep_research",
        owner="messari",
        fallback=[],
        forbidden=["coingecko", "cryptorank", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.70,
        description="Deep research content - optional"
    ),
    FieldOwnership(
        field="thesis",
        owner="messari",
        fallback=[],
        forbidden=["coingecko", "cryptorank", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.70,
        description="Investment thesis - optional"
    ),
    FieldOwnership(
        field="tokenomics_notes",
        owner="messari",
        fallback=[],
        forbidden=["coingecko", "cryptorank", "exchange_providers"],
        tree=DataTree.INTEL,
        weight=0.70,
        description="Tokenomics analysis notes - optional"
    ),
]


# Combine all fields
ALL_FIELDS = EXCHANGE_FIELDS + INTEL_FIELDS


# ═══════════════════════════════════════════════════════════════
# PROVIDER CAPABILITY MAP
# ═══════════════════════════════════════════════════════════════

PROVIDER_CAPABILITIES = {
    # ─────────────────────────────────────────────────────────────
    # TIER 1: CORE INTEL
    # ─────────────────────────────────────────────────────────────
    "cryptorank": {
        "domain": "funding",
        "weight": 0.95,
        "priority_score": 100,
        "tier": 1,
        "owns": ["funding_rounds", "funding_amount", "investor_list", "lead_investor"],
        "can_provide": ["team_members", "ico_calendar", "unlocks"],
        "forbidden_for": ["tvl", "spot_price", "ohlcv", "market_cap"]
    },
    "rootdata": {
        "domain": "funding",
        "weight": 0.90,
        "priority_score": 95,
        "tier": 1,
        "owns": ["fund_profile", "fund_portfolio", "founders", "team_members", "advisors"],
        "can_provide": ["funding_rounds", "investor_list"],
        "forbidden_for": ["tvl", "spot_price", "ohlcv", "market_cap"]
    },
    "defillama": {
        "domain": "defi",
        "weight": 0.92,
        "priority_score": 90,
        "tier": 1,
        "owns": ["tvl", "protocols", "chains", "defi_categories"],
        "can_provide": ["project_category", "ecosystem_type"],
        "forbidden_for": ["funding_rounds", "investor_list", "spot_price", "ohlcv"]
    },
    "dropstab": {
        "domain": "tokenomics",
        "weight": 0.85,
        "priority_score": 85,
        "tier": 1,
        "owns": ["token_allocations", "vesting_model", "insider_supply", "sell_pressure"],
        "can_provide": ["unlock_schedule", "fdv", "circulating_supply"],
        "forbidden_for": ["tvl", "spot_price", "ohlcv", "funding_rounds"]
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER 2: MARKET / TOKEN
    # ─────────────────────────────────────────────────────────────
    "coingecko": {
        "domain": "market",
        "weight": 0.88,
        "priority_score": 80,
        "tier": 2,
        "owns": ["market_cap", "fdv", "circulating_supply", "total_supply", "official_links"],
        "can_provide": ["spot_price", "ohlcv", "exchange_markets", "trading_pairs"],
        "forbidden_for": ["tvl", "funding_rounds", "investor_list", "team_members"]
    },
    "coinmarketcap": {
        "domain": "market",
        "weight": 0.85,
        "priority_score": 75,
        "tier": 2,
        "owns": [],
        "can_provide": ["market_cap", "fdv", "circulating_supply", "spot_price", "exchange_markets"],
        "forbidden_for": ["tvl", "funding_rounds", "investor_list", "team_members"]
    },
    "tokenunlocks": {
        "domain": "tokenomics",
        "weight": 0.93,
        "priority_score": 70,
        "tier": 2,
        "owns": ["unlock_schedule", "unlock_amount_usd", "unlock_percent"],
        "can_provide": ["vesting_model"],
        "forbidden_for": ["tvl", "spot_price", "funding_rounds", "investor_list"]
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER 3: ACTIVITIES
    # ─────────────────────────────────────────────────────────────
    "dropsearn": {
        "domain": "activities",
        "weight": 0.85,
        "priority_score": 60,
        "tier": 3,
        "owns": ["airdrop_campaigns", "ecosystem_activities"],
        "can_provide": ["testnets", "quests"],
        "forbidden_for": ["tvl", "spot_price", "funding_rounds"]
    },
    "icodrops": {
        "domain": "ico",
        "weight": 0.80,
        "priority_score": 55,
        "tier": 3,
        "owns": ["ico_sale", "launch"],
        "can_provide": ["token_allocations"],
        "forbidden_for": ["tvl", "spot_price", "funding_rounds"]
    },
    "dappradar": {
        "domain": "dapps",
        "weight": 0.78,
        "priority_score": 50,
        "tier": 3,
        "owns": [],
        "can_provide": ["protocols", "defi_categories", "ecosystem_activities"],
        "forbidden_for": ["tvl", "spot_price", "funding_rounds", "investor_list"]
    },
    "airdropalert": {
        "domain": "activities",
        "weight": 0.75,
        "priority_score": 45,
        "tier": 3,
        "owns": [],
        "can_provide": ["airdrop_campaigns"],
        "forbidden_for": ["tvl", "spot_price", "funding_rounds", "market_cap"]
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER 4: RESEARCH (optional)
    # ─────────────────────────────────────────────────────────────
    "messari": {
        "domain": "research",
        "weight": 0.70,
        "priority_score": 30,
        "tier": 4,
        "owns": ["deep_research", "thesis", "tokenomics_notes", "project_description"],
        "can_provide": ["token_allocations", "vesting_model"],
        "forbidden_for": ["tvl", "spot_price", "funding_rounds", "investor_list", "market_cap"]
    },
    
    # ─────────────────────────────────────────────────────────────
    # PERSON DATA
    # ─────────────────────────────────────────────────────────────
    "linkedin": {
        "domain": "persons",
        "weight": 0.85,
        "priority_score": 25,
        "tier": 4,
        "owns": ["person_positions", "worked_at"],
        "can_provide": ["team_members", "advisors"],
        "forbidden_for": ["tvl", "spot_price", "funding_rounds", "market_cap"]
    },
    "github": {
        "domain": "persons",
        "weight": 0.80,
        "priority_score": 42,
        "tier": 3,
        "owns": [],
        "can_provide": ["developer_activity", "contributors", "team_members"],
        "forbidden_for": ["tvl", "spot_price", "funding_rounds", "market_cap"]
    },
    "twitter": {
        "domain": "persons",
        "weight": 0.75,
        "priority_score": 40,
        "tier": 3,
        "owns": [],
        "can_provide": ["social_presence", "followers"],
        "forbidden_for": ["tvl", "spot_price", "funding_rounds", "market_cap"]
    },
    
    # ─────────────────────────────────────────────────────────────
    # EXCHANGE PROVIDERS (separate tree)
    # ─────────────────────────────────────────────────────────────
    "exchange_providers": {
        "domain": "market",
        "weight": 1.0,
        "priority_score": 100,
        "tier": 0,  # Separate tree
        "tree": "exchange",
        "owns": ["spot_price", "ohlcv", "candles", "spot_volume", "pair_volume", 
                 "open_interest", "funding_rate", "liquidations", 
                 "exchange_markets", "trading_pairs", "listed_on"],
        "can_provide": [],
        "forbidden_for": ["tvl", "funding_rounds", "investor_list", "team_members", 
                         "token_allocations", "unlock_schedule"]
    }
}


# ═══════════════════════════════════════════════════════════════
# SOURCE WEIGHT TABLE (for aggregation)
# ═══════════════════════════════════════════════════════════════

SOURCE_WEIGHTS = {
    # TIER 1
    "cryptorank": 0.95,
    "rootdata": 0.90,
    "defillama": 0.92,
    "dropstab": 0.85,
    
    # TIER 2
    "coingecko": 0.88,
    "coinmarketcap": 0.85,
    "tokenunlocks": 0.93,
    
    # TIER 3
    "dropsearn": 0.85,
    "icodrops": 0.80,
    "dappradar": 0.78,
    "airdropalert": 0.75,
    "github": 0.80,
    "twitter": 0.75,
    
    # TIER 4
    "messari": 0.70,
    "linkedin": 0.85,
    
    # Exchange providers always 1.0 for their domain
    "exchange_providers": 1.0
}


class FieldOwnershipRegistry:
    """
    Registry for field ownership lookup and validation
    """
    
    def __init__(self):
        self._field_map = {f.field: f for f in ALL_FIELDS}
        self._provider_map = PROVIDER_CAPABILITIES
    
    def get_owner(self, field: str) -> Optional[str]:
        """Get owner source for a field"""
        if field in self._field_map:
            return self._field_map[field].owner
        return None
    
    def get_fallback(self, field: str) -> List[str]:
        """Get fallback sources for a field"""
        if field in self._field_map:
            return self._field_map[field].fallback
        return []
    
    def is_forbidden(self, field: str, source: str) -> bool:
        """Check if source is forbidden for this field"""
        if field in self._field_map:
            return source in self._field_map[field].forbidden
        return False
    
    def get_tree(self, field: str) -> Optional[DataTree]:
        """Get which data tree owns this field"""
        if field in self._field_map:
            return self._field_map[field].tree
        return None
    
    def get_provider_capabilities(self, provider: str) -> Dict:
        """Get capabilities for a provider"""
        return self._provider_map.get(provider, {})
    
    def get_providers_for_field(self, field: str) -> List[str]:
        """Get all providers that can provide this field (owner + fallback)"""
        if field not in self._field_map:
            return []
        
        ownership = self._field_map[field]
        providers = [ownership.owner]
        providers.extend(ownership.fallback)
        return providers
    
    def validate_source_for_field(self, field: str, source: str) -> bool:
        """Validate if source can be used for this field"""
        if self.is_forbidden(field, source):
            return False
        
        owner = self.get_owner(field)
        fallback = self.get_fallback(field)
        
        return source == owner or source in fallback
    
    def weighted_merge(self, field: str, values: Dict[str, Any]) -> Any:
        """
        Merge values from multiple sources using weighted average
        values: {source_id: value}
        """
        if not values:
            return None
        
        # Filter only valid sources
        valid_values = {
            src: val for src, val in values.items() 
            if self.validate_source_for_field(field, src)
        }
        
        if not valid_values:
            return None
        
        # If only one value, return it
        if len(valid_values) == 1:
            return list(valid_values.values())[0]
        
        # Check if values are numeric for weighted average
        first_val = list(valid_values.values())[0]
        if isinstance(first_val, (int, float)):
            total_weight = 0
            weighted_sum = 0
            for src, val in valid_values.items():
                weight = SOURCE_WEIGHTS.get(src, 0.5)
                weighted_sum += val * weight
                total_weight += weight
            return weighted_sum / total_weight if total_weight > 0 else None
        
        # For non-numeric, return value from highest priority source
        best_source = None
        best_score = -1
        for src in valid_values:
            caps = self._provider_map.get(src, {})
            score = caps.get("priority_score", 0)
            if score > best_score:
                best_score = score
                best_source = src
        
        return valid_values.get(best_source)


# Singleton instance
field_registry = FieldOwnershipRegistry()
