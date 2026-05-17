"""
Standardized On-Chain Drivers
==============================
Used by entity_intelligence signals and Alpha Layer.
"""

# Exchange Drivers
CEX_INFLOW = "cex_inflow"
CEX_OUTFLOW = "cex_outflow"
EXCHANGE_REBALANCE = "exchange_rebalance"

# Whale Drivers
WHALE_TRANSFER = "whale_transfer"
WHALE_ACCUMULATION = "whale_accumulation"
WHALE_DISTRIBUTION = "whale_distribution"

# Entity Drivers
FUND_ACTIVITY = "fund_activity"
MM_ACTIVITY = "mm_activity"
SMART_MONEY_FLOW = "smart_money_flow"

# Structural Drivers
CLUSTER_ACTIVITY = "cluster_activity"
ENTITY_SPIKE = "entity_spike"
CROSS_EXCHANGE_FLOW = "cross_exchange_flow"

# Token Drivers
TOKEN_TRANSFER = "token_transfer"
TOKEN_ACCUMULATION = "token_accumulation"

# Discovery Drivers (Sprint 2)
SMART_MONEY_ACCUMULATION = "smart_money_accumulation"
SMART_MONEY_DISTRIBUTION = "smart_money_distribution"

# Driver metadata for UI
DRIVER_META = {
    CEX_INFLOW: {"label": "Exchange Inflow", "category": "exchange", "bearish_bias": True},
    CEX_OUTFLOW: {"label": "Exchange Outflow", "category": "exchange", "bearish_bias": False},
    EXCHANGE_REBALANCE: {"label": "Exchange Rebalance", "category": "exchange", "bearish_bias": None},
    WHALE_TRANSFER: {"label": "Whale Transfer", "category": "whale", "bearish_bias": None},
    WHALE_ACCUMULATION: {"label": "Whale Accumulation", "category": "whale", "bearish_bias": False},
    WHALE_DISTRIBUTION: {"label": "Whale Distribution", "category": "whale", "bearish_bias": True},
    FUND_ACTIVITY: {"label": "Fund Activity", "category": "entity", "bearish_bias": None},
    MM_ACTIVITY: {"label": "Market Maker Activity", "category": "entity", "bearish_bias": None},
    SMART_MONEY_FLOW: {"label": "Smart Money Flow", "category": "entity", "bearish_bias": None},
    CLUSTER_ACTIVITY: {"label": "Cluster Activity", "category": "structural", "bearish_bias": None},
    ENTITY_SPIKE: {"label": "Entity Activity Spike", "category": "structural", "bearish_bias": None},
    CROSS_EXCHANGE_FLOW: {"label": "Cross-Exchange Flow", "category": "structural", "bearish_bias": None},
    SMART_MONEY_ACCUMULATION: {"label": "Smart Money Accumulation", "category": "discovery", "bearish_bias": False},
    SMART_MONEY_DISTRIBUTION: {"label": "Smart Money Distribution", "category": "discovery", "bearish_bias": True},
}

CHAIN_EXPLORERS = {
    "ethereum": "https://etherscan.io",
    "arbitrum": "https://arbiscan.io",
    "optimism": "https://optimistic.etherscan.io",
    "base": "https://basescan.org",
}

CHAIN_LABELS = {
    "ethereum": "ETH",
    "arbitrum": "ARB",
    "optimism": "OP",
    "base": "BASE",
}
